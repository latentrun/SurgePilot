from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "apps/api/migrations/versions/0022_p2_04_system_openapi_identity.py"
)
DEFAULT_WORKSPACE_ID = "01HZW000000000000000000000"
FIRST_USER_ID = "01J00000000000000000000001"
LATER_USER_ID = "01J00000000000000000000002"


def run_migration(connection: sa.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = importlib.util.spec_from_file_location(
        "system_openapi_identity_migration", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
    migration.upgrade()


def seed_legacy_schema(connection: sa.Connection) -> None:
    connection.execute(
        sa.text("CREATE TABLE users (id TEXT PRIMARY KEY, created_at TEXT NOT NULL)")
    )
    connection.execute(
        sa.text(
            "CREATE TABLE audit_events (event_type TEXT NOT NULL, target_type TEXT, target_id TEXT)"
        )
    )
    connection.execute(
        sa.text(
            "CREATE TABLE api_catalog_specs ("
            "id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, status TEXT NOT NULL, "
            "name TEXT NOT NULL, filename TEXT NOT NULL, document_title TEXT NOT NULL, "
            "source_format TEXT NOT NULL, created_by TEXT NOT NULL)"
        )
    )
    connection.execute(
        sa.text("INSERT INTO users (id, created_at) VALUES (:id, :created_at)"),
        [
            {"id": FIRST_USER_ID, "created_at": "2020-01-01"},
            {"id": LATER_USER_ID, "created_at": "2020-01-02"},
        ],
    )


def add_spec(connection: sa.Connection, spec_id: str, **overrides: str) -> None:
    values = {
        "id": spec_id,
        "workspace_id": DEFAULT_WORKSPACE_ID,
        "status": "available",
        "name": "SurgePilot API",
        "filename": "surgepilot-api.openapi.json",
        "document_title": "SurgePilot API",
        "source_format": "openapi_json",
        "created_by": FIRST_USER_ID,
        **overrides,
    }
    connection.execute(
        sa.text(
            "INSERT INTO api_catalog_specs "
            "(id, workspace_id, status, name, filename, document_title, source_format, created_by) "
            "VALUES (:id, :workspace_id, :status, :name, :filename, :document_title, "
            ":source_format, :created_by)"
        ),
        values,
    )


@pytest.mark.parametrize(
    ("candidates", "audited", "adopted"),
    [
        ([], False, set()),
        ([({}, "system")], False, {"system"}),
        ([({}, "first"), ({}, "second")], False, set()),
        ([({"created_by": LATER_USER_ID}, "later")], False, set()),
        ([({}, "uploaded")], True, set()),
        ([({"status": "deleted"}, "deleted")], False, set()),
        ([({"name": "User API"}, "user")], False, set()),
        ([({"filename": "customer.openapi.json"}, "other-filename")], False, set()),
        ([({"document_title": "Customer API"}, "other-title")], False, set()),
        ([({"source_format": "openapi_yaml"}, "other-format")], False, set()),
        ([({"workspace_id": LATER_USER_ID}, "other-workspace")], False, set()),
    ],
)
def test_historical_adoption_only_marks_one_unaudited_canonical_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    candidates: list[tuple[dict[str, str], str]],
    audited: bool,
    adopted: set[str],
) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        seed_legacy_schema(connection)
        add_spec(connection, "ordinary", name="Customer API")
        for overrides, spec_id in candidates:
            add_spec(connection, spec_id, **overrides)
        if audited:
            connection.execute(
                sa.text(
                    "INSERT INTO audit_events (event_type, target_type, target_id) "
                    "VALUES ('api_catalog_spec.uploaded', 'api_catalog_spec', 'uploaded')"
                )
            )

        run_migration(connection, monkeypatch)

        rows = connection.execute(sa.text("SELECT id, system_key FROM api_catalog_specs")).all()
        assert {row.id for row in rows if row.system_key == "surgepilot_api"} == adopted
        assert all(row.system_key is None for row in rows if row.id not in adopted)
    engine.dispose()
