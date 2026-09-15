from __future__ import annotations

import argparse
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

from minio import Minio
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
TEST_RUNNER_INTERNAL_TOKEN = os.environ.setdefault(
    "RUNNER_INTERNAL_TOKEN", "surgepilot-e2e-runner-token"
)
COMPOSE_FILES = (
    "infra/docker/docker-compose.base.yml",
    "infra/docker/docker-compose.smoke.yml",
    "infra/docker/docker-compose.ssh-e2e.yml",
)
PROJECT_NAME = os.environ.get("SURGEPILOT_P0_06_SSH_E2E_PROJECT", "surgepilot-p0-06-ssh-e2e")
E2E_HOST_IP = os.environ.get("SURGEPILOT_E2E_HOST_IP")


def strip_api_suffix(url: str) -> str:
    stripped = url.rstrip("/")
    return stripped[:-4] if stripped.endswith("/api") else stripped


def derive_api_base_url(*, legacy_env: str, legacy_default: str) -> str:
    return strip_api_suffix(
        os.environ.get(
            "SURGEPILOT_E2E_API_ORCHESTRATION_URL",
            os.environ.get(legacy_env, legacy_default),
        )
    )


def derive_remote_api_base_url(*, legacy_env: str) -> str:
    if E2E_HOST_IP:
        return f"http://{E2E_HOST_IP}:8000"
    e2e_orchestration_url = os.environ.get("SURGEPILOT_E2E_API_ORCHESTRATION_URL")
    if e2e_orchestration_url:
        return strip_api_suffix(e2e_orchestration_url)
    return strip_api_suffix(os.environ.get(legacy_env, "http://api:8000"))


def derive_node_api_base_url() -> str:
    configured = os.environ.get("SURGEPILOT_E2E_NODE_API_BASE_URL") or os.environ.get(
        "SURGEPILOT_NODE_API_BASE_URL"
    )
    if configured:
        return strip_api_suffix(configured)
    if E2E_HOST_IP:
        return f"http://{E2E_HOST_IP}:8000"
    e2e_orchestration_url = os.environ.get("SURGEPILOT_E2E_API_ORCHESTRATION_URL")
    if e2e_orchestration_url:
        return strip_api_suffix(e2e_orchestration_url)
    return "http://api.surgepilot.test:8000"


