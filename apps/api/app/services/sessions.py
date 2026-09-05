from dataclasses import dataclass
from datetime import timedelta
import hashlib
import secrets

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.ids import new_ulid
from app.core.time import as_utc, utc_now
from app.models.auth import SessionRecord, User

SESSION_COOKIE_NAME = "surgepilot_session"
SESSION_ABSOLUTE_TTL = timedelta(days=7)
SESSION_IDLE_TTL = timedelta(hours=24)


@dataclass(frozen=True)
class CreatedSession:
    record: SessionRecord
    session_token: str
    csrf_token: str


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(48)}"


def create_session(db: Session, *, user: User) -> CreatedSession:
    now = utc_now()
    session_token = new_token("sess")
    csrf_token = new_token("csrf")
    record = SessionRecord(
        id=new_ulid(),
        session_token_hash=token_hash(session_token),
        user_id=user.id,
        csrf_token_hash=token_hash(csrf_token),
        created_at=now,
        last_seen_at=now,
        expires_at=now + SESSION_ABSOLUTE_TTL,
    )
    db.add(record)
    db.flush()
    return CreatedSession(record=record, session_token=session_token, csrf_token=csrf_token)


def rotate_csrf_token(db: Session, record: SessionRecord) -> str:
    csrf_token = new_token("csrf")
    record.csrf_token_hash = token_hash(csrf_token)
    db.flush()
    return csrf_token


def session_is_active(record: SessionRecord, *, now=None) -> bool:
    current_time = now or utc_now()
    if record.revoked_at is not None:
        return False
    if as_utc(record.expires_at) <= current_time:
        return False
    return as_utc(record.last_seen_at) + SESSION_IDLE_TTL > current_time


def find_active_session(db: Session, session_token: str | None) -> SessionRecord | None:
    if not session_token:
        return None
    record = db.scalar(
        select(SessionRecord).where(SessionRecord.session_token_hash == token_hash(session_token))
    )
    if record is None or not session_is_active(record):
        return None
    record.last_seen_at = utc_now()
    db.flush()
    return record


def get_session_user(db: Session, record: SessionRecord) -> User:
    return db.scalar(select(User).where(User.id == record.user_id))  # type: ignore[return-value]


def revoke_session(db: Session, record: SessionRecord) -> None:
    if record.revoked_at is None:
        record.revoked_at = utc_now()
        db.flush()


def verify_csrf(record: SessionRecord, csrf_token: str | None) -> bool:
    return csrf_token is not None and secrets.compare_digest(
        token_hash(csrf_token), record.csrf_token_hash
    )


def set_session_cookie(response: Response, session_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="Lax",
        path="/",
        max_age=int(SESSION_ABSOLUTE_TTL.total_seconds()),
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/", samesite="Lax")
