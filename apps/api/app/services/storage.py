from typing import BinaryIO
from io import BytesIO
import secrets
from dataclasses import dataclass
from urllib.parse import urlparse
import hashlib
import logging

from minio import Minio
from minio.error import MinioException, S3Error

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

DEFAULT_PART_SIZE = 10 * 1024 * 1024


def log_storage_unavailable(operation: str, exc: Exception) -> None:
    logger.warning(
        "Storage operation failed: STORAGE_UNAVAILABLE",
        extra={
            "operation": operation,
            "error_code": "STORAGE_UNAVAILABLE",
            "storage_error_type": type(exc).__name__,
        },
    )


class StorageError(AppError):
    def __init__(self) -> None:
        super().__init__("STORAGE_UNAVAILABLE", "Storage is unavailable.", 503)


@dataclass(frozen=True)
class PutResult:
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class StoredObjectStream:
    content_type: str | None
    size_bytes: int | None
    stream: BinaryIO


class LimitedHashingReader:
    def __init__(self, source: BinaryIO, *, size_limit: int) -> None:
        self._source = source
        self._size_limit = size_limit
        self._hasher = hashlib.sha256()
        self._size_bytes = 0

    @property
    def size_bytes(self) -> int:
        return self._size_bytes

    @property
    def sha256_hex(self) -> str:
        return self._hasher.hexdigest()

    def read(self, size: int = -1) -> bytes:
        chunk = self._source.read(size)
        if not chunk:
            return b""
        self._size_bytes += len(chunk)
        if self._size_bytes > self._size_limit:
            raise AppError("PAYLOAD_TOO_LARGE", "Uploaded file is too large.", 413)
        self._hasher.update(chunk)
        return chunk


class StorageClient:
    def put_stream(
        self,
        *,
        bucket: str,
        object_key: str,
        stream: BinaryIO,
        size_limit: int,
        content_type: str | None = None,
    ) -> PutResult:
        raise NotImplementedError

    def get_stream(self, *, bucket: str, object_key: str) -> StoredObjectStream:
        raise NotImplementedError

    def delete_object_best_effort(self, *, bucket: str, object_key: str) -> bool:
        raise NotImplementedError

    def health_check(self) -> bool:
        raise NotImplementedError


class MinioStorageClient(StorageClient):
    def __init__(self) -> None:
        settings = get_settings()
        parsed = urlparse(settings.minio_endpoint)
        endpoint = parsed.netloc or parsed.path
        secure = settings.minio_secure if parsed.scheme == "" else parsed.scheme == "https"
        self._client = Minio(
            endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=secure,
            region=settings.minio_region or None,
        )

    def put_stream(
        self,
        *,
        bucket: str,
        object_key: str,
        stream: BinaryIO,
        size_limit: int,
        content_type: str | None = None,
    ) -> PutResult:
        reader = LimitedHashingReader(stream, size_limit=size_limit)
        try:
            self._client.put_object(
                bucket,
                object_key,
                reader,
                length=-1,
                part_size=DEFAULT_PART_SIZE,
                content_type=content_type or "application/octet-stream",
            )
        except AppError:
            raise
        except (MinioException, S3Error, OSError) as exc:
            log_storage_unavailable("put_object", exc)
            raise StorageError() from exc
        return PutResult(size_bytes=reader.size_bytes, sha256=reader.sha256_hex)

    def get_stream(self, *, bucket: str, object_key: str) -> StoredObjectStream:
        try:
            response = self._client.get_object(bucket, object_key)
            stat = self._client.stat_object(bucket, object_key)
        except (MinioException, S3Error, OSError) as exc:
            log_storage_unavailable("get_object", exc)
            raise StorageError() from exc
        return StoredObjectStream(
            content_type=getattr(stat, "content_type", None),
            size_bytes=getattr(stat, "size", None),
            stream=response,
        )

    def delete_object_best_effort(self, *, bucket: str, object_key: str) -> bool:
        try:
            self._client.remove_object(bucket, object_key)
            return True
        except (MinioException, S3Error, OSError) as exc:
            log_storage_unavailable("delete_object_best_effort", exc)
            return False

    def health_check(self) -> bool:
        settings = get_settings()
        bucket = settings.minio_bucket
        object_key = f"health/{secrets.token_hex(16)}.txt"
        payload = b"ok"
        try:
            if not self._client.bucket_exists(bucket):
                return False
            self._client.put_object(
                bucket,
                object_key,
                BytesIO(payload),
                length=len(payload),
                part_size=DEFAULT_PART_SIZE,
                content_type="text/plain",
            )
            response = self._client.get_object(bucket, object_key)
            try:
                return response.read() == payload
            finally:
                close = getattr(response, "close", None)
                if callable(close):
                    close()
                release_conn = getattr(response, "release_conn", None)
                if callable(release_conn):
                    release_conn()
        except (MinioException, S3Error, OSError):
            return False
        finally:
            try:
                self._client.remove_object(bucket, object_key)
            except (MinioException, S3Error, OSError):
                pass


_storage_client: StorageClient | None = None


def get_storage_client() -> StorageClient:
    global _storage_client
    if _storage_client is None:
        _storage_client = MinioStorageClient()
    return _storage_client
