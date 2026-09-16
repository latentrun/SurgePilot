from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import AppError
from app.models.auth import DEFAULT_WORKSPACE_ID, User
from app.models.load_nodes import LoadNodeInitializationAttempt
from app.services.load_nodes import create_load_node
from app.services.load_nodes import InitResult, LoadNodeInitializer
from app.schemas.load_nodes import LoadNodeCredentialInput
from app.worker import run_once


def trusted_host_key() -> dict[str, str]:
    return {
        "algorithm": "ssh-ed25519",
        "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        "fingerprintSha256": "SHA256:SurgePilotTrustedHostKey",
    }


class SuccessfulInitializer(LoadNodeInitializer):
    def initialize(self, node, credential):  # noqa: ANN001
        _ = credential
        return InitResult(
            ok=True,
            log=f"[info] prepared {node.runner_home}",
            message="Initialization succeeded.",
            runner_version="0.1.0",
            bundle_version="p0-03",
        )


def queue_private_node_initialization(
    db_session: Session,
    *,
    actor_id: str,
    attempt_id: str,
    email: str,
    host: str,
) -> tuple[LoadNodeInitializationAttempt, object]:
    now = datetime.now(UTC)
    actor = User(
        id=actor_id,
        email=email,
        display_name="Worker",
        password_hash="hash",
        role="user",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(actor)
    db_session.flush()
    node = create_load_node(
        db_session,
        actor=actor,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host=host,
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=LoadNodeCredentialInput(authType="password", password="secret"),
        ssh_host_key=trusted_host_key(),
        maintainer=None,
        remark=None,
    )
    attempt = LoadNodeInitializationAttempt(
        id=attempt_id,
        node_id=node.id,
        status="queued",
        requested_by=actor.id,
        message="Initialization queued.",
        created_at=now,
        updated_at=now,
    )
    node.status = "initializing"
    node.last_init_attempt_id = attempt.id
    db_session.add(attempt)
    db_session.commit()
    return attempt, node


def test_api_worker_run_once_processes_queued_attempt(db_session: Session) -> None:
    now = datetime.now(UTC)
    actor = User(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        email="worker@example.com",
        display_name="Worker",
        password_hash="hash",
        role="user",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(actor)
    db_session.flush()
    node = create_load_node(
        db_session,
        actor=actor,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host="worker-node.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=LoadNodeCredentialInput(authType="password", password="secret"),
        ssh_host_key=trusted_host_key(),
        maintainer=None,
        remark=None,
    )
    attempt = LoadNodeInitializationAttempt(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7D",
        node_id=node.id,
        status="queued",
        requested_by=actor.id,
        message="Initialization queued.",
        created_at=now,
        updated_at=now,
    )
    node.status = "initializing"
    node.last_init_attempt_id = attempt.id
    db_session.add(attempt)
    db_session.commit()

    factory = sessionmaker(
        bind=db_session.bind, autoflush=False, expire_on_commit=False, future=True
    )
    assert run_once(factory, load_node_initializer=SuccessfulInitializer()) == 1
    db_session.expire_all()

    refreshed_attempt = db_session.get(LoadNodeInitializationAttempt, attempt.id)
    db_session.refresh(node)
    assert refreshed_attempt is not None
    assert refreshed_attempt.status == "succeeded"
    assert "secret" not in (refreshed_attempt.sanitized_log_tail or "")
    assert node.status == "idle"


def test_api_worker_default_initializer_factory_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.load_node_initializer as initializer_module
    import app.worker as worker_module

    class FakeRealInitializer(SuccessfulInitializer):
        pass

    monkeypatch.setattr(initializer_module, "RealLoadNodeInitializer", FakeRealInitializer)

    assert isinstance(worker_module._default_load_node_initializer(), FakeRealInitializer)


def test_api_worker_records_credential_app_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.worker as worker_module

    attempt, node = queue_private_node_initialization(
        db_session,
        actor_id="01HZX3Y9M0E9W7Z6M5QK9S8P7J",
        attempt_id="01HZX3Y9M0E9W7Z6M5QK9S8P7K",
        email="credential-app-error@example.com",
        host="credential-app-error-node.internal",
    )

    def fail_decrypt(_credential):  # noqa: ANN001
        raise AppError("CREDENTIAL_DECRYPT_FAILED", "Credential decrypt failed.", 500)

    monkeypatch.setattr(worker_module, "decrypt_credential", fail_decrypt)
    factory = sessionmaker(
        bind=db_session.bind, autoflush=False, expire_on_commit=False, future=True
    )

    assert run_once(factory, load_node_initializer=SuccessfulInitializer()) == 1
    db_session.expire_all()
    refreshed_attempt = db_session.get(LoadNodeInitializationAttempt, attempt.id)
    db_session.refresh(node)
    assert refreshed_attempt is not None
    assert refreshed_attempt.status == "failed"
    assert refreshed_attempt.error_code == "CREDENTIAL_DECRYPT_FAILED"
    assert node.status == "offline"


def test_api_worker_records_credential_unexpected_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.worker as worker_module

    attempt, node = queue_private_node_initialization(
        db_session,
        actor_id="01HZX3Y9M0E9W7Z6M5QK9S8P7L",
        attempt_id="01HZX3Y9M0E9W7Z6M5QK9S8P7M",
        email="credential-runtime-error@example.com",
        host="credential-runtime-error-node.internal",
    )

    def fail_decrypt(_credential):  # noqa: ANN001
        raise RuntimeError("boom")

    monkeypatch.setattr(worker_module, "decrypt_credential", fail_decrypt)
    factory = sessionmaker(
        bind=db_session.bind, autoflush=False, expire_on_commit=False, future=True
    )

    assert run_once(factory, load_node_initializer=SuccessfulInitializer()) == 1
    db_session.expire_all()
    refreshed_attempt = db_session.get(LoadNodeInitializationAttempt, attempt.id)
    db_session.refresh(node)
    assert refreshed_attempt is not None
    assert refreshed_attempt.status == "failed"
    assert refreshed_attempt.error_code == "LOAD_NODE_INIT_FAILED"
    assert node.status == "offline"


def test_api_worker_records_initializer_app_error(db_session: Session) -> None:
    class AppErrorInitializer(LoadNodeInitializer):
        def initialize(self, node, credential):  # noqa: ANN001
            _ = node, credential
            raise AppError("LOAD_NODE_PYTHON_MISSING", "Python missing.", 422)

    attempt, node = queue_private_node_initialization(
        db_session,
        actor_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
        attempt_id="01HZX3Y9M0E9W7Z6M5QK9S8P7O",
        email="initializer-app-error@example.com",
        host="initializer-app-error-node.internal",
    )
    factory = sessionmaker(
        bind=db_session.bind, autoflush=False, expire_on_commit=False, future=True
    )

    assert run_once(factory, load_node_initializer=AppErrorInitializer()) == 1
    db_session.expire_all()
    refreshed_attempt = db_session.get(LoadNodeInitializationAttempt, attempt.id)
    db_session.refresh(node)
    assert refreshed_attempt is not None
    assert refreshed_attempt.status == "failed"
    assert refreshed_attempt.error_code == "LOAD_NODE_PYTHON_MISSING"
    assert node.status == "offline"


def test_api_worker_records_host_key_initializer_failure_as_uninitialized(
    db_session: Session,
) -> None:
    class HostKeyChangedInitializer(LoadNodeInitializer):
        def initialize(self, node, credential):  # noqa: ANN001
            _ = node, credential
            return InitResult(
                ok=False,
                error_code="LOAD_NODE_SSH_HOST_KEY_CHANGED",
                message="Initialization failed.",
                log="[error] SSH host key changed.",
            )

    attempt, node = queue_private_node_initialization(
        db_session,
        actor_id="01HZX3Y9M0E9W7Z6M5QK9S8P7X",
        attempt_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Y",
        email="initializer-host-key@example.com",
        host="initializer-host-key-node.internal",
    )
    factory = sessionmaker(
        bind=db_session.bind, autoflush=False, expire_on_commit=False, future=True
    )

    assert run_once(factory, load_node_initializer=HostKeyChangedInitializer()) == 1
    db_session.expire_all()
    refreshed_attempt = db_session.get(LoadNodeInitializationAttempt, attempt.id)
    db_session.refresh(node)
    assert refreshed_attempt is not None
    assert refreshed_attempt.status == "failed"
    assert refreshed_attempt.error_code == "LOAD_NODE_SSH_HOST_KEY_CHANGED"
    assert node.status == "uninitialized"
    assert node.last_status_reason == "LOAD_NODE_SSH_HOST_KEY_CHANGED"


def test_api_worker_records_initializer_unexpected_error(db_session: Session) -> None:
    class RuntimeErrorInitializer(LoadNodeInitializer):
        def initialize(self, node, credential):  # noqa: ANN001
            _ = node, credential
            raise RuntimeError("boom")

    attempt, node = queue_private_node_initialization(
        db_session,
        actor_id="01HZX3Y9M0E9W7Z6M5QK9S8P7P",
        attempt_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Q",
        email="initializer-runtime-error@example.com",
        host="initializer-runtime-error-node.internal",
    )
    factory = sessionmaker(
        bind=db_session.bind, autoflush=False, expire_on_commit=False, future=True
    )

    assert run_once(factory, load_node_initializer=RuntimeErrorInitializer()) == 1
    db_session.expire_all()
    refreshed_attempt = db_session.get(LoadNodeInitializationAttempt, attempt.id)
    db_session.refresh(node)
    assert refreshed_attempt is not None
    assert refreshed_attempt.status == "failed"
    assert refreshed_attempt.error_code == "LOAD_NODE_INIT_FAILED"
    assert node.status == "offline"


def test_api_worker_skips_claimed_attempt_without_active_node(db_session: Session) -> None:
    attempt, node = queue_private_node_initialization(
        db_session,
        actor_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        attempt_id="01HZX3Y9M0E9W7Z6M5QK9S8P7S",
        email="inactive-node@example.com",
        host="inactive-node.internal",
    )
    node.status = "offline"
    db_session.commit()
    factory = sessionmaker(
        bind=db_session.bind, autoflush=False, expire_on_commit=False, future=True
    )

    assert run_once(factory, load_node_initializer=SuccessfulInitializer()) == 0
    db_session.expire_all()
    refreshed_attempt = db_session.get(LoadNodeInitializationAttempt, attempt.id)
    assert refreshed_attempt is not None
    assert refreshed_attempt.status == "running"


def test_api_worker_runs_initializer_outside_database_transaction(db_session: Session) -> None:
    class TrackingSession(Session):
        active_begin_depth = 0

        def begin(self):  # noqa: ANN201
            context = super().begin()

            class TrackingContext:
                def __enter__(self_inner):  # noqa: ANN001, ANN202
                    TrackingSession.active_begin_depth += 1
                    return context.__enter__()

                def __exit__(self_inner, exc_type, exc, traceback):  # noqa: ANN001, ANN202
                    try:
                        return context.__exit__(exc_type, exc, traceback)
                    finally:
                        TrackingSession.active_begin_depth -= 1

            return TrackingContext()

    class AssertingInitializer(SuccessfulInitializer):
        def __init__(self) -> None:
            self.called = False

        def initialize(self, node, credential):  # noqa: ANN001
            self.called = True
            assert TrackingSession.active_begin_depth == 0
            return super().initialize(node, credential)

    now = datetime.now(UTC)
    actor = User(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7H",
        email="worker-outside-tx@example.com",
        display_name="Worker",
        password_hash="hash",
        role="user",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(actor)
    db_session.flush()
    node = create_load_node(
        db_session,
        actor=actor,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host="worker-outside-tx-node.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=LoadNodeCredentialInput(authType="password", password="secret"),
        ssh_host_key=trusted_host_key(),
        maintainer=None,
        remark=None,
    )
    attempt = LoadNodeInitializationAttempt(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7I",
        node_id=node.id,
        status="queued",
        requested_by=actor.id,
        message="Initialization queued.",
        created_at=now,
        updated_at=now,
    )
    node.status = "initializing"
    node.last_init_attempt_id = attempt.id
    db_session.add(attempt)
    db_session.commit()

    factory = sessionmaker(
        bind=db_session.bind,
        class_=TrackingSession,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )
    initializer = AssertingInitializer()

    assert run_once(factory, load_node_initializer=initializer) == 1
    assert initializer.called is True
    db_session.expire_all()
    refreshed_attempt = db_session.get(LoadNodeInitializationAttempt, attempt.id)
    assert refreshed_attempt is not None
    assert refreshed_attempt.status == "succeeded"


def test_api_worker_run_once_recovers_stale_running_attempt(
    db_session: Session, monkeypatch
) -> None:
    now = datetime.now(UTC)
    actor = User(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        email="stale-worker@example.com",
        display_name="Worker",
        password_hash="hash",
        role="user",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(actor)
    db_session.flush()
    node = create_load_node(
        db_session,
        actor=actor,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host="stale-worker-node.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=LoadNodeCredentialInput(authType="password", password="secret"),
        ssh_host_key=trusted_host_key(),
        maintainer=None,
        remark=None,
    )
    attempt = LoadNodeInitializationAttempt(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
        node_id=node.id,
        status="running",
        requested_by=actor.id,
        started_at=now - timedelta(seconds=300),
        created_at=now - timedelta(seconds=300),
        updated_at=now - timedelta(seconds=300),
    )
    node.status = "initializing"
    db_session.add(attempt)
    db_session.commit()
    monkeypatch.setenv("LOAD_NODE_INIT_TIMEOUT_SECONDS", "1")

    factory = sessionmaker(
        bind=db_session.bind, autoflush=False, expire_on_commit=False, future=True
    )
    assert run_once(factory) == 1
    db_session.expire_all()

    refreshed_attempt = db_session.get(LoadNodeInitializationAttempt, attempt.id)
    db_session.refresh(node)
    assert refreshed_attempt is not None
    assert refreshed_attempt.status == "failed"
    assert refreshed_attempt.error_code == "LOAD_NODE_INIT_FAILED"
    assert node.status == "offline"


def test_api_worker_run_once_recovers_stale_initializing_node_without_active_attempt(
    db_session: Session, monkeypatch
) -> None:
    now = datetime.now(UTC)
    actor = User(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7F",
        email="stale-initializing-worker@example.com",
        display_name="Worker",
        password_hash="hash",
        role="user",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(actor)
    db_session.flush()
    node = create_load_node(
        db_session,
        actor=actor,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host="stale-initializing-node.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=LoadNodeCredentialInput(authType="password", password="secret"),
        ssh_host_key=trusted_host_key(),
        maintainer=None,
        remark=None,
    )
    node.status = "initializing"
    node.last_init_attempt_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7G"
    node.updated_at = now - timedelta(seconds=300)
    db_session.commit()
    monkeypatch.setenv("LOAD_NODE_INIT_TIMEOUT_SECONDS", "1")

    factory = sessionmaker(
        bind=db_session.bind, autoflush=False, expire_on_commit=False, future=True
    )
    assert run_once(factory) == 1
    db_session.expire_all()

    db_session.refresh(node)
    assert node.status == "offline"
    assert node.last_status_reason == "LOAD_NODE_INIT_FAILED"


def test_api_worker_advisory_lock_uses_postgres_lock() -> None:
    from app.worker import _advisory_unlock, _try_advisory_lock

    class _Dialect:
        name = "postgresql"

    class _Bind:
        dialect = _Dialect()

    class _Result:
        def __init__(self, value: bool = True) -> None:
            self.value = value

        def scalar(self) -> bool:
            return self.value

    class _Session:
        bind = _Bind()

        def __init__(self) -> None:
            self.statements: list[str] = []

        def execute(self, statement, params):  # noqa: ANN001
            self.statements.append(str(statement))
            assert params == {"key": 9303}
            return _Result(True)

    session = _Session()

    assert _try_advisory_lock(session) is True
    _advisory_unlock(session)

    assert any("pg_try_advisory_lock" in statement for statement in session.statements)
    assert any("pg_advisory_unlock" in statement for statement in session.statements)


def test_api_worker_run_once_clears_transaction_after_advisory_lock_miss(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import worker

    lock_attempts: list[int] = []

    def miss_lock(session, key=worker.LOAD_NODE_INIT_ADVISORY_LOCK):  # noqa: ANN001
        lock_attempts.append(key)
        session.execute(text("select 1")).scalar()
        assert session.in_transaction()
        return False

    monkeypatch.setattr(worker, "_try_advisory_lock", miss_lock)
    factory = sessionmaker(
        bind=db_session.bind, autoflush=False, expire_on_commit=False, future=True
    )

    assert worker.run_once(factory) == 0
    assert lock_attempts == [
        worker.LOAD_NODE_INIT_ADVISORY_LOCK,
        worker.RUN_PROTOCOL_ADVISORY_LOCK,
        worker.RUN_REPORT_SUMMARY_ADVISORY_LOCK,
    ]


def test_api_worker_run_once_builds_default_session_factory(
    db_session: Session, monkeypatch
) -> None:
    from app import worker

    class _Settings:
        database_url = "sqlite:///:memory:"

    monkeypatch.setattr(worker, "get_settings", lambda: _Settings())
    monkeypatch.setattr(worker, "create_engine", lambda *args, **kwargs: db_session.bind)

    assert worker.run_once() == 0


def test_api_worker_main_once_prints_completed_count(monkeypatch, capsys) -> None:
    from app import worker

    monkeypatch.setattr("sys.argv", ["api-worker", "--once"])
    monkeypatch.setattr(worker, "run_once", lambda: 3)

    worker.main()

    assert "api-worker completed 3 task(s)" in capsys.readouterr().out


def test_api_worker_main_rejects_malformed_ssh_credential_encryption_key(
    monkeypatch,
) -> None:
    from app import worker

    run_once = Mock()
    monkeypatch.setenv("SSH_CREDENTIAL_ENCRYPTION_KEY", "not-base64")
    monkeypatch.setattr("sys.argv", ["api-worker", "--once"])
    monkeypatch.setattr(worker, "run_once", run_once)

    with pytest.raises(ValueError, match="SSH_CREDENTIAL_ENCRYPTION_KEY"):
        worker.main()

    run_once.assert_not_called()


def test_api_worker_main_loop_logs_cycle_failure_then_sleeps(monkeypatch) -> None:
    from app import worker

    calls = {"run_once": 0}

    def fail_once() -> None:
        calls["run_once"] += 1
        raise RuntimeError("boom")

    def stop_loop(_interval: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("sys.argv", ["api-worker", "--interval", "0"])
    monkeypatch.setattr(worker, "run_once", fail_once)
    monkeypatch.setattr(worker.time, "sleep", stop_loop)

    import pytest

    with pytest.raises(KeyboardInterrupt):
        worker.main()

    assert calls["run_once"] == 1
