from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import BinaryIO
import paramiko
import pytest

from app.core.config import get_settings
from app.models.load_nodes import LoadNode
from app.services.load_node_initializer import (
    RealLoadNodeInitializer,
    safe_join,
    safe_remote_path,
)
from app.services.load_nodes import CredentialPlaintext
from app.services.runner_bundle import RunnerBundleFile
from app.services.ssh_remote import (
    RemoteCommandResult,
    SshHostKeyChangedError,
    SshHostKeyUntrustedError,
    SshTarget,
)


def node() -> LoadNode:
    now = datetime.now(UTC)
    return LoadNode(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
        scope="workspace",
        workspace_id="01HZW000000000000000000000",
        host="node.example.test",
        ssh_port=2222,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        auth_type="password",
        ssh_host_key_algorithm="ssh-ed25519",
        ssh_host_key_public_key="AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        ssh_host_key_fingerprint_sha256="SHA256:SurgePilotTrustedHostKey",
        ssh_host_key_trusted_at=now,
        ssh_host_key_trusted_by="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        status="initializing",
        created_by="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        created_at=now,
        updated_at=now,
    )


def credential() -> CredentialPlaintext:
    return CredentialPlaintext(auth_type="password", password="ssh-password")


class FakeBundle:
    def files(self) -> list[RunnerBundleFile]:
        return [
            RunnerBundleFile(relative_path="runner.py", content=b"runner", mode=0o755),
            RunnerBundleFile(relative_path="surgepilot_runner/cli.py", content=b"cli", mode=0o644),
        ]


class FakeAdapter:
    def __init__(
        self,
        results: dict[str, RemoteCommandResult] | None = None,
        exception_on_command: Exception | None = None,
    ) -> None:
        self.results = results or {}
        self.exception_on_command = exception_on_command
        self.commands: list[str] = []
        self.uploads: list[tuple[str, bytes, int]] = []
        self.stream_uploads: list[tuple[str, bytes, int]] = []
        self.targets: list[SshTarget] = []
        self.timeouts_by_command: list[tuple[str, int]] = []

    def upload_text(self, target: SshTarget, *, remote_path: str, content: str, mode: int) -> None:
        self.upload_bytes(
            target, remote_path=remote_path, content=content.encode("utf-8"), mode=mode
        )

    def upload_bytes(
        self, target: SshTarget, *, remote_path: str, content: bytes, mode: int
    ) -> None:
        self.targets.append(target)
        self.uploads.append((remote_path, content, mode))

    def upload_stream(
        self, target: SshTarget, *, remote_path: str, source: BinaryIO, mode: int
    ) -> None:
        self.targets.append(target)
        self.stream_uploads.append((remote_path, source.read(), mode))

    def run_command(
        self,
        target: SshTarget,
        *,
        command: str,
        timeout_seconds: int,
        output_limit_bytes: int = 4096,
    ) -> RemoteCommandResult:
        _ = timeout_seconds, output_limit_bytes
        self.targets.append(target)
        self.commands.append(command)
        self.timeouts_by_command.append((command, timeout_seconds))
        if self.exception_on_command is not None:
            raise self.exception_on_command
        for marker, result in self.results.items():
            if marker in command:
                return result
        if "runner.py version" in command:
            return RemoteCommandResult(
                exit_status=0,
                stdout_preview="SurgePilot Runner 0.1.0\n",
                stderr_preview="",
            )
        if "--version" in command or " -version" in command:
            return RemoteCommandResult(
                exit_status=0, stdout_preview="version ok\n", stderr_preview=""
            )
        return RemoteCommandResult(exit_status=0, stdout_preview="ok\n", stderr_preview="")


def initializer(adapter: FakeAdapter) -> RealLoadNodeInitializer:
    settings = replace(
        get_settings(),
        load_node_ssh_connect_timeout_seconds=7,
        load_node_init_command_timeout_seconds=11,
    )
    return RealLoadNodeInitializer(adapter=adapter, runner_bundle=FakeBundle(), settings=settings)


