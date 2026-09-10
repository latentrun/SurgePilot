from __future__ import annotations

from dataclasses import dataclass
from http.cookiejar import CookieJar
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

os.environ.setdefault("RUNNER_INTERNAL_TOKEN", "surgepilot-e2e-runner-token")
os.environ.setdefault(
    "SSH_CREDENTIAL_ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
)
TEST_MINIO_ACCESS_KEY = "minioadmin"
TEST_MINIO_SECRET_KEY = "surgepilot-verification-minio-secret"
TEST_MINIO_BUCKET = "surgepilot"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPOSE = [
    "docker",
    "compose",
    "-f",
    "infra/docker/docker-compose.yml",
]
PROJECT_NAME = os.environ.get("COMPOSE_PROJECT_NAME", "surgepilot-p1-00-monitoring-compose")
API_HOST_PORT = os.environ.get("SURGEPILOT_API_HOST_PORT", "18000")
NGINX_URL = os.environ.get("SURGEPILOT_MONITORING_NGINX_URL", "http://localhost:8080")
API_BASE_URL = os.environ.get("SURGEPILOT_MONITORING_API_URL", f"http://localhost:{API_HOST_PORT}")
INFLUXDB_HOST_PORT = os.environ.get("SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT", "18086")
INFLUXDB_URL = os.environ.get(
    "SURGEPILOT_MONITORING_INFLUXDB_URL", f"http://localhost:{INFLUXDB_HOST_PORT}"
)
INFLUXDB_NODE_WRITE_URL = os.environ.get(
    "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL",
    f"http://host.docker.internal:{INFLUXDB_HOST_PORT}",
)


@dataclass(frozen=True)
class RegisteredSession:
    opener: urllib.request.OpenerDirector
    workspace_id: str


WORKER_LOG_FAILURE_MARKERS = (
    "api-worker cycle failed",
    "Traceback (most recent call last)",
    "IndexError",
)


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "COMPOSE_PROJECT_NAME": PROJECT_NAME,
        "SURGEPILOT_API_HOST_PORT": API_HOST_PORT,
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": INFLUXDB_HOST_PORT,
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": INFLUXDB_NODE_WRITE_URL,
        "MINIO_ACCESS_KEY": TEST_MINIO_ACCESS_KEY,
        "MINIO_SECRET_KEY": TEST_MINIO_SECRET_KEY,
        "MINIO_ROOT_USER": TEST_MINIO_ACCESS_KEY,
        "MINIO_ROOT_PASSWORD": TEST_MINIO_SECRET_KEY,
        "MINIO_BUCKET": TEST_MINIO_BUCKET,
    }
    result = subprocess.run(
        [*COMPOSE, *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}"
        )
    return result


def wait_for_url(
    description: str,
    url: str,
    *,
    timeout_seconds: int = 120,
    expected_status: int | tuple[int, ...] = 200,
) -> None:
    expected = (expected_status,) if isinstance(expected_status, int) else expected_status
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                response.read()
                if response.status in expected:
                    return
        except urllib.error.HTTPError as exc:
            if exc.code in expected:
                return
            last_error = exc
        except Exception as exc:  # noqa: BLE001 - keep readiness polling robust.
            last_error = exc
        time.sleep(2)
    raise RuntimeError(f"{description} was not ready at {url}: {last_error}")


def assert_worker_is_clean() -> None:
    time.sleep(6)
    logs = run(["logs", "--no-color", "--tail=200", "api-worker"]).stdout
    failures = [marker for marker in WORKER_LOG_FAILURE_MARKERS if marker in logs]
    if failures:
        raise RuntimeError(
            f"api-worker reported a monitoring startup failure ({', '.join(failures)}):\n{logs}"
        )


