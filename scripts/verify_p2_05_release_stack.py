"""Verify the tagged-release stack through a container-backed SSH fixture and LAN origins."""

from __future__ import annotations

import csv
from http.cookiejar import CookieJar
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_p0_api_main_flow_e2e import (  # noqa: E402
    API_BASE_URL,
    ApiSession,
    LocalhostSecureCookiePolicy,
    api_headers,
    create_json,
    get_json,
    http_bytes,
    http_json,
    initialize_node,
    new_ulid_like,
    poll_report_state,
    read_headers,
    register_user,
    scan_load_node_ssh_host_key,
)


TARGET_URL = os.environ.get(
    "SURGEPILOT_E2E_TARGET_URL", "http://api.surgepilot.test:8000/api/healthz"
)
INFLUXDB_ORG = os.environ.get("SURGEPILOT_MONITORING_INFLUXDB_ORG", "surgepilot")
INFLUXDB_BUCKET = os.environ.get("SURGEPILOT_MONITORING_INFLUXDB_BUCKET", "jmeter")
REQUIRED_MEASUREMENTS = {"requestsRaw", "virtualUsers", "testStartEnd"}
PRODUCT_VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
SKILL_OPENAPI_PATH = "surgepilot-public-api/references/public-api.openapi.json"
UPGRADE_STATE_FILE = os.environ.get("SURGEPILOT_E2E_UPGRADE_STATE_FILE")
REUSE_UPGRADE_STATE = os.environ.get("SURGEPILOT_E2E_REUSE_UPGRADE_STATE") == "true"


def target_origin() -> str:
    parsed = urllib.parse.urlsplit(TARGET_URL)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("SURGEPILOT_E2E_TARGET_URL must be an absolute HTTP URL")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def expected_product_version() -> str:
    value = os.environ.get("SURGEPILOT_E2E_EXPECTED_PRODUCT_VERSION")
    if not value:
        raise RuntimeError("SURGEPILOT_E2E_EXPECTED_PRODUCT_VERSION is required")
    if not PRODUCT_VERSION_PATTERN.fullmatch(value) or value == "0.0.0":
        raise RuntimeError("SURGEPILOT_E2E_EXPECTED_PRODUCT_VERSION must be canonical X.Y.Z")
    return value


def expected_runtime_version() -> str:
    return f"v{expected_product_version()}"


def fetch_runtime_openapi() -> dict:
    with urllib.request.urlopen(f"{API_BASE_URL}/api/openapi.json", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def download_skill_bundle(session) -> bytes:
    request = urllib.request.Request(
        f"{API_BASE_URL}/api/v1/account/ai-skill/download",
        method="GET",
    )
    with session.opener.open(request, timeout=30) as response:
        return response.read()


def _assert_version(surface: str, actual: object, expected: str) -> None:
    if actual != expected:
        raise RuntimeError(f"{surface} version mismatch: expected {expected}, got {actual!r}")


def get_catalog_content(session, spec_id: str) -> dict:
    document, _headers, _status = http_json(
        session.opener,
        "GET",
        f"/api/v1/api-catalog/specs/{spec_id}/content",
        headers=read_headers(session),
        expected_status=200,
    )
    if not isinstance(document, dict):
        raise RuntimeError("system Catalog content is invalid")
    return document


def verify_product_identity(
    session,
    node_id: str,
) -> None:
    expected = expected_product_version()
    runtime_openapi = fetch_runtime_openapi()
    _assert_version("runtime OpenAPI", runtime_openapi.get("info", {}).get("version"), expected)

    system_specs = []
    offset = 0
    expected_total = None
    while True:
        catalog = get_json(session, f"/api/v1/api-catalog/specs?limit=100&offset={offset}")
        items = catalog.get("items")
        total = catalog.get("total")
        if (
            not isinstance(items, list)
            or not isinstance(total, int)
            or total < 0
            or (expected_total is not None and total != expected_total)
            or len(items) > 100
            or offset + len(items) > total
            or (offset < total and not items)
        ):
            raise RuntimeError("system Catalog listing is incomplete or invalid")
        expected_total = total
        system_specs.extend(
            item
            for item in items
            if item.get("name") == "SurgePilot API"
            and item.get("filename") == "surgepilot-api.openapi.json"
        )
        offset += len(items)
        if offset == total:
            break
    if len(system_specs) != 1:
        raise RuntimeError(
            f"system Catalog entry mismatch: expected one SurgePilot API entry, got {len(system_specs)}"
        )
    _assert_version(
        "system Catalog",
        system_specs[0].get("documentVersion"),
        expected,
    )
    spec_id = system_specs[0].get("id")
    if not isinstance(spec_id, str) or not spec_id:
        raise RuntimeError("system Catalog entry has no spec ID")
    stored_document = get_catalog_content(session, spec_id)
    info = stored_document.get("info", {})
    _assert_version("system Catalog content", info.get("version"), expected)
    if info.get("title") != "SurgePilot API":
        raise RuntimeError("system Catalog content title mismatch")

    try:
        with ZipFile(BytesIO(download_skill_bundle(session))) as archive:
            skill_openapi = json.loads(archive.read(SKILL_OPENAPI_PATH))
    except (BadZipFile, KeyError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("AI skill OpenAPI is unavailable or invalid") from exc
    _assert_version("AI skill OpenAPI", skill_openapi.get("info", {}).get("version"), expected)

    node = get_json(session, f"/api/v1/load-nodes/{node_id}")
    _assert_version("Runner", node.get("runnerVersion"), expected)


def scenario_payload() -> dict:
    return {
        "name": "P2-06 Release LAN Debug",
        "description": "Validate the released Runtime through the published LAN API origin.",
        "tags": ["p2-06", "release", "lan"],
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
                "id": new_ulid_like(),
                "enabled": True,
                "name": "GET SurgePilot health",
                "method": "GET",
                "path": "/api/healthz",
                "queryParams": [],
                "headers": [],
                "body": {
                    "type": "none",
                    "contentType": None,
                    "rawText": None,
                    "formFields": [],
                },
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


def standard_plan_payload(*, scenario_id: str, env_group_id: str, node_id: str) -> dict:
    return {
        "name": "P2-06 Release LAN Monitoring",
        "description": "Validate Standard Run monitoring through the published LAN origins.",
        "tags": ["p2-06", "release", "lan"],
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
                    "holdForSeconds": 6,
                    "iterations": None,
                    "targetRps": None,
                    "steps": None,
                    "delaySeconds": 0,
                },
            }
        ],
        "slaRules": [],
    }