def test_real_initializer_verifies_dependencies_and_uploads_runner() -> None:
    adapter = FakeAdapter()

    result = initializer(adapter).initialize(node(), credential())

    assert result.ok is True
    assert result.runner_version == "0.1.0"
    assert result.bundle_version == "p0-03"
    assert "[info] SSH connection verified." in result.log
    assert "[info] Runner bundle uploaded." in result.log
    assert any("mkdir -p" in command for command in adapter.commands)
    assert all("runtimes" not in command for command in adapter.commands)
    assert any("python3 --version" in command for command in adapter.commands)
    assert any("java -version" in command for command in adapter.commands)
    assert any("bzt --version" in command for command in adapter.commands)
    assert any("jmeter --version" in command for command in adapter.commands)
    assert any("runner.py version" in command for command in adapter.commands)
    forbidden = ["pip install", "python -m pip", "apt install", "curl ", "wget "]
    assert all(token not in command for token in forbidden for command in adapter.commands)
    assert ("/opt/surgepilot/runner/runner.py", b"runner", 0o755) in adapter.uploads
    assert (
        "/opt/surgepilot/runner/surgepilot_runner/cli.py",
        b"cli",
        0o644,
    ) in adapter.uploads
    assert adapter.targets[0].host == "node.example.test"
    assert adapter.targets[0].connect_timeout_seconds == 7


def test_real_initializer_maps_missing_python_to_stable_error_code() -> None:
    adapter = FakeAdapter(
        results={
            "python3 --version": RemoteCommandResult(
                exit_status=1, stdout_preview="", stderr_preview="python3: command not found"
            )
        }
    )

    result = initializer(adapter).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_PYTHON_MISSING"


def test_real_initializer_maps_missing_java_to_stable_error_code() -> None:
    adapter = FakeAdapter(
        results={
            "java -version": RemoteCommandResult(
                exit_status=1, stdout_preview="", stderr_preview="java: command not found"
            )
        }
    )

    result = initializer(adapter).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_JAVA_MISSING"


def test_real_initializer_maps_missing_taurus_to_stable_error_code() -> None:
    adapter = FakeAdapter(
        results={
            "bzt --version": RemoteCommandResult(
                exit_status=1, stdout_preview="", stderr_preview="bzt: command not found"
            )
        }
    )

    result = initializer(adapter).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_TAURUS_MISSING"


def test_real_initializer_maps_missing_jmeter_to_stable_error_code() -> None:
    adapter = FakeAdapter(
        results={
            "jmeter --version": RemoteCommandResult(
                exit_status=1, stdout_preview="", stderr_preview="jmeter: command not found"
            )
        }
    )

    result = initializer(adapter).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_JMETER_MISSING"


def test_real_initializer_maps_unwritable_runner_home_to_stable_error_code() -> None:
    adapter = FakeAdapter(
        results={
            "mkdir -p": RemoteCommandResult(
                exit_status=1, stdout_preview="", stderr_preview="Permission denied"
            )
        }
    )

    result = initializer(adapter).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_RUNNER_HOME_UNWRITABLE"


def test_real_initializer_maps_timed_out_command_to_ssh_timeout() -> None:
    adapter = FakeAdapter(
        results={
            "python3 --version": RemoteCommandResult(
                exit_status=None, stdout_preview="", stderr_preview="", timed_out=True
            )
        }
    )

    result = initializer(adapter).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_SSH_TIMEOUT"


def test_real_initializer_maps_ssh_auth_failure_to_stable_error_code() -> None:
    adapter = FakeAdapter(exception_on_command=paramiko.AuthenticationException("Auth failed"))

    result = initializer(adapter).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_SSH_AUTH_FAILED"


def test_real_initializer_maps_untrusted_ssh_host_key_to_stable_error_code() -> None:
    adapter = FakeAdapter(exception_on_command=SshHostKeyUntrustedError("Host key untrusted"))

    result = initializer(adapter).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_SSH_HOST_KEY_UNTRUSTED"


def test_real_initializer_maps_changed_ssh_host_key_to_stable_error_code() -> None:
    adapter = FakeAdapter(exception_on_command=SshHostKeyChangedError("Host key changed"))

    result = initializer(adapter).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_SSH_HOST_KEY_CHANGED"


def test_real_initializer_rejects_unsafe_runner_home_before_remote_command() -> None:
    bad_node = replace(node(), runner_home="/tmp/foo;rm -rf /")

    with pytest.raises(ValueError):
        initializer(FakeAdapter()).initialize(bad_node, credential())


def test_safe_remote_path_accepts_valid_posix_paths() -> None:
    assert safe_remote_path("/opt/surgepilot/runner") == "/opt/surgepilot/runner"
    assert safe_remote_path("/home/surgepilot/runner/") == "/home/surgepilot/runner"


def test_safe_remote_path_rejects_unsafe_inputs() -> None:
    unsafe_candidates = ["", "relative/path", "/", "/opt/runner/../escape", "/opt/runner/foo bar"]
    for path in unsafe_candidates:
        with pytest.raises(ValueError):
            safe_remote_path(path)


def test_safe_join_rejects_traversal() -> None:
    assert safe_join("/opt/runner", "bin/runner.py") == "/opt/runner/bin/runner.py"
    with pytest.raises(ValueError):
        safe_join("/opt/runner", "../outside")
