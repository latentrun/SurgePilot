from dataclasses import dataclass
from typing import Annotated

import secrets

from fastapi import Cookie, Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.ids import is_ulid
from app.core.time import as_utc, utc_now
from app.db.session import get_db
from app.models.auth import ApiToken, SessionRecord, User, Workspace, WorkspaceMember
from app.services.sessions import (
    SESSION_COOKIE_NAME,
    find_active_session,
    get_session_user,
    token_hash,
    verify_csrf,
)
from app.services.api_tokens import parse_plaintext_token
from app.services.workspaces import get_default_workspace
from app.services.workspace_admin import ensure_active_user, get_accessible_workspace

DbDep = Annotated[Session, Depends(get_db)]
SessionCookieDep = Annotated[
    str | None,
    Cookie(alias=SESSION_COOKIE_NAME, title="SurgePilot Session"),
]
CsrfHeaderDep = Annotated[str | None, Header(alias="x-csrf-token")]
WorkspaceHeaderDep = Annotated[str | None, Header(alias="x-workspace-id")]
bearer_scheme = HTTPBearer(auto_error=False)


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


@dataclass(frozen=True)
class PublicApiContext:
    token: ApiToken
    user: User
    workspace: Workspace


def _unauthenticated_public() -> AppError:
    return AppError("UNAUTHENTICATED", "Authentication is required.", 401)


def _public_token_scope_denied() -> AppError:
    return AppError("PUBLIC_TOKEN_SCOPE_DENIED", "API token scope is not sufficient.", 403)


def _resolve_public_workspace(
    db: Session, *, token: ApiToken, user: User, workspace_id: str | None
) -> Workspace:
    allowlist = list(token.workspace_allowlist or [])
    if workspace_id is None:
        if len(allowlist) != 1:
            raise AppError("WORKSPACE_REQUIRED", "Workspace context is required.", 400)
        workspace_id = allowlist[0]
    elif not is_ulid(workspace_id):
        raise AppError("WORKSPACE_REQUIRED", "Workspace context is required.", 400)

    if workspace_id not in allowlist:
        raise AppError("WORKSPACE_ACCESS_DENIED", "Workspace access is denied.", 403)

    workspace = db.get(Workspace, workspace_id)
    if workspace is None or workspace.status != "active":
        raise AppError("WORKSPACE_ACCESS_DENIED", "Workspace access is denied.", 403)
    membership = db.get(WorkspaceMember, {"workspace_id": workspace_id, "user_id": user.id})
    if membership is None:
        raise AppError("WORKSPACE_ACCESS_DENIED", "Workspace access is denied.", 403)
    return workspace


def get_public_api_context(
    db: DbDep,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    workspace_id: WorkspaceHeaderDep = None,
) -> PublicApiContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthenticated_public()
    parsed = parse_plaintext_token(credentials.credentials)
    if parsed is None:
        raise _unauthenticated_public()
    public_id, secret = parsed
    token = db.scalar(select(ApiToken).where(ApiToken.public_id == public_id))
    now = utc_now()
    if (
        token is None
        or token.revoked_at is not None
        or as_utc(token.expires_at) <= now
        or not secrets.compare_digest(token.secret_hash, token_hash(secret))
    ):
        raise _unauthenticated_public()
    user = db.get(User, token.actor_user_id)
    if user is None or user.status != "active":
        raise _unauthenticated_public()
    workspace = _resolve_public_workspace(db, token=token, user=user, workspace_id=workspace_id)
    token.last_used_at = now
    request.state.workspace_id = workspace.id
    return PublicApiContext(token=token, user=user, workspace=workspace)


PublicApiContextDep = Annotated[PublicApiContext, Depends(get_public_api_context)]


def require_public_scope(required_scope: str):
    def dependency(context: PublicApiContextDep) -> PublicApiContext:
        if required_scope not in set(context.token.scopes or []):
            raise _public_token_scope_denied()
        return context

    return dependency


def require_public_any_scope(*required_scopes: str):
    def dependency(context: PublicApiContextDep) -> PublicApiContext:
        if set(context.token.scopes or []).isdisjoint(required_scopes):
            raise _public_token_scope_denied()
        return context

    return dependency


PublicReadDep = Annotated[PublicApiContext, Depends(require_public_scope("read"))]
PublicConfigWriteDep = Annotated[PublicApiContext, Depends(require_public_scope("config:write"))]
PublicDependencyWriteDep = Annotated[
    PublicApiContext, Depends(require_public_scope("dependency:write"))
]
PublicRunDep = Annotated[PublicApiContext, Depends(require_public_scope("run"))]
PublicReadOrRunDep = Annotated[PublicApiContext, Depends(require_public_any_scope("read", "run"))]
