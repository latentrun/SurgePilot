"""P0-04 runs, node leases, runner protocol, and artifacts."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_p0_04"
down_revision = "0004_p0_03"
branch_labels = None
depends_on = None


def json_type() -> sa.types.TypeEngine:
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.add_column(
        "load_nodes", sa.Column("last_force_kill_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("run_type", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_id", sa.String(length=26), nullable=True),
        sa.Column("selected_node_id", sa.String(length=26), nullable=False),
        sa.Column("triggered_by_user_id", sa.String(length=26), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_callback_event_id", sa.String(length=26), nullable=True),
        sa.Column("stop_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stop_requested_by_user_id", sa.String(length=26), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("forced_convergence", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("runner_pid", sa.Integer(), nullable=True),
        sa.Column("remote_start_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remote_start_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remote_start_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_force_kill_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validity", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(id) = 26", name="ck_runs_id_len"),
        sa.CheckConstraint("length(workspace_id) = 26", name="ck_runs_workspace_id_len"),
        sa.CheckConstraint("run_type in ('debug', 'standard')", name="ck_runs_run_type"),
        sa.CheckConstraint(
            "state in ('initializing', 'running', 'stopping', 'finished', 'failed', 'aborted')",
            name="ck_runs_state",
        ),
        sa.CheckConstraint(
            "source_type in ('protocol_smoke', 'debug_scenario', 'test_plan')",
            name="ck_runs_source_type",
        ),
        sa.CheckConstraint(
            "source_id is null or length(source_id) = 26", name="ck_runs_source_id_len"
        ),
        sa.CheckConstraint("length(selected_node_id) = 26", name="ck_runs_selected_node_id_len"),
        sa.CheckConstraint(
            "length(triggered_by_user_id) = 26", name="ck_runs_triggered_by_user_id_len"
        ),
        sa.CheckConstraint(
            "stop_requested_by_user_id is null or length(stop_requested_by_user_id) = 26",
            name="ck_runs_stop_requested_by_user_id_len",
        ),
        sa.CheckConstraint(
            "last_callback_event_id is null or length(last_callback_event_id) = 26",
            name="ck_runs_last_callback_event_id_len",
        ),
        sa.CheckConstraint(
            "validity is null or validity in ('valid', 'invalid')", name="ck_runs_validity"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["selected_node_id"], ["load_nodes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["stop_requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_runs_workspace_created",
        "runs",
        ["workspace_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_runs_workspace_state_created",
        "runs",
        ["workspace_id", "state", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index("ix_runs_state_heartbeat", "runs", ["state", "last_heartbeat_at"])
    op.create_index("ix_runs_state_started", "runs", ["state", "started_at"])
    op.create_index(
        "ix_runs_state_remote_start", "runs", ["state", "remote_start_requested_at", "accepted_at"]
    )
    op.create_index("ix_runs_state_stop_requested", "runs", ["state", "stop_requested_at"])

    op.create_table(
        "run_snapshots",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("run_id", sa.String(length=26), nullable=False, unique=True),
        sa.Column("snapshot_version", sa.Integer(), nullable=False),
        sa.Column("snapshot_hash", sa.Text(), nullable=False),
        sa.Column("snapshot_json", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("snapshot_version = 1", name="ck_run_snapshots_version"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "node_leases",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("node_id", sa.String(length=26), nullable=False),
        sa.Column("run_id", sa.String(length=26), nullable=False, unique=True),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_id"], ["load_nodes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "uq_node_leases_active_node",
        "node_leases",
        ["node_id"],
        unique=True,
        postgresql_where=sa.text("released_at is null"),
    )
    op.create_index(
        "ix_node_leases_released_acquired", "node_leases", ["released_at", "acquired_at"]
    )
    op.create_index("ix_node_leases_node", "node_leases", ["node_id"])
    op.create_table(
        "runner_callback_events",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("run_id", sa.String(length=26), nullable=False),
        sa.Column("node_id", sa.String(length=26), nullable=False),
        sa.Column("event_id", sa.String(length=26), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.Text(), nullable=False),
        sa.Column("payload_json", json_type(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_duplicate_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ignored_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type in ('accepted', 'running', 'heartbeat', 'artifact', 'finished', 'failed', 'aborted')",
            name="ck_runner_callback_events_event_type",
        ),
        sa.CheckConstraint("seq >= 0", name="ck_runner_callback_events_seq"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_id"], ["load_nodes.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "uq_runner_callback_events_run_event",
        "runner_callback_events",
        ["run_id", "event_id"],
        unique=True,
    )
    op.create_index(
        "ix_runner_callback_events_run_received",
        "runner_callback_events",
        ["run_id", sa.text("received_at DESC"), sa.text("id DESC")],
    )
    op.create_index("ix_runner_callback_events_created", "runner_callback_events", ["created_at"])
    op.create_table(
        "run_control_requests",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("run_id", sa.String(length=26), nullable=False),
        sa.Column("node_id", sa.String(length=26), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "action in ('start', 'stop', 'force_kill')", name="ck_run_control_requests_action"
        ),
        sa.CheckConstraint(
            "status in ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_run_control_requests_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_run_control_requests_attempt_count"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_id"], ["load_nodes.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "uq_run_control_requests_active_action",
        "run_control_requests",
        ["run_id", "action"],
        unique=True,
        postgresql_where=sa.text("status in ('pending', 'running')"),
    )
    op.create_index(
        "ix_run_control_requests_claim",
        "run_control_requests",
        ["status", "run_after", "created_at"],
    )
    op.create_table(
        "run_artifacts",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("run_id", sa.String(length=26), nullable=False),
        sa.Column("node_id", sa.String(length=26), nullable=False),
        sa.Column("event_id", sa.String(length=26), nullable=False),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("display_filename", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("terminal_late", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "artifact_type in ('taurus_log', 'jmeter_log', 'final_stats_csv', 'failed_requests_csv', 'run_log')",
            name="ck_run_artifacts_artifact_type",
        ),
        sa.CheckConstraint("status in ('available', 'failed')", name="ck_run_artifacts_status"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_run_artifacts_size_bytes"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_id"], ["load_nodes.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "uq_run_artifacts_run_event", "run_artifacts", ["run_id", "event_id"], unique=True
    )
    op.create_index(
        "uq_run_artifacts_run_path_available",
        "run_artifacts",
        ["run_id", "relative_path"],
        unique=True,
        postgresql_where=sa.text("status = 'available'"),
    )
    op.create_index(
        "ix_run_artifacts_workspace_run_created",
        "run_artifacts",
        ["workspace_id", "run_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_foreign_key(
        "fk_load_nodes_current_run_id",
        "load_nodes",
        "runs",
        ["current_run_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_load_nodes_current_run_id", "load_nodes", type_="foreignkey")
    op.drop_index("ix_run_artifacts_workspace_run_created", table_name="run_artifacts")
    op.drop_index("uq_run_artifacts_run_path_available", table_name="run_artifacts")
    op.drop_index("uq_run_artifacts_run_event", table_name="run_artifacts")
    op.drop_table("run_artifacts")
    op.drop_index("ix_run_control_requests_claim", table_name="run_control_requests")
    op.drop_index("uq_run_control_requests_active_action", table_name="run_control_requests")
    op.drop_table("run_control_requests")
    op.drop_index("ix_runner_callback_events_created", table_name="runner_callback_events")
    op.drop_index("ix_runner_callback_events_run_received", table_name="runner_callback_events")
    op.drop_index("uq_runner_callback_events_run_event", table_name="runner_callback_events")
    op.drop_table("runner_callback_events")
    op.drop_index("ix_node_leases_node", table_name="node_leases")
    op.drop_index("ix_node_leases_released_acquired", table_name="node_leases")
    op.drop_index("uq_node_leases_active_node", table_name="node_leases")
    op.drop_table("node_leases")
    op.drop_table("run_snapshots")
    op.drop_index("ix_runs_state_stop_requested", table_name="runs")
    op.drop_index("ix_runs_state_remote_start", table_name="runs")
    op.drop_index("ix_runs_state_started", table_name="runs")
    op.drop_index("ix_runs_state_heartbeat", table_name="runs")
    op.drop_index("ix_runs_workspace_state_created", table_name="runs")
    op.drop_index("ix_runs_workspace_created", table_name="runs")
    op.drop_table("runs")
    op.drop_column("load_nodes", "last_force_kill_at")
