from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentSessionDep, CurrentUserDep, CurrentWorkspaceDep, DbDep
from app.core.errors import AppError
from app.core.ids import is_ulid
from app.schemas.common import ErrorResponse
from app.schemas.monitoring import MonitoringEmbedResponse
from app.services.monitoring import get_monitoring_embed

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])
internal_router = APIRouter(prefix="/api/internal/v1", tags=["internal"])
ERROR_RESPONSE = {"model": ErrorResponse}


def _validate_optional_run_id(run_id: str | None) -> None:
    if run_id is not None and not is_ulid(run_id):
        raise AppError(
            "VALIDATION_ERROR",
            "Validation failed.",
            422,
            [{"field": "runId", "code": "INVALID_FIELD", "message": "Invalid Run ID."}],
        )


@router.get(
    "/embed",
    operation_id="getMonitoringEmbed",
    response_model=MonitoringEmbedResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def get_monitoring_embed_route(
    response: Response,
    db: DbDep,
    workspace: CurrentWorkspaceDep,
    run_id: Annotated[str | None, Query(alias="runId")] = None,
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: Annotated[str | None, Query()] = None,
) -> MonitoringEmbedResponse:
    _validate_optional_run_id(run_id)
    response.headers["x-workspace-id"] = workspace.id
    result = get_monitoring_embed(db, workspace_id=workspace.id, run_id=run_id, from_=from_, to=to)
    db.commit()
    return result


@internal_router.get("/session-check", include_in_schema=False, status_code=204)
def check_session_for_proxy(
    _session: CurrentSessionDep,
    _user: CurrentUserDep,
) -> Response:
    return Response(status_code=204)
