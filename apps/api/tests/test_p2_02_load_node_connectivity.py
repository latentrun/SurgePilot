from dataclasses import replace

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.time import utc_now
from app.models.auth import SystemSetting, Workspace
from app.services.load_node_connectivity import (
    LoadNodeApiBaseUrlInvalid,
    validate_load_node_api_base_url,
)
from app.services.load_nodes import CredentialPlaintext
from app.services.run_control_executor import RemoteExecutorOptions, RemoteRunControlExecutor
from app.services.runs import RunControlCommand
from app.services.ssh_remote import RemoteCommandResult, SshTarget


async def register_admin(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "admin@example.com", "displayName": "Admin", "password": "password123"},
    )
    assert response.status_code == 201


async def csrf(client: AsyncClient) -> str:
    response = await client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrfToken"]


async def create_user_client(client: AsyncClient, db_session: Session) -> AsyncClient:
    token = await csrf(client)
    workspace = db_session.query(Workspace).filter(Workspace.status == "active").one()
    created = await client.post(
        "/api/v1/admin/users",
        headers={"x-csrf-token": token},
        json={
            "email": "member@example.com",
            "displayName": "Member",
            "role": "user",
            "status": "active",
            "password": "password123",
            "workspaceIds": [workspace.id],
        },
    )
    assert created.status_code == 201
    user_client = AsyncClient(transport=client._transport, base_url="http://testserver")
    login = await user_client.post(
        "/api/v1/auth/login",
        json={"email": "member@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    return user_client


class MemoryBundle:
    def files(self):
        from app.services.runner_bundle import RunnerBundleFile

        return [RunnerBundleFile("runner.py", b"print('runner')\n", 0o755)]


class RecordingAdapter:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str | bytes, int]] = []
        self.commands: list[str] = []

    def upload_text(self, target: SshTarget, *, remote_path: str, content: str, mode: int) -> None:
        _ = target
        self.uploads.append((remote_path, content, mode))

    def upload_bytes(
        self, target: SshTarget, *, remote_path: str, content: bytes, mode: int
    ) -> None:
        _ = target
        self.uploads.append((remote_path, content, mode))

    def upload_stream(self, target: SshTarget, *, remote_path: str, source, mode: int) -> None:
        _ = target
        self.uploads.append((remote_path, source.read(), mode))

    def run_command(
        self,
        target: SshTarget,
        *,
        command: str,
        timeout_seconds: int,
        output_limit_bytes: int = 4096,
    ) -> RemoteCommandResult:
        _ = target, timeout_seconds, output_limit_bytes
        self.commands.append(command)
        return RemoteCommandResult(0, "runtime-test-v1", "")


def command(action: str = "start", *, source_type: str = "protocol_smoke") -> RunControlCommand:
    return RunControlCommand(
        request_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        action=action,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        reason="user requested stop" if action != "start" else None,
        source_type=source_type,
        host="ssh-load-node",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        trusted_host_key_algorithm="ssh-ed25519",
        trusted_host_key_public_key="AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        trusted_host_key_fingerprint_sha256="SHA256:SurgePilotTrustedHostKey",
        argv=("python3", "/opt/surgepilot/runner/runner.py", action),
        expected_runtime_version="runtime-test-v1",
    )


