from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
import os
import re
from socket import inet_aton
from urllib.parse import unquote, urlsplit, urlunsplit

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


def _invalid(message: str) -> LoadNodeApiBaseUrlInvalid:
    return LoadNodeApiBaseUrlInvalid(message)


def _validate_host(host: str) -> str:
    raw = host.strip().lower()
    if not raw:
        raise _invalid("Host is required.")
    if "*" in unquote(raw):
        raise _invalid("Host must not contain wildcard characters.")
    if "%" in raw:
        raise _invalid("Host must be an IP address or fully qualified domain name.")
    try:
        normalized = raw.encode("idna").decode("ascii").rstrip(".")
    except UnicodeError as exc:
        raise _invalid("Host must be an IP address or fully qualified domain name.") from exc
    if normalized == "host.docker.internal":
        raise _invalid("Use an address reachable from the Load Node network.")
    try:
        parsed_ip = ip_address(normalized)
    except ValueError:
        try:
            inet_aton(normalized)
        except OSError:
            pass
        else:
            raise _invalid("Host must use canonical IP address notation.")
        if normalized == "localhost" or "." not in normalized:
            raise _invalid("Host must be an IP address or fully qualified domain name.")
        if len(normalized) > 253 or any(
            _DNS_LABEL_PATTERN.fullmatch(label) is None for label in normalized.split(".")
        ):
            raise _invalid("Host must be an IP address or fully qualified domain name.")
        return normalized
    ip_for_safety_checks = getattr(parsed_ip, "ipv4_mapped", None) or parsed_ip
    if (
        ip_for_safety_checks.is_loopback
        or ip_for_safety_checks.is_unspecified
        or ip_for_safety_checks.is_link_local
    ):
        raise _invalid("Host must be reachable from the Load Node network.")
    return normalized


def validate_load_node_api_base_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid("Load Node API Base URL is required.")
    raw = value.strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise _invalid("URL must be an absolute http or https origin.")
    if parsed.username or parsed.password:
        raise _invalid("URL must not include credentials.")
    if parsed.query or parsed.fragment:
        raise _invalid("URL must not include query or fragment.")
    if parsed.path not in {"", "/"}:
        raise _invalid("URL must be an origin and must not include /api or another path.")
    host = _validate_host(parsed.hostname or "")
    try:
        port = parsed.port
    except ValueError as exc:
        raise _invalid("Port is invalid.") from exc
    if port is not None and (port < 1 or port > 65535):
        raise _invalid("Port must be between 1 and 65535.")
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parsed.scheme.lower(), netloc, "", "", ""))


def configured_load_node_api_base_url(db: Session) -> str | None:
    row = db.get(SystemSetting, LOAD_NODE_API_BASE_URL)
    if row is None:
        return None
    value = row.value_json
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def env_load_node_api_base_url() -> str | None:
    value = os.environ.get(LOAD_NODE_API_BASE_URL_ENV)
    if value is None:
        return None
    text = value.strip()
    return text or None


def load_node_api_base_url_summary(db: Session) -> LoadNodeConnectivitySummary:
    configured = configured_load_node_api_base_url(db)
    if configured is not None:
        return _summary_for_value(configured, source="configured")
    env_value = env_load_node_api_base_url()
    if env_value is not None:
        return _summary_for_value(env_value, source="env_fallback")
    return LoadNodeConnectivitySummary(
        effective_url=None,
        source="missing",
        readiness="missing",
        message="Load Node API Base URL is not configured.",
    )


def _summary_for_value(value: str, *, source: str) -> LoadNodeConnectivitySummary:
    try:
        normalized = validate_load_node_api_base_url(value)
    except LoadNodeApiBaseUrlInvalid as exc:
        return LoadNodeConnectivitySummary(
            effective_url=value,
            source=source,
            readiness="invalid",
            message=str(exc),
        )
    return LoadNodeConnectivitySummary(
        effective_url=normalized,
        source=source,
        readiness="ready",
        message="Load Node API Base URL is statically valid. It has not been tested from a Load Node.",
    )


def effective_load_node_api_base_url(db: Session) -> str:
    summary = load_node_api_base_url_summary(db)
    if summary.readiness != "ready" or summary.effective_url is None:
        raise AppError(
            "RUN_CONTROL_INVALID_API_BASE_URL",
            "Load Node API Base URL is missing or invalid.",
            400,
        )
    return summary.effective_url
