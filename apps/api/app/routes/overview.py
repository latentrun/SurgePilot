from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentWorkspaceDep, DbDep
from app.schemas.common import ErrorResponse
from app.schemas.overview import OverviewResponse
from app.services.overview import DEFAULT_RECENT_RUN_LIMIT, get_overview

router = APIRouter(prefix="/api/v1/overview", tags=["overview"])
ERROR_RESPONSE = {"model": ErrorResponse}


@router.get(
    "",
    operation_id="getOverview",
    response_model=OverviewResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def get_overview_route(
    response: Response,
    db: DbDep,
    workspace: CurrentWorkspaceDep,
    recent_limit: Annotated[
        int, Query(alias="recentLimit", ge=1, le=10)
    ] = DEFAULT_RECENT_RUN_LIMIT,
) -> OverviewResponse:
    response.headers["x-workspace-id"] = workspace.id
    return get_overview(db, workspace=workspace, recent_limit=recent_limit)
