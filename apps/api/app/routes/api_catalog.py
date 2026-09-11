from collections.abc import Iterator

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.api.deps import CsrfDep, CurrentUserDep, CurrentWorkspaceDep, DbDep
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ids import is_ulid
from app.models.api_catalog import ApiCatalogSpec
from app.schemas.api_catalog import (
    ApiCatalogSpecListResponse,
    ApiCatalogSpecResponse,
    ApiCatalogSpecSummary,
)
from app.schemas.common import ErrorResponse
from app.services.api_catalog import (
    UploadedApiSpec,
    create_api_catalog_spec,
    delete_api_catalog_spec_metadata,
    get_api_catalog_spec,
    list_api_catalog_specs,
    safe_write_api_catalog_audit,
)
from app.services.storage import StoredObjectStream, get_storage_client

router = APIRouter(prefix="/api/v1/api-catalog/specs", tags=["api-catalog"])

ERROR_RESPONSE = {"model": ErrorResponse}
MULTIPART_CONTENT_LENGTH_OVERHEAD = 1024 * 1024
UPLOAD_READ_CHUNK_SIZE = 1024 * 1024
ALLOWED_LIST_QUERY_PARAMS = {"limit", "offset"}
LIST_QUERY_OPENAPI_PARAMETERS = [
    {
        "name": "limit",
        "in": "query",
        "required": False,
        "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
    },
    {
        "name": "offset",
        "in": "query",
        "required": False,
        "schema": {"type": "integer", "minimum": 0, "default": 0},
    },
]


def error_example_response(description: str, code: str, message: str) -> dict:
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json": {
                "example": {"code": code, "message": message, "requestId": "req_example"}
            }
        },
    }


API_SPEC_TOO_LARGE_RESPONSE = error_example_response(
    "Uploaded API spec exceeds the configured size limit.",
    "API_SPEC_TOO_LARGE",
    "Uploaded API spec is too large.",
)
API_SPEC_PARSE_FAILED_RESPONSE = error_example_response(
    "Uploaded API spec cannot be parsed safely.",
    "API_SPEC_PARSE_FAILED",
    "The uploaded API spec could not be parsed.",
)
UNSUPPORTED_API_SPEC_FORMAT_RESPONSE = error_example_response(
    "Uploaded file is not a supported OpenAPI or Swagger document.",
    "UNSUPPORTED_API_SPEC_FORMAT",
    "The uploaded file must be an OpenAPI or Swagger document.",
)
STORAGE_UNAVAILABLE_RESPONSE = error_example_response(
    "MinIO storage is unavailable or the configured bucket is inaccessible.",
    "STORAGE_UNAVAILABLE",
    "Storage is unavailable.",
)


def iso_z(value) -> str:
    return value.isoformat().replace("+00:00", "Z")


def attach_workspace_header(response: Response, workspace_id: str) -> None:
    response.headers["x-workspace-id"] = workspace_id


def validate_spec_id(spec_id: str) -> None:
    if not is_ulid(spec_id):
        raise AppError(
            "VALIDATION_ERROR",
            "Validation failed.",
            422,
            [
                {
                    "field": "specId",
                    "code": "INVALID_FIELD",
                    "message": "Invalid API Catalog spec ID.",
                }
            ],
        )


def spec_content_url(spec_id: str) -> str:
    return f"/api/v1/api-catalog/specs/{spec_id}/content"


def summary_response(spec: ApiCatalogSpec) -> ApiCatalogSpecSummary:
    return ApiCatalogSpecSummary(
        id=spec.id,
        name=spec.name,
        filename=spec.filename,
        source_format=spec.source_format,
        document_title=spec.document_title,
        document_version=spec.document_version,
        size_bytes=spec.size_bytes,
        sha256=spec.sha256,
        status=spec.status,
        created_at=iso_z(spec.created_at),
        updated_at=iso_z(spec.updated_at),
    )


def detail_response(spec: ApiCatalogSpec) -> ApiCatalogSpecResponse:
    return ApiCatalogSpecResponse(
        **summary_response(spec).model_dump(),
        openapi_version=spec.openapi_version,
        content_url=spec_content_url(spec.id),
        validation_message=spec.validation_message,
    )


def upload_validation_error(field: str, message: str, code: str) -> AppError:
    return AppError(
        "VALIDATION_ERROR",
        "Validation failed.",
        422,
        [{"field": field, "code": code, "message": message}],
    )


