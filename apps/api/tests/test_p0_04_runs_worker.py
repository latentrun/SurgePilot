from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.auth import DEFAULT_WORKSPACE_ID, User
from app.models.runs import NodeLease, RunControlRequest, RunnerCallbackEvent
from app.schemas.load_nodes import LoadNodeCredentialInput
from app.services.load_nodes import create_load_node
from app.services.runs import (
    FakeRunControlExecutor,
    RunControlCommand,
    RunControlExecutionResult,
    RunControlExecutor,
    create_protocol_smoke_run,
    enqueue_control_request,
)
from app.worker import RUN_PROTOCOL_ADVISORY_LOCK, run_once


def trusted_host_key() -> dict[str, str]:
    return {
        "algorithm": "ssh-ed25519",
        "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        "fingerprintSha256": "SHA256:SurgePilotTrustedHostKey",
    }


class RecordingRunControlExecutor(RunControlExecutor):
    def __init__(self, result: RunControlExecutionResult | None = None) -> None:
        self.result = result or RunControlExecutionResult(ok=True)
        self.commands: list[RunControlCommand] = []

    def execute(self, command: RunControlCommand) -> RunControlExecutionResult:
        self.commands.append(command)
        return self.result


class SequencedRunControlExecutor(RunControlExecutor):
    def __init__(self, results: list[RunControlExecutionResult]) -> None:
        self.results = iter(results)
        self.commands: list[RunControlCommand] = []

    def execute(self, command: RunControlCommand) -> RunControlExecutionResult:
        self.commands.append(command)
        return next(self.results)


class RaisingRunControlExecutor(RunControlExecutor):
    def execute(self, command: RunControlCommand) -> RunControlExecutionResult:
        _ = command
        raise RuntimeError("boom")


@pytest.fixture(autouse=True)
def worker_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "SSH_CREDENTIAL_ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
    )

    from app.services.ssh_remote import ScannedSshHostKey

    def fake_scan(host: str, port: int, timeout_seconds: int) -> ScannedSshHostKey:
        _ = host, port, timeout_seconds
        return ScannedSshHostKey(
            host=host,
            port=port,
            algorithm="ssh-ed25519",
            public_key="AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
            fingerprint_sha256="SHA256:SurgePilotTrustedHostKey",
        )

    monkeypatch.setattr("app.services.load_nodes.scan_ssh_host_key", fake_scan)


def actor() -> User:
    now = datetime.now(UTC)
    return User(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        email="worker-run@example.com",
        display_name="Worker User",
        password_hash="hash",
        role="user",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )


def seed_run(db_session: Session, monkeypatch, *, state: str = "initializing"):
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    db_session.add(user)
    db_session.flush()
    node = create_load_node(
        db_session,
        actor=user,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host=f"worker-node-{state}.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=LoadNodeCredentialInput(authType="password", password="secret-password"),
        ssh_host_key=trusted_host_key(),
        maintainer=None,
        remark=None,
    )
    node.status = "idle"
    db_session.flush()
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    run.state = state
    db_session.flush()
    db_session.commit()
    return node, run


def worker_factory(db_session: Session) -> sessionmaker:
    return sessionmaker(
        bind=db_session.get_bind(), autoflush=False, expire_on_commit=False, future=True
    )


def test_worker_completes_start_request_without_marking_running(
    db_session: Session, monkeypatch
) -> None:
    _node, run = seed_run(db_session, monkeypatch)
    executor = RecordingRunControlExecutor()

    assert run_once(worker_factory(db_session), run_control_executor=executor) >= 1

    db_session.expire_all()
    assert db_session.get(type(run), run.id).state == "initializing"
    request = db_session.scalar(
        select(RunControlRequest).where(RunControlRequest.run_id == run.id)
    )
    assert request is not None
    assert request.status == "succeeded"
    assert [command.action for command in executor.commands] == ["start"]
    assert executor.commands[0].run_id == run.id
    assert executor.commands[0].node_id == run.selected_node_id
    assert executor.commands[0].argv == (
        "python3",
        "/opt/surgepilot/runner/runner.py",
        "start",
        "--run-id",
        run.id,
        "--fake",
    )


def test_worker_marks_start_failed_when_executor_fails(
    db_session: Session, monkeypatch
) -> None:
    node, run = seed_run(db_session, monkeypatch)
    executor = RecordingRunControlExecutor(
        RunControlExecutionResult(
            ok=False,
            error_code="RUNNER_START_FAILED",
            message="Runner start command failed.",
            stderr_preview="safe stderr",
            quarantine_node=False,
        )
    )

    assert run_once(worker_factory(db_session), run_control_executor=executor) >= 1

    db_session.expire_all()
    run = db_session.get(type(run), run.id)
    node = db_session.get(type(node), node.id)
    request = db_session.scalar(
        select(RunControlRequest).where(RunControlRequest.run_id == run.id)
    )
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert run is not None and run.state == "failed"
    assert run.failure_reason == "runner_start_failed"
    assert node is not None and node.status == "idle"
    assert node.current_run_id is None
    assert lease is not None and lease.released_at is not None
    assert request is not None and request.status == "failed"
    assert request.last_error_code == "RUNNER_START_FAILED"
    assert len(executor.commands) == 1


