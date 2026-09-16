from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
import posixpath
import sys
import urllib.error
import urllib.request
from uuid import uuid4

os.environ.setdefault(
    "SURGEPILOT_P0_06_SSH_E2E_PROJECT",
    os.environ.get("SURGEPILOT_P1_01_SSH_E2E_PROJECT", "surgepilot-p1-01-ssh-e2e"),
)
os.environ.setdefault("SURGEPILOT_P0_06_RUNNER_HOME", "/opt/surgepilot/runner")
os.environ.setdefault("SURGEPILOT_P0_06_API_BASE_URL", "http://localhost:8000")
os.environ.setdefault("SURGEPILOT_P0_06_REMOTE_API_BASE_URL", "http://api:8000")
os.environ.setdefault(
    "SURGEPILOT_P0_06_DATABASE_URL",
    "postgresql://surgepilot:surgepilot@localhost:5432/surgepilot",
)
USER_CONFIGURED_MINIO_ENDPOINT = "SURGEPILOT_P0_06_MINIO_ENDPOINT" in os.environ
os.environ.setdefault("SURGEPILOT_P0_06_MINIO_ENDPOINT", "localhost:9000")

import verify_p0_06_ssh_taurus_smoke as base  # noqa: E402

SSH_SERVICES = ("ssh-load-node", "ssh-load-node-2")
PUBLISHED_SSH_PORT_DEFAULTS = ("22322", "22323")
STACK_SERVICES = [
    "postgres",
    "minio",
    "minio-init",
    "api-migrate",
    "api",
    "api-worker",
    *SSH_SERVICES,
]
APP_BUILD_SERVICES = ["api-migrate", "api", "api-worker"]
RUNNER_TOKEN_MASTER = os.environ.get("RUNNER_INTERNAL_TOKEN", "change-me")


@dataclass(frozen=True)
class SshTarget:
    service: str
    host: str
    port: int


def parse_node_endpoints(value: str) -> list[tuple[str, int]]:
    endpoints = [part.strip() for part in value.split(",") if part.strip()]
    if len(endpoints) != len(SSH_SERVICES):
        raise ValueError("SURGEPILOT_E2E_NODE_ENDPOINTS must contain exactly two host:port values")
    parsed: list[tuple[str, int]] = []
    for endpoint in endpoints:
        if ":" not in endpoint:
            raise ValueError(f"Invalid SSH endpoint {endpoint!r}; expected host:port")
        host, port_text = endpoint.rsplit(":", 1)
        if not host or not port_text:
            raise ValueError(f"Invalid SSH endpoint {endpoint!r}; expected host:port")
        try:
            port = int(port_text)
        except ValueError as exc:
            raise ValueError(f"Invalid SSH endpoint port in {endpoint!r}") from exc
        parsed.append((host, port))
    return parsed


def configured_node_endpoint(index: int) -> tuple[str, int] | None:
    endpoints = os.environ.get("SURGEPILOT_E2E_NODE_ENDPOINTS")
    if not endpoints:
        return None
    return parse_node_endpoints(endpoints)[index - 1]


def new_event_id() -> str:
    return uuid4().hex[:26].upper()


def sign_node_token(node_id: str) -> str:
    signature = hmac.new(RUNNER_TOKEN_MASTER.encode(), node_id.encode(), hashlib.sha256).hexdigest()
    return f"node:{node_id}:{signature}"


def load_node_target(service: str) -> SshTarget:
    if service not in SSH_SERVICES:
        raise ValueError(f"Unknown SSH service: {service}")
    index = SSH_SERVICES.index(service) + 1
    configured = configured_node_endpoint(index)
    if configured is not None:
        host, port_number = configured
        return SshTarget(service=service, host=host, port=port_number)
    host = os.environ.get(f"SURGEPILOT_E2E_NODE_{index}_SSH_HOST")
    port = os.environ.get(f"SURGEPILOT_E2E_NODE_{index}_SSH_PORT")
    if index == 1:
        host = host or os.environ.get("SURGEPILOT_E2E_NODE_SSH_HOST")
        port = port or os.environ.get("SURGEPILOT_E2E_NODE_SSH_PORT")
    if not host and base.E2E_HOST_IP:
        host = base.E2E_HOST_IP
    if not port and host and host != service:
        port = PUBLISHED_SSH_PORT_DEFAULTS[index - 1]
    return SshTarget(service=service, host=host or service, port=int(port or "22"))


def load_node_targets() -> list[SshTarget]:
    return [load_node_target(service) for service in SSH_SERVICES]


