from __future__ import annotations

import argparse
import base64
import binascii
from collections.abc import Callable, Mapping, Sequence
import errno
from ipaddress import ip_address
import json
import os
import re
import socket
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit

API_URL_ENV = "SURGEPILOT_NODE_API_BASE_URL"
API_PORT_ENV = "SURGEPILOT_API_HOST_PORT"
INFLUXDB_URL_ENV = "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"
INFLUXDB_PORT_ENV = "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT"
SSH_CREDENTIAL_ENCRYPTION_KEY_ENV = "SSH_CREDENTIAL_ENCRYPTION_KEY"
_DNS_LABEL_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_COMPOSE_HOST_PORT_PATTERN = re.compile(r"[0-9]+\Z")


class NodeFacingStartupError(ValueError):
    pass


def validate_required_environment(environ: Mapping[str, str]) -> None:
    value = environ.get(SSH_CREDENTIAL_ENCRYPTION_KEY_ENV, "")
    if not value.strip():
        raise NodeFacingStartupError(f"{SSH_CREDENTIAL_ENCRYPTION_KEY_ENV} is required.")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise NodeFacingStartupError(
            f"{SSH_CREDENTIAL_ENCRYPTION_KEY_ENV} must be valid base64 encoding for 32 bytes."
        ) from exc
    if len(decoded) != 32:
        raise NodeFacingStartupError(
            f"{SSH_CREDENTIAL_ENCRYPTION_KEY_ENV} must decode to exactly 32 bytes."
        )


def _safe_publish_address(value: str) -> str | None:
    try:
        address = ip_address(value.strip())
    except ValueError:
        return None
    if address.is_loopback or address.is_unspecified or address.is_link_local:
        return None
    return address.compressed