def executor(db_session: Session, adapter: RecordingAdapter) -> RemoteRunControlExecutor:
    return RemoteRunControlExecutor(
        session_factory=sessionmaker(bind=db_session.get_bind(), expire_on_commit=False),
        credential_resolver=lambda _node_id: CredentialPlaintext(
            auth_type="password", password="pw"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=replace(
            get_settings(),
            app_base_url="http://api:8000",
            runner_internal_token="runner-secret-token",
            load_node_ssh_connect_timeout_seconds=3,
            runner_force_kill_ssh_timeout_seconds=7,
        ),
        options=RemoteExecutorOptions(command_timeout_seconds=7, output_limit_bytes=256),
    )


def executor_without_session(adapter: RecordingAdapter) -> RemoteRunControlExecutor:
    return RemoteRunControlExecutor(
        credential_resolver=lambda _node_id: CredentialPlaintext(
            auth_type="password", password="pw"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=replace(
            get_settings(),
            app_base_url="http://api:8000",
            runner_internal_token="runner-secret-token",
            load_node_ssh_connect_timeout_seconds=3,
            runner_force_kill_ssh_timeout_seconds=7,
        ),
        options=RemoteExecutorOptions(command_timeout_seconds=7, output_limit_bytes=256),
    )


@pytest.mark.anyio
async def test_system_settings_store_and_validate_load_node_api_base_url(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "https://bootstrap.example.test:8443")
    await register_admin(client)
    token = await csrf(client)

    current = await client.get("/api/v1/admin/system-settings")
    assert current.status_code == 200
    assert current.json()["settings"]["loadNodeApiBaseUrl"] is None

    saved = await client.patch(
        "/api/v1/admin/system-settings",
        headers={"x-csrf-token": token},
        json={"loadNodeApiBaseUrl": "http://10.0.0.5:8080/"},
    )
    assert saved.status_code == 200
    assert saved.json()["settings"]["loadNodeApiBaseUrl"] == "http://10.0.0.5:8080"

    invalid_cases = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://api:8000",
        "http://host.docker.internal:8000",
        "https://surgepilot.example.test/api",
        "https://user:pass@surgepilot.example.test",
        "ftp://surgepilot.example.test",
        "http://[::ffff:127.0.0.1]:8080",
        "http://*.example.com:8080",
        "https://api.*.example.test",
        "https://%2A.example.com",
        "https://api.%2A.example.test",
        "https://%41.example.com",
        "http://127.1:8080",
        "http://0177.0.0.1:8080",
        "http://0x7f.0.0.1:8080",
        "http://127。0.0.1:8080",
        "http://127．0.0.1:8080",
        "http://127｡0.0.1:8080",
        "https://foo_bar.example.com",
        "https://-api.example.com",
    ]
    for value in invalid_cases:
        response = await client.patch(
            "/api/v1/admin/system-settings",
            headers={"x-csrf-token": token},
            json={"loadNodeApiBaseUrl": value},
        )
        assert response.status_code == 422, value
        assert response.json()["code"] == "VALIDATION_ERROR"

    cleared = await client.patch(
        "/api/v1/admin/system-settings",
        headers={"x-csrf-token": token},
        json={"loadNodeApiBaseUrl": ""},
    )
    assert cleared.status_code == 200
    assert cleared.json()["settings"]["loadNodeApiBaseUrl"] is None


@pytest.mark.parametrize(
    "value",
    [
        "http://*.example.com:8080",
        "https://api.*.example.test",
        "https://api*wildcard.example.test",
        "https://%2A.example.com",
        "https://api.%2A.example.test",
    ],
)
def test_validate_load_node_api_base_url_rejects_wildcard_hosts(value: str) -> None:
    with pytest.raises(LoadNodeApiBaseUrlInvalid, match="wildcard"):
        validate_load_node_api_base_url(value)


def test_validate_load_node_api_base_url_rejects_percent_encoded_hosts() -> None:
    with pytest.raises(LoadNodeApiBaseUrlInvalid, match="fully qualified domain name"):
        validate_load_node_api_base_url("https://%41.example.com")


@pytest.mark.parametrize(
    "value",
    [
        "http://127.1:8080",
        "http://0177.0.0.1:8080",
        "http://0x7f.0.0.1:8080",
        "http://127。0.0.1:8080",
        "http://127．0.0.1:8080",
        "http://127｡0.0.1:8080",
    ],
)
def test_validate_load_node_api_base_url_rejects_encoded_loopback_hosts(value: str) -> None:
    with pytest.raises(LoadNodeApiBaseUrlInvalid):
        validate_load_node_api_base_url(value)


@pytest.mark.parametrize(
    "value",
    ["https://foo_bar.example.com", "https://-api.example.com", "https://api-.example.com"],
)
def test_validate_load_node_api_base_url_rejects_invalid_dns_labels(value: str) -> None:
    with pytest.raises(LoadNodeApiBaseUrlInvalid, match="fully qualified domain name"):
        validate_load_node_api_base_url(value)


def test_validate_load_node_api_base_url_keeps_valid_fqdn_normalization() -> None:
    assert (
        validate_load_node_api_base_url("HTTPS://SurgePilot.Example.Test.:8443/")
        == "https://surgepilot.example.test:8443"
    )


def test_validate_load_node_api_base_url_normalizes_idna_fqdn() -> None:
    assert (
        validate_load_node_api_base_url("HTTPS://BÜCHER.Example./")
        == "https://xn--bcher-kva.example"
    )


def test_validate_load_node_api_base_url_rejects_invalid_idna_label() -> None:
    invalid_origin = f"https://{'a' * 64}.example.com"

    with pytest.raises(LoadNodeApiBaseUrlInvalid, match="fully qualified domain name"):
        validate_load_node_api_base_url(invalid_origin)


def test_validate_load_node_api_base_url_keeps_valid_ipv6_normalization() -> None:
    assert (
        validate_load_node_api_base_url("HTTP://[2001:db8::1]:8080/") == "http://[2001:db8::1]:8080"
    )


@pytest.mark.anyio
async def test_system_settings_unrelated_save_does_not_persist_env_fallback(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "https://bootstrap.example.test:8443")
    await register_admin(client)
    token = await csrf(client)

    response = await client.patch(
        "/api/v1/admin/system-settings",
        headers={"x-csrf-token": token},
        json={"allowSignup": False},
    )

    assert response.status_code == 200
    assert response.json()["settings"]["loadNodeApiBaseUrl"] is None
    assert db_session.get(SystemSetting, "loadNodeApiBaseUrl") is None

    summary = await client.get("/api/v1/load-nodes/connectivity-summary")
    assert summary.status_code == 200
    assert summary.json()["source"] == "env_fallback"
    assert summary.json()["effectiveUrl"] == "https://bootstrap.example.test:8443"


@pytest.mark.anyio
async def test_connectivity_summary_sources_and_non_admin_read(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SURGEPILOT_NODE_API_BASE_URL", raising=False)
    await register_admin(client)

    missing = await client.get("/api/v1/load-nodes/connectivity-summary")
    assert missing.status_code == 200
    assert missing.json() == {
        "effectiveUrl": None,
        "source": "missing",
        "readiness": "missing",
        "message": "Load Node API Base URL is not configured.",
    }

    user_client = await create_user_client(client, db_session)
    try:
        non_admin = await user_client.get("/api/v1/load-nodes/connectivity-summary")
        assert non_admin.status_code == 200
        assert non_admin.json()["source"] == "missing"
    finally:
        await user_client.aclose()

    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "http://192.168.1.50:8080")
    env_summary = await client.get("/api/v1/load-nodes/connectivity-summary")
    assert env_summary.status_code == 200
    assert env_summary.json()["source"] == "env_fallback"
    assert env_summary.json()["readiness"] == "ready"
    assert env_summary.json()["effectiveUrl"] == "http://192.168.1.50:8080"


@pytest.mark.anyio
async def test_connectivity_summary_keeps_configured_source_for_invalid_db_value(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "https://bootstrap.example.test")
    await register_admin(client)
    db_session.add(
        SystemSetting(key="loadNodeApiBaseUrl", value_json="http://api:8000", updated_at=utc_now())
    )
    db_session.commit()

    response = await client.get("/api/v1/load-nodes/connectivity-summary")

    assert response.status_code == 200
    assert response.json()["source"] == "configured"
    assert response.json()["readiness"] == "invalid"
    assert response.json()["effectiveUrl"] == "http://api:8000"


@pytest.mark.anyio
async def test_connectivity_summary_reports_invalid_env_without_fallback(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "http://localhost:8000")
    await register_admin(client)

    response = await client.get("/api/v1/load-nodes/connectivity-summary")

    assert response.status_code == 200
    assert response.json()["source"] == "env_fallback"
    assert response.json()["readiness"] == "invalid"
    assert response.json()["effectiveUrl"] == "http://localhost:8000"


def test_remote_run_start_writes_db_origin_over_env(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "https://env.example.test")
    db_session.add(
        SystemSetting(
            key="loadNodeApiBaseUrl", value_json="http://10.0.0.5:8080", updated_at=utc_now()
        )
    )
    db_session.commit()
    adapter = RecordingAdapter()

    result = executor(db_session, adapter).execute(command("start"))

    assert result.ok is True
    env_upload = next(upload for upload in adapter.uploads if upload[0].endswith(".surgepilot.env"))
    assert "SURGEPILOT_API_BASE_URL=http://10.0.0.5:8080\n" in env_upload[1]
    assert "https://env.example.test" not in env_upload[1]


def test_remote_run_start_fails_closed_when_origin_missing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SURGEPILOT_NODE_API_BASE_URL", raising=False)
    adapter = RecordingAdapter()

    result = executor(db_session, adapter).execute(command("start"))

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_INVALID_API_BASE_URL"
    assert adapter.uploads == []
    assert adapter.commands == []


@pytest.mark.parametrize(
    "invalid_origin",
    [
        "http://api:8000",
        "https://%2A.example.com",
        "http://127.1:8080",
        "http://127。0.0.1:8080",
    ],
)
def test_remote_run_start_fails_closed_when_env_origin_invalid(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, invalid_origin: str
) -> None:
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", invalid_origin)
    adapter = RecordingAdapter()

    result = executor(db_session, adapter).execute(command("start"))

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_INVALID_API_BASE_URL"
    assert adapter.uploads == []
    assert adapter.commands == []


@pytest.mark.parametrize("source_type", ["debug_scenario", "test_plan"])
@pytest.mark.parametrize(
    ("env_value", "delete_env"),
    [("http://api:8000", False), ("", True)],
)
def test_remote_run_start_url_validation_precedes_bundle_build(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    source_type: str,
    env_value: str,
    delete_env: bool,
) -> None:
    if delete_env:
        monkeypatch.delenv("SURGEPILOT_NODE_API_BASE_URL", raising=False)
    else:
        monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", env_value)
    adapter = RecordingAdapter()
    builder_path = (
        "app.services.run_control_executor.build_test_plan_execution_bundle"
        if source_type == "test_plan"
        else "app.services.run_control_executor.build_debug_scenario_execution_bundle"
    )

    def fail_if_bundle_build_runs(*args, **kwargs):
        raise AssertionError("bundle builder must not run before URL validation")

    monkeypatch.setattr(builder_path, fail_if_bundle_build_runs)

    result = executor(db_session, adapter).execute(command("start", source_type=source_type))

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_INVALID_API_BASE_URL"
    assert result.quarantine_node is False
    assert adapter.uploads == []
    assert adapter.commands == []


@pytest.mark.parametrize("source_type", ["debug_scenario", "test_plan"])
def test_remote_run_start_url_resolution_unexpected_failure_is_contained(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, source_type: str
) -> None:
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "https://bootstrap.example.test")
    adapter = RecordingAdapter()
    builder_path = (
        "app.services.run_control_executor.build_test_plan_execution_bundle"
        if source_type == "test_plan"
        else "app.services.run_control_executor.build_debug_scenario_execution_bundle"
    )

    def fail_effective_url(_session: Session) -> str:
        raise RuntimeError("database connection dropped")

    def fail_if_bundle_build_runs(*args, **kwargs):
        raise AssertionError("bundle builder must not run after URL resolution failure")

    monkeypatch.setattr(
        "app.services.run_control_executor.effective_load_node_api_base_url",
        fail_effective_url,
    )
    monkeypatch.setattr(builder_path, fail_if_bundle_build_runs)

    result = executor(db_session, adapter).execute(command("start", source_type=source_type))

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_EXECUTION_FAILED"
    assert result.quarantine_node is False
    assert adapter.uploads == []
    assert adapter.commands == []


@pytest.mark.parametrize("action", ["stop", "force_kill"])
@pytest.mark.parametrize("use_session_factory", [True, False])
@pytest.mark.parametrize(
    ("env_value", "delete_env"),
    [("http://api:8000", False), ("", True)],
)
def test_remote_non_start_actions_do_not_require_or_emit_node_api_base_url(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    use_session_factory: bool,
    env_value: str,
    delete_env: bool,
) -> None:
    if delete_env:
        monkeypatch.delenv("SURGEPILOT_NODE_API_BASE_URL", raising=False)
    else:
        monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", env_value)
    adapter = RecordingAdapter()
    active_executor = (
        executor(db_session, adapter) if use_session_factory else executor_without_session(adapter)
    )

    result = active_executor.execute(command(action))

    assert result.ok is True
    env_upload = next(upload for upload in adapter.uploads if upload[0].endswith(".surgepilot.env"))
    assert "SURGEPILOT_API_BASE_URL=" not in env_upload[1]
    assert "http://api:8000" not in env_upload[1]
    assert adapter.commands
