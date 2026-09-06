from datetime import UTC, datetime
from io import BytesIO
import os
import time
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.auth import DEFAULT_WORKSPACE_ID, AuditEvent, User
from app.models.dependency_files import DependencyFile
from app.services.storage import PutResult, StorageClient


def test_safe_filename_and_sensitive_blocklist_rules() -> None:
    from app.services.dependency_files import validate_dependency_filename

    assert validate_dependency_filename("users.csv", allowed_extensions=[]) == "users.csv"
    assert validate_dependency_filename("cert-prod.pem", allowed_extensions=[]) == "cert-prod.pem"
    assert validate_dependency_filename("client.key", allowed_extensions=[]) == "client.key"

    for filename in [
        "",
        ".",
        "..",
        "bad/name.csv",
        "bad\\name.csv",
        "bad name.csv",
        "invalid$name.csv",
    ]:
        with pytest.raises(AppError) as exc_info:
            validate_dependency_filename(filename, allowed_extensions=[])
        assert exc_info.value.code == "INVALID_FILENAME"

    for filename in [
        ".env",
        ".env.local",
        ".git",
        ".gitignore",
        "id_rsa",
        "id_ed25519.pub",
        "private.pem",
        "team.private.key",
    ]:
        with pytest.raises(AppError) as exc_info:
            validate_dependency_filename(filename, allowed_extensions=[])
        assert exc_info.value.code == "INVALID_FILENAME"


def test_extension_allowlist_is_optional_and_case_insensitive() -> None:
    from app.services.dependency_files import parse_allowed_extensions, validate_dependency_filename

    assert parse_allowed_extensions("") == []
    assert parse_allowed_extensions(".csv, json, .TXT") == [".csv", ".json", ".txt"]
    assert validate_dependency_filename("users.JSON", allowed_extensions=[".json"]) == "users.JSON"

    with pytest.raises(AppError) as unsupported:
        validate_dependency_filename("users.csv", allowed_extensions=[".json"])
    assert unsupported.value.code == "VALIDATION_ERROR"
    assert unsupported.value.details == [
        {
            "field": "file",
            "code": "UNSUPPORTED_FILE_EXTENSION",
            "message": "File extension is not allowed.",
        }
    ]


def test_dependency_file_object_key_is_strict_and_not_normalized() -> None:
    from app.services.dependency_files import dependency_file_object_key

    key = dependency_file_object_key(
        workspace_id=DEFAULT_WORKSPACE_ID,
        dependency_file_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        filename="users.csv",
    )
    assert key == "dependency-files/01HZW000000000000000000000/01HZX3Y9M0E9W7Z6M5QK9S8P7A/users.csv"

    with pytest.raises(AppError):
        dependency_file_object_key(
            workspace_id=DEFAULT_WORKSPACE_ID,
            dependency_file_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
            filename="../users.csv",
        )


def test_limited_hashing_reader_counts_size_hash_and_rejects_limit() -> None:
    from app.services.storage import LimitedHashingReader

    reader = LimitedHashingReader(BytesIO(b"abc"), size_limit=3)
    assert reader.read(2) == b"ab"
    assert reader.read(2) == b"c"
    assert reader.read(2) == b""
    assert reader.size_bytes == 3
    assert reader.sha256_hex == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    oversized = LimitedHashingReader(BytesIO(b"abcd"), size_limit=3)
    with pytest.raises(AppError) as exc_info:
        while oversized.read(2):
            pass
    assert exc_info.value.code == "PAYLOAD_TOO_LARGE"


def test_storage_client_base_methods_are_abstract() -> None:
    from app.services.storage import StorageClient

    storage = StorageClient()

    with pytest.raises(NotImplementedError):
        storage.put_stream(bucket="surgepilot", object_key="key", stream=BytesIO(), size_limit=1)
    with pytest.raises(NotImplementedError):
        storage.get_stream(bucket="surgepilot", object_key="key")
    with pytest.raises(NotImplementedError):
        storage.delete_object_best_effort(bucket="surgepilot", object_key="key")
    with pytest.raises(NotImplementedError):
        storage.health_check()


