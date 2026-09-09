from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ids import is_ulid, new_ulid
from app.core.time import utc_now
from app.models.auth import SessionRecord, User, Workspace, WorkspaceMember
from app.schemas.auth import (
    AdminUserSummary, AvailableWorkspaceSummary, PermissionSummary, UserSummary,
    WorkspaceMembershipSummary, WorkspaceSummary,
)
from app.services.passwords import PasswordPolicyError, hash_password


def require_admin(user: User) -> None:
    if user.role != "admin":
        raise AppError("FORBIDDEN", "Admin access is required.", 403)


def ensure_active_user(user: User | None) -> None:
    if user is None:
        raise AppError("UNAUTHENTICATED", "Authentication is required.", 401)
    if user.status == "disabled":
        raise AppError("USER_DISABLED", "User is disabled.", 403)


def workspace_summary(workspace: Workspace) -> WorkspaceSummary:
    name = get_settings().default_workspace_name if workspace.id == "01HZW000000000000000000000" else workspace.name
    return WorkspaceSummary(id=workspace.id, name=name, status=workspace.status, archived_at=workspace.archived_at)


def user_summary(user: User) -> UserSummary:
    return UserSummary(id=user.id, email=user.email, display_name=user.display_name, role=user.role, status=user.status)


def permissions_for(user: User) -> PermissionSummary:
    admin = user.role == "admin"
    return PermissionSummary(can_manage_workspaces=admin, can_manage_users=admin, can_manage_system_settings=admin, can_view_setup_status=admin)


def available_workspaces(db: Session, user: User) -> list[AvailableWorkspaceSummary]:
    if user.role == "admin":
        rows = db.scalars(select(Workspace).where(Workspace.status == "active").order_by(Workspace.created_at, Workspace.id)).all()
        member_rows = {row.workspace_id: row.joined_at for row in db.scalars(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id))}
        return [AvailableWorkspaceSummary(**workspace_summary(row).model_dump(), membership=WorkspaceMembershipSummary(kind="member" if row.id in member_rows else "admin_access", joined_at=member_rows.get(row.id))) for row in rows]
    rows = db.execute(select(Workspace, WorkspaceMember.joined_at).join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id).where(WorkspaceMember.user_id == user.id, Workspace.status == "active").order_by(Workspace.created_at, Workspace.id)).all()
    return [AvailableWorkspaceSummary(**workspace_summary(row).model_dump(), membership=WorkspaceMembershipSummary(kind="member", joined_at=joined)) for row, joined in rows]


def resolve_current_workspace(db: Session, *, user: User, preferred_workspace_id: str | None) -> tuple[Workspace, list[AvailableWorkspaceSummary]]:
    ensure_active_user(user)
    available = available_workspaces(db, user)
    if not available:
        raise AppError("WORKSPACE_REQUIRED", "Workspace context is required.", 400)
    selected = next((item.id for item in available if preferred_workspace_id and is_ulid(preferred_workspace_id) and item.id == preferred_workspace_id), available[0].id)
    workspace = db.get(Workspace, selected)
    if workspace is None:
        raise AppError("WORKSPACE_REQUIRED", "Workspace context is required.", 400)
    return workspace, available


def get_accessible_workspace(db: Session, *, user: User, workspace_id: str) -> Workspace | None:
    if not is_ulid(workspace_id):
        return None
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        return None
    if workspace.status == "archived":
        raise AppError("WORKSPACE_ARCHIVED", "Workspace is archived.", 403)
    if user.role == "admin" or db.get(WorkspaceMember, {"workspace_id": workspace_id, "user_id": user.id}) is not None:
        return workspace
    return None


def create_workspace(db: Session, *, name: str, actor: User) -> Workspace:
    require_admin(actor)
    normalized = name.strip()
    if db.scalar(select(Workspace.id).where(Workspace.status == "active", func.lower(Workspace.name) == normalized.lower())) is not None:
        raise AppError("WORKSPACE_NAME_CONFLICT", "Workspace name already exists.", 409)
    now = utc_now()
    workspace = Workspace(id=new_ulid(), name=normalized, status="active", created_at=now, updated_at=now)
    db.add(workspace); db.add(WorkspaceMember(workspace_id=workspace.id, user_id=actor.id, joined_at=now))
    try:
        db.flush()
    except IntegrityError as exc:
        raise AppError("WORKSPACE_NAME_CONFLICT", "Workspace name already exists.", 409) from exc
    return workspace


def rename_workspace(db: Session, *, workspace_id: str, name: str, actor: User) -> Workspace:
    require_admin(actor)
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise AppError("WORKSPACE_NOT_FOUND", "Workspace not found.", 404)
    normalized = name.strip()
    if db.scalar(select(Workspace.id).where(Workspace.id != workspace_id, Workspace.status == "active", func.lower(Workspace.name) == normalized.lower())) is not None:
        raise AppError("WORKSPACE_NAME_CONFLICT", "Workspace name already exists.", 409)
    workspace.name = normalized; workspace.updated_at = utc_now(); db.flush(); return workspace


