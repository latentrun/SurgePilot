from pathlib import Path
import importlib.util

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[3]


def test_sqlite_upgrade_to_p0_07_allows_artifacts_zip(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "upgrade.db"
    database_url = f"sqlite+pysqlite:///{database_path}"
    engine = create_engine(database_url, future=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    create table runs (
                        id text primary key,
                        run_type text not null,
                        validity text null
                    )
                    """
                )
            )
            connection.execute(text("create table workspaces (id text primary key)"))
            connection.execute(
                text(
                    """
                    create table run_artifacts (
                        id text primary key,
                        workspace_id text not null,
                        run_id text not null,
                        node_id text not null,
                        event_id text not null,
                        artifact_type text not null,
                        relative_path text not null,
                        display_filename text not null,
                        size_bytes integer not null,
                        sha256 text not null,
                        content_type text null,
                        storage_key text not null,
                        status text not null,
                        terminal_late boolean not null default 0,
                        created_at datetime not null,
                        constraint ck_run_artifacts_artifact_type
                            check (artifact_type in (
                                'taurus_log', 'jmeter_log', 'final_stats_csv',
                                'failed_requests_csv', 'run_log'
                            ))
                    )
                    """
                )
            )
            migration_path = ROOT / "apps/api/migrations/versions/0008_p0_07_run_reports.py"
            spec = importlib.util.spec_from_file_location("p0_07_migration", migration_path)
            assert spec is not None and spec.loader is not None
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            context = MigrationContext.configure(connection)
            monkeypatch.setattr(migration, "op", Operations(context))

            migration.upgrade()

            connection.execute(
                text(
                    """
                    insert into run_artifacts (
                        id, workspace_id, run_id, node_id, event_id, artifact_type,
                        relative_path, display_filename, size_bytes, sha256,
                        content_type, storage_key, status, terminal_late, created_at
                    )
                    values (
                        'artifact-1', 'workspace-1', 'run-1', 'node-1', 'event-1',
                        'artifacts_zip', 'artifacts/artifacts.zip', 'artifacts.zip',
                        22, :sha256, 'application/zip',
                        'run-artifacts/workspace-1/run-1/artifacts/artifacts.zip',
                        'available', 0, '2030-06-05T00:00:00Z'
                    )
                    """
                ),
                {"sha256": "a" * 64},
            )
    finally:
        engine.dispose()


def test_sqlite_upgrade_to_p1_08_allows_debug_http_trace(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "upgrade-p1-08.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}", future=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    create table run_artifacts (
                        id text primary key,
                        artifact_type text not null,
                        constraint ck_run_artifacts_artifact_type
                            check (artifact_type in (
                                'taurus_log', 'jmeter_log', 'final_stats_csv',
                                'run_log', 'artifacts_zip'
                            ))
                    )
                    """
                )
            )
            migration_path = ROOT / "apps/api/migrations/versions/0010_p1_debug_http_trace.py"
            spec = importlib.util.spec_from_file_location("p1_08_migration", migration_path)
            assert spec is not None and spec.loader is not None
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            context = MigrationContext.configure(connection)
            monkeypatch.setattr(migration, "op", Operations(context))

            migration.upgrade()

            connection.execute(
                text(
                    """
                    insert into run_artifacts (id, artifact_type)
                    values ('artifact-1', 'debug_http_trace')
                    """
                )
            )
    finally:
        engine.dispose()


def test_sqlite_alembic_upgrade_from_p0_05_shape_to_p1_01(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "upgrade-p1-01.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}", future=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("create table workspaces (id text primary key)"))
            connection.execute(text("create table load_nodes (id text primary key)"))
            connection.execute(text("create table runs (id text primary key)"))
            connection.execute(
                text(
                    """
                    create table test_plans (
                        id text primary key,
                        selected_node_id text null
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    create table node_leases (
                        id text primary key,
                        workspace_id text not null,
                        node_id text not null,
                        run_id text not null unique,
                        acquired_at datetime not null,
                        released_at datetime null,
                        release_reason text null,
                        created_at datetime not null,
                        updated_at datetime not null
                    )
                    """
                )
            )
            connection.execute(
                text("create unique index uq_node_leases_active_node on node_leases (node_id)")
            )
            connection.execute(
                text(
                    "create index ix_node_leases_released_acquired "
                    "on node_leases (released_at, acquired_at)"
                )
            )
            connection.execute(text("create index ix_node_leases_node on node_leases (node_id)"))
            connection.execute(
                text(
                    """
                    create table run_control_requests (
                        id text primary key,
                        workspace_id text not null,
                        run_id text not null,
                        node_id text not null,
                        action text not null,
                        reason text null,
                        status text not null,
                        run_after datetime not null,
                        attempt_count integer not null,
                        claimed_at datetime null,
                        claimed_by text null,
                        finished_at datetime null,
                        last_error_code text null,
                        last_error_message text null,
                        created_at datetime not null,
                        updated_at datetime not null
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "create unique index uq_run_control_requests_active_action "
                    "on run_control_requests (run_id, action) "
                    "where status in ('pending', 'running')"
                )
            )
            connection.execute(
                text(
                    """
                    create table run_artifacts (
                        id text primary key,
                        workspace_id text not null,
                        run_id text not null,
                        node_id text not null,
                        event_id text not null,
                        artifact_type text not null,
                        relative_path text not null,
                        display_filename text not null,
                        size_bytes integer not null,
                        sha256 text not null,
                        content_type text null,
                        storage_key text not null,
                        status text not null,
                        terminal_late boolean not null,
                        created_at datetime not null
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "create unique index uq_run_artifacts_run_event on run_artifacts (run_id, event_id)"
                )
            )
            connection.execute(
                text(
                    "create unique index uq_run_artifacts_run_path_available "
                    "on run_artifacts (run_id, relative_path) where status = 'available'"
                )
            )
            migration_path = ROOT / "apps/api/migrations/versions/0013_p1_01_resource_multi_node.py"
            spec = importlib.util.spec_from_file_location("p1_01_migration", migration_path)
            assert spec is not None and spec.loader is not None
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            context = MigrationContext.configure(connection)
            monkeypatch.setattr(migration, "op", Operations(context))

            migration.upgrade()

            indexes = connection.execute(text("PRAGMA index_list('node_leases')")).mappings().all()
            assert any(row["name"] == "ix_node_leases_run" for row in indexes)
            assert not any(row["unique"] and "run" in row["name"] for row in indexes)
            columns = (
                connection.execute(text("PRAGMA table_info('run_node_allocations')"))
                .mappings()
                .all()
            )
            assert {row["name"] for row in columns} >= {
                "run_id",
                "node_id",
                "node_index",
                "total_nodes",
            }
            artifact_columns = (
                connection.execute(text("PRAGMA table_info('run_artifacts')")).mappings().all()
            )
            assert "allocation_id" in {row["name"] for row in artifact_columns}
            artifact_indexes = (
                connection.execute(text("PRAGMA index_list('run_artifacts')")).mappings().all()
            )
            assert any(row["name"] == "ix_run_artifacts_run_allocation" for row in artifact_indexes)
            path_index = next(
                row
                for row in artifact_indexes
                if row["name"] == "uq_run_artifacts_run_path_available"
            )
            path_index_columns = (
                connection.execute(text(f"PRAGMA index_info('{path_index['name']}')"))
                .mappings()
                .all()
            )
            assert [row["name"] for row in path_index_columns] == [
                "run_id",
                "node_id",
                "allocation_id",
                "relative_path",
            ]
    finally:
        engine.dispose()
