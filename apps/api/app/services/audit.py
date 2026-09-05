from typing import Any

from fastapi import Request
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.core.ids import new_ulid
from app.core.time import utc_now
from app.models.auth import AuditEvent


def _client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host


def _user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    value = request.headers.get("user-agent")
    if value is None:
        return None
    return value[:512]


def write_audit_event(
    db: Session,
    *,
    event_type: str,
    request: Request | None = None,
    actor_user_id: str | None = None,
    workspace_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditEvent(
            id=new_ulid(),
            event_type=event_type,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            target_type=target_type,
            target_id=target_id,
            request_id=getattr(request.state, "request_id", None) if request else None,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
            details_json=details or {},
            created_at=utc_now(),
        )
    )


def _independent_audit_bind(bind: Engine | Connection) -> Engine:
    if isinstance(bind, Connection):
        return bind.engine
    return bind


def write_audit_event_in_new_transaction(
    bind: Engine | Connection,
    *,
    event_type: str,
    request: Request | None = None,
    actor_user_id: str | None = None,
    workspace_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    with Session(
        bind=_independent_audit_bind(bind),
        autoflush=False,
        expire_on_commit=False,
        future=True,
    ) as audit_db:
        try:
            write_audit_event(
                audit_db,
                event_type=event_type,
                request=request,
                actor_user_id=actor_user_id,
                workspace_id=workspace_id,
                target_type=target_type,
                target_id=target_id,
                details=details,
            )
            audit_db.commit()
        except Exception:
            audit_db.rollback()
            raise