@pytest.mark.parametrize("cleanup_succeeds", [True, False])
def test_worker_converges_uncertain_start_through_force_kill(
    db_session: Session, monkeypatch, cleanup_succeeds: bool
) -> None:
    node, run = seed_run(db_session, monkeypatch)
    executor = SequencedRunControlExecutor(
        [
            RunControlExecutionResult(
                ok=False,
                error_code="RUN_CONTROL_TIMEOUT",
                message="Run control command timed out.",
                timed_out=True,
                quarantine_node=False,
                cleanup_required=True,
            ),
            RunControlExecutionResult(
                ok=cleanup_succeeds,
                error_code=None if cleanup_succeeds else "RUN_CONTROL_TIMEOUT",
                message=None if cleanup_succeeds else "Run control command timed out.",
                timed_out=not cleanup_succeeds,
            ),
        ]
    )

    assert run_once(worker_factory(db_session), run_control_executor=executor) >= 2

    db_session.expire_all()
    node = db_session.get(type(node), node.id)
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    requests = db_session.scalars(
        select(RunControlRequest)
        .where(RunControlRequest.run_id == run.id)
        .order_by(RunControlRequest.created_at)
    ).all()
    assert [command.action for command in executor.commands] == ["start", "force_kill"]
    assert requests[1].action == "force_kill"
    assert lease is not None and lease.released_at is not None
    assert node is not None
    assert node.current_run_id is None
    assert node.status == ("idle" if cleanup_succeeds else "quarantined")
    assert lease.release_reason == (
        "force_kill_success" if cleanup_succeeds else "force_kill_failed"
    )


def test_worker_marks_request_failed_when_executor_raises(
    db_session: Session, monkeypatch
) -> None:
    node, run = seed_run(db_session, monkeypatch)

    assert (
        run_once(worker_factory(db_session), run_control_executor=RaisingRunControlExecutor()) >= 1
    )

    db_session.expire_all()
    run = db_session.get(type(run), run.id)
    node = db_session.get(type(node), node.id)
    start_request = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id, RunControlRequest.action == "start"
        )
    )
    assert run is not None and run.state == "failed"
    assert node is not None and node.status == "quarantined"
    assert start_request is not None and start_request.status == "failed"
    assert start_request.last_error_code == "RUN_CONTROL_EXECUTION_FAILED"


def test_worker_preserves_credential_failure_without_quarantining_node(
    db_session: Session, monkeypatch
) -> None:
    node, run = seed_run(db_session, monkeypatch)
    executor = RecordingRunControlExecutor(
        RunControlExecutionResult(
            ok=False,
            error_code="CREDENTIAL_DECRYPT_FAILED",
            message="Credential encryption is not configured.",
            quarantine_node=False,
        )
    )

    assert run_once(worker_factory(db_session), run_control_executor=executor) >= 1

    db_session.expire_all()
    run = db_session.get(type(run), run.id)
    node = db_session.get(type(node), node.id)
    request = db_session.scalar(
        select(RunControlRequest).where(RunControlRequest.run_id == run.id)
    )
    assert run is not None and run.state == "failed"
    assert run.failure_reason == "runner_start_failed"
    assert run.failure_message == "Credential encryption is not configured."
    assert node is not None and node.status == "idle"
    assert request is not None and request.status == "failed"
    assert request.last_error_code == "CREDENTIAL_DECRYPT_FAILED"
    assert request.last_error_message == "Credential encryption is not configured."


def test_worker_does_not_execute_stale_start_request_after_terminal_convergence(
    db_session: Session, monkeypatch
) -> None:
    _node, run = seed_run(db_session, monkeypatch)
    run.state = "failed"
    db_session.commit()
    executor = RecordingRunControlExecutor()

    assert run_once(worker_factory(db_session), run_control_executor=executor) >= 1

    db_session.expire_all()
    request = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id, RunControlRequest.action == "start"
        )
    )
    assert request is not None and request.status == "cancelled"
    assert request.last_error_code == "RUN_CONTROL_OBSOLETE"
    assert [command.action for command in executor.commands] == ["force_kill"]