def _influxdb_token() -> str:
    token_file = os.environ.get("SURGEPILOT_E2E_INFLUXDB_TOKEN_FILE")
    if not token_file:
        raise RuntimeError("SURGEPILOT_E2E_INFLUXDB_TOKEN_FILE is required")
    token = Path(token_file).read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError("InfluxDB token file is empty")
    return token


def query_measurements(run_id: str) -> set[str]:
    query_url = os.environ.get("SURGEPILOT_E2E_INFLUXDB_QUERY_URL")
    if not query_url:
        raise RuntimeError("SURGEPILOT_E2E_INFLUXDB_QUERY_URL is required")
    flux = f"""
from(bucket: {json.dumps(INFLUXDB_BUCKET)})
  |> range(start: -30m)
  |> filter(fn: (r) => r.runId == {json.dumps(run_id)})
  |> keep(columns: ["_measurement"])
  |> distinct(column: "_measurement")
"""
    request = urllib.request.Request(
        f"{query_url.rstrip('/')}/api/v2/query?org={INFLUXDB_ORG}",
        data=flux.encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Token {_influxdb_token()}",
            "Accept": "application/csv",
            "Content-Type": "application/vnd.flux",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"InfluxDB query failed: {exc.code} {exc.read().decode()}") from exc
    measurements: set[str] = set()
    for row in csv.DictReader(line for line in body.splitlines() if not line.startswith("#")):
        for key in ("_measurement", "_value"):
            value = row.get(key)
            if value:
                measurements.add(value)
    return measurements


def wait_for_monitoring_points(run_id: str) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        missing = REQUIRED_MEASUREMENTS - query_measurements(run_id)
        if not missing:
            return
        print(f"Waiting for InfluxDB measurements for {run_id}; missing {sorted(missing)}")
        time.sleep(2)
    raise RuntimeError(f"Standard Run did not publish required InfluxDB measurements: {run_id}")


def assert_no_monitoring_secrets(*payloads: dict) -> None:
    serialized = "\n".join(json.dumps(payload, sort_keys=True) for payload in payloads)
    sensitive_values = (
        _influxdb_token(),
        os.environ.get("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"),
        os.environ.get("SURGEPILOT_E2E_INFLUXDB_QUERY_URL"),
    )
    if any(value and value in serialized for value in sensitive_values):
        raise RuntimeError("Release acceptance response exposed InfluxDB token or node-write URL")


def login_existing_user(email: str) -> ApiSession:
    cookie_jar = CookieJar(policy=LocalhostSecureCookiePolicy())
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    data, _headers, _status = http_json(
        opener,
        "POST",
        "/api/v1/auth/login",
        payload={"email": email, "password": "password123"},
        expected_status=200,
    )
    return ApiSession(
        csrf_token=data["csrfToken"],
        workspace_id=data["defaultWorkspace"]["id"],
        email=data["user"]["email"],
        opener=opener,
    )


