from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
import pytest

from dataclasses import replace

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.auth import DEFAULT_WORKSPACE_ID
from app.models.dependency_files import DependencyFile
from app.models.runs import Run, RunMonitoringConfig, RunSnapshot
from app.services.load_nodes import CredentialPlaintext
from app.services.run_control_executor import (
    RemoteExecutorOptions,
    RemoteRunControlExecutor,
    _monitoring_token_from_worker_env,
)
from app.services.runner_bundle import RunnerBundleFile
from app.services.runs import RunControlCommand
from app.services import execution_bundles
from app.services.ssh_remote import (
    RemoteCommandResult,
    SshHostKeyChangedError,
    SshHostKeyUntrustedError,
    SshTarget,
)
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture(autouse=True)
def valid_node_api_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "http://192.168.1.50:8080")


class MemoryBundle:
    def files(self):
        return [
            RunnerBundleFile("runner.py", b"print('runner')\n", 0o755),
            RunnerBundleFile("surgepilot_runner/cli.py", b"print('cli')\n", 0o644),
        ]


class MemoryAdapter:
    def __init__(
        self,
        result: RemoteCommandResult | None = None,
        *,
        runtime_version: str = "runtime-test-v1",
    ) -> None:
        self.result = result or RemoteCommandResult(0, "ok", "")
        self.runtime_version = runtime_version
        self.uploads: list[tuple[str, bytes | str, int, str]] = []
        self.commands: list[tuple[SshTarget, str, int, int]] = []

    def upload_text(self, target: SshTarget, *, remote_path: str, content: str, mode: int) -> None:
        self.uploads.append((remote_path, content, mode, target.credential.password or ""))

    def upload_bytes(
        self, target: SshTarget, *, remote_path: str, content: bytes, mode: int
    ) -> None:
        self.uploads.append((remote_path, content, mode, target.credential.password or ""))

    def upload_stream(self, target: SshTarget, *, remote_path: str, source, mode: int) -> None:
        self.uploads.append((remote_path, source.read(), mode, target.credential.password or ""))

    def run_command(
        self,
        target: SshTarget,
        *,
        command: str,
        timeout_seconds: int,
        output_limit_bytes: int = 4096,
    ) -> RemoteCommandResult:
        self.commands.append((target, command, timeout_seconds, output_limit_bytes))
        if "metadata.json" in command:
            return RemoteCommandResult(0, self.runtime_version, "")
        return self.result


class FailingMonitoringUploadAdapter(MemoryAdapter):
    def upload_text(self, target: SshTarget, *, remote_path: str, content: str, mode: int) -> None:
        if remote_path.endswith("monitoring.properties"):
            raise OSError("monitoring upload failed")
        super().upload_text(target, remote_path=remote_path, content=content, mode=mode)


class PartialMonitoringUploadAdapter(MemoryAdapter):
    def __init__(self, *, cleanup_outcome: bool | Exception) -> None:
        super().__init__()
        self.cleanup_outcome = cleanup_outcome
        self.cleanup_attempted = False
        self.remote_secret_paths: set[str] = set()

    def upload_text(self, target: SshTarget, *, remote_path: str, content: str, mode: int) -> None:
        super().upload_text(target, remote_path=remote_path, content=content, mode=mode)
        if remote_path.endswith((".surgepilot.env", "monitoring.properties")):
            self.remote_secret_paths.add(remote_path)
        if remote_path.endswith("monitoring.properties"):
            raise OSError("SFTP close failed after the Monitoring secret was written")

    def run_command(
        self,
        target: SshTarget,
        *,
        command: str,
        timeout_seconds: int,
        output_limit_bytes: int = 4096,
    ) -> RemoteCommandResult:
        if command.startswith("rm -f "):
            self.commands.append((target, command, timeout_seconds, output_limit_bytes))
            self.cleanup_attempted = True
            if isinstance(self.cleanup_outcome, Exception):
                raise self.cleanup_outcome
            if self.cleanup_outcome:
                self.remote_secret_paths.clear()
                return RemoteCommandResult(0, "", "")
            return RemoteCommandResult(1, "", "cleanup failed")
        return super().run_command(
            target,
            command=command,
            timeout_seconds=timeout_seconds,
            output_limit_bytes=output_limit_bytes,
        )


