from __future__ import annotations

from datetime import UTC, datetime
import json
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.core.product_version import PRODUCT_VERSION
from app.models.api_catalog import ApiCatalogSpec
from app.models.auth import DEFAULT_WORKSPACE_ID, User
from app.services.storage import LimitedHashingReader, PutResult, StorageClient


class FakeStorage(StorageClient):
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, str | None]] = {}
        self.deleted: list[tuple[str, str]] = []
        self.writes = 0

    def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):
        self.writes += 1
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


def changed_payload() -> bytes:
    from app.services.system_openapi_bootstrap import build_curated_openapi_payload

    document = json.loads(build_curated_openapi_payload(app))
    document["paths"]["/v1/new-capability"] = {"get": {"responses": {"200": {"description": "OK"}}}}
    return json.dumps(document, sort_keys=True).encode("utf-8")


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
    assert spec.system_key == "surgepilot_api"
    assert spec.document_version == PRODUCT_VERSION
    assert spec.filename == "surgepilot-api.openapi.json"
    assert spec.content_type == "application/json"
    payload, content_type = storage.objects[(spec.storage_bucket, spec.storage_object_key)]
    assert content_type == "application/json"
    assert payload == bootstrap.build_curated_openapi_payload(app)
    assert json.loads(payload)["info"]["version"] == PRODUCT_VERSION


