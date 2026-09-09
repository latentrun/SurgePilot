from datetime import timedelta

from fastapi import Request
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.ids import new_ulid
from app.core.time import as_utc, utc_now
from app.models.auth import User, Workspace
from app.schemas.auth import (
    AuthSessionResponse,
    CurrentUserResponse,
)
from app.services.audit import write_audit_event
from app.services.passwords import PasswordPolicyError, hash_password, verify_password
from app.services.sessions import CreatedSession, create_session
from app.services.system_settings import effective_allow_signup
from app.services.workspace_admin import (
    available_workspaces,
    permissions_for,
    resolve_current_workspace,
    user_summary,
    workspace_summary,
)
from app.services.workspaces import add_default_membership, get_default_workspace

DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=19456,t=2,p=1$OFsp4RtPJeT99AnXXo4/hw$"
    "FuHDOeVmp6kLSjzxnC7v/bLvphfFU/XELjZpb9S92R8"
)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _session_context(db: Session, user: User, workspace: Workspace):
    workspace_data = workspace_summary(workspace)
    return {
        "user": user_summary(user),
        "current_workspace": workspace_data,
        "available_workspaces": available_workspaces(db, user),
        "permissions": permissions_for(user),
        "default_workspace": workspace_data,
    }


def auth_response(
    db: Session, user: User, workspace: Workspace, session: CreatedSession
) -> AuthSessionResponse:
    return AuthSessionResponse(
        **_session_context(db, user, workspace), csrf_token=session.csrf_token
    )


def current_user_response(db: Session, user: User, workspace: Workspace) -> CurrentUserResponse:
    return CurrentUserResponse(**_session_context(db, user, workspace))


def current_user_response_for_preference(
    db: Session, *, user: User, preferred_workspace_id: str | None
) -> CurrentUserResponse:
    workspace, _ = resolve_current_workspace(db, user=user, preferred_workspace_id=preferred_workspace_id)
    return current_user_response(db, user, workspace)


def users_exist(db: Session) -> bool:
    return (db.scalar(select(func.count(User.id))) or 0) > 0


def lock_users_for_bootstrap(db: Session) -> None:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))


def register_user(
    db: Session,
    *,
    email: str,
    display_name: str,
    password: str,
    request: Request,
) -> tuple[User, Workspace, CreatedSession]:
    normalized_email = normalize_email(email)
    trimmed_display_name = display_name.strip()
    if not trimmed_display_name:
        raise AppError(
            "VALIDATION_ERROR",
            "Validation failed.",
            422,
            [
                {
                    "field": "displayName",
                    "code": "INVALID_FIELD",
                    "message": "Display name is required.",
                }
            ],
        )
    try:
        password_hash = hash_password(password)
    except PasswordPolicyError as exc:
        raise AppError(
            "PASSWORD_POLICY_VIOLATION",
            "Password does not meet the policy.",
            422,
            [{"field": "password", "code": "PASSWORD_POLICY_VIOLATION", "message": str(exc)}],
        ) from exc

    with db.begin_nested():
        lock_users_for_bootstrap(db)
        first_user = not users_exist(db)
        if not first_user and not effective_allow_signup(db):
            raise AppError("SIGNUP_DISABLED", "Signup is disabled.", 403)
        now = utc_now()
        user = User(
            id=new_ulid(),
            email=normalized_email,
            display_name=trimmed_display_name,
            password_hash=password_hash,
            role="admin" if first_user else "user",
            status="active",
            failed_login_count=0,
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        try:
            db.flush()
        except IntegrityError as exc:
            raise AppError("EMAIL_ALREADY_EXISTS", "Email already exists.", 409) from exc
        add_default_membership(db, user_id=user.id, joined_at=now)
        db.flush()
        workspace = get_default_workspace(db, user.id)
        session = create_session(db, user=user)
        write_audit_event(
            db,
            event_type="auth.register",
            request=request,
            actor_user_id=user.id,
            workspace_id=workspace.id,
            target_type="user",
            target_id=user.id,
            details={"role": user.role},
        )
    db.commit()
    return user, workspace, session


def _lock_duration(failed_login_count: int) -> timedelta | None:
    if failed_login_count >= 10:
        return timedelta(minutes=30)
    if failed_login_count >= 5:
        return timedelta(minutes=5)
    return None


def _record_login_failure(db: Session, *, user: User | None, request: Request) -> None:
    if user is None:
        write_audit_event(
            db,
            event_type="auth.login_failed",
            request=request,
            details={"reason": "generic"},
        )
        db.commit()
        return

    user.failed_login_count += 1
    duration = _lock_duration(user.failed_login_count)
    if duration is not None:
        user.locked_until = utc_now() + duration
        write_audit_event(
            db,
            event_type="auth.locked",
            request=request,
            actor_user_id=user.id,
            target_type="user",
            target_id=user.id,
            details={"failedLoginCount": user.failed_login_count},
        )
    write_audit_event(
        db,
        event_type="auth.login_failed",
        request=request,
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
        details={"reason": "generic"},
    )
    db.commit()


def login_user(
    db: Session,
    *,
    email: str,
    password: str,
    request: Request,
) -> tuple[User, Workspace, CreatedSession]:
    normalized_email = normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized_email))
    now = utc_now()
    password_matches = verify_password(
        password, user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    )
    if user is None:
        _record_login_failure(db, user=None, request=request)
        raise AppError("INVALID_CREDENTIALS", "Invalid email or password.", 401)
    if user.locked_until is not None and as_utc(user.locked_until) > now:
        _record_login_failure(db, user=user, request=request)
        raise AppError("INVALID_CREDENTIALS", "Invalid email or password.", 401)
    if not password_matches:
        _record_login_failure(db, user=user, request=request)
        raise AppError("INVALID_CREDENTIALS", "Invalid email or password.", 401)

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    user.updated_at = now
    if user.status == "disabled":
        raise AppError("USER_DISABLED", "User is disabled.", 403)
    workspace, _ = resolve_current_workspace(db, user=user, preferred_workspace_id=None)
    session = create_session(db, user=user)
    write_audit_event(
        db,
        event_type="auth.login",
        request=request,
        actor_user_id=user.id,
        workspace_id=workspace.id,
        target_type="session",
        target_id=session.record.id,
    )
    db.commit()
    return user, workspace, session
