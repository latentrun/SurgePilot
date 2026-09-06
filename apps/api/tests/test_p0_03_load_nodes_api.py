from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuditEvent, Workspace, WorkspaceMember
from app.models.load_nodes import LoadNode, LoadNodeCredential, LoadNodeInitializationAttempt
from app.services.ssh_remote import ScannedSshHostKey


async def register(client: AsyncClient, email: str, name: str = "User") -> tuple[str, str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": name, "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["csrfToken"], body["defaultWorkspace"]["id"], body["user"]["id"]


TRUSTED_HOST_KEY = {
    "algorithm": "ssh-ed25519",
    "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
    "fingerprintSha256": "SHA256:SurgePilotTrustedHostKey",
}


def scanned_key(
    *,
    host: str = "load-node-01.internal",
    port: int = 22,
    algorithm: str = TRUSTED_HOST_KEY["algorithm"],
    public_key: str = TRUSTED_HOST_KEY["publicKey"],
    fingerprint: str = TRUSTED_HOST_KEY["fingerprintSha256"],
) -> ScannedSshHostKey:
    return ScannedSshHostKey(
        host=host,
        port=port,
        algorithm=algorithm,
        public_key=public_key,
        fingerprint_sha256=fingerprint,
    )


@pytest.fixture(autouse=True)
def fake_host_key_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_scan(host: str, port: int, timeout_seconds: int) -> ScannedSshHostKey:
        _ = timeout_seconds
        return scanned_key(host=host, port=port)

    monkeypatch.setattr("app.services.load_nodes.scan_ssh_host_key", fake_scan)
    monkeypatch.setattr("app.routes.load_nodes.scan_ssh_host_key", fake_scan)


def password_payload(scope: str = "workspace", host: str = "load-node-01.internal") -> dict:
    return {
        "scope": scope,
        "host": host,
        "sshPort": 22,
        "sshUser": "surgepilot",
        "runnerHome": "/opt/surgepilot/runner",
        "sshHostKey": TRUSTED_HOST_KEY.copy(),
        "credential": {"authType": "password", "password": "submitted-secret"},
        "maintainer": "Performance Team",
        "remark": "Private capacity",
    }


def seed_other_workspace(db_session: Session, user_id: str) -> str:
    now = datetime.now(UTC)
    workspace = Workspace(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7D",
        name="Other Workspace",
        status="active",
        created_at=now,
        updated_at=now,
    )
    db_session.add(workspace)
    db_session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user_id, joined_at=now))
    db_session.flush()
    return workspace.id


