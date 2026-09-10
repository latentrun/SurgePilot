"""P1-01 resource multi-node allocations."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_p1_01_resource_multi_node"
down_revision = "0012_p0_05_script_refs"
branch_labels = None
depends_on = None


def json_type() -> sa.types.TypeEngine:
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def _create_node_leases_table(*, unique_run: bool) -> None:
    op.create_table(
        "node_leases",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("node_id", sa.String(length=26), nullable=False),
        sa.Column("run_id", sa.String(length=26), nullable=False, unique=unique_run),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(id) = 26", name="ck_node_leases_id_len"),
        sa.CheckConstraint("length(workspace_id) = 26", name="ck_node_leases_workspace_id_len"),
        sa.CheckConstraint("length(node_id) = 26", name="ck_node_leases_node_id_len"),
        sa.CheckConstraint("length(run_id) = 26", name="ck_node_leases_run_id_len"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_id"], ["load_nodes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
    )


def _copy_node_leases_from_renamed() -> None:
    op.execute(
        """
        insert into node_leases (
            id, workspace_id, node_id, run_id, acquired_at, released_at,
            release_reason, created_at, updated_at
        )
        select
            id, workspace_id, node_id, run_id, acquired_at, released_at,
            release_reason, created_at, updated_at
        from node_leases_old
        """
    )


def _create_node_lease_indexes(*, include_run_index: bool) -> None:
    op.create_index(
        "uq_node_leases_active_node",
        "node_leases",
        ["node_id"],
        unique=True,
        sqlite_where=sa.text("released_at is null"),
        postgresql_where=sa.text("released_at is null"),
    )
    op.create_index(
        "ix_node_leases_released_acquired", "node_leases", ["released_at", "acquired_at"]
    )
    op.create_index("ix_node_leases_node", "node_leases", ["node_id"])
    if include_run_index:
        op.create_index("ix_node_leases_run", "node_leases", ["run_id"])


def _recreate_sqlite_node_leases(*, unique_run: bool, include_run_index: bool) -> None:
    op.rename_table("node_leases", "node_leases_old")
    _create_node_leases_table(unique_run=unique_run)
    _copy_node_leases_from_renamed()
    op.drop_table("node_leases_old")
    _create_node_lease_indexes(include_run_index=include_run_index)


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    with op.batch_alter_table("test_plans") as batch_op:
        batch_op.add_column(
            sa.Column("resource_mode", sa.Text(), nullable=False, server_default="manual")
        )
        batch_op.add_column(
            sa.Column("selected_node_ids_json", json_type(), nullable=False, server_default="[]")
        )
        batch_op.add_column(sa.Column("node_count", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "ck_test_plans_resource_mode", "resource_mode in ('manual', 'auto')"
        )
        batch_op.create_check_constraint(
            "ck_test_plans_node_count", "node_count is null or node_count > 0"
        )
    if dialect != "sqlite":
        op.alter_column("test_plans", "resource_mode", server_default=None)
        op.alter_column("test_plans", "selected_node_ids_json", server_default=None)
    if dialect == "postgresql":
        op.execute(
            "update test_plans set selected_node_ids_json = "
            "case when selected_node_id is null then '[]'::jsonb "
            "else jsonb_build_array(selected_node_id) end"
        )
    else:
        op.execute(
            "update test_plans set selected_node_ids_json = "
            "case when selected_node_id is null then '[]' "
            "else '[\"' || selected_node_id || '\"]' end"
        )

    op.create_table(
        "run_node_allocations",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("run_id", sa.String(length=26), nullable=False),
        sa.Column("node_id", sa.String(length=26), nullable=False),
        sa.Column("node_index", sa.Integer(), nullable=False),
        sa.Column("total_nodes", sa.Integer(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("runner_pid", sa.Integer(), nullable=True),
        sa.Column("terminal_reason", sa.Text(), nullable=True),
        sa.Column("terminal_message", sa.Text(), nullable=True),
        sa.Column("cleanup_status", sa.Text(), nullable=True),
        sa.Column("quarantine_reason", sa.Text(), nullable=True),
        sa.Column("sla_result", sa.Text(), nullable=True),
        sa.Column("sla_result_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(id) = 26", name="ck_run_node_allocations_id_len"),
        sa.CheckConstraint(
            "length(workspace_id) = 26", name="ck_run_node_allocations_workspace_id_len"
        ),
        sa.CheckConstraint("length(run_id) = 26", name="ck_run_node_allocations_run_id_len"),
        sa.CheckConstraint("length(node_id) = 26", name="ck_run_node_allocations_node_id_len"),
        sa.CheckConstraint("node_index >= 1", name="ck_run_node_allocations_node_index"),
        sa.CheckConstraint("total_nodes >= 1", name="ck_run_node_allocations_total_nodes"),
        sa.CheckConstraint(
            "state in ('initializing', 'running', 'stopping', 'finished', 'failed', 'aborted')",
            name="ck_run_node_allocations_state",
        ),
        sa.CheckConstraint(
            "sla_result is null or sla_result in ('passed', 'failed', 'not_evaluated')",
            name="ck_run_node_allocations_sla_result",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_id"], ["load_nodes.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "uq_run_node_allocations_run_node",
        "run_node_allocations",
        ["run_id", "node_id"],
        unique=True,
    )
    op.create_index(
        "uq_run_node_allocations_run_index",
        "run_node_allocations",
        ["run_id", "node_index"],
        unique=True,
    )
    op.create_index(
        "ix_run_node_allocations_workspace_run",
        "run_node_allocations",
        ["workspace_id", "run_id"],
    )
    op.create_index(
        "ix_run_node_allocations_node_state",
        "run_node_allocations",
        ["node_id", "state"],
    )

    if dialect == "postgresql":
        op.drop_constraint("node_leases_run_id_key", "node_leases", type_="unique")
        op.create_index("ix_node_leases_run", "node_leases", ["run_id"])
    else:
        _recreate_sqlite_node_leases(unique_run=False, include_run_index=True)

    with op.batch_alter_table("run_control_requests") as batch_op:
        batch_op.add_column(sa.Column("allocation_id", sa.String(length=26), nullable=True))
        batch_op.create_foreign_key(
            "fk_run_control_requests_allocation_id",
            "run_node_allocations",
            ["allocation_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.drop_index("uq_run_control_requests_active_action")
        batch_op.create_index(
            "uq_run_control_requests_active_action",
            ["run_id", "node_id", "action"],
            unique=True,
            sqlite_where=sa.text("status in ('pending', 'running')"),
            postgresql_where=sa.text("status in ('pending', 'running')"),
        )

    recreate = "always" if dialect == "sqlite" else "auto"
    with op.batch_alter_table("run_artifacts", recreate=recreate) as batch_op:
        batch_op.add_column(sa.Column("allocation_id", sa.String(length=26), nullable=True))
        batch_op.create_foreign_key(
            "fk_run_artifacts_allocation_id",
            "run_node_allocations",
            ["allocation_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.drop_index("uq_run_artifacts_run_path_available")
        batch_op.create_index(
            "uq_run_artifacts_run_path_available",
            ["run_id", "node_id", "allocation_id", "relative_path"],
            unique=True,
            sqlite_where=sa.text("status = 'available'"),
            postgresql_where=sa.text("status = 'available'"),
        )
        batch_op.create_index(
            "ix_run_artifacts_run_allocation",
            ["run_id", "allocation_id"],
        )


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    recreate = "always" if dialect == "sqlite" else "auto"
    with op.batch_alter_table("run_artifacts", recreate=recreate) as batch_op:
        batch_op.drop_index("ix_run_artifacts_run_allocation")
        batch_op.drop_index("uq_run_artifacts_run_path_available")
        batch_op.create_index(
            "uq_run_artifacts_run_path_available",
            ["run_id", "relative_path"],
            unique=True,
            sqlite_where=sa.text("status = 'available'"),
            postgresql_where=sa.text("status = 'available'"),
        )
        batch_op.drop_constraint("fk_run_artifacts_allocation_id", type_="foreignkey")
        batch_op.drop_column("allocation_id")
    with op.batch_alter_table("run_control_requests") as batch_op:
        batch_op.drop_index("uq_run_control_requests_active_action")
        batch_op.create_index(
            "uq_run_control_requests_active_action",
            ["run_id", "action"],
            unique=True,
            sqlite_where=sa.text("status in ('pending', 'running')"),
            postgresql_where=sa.text("status in ('pending', 'running')"),
        )
        batch_op.drop_constraint("fk_run_control_requests_allocation_id", type_="foreignkey")
        batch_op.drop_column("allocation_id")
    if dialect == "postgresql":
        op.drop_index("ix_node_leases_run", table_name="node_leases")
        op.create_unique_constraint("node_leases_run_id_key", "node_leases", ["run_id"])
    else:
        _recreate_sqlite_node_leases(unique_run=True, include_run_index=False)
    op.drop_index("ix_run_node_allocations_node_state", table_name="run_node_allocations")
    op.drop_index("ix_run_node_allocations_workspace_run", table_name="run_node_allocations")
    op.drop_index("uq_run_node_allocations_run_index", table_name="run_node_allocations")
    op.drop_index("uq_run_node_allocations_run_node", table_name="run_node_allocations")
    op.drop_table("run_node_allocations")
    with op.batch_alter_table("test_plans") as batch_op:
        batch_op.drop_constraint("ck_test_plans_node_count", type_="check")
        batch_op.drop_constraint("ck_test_plans_resource_mode", type_="check")
        batch_op.drop_column("node_count")
        batch_op.drop_column("selected_node_ids_json")
        batch_op.drop_column("resource_mode")
