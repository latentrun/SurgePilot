from typing import Annotated

from fastapi import APIRouter, Cookie, Header, Request, Response, status

from app.api.deps import CurrentSessionDep, CurrentUserDep, DbDep
from app.core.errors import AppError
from app.schemas.auth import (
    AuthSessionResponse,
    CsrfTokenResponse,
    CurrentUserResponse,
    LoginRequest,
    RegisterRequest,
)
from app.schemas.common import ErrorResponse
from app.services.accounts import (
    auth_response,
    current_user_response,
    login_user,
    register_user,
)
from app.services.audit import write_audit_event
from app.services.sessions import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    find_active_session,
    revoke_session,
    rotate_csrf_token,
    set_session_cookie,
    verify_csrf,
)
from app.services.workspaces import get_default_workspace

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
SessionCookieDep = Annotated[
    str | None,
    Cookie(alias=SESSION_COOKIE_NAME, title="SurgePilot Session"),
]
CsrfHeaderDep = Annotated[str | None, Header(alias="x-csrf-token")]

ERROR_RESPONSE = {"model": ErrorResponse}


def _attach_workspace_header(response: Response, workspace_id: str) -> None:
    response.headers["x-workspace-id"] = workspace_id


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    operation_id="register",
    response_model=AuthSessionResponse,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
        500: ERROR_RESPONSE,
    },
)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: DbDep,
) -> AuthSessionResponse:
    user, workspace, created_session = register_user(
        db,
        email=str(payload.email),
        display_name=payload.display_name,
        password=payload.password,
        request=request,
    )
    set_session_cookie(response, created_session.session_token)
    _attach_workspace_header(response, workspace.id)
    return auth_response(db, user, workspace, created_session)


@router.post(
    "/login",
    operation_id="login",
    response_model=AuthSessionResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbDep,
) -> AuthSessionResponse:
    user, workspace, created_session = login_user(
        db,
        email=payload.email or "",
        password=payload.password or "",
        request=request,
    )
    set_session_cookie(response, created_session.session_token)
    _attach_workspace_header(response, workspace.id)
    return auth_response(db, user, workspace, created_session)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="logout",
    response_model=None,
    responses={403: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def logout(
    request: Request,
    db: DbDep,
    session_token: SessionCookieDep = None,
    csrf_token: CsrfHeaderDep = None,
) -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    record = find_active_session(db, session_token)
    if record is None:
        clear_session_cookie(response)
        return response
    if csrf_token is None:
        raise AppError("CSRF_TOKEN_REQUIRED", "CSRF token is required.", 403)
    if not verify_csrf(record, csrf_token):
        raise AppError("CSRF_TOKEN_INVALID", "CSRF token is invalid.", 403)

    revoke_session(db, record)
    write_audit_event(
        db,
        event_type="auth.logout",
        request=request,
        actor_user_id=record.user_id,
        target_type="session",
        target_id=record.id,
    )
    db.commit()
    clear_session_cookie(response)
    return response


@router.get(
    "/me",
    operation_id="getCurrentUser",
    response_model=CurrentUserResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def get_current_user(
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
) -> CurrentUserResponse:
    workspace = get_default_workspace(db, user.id)
    result = current_user_response(db, user, workspace)
    _attach_workspace_header(response, workspace.id)
    db.commit()
    return result


@router.get(
    "/csrf",
    operation_id="getCsrfToken",
    response_model=CsrfTokenResponse,
    response_model_by_alias=True,
    responses={401: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def get_csrf_token(
    db: DbDep,
    record: CurrentSessionDep,
    session_token: SessionCookieDep = None,
) -> CsrfTokenResponse:
    _ = session_token
    csrf_token = rotate_csrf_token(db, record)
    db.commit()
    return CsrfTokenResponse(csrf_token=csrf_token)