def persist_upgrade_state(
    *,
    session: ApiSession,
    node: dict,
    env_group: dict,
    scenario: dict,
    source_run: dict,
) -> None:
    if not UPGRADE_STATE_FILE:
        return
    artifacts = get_json(session, f"/api/v1/runs/{source_run['id']}/artifacts")
    items = artifacts.get("items") or []
    if not items:
        raise RuntimeError("Source release Run did not preserve a MinIO-backed artifact")
    artifact = items[0]
    state = {
        "email": session.email,
        "workspaceId": session.workspace_id,
        "nodeId": node["id"],
        "sourceRuntimeVersion": get_json(session, f"/api/v1/load-nodes/{node['id']}")[
            "runtimeVersion"
        ],
        "envGroupId": env_group["id"],
        "scenarioId": scenario["id"],
        "scenarioRevision": scenario["revision"],
        "sourceRunId": source_run["id"],
        "artifactId": artifact["id"],
        "artifactSha256": artifact["sha256"],
    }
    path = Path(UPGRADE_STATE_FILE)
    path.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def verify_preserved_upgrade_state() -> None:
    if not UPGRADE_STATE_FILE:
        raise RuntimeError("SURGEPILOT_E2E_UPGRADE_STATE_FILE is required for upgrade reuse")
    state = json.loads(Path(UPGRADE_STATE_FILE).read_text(encoding="utf-8"))
    target_runtime_version = expected_runtime_version()
    session = login_existing_user(str(state["email"]))
    if session.workspace_id != state["workspaceId"]:
        raise RuntimeError("Upgrade did not preserve the source Workspace identity")

    node = get_json(session, f"/api/v1/load-nodes/{state['nodeId']}")
    if (
        node.get("status") != "idle"
        or node.get("credentialConfigured") is not True
        or node.get("runtimeVersion") != state["sourceRuntimeVersion"]
        or node.get("runtimeVersion") == target_runtime_version
    ):
        raise RuntimeError(f"Source Load Node eligibility state was not preserved: {node}")

    rejected, _headers, status = http_json(
        session.opener,
        "POST",
        "/api/v1/runs",
        payload={
            "runType": "debug",
            "sourceType": "debug_scenario",
            "sourceId": state["scenarioId"],
            "expectedSourceRevision": state["scenarioRevision"],
            "envGroupId": state["envGroupId"],
            "selectedNodeId": state["nodeId"],
        },
        headers=api_headers(session),
        expected_status=409,
    )
    if status != 409:
        raise RuntimeError(f"Old Runtime unexpectedly accepted a target Run: {rejected}")

    source_report = get_json(session, f"/api/v1/runs/{state['sourceRunId']}")
    if source_report.get("verdict", {}).get("state") != "finished":
        raise RuntimeError("Upgrade did not preserve the source Run record")
    artifacts = get_json(session, f"/api/v1/runs/{state['sourceRunId']}/artifacts")
    artifact = next(
        (item for item in artifacts.get("items", []) if item.get("id") == state["artifactId"]),
        None,
    )
    if artifact is None or artifact.get("sha256") != state["artifactSha256"]:
        raise RuntimeError("Upgrade did not preserve source artifact metadata")
    artifact_bytes, _headers, _status = http_bytes(
        session.opener,
        "GET",
        artifact["downloadUrl"],
        headers=read_headers(session),
    )
    if not artifact_bytes:
        raise RuntimeError("Upgrade did not preserve the MinIO-backed source artifact")

    initialize_node(session, str(state["nodeId"]))
    initialized = get_json(session, f"/api/v1/load-nodes/{state['nodeId']}")
    if (
        initialized.get("credentialConfigured") is not True
        or initialized.get("runtimeVersion") != target_runtime_version
    ):
        raise RuntimeError(
            "Explicit reinitialization did not preserve credentials and install target: "
            f"{initialized}"
        )
    verify_product_identity(session, str(state["nodeId"]))

    post_run = create_json(
        session,
        "/api/v1/runs",
        {
            "runType": "debug",
            "sourceType": "debug_scenario",
            "sourceId": state["scenarioId"],
            "expectedSourceRevision": state["scenarioRevision"],
            "envGroupId": state["envGroupId"],
            "selectedNodeId": state["nodeId"],
        },
    )
    post_report = poll_report_state(session, post_run["id"], {"finished"}, 300)
    if post_report["verdict"]["state"] != "finished":
        raise RuntimeError(f"Post-upgrade Run in preserved Workspace did not finish: {post_report}")


