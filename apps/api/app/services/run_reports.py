from __future__ import annotations

import base64
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import math
from io import StringIO
from typing import Any, BinaryIO

from fastapi import Request
from sqlalchemy import Text, and_, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ids import new_ulid
from app.core.time import as_utc, utc_now
from app.models.auth import User
from app.models.load_nodes import LoadNode
from app.models.runs import (
    PUBLIC_RUN_ARTIFACT_TYPES,
    SLA_RESULTS,
    TERMINAL_RUN_STATES,
    Run,
    RunArtifact,
    RunReportSummary,
    RunSnapshot,
    RunNodeAllocation,
)
from app.schemas.runs import (
    DebugHttpTrace,
    FailureDiagnostics,
    FinalStatsPreview,
    FinalStatsPreviewRow,
    RunActor,
    RunArtifactItem,
    RunArtifactListResponse,
    RunArtifactsSummary,
    RunKpiSummary,
    RunListItem,
    RunListResponse,
    RunReportDetail,
    RunAllocatedNode,
    RunSelectedNode,
    RunSnapshotLoadSettings,
    RunSnapshotResourceRequest,
    RunSnapshotScenarioItem,
    RunSnapshotSlaRule,
    RunSnapshotSummary,
    RunValidityPatchResponse,
    RunVerdict,
)
from app.services.audit import write_audit_event
from app.services.debug_http_trace import (
    DEBUG_HTTP_BODY_BLOB_ARTIFACT_TYPE,
    DEBUG_HTTP_TRACE_ARTIFACT_TYPE,
    parse_debug_http_trace_jsonl,
)
from app.services.storage import StoredObjectStream, get_storage_client
from app.services.test_plans import sla_threshold_text

FINAL_STATS_TOTAL_ROW_MISSING = "FINAL_STATS_TOTAL_ROW_MISSING"
FINAL_STATS_PARSE_FAILED = "FINAL_STATS_PARSE_FAILED"
FINAL_STATS_TOO_LARGE = "FINAL_STATS_TOO_LARGE"
FINAL_STATS_SOURCE_ARTIFACT_MISSING = "FINAL_STATS_SOURCE_ARTIFACT_MISSING"
MAX_FINAL_STATS_BYTES = 2 * 1024 * 1024
MAX_FINAL_STATS_PREVIEW_ROWS = 200
ACTIVE_RUN_STATES = {"initializing", "running", "stopping"}
TERMINAL_STATES = set(TERMINAL_RUN_STATES)
PUBLIC_ARTIFACT_TYPES = set(PUBLIC_RUN_ARTIFACT_TYPES)
SAFE_SLA_RESULTS = set(SLA_RESULTS)


@dataclass(frozen=True)
class FinalStatsParseResult:
    parse_status: str
    summary_json: dict[str, Any]
    truncated: bool
    parse_error_code: str | None = None


@dataclass(frozen=True)
class ArtifactDownload:
    artifact: RunArtifact
    stored: StoredObjectStream


@dataclass(frozen=True)
class FinalStatsReportProjection:
    status: str
    artifact: RunArtifact | None = None
    summary: RunReportSummary | None = None
    source_artifact_id: str | None = None
    total: dict[str, Any] | None = None
    rows: list[dict[str, Any]] | None = None
    truncated: bool = False
    missing_reasons: list[str] | None = None
    warnings: list[str] | None = None


