import asyncio
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.main import app
from app.models.auth import DEFAULT_WORKSPACE_ID, User, Workspace


ROOT = Path(__file__).resolve().parents[3]


def _normalize_postgres_url(value: str) -> str:
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def _render_url(url: URL) -> str:
    return url.render_as_string(hide_password=False)


@pytest.fixture()
def migrated_postgres_engine(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    base_value = os.environ.get("SURGEPILOT_TEST_DATABASE_URL")
    if not base_value:
        pytest.skip("Set SURGEPILOT_TEST_DATABASE_URL to run PostgreSQL integration tests.")

    base_url = make_url(_normalize_postgres_url(base_value))
    database_name = f"surgepilot_test_{uuid4().hex}"
    admin_url = base_url.set(database="postgres")
    test_url = base_url.set(database=database_name)

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
    with admin_engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    admin_engine.dispose()

    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("DEFAULT_WORKSPACE_NAME", "Default Workspace")
    monkeypatch.setenv("DATABASE_URL", _render_url(test_url))

    alembic_config = Config(str(ROOT / "apps/api/alembic.ini"))
    alembic_config.set_main_option("script_location", str(ROOT / "apps/api/migrations"))
    alembic_config.set_main_option("path_separator", "os")
    engine = create_engine(test_url, future=True)
    try:
        command.upgrade(alembic_config, "head")
        yield engine
    finally:
        engine.dispose()
        cleanup_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
        with cleanup_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        cleanup_engine.dispose()


def test_p0_00_alembic_upgrade_creates_auth_workspace_schema(
    migrated_postgres_engine: Engine,
) -> None:
    inspector = inspect(migrated_postgres_engine)

    assert {
        "users",
        "sessions",
        "workspaces",
        "workspace_members",
        "audit_events",
    } <= set(inspector.get_table_names())

    with Session(migrated_postgres_engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Workspace)
                .where(Workspace.id == DEFAULT_WORKSPACE_ID)
            )
            == 1
        )


def test_api_worker_run_once_handles_postgres_advisory_lock_contention(
    migrated_postgres_engine: Engine,
) -> None:
    from app import worker

    testing_session = sessionmaker(
        bind=migrated_postgres_engine,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )
    lock_keys = [
        worker.LOAD_NODE_INIT_ADVISORY_LOCK,
        worker.RUN_PROTOCOL_ADVISORY_LOCK,
        worker.RUN_REPORT_SUMMARY_ADVISORY_LOCK,
    ]

    with migrated_postgres_engine.connect() as holder:
        locked = [
            holder.execute(text("select pg_try_advisory_lock(:key)"), {"key": key}).scalar()
            for key in lock_keys
        ]
        assert locked == [True, True, True]
        try:
            assert worker.run_once(testing_session) == 0
        finally:
            for key in lock_keys:
                holder.execute(text("select pg_advisory_unlock(:key)"), {"key": key})


@pytest.mark.anyio
async def test_concurrent_first_admin_registration_creates_exactly_one_admin(
    migrated_postgres_engine: Engine,
) -> None:
    TestingSession = sessionmaker(
        bind=migrated_postgres_engine,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )

    def override_db() -> Iterator[Session]:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with (
            AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as first_client,
            AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as second_client,
        ):
            first, second = await asyncio.gather(
                first_client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": "first@example.com",
                        "displayName": "First User",
                        "password": "password123",
                    },
                ),
                second_client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": "second@example.com",
                        "displayName": "Second User",
                        "password": "password123",
                    },
                ),
            )
    finally:
        app.dependency_overrides.clear()

    assert {first.status_code, second.status_code} == {201}

    with Session(migrated_postgres_engine) as db:
        roles = db.scalars(select(User.role)).all()
        assert roles.count("admin") == 1
        assert roles.count("user") == 1
