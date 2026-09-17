from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.api_catalog import ApiCatalogSpec
from app.models.auth import AuditEvent, Workspace, WorkspaceMember
from app.services.storage import PutResult, StorageClient, StoredObjectStream


class FakeStorage(StorageClient):
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, str | None]] = {}
        self.deleted: list[tuple[str, str]] = []
        self.fail_put = False
        self.fail_get = False

    def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):
        if self.fail_put:
            from app.services.storage import StorageError

            raise StorageError()
        from app.services.storage import LimitedHashingReader

        reader = LimitedHashingReader(stream, size_limit=size_limit)
        data = bytearray()
        while True:
            chunk = reader.read(3)
            if not chunk:
                break
            data.extend(chunk)
        self.objects[(bucket, object_key)] = (bytes(data), content_type)
        return PutResult(size_bytes=reader.size_bytes, sha256=reader.sha256_hex)

    def get_stream(self, *, bucket, object_key):
        if self.fail_get or (bucket, object_key) not in self.objects:
            from app.services.storage import StorageError

            raise StorageError()
        payload, content_type = self.objects[(bucket, object_key)]
        return StoredObjectStream(
            content_type=content_type,
            size_bytes=len(payload),
            stream=BytesIO(payload),
        )

    def delete_object_best_effort(self, *, bucket, object_key):
        self.deleted.append((bucket, object_key))
        self.objects.pop((bucket, object_key), None)

    def copy_object(self, *, bucket, source_key, destination_key):
        self.objects[(bucket, destination_key)] = self.objects[(bucket, source_key)]

    def health_check(self):
        return True


@pytest.fixture()
def fake_storage(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    from app.routes import api_catalog

    storage = FakeStorage()
    monkeypatch.setattr(api_catalog, "get_storage_client", lambda: storage)
    return storage


async def register_user(
    client: AsyncClient,
    email: str = "api-catalog@example.com",
    password: str = "password123",
) -> tuple[str, str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": "API Catalog User", "password": password},
    )
    assert response.status_code == 201
    body = response.json()
    return body["csrfToken"], body["defaultWorkspace"]["id"], body["user"]["id"]


def seed_other_workspace(db_session: Session, user_id: str) -> str:
    now = datetime.now(UTC)
    workspace = Workspace(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        name="Other Workspace",
        status="active",
        created_at=now,
        updated_at=now,
    )
    db_session.add(workspace)
    db_session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user_id, joined_at=now))
    db_session.flush()
    return workspace.id


OPENAPI_JSON = b'{"openapi":"3.1.0","info":{"title":"Orders API","version":"1.0.0"},"paths":{},"servers":[{"url":"https://api.example.invalid"}]}'
SWAGGER_YAML = b"""
swagger: '2.0'
info:
  title: Inventory API
  version: 1.0
paths: {}
"""