def discover_publish_addresses(
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[str]:
    candidates: set[str] = set()
    for family_args, fallback_destination in (([], "192.0.2.1"), (["-6"], "2001:db8::1")):
        command_prefix = ["ip", *family_args, "-json", "route"]
        try:
            result = run(
                [*command_prefix, "show", "table", "all"],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            routes = json.loads(result.stdout) if result.returncode == 0 else []
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            continue
        default_routes: list[dict[str, object]] = []
        for route in routes:
            if not isinstance(route, dict) or route.get("dst") != "default":
                continue
            if str(route.get("type") or "unicast") != "unicast":
                continue
            if not str(route.get("prefsrc") or route.get("src") or route.get("dev") or "").strip():
                continue
            default_routes.append(route)
        if len(default_routes) > 1 and any(
            not str(route.get("prefsrc") or route.get("src") or "").strip()
            for route in default_routes
        ):
            # `ip route get` cannot select an arbitrary policy table. Resolving more than one
            # source-less default route without its rule context could collapse distinct source
            # addresses into one candidate, so require explicit final URLs instead.
            return []
        for route in default_routes:
            candidate = _safe_publish_address(str(route.get("prefsrc") or route.get("src") or ""))
            if candidate is not None:
                candidates.add(candidate)
                continue
            device = str(route.get("dev") or "").strip()
            destination = fallback_destination
            if not device:
                continue
            try:
                source_result = run(
                    [*command_prefix, "get", destination, "oif", device],
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                source_routes = (
                    json.loads(source_result.stdout) if source_result.returncode == 0 else []
                )
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                continue
            for source_route in source_routes:
                if not isinstance(source_route, dict):
                    continue
                source = _safe_publish_address(
                    str(source_route.get("prefsrc") or source_route.get("src") or "")
                )
                if source is not None:
                    candidates.add(source)
    return sorted(candidates)


def _port(environ: Mapping[str, str], name: str, default: int) -> int:
    raw = environ.get(name)
    if raw is None or raw == "":
        return default
    if _COMPOSE_HOST_PORT_PATTERN.fullmatch(raw) is None:
        raise NodeFacingStartupError(
            f"{name} must use decimal digits without signs, separators, or whitespace."
        )
    value = int(raw)
    if value < 1 or value > 65535:
        raise NodeFacingStartupError(f"{name} must be between 1 and 65535.")
    return value


def _effective_publish_port_environment(environ: Mapping[str, str]) -> dict[str, str]:
    return {
        API_PORT_ENV: str(_port(environ, API_PORT_ENV, 8000)),
        INFLUXDB_PORT_ENV: str(_port(environ, INFLUXDB_PORT_ENV, 8086)),
    }


def _origin(value: str, *, name: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise NodeFacingStartupError(f"{name} must be an absolute http or https origin.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise NodeFacingStartupError(f"{name} must be an origin without credentials or query data.")
    if parsed.path not in {"", "/"}:
        raise NodeFacingStartupError(f"{name} must not include /api or another path.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise NodeFacingStartupError(f"{name} contains an invalid port.") from exc
    host = parsed.hostname
    if not host:
        raise NodeFacingStartupError(f"{name} must include a host.")
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parsed.scheme.lower(), netloc, "", "", ""))


def _api_origin(value: str) -> str:
    normalized = _origin(value, name=API_URL_ENV)
    parsed = urlsplit(normalized)
    raw_host = (parsed.hostname or "").strip().lower()
    if "*" in raw_host or "%" in raw_host:
        raise NodeFacingStartupError(
            f"{API_URL_ENV} host must be a canonical IP address or fully qualified domain name."
        )
    try:
        host = raw_host.encode("idna").decode("ascii").rstrip(".")
    except UnicodeError as exc:
        raise NodeFacingStartupError(
            f"{API_URL_ENV} host must be a canonical IP address or fully qualified domain name."
        ) from exc
    if host == "host.docker.internal":
        raise NodeFacingStartupError(
            f"{API_URL_ENV} must use an address reachable from the Load Node network."
        )
    try:
        parsed_ip = ip_address(host)
    except ValueError:
        try:
            socket.inet_aton(host)
        except OSError:
            pass
        else:
            raise NodeFacingStartupError(f"{API_URL_ENV} must use canonical IP notation.")
        if host == "localhost" or "." not in host:
            raise NodeFacingStartupError(
                f"{API_URL_ENV} host must be a canonical IP address or fully qualified domain name."
            )
        if len(host) > 253 or any(
            _DNS_LABEL_PATTERN.fullmatch(label) is None for label in host.split(".")
        ):
            raise NodeFacingStartupError(
                f"{API_URL_ENV} host must be a canonical IP address or fully qualified domain name."
            )
    else:
        safety_ip = getattr(parsed_ip, "ipv4_mapped", None) or parsed_ip
        if safety_ip.is_loopback or safety_ip.is_unspecified or safety_ip.is_link_local:
            raise NodeFacingStartupError(
                f"{API_URL_ENV} must use an address reachable from the Load Node network."
            )
    netloc = f"[{host}]" if ":" in host else host
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, "", "", ""))


def _derived_origin(address: str, port: int) -> str:
    host = f"[{address}]" if ":" in address else address
    return f"http://{host}:{port}"


def _unavailable_port_families(port: int) -> set[str]:
    families = (
        ("ipv4", socket.AF_INET, ("0.0.0.0", port)),
        ("ipv6", socket.AF_INET6, ("::", port)),
    )
    unavailable: set[str] = set()
    for family_name, family, address in families:
        try:
            with socket.socket(family, socket.SOCK_STREAM) as listener:
                if family == socket.AF_INET6:
                    listener.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                listener.bind(address)
        except OSError as exc:
            if family == socket.AF_INET6 and exc.errno in {
                errno.EAFNOSUPPORT,
                errno.EADDRNOTAVAIL,
                errno.ENOPROTOOPT,
            }:
                continue
            unavailable.add(family_name)
    return unavailable


def _published_families_from_compose_ps(
    output: str, container_port: int, host_port: int
) -> set[str]:
    rendered = output.strip()
    if not rendered:
        return set()
    try:
        payload = json.loads(rendered)
        records = payload if isinstance(payload, list) else [payload]
    except json.JSONDecodeError:
        records = []
        for line in rendered.splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    families: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        for publisher in record.get("Publishers") or []:
            if not isinstance(publisher, dict):
                continue
            try:
                if int(publisher.get("TargetPort")) != container_port:
                    continue
                if int(publisher.get("PublishedPort")) != host_port:
                    continue
                parsed = ip_address(str(publisher.get("URL") or ""))
            except (TypeError, ValueError):
                continue
            families.add("ipv4" if parsed.version == 4 else "ipv6")
    return families


def _compose_owned_families(service: str, container_port: int, host_port: int) -> set[str]:
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "infra/docker/docker-compose.yml",
                "ps",
                "--format",
                "json",
                service,
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return set()
    if result.returncode != 0 or not result.stdout.strip():
        return set()
    return _published_families_from_compose_ps(result.stdout, container_port, host_port)


def validate_publish_ports(
    environ: Mapping[str, str],
    *,
    unavailable_families: Callable[[int], set[str]] = _unavailable_port_families,
    compose_owned_families: Callable[[str, int, int], set[str]] = _compose_owned_families,
) -> None:
    checks = (
        (API_PORT_ENV, _port(environ, API_PORT_ENV, 8000), "api", 8000),
        (INFLUXDB_PORT_ENV, _port(environ, INFLUXDB_PORT_ENV, 8086), "influxdb", 8086),
    )
    if checks[0][1] == checks[1][1]:
        raise NodeFacingStartupError(
            f"{API_PORT_ENV} and {INFLUXDB_PORT_ENV} must use different host ports."
        )
    for name, host_port, service, container_port in checks:
        unavailable = unavailable_families(host_port)
        if not unavailable:
            continue
        foreign = unavailable - compose_owned_families(service, container_port, host_port)
        if not foreign:
            continue
        raise NodeFacingStartupError(
            f"{name}={host_port} is already in use by another process. "
            f"Conflicting address families: {', '.join(sorted(foreign))}. "
            "Choose an available published port before starting SurgePilot."
        )


def resolve_node_facing_environment(
    environ: Mapping[str, str],
    *,
    discover: Callable[[], list[str]] = discover_publish_addresses,
) -> dict[str, str]:
    api_url = environ.get(API_URL_ENV, "").strip()
    influxdb_url = environ.get(INFLUXDB_URL_ENV, "").strip()
    if api_url and influxdb_url:
        return {
            API_URL_ENV: _api_origin(api_url),
            INFLUXDB_URL_ENV: _origin(influxdb_url, name=INFLUXDB_URL_ENV),
        }

    candidates = discover()
    if len(candidates) != 1:
        rendered = "none" if not candidates else ", ".join(candidates)
        raise NodeFacingStartupError(
            "Could not select one host publish address "
            f"(candidates: {rendered}). Set the final URL overrides "
            f"{API_URL_ENV} and {INFLUXDB_URL_ENV}."
        )
    address = candidates[0]
    return {
        API_URL_ENV: (
            _api_origin(api_url)
            if api_url
            else _derived_origin(address, _port(environ, API_PORT_ENV, 8000))
        ),
        INFLUXDB_URL_ENV: (
            _origin(influxdb_url, name=INFLUXDB_URL_ENV)
            if influxdb_url
            else _derived_origin(address, _port(environ, INFLUXDB_PORT_ENV, 8086))
        ),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Derive missing node-facing final URLs before an official startup command."
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("A command is required after --.", file=sys.stderr)
        return 2
    try:
        validate_required_environment(os.environ)
        publish_ports = _effective_publish_port_environment(os.environ)
        effective_environ = {**os.environ, **publish_ports}
        resolved = resolve_node_facing_environment(effective_environ)
        validate_publish_ports(effective_environ)
    except NodeFacingStartupError as exc:
        print(f"Node-facing URL preflight failed: {exc}", file=sys.stderr)
        return 2
    child_env = {**effective_environ, **resolved}
    for name, value in resolved.items():
        source = "configured" if os.environ.get(name, "").strip() else "derived"
        print(f"Node-facing URL preflight: {name}={value} ({source}).", flush=True)
    os.execvpe(command[0], command, child_env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