def configure_compose_external_node_env() -> None:
    for index, target in enumerate(load_node_targets(), start=1):
        if target.host == target.service and target.port == 22:
            continue
        os.environ.setdefault(f"SURGEPILOT_E2E_NODE_{index}_SSH_HOST", target.host)
        os.environ.setdefault(f"SURGEPILOT_E2E_NODE_{index}_SSH_PORT", str(target.port))


def normalize_host_endpoint(endpoint: str) -> str:
    host, separator, port = endpoint.strip().rpartition(":")
    if not separator or not host or not port:
        return endpoint.strip()
    if host in {"0.0.0.0", "::", "[::]"}:
        host = "127.0.0.1"
    return f"{host}:{port}"


def configure_host_minio_endpoint() -> None:
    if USER_CONFIGURED_MINIO_ENDPOINT:
        return
    port_result = base.run_command(base.compose_cmd("port", "minio", "9000"), check=False)
    published = port_result.stdout.strip().splitlines()
    if published:
        base.MINIO_ENDPOINT = normalize_host_endpoint(published[0])
        return
    container_result = base.run_command(base.compose_cmd("ps", "-q", "minio"), check=False)
    container_id = container_result.stdout.strip()
    if not container_id:
        return
    inspect_result = base.run_command(
        [
            "docker",
            "inspect",
            "-f",
            "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            container_id,
        ],
        check=False,
    )
    container_ip = inspect_result.stdout.strip()
    if container_ip:
        base.MINIO_ENDPOINT = f"{container_ip}:9000"


def load_node_payload(service: str, ssh_host_key: dict | None = None) -> dict:
    target = load_node_target(service)
    payload = {
        "scope": "workspace",
        "host": target.host,
        "sshPort": target.port,
        "sshUser": "surgepilot",
        "runnerHome": base.RUNNER_HOME,
        "credential": {"authType": "password", "password": "surgepilot"},
        "maintainer": "P1-01 SSH two-node smoke",
        "remark": f"Container-backed P1-01 smoke Load Node {service}.",
    }
    if ssh_host_key is not None:
        payload["sshHostKey"] = {
            "algorithm": ssh_host_key["algorithm"],
            "publicKey": ssh_host_key["publicKey"],
            "fingerprintSha256": ssh_host_key["fingerprintSha256"],
        }
    return payload


def test_plan_payload(*, scenario_id: str, node_ids: list[str]) -> dict:
    return {
        "name": "P1-01 SSH two-node Standard Run",
        "description": "P1-01 multi-node SSH/Taurus Standard Run acceptance.",
        "tags": ["p1-01", "ssh-smoke", "multi-node"],
        "envGroupId": None,
        "runMode": "parallel",
        "resource": {
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_ids[0],
            "selectedNodeIds": node_ids,
            "nodeCount": None,
        },
        "scenarioItems": [
            {
                "id": base.new_ulid_like(),
                "scenarioId": scenario_id,
                "enabled": True,
                "order": 0,
                "loadSettings": {
                    "concurrencyPerNode": 1,
                    "rampUpSeconds": 0,
                    "holdForSeconds": 60,
                    "iterations": None,
                    "targetRps": None,
                    "steps": None,
                    "delaySeconds": 0,
                },
            }
        ],
        "slaRules": [],
    }


def create_two_node_run(session: base.ApiSession, plan: dict, node_ids: list[str]) -> dict:
    return base.create_json(
        session,
        "/api/v1/runs",
        {
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": plan["id"],
            "expectedSourceRevision": plan["revision"],
            "resourceRequest": {
                "mode": "manual",
                "selectedNodeIds": node_ids,
                "concurrencyPerNode": 1,
            },
        },
    )


def setup_stack(*, build_app: bool, build_ssh: bool) -> None:
    configure_compose_external_node_env()
    base.run_command(base.compose_cmd("down", "-v"), check=False)
    if build_ssh:
        base.run_command(base.compose_cmd("build", SSH_SERVICES[0]))
    base.seed_runtime_artifact()
    if build_app:
        base.run_command(base.compose_cmd("build", *APP_BUILD_SERVICES))
    base.run_command(base.compose_cmd("up", "-d", "--no-build", *STACK_SERVICES))
    configure_host_minio_endpoint()
    base.wait_for_api_health()
    verify_remote_api_reachable()


def verify_remote_api_reachable() -> None:
    command = (
        "python3 - <<'PY'\n"
        "import urllib.request\n"
        f"url = {json.dumps(base.REMOTE_API_BASE_URL + base.API_HEALTH_PATH)}\n"
        "with urllib.request.urlopen(url, timeout=5) as response:\n"
        "    body = response.read().decode()\n"
        "assert response.status == 200, response.status\n"
        "assert '\"status\":\"ok\"' in body.replace(' ', ''), body\n"
        "PY"
    )
    for service in SSH_SERVICES:
        base.run_command(base.compose_cmd("exec", "-T", service, "bash", "-lc", command))


