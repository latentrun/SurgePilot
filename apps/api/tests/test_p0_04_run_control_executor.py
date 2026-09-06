from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.services.load_nodes import CredentialPlaintext
from app.services.run_control_executor import (
    RemoteExecutorOptions,
    RemoteRunControlExecutor,
)
from app.services.runner_bundle import RunnerBundleFile
from app.services.runs import RunControlCommand
from app.services.ssh_remote import (
    RemoteCommandResult,
    SshHostKeyChangedError,
    SshHostKeyUntrustedError,
    SshTarget,
)

RUN_ID = "01HZX3Y9M0E9W7Z6M5QK9S8P7B"
NODE_ID = "01HZX3Y9M0E9W7Z6M5QK9S8P7C"
REQUEST_ID = "01HZX3Y9M0E9W7Z6M5QK9S8P7A"


def trusted_host_key() -> dict[str, str]:
    return {
        "algorithm": "ssh-ed25519",
        "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        "fingerprintSha256": "SHA256:SurgePilotTrustedHostKey",
    }


@pytest.fixture(autouse=True)
def executor_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "master-runner-token")
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "http://192.168.1.50:8080")


class MemoryBundle:
    def files(self):
        return [
            RunnerBundleFile("runner.py", b"print('runner')\n", 0o755),
            RunnerBundleFile("surgepilot_runner/cli.py", b"print('cli')\n", 0o644),
        ]


class MemoryAdapter:
    def __init__(self, result: RemoteCommandResult | None = None) -> None:
        self.result = result or RemoteCommandResult(0, "ok", "")
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
        return self.result


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


class FailingEnvUploadAdapter(MemoryAdapter):
    def __init__(self, *, cleanup_outcome: bool) -> None:
        super().__init__()
        self.cleanup_outcome = cleanup_outcome
        self.cleanup_attempted = False

    def upload_text(self, target: SshTarget, *, remote_path: str, content: str, mode: int) -> None:
        if remote_path.endswith(".surgepilot.env"):
            raise OSError("env upload failed")
        super().upload_text(target, remote_path=remote_path, content=content, mode=mode)

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
            if self.cleanup_outcome:
                return RemoteCommandResult(0, "", "")
            return RemoteCommandResult(1, "", "cleanup failed")
        return super().run_command(
            target,
            command=command,
            timeout_seconds=timeout_seconds,
            output_limit_bytes=output_limit_bytes,
        )


class UntrustedHostKeyAdapter(MemoryAdapter):
    def run_command(
        self,
        target: SshTarget,
        *,
        command: str,
        timeout_seconds: int,
        output_limit_bytes: int = 4096,
    ) -> RemoteCommandResult:
        if "runner.py" in command:
            raise SshHostKeyUntrustedError()
        return super().run_command(
            target,
            command=command,
            timeout_seconds=timeout_seconds,
            output_limit_bytes=output_limit_bytes,
        )


class ChangedHostKeyAdapter(MemoryAdapter):
    def run_command(
        self,
        target: SshTarget,
        *,
        command: str,
        timeout_seconds: int,
        output_limit_bytes: int = 4096,
    ) -> RemoteCommandResult:
        if "runner.py" in command:
            raise SshHostKeyChangedError()
        return super().run_command(
            target,
            command=command,
            timeout_seconds=timeout_seconds,
            output_limit_bytes=output_limit_bytes,
        )


def command(*, action: str = "start", source_type: str = "protocol_smoke") -> RunControlCommand:
    key = trusted_host_key()
    argv_command = "kill" if action == "force_kill" else action
    argv = (
        "python3",
        "/opt/surgepilot/runner/runner.py",
        argv_command,
        "--run-id",
        RUN_ID,
    )
    if action == "start" and source_type == "protocol_smoke":
        argv = (*argv, "--fake")
    return RunControlCommand(
        request_id=REQUEST_ID,
        action=action,
        run_id=RUN_ID,
        node_id=NODE_ID,
        reason=None,
        source_type=source_type,
        host="ssh-load-node",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        trusted_host_key_algorithm=key["algorithm"],
        trusted_host_key_public_key=key["publicKey"],
        trusted_host_key_fingerprint_sha256=key["fingerprintSha256"],
        argv=argv,
    )


def executor(adapter: MemoryAdapter) -> RemoteRunControlExecutor:
    return RemoteRunControlExecutor(
        credential_resolver=lambda node_id: CredentialPlaintext(
            auth_type="password", password="secret-password"
        ),
        adapter=adapter,
        runner_bundle=MemoryBundle(),
    )


def env_content(adapter: MemoryAdapter) -> str:
    for remote_path, content, _mode, _password in adapter.uploads:
        if remote_path.endswith(".surgepilot.env"):
            assert isinstance(content, str)
            return content
    raise AssertionError("env file was not uploaded")


def test_start_uploads_bundle_and_env_then_runs_fake_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "master-runner-token")
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "http://192.168.1.50:8080")
    adapter = MemoryAdapter()
    result = executor(adapter).execute(command())

    assert result.ok
    uploaded_paths = [entry[0] for entry in adapter.uploads]
    assert uploaded_paths[0].endswith("runner.py")
    assert uploaded_paths[1].endswith("surgepilot_runner/cli.py")
    assert uploaded_paths[-1].endswith("/runs/01HZX3Y9M0E9W7Z6M5QK9S8P7B/.surgepilot.env")
    assert adapter.uploads[-1][2] == 0o600
    assert len(adapter.commands) == 1
    command_text = adapter.commands[0][1]
    assert "runner.py start --run-id 01HZX3Y9M0E9W7Z6M5QK9S8P7B --fake" in command_text
    assert "secret-password" not in command_text


