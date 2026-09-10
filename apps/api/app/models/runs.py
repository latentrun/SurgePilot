from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

RUN_STATES = ("initializing", "running", "stopping", "finished", "failed", "aborted")
TERMINAL_RUN_STATES = ("finished", "failed", "aborted")
RUN_ARTIFACT_TYPES = (
    "taurus_log",
    "jmeter_log",
    "final_stats_csv",
    "run_log",
    "artifacts_zip",
    "debug_http_trace",
    "debug_http_body_blob",
)
INTERNAL_RUN_ARTIFACT_TYPES = {"debug_http_trace", "debug_http_body_blob"}
PUBLIC_RUN_ARTIFACT_TYPES = tuple(
    artifact_type
    for artifact_type in RUN_ARTIFACT_TYPES
    if artifact_type not in INTERNAL_RUN_ARTIFACT_TYPES
)
SLA_RESULTS = ("passed", "failed", "not_evaluated")
REPORT_SUMMARY_STATUSES = ("pending", "parsed", "failed")
REPORT_SUMMARY_TYPES = ("final_stats",)
RUN_MONITORING_STATUSES = ("enabled", "config_error")


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_runs_id_len"),
        CheckConstraint("length(workspace_id) = 26", name="ck_runs_workspace_id_len"),
        CheckConstraint("run_type in ('debug', 'standard')", name="ck_runs_run_type"),
        CheckConstraint(
            "state in ('initializing', 'running', 'stopping', 'finished', 'failed', 'aborted')",
            name="ck_runs_state",
        ),
        CheckConstraint(
            "source_type in ('protocol_smoke', 'debug_scenario', 'test_plan')",
            name="ck_runs_source_type",
        ),
        CheckConstraint(
            "source_id is null or length(source_id) = 26", name="ck_runs_source_id_len"
        ),
        CheckConstraint("length(selected_node_id) = 26", name="ck_runs_selected_node_id_len"),
        CheckConstraint(
            "length(triggered_by_user_id) = 26", name="ck_runs_triggered_by_user_id_len"
        ),
        CheckConstraint(
            "stop_requested_by_user_id is null or length(stop_requested_by_user_id) = 26",
            name="ck_runs_stop_requested_by_user_id_len",
        ),
        CheckConstraint(
            "last_callback_event_id is null or length(last_callback_event_id) = 26",
            name="ck_runs_last_callback_event_id_len",
        ),
        CheckConstraint(
            "validity is null or validity in ('valid', 'invalid')", name="ck_runs_validity"
        ),
        CheckConstraint(
            "sla_result in ('passed', 'failed', 'not_evaluated')",
            name="ck_runs_sla_result",
        ),
        CheckConstraint(
            "validity_updated_by_user_id is null or length(validity_updated_by_user_id) = 26",
            name="ck_runs_validity_updated_by_user_id_len",
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    run_type: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(26))
    selected_node_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("load_nodes.id", ondelete="RESTRICT"), nullable=False
    )
    triggered_by_user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_callback_event_id: Mapped[str | None] = mapped_column(String(26))
    stop_requested_at: Mapped[datetime | None] = mapped_column(nullable=True)
    stop_requested_by_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT")
    )
    failure_reason: Mapped[str | None] = mapped_column(Text)
    failure_message: Mapped[str | None] = mapped_column(Text)
    forced_convergence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    runner_pid: Mapped[int | None] = mapped_column(nullable=True)
    remote_start_requested_at: Mapped[datetime | None] = mapped_column(nullable=True)
    remote_start_attempted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    remote_start_completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_force_kill_at: Mapped[datetime | None] = mapped_column(nullable=True)
    validity: Mapped[str | None] = mapped_column(Text)
    sla_result: Mapped[str] = mapped_column(Text, nullable=False, default="not_evaluated")
    sla_result_reason: Mapped[str | None] = mapped_column(Text)
    validity_updated_by_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT")
    )
    validity_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)

    snapshot: Mapped["RunSnapshot"] = relationship(back_populates="run", uselist=False)
    leases: Mapped[list["NodeLease"]] = relationship(back_populates="run")
    node_allocations: Mapped[list["RunNodeAllocation"]] = relationship(back_populates="run")
    control_requests: Mapped[list["RunControlRequest"]] = relationship(back_populates="run")
    monitoring_config: Mapped["RunMonitoringConfig | None"] = relationship(
        back_populates="run", uselist=False
    )


