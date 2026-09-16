from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import app.db.session as session_module
from app.api.deps import get_current_session, request_id, require_csrf

from app.core.config import (
    decode_ssh_credential_encryption_key,
    _monitoring_token_configured_from_env,
    _normalize_database_url,
    get_settings,
)
from app.core.errors import AppError, error_payload
from app.core.ids import is_ulid, new_request_id
from app.models.auth import SessionRecord, User
from app.services.audit import _client_ip, _user_agent
from app.services.accounts import lock_users_for_bootstrap
from app.services.sessions import create_session, revoke_session, session_is_active, token_hash
from app.services.workspaces import get_default_workspace


def test_config_normalizes_postgres_url_and_parses_false_signup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("ALLOW_SIGNUP", "false")

    settings = get_settings()

    assert _normalize_database_url("postgresql://user:pass@localhost/db").startswith(
        "postgresql+psycopg://"
    )
    assert settings.database_url == "sqlite:///test.db"
    assert settings.allow_signup is False


@pytest.mark.parametrize(("value", "expected"), [("true", True), (" FALSE ", False)])
def test_session_cookie_secure_uses_strict_explicit_boolean(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", value)

    assert get_settings().session_cookie_secure is expected


def test_session_cookie_secure_defaults_from_environment_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    assert get_settings().session_cookie_secure is True
    monkeypatch.setenv("APP_ENV", "development")
    assert get_settings().session_cookie_secure is False


@pytest.mark.parametrize("value", ["", "ture", "1", "0", "yes", "no", "on", "off"])
def test_session_cookie_secure_rejects_ambiguous_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("SESSION_COOKIE_SECURE", value)

    with pytest.raises(ValueError, match="SESSION_COOKIE_SECURE must be true or false"):
        get_settings()


def test_monitoring_token_configured_uses_explicit_presence_flag(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "secret"
    token_file.write_text("token\n", encoding="utf-8")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN", "configured")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE", str(token_file))
    monkeypatch.delenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED", raising=False)
    assert _monitoring_token_configured_from_env() is False

    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED", "true")
    assert _monitoring_token_configured_from_env() is True

    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED", "false")
    assert _monitoring_token_configured_from_env() is False


def test_request_id_and_ulid_helpers_validate_format() -> None:
    request_id_value = new_request_id()

    assert request_id_value.startswith("req_")
    assert is_ulid(request_id_value.removeprefix("req_"))
    assert not is_ulid("not-a-ulid")


def test_error_payload_omits_details_when_none() -> None:
    payload = error_payload("UNAUTHENTICATED", "Authentication is required.", "req_test")

    assert payload == {
        "code": "UNAUTHENTICATED",
        "message": "Authentication is required.",
        "requestId": "req_test",
    }


def test_audit_helpers_handle_absent_request_and_user_agent() -> None:
    request_without_client = SimpleNamespace(client=None, headers={}, state=SimpleNamespace())
    request_with_long_agent = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"user-agent": "a" * 600},
        state=SimpleNamespace(request_id="req_test"),
    )

    assert _client_ip(None) is None
    assert _client_ip(request_without_client) is None
    assert _client_ip(request_with_long_agent) == "127.0.0.1"
    assert _user_agent(None) is None
    assert _user_agent(request_without_client) is None
    assert len(_user_agent(request_with_long_agent)) == 512


def test_dependency_helpers_raise_expected_security_errors(db_session) -> None:
    now = datetime.now(UTC)
    with pytest.raises(AppError) as unauthenticated:
        get_current_session(db_session, None)
    assert unauthenticated.value.code == "UNAUTHENTICATED"

    active_record = SessionRecord(
        id="01HZW000000000000000000001",
        session_token_hash="hash",
        user_id="01HZW000000000000000000002",
        csrf_token_hash="hash",
        created_at=now,
        last_seen_at=now,
        expires_at=now,
    )
    with pytest.raises(AppError) as missing:
        require_csrf(active_record, None)
    assert missing.value.code == "CSRF_TOKEN_REQUIRED"

    with pytest.raises(AppError) as invalid:
        require_csrf(active_record, "wrong")
    assert invalid.value.code == "CSRF_TOKEN_INVALID"


