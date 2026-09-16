from __future__ import annotations

import argparse
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from http.cookiejar import CookieJar, DefaultCookiePolicy
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

ROOT = Path(__file__).resolve().parents[1]
TEST_RUNNER_INTERNAL_TOKEN = os.environ.setdefault(
    "RUNNER_INTERNAL_TOKEN", "surgepilot-e2e-runner-token"
)
COMPOSE_FILES = (
    "infra/docker/docker-compose.base.yml",
    "infra/docker/docker-compose.smoke.yml",
    "infra/docker/docker-compose.ssh-e2e.yml",
)
PROJECT_NAME = os.environ.get("SURGEPILOT_P0_API_E2E_PROJECT", "surgepilot-p0-api-main-flow-e2e")
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
    legacy_env="SURGEPILOT_P0_API_E2E_API_BASE_URL", legacy_default="http://localhost:8000"
)
REMOTE_API_BASE_URL = derive_remote_api_base_url(
    legacy_env="SURGEPILOT_P0_API_E2E_REMOTE_API_BASE_URL"
)
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
MINIO_ENDPOINT = os.environ.get("SURGEPILOT_P0_API_E2E_MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "surgepilot")
RUNNER_HOME = os.environ.get("SURGEPILOT_P0_API_E2E_RUNNER_HOME", "/opt/surgepilot/runner")
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
FORBIDDEN_PUBLIC_KEYS = {
    "password",
    "privateKey",
    "private_key",
    "privateKeyPassphrase",
    "private_key_passphrase",
    "credential",
    "runnerToken",
    "runner_token",
    "token",
    "secret",
    "storageKey",
    "storage_key",
    "storageObjectKey",
    "storage_object_key",
    "storageBucket",
    "storage_bucket",
    "bucket",
    "objectKey",
    "object_key",
    "presignedUrl",
    "presigned_url",
}
FORBIDDEN_PUBLIC_VALUE_FRAGMENTS = tuple(
    value
    for value in {
        MINIO_ACCESS_KEY,
        MINIO_SECRET_KEY,
        TEST_CREDENTIAL_KEY,
        "run-artifacts/",
    }
    if value
)
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
    email: str
    opener: urllib.request.OpenerDirector


class LocalhostSecureCookiePolicy(DefaultCookiePolicy):
    """Match browser handling of Secure cookies on the localhost trusted origin."""

    def return_ok_secure(self, cookie, request) -> bool:
        if cookie.secure and request.type not in self.secure_protocols:
            return urllib.parse.urlparse(request.full_url).hostname == "localhost"
        return super().return_ok_secure(cookie, request)


class E2EFailure(RuntimeError):
    pass


class TerminalE2EFailure(E2EFailure):
    pass


def new_ulid_like() -> str:
    return uuid4().hex[:26].upper()


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
        raise E2EFailure(f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}")
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
        "name": "P0 API Main Flow Env",
        "description": "API e2e environment group for the P0 main flow.",
        "variables": {"base_url": {"type": "plain", "value": target_base_url()}},
    }


