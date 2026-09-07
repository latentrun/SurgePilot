from typing import Annotated

from fastapi import APIRouter, Path, Response, status

from app.api.deps import CsrfDep, CurrentUserDep, CurrentWorkspaceDep, DbDep
from app.core.errors import AppError
from app.core.ids import is_ulid
from app.schemas.common import ErrorResponse
from app.schemas.runs import RunStopResponse
from app.services.runs import request_stop_by_id

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