API_BASE_URL = derive_api_base_url(
    legacy_env="SURGEPILOT_P0_06_API_BASE_URL", legacy_default="http://localhost:8000"
)
REMOTE_API_BASE_URL = derive_remote_api_base_url(legacy_env="SURGEPILOT_P0_06_REMOTE_API_BASE_URL")
NODE_API_BASE_URL = derive_node_api_base_url()
TARGET_URL = os.environ.get(
    "SURGEPILOT_E2E_TARGET_URL",
    f"http://{E2E_HOST_IP}:18080/health" if E2E_HOST_IP else REMOTE_API_BASE_URL + "/api/healthz",
)
INFLUXDB_NODE_WRITE_URL = os.environ.get("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL")
NODE_SSH_HOST = os.environ.get("SURGEPILOT_E2E_NODE_SSH_HOST", E2E_HOST_IP or "ssh-load-node")
NODE_SSH_PORT = int(
    os.environ.get(
        "SURGEPILOT_E2E_NODE_SSH_PORT",
        os.environ.get("SURGEPILOT_SSH_E2E_PORT", "22322") if E2E_HOST_IP else "22",
    )
)
DATABASE_URL = os.environ.get(
    "SURGEPILOT_P0_06_DATABASE_URL", "postgresql://surgepilot:surgepilot@localhost:5432/surgepilot"
)
MINIO_ENDPOINT = os.environ.get("SURGEPILOT_P0_06_MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "surgepilot")
RUNNER_HOME = os.environ.get("SURGEPILOT_P0_06_RUNNER_HOME", "/opt/surgepilot/runner")
RUNTIME_VERSION = os.environ.get("LOAD_NODE_RUNTIME_VERSION", "p0-e2e")
RUNTIME_ARTIFACT_HOST_DIR = Path(
    os.environ.get(
        "LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR",
        f"/tmp/surgepilot-runtime-artifacts-{PROJECT_NAME}",
    )
)
RUNTIME_BUILD_DIR = Path(
    os.environ.get("LOAD_NODE_RUNTIME_BUILD_DIR", f"/tmp/surgepilot-runtime-build-{PROJECT_NAME}")
)
RUNTIME_CACHE_DIR = Path(
    os.environ.get("LOAD_NODE_RUNTIME_CACHE_DIR", f"/tmp/surgepilot-runtime-cache-{PROJECT_NAME}")
)
RUNTIME_ENV_FILE = Path(
    os.environ.get("LOAD_NODE_RUNTIME_ENV_FILE", str(RUNTIME_ARTIFACT_HOST_DIR / "runtime.env"))
)
TEST_CREDENTIAL_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
SSH_SERVICE = "ssh-load-node"
API_HEALTH_PATH = "/api/healthz"
API_HOST_PORT = str(urllib.parse.urlparse(API_BASE_URL).port or 8000)
SAFE_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
REMOTE_PROCESS_CLEANUP_TIMEOUT_SECONDS = 45
SECRET_KEYS = {
    "password",
    "privateKey",
    "private_key",
    "privateKeyPassphrase",
    "private_key_passphrase",
    "runnerToken",
    "runner_token",
    "token",
    "secret",
}


def new_ulid_like() -> str:
    return uuid4().hex[:26].upper()


STACK_SERVICES = [
    "postgres",
    "minio",
    "minio-init",
    "api-migrate",
    "api",
    "api-worker",
    SSH_SERVICE,
]
APP_BUILD_SERVICES = ["api-migrate", "api", "api-worker"]


@dataclass(frozen=True)
class ApiSession:
    csrf_token: str
    workspace_id: str
    opener: urllib.request.OpenerDirector


class SmokeFailure(RuntimeError):
    pass


def compose_cmd(*args: str) -> list[str]:
    command = ["docker", "compose"]
    for file in COMPOSE_FILES:
        command.extend(["-f", file])
    command.extend(["--profile", "smoke", "--profile", "ssh-e2e"])
    command.extend(args)
    return command


def run_command(
    args: list[str], *, check: bool = True, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "COMPOSE_PROJECT_NAME": PROJECT_NAME,
        "SURGEPILOT_API_HOST_PORT": os.environ.get("SURGEPILOT_API_HOST_PORT", API_HOST_PORT),
        "SURGEPILOT_E2E_NODE_SSH_HOST": NODE_SSH_HOST,
        "SURGEPILOT_E2E_NODE_SSH_PORT": str(NODE_SSH_PORT),
        "SURGEPILOT_NODE_API_BASE_URL": NODE_API_BASE_URL,
        "SSH_CREDENTIAL_ENCRYPTION_KEY": os.environ.get(
            "SSH_CREDENTIAL_ENCRYPTION_KEY", TEST_CREDENTIAL_KEY
        ),
        "MINIO_ACCESS_KEY": MINIO_ACCESS_KEY,
        "MINIO_SECRET_KEY": MINIO_SECRET_KEY,
        "MINIO_ROOT_USER": MINIO_ACCESS_KEY,
        "MINIO_ROOT_PASSWORD": MINIO_SECRET_KEY,
        "MINIO_BUCKET": MINIO_BUCKET,
        "LOAD_NODE_RUNTIME_VERSION": RUNTIME_VERSION,
        "LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR": str(RUNTIME_ARTIFACT_HOST_DIR),
        "LOAD_NODE_RUNTIME_INSTALL_TIMEOUT_SECONDS": os.environ.get(
            "LOAD_NODE_RUNTIME_INSTALL_TIMEOUT_SECONDS", "180"
        ),
    }
    result = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if check and result.returncode != 0:
        raise SmokeFailure(
            f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}"
        )
    return result