def create_assets(session: base.ApiSession) -> tuple[str, list[str]]:
    env = base.create_json(session, "/api/v1/env-groups", base.env_group_payload())
    scenario = base.create_json(session, "/api/v1/scenarios", base.scenario_payload())
    node_ids: list[str] = []
    for service in SSH_SERVICES:
        target = load_node_target(service)
        ssh_host_key = base.scan_load_node_ssh_host_key(
            session, host=target.host, ssh_port=target.port
        )
        node = base.create_json(
            session, "/api/v1/load-nodes", load_node_payload(service, ssh_host_key)
        )
        base.initialize_node(session, node["id"])
        node_ids.append(node["id"])
    plan_payload = test_plan_payload(scenario_id=scenario["id"], node_ids=node_ids)
    plan_payload["envGroupId"] = env["id"]
    plan = base.create_json(session, "/api/v1/test-plans", plan_payload)
    return plan["id"], node_ids


def run_allocations(run_id: str) -> list[dict]:
    return base.fetch_all(
        """
        select *
        from run_node_allocations
        where run_id = %s
        order by node_index
        """,
        (run_id,),
    )


def assert_initial_allocation_state(run_id: str, node_ids: list[str]) -> None:
    def ready() -> bool:
        allocations = run_allocations(run_id)
        leases = base.fetch_all("select * from node_leases where run_id = %s", (run_id,))
        controls = base.fetch_all(
            "select * from run_control_requests where run_id = %s and action = 'start'",
            (run_id,),
        )
        return (
            len(allocations) == len(node_ids)
            and len(leases) == len(node_ids)
            and len(controls) == len(node_ids)
        )

    base.wait_until("two allocations, leases, and start controls", 30, ready)
    allocations = run_allocations(run_id)
    if [row["node_id"] for row in allocations] != node_ids:
        raise AssertionError(f"Unexpected allocation node order: {allocations}")


def wait_for_node_callbacks(run_id: str, node_ids: list[str], event_type: str) -> None:
    def present() -> bool:
        rows = base.fetch_all(
            """
            select distinct node_id
            from runner_callback_events
            where run_id = %s and event_type = %s
            """,
            (run_id, event_type),
        )
        return {row["node_id"] for row in rows} == set(node_ids)

    base.wait_until(f"{event_type} callbacks from both nodes", 120, present)


def wait_for_allocation_state(run_id: str, node_ids: list[str], states: set[str]) -> None:
    def reached() -> bool:
        rows = run_allocations(run_id)
        return len(rows) == len(node_ids) and all(row["state"] in states for row in rows)

    base.wait_until(f"allocations to reach {sorted(states)}", 180, reached)


def expect_callback_mismatch_forbidden(
    run_id: str, token_node_id: str, payload_node_id: str
) -> None:
    payload = {
        "schemaVersion": "1",
        "eventId": new_event_id(),
        "runId": run_id,
        "nodeId": payload_node_id,
        "eventType": "heartbeat",
        "seq": 1000,
        "eventTime": "2030-06-20T00:00:00Z",
        "message": "Mismatch callback probe.",
        "details": {},
    }
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{base.API_BASE_URL}/api/internal/v1/runner/callbacks",
        data=body,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-runner-token": sign_node_token(token_node_id),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raise AssertionError(f"Callback token mismatch unexpectedly returned {response.status}")
    except urllib.error.HTTPError as exc:
        if exc.code != 403:
            raise AssertionError(
                f"Callback token mismatch returned {exc.code}: {exc.read()}"
            ) from exc


