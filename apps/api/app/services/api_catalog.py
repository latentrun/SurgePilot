from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import json
import logging
import re
from typing import Any

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.ids import is_ulid, new_ulid
from app.core.time import utc_now
from app.models.api_catalog import ApiCatalogSpec
from app.services.audit import write_audit_event_in_new_transaction
from app.services.dependency_files import validate_safe_filename_floor
from app.services.storage import PutResult, StorageClient, StoredObjectStream

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".json", ".yaml", ".yml"}
JSON_CONTENT_TYPES = {"application/json", "text/json"}
YAML_CONTENT_TYPES = {
    "application/yaml",
    "application/x-yaml",
    "text/yaml",
    "text/x-yaml",
}
FALLBACK_CONTENT_TYPES = {"", "application/octet-stream"}
DISPLAY_NAME_MAX_LENGTH = 120
DOCUMENT_VERSION_MAX_LENGTH = 80


@dataclass(frozen=True)
class ParsedApiSpec:
    source_format: str
    openapi_version: str
    document_title: str
    document_version: str
    normalized_content_type: str


@dataclass(frozen=True)
class UploadedApiSpec:
    filename: str
    content_type: str | None
    payload: bytes
    name: str | None


def field_error(field: str, message: str, code: str = "INVALID_FIELD") -> dict[str, str]:
    return {"field": field, "code": code, "message": message}


def _validation_error(code: str, message: str, field_code: str) -> AppError:
    return AppError(code, message, 422, [field_error("file", message, field_code)])


def _extension(filename: str) -> str:
    dot_index = filename.rfind(".")
    return filename[dot_index:].lower() if dot_index > 0 else ""


def validate_spec_filename(filename: str | None) -> str:
    safe = validate_safe_filename_floor(filename)
    if _extension(safe) not in ALLOWED_EXTENSIONS:
        raise _validation_error(
            "UNSUPPORTED_API_SPEC_FORMAT",
            "The uploaded file must use a .json, .yaml, or .yml extension.",
            "unsupported_extension",
        )
    return safe


def validate_content_type(content_type: str | None, *, extension: str) -> str:
    value = (content_type or "").split(";", 1)[0].strip().lower()
    allowed = JSON_CONTENT_TYPES if extension == ".json" else YAML_CONTENT_TYPES
    if value in allowed or value in FALLBACK_CONTENT_TYPES:
        if extension == ".json":
            return "application/json"
        return "text/yaml"
    raise _validation_error(
        "UNSUPPORTED_API_SPEC_FORMAT",
        "The uploaded file content type is not supported.",
        "unsupported_content_type",
    )


def _safe_display_text(value: Any, *, max_length: int, fallback: str) -> str:
    if isinstance(value, bool) or value is None:
        return fallback
    if not isinstance(value, str):
        value = str(value)
    compact = re.sub(r"\s+", " ", value).strip()
    if not compact:
        return fallback
    return compact[:max_length]


def _parse_json(payload: bytes) -> Any:
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _validation_error(
            "API_SPEC_PARSE_FAILED",
            "The uploaded API spec could not be parsed.",
            "parse_failed",
        ) from exc


def _parse_yaml(payload: bytes) -> Any:
    try:
        text = payload.decode("utf-8")
        return yaml.safe_load(text)
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise _validation_error(
            "API_SPEC_PARSE_FAILED",
            "The uploaded API spec could not be parsed.",
            "parse_failed",
        ) from exc


