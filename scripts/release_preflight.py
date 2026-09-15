"""Validate tagged-release inputs and select Runtime architectures."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Mapping
from io import StringIO
from ipaddress import ip_address
from pathlib import Path
from socket import inet_aton
from urllib.parse import urlsplit

from dotenv import dotenv_values


MINIMUM_DOCKER_VERSION = "26.0.0"
MINIMUM_COMPOSE_VERSION = "2.27.0"
SEMANTIC_VERSION_PATTERN = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+\Z")
DIGEST_PATTERN = re.compile(r"sha256:[a-f0-9]{64}\Z")
ARCHITECTURES = ("amd64", "arm64")
DNS_LABEL_PATTERN = re.compile(r"(?!-)[a-z0-9-]{1,63}(?<!-)\Z", re.IGNORECASE)
COMPOSE_ONLY_HOSTS = frozenset(
    {
        "localhost",
        "host.docker.internal",
        "api",
        "api-migrate",
        "api-worker",
        "api.surgepilot.test",
        "demo-load-node",
        "grafana",
        "influxdb",
        "minio",
        "minio-init",
        "nginx",
        "postgres",
        "web",
    }
)
LOCAL_ONLY_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class ReleasePreflightError(ValueError):
    """Raised when release startup inputs violate the P2-05 contract."""


def prepare_preview_runtime_directory(path: Path) -> None:
    """Create or validate the private empty host directory mounted by source Preview."""
    if not path.is_absolute():
        raise ReleasePreflightError(f"Preview Runtime directory path must be absolute: {path}")
    try:
        path.mkdir(mode=0o700, parents=True)
    except FileExistsError:
        pass
    except OSError as exc:
        raise ReleasePreflightError(
            f"Preview Runtime directory could not be created: {path}"
        ) from exc

    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ReleasePreflightError(
            f"Preview Runtime directory could not be inspected: {path}"
        ) from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise ReleasePreflightError(
            f"Preview Runtime path must be a real directory, not a file or symlink: {path}"
        )
    if metadata.st_uid != os.geteuid():
        raise ReleasePreflightError(
            f"Preview Runtime directory must be owned by the current host user: {path}"
        )
    if stat.S_IMODE(metadata.st_mode) != 0o700:
        raise ReleasePreflightError(f"Preview Runtime directory permissions must be 0700: {path}")
    try:
        if next(path.iterdir(), None) is not None:
            raise ReleasePreflightError(f"Preview Runtime directory must be empty: {path}")
    except OSError as exc:
        raise ReleasePreflightError(
            f"Preview Runtime directory contents could not be inspected: {path}"
        ) from exc


def normalize_daemon_arch(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"x86_64", "amd64"}:
        return "amd64"
    if normalized in {"aarch64", "arm64"}:
        return "arm64"
    raise ReleasePreflightError(f"unsupported Docker daemon architecture: {value or '<empty>'}")


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = re.search(r"(?:^|[^0-9])v?([0-9]+)\.([0-9]+)\.([0-9]+)", value.strip())
    if match is None:
        raise ReleasePreflightError(f"could not parse version: {value or '<empty>'}")
    return tuple(int(group) for group in match.groups())  # type: ignore[return-value]


def require_minimum_version(name: str, actual: str, minimum: str) -> None:
    try:
        actual_tuple = _version_tuple(actual)
    except ReleasePreflightError as exc:
        raise ReleasePreflightError(
            f"could not parse {name} version: {actual or '<empty>'}"
        ) from exc
    if actual_tuple < _version_tuple(minimum):
        raise ReleasePreflightError(f"{name} {minimum} or newer is required; found {actual}")


def _forced_platform_arch(value: str) -> str | None:
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized in {"linux/amd64", "amd64"}:
        return "amd64"
    if normalized in {"linux/arm64", "linux/arm64/v8", "arm64"}:
        return "arm64"
    raise ReleasePreflightError(
        "DOCKER_DEFAULT_PLATFORM must be unset, linux/amd64, or linux/arm64 for SurgePilot"
    )


def resolve_runtime_architectures(
    *,
    configured: str,
    demo_enabled: bool,
    daemon_arch: str,
    forced_platform: str,
) -> tuple[str, ...]:
    normalized_daemon = normalize_daemon_arch(daemon_arch)
    forced_arch = _forced_platform_arch(forced_platform) if demo_enabled else None
    if forced_arch is not None and forced_arch != normalized_daemon:
        raise ReleasePreflightError(
            "forced Docker platform conflicts with the Docker daemon architecture for the "
            "default Demo Load Node flow"
        )
    selected = configured.strip().lower()
    if selected == "auto":
        return (normalized_daemon,)

    values = tuple(part.strip() for part in selected.split(","))
    if not values or any(value not in ARCHITECTURES for value in values):
        raise ReleasePreflightError(
            "SURGEPILOT_RUNTIME_ARCHITECTURES must be auto, amd64, arm64, or amd64,arm64"
        )
    if len(set(values)) != len(values) or values not in {
        ("amd64",),
        ("arm64",),
        ("amd64", "arm64"),
    }:
        raise ReleasePreflightError(
            "SURGEPILOT_RUNTIME_ARCHITECTURES must be auto, amd64, arm64, or amd64,arm64"
        )
    if demo_enabled and normalized_daemon not in values:
        raise ReleasePreflightError(
            "SURGEPILOT_RUNTIME_ARCHITECTURES must include the Docker daemon architecture when "
            "the Demo Load Node is enabled"
        )
    return values


def _validate_origin(value: str, *, name: str) -> None:
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise ReleasePreflightError(f"{name} must not contain ASCII control characters")
    try:
        parsed = urlsplit(value.strip())
    except ValueError as exc:
        raise ReleasePreflightError(f"{name} must be an absolute http or https origin") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ReleasePreflightError(f"{name} must be an absolute http or https origin")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ReleasePreflightError(f"{name} must use a valid TCP port from 1 to 65535") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ReleasePreflightError(f"{name} must use a valid TCP port from 1 to 65535")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ReleasePreflightError(f"{name} must not contain credentials, query, or fragment")
    if parsed.path not in {"", "/"}:
        raise ReleasePreflightError(f"{name} must not contain a path")


def _origin_is_local_only(value: str) -> bool:
    try:
        host = urlsplit(value).hostname or ""
    except ValueError:
        return False
    return host.lower().rstrip(".") in LOCAL_ONLY_HOSTS


def _reject_legacy_ipv4_notation(host: str, *, name: str) -> None:
    try:
        inet_aton(host)
    except OSError:
        return
    raise ReleasePreflightError(f"{name} must use canonical IPv4 address notation")


def _validate_external_origin(value: str, *, name: str, allow_local_only: bool = False) -> None:
    _validate_origin(value, name=name)
    host = (urlsplit(value).hostname or "").lower().rstrip(".")
    if allow_local_only and host in LOCAL_ONLY_HOSTS:
        return
    if host in COMPOSE_ONLY_HOSTS:
        raise ReleasePreflightError(f"{name} must be reachable from external Load Nodes")
    try:
        address = ip_address(host)
    except ValueError:
        _reject_legacy_ipv4_notation(host, name=name)
        try:
            ascii_host = host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ReleasePreflightError(f"{name} must use a valid DNS hostname") from exc
        if ascii_host in COMPOSE_ONLY_HOSTS:
            raise ReleasePreflightError(f"{name} must be reachable from external Load Nodes")
        try:
            ip_address(ascii_host)
        except ValueError:
            _reject_legacy_ipv4_notation(ascii_host, name=name)
        else:
            raise ReleasePreflightError(f"{name} must use canonical IP address notation")
        if len(ascii_host) > 253 or any(
            DNS_LABEL_PATTERN.fullmatch(label) is None for label in ascii_host.split(".")
        ):
            raise ReleasePreflightError(
                f"{name} must use a valid DNS hostname reachable from external Load Nodes"
            )
    else:
        safety_address = getattr(address, "ipv4_mapped", None) or address
        if (
            safety_address.is_loopback
            or safety_address.is_unspecified
            or safety_address.is_link_local
            or safety_address.is_multicast
        ):
            raise ReleasePreflightError(
                f"{name} must use a final origin reachable from external Load Nodes"
            )


def validate_external_node_urls(environ: Mapping[str, str]) -> None:
    api_value = environ.get("SURGEPILOT_NODE_API_BASE_URL", "").strip()
    influx_value = environ.get("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "").strip()
    if bool(api_value) != bool(influx_value):
        raise ReleasePreflightError(
            "SURGEPILOT_NODE_API_BASE_URL and SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL "
            "must be set together for external Load Nodes"
        )
    if api_value:
        _validate_external_origin(api_value, name="SURGEPILOT_NODE_API_BASE_URL")
        _validate_external_origin(
            influx_value, name="SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"
        )


def normalize_lan_host(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ReleasePreflightError("LAN host or IP is required")
    if "%" in raw:
        raise ReleasePreflightError("LAN host or IP must not use an IPv6 zone identifier")

    bracketed = raw.startswith("[") or raw.endswith("]")
    if bracketed:
        if not (raw.startswith("[") and raw.endswith("]")):
            raise ReleasePreflightError("LAN IPv6 brackets must be balanced")
        inner = raw[1:-1]
        if not inner or "[" in inner or "]" in inner:
            raise ReleasePreflightError("LAN IPv6 input must use at most one bracket pair")
        try:
            address = ip_address(inner)
        except ValueError as exc:
            raise ReleasePreflightError("bracketed LAN host must be an IPv6 address") from exc
        if address.version != 6:
            raise ReleasePreflightError("bracketed LAN host must be an IPv6 address")
    else:
        if "[" in raw or "]" in raw:
            raise ReleasePreflightError("LAN IPv6 brackets must be balanced")
        try:
            address = ip_address(raw)
        except ValueError:
            normalized = raw.lower().rstrip(".")
            _reject_legacy_ipv4_notation(normalized, name="LAN host")
            if normalized == "localhost":
                return normalized
            if normalized in COMPOSE_ONLY_HOSTS:
                raise ReleasePreflightError("LAN host must be reachable from external Load Nodes")
            try:
                ascii_host = normalized.encode("idna").decode("ascii")
            except UnicodeError as exc:
                raise ReleasePreflightError("LAN host must be a valid DNS hostname") from exc
            if ascii_host in COMPOSE_ONLY_HOSTS:
                raise ReleasePreflightError("LAN host must be reachable from external Load Nodes")
            try:
                ip_address(ascii_host)
            except ValueError:
                _reject_legacy_ipv4_notation(ascii_host, name="LAN host")
            else:
                raise ReleasePreflightError("LAN host must use canonical IP address notation")
            if (
                not ascii_host
                or len(ascii_host) > 253
                or any(
                    DNS_LABEL_PATTERN.fullmatch(label) is None for label in ascii_host.split(".")
                )
            ):
                raise ReleasePreflightError("LAN host must be a valid DNS hostname")
            return ascii_host.lower()

    safety_address = getattr(address, "ipv4_mapped", None) or address
    if safety_address.is_loopback:
        if str(address) == "127.0.0.1":
            return "127.0.0.1"
        if str(address) == "::1":
            return "[::1]"
        raise ReleasePreflightError(
            "LAN host must use localhost, 127.0.0.1, or ::1 for explicit local-only access"
        )
    if safety_address.is_unspecified or safety_address.is_link_local or safety_address.is_multicast:
        raise ReleasePreflightError("LAN host must be reachable from external Load Nodes")
    if address.version == 6:
        return f"[{address.compressed}]"
    return str(address)


def _port(value: str, *, name: str) -> int:
    normalized = value.strip()
    if not normalized.isdecimal():
        raise ReleasePreflightError(f"{name} must be an integer from 1 to 65535")
    parsed = int(normalized)
    if not 1 <= parsed <= 65535:
        raise ReleasePreflightError(f"{name} must be an integer from 1 to 65535")
    return parsed


def normalize_release_bootstrap(
    *,
    host: str,
    http_port: str,
    influx_port: str,
    runtime_architectures: str,
    daemon_arch: str,
    forced_platform: str,
) -> dict[str, str]:
    normalized_host = normalize_lan_host(host)
    normalized_http_port = _port(http_port, name="HTTP port")
    normalized_influx_port = _port(influx_port, name="InfluxDB node-write port")
    if normalized_http_port == normalized_influx_port:
        raise ReleasePreflightError("HTTP port and InfluxDB node-write port must be distinct")
    configured = runtime_architectures.strip().lower()
    resolve_runtime_architectures(
        configured=configured,
        demo_enabled=False,
        daemon_arch=daemon_arch,
        forced_platform=forced_platform,
    )
    return {
        "SURGEPILOT_HTTP_PORT": str(normalized_http_port),
        "SURGEPILOT_NODE_API_BASE_URL": (f"http://{normalized_host}:{normalized_http_port}"),
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": str(normalized_influx_port),
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": (
            f"http://{normalized_host}:{normalized_influx_port}"
        ),
        "SURGEPILOT_DEMO_LOAD_NODE_ENABLED": "false",
        "SURGEPILOT_RUNTIME_ARCHITECTURES": configured,
        "SESSION_COOKIE_SECURE": "false",
    }


REQUIRED_RELEASE_ENVIRONMENT_KEYS = (
    "SURGEPILOT_HTTP_PORT",
    "SURGEPILOT_NODE_API_BASE_URL",
    "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT",
    "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL",
    "SURGEPILOT_DEMO_LOAD_NODE_ENABLED",
    "SURGEPILOT_RUNTIME_ARCHITECTURES",
    "SESSION_COOKIE_SECURE",
)

RELEASE_ENVIRONMENT_DESCRIPTION_KEYS = (
    "SURGEPILOT_CONFIG_MODE",
    "SURGEPILOT_CONFIG_HOST",
    "SURGEPILOT_HTTP_PORT",
    "SURGEPILOT_NODE_API_BASE_URL",
    "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT",
    "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL",
    "SURGEPILOT_RUNTIME_ARCHITECTURES",
    "SURGEPILOT_SELECTED_RUNTIME_ARCHITECTURES",
    "SURGEPILOT_DEMO_LOAD_NODE_ENABLED",
    "SURGEPILOT_ENV_SHA256",
)


def validate_release_environment(
    environ: Mapping[str, str], *, daemon_arch: str, forced_platform: str
) -> tuple[str, ...]:
    values: dict[str, str] = {}
    for key in REQUIRED_RELEASE_ENVIRONMENT_KEYS:
        value = environ.get(key)
        if value is None or not value.strip():
            raise ReleasePreflightError(f"existing .env is missing required {key}")
        values[key] = value.strip()

    http_port = _port(values["SURGEPILOT_HTTP_PORT"], name="SURGEPILOT_HTTP_PORT")
    influx_port = _port(
        values["SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT"],
        name="SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT",
    )
    if http_port == influx_port:
        raise ReleasePreflightError(
            "SURGEPILOT_HTTP_PORT and SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT must be distinct"
        )

    cookie_secure = _bool(values["SESSION_COOKIE_SECURE"], name="SESSION_COOKIE_SECURE")
    demo_enabled = _bool(
        values["SURGEPILOT_DEMO_LOAD_NODE_ENABLED"],
        name="SURGEPILOT_DEMO_LOAD_NODE_ENABLED",
    )
    api_url = values["SURGEPILOT_NODE_API_BASE_URL"]
    influx_url = values["SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"]
    if demo_enabled and (_origin_is_local_only(api_url) or _origin_is_local_only(influx_url)):
        raise ReleasePreflightError(
            "Demo Load Node requires non-loopback API and InfluxDB origins reachable from its "
            "container"
        )
    allow_local_only = not demo_enabled and not cookie_secure
    _validate_external_origin(
        api_url,
        name="SURGEPILOT_NODE_API_BASE_URL",
        allow_local_only=allow_local_only,
    )
    _validate_external_origin(
        influx_url,
        name="SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL",
        allow_local_only=allow_local_only,
    )
    if cookie_secure:
        if urlsplit(api_url).scheme != "https":
            raise ReleasePreflightError(
                "SURGEPILOT_NODE_API_BASE_URL must use https when SESSION_COOKIE_SECURE=true"
            )
    else:
        api = urlsplit(api_url)
        influx = urlsplit(influx_url)
        if api.scheme != "http" or influx.scheme != "http":
            raise ReleasePreflightError(
                "direct LAN node-facing origins must use http when SESSION_COOKIE_SECURE=false"
            )
        if api.hostname != influx.hostname:
            raise ReleasePreflightError(
                "direct LAN API and InfluxDB origins must use the same host"
            )
        if api.port != http_port:
            raise ReleasePreflightError(
                "SURGEPILOT_NODE_API_BASE_URL port must match SURGEPILOT_HTTP_PORT"
            )
        if influx.port != influx_port:
            raise ReleasePreflightError(
                "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL port must match "
                "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT"
            )

    return resolve_runtime_architectures(
        configured=values["SURGEPILOT_RUNTIME_ARCHITECTURES"],
        demo_enabled=demo_enabled,
        daemon_arch=daemon_arch,
        forced_platform=forced_platform,
    )


def describe_release_environment(
    root: Path, *, daemon_arch: str, forced_platform: str
) -> dict[str, str]:
    try:
        env_bytes = (root / ".env").read_bytes()
    except OSError as exc:
        raise ReleasePreflightError(f"cannot read existing .env: {exc}") from exc
    try:
        text = env_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReleasePreflightError("existing .env must be valid UTF-8") from exc

    parsed = dotenv_values(stream=StringIO(text))
    values = {key: value for key, value in parsed.items() if value is not None}
    selected = validate_release_environment(
        values,
        daemon_arch=daemon_arch,
        forced_platform=forced_platform,
    )
    cookie_secure = _bool(values["SESSION_COOKIE_SECURE"], name="SESSION_COOKIE_SECURE")
    config_host = ""
    if not cookie_secure:
        config_host = urlsplit(values["SURGEPILOT_NODE_API_BASE_URL"].strip()).hostname or ""
        try:
            if ip_address(config_host).version == 6:
                config_host = f"[{config_host}]"
        except ValueError:
            pass

    return {
        "SURGEPILOT_CONFIG_MODE": ("advanced_https" if cookie_secure else "direct_lan_http"),
        "SURGEPILOT_CONFIG_HOST": config_host,
        "SURGEPILOT_HTTP_PORT": values["SURGEPILOT_HTTP_PORT"].strip(),
        "SURGEPILOT_NODE_API_BASE_URL": values["SURGEPILOT_NODE_API_BASE_URL"].strip(),
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": values[
            "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT"
        ].strip(),
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": values[
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"
        ].strip(),
        "SURGEPILOT_RUNTIME_ARCHITECTURES": values["SURGEPILOT_RUNTIME_ARCHITECTURES"].strip(),
        "SURGEPILOT_SELECTED_RUNTIME_ARCHITECTURES": ",".join(selected),
        "SURGEPILOT_DEMO_LOAD_NODE_ENABLED": values["SURGEPILOT_DEMO_LOAD_NODE_ENABLED"].strip(),
        "SURGEPILOT_ENV_SHA256": hashlib.sha256(env_bytes).hexdigest(),
    }


def _runtime_asset_names(arch: str, version: str) -> tuple[str, str, str]:
    prefix = f"surgepilot-runtime-linux-{arch}-{version}"
    return f"{prefix}.tar.gz", f"{prefix}.tar.gz.sha256", f"{prefix}.manifest.json"


def load_release_manifest(root: Path, *, expected_version: str) -> dict[str, object]:
    path = root / "release-manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleasePreflightError(f"cannot read release manifest: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != 1:
        raise ReleasePreflightError("release manifest schemaVersion must be 1")
    version = manifest.get("version")
    if version != expected_version:
        raise ReleasePreflightError(
            f"release manifest version mismatch: expected {expected_version}, found {version}"
        )
    if not SEMANTIC_VERSION_PATTERN.fullmatch(expected_version):
        raise ReleasePreflightError("release version must use exact vX.Y.Z form")
    revision = manifest.get("revision")
    if not isinstance(revision, str) or re.fullmatch(r"[a-f0-9]{40}", revision) is None:
        raise ReleasePreflightError("release manifest revision must be a full Git commit SHA")

    images = manifest.get("images")
    expected_images = {
        "api": "ghcr.io/latentrun/surgepilot-api",
        "web": "ghcr.io/latentrun/surgepilot-web",
        "demoNode": "ghcr.io/latentrun/surgepilot-demo-node",
    }
    if not isinstance(images, dict):
        raise ReleasePreflightError("release manifest images are missing")
    for key, repository in expected_images.items():
        entry = images.get(key)
        if not isinstance(entry, dict) or entry.get("repository") != repository:
            raise ReleasePreflightError(f"release manifest image repository mismatch for {key}")
        digest = entry.get("digest")
        if not isinstance(digest, str) or DIGEST_PATTERN.fullmatch(digest) is None:
            raise ReleasePreflightError(f"release manifest image digest is invalid for {key}")

    runtimes = manifest.get("runtimes")
    if not isinstance(runtimes, dict):
        raise ReleasePreflightError("release manifest runtimes are missing")
    for arch in ARCHITECTURES:
        entry = runtimes.get(arch)
        if not isinstance(entry, dict):
            raise ReleasePreflightError(f"release manifest Runtime entry is missing for {arch}")
        archive, sidecar, runtime_manifest = _runtime_asset_names(arch, expected_version)
        expected_names = {
            "archive": archive,
            "sha256Sidecar": sidecar,
            "manifest": runtime_manifest,
        }
        for field, expected in expected_names.items():
            if entry.get(field) != expected:
                raise ReleasePreflightError(f"release manifest Runtime {field} mismatch for {arch}")
        digest = entry.get("sha256")
        if not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
            raise ReleasePreflightError(f"release manifest Runtime digest is invalid for {arch}")
    return manifest


def _environment(root: Path) -> dict[str, str]:
    values = dotenv_values(root / ".env")
    return {key: value for key, value in values.items() if value is not None}


def _bool(value: str, *, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ReleasePreflightError(f"{name} must be true or false")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--root", required=True, type=Path)
    preflight.add_argument("--expected-version", required=True)
    preflight.add_argument("--engine-version", required=True)
    preflight.add_argument("--compose-version", required=True)
    preflight.add_argument("--daemon-arch", required=True)

    select = subparsers.add_parser("select-runtime")
    select.add_argument("--root", required=True, type=Path)
    select.add_argument("--expected-version", required=True)
    select.add_argument("--daemon-arch", required=True)
    select.add_argument("--forced-platform", default="")
    describe = subparsers.add_parser("describe-release")
    describe.add_argument("--root", required=True, type=Path)
    describe.add_argument("--expected-version", required=True)
    describe.add_argument("--daemon-arch", required=True)
    describe.add_argument("--forced-platform", default="")
    validate_runtime = subparsers.add_parser("validate-runtime")
    validate_runtime.add_argument("--configured", required=True)
    validate_runtime.add_argument("--demo-enabled", required=True)
    validate_runtime.add_argument("--daemon-arch", required=True)
    validate_runtime.add_argument("--forced-platform", default="")
    normalize_bootstrap = subparsers.add_parser("normalize-bootstrap")
    normalize_bootstrap.add_argument("--host", required=True)
    normalize_bootstrap.add_argument("--http-port", required=True)
    normalize_bootstrap.add_argument("--influx-port", required=True)
    normalize_bootstrap.add_argument("--runtime-architectures", required=True)
    normalize_bootstrap.add_argument("--daemon-arch", required=True)
    normalize_bootstrap.add_argument("--forced-platform", default="")
    subparsers.add_parser("validate-external")
    prepare_preview_runtime = subparsers.add_parser("prepare-preview-runtime")
    prepare_preview_runtime.add_argument("--path", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "validate-external":
            validate_external_node_urls(os.environ)
            return 0
        if args.command == "prepare-preview-runtime":
            prepare_preview_runtime_directory(args.path)
            return 0
        if args.command == "validate-runtime":
            resolve_runtime_architectures(
                configured=args.configured,
                demo_enabled=_bool(
                    args.demo_enabled,
                    name="SURGEPILOT_DEMO_LOAD_NODE_ENABLED",
                ),
                daemon_arch=args.daemon_arch,
                forced_platform=args.forced_platform,
            )
            return 0
        if args.command == "normalize-bootstrap":
            values = normalize_release_bootstrap(
                host=args.host,
                http_port=args.http_port,
                influx_port=args.influx_port,
                runtime_architectures=args.runtime_architectures,
                daemon_arch=args.daemon_arch,
                forced_platform=args.forced_platform,
            )
            for key in REQUIRED_RELEASE_ENVIRONMENT_KEYS:
                print(f"{key}={values[key]}")
            return 0
        load_release_manifest(args.root, expected_version=args.expected_version)
        if args.command == "preflight":
            require_minimum_version("Docker Engine", args.engine_version, MINIMUM_DOCKER_VERSION)
            require_minimum_version("Docker Compose", args.compose_version, MINIMUM_COMPOSE_VERSION)
            normalize_daemon_arch(args.daemon_arch)
            return 0
        if args.command == "describe-release":
            description = describe_release_environment(
                args.root,
                daemon_arch=args.daemon_arch,
                forced_platform=args.forced_platform,
            )
            for key in RELEASE_ENVIRONMENT_DESCRIPTION_KEYS:
                print(f"{key}={description[key]}")
            return 0

        environ = _environment(args.root)
        selected = validate_release_environment(
            environ,
            daemon_arch=args.daemon_arch,
            forced_platform=args.forced_platform,
        )
        print(",".join(selected))
        return 0
    except ReleasePreflightError as exc:
        print(f"Release preflight failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
