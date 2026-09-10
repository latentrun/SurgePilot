"""P0-04 Run state machine, node lease, run snapshot, and artifact services.

This module implements the single-node P0 Run execution contract from
``docs/sdd/slices/P0-04-run-state-machine-runner-protocol.md``:

- Atomic Run + Run Snapshot shell + node lease acquisition for already-validated
  execution input, with the Load Node moved to ``busy`` only after the lease is
  acquired.
- Run state machine transitions with terminal-state protection and idempotent
  Runner callback handling keyed by ``(runId, eventId)`` plus payload hash.
- Node lease release and node status convergence on terminal callbacks and
  cleanup outcomes.
- Runner artifact upload metadata and MinIO write path without exposing MinIO
  credentials or object keys to the Runner.
- Worker-facing run-control job processing (claim, command build, and
  completion), timeout sweeps, stale lease recovery, and Runner callback
  retention cleanup driven by the ``api-worker``.

State transitions are applied in the caller's transaction through conditional
updates: the Run row is locked with ``FOR UPDATE`` first, so late, duplicate, or
illegal Runner callbacks are recorded but never overwrite terminal state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import logging
import re
from typing import Any, BinaryIO

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ids import is_ulid, new_ulid
from app.core.time import as_utc, utc_now
from app.models.auth import User
from app.models.load_nodes import LoadNode
from app.models.runs import (
    RUN_ARTIFACT_TYPES,
    TERMINAL_RUN_STATES,
    NodeLease,
    Run,
    RunArtifact,
    RunControlRequest,
    RunnerCallbackEvent,
    RunNodeAllocation,
    RunSnapshot,
)
from app.services.audit import write_audit_event
from app.services.debug_http_trace import (
    DEBUG_HTTP_BODY_BLOB_ARTIFACT_TYPE,
    DEBUG_HTTP_TRACE_ARTIFACT_TYPE,
    DEBUG_HTTP_TRACE_RELATIVE_PATH,
)
from app.services.load_nodes import visible_node_filters
from app.services.storage import get_storage_client

RUN_TRANSITIONS: dict[str, set[str]] = {
    "running": {"initializing"},
    "stopping": {"initializing", "running"},
    "finished": {"running"},
    "failed": {"initializing", "running", "stopping"},
    "aborted": {"initializing", "running", "stopping"},
}
TERMINAL_STATES = set(TERMINAL_RUN_STATES)
ACTIVE_CONTROL_STATUSES = {"pending", "running"}
SAFE_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
MAX_SAFE_MESSAGE = 500
CALLBACK_MAX_SANITIZE_DEPTH = 8
REDACTED = "[REDACTED]"
SENSITIVE_DETAIL_KEYS = (
    "authorization",
    "csrf",
    "credential",
    "password",
    "passphrase",
    "api_key",
    "private_key",
    "secret",
    "token",
)
SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)\b(bearer\s+[A-Za-z0-9._~+/=-]+|basic\s+[A-Za-z0-9+/=-]+|token[:=]\S+|password[:=]\S+)"
)
logger = logging.getLogger(__name__)
NODE_BOUND_TOKEN_PREFIX = "node:"


@dataclass(frozen=True)
class CallbackResult:
    accepted: bool
    duplicate: bool
    state_changed: bool
    current_state: str
    ignored_reason: str | None = None


@dataclass(frozen=True)
class StopResult:
    run_id: str
    state: str
    stop_requested_at: datetime | None
    duplicate: bool
    status_code: int


@dataclass(frozen=True)
class RunnerCallbackInput:
    schema_version: str
    event_id: str
    run_id: str
    node_id: str
    runtime_version: str
    event_type: str
    seq: int
    event_time: datetime
    message: str | None = None
    runner_pid: int | None = None
    details: dict[str, Any] | None = None
    raw_payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class ArtifactResult:
    artifact_id: str
    duplicate: bool


@dataclass(frozen=True)
class RunExecutionInput:
    workspace_id: str
    actor: User
    selected_node_id: str
    run_type: str
    source_type: str
    source_id: str | None
    snapshot_payload: dict[str, Any]
    selected_node_ids: tuple[str, ...] = ()
    resource_mode: str = "manual"
    pool_type: str | None = None
    node_count: int | None = None


@dataclass(frozen=True)
class RunControlCommand:
    """One remote command the ``api-worker`` executes on the bound Load Node."""

    request_id: str
    action: str
    run_id: str
    node_id: str
    reason: str | None
    source_type: str
    host: str
    ssh_port: int
    ssh_user: str
    runner_home: str
    trusted_host_key_algorithm: str
    trusted_host_key_public_key: str
    trusted_host_key_fingerprint_sha256: str
    argv: tuple[str, ...]


@dataclass(frozen=True)
class RunControlExecutionResult:
    """Outcome of one remote run-control execution."""

    ok: bool
    error_code: str | None = None
    message: str | None = None
    stderr_preview: str | None = None
    timed_out: bool = False
    quarantine_node: bool = True
    cleanup_required: bool = False


class RunControlExecutor:
    """Boundary implemented by the ``api-worker`` remote SSH executor."""

    def execute(self, command: RunControlCommand) -> RunControlExecutionResult:
        raise NotImplementedError


class FakeRunControlExecutor(RunControlExecutor):
    def execute(self, command: RunControlCommand) -> RunControlExecutionResult:
        _ = command
        return RunControlExecutionResult(ok=True)


def _runner_command_argv(
    *, runner_home: str, action: str, run_id: str, use_fake_runner: bool = False
) -> tuple[str, ...]:
    command = "kill" if action == "force_kill" else action
    argv = ("python3", f"{runner_home.rstrip('/')}/runner.py", command, "--run-id", run_id)
    if action == "start" and use_fake_runner:
        return (*argv, "--fake")
    return argv


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_hash(payload: dict[str, Any]) -> str:
    return _canonical_hash(payload)


def _safe_message(value: str | None, default: str) -> str:
    text = (value or default).strip() or default
    return text[:MAX_SAFE_MESSAGE]


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    compact = normalized.replace("_", "")
    return any(
        marker in normalized or marker.replace("_", "") in compact
        for marker in SENSITIVE_DETAIL_KEYS
    )


def _sanitize_callback_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= CALLBACK_MAX_SANITIZE_DEPTH:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                sanitized[key_text] = REDACTED
            else:
                sanitized[key_text] = _sanitize_callback_value(item, depth=depth + 1)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_callback_value(item, depth=depth + 1) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_callback_value(item, depth=depth + 1) for item in value]
    if isinstance(value, str) and SENSITIVE_VALUE_PATTERN.search(value):
        return SENSITIVE_VALUE_PATTERN.sub(REDACTED, value)
    return value


def _sanitize_callback_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_callback_value(payload)
    return sanitized if isinstance(sanitized, dict) else {}


def _lock_run(db: Session, run_id: str) -> Run:
    run = db.scalar(
        select(Run)
        .where(Run.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    return run


def _active_lease(
    db: Session, *, run_id: str | None = None, node_id: str | None = None
) -> NodeLease | None:
    conditions = [NodeLease.released_at.is_(None)]
    if run_id is not None:
        conditions.append(NodeLease.run_id == run_id)
    if node_id is not None:
        conditions.append(NodeLease.node_id == node_id)
    return db.scalar(select(NodeLease).where(*conditions).with_for_update())


def enqueue_control_request(
    db: Session,
    *,
    run: Run,
    action: str,
    reason: str | None = None,
    run_after: datetime | None = None,
    allocation: RunNodeAllocation | None = None,
) -> RunControlRequest:
    existing = db.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id,
            RunControlRequest.action == action,
            *([RunControlRequest.node_id == allocation.node_id] if allocation else []),
            RunControlRequest.status.in_(list(ACTIVE_CONTROL_STATUSES)),
        )
    )
    if existing is not None:
        return existing
    now = utc_now()
    request = RunControlRequest(
        id=new_ulid(),
        workspace_id=run.workspace_id,
        run_id=run.id,
        allocation_id=allocation.id if allocation else None,
        node_id=allocation.node_id if allocation else run.selected_node_id,
        action=action,
        reason=reason,
        status="pending",
        run_after=run_after or now,
        attempt_count=0,
        created_at=now,
        updated_at=now,
    )
    db.add(request)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError("RUN_CONTROL_CONFLICT", "Run control request already exists.", 409)
    return request


def _allocation_for_node(db: Session, *, run_id: str, node_id: str) -> RunNodeAllocation | None:
    return db.scalar(
        select(RunNodeAllocation)
        .where(RunNodeAllocation.run_id == run_id, RunNodeAllocation.node_id == node_id)
        .with_for_update()
    )


def _validate_authenticated_runner_node(
    *,
    authenticated_node_id: str | None,
    payload_node_id: str,
    allocation: RunNodeAllocation | None,
) -> None:
    if authenticated_node_id is None or authenticated_node_id != payload_node_id:
        raise AppError("RUNNER_FORBIDDEN", "Runner is not allowed to report this node.", 403)
    if allocation is None:
        raise AppError("RUNNER_FORBIDDEN", "Runner is not allowed to report this Run.", 403)


def _allocations_for_run(db: Session, *, run_id: str) -> list[RunNodeAllocation]:
    return list(
        db.scalars(
            select(RunNodeAllocation)
            .where(RunNodeAllocation.run_id == run_id)
            .order_by(RunNodeAllocation.node_index.asc())
            .with_for_update()
        ).all()
    )


def _derive_run_terminal_from_allocations(
    db: Session, *, run: Run, allocations: list[RunNodeAllocation], now: datetime
) -> bool:
    if not allocations or any(allocation.state not in TERMINAL_STATES for allocation in allocations):
        return False
    if any(allocation.state == "failed" for allocation in allocations):
        target = "failed"
    elif any(allocation.state == "aborted" for allocation in allocations):
        target = "aborted"
    else:
        target = "finished"
    if run.state not in TERMINAL_STATES:
        failed = next((a for a in allocations if a.state == "failed"), None)
        if not _apply_transition(
            db,
            run=run,
            new_state=target,
            reason=failed.terminal_reason if failed else None,
            message=failed.terminal_message if failed else None,
            now=now,
        ):
            return False
    if run.run_type == "standard":
        snapshot = db.scalar(select(RunSnapshot).where(RunSnapshot.run_id == run.id))
        snapshot_json = snapshot.snapshot_json if snapshot is not None else {}
        rules = snapshot_json.get("slaRules", []) if isinstance(snapshot_json, dict) else []
        enabled_rules = [r for r in rules if isinstance(r, dict) and r.get("enabled", True)]
        if snapshot_json.get("slaEvaluationMode") == "passfail" and enabled_rules:
            verdicts = [allocation.sla_result for allocation in allocations]
            if any(verdict == "failed" for verdict in verdicts):
                run.sla_result = "failed"
                run.sla_result_reason = "node_sla_failed"
            elif all(verdict == "passed" for verdict in verdicts):
                run.sla_result = "passed"
                run.sla_result_reason = None
            else:
                run.sla_result = "not_evaluated"
                run.sla_result_reason = "missing_sla_result"
    db.flush()
    return True


def _enqueue_cleanup_for_non_terminal_siblings(
    db: Session,
    *,
    run: Run,
    failed_allocation: RunNodeAllocation,
    reason: str,
    now: datetime,
) -> None:
    for allocation in _allocations_for_run(db, run_id=run.id):
        if allocation.id == failed_allocation.id or allocation.state in TERMINAL_STATES:
            continue
        enqueue_control_request(
            db,
            run=run,
            action="force_kill",
            reason=reason,
            run_after=now,
            allocation=allocation,
        )


def _validate_selected_node(
    db: Session, *, execution: RunExecutionInput, now: datetime
) -> LoadNode:
    node = db.scalar(
        select(LoadNode)
        .where(
            LoadNode.id == execution.selected_node_id,
            LoadNode.archived_at.is_(None),
            visible_node_filters(workspace_id=execution.workspace_id),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if node is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    if node.status != "idle" or _active_lease(db, node_id=node.id) is not None:
        raise AppError("LOAD_NODE_BUSY", "Load Node is busy.", 409)
    if node.last_force_kill_at is not None and as_utc(node.last_force_kill_at) > now - timedelta(
        seconds=get_settings().node_cooldown_seconds
    ):
        raise AppError("LOAD_NODE_ACTION_NOT_ALLOWED", "Load Node is cooling down.", 409)
    return node


def _requested_node_ids(db: Session, *, execution: RunExecutionInput) -> list[str]:
    explicit = list(execution.selected_node_ids or ())
    if not explicit and execution.selected_node_id:
        explicit = [execution.selected_node_id]
    if execution.resource_mode == "manual":
        if not explicit or len(set(explicit)) != len(explicit):
            raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
        return explicit
    if execution.resource_mode != "auto" or not execution.node_count or execution.pool_type not in {"public", "private"}:
        raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
    query = select(LoadNode).where(
        LoadNode.archived_at.is_(None),
        LoadNode.status == "idle",
        visible_node_filters(workspace_id=execution.workspace_id),
        LoadNode.scope == "public" if execution.pool_type == "public" else and_(LoadNode.scope == "workspace", LoadNode.workspace_id == execution.workspace_id),
    )
    runtime_version = get_settings().load_node_runtime_version
    if runtime_version:
        query = query.where(LoadNode.runtime_version == runtime_version)
    nodes = db.scalars(
        query
        .order_by(LoadNode.created_at.asc(), LoadNode.id.asc())
        .with_for_update()
    ).all()
    available = [node for node in nodes if _active_lease(db, node_id=node.id) is None]
    if len(available) < execution.node_count:
        raise AppError("LOAD_NODE_CAPACITY_UNAVAILABLE", "Not enough Load Nodes are available.", 409)
    return [node.id for node in available[: execution.node_count]]


def _validate_nodes_for_allocation(
    db: Session, *, execution: RunExecutionInput, node_ids: list[str], now: datetime
) -> list[LoadNode]:
    nodes = db.scalars(
        select(LoadNode).where(LoadNode.id.in_(node_ids)).with_for_update()
    ).all()
    by_id = {node.id: node for node in nodes}
    result: list[LoadNode] = []
    for node_id in node_ids:
        node = by_id.get(node_id)
        visible = node is not None and (
            node.scope == "public" or node.workspace_id == execution.workspace_id
        )
        in_pool = execution.pool_type is None or (
            execution.pool_type == "public" and node is not None and node.scope == "public"
        ) or (
            execution.pool_type == "private" and node is not None
            and node.scope == "workspace" and node.workspace_id == execution.workspace_id
        )
        if node is None or node.archived_at is not None or not visible or not in_pool:
            raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
        if node.status != "idle" or _active_lease(db, node_id=node.id) is not None:
            raise AppError("LOAD_NODE_UNAVAILABLE" if len(node_ids) > 1 else "LOAD_NODE_BUSY", "Load Node is unavailable." if len(node_ids) > 1 else "Load Node is busy.", 409)
        if get_settings().load_node_runtime_version and node.runtime_version != get_settings().load_node_runtime_version:
            raise AppError("LOAD_NODE_UNAVAILABLE", "Load Node is unavailable.", 409)
        if node.last_force_kill_at is not None and as_utc(node.last_force_kill_at) > now - timedelta(seconds=get_settings().node_cooldown_seconds):
            raise AppError("LOAD_NODE_ACTION_NOT_ALLOWED", "Load Node is cooling down.", 409)
        result.append(node)
    return result


def create_run_execution(db: Session, execution: RunExecutionInput) -> Run:
    """Atomically create a Run, Run Snapshot shell, node lease, and Busy node.

    The caller owns the surrounding transaction. DB work never executes SSH,
    SFTP, remote shell commands, or MinIO operations here. A ``start``
    ``run_control_requests`` row is enqueued so a later ``api-worker`` claim
    performs the remote start.
    """
    if execution.source_type == "protocol_smoke" and not get_settings().enable_protocol_smoke_runs:
        raise AppError("RUN_CREATION_NOT_ALLOWED", "Protocol smoke Runs are disabled.", 403)
    now = utc_now()
    node_ids = _requested_node_ids(db, execution=execution)
    if execution.run_type == "debug" and len(node_ids) != 1:
        raise AppError("RESOURCE_REQUEST_INVALID", "Debug Runs support one Load Node only.", 422)
    nodes = _validate_nodes_for_allocation(db, execution=execution, node_ids=node_ids, now=now)
    node = nodes[0]

    run = Run(
        id=new_ulid(),
        workspace_id=execution.workspace_id,
        run_type=execution.run_type,
        state="initializing",
        source_type=execution.source_type,
        source_id=execution.source_id,
        selected_node_id=node.id,
        triggered_by_user_id=execution.actor.id,
        forced_convergence=False,
        remote_start_requested_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(run)
    # LoadNode.current_run_id is an ALTERed FK without an ORM relationship, so
    # PostgreSQL can otherwise flush LoadNode updates before the Run insert.
    # Keep this inside the caller's transaction; any later lease/control-request
    # failure still rolls back the Run with the rest of the unit of work.
    db.flush([run])

    snapshot_payload = dict(execution.snapshot_payload)
    snapshot_payload.setdefault("protocolSchemaVersion", 1)
    snapshot_payload["runType"] = run.run_type
    snapshot_payload["sourceType"] = run.source_type
    snapshot_payload["allocatedNodeIds"] = [allocated_node.id for allocated_node in nodes]
    if execution.source_id is None:
        snapshot_payload.pop("sourceId", None)
    else:
        snapshot_payload["sourceId"] = execution.source_id
    snapshot_payload.setdefault(
        "selectedNode",
        {
            "id": node.id,
            "scope": node.scope,
            "workspaceId": node.workspace_id,
            "host": node.host,
            "sshPort": node.ssh_port,
            "sshUser": node.ssh_user,
            "runnerHome": node.runner_home,
        },
    )
    snapshot_payload.setdefault("actorId", execution.actor.id)
    snapshot_payload.setdefault("createdAt", now.isoformat().replace("+00:00", "Z"))
    snapshot = RunSnapshot(
        id=new_ulid(),
        workspace_id=execution.workspace_id,
        run_id=run.id,
        snapshot_version=1,
        snapshot_hash=_snapshot_hash(snapshot_payload),
        snapshot_json=snapshot_payload,
        created_at=now,
    )
    db.add(snapshot)
    allocations: list[RunNodeAllocation] = []
    requests: list[RunControlRequest] = []
    for index, allocated_node in enumerate(nodes, start=1):
        allocation = RunNodeAllocation(
            id=new_ulid(), workspace_id=execution.workspace_id, run_id=run.id,
            node_id=allocated_node.id, node_index=index, total_nodes=len(nodes),
            expected_runtime_version=allocated_node.runtime_version,
            state="initializing", sla_result="not_evaluated", created_at=now, updated_at=now,
        )
        allocations.append(allocation)
        db.add(NodeLease(
            id=new_ulid(), workspace_id=execution.workspace_id, node_id=allocated_node.id,
            run_id=run.id, acquired_at=now, created_at=now, updated_at=now,
        ))
        allocated_node.status = "busy"
        allocated_node.current_run_id = run.id
        allocated_node.last_status_reason = None
        allocated_node.updated_at = now
        requests.append(RunControlRequest(
            id=new_ulid(), workspace_id=execution.workspace_id, run_id=run.id,
            allocation_id=allocation.id, node_id=allocated_node.id, action="start",
            reason=None, status="pending", run_after=now, attempt_count=0,
            created_at=now, updated_at=now,
        ))
        db.add(allocation)
    try:
        db.flush()
        db.add_all(requests)
        db.flush()
    except IntegrityError as exc:
        raise AppError("LOAD_NODE_UNAVAILABLE", "Load Node is unavailable.", 409) from exc
    from app.services.monitoring import create_run_monitoring_snapshot

    create_run_monitoring_snapshot(db, run=run)
    return run


def create_protocol_smoke_run(
    db: Session, *, workspace_id: str, actor: User, selected_node_id: str
) -> Run:
    """Create a protocol-smoke Run for tests, CI, and local dev helpers."""
    return create_run_execution(
        db,
        RunExecutionInput(
            workspace_id=workspace_id,
            actor=actor,
            selected_node_id=selected_node_id,
            run_type="debug",
            source_type="protocol_smoke",
            source_id=None,
            snapshot_payload={"protocolSchemaVersion": 1},
        ),
    )


def release_run_lease(
    db: Session,
    *,
    run: Run,
    reason: str,
    quarantine: bool = False,
    now: datetime | None = None,
    node_id: str | None = None,
    allocation: RunNodeAllocation | None = None,
) -> None:
    """Release the active node lease and converge node status.

    A terminal Run whose cleanup is proven safe releases the lease and returns
    the node to ``idle``. Cleanup failure, timeout, stale process detection, or
    inconsistent managed process state quarantines the node instead. Releasing a
    lease alone never makes a disabled/offline/quarantined node selectable.
    """
    at = now or utc_now()
    target_node_id = node_id or (allocation.node_id if allocation else None)
    conditions = [NodeLease.run_id == run.id, NodeLease.released_at.is_(None)]
    if target_node_id is not None:
        conditions.append(NodeLease.node_id == target_node_id)
    leases = list(db.scalars(select(NodeLease).where(*conditions).with_for_update()).all())
    for lease in leases:
        lease.released_at = at
        lease.release_reason = reason
        lease.updated_at = at
        node = db.scalar(select(LoadNode).where(LoadNode.id == lease.node_id).with_for_update())
        if node is not None:
            node.current_run_id = None
            if quarantine:
                node.status = "quarantined"
                node.last_status_reason = reason
                write_audit_event(
                    db,
                    event_type="load_node.quarantined",
                    actor_user_id=None,
                    workspace_id=run.workspace_id,
                    target_type="load_node",
                    target_id=node.id,
                    details={
                        "nodeId": node.id,
                        "runId": run.id,
                        "workspaceId": run.workspace_id,
                        "reason": reason,
                        "recoveryHint": (
                            "Manually confirm and clean residual processes, then disable, "
                            "enable, and reinitialize this Load Node."
                        ),
                    },
                )
            elif node.status == "busy":
                node.status = "idle"
                node.last_status_reason = None
            node.updated_at = at
    if allocation is not None:
        allocation.cleanup_status = "quarantined" if quarantine else "released"
        allocation.quarantine_reason = reason if quarantine else None
        allocation.updated_at = at
    db.flush()


def _apply_transition(
    db: Session,
    *,
    run: Run,
    new_state: str,
    reason: str | None = None,
    message: str | None = None,
    forced_convergence: bool = False,
    now: datetime | None = None,
) -> bool:
    at = now or utc_now()
    if run.state not in RUN_TRANSITIONS.get(new_state, set()):
        return False
    run.state = new_state
    run.updated_at = at
    if new_state == "running":
        run.started_at = at
    if new_state in TERMINAL_STATES:
        run.ended_at = at
        run.failure_reason = reason
        run.failure_message = (
            _safe_message(message, "Run reached a terminal state.") if reason else None
        )
        run.forced_convergence = forced_convergence
    db.flush()
    return True


def _callback_event_payload(callback: RunnerCallbackInput) -> tuple[dict[str, Any], str]:
    raw_payload = callback.raw_payload or {
        "schemaVersion": callback.schema_version,
        "eventId": callback.event_id,
        "runId": callback.run_id,
        "nodeId": callback.node_id,
        "runtimeVersion": callback.runtime_version,
        "eventType": callback.event_type,
        "seq": callback.seq,
        "eventTime": callback.event_time.isoformat().replace("+00:00", "Z"),
        "message": callback.message,
        "runnerPid": callback.runner_pid,
        "details": callback.details or {},
    }
    payload = _sanitize_callback_payload(raw_payload)
    return payload, _canonical_hash(payload)


def _record_callback_duplicate(
    db: Session,
    *,
    run: Run,
    callback: RunnerCallbackInput,
    payload_hash: str,
    now: datetime,
) -> RunnerCallbackEvent | None:
    existing = db.scalar(
        select(RunnerCallbackEvent).where(
            RunnerCallbackEvent.run_id == run.id,
            RunnerCallbackEvent.event_id == callback.event_id,
        )
    )
    if existing is None:
        return None
    if existing.payload_sha256 != payload_hash:
        raise AppError(
            "RUNNER_CALLBACK_CONFLICT",
            "Runner callback idempotency key was reused with a different payload.",
            409,
        )
    existing.duplicate_count += 1
    existing.last_duplicate_at = now
    db.flush()
    logger.info(
        "Runner callback duplicate ignored",
        extra={
            "run_id": run.id,
            "event_id": callback.event_id,
            "event_type": callback.event_type,
            "duplicate": True,
        },
    )
    return existing


def _store_callback_event(
    db: Session,
    *,
    run: Run,
    callback: RunnerCallbackInput,
    request_id: str,
    payload: dict[str, Any],
    payload_hash: str,
    now: datetime,
) -> RunnerCallbackEvent:
    event = RunnerCallbackEvent(
        id=new_ulid(),
        workspace_id=run.workspace_id,
        run_id=run.id,
        node_id=callback.node_id,
        event_id=callback.event_id,
        event_type=callback.event_type,
        seq=callback.seq,
        event_time=callback.event_time,
        received_at=now,
        request_id=request_id,
        payload_sha256=payload_hash,
        payload_json=payload,
        duplicate_count=0,
        created_at=now,
    )
    db.add(event)
    db.flush()
    return event


def apply_runner_callback(
    db: Session,
    *,
    callback: RunnerCallbackInput,
    request_id: str,
    authenticated_node_id: str | None = None,
) -> CallbackResult:
    """Store and apply one Runner callback for the Run state machine.

    Event receipt is stored before any state mutation. ``(runId, eventId)``
    idempotency uses the sanitized payload hash; the API ``receivedAt`` time is
    authoritative for state changes and Runner ``eventTime``/``seq`` are
    diagnostic only. Valid late callbacks are stored but cannot mutate terminal
    state.
    """
    run = _lock_run(db, callback.run_id)
    allocation = _allocation_for_node(db, run_id=run.id, node_id=callback.node_id)
    _validate_authenticated_runner_node(
        authenticated_node_id=authenticated_node_id,
        payload_node_id=callback.node_id,
        allocation=allocation,
    )
    payload, payload_hash = _callback_event_payload(callback)
    now = utc_now()
    duplicate_event = _record_callback_duplicate(
        db,
        run=run,
        callback=callback,
        payload_hash=payload_hash,
        now=now,
    )
    if duplicate_event is not None:
        return CallbackResult(True, True, False, run.state, duplicate_event.ignored_reason)
    event = _store_callback_event(
        db,
        run=run,
        callback=callback,
        request_id=request_id,
        payload=payload,
        payload_hash=payload_hash,
        now=now,
    )

    state_changed = False
    ignored_reason = None
    at = event.received_at
    details = callback.details or {}
    if run.state in TERMINAL_STATES:
        ignored_reason = "terminal_state_protected"
    elif callback.event_type == "accepted":
        run.accepted_at = run.accepted_at or at
        run.runner_pid = callback.runner_pid
        allocation.accepted_at = allocation.accepted_at or at
        allocation.runner_pid = callback.runner_pid
        allocation.updated_at = at
        run.updated_at = at
    elif callback.event_type == "running":
        if allocation.state == "initializing":
            allocation.state = "running"
            allocation.started_at = allocation.started_at or at
            allocation.updated_at = at
            state_changed = True
        if run.state == "initializing":
            state_changed = _apply_transition(db, run=run, new_state="running", now=at) or state_changed
        if not state_changed:
            ignored_reason = "illegal_transition"
    elif callback.event_type == "heartbeat":
        run.last_heartbeat_at = at
        allocation.last_heartbeat_at = at
        allocation.updated_at = at
        run.updated_at = at
        node = db.get(LoadNode, callback.node_id)
        if node is not None:
            node.last_heartbeat_at = at
    elif callback.event_type == "artifact":
        run.updated_at = at
    elif callback.event_type in TERMINAL_STATES:
        reason = details.get("reason") if isinstance(details.get("reason"), str) else None
        process_group_exited = details.get("processGroupExited") is True
        sla_result = details.get("slaResult")
        if sla_result is not None and sla_result not in {"passed", "failed"}:
            raise AppError("RUNNER_CALLBACK_INVALID", "Runner callback is invalid.", 422)
        if callback.event_type == "finished" and allocation.state not in {"running", "stopping"}:
            ignored_reason = "illegal_transition"
        else:
            allocation.state = callback.event_type
            allocation.ended_at = at
            allocation.terminal_reason = reason or callback.event_type
            allocation.terminal_message = _safe_message(callback.message, "Run allocation ended.")
            allocation.sla_result = sla_result if isinstance(sla_result, str) else allocation.sla_result
            allocation.updated_at = at
            if process_group_exited:
                release_run_lease(db, run=run, reason=callback.event_type, now=at, allocation=allocation)
            else:
                enqueue_control_request(
                    db, run=run, action="force_kill", reason=reason or callback.event_type,
                    allocation=allocation,
                )
            if callback.event_type == "failed":
                run.failure_reason = allocation.terminal_reason
                run.failure_message = allocation.terminal_message
                _enqueue_cleanup_for_non_terminal_siblings(
                    db,
                    run=run,
                    failed_allocation=allocation,
                    reason=reason or callback.event_type,
                    now=at,
                )
            state_changed = _derive_run_terminal_from_allocations(
                db, run=run, allocations=_allocations_for_run(db, run_id=run.id), now=at
            )
    run.last_callback_event_id = event.id
    event.ignored_reason = ignored_reason
    db.flush()
    logger.info(
        "Runner callback ignored" if ignored_reason else "Runner callback applied",
        extra={
            "run_id": run.id,
            "event_id": callback.event_id,
            "event_type": callback.event_type,
            "state_changed": state_changed,
            "ignored_reason": ignored_reason,
            "duplicate": False,
        },
    )
    return CallbackResult(True, False, state_changed, run.state, ignored_reason)


def request_stop(
    db: Session, *, run: Run, actor: User, request_id: str | None = None
) -> StopResult:
    """Request an idempotent Stop for a non-terminal Run.

    First accepted Stop returns ``202`` and transitions the Run to ``stopping``
    with one ``stop`` run-control request. Duplicate Stop while ``stopping``
    returns ``200`` without creating a parallel remote stop. Terminal Runs are
    never mutated.
    """
    _ = request_id
    now = utc_now()
    if run.state == "stopping":
        return StopResult(run.id, run.state, run.stop_requested_at, True, 200)
    if run.state in TERMINAL_STATES:
        raise AppError("RUN_TERMINAL_STATE", "Run is already terminal.", 409)
    if run.state not in {"initializing", "running"}:
        raise AppError("RUN_STOP_NOT_ALLOWED", "Run cannot be stopped from its current state.", 409)
    allocations = _allocations_for_run(db, run_id=run.id)
    if not allocations:
        raise AppError("RUN_ALLOCATION_REQUIRED", "Run has no node allocation.", 409)
    previous = run.state
    run.state = "stopping"
    run.stop_requested_at = now
    run.stop_requested_by_user_id = actor.id
    run.updated_at = now
    for allocation in allocations:
        if allocation.state not in TERMINAL_STATES:
            allocation.state = "stopping"
            allocation.updated_at = now
            enqueue_control_request(
                db, run=run, action="stop", run_after=now, allocation=allocation
            )
    write_audit_event(
        db,
        event_type="run.stop_requested",
        actor_user_id=actor.id,
        workspace_id=run.workspace_id,
        target_type="run",
        target_id=run.id,
        details={
            "runId": run.id,
            "workspaceId": run.workspace_id,
            "previousState": previous,
            "allocationCount": len(allocations),
        },
    )
    db.flush()
    return StopResult(run.id, run.state, run.stop_requested_at, False, 202)


def request_stop_by_id(
    db: Session, *, run_id: str, workspace_id: str, actor: User, request_id: str | None = None
) -> StopResult:
    run = db.scalar(
        select(Run)
        .where(Run.id == run_id, Run.workspace_id == workspace_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    return request_stop(db, run=run, actor=actor, request_id=request_id)


def cancel_run_control_request(
    request: RunControlRequest,
    *,
    error_code: str = "RUN_CONTROL_OBSOLETE",
    message: str = "Run control request is obsolete.",
    now: datetime | None = None,
) -> None:
    at = now or utc_now()
    request.status = "cancelled"
    request.finished_at = at
    request.claimed_at = None
    request.claimed_by = None
    request.last_error_code = error_code
    request.last_error_message = _safe_message(message, "Run control request is obsolete.")
    request.updated_at = at


def _has_active_force_kill_request(
    db: Session, *, run_id: str, node_id: str | None = None
) -> bool:
    conditions = [
        RunControlRequest.run_id == run_id,
        RunControlRequest.action == "force_kill",
        RunControlRequest.status.in_(list(ACTIVE_CONTROL_STATUSES)),
    ]
    if node_id is not None:
        conditions.append(RunControlRequest.node_id == node_id)
    return db.scalar(select(RunControlRequest.id).where(*conditions).limit(1)) is not None


def claim_next_run_control_request(
    db: Session, *, worker_id: str = "api-worker"
) -> RunControlRequest | None:
    """Claim the next due ``run_control_requests`` row for the api-worker.

    Row-level ``FOR UPDATE SKIP LOCKED`` claiming means more than one worker
    process can never execute the same request.
    """
    now = utc_now()
    request = db.scalar(
        select(RunControlRequest)
        .where(RunControlRequest.status == "pending", RunControlRequest.run_after <= now)
        .order_by(RunControlRequest.created_at.asc(), RunControlRequest.id.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if request is None:
        return None
    request.status = "running"
    request.claimed_at = now
    request.claimed_by = worker_id
    request.attempt_count += 1
    request.updated_at = now
    db.flush()
    return request


def build_run_control_command(
    db: Session, *, request: RunControlRequest
) -> RunControlCommand | None:
    """Re-validate a claimed request and build the remote command to execute.

    The worker only executes a command after this validation commits. An
    obsolete request (Run already converged, or its node lease is gone) is
    cancelled here so a remote action is never run against a stale target.
    """
    current = db.scalar(
        select(RunControlRequest)
        .where(RunControlRequest.id == request.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if current is None or current.status != "running":
        return None
    run = db.scalar(
        select(Run)
        .where(Run.id == current.run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None:
        return None
    allocation = db.scalar(
        select(RunNodeAllocation)
        .where(
            RunNodeAllocation.id == current.allocation_id
            if current.allocation_id is not None
            else and_(RunNodeAllocation.run_id == run.id, RunNodeAllocation.node_id == current.node_id)
        )
        .with_for_update()
    )
    if current.action == "start" and (
        run.state not in {"initializing", "running"}
        or allocation is None
        or allocation.state != "initializing"
    ):
        cancel_run_control_request(current)
        db.flush()
        return None
    if current.action == "stop" and run.state != "stopping":
        cancel_run_control_request(current)
        db.flush()
        return None
    node = db.scalar(
        select(LoadNode)
        .where(LoadNode.id == current.node_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if node is None:
        return None
    return RunControlCommand(
        request_id=current.id,
        action=current.action,
        run_id=current.run_id,
        node_id=current.node_id,
        reason=current.reason,
        source_type=run.source_type,
        host=node.host,
        ssh_port=node.ssh_port,
        ssh_user=node.ssh_user,
        runner_home=node.runner_home,
        trusted_host_key_algorithm=node.ssh_host_key_algorithm or "",
        trusted_host_key_public_key=node.ssh_host_key_public_key or "",
        trusted_host_key_fingerprint_sha256=node.ssh_host_key_fingerprint_sha256 or "",
        argv=_runner_command_argv(
            runner_home=node.runner_home,
            action=current.action,
            run_id=current.run_id,
            use_fake_runner=current.action == "start"
            and run.source_type == "protocol_smoke",
        ),
    )


def complete_run_control_request(
    db: Session,
    *,
    request: RunControlRequest,
    success: bool = True,
    error_code: str | None = None,
    error_message: str | None = None,
    stderr_preview: str | None = None,
    timed_out: bool = False,
    quarantine_node: bool = True,
    cleanup_required: bool = False,
) -> None:
    """Apply one finished run-control request to the Run and its node lease.

    A successful ``start`` only records the remote-start completion window; the
    Run stays ``initializing`` until the Runner reports ``accepted``/``running``
    callbacks. A failed ``start`` converges the Run to ``failed`` with reason
    ``runner_start_failed``. If the remote start result is uncertain
    (``cleanup_required``), the node stays Busy under its lease until a shared
    ``force_kill`` request reports the cleanup result; otherwise the lease is
    released immediately subject to the quarantine decision. A finished
    ``force_kill`` releases the lease with the node Idle on success or
    Quarantined on failure.
    """
    now = utc_now()
    effective_error_code = error_code or "RUN_CONTROL_FAILED"
    request.status = "succeeded" if success else "failed"
    request.finished_at = now
    request.last_error_code = None if success else effective_error_code
    request.last_error_message = (
        None if success else _safe_message(error_message, "Run control request failed.")
    )
    request.updated_at = now
    run = db.get(Run, request.run_id)
    allocation = db.get(RunNodeAllocation, request.allocation_id) if request.allocation_id else None
    if run is not None and request.action == "start" and success:
        run.remote_start_attempted_at = run.remote_start_attempted_at or now
        run.remote_start_completed_at = now
    if (
        run is not None
        and request.action == "start"
        and not success
        and run.state not in TERMINAL_STATES
    ):
        terminal_message = _safe_message(error_message, "Runner start failed.")
        if allocation is not None:
            allocation.state = "failed"
            allocation.ended_at = now
            allocation.terminal_reason = "runner_start_failed"
            allocation.terminal_message = terminal_message
            allocation.updated_at = now
        if cleanup_required:
            # Uncertain remote start: keep the node unavailable under its lease
            # until the shared force-kill cleanup reports a result.
            enqueue_control_request(
                db,
                run=run,
                action="force_kill",
                reason="runner_start_failed",
                run_after=now,
                allocation=allocation,
            )
        else:
            release_run_lease(
                db,
                run=run,
                reason="runner_start_failed",
                quarantine=quarantine_node,
                now=now,
                allocation=allocation,
            )
        if allocation is not None:
            _derive_run_terminal_from_allocations(
                db, run=run, allocations=_allocations_for_run(db, run_id=run.id), now=now
            )
    if run is not None and request.action == "force_kill":
        quarantine_required = request.reason == "stale_process_detected" or not success
        release_reason = (
            request.reason
            if success and request.reason == "stale_process_detected"
            else "force_kill_success"
            if success
            else "force_kill_failed"
        )
        if success:
            run.last_force_kill_at = now
        if allocation is not None and allocation.state not in TERMINAL_STATES:
            allocation.state = (
                "aborted"
                if run.stop_requested_at is not None and run.failure_reason is None
                else "failed"
            )
            allocation.ended_at = now
            allocation.terminal_reason = request.reason or release_reason
            allocation.terminal_message = (
                "Runner cleanup completed."
                if success
                else _safe_message(error_message, "Runner cleanup failed.")
            )
            allocation.updated_at = now
            if allocation.state == "failed":
                run.failure_reason = allocation.terminal_reason
                run.failure_message = allocation.terminal_message
        node = db.get(LoadNode, request.node_id)
        if success and node is not None:
            node.last_force_kill_at = now
            node.updated_at = now
        write_audit_event(
            db,
            event_type="run.force_kill",
            actor_user_id=None,
            workspace_id=request.workspace_id,
            target_type="run",
            target_id=request.run_id,
            details={
                "runId": request.run_id,
                "nodeId": request.node_id,
                "reason": request.reason,
                "success": success,
                "timedOut": timed_out,
                "stderrPreview": (
                    _safe_message(stderr_preview, "") if stderr_preview else None
                ),
            },
        )
        release_run_lease(
            db,
            run=run,
            reason=release_reason,
            quarantine=quarantine_required,
            now=now,
            node_id=request.node_id,
            allocation=allocation,
        )
        _derive_run_terminal_from_allocations(
            db, run=run, allocations=_allocations_for_run(db, run_id=run.id), now=now
        )
    db.flush()


def _force_converge_run(
    db: Session,
    *,
    run: Run,
    target_state: str,
    reason: str,
    forced: bool,
    now: datetime,
) -> bool:
    """Force-converge one single-node Run to a terminal state and enqueue cleanup.

    The Run only converges while its node lease is still active; the worker
    keeps the node unavailable until the shared force-kill cleanup reports a
    result.
    """
    if run.state in TERMINAL_STATES:
        return False
    if target_state == "failed" and run.state not in {"initializing", "running", "stopping"}:
        return False
    if target_state == "aborted" and run.state != "stopping":
        return False
    allocations = _allocations_for_run(db, run_id=run.id)
    if not allocations:
        return False
    run.failure_reason = reason
    run.failure_message = _safe_message(None, "Run was force-converged by SurgePilot.")
    run.forced_convergence = forced
    run.updated_at = now
    for allocation in allocations:
        if allocation.state in TERMINAL_STATES:
            continue
        allocation.state = target_state
        allocation.ended_at = now
        allocation.terminal_reason = reason
        allocation.terminal_message = run.failure_message
        allocation.updated_at = now
        enqueue_control_request(
            db, run=run, action="force_kill", reason=reason, run_after=now, allocation=allocation
        )
    _derive_run_terminal_from_allocations(
        db, run=run, allocations=_allocations_for_run(db, run_id=run.id), now=now
    )
    db.flush()
    return True


def sweep_accepted_timeouts(
    db: Session, *, now: datetime | None = None, timeout_seconds: int | None = None
) -> int:
    """Fail Runs that never received an ``accepted`` callback after remote start."""
    at = now or utc_now()
    cutoff = at - timedelta(
        seconds=timeout_seconds or get_settings().runner_accepted_timeout_seconds
    )
    rows = db.execute(
        select(Run, RunNodeAllocation)
        .join(RunNodeAllocation, RunNodeAllocation.run_id == Run.id)
        .where(
            Run.state.in_(("initializing", "running")),
            Run.remote_start_requested_at.is_not(None),
            Run.remote_start_requested_at < cutoff,
            RunNodeAllocation.state == "initializing",
            RunNodeAllocation.accepted_at.is_(None),
        )
        .with_for_update(skip_locked=True)
    ).all()
    converged = 0
    for run, allocation in rows:
        allocation.state = "failed"
        allocation.ended_at = at
        allocation.terminal_reason = "runner_accept_timeout"
        allocation.terminal_message = "Run allocation timed out waiting for Runner acceptance."
        allocation.updated_at = at
        enqueue_control_request(
            db, run=run, action="force_kill", reason="runner_accept_timeout",
            run_after=at, allocation=allocation
        )
        _enqueue_cleanup_for_non_terminal_siblings(
            db, run=run, failed_allocation=allocation, reason="runner_accept_timeout", now=at
        )
        _derive_run_terminal_from_allocations(
            db, run=run, allocations=_allocations_for_run(db, run_id=run.id), now=at
        )
        converged += 1
    return converged


def sweep_heartbeat_timeouts(
    db: Session, *, now: datetime | None = None, timeout_seconds: int | None = None
) -> int:
    """Fail accepted-but-not-started and heart-beat-less active Runs.

    An ``initializing`` Run that was accepted but never reported ``running``
    converges with ``runner_start_timeout``; a ``running`` Run whose heartbeat
    went stale converges with ``heartbeat_timeout``.
    """
    at = now or utc_now()
    cutoff = at - timedelta(
        seconds=timeout_seconds or get_settings().runner_heartbeat_timeout_seconds
    )
    rows = db.execute(
        select(Run, RunNodeAllocation)
        .join(RunNodeAllocation, RunNodeAllocation.run_id == Run.id)
        .where(
            Run.state.in_(("initializing", "running")),
            RunNodeAllocation.state.in_(("initializing", "running")),
            or_(
                and_(
                    RunNodeAllocation.state == "initializing",
                    RunNodeAllocation.accepted_at.is_not(None),
                    RunNodeAllocation.accepted_at < cutoff,
                    RunNodeAllocation.started_at.is_(None),
                ),
                and_(
                    RunNodeAllocation.state == "running",
                    or_(
                        RunNodeAllocation.last_heartbeat_at < cutoff,
                        and_(
                            RunNodeAllocation.last_heartbeat_at.is_(None),
                            RunNodeAllocation.started_at.is_not(None),
                            RunNodeAllocation.started_at < cutoff,
                        ),
                    ),
                ),
            ),
        )
        .with_for_update(skip_locked=True)
    ).all()
    converged = 0
    for run, allocation in rows:
        reason = "runner_start_timeout" if allocation.state == "initializing" else "heartbeat_timeout"
        allocation.state = "failed"
        allocation.ended_at = at
        allocation.terminal_reason = reason
        allocation.terminal_message = "Run allocation timed out."
        allocation.updated_at = at
        enqueue_control_request(
            db, run=run, action="force_kill", reason=reason, run_after=at, allocation=allocation
        )
        _enqueue_cleanup_for_non_terminal_siblings(
            db, run=run, failed_allocation=allocation, reason=reason, now=at
        )
        _derive_run_terminal_from_allocations(
            db, run=run, allocations=_allocations_for_run(db, run_id=run.id), now=at
        )
        converged += 1
    return converged


def sweep_stop_grace_timeouts(
    db: Session, *, now: datetime | None = None, timeout_seconds: int | None = None
) -> int:
    """Force-converge ``stopping`` Runs that exceeded their Stop grace window."""
    at = now or utc_now()
    cutoff = at - timedelta(seconds=timeout_seconds or get_settings().runner_stop_grace_seconds)
    runs = db.scalars(
        select(Run)
        .where(
            Run.state == "stopping",
            Run.stop_requested_at.is_not(None),
            Run.stop_requested_at < cutoff,
        )
        .with_for_update(skip_locked=True)
    ).all()
    return sum(
        1
        for run in runs
        if _force_converge_run(
            db,
            run=run,
            target_state="aborted",
            reason="stop_grace_timeout",
            forced=True,
            now=at,
        )
    )


def recover_stale_leases(db: Session) -> int:
    """Enqueue one force-kill cleanup for terminal Runs whose lease is open.

    A worker crash after the terminal transition but before lease release is
    recovered here: the node stays unavailable until cleanup reports a result.
    """
    leases = db.scalars(
        select(NodeLease).where(NodeLease.released_at.is_(None)).with_for_update(skip_locked=True)
    ).all()
    count = 0
    for lease in leases:
        run = db.get(Run, lease.run_id)
        if (
            run is not None
            and run.state in TERMINAL_STATES
            and not _has_active_force_kill_request(db, run_id=run.id, node_id=lease.node_id)
        ):
            enqueue_control_request(
                db,
                run=run,
                action="force_kill",
                reason="stale_recovery",
                run_after=utc_now(),
                allocation=_allocation_for_node(db, run_id=run.id, node_id=lease.node_id),
            )
            count += 1
    return count


def _reset_run_control_request_for_retry(
    request: RunControlRequest,
    *,
    now: datetime,
    error_code: str = "RUN_CONTROL_STALE_RETRY",
    message: str = "Run control request was reclaimed after a stale worker claim.",
) -> None:
    request.status = "pending"
    request.claimed_at = None
    request.claimed_by = None
    request.finished_at = None
    request.last_error_code = error_code
    request.last_error_message = _safe_message(message, "Run control request was reclaimed.")
    request.updated_at = now


def recover_stale_run_control_requests(
    db: Session, *, now: datetime | None = None, stale_seconds: int | None = None
) -> int:
    """Reset or cancel run-control requests claimed by a dead worker.

    Requests whose target Run already converged are cancelled; still-valid
    requests return to ``pending`` for another worker claim.
    """
    at = now or utc_now()
    cutoff = at - timedelta(seconds=stale_seconds or get_settings().run_control_stale_seconds)
    requests = db.scalars(
        select(RunControlRequest)
        .where(
            RunControlRequest.status == "running",
            RunControlRequest.claimed_at.is_not(None),
            RunControlRequest.claimed_at < cutoff,
        )
        .with_for_update(skip_locked=True)
    ).all()
    recovered = 0
    for request in requests:
        run = db.get(Run, request.run_id)
        if run is None:
            cancel_run_control_request(
                request,
                error_code="RUN_CONTROL_TARGET_MISSING",
                message="Run control target was not found.",
                now=at,
            )
            recovered += 1
            continue
        if request.action == "start" and (
            run.state not in {"initializing", "running"}
            or _active_lease(db, run_id=run.id) is None
        ):
            cancel_run_control_request(request, now=at)
            recovered += 1
            continue
        if request.action == "stop" and run.state != "stopping":
            cancel_run_control_request(request, now=at)
            recovered += 1
            continue
        _reset_run_control_request_for_retry(request, now=at)
        recovered += 1
    db.flush()
    return recovered


def cleanup_callback_retention(db: Session, *, older_than: datetime) -> int:
    """Delete Runner callback events older than the retention window."""
    events = db.scalars(
        select(RunnerCallbackEvent).where(RunnerCallbackEvent.created_at < older_than)
    ).all()
    count = len(events)
    for event in events:
        db.delete(event)
    db.flush()
    return count


def sign_runner_node_token(node_id: str, *, secret: str | None = None) -> str:
    master = secret if secret is not None else get_settings().runner_internal_token
    if not master or not is_ulid(node_id):
        raise AppError("RUNNER_UNAUTHORIZED", "Runner token is invalid.", 401)
    signature = hmac.new(master.encode(), node_id.encode(), hashlib.sha256).hexdigest()
    return f"{NODE_BOUND_TOKEN_PREFIX}{node_id}:{signature}"


def validate_runner_token(token: str | None, *, node_id: str | None = None) -> str | None:
    expected = get_settings().runner_internal_token
    if not expected or not token:
        raise AppError("RUNNER_UNAUTHORIZED", "Runner token is invalid.", 401)
    if token.startswith(NODE_BOUND_TOKEN_PREFIX):
        parts = token.split(":", 2)
        if len(parts) != 3 or parts[0] != "node":
            raise AppError("RUNNER_UNAUTHORIZED", "Runner token is invalid.", 401)
        authenticated_node_id = parts[1]
        signature = parts[2]
        if not authenticated_node_id or not is_ulid(authenticated_node_id) or not signature:
            raise AppError("RUNNER_UNAUTHORIZED", "Runner token is invalid.", 401)
        expected_token = sign_runner_node_token(authenticated_node_id, secret=expected)
        if not hmac.compare_digest(token, expected_token):
            raise AppError("RUNNER_UNAUTHORIZED", "Runner token is invalid.", 401)
        if node_id is not None and authenticated_node_id != node_id:
            raise AppError("RUNNER_FORBIDDEN", "Runner is not allowed to report this node.", 403)
        return authenticated_node_id
    raise AppError("RUNNER_UNAUTHORIZED", "Runner token is invalid.", 401)


def validate_artifact_relative_path(path: str) -> str:
    if not path or path.startswith("/") or "\\" in path or "//" in path or ":" in path:
        raise AppError("INVALID_ARTIFACT_PATH", "Artifact path is invalid.", 400)
    parts = path.split("/")
    if any(part in {"", ".", ".."} or not SAFE_PATH_SEGMENT.fullmatch(part) for part in parts):
        raise AppError("INVALID_ARTIFACT_PATH", "Artifact path is invalid.", 400)
    return path


def _terminal_late_policy_limit(run: Run, *, declared_size_bytes: int, now: datetime) -> int:
    settings = get_settings()
    if run.state not in TERMINAL_STATES:
        return settings.run_artifact_max_bytes
    if run.ended_at is None:
        raise AppError("RUN_TERMINAL_STATE", "Run is already terminal.", 409)
    ended_at = as_utc(run.ended_at)
    if ended_at < now - timedelta(seconds=settings.run_terminal_late_artifact_seconds):
        raise AppError("RUN_TERMINAL_STATE", "Run is already terminal.", 409)
    max_bytes = settings.run_terminal_late_artifact_max_bytes
    if declared_size_bytes >= max_bytes:
        raise AppError("RUN_TERMINAL_STATE", "Run is already terminal.", 409)
    return max_bytes


DEBUG_HTTP_BODY_BLOB_RELATIVE_PATH_PREFIX = "artifacts/debug-http-body-blobs/"


def _validate_debug_http_internal_scope_and_path(
    run: Run, *, artifact_type: str, relative_path: str
) -> None:
    if artifact_type not in {DEBUG_HTTP_TRACE_ARTIFACT_TYPE, DEBUG_HTTP_BODY_BLOB_ARTIFACT_TYPE}:
        return
    if run.run_type != "debug" or run.source_type not in {"debug_scenario", "test_plan"}:
        raise AppError("RUNNER_FORBIDDEN", "Runner is not allowed to upload this artifact.", 403)
    if artifact_type == DEBUG_HTTP_TRACE_ARTIFACT_TYPE:
        if relative_path != DEBUG_HTTP_TRACE_RELATIVE_PATH:
            raise AppError("INVALID_ARTIFACT_PATH", "Artifact path is invalid.", 400)
    elif not (
        relative_path.startswith(DEBUG_HTTP_BODY_BLOB_RELATIVE_PATH_PREFIX)
        and relative_path.endswith(".bin")
        and relative_path.count("/") == 2
    ):
        raise AppError("INVALID_ARTIFACT_PATH", "Artifact path is invalid.", 400)


def _validate_debug_http_internal_pre_terminal(run: Run, *, artifact_type: str) -> None:
    if artifact_type in {DEBUG_HTTP_TRACE_ARTIFACT_TYPE, DEBUG_HTTP_BODY_BLOB_ARTIFACT_TYPE} and run.state in TERMINAL_STATES:
        raise AppError("RUN_TERMINAL_STATE", "Run is already terminal.", 409)


def _validate_debug_http_body_blob_total_budget(db: Session, *, run_id: str, new_size_bytes: int) -> None:
    if new_size_bytes < 0:
        raise AppError("ARTIFACT_SIZE_MISMATCH", "Artifact size does not match.", 400)
    existing = db.scalar(select(func.coalesce(func.sum(RunArtifact.size_bytes), 0)).where(
        RunArtifact.run_id == run_id,
        RunArtifact.artifact_type == DEBUG_HTTP_BODY_BLOB_ARTIFACT_TYPE,
        RunArtifact.status == "available",
    ))
    if int(existing or 0) + new_size_bytes > get_settings().debug_trace_body_blob_total_max_bytes:
        raise AppError("PAYLOAD_TOO_LARGE", "Uploaded file is too large.", 413)


def _delete_artifact_object_best_effort(*, bucket: str, object_key: str, storage_client) -> None:
    delete = getattr(storage_client, "delete_object_best_effort", None)
    if callable(delete):
        delete(bucket=bucket, object_key=object_key)


def _copy_artifact_object(
    *, bucket: str, source_key: str, destination_key: str, storage_client
) -> None:
    copy = getattr(storage_client, "copy_object", None)
    if callable(copy):
        copy(bucket=bucket, source_key=source_key, destination_key=destination_key)
        return
    raise AppError("STORAGE_UNAVAILABLE", "Storage is unavailable.", 503)


def _artifact_path_conditions(
    *, run_id: str, node_id: str, allocation: RunNodeAllocation, safe_path: str
) -> list[Any]:
    return [
        RunArtifact.run_id == run_id,
        RunArtifact.node_id == node_id,
        RunArtifact.allocation_id == allocation.id,
        RunArtifact.relative_path == safe_path,
        RunArtifact.status == "available",
    ]


def ingest_run_artifact(
    db: Session,
    *,
    event_id: str,
    run_id: str,
    node_id: str,
    authenticated_node_id: str | None = None,
    artifact_type: str,
    relative_path: str,
    declared_sha256: str,
    declared_size_bytes: int,
    file: BinaryIO,
    content_type: str | None,
) -> ArtifactResult:
    """Accept a Runner artifact upload through API-mediated MinIO storage.

    The API derives the Workspace from the Run, validates the declared size and
    SHA-256 while streaming, and never returns MinIO credentials or object keys.
    The object is staged under a temporary key and copied to its final key only
    after in-DB duplicate/path-conflict rechecks succeed, so a concurrent winner
    object is never deleted by the loser.
    """
    if artifact_type not in RUN_ARTIFACT_TYPES:
        raise AppError("INVALID_ARTIFACT_TYPE", "Artifact type is invalid.", 400)
    safe_path = validate_artifact_relative_path(relative_path)
    if declared_size_bytes < 0:
        raise AppError("ARTIFACT_SIZE_MISMATCH", "Artifact size does not match.", 400)
    run = _lock_run(db, run_id)
    _validate_debug_http_internal_scope_and_path(
        run, artifact_type=artifact_type, relative_path=safe_path
    )
    _validate_debug_http_internal_pre_terminal(run, artifact_type=artifact_type)
    allocation = _allocation_for_node(db, run_id=run.id, node_id=node_id)
    _validate_authenticated_runner_node(
        authenticated_node_id=authenticated_node_id,
        payload_node_id=node_id,
        allocation=allocation,
    )
    existing = db.scalar(
        select(RunArtifact).where(RunArtifact.run_id == run_id, RunArtifact.event_id == event_id)
    )
    if existing is not None:
        return ArtifactResult(existing.id, True)
    path_existing = db.scalar(
        select(RunArtifact).where(
            *_artifact_path_conditions(
                run_id=run_id, node_id=node_id, allocation=allocation, safe_path=safe_path
            )
        )
    )
    if path_existing is not None:
        if (
            path_existing.artifact_type != artifact_type
            or path_existing.size_bytes != declared_size_bytes
            or path_existing.sha256.lower() != declared_sha256.lower()
        ):
            raise AppError(
                "ARTIFACT_PATH_CONFLICT", "Artifact path already has different content.", 409
            )
        return ArtifactResult(path_existing.id, True)
    settings = get_settings()
    artifact_id = new_ulid()
    storage_key = (
        f"run-artifacts/{run.workspace_id}/{run.id}/nodes/{node_id}/allocations/{allocation.id}/{safe_path}"
    )
    temp_storage_key = (
        f"run-artifacts/{run.workspace_id}/{run.id}/.tmp/{artifact_id}/"
        f"nodes/{node_id}/allocations/{allocation.id}/{safe_path}"
    )
    now = utc_now()
    terminal_late = run.state in TERMINAL_STATES
    limit = _terminal_late_policy_limit(run, declared_size_bytes=declared_size_bytes, now=now)
    if declared_size_bytes > limit:
        raise AppError("PAYLOAD_TOO_LARGE", "Uploaded file is too large.", 413)
    bucket = settings.minio_bucket
    storage_client = get_storage_client()
    final_object_copied = False
    db.commit()
    try:
        put = storage_client.put_stream(
            bucket=bucket,
            object_key=temp_storage_key,
            stream=file,
            size_limit=limit,
            content_type=content_type,
        )
    except AppError as exc:
        if terminal_late and exc.code == "PAYLOAD_TOO_LARGE":
            raise AppError("RUN_TERMINAL_STATE", "Run is already terminal.", 409) from exc
        raise
    if terminal_late and put.size_bytes >= get_settings().run_terminal_late_artifact_max_bytes:
        _delete_artifact_object_best_effort(
            bucket=bucket, object_key=temp_storage_key, storage_client=storage_client
        )
        raise AppError("RUN_TERMINAL_STATE", "Run is already terminal.", 409)
    if artifact_type == DEBUG_HTTP_BODY_BLOB_ARTIFACT_TYPE:
        _validate_debug_http_body_blob_total_budget(db, run_id=run_id, new_size_bytes=put.size_bytes)
    if put.size_bytes != declared_size_bytes:
        _delete_artifact_object_best_effort(
            bucket=bucket, object_key=temp_storage_key, storage_client=storage_client
        )
        raise AppError("ARTIFACT_SIZE_MISMATCH", "Artifact size does not match.", 400)
    if put.sha256.lower() != declared_sha256.lower():
        _delete_artifact_object_best_effort(
            bucket=bucket, object_key=temp_storage_key, storage_client=storage_client
        )
        raise AppError("ARTIFACT_HASH_MISMATCH", "Artifact hash does not match.", 400)
    try:
        run = _lock_run(db, run_id)
        _validate_debug_http_internal_scope_and_path(
            run, artifact_type=artifact_type, relative_path=safe_path
        )
        _validate_debug_http_internal_pre_terminal(run, artifact_type=artifact_type)
        allocation = _allocation_for_node(db, run_id=run.id, node_id=node_id)
        _validate_authenticated_runner_node(
            authenticated_node_id=authenticated_node_id,
            payload_node_id=node_id,
            allocation=allocation,
        )
        existing = db.scalar(
            select(RunArtifact).where(
                RunArtifact.run_id == run_id, RunArtifact.event_id == event_id
            )
        )
        if existing is not None:
            _delete_artifact_object_best_effort(
                bucket=bucket, object_key=temp_storage_key, storage_client=storage_client
            )
            return ArtifactResult(existing.id, True)
        path_existing = db.scalar(
            select(RunArtifact).where(
                *_artifact_path_conditions(
                    run_id=run_id, node_id=node_id, allocation=allocation, safe_path=safe_path
                )
            )
        )
        if path_existing is not None:
            if (
                path_existing.artifact_type != artifact_type
                or path_existing.size_bytes != put.size_bytes
                or path_existing.sha256.lower() != put.sha256.lower()
            ):
                raise AppError(
                    "ARTIFACT_PATH_CONFLICT",
                    "Artifact path already has different content.",
                    409,
                )
            _delete_artifact_object_best_effort(
                bucket=bucket, object_key=temp_storage_key, storage_client=storage_client
            )
            return ArtifactResult(path_existing.id, True)
        terminal_late = run.state in TERMINAL_STATES
        if terminal_late:
            _terminal_late_policy_limit(run, declared_size_bytes=put.size_bytes, now=utc_now())
            if put.size_bytes >= get_settings().run_terminal_late_artifact_max_bytes:
                raise AppError("RUN_TERMINAL_STATE", "Run is already terminal.", 409)
        if artifact_type == DEBUG_HTTP_BODY_BLOB_ARTIFACT_TYPE:
            _validate_debug_http_body_blob_total_budget(
                db, run_id=run_id, new_size_bytes=put.size_bytes
            )
        _copy_artifact_object(
            bucket=bucket,
            source_key=temp_storage_key,
            destination_key=storage_key,
            storage_client=storage_client,
        )
        final_object_copied = True
        artifact = RunArtifact(
            id=artifact_id,
            workspace_id=run.workspace_id,
            run_id=run.id,
            node_id=node_id,
            allocation_id=allocation.id,
            event_id=event_id,
            artifact_type=artifact_type,
            relative_path=safe_path,
            display_filename=safe_path.rsplit("/", 1)[-1],
            size_bytes=put.size_bytes,
            sha256=put.sha256,
            content_type=content_type,
            storage_key=storage_key,
            status="available",
            terminal_late=terminal_late,
            created_at=now,
        )
        db.add(artifact)
        write_audit_event(
            db,
            event_type="artifact.uploaded",
            workspace_id=run.workspace_id,
            target_type="run_artifact",
            target_id=artifact_id,
            details={
                "artifactId": artifact_id,
                "runId": run.id,
                "nodeId": node_id,
                "workspaceId": run.workspace_id,
                "artifactType": artifact_type,
                "relativePath": safe_path,
                "sizeBytes": put.size_bytes,
                "sha256": put.sha256,
                "terminalLate": artifact.terminal_late,
            },
        )
        db.flush()
        db.commit()
        _delete_artifact_object_best_effort(
            bucket=bucket, object_key=temp_storage_key, storage_client=storage_client
        )
    except Exception:
        _delete_artifact_object_best_effort(
            bucket=bucket, object_key=temp_storage_key, storage_client=storage_client
        )
        if final_object_copied:
            _delete_artifact_object_best_effort(
                bucket=bucket, object_key=storage_key, storage_client=storage_client
            )
        raise
    return ArtifactResult(artifact_id, False)
