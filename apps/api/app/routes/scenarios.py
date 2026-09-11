from typing import Annotated

from fastapi import APIRouter, Path, Query, Request, Response, status

from app.api.deps import CsrfDep, CurrentUserDep, CurrentWorkspaceDep, DbDep
from app.core.errors import AppError
from app.core.ids import is_ulid
from app.schemas.common import CloneRequest, ErrorResponse
from app.schemas.scenarios import (
    CurlImportParseRequest,
    CurlImportParseResponse,
    OpenApiOperationListResponse,
    OpenApiSpecSourceListResponse,
    OpenApiStepDraftGenerateRequest,
    OpenApiStepDraftPreviewResponse,
    ScenarioCreateRequest,
    ScenarioDetail,
    ScenarioListResponse,
    ScenarioPatchRequest,
    ScenarioSummary,
)
from app.services.curl_import import parse_curl_import
from app.services.storage import get_storage_client
from app.services.openapi_step_generation import (
    generate_drafts as generate_openapi_step_drafts_service,
    get_authorized_spec as get_authorized_openapi_spec_service,
    list_openapi_spec_sources as list_openapi_spec_sources_service,
    operations_response as openapi_operations_response_service,
    parse_authorized_spec,
)
from app.services.scenarios import (
    clone_scenario as clone_scenario_service,
    create_scenario as create_scenario_service,
    delete_scenario as delete_scenario_service,
    get_scenario as get_scenario_service,
    list_scenarios as list_scenarios_service,
    patch_scenario as patch_scenario_service,
)

router = APIRouter(prefix="/api/v1/scenarios", tags=["scenarios"])
ERROR_RESPONSE = {"model": ErrorResponse}
ScenarioIdPath = Annotated[str, Path(alias="scenarioId")]
SCENARIO_SORT_VALUES = ("-updatedAt", "updatedAt", "name", "-name")
ALLOWED_SCENARIO_SORTS = set(SCENARIO_SORT_VALUES)


def validate_scenario_id(scenario_id: str) -> None:
    if not is_ulid(scenario_id):
        raise AppError(
            "VALIDATION_ERROR",
            "Validation failed.",
            422,
            [{"field": "scenarioId", "code": "INVALID_FIELD", "message": "Invalid Scenario ID."}],
        )


def iso_z(value) -> str:
    return value.isoformat().replace("+00:00", "Z")


def scenario_summary(scenario) -> ScenarioSummary:
    steps = scenario.steps_json or []
    enabled_steps = [step for step in steps if step.get("enabled", True)]
    data_sources = [item for item in scenario.data_sources_json or [] if item.get("enabled", True)]
    upload_file_count = sum(
        1 for step in steps for upload in step.get("uploadFiles", []) if upload.get("enabled", True)
    )
    return ScenarioSummary(
        id=scenario.id,
        name=scenario.name,
        description=scenario.description,
        tags=scenario.tags_json,
        scenario_type="visual",
        step_count=len(steps),
        enabled_step_count=len(enabled_steps),
        dependency_file_count=len(data_sources) + upload_file_count,
        revision=scenario.revision,
        created_at=iso_z(scenario.created_at),
        updated_at=iso_z(scenario.updated_at),
    )


def scenario_detail(scenario) -> ScenarioDetail:
    summary = scenario_summary(scenario).model_dump()
    return ScenarioDetail(
        **summary,
        base_url_expression=scenario.base_url_expression,
        default_settings=scenario.default_settings_json,
        data_sources=scenario.data_sources_json,
        steps=scenario.steps_json,
    )


def attach_workspace_header(response: Response, workspace_id: str) -> None:
    response.headers["x-workspace-id"] = workspace_id


def invalid_query(field: str, message: str) -> AppError:
    return AppError(
        "INVALID_QUERY_PARAMETER",
        "Invalid query parameter.",
        400,
        [{"field": field, "code": "INVALID_QUERY_PARAMETER", "message": message}],
    )


