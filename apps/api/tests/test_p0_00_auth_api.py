from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import as_utc
from app.models.auth import AuditEvent, SessionRecord, User, Workspace, WorkspaceMember


async def register(
    client: AsyncClient,
    email: str = "admin@example.com",
    password: str = "password123",
    display_name: str = "Admin User",
):
    return await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": display_name, "password": password},
    )


@pytest.mark.anyio
async def test_setup_status_reports_bootstrap_and_signup_state(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALLOW_SIGNUP", "false")
    from app.routes import setup

    monkeypatch.setattr(setup, "storage_is_available", lambda: True)

    response = await client.get("/api/v1/setup/status")

    assert response.status_code == 200
    assert response.json() == {
        "needsBootstrap": True,
        "allowSignup": True,
        "hasDefaultWorkspace": True,
        "storageAvailable": True,
    }
    assert "x-request-id" in response.headers
    assert "userCount" not in response.text
    assert "admin@example.com" not in response.text


@pytest.mark.anyio
async def test_setup_status_reports_missing_default_workspace(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.routes import setup

    monkeypatch.setattr(setup, "storage_is_available", lambda: True)
    db_session.query(Workspace).delete()
    db_session.commit()

    response = await client.get("/api/v1/setup/status")

    assert response.status_code == 200
    assert response.json()["hasDefaultWorkspace"] is False


@pytest.mark.anyio
async def test_setup_status_reports_storage_availability(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.routes import setup

    monkeypatch.setattr(setup, "storage_is_available", lambda: False)

    response = await client.get("/api/v1/setup/status")

    assert response.status_code == 200
    assert response.json()["storageAvailable"] is False
    assert "minioadmin" not in response.text
    assert "storageObjectKey" not in response.text


def test_setup_status_storage_health_helper_uses_safe_boolean_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.routes import setup

    class HealthyStorage:
        def health_check(self) -> bool:
            return True

    monkeypatch.setattr(setup, "get_storage_client", lambda: HealthyStorage())

    assert setup.storage_is_available() is True


def test_setup_status_storage_health_helper_hides_storage_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.routes import setup

    class BrokenStorage:
        def health_check(self) -> bool:
            raise RuntimeError("minioadmin secret must not leak")

    monkeypatch.setattr(setup, "get_storage_client", lambda: BrokenStorage())

    assert setup.storage_is_available() is False


@pytest.mark.anyio
async def test_first_registration_creates_admin_session_membership_and_audit_event(
    client: AsyncClient, db_session: Session
) -> None:
    response = await register(client, email=" Admin@Example.com ")

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "admin@example.com"
    assert body["user"]["role"] == "admin"
    assert body["user"]["status"] == "active"
    assert body["defaultWorkspace"]["name"] == "Default Workspace"
    assert body["csrfToken"]
    assert "password" not in response.text
    assert "passwordHash" not in response.text
    assert response.headers["x-workspace-id"] == body["defaultWorkspace"]["id"]
    assert response.headers["cache-control"] == "no-store"
    assert "surgepilot_session=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=Lax" in response.headers["set-cookie"]
    assert "Path=/" in response.headers["set-cookie"]

    user = db_session.scalar(select(User).where(User.email == "admin@example.com"))
    assert user is not None
    assert user.password_hash.startswith("$argon2id$")
    assert (
        db_session.scalar(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id))
        is not None
    )
    assert (
        db_session.scalar(select(AuditEvent).where(AuditEvent.event_type == "auth.register"))
        is not None
    )


@pytest.mark.anyio
@pytest.mark.parametrize(("secure", "expected"), [("true", True), ("false", False)])
async def test_registration_cookie_uses_explicit_transport_policy(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    secure: str,
    expected: bool,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", secure)

    response = await register(client, email=f"cookie-{secure}@example.com")

    assert response.status_code == 201
    has_secure = "; Secure" in response.headers["set-cookie"]
    assert has_secure is expected


@pytest.mark.anyio
async def test_later_registration_creates_user_and_can_be_disabled_after_bootstrap(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = await register(client, email="admin@example.com")
    assert first.status_code == 201

    second = await register(client, email="user@example.com", display_name="Normal User")
    assert second.status_code == 201
    assert second.json()["user"]["role"] == "user"

    monkeypatch.setenv("ALLOW_SIGNUP", "false")
    disabled = await register(client, email="blocked@example.com", display_name="Blocked User")

    assert disabled.status_code == 403
    assert disabled.json()["code"] == "SIGNUP_DISABLED"


@pytest.mark.anyio
async def test_duplicate_email_and_invalid_password_use_registered_error_codes(
    client: AsyncClient,
) -> None:
    first = await register(client, email="admin@example.com")
    assert first.status_code == 201

    duplicate = await register(client, email="ADMIN@example.com")
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "EMAIL_ALREADY_EXISTS"

    invalid_password = await register(
        client,
        email="new@example.com",
        password="passwordonly",
        display_name="New User",
    )
    assert invalid_password.status_code == 422
    assert invalid_password.json()["code"] == "PASSWORD_POLICY_VIOLATION"


@pytest.mark.anyio
async def test_invalid_request_shape_uses_unified_validation_error(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "displayName": "", "password": "password123"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["requestId"] == response.headers["x-request-id"]
    assert response.json()["details"]


@pytest.mark.anyio
async def test_whitespace_display_name_is_rejected_by_backend_service(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "admin@example.com", "displayName": "   ", "password": "password123"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["details"][0]["field"] == "displayName"


@pytest.mark.anyio
async def test_login_creates_independent_sessions_and_logout_revokes_only_current_session(
    client: AsyncClient, db_session: Session
) -> None:
    created = await register(client, email="admin@example.com")
    assert created.status_code == 201

    login_one = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )
    login_two_client = AsyncClient(
        transport=client._transport,
        base_url="http://testserver",
    )
    login_two = await login_two_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )

    assert login_one.status_code == 200
    assert login_two.status_code == 200
    assert login_one.json()["csrfToken"] != login_two.json()["csrfToken"]
    assert db_session.scalar(select(SessionRecord).where(SessionRecord.revoked_at.is_(None)))

    logout = await client.post(
        "/api/v1/auth/logout",
        headers={"x-csrf-token": login_one.json()["csrfToken"]},
    )
    assert logout.status_code == 204
    assert "surgepilot_session=" in logout.headers["set-cookie"]

    me_current = await client.get("/api/v1/auth/me")
    assert me_current.status_code == 401
    me_other = await login_two_client.get("/api/v1/auth/me")
    assert me_other.status_code == 200
    await login_two_client.aclose()


@pytest.mark.anyio
async def test_logout_requires_csrf_only_when_valid_session_exists(client: AsyncClient) -> None:
    created = await register(client, email="admin@example.com")
    assert created.status_code == 201

    missing = await client.post("/api/v1/auth/logout")
    assert missing.status_code == 403
    assert missing.json()["code"] == "CSRF_TOKEN_REQUIRED"

    invalid = await client.post("/api/v1/auth/logout", headers={"x-csrf-token": "bad-token"})
    assert invalid.status_code == 403
    assert invalid.json()["code"] == "CSRF_TOKEN_INVALID"

    no_session_client = AsyncClient(transport=client._transport, base_url="http://testserver")
    no_session = await no_session_client.post("/api/v1/auth/logout")
    assert no_session.status_code == 204
    await no_session_client.aclose()


@pytest.mark.anyio
async def test_me_and_csrf_require_active_session_and_do_not_leak_csrf_from_me(
    client: AsyncClient, db_session: Session
) -> None:
    created = await register(client, email="admin@example.com")
    assert created.status_code == 201

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert "csrfToken" not in me.json()
    assert me.json()["defaultWorkspace"]["name"] == "Default Workspace"

    csrf = await client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200
    rotated_csrf = csrf.json()["csrfToken"]
    assert rotated_csrf
    assert rotated_csrf != created.json()["csrfToken"]

    old_logout = await client.post(
        "/api/v1/auth/logout", headers={"x-csrf-token": created.json()["csrfToken"]}
    )
    assert old_logout.status_code == 403
    assert old_logout.json()["code"] == "CSRF_TOKEN_INVALID"

    session = db_session.scalar(select(SessionRecord))
    assert session is not None
    session.last_seen_at = datetime.now(UTC) - timedelta(hours=25)
    db_session.commit()

    expired = await client.get("/api/v1/auth/me")
    assert expired.status_code == 401
    assert expired.json()["code"] == "UNAUTHENTICATED"


@pytest.mark.anyio
async def test_default_workspace_response_uses_runtime_display_name_override(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEFAULT_WORKSPACE_NAME", "Internal Load Testing")

    created = await register(client, email="admin@example.com")
    assert created.status_code == 201
    assert created.json()["defaultWorkspace"]["name"] == "Internal Load Testing"

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["defaultWorkspace"]["name"] == "Internal Load Testing"


@pytest.mark.anyio
async def test_me_rejects_absolute_expiry_and_missing_default_workspace_membership(
    client: AsyncClient, db_session: Session
) -> None:
    created = await register(client, email="admin@example.com")
    assert created.status_code == 201

    session = db_session.scalar(select(SessionRecord))
    assert session is not None
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    expired = await client.get("/api/v1/auth/me")
    assert expired.status_code == 401
    assert expired.json()["code"] == "UNAUTHENTICATED"

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    db_session.query(WorkspaceMember).delete()
    db_session.commit()

    missing_workspace = await client.get("/api/v1/auth/me")
    assert missing_workspace.status_code == 200
    assert (
        missing_workspace.json()["currentWorkspace"]["id"]
        == created.json()["defaultWorkspace"]["id"]
    )
    assert (
        missing_workspace.json()["availableWorkspaces"][0]["membership"]["kind"] == "admin_access"
    )


@pytest.mark.anyio
async def test_login_failures_are_generic_and_lockout_thresholds_are_audited(
    client: AsyncClient, db_session: Session
) -> None:
    created = await register(client, email="admin@example.com")
    assert created.status_code == 201

    for attempt in range(1, 6):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "wrong-password123"},
        )
        assert response.status_code == 401
        assert response.json()["code"] == "INVALID_CREDENTIALS"
        user = db_session.scalar(select(User).where(User.email == "admin@example.com"))
        assert user is not None
        if attempt == 4:
            assert user.locked_until is None
        if attempt == 5:
            assert user.locked_until is not None
            assert (
                timedelta(minutes=4)
                < user.locked_until - datetime.now(UTC)
                <= timedelta(minutes=5, seconds=5)
            )

    locked_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )
    assert locked_response.status_code == 401
    assert locked_response.json()["code"] == "INVALID_CREDENTIALS"
    assert db_session.scalar(select(AuditEvent).where(AuditEvent.event_type == "auth.locked"))


@pytest.mark.anyio
async def test_login_unknown_and_locked_users_execute_password_verification(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, str]] = []

    def recording_verify_password(password: str, password_hash: str) -> bool:
        calls.append((password, password_hash))
        return False

    monkeypatch.setattr("app.services.accounts.verify_password", recording_verify_password)

    unknown = await client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "password123"},
    )

    assert unknown.status_code == 401
    assert unknown.json()["code"] == "INVALID_CREDENTIALS"
    assert len(calls) == 1
    assert calls[0][0] == "password123"

    calls.clear()
    created = await register(client, email="locked@example.com")
    assert created.status_code == 201
    user = db_session.scalar(select(User).where(User.email == "locked@example.com"))
    assert user is not None
    user.locked_until = datetime.now(UTC) + timedelta(minutes=5)
    db_session.commit()

    locked = await client.post(
        "/api/v1/auth/login",
        json={"email": "locked@example.com", "password": "password123"},
    )

    assert locked.status_code == 401
    assert locked.json()["code"] == "INVALID_CREDENTIALS"
    assert len(calls) == 1
    assert calls[0][0] == "password123"
    assert calls[0][1] == user.password_hash


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {"password": "password123"},
        {"email": "", "password": "password123"},
        {"email": "   ", "password": "password123"},
        {"email": "not-an-email", "password": "password123"},
        {"email": "admin@example.com"},
    ],
)
async def test_login_missing_empty_or_malformed_credentials_use_generic_failure(
    client: AsyncClient, payload: dict[str, str]
) -> None:
    created = await register(client, email="admin@example.com")
    assert created.status_code == 201

    response = await client.post("/api/v1/auth/login", json=payload)

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


@pytest.mark.anyio
async def test_unknown_email_and_tenth_failure_use_generic_login_failure(
    client: AsyncClient, db_session: Session
) -> None:
    created = await register(client, email="admin@example.com")
    assert created.status_code == 201

    unknown_email = await client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "password123"},
    )
    assert unknown_email.status_code == 401
    assert unknown_email.json()["code"] == "INVALID_CREDENTIALS"

    for _ in range(5):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "wrong-password123"},
        )
        assert response.status_code == 401

    user = db_session.scalar(select(User).where(User.email == "admin@example.com"))
    assert user is not None
    user.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    for _ in range(5):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "wrong-password123"},
        )
        assert response.status_code == 401

    db_session.refresh(user)
    assert user.failed_login_count == 10
    assert user.locked_until is not None
    assert (
        timedelta(minutes=29)
        < as_utc(user.locked_until) - datetime.now(UTC)
        <= timedelta(minutes=30, seconds=5)
    )


@pytest.mark.anyio
async def test_write_without_csrf_fails_on_authenticated_business_endpoint(
    client: AsyncClient,
) -> None:
    created = await register(client, email="admin@example.com")
    assert created.status_code == 201

    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_TOKEN_REQUIRED"
