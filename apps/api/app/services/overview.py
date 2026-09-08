from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.time import as_utc, utc_now
from app.models.auth import Workspace
from app.models.load_nodes import LOAD_NODE_STATUSES, LoadNode
from app.models.runs import RUN_ARTIFACT_TYPES, Run, RunArtifact, RunSnapshot
from app.schemas.overview import (
    OverviewActiveRuns,
    OverviewLoadNodeStatusCounts,
    OverviewRecentRun,
    OverviewResourceSummary,
    OverviewResponse,
    OverviewResultRunScope,
    OverviewResultRuns,
    OverviewRunStats,
    OverviewSlaResultCounts,
    OverviewStatsScope,
    OverviewTerminalStateCounts,
    OverviewWorkspace,
)
from app.services.load_nodes import visible_node_filters

OVERVIEW_WINDOW_DAYS = 30
DEFAULT_RECENT_RUN_LIMIT = 5
MAX_RECENT_RUN_LIMIT = 10
TERMINAL_STATES = ("finished", "failed", "aborted")
ACTIVE_STATES = ("initializing", "running", "stopping")
SLA_RESULTS = ("passed", "failed", "not_evaluated")


def iso_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    return as_utc(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _duration_ms(run: Run, *, now: datetime) -> int | None:
    start = run.started_at or run.created_at
    end = run.ended_at or (now if run.state in ACTIVE_STATES else None)
    if start is None or end is None:
        return None
    return max(int((as_utc(end) - as_utc(start)).total_seconds() * 1000), 0)


def _snapshot_source_name(snapshot: dict[str, Any], run: Run) -> str | None:
    if run.source_type == "test_plan":
        plan = snapshot.get("testPlan") if isinstance(snapshot.get("testPlan"), dict) else {}
        return plan.get("name")
    if run.source_type == "debug_scenario":
        scenario = snapshot.get("scenario") if isinstance(snapshot.get("scenario"), dict) else {}
        return scenario.get("name")
    return run.source_type


def _zero_counts(keys: tuple[str, ...]) -> dict[str, int]:
    return {key: 0 for key in keys}


def _result_state_counts(
    db: Session, *, workspace_id: str, window_started_at: datetime
) -> dict[str, int]:
    counts = _zero_counts(TERMINAL_STATES)
    rows = db.execute(
        select(Run.state, func.count(Run.id))
        .where(
            Run.workspace_id == workspace_id,
            Run.run_type == "standard",
            Run.validity == "valid",
            Run.state.in_(TERMINAL_STATES),
            Run.created_at >= window_started_at,
        )
        .group_by(Run.state)
    ).all()
    for state, count in rows:
        if state in counts:
            counts[state] = int(count)
    return counts


def _result_sla_counts(
    db: Session, *, workspace_id: str, window_started_at: datetime
) -> dict[str, int]:
    counts = _zero_counts(SLA_RESULTS)
    rows = db.execute(
        select(Run.sla_result, func.count(Run.id))
        .where(
            Run.workspace_id == workspace_id,
            Run.run_type == "standard",
            Run.validity == "valid",
            Run.state.in_(TERMINAL_STATES),
            Run.created_at >= window_started_at,
        )
        .group_by(Run.sla_result)
    ).all()
    for sla_result, count in rows:
        if sla_result in counts:
            counts[sla_result] = int(count)
    return counts


def _active_counts(
    db: Session, *, workspace_id: str, window_started_at: datetime
) -> dict[str, int]:
    counts = _zero_counts(ACTIVE_STATES)
    rows = db.execute(
        select(Run.state, func.count(Run.id))
        .where(
            Run.workspace_id == workspace_id,
            Run.state.in_(ACTIVE_STATES),
            Run.created_at >= window_started_at,
        )
        .group_by(Run.state)
    ).all()
    for state, count in rows:
        if state in counts:
            counts[state] = int(count)
    return counts


def _artifact_summary_by_run(db: Session, run_ids: list[str]) -> dict[str, tuple[int, bool]]:
    if not run_ids:
        return {}
    rows = db.execute(
        select(
            RunArtifact.run_id,
            func.count(RunArtifact.id),
            func.max(case((RunArtifact.artifact_type == "artifacts_zip", 1), else_=0)),
        )
        .where(
            RunArtifact.run_id.in_(run_ids),
            RunArtifact.status == "available",
            RunArtifact.artifact_type.in_(RUN_ARTIFACT_TYPES),
        )
        .group_by(RunArtifact.run_id)
    ).all()
    return {run_id: (int(count), bool(has_zip)) for run_id, count, has_zip in rows}


def _recent_runs(
    db: Session, *, workspace_id: str, recent_limit: int, now: datetime
) -> list[OverviewRecentRun]:
    rows = db.execute(
        select(Run, RunSnapshot)
        .join(RunSnapshot, RunSnapshot.run_id == Run.id, isouter=True)
        .where(Run.workspace_id == workspace_id)
        .order_by(Run.created_at.desc(), Run.id.desc())
        .limit(recent_limit)
    ).all()
    run_ids = [run.id for run, _snapshot in rows]
    artifact_counts = _artifact_summary_by_run(db, run_ids)
    items: list[OverviewRecentRun] = []
    for run, snapshot in rows:
        artifact_count, has_artifacts_zip = artifact_counts.get(run.id, (0, False))
        source_name = _snapshot_source_name(snapshot.snapshot_json if snapshot else {}, run)
        items.append(
            OverviewRecentRun(
                id=run.id,
                run_type=run.run_type,  # type: ignore[arg-type]
                source_type=run.source_type,  # type: ignore[arg-type]
                source_name=source_name,
                state=run.state,  # type: ignore[arg-type]
                validity=run.validity,  # type: ignore[arg-type]
                sla_result=run.sla_result,  # type: ignore[arg-type]
                created_at=iso_z(run.created_at) or "",
                started_at=iso_z(run.started_at),
                ended_at=iso_z(run.ended_at),
                duration_ms=_duration_ms(run, now=now),
                artifact_count=artifact_count,
                has_artifacts_zip=has_artifacts_zip,
            )
        )
    return items


def _resource_summary(db: Session, *, workspace_id: str) -> OverviewResourceSummary:
    counts = _zero_counts(LOAD_NODE_STATUSES)
    rows = db.execute(
        select(LoadNode.status, func.count(LoadNode.id))
        .where(visible_node_filters(workspace_id=workspace_id), LoadNode.archived_at.is_(None))
        .group_by(LoadNode.status)
    ).all()
    for status, count in rows:
        if status in counts:
            counts[status] = int(count)
    return OverviewResourceSummary(
        total_visible_nodes=sum(counts.values()),
        by_status=OverviewLoadNodeStatusCounts(**counts),
    )


def get_overview(
    db: Session, *, workspace: Workspace, recent_limit: int = DEFAULT_RECENT_RUN_LIMIT
) -> OverviewResponse:
    if recent_limit < 1 or recent_limit > MAX_RECENT_RUN_LIMIT:
        raise ValueError("recent_limit must be between 1 and 10")
    now = utc_now()
    window_started_at = now - timedelta(days=OVERVIEW_WINDOW_DAYS)
    state_counts = _result_state_counts(
        db, workspace_id=workspace.id, window_started_at=window_started_at
    )
    sla_counts = _result_sla_counts(
        db, workspace_id=workspace.id, window_started_at=window_started_at
    )
    active_counts = _active_counts(
        db, workspace_id=workspace.id, window_started_at=window_started_at
    )
    result_total = sum(state_counts.values())
    active_total = sum(active_counts.values())
    return OverviewResponse(
        generated_at=iso_z(now) or "",
        workspace=OverviewWorkspace(id=workspace.id, name=workspace.name),
        stats_scope=OverviewStatsScope(
            window_days=OVERVIEW_WINDOW_DAYS,
            window_started_at=iso_z(window_started_at) or "",
            result_run_scope=OverviewResultRunScope.valid_standard_terminal_runs,
            recent_run_limit=recent_limit,
        ),
        run_stats=OverviewRunStats(
            result_runs=OverviewResultRuns(
                total=result_total,
                by_state=OverviewTerminalStateCounts(**state_counts),
                by_sla_result=OverviewSlaResultCounts(**sla_counts),
            ),
            active_runs=OverviewActiveRuns(total=active_total, **active_counts),
        ),
        recent_runs=_recent_runs(db, workspace_id=workspace.id, recent_limit=recent_limit, now=now),
        resource_summary=_resource_summary(db, workspace_id=workspace.id),
    )