def test_minio_storage_client_uses_safe_logs_and_wraps_failures(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app.services import storage as storage_module
    from app.services.storage import MinioStorageClient, StorageError

    class FailingMinio:
        def __init__(self, endpoint, access_key, secret_key, secure, region):
            self.endpoint = endpoint
            self.access_key = access_key
            self.secret_key = secret_key
            self.secure = secure
            self.region = region

        def put_object(self, *args, **kwargs):
            raise OSError("raw minio endpoint and bucket detail")

        def get_object(self, *args, **kwargs):
            raise OSError("raw object detail")

        def stat_object(self, *args, **kwargs):
            raise OSError("raw stat detail")

        def remove_object(self, *args, **kwargs):
            raise OSError("raw delete detail")

        def bucket_exists(self, *args, **kwargs):
            raise OSError("raw health detail")

    monkeypatch.setenv("MINIO_ENDPOINT", "https://minio.example.test:9443")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "access-key")
    monkeypatch.setenv("MINIO_SECRET_KEY", "secret-key")
    monkeypatch.setenv("MINIO_REGION", "us-test-1")
    monkeypatch.setattr(storage_module, "Minio", FailingMinio)

    client = MinioStorageClient()
    assert client._client.endpoint == "minio.example.test:9443"
    assert client._client.secure is True
    assert client._client.region == "us-test-1"

    with caplog.at_level("DEBUG", logger="app.services.storage"):
        with pytest.raises(StorageError):
            client.put_stream(
                bucket="confidential-bucket",
                object_key="dependency-files/key",
                stream=BytesIO(b"abc"),
                size_limit=10,
            )
        with pytest.raises(StorageError):
            client.get_stream(bucket="confidential-bucket", object_key="dependency-files/key")
        client.delete_object_best_effort(
            bucket="confidential-bucket", object_key="dependency-files/key"
        )

    assert client.health_check() is False
    warning_text = "\n".join(record.getMessage() for record in caplog.records)
    full_log_text = "\n".join(
        f"{record.getMessage()} {record.__dict__}" for record in caplog.records
    )
    assert "STORAGE_UNAVAILABLE" in warning_text
    assert "dependency-files/key" not in full_log_text
    assert "confidential-bucket" not in full_log_text
    assert "minio.example.test" not in full_log_text
    assert "secret-key" not in full_log_text
    assert "raw minio endpoint and bucket detail" not in full_log_text
    assert all(record.exc_info is None for record in caplog.records)


def test_minio_storage_client_with_fake_minio_round_trips_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import storage as storage_module
    from app.services.storage import MinioStorageClient

    class Stat:
        content_type = "text/csv"
        size = 3

    class FakeMinio:
        objects: dict[tuple[str, str], bytes] = {}
        probe_puts = 0
        probe_gets = 0
        probe_deletes = 0
        probe_releases = 0

        def __init__(self, endpoint, access_key, secret_key, secure, region):
            self.endpoint = endpoint

        def put_object(self, bucket, object_key, reader, length, part_size, content_type):
            chunks = bytearray()
            while True:
                chunk = reader.read(2)
                if not chunk:
                    break
                chunks.extend(chunk)
            self.objects[(bucket, object_key)] = bytes(chunks)

        def get_object(self, bucket, object_key):
            class Response(BytesIO):
                def release_conn(self) -> None:
                    FakeMinio.probe_releases += 1

            return Response(self.objects[(bucket, object_key)])

        def stat_object(self, bucket, object_key):
            return Stat()

        def remove_object(self, bucket, object_key):
            if object_key.startswith("health/"):
                type(self).probe_deletes += 1
            self.objects.pop((bucket, object_key), None)

        def bucket_exists(self, bucket):
            return bucket == "surgepilot"

    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9000")
    monkeypatch.setenv("MINIO_SECURE", "true")
    monkeypatch.setattr(storage_module, "Minio", FakeMinio)

    client = MinioStorageClient()
    result = client.put_stream(
        bucket="surgepilot",
        object_key="dependency-files/test/users.csv",
        stream=BytesIO(b"abc"),
        size_limit=10,
        content_type="text/csv",
    )

    assert result.size_bytes == 3
    assert result.sha256 == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    stored = client.get_stream(bucket="surgepilot", object_key="dependency-files/test/users.csv")
    assert stored.content_type == "text/csv"
    assert stored.size_bytes == 3
    assert stored.stream.read() == b"abc"
    assert client.health_check() is True
    assert any(key[1].startswith("health/") for key in FakeMinio.objects) is False
    assert FakeMinio.probe_deletes == 1
    assert FakeMinio.probe_releases == 1
    client.delete_object_best_effort(
        bucket="surgepilot", object_key="dependency-files/test/users.csv"
    )
    assert FakeMinio.objects == {}


