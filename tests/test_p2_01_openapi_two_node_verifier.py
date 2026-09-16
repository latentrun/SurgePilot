from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPT_DIR / "verify_p2_01_openapi_two_node_e2e.py"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location("verify_p2_01_openapi_two_node_e2e", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
verifier = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = verifier
spec.loader.exec_module(verifier)


def test_parse_args_defaults_to_cleanup_stack() -> None:
    args = verifier.parse_args([])

    assert args.build_app is False
    assert args.build_ssh is False
    assert args.keep_stack is False


def test_user_registration_payload_uses_unique_email(monkeypatch) -> None:
    monkeypatch.setattr(verifier.e2e, "unique_suffix", lambda: "20300706000102-abcdef12")

    payload = verifier.user_registration_payload()

    assert payload == {
        "email": "openapi-two-node-20300706000102-abcdef12@example.com",
        "displayName": "OpenAPI Two Node User",
        "password": "password123",
    }


def test_scenario_patch_payload_materializes_generated_drafts() -> None:
    ids = iter([f"01JSTEP00000000000000000{i:02d}" for i in range(1, 5)])
    scenario = {
        "id": "01JSCENARIO000000000000000",
        "revision": 3,
        "name": "OpenAPI generated scenario",
        "description": None,
        "tags": ["p2-01"],
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
    draft = {
        "name": "GET generated health",
        "method": "GET",
        "path": "/api/healthz",
        "queryParams": [{"name": "source", "value": "openapi"}],
        "headers": [],
        "body": {"type": "none", "contentType": None, "rawText": None, "formFields": []},
        "settings": {"timeoutMs": 30000, "followRedirects": True, "keepAlive": True},
    }

    payload = verifier.scenario_patch_payload(scenario, [draft], id_factory=lambda: next(ids))

    assert payload["expectedRevision"] == 3
    assert payload["steps"][0]["id"] == "01JSTEP0000000000000000001"
    assert payload["steps"][0]["queryParams"][0]["id"] == "01JSTEP0000000000000000002"
    assert payload["steps"][0]["assertions"] == []


def test_draft_generation_payload_includes_append_insert_plan() -> None:
    operation_ref = {"method": "GET", "path": "/api/healthz", "operationId": "getHealth"}

    payload = verifier.draft_generation_payload("01JSPEC000000000000000000", [operation_ref])

    assert payload == {
        "specId": "01JSPEC000000000000000000",
        "operationRefs": [operation_ref],
        "insert": {"mode": "append"},
    }


def test_env_group_payload_uses_unique_name(monkeypatch) -> None:
    monkeypatch.setattr(verifier.e2e, "unique_name", lambda prefix: f"{prefix} unique")

    payload = verifier.env_group_payload()

    assert payload["name"] == "OpenAPI Two Node Env unique"
    assert payload["variables"]["base_url"]["type"] == "plain"


def test_create_initialized_load_node_scans_and_persists_host_key(monkeypatch) -> None:
    session = object()
    target = SimpleNamespace(host="ssh-load-node", port=22)
    scanned_host_key = {
        "algorithm": "ssh-ed25519",
        "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAITestKey",
        "fingerprintSha256": "SHA256:testFingerprint",
    }
    created_payloads: list[dict] = []
    initialized_node_ids: list[str] = []

    monkeypatch.setattr(verifier.two_node, "load_node_target", lambda _service: target)
    monkeypatch.setattr(
        verifier.base,
        "scan_load_node_ssh_host_key",
        lambda actual_session, *, host, ssh_port: (
            scanned_host_key
            if (actual_session, host, ssh_port) == (session, target.host, target.port)
            else None
        ),
    )
    monkeypatch.setattr(
        verifier.two_node,
        "load_node_payload",
        lambda service, ssh_host_key: {
            "service": service,
            "sshHostKey": ssh_host_key,
        },
    )

    def create_json(actual_session, path, payload):
        assert actual_session is session
        assert path == "/api/v1/load-nodes"
        created_payloads.append(payload)
        return {"id": "01JLOADNODE000000000000000"}

    monkeypatch.setattr(verifier.base, "create_json", create_json)
    monkeypatch.setattr(
        verifier.base,
        "initialize_node",
        lambda actual_session, node_id: (
            initialized_node_ids.append(node_id) if actual_session is session else None
        ),
    )

    node_id = verifier.create_initialized_load_node(session, "ssh-load-node")

    assert node_id == "01JLOADNODE000000000000000"
    assert created_payloads == [{"service": "ssh-load-node", "sshHostKey": scanned_host_key}]
    assert initialized_node_ids == [node_id]
