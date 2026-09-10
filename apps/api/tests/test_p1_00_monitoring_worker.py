from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.auth import DEFAULT_WORKSPACE_ID
from app.models.runs import Run, RunMonitoringConfig
from app.services.load_nodes import CredentialPlaintext
from app.services.run_control_executor import (
    RemoteExecutorOptions,
    RemoteRunControlExecutor,
    _monitoring_token_from_worker_env,
)
from app.services.runner_bundle import RunnerBundleFile
from app.services.runs import RunControlCommand
from app.services.ssh_remote import RemoteCommandResult, SshTarget

RUN_ID = "01HZX3Y9M0E9W7Z6M5QK9S8P7B"
NODE_ID = "01HZX3Y9M0E9W7Z6M5QK9S8P7C"
REQUEST_ID = "01HZX3Y9M0E9W7Z6M5QK9S8P7A"
NODE_WRITE_URL = "https://node-write.example.test"


class MemoryBundle:
    def files(self):
        return [RunnerBundleFile("runner.py", b"print('runner')\n", 0o755)]


class MemoryAdapter:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, bytes | str, int]] = []
        self.commands: list[tuple[SshTarget, str, int, int]] = []

    def upload_text(self, target: SshTarget, *, remote_path: str, content: str, mode: int) -> None:
        self.uploads.append((remote_path, content, mode))

    def upload_bytes(
        self, target: SshTarget, *, remote_path: str, content: bytes, mode: int
    ) -> None:
        self.uploads.append((remote_path, content, mode))

    def upload_stream(self, target: SshTarget, *, remote_path: str, source, mode: int) -> None:
        self.uploads.append((remote_path, source.read(), mode))

    def run_command(
        self,
        target: SshTarget,
        *,
        command: str,
        timeout_seconds: int,
        output_limit_bytes: int = 4096,
    ) -> RemoteCommandResult:
        self.commands.append((target, command, timeout_seconds, output_limit_bytes))
        return RemoteCommandResult(0, "ok", "")


class FailingMonitoringUploadAdapter(MemoryAdapter):
    def upload_text(self, target: SshTarget, *, remote_path: str, content: str, mode: int) -> None:
        if remote_path.endswith("monitoring.properties"):
            raise OSError("monitoring upload failed")
        super().upload_text(target, remote_path=remote_path, content=content, mode=mode)


def command() -> RunControlCommand:
    return RunControlCommand(
        request_id=REQUEST_ID,
        action="start",
        run_id=RUN_ID,
        node_id=NODE_ID,
        reason=None,
        source_type="protocol_smoke",
        host="ssh-load-node",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        trusted_host_key_algorithm="ssh-ed25519",
        trusted_host_key_public_key=(
            "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC"
        ),
        trusted_host_key_fingerprint_sha256="SHA256:SurgePilotTrustedHostKey",
        argv=("python3", "/opt/surgepilot/runner/runner.py", "start", "--run-id", RUN_ID, "--fake"),
    )


def monitoring_settings():
    return replace(
        get_settings(),
        monitoring_enabled=True,
        monitoring_influxdb_internal_url="http://influxdb:8086",
        monitoring_influxdb_node_write_url=NODE_WRITE_URL,
        monitoring_influxdb_org="surgepilot",
        monitoring_influxdb_bucket="jmeter",
        monitoring_influxdb_token_configured=True,
    )


def seed_monitoring_run(
    db_session: Session, *, run_type: str, status: str | None, node_write_url: str | None
) -> str:
    now = datetime.now(UTC)
    db_session.add(
        Run(
            id=RUN_ID,
            workspace_id=DEFAULT_WORKSPACE_ID,
            run_type=run_type,
            state="initializing",
            source_type="test_plan",
            source_id="01HZX3Y9M0E9W7Z6M5QK9S8P7S",
            selected_node_id=NODE_ID,
            triggered_by_user_id="01HZX3Y9M0E9W7Z6M5QK9S8P7U",
            forced_convergence=False,
            validity="valid",
            sla_result="not_evaluated",
            created_at=now,
            updated_at=now,
        )
    )
    if status is not None:
        db_session.add(
            RunMonitoringConfig(
                run_id=RUN_ID,
                workspace_id=DEFAULT_WORKSPACE_ID,
                status=status,
                disabled_reason=None,
                influxdb_node_write_url=node_write_url,
                dashboard_uid="surgepilot-jmeter-13644",
                grafana_base_path="/grafana",
                created_at=now,
            )
        )
    db_session.flush()
    db_session.commit()
    return RUN_ID