def test_worker_cancels_stale_start_request_after_stop_without_quarantine(
    db_session: Session, monkeypatch
) -> None:
    node, run = seed_run(db_session, monkeypatch)
    run.state = "stopping"
    db_session.commit()
    executor = RecordingRunControlExecutor()

    run_once(worker_factory(db_session), run_control_executor=executor)

    db_session.expire_all()
    request = db_session.scalar(
        select(RunControlRequest).where(RunControlRequest.run_id == run.id)
    )
    run = db_session.get(type(run), run.id)
    node = db_session.get(type(node), node.id)
    assert request is not None and request.status == "cancelled"
    assert request.last_error_code == "RUN_CONTROL_OBSOLETE"
    assert run is not None and run.state == "stopping"
    assert node is not None and node.status == "busy"
    assert node.current_run_id == run.id
    assert executor.commands == []


def test_worker_sweeps_accept_timeout_and_recovers_stale_terminal_lease(
    db_session: Session, monkeypatch
) -> None:
    node, run = seed_run(db_session, monkeypatch)
    run.remote_start_requested_at = datetime.now(UTC) - timedelta(seconds=500)
    db_session.commit()
    executor = RecordingRunControlExecutor()

    assert run_once(worker_factory(db_session), run_control_executor=executor) >= 1

    db_session.expire_all()
    run = db_session.get(type(run), run.id)
    node = db_session.get(type(node), node.id)
    assert run is not None and run.state == "failed"
    assert run.failure_reason == "runner_accept_timeout"
    assert node is not None and node.status == "idle"
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert lease is not None and lease.released_at is not None
    assert [command.action for command in executor.commands] == ["force_kill"]


def test_worker_sweeps_heartbeat_timeout(db_session: Session, monkeypatch) -> None:
    node, run = seed_run(db_session, monkeypatch, state="running")
    old = datetime.now(UTC) - timedelta(seconds=500)
    run.started_at = old
    run.last_heartbeat_at = old
    db_session.commit()
    executor = RecordingRunControlExecutor()

    assert run_once(worker_factory(db_session), run_control_executor=executor) >= 1

    db_session.expire_all()
    run = db_session.get(type(run), run.id)
    node = db_session.get(type(node), node.id)
    assert run is not None and run.state == "failed"
    assert run.failure_reason == "heartbeat_timeout"
    assert node is not None and node.status == "idle"
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert lease is not None and lease.released_at is not None
    assert [command.action for command in executor.commands] == ["force_kill"]


def test_worker_sweeps_stop_grace_timeout(db_session: Session, monkeypatch) -> None:
    node, run = seed_run(db_session, monkeypatch)
    run.state = "stopping"
    run.stop_requested_at = datetime.now(UTC) - timedelta(seconds=500)
    db_session.commit()
    executor = RecordingRunControlExecutor()

    assert run_once(worker_factory(db_session), run_control_executor=executor) >= 1

    db_session.expire_all()
    run = db_session.get(type(run), run.id)
    node = db_session.get(type(node), node.id)
    assert run is not None and run.state == "aborted"
    assert run.failure_reason == "stop_grace_timeout"
    assert run.forced_convergence is True
    assert node is not None and node.status == "idle"
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert lease is not None and lease.released_at is not None
    assert [command.action for command in executor.commands] == ["force_kill"]


def test_worker_recovers_and_executes_stale_running_force_kill_request(
    db_session: Session, monkeypatch
) -> None:
    node, run = seed_run(db_session, monkeypatch)
    start_request = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id, RunControlRequest.action == "start"
        )
    )
    assert start_request is not None
    start_request.status = "cancelled"
    run.state = "failed"
    force_kill = enqueue_control_request(
        db_session, run=run, action="force_kill", reason="heartbeat_timeout"
    )
    force_kill.status = "running"
    force_kill.claimed_at = datetime.now(UTC) - timedelta(seconds=500)
    force_kill.claimed_by = "dead-worker"
    db_session.commit()
    executor = RecordingRunControlExecutor()

    assert run_once(worker_factory(db_session), run_control_executor=executor) >= 1

    db_session.expire_all()
    node = db_session.get(type(node), node.id)
    force_kill = db_session.get(RunControlRequest, force_kill.id)
    assert force_kill is not None and force_kill.status == "succeeded"
    assert node is not None and node.status == "idle"
    assert [command.action for command in executor.commands] == ["force_kill"]


def test_worker_deletes_old_callback_events(db_session: Session, monkeypatch) -> None:
    _node, run = seed_run(db_session, monkeypatch)
    old = datetime.now(UTC) - timedelta(days=31)
    event = RunnerCallbackEvent(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_id=run.id,
        node_id=run.selected_node_id,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7D",
        event_type="heartbeat",
        seq=1,
        event_time=old,
        received_at=old,
        request_id="req-old",
        payload_sha256="a" * 64,
        payload_json={"safe": True},
        duplicate_count=0,
        created_at=old,
    )
    db_session.add(event)
    event_id = event.id
    db_session.commit()

    run_once(worker_factory(db_session), run_control_executor=FakeRunControlExecutor())

    db_session.expire_all()
    assert db_session.get(RunnerCallbackEvent, event_id) is None
    assert RUN_PROTOCOL_ADVISORY_LOCK != 9303