def scenario_payload(*, dependency_file_id: str) -> dict:
    return {
        "name": "P0 API Main Flow Scenario",
        "description": "GET SurgePilot health endpoint from a real SSH Load Node container.",
        "tags": ["p0-api-e2e", "main-flow"],
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
        "dataSources": [
            {
                "id": new_ulid_like(),
                "dependencyFileId": dependency_file_id,
                "displayName": "users.csv",
                "delimiter": ",",
                "quoted": True,
                "loop": True,
                "variableNames": ["username", "tenant"],
                "randomOrder": False,
                "enabled": True,
            }
        ],
        "steps": [
            {
                "id": new_ulid_like(),
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
                        "id": new_ulid_like(),
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
    *, scenario_id: str, env_group_id: str, node_id: str, hold_for_seconds: int, plan_name: str
) -> dict:
    return {
        "name": plan_name,
        "description": "P0 API main flow Test Plan using a real SSH Load Node.",
        "tags": ["p0-api-e2e", "main-flow"],
        "envGroupId": env_group_id,
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
        "maintainer": "P0 API main flow e2e",
        "remark": "Container-backed SSH Load Node for P0 API e2e.",
    }
    if ssh_host_key is not None:
        payload["sshHostKey"] = {
            "algorithm": ssh_host_key["algorithm"],
            "publicKey": ssh_host_key["publicKey"],
            "fingerprintSha256": ssh_host_key["fingerprintSha256"],
        }
    return payload


def assert_no_forbidden_keys(value: object, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            assert_no_forbidden_keys(child, path=f"{path}.{key_text}")
            if key_text in FORBIDDEN_PUBLIC_KEYS and not path.endswith(".variables"):
                raise AssertionError(f"forbidden public field echoed at {path}.{key_text}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_forbidden_keys(child, path=f"{path}[{index}]")
    elif isinstance(value, str):
        for fragment in FORBIDDEN_PUBLIC_VALUE_FRAGMENTS:
            if fragment in value:
                raise AssertionError(f"sensitive public value echoed at {path}")


def assert_safe_relative_path(relative_path: str) -> None:
    parts = relative_path.split("/")
    if (
        not relative_path
        or relative_path.startswith("/")
        or "\\" in relative_path
        or "//" in relative_path
        or any(part in {"", ".", ".."} or not SAFE_PATH_SEGMENT.fullmatch(part) for part in parts)
    ):
        raise AssertionError(f"unsafe relative path: {relative_path}")


def assert_public_artifact_metadata_safe(artifacts: list[dict]) -> None:
    if not artifacts:
        raise AssertionError("expected at least one public artifact")
    assert_no_forbidden_keys(artifacts)
    for artifact in artifacts:
        relative_path = artifact["relativePath"]
        assert_safe_relative_path(str(relative_path))
        if int(artifact["sizeBytes"]) <= 0:
            raise AssertionError(f"artifact has empty content: {relative_path}")
        if not SHA256.fullmatch(str(artifact["sha256"])):
            raise AssertionError(f"invalid sha256 for artifact: {relative_path}")
        download_url = str(artifact.get("downloadUrl", ""))
        if not download_url.startswith("/api/v1/runs/") or not download_url.endswith("/download"):
            raise AssertionError(f"unsafe downloadUrl for artifact: {download_url}")


def wait_until(description: str, timeout_seconds: int, predicate: Callable[[], bool]) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except TerminalE2EFailure:
            raise
        except Exception as exc:  # noqa: BLE001 - include last diagnostic in E2E failure.
            last_error = exc
        time.sleep(2)
    suffix = f": {last_error}" if last_error is not None else ""
    raise E2EFailure(f"Timed out waiting for {description}{suffix}")


def http_json(
    opener: urllib.request.OpenerDirector,
    method: str,
    path: str,
    *,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    expected_status: int | tuple[int, ...] = 200,
) -> tuple[dict, dict[str, str], int]:
    body = json.dumps(payload).encode() if payload is not None else None
    request_headers = {"accept": "application/json", **(headers or {})}
    if body is not None:
        request_headers["content-type"] = "application/json"
    request = urllib.request.Request(
        f"{API_BASE_URL.rstrip('/')}{path}", data=body, method=method, headers=request_headers
    )
    expected = (expected_status,) if isinstance(expected_status, int) else expected_status
    try:
        with opener.open(request, timeout=15) as response:
            response_body = response.read().decode()
            data = json.loads(response_body) if response_body else {}
            if response.status not in expected:
                raise E2EFailure(f"{method} {path} returned {response.status}: {data}")
            return data, dict(response.headers.items()), response.status
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode()
        if exc.code in expected:
            return json.loads(error_body) if error_body else {}, dict(exc.headers.items()), exc.code
        raise E2EFailure(f"{method} {path} returned {exc.code}: {error_body}") from exc


def http_bytes(
    opener: urllib.request.OpenerDirector,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    expected_status: int | tuple[int, ...] = 200,
) -> tuple[bytes, dict[str, str], int]:
    request = urllib.request.Request(
        f"{API_BASE_URL.rstrip('/')}{path}", method=method, headers={**(headers or {})}
    )
    expected = (expected_status,) if isinstance(expected_status, int) else expected_status
    try:
        with opener.open(request, timeout=30) as response:
            data = response.read()
            if response.status not in expected:
                raise E2EFailure(f"{method} {path} returned {response.status}: {data[:200]!r}")
            return data, dict(response.headers.items()), response.status
    except urllib.error.HTTPError as exc:
        body = exc.read()
        if exc.code in expected:
            return body, dict(exc.headers.items()), exc.code
        raise E2EFailure(f"{method} {path} returned {exc.code}: {body[:500]!r}") from exc


def multipart_upload(
    session: ApiSession,
    *,
    filename: str,
    content: bytes,
    expected_status: int | tuple[int, ...] = 201,
) -> tuple[dict, dict[str, str], int]:
    boundary = f"----surgepilot-{uuid4().hex}"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            (
                'Content-Disposition: form-data; name="file"; '
                f'filename="{filename}"\r\n'
                "Content-Type: text/csv\r\n\r\n"
            ).encode(),
            content,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    request = urllib.request.Request(
        f"{API_BASE_URL.rstrip()}/api/v1/dependency-files",
        data=body,
        method="POST",
        headers={
            "accept": "application/json",
            "content-type": f"multipart/form-data; boundary={boundary}",
            **api_headers(session),
        },
    )
    expected = (expected_status,) if isinstance(expected_status, int) else expected_status
    try:
        with session.opener.open(request, timeout=30) as response:
            response_body = response.read().decode()
            data = json.loads(response_body) if response_body else {}
            if response.status not in expected:
                raise E2EFailure(f"upload returned {response.status}: {data}")
            return data, dict(response.headers.items()), response.status
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode()
        if exc.code in expected:
            return json.loads(error_body) if error_body else {}, dict(exc.headers.items()), exc.code
        raise E2EFailure(f"upload returned {exc.code}: {error_body}") from exc


def wait_for_api_health() -> None:
    def healthy() -> bool:
        with urllib.request.urlopen(f"{API_BASE_URL}{API_HEALTH_PATH}", timeout=3) as response:
            body = response.read().decode()
        return response.status == 200 and '"status":"ok"' in body.replace(" ", "")

    wait_until("API health", 120, healthy)


def minio_client() -> Minio:
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )


def register_user(label: str) -> ApiSession:
    cookie_jar = CookieJar(policy=LocalhostSecureCookiePolicy())
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    suffix = f"{int(time.time())}-{uuid4().hex[:8]}"
    data, headers, status = http_json(
        opener,
        "POST",
        "/api/v1/auth/register",
        payload={
            "email": f"{label}-{suffix}@example.com",
            "displayName": f"{label} User",
            "password": "password123",
        },
        expected_status=201,
    )
    if "x-workspace-id" not in {key.lower(): value for key, value in headers.items()}:
        raise AssertionError("register response did not include x-workspace-id")
    assert_no_forbidden_keys(data)
    return ApiSession(
        csrf_token=data["csrfToken"],
        workspace_id=data["defaultWorkspace"]["id"],
        email=data["user"]["email"],
        opener=opener,
    )


def api_headers(session: ApiSession) -> dict[str, str]:
    return {"x-csrf-token": session.csrf_token, "x-workspace-id": session.workspace_id}


def read_headers(session: ApiSession) -> dict[str, str]:
    return {"x-workspace-id": session.workspace_id}


def create_json(session: ApiSession, path: str, payload: dict) -> dict:
    data, _headers, _status = http_json(
        session.opener,
        "POST",
        path,
        payload=payload,
        headers=api_headers(session),
        expected_status=(200, 201, 202),
    )
    assert_no_forbidden_keys(data)
    return data


def scan_load_node_ssh_host_key(session: ApiSession, *, host: str, ssh_port: int) -> dict:
    scanned = create_json(
        session,
        "/api/v1/load-nodes/ssh-host-key/scan",
        {"scope": "workspace", "host": host, "sshPort": ssh_port},
    )
    for key in ("algorithm", "publicKey", "fingerprintSha256"):
        if not scanned.get(key):
            raise AssertionError(f"SSH host key scan did not return {key}.")
    return scanned


def patch_json(session: ApiSession, path: str, payload: dict) -> dict:
    data, _headers, _status = http_json(
        session.opener,
        "PATCH",
        path,
        payload=payload,
        headers=api_headers(session),
        expected_status=200,
    )
    assert_no_forbidden_keys(data)
    return data


def get_json(
    session: ApiSession, path: str, *, expected_status: int | tuple[int, ...] = 200
) -> dict:
    data, _headers, _status = http_json(
        session.opener,
        "GET",
        path,
        headers=read_headers(session),
        expected_status=expected_status,
    )
    assert_no_forbidden_keys(data)
    return data


def initialize_node(session: ApiSession, node_id: str) -> None:
    create_json(session, f"/api/v1/load-nodes/{node_id}/initialize", {"force": True})

    def is_idle() -> bool:
        data = get_json(session, f"/api/v1/load-nodes/{node_id}")
        latest = data.get("latestInitAttempt") or {}
        if latest.get("status") == "failed":
            raise E2EFailure(f"Load Node initialization failed: {data}")
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


def poll_report_state(
    session: ApiSession, run_id: str, expected: set[str], timeout_seconds: int
) -> dict:
    current: dict | None = None

    def reached() -> bool:
        nonlocal current
        current = get_json(session, f"/api/v1/runs/{run_id}")
        state = current["verdict"]["state"]
        if state in {"failed", "aborted", "finished"} - expected:
            raise E2EFailure(f"Run {run_id} reached unexpected terminal state: {current}")
        return state in expected

    wait_until(f"Run {run_id} to reach {sorted(expected)}", timeout_seconds, reached)
    assert current is not None
    return current


def _finished_report_has_parsed_final_stats(report: dict) -> bool:
    return (
        report["verdict"]["state"] == "finished"
        and report["artifactsSummary"].get("hasFinalStatsCsv") is True
        and report["kpiSummary"].get("status") == "parsed"
        and report["finalStatsPreview"].get("status") == "parsed"
    )


def poll_finished_report_complete(session: ApiSession, run_id: str, timeout_seconds: int) -> dict:
    current: dict | None = None

    def complete() -> bool:
        nonlocal current
        current = get_json(session, f"/api/v1/runs/{run_id}")
        state = current["verdict"]["state"]
        if state != "finished":
            raise TerminalE2EFailure(
                f"Run {run_id} left finished state while waiting for summary: {current}"
            )
        if (
            current["kpiSummary"].get("status") == "failed"
            or current["finalStatsPreview"].get("status") == "failed"
        ):
            raise TerminalE2EFailure(f"Run {run_id} final stats summary failed to parse: {current}")
        return _finished_report_has_parsed_final_stats(current)

    wait_until(f"Run {run_id} final stats summary", timeout_seconds, complete)
    assert current is not None
    return current


def stop_run(session: ApiSession, run_id: str, *, expected_status: int | tuple[int, ...]) -> dict:
    data, _headers, _status = http_json(
        session.opener,
        "POST",
        f"/api/v1/runs/{run_id}/stop",
        payload={},
        headers=api_headers(session),
        expected_status=expected_status,
    )
    assert_no_forbidden_keys(data)
    return data


def assert_node_idle(session: ApiSession, node_id: str) -> None:
    node = get_json(session, f"/api/v1/load-nodes/{node_id}")
    if node["status"] != "idle" or node.get("currentRunId") is not None:
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


def assert_report_safe_and_complete(report: dict, *, expected_state: str) -> None:
    assert_no_forbidden_keys(report)
    verdict = report["verdict"]
    snapshot = report["snapshot"]
    if verdict["state"] != expected_state:
        raise AssertionError(f"unexpected report state: {verdict['state']}")
    if snapshot["scenarioCount"] < 1:
        raise AssertionError(f"report snapshot missing scenarios: {snapshot}")
    if snapshot["dependencyFileCount"] < 1:
        raise AssertionError(f"report snapshot missing dependency files: {snapshot}")
    resource = snapshot.get("resourceRequest") or {}
    if resource.get("poolType") != "private" or not resource.get("selectedNodeId"):
        raise AssertionError(f"report snapshot missing private selected node: {snapshot}")
    if expected_state == "finished":
        artifacts_summary = report["artifactsSummary"]
        kpi_summary = report["kpiSummary"]
        final_stats_preview = report["finalStatsPreview"]
        if artifacts_summary.get("hasFinalStatsCsv") is not True:
            raise AssertionError(
                f"finished report missing final stats artifact: {artifacts_summary}"
            )
        if kpi_summary.get("status") != "parsed":
            raise AssertionError(f"finished report did not parse KPI summary: {kpi_summary}")
        if final_stats_preview.get("status") != "parsed" or not final_stats_preview.get("rows"):
            raise AssertionError(
                f"finished report missing final stats preview rows: {final_stats_preview}"
            )
        assert_successful_health_check_kpis(kpi_summary, final_stats_preview)


def assert_successful_health_check_kpis(kpi_summary: dict, final_stats_preview: dict) -> None:
    total_requests = int(kpi_summary.get("totalRequests") or 0)
    failed_requests = int(kpi_summary.get("failedRequests") or 0)
    error_rate = float(kpi_summary.get("errorRate") or 0)
    if total_requests < 1 or failed_requests != 0 or error_rate != 0:
        raise AssertionError(f"finished report missing successful health-check KPI: {kpi_summary}")

    rows = final_stats_preview.get("rows") or []
    successful_200_rows = [
        row
        for row in rows
        if int((row.get("responseCodeCounts") or {}).get("200") or 0) >= 1
        and int(row.get("totalRequests") or 0) >= 1
        and int(row.get("failedRequests") or 0) == 0
        and float(row.get("errorRate") or 0) == 0
    ]
    if not successful_200_rows:
        raise AssertionError(
            f"finished report missing successful health-check KPI rows: {final_stats_preview}"
        )


def assert_artifact_downloads(session: ApiSession, run_id: str) -> list[dict]:
    artifact_list = get_json(session, f"/api/v1/runs/{run_id}/artifacts")
    artifacts = artifact_list["items"]
    assert_public_artifact_metadata_safe(artifacts)
    final_stats = next(
        (artifact for artifact in artifacts if artifact["artifactType"] == "final_stats_csv"), None
    )
    if final_stats is None:
        raise AssertionError(f"final_stats_csv artifact was not listed: {artifacts}")
    body, headers, status = http_bytes(
        session.opener,
        "GET",
        final_stats["downloadUrl"],
        headers=read_headers(session),
        expected_status=200,
    )
    if status != 200 or len(body) <= 0:
        raise AssertionError("final_stats_csv download returned empty content")
    if b"200" not in body:
        raise AssertionError("final_stats_csv download did not include HTTP 200 results")
    content_disposition = {key.lower(): value for key, value in headers.items()}.get(
        "content-disposition", ""
    )
    if "attachment" not in content_disposition:
        raise AssertionError(f"artifact download is not an attachment: {headers}")
    return artifacts


def assert_minio_artifacts_exist(*, workspace_id: str, run_id: str) -> None:
    prefix = f"run-artifacts/{workspace_id}/{run_id}/"
    objects = list(minio_client().list_objects(MINIO_BUCKET, prefix=prefix, recursive=True))
    if not objects:
        raise AssertionError(f"No MinIO objects found for run artifact prefix {prefix}")
    if any(obj.size is None or obj.size <= 0 for obj in objects):
        raise AssertionError(f"One or more MinIO artifacts are empty for {prefix}")


def assert_workspace_fallback(session: ApiSession) -> None:
    data, headers, _status = http_json(session.opener, "GET", "/api/v1/env-groups")
    if "items" not in data:
        raise AssertionError(f"default workspace fallback list failed: {data}")
    header_map = {key.lower(): value for key, value in headers.items()}
    if header_map.get("x-workspace-id") != session.workspace_id:
        raise AssertionError(
            f"default workspace fallback returned wrong workspace header: {headers}"
        )


def assert_csrf_required(session: ApiSession) -> None:
    data, _headers, status = http_json(
        session.opener,
        "POST",
        "/api/v1/env-groups",
        payload=env_group_payload(),
        headers={"x-workspace-id": session.workspace_id},
        expected_status=(400, 403),
    )
    if status not in {400, 403} or data.get("code") not in {
        "CSRF_INVALID",
        "CSRF_TOKEN_REQUIRED",
        "FORBIDDEN",
    }:
        raise AssertionError(f"missing CSRF was not rejected as expected: {status} {data}")


def assert_dependency_file_download(session: ApiSession, file_id: str, expected: bytes) -> None:
    body, headers, status = http_bytes(
        session.opener,
        "GET",
        f"/api/v1/dependency-files/{file_id}/download",
        headers=read_headers(session),
        expected_status=200,
    )
    if status != 200 or body != expected:
        raise AssertionError("Dependency File download content mismatch")
    if "attachment" not in {key.lower(): value for key, value in headers.items()}.get(
        "content-disposition", ""
    ):
        raise AssertionError(f"Dependency File download is not an attachment: {headers}")


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
    except E2EFailure as exc:
        raise E2EFailure(f"Load Node preflight failed for {env_name}={url}: {exc}") from exc


def influxdb_health_url(node_write_url: str) -> str:
    parsed = urllib.parse.urlparse(node_write_url)
    if not parsed.scheme or not parsed.netloc:
        raise E2EFailure(
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


def diagnostics() -> None:
    print("\n--- compose ps ---", file=sys.stderr)
    print(run_command(compose_cmd("ps"), check=False).stdout, file=sys.stderr)
    print("\n--- compose logs tail ---", file=sys.stderr)
    print(
        run_command(compose_cmd("logs", "--no-color", "--tail=240"), check=False).stdout,
        file=sys.stderr,
    )


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


def create_main_assets(session: ApiSession) -> tuple[dict, dict, dict, dict, bytes]:
    assert_workspace_fallback(session)
    assert_csrf_required(session)

    env_group = create_json(session, "/api/v1/env-groups", env_group_payload())
    listed_envs = get_json(session, "/api/v1/env-groups")
    if env_group["id"] not in {item["id"] for item in listed_envs["items"]}:
        raise AssertionError("Created Env Group was not listed")

    csv_bytes = b"username,tenant\nalice,default\n"
    dependency_file, _headers, _status = multipart_upload(
        session, filename="users.csv", content=csv_bytes, expected_status=201
    )
    assert_no_forbidden_keys(dependency_file)
    assert_dependency_file_download(session, dependency_file["id"], csv_bytes)
    unsafe, _headers, status = multipart_upload(
        session, filename="../unsafe.csv", content=b"x\n", expected_status=(400, 422)
    )
    if status not in {400, 422} or unsafe.get("code") not in {
        "INVALID_FILENAME",
        "INVALID_REQUEST",
        "VALIDATION_ERROR",
    }:
        raise AssertionError(f"unsafe filename was not rejected as expected: {status} {unsafe}")

    ssh_host_key = scan_load_node_ssh_host_key(session, host=NODE_SSH_HOST, ssh_port=NODE_SSH_PORT)
    node = create_json(session, "/api/v1/load-nodes", load_node_payload(ssh_host_key))
    node_detail = get_json(session, f"/api/v1/load-nodes/{node['id']}")
    node_list = get_json(session, "/api/v1/load-nodes")
    assert_no_forbidden_keys(node_detail)
    assert_no_forbidden_keys(node_list)
    if node_detail["credentialConfigured"] is not True or node_detail["authType"] != "password":
        raise AssertionError(f"Load Node credential metadata is wrong: {node_detail}")
    initialize_node(session, node["id"])

    scenario = create_json(
        session, "/api/v1/scenarios", scenario_payload(dependency_file_id=dependency_file["id"])
    )
    scenario_detail = get_json(session, f"/api/v1/scenarios/{scenario['id']}")
    if scenario_detail["dependencyFileCount"] != 1:
        raise AssertionError(f"Scenario did not reference dependency file: {scenario_detail}")

    plan = create_json(
        session,
        "/api/v1/test-plans",
        test_plan_payload(
            scenario_id=scenario["id"],
            env_group_id=env_group["id"],
            node_id=node["id"],
            hold_for_seconds=6,
            plan_name="P0 API Main Flow Happy Plan",
        ),
    )
    if plan["runnable"] is not True:
        raise AssertionError(f"Test Plan is not runnable: {plan}")

    env_delete, _headers, env_delete_status = http_json(
        session.opener,
        "DELETE",
        f"/api/v1/env-groups/{env_group['id']}",
        headers=api_headers(session),
        expected_status=409,
    )
    if env_delete_status != 409 or env_delete.get("code") != "ENV_GROUP_IN_USE":
        raise AssertionError(
            f"Env Group delete was not protected: {env_delete_status} {env_delete}"
        )
    dep_delete, _headers, dep_delete_status = http_json(
        session.opener,
        "DELETE",
        f"/api/v1/dependency-files/{dependency_file['id']}",
        headers=api_headers(session),
        expected_status=409,
    )
    if dep_delete_status != 409 or dep_delete.get("code") != "FILE_IN_USE":
        raise AssertionError(
            f"Dependency File delete was not protected: {dep_delete_status} {dep_delete}"
        )

    return env_group, dependency_file, node, plan, csv_bytes


def verify_happy_path(session: ApiSession, node: dict, plan: dict) -> str:
    run = create_run_now(session, plan)
    print(f"Started P0 API happy Run: {run['id']}")
    running_or_finished = poll_report_state(session, run["id"], {"running", "finished"}, 150)
    assert_report_safe_and_complete(
        running_or_finished,
        expected_state=running_or_finished["verdict"]["state"],
    )
    report = poll_report_state(session, run["id"], {"finished"}, 240)
    report = poll_finished_report_complete(session, run["id"], 120)
    assert_report_safe_and_complete(report, expected_state="finished")
    artifacts = assert_artifact_downloads(session, run["id"])
    assert_minio_artifacts_exist(workspace_id=session.workspace_id, run_id=run["id"])
    if report["artifactsSummary"]["count"] != len(artifacts):
        raise AssertionError(
            f"artifact count mismatch: {report['artifactsSummary']} vs {artifacts}"
        )
    verify_runtime_bootstrap(run["id"])
    listed_runs = get_json(session, "/api/v1/runs?sourceType=test_plan&limit=10")
    if run["id"] not in {item["id"] for item in listed_runs["items"]}:
        raise AssertionError("Finished Run was not visible in Run List")
    invalid = patch_json(session, f"/api/v1/runs/{run['id']}/validity", {"validity": "invalid"})
    if invalid["validity"] != "invalid":
        raise AssertionError(f"Run validity was not set to invalid: {invalid}")
    valid = patch_json(session, f"/api/v1/runs/{run['id']}/validity", {"validity": "valid"})
    if valid["validity"] != "valid":
        raise AssertionError(f"Run validity was not set back to valid: {valid}")
    terminal_stop, _headers, terminal_status = http_json(
        session.opener,
        "POST",
        f"/api/v1/runs/{run['id']}/stop",
        payload={},
        headers=api_headers(session),
        expected_status=409,
    )
    if terminal_status != 409 or terminal_stop.get("code") != "RUN_TERMINAL_STATE":
        raise AssertionError(f"Terminal Stop did not preserve terminal state: {terminal_stop}")
    assert_node_idle(session, node["id"])
    assert_remote_processes_clean(run["id"])
    print(f"Finished P0 API happy Run: {run['id']}")
    return run["id"]


def verify_stop_path(session: ApiSession, node: dict, scenario_id: str, env_group_id: str) -> str:
    stop_plan = create_json(
        session,
        "/api/v1/test-plans",
        test_plan_payload(
            scenario_id=scenario_id,
            env_group_id=env_group_id,
            node_id=node["id"],
            hold_for_seconds=30,
            plan_name="P0 API Main Flow Stop Plan",
        ),
    )
    run = create_run_now(session, stop_plan)
    print(f"Started P0 API stoppable Run: {run['id']}")
    poll_report_state(session, run["id"], {"running"}, 150)
    first_stop = stop_run(session, run["id"], expected_status=(200, 202))
    second_stop = stop_run(session, run["id"], expected_status=(200, 202))
    if first_stop["state"] != "stopping" or first_stop["duplicate"] is not False:
        raise AssertionError(f"First Stop was not accepted correctly: {first_stop}")
    if second_stop["state"] != "stopping" or second_stop["duplicate"] is not True:
        raise AssertionError(f"Second Stop was not idempotent: {second_stop}")
    report = poll_report_state(session, run["id"], {"aborted"}, 180)
    assert_report_safe_and_complete(report, expected_state="aborted")
    verify_runtime_bootstrap(run["id"])
    assert_node_idle(session, node["id"])
    assert_remote_processes_clean(run["id"])
    print(f"Stopped P0 API Run: {run['id']}")
    return run["id"]


def verify_workspace_enforcement(session: ApiSession, run_id: str) -> None:
    inaccessible_workspace_id = "01J0000000000000000000BAD1"
    denied, _headers, status = http_json(
        session.opener,
        "GET",
        f"/api/v1/runs/{run_id}",
        headers={"x-workspace-id": inaccessible_workspace_id},
        expected_status=403,
    )
    if status != 403 or denied.get("code") != "WORKSPACE_ACCESS_DENIED":
        raise AssertionError(f"Workspace access enforcement failed: {status} {denied}")
    owner_report = get_json(session, f"/api/v1/runs/{run_id}")
    if owner_report["id"] != run_id:
        raise AssertionError("Owner could not read its own Run after workspace enforcement check")


def run_e2e(*, include_stop: bool) -> None:
    setup, _headers, _status = http_json(
        urllib.request.build_opener(), "GET", "/api/v1/setup/status", expected_status=200
    )
    assert_no_forbidden_keys(setup)
    session = register_user("p0-api-main-flow")
    env_group, _dependency_file, node, plan, _csv = create_main_assets(session)
    scenario_id = plan["scenarioItems"][0]["scenarioId"]
    happy_run_id = verify_happy_path(session, node, plan)
    if include_stop:
        verify_stop_path(session, node, scenario_id, env_group["id"])
    verify_workspace_enforcement(session, happy_run_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify P0-00 to P0-07 API main flow on real compose stack."
    )
    parser.add_argument("--build-app", action="store_true", help="Build API images before running.")
    parser.add_argument(
        "--build-ssh", action="store_true", help="Build SSH load-node image before running."
    )
    parser.add_argument("--skip-stop", action="store_true", help="Skip the stoppable Run path.")
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
            run_e2e(include_stop=not args.skip_stop)
    except Exception as exc:  # noqa: BLE001 - E2E tool prints actionable diagnostics.
        print(f"P0 API main flow e2e failed: {exc}", file=sys.stderr)
        return 1
    print("P0 API main flow e2e passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
