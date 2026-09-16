from typing import Annotated, Any, Literal

from fastapi import APIRouter, Path, Query, Request, Response, status
from sqlalchemy import func, select

from app.api.deps import (
    DbDep,
    PublicConfigWriteDep,
    PublicDependencyWriteDep,
    PublicReadDep,
    PublicReadOrRunDep,
    PublicRunDep,
)
from app.core.config import get_settings
from app.core.errors import AppError
from app.models.load_nodes import LoadNode
from app.routes.env_groups import (
    summary_response as env_group_summary_response,
    validate_env_group_id,
)
from app.routes.dependency_files import (
    FILE_IN_USE_RESPONSE,
    INVALID_FILENAME_RESPONSE,
    NAME_CONFLICT_RESPONSE,
    PAYLOAD_TOO_LARGE_RESPONSE,
    STORAGE_UNAVAILABLE_RESPONSE,
    single_upload_file,
    summary_response as dependency_file_summary_response,
    validate_dependency_file_id,
)
from app.routes.runs import iso_z as run_iso_z, validate_run_id
from app.routes.scenarios import (
    ALLOWED_SCENARIO_SORTS,
    invalid_query as scenario_invalid_query,
    scenario_detail,
    scenario_summary,
    validate_scenario_id,
)
from app.routes.test_plans import (
    detail_payload,
    parse_list_query as parse_test_plan_list_query,
    validate_test_plan_id,
)
from app.schemas.common import ErrorResponse
from app.schemas.env_groups import (
    PublicEnvGroupCreateRequest,
    PublicEnvGroupDetail,
    PublicEnvGroupPatchRequest,
)
from app.schemas.dependency_files import DependencyFileListResponse, DependencyFileSummary
from app.schemas.public_api import (
    PublicLoadNodeListResponse,
    PublicLoadNodeSummary,
    PublicRunCreateRequest,
    PublicRunReport,
    PublicTestPlanCreateRequest,
    PublicTestPlanPatchRequest,
)
from app.schemas.runs import (
    RunCreateResponse,
    RunListResponse,
    RunSourceType,
    RunState,
    RunStopResponse,
    RunType,
    RunValidity,
)
from app.schemas.scenarios import (
    ScenarioCreateRequest,
    ScenarioDetail,
    ScenarioListResponse,
    ScenarioPatchRequest,
)
from app.schemas.test_plans import (
    TestPlanDetail,
    TestPlanListResponse,
    TestPlanSummary,
)
from app.services.dependency_files import (
    DependencyFileReferenceChecker,
    audit_details_for_upload,
    delete_dependency_file_metadata,
    get_dependency_file,
    safe_write_dependency_file_audit,
    upload_dependency_file,
)
from app.services.storage import get_storage_client
from app.services.system_settings import dependency_file_policy
from app.services.env_groups import (
    EnvGroupReferenceChecker,
    create_env_group,
    delete_env_group,
    duplicate_env_group,
    env_group_has_secret_variables,
    get_env_group,
    public_plain_variables,
    raise_public_secret_copy_denied,
    reject_public_secret_bearing_group,
    update_env_group,
)
from app.services.load_nodes import visible_node_filters
from app.services.run_reports import get_run_report, list_runs_report
from app.services.runs import request_stop_by_id
from app.services.scenarios import (
    create_debug_run,
    create_scenario as create_scenario_service,
    delete_scenario as delete_scenario_service,
    get_scenario as get_scenario_service,
    list_scenarios as list_scenarios_service,
    patch_scenario as patch_scenario_service,
)
from app.services.test_plans import (
    create_test_plan as create_test_plan_service,
    create_test_plan_run,
    delete_test_plan as delete_test_plan_service,
    get_test_plan as get_test_plan_service,
    list_test_plans as list_test_plans_service,
    patch_test_plan as patch_test_plan_service,
    summary_payloads,
)

router = APIRouter(prefix="/api/public/v1", tags=["public-api"])
ERROR_RESPONSE = {"model": ErrorResponse}
LimitQuery = Annotated[int, Query(ge=1, le=100)]
ScenarioIdPath = Annotated[str, Path(alias="scenarioId")]
TestPlanIdPath = Annotated[str, Path(alias="testPlanId")]
RunIdPath = Annotated[str, Path(alias="runId")]