def test_minio_health_check_fails_when_bucket_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import storage as storage_module
    from app.services.storage import MinioStorageClient

    class MissingBucketMinio:
        def __init__(self, *args, **kwargs):
            pass

        def bucket_exists(self, bucket):
            return False

        def put_object(self, *args, **kwargs):
            raise AssertionError("health check must not write when bucket is missing")

        def remove_object(self, *args, **kwargs):
            pass

    monkeypatch.setattr(storage_module, "Minio", MissingBucketMinio)

    assert MinioStorageClient().health_check() is False


def test_get_storage_client_caches_minio_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import storage as storage_module

    class FakeMinio:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(storage_module, "_storage_client", None)
    monkeypatch.setattr(storage_module, "Minio", FakeMinio)

    first = storage_module.get_storage_client()
    second = storage_module.get_storage_client()

    assert first is second


@pytest.mark.skipif(
    os.environ.get("SURGEPILOT_REAL_MINIO_TEST") != "1",
    reason="set SURGEPILOT_REAL_MINIO_TEST=1 with local MinIO to run storage integration",
)
def test_real_minio_storage_adapter_round_trip() -> None:
    from app.services.storage import MinioStorageClient, StorageError

    client = MinioStorageClient()
    deadline = time.monotonic() + 30
    while True:
        if client.health_check():
            break
        if time.monotonic() >= deadline:
            pytest.fail("MinIO bucket did not become available for storage integration test")
        time.sleep(1)

    object_key = "dependency-files/01HZW000000000000000000000/01HZX3Y9M0E9W7Z6M5QK9S8P7A/pytest.csv"
    payload = b"id,name\n1,Ada\n"
    result = client.put_stream(
        bucket="surgepilot",
        object_key=object_key,
        stream=BytesIO(payload),
        size_limit=1024,
        content_type="text/csv",
    )
    try:
        assert result.size_bytes == len(payload)
        stored = client.get_stream(bucket="surgepilot", object_key=object_key)
        try:
            assert stored.content_type == "text/csv"
            assert stored.stream.read() == payload
        finally:
            stored.stream.close()
    finally:
        client.delete_object_best_effort(bucket="surgepilot", object_key=object_key)

    with pytest.raises(StorageError):
        client.get_stream(bucket="surgepilot", object_key=object_key)


def test_reference_checker_is_false_for_p0_02() -> None:
    from app.services.dependency_files import DependencyFileReferenceChecker

    checker = DependencyFileReferenceChecker()

    assert checker.is_in_use("01HZX3Y9M0E9W7Z6M5QK9S8P7A") is False


