from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.time import as_utc, utc_now
from app.models.runs import Run, RunMonitoringConfig
from app.schemas.monitoring import MonitoringEmbedResponse, RunMonitoringLinkResponse

MONITORING_SAMPLERS_LIST = ".*"
MONITORING_USE_REGEX = "true"
MONITORING_SUMMARY_ONLY = "false"
MONITORING_SAVE_RESPONSE_BODY_OF_FAILURES = "false"
MONITORING_RESPONSE_BODY_LENGTH = "0"
MONITORING_FLUSH_INTERVAL_MS = "4000"
MONITORING_MAX_BATCH_SIZE = "2000"
MONITORING_THRESHOLD_ERROR_COUNT = "5"


@dataclass(frozen=True)
class MonitoringResolution:
    enabled_for_run: bool
    status: str
    disabled_reason: str | None
    dashboard_uid: str
    grafana_base_path: str
    influxdb_node_write_url: str | None = None
    warnings: tuple[str, ...] = ()


def _iso_z(value) -> str | None:
    if value is None:
        return None
    return as_utc(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _clean_base_path(path: str) -> str:
    stripped = (path or "/grafana").strip() or "/grafana"
    return "/" + stripped.strip("/")


def _settings_ready(settings: Settings) -> bool:
    return all(
        [
            settings.monitoring_influxdb_internal_url,
            settings.monitoring_influxdb_node_write_url,
            settings.monitoring_influxdb_org,
            settings.monitoring_influxdb_bucket,
            settings.monitoring_influxdb_token_configured,
        ]
    )


def _resolve_deployment(settings: Settings | None = None) -> MonitoringResolution:
    settings = settings or get_settings()
    if not settings.monitoring_enabled:
        return MonitoringResolution(
            enabled_for_run=False,
            status="not_configured",
            disabled_reason="not_configured",
            dashboard_uid=settings.monitoring_dashboard_uid,
            grafana_base_path=_clean_base_path(settings.monitoring_grafana_base_path),
        )
    if not _settings_ready(settings):
        return MonitoringResolution(
            enabled_for_run=False,
            status="config_error",
            disabled_reason=None,
            dashboard_uid=settings.monitoring_dashboard_uid,
            grafana_base_path=_clean_base_path(settings.monitoring_grafana_base_path),
            warnings=("monitoring_config_incomplete",),
        )
    return MonitoringResolution(
        enabled_for_run=True,
        status="enabled",
        disabled_reason=None,
        dashboard_uid=settings.monitoring_dashboard_uid,
        grafana_base_path=_clean_base_path(settings.monitoring_grafana_base_path),
        influxdb_node_write_url=settings.monitoring_influxdb_node_write_url,
    )


def create_run_monitoring_snapshot(
    db: Session, *, run: Run, settings: Settings | None = None
) -> RunMonitoringConfig | None:
    if run.run_type == "debug":
        return None
    existing = db.get(RunMonitoringConfig, run.id)
    if existing is not None:
        return existing
    resolved = _resolve_deployment(settings)
    if resolved.status in {"disabled", "not_configured"}:
        return None
    row = RunMonitoringConfig(
        run_id=run.id,
        workspace_id=run.workspace_id,
        status="enabled" if resolved.enabled_for_run else "config_error",
        disabled_reason=None,
        influxdb_node_write_url=resolved.influxdb_node_write_url,
        dashboard_uid=resolved.dashboard_uid,
        grafana_base_path=resolved.grafana_base_path,
        created_at=utc_now(),
    )
    db.add(row)
    db.flush([row])
    return row


def _monitoring_row(db: Session, *, run_id: str) -> RunMonitoringConfig | None:
    return db.scalar(select(RunMonitoringConfig).where(RunMonitoringConfig.run_id == run_id))


def resolve_monitoring_for_run(
    db: Session, *, run: Run, settings: Settings | None = None
) -> MonitoringResolution:
    settings = settings or get_settings()
    if run.run_type == "debug":
        return MonitoringResolution(
            enabled_for_run=False,
            status="disabled",
            disabled_reason="debug_run_not_monitored",
            dashboard_uid=settings.monitoring_dashboard_uid,
            grafana_base_path=_clean_base_path(settings.monitoring_grafana_base_path),
        )
    row = _monitoring_row(db, run_id=run.id)
    if row is None:
        deployment = _resolve_deployment(settings)
        if deployment.status == "disabled":
            return deployment
        return MonitoringResolution(
            enabled_for_run=False,
            status="not_configured",
            disabled_reason="not_configured",
            dashboard_uid=settings.monitoring_dashboard_uid,
            grafana_base_path=_clean_base_path(settings.monitoring_grafana_base_path),
        )
    if row.status == "enabled" and row.influxdb_node_write_url:
        return MonitoringResolution(
            enabled_for_run=True,
            status="enabled",
            disabled_reason=None,
            dashboard_uid=row.dashboard_uid,
            grafana_base_path=_clean_base_path(row.grafana_base_path),
            influxdb_node_write_url=row.influxdb_node_write_url,
        )
    return MonitoringResolution(
        enabled_for_run=False,
        status="config_error",
        disabled_reason=None,
        dashboard_uid=row.dashboard_uid,
        grafana_base_path=_clean_base_path(row.grafana_base_path),
        warnings=("monitoring_config_incomplete",),
    )


def _run_window(run: Run, *, settings: Settings) -> tuple[str, str, list[str]]:
    padding = timedelta(seconds=max(settings.monitoring_time_padding_seconds, 0))
    warnings: list[str] = []
    started = run.started_at or run.created_at
    if run.started_at is None:
        warnings.append("monitoring_started_at_missing")
    start_ms = int((as_utc(started) - padding).timestamp() * 1000)
    if run.ended_at is None:
        return str(start_ms), "now", warnings
    end_ms = int((as_utc(run.ended_at) + padding).timestamp() * 1000)
    return str(start_ms), str(end_ms), warnings


def _default_monitoring_window(
    *, from_: str | None, to: str | None
) -> tuple[str | None, str | None]:
    if from_ or to:
        return from_, to
    start_ms = int((utc_now() - timedelta(minutes=5)).timestamp() * 1000)
    return str(start_ms), "now"


def _grafana_iframe_url(
    *,
    base_path: str,
    dashboard_uid: str,
    dashboard_slug: str,
    run_id: str | None,
    from_: str | None,
    to: str | None,
) -> str:
    query_parts = [urlencode({"orgId": "1"}), "kiosk", urlencode({"theme": "dark"})]
    if run_id:
        query_parts.append(urlencode({"var-runId": run_id}))
    if from_:
        query_parts.append(urlencode({"from": from_}))
    if to:
        query_parts.append(urlencode({"to": to}))
    return f"{base_path}/d/{dashboard_uid}/{dashboard_slug}?{'&'.join(query_parts)}"


def _platform_url(*, run_id: str, from_: str, to: str) -> str:
    return f"/observability/monitoring?{urlencode({'runId': run_id, 'from': from_, 'to': to})}"


def _get_run(db: Session, *, workspace_id: str, run_id: str) -> Run:
    run = db.scalar(select(Run).where(Run.id == run_id, Run.workspace_id == workspace_id))
    if run is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    return run


def get_run_monitoring_link(
    db: Session, *, workspace_id: str, run_id: str, settings: Settings | None = None
) -> RunMonitoringLinkResponse:
    settings = settings or get_settings()
    run = _get_run(db, workspace_id=workspace_id, run_id=run_id)
    resolved = resolve_monitoring_for_run(db, run=run, settings=settings)
    if not resolved.enabled_for_run:
        return RunMonitoringLinkResponse(
            run_id=run.id,
            enabled_for_run=False,
            status=resolved.status,  # type: ignore[arg-type]
            disabled_reason=resolved.disabled_reason,  # type: ignore[arg-type]
            dashboard_uid=resolved.dashboard_uid,
            run_started_at=_iso_z(run.started_at),
            run_ended_at=_iso_z(run.ended_at),
            warnings=list(resolved.warnings),
        )
    grafana_from, grafana_to, warnings = _run_window(run, settings=settings)
    iframe_url = _grafana_iframe_url(
        base_path=resolved.grafana_base_path,
        dashboard_uid=resolved.dashboard_uid,
        dashboard_slug=settings.monitoring_dashboard_slug,
        run_id=run.id,
        from_=grafana_from,
        to=grafana_to,
    )
    return RunMonitoringLinkResponse(
        run_id=run.id,
        enabled_for_run=True,
        status="enabled",
        disabled_reason=None,
        platform_monitoring_url=_platform_url(run_id=run.id, from_=grafana_from, to=grafana_to),
        iframe_url=iframe_url,
        dashboard_uid=resolved.dashboard_uid,
        run_started_at=_iso_z(run.started_at),
        run_ended_at=_iso_z(run.ended_at),
        grafana_from=grafana_from,
        grafana_to=grafana_to,
        warnings=[*warnings, *resolved.warnings],
    )


def get_monitoring_embed(
    db: Session,
    *,
    workspace_id: str,
    run_id: str | None,
    from_: str | None = None,
    to: str | None = None,
    settings: Settings | None = None,
) -> MonitoringEmbedResponse:
    settings = settings or get_settings()
    if run_id:
        link = get_run_monitoring_link(
            db, workspace_id=workspace_id, run_id=run_id, settings=settings
        )
        return MonitoringEmbedResponse(
            enabled=link.enabled_for_run,
            status="ready" if link.enabled_for_run else link.status,  # type: ignore[arg-type]
            iframe_url=link.iframe_url,
            run_id=run_id,
            from_=link.grafana_from,
            to=link.grafana_to,
            dashboard_uid=link.dashboard_uid,
            warnings=link.warnings,
        )
    resolved = _resolve_deployment(settings)
    if not resolved.enabled_for_run:
        return MonitoringEmbedResponse(
            enabled=False,
            status="config_error" if resolved.status == "config_error" else resolved.status,  # type: ignore[arg-type]
            dashboard_uid=resolved.dashboard_uid,
            warnings=list(resolved.warnings),
        )
    grafana_from, grafana_to = _default_monitoring_window(from_=from_, to=to)
    iframe_url = _grafana_iframe_url(
        base_path=resolved.grafana_base_path,
        dashboard_uid=resolved.dashboard_uid,
        dashboard_slug=settings.monitoring_dashboard_slug,
        run_id=None,
        from_=grafana_from,
        to=grafana_to,
    )
    return MonitoringEmbedResponse(
        enabled=True,
        status="ready",
        iframe_url=iframe_url,
        dashboard_uid=resolved.dashboard_uid,
        from_=grafana_from,
        to=grafana_to,
    )


def build_monitoring_properties(
    db: Session,
    *,
    run_id: str,
    node_id: str | None,
    monitoring_token: str | None,
    settings: Settings | None = None,
) -> str | None:
    settings = settings or get_settings()
    run = db.get(Run, run_id)
    row = _monitoring_row(db, run_id=run_id)
    if run is None or run.run_type != "standard" or row is None or row.status != "enabled":
        return None
    if not row.influxdb_node_write_url or not monitoring_token or not node_id:
        raise RuntimeError("Enabled monitoring is missing node write URL, node ID, or token.")
    values = {
        "SURGEPILOT_RUN_ID": run.id,
        "SURGEPILOT_NODE_ID": node_id,
        "SURGEPILOT_INFLUXDB_URL": row.influxdb_node_write_url,
        "SURGEPILOT_INFLUXDB_ORG": settings.monitoring_influxdb_org or "",
        "SURGEPILOT_INFLUXDB_BUCKET": settings.monitoring_influxdb_bucket or "",
        "SURGEPILOT_INFLUXDB_TOKEN": monitoring_token,
        "SURGEPILOT_MONITORING_SAMPLERS_LIST": MONITORING_SAMPLERS_LIST,
        "SURGEPILOT_MONITORING_USE_REGEX": MONITORING_USE_REGEX,
        "SURGEPILOT_MONITORING_SUMMARY_ONLY": MONITORING_SUMMARY_ONLY,
        "SURGEPILOT_MONITORING_SAVE_RESPONSE_BODY_OF_FAILURES": MONITORING_SAVE_RESPONSE_BODY_OF_FAILURES,
        "SURGEPILOT_MONITORING_RESPONSE_BODY_LENGTH": MONITORING_RESPONSE_BODY_LENGTH,
        "SURGEPILOT_MONITORING_FLUSH_INTERVAL_MS": MONITORING_FLUSH_INTERVAL_MS,
        "SURGEPILOT_MONITORING_MAX_BATCH_SIZE": MONITORING_MAX_BATCH_SIZE,
        "SURGEPILOT_MONITORING_THRESHOLD_ERROR_COUNT": MONITORING_THRESHOLD_ERROR_COUNT,
    }
    return "".join(f"{key}={value}\n" for key, value in values.items())