def public_env_group_detail(
    group, checker: EnvGroupReferenceChecker | None = None
) -> PublicEnvGroupDetail:
    variables = public_plain_variables(group.variables)
    summary = env_group_summary_response(group, checker).model_dump()
    summary["variable_count"] = len(variables)
    return PublicEnvGroupDetail(
        **summary,
        variables=variables,
    )


def attach_workspace_header(response: Response, workspace_id: str) -> None:
    response.headers["x-workspace-id"] = workspace_id


def iso_z(value) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


@router.get(
    "/scenarios",
    operation_id="publicListScenarios",
    response_model=ScenarioListResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def public_list_scenarios(
    response: Response,
    db: DbDep,
    context: PublicReadDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=120)] = None,
    tag: Annotated[list[str] | None, Query()] = None,
    sort: Annotated[str, Query()] = "-updatedAt",
) -> ScenarioListResponse:
    if sort not in ALLOWED_SCENARIO_SORTS:
        raise scenario_invalid_query("sort", "Unsupported sort parameter.")
    items, total = list_scenarios_service(
        db,
        workspace_id=context.workspace.id,
        page=page,
        page_size=page_size,
        search=search,
        tag=tag or [],
        sort=sort,
    )
    db.commit()
    attach_workspace_header(response, context.workspace.id)
    return ScenarioListResponse(
        items=[scenario_summary(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/scenarios/{scenarioId}",
    operation_id="publicGetScenario",
    response_model=ScenarioDetail,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 404: ERROR_RESPONSE},
)
def public_get_scenario(
    scenario_id: ScenarioIdPath, response: Response, db: DbDep, context: PublicReadDep
) -> ScenarioDetail:
    validate_scenario_id(scenario_id)
    scenario = get_scenario_service(db, workspace_id=context.workspace.id, scenario_id=scenario_id)
    db.commit()
    attach_workspace_header(response, context.workspace.id)
    return scenario_detail(scenario)


@router.post(
    "/scenarios",
    operation_id="publicCreateScenario",
    response_model=ScenarioDetail,
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
def public_create_scenario(
    payload: ScenarioCreateRequest,
    response: Response,
    db: DbDep,
    context: PublicConfigWriteDep,
) -> ScenarioDetail:
    scenario = create_scenario_service(
        db,
        workspace_id=context.workspace.id,
        actor=context.user,
        payload=payload.model_dump(by_alias=True, mode="json"),
    )
    db.commit()
    attach_workspace_header(response, context.workspace.id)
    return scenario_detail(scenario)


@router.patch(
    "/scenarios/{scenarioId}",
    operation_id="publicPatchScenario",
    response_model=ScenarioDetail,
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
def public_patch_scenario(
    scenario_id: ScenarioIdPath,
    payload: ScenarioPatchRequest,
    response: Response,
    db: DbDep,
    context: PublicConfigWriteDep,
) -> ScenarioDetail:
    validate_scenario_id(scenario_id)
    scenario = get_scenario_service(db, workspace_id=context.workspace.id, scenario_id=scenario_id)
    updated = patch_scenario_service(
        db,
        scenario=scenario,
        actor=context.user,
        expected_revision=payload.expected_revision,
        payload=payload.model_dump(by_alias=True, mode="json", exclude={"expected_revision"}),
    )
    db.commit()
    attach_workspace_header(response, context.workspace.id)
    return scenario_detail(updated)


@router.delete(
    "/scenarios/{scenarioId}",
    operation_id="publicDeleteScenario",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def public_delete_scenario(
    scenario_id: ScenarioIdPath, response: Response, db: DbDep, context: PublicConfigWriteDep
) -> Response:
    validate_scenario_id(scenario_id)
    scenario = get_scenario_service(db, workspace_id=context.workspace.id, scenario_id=scenario_id)
    delete_scenario_service(db, scenario=scenario, actor=context.user)
    db.commit()
    return Response(
        status_code=status.HTTP_204_NO_CONTENT, headers={"x-workspace-id": context.workspace.id}
    )


@router.post(
    "/env-groups",
    operation_id="publicCreateEnvGroup",
    response_model=PublicEnvGroupDetail,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def public_create_env_group(
    payload: PublicEnvGroupCreateRequest,
    response: Response,
    db: DbDep,
    context: PublicConfigWriteDep,
) -> PublicEnvGroupDetail:
    group = create_env_group(
        db,
        workspace_id=context.workspace.id,
        actor_user_id=context.user.id,
        name=payload.name,
        description=payload.description,
        variables=payload.variables,
        allow_secret=False,
    )
    db.commit()
    attach_workspace_header(response, context.workspace.id)
    return public_env_group_detail(group)


@router.patch(
    "/env-groups/{envGroupId}",
    operation_id="publicPatchEnvGroup",
    response_model=PublicEnvGroupDetail,
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
def public_patch_env_group(
    envGroupId: str,
    payload: PublicEnvGroupPatchRequest,
    response: Response,
    db: DbDep,
    context: PublicConfigWriteDep,
) -> PublicEnvGroupDetail:
    validate_env_group_id(envGroupId)
    group = get_env_group(db, workspace_id=context.workspace.id, env_group_id=envGroupId)
    if payload.model_fields_set and "variables" in payload.model_fields_set:
        reject_public_secret_bearing_group(group)
    updated = update_env_group(
        db,
        group=group,
        actor_user_id=context.user.id,
        fields=payload.model_dump(exclude_unset=True, by_alias=False),
        allow_secret=False,
        allow_secret_preserve=False,
    )
    checker = EnvGroupReferenceChecker(db, workspace_id=context.workspace.id)
    db.commit()
    attach_workspace_header(response, context.workspace.id)
    return public_env_group_detail(updated, checker)


@router.delete(
    "/env-groups/{envGroupId}",
    operation_id="publicDeleteEnvGroup",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def public_delete_env_group(envGroupId: str, db: DbDep, context: PublicConfigWriteDep) -> Response:
    validate_env_group_id(envGroupId)
    group = get_env_group(db, workspace_id=context.workspace.id, env_group_id=envGroupId)
    delete_env_group(
        db,
        group=group,
        reference_checker=EnvGroupReferenceChecker(db, workspace_id=context.workspace.id),
    )
    db.commit()
    return Response(
        status_code=status.HTTP_204_NO_CONTENT, headers={"x-workspace-id": context.workspace.id}
    )


@router.post(
    "/env-groups/{envGroupId}/copy",
    operation_id="publicCopyEnvGroup",
    response_model=PublicEnvGroupDetail,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def public_copy_env_group(
    envGroupId: str, response: Response, db: DbDep, context: PublicConfigWriteDep
) -> PublicEnvGroupDetail:
    validate_env_group_id(envGroupId)
    source = get_env_group(db, workspace_id=context.workspace.id, env_group_id=envGroupId)
    if env_group_has_secret_variables(source):
        raise_public_secret_copy_denied()
    duplicated = duplicate_env_group(db, source=source, actor_user_id=context.user.id)
    db.commit()
    attach_workspace_header(response, context.workspace.id)
    return public_env_group_detail(duplicated)


@router.get(
    "/test-plans",
    operation_id="publicListTestPlans",
    response_model=TestPlanListResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE},
)
def public_list_test_plans(
    request: Request, response: Response, db: DbDep, context: PublicReadDep
) -> TestPlanListResponse:
    page, page_size, search, tag, sort = parse_test_plan_list_query(request)
    rows, total = list_test_plans_service(
        db,
        workspace_id=context.workspace.id,
        page=page,
        page_size=page_size,
        search=search,
        tag=tag,
        sort=sort,
    )
    db.commit()
    attach_workspace_header(response, context.workspace.id)
    return TestPlanListResponse(
        items=[
            TestPlanSummary.model_validate(payload)
            for payload in summary_payloads(db, workspace_id=context.workspace.id, plans=rows)
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/test-plans/{testPlanId}",
    operation_id="publicGetTestPlan",
    response_model=TestPlanDetail,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 404: ERROR_RESPONSE},
)
def public_get_test_plan(
    test_plan_id: TestPlanIdPath, response: Response, db: DbDep, context: PublicReadDep
) -> TestPlanDetail:
    validate_test_plan_id(test_plan_id)
    plan = get_test_plan_service(db, workspace_id=context.workspace.id, test_plan_id=test_plan_id)
    db.commit()
    attach_workspace_header(response, context.workspace.id)
    return TestPlanDetail.model_validate(detail_payload(db, plan))


@router.post(
    "/test-plans",
    operation_id="publicCreateTestPlan",
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
def public_create_test_plan(
    payload: PublicTestPlanCreateRequest,
    response: Response,
    db: DbDep,
    context: PublicConfigWriteDep,
) -> TestPlanDetail:
    plan = create_test_plan_service(
        db,
        workspace_id=context.workspace.id,
        actor=context.user,
        payload=payload.model_dump(by_alias=True, mode="json"),
    )
    db.commit()
    attach_workspace_header(response, context.workspace.id)
    return TestPlanDetail.model_validate(detail_payload(db, plan))


@router.patch(
    "/test-plans/{testPlanId}",
    operation_id="publicPatchTestPlan",
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
def public_patch_test_plan(
    test_plan_id: TestPlanIdPath,
    payload: PublicTestPlanPatchRequest,
    response: Response,
    db: DbDep,
    context: PublicConfigWriteDep,
) -> TestPlanDetail:
    validate_test_plan_id(test_plan_id)
    plan = get_test_plan_service(db, workspace_id=context.workspace.id, test_plan_id=test_plan_id)
    updated = patch_test_plan_service(
        db,
        plan=plan,
        actor=context.user,
        expected_revision=payload.expected_revision,
        payload=payload.model_dump(by_alias=True, mode="json", exclude={"expected_revision"}),
    )
    db.commit()
    attach_workspace_header(response, context.workspace.id)
    return TestPlanDetail.model_validate(detail_payload(db, updated))


@router.delete(
    "/test-plans/{testPlanId}",
    operation_id="publicDeleteTestPlan",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def public_delete_test_plan(
    test_plan_id: TestPlanIdPath, db: DbDep, context: PublicConfigWriteDep
) -> Response:
    validate_test_plan_id(test_plan_id)
    plan = get_test_plan_service(db, workspace_id=context.workspace.id, test_plan_id=test_plan_id)
    delete_test_plan_service(db, plan=plan, actor=context.user)
    db.commit()
    return Response(
        status_code=status.HTTP_204_NO_CONTENT, headers={"x-workspace-id": context.workspace.id}
    )


@router.get(
    "/runs",
    operation_id="publicListRuns",
    response_model=RunListResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def public_list_runs(
    response: Response,
    db: DbDep,
    context: PublicReadOrRunDep,
    state: Annotated[RunState | None, Query()] = None,
    validity: Annotated[RunValidity | None, Query()] = None,
    run_type: Annotated[RunType | None, Query(alias="runType")] = None,
    source_type: Annotated[RunSourceType | None, Query(alias="sourceType")] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    tag: Annotated[str | None, Query(max_length=50)] = None,
    recent_hours: Annotated[int | None, Query(alias="recentHours", gt=0)] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: LimitQuery = 20,
    sort: Annotated[Literal["-createdAt"], Query()] = "-createdAt",
) -> RunListResponse:
    result = list_runs_report(
        db,
        workspace_id=context.workspace.id,
        state=state.value if state else None,
        validity=validity.value if validity else None,
        run_type=run_type.value if run_type else None,
        source_type=source_type.value if source_type else None,
        q=q,
        tag=tag,
        recent_hours=recent_hours,
        cursor=cursor,
        limit=limit,
        sort=sort,
    )
    db.commit()
    attach_workspace_header(response, context.workspace.id)
    return result


@router.post(
    "/runs",
    operation_id="publicCreateRun",
    response_model=RunCreateResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": RunCreateResponse},
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def public_create_run(
    payload: PublicRunCreateRequest,
    request: Request,
    response: Response,
    db: DbDep,
    context: PublicRunDep,
) -> RunCreateResponse:
    if payload.source_type == "debug_scenario":
        if payload.run_type != "debug" or payload.selected_node_id is None:
            raise AppError(
                "VALIDATION_ERROR",
                "Validation failed.",
                422,
                [
                    {
                        "field": "sourceType",
                        "code": "unsupported_run_source",
                        "message": "Only Scenario Debug Runs are supported for this source.",
                    }
                ],
            )
        result = create_debug_run(
            db,
            workspace_id=context.workspace.id,
            actor=context.user,
            request=request,
            source_id=payload.source_id,
            expected_source_revision=payload.expected_source_revision,
            env_group_id=payload.env_group_id,
            selected_node_id=payload.selected_node_id,
        )
    elif payload.source_type == "test_plan":
        if payload.env_group_id is not None or payload.selected_node_id is not None:
            raise AppError(
                "VALIDATION_ERROR",
                "Validation failed.",
                422,
                [
                    {
                        "field": "sourceType",
                        "code": "unsupported_run_override",
                        "message": "Test Plan Runs use saved Env Group and Load Node settings.",
                    }
                ],
            )
        result = create_test_plan_run(
            db,
            workspace_id=context.workspace.id,
            actor=context.user,
            request=request,
            source_id=payload.source_id,
            expected_source_revision=payload.expected_source_revision,
            run_type=payload.run_type.value,
            confirm_high_concurrency=payload.confirm_high_concurrency,
            resource_request=payload.resource_request,
        )
    else:
        raise AppError(
            "VALIDATION_ERROR",
            "Validation failed.",
            422,
            [
                {
                    "field": "sourceType",
                    "code": "unsupported_run_source",
                    "message": "Run source is not supported in this release.",
                }
            ],
        )
    db.commit()
    response.status_code = result.status_code
    attach_workspace_header(response, context.workspace.id)
    return RunCreateResponse(
        id=result.run.id,
        state=result.run.state,
        run_type=result.run.run_type,
        source_type=result.run.source_type,
        source_id=result.run.source_id,
        selected_node_id=result.run.selected_node_id,
        validity=result.run.validity,
        created_at=run_iso_z(result.run.created_at) or "",
        deduplicated=result.deduplicated,
    )


@router.get(
    "/runs/{runId}",
    operation_id="publicGetRun",
    response_model=PublicRunReport,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def public_get_run(
    run_id: RunIdPath, response: Response, db: DbDep, context: PublicReadOrRunDep
) -> PublicRunReport:
    validate_run_id(run_id)
    report = get_run_report(db, workspace_id=context.workspace.id, run_id=run_id)
    db.commit()
    attach_workspace_header(response, context.workspace.id)
    return PublicRunReport.model_validate(report.model_dump())


@router.get(
    "/runs/{runId}/report",
    operation_id="publicGetRunReport",
    response_model=PublicRunReport,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def public_get_run_report(
    run_id: RunIdPath, response: Response, db: DbDep, context: PublicReadOrRunDep
) -> PublicRunReport:
    return public_get_run(run_id, response, db, context)


@router.post(
    "/runs/{runId}/stop",
    operation_id="publicStopRun",
    response_model=RunStopResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        200: {"model": RunStopResponse},
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def public_stop_run(
    run_id: RunIdPath, response: Response, db: DbDep, context: PublicRunDep
) -> RunStopResponse:
    validate_run_id(run_id)
    result = request_stop_by_id(
        db, run_id=run_id, workspace_id=context.workspace.id, actor=context.user
    )
    db.commit()
    response.status_code = result.status_code
    attach_workspace_header(response, context.workspace.id)
    return RunStopResponse(
        id=result.run_id,
        state=result.state,
        stop_requested_at=run_iso_z(result.stop_requested_at),
        duplicate=result.duplicate,
    )


@router.get(
    "/load-nodes",
    operation_id="publicListLoadNodes",
    response_model=PublicLoadNodeListResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def public_list_load_nodes(
    response: Response,
    db: DbDep,
    context: PublicReadDep,
    scope: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PublicLoadNodeListResponse:
    filters: list[Any] = [
        visible_node_filters(workspace_id=context.workspace.id),
        LoadNode.archived_at.is_(None),
    ]
    if scope is not None:
        filters.append(LoadNode.scope == scope)
    if status_filter is not None:
        filters.append(LoadNode.status == status_filter)
    statement = (
        select(LoadNode).where(*filters).order_by(LoadNode.created_at.desc(), LoadNode.id.desc())
    )
    count_statement = select(func.count(LoadNode.id)).where(*filters)
    total = db.scalar(count_statement) or 0
    nodes = db.scalars(statement.offset(offset).limit(limit)).all()
    db.commit()
    attach_workspace_header(response, context.workspace.id)
    return PublicLoadNodeListResponse(
        items=[
            PublicLoadNodeSummary(
                id=node.id,
                scope=node.scope,
                workspace_id=node.workspace_id,
                host=node.host,
                status=node.status,
                runner_version=node.runner_version,
                bundle_version=node.bundle_version,
                runtime_version=node.runtime_version,
                last_checked_at=iso_z(node.last_checked_at),
                last_heartbeat_at=iso_z(node.last_heartbeat_at),
                created_at=iso_z(node.created_at) or "",
                updated_at=iso_z(node.updated_at) or "",
            )
            for node in nodes
        ],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.get(
    "/dependency-files",
    operation_id="publicListDependencyFiles",
    response_model=DependencyFileListResponse,
    response_model_by_alias=True,
    responses={401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def public_list_dependency_files(
    response: Response,
    db: DbDep,
    context: PublicReadDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DependencyFileListResponse:
    from app.models.dependency_files import DependencyFile

    files = db.scalars(
        select(DependencyFile)
        .where(
            DependencyFile.workspace_id == context.workspace.id,
            DependencyFile.status == "available",
        )
        .order_by(DependencyFile.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = (
        db.scalar(
            select(func.count(DependencyFile.id)).where(
                DependencyFile.workspace_id == context.workspace.id,
                DependencyFile.status == "available",
            )
        )
        or 0
    )
    db.commit()
    attach_workspace_header(response, context.workspace.id)
    reference_checker = DependencyFileReferenceChecker(db)
    return DependencyFileListResponse(
        items=[dependency_file_summary_response(file, reference_checker) for file in files],
        page=(offset // limit) + 1,
        page_size=limit,
        total=total,
    )


@router.post(
    "/dependency-files",
    operation_id="publicUploadDependencyFile",
    status_code=status.HTTP_201_CREATED,
    response_model=DependencyFileSummary,
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
async def public_upload_dependency_file(
    request: Request,
    response: Response,
    db: DbDep,
    context: PublicDependencyWriteDep,
) -> DependencyFileSummary:
    policy = dependency_file_policy(db)
    upload = await single_upload_file(request, max_bytes=policy.max_bytes)
    created = upload_dependency_file(
        db,
        workspace_id=context.workspace.id,
        actor_user_id=context.user.id,
        filename=upload.filename or "",
        content_type=upload.content_type,
        source=upload.file,
        storage=get_storage_client(),
        bucket=get_settings().minio_bucket,
        max_bytes=policy.max_bytes,
        allowed_extensions=policy.allowed_extensions,
    )
    db.commit()
    safe_write_dependency_file_audit(
        db,
        request=request,
        event_type="dependency_file.uploaded",
        actor_user_id=context.user.id,
        workspace_id=context.workspace.id,
        file=created,
        details=audit_details_for_upload(
            dependency_file_id=created.id,
            workspace_id=context.workspace.id,
            filename=created.filename,
            size_bytes=created.size_bytes,
            sha256=created.sha256,
            request_id=getattr(request.state, "request_id", ""),
        ),
    )
    attach_workspace_header(response, context.workspace.id)
    return dependency_file_summary_response(created, DependencyFileReferenceChecker(db))


@router.delete(
    "/dependency-files/{dependencyFileId}",
    operation_id="publicDeleteDependencyFile",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: FILE_IN_USE_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def public_delete_dependency_file(
    dependency_file_id: Annotated[str, Path(alias="dependencyFileId")],
    request: Request,
    response: Response,
    db: DbDep,
    context: PublicDependencyWriteDep,
) -> None:
    validate_dependency_file_id(dependency_file_id)
    file = get_dependency_file(
        db, workspace_id=context.workspace.id, dependency_file_id=dependency_file_id
    )
    delete_dependency_file_metadata(
        db,
        file=file,
        actor_user_id=context.user.id,
        reference_checker=DependencyFileReferenceChecker(db),
    )
    db.commit()
    safe_write_dependency_file_audit(
        db,
        request=request,
        event_type="dependency_file.deleted",
        actor_user_id=context.user.id,
        workspace_id=context.workspace.id,
        file=file,
        details={
            "dependencyFileId": file.id,
            "workspaceId": context.workspace.id,
            "filename": file.filename,
            "requestId": getattr(request.state, "request_id", ""),
        },
    )
    attach_workspace_header(response, context.workspace.id)