Index("ix_runs_workspace_created", Run.workspace_id, Run.created_at.desc(), Run.id.desc())
Index(
    "ix_runs_workspace_type_validity_state_created",
    Run.workspace_id,
    Run.run_type,
    Run.validity,
    Run.state,
    Run.created_at.desc(),
)
Index(
    "ix_runs_workspace_state_created",
    Run.workspace_id,
    Run.state,
    Run.created_at.desc(),
    Run.id.desc(),
)
Index("ix_runs_state_heartbeat", Run.state, Run.last_heartbeat_at)
Index("ix_runs_state_started", Run.state, Run.started_at)
Index("ix_runs_state_remote_start", Run.state, Run.remote_start_requested_at, Run.accepted_at)
Index("ix_runs_state_stop_requested", Run.state, Run.stop_requested_at)


class RunSnapshot(Base):
    __tablename__ = "run_snapshots"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_run_snapshots_id_len"),
        CheckConstraint("length(workspace_id) = 26", name="ck_run_snapshots_workspace_id_len"),
        CheckConstraint("length(run_id) = 26", name="ck_run_snapshots_run_id_len"),
        CheckConstraint("snapshot_version = 1", name="ck_run_snapshots_version"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("runs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    snapshot_version: Mapped[int] = mapped_column(nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    run: Mapped[Run] = relationship(back_populates="snapshot")


class RunMonitoringConfig(Base):
    __tablename__ = "run_monitoring_configs"
    __table_args__ = (
        CheckConstraint("length(run_id) = 26", name="ck_run_monitoring_configs_run_id_len"),
        CheckConstraint(
            "length(workspace_id) = 26", name="ck_run_monitoring_configs_workspace_id_len"
        ),
        CheckConstraint(
            "status in ('enabled', 'config_error')", name="ck_run_monitoring_configs_status"
        ),
        CheckConstraint(
            "disabled_reason is null or disabled_reason in ('not_configured')",
            name="ck_run_monitoring_configs_disabled_reason",
        ),
    )

    run_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True
    )
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    disabled_reason: Mapped[str | None] = mapped_column(Text)
    influxdb_node_write_url: Mapped[str | None] = mapped_column(Text)
    dashboard_uid: Mapped[str] = mapped_column(Text, nullable=False)
    grafana_base_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    run: Mapped[Run] = relationship(back_populates="monitoring_config")


Index(
    "ix_run_monitoring_configs_workspace_run",
    RunMonitoringConfig.workspace_id,
    RunMonitoringConfig.run_id,
)


class NodeLease(Base):
    __tablename__ = "node_leases"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_node_leases_id_len"),
        CheckConstraint("length(workspace_id) = 26", name="ck_node_leases_workspace_id_len"),
        CheckConstraint("length(node_id) = 26", name="ck_node_leases_node_id_len"),
        CheckConstraint("length(run_id) = 26", name="ck_node_leases_run_id_len"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    node_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("load_nodes.id", ondelete="RESTRICT"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    acquired_at: Mapped[datetime] = mapped_column(nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(nullable=True)
    release_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)

    run: Mapped[Run] = relationship(back_populates="leases")


Index(
    "uq_node_leases_active_node",
    NodeLease.node_id,
    unique=True,
    sqlite_where=NodeLease.released_at.is_(None),
    postgresql_where=NodeLease.released_at.is_(None),
)
Index("ix_node_leases_released_acquired", NodeLease.released_at, NodeLease.acquired_at)
Index("ix_node_leases_node", NodeLease.node_id)
Index("ix_node_leases_run", NodeLease.run_id)


class RunNodeAllocation(Base):
    __tablename__ = "run_node_allocations"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_run_node_allocations_id_len"),
        CheckConstraint("length(workspace_id) = 26", name="ck_run_node_allocations_workspace_id_len"),
        CheckConstraint("length(run_id) = 26", name="ck_run_node_allocations_run_id_len"),
        CheckConstraint("length(node_id) = 26", name="ck_run_node_allocations_node_id_len"),
        CheckConstraint("node_index >= 1", name="ck_run_node_allocations_node_index"),
        CheckConstraint("total_nodes >= 1", name="ck_run_node_allocations_total_nodes"),
        CheckConstraint(
            "state in ('initializing', 'running', 'stopping', 'finished', 'failed', 'aborted')",
            name="ck_run_node_allocations_state",
        ),
        CheckConstraint(
            "sla_result is null or sla_result in ('passed', 'failed', 'not_evaluated')",
            name="ck_run_node_allocations_sla_result",
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[str] = mapped_column(String(26), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[str] = mapped_column(String(26), ForeignKey("load_nodes.id", ondelete="RESTRICT"), nullable=False)
    node_index: Mapped[int] = mapped_column(nullable=False)
    total_nodes: Mapped[int] = mapped_column(nullable=False)
    expected_runtime_version: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(nullable=True)
    runner_pid: Mapped[int | None] = mapped_column(nullable=True)
    terminal_reason: Mapped[str | None] = mapped_column(Text)
    terminal_message: Mapped[str | None] = mapped_column(Text)
    cleanup_status: Mapped[str | None] = mapped_column(Text)
    quarantine_reason: Mapped[str | None] = mapped_column(Text)
    sla_result: Mapped[str | None] = mapped_column(Text)
    sla_result_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)

    run: Mapped[Run] = relationship(back_populates="node_allocations")


Index("uq_run_node_allocations_run_node", RunNodeAllocation.run_id, RunNodeAllocation.node_id, unique=True)
Index("uq_run_node_allocations_run_index", RunNodeAllocation.run_id, RunNodeAllocation.node_index, unique=True)
Index("ix_run_node_allocations_workspace_run", RunNodeAllocation.workspace_id, RunNodeAllocation.run_id)
Index("ix_run_node_allocations_node_state", RunNodeAllocation.node_id, RunNodeAllocation.state)


class RunnerCallbackEvent(Base):
    __tablename__ = "runner_callback_events"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_runner_callback_events_id_len"),
        CheckConstraint(
            "event_type in ('accepted', 'running', 'heartbeat', 'artifact', 'finished', 'failed', 'aborted')",
            name="ck_runner_callback_events_event_type",
        ),
        CheckConstraint("seq >= 0", name="ck_runner_callback_events_seq"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    node_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("load_nodes.id", ondelete="RESTRICT"), nullable=False
    )
    event_id: Mapped[str] = mapped_column(String(26), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    seq: Mapped[int] = mapped_column(nullable=False)
    event_time: Mapped[datetime] = mapped_column(nullable=False)
    received_at: Mapped[datetime] = mapped_column(nullable=False)
    request_id: Mapped[str] = mapped_column(Text, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False
    )
    duplicate_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_duplicate_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ignored_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


Index(
    "uq_runner_callback_events_run_event",
    RunnerCallbackEvent.run_id,
    RunnerCallbackEvent.event_id,
    unique=True,
)
Index(
    "ix_runner_callback_events_run_received",
    RunnerCallbackEvent.run_id,
    RunnerCallbackEvent.received_at.desc(),
    RunnerCallbackEvent.id.desc(),
)
Index("ix_runner_callback_events_created", RunnerCallbackEvent.created_at)


class RunControlRequest(Base):
    __tablename__ = "run_control_requests"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_run_control_requests_id_len"),
        CheckConstraint(
            "action in ('start', 'stop', 'force_kill')", name="ck_run_control_requests_action"
        ),
        CheckConstraint(
            "status in ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_run_control_requests_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_run_control_requests_attempt_count"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    allocation_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("run_node_allocations.id", ondelete="CASCADE")
    )
    node_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("load_nodes.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    run_after: Mapped[datetime] = mapped_column(nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(Text)
    last_error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)

    run: Mapped[Run] = relationship(back_populates="control_requests")


Index(
    "uq_run_control_requests_active_action",
    RunControlRequest.run_id,
    RunControlRequest.node_id,
    RunControlRequest.action,
    unique=True,
    sqlite_where=RunControlRequest.status.in_(["pending", "running"]),
    postgresql_where=RunControlRequest.status.in_(["pending", "running"]),
)
Index(
    "ix_run_control_requests_claim",
    RunControlRequest.status,
    RunControlRequest.run_after,
    RunControlRequest.created_at,
)


class RunArtifact(Base):
    __tablename__ = "run_artifacts"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_run_artifacts_id_len"),
        CheckConstraint(
            "artifact_type in ('taurus_log', 'jmeter_log', 'final_stats_csv', "
            "'run_log', 'artifacts_zip', 'debug_http_trace', 'debug_http_body_blob')",
            name="ck_run_artifacts_artifact_type",
        ),
        CheckConstraint("status in ('available', 'failed')", name="ck_run_artifacts_status"),
        CheckConstraint("size_bytes >= 0", name="ck_run_artifacts_size_bytes"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    node_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("load_nodes.id", ondelete="RESTRICT"), nullable=False
    )
    allocation_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("run_node_allocations.id", ondelete="SET NULL")
    )
    event_id: Mapped[str] = mapped_column(String(26), nullable=False)
    artifact_type: Mapped[str] = mapped_column(Text, nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    display_filename: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    terminal_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


Index("uq_run_artifacts_run_event", RunArtifact.run_id, RunArtifact.event_id, unique=True)
Index(
    "uq_run_artifacts_run_path_available",
    RunArtifact.run_id,
    RunArtifact.node_id,
    RunArtifact.allocation_id,
    RunArtifact.relative_path,
    unique=True,
    sqlite_where=RunArtifact.status == "available",
    postgresql_where=RunArtifact.status == "available",
)
Index("ix_run_artifacts_run_allocation", RunArtifact.run_id, RunArtifact.allocation_id)
Index(
    "ix_run_artifacts_workspace_run_created",
    RunArtifact.workspace_id,
    RunArtifact.run_id,
    RunArtifact.created_at.desc(),
    RunArtifact.id.desc(),
)


class RunReportSummary(Base):
    __tablename__ = "run_report_summaries"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_run_report_summaries_id_len"),
        CheckConstraint(
            "length(workspace_id) = 26", name="ck_run_report_summaries_workspace_id_len"
        ),
        CheckConstraint("length(run_id) = 26", name="ck_run_report_summaries_run_id_len"),
        CheckConstraint(
            "length(source_artifact_id) = 26",
            name="ck_run_report_summaries_source_artifact_id_len",
        ),
        CheckConstraint("summary_type in ('final_stats')", name="ck_run_report_summaries_type"),
        CheckConstraint(
            "parse_status in ('pending', 'parsed', 'failed')",
            name="ck_run_report_summaries_parse_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    source_artifact_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("run_artifacts.id", ondelete="CASCADE"), nullable=False
    )
    summary_type: Mapped[str] = mapped_column(Text, nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False
    )
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parse_status: Mapped[str] = mapped_column(Text, nullable=False)
    parse_error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)


Index(
    "uq_run_report_summaries_run_artifact_type",
    RunReportSummary.run_id,
    RunReportSummary.source_artifact_id,
    RunReportSummary.summary_type,
    unique=True,
)
Index(
    "ix_run_report_summaries_workspace_run_type",
    RunReportSummary.workspace_id,
    RunReportSummary.run_id,
    RunReportSummary.summary_type,
)
Index(
    "ix_run_report_summaries_status_created",
    RunReportSummary.parse_status,
    RunReportSummary.created_at,
)
