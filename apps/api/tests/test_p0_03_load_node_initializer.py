from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import hashlib
import io
from pathlib import Path
import subprocess
import tarfile
from typing import BinaryIO

import paramiko

from app.core.config import get_settings
from app.models.load_nodes import LoadNode
from app.services.load_node_initializer import (
    local_runtime_artifact_digest,
    parse_sha256_sidecar,
    RealLoadNodeInitializer,
    runtime_activation_command,
    runtime_architecture,
    runtime_critical_files_command,
    runtime_extract_command,
    runtime_metadata_command,
    runtime_plugin_command,
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
    def __init__(self, results: dict[str, RemoteCommandResult] | None = None) -> None:
        self.results = results or {}
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
        for marker, result in self.results.items():
            if marker in command:
                return result
        if "surgepilot-installed-runtime-check" in command:
            return RemoteCommandResult(exit_status=1, stdout_preview="", stderr_preview="")
        if "uname -m" in command:
            return RemoteCommandResult(exit_status=0, stdout_preview="x86_64\n", stderr_preview="")
        if "metadata.json" in command or "apache-jmeter-5.6.3/bin/jmeter" in command:
            return RemoteCommandResult(
                exit_status=0, stdout_preview="Version 5.6.3\n", stderr_preview=""
            )
        if "runner.py version" in command:
            return RemoteCommandResult(
                exit_status=0,
                stdout_preview="SurgePilot Runner 0.1.0\n",
                stderr_preview="",
            )
        if "bin/bzt -h" in command:
            return RemoteCommandResult(
                exit_status=0,
                stdout_preview="BlazeMeter Taurus Tool v1.16.50\n",
                stderr_preview="",
            )
        if "--version" in command or " -version" in command:
            return RemoteCommandResult(
                exit_status=0, stdout_preview="version ok\n", stderr_preview=""
            )
        return RemoteCommandResult(exit_status=0, stdout_preview="ok\n", stderr_preview="")


def write_runtime_artifact(tmp_path: Path, *, version: str = "p0-test") -> Path:
    artifact_dir = tmp_path / "runtime-artifacts"
    artifact_dir.mkdir()
    archive = artifact_dir / f"surgepilot-runtime-linux-amd64-{version}.tar.gz"
    archive.write_bytes(b"runtime archive")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (artifact_dir / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n")
    return artifact_dir


def initializer(
    adapter: FakeAdapter, tmp_path: Path, *, artifact_dir: Path | None = None
) -> RealLoadNodeInitializer:
    artifact_root = artifact_dir or write_runtime_artifact(tmp_path)
    settings = replace(
        get_settings(),
        load_node_ssh_connect_timeout_seconds=7,
        load_node_init_command_timeout_seconds=11,
        load_node_runtime_artifact_dir=str(artifact_root),
        load_node_runtime_version="p0-test",
        load_node_runtime_install_timeout_seconds=17,
    )
    return RealLoadNodeInitializer(adapter=adapter, runner_bundle=FakeBundle(), settings=settings)


def test_runtime_settings_are_loaded_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("LOAD_NODE_RUNTIME_ARTIFACT_DIR", "/srv/surgepilot/runtime-artifacts")
    monkeypatch.setenv("LOAD_NODE_RUNTIME_VERSION", "test-runtime-v1")
    monkeypatch.setenv("LOAD_NODE_RUNTIME_INSTALL_TIMEOUT_SECONDS", "321")

    settings = get_settings()

    assert settings.load_node_runtime_artifact_dir == "/srv/surgepilot/runtime-artifacts"
    assert settings.load_node_runtime_version == "test-runtime-v1"
    assert settings.load_node_runtime_install_timeout_seconds == 321
    assert not hasattr(settings, "load_node_jmeter_path")
    assert not hasattr(settings, "load_node_jmeter_version")


def test_real_initializer_installs_runtime_and_uploads_runner(tmp_path: Path) -> None:
    adapter = FakeAdapter()

    result = initializer(adapter, tmp_path).initialize(node(), credential())

    assert result.ok is True
    assert result.runner_version == "0.1.0"
    assert result.bundle_version == "p0-03"
    assert result.runtime_version == "p0-test"
    assert "[info] SSH connection verified." in result.log
    assert "[info] Runner bundle uploaded." in result.log
    assert any("mkdir -p" in command for command in adapter.commands)
    assert any("python3 --version" in command for command in adapter.commands)
    assert any("java -version" in command for command in adapter.commands)
    assert any("tar --version" in command for command in adapter.commands)
    assert any("uname -m" in command for command in adapter.commands)
    assert any(
        "/opt/surgepilot/runner/tmp/runtime-extract-p0-test/bin/bzt -h" in command
        for command in adapter.commands
    )
    assert any(
        "/opt/surgepilot/runner/tmp/runtime-extract-p0-test/apache-jmeter-5.6.3/bin/jmeter --version"
        in command
        for command in adapter.commands
    )
    assert all("bzt --help" not in command for command in adapter.commands)
    assert all(
        "/opt/surgepilot/apache-jmeter/bin/jmeter" not in command for command in adapter.commands
    )
    forbidden = ["pip install", "python -m pip", "apt install", "curl ", "wget "]
    assert all(token not in command for token in forbidden for command in adapter.commands)
    assert (
        "/opt/surgepilot/runner/tmp/surgepilot-runtime-linux-amd64-p0-test.tar.gz",
        b"runtime archive",
        0o600,
    ) in adapter.stream_uploads
    assert any("runner.py version" in command for command in adapter.commands)
    assert ("/opt/surgepilot/runner/runner.py", b"runner", 0o755) in adapter.uploads
    assert (
        "/opt/surgepilot/runner/surgepilot_runner/cli.py",
        b"cli",
        0o644,
    ) in adapter.uploads
    assert adapter.targets[0].host == "node.example.test"
    assert adapter.targets[0].connect_timeout_seconds == 7


def test_real_initializer_uses_runtime_install_timeout_for_runtime_commands(tmp_path: Path) -> None:
    adapter = FakeAdapter()

    result = initializer(adapter, tmp_path).initialize(node(), credential())

    assert result.ok is True
    runtime_command_markers = [
        "surgepilot-installed-runtime-check",
        "tmp/surgepilot-runtime-linux-amd64-p0-test.tar.gz",
        "tmp/runtime-extract-p0-test",
        "metadata.json",
        "current/bin/bzt -h",
        "apache-jmeter-5.6.3/bin/jmeter --version",
        "jpgc-casutg",
        "Runtime activation",
    ]
    runtime_timeouts = [
        timeout
        for command, timeout in adapter.timeouts_by_command
        if any(marker in command for marker in runtime_command_markers)
    ]
    assert runtime_timeouts
    assert set(runtime_timeouts) == {17}


def test_runtime_extract_command_rejects_symlinked_tmp_outside_runner_home(tmp_path: Path) -> None:
    runner_home = tmp_path / "runner"
    outside = tmp_path / "outside"
    runner_home.mkdir()
    outside.mkdir()
    (runner_home / "tmp").symlink_to(outside, target_is_directory=True)
    archive = tmp_path / "runtime.tar.gz"
    metadata = tmp_path / "metadata.json"
    metadata.write_text('{"name":"surgepilot-runtime"}')
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(metadata, arcname="metadata.json")

    result = subprocess.run(
        runtime_extract_command(
            archive_path=str(archive),
            runner_home=str(runner_home),
            version="p0-test",
        ),
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode != 0
    assert not (outside / "runtime-extract-p0-test").exists()


def run_runtime_extract(archive: Path, runner_home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        runtime_extract_command(
            archive_path=str(archive),
            runner_home=str(runner_home),
            version="p0-test",
        ),
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_archive_with_member(tmp_path: Path, member: tarfile.TarInfo) -> Path:
    archive = tmp_path / f"runtime-{abs(hash(member.name))}.tar.gz"
    metadata = tarfile.TarInfo("metadata.json")
    metadata_content = b'{"name":"surgepilot-runtime"}'
    metadata.size = len(metadata_content)
    with tarfile.open(archive, "w:gz") as tar:
        tar.addfile(metadata, io.BytesIO(metadata_content))
        if member.isfile():
            content = b"bad"
            member.size = len(content)
            tar.addfile(member, io.BytesIO(content))
        else:
            tar.addfile(member)
    return archive


def test_runtime_extract_command_rejects_absolute_and_parent_traversal_members(
    tmp_path: Path,
) -> None:
    runner_home = tmp_path / "runner"
    (runner_home / "tmp").mkdir(parents=True)

    for unsafe_name in ("/absolute.txt", "safe/../escape.txt"):
        member = tarfile.TarInfo(unsafe_name)
        member.type = tarfile.REGTYPE
        archive = write_archive_with_member(tmp_path, member)

        result = run_runtime_extract(archive, runner_home)

        assert result.returncode != 0
        assert not (runner_home / "tmp" / "runtime-extract-p0-test" / "escape.txt").exists()


def test_runtime_extract_command_rejects_symlink_escape_and_special_tar_types(
    tmp_path: Path,
) -> None:
    runner_home = tmp_path / "runner"
    (runner_home / "tmp").mkdir(parents=True)
    symlink_member = tarfile.TarInfo("safe/link")
    symlink_member.type = tarfile.SYMTYPE
    symlink_member.linkname = "../../outside"
    fifo_member = tarfile.TarInfo("safe/fifo")
    fifo_member.type = tarfile.FIFOTYPE

    for member in (symlink_member, fifo_member):
        archive = write_archive_with_member(tmp_path, member)

        result = run_runtime_extract(archive, runner_home)

        assert result.returncode != 0


def test_runtime_activation_failure_preserves_existing_current_symlink(tmp_path: Path) -> None:
    runner_home = tmp_path / "runner"
    runtimes = runner_home / "runtimes"
    runtimes.mkdir(parents=True)
    old_target = runtimes / "old"
    old_target.mkdir()
    (runner_home / "current").symlink_to(old_target)
    tmp_runtime = runner_home / "tmp" / "runtime-extract-p0-test"
    tmp_runtime.mkdir(parents=True)
    (tmp_runtime / "metadata.json").write_text("{}")
    runtimes.chmod(0o555)
    try:
        result = subprocess.run(
            runtime_activation_command(
                runner_home=str(runner_home),
                tmp_runtime=str(tmp_runtime),
                version="p0-test",
            ),
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    finally:
        runtimes.chmod(0o755)

    assert result.returncode != 0
    assert (runner_home / "current").resolve() == old_target.resolve()


def test_runtime_activation_command_replaces_stale_inactive_target(tmp_path: Path) -> None:
    runner_home = tmp_path / "runner"
    runtimes = runner_home / "runtimes"
    runtimes.mkdir(parents=True)
    old_target = runner_home / "runtimes" / "old"
    old_target.mkdir()
    (runner_home / "current").symlink_to(old_target)
    stale_target = runner_home / "runtimes" / "p0-test-stale"
    stale_target.mkdir()
    (stale_target / "stale.txt").write_text("stale")
    tmp_runtime = runner_home / "tmp" / "runtime-extract-p0-test"
    tmp_runtime.mkdir(parents=True)
    (tmp_runtime / "metadata.json").write_text("{}")

    result = subprocess.run(
        runtime_activation_command(
            runner_home=str(runner_home),
            tmp_runtime=str(tmp_runtime),
            version="p0-test",
        ),
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 0, result.stderr
    current_target = (runner_home / "current").resolve()
    assert current_target.parent == runtimes.resolve()
    assert current_target.name.startswith("p0-test-")
    assert current_target != stale_target.resolve()
    assert stale_target.exists()
    assert not old_target.exists()
    assert (current_target / "metadata.json").exists()


def test_runtime_activation_command_repairs_damaged_active_same_version(
    tmp_path: Path,
) -> None:
    runner_home = tmp_path / "runner"
    runtimes = runner_home / "runtimes"
    runtimes.mkdir(parents=True)
    active_target = runtimes / "p0-test-active"
    active_plugin_dir = active_target / "apache-jmeter-5.6.3" / "lib" / "ext"
    active_plugin_dir.mkdir(parents=True)
    active_plugin = active_plugin_dir / "jmeter-plugins-casutg-2.10.jar"
    active_plugin.write_bytes(b"damaged")
    (runner_home / "current").symlink_to(active_target)

    tmp_runtime = runner_home / "tmp" / "runtime-extract-p0-test"
    candidate_plugin_dir = tmp_runtime / "apache-jmeter-5.6.3" / "lib" / "ext"
    candidate_plugin_dir.mkdir(parents=True)
    candidate_plugin = candidate_plugin_dir / "jmeter-plugins-casutg-2.10.jar"
    candidate_plugin.write_bytes(b"verified runtime jar")
    (tmp_runtime / "metadata.json").write_text('{"version":"p0-test"}')

    result = subprocess.run(
        runtime_activation_command(
            runner_home=str(runner_home),
            tmp_runtime=str(tmp_runtime),
            version="p0-test",
        ),
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 0, result.stderr
    current_target = (runner_home / "current").resolve()
    assert current_target.parent == runtimes.resolve()
    assert current_target.name.startswith("p0-test-")
    assert current_target != active_target.resolve()
    assert not active_target.exists()
    assert (
        current_target / "apache-jmeter-5.6.3" / "lib" / "ext" / "jmeter-plugins-casutg-2.10.jar"
    ).read_bytes() == b"verified runtime jar"


def test_runtime_activation_command_never_removes_active_target_before_current_switch() -> None:
    command = runtime_activation_command(
        runner_home="/opt/surgepilot/runner",
        tmp_runtime="/opt/surgepilot/runner/tmp/runtime-extract-p0-test",
        version="p0-test",
    )

    assert "rm -rf" not in command
    assert "os.replace(tmp_runtime, target)" in command
    assert "os.replace(current_tmp, current)" in command
    assert command.index("os.replace(tmp_runtime, target)") < command.index(
        "os.replace(current_tmp, current)"
    )
    assert command.index("os.replace(current_tmp, current)") < command.index(
        "shutil.rmtree(old_target"
    )


def test_runtime_activation_command_never_deletes_runtime_root(tmp_path: Path) -> None:
    runner_home = tmp_path / "runner"
    runtimes = runner_home / "runtimes"
    runtimes.mkdir(parents=True)
    marker = runtimes / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    current = runner_home / "current"
    current.symlink_to(runtimes)
    tmp_runtime = runner_home / "tmp-runtime"
    tmp_runtime.mkdir()
    (tmp_runtime / "metadata.json").write_text("{}", encoding="utf-8")

    result = subprocess.run(
        runtime_activation_command(
            runner_home=str(runner_home),
            tmp_runtime=str(tmp_runtime),
            version="p0-test",
        ),
        shell=True,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert marker.read_text(encoding="utf-8") == "keep"
    current_target = current.resolve()
    assert current_target.parent == runtimes.resolve()
    assert current_target.name.startswith("p0-test-")


def test_runtime_critical_files_command_rejects_system_bzt_wrappers() -> None:
    command = runtime_critical_files_command("/opt/surgepilot/runner/current")

    assert "python/bin/python3" in command
    assert "/usr/local/bin/bzt" in command


def test_runtime_critical_files_reject_system_python_wrapper() -> None:
    command = runtime_critical_files_command("/opt/surgepilot/runner/current")

    assert "/usr/bin/python3" in command


def test_runtime_metadata_rejects_e2e_system_python_marker() -> None:
    command = runtime_metadata_command(
        runtime_path="/opt/surgepilot/runner/current",
        version="p0-test",
        metadata_arch="amd64",
    )

    assert "system-e2e" in command


def test_runtime_plugin_command_requires_valid_jar_zip() -> None:
    command = runtime_plugin_command("/opt/surgepilot/runner/current")

    assert "zipfile.is_zipfile" in command
    assert "jmeter-plugins-casutg" in command
    assert "jmeter-plugins-json" in command
    assert "jmeter-plugins-tst" in command
    assert "jmeter-plugins-random-csv-data-set" in command
    assert "influxdb2-listener" in command
    assert "JSONPathAssertion.class" in command
    assert "VariableThroughputTimer.class" in command
    assert "RandomCSVDataSetConfig.class" in command
    assert "InfluxDatabaseBackendListenerClient.class" in command


def test_runtime_critical_files_command_requires_monitoring_wrapper() -> None:
    command = runtime_critical_files_command("/opt/surgepilot/runner/current")

    assert "apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper" in command
    assert "python/lib/surgepilot_runner/jmeter_wrapper.py" in command
    assert "-m surgepilot_runner.jmeter_wrapper" in command
    assert "InfluxDatabaseBackendListenerClient" in command
    assert "monitoring.properties" in command


def test_real_initializer_does_not_fail_after_activation_probe(tmp_path: Path) -> None:
    adapter = FakeAdapter(
        {
            "current/bin/bzt -h": RemoteCommandResult(
                exit_status=127, stdout_preview="", stderr_preview="current unavailable"
            )
        }
    )

    result = initializer(adapter, tmp_path).initialize(node(), credential())

    assert result.ok is True
    assert any("surgepilot-runtime-activation" in command for command in adapter.commands)


def test_real_initializer_maps_runtime_bzt_failure_to_stable_error_code(tmp_path: Path) -> None:
    adapter = FakeAdapter(
        {
            "tmp/runtime-extract-p0-test/bin/bzt -h": RemoteCommandResult(
                exit_status=127,
                stdout_preview="",
                stderr_preview="password=secret bzt: not found",
            )
        }
    )

    result = initializer(adapter, tmp_path).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_RUNTIME_BZT_FAILED"
    assert "secret" not in result.log
    assert "not found" not in result.log
    assert "Runtime Taurus check failed" in result.log


def test_real_initializer_maps_timed_out_command_to_ssh_timeout(tmp_path: Path) -> None:
    adapter = FakeAdapter(
        {
            "python3 --version": RemoteCommandResult(
                exit_status=None,
                stdout_preview="",
                stderr_preview="Remote command timed out.",
                timed_out=True,
            )
        }
    )

    result = initializer(adapter, tmp_path).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_SSH_TIMEOUT"
    assert "timed out" in result.log


def test_real_initializer_maps_ssh_auth_failure_to_stable_error_code(tmp_path: Path) -> None:
    class AuthFailAdapter(FakeAdapter):
        def run_command(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise paramiko.AuthenticationException("bad password")

    result = initializer(AuthFailAdapter(), tmp_path).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_SSH_AUTH_FAILED"
    assert "bad password" not in result.log


def test_real_initializer_maps_untrusted_ssh_host_key_to_stable_error_code(
    tmp_path: Path,
) -> None:
    class HostKeyFailAdapter(FakeAdapter):
        def run_command(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise SshHostKeyUntrustedError("host key is not trusted")

    result = initializer(HostKeyFailAdapter(), tmp_path).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_SSH_HOST_KEY_UNTRUSTED"
    assert "not trusted" not in result.log
    assert "host key" in result.log


def test_real_initializer_maps_changed_ssh_host_key_to_stable_error_code(
    tmp_path: Path,
) -> None:
    class HostKeyFailAdapter(FakeAdapter):
        def run_command(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise SshHostKeyChangedError("live key changed")

    result = initializer(HostKeyFailAdapter(), tmp_path).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_SSH_HOST_KEY_CHANGED"
    assert "live key changed" not in result.log
    assert "host key" in result.log


def test_real_initializer_fails_when_matching_runtime_artifact_is_missing(tmp_path: Path) -> None:
    adapter = FakeAdapter()
    empty_artifact_dir = tmp_path / "empty-runtime-artifacts"
    empty_artifact_dir.mkdir()

    result = initializer(adapter, tmp_path, artifact_dir=empty_artifact_dir).initialize(
        node(), credential()
    )

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_RUNTIME_ARTIFACT_MISSING"
    assert "runtime artifact" in result.log
    assert "empty-runtime-artifacts" not in result.log
    assert adapter.stream_uploads == []


def test_real_initializer_fails_when_runtime_version_is_not_configured(tmp_path: Path) -> None:
    adapter = FakeAdapter()
    settings = replace(
        get_settings(),
        load_node_runtime_artifact_dir=str(write_runtime_artifact(tmp_path)),
        load_node_runtime_version=None,
        load_node_runtime_install_timeout_seconds=17,
    )

    result = RealLoadNodeInitializer(
        adapter=adapter, runner_bundle=FakeBundle(), settings=settings
    ).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_RUNTIME_ARTIFACT_MISSING"
    assert adapter.stream_uploads == []


def test_real_initializer_fails_when_runtime_checksum_sidecar_is_invalid(tmp_path: Path) -> None:
    adapter = FakeAdapter()
    artifact_dir = write_runtime_artifact(tmp_path)
    next(artifact_dir.glob("*.sha256")).write_text("not-a-digest artifact.tar.gz\n")

    result = initializer(adapter, tmp_path, artifact_dir=artifact_dir).initialize(
        node(), credential()
    )

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_RUNTIME_ARTIFACT_MISSING"
    assert adapter.stream_uploads == []


def test_real_initializer_fails_when_runtime_checksum_sidecar_digest_mismatches(
    tmp_path: Path,
) -> None:
    adapter = FakeAdapter()
    artifact_dir = write_runtime_artifact(tmp_path)
    next(artifact_dir.glob("*.sha256")).write_text(
        "0" * 64 + "  surgepilot-runtime-linux-amd64-p0-test.tar.gz\n",
        encoding="utf-8",
    )

    result = initializer(adapter, tmp_path, artifact_dir=artifact_dir).initialize(
        node(), credential()
    )

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_RUNTIME_ARTIFACT_MISSING"
    assert adapter.stream_uploads == []


def test_real_initializer_skips_upload_when_runtime_is_already_verified(tmp_path: Path) -> None:
    adapter = FakeAdapter(
        {
            "surgepilot-installed-runtime-check": RemoteCommandResult(
                exit_status=0, stdout_preview="", stderr_preview=""
            )
        }
    )

    result = initializer(adapter, tmp_path).initialize(node(), credential())

    assert result.ok is True
    assert "[info] Runtime already installed and verified." in result.log
    assert adapter.stream_uploads == []
    assert any("current/bin/bzt -h" in command for command in adapter.commands)
    assert any(
        "current/apache-jmeter-5.6.3/bin/jmeter --version" in command
        for command in adapter.commands
    )
    assert any("jpgc-casutg" in command for command in adapter.commands)


def test_real_initializer_maps_runtime_checksum_failure_to_stable_error_code(
    tmp_path: Path,
) -> None:
    adapter = FakeAdapter(
        {
            "digest.hexdigest": RemoteCommandResult(
                exit_status=1, stdout_preview="", stderr_preview="checksum mismatch"
            )
        }
    )

    result = initializer(adapter, tmp_path).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_RUNTIME_CHECKSUM_FAILED"
    assert "checksum mismatch" not in result.log
    assert adapter.uploads == []


def test_real_initializer_maps_runtime_metadata_failure_to_stable_error_code(
    tmp_path: Path,
) -> None:
    adapter = FakeAdapter(
        {
            "metadata.get('name')": RemoteCommandResult(
                exit_status=1, stdout_preview="bad metadata", stderr_preview=""
            )
        }
    )

    result = initializer(adapter, tmp_path).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_RUNTIME_METADATA_INVALID"
    assert "bad metadata" not in result.log
    assert adapter.uploads == []


def test_real_initializer_upload_failure_preserves_stable_error_code(tmp_path: Path) -> None:
    class UploadFailAdapter(FakeAdapter):
        def upload_stream(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise OSError("disk full")

    result = initializer(UploadFailAdapter(), tmp_path).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_RUNTIME_UPLOAD_FAILED"


def test_real_initializer_fails_for_unsupported_remote_architecture(tmp_path: Path) -> None:
    adapter = FakeAdapter(
        {
            "uname -m": RemoteCommandResult(
                exit_status=0, stdout_preview="ppc64le\n", stderr_preview=""
            )
        }
    )

    result = initializer(adapter, tmp_path).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_RUNTIME_ARCH_UNSUPPORTED"
    assert adapter.stream_uploads == []


def test_real_initializer_fails_for_empty_architecture_output(tmp_path: Path) -> None:
    adapter = FakeAdapter(
        {"uname -m": RemoteCommandResult(exit_status=0, stdout_preview="", stderr_preview="")}
    )

    result = initializer(adapter, tmp_path).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_RUNTIME_ARCH_UNSUPPORTED"
    assert adapter.stream_uploads == []


def test_real_initializer_fails_when_runtime_jmeter_version_mismatches(tmp_path: Path) -> None:
    adapter = FakeAdapter(
        {
            "apache-jmeter-5.6.3/bin/jmeter --version": RemoteCommandResult(
                exit_status=0,
                stdout_preview="Version 5.5\n",
                stderr_preview="",
            )
        }
    )

    result = initializer(adapter, tmp_path).initialize(node(), credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_RUNTIME_JMETER_FAILED"
    assert "JMeter version" in result.log


def test_real_initializer_rejects_unsafe_runner_home_before_remote_command(tmp_path: Path) -> None:
    adapter = FakeAdapter()
    unsafe_node = node()
    unsafe_node.runner_home = "/opt/surgepilot/runner;rm"

    result = initializer(adapter, tmp_path).initialize(unsafe_node, credential())

    assert result.ok is False
    assert result.error_code == "LOAD_NODE_INIT_FAILED"
    assert adapter.commands == []


def test_runtime_architecture_maps_arm64_variants() -> None:
    assert runtime_architecture("aarch64").artifact_arch == "linux-arm64"
    assert runtime_architecture("arm64").metadata_arch == "arm64"


def test_parse_sha256_sidecar_handles_missing_empty_and_mismatched_files(tmp_path: Path) -> None:
    missing = tmp_path / "missing.sha256"
    assert parse_sha256_sidecar(missing, expected_filename="runtime.tar.gz") is None

    sidecar = tmp_path / "runtime.sha256"
    sidecar.write_text("\n" + "a" * 64 + "  other.tar.gz\n")
    assert parse_sha256_sidecar(sidecar, expected_filename="runtime.tar.gz") is None


def test_local_runtime_artifact_digest_handles_missing_archive(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.tar.gz"
    sidecar = tmp_path / "runtime.tar.gz.sha256"
    sidecar.write_text("a" * 64 + "  runtime.tar.gz\n", encoding="utf-8")

    assert local_runtime_artifact_digest(archive, sidecar) is None
