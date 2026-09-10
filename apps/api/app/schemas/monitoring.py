from typing import Literal

from pydantic import Field

from app.schemas.common import ApiSchema


MonitoringEmbedStatus = Literal["ready", "not_configured", "disabled", "config_error"]
RunMonitoringStatus = Literal["not_configured", "disabled", "enabled", "config_error"]
MonitoringDisabledReason = Literal[
    "debug_run_not_monitored", "monitoring_disabled", "not_configured"
]


class MonitoringEmbedResponse(ApiSchema):
    enabled: bool
    status: MonitoringEmbedStatus
    iframe_url: str | None = None
    run_id: str | None = None
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    dashboard_uid: str
    warnings: list[str] = Field(default_factory=list)


class RunMonitoringLinkResponse(ApiSchema):
    run_id: str
    enabled_for_run: bool
    status: RunMonitoringStatus
    disabled_reason: MonitoringDisabledReason | None = None
    platform_monitoring_url: str | None = None
    iframe_url: str | None = None
    dashboard_uid: str
    run_started_at: str | None = None
    run_ended_at: str | None = None
    grafana_from: str | None = None
    grafana_to: str | None = None
    warnings: list[str] = Field(default_factory=list)
