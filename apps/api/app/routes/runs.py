from typing import Annotated

from fastapi import APIRouter, Path, Request, Response, status

from app.api.deps import CsrfDep, CurrentUserDep, CurrentWorkspaceDep, DbDep
from app.core.errors import AppError
from app.core.ids import is_ulid
from app.schemas.common import ErrorResponse
from app.schemas.runs import RunCreateRequest, RunCreateResponse, RunStopResponse
from app.services.runs import request_stop_by_id
from app.services.scenarios import create_debug_run

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])
ERROR_RESPONSE = {"model": ErrorResponse}
RunIdPath = Annotated[str, Path(alias="runId")]


def iso_z(value) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def validate_run_id(run_id: str) -> None:
    if not is_ulid(run_id):
        raise AppError(
            "VALIDATION_ERROR",
            "Validation failed.",
            422,
            [{"field": "runId", "code": "INVALID_FIELD", "message": "Invalid Run ID."}],
        )


def attach_workspace_header(response: Response, workspace_id: str) -> None:
    response.headers["x-workspace-id"] = workspace_id


@router.post(
    "",
    operation_id="createRun",
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
def create_run(
    payload: RunCreateRequest,
    request: Request,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> RunCreateResponse:
    """Create a Scenario Debug Run.

    P0-05 accepts ``runType=debug`` with ``sourceType=debug_scenario`` only.
    A short-window dedup hit returns the already-created Run with
    ``deduplicated: true`` and status 200 instead of 201.
    """
    if payload.source_type != "debug_scenario":
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
        workspace_id=workspace.id,
        actor=user,
        request=request,
        source_id=payload.source_id,
        expected_source_revision=payload.expected_source_revision,
        env_group_id=payload.env_group_id,
        selected_node_id=payload.selected_node_id,
    )
    db.commit()
    response.status_code = result.status_code
    response.headers["x-workspace-id"] = workspace.id
    return RunCreateResponse(
        id=result.run.id,
        state=result.run.state,  # type: ignore[arg-type]
        run_type=result.run.run_type,  # type: ignore[arg-type]
        source_type=result.run.source_type,  # type: ignore[arg-type]
        source_id=result.run.source_id,
        selected_node_id=result.run.selected_node_id,
        created_at=iso_z(result.run.created_at) or "",
        deduplicated=result.deduplicated,
    )


@router.post(
    "/{runId}/stop",
    operation_id="stopRun",
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
def stop_run(
    run_id: RunIdPath,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> RunStopResponse:
    validate_run_id(run_id)
    result = request_stop_by_id(db, run_id=run_id, workspace_id=workspace.id, actor=user)
    db.commit()
    response.status_code = result.status_code
    response.headers["x-workspace-id"] = workspace.id
    return RunStopResponse(
        id=result.run_id,
        state=result.state,  # type: ignore[arg-type]
        stop_requested_at=iso_z(result.stop_requested_at),
        duplicate=result.duplicate,
    )