def test_bootstrap_uses_system_identity_even_if_renamed(
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


def test_user_spec_with_identical_sha_does_not_suppress_system_bootstrap(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import system_openapi_bootstrap as bootstrap
    from app.services.api_catalog import UploadedApiSpec, create_api_catalog_spec

    admin = seed_admin(db_session)
    storage = FakeStorage()
    monkeypatch.setattr(bootstrap, "get_settings", settings)
    payload = bootstrap.build_curated_openapi_payload(app)
    user_spec = create_api_catalog_spec(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor_user_id=admin.id,
        upload=UploadedApiSpec(
            filename="surgepilot-api.openapi.json",
            content_type="application/json",
            payload=payload,
            name="SurgePilot API",
        ),
        storage=storage,
        bucket="surgepilot",
        max_bytes=settings().api_catalog_spec_max_bytes,
    )
    db_session.commit()

    assert (
        bootstrap.reconcile_system_openapi(
            application=app,
            session_factory=session_factory(db_session),
            storage=storage,
        )
        is False
    )
    assert storage.writes == 1
    assert (
        bootstrap.import_system_openapi(
            application=app,
            workspace_id=DEFAULT_WORKSPACE_ID,
            admin_user_id=admin.id,
            session_factory=session_factory(db_session),
            storage=storage,
        )
        is True
    )
    db_session.expire_all()
    assert user_spec.system_key is None
    assert db_session.scalar(select(func.count(ApiCatalogSpec.id))) == 2
    assert (
        db_session.scalar(
            select(ApiCatalogSpec).where(ApiCatalogSpec.system_key == "surgepilot_api")
        )
        is not None
    )


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


def test_startup_same_sha_does_not_mutate_catalog_or_storage(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import system_openapi_bootstrap as bootstrap

    admin = seed_admin(db_session)
    storage = FakeStorage()
    monkeypatch.setattr(bootstrap, "get_settings", settings)
    factory = session_factory(db_session)
    assert (
        bootstrap.import_system_openapi(
            application=app,
            workspace_id=DEFAULT_WORKSPACE_ID,
            admin_user_id=admin.id,
            session_factory=factory,
            storage=storage,
        )
        is True
    )
    db_session.expire_all()
    previous = db_session.scalar(select(ApiCatalogSpec))
    assert previous is not None
    updated_at = previous.updated_at

    assert (
        bootstrap.reconcile_system_openapi(
            application=app, session_factory=factory, storage=storage
        )
        is False
    )
    db_session.expire_all()
    assert db_session.scalar(select(func.count(ApiCatalogSpec.id))) == 1
    assert db_session.scalar(select(ApiCatalogSpec)).updated_at == updated_at
    assert storage.writes == 1
    assert storage.deleted == []


def test_startup_replaces_entire_stored_document_and_preserves_owner(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import system_openapi_bootstrap as bootstrap

    admin = seed_admin(db_session)
    storage = FakeStorage()
    monkeypatch.setattr(bootstrap, "get_settings", settings)
    factory = session_factory(db_session)
    bootstrap.import_system_openapi(
        application=app,
        workspace_id=DEFAULT_WORKSPACE_ID,
        admin_user_id=admin.id,
        session_factory=factory,
        storage=storage,
    )
    db_session.expire_all()
    old = db_session.scalar(select(ApiCatalogSpec))
    assert old is not None
    old_id = old.id
    old_object = (old.storage_bucket, old.storage_object_key)
    old.document_version = "0.1.0"
    db_session.commit()
    new_payload = changed_payload()
    monkeypatch.setattr(bootstrap, "build_curated_openapi_payload", lambda _app: new_payload)

    assert (
        bootstrap.reconcile_system_openapi(
            application=app, session_factory=factory, storage=storage
        )
        is True
    )
    db_session.expire_all()
    active = db_session.scalar(select(ApiCatalogSpec).where(ApiCatalogSpec.status != "deleted"))
    retired = db_session.get(ApiCatalogSpec, old_id)
    assert active is not None and retired is not None
    assert active.id != old_id
    assert active.system_key == "surgepilot_api"
    assert active.created_by == admin.id
    assert active.document_version == PRODUCT_VERSION
    assert storage.objects[(active.storage_bucket, active.storage_object_key)][0] == new_payload
    assert (
        json.loads(storage.objects[(active.storage_bucket, active.storage_object_key)][0])["info"][
            "version"
        ]
        == PRODUCT_VERSION
    )
    assert retired.status == "deleted"
    assert retired.deleted_by is None
    assert old_object in storage.deleted


def test_startup_does_not_recreate_deleted_system_asset(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import system_openapi_bootstrap as bootstrap

    admin = seed_admin(db_session)
    storage = FakeStorage()
    monkeypatch.setattr(bootstrap, "get_settings", settings)
    factory = session_factory(db_session)
    bootstrap.import_system_openapi(
        application=app,
        workspace_id=DEFAULT_WORKSPACE_ID,
        admin_user_id=admin.id,
        session_factory=factory,
        storage=storage,
    )
    db_session.expire_all()
    spec = db_session.scalar(select(ApiCatalogSpec))
    assert spec is not None
    spec.status = "deleted"
    db_session.commit()

    assert (
        bootstrap.reconcile_system_openapi(
            application=app, session_factory=factory, storage=storage
        )
        is False
    )
    assert db_session.scalar(select(func.count(ApiCatalogSpec.id))) == 1
    assert storage.writes == 1


def test_startup_replacement_commit_failure_preserves_previous_asset(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import system_openapi_bootstrap as bootstrap

    admin = seed_admin(db_session)
    storage = FakeStorage()
    monkeypatch.setattr(bootstrap, "get_settings", settings)
    bootstrap.import_system_openapi(
        application=app,
        workspace_id=DEFAULT_WORKSPACE_ID,
        admin_user_id=admin.id,
        session_factory=session_factory(db_session),
        storage=storage,
    )
    db_session.expire_all()
    previous = db_session.scalar(select(ApiCatalogSpec))
    assert previous is not None
    previous_id = previous.id
    previous_object = (previous.storage_bucket, previous.storage_object_key)
    payload = changed_payload()
    monkeypatch.setattr(bootstrap, "build_curated_openapi_payload", lambda _app: payload)

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
        bootstrap.reconcile_system_openapi(
            application=app, session_factory=failing_factory, storage=storage
        )

    db_session.expire_all()
    assert db_session.scalar(select(func.count(ApiCatalogSpec.id))) == 1
    assert db_session.get(ApiCatalogSpec, previous_id).status == "available"
    assert previous_object in storage.objects
    assert previous_object not in storage.deleted
    assert storage.writes == 2
    assert len(storage.deleted) == 1


@pytest.mark.parametrize("raises", [False, True])
def test_old_object_cleanup_failure_keeps_replacement_authoritative(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, raises: bool
) -> None:
    from app.services import system_openapi_bootstrap as bootstrap

    admin = seed_admin(db_session)
    storage = FakeStorage()
    monkeypatch.setattr(bootstrap, "get_settings", settings)
    factory = session_factory(db_session)
    bootstrap.import_system_openapi(
        application=app,
        workspace_id=DEFAULT_WORKSPACE_ID,
        admin_user_id=admin.id,
        session_factory=factory,
        storage=storage,
    )
    db_session.expire_all()
    old = db_session.scalar(select(ApiCatalogSpec))
    assert old is not None
    old_id = old.id
    old_object = (old.storage_bucket, old.storage_object_key)
    payload = changed_payload()
    monkeypatch.setattr(bootstrap, "build_curated_openapi_payload", lambda _app: payload)

    def fail_cleanup(**_kwargs):
        if raises:
            raise RuntimeError("storage unavailable")
        return False

    monkeypatch.setattr(storage, "delete_object_best_effort", fail_cleanup)

    assert (
        bootstrap.reconcile_system_openapi(
            application=app, session_factory=factory, storage=storage
        )
        is True
    )
    db_session.expire_all()
    active = db_session.scalar(select(ApiCatalogSpec).where(ApiCatalogSpec.status == "available"))
    assert active is not None and active.id != old_id
    assert (active.storage_bucket, active.storage_object_key) in storage.objects
    assert old_object in storage.objects


def test_duplicate_active_system_rows_are_not_reconciled(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import system_openapi_bootstrap as bootstrap
    from app.services.api_catalog import UploadedApiSpec, create_api_catalog_spec

    admin = seed_admin(db_session)
    storage = FakeStorage()
    monkeypatch.setattr(bootstrap, "get_settings", settings)
    factory = session_factory(db_session)
    bootstrap.import_system_openapi(
        application=app,
        workspace_id=DEFAULT_WORKSPACE_ID,
        admin_user_id=admin.id,
        session_factory=factory,
        storage=storage,
    )
    duplicate = create_api_catalog_spec(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor_user_id=admin.id,
        upload=UploadedApiSpec(
            filename="surgepilot-api.openapi.json",
            content_type="application/json",
            payload=bootstrap.build_curated_openapi_payload(app),
            name="SurgePilot API",
        ),
        storage=storage,
        bucket="surgepilot",
        max_bytes=settings().api_catalog_spec_max_bytes,
    )
    duplicate.system_key = "surgepilot_api"
    db_session.commit()
    payload = changed_payload()
    monkeypatch.setattr(bootstrap, "build_curated_openapi_payload", lambda _app: payload)

    assert (
        bootstrap.reconcile_system_openapi(
            application=app, session_factory=factory, storage=storage
        )
        is False
    )
    assert db_session.scalar(select(func.count(ApiCatalogSpec.id))) == 2
    assert storage.writes == 2
    assert storage.deleted == []


@pytest.mark.anyio
async def test_lifespan_continues_when_reconciliation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main
    from app.services import system_openapi_bootstrap as bootstrap

    def fail(**_kwargs):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(bootstrap, "reconcile_system_openapi", fail)
    monkeypatch.setattr(
        main, "reconcile_system_openapi_best_effort", bootstrap.reconcile_system_openapi_best_effort
    )
    async with main.lifespan(app):
        assert True


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
