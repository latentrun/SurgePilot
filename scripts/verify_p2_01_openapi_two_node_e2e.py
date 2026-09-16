from __future__ import annotations

import argparse
from http.cookiejar import CookieJar
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Sequence
from uuid import uuid4

import surgepilot_e2e_helpers as e2e
import verify_p1_01_ssh_two_node_smoke as two_node

base = two_node.base


def user_registration_payload() -> dict[str, str]:
    return {
        "email": f"openapi-two-node-{e2e.unique_suffix()}@example.com",
        "displayName": "OpenAPI Two Node User",
        "password": "password123",
    }


def register_user() -> base.ApiSession:
    cookie_jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    data, _headers = base.http_json(
        opener,
        "POST",
        "/api/v1/auth/register",
        payload=user_registration_payload(),
        expected_status=201,
    )
    return base.ApiSession(
        csrf_token=data["csrfToken"],
        workspace_id=data["defaultWorkspace"]["id"],
        opener=opener,
    )


def _target_openapi_path() -> str:
    parsed = urllib.parse.urlparse(base.TARGET_URL)
    return parsed.path or "/api/healthz"


def openapi_spec_content() -> bytes:
    path = _target_openapi_path()
    return f"""openapi: 3.1.0
info:
  title: SurgePilot E2E Target
  version: 1.0.0
paths:
  {path}:
    get:
      operationId: getSurgePilotE2ETarget
      summary: Get SurgePilot E2E target health
      responses:
        '200':
          description: OK
""".encode()


def env_group_payload() -> dict[str, Any]:
    return {
        "name": e2e.unique_name("OpenAPI Two Node Env"),
        "description": "Created by the OpenAPI + two-node E2E verifier.",
        "variables": {"base_url": {"type": "plain", "value": base.target_base_url()}},
    }


def scenario_create_payload() -> dict[str, Any]:
    return {
        "name": e2e.unique_name("OpenAPI Generated Health Scenario"),
        "description": "Scenario populated from an OpenAPI Step draft by E2E automation.",
        "tags": ["p2-01", "p1-01", "openapi-two-node"],
        "baseUrlExpression": "${base_url}",
        "globalHeaders": [],
        "variables": [],
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
        "steps": [],
    }


def scenario_patch_payload(
    scenario: dict[str, Any],
    step_drafts: list[dict[str, Any]],
    *,
    id_factory: Callable[[], str] = e2e.new_ulid_like,
) -> dict[str, Any]:
    return {
        "expectedRevision": scenario["revision"],
        "name": scenario["name"],
        "description": scenario.get("description"),
        "tags": scenario.get("tags") or [],
        "baseUrlExpression": scenario.get("baseUrlExpression") or "${base_url}",
        "globalHeaders": scenario.get("globalHeaders") or [],
        "variables": scenario.get("variables") or [],
        "defaultSettings": scenario["defaultSettings"],
        "dataSources": scenario.get("dataSources") or [],
        "steps": [
            e2e.materialize_openapi_step_draft(draft, id_factory=id_factory)
            for draft in step_drafts
        ],
    }


def test_plan_payload(
    *, scenario_id: str, env_group_id: str, node_ids: list[str]
) -> dict[str, Any]:
    payload = two_node.test_plan_payload(scenario_id=scenario_id, node_ids=node_ids)
    payload["name"] = e2e.unique_name("OpenAPI Two Node Standard Run Plan")
    payload["description"] = "P2-01 OpenAPI Step Generation combined with P1-01 two-node run."
    payload["tags"] = ["p2-01", "p1-01", "openapi-two-node"]
    payload["envGroupId"] = env_group_id
    return payload


def read_json(session: base.ApiSession, path: str) -> dict[str, Any]:
    data, _headers = base.http_json(
        session.opener,
        "GET",
        path,
        headers={"x-workspace-id": session.workspace_id},
    )
    base.assert_no_secret_echo(data)
    return data


