import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.auth import DEFAULT_WORKSPACE_ID


@pytest.fixture()
def db_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("DEFAULT_WORKSPACE_NAME", "Default Workspace")

    database_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}", future=True)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

    with TestingSession.begin() as seed_session:
        now = datetime.now(UTC)
        seed_session.execute(
            Base.metadata.tables["workspaces"]
            .insert()
            .values(
                id=DEFAULT_WORKSPACE_ID,
                name="Default Workspace",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )

    with TestingSession() as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
async def client(db_session: Session) -> AsyncIterator[AsyncClient]:
    def override_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def stable_env(monkeypatch: pytest.MonkeyPatch) -> None:
    os.environ.setdefault("ALLOW_SIGNUP", "true")
    os.environ.setdefault("DEFAULT_WORKSPACE_NAME", "Default Workspace")
    os.environ.setdefault(
        "SSH_CREDENTIAL_ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
    )

    from app.services.ssh_remote import ScannedSshHostKey

    def fake_scan(host: str, port: int, timeout_seconds: int) -> ScannedSshHostKey:
        _ = timeout_seconds
        return ScannedSshHostKey(
            host=host,
            port=port,
            algorithm="ssh-ed25519",
            public_key="AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
            fingerprint_sha256="SHA256:SurgePilotTrustedHostKey",
        )

    monkeypatch.setattr("app.services.load_nodes.scan_ssh_host_key", fake_scan)
