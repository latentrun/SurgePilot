from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
import json
import re
import sys
from pathlib import Path
from typing import Sequence

import verify_p0_api_main_flow_e2e as base

ARCHIVE_ROOT = Path("tmp/e2e-results")
SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class CreatedToken:
    token_id: str
    public_id: str
    plaintext: str


@dataclass
class LifecycleSummary:
    email: str
    workspace_id: str
    token_public_ids: list[str]
    run_id: str
    mode: str
    token_ids: list[str] = field(default_factory=list, repr=False)


def future_expiry() -> str:
    return (datetime.now(UTC) + timedelta(days=30)).isoformat().replace("+00:00", "Z")


def sanitize_segment(value: str) -> str:
    return SAFE_SEGMENT.sub("-", value).strip("-") or "unknown"


def archive_path(*, root: Path = ARCHIVE_ROOT, run_id: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / f"{stamp}-public-api-lifecycle-{sanitize_segment(run_id)}"


def write_archive(summary: LifecycleSummary, *, root: Path = ARCHIVE_ROOT) -> Path:
    archive = archive_path(root=root, run_id=summary.run_id)
    archive.mkdir(parents=True, exist_ok=True)
    payload = asdict(summary)
    payload.pop("token_ids", None)
    (archive / "summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return archive


def write_best_effort(archive: Path, filename: str, producer) -> None:
    try:
        content = producer()
    except Exception as exc:  # noqa: BLE001 - archive should not mask E2E result.
        content = f"archive collection failed: {exc}\n"
    (archive / filename).write_text(content)


def archive_runtime_evidence(summary: LifecycleSummary) -> Path:
    archive = write_archive(summary)
    print(f"Public lifecycle archive path: {archive}")
    write_best_effort(
        archive,
        "compose-ps.txt",
        lambda: base.run_command(base.compose_cmd("ps"), check=False).stdout,
    )
    write_best_effort(
        archive,
        "compose-logs-tail.txt",
        lambda: (
            base.run_command(
                base.compose_cmd("logs", "--no-color", "--tail=240"), check=False
            ).stdout
        ),
    )
    write_best_effort(
        archive,
        "db-run-rows.json",
        lambda: (
            base.run_command(
                base.compose_cmd(
                    "exec",
                    "-T",
                    "postgres",
                    "psql",
                    "-U",
                    "surgepilot",
                    "-d",
                    "surgepilot",
                    "-tAc",
                    "select row_to_json(r) from runs r where id = '"
                    + summary.run_id.replace("'", "''")
                    + "'",
                ),
                check=False,
            ).stdout
        ),
    )
    write_best_effort(
        archive,
        "minio-objects.txt",
        lambda: (
            "\n".join(
                obj.object_name or ""
                for obj in base.minio_client().list_objects(base.MINIO_BUCKET, recursive=True)
            )
            + "\n"
        ),
    )
    return archive


def session_headers(session: base.ApiSession) -> dict[str, str]:
    return base.api_headers(session)


def public_headers(token: CreatedToken, workspace_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token.plaintext}", "x-workspace-id": workspace_id}


def create_api_token(session: base.ApiSession, *, name: str, scopes: list[str]) -> CreatedToken:
    data, _headers, _status = base.http_json(
        session.opener,
        "POST",
        "/api/v1/account/api-tokens",
        payload={
            "name": name,
            "scopes": scopes,
            "workspaceAllowlist": [session.workspace_id],
            "expiresAt": future_expiry(),
        },
        headers=session_headers(session),
        expected_status=201,
    )
    token = data["token"]
    return CreatedToken(
        token_id=token["id"],
        public_id=token["publicId"],
        plaintext=token["plaintext"],
    )


def delete_session_resource(session: base.ApiSession, path: str) -> None:
    base.http_json(
        session.opener,
        "DELETE",
        path,
        headers=session_headers(session),
        expected_status=(204, 404),
    )


def cleanup_created_data(session: base.ApiSession, summary: LifecycleSummary) -> None:
    for token_id in summary.token_ids:
        delete_session_resource(session, f"/api/v1/account/api-tokens/{token_id}")


def public_json(
    session: base.ApiSession,
    method: str,
    path: str,
    token: CreatedToken,
    *,
    payload: dict | None = None,
    expected_status: int | tuple[int, ...] = 200,
) -> dict:
    data, _headers, _status = base.http_json(
        session.opener,
        method,
        path,
        payload=payload,
        headers=public_headers(token, session.workspace_id),
        expected_status=expected_status,
    )
    base.assert_no_forbidden_keys(data)
    return data


def scenario_payload(name: str) -> dict:
    return {
        "name": name,
        "description": "Public API lifecycle scenario.",
        "tags": ["p2-02", "public-lifecycle"],
        "baseUrlExpression": "${base_url}",
        "globalHeaders": [
            {"id": base.new_ulid_like(), "name": "x-public-e2e", "value": "true", "enabled": True}
        ],
        "variables": [
            {"id": base.new_ulid_like(), "name": "client", "value": "public", "enabled": True}
        ],
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
                "id": base.new_ulid_like(),
                "enabled": True,
                "name": "GET public lifecycle target",
                "method": "GET",
                "path": base.target_path(),
                "queryParams": [],
                "headers": [],
                "body": {"type": "none", "contentType": None, "rawText": None, "formFields": []},
                "uploadFiles": [],
                "extractors": [],
                "assertions": [
                    {
                        "id": base.new_ulid_like(),
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


def test_plan_payload(*, scenario_id: str, env_group_id: str, node_id: str) -> dict:
    return {
        "name": "Public API Lifecycle Plan",
        "description": "P2-02 public API lifecycle E2E plan.",
        "tags": ["p2-02", "public-lifecycle"],
        "envGroupId": env_group_id,
        "runMode": "sequential",
        "resource": {"mode": "manual", "poolType": "private", "selectedNodeId": node_id},
        "scenarioItems": [
            {
                "id": base.new_ulid_like(),
                "scenarioId": scenario_id,
                "enabled": True,
                "order": 0,
                "loadSettings": {
                    "concurrencyPerNode": 1,
                    "rampUpSeconds": 0,
                    "holdForSeconds": 45,
                    "iterations": None,
                    "targetRps": None,
                    "steps": None,
                    "delaySeconds": 0,
                },
            }
        ],
        "slaRules": [],
    }


def create_setup_load_node(session: base.ApiSession) -> dict:
    ssh_host_key = base.scan_load_node_ssh_host_key(
        session,
        host=base.NODE_SSH_HOST,
        ssh_port=base.NODE_SSH_PORT,
    )
    node = base.create_json(
        session,
        "/api/v1/load-nodes",
        base.load_node_payload(ssh_host_key),
    )
    base.initialize_node(session, node["id"])
    return node


def wait_public_run_state(
    session: base.ApiSession, token: CreatedToken, run_id: str, expected: set[str], timeout: int
) -> dict:
    current: dict | None = None

    def reached() -> bool:
        nonlocal current
        current = public_json(session, "GET", f"/api/public/v1/runs/{run_id}", token)
        state = current["verdict"]["state"]
        if state in {"failed", "aborted", "finished"} and state not in expected:
            raise base.TerminalE2EFailure(f"Run reached unexpected terminal state: {current}")
        return state in expected

    base.wait_until(f"public Run {run_id} state in {sorted(expected)}", timeout, reached)
    assert current is not None
    return current


def run_public_lifecycle(data_mode: str) -> LifecycleSummary:
    session = base.register_user("p2-02-public-lifecycle")
    read_token = create_api_token(session, name="Lifecycle read", scopes=["read"])
    config_token = create_api_token(session, name="Lifecycle config", scopes=["config:write"])
    run_token = create_api_token(session, name="Lifecycle run", scopes=["run"])
    node = create_setup_load_node(session)

    env_group = public_json(
        session,
        "POST",
        "/api/public/v1/env-groups",
        config_token,
        payload={
            "name": "Public API Lifecycle Env",
            "description": "Created by public API lifecycle E2E.",
            "variables": {"base_url": {"type": "plain", "value": base.target_base_url()}},
        },
        expected_status=201,
    )
    scenario = public_json(
        session,
        "POST",
        "/api/public/v1/scenarios",
        config_token,
        payload=scenario_payload("Public API Lifecycle Scenario"),
        expected_status=201,
    )
    public_json(session, "GET", "/api/public/v1/scenarios", read_token)
    public_json(session, "GET", f"/api/public/v1/scenarios/{scenario['id']}", read_token)
    plan = public_json(
        session,
        "POST",
        "/api/public/v1/test-plans",
        config_token,
        payload=test_plan_payload(
            scenario_id=scenario["id"], env_group_id=env_group["id"], node_id=node["id"]
        ),
        expected_status=201,
    )
    public_json(session, "GET", "/api/public/v1/test-plans", read_token)
    public_json(session, "GET", f"/api/public/v1/test-plans/{plan['id']}", read_token)

    run = public_json(
        session,
        "POST",
        "/api/public/v1/runs",
        run_token,
        payload={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": plan["id"],
            "expectedSourceRevision": plan["revision"],
        },
        expected_status=201,
    )
    run_id = run["id"]
    print(f"Started Public API lifecycle Run: {run_id}")
    wait_public_run_state(session, run_token, run_id, {"running"}, 150)
    first_stop = public_json(
        session, "POST", f"/api/public/v1/runs/{run_id}/stop", run_token, expected_status=(200, 202)
    )
    second_stop = public_json(
        session, "POST", f"/api/public/v1/runs/{run_id}/stop", run_token, expected_status=(200, 202)
    )
    if first_stop.get("duplicate") is not False or second_stop.get("duplicate") is not True:
        raise AssertionError(f"Public Stop was not idempotent: {first_stop}, {second_stop}")
    wait_public_run_state(session, run_token, run_id, {"aborted"}, 180)
    public_json(session, "GET", "/api/public/v1/runs", run_token)
    public_json(session, "GET", f"/api/public/v1/runs/{run_id}/report", run_token)

    summary = LifecycleSummary(
        email=session.email,
        workspace_id=session.workspace_id,
        token_public_ids=[read_token.public_id, config_token.public_id, run_token.public_id],
        token_ids=[read_token.token_id, config_token.token_id, run_token.token_id],
        run_id=run_id,
        mode=data_mode,
    )
    if data_mode == "cleanup":
        cleanup_created_data(session, summary)
    return summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify P2-02 Public API lifecycle E2E.")
    parser.add_argument("--build-app", action="store_true", help="Build API images before running.")
    parser.add_argument(
        "--build-ssh", action="store_true", help="Build SSH load-node image before running."
    )
    parser.add_argument(
        "--keep-stack", action="store_true", help="Leave Docker Compose stack running."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--cleanup-data", dest="data_mode", action="store_const", const="cleanup")
    mode.add_argument("--retain-data", dest="data_mode", action="store_const", const="retain")
    parser.set_defaults(data_mode="cleanup")
    args = parser.parse_args(argv)
    if args.data_mode == "retain":
        args.keep_stack = True
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    keep_data = args.data_mode == "retain"
    try:
        with base.stack_context(
            build_app=args.build_app,
            build_ssh=args.build_ssh,
            keep_stack=args.keep_stack,
            keep_data=keep_data,
        ):
            summary = run_public_lifecycle(args.data_mode)
            archive = archive_runtime_evidence(summary)
            print(f"Public lifecycle workspace: {summary.workspace_id}")
            print(f"Public lifecycle token public IDs: {', '.join(summary.token_public_ids)}")
            print(f"Public lifecycle run ID: {summary.run_id}")
            print(f"Public lifecycle archive: {archive}")
    except Exception as exc:  # noqa: BLE001 - verifier prints actionable diagnostics.
        print(f"P2-02 Public API lifecycle e2e failed: {exc}", file=sys.stderr)
        return 1
    print("P2-02 Public API lifecycle e2e passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
