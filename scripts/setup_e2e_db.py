from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import Base
from app.models.auth import DEFAULT_WORKSPACE_ID, Workspace
import app.models.auth  # noqa: F401


def main() -> None:
    engine = create_engine(get_settings().database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        workspace = session.scalar(select(Workspace).where(Workspace.id == DEFAULT_WORKSPACE_ID))
        if workspace is None:
            now = datetime.now(UTC)
            session.add(
                Workspace(
                    id=DEFAULT_WORKSPACE_ID,
                    name="Default Workspace",
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()


if __name__ == "__main__":
    main()
