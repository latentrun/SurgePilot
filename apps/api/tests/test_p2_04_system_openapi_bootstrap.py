from __future__ import annotations

from datetime import UTC, datetime
import json
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.models.api_catalog import ApiCatalogSpec
from app.models.auth import DEFAULT_WORKSPACE_ID, User, Workspace
from app.services.storage import LimitedHashingReader, PutResult, StorageClient


class FakeStorage(StorageClient):
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, str | None]] = {}
        self.deleted: list[tuple[str, str]] = []

    def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):
        reader = LimitedHashingReader(stream, size_limit=size_limit)
        data = bytearray()
        while chunk := reader.read(4096):
            data.extend(chunk)
        self.objects[(bucket, object_key)] = (bytes(data), content_type)
        return PutResult(size_bytes=reader.size_bytes, sha256=reader.sha256_hex)

    def get_stream(self, *, bucket, object_key):
        raise NotImplementedError

    def delete_object_best_effort(self, *, bucket, object_key):
        self.deleted.append((bucket, object_key))
        self.objects.pop((bucket, object_key), None)
        return True

    def copy_object(self, *, bucket, source_key, destination_key):
        raise NotImplementedError

    def health_check(self):
        return True


def seed_admin(db: Session, *, user_id: str = "01J00000000000000000000001") -> User:
    now = datetime.now(UTC)
    user = User(
        id=user_id,
        email=f"{user_id.lower()}@example.com",
        display_name="Bootstrap Admin",
        password_hash="not-used",
        role="admin",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    return user


def session_factory(db: Session):
    return sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False, future=True)


def settings():
    return SimpleNamespace(minio_bucket="surgepilot", api_catalog_spec_max_bytes=10 * 1024 * 1024)


def test_curated_bootstrap_payload_uses_runtime_internal_export() -> None:
    from app.services.system_openapi_bootstrap import build_curated_openapi_payload

    payload = build_curated_openapi_payload(app)
    document = json.loads(payload)

    assert payload == json.dumps(document, sort_keys=True).encode("utf-8")
    assert "/v1/account/ai-skill/download" in document["paths"]
    assert document["paths"]
    assert all(path.startswith("/v1/") for path in document["paths"])
    assert all(not path.startswith("/api/public/v1/") for path in document["paths"])


