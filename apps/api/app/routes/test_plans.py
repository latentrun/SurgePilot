from typing import Annotated

from fastapi import APIRouter, Path, Query, Request, Response, status

from app.api.deps import CsrfDep, CurrentUserDep, CurrentWorkspaceDep, DbDep
from app.core.errors import AppError
from app.core.ids import is_ulid
from app.schemas.common import CloneRequest, ErrorResponse, ExecutionPreviewResponse
from app.schemas.test_plans import (
    TestPlanCreateRequest,
    TestPlanDetail,
    TestPlanListResponse,
    TestPlanPatchRequest,
    TestPlanSummary,
)
from app.services.test_plans import (
    clone_test_plan as clone_test_plan_service,
    create_test_plan as create_test_plan_service,
    delete_test_plan as delete_test_plan_service,
    detail_payload,
    get_test_plan_execution_preview as get_test_plan_execution_preview_service,
    get_test_plan as get_test_plan_service,
    list_test_plans as list_test_plans_service,
    patch_test_plan as patch_test_plan_service,
    summary_payloads,
)

router = APIRouter(prefix="/api/v1/test-plans", tags=["test-plans"])
ERROR_RESPONSE = {"model": ErrorResponse}
TestPlanIdPath = Annotated[str, Path(alias="testPlanId")]
TEST_PLAN_SORT_VALUES = ("-updatedAt", "updatedAt", "name", "-name")
ALLOWED_SORTS = set(TEST_PLAN_SORT_VALUES)
ALLOWED_LIST_QUERY_PARAMS = {"page", "pageSize", "search", "tag", "sort"}
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
        "name": "search",
        "in": "query",
        "required": False,
        "schema": {"anyOf": [{"type": "string", "maxLength": 120}, {"type": "null"}]},
    },
    {
        "name": "tag",
        "in": "query",
        "required": False,
        "schema": {"anyOf": [{"type": "string", "maxLength": 32}, {"type": "null"}]},
    },
    {
        "name": "sort",
        "in": "query",
        "required": False,
        "schema": {"type": "string", "default": "-updatedAt"},
    },
]


def attach_workspace_header(response: Response, workspace_id: str) -> None:
    response.headers["x-workspace-id"] = workspace_id