def iso_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    return as_utc(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _duration_ms(run: Run, *, now: datetime | None = None) -> int | None:
    start = run.started_at or run.created_at
    end = run.ended_at or (now if run.state in ACTIVE_RUN_STATES else None)
    if start is None or end is None:
        return None
    delta = as_utc(end) - as_utc(start)
    return max(int(delta.total_seconds() * 1000), 0)


def _read_bounded(stream: BinaryIO, max_bytes: int) -> bytes:
    data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(FINAL_STATS_TOO_LARGE)
    return data


def _safe_number(raw: Any) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if text == "":
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


def _int_count(raw: Any) -> int | None:
    value = _safe_number(raw)
    if value is None:
        return None
    return int(value)


def _milliseconds(
    raw: Any, *, missing_code: str, invalid_code: str, warnings: set[str]
) -> float | None:
    text = "" if raw is None else str(raw).strip()
    if text == "":
        warnings.add(missing_code)
        return None
    value = _safe_number(text)
    if value is None:
        warnings.add(invalid_code)
        return None
    return round(value * 1000, 3)


def _response_codes(row: dict[str, Any], warnings: set[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key, value in row.items():
        if not key.startswith("rc_"):
            continue
        parsed = _int_count(value)
        if parsed is None:
            warnings.add("response_code_count_invalid")
            continue
        code = key.removeprefix("rc_")
        counts[code] = parsed
    return counts


def _metric_row(row: dict[str, Any], warnings: set[str]) -> dict[str, Any]:
    total_requests = _int_count(row.get("throughput"))
    success_requests = _int_count(row.get("succ"))
    failed_requests = _int_count(row.get("fail"))
    if total_requests is None:
        warnings.add("total_requests_invalid")
    if success_requests is None:
        warnings.add("success_requests_invalid")
    if failed_requests is None:
        warnings.add("failed_requests_invalid")
    error_rate = None
    if total_requests is not None and failed_requests is not None and total_requests > 0:
        error_rate = round(failed_requests / total_requests, 6)
    average_response_time_ms = _milliseconds(
        row.get("avg_rt"),
        missing_code="average_response_time_missing",
        invalid_code="average_response_time_invalid",
        warnings=warnings,
    )

    def percentile(column: str) -> float | None:
        if column not in row or str(row.get(column) or "").strip() == "":
            warnings.add("percentile_column_missing")
            return None
        return _milliseconds(
            row.get(column),
            missing_code="percentile_column_missing",
            invalid_code="percentile_value_invalid",
            warnings=warnings,
        )

    label = str(row.get("label") or "").strip() or None
    return {
        "label": label,
        "totalRequests": total_requests,
        "successRequests": success_requests,
        "failedRequests": failed_requests,
        "errorRate": error_rate,
        "averageResponseTimeMs": average_response_time_ms,
        "p90Ms": percentile("perc_90.0"),
        "p95Ms": percentile("perc_95.0"),
        "p99Ms": percentile("perc_99.0"),
        "responseCodeCounts": _response_codes(row, warnings),
    }


def _failed_summary(code: str) -> FinalStatsParseResult:
    return FinalStatsParseResult(
        parse_status="failed",
        summary_json={"schemaVersion": 1, "total": None, "rows": [], "warnings": [code]},
        truncated=False,
        parse_error_code=code,
    )


def parse_final_stats_csv(
    stream: BinaryIO,
    *,
    max_rows: int = MAX_FINAL_STATS_PREVIEW_ROWS,
    max_bytes: int = MAX_FINAL_STATS_BYTES,
) -> FinalStatsParseResult:
    try:
        data = _read_bounded(stream, max_bytes)
    except ValueError as exc:
        code = str(exc) or FINAL_STATS_PARSE_FAILED
        return _failed_summary(code)
    try:
        text = data.decode("utf-8-sig")
        reader = csv.DictReader(StringIO(text))
        if not reader.fieldnames:
            return _failed_summary(FINAL_STATS_PARSE_FAILED)
        total_row: dict[str, Any] | None = None
        preview_rows: list[dict[str, Any]] = []
        truncated = False
        for row in reader:
            label = str(row.get("label") or "").strip()
            if label == "" and total_row is None:
                total_row = row
                continue
            if len(preview_rows) < max_rows:
                preview_rows.append(row)
            else:
                truncated = True
        if total_row is None:
            return _failed_summary(FINAL_STATS_TOTAL_ROW_MISSING)
        warnings: set[str] = set()
        total = _metric_row(total_row, warnings)
        rows = [_metric_row(row, warnings) for row in preview_rows]
        return FinalStatsParseResult(
            parse_status="parsed",
            summary_json={
                "schemaVersion": 1,
                "total": total,
                "rows": rows,
                "warnings": sorted(warnings),
            },
            truncated=truncated,
        )
    except csv.Error:
        return _failed_summary(FINAL_STATS_PARSE_FAILED)
    except UnicodeDecodeError:
        return _failed_summary(FINAL_STATS_PARSE_FAILED)


def parse_and_store_final_stats_summary(
    db: Session,
    *,
    artifact: RunArtifact,
    stream: BinaryIO,
) -> RunReportSummary:
    if artifact.artifact_type != "final_stats_csv":
        raise AppError("INVALID_ARTIFACT_TYPE", "Artifact type is invalid.", 400)
    result = parse_final_stats_csv(stream)
    now = utc_now()
    summary = db.scalar(
        select(RunReportSummary).where(
            RunReportSummary.run_id == artifact.run_id,
            RunReportSummary.source_artifact_id == artifact.id,
            RunReportSummary.summary_type == "final_stats",
        )
    )
    if summary is None:
        summary = RunReportSummary(
            id=new_ulid(),
            workspace_id=artifact.workspace_id,
            run_id=artifact.run_id,
            source_artifact_id=artifact.id,
            summary_type="final_stats",
            summary_json=result.summary_json,
            truncated=result.truncated,
            parse_status=result.parse_status,
            parse_error_code=result.parse_error_code,
            created_at=now,
            updated_at=now,
        )
        db.add(summary)
    else:
        summary.summary_json = result.summary_json
        summary.truncated = result.truncated
        summary.parse_status = result.parse_status
        summary.parse_error_code = result.parse_error_code
        summary.updated_at = now
    db.flush()
    return summary


def create_pending_final_stats_summary(db: Session, *, artifact: RunArtifact) -> RunReportSummary:
    if artifact.artifact_type != "final_stats_csv":
        raise AppError("INVALID_ARTIFACT_TYPE", "Artifact type is invalid.", 400)
    now = utc_now()
    summary = db.scalar(
        select(RunReportSummary).where(
            RunReportSummary.run_id == artifact.run_id,
            RunReportSummary.source_artifact_id == artifact.id,
            RunReportSummary.summary_type == "final_stats",
        )
    )
    if summary is None:
        summary = RunReportSummary(
            id=new_ulid(),
            workspace_id=artifact.workspace_id,
            run_id=artifact.run_id,
            source_artifact_id=artifact.id,
            summary_type="final_stats",
            summary_json={"schemaVersion": 1, "total": None, "rows": [], "warnings": []},
            truncated=False,
            parse_status="pending",
            parse_error_code=None,
            created_at=now,
            updated_at=now,
        )
        db.add(summary)
        db.flush()
    return summary


def _store_final_stats_failure(summary: RunReportSummary, code: str) -> None:
    now = utc_now()
    summary.summary_json = {"schemaVersion": 1, "total": None, "rows": [], "warnings": [code]}
    summary.truncated = False
    summary.parse_status = "failed"
    summary.parse_error_code = code
    summary.updated_at = now


def process_next_pending_final_stats_summary(db: Session) -> int:
    summary = db.scalar(
        select(RunReportSummary)
        .where(
            RunReportSummary.summary_type == "final_stats",
            RunReportSummary.parse_status == "pending",
        )
        .order_by(RunReportSummary.created_at.asc(), RunReportSummary.id.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if summary is None:
        return 0
    artifact = db.scalar(
        select(RunArtifact).where(
            RunArtifact.id == summary.source_artifact_id,
            RunArtifact.run_id == summary.run_id,
            RunArtifact.workspace_id == summary.workspace_id,
            RunArtifact.artifact_type == "final_stats_csv",
            RunArtifact.status == "available",
        )
    )
    if artifact is None:
        _store_final_stats_failure(summary, FINAL_STATS_SOURCE_ARTIFACT_MISSING)
        db.flush()
        return 1
    stored = get_storage_client().get_stream(
        bucket=get_settings().minio_bucket,
        object_key=artifact.storage_key,
    )
    try:
        parse_and_store_final_stats_summary(db, artifact=artifact, stream=stored.stream)
    finally:
        close = getattr(stored.stream, "close", None)
        if callable(close):
            close()
    return 1


def _cursor_encode(created_at: datetime, item_id: str) -> str:
    payload = {"createdAt": iso_z(created_at), "id": item_id}
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def _cursor_decode(cursor: str) -> tuple[datetime, str]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        created_at = datetime.fromisoformat(str(payload["createdAt"]).replace("Z", "+00:00"))
        item_id = str(payload["id"])
    except Exception as exc:
        raise AppError("VALIDATION_ERROR", "Validation failed.", 422) from exc
    if len(item_id) != 26:
        raise AppError("VALIDATION_ERROR", "Validation failed.", 422)
    return created_at, item_id


def _snapshot_source(
    snapshot: dict[str, Any], run: Run
) -> tuple[str | None, int | None, list[str]]:
    if run.source_type == "test_plan":
        plan = snapshot.get("testPlan") if isinstance(snapshot.get("testPlan"), dict) else {}
        return (
            plan.get("name"),
            plan.get("revision") or snapshot.get("sourceRevision"),
            list(plan.get("tags") or []),
        )
    if run.source_type == "debug_scenario":
        scenario = snapshot.get("scenario") if isinstance(snapshot.get("scenario"), dict) else {}
        return (
            scenario.get("name"),
            snapshot.get("sourceRevision"),
            list(scenario.get("tags") or []),
        )
    return run.source_type, snapshot.get("sourceRevision"), []


def _node_name(node: LoadNode | None, run: Run) -> str:
    if node is None:
        return run.selected_node_id
    return f"Load Node {node.id[-6:]}"


def _artifact_counts(db: Session, run_id: str) -> tuple[int, bool, bool, datetime | None]:
    artifacts = db.scalars(
        select(RunArtifact).where(
            RunArtifact.run_id == run_id,
            RunArtifact.status == "available",
            RunArtifact.artifact_type.in_(PUBLIC_ARTIFACT_TYPES),
        )
    ).all()
    latest = max((artifact.created_at for artifact in artifacts), default=None)
    types = {artifact.artifact_type for artifact in artifacts}
    return len(artifacts), "artifacts_zip" in types, "final_stats_csv" in types, latest


def _run_actor(db: Session, user_id: str) -> RunActor:
    user = db.get(User, user_id)
    return RunActor(id=user_id, email=user.email if user is not None else "unknown@example.com")


def _selected_node(db: Session, run: Run) -> tuple[RunSelectedNode, LoadNode | None]:
    node = db.get(LoadNode, run.selected_node_id)
    return (
        RunSelectedNode(
            id=run.selected_node_id,
            name=_node_name(node, run),
            scope=node.scope if node is not None else "workspace",
        ),
        node,
    )


@dataclass(frozen=True)
class _RunListBatchData:
    artifact_counts: dict[str, tuple[int, bool, bool, datetime | None]]
    selected_nodes: dict[str, LoadNode]
    actors: dict[str, User]
    allocation_counts: dict[str, int]


def _batch_run_list_data(db: Session, runs: list[Run]) -> _RunListBatchData:
    run_ids = [run.id for run in runs]
    if not run_ids:
        return _RunListBatchData({}, {}, {}, {})

    artifact_counts: dict[str, tuple[int, bool, bool, datetime | None]] = {
        run_id: (0, False, False, None) for run_id in run_ids
    }
    artifacts = db.scalars(
        select(RunArtifact).where(
            RunArtifact.run_id.in_(run_ids),
            RunArtifact.status == "available",
            RunArtifact.artifact_type.in_(PUBLIC_ARTIFACT_TYPES),
        )
    ).all()
    grouped_artifacts: dict[str, list[RunArtifact]] = {run_id: [] for run_id in run_ids}
    for artifact in artifacts:
        grouped_artifacts.setdefault(artifact.run_id, []).append(artifact)
    for run_id, grouped in grouped_artifacts.items():
        latest = max((artifact.created_at for artifact in grouped), default=None)
        types = {artifact.artifact_type for artifact in grouped}
        artifact_counts[run_id] = (
            len(grouped),
            "artifacts_zip" in types,
            "final_stats_csv" in types,
            latest,
        )

    node_ids = sorted({run.selected_node_id for run in runs if run.selected_node_id})
    nodes = db.scalars(select(LoadNode).where(LoadNode.id.in_(node_ids))).all() if node_ids else []
    selected_nodes = {node.id: node for node in nodes}

    actor_ids = sorted({run.triggered_by_user_id for run in runs if run.triggered_by_user_id})
    users = db.scalars(select(User).where(User.id.in_(actor_ids))).all() if actor_ids else []
    actors = {user.id: user for user in users}

    allocation_rows = db.execute(
        select(RunNodeAllocation.run_id, func.count(RunNodeAllocation.id))
        .where(RunNodeAllocation.run_id.in_(run_ids))
        .group_by(RunNodeAllocation.run_id)
    ).all()
    allocation_counts = {run_id: int(count or 0) for run_id, count in allocation_rows}

    return _RunListBatchData(
        artifact_counts=artifact_counts,
        selected_nodes=selected_nodes,
        actors=actors,
        allocation_counts=allocation_counts,
    )


def _list_item(
    db: Session,
    run: Run,
    snapshot: RunSnapshot | None,
    *,
    now: datetime,
    batch: _RunListBatchData,
) -> RunListItem:
    source_name, source_revision, tags = _snapshot_source(
        snapshot.snapshot_json if snapshot else {}, run
    )
    artifact_count, has_zip, _has_final, _latest = batch.artifact_counts.get(
        run.id, (0, False, False, None)
    )
    node = batch.selected_nodes.get(run.selected_node_id)
    selected_node = RunSelectedNode(
        id=run.selected_node_id,
        name=_node_name(node, run),
        scope=node.scope if node is not None else "workspace",
    )
    actor = batch.actors.get(run.triggered_by_user_id)
    triggered_by = RunActor(
        id=run.triggered_by_user_id,
        email=actor.email if actor is not None else "unknown@example.com",
    )
    allocated_node_count = batch.allocation_counts.get(run.id, 0)
    return RunListItem(
        id=run.id,
        state=run.state,
        run_type=run.run_type,
        source_type=run.source_type,
        source_id=run.source_id,
        source_name=source_name,
        source_revision=source_revision,
        tags=tags,
        validity=run.validity or ("invalid" if run.run_type == "debug" else "valid"),
        sla_result=run.sla_result or "not_evaluated",
        triggered_by=triggered_by,
        selected_node=selected_node,
        allocated_node_count=max(1, int(allocated_node_count or 0)),
        created_at=iso_z(run.created_at) or "",
        started_at=iso_z(run.started_at),
        ended_at=iso_z(run.ended_at),
        duration_ms=_duration_ms(run, now=now),
        artifact_count=artifact_count,
        has_artifacts_zip=has_zip,
    )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_runs_report(
    db: Session,
    *,
    workspace_id: str,
    state: str | None = None,
    validity: str | None = None,
    run_type: str | None = None,
    source_type: str | None = None,
    q: str | None = None,
    tag: str | None = None,
    recent_hours: int | None = None,
    cursor: str | None = None,
    limit: int = 20,
    sort: str = "-createdAt",
) -> RunListResponse:
    if sort != "-createdAt":
        raise AppError("VALIDATION_ERROR", "Validation failed.", 422)
    if limit < 1 or limit > 100:
        raise AppError("VALIDATION_ERROR", "Validation failed.", 422)
    if q is not None:
        q = q.strip()
        if len(q) > 120:
            raise AppError("VALIDATION_ERROR", "Validation failed.", 422)
        q = q or None
    if tag is not None:
        tag = tag.strip()
        if len(tag) > 50:
            raise AppError("VALIDATION_ERROR", "Validation failed.", 422)
        tag = tag or None
    conditions = [Run.workspace_id == workspace_id]
    if state is not None:
        conditions.append(Run.state == state)
    if validity is not None:
        default_validity_run_type = "debug" if validity == "invalid" else "standard"
        conditions.append(
            or_(
                Run.validity == validity,
                and_(Run.validity.is_(None), Run.run_type == default_validity_run_type),
            )
        )
    if run_type is not None:
        conditions.append(Run.run_type == run_type)
    if source_type is not None:
        conditions.append(Run.source_type == source_type)
    test_plan_name = func.lower(RunSnapshot.snapshot_json["testPlan"]["name"].as_string())
    scenario_name = func.lower(RunSnapshot.snapshot_json["scenario"]["name"].as_string())
    test_plan_tags = func.lower(cast(RunSnapshot.snapshot_json["testPlan"]["tags"], Text))
    scenario_tags = func.lower(cast(RunSnapshot.snapshot_json["scenario"]["tags"], Text))
    if q is not None:
        q_like = f"%{_escape_like(q.lower())}%"
        conditions.append(
            or_(
                func.lower(Run.id).like(q_like, escape="\\"),
                test_plan_name.like(q_like, escape="\\"),
                scenario_name.like(q_like, escape="\\"),
            )
        )
    if tag is not None:
        tag_like = f'%"{_escape_like(tag.lower())}"%'
        conditions.append(
            or_(
                test_plan_tags.like(tag_like, escape="\\"),
                scenario_tags.like(tag_like, escape="\\"),
            )
        )
    if recent_hours is not None:
        if recent_hours <= 0:
            raise AppError("VALIDATION_ERROR", "Validation failed.", 422)
        conditions.append(Run.created_at >= utc_now() - timedelta(hours=recent_hours))
    if cursor:
        cursor_created_at, cursor_id = _cursor_decode(cursor)
        conditions.append(
            or_(
                Run.created_at < cursor_created_at,
                and_(Run.created_at == cursor_created_at, Run.id < cursor_id),
            )
        )
    now = utc_now()
    rows = db.execute(
        select(Run, RunSnapshot)
        .join(RunSnapshot, RunSnapshot.run_id == Run.id, isouter=True)
        .where(*conditions)
        .order_by(Run.created_at.desc(), Run.id.desc())
        .limit(limit + 1)
    ).all()
    batch = _batch_run_list_data(db, [run for run, _snapshot in rows])
    matched = [_list_item(db, run, snapshot, now=now, batch=batch) for run, snapshot in rows]
    next_cursor = None
    if len(matched) > limit:
        run = rows[limit - 1][0]
        next_cursor = _cursor_encode(run.created_at, run.id)
        matched = matched[:limit]
    return RunListResponse(items=matched, next_cursor=next_cursor)


def _get_run_with_snapshot(
    db: Session, *, workspace_id: str, run_id: str
) -> tuple[Run, RunSnapshot | None]:
    row = db.execute(
        select(Run, RunSnapshot)
        .join(RunSnapshot, RunSnapshot.run_id == Run.id, isouter=True)
        .where(Run.id == run_id, Run.workspace_id == workspace_id)
    ).first()
    if row is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    return row[0], row[1]


def _sla_result_for_report(run: Run, snapshot: dict[str, Any]) -> tuple[str, str | None]:
    result = run.sla_result or "not_evaluated"
    reason = run.sla_result_reason
    if result == "not_evaluated" and run.state in TERMINAL_STATES:
        mode = snapshot.get("slaEvaluationMode")
        if mode == "passfail":
            reason = reason or "missing_sla_result"
    return result, reason


def _summary_for_run(
    db: Session, run_id: str
) -> tuple[RunArtifact | None, RunReportSummary | None]:
    artifact = db.scalar(
        select(RunArtifact)
        .where(
            RunArtifact.run_id == run_id,
            RunArtifact.artifact_type == "final_stats_csv",
            RunArtifact.status == "available",
        )
        .order_by(RunArtifact.created_at.desc(), RunArtifact.id.desc())
        .limit(1)
    )
    if artifact is None:
        return None, None
    summary = db.scalar(
        select(RunReportSummary)
        .where(
            RunReportSummary.run_id == run_id,
            RunReportSummary.source_artifact_id == artifact.id,
            RunReportSummary.summary_type == "final_stats",
        )
        .order_by(RunReportSummary.updated_at.desc())
        .limit(1)
    )
    return artifact, summary


def _required_final_stats_allocations(db: Session, run_id: str) -> list[RunNodeAllocation]:
    return db.scalars(
        select(RunNodeAllocation)
        .where(RunNodeAllocation.run_id == run_id)
        .order_by(RunNodeAllocation.node_index.asc(), RunNodeAllocation.id.asc())
    ).all()


def _summary_for_artifact(db: Session, *, run_id: str, artifact_id: str) -> RunReportSummary | None:
    return db.scalar(
        select(RunReportSummary)
        .where(
            RunReportSummary.run_id == run_id,
            RunReportSummary.source_artifact_id == artifact_id,
            RunReportSummary.summary_type == "final_stats",
        )
        .order_by(RunReportSummary.updated_at.desc())
        .limit(1)
    )


def _allocation_missing_final_stats_status(allocation: RunNodeAllocation) -> tuple[str, str]:
    if allocation.state not in TERMINAL_STATES:
        return "pending", "allocation_pending_for_final_stats"
    if allocation.state == "failed" or allocation.quarantine_reason is not None:
        return "failed", "final_stats_missing_for_failed_allocations"
    return "missing", "final_stats_missing_for_allocations"


def _projection_from_single_artifact(
    db: Session, *, run_id: str, artifact: RunArtifact | None
) -> FinalStatsReportProjection:
    if artifact is None:
        return FinalStatsReportProjection(
            status="missing",
            missing_reasons=_missing_reasons("missing", None),
        )
    summary = _summary_for_artifact(db, run_id=run_id, artifact_id=artifact.id)
    if summary is None:
        return FinalStatsReportProjection(
            status="pending",
            artifact=artifact,
            summary=None,
            source_artifact_id=artifact.id,
            missing_reasons=_missing_reasons("pending", None),
        )
    if summary.parse_status != "parsed":
        status = "failed" if summary.parse_status == "failed" else "pending"
        return FinalStatsReportProjection(
            status=status,
            artifact=artifact,
            summary=summary,
            source_artifact_id=artifact.id,
            missing_reasons=_missing_reasons(status, summary),
            warnings=list((summary.summary_json or {}).get("warnings") or []),
            truncated=summary.truncated,
        )
    payload = summary.summary_json or {}
    return FinalStatsReportProjection(
        status="parsed",
        artifact=artifact,
        summary=summary,
        source_artifact_id=artifact.id,
        total=payload.get("total") if isinstance(payload.get("total"), dict) else None,
        rows=[row for row in payload.get("rows") or [] if isinstance(row, dict)],
        truncated=summary.truncated,
        missing_reasons=_missing_reasons("parsed", summary),
        warnings=list(payload.get("warnings") or []),
    )


def _single_allocation_final_stats_projection(
    db: Session, *, run_id: str, allocation: RunNodeAllocation
) -> FinalStatsReportProjection:
    artifacts = db.scalars(
        select(RunArtifact)
        .where(
            RunArtifact.run_id == run_id,
            RunArtifact.artifact_type == "final_stats_csv",
            RunArtifact.status == "available",
            RunArtifact.allocation_id == allocation.id,
        )
        .order_by(RunArtifact.created_at.desc(), RunArtifact.id.desc())
    ).all()
    if len(artifacts) > 1:
        return FinalStatsReportProjection(
            status="failed",
            missing_reasons=["final_stats_conflict_for_allocations"],
            warnings=["final_stats_conflict_for_allocations"],
        )
    if not artifacts:
        status, reason = _allocation_missing_final_stats_status(allocation)
        if reason == "final_stats_missing_for_allocations":
            return FinalStatsReportProjection(
                status="missing", missing_reasons=_missing_reasons("missing", None)
            )
        return FinalStatsReportProjection(
            status=status,
            missing_reasons=[reason],
            warnings=[reason],
        )
    artifact = artifacts[0]
    if artifact.node_id != allocation.node_id:
        return FinalStatsReportProjection(
            status="failed",
            missing_reasons=["final_stats_allocation_node_mismatch"],
            warnings=["final_stats_allocation_node_mismatch"],
        )
    projection = _projection_from_single_artifact(db, run_id=run_id, artifact=artifact)
    if artifact.terminal_late:
        warnings = list(projection.warnings or [])
        for code in ("terminal_late_final_stats_used",):
            if code not in warnings:
                warnings.append(code)
        return FinalStatsReportProjection(
            status=projection.status,
            artifact=projection.artifact,
            summary=projection.summary,
            source_artifact_id=projection.source_artifact_id,
            total=projection.total,
            rows=projection.rows,
            truncated=projection.truncated,
            missing_reasons=projection.missing_reasons,
            warnings=warnings,
        )
    return projection


def _numeric_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        numeric_value = int(value)
        return numeric_value if numeric_value >= 0 else None
    return None


def _numeric_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float) and math.isfinite(value):
        numeric_value = float(value)
        return numeric_value if numeric_value >= 0 else None
    return None


def _dedupe_codes(codes: list[str]) -> list[str]:
    result: list[str] = []
    for code in codes:
        if code not in result:
            result.append(code)
    return result


def _aggregate_final_stats_projection(
    contributors: list[tuple[RunArtifact, RunReportSummary]],
) -> FinalStatsReportProjection:
    warnings: list[str] = []
    total_requests_values: list[int] = []
    failed_requests_values: list[int] = []
    success_requests_values: list[int] = []
    average_terms: list[float] = []
    response_code_counts: dict[str, int] = {}
    truncated = False

    for artifact, summary in contributors:
        payload = summary.summary_json or {}
        total = payload.get("total") if isinstance(payload.get("total"), dict) else {}
        total_requests = _numeric_int(total.get("totalRequests"))
        failed_requests = _numeric_int(total.get("failedRequests"))
        success_requests = _numeric_int(total.get("successRequests"))
        average_ms = _numeric_float(total.get("averageResponseTimeMs"))
        if total_requests is not None:
            total_requests_values.append(total_requests)
        if failed_requests is not None:
            failed_requests_values.append(failed_requests)
        if success_requests is not None:
            success_requests_values.append(success_requests)
        if total_requests is not None and average_ms is not None:
            average_terms.append(average_ms * total_requests)
        raw_response_code_counts = total.get("responseCodeCounts")
        if isinstance(raw_response_code_counts, dict):
            for code, count in raw_response_code_counts.items():
                safe_count = _numeric_int(count)
                if safe_count is not None:
                    response_code_counts[str(code)] = (
                        response_code_counts.get(str(code), 0) + safe_count
                    )
        if artifact.terminal_late:
            warnings.append("terminal_late_final_stats_used")
        warnings.extend(
            str(item) for item in payload.get("warnings") or [] if isinstance(item, str)
        )
        truncated = truncated or bool(summary.truncated)

    contributor_count = len(contributors)
    all_totals_available = len(total_requests_values) == contributor_count
    all_failed_available = len(failed_requests_values) == contributor_count
    all_success_available = len(success_requests_values) == contributor_count
    total_requests = sum(total_requests_values) if all_totals_available else None
    failed_requests = sum(failed_requests_values) if all_failed_available else None
    success_requests = sum(success_requests_values) if all_success_available else None
    if total_requests is None or failed_requests is None or total_requests <= 0:
        error_rate = None
        warnings.append("aggregate_rate_denominator_unavailable")
    else:
        error_rate = failed_requests / total_requests
    if total_requests is None or total_requests <= 0 or len(average_terms) != contributor_count:
        average_response_time_ms = None
        warnings.append("aggregate_average_denominator_unavailable")
    else:
        average_response_time_ms = sum(average_terms) / total_requests
    warnings.append("percentile_aggregation_unsupported")
    warnings = _dedupe_codes(warnings)
    aggregate_total = {
        "label": None,
        "totalRequests": total_requests,
        "successRequests": success_requests,
        "failedRequests": failed_requests,
        "errorRate": error_rate,
        "averageResponseTimeMs": average_response_time_ms,
        "p90Ms": None,
        "p95Ms": None,
        "p99Ms": None,
        "responseCodeCounts": response_code_counts,
    }
    return FinalStatsReportProjection(
        status="parsed",
        source_artifact_id=None,
        total=aggregate_total,
        rows=[],
        truncated=truncated,
        missing_reasons=[],
        warnings=warnings,
    )


def _allocation_aware_final_stats_projection(
    db: Session, *, run_id: str
) -> FinalStatsReportProjection:
    allocations = _required_final_stats_allocations(db, run_id)
    if not allocations:
        artifact, _summary = _summary_for_run(db, run_id)
        return _projection_from_single_artifact(db, run_id=run_id, artifact=artifact)
    if len(allocations) == 1:
        return _single_allocation_final_stats_projection(
            db, run_id=run_id, allocation=allocations[0]
        )

    allocation_by_id = {allocation.id: allocation for allocation in allocations}
    artifacts = db.scalars(
        select(RunArtifact)
        .where(
            RunArtifact.run_id == run_id,
            RunArtifact.artifact_type == "final_stats_csv",
            RunArtifact.status == "available",
            RunArtifact.allocation_id.in_(allocation_by_id.keys()),
        )
        .order_by(
            RunArtifact.allocation_id.asc(), RunArtifact.created_at.desc(), RunArtifact.id.desc()
        )
    ).all()
    artifacts_by_allocation: dict[str, list[RunArtifact]] = {
        allocation.id: [] for allocation in allocations
    }
    for artifact in artifacts:
        if artifact.allocation_id in artifacts_by_allocation:
            artifacts_by_allocation[artifact.allocation_id].append(artifact)

    contributors: list[tuple[RunArtifact, RunReportSummary]] = []
    for allocation in allocations:
        candidates = artifacts_by_allocation[allocation.id]
        if not candidates:
            status, reason = _allocation_missing_final_stats_status(allocation)
            return FinalStatsReportProjection(
                status=status,
                missing_reasons=[reason],
                warnings=[reason],
            )
        if len(candidates) > 1:
            return FinalStatsReportProjection(
                status="failed",
                missing_reasons=["final_stats_conflict_for_allocations"],
                warnings=["final_stats_conflict_for_allocations"],
            )
        artifact = candidates[0]
        if artifact.node_id != allocation.node_id:
            return FinalStatsReportProjection(
                status="failed",
                missing_reasons=["final_stats_allocation_node_mismatch"],
                warnings=["final_stats_allocation_node_mismatch"],
            )
        summary = _summary_for_artifact(db, run_id=run_id, artifact_id=artifact.id)
        if summary is None or summary.parse_status == "pending":
            return FinalStatsReportProjection(
                status="pending",
                missing_reasons=["summary_pending_for_allocations"],
                warnings=["summary_pending_for_allocations"],
            )
        if summary.parse_status == "failed":
            return FinalStatsReportProjection(
                status="failed",
                missing_reasons=["summary_parse_failed_for_allocations"],
                warnings=["summary_parse_failed_for_allocations"],
            )
        contributors.append((artifact, summary))
    return _aggregate_final_stats_projection(contributors)


def _debug_trace_artifact(db: Session, run_id: str) -> RunArtifact | None:
    return db.scalar(
        select(RunArtifact)
        .where(
            RunArtifact.run_id == run_id,
            RunArtifact.artifact_type == DEBUG_HTTP_TRACE_ARTIFACT_TYPE,
            RunArtifact.status == "available",
        )
        .order_by(RunArtifact.created_at.desc(), RunArtifact.id.desc())
        .limit(1)
    )


def _debug_http_body_blob_artifact_ids_by_relative_path(
    db: Session, *, workspace_id: str, run_id: str
) -> dict[str, str]:
    artifacts = db.scalars(
        select(RunArtifact).where(
            RunArtifact.workspace_id == workspace_id,
            RunArtifact.run_id == run_id,
            RunArtifact.artifact_type == DEBUG_HTTP_BODY_BLOB_ARTIFACT_TYPE,
            RunArtifact.status == "available",
        )
    ).all()
    return {artifact.relative_path: artifact.id for artifact in artifacts}


def _debug_http_trace_for_run(
    db: Session, run: Run, artifact: RunArtifact | None
) -> DebugHttpTrace | None:
    if run.run_type != "debug" or run.source_type not in {"debug_scenario", "test_plan"}:
        return None
    if artifact is None:
        if run.state in TERMINAL_STATES:
            return DebugHttpTrace(
                status="unavailable",
                source_artifact_id=None,
                entry_count=0,
                trace_truncated=False,
                warnings=["debug_http_trace_missing"],
                entries=[],
            )
        return None
    settings = get_settings()
    blob_ids_by_path = _debug_http_body_blob_artifact_ids_by_relative_path(
        db, workspace_id=run.workspace_id, run_id=run.id
    )
    try:
        stored = get_storage_client().get_stream(
            bucket=artifact.storage_bucket
            if hasattr(artifact, "storage_bucket")
            else settings.minio_bucket,
            object_key=artifact.storage_key,
        )
        try:
            return parse_debug_http_trace_jsonl(
                stored.stream,
                source_artifact_id=artifact.id,
                max_requests=settings.debug_trace_max_requests,
                body_max_bytes=settings.debug_trace_body_max_bytes,
                artifact_max_bytes=settings.debug_trace_artifact_max_bytes,
                record_max_bytes=settings.debug_trace_record_max_bytes,
                body_blob_artifact_ids_by_relative_path=blob_ids_by_path,
            )
        finally:
            close = getattr(stored.stream, "close", None)
            if callable(close):
                close()
    except Exception:
        return DebugHttpTrace(
            status="unavailable",
            source_artifact_id=artifact.id,
            entry_count=0,
            trace_truncated=False,
            warnings=["debug_http_trace_unavailable"],
            entries=[],
        )


def _missing_reasons(status: str, summary: RunReportSummary | None) -> list[str]:
    if status == "missing":
        return ["final_stats_missing"]
    if status == "pending":
        return ["summary_pending"]
    if status == "failed":
        return ["summary_parse_failed"]
    warnings = [] if summary is None else list((summary.summary_json or {}).get("warnings") or [])
    mapping = {
        "percentile_column_missing": "percentile_column_missing",
        "percentile_value_invalid": "percentile_value_invalid",
        "average_response_time_missing": "average_response_time_missing",
        "average_response_time_invalid": "average_response_time_invalid",
    }
    return [mapping[item] for item in warnings if item in mapping]


def _kpi_summary(artifact: RunArtifact | None, summary: RunReportSummary | None) -> RunKpiSummary:
    if artifact is None:
        return RunKpiSummary(status="missing", missing_reasons=_missing_reasons("missing", None))
    if summary is None:
        return RunKpiSummary(
            status="pending",
            source_artifact_id=artifact.id,
            missing_reasons=_missing_reasons("pending", None),
        )
    if summary.parse_status != "parsed":
        status = "failed" if summary.parse_status == "failed" else "pending"
        return RunKpiSummary(
            status=status,
            source_artifact_id=artifact.id,
            missing_reasons=_missing_reasons(status, summary),
        )
    total = (summary.summary_json or {}).get("total") or {}
    return RunKpiSummary(
        status="parsed",
        source_artifact_id=artifact.id,
        total_requests=total.get("totalRequests"),
        failed_requests=total.get("failedRequests"),
        error_rate=total.get("errorRate"),
        average_response_time_ms=total.get("averageResponseTimeMs"),
        p90_ms=total.get("p90Ms"),
        p95_ms=total.get("p95Ms"),
        p99_ms=total.get("p99Ms"),
        throughput_per_second=None,
        missing_reasons=_missing_reasons("parsed", summary),
    )


def _kpi_summary_from_projection(projection: FinalStatsReportProjection) -> RunKpiSummary:
    if projection.status != "parsed":
        return RunKpiSummary(
            status=projection.status,  # type: ignore[arg-type]
            source_artifact_id=projection.source_artifact_id,
            missing_reasons=list(projection.missing_reasons or []),
        )
    total = projection.total or {}
    return RunKpiSummary(
        status="parsed",
        source_artifact_id=projection.source_artifact_id,
        total_requests=total.get("totalRequests"),
        failed_requests=total.get("failedRequests"),
        error_rate=total.get("errorRate"),
        average_response_time_ms=total.get("averageResponseTimeMs"),
        p90_ms=total.get("p90Ms"),
        p95_ms=total.get("p95Ms"),
        p99_ms=total.get("p99Ms"),
        throughput_per_second=None,
        missing_reasons=list(projection.missing_reasons or []),
    )


def _preview_row(data: dict[str, Any]) -> FinalStatsPreviewRow:
    return FinalStatsPreviewRow(
        label=data.get("label"),
        total_requests=data.get("totalRequests"),
        success_requests=data.get("successRequests"),
        failed_requests=data.get("failedRequests"),
        error_rate=data.get("errorRate"),
        average_response_time_ms=data.get("averageResponseTimeMs"),
        p90_ms=data.get("p90Ms"),
        p95_ms=data.get("p95Ms"),
        p99_ms=data.get("p99Ms"),
        response_code_counts=dict(data.get("responseCodeCounts") or {}),
    )


def _final_stats_preview(
    artifact: RunArtifact | None, summary: RunReportSummary | None
) -> FinalStatsPreview:
    if artifact is None:
        return FinalStatsPreview(status="missing", truncated=False, rows=[])
    if summary is None:
        return FinalStatsPreview(status="pending", truncated=False, rows=[])
    if summary.parse_status != "parsed":
        status = "failed" if summary.parse_status == "failed" else "pending"
        return FinalStatsPreview(
            status=status,
            truncated=summary.truncated,
            rows=[],
            warnings=list((summary.summary_json or {}).get("warnings") or []),
        )
    payload = summary.summary_json or {}
    rows: list[FinalStatsPreviewRow] = []
    total = payload.get("total")
    if isinstance(total, dict):
        rows.append(_preview_row(total))
    rows.extend(_preview_row(row) for row in payload.get("rows") or [] if isinstance(row, dict))
    return FinalStatsPreview(
        status="parsed",
        truncated=summary.truncated,
        rows=rows,
        warnings=list(payload.get("warnings") or []),
    )


def _final_stats_preview_from_projection(
    projection: FinalStatsReportProjection,
) -> FinalStatsPreview:
    if projection.status != "parsed":
        return FinalStatsPreview(
            status=projection.status,  # type: ignore[arg-type]
            truncated=projection.truncated,
            rows=[],
            warnings=list(projection.warnings or []),
        )
    rows: list[FinalStatsPreviewRow] = []
    if isinstance(projection.total, dict):
        rows.append(_preview_row(projection.total))
    rows.extend(_preview_row(row) for row in projection.rows or [] if isinstance(row, dict))
    return FinalStatsPreview(
        status="parsed",
        truncated=projection.truncated,
        rows=rows,
        warnings=list(projection.warnings or []),
    )


def _safe_text(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int | float):
        return str(raw)
    return None


def _safe_int(raw: Any) -> int | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return int(value)


def _safe_float(raw: Any) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def _snapshot_load_settings(payload: dict[str, Any]) -> RunSnapshotLoadSettings:
    return RunSnapshotLoadSettings(
        concurrency_per_node=_safe_int(payload.get("concurrencyPerNode")),
        ramp_up_seconds=_safe_int(payload.get("rampUpSeconds")),
        hold_for_seconds=_safe_int(payload.get("holdForSeconds")),
        iterations=_safe_int(payload.get("iterations")),
        target_rps=_safe_float(payload.get("targetRps")),
        steps=_safe_int(payload.get("steps")),
        delay_seconds=_safe_int(payload.get("delaySeconds")),
    )


def _snapshot_scenario_items(
    snapshot: dict[str, Any], scenario_items: list[Any], scenario: dict[str, Any] | None
) -> list[RunSnapshotScenarioItem]:
    items: list[RunSnapshotScenarioItem] = []
    for item in scenario_items:
        if not isinstance(item, dict):
            continue
        name = _safe_text(item.get("scenarioName"))
        settings = item.get("loadSettings")
        if not name or not isinstance(settings, dict):
            continue
        items.append(
            RunSnapshotScenarioItem(
                scenario_name=str(name),
                load_settings=_snapshot_load_settings(settings),
            )
        )
    if not items and scenario and scenario.get("name"):
        debug_profile = (
            snapshot.get("debugProfile") if isinstance(snapshot.get("debugProfile"), dict) else {}
        )
        items.append(
            RunSnapshotScenarioItem(
                scenario_name=str(scenario["name"]),
                load_settings=RunSnapshotLoadSettings(
                    concurrency_per_node=_safe_int(debug_profile.get("concurrency")),
                    iterations=_safe_int(debug_profile.get("iterations")),
                ),
            )
        )
    return items[:10]


def _threshold_text(threshold: Any) -> str | None:
    if not isinstance(threshold, dict):
        return None
    if threshold.get("value") is None or threshold.get("unit") is None:
        return None
    try:
        return str(sla_threshold_text(threshold))
    except (ArithmeticError, KeyError, TypeError, ValueError):
        return None


def _snapshot_sla_rules(snapshot: dict[str, Any]) -> list[RunSnapshotSlaRule]:
    rules = snapshot.get("slaRules") if isinstance(snapshot.get("slaRules"), list) else []
    result: list[RunSnapshotSlaRule] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        result.append(
            RunSnapshotSlaRule(
                metric=_safe_text(rule.get("metric") or rule.get("subject")),
                condition=_safe_text(rule.get("condition")),
                threshold_text=_safe_text(rule.get("thresholdText"))
                or _threshold_text(rule.get("threshold")),
            )
        )
    return result[:20]


def _dependency_file_names(snapshot: dict[str, Any]) -> list[str]:
    files = (
        snapshot.get("dependencyFiles") if isinstance(snapshot.get("dependencyFiles"), list) else []
    )
    names = [
        str(item.get("filename") or item.get("displayName"))
        for item in files
        if isinstance(item, dict) and (item.get("filename") or item.get("displayName"))
    ]
    return names[:20]


def _env_group_variable_keys(env: dict[str, Any] | None) -> list[str]:
    variables = env.get("variables") if env else None
    if not isinstance(variables, dict):
        return []
    return sorted(str(key) for key in variables.keys())[:50]


def _snapshot_summary(snapshot: dict[str, Any], run: Run) -> RunSnapshotSummary:
    source_name, source_revision, _tags = _snapshot_source(snapshot, run)
    env = snapshot.get("envGroup") if isinstance(snapshot.get("envGroup"), dict) else None
    plan = snapshot.get("testPlan") if isinstance(snapshot.get("testPlan"), dict) else None
    scenario = snapshot.get("scenario") if isinstance(snapshot.get("scenario"), dict) else None
    scenario_items = (
        snapshot.get("scenarioItems") if isinstance(snapshot.get("scenarioItems"), list) else []
    )
    scenario_names = [
        str(item.get("scenarioName"))
        for item in scenario_items
        if isinstance(item, dict) and item.get("scenarioName")
    ]
    if scenario and scenario.get("name"):
        scenario_names = [str(scenario["name"])]
    resource = (
        snapshot.get("resourceRequest")
        if isinstance(snapshot.get("resourceRequest"), dict)
        else None
    )
    selected_node_ids = [run.selected_node_id]
    if resource:
        raw_selected_node_ids = resource.get("selectedNodeIds")
        if isinstance(raw_selected_node_ids, list) and raw_selected_node_ids:
            selected_node_ids = list(raw_selected_node_ids)
        elif resource.get("selectedNodeId"):
            selected_node_ids = [resource["selectedNodeId"]]
    scenario_details = _snapshot_scenario_items(snapshot, scenario_items, scenario)
    return RunSnapshotSummary(
        schema_version=int(snapshot.get("schemaVersion") or snapshot.get("snapshotVersion") or 1),
        source_name=source_name,
        source_revision=source_revision,
        env_group_name=env.get("name") if env else None,
        run_mode=plan.get("runMode") if plan else None,
        scenario_count=len(scenario_items) if scenario_items else (1 if scenario else 0),
        scenario_names=scenario_names[:10],
        scenario_items=scenario_details,
        sla_rule_count=len(snapshot.get("slaRules") or []),
        sla_rules=_snapshot_sla_rules(snapshot),
        dependency_file_count=len(snapshot.get("dependencyFiles") or []),
        dependency_file_names=_dependency_file_names(snapshot),
        env_group_variable_keys=_env_group_variable_keys(env),
        resource_request=RunSnapshotResourceRequest(
            mode=resource.get("mode") if resource else "manual",
            pool_type=resource.get("poolType") if resource else None,
            selected_node_id=resource.get("selectedNodeId") if resource else run.selected_node_id,
            selected_node_ids=selected_node_ids,
            node_count=resource.get("nodeCount") if resource else None,
            expected_concurrency_per_node=resource.get("expectedConcurrencyPerNode")
            if resource
            else None,
        ),
    )


def _allocation_rows(
    db: Session, run: Run
) -> list[tuple[RunNodeAllocation, RunSelectedNode, LoadNode | None]]:
    allocations = list(
        db.scalars(
            select(RunNodeAllocation)
            .where(RunNodeAllocation.run_id == run.id)
            .order_by(RunNodeAllocation.node_index.asc())
        ).all()
    )
    rows: list[tuple[RunNodeAllocation, RunSelectedNode, LoadNode | None]] = []
    for allocation in allocations:
        node = db.get(LoadNode, allocation.node_id)
        rows.append(
            (
                allocation,
                RunSelectedNode(
                    id=allocation.node_id,
                    name=f"Load Node {allocation.node_id[-6:]}",
                    scope=node.scope if node is not None else "unknown",
                ),
                node,
            )
        )
    return rows


def get_run_report(db: Session, *, workspace_id: str, run_id: str) -> RunReportDetail:
    run, snapshot_row = _get_run_with_snapshot(db, workspace_id=workspace_id, run_id=run_id)
    snapshot = snapshot_row.snapshot_json if snapshot_row is not None else {}
    final_stats_projection = _allocation_aware_final_stats_projection(db, run_id=run.id)
    artifact_count, has_zip, has_final_stats, latest = _artifact_counts(db, run.id)
    debug_trace_artifact = _debug_trace_artifact(db, run.id)
    allocation_rows = _allocation_rows(db, run)
    sla_result, sla_reason = _sla_result_for_report(run, snapshot)
    notes: list[str] = _dedupe_codes(list(final_stats_projection.missing_reasons or []))
    if run.forced_convergence:
        notes.append("forced_convergence")
    return RunReportDetail(
        id=run.id,
        verdict=RunVerdict(
            state=run.state,
            run_type=run.run_type,
            source_type=run.source_type,
            validity=run.validity or ("invalid" if run.run_type == "debug" else "valid"),
            sla_result=sla_result,
            sla_result_reason=sla_reason,
            duration_ms=_duration_ms(run, now=utc_now()),
            triggered_by=_run_actor(db, run.triggered_by_user_id),
            created_at=iso_z(run.created_at) or "",
            accepted_at=iso_z(run.accepted_at),
            started_at=iso_z(run.started_at),
            ended_at=iso_z(run.ended_at),
            last_heartbeat_at=iso_z(run.last_heartbeat_at),
            failure_reason=run.failure_reason,
            failure_message=run.failure_message,
            forced_convergence=run.forced_convergence,
            warnings=notes,
        ),
        kpi_summary=_kpi_summary_from_projection(final_stats_projection),
        failure_diagnostics=FailureDiagnostics(
            failure_reason=run.failure_reason,
            failure_message=run.failure_message,
            has_failed_requests_preview=False,
            notes=notes,
        ),
        final_stats_preview=_final_stats_preview_from_projection(final_stats_projection),
        debug_http_trace=_debug_http_trace_for_run(db, run, debug_trace_artifact),
        snapshot=_snapshot_summary(snapshot, run),
        artifacts_summary=RunArtifactsSummary(
            count=artifact_count,
            has_artifacts_zip=has_zip,
            has_final_stats_csv=has_final_stats,
            latest_available_at=iso_z(latest),
        ),
        allocated_nodes=[
            RunAllocatedNode(
                id=selected.id,
                name=selected.name,
                scope=selected.scope,
                node_index=allocation.node_index,
                total_nodes=allocation.total_nodes,
                state=allocation.state,
                last_heartbeat_at=iso_z(
                    allocation.last_heartbeat_at
                    or (node.last_heartbeat_at if node is not None else None)
                ),
                terminal_reason=allocation.terminal_reason,
                cleanup_status=allocation.cleanup_status,
                quarantine_reason=allocation.quarantine_reason,
                sla_result=allocation.sla_result,
            )
            for allocation, selected, node in allocation_rows
        ],
    )


def _artifact_cursor_condition(cursor: str, sort: str):
    created_at, artifact_id = _cursor_decode(cursor)
    if sort == "createdAt":
        return or_(
            RunArtifact.created_at > created_at,
            and_(RunArtifact.created_at == created_at, RunArtifact.id > artifact_id),
        )
    return or_(
        RunArtifact.created_at < created_at,
        and_(RunArtifact.created_at == created_at, RunArtifact.id < artifact_id),
    )


def _artifact_item(artifact: RunArtifact) -> RunArtifactItem:
    return RunArtifactItem(
        id=artifact.id,
        node_id=artifact.node_id,
        allocation_id=artifact.allocation_id,
        artifact_type=artifact.artifact_type,
        relative_path=artifact.relative_path,
        display_filename=artifact.display_filename,
        size_bytes=artifact.size_bytes,
        sha256=artifact.sha256,
        content_type=artifact.content_type,
        terminal_late=artifact.terminal_late,
        created_at=iso_z(artifact.created_at) or "",
        available_at=iso_z(artifact.created_at) if artifact.status == "available" else None,
        download_url=f"/api/v1/runs/{artifact.run_id}/artifacts/{artifact.id}/download",
    )


def list_run_artifacts_report(
    db: Session,
    *,
    workspace_id: str,
    run_id: str,
    artifact_type: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    sort: str = "createdAt",
) -> RunArtifactListResponse:
    _get_run_with_snapshot(db, workspace_id=workspace_id, run_id=run_id)
    if limit < 1 or limit > 100 or sort not in {"createdAt", "-createdAt"}:
        raise AppError("VALIDATION_ERROR", "Validation failed.", 422)
    if artifact_type is not None and artifact_type not in PUBLIC_ARTIFACT_TYPES:
        raise AppError("VALIDATION_ERROR", "Validation failed.", 422)
    conditions = [
        RunArtifact.workspace_id == workspace_id,
        RunArtifact.run_id == run_id,
        RunArtifact.status == "available",
        RunArtifact.artifact_type.in_(PUBLIC_ARTIFACT_TYPES),
    ]
    if artifact_type is not None:
        conditions.append(RunArtifact.artifact_type == artifact_type)
    if cursor:
        conditions.append(_artifact_cursor_condition(cursor, sort))
    order = (RunArtifact.created_at.asc(), RunArtifact.id.asc())
    if sort == "-createdAt":
        order = (RunArtifact.created_at.desc(), RunArtifact.id.desc())
    artifacts = db.scalars(
        select(RunArtifact).where(*conditions).order_by(*order).limit(limit + 1)
    ).all()
    items = [_artifact_item(artifact) for artifact in artifacts[:limit]]
    next_cursor = None
    if len(artifacts) > limit:
        last = artifacts[limit - 1]
        next_cursor = _cursor_encode(last.created_at, last.id)
    return RunArtifactListResponse(items=items, next_cursor=next_cursor)


def get_run_artifact_download(
    db: Session,
    *,
    workspace_id: str,
    run_id: str,
    artifact_id: str,
) -> ArtifactDownload:
    _get_run_with_snapshot(db, workspace_id=workspace_id, run_id=run_id)
    artifact = db.scalar(
        select(RunArtifact).where(
            RunArtifact.id == artifact_id,
            RunArtifact.run_id == run_id,
            RunArtifact.workspace_id == workspace_id,
        )
    )
    if artifact is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    if artifact.artifact_type not in PUBLIC_ARTIFACT_TYPES:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    if artifact.status != "available":
        raise AppError("ARTIFACT_NOT_READY", "Artifact is not ready.", 409)
    stored = get_storage_client().get_stream(
        bucket=get_settings().minio_bucket,
        object_key=artifact.storage_key,
    )
    return ArtifactDownload(artifact=artifact, stored=stored)


def get_debug_http_body_blob_download(
    db: Session,
    *,
    workspace_id: str,
    run_id: str,
    artifact_id: str,
) -> ArtifactDownload:
    run, _snapshot = _get_run_with_snapshot(db, workspace_id=workspace_id, run_id=run_id)
    if run.run_type != "debug" or run.source_type not in {"debug_scenario", "test_plan"}:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    artifact = db.scalar(
        select(RunArtifact).where(
            RunArtifact.id == artifact_id,
            RunArtifact.run_id == run_id,
            RunArtifact.workspace_id == workspace_id,
            RunArtifact.artifact_type == DEBUG_HTTP_BODY_BLOB_ARTIFACT_TYPE,
        )
    )
    if artifact is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    if artifact.status != "available":
        raise AppError("ARTIFACT_NOT_READY", "Artifact is not ready.", 409)
    stored = get_storage_client().get_stream(
        bucket=get_settings().minio_bucket,
        object_key=artifact.storage_key,
    )
    return ArtifactDownload(artifact=artifact, stored=stored)


def update_run_validity(
    db: Session,
    *,
    workspace_id: str,
    run_id: str,
    validity: str,
    actor: User,
    request: Request | None = None,
) -> RunValidityPatchResponse:
    run = db.scalar(
        select(Run)
        .where(Run.id == run_id, Run.workspace_id == workspace_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    if validity not in {"valid", "invalid"}:
        raise AppError("VALIDATION_ERROR", "Validation failed.", 422)
    old_validity = run.validity or ("invalid" if run.run_type == "debug" else "valid")
    now = utc_now()
    changed = old_validity != validity
    run.validity = validity
    run.validity_updated_by_user_id = actor.id
    run.validity_updated_at = now
    run.updated_at = now
    if changed:
        write_audit_event(
            db,
            event_type="run.validity_changed",
            request=request,
            actor_user_id=actor.id,
            workspace_id=workspace_id,
            target_type="run",
            target_id=run.id,
            details={
                "runId": run.id,
                "workspaceId": workspace_id,
                "oldValidity": old_validity,
                "newValidity": validity,
                "requestId": getattr(request.state, "request_id", None) if request else None,
            },
        )
    db.flush()
    return RunValidityPatchResponse(
        id=run.id,
        validity=run.validity,
        validity_updated_at=iso_z(run.validity_updated_at) or "",
        validity_updated_by=RunActor(id=actor.id, email=actor.email),
    )


__all__ = [
    "FINAL_STATS_TOTAL_ROW_MISSING",
    "parse_final_stats_csv",
    "parse_and_store_final_stats_summary",
    "create_pending_final_stats_summary",
    "process_next_pending_final_stats_summary",
    "list_runs_report",
    "get_run_report",
    "list_run_artifacts_report",
    "get_run_artifact_download",
    "update_run_validity",
]
