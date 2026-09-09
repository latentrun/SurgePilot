from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, status
from sqlalchemy import func, select

from app.api.deps import CsrfDep, CurrentUserDep, DbDep
from app.core.errors import AppError
from app.models.auth import User
from app.schemas.auth import (
    AdminUserCreateRequest,
    AdminUserEnvelope,
    AdminUserListResponse,
    AdminUserPatchRequest,
    AdminWorkspaceListResponse,
    MembershipReplaceRequest,
    ResetPasswordRequest,
    SetupStatusResponse,
    SystemSettingsPatchRequest,
    SystemSettingsResponse,
    WorkspaceEnvelope,
    WorkspaceWriteRequest,
)
from app.schemas.common import ErrorResponse
from app.services.system_settings import (
    current_settings,
    effective_allow_signup,
    sensitive_status,
    update_settings,
)
from app.services.workspace_admin import (
    admin_user_summary,
    archive_workspace,
    create_admin_user,
    create_workspace,
    list_admin_workspaces,
    patch_admin_user,
    rename_workspace,
    replace_memberships,
    require_admin,
    reset_password,
    workspace_summary,
)
from app.services.workspaces import has_default_workspace

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
ERROR_RESPONSE = {"model": ErrorResponse}


@router.get(
    "/setup-status",
    operation_id="getAdminSetupStatus",
    response_model=SetupStatusResponse,
    response_model_by_alias=True,
    responses={401: ERROR_RESPONSE, 403: ERROR_RESPONSE},
)
def get_admin_setup_status(db: DbDep, user: CurrentUserDep) -> SetupStatusResponse:
    require_admin(user)
    user_count = db.scalar(select(func.count(User.id))) or 0
    needs_bootstrap = user_count == 0
    return SetupStatusResponse(
        needs_bootstrap=needs_bootstrap,
        allow_signup=True if needs_bootstrap else effective_allow_signup(db),
        has_default_workspace=has_default_workspace(db),
    )


@router.get(
    "/workspaces",
    operation_id="adminListWorkspaces",
    response_model=AdminWorkspaceListResponse,
    response_model_by_alias=True,
    responses={401: ERROR_RESPONSE, 403: ERROR_RESPONSE},
)
def admin_list_workspaces(
    db: DbDep,
    user: CurrentUserDep,
    status_filter: Annotated[
        Literal["active", "archived", "all"], Query(alias="status")
    ] = "active",
) -> AdminWorkspaceListResponse:
    require_admin(user)
    return AdminWorkspaceListResponse(
        workspaces=[
            workspace_summary(workspace) for workspace in list_admin_workspaces(db, status_filter)
        ]
    )