class FailingUploadAdapter(MemoryAdapter):
    def __init__(self, exc: Exception) -> None:
        super().__init__()
        self.exc = exc

    def upload_bytes(
        self, target: SshTarget, *, remote_path: str, content: bytes, mode: int
    ) -> None:
        _ = target, remote_path, content, mode
        raise self.exc


class FailingEnvUploadAdapter(MemoryAdapter):
    def upload_text(self, target: SshTarget, *, remote_path: str, content: str, mode: int) -> None:
        if remote_path.endswith(".surgepilot.env"):
            raise OSError("env upload failed")
        super().upload_text(target, remote_path=remote_path, content=content, mode=mode)


class StartTransportFailureAdapter(MemoryAdapter):
    def run_command(
        self,
        target: SshTarget,
        *,
        command: str,
        timeout_seconds: int,
        output_limit_bytes: int = 4096,
    ) -> RemoteCommandResult:
        if "runner.py start" in command:
            raise OSError("SSH transport closed before the start result was received")
        return super().run_command(
            target,
            command=command,
            timeout_seconds=timeout_seconds,
            output_limit_bytes=output_limit_bytes,
        )


def command() -> RunControlCommand:
    return RunControlCommand(
        request_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        action="start",
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        reason=None,
        source_type="protocol_smoke",
        host="ssh-load-node",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        trusted_host_key_algorithm="ssh-ed25519",
        trusted_host_key_public_key="AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        trusted_host_key_fingerprint_sha256="SHA256:SurgePilotTrustedHostKey",
        argv=(
            "python3",
            "/opt/surgepilot/runner/runner.py",
            "start",
            "--run-id",
            "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
            "--fake",
        ),
        expected_runtime_version="runtime-test-v1",
    )


class MemoryStorage:
    def __init__(self, objects: dict[tuple[str, str], bytes]) -> None:
        self.objects = objects

    def get_stream(self, *, bucket: str, object_key: str):
        return execution_bundles.StoredBundleObject(
            stream=BytesIO(self.objects[(bucket, object_key)]),
            size_bytes=len(self.objects[(bucket, object_key)]),
        )


def debug_command(run_id: str) -> RunControlCommand:
    return RunControlCommand(
        request_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        action="start",
        run_id=run_id,
        node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        reason=None,
        source_type="debug_scenario",
        host="ssh-load-node",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        trusted_host_key_algorithm="ssh-ed25519",
        trusted_host_key_public_key="AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        trusted_host_key_fingerprint_sha256="SHA256:SurgePilotTrustedHostKey",
        argv=(
            "python3",
            "/opt/surgepilot/runner/runner.py",
            "start",
            "--run-id",
            run_id,
        ),
        expected_runtime_version="runtime-test-v1",
    )


def plan_command(run_id: str) -> RunControlCommand:
    return RunControlCommand(
        request_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        action="start",
        run_id=run_id,
        node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        reason=None,
        source_type="test_plan",
        host="ssh-load-node",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        trusted_host_key_algorithm="ssh-ed25519",
        trusted_host_key_public_key="AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        trusted_host_key_fingerprint_sha256="SHA256:SurgePilotTrustedHostKey",
        argv=(
            "python3",
            "/opt/surgepilot/runner/runner.py",
            "start",
            "--run-id",
            run_id,
        ),
        expected_runtime_version="runtime-test-v1",
    )


def settings():
    return replace(
        get_settings(),
        app_base_url="http://api:8000",
        runner_internal_token="runner-secret-token",
        load_node_ssh_connect_timeout_seconds=3,
        runner_force_kill_ssh_timeout_seconds=7,
    )


def monitoring_settings():
    return replace(
        settings(),
        monitoring_enabled=True,
        monitoring_influxdb_internal_url="http://influxdb:8086",
        monitoring_influxdb_node_write_url="https://node-write.example.test",
        monitoring_influxdb_org="surgepilot",
        monitoring_influxdb_bucket="jmeter",
        monitoring_influxdb_token_configured=True,
    )


