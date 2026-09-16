from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa


ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = ROOT / "apps/api/migrations/versions/0021_p0_run_allocation_runtime.py"


def load_migration():
    spec = importlib.util.spec_from_file_location("p0_runtime_allocation_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def create_pre_migration_schema(connection: sa.Connection) -> None:
    connection.execute(sa.text("CREATE TABLE runs (id TEXT PRIMARY KEY, state TEXT NOT NULL)"))
    connection.execute(
        sa.text("CREATE TABLE load_nodes (id TEXT PRIMARY KEY, runtime_version TEXT NULL)")
    )
    connection.execute(
        sa.text(
            "CREATE TABLE run_node_allocations ("
            "id TEXT PRIMARY KEY, run_id TEXT NOT NULL, node_id TEXT NOT NULL)"
        )
    )


@pytest.mark.parametrize("active_state", ["initializing", "running", "stopping"])
def test_runtime_identity_migration_rejects_active_runs_before_schema_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, active_state: str
) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / f'active-{active_state}.db'}")
    with engine.begin() as connection:
        create_pre_migration_schema(connection)
        connection.execute(
            sa.text("INSERT INTO runs (id, state) VALUES ('run-active', :state)"),
            {"state": active_state},
        )
        context = MigrationContext.configure(connection)
        migration = load_migration()
        monkeypatch.setattr(migration, "op", Operations(context))

        with pytest.raises(RuntimeError, match="active Runs"):
            migration.upgrade()

        columns = {
            column["name"] for column in sa.inspect(connection).get_columns("run_node_allocations")
        }
        assert "expected_runtime_version" not in columns


def test_runtime_identity_migration_leaves_terminal_legacy_allocation_unidentified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'terminal-runs.db'}")
    with engine.begin() as connection:
        create_pre_migration_schema(connection)
        connection.execute(
            sa.text("INSERT INTO runs (id, state) VALUES ('run-finished', 'finished')")
        )
        connection.execute(
            sa.text(
                "INSERT INTO load_nodes (id, runtime_version) VALUES ('node-1', 'runtime-test-v1')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO run_node_allocations (id, run_id, node_id) "
                "VALUES ('allocation-1', 'run-finished', 'node-1')"
            )
        )
        context = MigrationContext.configure(connection)
        migration = load_migration()
        monkeypatch.setattr(migration, "op", Operations(context))

        migration.upgrade()

        expected_runtime_version = connection.scalar(
            sa.text(
                "SELECT expected_runtime_version FROM run_node_allocations "
                "WHERE id = 'allocation-1'"
            )
        )
        assert expected_runtime_version is None