def test_start_env_carries_node_bound_token_and_api_base_url() -> None:
    adapter = MemoryAdapter()
    result = executor(adapter).execute(command())
    assert result.ok
    env = env_content(adapter)
    assert "RUNNER_INTERNAL_TOKEN='node:" in env
    assert "master-runner-token" not in env
    assert "SURGEPILOT_NODE_ID='01HZX3Y9M0E9W7Z6M5QK9S8P7C'" in env
    assert "SURGEPILOT_API_BASE_URL='http://192.168.1.50:8080'" in env


def test_start_env_omits_api_base_url_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SURGEPILOT_NODE_API_BASE_URL")
    adapter = MemoryAdapter()
    result = executor(adapter).execute(command())
    assert result.ok
    env = env_content(adapter)
    assert "SURGEPILOT_API_BASE_URL" not in env
    assert "RUNNER_INTERNAL_TOKEN='node:" in env


@pytest.mark.parametrize(
    ("action", "expected_command"),
    [
        ("stop", "runner.py stop --run-id 01HZX3Y9M0E9W7Z6M5QK9S8P7B"),
        ("force_kill", "runner.py kill --run-id 01HZX3Y9M0E9W7Z6M5QK9S8P7B"),
    ],
)
def test_stop_and_force_kill_invoke_runner_cli(action: str, expected_command: str) -> None:
    adapter = MemoryAdapter()
    result = executor(adapter).execute(command(action=action))
    assert result.ok
    assert len(adapter.commands) == 1
    assert expected_command in adapter.commands[0][1]


def test_start_timeout_reports_cleanup_required() -> None:
    adapter = MemoryAdapter(RemoteCommandResult(None, "", "timed out", timed_out=True))
    result = executor(adapter).execute(command())
    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_TIMEOUT"
    assert result.message == "Run control command timed out."
    assert result.timed_out is True
    assert result.quarantine_node is False
    assert result.cleanup_required is True


def test_stop_remote_failure_reports_quarantine() -> None:
    adapter = MemoryAdapter(RemoteCommandResult(1, "", "stop failed"))
    result = executor(adapter).execute(command(action="stop"))
    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_REMOTE_FAILED"
    assert result.quarantine_node is True
    assert result.cleanup_required is False


def test_force_kill_timeout_reports_quarantine() -> None:
    adapter = MemoryAdapter(RemoteCommandResult(None, "", "timed out", timed_out=True))
    result = executor(adapter).execute(command(action="force_kill"))
    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_TIMEOUT"
    assert result.quarantine_node is True


def test_start_transport_failure_before_result_is_uncertain_cleanup() -> None:
    adapter = StartTransportFailureAdapter()
    result = executor(adapter).execute(command())
    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_EXECUTION_FAILED"
    assert result.cleanup_required is True


def test_untrusted_host_key_failure_is_safe() -> None:
    adapter = UntrustedHostKeyAdapter()
    result = executor(adapter).execute(command())
    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_SSH_HOST_KEY_UNTRUSTED"


def test_changed_host_key_failure_is_safe() -> None:
    adapter = ChangedHostKeyAdapter()
    result = executor(adapter).execute(command())
    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_SSH_HOST_KEY_CHANGED"


@pytest.mark.parametrize("cleanup_ok", [True, False])
def test_env_upload_failure_quarantines_only_when_compensation_fails(
    cleanup_ok: bool,
) -> None:
    adapter = FailingEnvUploadAdapter(cleanup_outcome=cleanup_ok)
    result = executor(adapter).execute(command())
    assert result.ok is False
    assert result.error_code == "RUN_CONTROL_EXECUTION_FAILED"
    assert adapter.cleanup_attempted is True
    assert result.quarantine_node is (not cleanup_ok)


def test_remote_stderr_preview_is_sanitized() -> None:
    adapter = MemoryAdapter(RemoteCommandResult(1, "", "failed password=super-secret"))
    result = executor(adapter).execute(command(action="stop"))
    assert result.ok is False
    assert "super-secret" not in (result.stderr_preview or "")
    assert "password=[REDACTED]" in (result.stderr_preview or "")


def test_credential_app_error_is_preserved() -> None:
    def resolver(_node_id: str) -> CredentialPlaintext:
        raise AppError("CREDENTIAL_DECRYPT_FAILED", "Credential encryption is not configured.", 500)

    adapter = MemoryAdapter()
    result = RemoteRunControlExecutor(
        credential_resolver=resolver,
        adapter=adapter,
        runner_bundle=MemoryBundle(),
    ).execute(command())
    assert result.ok is False
    assert result.error_code == "CREDENTIAL_DECRYPT_FAILED"
    assert result.message == "Credential encryption is not configured."
    assert result.quarantine_node is False


def test_remote_executor_options_defaults() -> None:
    executor_instance = executor(MemoryAdapter())
    assert isinstance(executor_instance.options, RemoteExecutorOptions)
    assert executor_instance.options.output_limit_bytes == 4096
    assert executor_instance.options.command_timeout_seconds > 0
