from dataclasses import dataclass
from datetime import datetime
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.ids import new_ulid
from app.core.time import as_utc, utc_now
from app.models.auth import ApiToken, User, Workspace, WorkspaceMember
from app.schemas.api_tokens import ALLOWED_API_TOKEN_SCOPES
from app.services.sessions import token_hash

PAT_PREFIX = "surgepilot_pat"


@dataclass(frozen=True)
class CreatedApiToken:
    token: ApiToken
    plaintext: str


def _validation_error(field: str, message: str) -> AppError:
    return AppError(
        "VALIDATION_ERROR",
        "Validation failed.",
        422,
        [{"field": field, "code": "INVALID_FIELD", "message": message}],
    )


def _ensure_phase_a_scopes(scopes: list[str]) -> list[str]:
    if not scopes:
        raise _validation_error("scopes", "At least one scope is required.")
    if len(set(scopes)) != len(scopes):
        raise _validation_error("scopes", "Scopes must be distinct.")
    unsupported = sorted(set(scopes) - ALLOWED_API_TOKEN_SCOPES)
    if unsupported:
        raise _validation_error("scopes", "Unsupported API token scope.")
    return scopes


def _ensure_active_memberships(
    db: Session, *, actor_user_id: str, workspace_allowlist: list[str]
) -> list[str]:
    if not workspace_allowlist:
        raise _validation_error("workspaceAllowlist", "At least one Workspace is required.")
    memberships = set(
        db.scalars(
            select(WorkspaceMember.workspace_id)
            .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                WorkspaceMember.user_id == actor_user_id,
                WorkspaceMember.workspace_id.in_(workspace_allowlist),
                Workspace.status == "active",
            )
        ).all()
    )
    missing = [
        workspace_id for workspace_id in workspace_allowlist if workspace_id not in memberships
    ]
    if missing:
        raise AppError("WORKSPACE_ACCESS_DENIED", "Workspace access is denied.", 403)
    return workspace_allowlist


def _plaintext(public_id: str, secret: str) -> str:
    return f"{PAT_PREFIX}_{public_id}_{secret}"


def create_api_token(
    db: Session,
    *,
    actor: User,
    name: str,
    scopes: list[str],
    workspace_allowlist: list[str],
    expires_at: datetime,
) -> CreatedApiToken:
    now = utc_now()
    if as_utc(expires_at) <= now:
        raise _validation_error("expiresAt", "Expiration must be in the future.")
    checked_scopes = _ensure_phase_a_scopes(scopes)
    checked_workspaces = _ensure_active_memberships(
        db, actor_user_id=actor.id, workspace_allowlist=workspace_allowlist
    )
    public_id = new_ulid()
    secret = secrets.token_urlsafe(32)
    token = ApiToken(
        id=new_ulid(),
        public_id=public_id,
        secret_hash=token_hash(secret),
        actor_user_id=actor.id,
        name=name.strip(),
        scopes=checked_scopes,
        workspace_allowlist=checked_workspaces,
        created_at=now,
        expires_at=expires_at,
    )
    db.add(token)
    db.flush()
    return CreatedApiToken(token=token, plaintext=_plaintext(public_id, secret))


def list_api_tokens(db: Session, *, actor_user_id: str) -> list[ApiToken]:
    return list(
        db.scalars(
            select(ApiToken)
            .where(ApiToken.actor_user_id == actor_user_id)
            .order_by(ApiToken.created_at.desc(), ApiToken.id.desc())
        ).all()
    )


def get_owned_api_token(db: Session, *, actor_user_id: str, token_id: str) -> ApiToken:
    token = db.scalar(
        select(ApiToken).where(ApiToken.id == token_id, ApiToken.actor_user_id == actor_user_id)
    )
    if token is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    return token


def revoke_api_token(db: Session, *, actor_user_id: str, token_id: str) -> None:
    token = get_owned_api_token(db, actor_user_id=actor_user_id, token_id=token_id)
    if token.revoked_at is None:
        token.revoked_at = utc_now()
        db.flush()


def parse_plaintext_token(value: str) -> tuple[str, str] | None:
    parts = value.split("_", 3)
    if len(parts) != 4 or parts[0] != "surgepilot" or parts[1] != "pat":
        return None
    public_id, secret = parts[2], parts[3]
    if not public_id or not secret:
        return None
    return public_id, secret
