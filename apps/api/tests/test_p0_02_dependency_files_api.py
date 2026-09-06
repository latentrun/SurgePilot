from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuditEvent, User, Workspace, WorkspaceMember
from app.models.dependency_files import DependencyFile
from app.services.storage import PutResult, StorageClient, StoredObjectStream


class FakeStorage(StorageClient):
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.fail_put = False
        self.fail_get = False
        self.deleted: list[tuple[str, str]] = []

    def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):
        if self.fail_put:
            from app.services.storage import StorageError

            raise StorageError()
        from app.services.storage import LimitedHashingReader

        reader = LimitedHashingReader(stream, size_limit=size_limit)
        data = bytearray()
        while True:
            chunk = reader.read(2)
            if not chunk:
                break
            data.extend(chunk)
        self.objects[(bucket, object_key)] = bytes(data)
        return PutResult(size_bytes=reader.size_bytes, sha256=reader.sha256_hex)

    def get_stream(self, *, bucket, object_key):
        if self.fail_get or (bucket, object_key) not in self.objects:
            from app.services.storage import StorageError

            raise StorageError()
        return StoredObjectStream(
            content_type="text/csv",
            size_bytes=len(self.objects[(bucket, object_key)]),
            stream=BytesIO(self.objects[(bucket, object_key)]),
        )

    def delete_object_best_effort(self, *, bucket, object_key):
        self.deleted.append((bucket, object_key))
        self.objects.pop((bucket, object_key), None)

    def health_check(self):
        return True


async def register_user(
    client: AsyncClient,
    email: str = "dependency-admin@example.com",
    password: str = "password123",
) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": "Dependency Admin", "password": password},
    )
    assert response.status_code == 201
    return response.json()["csrfToken"], response.json()["defaultWorkspace"]["id"]


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


@pytest.fixture()
def fake_storage(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    from app.routes import dependency_files

    storage = FakeStorage()
    monkeypatch.setattr(dependency_files, "get_storage_client", lambda: storage)
    return storage


class UploadRequestWithoutParsing:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers
        self.form_called = False

    async def form(self):
        self.form_called = True
        raise AssertionError("multipart parser should not be called")


@pytest.mark.anyio
async def test_upload_rejects_oversized_content_length_before_form_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.routes.dependency_files import MULTIPART_CONTENT_LENGTH_OVERHEAD, single_upload_file

    monkeypatch.setenv("DEPENDENCY_FILE_MAX_BYTES", "10")
    request = UploadRequestWithoutParsing(
        {
            "content-type": "multipart/form-data; boundary=test",
            "content-length": str(11 + MULTIPART_CONTENT_LENGTH_OVERHEAD),
        }
    )

    with pytest.raises(Exception) as exc_info:
        await single_upload_file(request, max_bytes=10)  # type: ignore[arg-type]

    assert getattr(exc_info.value, "code", None) == "PAYLOAD_TOO_LARGE"
    assert request.form_called is False


@pytest.mark.anyio
async def test_dependency_file_endpoints_require_session_and_csrf(
    client: AsyncClient, fake_storage: FakeStorage
) -> None:
    unauthenticated = await client.get("/api/v1/dependency-files")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "UNAUTHENTICATED"

    csrf_token, _workspace_id = await register_user(client)
    missing_csrf = await client.post(
        "/api/v1/dependency-files",
        files={"file": ("users.csv", b"a,b\n", "text/csv")},
    )
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "CSRF_TOKEN_REQUIRED"

    invalid_csrf = await client.delete(
        "/api/v1/dependency-files/01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        headers={"x-csrf-token": "bad-token"},
    )
    assert invalid_csrf.status_code == 403
    assert invalid_csrf.json()["code"] == "CSRF_TOKEN_INVALID"

    created = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token},
        files={"file": ("users.csv", b"a,b\n", "text/csv")},
    )
    assert created.status_code == 201


