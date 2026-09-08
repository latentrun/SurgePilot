from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import io
import math
from typing import Any, BinaryIO

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ids import new_ulid
from app.core.time import as_utc, utc_now
from app.models.auth import User
from app.models.load_nodes import LoadNode
from app.models.runs import Run, RunArtifact, RunReportSummary, RunSnapshot
from app.schemas.runs import (
    FailureDiagnostics,
    FinalStatsPreview,
    FinalStatsPreviewRow,
    RunActor,
    RunArtifactsSummary,
    RunKpiSummary,
    RunReportDetail,
    RunSnapshotResourceRequest,
    RunSnapshotSummary,
    RunValidityPatchResponse,
    RunVerdict,
)
from app.services.audit import write_audit_event
from app.services.storage import StoredObjectStream, get_storage_client

FINAL_STATS_TOTAL_ROW_MISSING = "FINAL_STATS_TOTAL_ROW_MISSING"
FINAL_STATS_PARSE_FAILED = "FINAL_STATS_PARSE_FAILED"
FINAL_STATS_TOO_LARGE = "FINAL_STATS_TOO_LARGE"
FINAL_STATS_SOURCE_ARTIFACT_MISSING = "FINAL_STATS_SOURCE_ARTIFACT_MISSING"
MAX_FINAL_STATS_BYTES = 2 * 1024 * 1024
MAX_FINAL_STATS_PREVIEW_ROWS = 200
TERMINAL_RUN_STATES = {"finished", "failed", "aborted"}
PUBLIC_ARTIFACT_TYPES = {"taurus_log", "jmeter_log", "final_stats_csv", "run_log", "artifacts_zip"}


@dataclass(frozen=True)
class FinalStatsParseResult:
    parse_status: str
    summary_json: dict[str, Any]
    truncated: bool
    parse_error_code: str | None = None


@dataclass(frozen=True)
class ArtifactDownload:
    artifact: RunArtifact
    stored: StoredObjectStream