def split_target_url(url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Target URL must be absolute: {url}")
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return base_url, path


def target_base_url() -> str:
    return split_target_url(TARGET_URL)[0]


def target_path() -> str:
    return split_target_url(TARGET_URL)[1]


def env_group_payload() -> dict:
    return {
        "name": "P0-06 SSH Smoke",
        "variables": {"base_url": {"type": "plain", "value": target_base_url()}},
    }


def scenario_payload() -> dict:
    return {
        "name": "P0-06 self health smoke",
        "description": "GET SurgePilot health endpoint from an SSH load node container.",
        "tags": ["p0-06", "ssh-smoke"],
        "baseUrlExpression": "${base_url}",
        "defaultSettings": {
            "thinkTimeMs": 0,
            "timeoutMs": 30000,
            "followRedirects": True,
            "keepAlive": True,
            "storeCache": True,
            "storeCookie": True,
            "retrieveResources": False,
        },
        "dataSources": [],
        "steps": [
            {
                "id": "01J0000000000000000000000A",
                "enabled": True,
                "name": "GET API health",
                "method": "GET",
                "path": target_path(),
                "queryParams": [],
                "headers": [],
                "body": {"type": "none", "contentType": None, "rawText": None, "formFields": []},
                "uploadFiles": [],
                "extractors": [],
                "assertions": [
                    {
                        "id": "01J0000000000000000000000B",
                        "type": "status_code",
                        "expectedStatus": 200,
                        "enabled": True,
                    }
                ],
                "scripts": [],
                "settings": {
                    "thinkTimeMs": None,
                    "timeoutMs": None,
                    "followRedirects": None,
                    "keepAlive": None,
                },
            }
        ],
    }


def test_plan_payload(
    *, scenario_id: str, node_id: str, hold_for_seconds: int, plan_name: str
) -> dict:
    return {
        "name": plan_name,
        "description": "P0-06 SSH/Taurus smoke Test Plan.",
        "tags": ["p0-06", "ssh-smoke"],
        "envGroupId": None,
        "runMode": "sequential",
        "resource": {"poolType": "private", "selectedNodeId": node_id},
        "scenarioItems": [
            {
                "id": new_ulid_like(),
                "scenarioId": scenario_id,
                "enabled": True,
                "order": 0,
                "loadSettings": {
                    "concurrencyPerNode": 1,
                    "rampUpSeconds": 0,
                    "holdForSeconds": hold_for_seconds,
                    "iterations": None,
                    "targetRps": None,
                    "steps": None,
                    "delaySeconds": 0,
                },
            }
        ],
        "slaRules": [],
    }


def load_node_payload(ssh_host_key: dict | None = None) -> dict:
    payload = {
        "scope": "workspace",
        "host": NODE_SSH_HOST,
        "sshPort": NODE_SSH_PORT,
        "sshUser": "surgepilot",
        "runnerHome": RUNNER_HOME,
        "credential": {"authType": "password", "password": "surgepilot"},
        "maintainer": "P0-06 SSH smoke",
        "remark": "Container-backed smoke Load Node.",
    }
    if ssh_host_key is not None:
        payload["sshHostKey"] = {
            "algorithm": ssh_host_key["algorithm"],
            "publicKey": ssh_host_key["publicKey"],
            "fingerprintSha256": ssh_host_key["fingerprintSha256"],
        }
    return payload


def assert_no_secret_echo(value: object, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text in SECRET_KEYS:
                raise AssertionError(f"secret field echoed at {path}.{key_text}")
            assert_no_secret_echo(child, path=f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_secret_echo(child, path=f"{path}[{index}]")


def assert_artifact_metadata_safe(artifacts: list[dict]) -> None:
    if not artifacts:
        raise AssertionError("expected at least one uploaded artifact")
    for artifact in artifacts:
        relative_path = artifact["relative_path"]
        parts = str(relative_path).split("/")
        if (
            not relative_path
            or str(relative_path).startswith("/")
            or "\\" in str(relative_path)
            or "//" in str(relative_path)
            or any(
                part in {"", ".", ".."} or not SAFE_PATH_SEGMENT.fullmatch(part) for part in parts
            )
        ):
            raise AssertionError(f"unsafe relative path: {relative_path}")
        if int(artifact["size_bytes"]) <= 0:
            raise AssertionError(f"artifact has empty content: {relative_path}")
        if not SHA256.fullmatch(artifact["sha256"]):
            raise AssertionError(f"invalid sha256 for artifact: {relative_path}")
        storage_key = artifact.get("storage_key")
        if storage_key and not str(storage_key).startswith("run-artifacts/"):
            raise AssertionError(f"unexpected storage key prefix for artifact: {relative_path}")


def assert_snapshot_has_no_secrets(snapshot: object) -> None:
    assert_no_secret_echo(snapshot)
    encoded = json.dumps(snapshot, sort_keys=True)
    forbidden_fragments = [
        "surgepilot:surgepilot",
        "RUNNER_INTERNAL_TOKEN",
        "MINIO_SECRET_KEY",
        "privateKey",
        "password",
    ]
    for fragment in forbidden_fragments:
        if fragment in encoded:
            raise AssertionError(f"snapshot contains forbidden fragment: {fragment}")


def wait_until(description: str, timeout_seconds: int, predicate: Callable[[], bool]) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except Exception as exc:  # noqa: BLE001 - collect best diagnostic for smoke failure.
            last_error = exc
        time.sleep(2)
    suffix = f": {last_error}" if last_error is not None else ""
    raise SmokeFailure(f"Timed out waiting for {description}{suffix}")


def http_json(
    opener: urllib.request.OpenerDirector,
    method: str,
    path: str,
    *,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    expected_status: int | tuple[int, ...] = 200,
) -> tuple[dict, dict[str, str]]:
    body = json.dumps(payload).encode() if payload is not None else None
    request_headers = {"accept": "application/json", **(headers or {})}
    if body is not None:
        request_headers["content-type"] = "application/json"
    request = urllib.request.Request(
        f"{API_BASE_URL.rstrip('/')}{path}", data=body, method=method, headers=request_headers
    )
    expected = (expected_status,) if isinstance(expected_status, int) else expected_status
    try:
        with opener.open(request, timeout=10) as response:
            response_body = response.read().decode()
            data = json.loads(response_body) if response_body else {}
            if response.status not in expected:
                raise SmokeFailure(f"{method} {path} returned {response.status}: {data}")
            return data, dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode()
        raise SmokeFailure(f"{method} {path} returned {exc.code}: {error_body}") from exc


def wait_for_api_health() -> None:
    def healthy() -> bool:
        with urllib.request.urlopen(f"{API_BASE_URL}{API_HEALTH_PATH}", timeout=3) as response:
            body = response.read().decode()
        return response.status == 200 and '"status":"ok"' in body.replace(" ", "")

    wait_until("API health", 120, healthy)


def db_connect() -> AbstractContextManager[psycopg.Connection]:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def fetch_one(query: str, params: tuple = ()) -> dict | None:
    with db_connect() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone()


def fetch_all(query: str, params: tuple = ()) -> list[dict]:
    with db_connect() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return list(cur.fetchall())


def minio_client() -> Minio:
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )


def register_user() -> ApiSession:
    cookie_jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    suffix = int(time.time())
    data, headers = http_json(
        opener,
        "POST",
        "/api/v1/auth/register",
        payload={
            "email": f"p0-06-ssh-smoke-{suffix}@example.com",
            "displayName": "P0-06 SSH Smoke",
            "password": "password123",
        },
        expected_status=201,
    )
    return ApiSession(
        csrf_token=data["csrfToken"],
        workspace_id=data["defaultWorkspace"]["id"],
        opener=opener,
    )


def api_headers(session: ApiSession) -> dict[str, str]:
    return {"x-csrf-token": session.csrf_token, "x-workspace-id": session.workspace_id}


def create_json(session: ApiSession, path: str, payload: dict) -> dict:
    data, _headers = http_json(
        session.opener,
        "POST",
        path,
        payload=payload,
        headers=api_headers(session),
        expected_status=(200, 201, 202),
    )
    assert_no_secret_echo(data)
    return data


def scan_load_node_ssh_host_key(session: ApiSession, *, host: str, ssh_port: int) -> dict:
    scanned = create_json(
        session,
        "/api/v1/load-nodes/ssh-host-key/scan",
        {"scope": "workspace", "host": host, "sshPort": ssh_port},
    )
    for key in ("algorithm", "publicKey", "fingerprintSha256"):
        if not scanned.get(key):
            raise SmokeFailure(f"SSH host key scan did not return {key}.")
    return scanned


def initialize_node(session: ApiSession, node_id: str) -> None:
    create_json(session, f"/api/v1/load-nodes/{node_id}/initialize", {"force": True})

    def is_idle() -> bool:
        data, _headers = http_json(
            session.opener,
            "GET",
            f"/api/v1/load-nodes/{node_id}",
            headers={"x-workspace-id": session.workspace_id},
        )
        if data.get("latestInitAttempt", {}).get("status") == "failed":
            raise SmokeFailure(f"Load Node initialization failed: {data}")
        return data["status"] == "idle"

    wait_until("Load Node initialization", 180, is_idle)


def create_run_now(session: ApiSession, plan: dict) -> dict:
    return create_json(
        session,
        "/api/v1/runs",
        {
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": plan["id"],
            "expectedSourceRevision": plan["revision"],
        },
    )


def stop_run(session: ApiSession, run_id: str, *, expected_status: int | tuple[int, ...]) -> dict:
    data, _headers = http_json(
        session.opener,
        "POST",
        f"/api/v1/runs/{run_id}/stop",
        payload={},
        headers=api_headers(session),
        expected_status=expected_status,
    )
    return data


def poll_run_state(run_id: str, expected: set[str], timeout_seconds: int) -> dict:
    current: dict | None = None

    def reached() -> bool:
        nonlocal current
        current = fetch_one("select * from runs where id = %s", (run_id,))
        if current is None:
            return False
        if current["state"] in {"failed", "aborted", "finished"} - expected:
            raise SmokeFailure(f"Run {run_id} reached unexpected terminal state: {current}")
        return current["state"] in expected

    wait_until(f"Run {run_id} to reach {sorted(expected)}", timeout_seconds, reached)
    assert current is not None
    return current


def wait_for_callback(run_id: str, event_type: str, timeout_seconds: int = 60) -> None:
    def callback_exists() -> bool:
        row = fetch_one(
            "select 1 from runner_callback_events where run_id = %s and event_type = %s limit 1",
            (run_id, event_type),
        )
        return row is not None

    wait_until(f"{event_type} callback for {run_id}", timeout_seconds, callback_exists)


def artifact_rows(run_id: str) -> list[dict]:
    return fetch_all(
        """
        select id, artifact_type, relative_path, size_bytes, sha256, storage_key
        from run_artifacts
        where run_id = %s and status = 'available'
        order by created_at, id
        """,
        (run_id,),
    )


def assert_minio_objects_exist(artifacts: list[dict]) -> None:
    client = minio_client()
    for artifact in artifacts:
        stat = client.stat_object(MINIO_BUCKET, artifact["storage_key"])
        if stat.size != artifact["size_bytes"]:
            raise AssertionError(
                f"MinIO size mismatch for {artifact['relative_path']}: "
                f"{stat.size} != {artifact['size_bytes']}"
            )


def assert_snapshot(run_id: str) -> None:
    row = fetch_one("select snapshot_json from run_snapshots where run_id = %s", (run_id,))
    if row is None:
        raise AssertionError(f"Run Snapshot missing for {run_id}")
    snapshot = row["snapshot_json"]
    assert_snapshot_has_no_secrets(snapshot)
    required = {"testPlan", "scenarioItems", "resourceRequest"}
    missing = required - set(snapshot)
    if missing:
        raise AssertionError(f"Run Snapshot missing sections: {sorted(missing)}")
    scenario_items = snapshot.get("scenarioItems")
    if not isinstance(scenario_items, list) or not scenario_items:
        raise AssertionError("Run Snapshot missing executable scenario items")
    if any("loadSettings" not in item for item in scenario_items):
        raise AssertionError("Run Snapshot scenario item missing loadSettings")


def assert_lease_released(run_id: str) -> None:
    lease = fetch_one("select * from node_leases where run_id = %s", (run_id,))
    if lease is None:
        raise AssertionError(f"Node lease missing for {run_id}")
    if lease["released_at"] is None:
        raise AssertionError(f"Node lease was not released for {run_id}")
    active = fetch_one(
        "select 1 from node_leases where node_id = %s and released_at is null limit 1",
        (lease["node_id"],),
    )
    if active is not None:
        raise AssertionError(f"Node still has an active lease after {run_id}")


def assert_node_idle(node_id: str) -> None:
    node = fetch_one("select status, current_run_id from load_nodes where id = %s", (node_id,))
    if node is None:
        raise AssertionError(f"Load Node missing: {node_id}")
    if node["status"] != "idle" or node["current_run_id"] is not None:
        raise AssertionError(f"Load Node did not return to idle: {node}")


def assert_remote_processes_clean(run_id: str) -> None:
    command = f"""
set -eu
pidfile={posixpath.join(RUNNER_HOME, "runs", run_id, "workload.pid")}
if [ -f "$pidfile" ]; then
  pgid=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["pid"])' "$pidfile")
  if kill -0 -"$pgid" 2>/dev/null; then
    echo "workload process group still alive: $pgid"
    exit 1
  fi
fi
if pgrep -u surgepilot -af '(python3 .*runner[.]py start|/usr/local/bin/bzt|apache-jmeter|ApacheJMeter|org[.]apache[.]jmeter)' >/tmp/surgepilot-live-processes 2>/dev/null; then
  cat /tmp/surgepilot-live-processes
  exit 1
fi
"""

    def clean() -> bool:
        result = run_command(
            compose_cmd("exec", "-T", SSH_SERVICE, "bash", "-lc", command), check=False
        )
        if result.returncode == 0:
            return True
        print(f"Waiting for remote process cleanup for {run_id}:\n{result.stdout}")
        return False

    wait_until(
        f"remote process cleanup for {run_id}", REMOTE_PROCESS_CLEANUP_TIMEOUT_SECONDS, clean
    )


def assert_run_artifacts(run_id: str) -> None:
    artifacts = artifact_rows(run_id)
    assert_artifact_metadata_safe(artifacts)
    assert_minio_objects_exist(artifacts)
    types = {artifact["artifact_type"] for artifact in artifacts}
    if not ({"final_stats_csv", "taurus_log", "run_log"} & types):
        raise AssertionError(f"Expected key smoke artifacts; got {sorted(types)}")


def assert_run_cleanly_converged(run_id: str, node_id: str, expected_state: str) -> None:
    row = fetch_one("select state, ended_at from runs where id = %s", (run_id,))
    if row is None or row["state"] != expected_state or row["ended_at"] is None:
        raise AssertionError(f"Run did not converge to {expected_state}: {row}")
    assert_lease_released(run_id)
    assert_node_idle(node_id)
    assert_remote_processes_clean(run_id)


def verify_finished_run(run_id: str, node_id: str) -> None:
    poll_run_state(run_id, {"finished"}, 180)
    for event_type in ["accepted", "running", "finished"]:
        wait_for_callback(run_id, event_type)
    assert_snapshot(run_id)
    assert_run_artifacts(run_id)
    verify_runtime_bootstrap(run_id)
    assert_run_cleanly_converged(run_id, node_id, "finished")


def verify_stopped_run(session: ApiSession, run_id: str, node_id: str) -> None:
    poll_run_state(run_id, {"running"}, 120)
    wait_for_callback(run_id, "running")
    try:
        wait_for_callback(run_id, "heartbeat", timeout_seconds=20)
    except SmokeFailure:
        print("Heartbeat callback was not observed before Stop; continuing with Stop convergence.")
    first_stop = stop_run(session, run_id, expected_status=(200, 202))
    second_stop = stop_run(session, run_id, expected_status=(200, 202))
    if first_stop["state"] != "stopping" or second_stop["state"] != "stopping":
        raise AssertionError(
            f"Stop did not return idempotent stopping responses: {first_stop}, {second_stop}"
        )
    poll_run_state(run_id, {"aborted"}, 120)
    wait_for_callback(run_id, "aborted")
    verify_runtime_bootstrap(run_id)
    assert_run_cleanly_converged(run_id, node_id, "aborted")


def verify_url_reachable_from_node(
    *,
    env_name: str,
    url: str,
    expected_body_fragment: str | None = None,
) -> None:
    expected_fragment_literal = (
        "None" if expected_body_fragment is None else repr(expected_body_fragment)
    )
    command = (
        "python3 - <<'PY'\n"
        "import urllib.request\n"
        f"url = {json.dumps(url)}\n"
        f"expected_body_fragment = {expected_fragment_literal}\n"
        "with urllib.request.urlopen(url, timeout=5) as response:\n"
        "    body = response.read().decode()\n"
        "assert response.status < 400, response.status\n"
        "if expected_body_fragment is not None:\n"
        "    assert expected_body_fragment in body.replace(' ', ''), body\n"
        "PY"
    )
    try:
        run_command(compose_cmd("exec", "-T", SSH_SERVICE, "bash", "-lc", command))
    except SmokeFailure as exc:
        raise SmokeFailure(f"Load Node preflight failed for {env_name}={url}: {exc}") from exc


def influxdb_health_url(node_write_url: str) -> str:
    parsed = urllib.parse.urlparse(node_write_url)
    if not parsed.scheme or not parsed.netloc:
        raise SmokeFailure(
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL must be an absolute URL "
            f"when set: {node_write_url}"
        )
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/health", "", "", ""))


def verify_remote_api_reachable() -> None:
    verify_url_reachable_from_node(
        env_name="SURGEPILOT_E2E_API_ORCHESTRATION_URL/REMOTE_API_BASE_URL",
        url=REMOTE_API_BASE_URL + API_HEALTH_PATH,
        expected_body_fragment='"status":"ok"',
    )


def verify_node_api_reachable() -> None:
    verify_url_reachable_from_node(
        env_name="SURGEPILOT_NODE_API_BASE_URL",
        url=NODE_API_BASE_URL + API_HEALTH_PATH,
        expected_body_fragment='"status":"ok"',
    )


def verify_target_reachable() -> None:
    verify_url_reachable_from_node(env_name="SURGEPILOT_E2E_TARGET_URL", url=TARGET_URL)


def verify_influxdb_node_write_reachable() -> None:
    if not INFLUXDB_NODE_WRITE_URL:
        return
    verify_url_reachable_from_node(
        env_name="SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL",
        url=influxdb_health_url(INFLUXDB_NODE_WRITE_URL),
    )


def verify_api_worker_can_reach_node_ssh() -> None:
    command = (
        "python3 - <<'PY'\n"
        "import socket\n"
        f"host = {json.dumps(NODE_SSH_HOST)}\n"
        f"port = {NODE_SSH_PORT!r}\n"
        "with socket.create_connection((host, port), timeout=5):\n"
        "    pass\n"
        "PY"
    )
    run_command(compose_cmd("exec", "-T", "api-worker", "bash", "-lc", command))


def seed_runtime_artifact() -> None:
    run_command(
        [
            sys.executable,
            "scripts/release_runtime_artifact.py",
            "--output-dir",
            str(RUNTIME_ARTIFACT_HOST_DIR),
            "--build-dir",
            str(RUNTIME_BUILD_DIR),
            "--cache-dir",
            str(RUNTIME_CACHE_DIR),
            "--env-file",
            str(RUNTIME_ENV_FILE),
            "--fixed-version",
            RUNTIME_VERSION,
        ]
    )


def verify_runtime_bootstrap(run_id: str) -> None:
    run_root = posixpath.join(RUNNER_HOME, "runs", run_id)
    bundle_yaml = posixpath.join(RUNNER_HOME, "runs", run_id, "bundle", "surgepilot.yml")
    command = f"""
set -eu
test -x {posixpath.join(RUNNER_HOME, "current", "bin", "bzt")!r}
test -x {posixpath.join(RUNNER_HOME, "current", "apache-jmeter-5.6.3", "bin", "jmeter")!r}
if [ -f {bundle_yaml!r} ]; then
  grep -q 'current/apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper' {bundle_yaml!r}
  if grep -q '~/.bzt/jmeter-taurus' {bundle_yaml!r}; then
    echo "bundle used Taurus auto-download JMeter path"
    exit 1
  fi
elif [ -e {run_root!r} ]; then
  echo "run directory exists without bundle surgepilot.yml"
  exit 1
fi
"""
    run_command(compose_cmd("exec", "-T", SSH_SERVICE, "bash", "-lc", command))


def setup_stack(*, build_app: bool, build_ssh: bool) -> None:
    run_command(compose_cmd("down", "-v"), check=False)
    if build_ssh:
        run_command(compose_cmd("build", SSH_SERVICE))
    seed_runtime_artifact()
    if build_app:
        run_command(compose_cmd("build", *APP_BUILD_SERVICES))
    run_command(compose_cmd("up", "-d", "--no-build", *STACK_SERVICES))
    wait_for_api_health()
    verify_api_worker_can_reach_node_ssh()
    verify_node_api_reachable()
    verify_target_reachable()
    verify_influxdb_node_write_reachable()


@contextmanager
def stack_context(*, build_app: bool, build_ssh: bool, keep_stack: bool, keep_data: bool):
    try:
        setup_stack(build_app=build_app, build_ssh=build_ssh)
        yield
    except Exception:
        diagnostics()
        raise
    finally:
        if not keep_stack:
            down_args = ("down",) if keep_data else ("down", "-v")
            run_command(compose_cmd(*down_args), check=False)


def diagnostics() -> None:
    print("\n--- compose ps ---", file=sys.stderr)
    print(run_command(compose_cmd("ps"), check=False).stdout, file=sys.stderr)
    print("\n--- compose logs tail ---", file=sys.stderr)
    print(
        run_command(compose_cmd("logs", "--no-color", "--tail=200"), check=False).stdout,
        file=sys.stderr,
    )


def prepare_assets(session: ApiSession) -> tuple[str, str]:
    env = create_json(session, "/api/v1/env-groups", env_group_payload())
    scenario = create_json(session, "/api/v1/scenarios", scenario_payload())
    ssh_host_key = scan_load_node_ssh_host_key(session, host=NODE_SSH_HOST, ssh_port=NODE_SSH_PORT)
    node = create_json(session, "/api/v1/load-nodes", load_node_payload(ssh_host_key))
    initialize_node(session, node["id"])
    return env["id"], scenario["id"], node["id"]


def create_plan(session: ApiSession, scenario_id: str, node_id: str, hold: int, name: str) -> dict:
    payload = test_plan_payload(
        scenario_id=scenario_id, node_id=node_id, hold_for_seconds=hold, plan_name=name
    )
    # The Env Group is saved after asset creation to keep helper tests deterministic.
    env_id = fetch_one("select id from env_groups where name = %s", ("P0-06 SSH Smoke",))
    if env_id is None:
        raise SmokeFailure("Env Group was not persisted.")
    payload["envGroupId"] = env_id["id"]
    return create_json(session, "/api/v1/test-plans", payload)


def run_smoke(*, include_stop: bool) -> None:
    session = register_user()
    _env_id, scenario_id, node_id = prepare_assets(session)

    short_plan = create_plan(session, scenario_id, node_id, 10, "P0-06 SSH short run")
    short_run = create_run_now(session, short_plan)
    print(f"Started short P0-06 SSH Run: {short_run['id']}")
    verify_finished_run(short_run["id"], node_id)
    print(f"Finished short P0-06 SSH Run: {short_run['id']}")

    if include_stop:
        stop_plan = create_plan(session, scenario_id, node_id, 30, "P0-06 SSH stop run")
        stop_run_response = create_run_now(session, stop_plan)
        print(f"Started stoppable P0-06 SSH Run: {stop_run_response['id']}")
        verify_stopped_run(session, stop_run_response["id"], node_id)
        print(f"Stopped P0-06 SSH Run: {stop_run_response['id']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify P0-06 Test Plan Run Now over SSH/Taurus.")
    parser.add_argument("--build-app", action="store_true", help="Build API images before running.")
    parser.add_argument(
        "--build-ssh", action="store_true", help="Build SSH load-node image before running."
    )
    parser.add_argument("--skip-stop", action="store_true", help="Only run the 10s happy path.")
    parser.add_argument(
        "--keep-stack", action="store_true", help="Leave Docker Compose stack running."
    )
    parser.add_argument(
        "--keep-data", action="store_true", help="Keep Docker volumes after the run for inspection."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        with stack_context(
            build_app=args.build_app,
            build_ssh=args.build_ssh,
            keep_stack=args.keep_stack,
            keep_data=args.keep_data,
        ):
            run_smoke(include_stop=not args.skip_stop)
    except Exception as exc:  # noqa: BLE001 - smoke tool prints actionable diagnostics.
        print(f"P0-06 SSH/Taurus smoke failed: {exc}", file=sys.stderr)
        return 1
    print("P0-06 SSH/Taurus smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