def test_case_insensitive_name_uniqueness_active_only(db_session: Session) -> None:
    from app.services.dependency_files import (
        create_dependency_file_metadata,
        delete_dependency_file_metadata,
    )

    now = datetime.now(UTC)
    user = User(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        email="dep-user@example.com",
        display_name="Dependency User",
        password_hash="hash",
        role="user",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.flush()

    created = create_dependency_file_metadata(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor_user_id=user.id,
        filename="Users.csv",
        content_type="text/csv",
        size_bytes=3,
        sha256="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        storage_bucket="surgepilot",
        storage_object_key="dependency-files/key",
    )
    assert created.filename == "Users.csv"

    with pytest.raises(AppError) as conflict:
        create_dependency_file_metadata(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor_user_id=user.id,
            filename="users.csv",
            content_type="text/csv",
            size_bytes=3,
            sha256="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            storage_bucket="surgepilot",
            storage_object_key="dependency-files/key2",
        )
    assert conflict.value.code == "DEPENDENCY_FILE_NAME_CONFLICT"

    delete_dependency_file_metadata(db_session, file=created, actor_user_id=user.id)
    recreated = create_dependency_file_metadata(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor_user_id=user.id,
        filename="users.csv",
        content_type="text/csv",
        size_bytes=3,
        sha256="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        storage_bucket="surgepilot",
        storage_object_key="dependency-files/key3",
    )
    assert recreated.status == "available"


def test_upload_cleanup_deletes_object_when_metadata_creation_fails(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import dependency_files as service
    from app.services.storage import PutResult, StorageClient

    class RecordingStorage(StorageClient):
        def __init__(self) -> None:
            self.put_objects: list[tuple[str, str]] = []
            self.deleted_objects: list[tuple[str, str]] = []

        def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):
            _ = stream, size_limit, content_type
            self.put_objects.append((bucket, object_key))
            return PutResult(
                size_bytes=3,
                sha256="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            )

        def delete_object_best_effort(self, *, bucket, object_key):
            self.deleted_objects.append((bucket, object_key))

    def failing_create_metadata(*args, **kwargs):
        _ = args, kwargs
        raise AppError("VALIDATION_ERROR", "Validation failed.", 422)

    storage = RecordingStorage()
    monkeypatch.setattr(service, "create_dependency_file_metadata", failing_create_metadata)

    with pytest.raises(AppError) as exc_info:
        service.upload_dependency_file(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor_user_id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
            filename="users.csv",
            content_type="text/csv",
            source=BytesIO(b"abc"),
            storage=storage,
            bucket="surgepilot",
            max_bytes=100,
            allowed_extensions=[],
        )

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert storage.put_objects
    assert storage.deleted_objects == storage.put_objects


def test_audit_details_exclude_storage_internals() -> None:
    from app.services.dependency_files import audit_details_for_upload

    details = audit_details_for_upload(
        dependency_file_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        workspace_id=DEFAULT_WORKSPACE_ID,
        filename="users.csv",
        size_bytes=3,
        sha256="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        request_id="req_123",
    )

    assert details == {
        "dependencyFileId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        "workspaceId": DEFAULT_WORKSPACE_ID,
        "filename": "users.csv",
        "sizeBytes": 3,
        "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        "requestId": "req_123",
    }
    assert "storageObjectKey" not in details
    assert "storageBucket" not in details


def test_dependency_file_audit_db_failure_does_not_pollute_caller_transaction(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app.models.dependency_files import DependencyFile
    from app.services import audit as audit_service
    from app.services import dependency_files as service

    now = datetime.now(UTC)
    user = User(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7D",
        email="audit-isolation@example.com",
        display_name="Audit Isolation",
        password_hash="hash",
        role="user",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )
    file = DependencyFile(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
        workspace_id=DEFAULT_WORKSPACE_ID,
        filename="audit.csv",
        content_type="text/csv",
        size_bytes=3,
        sha256="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        storage_bucket="surgepilot",
        storage_object_key="dependency-files/internal-key",
        status="available",
        created_by=user.id,
        created_at=now,
    )
    db_session.add_all([user, file])
    db_session.commit()

    def add_invalid_audit_row(db: Session, **kwargs: object) -> None:
        db.add(
            AuditEvent(
                id="bad",
                event_type=str(kwargs["event_type"]),
                actor_user_id=str(kwargs["actor_user_id"]),
                workspace_id=str(kwargs["workspace_id"]),
                target_type=str(kwargs["target_type"]),
                target_id=str(kwargs["target_id"]),
                request_id="req_audit_isolation",
                ip_address=None,
                user_agent=None,
                details_json={},
                created_at=datetime.now(UTC),
            )
        )

    monkeypatch.setattr(service, "write_audit_event", add_invalid_audit_row, raising=False)
    monkeypatch.setattr(audit_service, "write_audit_event", add_invalid_audit_row)
    request = SimpleNamespace(
        state=SimpleNamespace(request_id="req_audit_isolation"),
        headers={},
        client=None,
    )

    with caplog.at_level("ERROR", logger="app.services.dependency_files"):
        service.safe_write_dependency_file_audit(
            db_session,
            request=request,  # type: ignore[arg-type]
            event_type="dependency_file.downloaded",
            actor_user_id=user.id,
            workspace_id=DEFAULT_WORKSPACE_ID,
            file=file,
            details={
                "dependencyFileId": file.id,
                "workspaceId": DEFAULT_WORKSPACE_ID,
                "filename": file.filename,
                "sizeBytes": file.size_bytes,
                "requestId": "req_audit_isolation",
            },
        )

    file.filename = "audit-renamed.csv"
    db_session.commit()
    db_session.refresh(file)

    assert file.filename == "audit-renamed.csv"
    error_messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "Failed to write dependency file audit event" in error_messages
    assert "dependency-files/internal-key" not in error_messages