@router.post(
    "/curl-import/parse",
    operation_id="parseScenarioCurlImport",
    response_model=CurlImportParseResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def parse_scenario_curl_import(
    payload: CurlImportParseRequest,
    response: Response,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> CurlImportParseResponse:
    _ = user
    result = parse_curl_import(payload.raw_curl)
    attach_workspace_header(response, workspace.id)
    return result


@router.get(
    "",
    operation_id="listScenarios",
    response_model=ScenarioListResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def list_scenarios(
    request: Request,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=120)] = None,
    tag: Annotated[list[str] | None, Query()] = None,
    sort: Annotated[str, Query(json_schema_extra={"enum": list(SCENARIO_SORT_VALUES)})] = (
        "-updatedAt"
    ),
) -> ScenarioListResponse:
    _ = (request, user)
    if sort not in ALLOWED_SCENARIO_SORTS:
        raise invalid_query("sort", "Unsupported sort parameter.")
    items, total = list_scenarios_service(
        db,
        workspace_id=workspace.id,
        page=page,
        page_size=page_size,
        search=search,
        tag=tag or [],
        sort=sort,
    )
    attach_workspace_header(response, workspace.id)
    return ScenarioListResponse(
        items=[scenario_summary(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    operation_id="createScenario",
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
def create_scenario(
    payload: ScenarioCreateRequest,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> ScenarioDetail:
    scenario = create_scenario_service(
        db,
        workspace_id=workspace.id,
        actor=user,
        payload=payload.model_dump(by_alias=True, mode="json"),
    )
    db.commit()
    attach_workspace_header(response, workspace.id)
    return scenario_detail(scenario)


@router.post(
    "/{scenarioId}/clone",
    operation_id="cloneScenario",
    response_model=ScenarioDetail,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    summary="Clone Scenario",
    description="Clone a visible Scenario in the current Workspace.",
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def clone_scenario(
    scenario_id: ScenarioIdPath,
    payload: CloneRequest,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> ScenarioDetail:
    validate_scenario_id(scenario_id)
    scenario = clone_scenario_service(
        db,
        workspace_id=workspace.id,
        scenario_id=scenario_id,
        actor=user,
        name=payload.name,
    )
    db.commit()
    attach_workspace_header(response, workspace.id)
    return scenario_detail(scenario)


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


@router.get(
    "/{scenarioId}/openapi-step-generation/specs",
    operation_id="listScenarioOpenApiSpecSources",
    response_model=OpenApiSpecSourceListResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 404: ERROR_RESPONSE},
)
def list_scenario_openapi_spec_sources(
    scenario_id: ScenarioIdPath,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> OpenApiSpecSourceListResponse:
    _ = user
    validate_scenario_id(scenario_id)
    get_scenario_service(db, workspace_id=workspace.id, scenario_id=scenario_id)
    result = list_openapi_spec_sources_service(
        db, workspace_id=workspace.id, limit=limit, offset=offset
    )
    attach_workspace_header(response, workspace.id)
    return result


@router.get(
    "/{scenarioId}/openapi-step-generation/specs/{specId}/operations",
    operation_id="listScenarioOpenApiOperations",
    response_model=OpenApiOperationListResponse,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
        503: ERROR_RESPONSE,
    },
)
def list_scenario_openapi_operations(
    scenario_id: ScenarioIdPath,
    specId: str,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
) -> OpenApiOperationListResponse:
    _ = user
    validate_scenario_id(scenario_id)
    validate_spec_id(specId)
    get_scenario_service(db, workspace_id=workspace.id, scenario_id=scenario_id)
    spec = get_authorized_openapi_spec_service(db, workspace_id=workspace.id, spec_id=specId)
    parsed = parse_authorized_spec(spec, storage=get_storage_client())
    attach_workspace_header(response, workspace.id)
    return openapi_operations_response_service(spec, parsed)


@router.post(
    "/{scenarioId}/openapi-step-generation/drafts",
    operation_id="generateScenarioOpenApiStepDrafts",
    response_model=OpenApiStepDraftPreviewResponse,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
        503: ERROR_RESPONSE,
    },
)
def generate_scenario_openapi_step_drafts(
    scenario_id: ScenarioIdPath,
    payload: OpenApiStepDraftGenerateRequest,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> OpenApiStepDraftPreviewResponse:
    _ = user
    validate_scenario_id(scenario_id)
    validate_spec_id(payload.spec_id)
    get_scenario_service(db, workspace_id=workspace.id, scenario_id=scenario_id)
    spec = get_authorized_openapi_spec_service(
        db, workspace_id=workspace.id, spec_id=payload.spec_id
    )
    parsed = parse_authorized_spec(spec, storage=get_storage_client())
    result = generate_openapi_step_drafts_service(
        spec=spec,
        parsed=parsed,
        operation_refs=payload.operation_refs,
        insert=payload.insert,
    )
    attach_workspace_header(response, workspace.id)
    return result


@router.get(
    "/{scenarioId}",
    operation_id="getScenario",
    response_model=ScenarioDetail,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def get_scenario(
    scenario_id: ScenarioIdPath,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
) -> ScenarioDetail:
    _ = user
    validate_scenario_id(scenario_id)
    scenario = get_scenario_service(db, workspace_id=workspace.id, scenario_id=scenario_id)
    attach_workspace_header(response, workspace.id)
    return scenario_detail(scenario)


@router.patch(
    "/{scenarioId}",
    operation_id="patchScenario",
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
def patch_scenario(
    scenario_id: ScenarioIdPath,
    payload: ScenarioPatchRequest,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> ScenarioDetail:
    validate_scenario_id(scenario_id)
    scenario = get_scenario_service(db, workspace_id=workspace.id, scenario_id=scenario_id)
    updated = patch_scenario_service(
        db,
        scenario=scenario,
        actor=user,
        expected_revision=payload.expected_revision,
        payload=payload.model_dump(by_alias=True, mode="json", exclude={"expected_revision"}),
    )
    db.commit()
    attach_workspace_header(response, workspace.id)
    return scenario_detail(updated)


@router.delete(
    "/{scenarioId}",
    operation_id="deleteScenario",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive Scenario",
    description=(
        "Archive a Scenario through the DELETE transport. Archived Scenarios are hidden "
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
def delete_scenario(
    scenario_id: ScenarioIdPath,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> None:
    validate_scenario_id(scenario_id)
    scenario = get_scenario_service(db, workspace_id=workspace.id, scenario_id=scenario_id)
    delete_scenario_service(db, scenario=scenario, actor=user)
    db.commit()
    attach_workspace_header(response, workspace.id)