@pytest.mark.anyio
async def test_upload_list_get_download_and_delete_dependency_file(
    client: AsyncClient, db_session: Session, fake_storage: FakeStorage
) -> None:
    csrf_token, workspace_id = await register_user(client)
    data = b"id,name\n1,Ada\n"

    created = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files={"file": ("users.csv", data, "text/csv")},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["filename"] == "users.csv"
    assert body["contentType"] == "text/csv"
    assert body["sizeBytes"] == len(data)
    assert body["sha256"] == sha256(data).hexdigest()
    assert body["inUse"] is False
    assert "storageBucket" not in body
    assert "storageObjectKey" not in body
    assert created.headers["x-workspace-id"] == workspace_id

    row = db_session.scalar(select(DependencyFile).where(DependencyFile.id == body["id"]))
    assert row is not None
    assert row.storage_object_key == f"dependency-files/{workspace_id}/{body['id']}/users.csv"
    assert fake_storage.objects[("surgepilot", row.storage_object_key)] == data

    listed = await client.get(
        "/api/v1/dependency-files",
        headers={"x-workspace-id": workspace_id},
        params={"q": "use", "sort": "filename", "page": "1", "pageSize": "20"},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["filename"] == "users.csv"
    assert "storageObjectKey" not in listed.text

    detail = await client.get(f"/api/v1/dependency-files/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["sha256"] == sha256(data).hexdigest()

    downloaded = await client.get(f"/api/v1/dependency-files/{body['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.content == data
    assert downloaded.headers["content-disposition"] == 'attachment; filename="users.csv"'
    assert downloaded.headers["cache-control"] == "private, no-store"
    assert "dependency-files/" not in str(downloaded.headers)

    deleted = await client.delete(
        f"/api/v1/dependency-files/{body['id']}", headers={"x-csrf-token": csrf_token}
    )
    assert deleted.status_code == 204

    db_session.refresh(row)
    assert row.status == "deleted"
    assert row.deleted_by == body["createdBy"]
    assert row.deleted_at is not None
    assert ("surgepilot", row.storage_object_key) in fake_storage.objects

    after_delete = await client.get(f"/api/v1/dependency-files/{body['id']}")
    assert after_delete.status_code == 404

    same_name = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token},
        files={"file": ("USERS.csv", data, "text/csv")},
    )
    assert same_name.status_code == 201

    events = db_session.scalars(select(AuditEvent).order_by(AuditEvent.created_at)).all()
    event_types = [event.event_type for event in events]
    assert "dependency_file.uploaded" in event_types
    assert "dependency_file.downloaded" in event_types
    assert "dependency_file.deleted" in event_types
    for event in events:
        assert "storageObjectKey" not in event.details_json
        assert "storageBucket" not in event.details_json


@pytest.mark.anyio
async def test_upload_commits_metadata_before_dependency_file_audit(
    client: AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    fake_storage: FakeStorage,
) -> None:
    from app.routes import dependency_files as route_module

    csrf_token, workspace_id = await register_user(client, email="audit-upload-order@example.com")
    observed: dict[str, str | None] = {}

    def record_committed_metadata(db: Session, *, file: DependencyFile, **kwargs: object) -> None:
        _ = kwargs
        with Session(bind=db.get_bind(), future=True) as independent_session:
            committed = independent_session.get(DependencyFile, file.id)
            observed["status"] = committed.status if committed is not None else None

    monkeypatch.setattr(route_module, "safe_write_dependency_file_audit", record_committed_metadata)

    created = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files={"file": ("audit-upload.csv", b"abc", "text/csv")},
    )

    assert created.status_code == 201
    assert observed == {"status": "available"}


