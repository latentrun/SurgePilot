from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.auth import DEFAULT_WORKSPACE_ID, Workspace, WorkspaceMember


def get_default_workspace(db: Session, user_id: str | None = None) -> Workspace:
    statement = select(Workspace).where(Workspace.id == DEFAULT_WORKSPACE_ID)
    if user_id is not None:
        statement = statement.join(
            WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id
        ).where(WorkspaceMember.user_id == user_id)
    workspace = db.scalar(statement)
    if workspace is None:
        raise AppError("WORKSPACE_REQUIRED", "Workspace context is required.", 400)
    return workspace


def get_workspace_for_user(db: Session, *, workspace_id: str, user_id: str) -> Workspace | None:
    return db.scalar(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(Workspace.id == workspace_id, WorkspaceMember.user_id == user_id)
    )


def add_default_membership(db: Session, *, user_id: str, joined_at) -> None:
    db.add(
        WorkspaceMember(
            workspace_id=DEFAULT_WORKSPACE_ID,
            user_id=user_id,
            joined_at=joined_at,
        )
    )


def has_default_workspace(db: Session) -> bool:
    return db.scalar(select(Workspace.id).where(Workspace.id == DEFAULT_WORKSPACE_ID)) is not None
