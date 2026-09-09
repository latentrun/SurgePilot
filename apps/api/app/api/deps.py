from typing import Annotated

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.ids import is_ulid
from app.db.session import get_db
from app.models.auth import SessionRecord, User, Workspace
from app.services.sessions import (
    SESSION_COOKIE_NAME,
    find_active_session,
    get_session_user,
    verify_csrf,
)
from app.services.workspace_admin import ensure_active_user, get_accessible_workspace
from app.services.workspaces import get_default_workspace

DbDep = Annotated[Session, Depends(get_db)]
SessionCookieDep = Annotated[
    str | None,
    Cookie(alias=SESSION_COOKIE_NAME, title="SurgePilot Session"),
]
CsrfHeaderDep = Annotated[str | None, Header(alias="x-csrf-token")]
WorkspaceHeaderDep = Annotated[str | None, Header(alias="x-workspace-id")]


def get_current_session(
    db: DbDep,
    session_token: SessionCookieDep = None,
) -> SessionRecord:
    record = find_active_session(db, session_token)
    if record is None:
        raise AppError("UNAUTHENTICATED", "Authentication is required.", 401)
    return record


CurrentSessionDep = Annotated[SessionRecord, Depends(get_current_session)]


def get_current_user(db: DbDep, record: CurrentSessionDep) -> User:
    user = get_session_user(db, record)
    ensure_active_user(user)
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_current_workspace(
    db: DbDep,
    user: CurrentUserDep,
    request: Request,
    workspace_id: WorkspaceHeaderDep = None,
) -> Workspace:
    if workspace_id is None:
        workspace = get_default_workspace(db, user.id)
    else:
        if not is_ulid(workspace_id):
            raise AppError("WORKSPACE_REQUIRED", "Workspace context is required.", 400)
        workspace = get_accessible_workspace(db, workspace_id=workspace_id, user=user)
        if workspace is None:
            raise AppError("WORKSPACE_ACCESS_DENIED", "Workspace access is denied.", 403)
    request.state.workspace_id = workspace.id
    return workspace


CurrentWorkspaceDep = Annotated[Workspace, Depends(get_current_workspace)]


def require_csrf(record: CurrentSessionDep, csrf_token: CsrfHeaderDep = None) -> None:
    if csrf_token is None:
        raise AppError("CSRF_TOKEN_REQUIRED", "CSRF token is required.", 403)
    if not verify_csrf(record, csrf_token):
        raise AppError("CSRF_TOKEN_INVALID", "CSRF token is invalid.", 403)


CsrfDep = Annotated[None, Depends(require_csrf)]


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")