@pytest.mark.anyio
async def test_api_catalog_upload_list_detail_content_and_delete(
    client: AsyncClient, db_session: Session, fake_storage: FakeStorage
) -> None:
    csrf_token, workspace_id, user_id = await register_user(client)

    created = await client.post(
        "/api/v1/api-catalog/specs",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        data={"name": "Orders docs"},
        files={"file": ("orders-openapi.json", OPENAPI_JSON, "application/json")},
    )

    assert created.status_code == 201
    assert created.headers["x-workspace-id"] == workspace_id
    body = created.json()
    assert body["name"] == "Orders docs"
    assert body["filename"] == "orders-openapi.json"
    assert body["sourceFormat"] == "openapi_json"
    assert body["openapiVersion"] == "3.1.0"
    assert body["documentTitle"] == "Orders API"
    assert body["documentVersion"] == "1.0.0"
    assert body["sizeBytes"] == len(OPENAPI_JSON)
    assert body["sha256"] == sha256(OPENAPI_JSON).hexdigest()
    assert body["status"] == "available"
    assert body["contentUrl"] == f"/api/v1/api-catalog/specs/{body['id']}/content"
    assert "storageBucket" not in body
    assert "storageObjectKey" not in body
    assert "api-catalog-specs/" not in created.text

    row = db_session.scalar(select(ApiCatalogSpec).where(ApiCatalogSpec.id == body["id"]))
    assert row is not None
    assert row.workspace_id == workspace_id
    assert row.created_by == user_id
    assert (
        row.storage_object_key
        == f"api-catalog-specs/{workspace_id}/{body['id']}/orders-openapi.json"
    )
    assert fake_storage.objects[("surgepilot", row.storage_object_key)] == (
        OPENAPI_JSON,
        "application/json",
    )

    listed = await client.get(
        "/api/v1/api-catalog/specs",
        headers={"x-workspace-id": workspace_id},
        params={"limit": "50", "offset": "0"},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["limit"] == 50
    assert listed.json()["offset"] == 0
    assert listed.json()["items"][0]["id"] == body["id"]
    assert "contentUrl" not in listed.json()["items"][0]
    assert "storageObjectKey" not in listed.text

    detail = await client.get(
        f"/api/v1/api-catalog/specs/{body['id']}", headers={"x-workspace-id": workspace_id}
    )
    assert detail.status_code == 200
    assert detail.json()["contentUrl"].endswith("/content")
    assert detail.json()["contentUrl"].startswith("/api/v1/")
    assert "http://" not in detail.json()["contentUrl"]

    content = await client.get(
        f"/api/v1/api-catalog/specs/{body['id']}/content",
        headers={"x-workspace-id": workspace_id},
    )
    assert content.status_code == 200
    assert content.content == OPENAPI_JSON
    assert content.headers["cache-control"] == "private, no-store"
    assert content.headers["x-workspace-id"] == workspace_id
    assert "api-catalog-specs/" not in str(content.headers)

    deleted = await client.delete(
        f"/api/v1/api-catalog/specs/{body['id']}",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
    )
    assert deleted.status_code == 204
    assert ("surgepilot", row.storage_object_key) in fake_storage.deleted
    assert ("surgepilot", row.storage_object_key) not in fake_storage.objects

    db_session.refresh(row)
    assert row.status == "deleted"
    assert row.deleted_by == user_id
    assert row.deleted_at is not None

    after_delete = await client.get(
        f"/api/v1/api-catalog/specs/{body['id']}", headers={"x-workspace-id": workspace_id}
    )
    assert after_delete.status_code == 404

    events = db_session.scalars(select(AuditEvent).order_by(AuditEvent.created_at)).all()
    event_types = [event.event_type for event in events]
    assert "api_catalog_spec.uploaded" in event_types
    assert "api_catalog_spec.deleted" in event_types
    for event in events:
        assert "storageObjectKey" not in event.details_json
        assert "storageBucket" not in event.details_json
        assert "api-catalog-specs" not in event.details_json


@pytest.mark.anyio
async def test_api_catalog_upload_accepts_swagger_yaml_and_derives_name(
    client: AsyncClient, fake_storage: FakeStorage
) -> None:
    csrf_token, workspace_id, _user_id = await register_user(
        client, email="api-catalog-yaml@example.com"
    )

    created = await client.post(
        "/api/v1/api-catalog/specs",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files={"file": ("inventory.yaml", SWAGGER_YAML, "text/yaml")},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Inventory API"
    assert body["sourceFormat"] == "swagger_yaml"
    assert body["openapiVersion"] == "2.0"
    assert body["documentVersion"] == "1.0"


@pytest.mark.anyio
async def test_api_catalog_rejects_invalid_uploads_safely(
    client: AsyncClient, fake_storage: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf_token, workspace_id, _user_id = await register_user(
        client, email="api-catalog-invalid@example.com"
    )

    empty = await client.post(
        "/api/v1/api-catalog/specs",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files={"file": ("empty.yaml", b"", "text/yaml")},
    )
    assert empty.status_code == 422
    assert empty.json()["code"] == "API_SPEC_PARSE_FAILED"
    assert "bucket" not in empty.text.lower()
    assert "traceback" not in empty.text.lower()

    malformed = await client.post(
        "/api/v1/api-catalog/specs",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files={"file": ("bad.json", b'{"openapi":', "application/json")},
    )
    assert malformed.status_code == 422
    assert malformed.json()["code"] == "API_SPEC_PARSE_FAILED"
    assert '{"openapi"' not in malformed.text

    unsupported_root = await client.post(
        "/api/v1/api-catalog/specs",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files={"file": ("not-openapi.yaml", b"name: nope\n", "text/yaml")},
    )
    assert unsupported_root.status_code == 422
    assert unsupported_root.json()["code"] == "UNSUPPORTED_API_SPEC_FORMAT"

    unsupported_extension = await client.post(
        "/api/v1/api-catalog/specs",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files={"file": ("openapi.txt", OPENAPI_JSON, "application/json")},
    )
    assert unsupported_extension.status_code == 422
    assert unsupported_extension.json()["code"] == "UNSUPPORTED_API_SPEC_FORMAT"

    multiple_files = await client.post(
        "/api/v1/api-catalog/specs",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files=[
            ("file", ("orders.json", OPENAPI_JSON, "application/json")),
            ("file", ("inventory.yaml", SWAGGER_YAML, "text/yaml")),
        ],
    )
    assert multiple_files.status_code == 422
    assert multiple_files.json()["code"] == "VALIDATION_ERROR"
    assert multiple_files.json()["details"][0]["field"] == "file"

    monkeypatch.setenv("SURGEPILOT_API_CATALOG_SPEC_MAX_BYTES", "10")
    oversized = await client.post(
        "/api/v1/api-catalog/specs",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files={"file": ("orders.json", OPENAPI_JSON, "application/json")},
    )
    assert oversized.status_code == 413
    assert oversized.json()["code"] == "API_SPEC_TOO_LARGE"


@pytest.mark.anyio
async def test_api_catalog_auth_csrf_workspace_and_storage_boundaries(
    client: AsyncClient, db_session: Session, fake_storage: FakeStorage
) -> None:
    unauthenticated = await client.get("/api/v1/api-catalog/specs")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "UNAUTHENTICATED"

    csrf_token, workspace_id, user_id = await register_user(
        client, email="api-catalog-boundary@example.com"
    )
    missing_csrf = await client.post(
        "/api/v1/api-catalog/specs",
        files={"file": ("orders.json", OPENAPI_JSON, "application/json")},
    )
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "CSRF_TOKEN_REQUIRED"

    created = await client.post(
        "/api/v1/api-catalog/specs",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files={"file": ("orders.json", OPENAPI_JSON, "application/json")},
    )
    assert created.status_code == 201
    spec_id = created.json()["id"]

    other_workspace_id = seed_other_workspace(db_session, user_id)
    other_detail = await client.get(
        f"/api/v1/api-catalog/specs/{spec_id}",
        headers={"x-workspace-id": other_workspace_id},
    )
    assert other_detail.status_code == 404
    other_content = await client.get(
        f"/api/v1/api-catalog/specs/{spec_id}/content",
        headers={"x-workspace-id": other_workspace_id},
    )
    assert other_content.status_code == 404
    other_delete = await client.delete(
        f"/api/v1/api-catalog/specs/{spec_id}",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": other_workspace_id},
    )
    assert other_delete.status_code == 404

    fake_storage.fail_get = True
    content = await client.get(
        f"/api/v1/api-catalog/specs/{spec_id}/content",
        headers={"x-workspace-id": workspace_id},
    )
    assert content.status_code == 503
    assert content.json()["code"] == "STORAGE_UNAVAILABLE"
    assert "api-catalog-specs" not in content.text
    assert "surgepilot" not in content.text

    fake_storage.fail_get = False
    fake_storage.fail_put = True
    unavailable = await client.post(
        "/api/v1/api-catalog/specs",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files={"file": ("inventory.yaml", SWAGGER_YAML, "text/yaml")},
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["code"] == "STORAGE_UNAVAILABLE"


@pytest.mark.anyio
async def test_api_catalog_does_not_call_external_servers(
    client: AsyncClient, fake_storage: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf_token, workspace_id, _user_id = await register_user(
        client, email="api-catalog-network@example.com"
    )

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("API Catalog upload must not resolve remote references or server URLs")

    import socket

    monkeypatch.setattr(socket, "create_connection", fail_if_called)
    spec_with_remote_refs = b'{"openapi":"3.0.3","info":{"title":"Remote Ref API","version":"1"},"servers":[{"url":"https://api.example.invalid"}],"paths":{},"components":{"schemas":{"Remote":{"$ref":"https://example.invalid/schema.json"}}}}'

    created = await client.post(
        "/api/v1/api-catalog/specs",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files={"file": ("remote.json", spec_with_remote_refs, "application/json")},
    )

    assert created.status_code == 201
    assert created.json()["documentTitle"] == "Remote Ref API"


@pytest.mark.anyio
async def test_api_catalog_upload_requires_content_length_before_form_parse() -> None:
    from app.core.errors import AppError
    from app.routes.api_catalog import parse_upload_form

    class MissingLengthRequest:
        headers = {"content-type": "multipart/form-data; boundary=test"}

        async def form(self, **_kwargs):
            raise AssertionError("form parsing should not run without Content-Length")

    with pytest.raises(AppError) as exc_info:
        await parse_upload_form(MissingLengthRequest(), max_bytes=10)  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_REQUEST"
    assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_api_catalog_upload_form_validation_branches() -> None:
    from starlette.datastructures import Headers, UploadFile

    from app.core.errors import AppError
    from app.routes.api_catalog import parse_upload_form

    class FakeForm:
        def __init__(self, items):
            self._items = items

        def multi_items(self):
            return list(self._items)

    class FakeRequest:
        def __init__(self, *, content_length: str, items):
            self.headers = {
                "content-type": "multipart/form-data; boundary=test",
                "content-length": content_length,
            }
            self._items = items

        async def form(self, **_kwargs):
            return FakeForm(self._items)

    upload = UploadFile(
        BytesIO(OPENAPI_JSON),
        filename="orders.json",
        headers=Headers({"content-type": "application/json"}),
    )

    invalid_length = FakeRequest(content_length="not-an-int", items=[])
    with pytest.raises(AppError) as invalid_length_error:
        await parse_upload_form(invalid_length, max_bytes=10)
    assert invalid_length_error.value.code == "INVALID_REQUEST"

    oversized_length = FakeRequest(content_length=str(2 * 1024 * 1024), items=[])
    with pytest.raises(AppError) as oversized_length_error:
        await parse_upload_form(oversized_length, max_bytes=10)
    assert oversized_length_error.value.code == "API_SPEC_TOO_LARGE"
    assert oversized_length_error.value.status_code == 413

    unsupported_field = FakeRequest(
        content_length="256",
        items=[("file", upload), ("unexpected", "value")],
    )
    with pytest.raises(AppError) as unsupported_field_error:
        await parse_upload_form(unsupported_field, max_bytes=1024)
    assert unsupported_field_error.value.code == "VALIDATION_ERROR"
    assert unsupported_field_error.value.details[0]["field"] == "unexpected"

    multiple_names = FakeRequest(
        content_length="256",
        items=[("file", upload), ("name", "one"), ("name", "two")],
    )
    with pytest.raises(AppError) as multiple_names_error:
        await parse_upload_form(multiple_names, max_bytes=1024)
    assert multiple_names_error.value.code == "VALIDATION_ERROR"
    assert multiple_names_error.value.details[0]["field"] == "name"