def executor(db_session: Session, adapter: MemoryAdapter) -> RemoteRunControlExecutor:
    return RemoteRunControlExecutor(
        session_factory=sessionmaker(bind=db_session.get_bind(), expire_on_commit=False),
        credential_resolver=lambda node_id: CredentialPlaintext(
            auth_type="password", password="pw"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=monitoring_settings(),
        options=RemoteExecutorOptions(command_timeout_seconds=9, output_limit_bytes=123),
    )


def monitoring_uploads(adapter: MemoryAdapter) -> list[tuple[str, bytes | str, int]]:
    return [item for item in adapter.uploads if item[0].endswith("monitoring.properties")]


def test_monitoring_token_worker_accessor_reads_env_file_and_ignores_unreadable(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN", raising=False)
    token_file = tmp_path / "monitoring-token"
    token_file.write_text("secret-monitoring-token\n", encoding="utf-8")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE", str(token_file))
    assert _monitoring_token_from_worker_env() == "secret-monitoring-token"

    monkeypatch.setenv(
        "SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE", str(tmp_path / "missing-token")
    )
    assert _monitoring_token_from_worker_env() is None


def test_remote_executor_uploads_monitoring_properties_for_enabled_standard_run(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN", "secret-monitoring-token")
    seed_monitoring_run(
        db_session, run_type="standard", status="enabled", node_write_url=NODE_WRITE_URL
    )
    adapter = MemoryAdapter()

    result = executor(db_session, adapter).execute(command())

    assert result.ok is True
    upload = next(iter(monitoring_uploads(adapter)))
    assert upload[0] == (
        f"/opt/surgepilot/runner/runs/{RUN_ID}/secrets/monitoring.properties"
    )
    assert upload[2] == 0o600
    assert isinstance(upload[1], str)
    assert f"SURGEPILOT_RUN_ID={RUN_ID}" in upload[1]
    assert f"SURGEPILOT_NODE_ID={NODE_ID}" in upload[1]
    assert f"SURGEPILOT_INFLUXDB_URL={NODE_WRITE_URL}" in upload[1]
    assert "SURGEPILOT_INFLUXDB_TOKEN=secret-monitoring-token" in upload[1]
    assert "influxdb:8086" not in upload[1]
    assert any("chmod 700" in entry[1] for entry in adapter.commands)


def test_remote_executor_fails_fast_when_enabled_monitoring_token_is_missing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN", raising=False)
    monkeypatch.delenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE", raising=False)
    seed_monitoring_run(
        db_session, run_type="standard", status="enabled", node_write_url=NODE_WRITE_URL
    )
    adapter = MemoryAdapter()

    result = executor(db_session, adapter).execute(command())

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_EXECUTION_FAILED"
    assert monitoring_uploads(adapter) == []
    assert not any("runner.py start" in entry[1] for entry in adapter.commands)


def test_remote_executor_fails_fast_when_monitoring_properties_upload_fails(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN", "secret-monitoring-token")
    seed_monitoring_run(
        db_session, run_type="standard", status="enabled", node_write_url=NODE_WRITE_URL
    )
    adapter = FailingMonitoringUploadAdapter()

    result = executor(db_session, adapter).execute(command())

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_EXECUTION_FAILED"
    assert not any("runner.py start" in entry[1] for entry in adapter.commands)


@pytest.mark.parametrize(
    ("run_type", "status", "node_write_url"),
    [
        ("debug", None, None),
        ("standard", "config_error", None),
        ("standard", None, None),
    ],
)
def test_remote_executor_skips_monitoring_secret_for_debug_disabled_and_config_error(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    run_type: str,
    status: str | None,
    node_write_url: str | None,
) -> None:
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN", "secret-monitoring-token")
    seed_monitoring_run(db_session, run_type=run_type, status=status, node_write_url=node_write_url)
    adapter = MemoryAdapter()

    result = executor(db_session, adapter).execute(command())

    assert result.ok is True
    assert monitoring_uploads(adapter) == []
    assert not any("monitoring.properties" in entry[1] for entry in adapter.commands)