def test_bootstrap_import_creates_one_default_workspace_spec(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import system_openapi_bootstrap as bootstrap

    admin = seed_admin(db_session)
    storage = FakeStorage()
    monkeypatch.setattr(bootstrap, "get_settings", settings)

    created = bootstrap.import_system_openapi(
        application=app,
        workspace_id=DEFAULT_WORKSPACE_ID,
        admin_user_id=admin.id,
        session_factory=session_factory(db_session),
        storage=storage,
    )

    assert created is True
    db_session.expire_all()
    spec = db_session.scalar(select(ApiCatalogSpec))
    assert spec is not None
    assert spec.workspace_id == DEFAULT_WORKSPACE_ID
    assert spec.created_by == admin.id
    assert spec.name == "SurgePilot API"
    assert spec.filename == "surgepilot-api.openapi.json"
    assert spec.content_type == "application/json"
    payload, content_type = storage.objects[(spec.storage_bucket, spec.storage_object_key)]
    assert content_type == "application/json"
    assert payload == bootstrap.build_curated_openapi_payload(app)


def test_bootstrap_deduplicates_by_workspace_and_sha_not_name(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import system_openapi_bootstrap as bootstrap

    admin = seed_admin(db_session)
    storage = FakeStorage()
    monkeypatch.setattr(bootstrap, "get_settings", settings)
    kwargs = {
        "application": app,
        "workspace_id": DEFAULT_WORKSPACE_ID,
        "admin_user_id": admin.id,
        "session_factory": session_factory(db_session),
        "storage": storage,
    }

    assert bootstrap.import_system_openapi(**kwargs) is True
    spec = db_session.scalar(select(ApiCatalogSpec))
    assert spec is not None
    spec.name = "Renamed by user"
    db_session.commit()

    assert bootstrap.import_system_openapi(**kwargs) is False
    assert db_session.scalar(select(func.count(ApiCatalogSpec.id))) == 1
    assert len(storage.objects) == 1


def test_deleted_bootstrap_spec_does_not_suppress_reimport(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import system_openapi_bootstrap as bootstrap

    admin = seed_admin(db_session)
    storage = FakeStorage()
    monkeypatch.setattr(bootstrap, "get_settings", settings)
    kwargs = {
        "application": app,
        "workspace_id": DEFAULT_WORKSPACE_ID,
        "admin_user_id": admin.id,
        "session_factory": session_factory(db_session),
        "storage": storage,
    }

    assert bootstrap.import_system_openapi(**kwargs) is True
    spec = db_session.scalar(select(ApiCatalogSpec))
    assert spec is not None
    spec.status = "deleted"
    db_session.commit()

    assert bootstrap.import_system_openapi(**kwargs) is True
    assert db_session.scalar(select(func.count(ApiCatalogSpec.id))) == 2
    assert len(storage.objects) == 2


def test_same_sha_in_another_workspace_does_not_suppress_default_workspace_import(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import system_openapi_bootstrap as bootstrap

    admin = seed_admin(db_session)
    now = datetime.now(UTC)
    other_workspace = Workspace(
        id="01J00000000000000000000002",
        name="Other Workspace",
        status="active",
        created_at=now,
        updated_at=now,
    )
    db_session.add(other_workspace)
    db_session.commit()
    storage = FakeStorage()
    monkeypatch.setattr(bootstrap, "get_settings", settings)
    common = {
        "application": app,
        "admin_user_id": admin.id,
        "session_factory": session_factory(db_session),
        "storage": storage,
    }

    assert bootstrap.import_system_openapi(workspace_id=other_workspace.id, **common) is True
    assert bootstrap.import_system_openapi(workspace_id=DEFAULT_WORKSPACE_ID, **common) is True
    assert db_session.scalar(select(func.count(ApiCatalogSpec.id))) == 2


def test_bootstrap_commit_failure_removes_new_storage_object(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import system_openapi_bootstrap as bootstrap

    admin = seed_admin(db_session)
    storage = FakeStorage()
    monkeypatch.setattr(bootstrap, "get_settings", settings)

    class CommitFailingSession(Session):
        def commit(self) -> None:
            raise RuntimeError("commit failed")

    failing_factory = sessionmaker(
        bind=db_session.get_bind(),
        class_=CommitFailingSession,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )

    with pytest.raises(RuntimeError, match="commit failed"):
        bootstrap.import_system_openapi(
            application=app,
            workspace_id=DEFAULT_WORKSPACE_ID,
            admin_user_id=admin.id,
            session_factory=failing_factory,
            storage=storage,
        )

    db_session.expire_all()
    assert db_session.scalar(select(func.count(ApiCatalogSpec.id))) == 0
    assert len(storage.deleted) == 1
    assert not storage.objects


def test_post_commit_logging_failure_does_not_delete_committed_object(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import system_openapi_bootstrap as bootstrap

    admin = seed_admin(db_session)
    storage = FakeStorage()
    monkeypatch.setattr(bootstrap, "get_settings", settings)

    def fail_completed_log(message, *args, **kwargs):
        if message == "System OpenAPI bootstrap completed":
            raise RuntimeError("log handler failed")

    monkeypatch.setattr(bootstrap.logger, "info", fail_completed_log)

    with pytest.raises(RuntimeError, match="log handler failed"):
        bootstrap.import_system_openapi(
            application=app,
            workspace_id=DEFAULT_WORKSPACE_ID,
            admin_user_id=admin.id,
            session_factory=session_factory(db_session),
            storage=storage,
        )

    db_session.expire_all()
    assert db_session.scalar(select(func.count(ApiCatalogSpec.id))) == 1
    assert len(storage.objects) == 1
    assert storage.deleted == []


def test_best_effort_wrapper_swallows_import_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import system_openapi_bootstrap as bootstrap

    def fail(**_kwargs):
        raise RuntimeError("unavailable")

    monkeypatch.setattr(bootstrap, "import_system_openapi", fail)

    bootstrap.bootstrap_system_openapi_best_effort(
        application=app,
        workspace_id=DEFAULT_WORKSPACE_ID,
        admin_user_id="01J00000000000000000000001",
    )


@pytest.mark.anyio
async def test_registration_stays_successful_when_real_bootstrap_wrapper_import_fails(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.routes import auth
    from app.services import system_openapi_bootstrap as bootstrap

    def fail(**_kwargs):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(bootstrap, "import_system_openapi", fail)
    monkeypatch.setattr(
        auth,
        "bootstrap_system_openapi_best_effort",
        bootstrap.bootstrap_system_openapi_best_effort,
    )

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "bootstrap-failure@example.com",
            "displayName": "Bootstrap Failure",
            "password": "password123",
        },
    )

    assert response.status_code == 201
    assert response.json()["user"]["role"] == "admin"


@pytest.mark.anyio
async def test_registration_triggers_bootstrap_only_for_explicit_first_user(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.routes import auth

    calls: list[dict[str, object]] = []

    def record_bootstrap(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(auth, "bootstrap_system_openapi_best_effort", record_bootstrap)

    first = await client.post(
        "/api/v1/auth/register",
        json={"email": "first@example.com", "displayName": "First", "password": "password123"},
    )
    second = await client.post(
        "/api/v1/auth/register",
        json={"email": "second@example.com", "displayName": "Second", "password": "password123"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert len(calls) == 1
    assert calls[0]["workspace_id"] == first.json()["defaultWorkspace"]["id"]
    assert calls[0]["admin_user_id"] == first.json()["user"]["id"]
    assert calls[0]["application"] is app