def archive_workspace(db: Session, *, workspace_id: str, actor: User) -> Workspace:
    require_admin(actor)
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise AppError("WORKSPACE_NOT_FOUND", "Workspace not found.", 404)
    if workspace.status == "active" and (db.scalar(select(func.count(Workspace.id)).where(Workspace.status == "active")) or 0) <= 1:
        raise AppError("WORKSPACE_LAST_ACTIVE_REQUIRED", "At least one active workspace is required.", 409)
    now = utc_now(); workspace.status = "archived"; workspace.archived_at = workspace.archived_at or now; workspace.updated_at = now; db.flush(); return workspace


def list_admin_workspaces(db: Session, status_filter: Literal["active", "archived", "all"]) -> list[Workspace]:
    stmt = select(Workspace).order_by(Workspace.created_at, Workspace.id)
    return list(db.scalars(stmt.where(Workspace.status == status_filter) if status_filter != "all" else stmt).all())


def _workspace_ids_for_user(db: Session, user_id: str) -> list[str]:
    return list(db.scalars(select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user_id)).all())


def _active_workspace_ids_for_user(db: Session, user_id: str) -> list[str]:
    return list(db.scalars(select(WorkspaceMember.workspace_id).join(Workspace, Workspace.id == WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user_id, Workspace.status == "active")).all())


def admin_user_summary(db: Session, user: User) -> AdminUserSummary:
    return AdminUserSummary(**user_summary(user).model_dump(), disabled_at=user.disabled_at, workspace_ids=_workspace_ids_for_user(db, user.id))


def active_admin_count(db: Session) -> int:
    return db.scalar(select(func.count(User.id)).where(User.role == "admin", User.status == "active")) or 0


def replace_memberships(db: Session, *, user: User, workspace_ids: list[str]) -> None:
    workspaces = list(db.scalars(select(Workspace).where(Workspace.id.in_(workspace_ids))).all()) if workspace_ids else []
    if {w.id for w in workspaces} != set(workspace_ids):
        raise AppError("WORKSPACE_NOT_FOUND", "Workspace not found.", 404)
    if any(w.status == "archived" for w in workspaces):
        raise AppError("WORKSPACE_ARCHIVED", "Workspace is archived.", 403)
    if user.role == "user" and user.status == "active" and not workspace_ids:
        raise AppError("USER_WORKSPACE_REQUIRED", "Active users require workspace access.", 409)
    db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user.id).delete()
    now = utc_now()
    for workspace_id in dict.fromkeys(workspace_ids): db.add(WorkspaceMember(workspace_id=workspace_id, user_id=user.id, joined_at=now))
    db.flush()


def create_admin_user(db: Session, *, actor: User, email: str, display_name: str, role: str, status: str, password: str, workspace_ids: list[str]) -> User:
    require_admin(actor)
    if role == "user" and status == "active" and not workspace_ids:
        raise AppError("USER_WORKSPACE_REQUIRED", "Active users require workspace access.", 409)
    try: password_hash = hash_password(password)
    except PasswordPolicyError as exc: raise AppError("PASSWORD_POLICY_VIOLATION", "Password does not meet the policy.", 422) from exc
    now = utc_now(); user = User(id=new_ulid(), email=email.strip().lower(), display_name=display_name.strip(), password_hash=password_hash, role=role, status=status, disabled_at=now if status == "disabled" else None, failed_login_count=0, created_at=now, updated_at=now)
    db.add(user)
    try: db.flush()
    except IntegrityError as exc: raise AppError("USER_EMAIL_CONFLICT", "Email already exists.", 409) from exc
    replace_memberships(db, user=user, workspace_ids=workspace_ids); return user


def revoke_user_sessions(db: Session, *, user_id: str) -> None:
    now = utc_now()
    for record in db.scalars(select(SessionRecord).where(SessionRecord.user_id == user_id, SessionRecord.revoked_at.is_(None))): record.revoked_at = now
    db.flush()


def patch_admin_user(db: Session, *, actor: User, user_id: str, display_name: str | None, role: str | None, status: str | None) -> User:
    require_admin(actor); target = db.get(User, user_id)
    if target is None: raise AppError("USER_NOT_FOUND", "User not found.", 404)
    next_role, next_status = role or target.role, status or target.status
    if target.role == "admin" and target.status == "active" and (next_role != "admin" or next_status != "active") and active_admin_count(db) <= 1:
        raise AppError("USER_LAST_ACTIVE_ADMIN", "At least one active admin is required.", 409)
    if next_role == "user" and next_status == "active" and not _active_workspace_ids_for_user(db, target.id):
        raise AppError("USER_WORKSPACE_REQUIRED", "Active users require workspace access.", 409)
    if display_name is not None: target.display_name = display_name.strip()
    target.role = next_role
    if target.status != next_status:
        target.status = next_status; target.disabled_at = utc_now() if next_status == "disabled" else None
        if next_status == "disabled": revoke_user_sessions(db, user_id=target.id)
    target.updated_at = utc_now(); db.flush(); return target


def reset_password(db: Session, *, actor: User, user_id: str, new_password: str) -> User:
    require_admin(actor); target = db.get(User, user_id)
    if target is None: raise AppError("USER_NOT_FOUND", "User not found.", 404)
    try: target.password_hash = hash_password(new_password)
    except PasswordPolicyError as exc: raise AppError("PASSWORD_POLICY_VIOLATION", "Password does not meet the policy.", 422) from exc
    target.updated_at = utc_now(); revoke_user_sessions(db, user_id=target.id); db.flush(); return target
