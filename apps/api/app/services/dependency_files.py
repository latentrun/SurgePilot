from typing import BinaryIO
import logging
import re

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.ids import is_ulid, new_ulid
from app.core.time import utc_now
from app.models.dependency_files import DependencyFile
from app.models.scenarios import Scenario, ScenarioDependencyFileRef
from app.services.audit import write_audit_event_in_new_transaction
from app.services.storage import PutResult, StorageClient

logger = logging.getLogger(__name__)

SAFE_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,255}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def field_error(field: str, message: str, code: str = "INVALID_FIELD") -> dict[str, str]:
    return {"field": field, "code": code, "message": message}


def validation_error(details: list[dict[str, str]]) -> AppError:
    return AppError("VALIDATION_ERROR", "Validation failed.", 422, details)


def parse_allowed_extensions(raw_value: str) -> list[str]:
    extensions: list[str] = []
    for part in raw_value.split(","):
        value = part.strip().lower()
        if not value:
            continue
        if not value.startswith("."):
            value = f".{value}"
        extensions.append(value)
    return extensions


def _is_sensitive_filename(filename: str) -> bool:
    value = filename.lower()
    exact = {
        ".env",
        ".git",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "known_hosts",
        "authorized_keys",
        "private.key",
        "private.pem",
    }
    prefixes = (".env.", ".git", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")
    return (
        value in exact
        or value.startswith(prefixes)
        or value.endswith(".private.key")
        or value.endswith(".private.pem")
    )


def validate_safe_filename_floor(filename: str | None) -> str:
    if filename is None or not SAFE_FILENAME_PATTERN.fullmatch(filename):
        raise AppError("INVALID_FILENAME", "Filename is invalid.", 400)
    if filename in {".", ".."}:
        raise AppError("INVALID_FILENAME", "Filename is invalid.", 400)
    return filename


def validate_dependency_filename(filename: str | None, *, allowed_extensions: list[str]) -> str:
    safe = validate_safe_filename_floor(filename)
    if _is_sensitive_filename(safe):
        raise AppError("INVALID_FILENAME", "Filename is invalid.", 400)
    if allowed_extensions:
        dot_index = safe.rfind(".")
        extension = safe[dot_index:].lower() if dot_index > 0 else ""
        if extension not in allowed_extensions:
            raise validation_error(
                [
                    field_error(
                        "file",
                        "File extension is not allowed.",
                        "UNSUPPORTED_FILE_EXTENSION",
                    )
                ]
            )
    return safe


def dependency_file_object_key(*, workspace_id: str, dependency_file_id: str, filename: str) -> str:
    if not is_ulid(workspace_id) or not is_ulid(dependency_file_id):
        raise AppError("VALIDATION_ERROR", "Validation failed.", 422)
    safe_filename = validate_safe_filename_floor(filename)
    return f"dependency-files/{workspace_id}/{dependency_file_id}/{safe_filename}"


def _raise_name_conflict() -> None:
    raise AppError("DEPENDENCY_FILE_NAME_CONFLICT", "Dependency File filename already exists.", 409)


def ensure_filename_available(
    db: Session, *, workspace_id: str, filename: str, exclude_dependency_file_id: str | None = None
) -> None:
    statement = select(DependencyFile.id).where(
        DependencyFile.workspace_id == workspace_id,
        DependencyFile.status == "available",
        func.lower(DependencyFile.filename) == filename.lower(),
    )
    if exclude_dependency_file_id is not None:
        statement = statement.where(DependencyFile.id != exclude_dependency_file_id)
    if db.scalar(statement) is not None:
        _raise_name_conflict()


class DependencyFileReferenceChecker:
    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def is_in_use(self, dependency_file_id: str) -> bool:
        if self.db is None:
            return False
        return (
            self.db.scalar(
                select(ScenarioDependencyFileRef.id)
                .join(Scenario, Scenario.id == ScenarioDependencyFileRef.scenario_id)
                .where(
                    ScenarioDependencyFileRef.dependency_file_id == dependency_file_id,
                    Scenario.deleted_at.is_(None),
                )
                .limit(1)
            )
            is not None
        )


def create_dependency_file_metadata(
    db: Session,
    *,
    workspace_id: str,
    actor_user_id: str,
    filename: str,
    content_type: str | None,
    size_bytes: int,
    sha256: str,
    storage_bucket: str,
    storage_object_key: str,
    dependency_file_id: str | None = None,
) -> DependencyFile:
    if not SHA256_PATTERN.fullmatch(sha256):
        raise validation_error([field_error("file", "SHA-256 is invalid.")])
    ensure_filename_available(db, workspace_id=workspace_id, filename=filename)
    now = utc_now()
    file = DependencyFile(
        id=dependency_file_id or new_ulid(),
        workspace_id=workspace_id,
        filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=sha256,
        storage_bucket=storage_bucket,
        storage_object_key=storage_object_key,
        status="available",
        created_by=actor_user_id,
        created_at=now,
    )
    db.add(file)
    try:
        db.flush()
    except IntegrityError as exc:
        raise _raise_name_conflict() from exc
    return file


def get_dependency_file(
    db: Session, *, workspace_id: str, dependency_file_id: str
) -> DependencyFile:
    file = db.scalar(
        select(DependencyFile).where(
            DependencyFile.id == dependency_file_id,
            DependencyFile.workspace_id == workspace_id,
            DependencyFile.status == "available",
        )
    )
    if file is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    return file


def delete_dependency_file_metadata(
    db: Session,
    *,
    file: DependencyFile,
    actor_user_id: str,
    reference_checker: DependencyFileReferenceChecker | None = None,
) -> None:
    checker = reference_checker or DependencyFileReferenceChecker(db)
    if checker.is_in_use(file.id):
        raise AppError("FILE_IN_USE", "Dependency File is in use and cannot be deleted.", 409)
    file.status = "deleted"
    file.deleted_by = actor_user_id
    file.deleted_at = utc_now()
    db.flush()


def upload_dependency_file(
    db: Session,
    *,
    workspace_id: str,
    actor_user_id: str,
    filename: str,
    content_type: str | None,
    source: BinaryIO,
    storage: StorageClient,
    bucket: str,
    max_bytes: int,
    allowed_extensions: list[str],
) -> DependencyFile:
    safe_filename = validate_dependency_filename(filename, allowed_extensions=allowed_extensions)
    ensure_filename_available(db, workspace_id=workspace_id, filename=safe_filename)
    dependency_file_id = new_ulid()
    object_key = dependency_file_object_key(
        workspace_id=workspace_id, dependency_file_id=dependency_file_id, filename=safe_filename
    )
    result: PutResult = storage.put_stream(
        bucket=bucket,
        object_key=object_key,
        stream=source,
        size_limit=max_bytes,
        content_type=content_type,
    )
    try:
        return create_dependency_file_metadata(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            filename=safe_filename,
            content_type=content_type,
            size_bytes=result.size_bytes,
            sha256=result.sha256,
            storage_bucket=bucket,
            storage_object_key=object_key,
            dependency_file_id=dependency_file_id,
        )
    except Exception:
        storage.delete_object_best_effort(bucket=bucket, object_key=object_key)
        raise


def audit_details_for_upload(
    *,
    dependency_file_id: str,
    workspace_id: str,
    filename: str,
    size_bytes: int,
    sha256: str,
    request_id: str,
) -> dict[str, object]:
    return {
        "dependencyFileId": dependency_file_id,
        "workspaceId": workspace_id,
        "filename": filename,
        "sizeBytes": size_bytes,
        "sha256": sha256,
        "requestId": request_id,
    }


def safe_write_dependency_file_audit(
    db: Session,
    *,
    request: Request,
    event_type: str,
    actor_user_id: str,
    workspace_id: str,
    file: DependencyFile,
    details: dict[str, object],
) -> None:
    try:
        write_audit_event_in_new_transaction(
            db.get_bind(),
            event_type=event_type,
            request=request,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            target_type="dependency_file",
            target_id=file.id,
            details=details,
        )
    except Exception:
        logger.error(
            "Failed to write dependency file audit event",
            extra={
                "event_type": event_type,
                "actor_user_id": actor_user_id,
                "workspace_id": workspace_id,
                "dependency_file_id": file.id,
                "request_id": getattr(request.state, "request_id", None),
            },
            exc_info=True,
        )