def verify_release_stack() -> None:
    if REUSE_UPGRADE_STATE:
        verify_preserved_upgrade_state()
        return
    password_path = Path(
        os.environ.get(
            "SURGEPILOT_E2E_NODE_SSH_PASSWORD_FILE",
            ".surgepilot/secrets/demo-load-node-password.secret",
        )
    )
    password = password_path.read_text(encoding="utf-8").strip()
    if not password:
        raise RuntimeError("Demo Load Node password file is empty")

    session = register_user("p2-05-release")
    host_key = scan_load_node_ssh_host_key(session, host="demo-load-node", ssh_port=22)
    node = create_json(
        session,
        "/api/v1/load-nodes",
        {
            "scope": "workspace",
            "host": "demo-load-node",
            "sshPort": 22,
            "sshUser": "surgepilot",
            "runnerHome": "/opt/surgepilot/runner",
            "credential": {"authType": "password", "password": password},
            "sshHostKey": {
                "algorithm": host_key["algorithm"],
                "publicKey": host_key["publicKey"],
                "fingerprintSha256": host_key["fingerprintSha256"],
            },
            "maintainer": "P2-05 release acceptance",
            "remark": "Container-backed SSH fixture using published LAN node-facing origins",
        },
    )
    initialize_node(session, node["id"])
    verify_product_identity(session, node["id"])
    env_group = create_json(
        session,
        "/api/v1/env-groups",
        {
            "name": "P2-06 Release LAN Target",
            "description": "Published LAN release acceptance target.",
            "variables": {"base_url": {"type": "plain", "value": target_origin()}},
        },
    )
    scenario = create_json(session, "/api/v1/scenarios", scenario_payload())
    run = create_json(
        session,
        "/api/v1/runs",
        {
            "runType": "debug",
            "sourceType": "debug_scenario",
            "sourceId": scenario["id"],
            "expectedSourceRevision": scenario["revision"],
            "envGroupId": env_group["id"],
            "selectedNodeId": node["id"],
        },
    )
    report = poll_report_state(session, run["id"], {"finished"}, 300)
    if report["verdict"]["state"] != "finished":
        raise RuntimeError(f"Release Debug Run did not finish: {report}")
    assert_no_monitoring_secrets(report)

    plan = create_json(
        session,
        "/api/v1/test-plans",
        standard_plan_payload(
            scenario_id=scenario["id"],
            env_group_id=env_group["id"],
            node_id=node["id"],
        ),
    )
    if plan.get("runnable") is not True:
        raise RuntimeError(f"Release Standard Run Test Plan is not runnable: {plan}")
    standard_run = create_json(
        session,
        "/api/v1/runs",
        {
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": plan["id"],
            "expectedSourceRevision": plan["revision"],
        },
    )
    standard_report = poll_report_state(session, standard_run["id"], {"finished"}, 300)
    if standard_report["verdict"]["state"] != "finished":
        raise RuntimeError(f"Release Standard Run did not finish: {standard_report}")
    assert_no_monitoring_secrets(standard_report)
    wait_for_monitoring_points(standard_run["id"])

    run_monitoring = get_json(session, f"/api/v1/runs/{standard_run['id']}/monitoring")
    platform_url = run_monitoring.get("platformMonitoringUrl")
    iframe_url = run_monitoring.get("iframeUrl")
    if (
        run_monitoring.get("runId") != standard_run["id"]
        or run_monitoring.get("enabledForRun") is not True
        or run_monitoring.get("status") != "enabled"
        or not platform_url
        or standard_run["id"] not in platform_url
        or not iframe_url
        or standard_run["id"] not in iframe_url
    ):
        raise RuntimeError(f"Release Standard Run Monitoring link is not ready: {run_monitoring}")
    assert_no_monitoring_secrets(run_monitoring)

    monitoring = get_json(session, "/api/v1/monitoring/embed")
    assert_no_monitoring_secrets(monitoring)
    if monitoring.get("status") != "ready" or not monitoring.get("iframeUrl"):
        raise RuntimeError(f"Release Monitoring entry is not ready: {monitoring}")
    persist_upgrade_state(
        session=session,
        node=node,
        env_group=env_group,
        scenario=scenario,
        source_run=standard_run,
    )


def main() -> int:
    try:
        verify_release_stack()
    except Exception as exc:  # noqa: BLE001 - E2E boundary prints one actionable failure.
        print(f"P2-05 release acceptance failed: {exc}", file=sys.stderr)
        return 1
    print(
        "P2-06 release LAN acceptance passed: node initialization, Debug Run, Standard Run, "
        "InfluxDB measurements, report, and completed-Run Monitoring."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