def seed_monitoring_run(db_session: Session, *, run_type: str, status: str = "enabled") -> str:
    run_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7B"
    now = datetime.now(UTC)
    db_session.add(
        Run(
            id=run_id,
            workspace_id=DEFAULT_WORKSPACE_ID,
            run_type=run_type,
            state="initializing",
            source_type="test_plan",
            source_id="01HZX3Y9M0E9W7Z6M5QK9S8P7S",
            selected_node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
            triggered_by_user_id="01HZX3Y9M0E9W7Z6M5QK9S8P7U",
            forced_convergence=False,
            validity="valid",
            sla_result="not_evaluated",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        RunSnapshot(
            id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
            workspace_id=DEFAULT_WORKSPACE_ID,
            run_id=run_id,
            snapshot_version=1,
            snapshot_hash="b" * 64,
            snapshot_json={"runType": run_type, "sourceType": "test_plan", "scenarioItems": []},
            created_at=now,
        )
    )
    if status in {"enabled", "config_error"}:
        db_session.add(
            RunMonitoringConfig(
                run_id=run_id,
                workspace_id=DEFAULT_WORKSPACE_ID,
                status=status,
                disabled_reason=None,
                influxdb_node_write_url="https://node-write.example.test"
                if status == "enabled"
                else None,
                dashboard_uid="surgepilot-jmeter-13644",
                grafana_base_path="/grafana",
                created_at=now,
            )
        )
    db_session.flush()
    db_session.commit()
    return run_id


def test_monitoring_token_worker_accessor_reads_env_file_and_ignores_unreadable(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN", raising=False)
    token_file = tmp_path / "monitoring-token"
    token_file.write_text("secret-monitoring-token\n", encoding="utf-8")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE", str(token_file))
    assert _monitoring_token_from_worker_env() == "secret-monitoring-token"

    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE", str(tmp_path / "missing-token"))
    assert _monitoring_token_from_worker_env() is None


def test_remote_executor_rejects_runtime_mismatch_before_upload() -> None:
    adapter = MemoryAdapter(runtime_version="runtime-old")
    executor = RemoteRunControlExecutor(
        credential_resolver=lambda _node_id: CredentialPlaintext(
            auth_type="password", password="ssh-password"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=settings(),
    )

    result = executor.execute(command())

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_RUNTIME_MISMATCH"
    assert adapter.uploads == []


def test_remote_executor_rejects_missing_allocation_runtime_before_upload() -> None:
    adapter = MemoryAdapter(runtime_version="runtime-test-v1")
    executor = RemoteRunControlExecutor(
        credential_resolver=lambda _node_id: CredentialPlaintext(
            auth_type="password", password="ssh-password"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=settings(),
    )

    result = executor.execute(replace(command(), expected_runtime_version=""))

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_RUNTIME_MISMATCH"
    assert adapter.uploads == []


def test_remote_executor_uploads_monitoring_properties_for_enabled_standard_run(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN", "secret-monitoring-token")
    run_id = seed_monitoring_run(db_session, run_type="standard", status="enabled")
    adapter = MemoryAdapter()
    executor = RemoteRunControlExecutor(
        session_factory=sessionmaker(bind=db_session.get_bind(), expire_on_commit=False),
        credential_resolver=lambda node_id: CredentialPlaintext(
            auth_type="password", password="pw"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=monitoring_settings(),
        options=RemoteExecutorOptions(command_timeout_seconds=9, output_limit_bytes=123),
    )

    result = executor.execute(plan_command(run_id))

    assert result.ok is True
    upload = next(item for item in adapter.uploads if item[0].endswith("monitoring.properties"))
    assert upload[0] == (
        "/opt/surgepilot/runner/runs/01HZX3Y9M0E9W7Z6M5QK9S8P7B/secrets/monitoring.properties"
    )
    assert upload[2] == 0o600
    assert "SURGEPILOT_RUN_ID=01HZX3Y9M0E9W7Z6M5QK9S8P7B" in upload[1]
    assert "SURGEPILOT_NODE_ID=01HZX3Y9M0E9W7Z6M5QK9S8P7C" in upload[1]
    assert "SURGEPILOT_INFLUXDB_URL=https://node-write.example.test" in upload[1]
    assert "SURGEPILOT_INFLUXDB_TOKEN=secret-monitoring-token" in upload[1]
    assert "influxdb:8086" not in upload[1]
    assert any("chmod 700" in command for _target, command, _timeout, _limit in adapter.commands)


def test_remote_executor_fails_fast_when_enabled_monitoring_token_is_missing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN", raising=False)
    monkeypatch.delenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE", raising=False)
    run_id = seed_monitoring_run(db_session, run_type="standard", status="enabled")
    adapter = MemoryAdapter()
    executor = RemoteRunControlExecutor(
        session_factory=sessionmaker(bind=db_session.get_bind(), expire_on_commit=False),
        credential_resolver=lambda node_id: CredentialPlaintext(
            auth_type="password", password="pw"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=monitoring_settings(),
        options=RemoteExecutorOptions(command_timeout_seconds=9, output_limit_bytes=123),
    )

    result = executor.execute(plan_command(run_id))

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_EXECUTION_FAILED"
    assert not any(
        command.endswith(" runner.py start")
        for _target, command, _timeout, _limit in adapter.commands
    )
    assert not any(item[0].endswith("monitoring.properties") for item in adapter.uploads)


def test_remote_executor_fails_fast_when_monitoring_properties_upload_fails(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN", "secret-monitoring-token")
    run_id = seed_monitoring_run(db_session, run_type="standard", status="enabled")
    adapter = FailingMonitoringUploadAdapter()
    executor = RemoteRunControlExecutor(
        session_factory=sessionmaker(bind=db_session.get_bind(), expire_on_commit=False),
        credential_resolver=lambda node_id: CredentialPlaintext(
            auth_type="password", password="pw"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=monitoring_settings(),
        options=RemoteExecutorOptions(command_timeout_seconds=9, output_limit_bytes=123),
    )

    result = executor.execute(plan_command(run_id))

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_EXECUTION_FAILED"
    assert result.quarantine_node is False
    assert not any(
        "runner.py start" in command for _target, command, _timeout, _limit in adapter.commands
    )


@pytest.mark.parametrize(
    ("cleanup_outcome", "expected_quarantine"),
    [(True, False), (False, True), (TimeoutError("cleanup timed out"), True)],
)
def test_remote_executor_compensates_for_partially_uploaded_pre_start_secrets(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    cleanup_outcome: bool | Exception,
    expected_quarantine: bool,
) -> None:
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN", "secret-monitoring-token")
    run_id = seed_monitoring_run(db_session, run_type="standard", status="enabled")
    adapter = PartialMonitoringUploadAdapter(cleanup_outcome=cleanup_outcome)
    executor = RemoteRunControlExecutor(
        session_factory=sessionmaker(bind=db_session.get_bind(), expire_on_commit=False),
        credential_resolver=lambda node_id: CredentialPlaintext(
            auth_type="password", password="pw"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=monitoring_settings(),
        options=RemoteExecutorOptions(command_timeout_seconds=9, output_limit_bytes=123),
    )

    result = executor.execute(plan_command(run_id))

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_EXECUTION_FAILED"
    assert result.quarantine_node is expected_quarantine
    assert adapter.cleanup_attempted is True
    assert bool(adapter.remote_secret_paths) is expected_quarantine
    assert not any(
        "runner.py start" in command for _target, command, _timeout, _limit in adapter.commands
    )


@pytest.mark.parametrize(
    ("run_type", "status"), [("debug", "enabled"), ("standard", "config_error")]
)
def test_remote_executor_does_not_upload_monitoring_properties_for_debug_or_config_error(
    db_session: Session, run_type: str, status: str
) -> None:
    run_id = seed_monitoring_run(db_session, run_type=run_type, status=status)
    adapter = MemoryAdapter()
    executor = RemoteRunControlExecutor(
        session_factory=sessionmaker(bind=db_session.get_bind(), expire_on_commit=False),
        credential_resolver=lambda node_id: CredentialPlaintext(
            auth_type="password", password="pw"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=monitoring_settings(),
        options=RemoteExecutorOptions(command_timeout_seconds=9, output_limit_bytes=123),
    )

    result = executor.execute(plan_command(run_id))

    assert result.ok is True
    assert not any(item[0].endswith("monitoring.properties") for item in adapter.uploads)


def test_remote_executor_uploads_bundle_and_runs_without_token_in_command() -> None:
    adapter = MemoryAdapter()
    executor = RemoteRunControlExecutor(
        credential_resolver=lambda node_id: CredentialPlaintext(
            auth_type="password", password=f"password-for-{node_id}"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=settings(),
        options=RemoteExecutorOptions(command_timeout_seconds=9, output_limit_bytes=123),
    )

    result = executor.execute(command())

    assert result.ok is True
    upload_paths = [path for path, _content, _mode, _password in adapter.uploads]
    assert "/opt/surgepilot/runner/runner.py" in upload_paths
    assert "/opt/surgepilot/runner/surgepilot_runner/cli.py" in upload_paths
    env_upload = next(item for item in adapter.uploads if item[0].endswith(".surgepilot.env"))
    assert env_upload[2] == 0o600
    assert "runner-secret-token" not in env_upload[1]
    assert "RUNNER_INTERNAL_TOKEN=node:01HZX3Y9M0E9W7Z6M5QK9S8P7C:" in env_upload[1]
    assert "current/metadata.json" in adapter.commands[0][1]
    remote_command = adapter.commands[-1][1]
    assert remote_command.startswith("set -eu; mkdir -p ")
    assert "runner-secret-token" not in remote_command
    assert "password-for-" not in remote_command
    assert (
        "set -a && . /opt/surgepilot/runner/runs/01HZX3Y9M0E9W7Z6M5QK9S8P7B/.surgepilot.env && set +a"
        in remote_command
    )
    assert (
        "trap 'rm -f /opt/surgepilot/runner/runs/01HZX3Y9M0E9W7Z6M5QK9S8P7B/.surgepilot.env' EXIT"
        in remote_command
    )
    assert (
        "rm -f /opt/surgepilot/runner/runs/01HZX3Y9M0E9W7Z6M5QK9S8P7B/.surgepilot.env"
        in remote_command
    )
    assert adapter.commands[-1][2] == 9
    assert adapter.commands[-1][3] == 123


def test_remote_executor_uploads_debug_scenario_execution_bundle(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7B"
    dependency_file_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7D"
    object_key = f"dependency-files/{DEFAULT_WORKSPACE_ID}/{dependency_file_id}/users.csv"
    now = datetime.now(UTC)
    db_session.add(
        DependencyFile(
            id=dependency_file_id,
            workspace_id=DEFAULT_WORKSPACE_ID,
            filename="users.csv",
            content_type="text/csv",
            size_bytes=12,
            sha256="a" * 64,
            storage_bucket="surgepilot",
            storage_object_key=object_key,
            status="available",
            created_by="01HZX3Y9M0E9W7Z6M5QK9S8P7U",
            created_at=now,
            deleted_by=None,
            deleted_at=None,
        )
    )
    db_session.add(
        Run(
            id=run_id,
            workspace_id=DEFAULT_WORKSPACE_ID,
            run_type="debug",
            state="initializing",
            source_type="debug_scenario",
            source_id="01HZX3Y9M0E9W7Z6M5QK9S8P7S",
            selected_node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
            triggered_by_user_id="01HZX3Y9M0E9W7Z6M5QK9S8P7U",
            forced_convergence=False,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        RunSnapshot(
            id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
            workspace_id=DEFAULT_WORKSPACE_ID,
            run_id=run_id,
            snapshot_version=1,
            snapshot_hash="b" * 64,
            snapshot_json={
                "snapshotVersion": 1,
                "runType": "debug",
                "sourceType": "debug_scenario",
                "sourceId": "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
                "sourceRevision": 1,
                "scenario": {
                    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
                    "name": "Checkout flow",
                    "scenarioType": "visual",
                    "baseUrlExpression": "https://api.example.internal",
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
                            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
                            "dependencyFileId": dependency_file_id,
                            "displayName": "users.csv",
                            "delimiter": ",",
                            "quoted": None,
                            "loop": True,
                            "variableNames": ["username"],
                            "randomOrder": False,
                            "enabled": True,
                        }
                    ],
                    "steps": [
                        {
                            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7G",
                            "enabled": True,
                            "name": "Health",
                            "method": "GET",
                            "path": "/health",
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
                            "assertions": [],
                            "scripts": [],
                            "settings": {
                                "thinkTimeMs": None,
                                "timeoutMs": None,
                                "followRedirects": None,
                                "keepAlive": None,
                            },
                        }
                    ],
                },
                "envGroup": None,
                "dependencyFiles": [
                    {
                        "id": dependency_file_id,
                        "filename": "users.csv",
                        "sizeBytes": 12,
                        "sha256": "a" * 64,
                        "refType": "data_source",
                        "stepId": None,
                    }
                ],
            },
            created_at=now,
        )
    )
    db_session.commit()
    factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, expire_on_commit=False, future=True
    )
    adapter = MemoryAdapter()
    monkeypatch.setattr(
        "app.services.execution_bundles.get_storage_client",
        lambda: MemoryStorage({("surgepilot", object_key): b"alice,secret\n"}),
    )
    executor = RemoteRunControlExecutor(
        session_factory=factory,
        credential_resolver=lambda node_id: CredentialPlaintext(
            auth_type="password", password=f"password-for-{node_id}"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=settings(),
        options=RemoteExecutorOptions(command_timeout_seconds=9, output_limit_bytes=123),
    )

    result = executor.execute(debug_command(run_id))

    assert result.ok is True
    uploads = {path: content for path, content, _mode, _password in adapter.uploads}
    bundle_root = f"/opt/surgepilot/runner/runs/{run_id}/bundle"
    assert f"{bundle_root}/surgepilot.yml" in uploads
    assert f"{bundle_root}/manifest.json" in uploads
    assert f"{bundle_root}/files/{dependency_file_id}/users.csv" in uploads
    assert uploads[f"{bundle_root}/files/{dependency_file_id}/users.csv"] == b"alice,secret\n"
    yaml_text = uploads[f"{bundle_root}/surgepilot.yml"].decode()
    assert "default-address: https://api.example.internal" in yaml_text
    assert "provisioning: local" in yaml_text
    assert "path: files/01HZX3Y9M0E9W7Z6M5QK9S8P7D/users.csv" in yaml_text
    assert (
        "path: /opt/surgepilot/runner/current/apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper"
        in yaml_text
    )
    assert "/opt/surgepilot/apache-jmeter/bin/jmeter" not in yaml_text
    assert object_key not in yaml_text
    assert "--fake" not in adapter.commands[-1][1]


def test_remote_executor_uploads_test_plan_execution_bundle(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7H"
    dependency_file_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7I"
    object_key = f"dependency-files/{DEFAULT_WORKSPACE_ID}/{dependency_file_id}/seed.csv"
    now = datetime.now(UTC)
    db_session.add(
        DependencyFile(
            id=dependency_file_id,
            workspace_id=DEFAULT_WORKSPACE_ID,
            filename="seed.csv",
            content_type="text/csv",
            size_bytes=12,
            sha256="c" * 64,
            storage_bucket="surgepilot",
            storage_object_key=object_key,
            status="available",
            created_by="01HZX3Y9M0E9W7Z6M5QK9S8P7U",
            created_at=now,
            deleted_by=None,
            deleted_at=None,
        )
    )
    db_session.add(
        Run(
            id=run_id,
            workspace_id=DEFAULT_WORKSPACE_ID,
            run_type="standard",
            state="initializing",
            source_type="test_plan",
            source_id="01HZX3Y9M0E9W7Z6M5QK9S8P7P",
            selected_node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
            triggered_by_user_id="01HZX3Y9M0E9W7Z6M5QK9S8P7U",
            forced_convergence=False,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        RunSnapshot(
            id="01HZX3Y9M0E9W7Z6M5QK9S8P7J",
            workspace_id=DEFAULT_WORKSPACE_ID,
            run_id=run_id,
            snapshot_version=1,
            snapshot_hash="d" * 64,
            snapshot_json={
                "schemaVersion": 1,
                "runType": "standard",
                "slaEvaluationMode": "passfail",
                "sourceType": "test_plan",
                "sourceId": "01HZX3Y9M0E9W7Z6M5QK9S8P7P",
                "sourceRevision": 3,
                "testPlan": {
                    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7P",
                    "name": "Checkout Baseline",
                    "revision": 3,
                    "runMode": "sequential",
                },
                "envGroup": {"id": "01HZX3Y9M0E9W7Z6M5QK9S8P7E", "name": "Stage", "variables": {}},
                "resourceRequest": {
                    "mode": "manual",
                    "poolType": "private",
                    "selectedNodeId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
                    "expectedConcurrencyPerNode": 2,
                },
                "scenarioItems": [
                    {
                        "itemId": "01HZX3Y9M0E9W7Z6M5QK9S8P7K",
                        "order": 0,
                        "scenarioId": "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
                        "scenarioRevision": 2,
                        "scenarioName": "Checkout flow",
                        "loadSettings": {
                            "concurrencyPerNode": 2,
                            "rampUpSeconds": 5,
                            "holdForSeconds": 30,
                            "iterations": None,
                            "targetRps": None,
                            "steps": None,
                            "delaySeconds": 0,
                        },
                        "visualScenario": {
                            "requests": [
                                {
                                    "label": "Health",
                                    "method": "GET",
                                    "url": "https://api.example.internal/health",
                                }
                            ]
                        },
                    }
                ],
                "dependencyFiles": [
                    {
                        "id": dependency_file_id,
                        "filename": "seed.csv",
                        "sizeBytes": 12,
                        "sha256": "c" * 64,
                        "refType": "data_source",
                        "stepId": None,
                        "scenarioId": "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
                    }
                ],
                "slaRules": [
                    {
                        "enabled": True,
                        "subject": "avg_rt",
                        "label": None,
                        "condition": "lt",
                        "threshold": {"value": 500, "unit": "ms"},
                        "timeframeLogic": "for",
                        "timeframeSeconds": 10,
                        "action": "continue",
                    }
                ],
            },
            created_at=now,
        )
    )
    db_session.commit()
    factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, expire_on_commit=False, future=True
    )
    adapter = MemoryAdapter()
    monkeypatch.setattr(
        "app.services.execution_bundles.get_storage_client",
        lambda: MemoryStorage({("surgepilot", object_key): b"alice,secret\n"}),
    )
    executor = RemoteRunControlExecutor(
        session_factory=factory,
        credential_resolver=lambda node_id: CredentialPlaintext(
            auth_type="password", password=f"password-for-{node_id}"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=settings(),
        options=RemoteExecutorOptions(command_timeout_seconds=9, output_limit_bytes=123),
    )

    result = executor.execute(plan_command(run_id))

    assert result.ok is True
    uploads = {path: content for path, content, _mode, _password in adapter.uploads}
    bundle_root = f"/opt/surgepilot/runner/runs/{run_id}/bundle"
    assert f"{bundle_root}/surgepilot.yml" in uploads
    assert f"{bundle_root}/execution/generated.yml" in uploads
    assert f"{bundle_root}/manifest.json" in uploads
    assert f"{bundle_root}/files/{dependency_file_id}/seed.csv" in uploads
    assert uploads[f"{bundle_root}/files/{dependency_file_id}/seed.csv"] == b"alice,secret\n"
    yaml_text = uploads[f"{bundle_root}/surgepilot.yml"].decode()
    manifest_text = uploads[f"{bundle_root}/manifest.json"].decode()
    assert "passfail" in yaml_text
    assert "provisioning: local" in yaml_text
    assert (
        "path: /opt/surgepilot/runner/current/apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper"
        in yaml_text
    )
    assert "/opt/surgepilot/apache-jmeter/bin/jmeter" not in yaml_text
    assert "Checkout Baseline" in manifest_text
    assert '"slaEvaluationMode":"passfail"' in manifest_text
    assert object_key not in yaml_text
    assert object_key not in manifest_text


def test_remote_executor_requires_cleanup_after_start_remote_failure() -> None:
    adapter = MemoryAdapter(RemoteCommandResult(2, "", "password=secret-token"))
    executor = RemoteRunControlExecutor(
        credential_resolver=lambda _node_id: CredentialPlaintext(
            auth_type="password", password="ssh-password"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=settings(),
    )

    result = executor.execute(command())

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_REMOTE_FAILED"
    assert result.stderr_preview == "password[REDACTED]"
    assert result.cleanup_required is True
    assert result.quarantine_node is False


def test_remote_executor_maps_timeout() -> None:
    adapter = MemoryAdapter(RemoteCommandResult(None, "", "Remote command timed out.", True))
    executor = RemoteRunControlExecutor(
        credential_resolver=lambda _node_id: CredentialPlaintext(
            auth_type="password", password="ssh-password"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=settings(),
    )

    result = executor.execute(command())

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_TIMEOUT"
    assert result.timed_out is True
    assert result.cleanup_required is True
    assert result.quarantine_node is False


def test_remote_executor_requires_cleanup_when_start_transport_result_is_uncertain() -> None:
    executor = RemoteRunControlExecutor(
        credential_resolver=lambda _node_id: CredentialPlaintext(
            auth_type="password", password="ssh-password"
        ),
        adapter=StartTransportFailureAdapter(),
        runner_bundle=MemoryBundle(),
        settings=settings(),
    )

    result = executor.execute(command())

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_EXECUTION_FAILED"
    assert result.cleanup_required is True
    assert result.quarantine_node is False


class EmptySession:
    def get(self, *_args):
        return None


def test_remote_executor_requires_credential_source() -> None:
    executor = RemoteRunControlExecutor(
        adapter=MemoryAdapter(),
        runner_bundle=MemoryBundle(),
        settings=settings(),
    )

    result = executor.execute(command())

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_EXECUTION_FAILED"


def test_remote_executor_preserves_credential_app_error_without_quarantine() -> None:
    def fail_credential(_node_id: str) -> CredentialPlaintext:
        raise AppError(
            "CREDENTIAL_DECRYPT_FAILED",
            "Credential encryption is not configured.",
            500,
        )

    executor = RemoteRunControlExecutor(
        credential_resolver=fail_credential,
        adapter=MemoryAdapter(),
        runner_bundle=MemoryBundle(),
        settings=settings(),
    )

    result = executor.execute(command())

    assert result.ok is False
    assert result.error_code == "CREDENTIAL_DECRYPT_FAILED"
    assert result.message == "Credential encryption is not configured."
    assert result.quarantine_node is False


@pytest.mark.parametrize(
    ("exception", "expected_code"),
    [
        (
            SshHostKeyUntrustedError("SSH host key is untrusted."),
            "RUN_CONTROL_SSH_HOST_KEY_UNTRUSTED",
        ),
        (
            SshHostKeyChangedError("SSH host key changed."),
            "RUN_CONTROL_SSH_HOST_KEY_CHANGED",
        ),
    ],
)
def test_remote_executor_maps_host_key_failures_without_quarantine(
    exception: Exception, expected_code: str
) -> None:
    executor = RemoteRunControlExecutor(
        credential_resolver=lambda _node_id: CredentialPlaintext(
            auth_type="password", password="ssh-password"
        ),
        adapter=FailingUploadAdapter(exception),
        runner_bundle=MemoryBundle(),
        settings=settings(),
    )

    result = executor.execute(command())

    assert result.ok is False
    assert result.error_code == expected_code
    assert result.message == "Run control SSH host key verification failed."
    assert result.quarantine_node is False


def test_remote_executor_rejects_missing_node_in_session() -> None:
    executor = RemoteRunControlExecutor(settings=settings())

    with pytest.raises(RuntimeError, match="target node was not found"):
        executor._credential_from_session(EmptySession(), node_id=command().node_id)


def test_debug_bundle_build_failure_does_not_touch_ssh_or_quarantine_node(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = MemoryAdapter()
    credential_requested = False

    def credential_resolver(node_id: str) -> CredentialPlaintext:
        nonlocal credential_requested
        credential_requested = True
        return CredentialPlaintext(auth_type="password", password=f"password-for-{node_id}")

    def fail_bundle(*args, **kwargs):
        raise RuntimeError("minio unavailable")

    monkeypatch.setattr(
        "app.services.run_control_executor.build_debug_scenario_execution_bundle", fail_bundle
    )
    executor = RemoteRunControlExecutor(
        session_factory=sessionmaker(bind=db_session.get_bind()),
        credential_resolver=credential_resolver,
        adapter=adapter,
        runner_bundle=MemoryBundle(),
        settings=settings(),
        options=RemoteExecutorOptions(command_timeout_seconds=9, output_limit_bytes=123),
    )

    result = executor.execute(debug_command("01HZX3Y9M0E9W7Z6M5QK9S8P7B"))

    assert result.ok is False
    assert result.error_code == "RUN_BUNDLE_BUILD_FAILED"
    assert result.quarantine_node is False
    assert credential_requested is False
    assert adapter.uploads == []
    assert adapter.commands == []


def test_remote_executor_closes_execution_bundle_streams_when_later_upload_fails(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7B"
    bundle_stream = BytesIO(b"large dependency payload")

    def build_bundle(*args, **kwargs):
        return [
            execution_bundles.ExecutionBundleFile.stream_file(
                "files/01HZX3Y9M0E9W7Z6M5QK9S8P7D/users.csv",
                bundle_stream,
            )
        ]

    monkeypatch.setattr(
        "app.services.run_control_executor.build_debug_scenario_execution_bundle",
        build_bundle,
    )
    executor = RemoteRunControlExecutor(
        session_factory=sessionmaker(bind=db_session.get_bind()),
        credential_resolver=lambda node_id: CredentialPlaintext(
            auth_type="password", password=f"password-for-{node_id}"
        ),
        adapter=FailingEnvUploadAdapter(),
        runner_bundle=MemoryBundle(),
        settings=settings(),
        options=RemoteExecutorOptions(command_timeout_seconds=9, output_limit_bytes=123),
    )

    result = executor.execute(debug_command(run_id))

    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_EXECUTION_FAILED"
    assert result.quarantine_node is False
    assert bundle_stream.closed is True