def patch_json(session: base.ApiSession, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    data, _headers = base.http_json(
        session.opener,
        "PATCH",
        path,
        payload=payload,
        headers=base.api_headers(session),
    )
    base.assert_no_secret_echo(data)
    return data


def draft_generation_payload(spec_id: str, operation_refs: list[dict[str, Any]]) -> dict[str, Any]:
    return {"specId": spec_id, "operationRefs": operation_refs, "insert": {"mode": "append"}}


def post_json(session: base.ApiSession, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    data, _headers = base.http_json(
        session.opener,
        "POST",
        path,
        payload=payload,
        headers=base.api_headers(session),
    )
    base.assert_no_secret_echo(data)
    return data


def upload_api_spec(session: base.ApiSession) -> dict[str, Any]:
    boundary = f"----surgepilot-openapi-two-node-{uuid4().hex}"
    filename = f"openapi-two-node-{uuid4().hex[:8]}.yaml"
    content = openapi_spec_content()
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            (
                'Content-Disposition: form-data; name="file"; '
                f'filename="{filename}"\r\n'
                "Content-Type: application/yaml\r\n\r\n"
            ).encode(),
            content,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    request = urllib.request.Request(
        f"{base.API_BASE_URL.rstrip()}/api/v1/api-catalog/specs",
        data=body,
        method="POST",
        headers={
            "accept": "application/json",
            "content-type": f"multipart/form-data; boundary={boundary}",
            **base.api_headers(session),
        },
    )
    try:
        with session.opener.open(request, timeout=30) as response:
            response_body = response.read().decode()
            data = json.loads(response_body) if response_body else {}
            if response.status != 201:
                raise base.SmokeFailure(f"API spec upload returned {response.status}: {data}")
            base.assert_no_secret_echo(data)
            return data
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode()
        raise base.SmokeFailure(f"API spec upload returned {exc.code}: {error_body}") from exc


def generated_step_drafts(
    session: base.ApiSession, *, scenario_id: str, spec_id: str
) -> list[dict]:
    operations = read_json(
        session,
        f"/api/v1/scenarios/{scenario_id}/openapi-step-generation/specs/{spec_id}/operations",
    )
    candidates = [
        item for item in operations.get("items", []) if item.get("supportedForGeneration")
    ]
    if not candidates:
        raise base.SmokeFailure(f"No supported OpenAPI operations found: {operations}")
    preview = post_json(
        session,
        f"/api/v1/scenarios/{scenario_id}/openapi-step-generation/drafts",
        draft_generation_payload(spec_id, [candidates[0]["ref"]]),
    )
    items = preview.get("items") or []
    drafts = [item["step"] for item in items if item.get("step")]
    if len(drafts) != 1:
        raise base.SmokeFailure(f"Expected one generated Step draft: {preview}")
    return drafts


def create_initialized_load_node(session: base.ApiSession, service: str) -> str:
    target = two_node.load_node_target(service)
    ssh_host_key = base.scan_load_node_ssh_host_key(
        session,
        host=target.host,
        ssh_port=target.port,
    )
    node = base.create_json(
        session,
        "/api/v1/load-nodes",
        two_node.load_node_payload(service, ssh_host_key),
    )
    base.initialize_node(session, node["id"])
    return node["id"]


def create_openapi_two_node_assets(session: base.ApiSession) -> tuple[str, list[str]]:
    spec = upload_api_spec(session)
    env_group = base.create_json(session, "/api/v1/env-groups", env_group_payload())
    scenario = base.create_json(session, "/api/v1/scenarios", scenario_create_payload())
    scenario = read_json(session, f"/api/v1/scenarios/{scenario['id']}")
    drafts = generated_step_drafts(session, scenario_id=scenario["id"], spec_id=spec["id"])
    patched = patch_json(
        session,
        f"/api/v1/scenarios/{scenario['id']}",
        scenario_patch_payload(scenario, drafts),
    )
    if len(patched.get("steps") or []) != 1:
        raise base.SmokeFailure(f"Generated Scenario was not persisted with one Step: {patched}")

    node_ids: list[str] = []
    for service in two_node.SSH_SERVICES:
        node_ids.append(create_initialized_load_node(session, service))

    plan = base.create_json(
        session,
        "/api/v1/test-plans",
        test_plan_payload(
            scenario_id=patched["id"], env_group_id=env_group["id"], node_ids=node_ids
        ),
    )
    return plan["id"], node_ids


def run_openapi_two_node_smoke() -> None:
    session = register_user()
    plan_id, node_ids = create_openapi_two_node_assets(session)
    plan = read_json(session, f"/api/v1/test-plans/{plan_id}")
    run = two_node.create_two_node_run(session, plan, node_ids)
    print(f"Started P2-01 OpenAPI + P1-01 two-node Run: {run['id']}")
    two_node.verify_stopped_two_node_run(session, run["id"], node_ids)
    print(f"Stopped P2-01 OpenAPI + P1-01 two-node Run: {run['id']}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify OpenAPI Step draft materialization with a two-node Standard Run."
    )
    parser.add_argument("--build-app", action="store_true", help="Build API images before running.")
    parser.add_argument("--build-ssh", action="store_true", help="Build SSH image before running.")
    parser.add_argument(
        "--keep-stack", action="store_true", help="Leave Docker Compose stack running."
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        two_node.setup_stack(build_app=args.build_app, build_ssh=args.build_ssh)
        run_openapi_two_node_smoke()
    except Exception as exc:  # noqa: BLE001 - verifier prints actionable diagnostics.
        base.diagnostics()
        print(f"P2-01 OpenAPI + P1-01 two-node e2e failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_stack:
            base.run_command(base.compose_cmd("down", "-v"), check=False)
    print("P2-01 OpenAPI + P1-01 two-node e2e passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