def parse_api_spec(payload: bytes, *, filename: str, content_type: str | None) -> ParsedApiSpec:
    if not payload:
        raise _validation_error(
            "API_SPEC_PARSE_FAILED",
            "The uploaded API spec is empty.",
            "empty_file",
        )
    extension = _extension(filename)
    normalized_content_type = validate_content_type(content_type, extension=extension)
    document = _parse_json(payload) if extension == ".json" else _parse_yaml(payload)
    if not isinstance(document, dict):
        raise _validation_error(
            "UNSUPPORTED_API_SPEC_FORMAT",
            "The uploaded file must be an OpenAPI or Swagger document.",
            "missing_openapi_root",
        )

    root_kind: str
    version: Any
    if "openapi" in document:
        root_kind = "openapi"
        version = document.get("openapi")
    elif "swagger" in document:
        root_kind = "swagger"
        version = document.get("swagger")
    else:
        raise _validation_error(
            "UNSUPPORTED_API_SPEC_FORMAT",
            "The uploaded file must be an OpenAPI or Swagger document.",
            "missing_openapi_root",
        )
    if not isinstance(version, str) or not version.strip():
        raise _validation_error(
            "UNSUPPORTED_API_SPEC_FORMAT",
            "The uploaded API spec version is missing or invalid.",
            "invalid_version",
        )
    if root_kind == "openapi" and not version.startswith("3."):
        raise _validation_error(
            "UNSUPPORTED_API_SPEC_FORMAT",
            "Only OpenAPI 3.x and Swagger 2.0 documents are supported.",
            "unsupported_version",
        )
    if root_kind == "swagger" and version.strip() != "2.0":
        raise _validation_error(
            "UNSUPPORTED_API_SPEC_FORMAT",
            "Only OpenAPI 3.x and Swagger 2.0 documents are supported.",
            "unsupported_version",
        )

    info = document.get("info")
    if not isinstance(info, dict):
        raise _validation_error(
            "UNSUPPORTED_API_SPEC_FORMAT",
            "The uploaded API spec must include info metadata.",
            "missing_info",
        )
    title = _safe_display_text(info.get("title"), max_length=DISPLAY_NAME_MAX_LENGTH, fallback="")
    if not title:
        raise _validation_error(
            "UNSUPPORTED_API_SPEC_FORMAT",
            "The uploaded API spec must include info.title.",
            "missing_info_title",
        )
    doc_version = _safe_display_text(
        info.get("version"), max_length=DOCUMENT_VERSION_MAX_LENGTH, fallback="unknown"
    )
    format_suffix = "json" if extension == ".json" else "yaml"
    return ParsedApiSpec(
        source_format=f"{root_kind}_{format_suffix}",
        openapi_version=version.strip()[:DOCUMENT_VERSION_MAX_LENGTH],
        document_title=title,
        document_version=doc_version,
        normalized_content_type=normalized_content_type,
    )


def api_catalog_object_key(*, workspace_id: str, spec_id: str, filename: str) -> str:
    if not is_ulid(workspace_id) or not is_ulid(spec_id):
        raise AppError("VALIDATION_ERROR", "Validation failed.", 422)
    safe_filename = validate_spec_filename(filename)
    return f"api-catalog-specs/{workspace_id}/{spec_id}/{safe_filename}"


def _display_name(upload_name: str | None, parsed: ParsedApiSpec, filename: str) -> str:
    if upload_name is not None:
        trimmed = re.sub(r"\s+", " ", upload_name).strip()
        if not trimmed:
            raise AppError(
                "VALIDATION_ERROR",
                "Validation failed.",
                422,
                [field_error("name", "Name must not be blank.", "blank")],
            )
        return trimmed[:DISPLAY_NAME_MAX_LENGTH]
    return parsed.document_title or filename