def validate_test_plan_id(test_plan_id: str) -> None:
    if not is_ulid(test_plan_id):
        raise AppError(
            "VALIDATION_ERROR",
            "Validation failed.",
            422,
            [{"field": "testPlanId", "code": "INVALID_FIELD", "message": "Invalid Test Plan ID."}],
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


def parse_list_query(request: Request) -> tuple[int, int, str | None, str | None, str]:
    unknown_params = set(request.query_params) - ALLOWED_LIST_QUERY_PARAMS
    if unknown_params:
        raise invalid_query(sorted(unknown_params)[0], "Unknown query parameter.")
    page = parse_list_int(request.query_params.get("page"), field="page", default=1)
    page_size = parse_list_int(
        request.query_params.get("pageSize"), field="pageSize", default=20, max_value=100
    )
    search = request.query_params.get("search")
    tag = request.query_params.get("tag")
    trimmed_search = search.strip() if search is not None else None
    trimmed_tag = tag.strip() if tag is not None else None
    if trimmed_search is not None and len(trimmed_search) > 120:
        raise invalid_query("search", "search must be 120 characters or less.")
    if trimmed_tag is not None and len(trimmed_tag) > 32:
        raise invalid_query("tag", "tag must be 32 characters or less.")
    sort = request.query_params.get("sort", "-updatedAt")
    if sort not in ALLOWED_SORTS:
        raise invalid_query("sort", "Unsupported sort parameter.")
    return page, page_size, trimmed_search, trimmed_tag, sort


@router.get(
    "",
    operation_id="listTestPlans",
    response_model=TestPlanListResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE},
    openapi_extra={"parameters": LIST_QUERY_OPENAPI_PARAMETERS},
)
def list_test_plans(
    request: Request,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
) -> TestPlanListResponse:
    _ = user
    page, page_size, search, tag, sort = parse_list_query(request)
    rows, total = list_test_plans_service(
        db,
        workspace_id=workspace.id,
        page=page,
        page_size=page_size,
        search=search,
        tag=tag,
        sort=sort,
    )
    attach_workspace_header(response, workspace.id)
    return TestPlanListResponse(
        items=[
            TestPlanSummary.model_validate(payload)
            for payload in summary_payloads(db, workspace_id=workspace.id, plans=rows)
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    operation_id="createTestPlan",
    response_model=TestPlanDetail,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def create_test_plan(
    payload: TestPlanCreateRequest,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> TestPlanDetail:
    plan = create_test_plan_service(
        db,
        workspace_id=workspace.id,
        actor=user,
        payload=payload.model_dump(by_alias=True, mode="json"),
    )
    db.commit()
    attach_workspace_header(response, workspace.id)
    return TestPlanDetail.model_validate(detail_payload(db, plan))


@router.post(
    "/{testPlanId}/clone",
    operation_id="cloneTestPlan",
    response_model=TestPlanDetail,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    summary="Clone Test Plan",
    description="Clone a visible Test Plan in the current Workspace.",
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def clone_test_plan(
    test_plan_id: TestPlanIdPath,
    payload: CloneRequest,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> TestPlanDetail:
    validate_test_plan_id(test_plan_id)
    plan = clone_test_plan_service(
        db,
        workspace_id=workspace.id,
        test_plan_id=test_plan_id,
        actor=user,
        name=payload.name,
    )
    db.commit()
    attach_workspace_header(response, workspace.id)
    return TestPlanDetail.model_validate(detail_payload(db, plan))


@router.get(
    "/{testPlanId}/execution-preview",
    operation_id="getTestPlanExecutionPreview",
    response_model=ExecutionPreviewResponse,
    response_model_by_alias=True,
    summary="Get Test Plan execution preview",
    description="Return a safe read-only debug or standard execution preview for the saved Test Plan revision.",
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def get_test_plan_execution_preview(
    test_plan_id: TestPlanIdPath,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    run_type: Annotated[
        str | None, Query(alias="runType", json_schema_extra={"enum": ["debug", "standard"]})
    ] = None,
) -> ExecutionPreviewResponse:
    _ = user
    validate_test_plan_id(test_plan_id)
    preview = get_test_plan_execution_preview_service(
        db,
        workspace_id=workspace.id,
        test_plan_id=test_plan_id,
        run_type=run_type,
    )
    attach_workspace_header(response, workspace.id)
    return preview


@router.get(
    "/{testPlanId}",
    operation_id="getTestPlan",
    response_model=TestPlanDetail,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def get_test_plan(
    test_plan_id: TestPlanIdPath,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
) -> TestPlanDetail:
    _ = user
    validate_test_plan_id(test_plan_id)
    plan = get_test_plan_service(db, workspace_id=workspace.id, test_plan_id=test_plan_id)
    attach_workspace_header(response, workspace.id)
    return TestPlanDetail.model_validate(detail_payload(db, plan))


@router.patch(
    "/{testPlanId}",
    operation_id="patchTestPlan",
    response_model=TestPlanDetail,
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
def patch_test_plan(
    test_plan_id: TestPlanIdPath,
    payload: TestPlanPatchRequest,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> TestPlanDetail:
    validate_test_plan_id(test_plan_id)
    plan = get_test_plan_service(db, workspace_id=workspace.id, test_plan_id=test_plan_id)
    updated = patch_test_plan_service(
        db,
        plan=plan,
        actor=user,
        expected_revision=payload.expected_revision,
        payload=payload.model_dump(by_alias=True, mode="json", exclude={"expected_revision"}),
    )
    db.commit()
    attach_workspace_header(response, workspace.id)
    return TestPlanDetail.model_validate(detail_payload(db, updated))


@router.delete(
    "/{testPlanId}",
    operation_id="deleteTestPlan",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive Test Plan",
    description=(
        "Archive a Test Plan through the DELETE transport. Archived Test Plans are hidden "
        "from active lists; historical Run Reports keep their saved snapshots."
    ),
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def delete_test_plan(
    test_plan_id: TestPlanIdPath,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> None:
    validate_test_plan_id(test_plan_id)
    plan = get_test_plan_service(db, workspace_id=workspace.id, test_plan_id=test_plan_id)
    delete_test_plan_service(db, plan=plan, actor=user)
    db.commit()
    attach_workspace_header(response, workspace.id)