def expect_artifact_mismatch_forbidden(
    run_id: str, token_node_id: str, payload_node_id: str
) -> None:
    before = base.fetch_one(
        "select count(*) as count from run_artifacts where run_id = %s and relative_path = %s",
        (run_id, "artifacts/mismatch.txt"),
    )["count"]
    boundary = "surgepilot-p1-01-boundary"
    content = b"forbidden\n"
    sha256 = hashlib.sha256(content).hexdigest()
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="schemaVersion"\r\n\r\n'
        "1\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="eventId"\r\n\r\n'
        f"{new_event_id()}\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="runId"\r\n\r\n'
        f"{run_id}\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="nodeId"\r\n\r\n'
        f"{payload_node_id}\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="artifactType"\r\n\r\n'
        "run_log\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="relativePath"\r\n\r\n'
        "artifacts/mismatch.txt\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="sizeBytes"\r\n\r\n'
        f"{len(content)}\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="sha256"\r\n\r\n'
        f"{sha256}\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="mismatch.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n"
        f"{content.decode()}\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    request = urllib.request.Request(
        f"{base.API_BASE_URL}/api/internal/v1/runner/artifacts",
        data=body,
        method="POST",
        headers={
            "content-type": f"multipart/form-data; boundary={boundary}",
            "content-length": str(len(body)),
            "x-runner-token": sign_node_token(token_node_id),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raise AssertionError(f"Artifact token mismatch unexpectedly returned {response.status}")
    except urllib.error.HTTPError as exc:
        if exc.code != 403:
            raise AssertionError(
                f"Artifact token mismatch returned {exc.code}: {exc.read()}"
            ) from exc
    after = base.fetch_one(
        "select count(*) as count from run_artifacts where run_id = %s and relative_path = %s",
        (run_id, "artifacts/mismatch.txt"),
    )["count"]
    if before != after:
        raise AssertionError("Forbidden artifact token mismatch created artifact metadata")


def assert_two_node_artifacts(
    run_id: str, node_ids: list[str], *, require_final_stats: bool
) -> None:
    artifacts = base.fetch_all(
        """
        select id, node_id, allocation_id, artifact_type, relative_path, size_bytes, sha256, storage_key
        from run_artifacts
        where run_id = %s and status = 'available'
        order by node_id, relative_path, id
        """,
        (run_id,),
    )
    base.assert_artifact_metadata_safe(artifacts)
    base.assert_minio_objects_exist(artifacts)
    final_stats = [
        row
        for row in artifacts
        if row["artifact_type"] == "final_stats_csv"
        and row["relative_path"] in {"artifacts/final_stats.csv", "artifacts/finalstats.csv"}
    ]
    if require_final_stats and {row["node_id"] for row in final_stats} != set(node_ids):
        raise AssertionError(f"Expected final stats from both nodes; got {final_stats}")
    archive_artifacts = [
        row
        for row in artifacts
        if row["artifact_type"] == "artifacts_zip"
        and row["relative_path"] == "artifacts/artifacts.zip"
        and row["size_bytes"] > 0
    ]
    if {row["node_id"] for row in archive_artifacts} != set(node_ids):
        raise AssertionError(f"Expected artifacts.zip from both nodes; got {archive_artifacts}")
    if any(row["allocation_id"] is None for row in artifacts):
        raise AssertionError(f"Expected allocation-owned artifacts; got {artifacts}")


def forbidden_node_detail_fragments() -> list[str]:
    fragments = {
        "ssh-load-node",
        "runnerHome",
        "sshPort",
        "sshUser",
        "storageKey",
    }
    for target in load_node_targets():
        if target.host == target.service and target.port == 22:
            continue
        fragments.add(target.host)
        fragments.add(f"{target.host}:{target.port}")
        fragments.add(f"[{target.host}]:{target.port}")
        if target.port != 22:
            fragments.add(str(target.port))
    return sorted(fragments)


def assert_run_report(session: base.ApiSession, run_id: str, node_ids: list[str]) -> None:
    report, _headers = base.http_json(
        session.opener,
        "GET",
        f"/api/v1/runs/{run_id}",
        headers={"x-workspace-id": session.workspace_id},
    )
    if report["verdict"]["slaResult"] != "not_evaluated":
        raise AssertionError(f"Unexpected SLA result for no-SLA run: {report['verdict']}")
    allocated = report.get("allocatedNodes") or []
    if len(allocated) != len(node_ids) or {row["id"] for row in allocated} != set(node_ids):
        raise AssertionError(f"Run Report missing two allocated nodes: {allocated}")
    encoded = json.dumps(report, sort_keys=True)
    for fragment in forbidden_node_detail_fragments():
        if fragment in encoded:
            raise AssertionError(f"Run Report exposed sensitive node/storage detail: {fragment}")
    artifacts, _headers = base.http_json(
        session.opener,
        "GET",
        f"/api/v1/runs/{run_id}/artifacts",
        headers={"x-workspace-id": session.workspace_id},
    )
    items = artifacts.get("items") or []
    if not items or {item.get("nodeId") for item in items} != set(node_ids):
        raise AssertionError(f"Run artifacts response missing node ownership: {items}")
    encoded_artifacts = json.dumps(artifacts, sort_keys=True)
    for fragment in forbidden_node_detail_fragments():
        if fragment in encoded_artifacts:
            raise AssertionError(f"Run artifacts response exposed sensitive detail: {fragment}")


def assert_leases_released_and_nodes_idle(run_id: str, node_ids: list[str]) -> None:
    leases = base.fetch_all("select * from node_leases where run_id = %s", (run_id,))
    if len(leases) != len(node_ids):
        raise AssertionError(f"Expected two leases: {leases}")
    if any(row["released_at"] is None for row in leases):
        raise AssertionError(f"Expected all leases released: {leases}")
    active = base.fetch_all(
        "select * from node_leases where node_id = any(%s) and released_at is null",
        (node_ids,),
    )
    if active:
        raise AssertionError(f"Nodes still have active leases: {active}")
    for node_id in node_ids:
        base.assert_node_idle(node_id)


def assert_remote_run_directories_removed(run_id: str) -> None:
    command = f"test ! -e {posixpath.join(base.RUNNER_HOME, 'runs', run_id)!r}"

    def removed() -> bool:
        for service in SSH_SERVICES:
            result = base.run_command(
                base.compose_cmd("exec", "-T", service, "bash", "-lc", command), check=False
            )
            if result.returncode != 0:
                print(
                    f"Waiting for run directory cleanup on {service} for {run_id}:\n{result.stdout}"
                )
                return False
        return True

    base.wait_until("two-node remote run directory cleanup", 60, removed)


def assert_remote_processes_clean(run_id: str) -> None:
    command = f"""
set -eu
pidfile={posixpath.join(base.RUNNER_HOME, "runs", run_id, "workload.pid")}
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
        for service in SSH_SERVICES:
            result = base.run_command(
                base.compose_cmd("exec", "-T", service, "bash", "-lc", command), check=False
            )
            if result.returncode != 0:
                print(f"Waiting for process cleanup on {service} for {run_id}:\n{result.stdout}")
                return False
        return True

    base.wait_until("two-node remote process cleanup", 60, clean)


def verify_stopped_two_node_run(session: base.ApiSession, run_id: str, node_ids: list[str]) -> None:
    assert_initial_allocation_state(run_id, node_ids)
    wait_for_node_callbacks(run_id, node_ids, "accepted")
    wait_for_node_callbacks(run_id, node_ids, "running")
    wait_for_allocation_state(run_id, node_ids, {"running"})
    expect_callback_mismatch_forbidden(run_id, node_ids[0], node_ids[1])
    expect_artifact_mismatch_forbidden(run_id, node_ids[0], node_ids[1])
    first_stop = base.stop_run(session, run_id, expected_status=(200, 202))
    second_stop = base.stop_run(session, run_id, expected_status=(200, 202))
    if first_stop["state"] != "stopping" or second_stop["state"] != "stopping":
        raise AssertionError(f"Stop was not idempotent: {first_stop}, {second_stop}")
    base.poll_run_state(run_id, {"aborted"}, 180)
    wait_for_node_callbacks(run_id, node_ids, "aborted")
    wait_for_allocation_state(run_id, node_ids, {"aborted", "failed"})
    assert_two_node_artifacts(run_id, node_ids, require_final_stats=False)
    assert_run_report(session, run_id, node_ids)
    assert_leases_released_and_nodes_idle(run_id, node_ids)
    assert_remote_processes_clean(run_id)
    assert_remote_run_directories_removed(run_id)


def run_smoke() -> None:
    session = base.register_user()
    plan_id, node_ids = create_assets(session)
    plan, _headers = base.http_json(
        session.opener,
        "GET",
        f"/api/v1/test-plans/{plan_id}",
        headers={"x-workspace-id": session.workspace_id},
    )
    run = create_two_node_run(session, plan, node_ids)
    print(f"Started P1-01 SSH two-node Run: {run['id']}")
    verify_stopped_two_node_run(session, run["id"], node_ids)
    print(f"Stopped P1-01 SSH two-node Run: {run['id']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify P1-01 two-node Standard Run over SSH.")
    parser.add_argument("--build-app", action="store_true", help="Build API images before running.")
    parser.add_argument("--build-ssh", action="store_true", help="Build SSH image before running.")
    parser.add_argument(
        "--keep-stack", action="store_true", help="Leave Docker Compose stack running."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        setup_stack(build_app=args.build_app, build_ssh=args.build_ssh)
        run_smoke()
    except Exception as exc:  # noqa: BLE001 - smoke tool prints actionable diagnostics.
        base.diagnostics()
        print(f"P1-01 SSH two-node smoke failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_stack:
            base.run_command(base.compose_cmd("down", "-v"), check=False)
    print("P1-01 SSH two-node smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
