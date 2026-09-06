from datetime import UTC, datetime
from io import BytesIO
import hashlib
import hmac

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import DEFAULT_WORKSPACE_ID, User, Workspace, WorkspaceMember
from app.models.load_nodes import LoadNode
from app.models.runs import Run, RunArtifact, RunControlRequest
from app.schemas.load_nodes import LoadNodeCredentialInput
from app.services.load_nodes import create_load_node
from app.services.runs import create_protocol_smoke_run


def node_bound_token(secret: str, node_id: str) -> str:
    sig = hmac.new(secret.encode(), node_id.encode(), hashlib.sha256).hexdigest()
    return f"node:{node_id}:{sig}"


async def register(client: AsyncClient, email: str) -> tuple[str, str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": "Run User", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["csrfToken"], body["defaultWorkspace"]["id"], body["user"]["id"]


def trusted_host_key() -> dict[str, str]:
    return {
        "algorithm": "ssh-ed25519",
        "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        "fingerprintSha256": "SHA256:SurgePilotTrustedHostKey",
    }


def credential() -> LoadNodeCredentialInput:
    return LoadNodeCredentialInput(authType="password", password="secret-password")


def seed_idle_node_and_run(
    db_session: Session, *, user_id: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[LoadNode, Run]:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    now = datetime.now(UTC)
    user = db_session.get(User, user_id)
    assert user is not None
    node = create_load_node(
        db_session,
        actor=user,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host=f"api-run-node-{user_id.lower()}.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=credential(),
        ssh_host_key=trusted_host_key(),
        maintainer=None,
        remark=None,
    )
    node.status = "idle"
    node.runtime_version = "runtime-test-v1"
    node.created_at = now
    db_session.flush()
    assert node.status == "idle"
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    db_session.flush()
    return node, run


@pytest.mark.anyio
async def test_stop_requires_csrf_is_workspace_scoped_and_idempotent(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf, workspace_id, user_id = await register(client, "stop-run@example.com")
    _node, run = seed_idle_node_and_run(db_session, user_id=user_id, monkeypatch=monkeypatch)

    missing_csrf = await client.post(f"/api/v1/runs/{run.id}/stop")
    assert missing_csrf.status_code == 403

    stopped = await client.post(
        f"/api/v1/runs/{run.id}/stop",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert stopped.status_code == 202
    assert stopped.json()["state"] == "stopping"
    assert stopped.json()["duplicate"] is False
    assert (
        db_session.scalar(
            select(RunControlRequest).where(
                RunControlRequest.run_id == run.id, RunControlRequest.action == "stop"
            )
        )
        is not None
    )

    duplicate = await client.post(
        f"/api/v1/runs/{run.id}/stop",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True

    other = Workspace(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7D",
        name="Other",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(other)
    db_session.add(
        WorkspaceMember(workspace_id=other.id, user_id=user_id, joined_at=datetime.now(UTC))
    )
    db_session.flush()
    cross = await client.post(
        f"/api/v1/runs/{run.id}/stop",
        headers={"x-csrf-token": csrf, "x-workspace-id": other.id},
    )
    assert cross.status_code == 404

    run.state = "aborted"
    db_session.flush()
    terminal = await client.post(
        f"/api/v1/runs/{run.id}/stop",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert terminal.status_code == 409
    assert terminal.json()["code"] == "RUN_TERMINAL_STATE"


@pytest.mark.anyio
async def test_runner_callback_requires_token_and_does_not_use_browser_csrf(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf, _workspace_id, user_id = await register(client, "callback-run@example.com")
    _node, run = seed_idle_node_and_run(db_session, user_id=user_id, monkeypatch=monkeypatch)
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    payload = {
        "schemaVersion": "1",
        "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        "runId": run.id,
        "nodeId": run.selected_node_id,
        "runtimeVersion": "runtime-test-v1",
        "eventType": "running",
        "seq": 1,
        "eventTime": "2030-06-01T10:00:00.000Z",
        "details": {},
    }

    missing = await client.post("/api/internal/v1/runner/callbacks", json=payload)
    assert missing.status_code == 401
    assert missing.json()["code"] == "RUNNER_UNAUTHORIZED"

    callback = await client.post(
        "/api/internal/v1/runner/callbacks",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        json=payload,
    )
    assert callback.status_code == 200
    assert callback.json()["stateChanged"] is True
    assert callback.json()["currentState"] == "running"

    duplicate = await client.post(
        "/api/internal/v1/runner/callbacks",
        headers={
            "x-runner-token": node_bound_token("runner-secret", run.selected_node_id),
            "x-csrf-token": csrf,
        },
        json=payload,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True


@pytest.mark.anyio
async def test_runner_callback_runtime_validation_uses_shared_schema(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _csrf, _workspace_id, user_id = await register(client, "callback-schema-run@example.com")
    _node, run = seed_idle_node_and_run(db_session, user_id=user_id, monkeypatch=monkeypatch)
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    artifact_missing_required_detail = {
        "schemaVersion": "1",
        "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
        "runId": run.id,
        "nodeId": run.selected_node_id,
        "runtimeVersion": "runtime-test-v1",
        "eventType": "artifact",
        "seq": 2,
        "eventTime": "2030-06-01T10:00:00.000Z",
        "details": {
            "artifactType": "run_log",
            "relativePath": "logs/runner.log",
            "sizeBytes": 10,
            "sha256": "a" * 64,
        },
    }

    artifact_response = await client.post(
        "/api/internal/v1/runner/callbacks",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        json=artifact_missing_required_detail,
    )

    assert artifact_response.status_code == 422
    assert artifact_response.json()["code"] == "RUNNER_CALLBACK_INVALID"

    unknown_field = {
        "schemaVersion": "1",
        "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P7E",
        "runId": run.id,
        "nodeId": run.selected_node_id,
        "runtimeVersion": "runtime-test-v1",
        "eventType": "heartbeat",
        "seq": 3,
        "eventTime": "2030-06-01T10:00:00.000Z",
        "details": {},
        "unexpected": "not allowed",
    }

    unknown_response = await client.post(
        "/api/internal/v1/runner/callbacks",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        json=unknown_field,
    )

    assert unknown_response.status_code == 422
    assert unknown_response.json()["code"] == "RUNNER_CALLBACK_INVALID"

    list_payload_response = await client.post(
        "/api/internal/v1/runner/callbacks",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        json=["not", "an", "object"],
    )

    assert list_payload_response.status_code == 422
    assert list_payload_response.json()["code"] == "RUNNER_CALLBACK_INVALID"

    non_z_event_time = {
        "schemaVersion": "1",
        "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
        "runId": run.id,
        "nodeId": run.selected_node_id,
        "runtimeVersion": "runtime-test-v1",
        "eventType": "heartbeat",
        "seq": 4,
        "eventTime": "2030-06-01T10:00:00+00:00",
        "details": {},
    }
    non_z_response = await client.post(
        "/api/internal/v1/runner/callbacks",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        json=non_z_event_time,
    )
    assert non_z_response.status_code == 422
    assert non_z_response.json()["code"] == "RUNNER_CALLBACK_INVALID"

    invalid_reason = {
        "schemaVersion": "1",
        "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P7G",
        "runId": run.id,
        "nodeId": run.selected_node_id,
        "runtimeVersion": "runtime-test-v1",
        "eventType": "failed",
        "seq": 5,
        "eventTime": "2030-06-01T10:00:00.000Z",
        "details": {"processGroupExited": True, "reason": "Runner Exit"},
    }
    invalid_reason_response = await client.post(
        "/api/internal/v1/runner/callbacks",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        json=invalid_reason,
    )
    assert invalid_reason_response.status_code == 422
    assert invalid_reason_response.json()["code"] == "RUNNER_CALLBACK_INVALID"


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):
        data = stream.read()
        assert object_key.startswith("run-artifacts/")
        self.objects[object_key] = data
        return type(
            "PutResult",
            (),
            {"size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
        )()

    def copy_object(self, *, bucket, source_key, destination_key):
        self.objects[destination_key] = self.objects[source_key]

    def delete_object_best_effort(self, *, bucket, object_key):
        self.objects.pop(object_key, None)


def artifact_form(
    *,
    event_id: str,
    run: Run,
    artifact_type: str = "run_log",
    relative_path: str = "logs/runner.log",
    sha256: str,
    size_bytes: int,
    node_id: str | None = None,
) -> dict[str, str]:
    return {
        "schemaVersion": "1",
        "eventId": event_id,
        "runId": run.id,
        "nodeId": node_id or run.selected_node_id,
        "runtimeVersion": "runtime-test-v1",
        "artifactType": artifact_type,
        "relativePath": relative_path,
        "sha256": sha256,
        "sizeBytes": str(size_bytes),
    }


@pytest.mark.anyio
async def test_runner_artifact_upload_validates_and_stores_metadata_without_object_key(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _csrf, _workspace_id, user_id = await register(client, "artifact-run@example.com")
    _node, run = seed_idle_node_and_run(db_session, user_id=user_id, monkeypatch=monkeypatch)
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: FakeStorage())
    data = b"runner log"
    digest = hashlib.sha256(data).hexdigest()

    upload = await client.post(
        "/api/internal/v1/runner/artifacts",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        data={
            "schemaVersion": "1",
            "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P7E",
            "runId": run.id,
            "nodeId": run.selected_node_id,
            "runtimeVersion": "runtime-test-v1",
            "artifactType": "run_log",
            "relativePath": "logs/runner.log",
            "sha256": digest,
            "sizeBytes": str(len(data)),
        },
        files={"file": ("runner.log", BytesIO(data), "text/plain")},
    )
    assert upload.status_code == 200
    artifact_id = upload.json()["artifactId"]
    assert "storageKey" not in upload.text
    artifact = db_session.get(RunArtifact, artifact_id)
    assert artifact is not None
    assert artifact.storage_key.startswith(
        f"run-artifacts/{run.workspace_id}/{run.id}/nodes/{run.selected_node_id}/"
    )
    assert artifact.storage_key.endswith("/logs/runner.log")
    assert artifact.id not in artifact.storage_key

    unsafe = await client.post(
        "/api/internal/v1/runner/artifacts",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        data={
            "schemaVersion": "1",
            "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
            "runId": run.id,
            "nodeId": run.selected_node_id,
            "runtimeVersion": "runtime-test-v1",
            "artifactType": "run_log",
            "relativePath": "../secret.log",
            "sha256": digest,
            "sizeBytes": str(len(data)),
        },
        files={"file": ("runner.log", BytesIO(data), "text/plain")},
    )
    assert unsafe.status_code == 400
    assert unsafe.json()["code"] == "INVALID_ARTIFACT_PATH"


@pytest.mark.anyio
async def test_runner_callback_body_limit_and_duplicate_conflict(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _csrf, _workspace_id, user_id = await register(client, "callback-conflict-run@example.com")
    _node, run = seed_idle_node_and_run(db_session, user_id=user_id, monkeypatch=monkeypatch)
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    payload = {
        "schemaVersion": "1",
        "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P7G",
        "runId": run.id,
        "nodeId": run.selected_node_id,
        "runtimeVersion": "runtime-test-v1",
        "eventType": "running",
        "seq": 1,
        "eventTime": "2030-06-01T10:00:00.000Z",
        "details": {},
    }

    oversized = await client.post(
        "/api/internal/v1/runner/callbacks",
        headers={
            "x-runner-token": node_bound_token("runner-secret", run.selected_node_id),
            "content-type": "application/json",
        },
        content=b'{"schemaVersion":"1","message":"' + (b"x" * 9000) + b'"}',
    )
    assert oversized.status_code == 422
    assert oversized.json()["code"] == "RUNNER_CALLBACK_INVALID"

    first = await client.post(
        "/api/internal/v1/runner/callbacks",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        json=payload,
    )
    assert first.status_code == 200

    changed_payload = {**payload, "message": "Same event id with different payload."}
    conflict = await client.post(
        "/api/internal/v1/runner/callbacks",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        json=changed_payload,
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "RUNNER_CALLBACK_CONFLICT"


@pytest.mark.anyio
async def test_runner_artifact_rejects_missing_token_after_node_binding_fields(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    data = b"runner log"
    response = await client.post(
        "/api/internal/v1/runner/artifacts",
        data={
            "schemaVersion": "1",
            "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P7H",
            "runId": "01HZX3Y9M0E9W7Z6M5QK9S8P7J",
            "nodeId": "01HZX3Y9M0E9W7Z6M5QK9S8P7K",
            "runtimeVersion": "runtime-test-v1",
            "artifactType": "run_log",
            "relativePath": "logs/runner.log",
            "sha256": hashlib.sha256(data).hexdigest(),
            "sizeBytes": str(len(data)),
        },
        files={"file": ("runner.log", BytesIO(data), "text/plain")},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "RUNNER_UNAUTHORIZED"


@pytest.mark.anyio
async def test_runner_artifact_upload_rejects_auth_binding_and_validation_errors(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _csrf, _workspace_id, user_id = await register(client, "artifact-errors-run@example.com")
    node, run = seed_idle_node_and_run(db_session, user_id=user_id, monkeypatch=monkeypatch)
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: FakeStorage())
    data = b"runner log"
    digest = hashlib.sha256(data).hexdigest()

    missing_token = await client.post(
        "/api/internal/v1/runner/artifacts",
        data=artifact_form(
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7H",
            run=run,
            sha256=digest,
            size_bytes=len(data),
        ),
        files={"file": ("runner.log", BytesIO(data), "text/plain")},
    )
    assert missing_token.status_code == 401
    assert missing_token.json()["code"] == "RUNNER_UNAUTHORIZED"

    missing_schema = await client.post(
        "/api/internal/v1/runner/artifacts",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        data={
            "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P8H",
            "runId": run.id,
            "nodeId": run.selected_node_id,
            "runtimeVersion": "runtime-test-v1",
            "artifactType": "run_log",
            "relativePath": "logs/runner.log",
            "sha256": digest,
            "sizeBytes": str(len(data)),
        },
        files={"file": ("runner.log", BytesIO(data), "text/plain")},
    )
    assert missing_schema.status_code == 400
    assert missing_schema.json()["code"] == "INVALID_REQUEST"

    missing_file = await client.post(
        "/api/internal/v1/runner/artifacts",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        data=artifact_form(
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P8J",
            run=run,
            sha256=digest,
            size_bytes=len(data),
        ),
    )
    assert missing_file.status_code == 400
    assert missing_file.json()["code"] == "INVALID_REQUEST"

    invalid_size = await client.post(
        "/api/internal/v1/runner/artifacts",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        data=artifact_form(
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P8K",
            run=run,
            sha256=digest,
            size_bytes=len(data),
        )
        | {"sizeBytes": "not-a-number"},
        files={"file": ("runner.log", BytesIO(data), "text/plain")},
    )
    assert invalid_size.status_code == 400
    assert invalid_size.json()["code"] == "INVALID_REQUEST"

    class FailingIfReadStorage(FakeStorage):
        def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):  # noqa: ANN001
            raise AssertionError(
                "storage stream should not be opened for oversized declared artifact"
            )

    monkeypatch.setenv("SURGEPILOT_RUN_ARTIFACT_MAX_BYTES", "8")
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: FailingIfReadStorage())
    oversized_declared = await client.post(
        "/api/internal/v1/runner/artifacts",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        data=artifact_form(
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Q",
            run=run,
            sha256=digest,
            size_bytes=9,
        ),
        files={"file": ("runner.log", BytesIO(data), "text/plain")},
    )
    assert oversized_declared.status_code == 413
    assert oversized_declared.json()["code"] == "PAYLOAD_TOO_LARGE"
    monkeypatch.setenv("SURGEPILOT_RUN_ARTIFACT_MAX_BYTES", "1048576")
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: FakeStorage())

    mismatch = await client.post(
        "/api/internal/v1/runner/artifacts",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        data=artifact_form(
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7J",
            run=run,
            node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7K",
            sha256=digest,
            size_bytes=len(data),
        ),
        files={"file": ("runner.log", BytesIO(data), "text/plain")},
    )
    assert mismatch.status_code == 403
    assert mismatch.json()["code"] == "RUNNER_FORBIDDEN"

    invalid_type = await client.post(
        "/api/internal/v1/runner/artifacts",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        data=artifact_form(
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7M",
            run=run,
            artifact_type="debug_dump",
            sha256=digest,
            size_bytes=len(data),
        ),
        files={"file": ("runner.log", BytesIO(data), "text/plain")},
    )
    assert invalid_type.status_code == 400
    assert invalid_type.json()["code"] == "INVALID_ARTIFACT_TYPE"

    size_mismatch = await client.post(
        "/api/internal/v1/runner/artifacts",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        data=artifact_form(
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
            run=run,
            sha256=digest,
            size_bytes=len(data) + 1,
        ),
        files={"file": ("runner.log", BytesIO(data), "text/plain")},
    )
    assert size_mismatch.status_code == 400
    assert size_mismatch.json()["code"] == "ARTIFACT_SIZE_MISMATCH"

    hash_mismatch = await client.post(
        "/api/internal/v1/runner/artifacts",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        data=artifact_form(
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7P",
            run=run,
            sha256="b" * 64,
            size_bytes=len(data),
        ),
        files={"file": ("runner.log", BytesIO(data), "text/plain")},
    )
    assert hash_mismatch.status_code == 400
    assert hash_mismatch.json()["code"] == "ARTIFACT_HASH_MISMATCH"
    assert node.current_run_id == run.id


@pytest.mark.anyio
async def test_runner_artifact_rejects_oversized_content_length_before_multipart_parsing(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from starlette.requests import Request as StarletteRequest

    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    monkeypatch.setenv("SURGEPILOT_RUN_ARTIFACT_MAX_BYTES", "8")

    async def fail_if_form_is_called(self):  # noqa: ANN001
        raise AssertionError("multipart body was parsed before content-length validation")

    monkeypatch.setattr(StarletteRequest, "form", fail_if_form_is_called)
    response = await client.post(
        "/api/internal/v1/runner/artifacts",
        headers={
            "content-type": "multipart/form-data; boundary=x",
            "content-length": "8201",
        },
        content=b"",
    )

    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.anyio
async def test_runner_artifact_upload_duplicate_event_and_path_conflict(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _csrf, _workspace_id, user_id = await register(client, "artifact-duplicate-run@example.com")
    _node, run = seed_idle_node_and_run(db_session, user_id=user_id, monkeypatch=monkeypatch)
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: FakeStorage())
    data = b"runner log"
    digest = hashlib.sha256(data).hexdigest()

    first = await client.post(
        "/api/internal/v1/runner/artifacts",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        data=artifact_form(
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Q",
            run=run,
            sha256=digest,
            size_bytes=len(data),
        ),
        files={"file": ("runner.log", BytesIO(data), "text/plain")},
    )
    assert first.status_code == 200
    artifact_id = first.json()["artifactId"]

    duplicate = await client.post(
        "/api/internal/v1/runner/artifacts",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        data=artifact_form(
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Q",
            run=run,
            sha256=digest,
            size_bytes=len(data),
        ),
        files={"file": ("runner.log", BytesIO(data), "text/plain")},
    )
    assert duplicate.status_code == 200
    assert duplicate.json() == {"artifactId": artifact_id, "duplicate": True}
    assert "storageKey" not in duplicate.text
    assert "artifacts/" not in duplicate.text

    different = b"different runner log"
    conflict = await client.post(
        "/api/internal/v1/runner/artifacts",
        headers={"x-runner-token": node_bound_token("runner-secret", run.selected_node_id)},
        data=artifact_form(
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
            run=run,
            sha256=hashlib.sha256(different).hexdigest(),
            size_bytes=len(different),
        ),
        files={"file": ("runner.log", BytesIO(different), "text/plain")},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "ARTIFACT_PATH_CONFLICT"


def test_runner_callback_schema_candidates_support_container_layout() -> None:
    from pathlib import Path

    from app.routes.runner_internal import runner_callback_schema_candidates

    candidates = runner_callback_schema_candidates(Path("/app/app/routes/runner_internal.py"))

    assert Path("/opt/surgepilot/contracts/runner/runner-callback.schema.json") in candidates
    assert all("runner-callback.schema.json" in str(candidate) for candidate in candidates)