@pytest.mark.anyio
async def test_delete_commits_metadata_before_dependency_file_audit(
    client: AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    fake_storage: FakeStorage,
) -> None:
    from app.routes import dependency_files as route_module

    csrf_token, workspace_id = await register_user(client, email="audit-delete-order@example.com")
    created = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files={"file": ("audit-delete.csv", b"abc", "text/csv")},
    )
    assert created.status_code == 201
    file_id = created.json()["id"]
    observed: dict[str, str | None] = {}

    def record_committed_metadata(db: Session, *, file: DependencyFile, **kwargs: object) -> None:
        _ = kwargs
        with Session(bind=db.get_bind(), future=True) as independent_session:
            committed = independent_session.get(DependencyFile, file.id)
            observed["status"] = committed.status if committed is not None else None

    monkeypatch.setattr(route_module, "safe_write_dependency_file_audit", record_committed_metadata)

    deleted = await client.delete(
        f"/api/v1/dependency-files/{file_id}",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
    )

    assert deleted.status_code == 204
    assert observed == {"status": "deleted"}


@pytest.mark.anyio
async def test_upload_validation_conflict_query_and_storage_errors(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, fake_storage: FakeStorage
) -> None:
    monkeypatch.setenv("DEPENDENCY_FILE_MAX_BYTES", "4")
    csrf_token, _workspace_id = await register_user(client)

    invalid = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token},
        files={"file": ("bad name.csv", b"abc", "text/csv")},
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "INVALID_FILENAME"

    sensitive = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token},
        files={"file": ("private.pem", b"abc", "application/octet-stream")},
    )
    assert sensitive.status_code == 400
    assert sensitive.json()["code"] == "INVALID_FILENAME"

    oversized = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token},
        files={"file": ("large.csv", b"abcde", "text/csv")},
    )
    assert oversized.status_code == 413
    assert oversized.json()["code"] == "PAYLOAD_TOO_LARGE"

    first = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token},
        files={"file": ("dupe.csv", b"abc", "text/csv")},
    )
    assert first.status_code == 201
    duplicate = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token},
        files={"file": ("DUPE.csv", b"abc", "text/csv")},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "DEPENDENCY_FILE_NAME_CONFLICT"

    invalid_sort = await client.get("/api/v1/dependency-files", params={"sort": "-filename"})
    assert invalid_sort.status_code == 400
    assert invalid_sort.json()["code"] == "INVALID_QUERY_PARAMETER"

    unknown_query = await client.get("/api/v1/dependency-files", params={"unexpected": "1"})
    assert unknown_query.status_code == 400
    assert unknown_query.json()["code"] == "INVALID_QUERY_PARAMETER"

    non_multipart = await client.post(
        "/api/v1/dependency-files", headers={"x-csrf-token": csrf_token}, json={"file": "bad"}
    )
    assert non_multipart.status_code == 415
    assert non_multipart.json()["code"] == "UNSUPPORTED_MEDIA_TYPE"

    unsupported_form_field = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token},
        files={"file": ("extra.csv", b"abc", "text/csv")},
        data={"storageObjectKey": "dependency-files/leak"},
    )
    assert unsupported_form_field.status_code == 400
    assert unsupported_form_field.json()["code"] == "INVALID_REQUEST"

    fake_storage.fail_put = True
    outage = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token},
        files={"file": ("outage.csv", b"abc", "text/csv")},
    )
    assert outage.status_code == 503
    assert outage.json()["code"] == "STORAGE_UNAVAILABLE"


