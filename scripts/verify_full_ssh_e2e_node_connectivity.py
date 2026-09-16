from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import os
import subprocess
import sys
import time
from urllib.parse import urlsplit, urlunsplit

SSH_SERVICES = ("ssh-load-node", "ssh-load-node-2")


class ConnectivityError(RuntimeError):
    pass


def _health_url(environ: Mapping[str, str], name: str, path: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise ConnectivityError(f"{name} must be set to the final node-facing URL.")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConnectivityError(f"{name} must be an absolute http or https origin.")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ConnectivityError(f"{name} must be an origin without a path, query, or fragment.")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def health_urls(environ: Mapping[str, str]) -> list[tuple[str, str, dict[str, str]]]:
    return [
        (
            "SURGEPILOT_NODE_API_BASE_URL",
            _health_url(environ, "SURGEPILOT_NODE_API_BASE_URL", "/api/healthz"),
            {"status": "ok"},
        ),
        (
            "SURGEPILOT_NODE_API_BASE_URL identity",
            _health_url(environ, "SURGEPILOT_NODE_API_BASE_URL", "/api/openapi.json"),
            {"info.title": "SurgePilot API"},
        ),
        (
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL",
            _health_url(environ, "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "/health"),
            {"name": "influxdb", "status": "pass"},
        ),
    ]


def _compose_exec(service: str, name: str, url: str, expected: Mapping[str, str]) -> list[str]:
    probe = (
        "import functools, json, urllib.request; "
        f"url={json.dumps(url)}; "
        f"expected={json.dumps(dict(expected))}; "
        "response=urllib.request.urlopen(url, timeout=5); "
        "body=response.read().decode(); "
        "assert response.status < 400, response.status; "
        "payload=json.loads(body); "
        "assert all(functools.reduce(lambda current, part: current.get(part) "
        "if isinstance(current, dict) else None, path.split('.'), payload) == value "
        "for path, value in expected.items()), payload"
    )
    return [
        "docker",
        "compose",
        "-f",
        "infra/docker/docker-compose.yml",
        "-f",
        "infra/docker/docker-compose.ssh-e2e.yml",
        "--profile",
        "ssh-e2e",
        "exec",
        "-T",
        service,
        "python3",
        "-c",
        probe,
        name,
    ]


def verify_connectivity(
    environ: Mapping[str, str],
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    sleep: Callable[[float], None] = time.sleep,
    attempts: int = 30,
) -> None:
    for service in SSH_SERVICES:
        for name, url, expected in health_urls(environ):
            last_output = ""
            for attempt in range(attempts):
                result = run(
                    _compose_exec(service, name, url, expected),
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                if result.returncode == 0:
                    break
                last_output = result.stdout.strip()
                if attempt + 1 < attempts:
                    sleep(2)
            else:
                raise ConnectivityError(
                    f"{service} cannot reach {name}={url} after {attempts} attempts: "
                    f"{last_output or 'no diagnostics'}"
                )
            print(f"Verified {service} -> {name}={url}.")


def main() -> int:
    try:
        verify_connectivity(os.environ)
    except ConnectivityError as exc:
        print(f"Full SSH E2E node connectivity failed: {exc}", file=sys.stderr)
        return 1
    print("Full SSH E2E node-facing API and InfluxDB health checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
