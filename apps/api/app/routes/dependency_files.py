from collections.abc import Iterator

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.api.deps import CsrfDep, CurrentUserDep, CurrentWorkspaceDep, DbDep
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ids import is_ulid
from app.models.dependency_files import DependencyFile
from app.schemas.common import ErrorResponse
from app.schemas.dependency_files import (
    DependencyFileDetail,
    DependencyFileListResponse,
    DependencyFileSummary,
)
from app.services.dependency_files import (
    DependencyFileReferenceChecker,
    audit_details_for_upload,
    delete_dependency_file_metadata,
    get_dependency_file,
    safe_write_dependency_file_audit,
    upload_dependency_file,
)
from app.services.system_settings import dependency_file_policy
from app.services.storage import StoredObjectStream, get_storage_client

router = APIRouter(prefix="/api/v1/dependency-files", tags=["dependency-files"])

ERROR_RESPONSE = {"model": ErrorResponse}
MULTIPART_CONTENT_LENGTH_OVERHEAD = 1024 * 1024
ALLOWED_LIST_QUERY_PARAMS = {"page", "pageSize", "q", "sort"}
ALLOWED_SORTS = {"filename", "createdAt", "-createdAt", "sizeBytes", "-sizeBytes"}
LIST_QUERY_OPENAPI_PARAMETERS = [
    {
        "name": "page",
        "in": "query",
        "required": False,
        "schema": {"type": "integer", "minimum": 1, "default": 1},
    },
    {
        "name": "pageSize",
        "in": "query",
        "required": False,
        "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
    },
    {
        "name": "q",
        "in": "query",
        "required": False,
        "schema": {"anyOf": [{"type": "string", "maxLength": 120}, {"type": "null"}]},
    },
    {
        "name": "sort",
        "in": "query",
        "required": False,
        "schema": {"type": "string", "default": "-createdAt"},
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


INVALID_FILENAME_RESPONSE = error_example_response(
    "Invalid Dependency File filename.", "INVALID_FILENAME", "Filename is invalid."
)
NAME_CONFLICT_RESPONSE = error_example_response(
    "Active Dependency File filename already exists in this Workspace.",
    "DEPENDENCY_FILE_NAME_CONFLICT",
    "Dependency File filename already exists.",
)
PAYLOAD_TOO_LARGE_RESPONSE = error_example_response(
    "Uploaded Dependency File exceeds the configured size limit.",
    "PAYLOAD_TOO_LARGE",
    "Uploaded file is too large.",
)
STORAGE_UNAVAILABLE_RESPONSE = error_example_response(
    "MinIO storage is unavailable or the configured bucket is inaccessible.",
    "STORAGE_UNAVAILABLE",
    "Storage is unavailable.",
)
FILE_IN_USE_RESPONSE = error_example_response(
    "Dependency File is referenced and cannot be deleted.",
    "FILE_IN_USE",
    "Dependency File is in use and cannot be deleted.",
)


def iso_z(value) -> str:
    return value.isoformat().replace("+00:00", "Z")


def attach_workspace_header(response: Response, workspace_id: str) -> None:
    response.headers["x-workspace-id"] = workspace_id


def validate_dependency_file_id(dependency_file_id: str) -> None:
    if not is_ulid(dependency_file_id):
        raise AppError(
            "VALIDATION_ERROR",
            "Validation failed.",
            422,
            [
                {
                    "field": "dependencyFileId",
                    "code": "INVALID_FIELD",
                    "message": "Invalid Dependency File ID.",
                }
            ],
        )


def summary_response(
    file: DependencyFile, reference_checker: DependencyFileReferenceChecker | None = None
) -> DependencyFileSummary:
    in_use = reference_checker.is_in_use(file.id) if reference_checker is not None else False
    return DependencyFileSummary(
        id=file.id,
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=file.size_bytes,
        sha256=file.sha256,
        in_use=in_use,
        created_by=file.created_by,
        created_at=iso_z(file.created_at),
    )


def detail_response(
    file: DependencyFile, reference_checker: DependencyFileReferenceChecker | None = None
) -> DependencyFileDetail:
    return DependencyFileDetail(**summary_response(file, reference_checker).model_dump())


def invalid_query(field: str, message: str) -> AppError:
    return AppError(
        "INVALID_QUERY_PARAMETER",
        "Invalid query parameter.",
        400,
        [{"field": field, "code": "INVALID_QUERY_PARAMETER", "message": message}],
    )


def parse_list_int(
    raw_value: str | None, *, field: str, default: int, max_value: int | None = None
) -> int:
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise invalid_query(field, f"{field} must be an integer.") from exc
    if value < 1:
        raise invalid_query(field, f"{field} must be greater than or equal to 1.")
    if max_value is not None and value > max_value:
        raise invalid_query(field, f"{field} must be less than or equal to {max_value}.")
    return value


def parse_list_query(request: Request) -> tuple[int, int, str | None, str]:
    unknown_params = set(request.query_params) - ALLOWED_LIST_QUERY_PARAMS
    if unknown_params:
        raise invalid_query(sorted(unknown_params)[0], "Unknown query parameter.")

    page = parse_list_int(request.query_params.get("page"), field="page", default=1)
    page_size = parse_list_int(
        request.query_params.get("pageSize"), field="pageSize", default=20, max_value=100
    )
    q = request.query_params.get("q")
    trimmed_q = q.strip() if q is not None else None
    if trimmed_q is not None and len(trimmed_q) > 120:
        raise invalid_query("q", "q must be 120 characters or less.")
    sort = request.query_params.get("sort", "-createdAt")
    if sort not in ALLOWED_SORTS:
        raise invalid_query("sort", "Unsupported sort parameter.")
    return page, page_size, trimmed_q, sort


async def single_upload_file(request: Request, *, max_bytes: int) -> StarletteUploadFile:
    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith("multipart/form-data"):
        raise AppError("UNSUPPORTED_MEDIA_TYPE", "Request content type is unsupported.", 415)
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            parsed_content_length = int(content_length)
        except ValueError as exc:
            raise AppError("INVALID_REQUEST", "Content length is invalid.", 400) from exc
        max_request_bytes = max_bytes + MULTIPART_CONTENT_LENGTH_OVERHEAD
        if parsed_content_length > max_request_bytes:
            raise AppError("PAYLOAD_TOO_LARGE", "Uploaded file is too large.", 413)
    try:
        form = await request.form()
    except Exception as exc:
        raise AppError("INVALID_REQUEST", "Multipart request is invalid.", 400) from exc
    unexpected_fields = [key for key, _value in form.multi_items() if key != "file"]
    if unexpected_fields:
        raise AppError("INVALID_REQUEST", "Multipart request contains unsupported fields.", 400)
    files = [value for key, value in form.multi_items() if key == "file"]
    if len(files) != 1 or not isinstance(files[0], StarletteUploadFile):
        raise AppError("INVALID_REQUEST", "A single file part is required.", 400)
    upload = files[0]
    if upload.filename is None:
        raise AppError("INVALID_REQUEST", "Filename is required.", 400)
    return upload


@router.get(
    "",
    operation_id="listDependencyFiles",
    response_model=DependencyFileListResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE},
    openapi_extra={"parameters": LIST_QUERY_OPENAPI_PARAMETERS},
)
def list_dependency_files(
    request: Request,
    response: Response,
    db: DbDep,
    workspace: CurrentWorkspaceDep,
) -> DependencyFileListResponse:
    page, page_size, q, sort = parse_list_query(request)
    attach_workspace_header(response, workspace.id)
    filters = [DependencyFile.workspace_id == workspace.id, DependencyFile.status == "available"]
    statement = select(DependencyFile).where(*filters)
    count_statement = select(func.count(DependencyFile.id)).where(*filters)
    if q:
        pattern = f"%{q.lower()}%"
        statement = statement.where(func.lower(DependencyFile.filename).like(pattern))
        count_statement = count_statement.where(func.lower(DependencyFile.filename).like(pattern))

    if sort == "filename":
        statement = statement.order_by(
            func.lower(DependencyFile.filename).asc(), DependencyFile.id.asc()
        )
    elif sort == "createdAt":
        statement = statement.order_by(DependencyFile.created_at.asc(), DependencyFile.id.asc())
    elif sort == "sizeBytes":
        statement = statement.order_by(DependencyFile.size_bytes.asc(), DependencyFile.id.asc())
    elif sort == "-sizeBytes":
        statement = statement.order_by(DependencyFile.size_bytes.desc(), DependencyFile.id.desc())
    else:
        statement = statement.order_by(DependencyFile.created_at.desc(), DependencyFile.id.desc())

    total = db.scalar(count_statement) or 0
    files = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    db.commit()
    reference_checker = DependencyFileReferenceChecker(db)
    return DependencyFileListResponse(
        items=[summary_response(file, reference_checker) for file in files],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    operation_id="uploadDependencyFile",
    response_model=DependencyFileDetail,
    response_model_by_alias=True,
    responses={
        400: INVALID_FILENAME_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        409: NAME_CONFLICT_RESPONSE,
        413: PAYLOAD_TOO_LARGE_RESPONSE,
        415: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
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
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                }
            },
        }
    },
)
async def upload_dependency_file_route(
    request: Request,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> DependencyFileDetail:
    policy = dependency_file_policy(db)
    upload = await single_upload_file(request, max_bytes=policy.max_bytes)
    settings = get_settings()
    file = upload_dependency_file(
        db,
        workspace_id=workspace.id,
        actor_user_id=user.id,
        filename=upload.filename or "",
        content_type=upload.content_type,
        source=upload.file,
        storage=get_storage_client(),
        bucket=settings.minio_bucket,
        max_bytes=policy.max_bytes,
        allowed_extensions=policy.allowed_extensions,
    )
    db.commit()
    safe_write_dependency_file_audit(
        db,
        request=request,
        event_type="dependency_file.uploaded",
        actor_user_id=user.id,
        workspace_id=workspace.id,
        file=file,
        details=audit_details_for_upload(
            dependency_file_id=file.id,
            workspace_id=workspace.id,
            filename=file.filename,
            size_bytes=file.size_bytes,
            sha256=file.sha256,
            request_id=getattr(request.state, "request_id", ""),
        ),
    )
    attach_workspace_header(response, workspace.id)
    return detail_response(file, DependencyFileReferenceChecker(db))


@router.get(
    "/{dependencyFileId}",
    operation_id="getDependencyFile",
    response_model=DependencyFileDetail,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def get_dependency_file_route(
    dependencyFileId: str,
    response: Response,
    db: DbDep,
    workspace: CurrentWorkspaceDep,
) -> DependencyFileDetail:
    validate_dependency_file_id(dependencyFileId)
    attach_workspace_header(response, workspace.id)
    file = get_dependency_file(db, workspace_id=workspace.id, dependency_file_id=dependencyFileId)
    db.commit()
    return detail_response(file, DependencyFileReferenceChecker(db))


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


@router.get(
    "/{dependencyFileId}/download",
    operation_id="downloadDependencyFile",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Dependency File bytes.",
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
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
def download_dependency_file_route(
    dependencyFileId: str,
    request: Request,
    db: DbDep,
    workspace: CurrentWorkspaceDep,
    user: CurrentUserDep,
) -> StreamingResponse:
    validate_dependency_file_id(dependencyFileId)
    file = get_dependency_file(db, workspace_id=workspace.id, dependency_file_id=dependencyFileId)
    stored = get_storage_client().get_stream(
        bucket=file.storage_bucket, object_key=file.storage_object_key
    )
    db.commit()
    safe_write_dependency_file_audit(
        db,
        request=request,
        event_type="dependency_file.downloaded",
        actor_user_id=user.id,
        workspace_id=workspace.id,
        file=file,
        details={
            "dependencyFileId": file.id,
            "workspaceId": workspace.id,
            "filename": file.filename,
            "sizeBytes": file.size_bytes,
            "requestId": getattr(request.state, "request_id", ""),
        },
    )
    return StreamingResponse(
        stream_iterator(stored),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{file.filename}"',
            "Cache-Control": "private, no-store",
            "x-workspace-id": workspace.id,
        },
    )


@router.delete(
    "/{dependencyFileId}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteDependencyFile",
    response_model=None,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: FILE_IN_USE_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def delete_dependency_file_route(
    dependencyFileId: str,
    request: Request,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> Response:
    validate_dependency_file_id(dependencyFileId)
    file = get_dependency_file(db, workspace_id=workspace.id, dependency_file_id=dependencyFileId)
    delete_dependency_file_metadata(db, file=file, actor_user_id=user.id)
    db.commit()
    safe_write_dependency_file_audit(
        db,
        request=request,
        event_type="dependency_file.deleted",
        actor_user_id=user.id,
        workspace_id=workspace.id,
        file=file,
        details={
            "dependencyFileId": file.id,
            "workspaceId": workspace.id,
            "filename": file.filename,
            "requestId": getattr(request.state, "request_id", ""),
        },
    )
    return Response(
        status_code=status.HTTP_204_NO_CONTENT, headers={"x-workspace-id": workspace.id}
    )