@pytest.mark.anyio
async def test_dependency_files_are_workspace_isolated(
    client: AsyncClient, db_session: Session, fake_storage: FakeStorage
) -> None:
    csrf_token, workspace_id = await register_user(client)
    user = db_session.scalar(select(User).where(User.email == "dependency-admin@example.com"))
    assert user is not None
    other_workspace_id = seed_other_workspace(db_session, user.id)

    other = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": other_workspace_id},
        files={"file": ("shared.csv", b"abc", "text/csv")},
    )
    assert other.status_code == 201

    same_name_default = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files={"file": ("SHARED.csv", b"abc", "text/csv")},
    )
    assert same_name_default.status_code == 201

    hidden = await client.get(
        f"/api/v1/dependency-files/{other.json()['id']}", headers={"x-workspace-id": workspace_id}
    )
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "RESOURCE_NOT_FOUND"
    assert hidden.headers["x-workspace-id"] == workspace_id

    hidden_download = await client.get(
        f"/api/v1/dependency-files/{other.json()['id']}/download",
        headers={"x-workspace-id": workspace_id},
    )
    assert hidden_download.status_code == 404
    assert hidden_download.json()["code"] == "RESOURCE_NOT_FOUND"
    assert hidden_download.headers["x-workspace-id"] == workspace_id

    hidden_delete = await client.delete(
        f"/api/v1/dependency-files/{other.json()['id']}",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
    )
    assert hidden_delete.status_code == 404
    assert hidden_delete.json()["code"] == "RESOURCE_NOT_FOUND"
    assert hidden_delete.headers["x-workspace-id"] == workspace_id

    other_list = await client.get(
        "/api/v1/dependency-files", headers={"x-workspace-id": other_workspace_id}
    )
    assert other_list.status_code == 200
    assert other_list.json()["items"][0]["filename"] == "shared.csv"


@pytest.mark.anyio
async def test_dependency_file_extension_allowlist_enforced_when_configured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, fake_storage: FakeStorage
) -> None:
    monkeypatch.setenv("DEPENDENCY_FILE_ALLOWED_EXTENSIONS", ".csv")
    csrf_token, workspace_id = await register_user(client, email="ext-allow@example.com")

    blocked_extension = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files={"file": ("users.txt", b"id,name\n1,Ada\n", "text/plain")},
    )
    assert blocked_extension.status_code == 422
    assert blocked_extension.json()["code"] == "VALIDATION_ERROR"
    assert blocked_extension.json()["details"] == [
        {
            "field": "file",
            "code": "UNSUPPORTED_FILE_EXTENSION",
            "message": "File extension is not allowed.",
        }
    ]

    created = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        files={"file": ("users.csv", b"id,name\n1,Ada\n", "text/csv")},
    )
    assert created.status_code == 201


@pytest.mark.anyio
async def test_delete_returns_file_in_use_when_reference_checker_reports_reference(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, fake_storage: FakeStorage
) -> None:
    from app.services.dependency_files import DependencyFileReferenceChecker

    csrf_token, _workspace_id = await register_user(client)
    created = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token},
        files={"file": ("referenced.csv", b"abc", "text/csv")},
    )
    assert created.status_code == 201

    monkeypatch.setattr(
        DependencyFileReferenceChecker, "is_in_use", lambda self, dependency_file_id: True
    )
    deleted = await client.delete(
        f"/api/v1/dependency-files/{created.json()['id']}", headers={"x-csrf-token": csrf_token}
    )
    assert deleted.status_code == 409
    assert deleted.json()["code"] == "FILE_IN_USE"


@pytest.mark.anyio
async def test_download_storage_outage_and_audit_failure_do_not_expose_internals(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, fake_storage: FakeStorage
) -> None:
    from app.services import dependency_files as service

    csrf_token, _workspace_id = await register_user(client)
    created = await client.post(
        "/api/v1/dependency-files",
        headers={"x-csrf-token": csrf_token},
        files={"file": ("download.csv", b"abc", "text/csv")},
    )
    assert created.status_code == 201

    def failing_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(service, "write_audit_event_in_new_transaction", failing_audit)
    ok_download = await client.get(f"/api/v1/dependency-files/{created.json()['id']}/download")
    assert ok_download.status_code == 200

    fake_storage.fail_get = True
    outage = await client.get(f"/api/v1/dependency-files/{created.json()['id']}/download")
    assert outage.status_code == 503
    body = outage.json()
    assert body["code"] == "STORAGE_UNAVAILABLE"
    assert "dependency-files/" not in body["message"]