def create_api_catalog_spec(
    db: Session,
    *,
    workspace_id: str,
    actor_user_id: str,
    upload: UploadedApiSpec,
    storage: StorageClient,
    bucket: str,
    max_bytes: int,
) -> ApiCatalogSpec:
    filename = validate_spec_filename(upload.filename)
    if len(upload.payload) > max_bytes:
        raise AppError("API_SPEC_TOO_LARGE", "Uploaded API spec is too large.", 413)
    parsed = parse_api_spec(upload.payload, filename=filename, content_type=upload.content_type)
    spec_id = new_ulid()
    object_key = api_catalog_object_key(
        workspace_id=workspace_id, spec_id=spec_id, filename=filename
    )
    result: PutResult = storage.put_stream(
        bucket=bucket,
        object_key=object_key,
        stream=BytesIO(upload.payload),
        size_limit=max_bytes,
        content_type=parsed.normalized_content_type,
    )
    now = utc_now()
    spec = ApiCatalogSpec(
        id=spec_id,
        workspace_id=workspace_id,
        name=_display_name(upload.name, parsed, filename),
        filename=filename,
        content_type=parsed.normalized_content_type,
        source_format=parsed.source_format,
        openapi_version=parsed.openapi_version,
        document_title=parsed.document_title,
        document_version=parsed.document_version,
        size_bytes=result.size_bytes,
        sha256=result.sha256,
        status="available",
        validation_message=None,
        storage_bucket=bucket,
        storage_object_key=object_key,
        created_by=actor_user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(spec)
    try:
        db.flush()
    except Exception:
        storage.delete_object_best_effort(bucket=bucket, object_key=object_key)
        raise
    return spec


def list_api_catalog_specs(
    db: Session, *, workspace_id: str, limit: int, offset: int
) -> tuple[list[ApiCatalogSpec], int]:
    filters = [ApiCatalogSpec.workspace_id == workspace_id, ApiCatalogSpec.status != "deleted"]
    total = db.scalar(select(func.count(ApiCatalogSpec.id)).where(*filters)) or 0
    items = db.scalars(
        select(ApiCatalogSpec)
        .where(*filters)
        .order_by(ApiCatalogSpec.created_at.desc(), ApiCatalogSpec.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(items), total


def get_api_catalog_spec(db: Session, *, workspace_id: str, spec_id: str) -> ApiCatalogSpec:
    spec = db.scalar(
        select(ApiCatalogSpec).where(
            ApiCatalogSpec.id == spec_id,
            ApiCatalogSpec.workspace_id == workspace_id,
            ApiCatalogSpec.status != "deleted",
        )
    )
    if spec is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    return spec


def get_api_catalog_spec_content(
    db: Session,
    *,
    workspace_id: str,
    spec_id: str,
    storage: StorageClient,
) -> tuple[ApiCatalogSpec, StoredObjectStream]:
    spec = get_api_catalog_spec(db, workspace_id=workspace_id, spec_id=spec_id)
    stored = storage.get_stream(
        bucket=spec.storage_bucket,
        object_key=spec.storage_object_key,
    )
    return spec, stored


def delete_api_catalog_spec_metadata(
    db: Session, *, spec: ApiCatalogSpec, actor_user_id: str, storage: StorageClient
) -> None:
    spec.status = "deleted"
    spec.deleted_by = actor_user_id
    spec.deleted_at = utc_now()
    spec.updated_at = spec.deleted_at
    db.flush()
    storage.delete_object_best_effort(
        bucket=spec.storage_bucket, object_key=spec.storage_object_key
    )


def safe_write_api_catalog_audit(
    db: Session,
    *,
    request,
    event_type: str,
    actor_user_id: str,
    workspace_id: str,
    spec: ApiCatalogSpec,
) -> None:
    try:
        write_audit_event_in_new_transaction(
            db.get_bind(),
            event_type=event_type,
            request=request,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            target_type="api_catalog_spec",
            target_id=spec.id,
            details={
                "apiCatalogSpecId": spec.id,
                "workspaceId": workspace_id,
                "filename": spec.filename,
                "sizeBytes": spec.size_bytes,
                "sha256Prefix": spec.sha256[:12],
                "requestId": getattr(request.state, "request_id", ""),
            },
        )
    except Exception:
        logger.error(
            "Failed to write API Catalog audit event",
            extra={
                "event_type": event_type,
                "actor_user_id": actor_user_id,
                "workspace_id": workspace_id,
                "api_catalog_spec_id": spec.id,
                "request_id": getattr(request.state, "request_id", None),
            },
            exc_info=True,
        )