def invalid_query(field: str, message: str) -> AppError:
    return AppError(
        "INVALID_QUERY_PARAMETER",
        "Invalid query parameter.",
        400,
        [{"field": field, "code": "INVALID_QUERY_PARAMETER", "message": message}],
    )


def parse_int_query(
    raw_value: str | None, *, field: str, default: int, min_value: int, max_value: int
) -> int:
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise invalid_query(field, f"{field} must be an integer.") from exc
    if value < min_value:
        raise invalid_query(field, f"{field} must be greater than or equal to {min_value}.")
    if value > max_value:
        raise invalid_query(field, f"{field} must be less than or equal to {max_value}.")
    return value


def parse_list_query(request: Request) -> tuple[int, int]:
    unknown_params = set(request.query_params) - ALLOWED_LIST_QUERY_PARAMS
    if unknown_params:
        raise invalid_query(sorted(unknown_params)[0], "Unknown query parameter.")
    limit = parse_int_query(
        request.query_params.get("limit"), field="limit", default=50, min_value=1, max_value=100
    )
    offset = parse_int_query(
        request.query_params.get("offset"),
        field="offset",
        default=0,
        min_value=0,
        max_value=100_000,
    )
    return limit, offset


async def read_upload_payload(upload: StarletteUploadFile, *, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(UPLOAD_READ_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise AppError("API_SPEC_TOO_LARGE", "Uploaded API spec is too large.", 413)
        chunks.append(chunk)
    return b"".join(chunks)


async def parse_upload_form(request: Request, *, max_bytes: int) -> UploadedApiSpec:
    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith("multipart/form-data"):
        raise AppError("UNSUPPORTED_MEDIA_TYPE", "Request content type is unsupported.", 415)
    content_length = request.headers.get("content-length")
    if content_length is None:
        raise AppError("INVALID_REQUEST", "Content length is required for API spec upload.", 400)
    try:
        parsed_content_length = int(content_length)
    except ValueError as exc:
        raise AppError("INVALID_REQUEST", "Content length is invalid.", 400) from exc
    if parsed_content_length > max_bytes + MULTIPART_CONTENT_LENGTH_OVERHEAD:
        raise AppError("API_SPEC_TOO_LARGE", "Uploaded API spec is too large.", 413)
    try:
        form = await request.form(max_files=2, max_fields=2)
    except Exception as exc:
        raise AppError("INVALID_REQUEST", "Multipart request is invalid.", 400) from exc
    unsupported = [key for key, _value in form.multi_items() if key not in {"file", "name"}]
    if unsupported:
        raise upload_validation_error(
            sorted(unsupported)[0],
            "Multipart request contains unsupported fields.",
            "unsupported_field",
        )
    files = [value for key, value in form.multi_items() if key == "file"]
    if len(files) != 1 or not isinstance(files[0], StarletteUploadFile):
        raise upload_validation_error(
            "file", "A single file part is required.", "single_file_required"
        )
    names = [value for key, value in form.multi_items() if key == "name"]
    if len(names) > 1 or any(isinstance(value, StarletteUploadFile) for value in names):
        raise upload_validation_error(
            "name", "A single text name field is allowed.", "single_name_required"
        )
    upload = files[0]
    payload = await read_upload_payload(upload, max_bytes=max_bytes)
    return UploadedApiSpec(
        filename=upload.filename or "",
        content_type=upload.content_type,
        payload=payload,
        name=str(names[0]) if names else None,
    )


@router.get(
    "",
    operation_id="listApiCatalogSpecs",
    response_model=ApiCatalogSpecListResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE},
    openapi_extra={"parameters": LIST_QUERY_OPENAPI_PARAMETERS},
)
def list_api_catalog_specs_route(
    request: Request,
    response: Response,
    db: DbDep,
    workspace: CurrentWorkspaceDep,
) -> ApiCatalogSpecListResponse:
    limit, offset = parse_list_query(request)
    items, total = list_api_catalog_specs(db, workspace_id=workspace.id, limit=limit, offset=offset)
    db.commit()
    attach_workspace_header(response, workspace.id)
    return ApiCatalogSpecListResponse(
        items=[summary_response(spec) for spec in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    operation_id="uploadApiCatalogSpec",
    response_model=ApiCatalogSpecResponse,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        413: API_SPEC_TOO_LARGE_RESPONSE,
        415: ERROR_RESPONSE,
        422: {
            **ERROR_RESPONSE,
            "content": {
                "application/json": {
                    "examples": {
                        "parseFailed": {
                            "value": {
                                "code": "API_SPEC_PARSE_FAILED",
                                "message": "The uploaded API spec could not be parsed.",
                                "requestId": "req_example",
                            }
                        },
                        "unsupportedFormat": {
                            "value": {
                                "code": "UNSUPPORTED_API_SPEC_FORMAT",
                                "message": "The uploaded file must be an OpenAPI or Swagger document.",
                                "requestId": "req_example",
                            }
                        },
                    }
                }
            },
        },
        503: STORAGE_UNAVAILABLE_RESPONSE,
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "properties": {
                            "file": {"type": "string", "format": "binary"},
                            "name": {"type": "string", "maxLength": 120},
                        },
                    }
                }
            },
        }
    },
)
async def upload_api_catalog_spec_route(
    request: Request,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> ApiCatalogSpecResponse:
    settings = get_settings()
    upload = await parse_upload_form(request, max_bytes=settings.api_catalog_spec_max_bytes)
    spec = create_api_catalog_spec(
        db,
        workspace_id=workspace.id,
        actor_user_id=user.id,
        upload=upload,
        storage=get_storage_client(),
        bucket=settings.minio_bucket,
        max_bytes=settings.api_catalog_spec_max_bytes,
    )
    db.commit()
    safe_write_api_catalog_audit(
        db,
        request=request,
        event_type="api_catalog_spec.uploaded",
        actor_user_id=user.id,
        workspace_id=workspace.id,
        spec=spec,
    )
    attach_workspace_header(response, workspace.id)
    return detail_response(spec)


@router.get(
    "/{specId}",
    operation_id="getApiCatalogSpec",
    response_model=ApiCatalogSpecResponse,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def get_api_catalog_spec_route(
    specId: str,
    response: Response,
    db: DbDep,
    workspace: CurrentWorkspaceDep,
) -> ApiCatalogSpecResponse:
    validate_spec_id(specId)
    spec = get_api_catalog_spec(db, workspace_id=workspace.id, spec_id=specId)
    db.commit()
    attach_workspace_header(response, workspace.id)
    return detail_response(spec)


def stream_iterator(stored: StoredObjectStream) -> Iterator[bytes]:
    try:
        while True:
            chunk = stored.stream.read(1024 * 1024)
            if not chunk:
                break
            yield chunk
    finally:
        close = getattr(stored.stream, "close", None)
        if callable(close):
            close()
        release_conn = getattr(stored.stream, "release_conn", None)
        if callable(release_conn):
            release_conn()


@router.get(
    "/{specId}/content",
    operation_id="getApiCatalogSpecContent",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Authorized OpenAPI or Swagger spec content.",
            "content": {
                "application/json": {"schema": {"type": "object"}},
                "text/yaml": {"schema": {"type": "string"}},
                "application/yaml": {"schema": {"type": "string"}},
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}},
            },
        },
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
        503: STORAGE_UNAVAILABLE_RESPONSE,
    },
)
def get_api_catalog_spec_content_route(
    specId: str,
    db: DbDep,
    workspace: CurrentWorkspaceDep,
) -> StreamingResponse:
    validate_spec_id(specId)
    spec = get_api_catalog_spec(db, workspace_id=workspace.id, spec_id=specId)
    stored = get_storage_client().get_stream(
        bucket=spec.storage_bucket, object_key=spec.storage_object_key
    )
    db.commit()
    media_type = spec.content_type or stored.content_type or "application/octet-stream"
    return StreamingResponse(
        stream_iterator(stored),
        media_type=media_type,
        headers={"Cache-Control": "private, no-store", "x-workspace-id": workspace.id},
    )


@router.delete(
    "/{specId}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteApiCatalogSpec",
    response_model=None,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def delete_api_catalog_spec_route(
    specId: str,
    request: Request,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> Response:
    validate_spec_id(specId)
    spec = get_api_catalog_spec(db, workspace_id=workspace.id, spec_id=specId)
    delete_api_catalog_spec_metadata(
        db, spec=spec, actor_user_id=user.id, storage=get_storage_client()
    )
    db.commit()
    safe_write_api_catalog_audit(
        db,
        request=request,
        event_type="api_catalog_spec.deleted",
        actor_user_id=user.id,
        workspace_id=workspace.id,
        spec=spec,
    )
    return Response(
        status_code=status.HTTP_204_NO_CONTENT, headers={"x-workspace-id": workspace.id}
    )
