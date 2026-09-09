from fastapi import APIRouter, Response

from app.api.deps import CsrfDep, CurrentUserDep, DbDep
from app.schemas.auth import (
    CurrentUserResponse,
    WorkspaceListResponse,
    WorkspaceSwitchRequest,
)
from app.schemas.common import ErrorResponse
from app.core.errors import AppError
from app.models.auth import Workspace
from app.services.accounts import current_user_response_for_preference
from app.services.workspace_admin import (
    available_workspaces,
    get_accessible_workspace,
    workspace_summary,
)

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])
ERROR_RESPONSE = {"model": ErrorResponse}


@router.get(
    "",
    operation_id="listWorkspaces",
    response_model=WorkspaceListResponse,
    response_model_by_alias=True,
    responses={401: ERROR_RESPONSE, 403: ERROR_RESPONSE},
)
def list_workspaces(db: DbDep, user: CurrentUserDep) -> WorkspaceListResponse:
    items = available_workspaces(db, user)
    return WorkspaceListResponse(
        workspaces=[
            workspace_summary(workspace)
            for workspace in (db.get(Workspace, item.id) for item in items)
            if workspace is not None
        ]
    )


@router.post(
    "/switch",
    operation_id="switchWorkspace",
    response_model=CurrentUserResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def switch_workspace(
    payload: WorkspaceSwitchRequest,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    _csrf: CsrfDep,
) -> CurrentUserResponse:
    workspace = get_accessible_workspace(db, user=user, workspace_id=payload.workspace_id)
    if workspace is None:
        raise AppError("WORKSPACE_ACCESS_DENIED", "Workspace access is denied.", 403)
    result = current_user_response_for_preference(
        db, user=user, preferred_workspace_id=workspace.id
    )
    response.headers["x-workspace-id"] = result.current_workspace.id
    db.commit()
    return result
