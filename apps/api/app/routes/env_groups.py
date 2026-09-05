from typing import Any

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import func, select

from app.api.deps import CsrfDep, CurrentUserDep, CurrentWorkspaceDep, DbDep
from app.core.errors import AppError
from app.core.ids import is_ulid
from app.models.env_groups import EnvGroup
from app.schemas.common import ErrorResponse
from app.schemas.env_groups import (
    EnvGroupCreateRequest,
    EnvGroupDetail,
    EnvGroupListResponse,
    EnvGroupPatchRequest,
    EnvGroupSummary,
)
from app.services.env_groups import (
    EnvGroupReferenceChecker,
    create_env_group,
    delete_env_group,
    duplicate_env_group,
    get_env_group,
    update_env_group,
)

router = APIRouter(prefix="/api/v1/env-groups", tags=["env-groups"])

ERROR_RESPONSE = {"model": ErrorResponse}
ALLOWED_LIST_QUERY_PARAMS = {"page", "pageSize", "q", "sort"}
ALLOWED_SORTS = {"name", "createdAt", "-createdAt"}
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


def iso_z(value) -> str:
    return value.isoformat().replace("+00:00", "Z")


def validate_env_group_id(env_group_id: str) -> None:
    if not is_ulid(env_group_id):
        raise AppError(
            "VALIDATION_ERROR",
            "Validation failed.",
            422,
            [{"field": "envGroupId", "code": "INVALID_FIELD", "message": "Invalid Env Group ID."}],
        )


def attach_workspace_header(response: Response, workspace_id: str) -> None:
    response.headers["x-workspace-id"] = workspace_id


def summary_response(
    group: EnvGroup, reference_checker: EnvGroupReferenceChecker | None = None
) -> EnvGroupSummary:
    return EnvGroupSummary(
        id=group.id,
        name=group.name,
        description=group.description,
        variable_count=len(group.variables),
        in_use=reference_checker.is_in_use(group.id) if reference_checker else False,
        created_by=group.created_by,
        updated_by=group.updated_by,
        created_at=iso_z(group.created_at),
        updated_at=iso_z(group.updated_at),
    )


def detail_response(
    group: EnvGroup, reference_checker: EnvGroupReferenceChecker | None = None
) -> EnvGroupDetail:
    return EnvGroupDetail(
        **summary_response(group, reference_checker).model_dump(),
        variables=dict(group.variables or {}),
    )


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


@router.get(
    "",
    operation_id="listEnvGroups",
    response_model=EnvGroupListResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE},
    openapi_extra={"parameters": LIST_QUERY_OPENAPI_PARAMETERS},
)
def list_env_groups(
    request: Request,
    response: Response,
    db: DbDep,
    workspace: CurrentWorkspaceDep,
) -> EnvGroupListResponse:
    page, page_size, q, sort = parse_list_query(request)
    attach_workspace_header(response, workspace.id)
    statement = select(EnvGroup).where(EnvGroup.workspace_id == workspace.id)
    count_statement = select(func.count(EnvGroup.id)).where(EnvGroup.workspace_id == workspace.id)
    if q:
        pattern = f"%{q.lower()}%"
        statement = statement.where(func.lower(EnvGroup.name).like(pattern))
        count_statement = count_statement.where(func.lower(EnvGroup.name).like(pattern))

    if sort == "name":
        statement = statement.order_by(func.lower(EnvGroup.name).asc(), EnvGroup.id.asc())
    elif sort == "createdAt":
        statement = statement.order_by(EnvGroup.created_at.asc(), EnvGroup.id.asc())
    else:
        statement = statement.order_by(EnvGroup.created_at.desc(), EnvGroup.id.desc())

    total = db.scalar(count_statement) or 0
    groups = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    db.commit()
    reference_checker = EnvGroupReferenceChecker(db, workspace_id=workspace.id)
    return EnvGroupListResponse(
        items=[summary_response(group, reference_checker) for group in groups],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    operation_id="createEnvGroup",
    response_model=EnvGroupDetail,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def create_env_group_route(
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
    payload: EnvGroupCreateRequest,
) -> EnvGroupDetail:
    attach_workspace_header(response, workspace.id)
    group = create_env_group(
        db,
        workspace_id=workspace.id,
        actor_user_id=user.id,
        name=payload.name,
        description=payload.description,
        variables=payload.variables,
    )
    db.commit()
    return detail_response(group)


@router.get(
    "/{envGroupId}",
    operation_id="getEnvGroup",
    response_model=EnvGroupDetail,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def get_env_group_route(
    envGroupId: str,
    response: Response,
    db: DbDep,
    workspace: CurrentWorkspaceDep,
) -> EnvGroupDetail:
    validate_env_group_id(envGroupId)
    attach_workspace_header(response, workspace.id)
    group = get_env_group(db, workspace_id=workspace.id, env_group_id=envGroupId)
    reference_checker = EnvGroupReferenceChecker(db, workspace_id=workspace.id)
    db.commit()
    return detail_response(group, reference_checker)


@router.patch(
    "/{envGroupId}",
    operation_id="patchEnvGroup",
    response_model=EnvGroupDetail,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def patch_env_group_route(
    envGroupId: str,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
    payload: EnvGroupPatchRequest,
) -> EnvGroupDetail:
    validate_env_group_id(envGroupId)
    attach_workspace_header(response, workspace.id)
    group = get_env_group(db, workspace_id=workspace.id, env_group_id=envGroupId)
    fields: dict[str, Any] = payload.model_dump(exclude_unset=True, by_alias=False)
    updated = update_env_group(db, group=group, actor_user_id=user.id, fields=fields)
    reference_checker = EnvGroupReferenceChecker(db, workspace_id=workspace.id)
    db.commit()
    return detail_response(updated, reference_checker)


@router.delete(
    "/{envGroupId}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteEnvGroup",
    response_model=None,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def delete_env_group_route(
    envGroupId: str,
    response: Response,
    db: DbDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> Response:
    validate_env_group_id(envGroupId)
    attach_workspace_header(response, workspace.id)
    group = get_env_group(db, workspace_id=workspace.id, env_group_id=envGroupId)
    delete_env_group(
        db,
        group=group,
        reference_checker=EnvGroupReferenceChecker(db, workspace_id=workspace.id),
    )
    db.commit()
    return Response(
        status_code=status.HTTP_204_NO_CONTENT, headers={"x-workspace-id": workspace.id}
    )


@router.post(
    "/{envGroupId}/duplicate",
    status_code=status.HTTP_201_CREATED,
    operation_id="duplicateEnvGroup",
    response_model=EnvGroupDetail,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def duplicate_env_group_route(
    envGroupId: str,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> EnvGroupDetail:
    validate_env_group_id(envGroupId)
    attach_workspace_header(response, workspace.id)
    source = get_env_group(db, workspace_id=workspace.id, env_group_id=envGroupId)
    duplicated = duplicate_env_group(db, source=source, actor_user_id=user.id)
    db.commit()
    return detail_response(duplicated)