def test_request_id_dependency_reads_request_state() -> None:
    request = SimpleNamespace(state=SimpleNamespace(request_id="req_test"))

    assert request_id(request) == "req_test"


def test_session_is_active_rejects_revoked_record() -> None:
    record = SimpleNamespace(revoked_at=object())

    assert session_is_active(record) is False


def test_revoke_session_is_idempotent_when_already_revoked() -> None:
    revoked_at = datetime.now(UTC)
    record = SimpleNamespace(revoked_at=revoked_at)

    revoke_session(SimpleNamespace(flush=lambda: (_ for _ in ()).throw(AssertionError())), record)

    assert record.revoked_at is revoked_at


def test_create_session_uses_independent_random_csrf_token(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import sessions

    now = datetime.now(UTC)
    user = User(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        email="session-user@example.com",
        display_name="Session User",
        password_hash="hash",
        role="user",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.flush()
    calls: list[str] = []

    def fake_new_token(prefix: str) -> str:
        calls.append(prefix)
        return f"{prefix}_raw"

    monkeypatch.setattr(sessions, "new_token", fake_new_token)

    created = create_session(db_session, user=user)

    assert calls == ["sess", "csrf"]
    assert created.session_token == "sess_raw"
    assert created.csrf_token == "csrf_raw"
    assert created.record.session_token_hash == token_hash("sess_raw")
    assert created.record.csrf_token_hash == token_hash("csrf_raw")


def test_verify_csrf_uses_constant_time_digest_compare(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import sessions

    record = SimpleNamespace(csrf_token_hash=token_hash("csrf_known"))
    calls: list[tuple[str, str]] = []

    def fake_compare_digest(left: str, right: str) -> bool:
        calls.append((left, right))
        return True

    monkeypatch.setattr(sessions.secrets, "compare_digest", fake_compare_digest)

    assert sessions.verify_csrf(record, "csrf_known") is True
    assert calls == [(token_hash("csrf_known"), token_hash("csrf_known"))]


def test_get_db_yields_session_from_session_local(monkeypatch: pytest.MonkeyPatch) -> None:
    closed: list[bool] = []

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            closed.append(True)

    monkeypatch.setattr(session_module, "SessionLocal", FakeSession)

    generator = session_module.get_db()
    yielded = next(generator)
    with pytest.raises(StopIteration):
        next(generator)

    assert isinstance(yielded, FakeSession)
    assert closed == [True]


def test_get_default_workspace_without_user_uses_seed(db_session) -> None:
    workspace = get_default_workspace(db_session)

    assert workspace.name == "Default Workspace"


def test_postgres_bootstrap_lock_executes_only_for_postgres() -> None:
    executed: list[str] = []
    postgres_session = SimpleNamespace(
        bind=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        execute=lambda statement: executed.append(str(statement)),
    )
    sqlite_session = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))

    lock_users_for_bootstrap(postgres_session)
    lock_users_for_bootstrap(sqlite_session)

    assert executed == ["LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"]


def test_jmeter_memory_xmx_defaults_and_rejects_invalid_values(monkeypatch) -> None:
    monkeypatch.delenv("SURGEPILOT_JMETER_MEMORY_XMX", raising=False)
    assert get_settings().jmeter_memory_xmx == "4G"

    monkeypatch.setenv("SURGEPILOT_JMETER_MEMORY_XMX", "0G")
    with pytest.raises(ValueError, match="SURGEPILOT_JMETER_MEMORY_XMX"):
        get_settings()

    monkeypatch.setenv("SURGEPILOT_JMETER_MEMORY_XMX", "512M")
    assert get_settings().jmeter_memory_xmx == "512M"


@pytest.mark.parametrize(
    "value",
    [None, "", "not-base64", "c2hvcnQ="],
)
def test_ssh_credential_encryption_key_requires_base64_32_bytes(value: str | None) -> None:
    with pytest.raises(ValueError, match="SSH_CREDENTIAL_ENCRYPTION_KEY"):
        decode_ssh_credential_encryption_key(value)

    assert (
        decode_ssh_credential_encryption_key("MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
        == b"0" * 32
    )