def register_session() -> RegisteredSession:
    cookie_jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    payload = json.dumps(
        {
            "email": f"monitoring-compose-{int(time.time())}@example.com",
            "displayName": "Monitoring Compose",
            "password": "password123",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{API_BASE_URL}/api/v1/auth/register",
        data=payload,
        method="POST",
        headers={"content-type": "application/json", "accept": "application/json"},
    )
    with opener.open(request, timeout=10) as response:
        body = response.read().decode("utf-8")
        if response.status != 201:
            raise RuntimeError(f"registration failed with status {response.status}")
    auth_body = json.loads(body)
    workspace_id = (auth_body.get("defaultWorkspace") or {}).get("id")
    if not workspace_id:
        raise RuntimeError(f"registration did not return default workspace: {auth_body}")
    return RegisteredSession(opener=opener, workspace_id=workspace_id)


def open_json(opener: urllib.request.OpenerDirector, url: str) -> dict:
    request = urllib.request.Request(url, headers={"accept": "application/json"})
    with opener.open(request, timeout=10) as response:
        body = response.read().decode("utf-8")
        if response.status != 200:
            raise RuntimeError(f"{url} returned {response.status}")
        return json.loads(body)


def assert_grafana_provisioning(opener: urllib.request.OpenerDirector) -> None:
    datasource = open_json(opener, f"{NGINX_URL}/grafana/api/datasources/uid/InfluxDB-SurgePilot")
    if (
        datasource.get("uid") != "InfluxDB-SurgePilot"
        or datasource.get("url") != "http://influxdb:8086"
    ):
        raise RuntimeError(f"Grafana datasource provisioning mismatch: {datasource}")
    dashboard = open_json(
        opener, f"{NGINX_URL}/grafana/api/dashboards/uid/surgepilot-jmeter-13644"
    )
    dashboard_body = dashboard.get("dashboard") or {}
    if dashboard_body.get("uid") != "surgepilot-jmeter-13644":
        raise RuntimeError(f"Grafana dashboard provisioning mismatch: {dashboard}")


def assert_monitoring_embed(session: RegisteredSession) -> None:
    request = urllib.request.Request(
        f"{API_BASE_URL}/api/v1/monitoring/embed",
        headers={
            "accept": "application/json",
            "x-workspace-id": session.workspace_id,
        },
    )
    with session.opener.open(request, timeout=10) as response:
        body = response.read().decode("utf-8")
        if response.status != 200:
            raise RuntimeError(f"monitoring embed returned {response.status}: {body}")
    embed = json.loads(body)
    iframe_url = embed.get("iframeUrl") or ""
    if embed.get("status") != "ready" or not embed.get("enabled"):
        raise RuntimeError(f"monitoring embed is not ready: {embed}")
    if not iframe_url.startswith("/grafana/"):
        raise RuntimeError(f"monitoring embed iframe is not same-origin Grafana: {embed}")
    if "theme=dark" not in iframe_url:
        raise RuntimeError(f"monitoring embed iframe is not dark themed: {embed}")
    if "var-runId" in iframe_url:
        raise RuntimeError(f"generic monitoring embed must not pin runId: {embed}")
    if not embed.get("from") or embed.get("to") != "now":
        raise RuntimeError(f"generic monitoring embed did not use last-5-minutes window: {embed}")
    if "influxdb" in body or "token" in body.lower():
        raise RuntimeError(f"monitoring embed leaked deployment internals: {body}")


def assert_grafana_session_gate() -> None:
    wait_for_url(
        "Grafana session gate",
        f"{NGINX_URL}/grafana/",
        timeout_seconds=30,
        expected_status=(401, 403),
    )
    session = register_session()
    assert_monitoring_embed(session)
    assert_grafana_provisioning(session.opener)
    with session.opener.open(
        f"{NGINX_URL}/grafana/d/surgepilot-jmeter-13644/jmeter-load-test"
        "?orgId=1&kiosk&theme=dark",
        timeout=10,
    ) as response:
        response.read()
        if response.status != 200:
            raise RuntimeError(f"authenticated Grafana iframe returned {response.status}")


def main() -> int:
    keep_stack = os.environ.get("SURGEPILOT_MONITORING_KEEP_STACK") == "1"
    try:
        run(["config"])
        run(["up", "-d", "--build"])
        wait_for_url("API health", f"{API_BASE_URL}/api/healthz")
        wait_for_url("InfluxDB health", f"{INFLUXDB_URL}/health")
        assert_worker_is_clean()
        assert_grafana_session_gate()
        print("P1-00 Monitoring compose profile started cleanly.")
        return 0
    except Exception as exc:  # noqa: BLE001 - print compose diagnostics before exit.
        print(f"P1-00 Monitoring compose verification failed: {exc}", file=sys.stderr)
        try:
            print(run(["ps"], check=False).stdout, file=sys.stderr)
            print(run(["logs", "--no-color", "--tail=160"], check=False).stdout, file=sys.stderr)
        except Exception as diagnostics_exc:  # noqa: BLE001
            print(f"Could not collect monitoring diagnostics: {diagnostics_exc}", file=sys.stderr)
        return 1
    finally:
        if not keep_stack:
            run(["down", "-v"], check=False)


if __name__ == "__main__":
    raise SystemExit(main())