@router.post(
    "/workspaces",
    status_code=status.HTTP_201_CREATED,
    operation_id="adminCreateWorkspace",
    response_model=WorkspaceEnvelope,
    response_model_by_alias=True,
    responses={401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 409: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def admin_create_workspace(
    payload: WorkspaceWriteRequest,
    db: DbDep,
    user: CurrentUserDep,
    _csrf: CsrfDep,
) -> WorkspaceEnvelope:
    workspace = create_workspace(db, name=payload.name, actor=user)
    db.commit()
    return WorkspaceEnvelope(workspace=workspace_summary(workspace))


@router.patch(
    "/workspaces/{workspaceId}",
    operation_id="adminPatchWorkspace",
    response_model=WorkspaceEnvelope,
    response_model_by_alias=True,
    responses={
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def admin_patch_workspace(
    workspace_id: Annotated[str, Path(alias="workspaceId")],
    payload: WorkspaceWriteRequest,
    db: DbDep,
    user: CurrentUserDep,
    _csrf: CsrfDep,
) -> WorkspaceEnvelope:
    workspace = rename_workspace(db, workspace_id=workspace_id, name=payload.name, actor=user)
    db.commit()
    return WorkspaceEnvelope(workspace=workspace_summary(workspace))


@router.post(
    "/workspaces/{workspaceId}/archive",
    operation_id="adminArchiveWorkspace",
    response_model=WorkspaceEnvelope,
    response_model_by_alias=True,
    responses={401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 404: ERROR_RESPONSE, 409: ERROR_RESPONSE},
)
def admin_archive_workspace(
    workspace_id: Annotated[str, Path(alias="workspaceId")],
    db: DbDep,
    user: CurrentUserDep,
    _csrf: CsrfDep,
) -> WorkspaceEnvelope:
    workspace = archive_workspace(db, workspace_id=workspace_id, actor=user)
    db.commit()
    return WorkspaceEnvelope(workspace=workspace_summary(workspace))


@router.get(
    "/users",
    operation_id="adminListUsers",
    response_model=AdminUserListResponse,
    response_model_by_alias=True,
    responses={401: ERROR_RESPONSE, 403: ERROR_RESPONSE},
)
def admin_list_users(
    db: DbDep,
    user: CurrentUserDep,
    q: str | None = None,
) -> AdminUserListResponse:
    require_admin(user)
    stmt = select(User).order_by(User.created_at, User.id)
    if q:
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            func.lower(User.email).like(pattern) | func.lower(User.display_name).like(pattern)
        )
    return AdminUserListResponse(users=[admin_user_summary(db, row) for row in db.scalars(stmt)])


@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    operation_id="adminCreateUser",
    response_model=AdminUserEnvelope,
    response_model_by_alias=True,
    responses={401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 409: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def admin_create_user(
    payload: AdminUserCreateRequest,
    db: DbDep,
    user: CurrentUserDep,
    _csrf: CsrfDep,
) -> AdminUserEnvelope:
    created = create_admin_user(
        db,
        actor=user,
        email=str(payload.email),
        display_name=payload.display_name,
        role=payload.role,
        status=payload.status,
        password=payload.password,
        workspace_ids=payload.workspace_ids,
    )
    db.commit()
    return AdminUserEnvelope(user=admin_user_summary(db, created))


@router.get(
    "/users/{userId}",
    operation_id="adminGetUser",
    response_model=AdminUserEnvelope,
    response_model_by_alias=True,
    responses={401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 404: ERROR_RESPONSE},
)
def admin_get_user(
    user_id: Annotated[str, Path(alias="userId")], db: DbDep, user: CurrentUserDep
) -> AdminUserEnvelope:
    require_admin(user)
    target = db.get(User, user_id)
    if target is None:
        raise AppError("USER_NOT_FOUND", "User not found.", 404)
    return AdminUserEnvelope(user=admin_user_summary(db, target))


@router.patch(
    "/users/{userId}",
    operation_id="adminPatchUser",
    response_model=AdminUserEnvelope,
    response_model_by_alias=True,
    responses={
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def admin_patch_user(
    user_id: Annotated[str, Path(alias="userId")],
    payload: AdminUserPatchRequest,
    db: DbDep,
    user: CurrentUserDep,
    _csrf: CsrfDep,
) -> AdminUserEnvelope:
    updated = patch_admin_user(
        db,
        actor=user,
        user_id=user_id,
        display_name=payload.display_name,
        role=payload.role,
        status=payload.status,
    )
    db.commit()
    return AdminUserEnvelope(user=admin_user_summary(db, updated))


@router.post(
    "/users/{userId}/reset-password",
    operation_id="adminResetUserPassword",
    response_model=AdminUserEnvelope,
    response_model_by_alias=True,
    responses={401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 404: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def admin_reset_user_password(
    user_id: Annotated[str, Path(alias="userId")],
    payload: ResetPasswordRequest,
    db: DbDep,
    user: CurrentUserDep,
    _csrf: CsrfDep,
) -> AdminUserEnvelope:
    target = reset_password(db, actor=user, user_id=user_id, new_password=payload.new_password)
    db.commit()
    return AdminUserEnvelope(user=admin_user_summary(db, target))


@router.put(
    "/users/{userId}/workspaces",
    operation_id="adminReplaceUserWorkspaces",
    response_model=AdminUserEnvelope,
    response_model_by_alias=True,
    responses={401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 404: ERROR_RESPONSE, 409: ERROR_RESPONSE},
)
def admin_replace_user_workspaces(
    user_id: Annotated[str, Path(alias="userId")],
    payload: MembershipReplaceRequest,
    db: DbDep,
    user: CurrentUserDep,
    _csrf: CsrfDep,
) -> AdminUserEnvelope:
    require_admin(user)
    target = db.get(User, user_id)
    if target is None:
        raise AppError("USER_NOT_FOUND", "User not found.", 404)
    replace_memberships(db, user=target, workspace_ids=payload.workspace_ids)
    db.commit()
    return AdminUserEnvelope(user=admin_user_summary(db, target))


@router.get(
    "/system-settings",
    operation_id="adminGetSystemSettings",
    response_model=SystemSettingsResponse,
    response_model_by_alias=True,
    responses={401: ERROR_RESPONSE, 403: ERROR_RESPONSE},
)
def admin_get_system_settings(db: DbDep, user: CurrentUserDep) -> SystemSettingsResponse:
    require_admin(user)
    return SystemSettingsResponse(
        settings=current_settings(db), sensitive_status=sensitive_status()
    )


@router.patch(
    "/system-settings",
    operation_id="adminPatchSystemSettings",
    response_model=SystemSettingsResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def admin_patch_system_settings(
    payload: SystemSettingsPatchRequest,
    db: DbDep,
    user: CurrentUserDep,
    _csrf: CsrfDep,
) -> SystemSettingsResponse:
    values = payload.model_dump(exclude_unset=True, by_alias=True)
    values.update(payload.extra_values())
    settings = update_settings(db, values=values, actor=user)
    db.commit()
    return SystemSettingsResponse(settings=settings, sensitive_status=sensitive_status())
