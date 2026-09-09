from dataclasses import dataclass
from ipaddress import ip_address
import os
import re
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.auth import SystemSetting

LOAD_NODE_API_BASE_URL = "loadNodeApiBaseUrl"
LOAD_NODE_API_BASE_URL_ENV = "SURGEPILOT_NODE_API_BASE_URL"
_DNS_LABEL_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


@dataclass(frozen=True)
class LoadNodeConnectivitySummary:
    effective_url: str | None
    source: str
    readiness: str
    message: str


class LoadNodeApiBaseUrlInvalid(ValueError):
    pass


def validate_load_node_api_base_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LoadNodeApiBaseUrlInvalid("Load Node API Base URL is required.")
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise LoadNodeApiBaseUrlInvalid("URL must be an absolute http or https origin.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise LoadNodeApiBaseUrlInvalid("URL must be an origin and must not include credentials, query, fragment, or a path.")
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host or host in {"localhost", "host.docker.internal"} or "*" in host:
        raise LoadNodeApiBaseUrlInvalid("Host must be reachable from the Load Node network.")
    try:
        parsed_ip = ip_address(host)
    except ValueError:
        if "." not in host or len(host) > 253 or any(_DNS_LABEL_PATTERN.fullmatch(label) is None for label in host.split(".")):
            raise LoadNodeApiBaseUrlInvalid("Host must be an IP address or fully qualified domain name.")
    else:
        if parsed_ip.is_loopback or parsed_ip.is_unspecified or parsed_ip.is_link_local:
            raise LoadNodeApiBaseUrlInvalid("Host must be reachable from the Load Node network.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise LoadNodeApiBaseUrlInvalid("Port is invalid.") from exc
    if port is not None and not 1 <= port <= 65535:
        raise LoadNodeApiBaseUrlInvalid("Port must be between 1 and 65535.")
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parsed.scheme.lower(), netloc, "", "", ""))


def configured_load_node_api_base_url(db: Session) -> str | None:
    row = db.get(SystemSetting, LOAD_NODE_API_BASE_URL)
    return None if row is None or row.value_json is None else str(row.value_json).strip() or None


def env_load_node_api_base_url() -> str | None:
    value = os.environ.get(LOAD_NODE_API_BASE_URL_ENV)
    return value.strip() or None if value is not None else None


def load_node_api_base_url_summary(db: Session) -> LoadNodeConnectivitySummary:
    configured = configured_load_node_api_base_url(db)
    source = "configured" if configured is not None else "env_fallback"
    value = configured if configured is not None else env_load_node_api_base_url()
    if value is None:
        return LoadNodeConnectivitySummary(None, "missing", "missing", "Load Node API Base URL is not configured.")
    try:
        normalized = validate_load_node_api_base_url(value)
    except LoadNodeApiBaseUrlInvalid as exc:
        return LoadNodeConnectivitySummary(value, source, "invalid", str(exc))
    return LoadNodeConnectivitySummary(normalized, source, "ready", "Load Node API Base URL is statically valid.")


def effective_load_node_api_base_url(db: Session) -> str:
    summary = load_node_api_base_url_summary(db)
    if summary.readiness != "ready" or summary.effective_url is None:
        raise AppError("RUN_CONTROL_INVALID_API_BASE_URL", "Load Node API Base URL is missing or invalid.", 400)
    return summary.effective_url