@pytest.mark.anyio
async def test_load_node_auth_csrf_create_list_get_and_redaction(
    client: AsyncClient, db_session: Session
) -> None:
    unauthenticated = await client.get("/api/v1/load-nodes")
    assert unauthenticated.status_code == 401

    csrf, workspace_id, _user_id = await register(client, "nodes@example.com", "Node User")
    missing_csrf = await client.post("/api/v1/load-nodes", json=password_payload())
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "CSRF_TOKEN_REQUIRED"

    created = await client.post(
        "/api/v1/load-nodes",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=password_payload(),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["scope"] == "workspace"
    assert body["workspaceId"] == workspace_id
    assert body["host"] == "load-node-01.internal"
    assert body["sshHostKey"]["algorithm"] == "ssh-ed25519"
    assert body["sshHostKey"]["fingerprintSha256"] == "SHA256:SurgePilotTrustedHostKey"
    assert body["sshHostKey"]["knownHostsLine"] == (
        "load-node-01.internal ssh-ed25519 "
        "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC"
    )
    assert body["status"] == "uninitialized"
    assert body["credentialConfigured"] is True
    serialized = str(body)
    assert "submitted-secret" not in serialized
    assert "passwordCiphertext" not in serialized
    assert created.headers["x-workspace-id"] == workspace_id

    row = db_session.scalar(select(LoadNode).where(LoadNode.id == body["id"]))
    assert row is not None
    credential = db_session.get(LoadNodeCredential, row.id)
    assert credential is not None
    assert credential.password_ciphertext is not None
    assert "submitted-secret" not in credential.password_ciphertext

    listed = await client.get("/api/v1/load-nodes", params={"status": "uninitialized"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == body["id"]

    detail = await client.get(f"/api/v1/load-nodes/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["credentialFingerprint"] is None
    assert detail.json()["sshHostKey"]["publicKey"] == TRUSTED_HOST_KEY["publicKey"]


@pytest.mark.anyio
async def test_load_node_create_requires_confirmed_host_key_and_masks_scan_failures(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf, workspace_id, _user_id = await register(client, "host-key-required@example.com")

    missing = password_payload()
    missing.pop("sshHostKey")
    missing_response = await client.post(
        "/api/v1/load-nodes",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=missing,
    )
    assert missing_response.status_code == 422
    assert missing_response.json()["code"] == "VALIDATION_ERROR"

    def fail_scan(host: str, port: int, timeout_seconds: int) -> ScannedSshHostKey:
        _ = host, port, timeout_seconds
        raise TimeoutError("tcp connect timed out")

    monkeypatch.setattr("app.services.load_nodes.scan_ssh_host_key", fail_scan)
    monkeypatch.setattr("app.routes.load_nodes.scan_ssh_host_key", fail_scan)
    scan_failed = await client.post(
        "/api/v1/load-nodes/ssh-host-key/scan",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={"scope": "workspace", "host": "load-node-01.internal", "sshPort": 22},
    )
    assert scan_failed.status_code == 400
    assert scan_failed.json()["code"] == "LOAD_NODE_SSH_HOST_KEY_SCAN_FAILED"
    assert "timed out" not in str(scan_failed.json())


@pytest.mark.anyio
async def test_load_node_scan_normalizes_host_and_create_rejects_mismatched_key(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf, workspace_id, _user_id = await register(client, "host-key-mismatch@example.com")

    scanned = await client.post(
        "/api/v1/load-nodes/ssh-host-key/scan",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={"scope": "workspace", "host": "  LOAD-node-01.Internal  ", "sshPort": 22},
    )
    assert scanned.status_code == 200
    assert scanned.json()["host"] == "load-node-01.internal"
    assert scanned.json()["knownHostsLine"].startswith("load-node-01.internal ssh-ed25519 ")
    audit = db_session.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "load_node.ssh_host_key_scanned")
    )
    assert audit is not None
    assert audit.details_json["scope"] == "workspace"

    def changed_scan(host: str, port: int, timeout_seconds: int) -> ScannedSshHostKey:
        _ = timeout_seconds
        return scanned_key(
            host=host,
            port=port,
            public_key="AAAAC3NzaC1lZDI1NTE5AAAAIChangedLiveHostKeyForTests",
            fingerprint="SHA256:changedLiveHostKey",
        )

    monkeypatch.setattr("app.services.load_nodes.scan_ssh_host_key", changed_scan)
    mismatch = await client.post(
        "/api/v1/load-nodes",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=password_payload(host="LOAD-node-01.Internal"),
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "LOAD_NODE_SSH_HOST_KEY_MISMATCH"
    assert "changedLiveHostKey" not in str(mismatch.json())

    row = db_session.scalar(select(LoadNode).where(LoadNode.host == "load-node-01.internal"))
    assert row is None


@pytest.mark.anyio
async def test_public_load_node_scan_requires_admin_before_scanning(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin_csrf, admin_workspace_id, _admin_user_id = await register(
        client, "scan-admin-bootstrap@example.com", "Admin"
    )
    calls: list[tuple[str, int, int]] = []

    def record_scan(host: str, port: int, timeout_seconds: int) -> ScannedSshHostKey:
        calls.append((host, port, timeout_seconds))
        return scanned_key(host=host, port=port)

    monkeypatch.setattr("app.services.load_nodes.scan_ssh_host_key", record_scan)
    monkeypatch.setattr("app.routes.load_nodes.scan_ssh_host_key", record_scan)

    public_allowed = await client.post(
        "/api/v1/load-nodes/ssh-host-key/scan",
        headers={"x-csrf-token": admin_csrf, "x-workspace-id": admin_workspace_id},
        json={"scope": "public", "host": "PUBLIC-admin-node.internal", "sshPort": 22},
    )
    assert public_allowed.status_code == 200
    assert public_allowed.json()["host"] == "public-admin-node.internal"
    assert len(calls) == 1
    assert calls[0][0:2] == ("public-admin-node.internal", 22)

    user_csrf, user_workspace_id, _user_id = await register(
        client, "scan-user@example.com", "Plain"
    )
    public_denied = await client.post(
        "/api/v1/load-nodes/ssh-host-key/scan",
        headers={"x-csrf-token": user_csrf, "x-workspace-id": user_workspace_id},
        json={"scope": "public", "host": "  PUBLIC-node.internal  ", "sshPort": 22},
    )
    assert public_denied.status_code == 403
    assert public_denied.json()["code"] == "LOAD_NODE_PUBLIC_ADMIN_REQUIRED"
    assert len(calls) == 1

    workspace_allowed = await client.post(
        "/api/v1/load-nodes/ssh-host-key/scan",
        headers={"x-csrf-token": user_csrf, "x-workspace-id": user_workspace_id},
        json={"scope": "workspace", "host": "  WORKSPACE-node.internal  ", "sshPort": 22},
    )
    assert workspace_allowed.status_code == 200
    assert workspace_allowed.json()["host"] == "workspace-node.internal"
    assert len(calls) == 2
    assert calls[1][0:2] == ("workspace-node.internal", 22)


@pytest.mark.anyio
async def test_public_node_requires_admin_and_private_is_workspace_scoped(
    client: AsyncClient, db_session: Session
) -> None:
    admin_csrf, workspace_id, _admin_user_id = await register(
        client, "admin-node@example.com", "Admin"
    )
    public_created = await client.post(
        "/api/v1/load-nodes",
        headers={"x-csrf-token": admin_csrf},
        json=password_payload(scope="public", host="public-node.internal"),
    )
    assert public_created.status_code == 201
    assert public_created.json()["workspaceId"] is None

    user_csrf, user_workspace_id, user_id = await register(
        client, "plain-node@example.com", "Plain"
    )
    public_denied = await client.post(
        "/api/v1/load-nodes",
        headers={"x-csrf-token": user_csrf},
        json=password_payload(scope="public", host="public-node-2.internal"),
    )
    assert public_denied.status_code == 403
    assert public_denied.json()["code"] == "LOAD_NODE_PUBLIC_ADMIN_REQUIRED"

    private_created = await client.post(
        "/api/v1/load-nodes",
        headers={"x-csrf-token": user_csrf, "x-workspace-id": user_workspace_id},
        json=password_payload(host="private-node.internal"),
    )
    assert private_created.status_code == 201
    private_id = private_created.json()["id"]
    other_workspace_id = seed_other_workspace(db_session, user_id)
    cross = await client.get(
        f"/api/v1/load-nodes/{private_id}", headers={"x-workspace-id": other_workspace_id}
    )
    assert cross.status_code == 404


@pytest.mark.anyio
async def test_patch_credentials_initialize_disable_enable_archive_and_attempt_logs(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, _user_id = await register(client, "flow-node@example.com", "Flow")
    created = await client.post(
        "/api/v1/load-nodes",
        headers={"x-csrf-token": csrf},
        json=password_payload(host="flow-node.internal"),
    )
    node_id = created.json()["id"]

    patched = await client.patch(
        f"/api/v1/load-nodes/{node_id}",
        headers={"x-csrf-token": csrf},
        json={"host": "flow-node-2.internal", "remark": None},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "uninitialized"
    assert patched.json()["remark"] is None
    assert patched.json()["sshHostKey"] is None

    trusted = await client.post(
        f"/api/v1/load-nodes/{node_id}/ssh-host-key/trust",
        headers={"x-csrf-token": csrf},
        json=TRUSTED_HOST_KEY,
    )
    assert trusted.status_code == 200
    assert (
        trusted.json()["sshHostKey"]["fingerprintSha256"] == TRUSTED_HOST_KEY["fingerprintSha256"]
    )

    credential_update = await client.post(
        f"/api/v1/load-nodes/{node_id}/credentials",
        headers={"x-csrf-token": csrf},
        json={"credential": {"authType": "generated_key"}},
    )
    assert credential_update.status_code == 200
    assert credential_update.json()["authType"] == "generated_key"
    assert credential_update.json()["generatedPublicKey"].startswith("ssh-ed25519")

    init = await client.post(
        f"/api/v1/load-nodes/{node_id}/initialize",
        headers={"x-csrf-token": csrf},
        json={"force": False},
    )
    assert init.status_code == 202
    attempt_id = init.json()["attempt"]["id"]
    duplicate = await client.post(
        f"/api/v1/load-nodes/{node_id}/initialize",
        headers={"x-csrf-token": csrf},
        json={"force": True},
    )
    assert duplicate.status_code == 202
    assert duplicate.json()["attempt"]["id"] == attempt_id

    for method, url, kwargs in [
        (client.post, f"/api/v1/load-nodes/{node_id}/disable", {"json": {"reason": "stop"}}),
        (client.post, f"/api/v1/load-nodes/{node_id}/enable", {}),
        (client.delete, f"/api/v1/load-nodes/{node_id}", {}),
    ]:
        response = await method(url, headers={"x-csrf-token": csrf}, **kwargs)
        assert response.status_code == 409
        assert response.json()["code"] == "LOAD_NODE_ACTION_NOT_ALLOWED"

    attempt = db_session.get(LoadNodeInitializationAttempt, attempt_id)
    assert attempt is not None
    attempt.status = "succeeded"
    attempt.sanitized_log_tail = "[info] setup output"
    attempt.finished_at = datetime.now(UTC)
    node = db_session.get(LoadNode, node_id)
    assert node is not None
    node.status = "idle"
    db_session.flush()

    idle_without_force = await client.post(
        f"/api/v1/load-nodes/{node_id}/initialize",
        headers={"x-csrf-token": csrf},
        json={"force": False},
    )
    assert idle_without_force.status_code == 409
    assert idle_without_force.json()["code"] == "LOAD_NODE_ACTION_NOT_ALLOWED"

    attempts = await client.get(f"/api/v1/load-nodes/{node_id}/init-attempts")
    assert attempts.status_code == 200
    assert attempts.json()["items"][0]["id"] == attempt_id
    detail = await client.get(f"/api/v1/load-nodes/{node_id}/init-attempts/{attempt_id}")
    assert detail.status_code == 200
    assert detail.json()["sanitizedLogTail"] == "[info] setup output"

    disabled = await client.post(
        f"/api/v1/load-nodes/{node_id}/disable",
        headers={"x-csrf-token": csrf},
        json={"reason": "Maintenance window"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"
    enabled = await client.post(
        f"/api/v1/load-nodes/{node_id}/enable", headers={"x-csrf-token": csrf}
    )
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "uninitialized"

    archived = await client.delete(f"/api/v1/load-nodes/{node_id}", headers={"x-csrf-token": csrf})
    assert archived.status_code == 204
    listed = await client.get("/api/v1/load-nodes", headers={"x-workspace-id": workspace_id})
    assert listed.status_code == 200
    assert listed.json()["total"] == 0

    for method, url, kwargs in [
        (client.patch, f"/api/v1/load-nodes/{node_id}", {"json": {"host": "archived.internal"}}),
        (
            client.post,
            f"/api/v1/load-nodes/{node_id}/credentials",
            {"json": {"credential": {"authType": "password", "password": "new-secret"}}},
        ),
        (client.post, f"/api/v1/load-nodes/{node_id}/initialize", {"json": {"force": True}}),
        (client.post, f"/api/v1/load-nodes/{node_id}/disable", {"json": {"reason": "stop"}}),
        (client.post, f"/api/v1/load-nodes/{node_id}/enable", {}),
        (client.delete, f"/api/v1/load-nodes/{node_id}", {}),
    ]:
        response = await method(url, headers={"x-csrf-token": csrf}, **kwargs)
        assert response.status_code == 404
        assert response.json()["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.anyio
async def test_busy_node_actions_and_invalid_fields_return_contract_errors(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, _workspace_id, _user_id = await register(client, "busy-node@example.com", "Busy")
    created = await client.post(
        "/api/v1/load-nodes",
        headers={"x-csrf-token": csrf},
        json=password_payload(host="busy-node.internal"),
    )
    node_id = created.json()["id"]
    node = db_session.get(LoadNode, node_id)
    assert node is not None
    node.status = "busy"
    db_session.flush()

    for method, url, kwargs in [
        (client.patch, f"/api/v1/load-nodes/{node_id}", {"json": {"host": "other.internal"}}),
        (
            client.post,
            f"/api/v1/load-nodes/{node_id}/credentials",
            {"json": {"credential": {"authType": "password", "password": "new-secret"}}},
        ),
        (client.post, f"/api/v1/load-nodes/{node_id}/initialize", {"json": {"force": True}}),
        (client.post, f"/api/v1/load-nodes/{node_id}/disable", {"json": {"reason": "stop"}}),
        (client.post, f"/api/v1/load-nodes/{node_id}/enable", {}),
        (client.delete, f"/api/v1/load-nodes/{node_id}", {}),
    ]:
        response = await method(url, headers={"x-csrf-token": csrf}, **kwargs)
        assert response.status_code == 409
        assert response.json()["code"] == "LOAD_NODE_BUSY"

    invalid_host = await client.post(
        "/api/v1/load-nodes",
        headers={"x-csrf-token": csrf},
        json=password_payload(host="http://bad/path"),
    )
    assert invalid_host.status_code == 422
    assert invalid_host.json()["code"] == "LOAD_NODE_HOST_INVALID"

    bad_patch = await client.patch(
        f"/api/v1/load-nodes/{node_id}",
        headers={"x-csrf-token": csrf},
        json={"credential": {"authType": "password", "password": "x"}},
    )
    assert bad_patch.status_code == 422
    assert bad_patch.json()["code"] == "VALIDATION_ERROR"