def iso_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    return as_utc(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _failed_summary(code: str) -> FinalStatsParseResult:
    return FinalStatsParseResult(
        parse_status="failed",
        summary_json={"schemaVersion": 1, "total": None, "rows": [], "warnings": [code]},
        truncated=False,
        parse_error_code=code,
    )


def _number(raw: Any) -> float | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _count(raw: Any) -> int | None:
    value = _number(raw)
    return int(value) if value is not None else None


def _milliseconds(raw: Any, *, missing: str, invalid: str, warnings: set[str]) -> float | None:
    if raw is None or str(raw).strip() == "":
        warnings.add(missing)
        return None
    value = _number(raw)
    if value is None:
        warnings.add(invalid)
        return None
    return round(value * 1000, 3)


def _metric_row(row: dict[str, Any], warnings: set[str]) -> dict[str, Any]:
    total = _count(row.get("throughput"))
    success = _count(row.get("succ"))
    failed = _count(row.get("fail"))
    if total is None:
        warnings.add("total_requests_invalid")
    if success is None:
        warnings.add("success_requests_invalid")
    if failed is None:
        warnings.add("failed_requests_invalid")
    error_rate = round(failed / total, 6) if total is not None and failed is not None and total > 0 else None
    result: dict[str, Any] = {
        "label": str(row.get("label") or "").strip() or None,
        "totalRequests": total,
        "successRequests": success,
        "failedRequests": failed,
        "errorRate": error_rate,
        "averageResponseTimeMs": _milliseconds(row.get("avg_rt"), missing="average_response_time_missing", invalid="average_response_time_invalid", warnings=warnings),
        "p90Ms": None,
        "p95Ms": None,
        "p99Ms": None,
        "responseCodeCounts": {},
    }
    for column, key in (("perc_90.0", "p90Ms"), ("perc_95.0", "p95Ms"), ("perc_99.0", "p99Ms")):
        if column not in row:
            warnings.add("percentile_column_missing")
        result[key] = _milliseconds(row.get(column), missing="percentile_column_missing", invalid="percentile_value_invalid", warnings=warnings) if column in row else None
    for key, raw in row.items():
        if key.startswith("rc_"):
            value = _count(raw)
            if value is None:
                warnings.add("response_code_count_invalid")
            else:
                result["responseCodeCounts"][key.removeprefix("rc_")] = value
    return result


def parse_final_stats_csv(stream: BinaryIO, *, max_rows: int = MAX_FINAL_STATS_PREVIEW_ROWS, max_bytes: int = MAX_FINAL_STATS_BYTES) -> FinalStatsParseResult:
    try:
        data = stream.read(max_bytes + 1)
        if len(data) > max_bytes:
            return _failed_summary(FINAL_STATS_TOO_LARGE)
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
        if not reader.fieldnames:
            return _failed_summary(FINAL_STATS_PARSE_FAILED)
        total_row: dict[str, Any] | None = None
        rows: list[dict[str, Any]] = []
        truncated = False
        for row in reader:
            if not str(row.get("label") or "").strip() and total_row is None:
                total_row = row
            elif len(rows) < max_rows:
                rows.append(row)
            else:
                truncated = True
        if total_row is None:
            return _failed_summary(FINAL_STATS_TOTAL_ROW_MISSING)
        warnings: set[str] = set()
        return FinalStatsParseResult("parsed", {"schemaVersion": 1, "total": _metric_row(total_row, warnings), "rows": [_metric_row(row, warnings) for row in rows], "warnings": sorted(warnings)}, truncated)
    except (UnicodeDecodeError, csv.Error, OSError):
        return _failed_summary(FINAL_STATS_PARSE_FAILED)


def _summary_query(db: Session, artifact: RunArtifact) -> RunReportSummary | None:
    return db.scalar(select(RunReportSummary).where(RunReportSummary.run_id == artifact.run_id, RunReportSummary.source_artifact_id == artifact.id, RunReportSummary.summary_type == "final_stats"))


def parse_and_store_final_stats_summary(db: Session, *, artifact: RunArtifact, stream: BinaryIO) -> RunReportSummary:
    if artifact.artifact_type != "final_stats_csv":
        raise AppError("INVALID_ARTIFACT_TYPE", "Artifact type is invalid.", 400)
    result = parse_final_stats_csv(stream)
    now = utc_now()
    summary = _summary_query(db, artifact)
    if summary is None:
        summary = RunReportSummary(id=new_ulid(), workspace_id=artifact.workspace_id, run_id=artifact.run_id, source_artifact_id=artifact.id, summary_type="final_stats", summary_json=result.summary_json, truncated=result.truncated, parse_status=result.parse_status, parse_error_code=result.parse_error_code, created_at=now, updated_at=now)
        db.add(summary)
    else:
        summary.summary_json = result.summary_json
        summary.truncated = result.truncated
        summary.parse_status = result.parse_status
        summary.parse_error_code = result.parse_error_code
        summary.updated_at = now
    db.flush()
    return summary


def create_pending_final_stats_summary(db: Session, *, artifact: RunArtifact) -> RunReportSummary:
    if artifact.artifact_type != "final_stats_csv":
        raise AppError("INVALID_ARTIFACT_TYPE", "Artifact type is invalid.", 400)
    summary = _summary_query(db, artifact)
    if summary is None:
        now = utc_now()
        summary = RunReportSummary(id=new_ulid(), workspace_id=artifact.workspace_id, run_id=artifact.run_id, source_artifact_id=artifact.id, summary_type="final_stats", summary_json={"schemaVersion": 1, "total": None, "rows": [], "warnings": []}, truncated=False, parse_status="pending", parse_error_code=None, created_at=now, updated_at=now)
        db.add(summary)
        db.flush()
    return summary


def process_next_pending_final_stats_summary(db: Session) -> int:
    summary = db.scalar(select(RunReportSummary).where(RunReportSummary.summary_type == "final_stats", RunReportSummary.parse_status == "pending").order_by(RunReportSummary.created_at.asc(), RunReportSummary.id.asc()).with_for_update(skip_locked=True).limit(1))
    if summary is None:
        return 0
    artifact = db.scalar(select(RunArtifact).where(RunArtifact.id == summary.source_artifact_id, RunArtifact.run_id == summary.run_id, RunArtifact.workspace_id == summary.workspace_id, RunArtifact.artifact_type == "final_stats_csv", RunArtifact.status == "available"))
    if artifact is None:
        summary.parse_status = "failed"
        summary.parse_error_code = FINAL_STATS_SOURCE_ARTIFACT_MISSING
        summary.summary_json = {"schemaVersion": 1, "total": None, "rows": [], "warnings": [FINAL_STATS_SOURCE_ARTIFACT_MISSING]}
        summary.updated_at = utc_now()
        db.flush()
        return 1
    stored = get_storage_client().get_stream(bucket=get_settings().minio_bucket, object_key=artifact.storage_key)
    try:
        parse_and_store_final_stats_summary(db, artifact=artifact, stream=stored.stream)
    finally:
        close = getattr(stored.stream, "close", None)
        if callable(close):
            close()
    return 1


def _kpi(status: str, artifact: RunArtifact | None, summary: RunReportSummary | None) -> RunKpiSummary:
    if status != "parsed":
        return RunKpiSummary(status=status, source_artifact_id=artifact.id if artifact else None, missing_reasons=["final_stats_missing" if status == "missing" else "summary_pending" if status == "pending" else "summary_parse_failed"])
    total = (summary.summary_json if summary else {}).get("total") or {}
    return RunKpiSummary(status="parsed", source_artifact_id=artifact.id if artifact else None, total_requests=total.get("totalRequests"), failed_requests=total.get("failedRequests"), error_rate=total.get("errorRate"), average_response_time_ms=total.get("averageResponseTimeMs"), p90_ms=total.get("p90Ms"), p95_ms=total.get("p95Ms"), p99_ms=total.get("p99Ms"), throughput_per_second=None, missing_reasons=[])


def _preview(summary: RunReportSummary | None, status: str) -> FinalStatsPreview:
    payload = (summary.summary_json if summary else {}) or {}
    rows = []
    if status == "parsed":
        values = ([payload["total"]] if isinstance(payload.get("total"), dict) else []) + [item for item in payload.get("rows", []) if isinstance(item, dict)]
        rows = [FinalStatsPreviewRow(label=item.get("label"), total_requests=item.get("totalRequests"), success_requests=item.get("successRequests"), failed_requests=item.get("failedRequests"), error_rate=item.get("errorRate"), average_response_time_ms=item.get("averageResponseTimeMs"), p90_ms=item.get("p90Ms"), p95_ms=item.get("p95Ms"), p99_ms=item.get("p99Ms"), response_code_counts=dict(item.get("responseCodeCounts") or {})) for item in values]
    return FinalStatsPreview(status=status, truncated=summary.truncated if summary else False, rows=rows, warnings=list(payload.get("warnings") or []))


def _find_final_stats(db: Session, run_id: str) -> tuple[RunArtifact | None, RunReportSummary | None]:
    artifact = db.scalar(select(RunArtifact).where(RunArtifact.run_id == run_id, RunArtifact.artifact_type == "final_stats_csv", RunArtifact.status == "available").order_by(RunArtifact.created_at.desc(), RunArtifact.id.desc()).limit(1))
    return artifact, _summary_query(db, artifact) if artifact else None


def _duration_ms(run: Run) -> int | None:
    start = run.started_at or run.created_at
    end = run.ended_at
    return max(int((as_utc(end) - as_utc(start)).total_seconds() * 1000), 0) if start and end else None


def _actor(db: Session, user_id: str) -> RunActor:
    user = db.get(User, user_id)
    return RunActor(id=user_id, email=user.email if user else "unknown@example.com")


def _snapshot_summary(snapshot: dict[str, Any], run: Run) -> RunSnapshotSummary:
    return RunSnapshotSummary(schema_version=int(snapshot.get("schemaVersion") or snapshot.get("snapshotVersion") or 1), source_name=(snapshot.get("testPlan") or snapshot.get("scenario") or {}).get("name"), source_revision=snapshot.get("sourceRevision"), env_group_name=(snapshot.get("envGroup") or {}).get("name"), run_mode=(snapshot.get("testPlan") or {}).get("runMode"), scenario_count=len(snapshot.get("scenarioItems") or []) or (1 if snapshot.get("scenario") else 0), scenario_names=[str(item.get("scenarioName")) for item in snapshot.get("scenarioItems", []) if isinstance(item, dict) and item.get("scenarioName")], scenario_items=[], sla_rule_count=len(snapshot.get("slaRules") or []), sla_rules=[], dependency_file_count=len(snapshot.get("dependencyFiles") or []), dependency_file_names=[], env_group_variable_keys=[], resource_request=RunSnapshotResourceRequest(mode="manual", selected_node_id=run.selected_node_id, selected_node_ids=[run.selected_node_id]))


def get_run_report(db: Session, *, workspace_id: str, run_id: str) -> RunReportDetail:
    row = db.execute(select(Run, RunSnapshot).join(RunSnapshot, RunSnapshot.run_id == Run.id, isouter=True).where(Run.id == run_id, Run.workspace_id == workspace_id)).first()
    if row is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    run, snapshot_row = row
    artifact, summary = _find_final_stats(db, run.id)
    status = "missing" if artifact is None else "pending" if summary is None or summary.parse_status == "pending" else "failed" if summary.parse_status == "failed" else "parsed"
    snapshot = snapshot_row.snapshot_json if snapshot_row else {}
    artifacts = db.scalars(select(RunArtifact).where(RunArtifact.run_id == run.id, RunArtifact.status == "available", RunArtifact.artifact_type.in_(PUBLIC_ARTIFACT_TYPES))).all()
    node = db.get(LoadNode, run.selected_node_id)
    return RunReportDetail(id=run.id, verdict=RunVerdict(state=run.state, run_type=run.run_type, source_type=run.source_type, validity=run.validity or ("invalid" if run.run_type == "debug" else "valid"), sla_result=run.sla_result or "not_evaluated", sla_result_reason=run.sla_result_reason, duration_ms=_duration_ms(run), triggered_by=_actor(db, run.triggered_by_user_id), created_at=iso_z(run.created_at) or "", accepted_at=iso_z(run.accepted_at), started_at=iso_z(run.started_at), ended_at=iso_z(run.ended_at), last_heartbeat_at=iso_z(run.last_heartbeat_at), failure_reason=run.failure_reason, failure_message=run.failure_message, forced_convergence=run.forced_convergence, warnings=[]), kpi_summary=_kpi(status, artifact, summary), failure_diagnostics=FailureDiagnostics(failure_reason=run.failure_reason, failure_message=run.failure_message, has_failed_requests_preview=False, notes=[]), final_stats_preview=_preview(summary, status), debug_http_trace=None, snapshot=_snapshot_summary(snapshot, run), allocated_nodes=[], artifacts_summary=RunArtifactsSummary(count=len(artifacts), has_artifacts_zip=any(item.artifact_type == "artifacts_zip" for item in artifacts), has_final_stats_csv=artifact is not None, latest_available_at=iso_z(max((item.created_at for item in artifacts), default=None))))


def update_run_validity(db: Session, *, workspace_id: str, run_id: str, validity: str, actor: User, request: Request | None = None) -> RunValidityPatchResponse:
    if validity not in {"valid", "invalid"}:
        raise AppError("VALIDATION_ERROR", "Validation failed.", 422)
    run = db.scalar(select(Run).where(Run.id == run_id, Run.workspace_id == workspace_id).with_for_update())
    if run is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    old = run.validity or ("invalid" if run.run_type == "debug" else "valid")
    now = utc_now()
    run.validity = validity
    run.validity_updated_by_user_id = actor.id
    run.validity_updated_at = now
    run.updated_at = now
    if old != validity:
        write_audit_event(db, event_type="run.validity_changed", request=request, actor_user_id=actor.id, workspace_id=workspace_id, target_type="run", target_id=run.id, details={"runId": run.id, "workspaceId": workspace_id, "oldValidity": old, "newValidity": validity})
    db.flush()
    return RunValidityPatchResponse(id=run.id, validity=validity, validity_updated_at=iso_z(now) or "", validity_updated_by=RunActor(id=actor.id, email=actor.email))


__all__ = ["FINAL_STATS_TOTAL_ROW_MISSING", "parse_final_stats_csv", "parse_and_store_final_stats_summary", "create_pending_final_stats_summary", "process_next_pending_final_stats_summary", "get_run_report", "update_run_validity"]
