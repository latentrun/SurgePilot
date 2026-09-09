from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Literal
import posixpath
import re
import shlex
import socket

import paramiko

from app.core.config import Settings, get_settings
from app.models.load_nodes import LoadNode
from app.services.load_nodes import (
    CredentialPlaintext,
    InitResult,
    LoadNodeInitializer,
    sanitize_log,
)
from app.services.runner_bundle import RunnerBundle
from app.services.ssh_remote import (
    ParamikoSshSftpAdapter,
    RemoteCommandResult,
    SshHostKeyChangedError,
    SshHostKeyUntrustedError,
    SshSftpAdapter,
    SshTarget,
)

BUNDLE_VERSION = "p0-03"
JMETER_VERSION = "5.6.3"
TAURUS_VERSION = "1.16.50"
REQUIRED_PLUGINS = ("jpgc-casutg", "jpgc-json", "jpgc-tst", "bzm-random-csv", "jmeter-plugin-influxdb2-listener")
REQUIRED_PLUGIN_CLASSES = (
    ("jmeter-plugins-casutg", ("com/blazemeter/jmeter/threads/concurrency/ConcurrencyThreadGroup.class",)),
    ("jmeter-plugins-json", ("com/atlantbh/jmeter/plugins/jsonutils/jsonpathextractor/JSONPathExtractor.class", "com/atlantbh/jmeter/plugins/jsonutils/jsonpathassertion/JSONPathAssertion.class")),
    ("jmeter-plugins-tst", ("kg/apc/jmeter/timers/VariableThroughputTimer.class",)),
    ("jmeter-plugins-random-csv-data-set", ("com/blazemeter/jmeter/RandomCSVDataSetConfig.class",)),
    ("jmeter-plugins-influxdb2-listener", ("io/github/mderevyankoaqa/influxdb2/visualizer/InfluxDatabaseBackendListenerClient.class",)),
)
UNSAFE_REMOTE_PATH_PATTERN = re.compile(r"[\s\\\x00\n\r;&|`$<>]")


@dataclass(frozen=True)
class RuntimeArchitecture:
    artifact_arch: str
    metadata_arch: str


@dataclass(frozen=True)
class RuntimeArtifact:
    archive_path: Path
    sha256_path: Path
    sha256: str
    artifact_arch: str
    metadata_arch: str
    version: str


class RealLoadNodeInitializer(LoadNodeInitializer):
    def __init__(
        self,
        *,
        adapter: SshSftpAdapter | None = None,
        runner_bundle: RunnerBundle | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.adapter = adapter or ParamikoSshSftpAdapter()
        self.runner_bundle = runner_bundle or RunnerBundle()
        self.settings = settings or get_settings()

    def initialize(self, node: LoadNode, credential: CredentialPlaintext) -> InitResult:
        if not (
            node.ssh_host_key_algorithm
            and node.ssh_host_key_public_key
            and node.ssh_host_key_fingerprint_sha256
        ):
            return failed(
                "LOAD_NODE_SSH_HOST_KEY_UNTRUSTED", ["[error] SSH host key is untrusted."]
            )
        target = SshTarget(
            host=node.host,
            port=node.ssh_port,
            username=node.ssh_user,
            credential=credential,
            connect_timeout_seconds=self.settings.load_node_ssh_connect_timeout_seconds,
            trusted_host_key_algorithm=node.ssh_host_key_algorithm,
            trusted_host_key_public_key=node.ssh_host_key_public_key,
            trusted_host_key_fingerprint_sha256=node.ssh_host_key_fingerprint_sha256,
        )
        log: list[str] = []
        try:
            runner_home = safe_remote_path(node.runner_home)
            self._prepare_runner_home(target=target, runner_home=runner_home, log=log)
            self._check_command(
                target=target,
                label="Python runtime",
                command="python3 --version",
                error_code="LOAD_NODE_PYTHON_MISSING",
                log=log,
            )
            self._check_command(
                target=target,
                label="Java runtime",
                command="java -version",
                error_code="LOAD_NODE_JAVA_MISSING",
                log=log,
            )
            self._check_command(
                target=target,
                label="Tar runtime",
                command="tar --version",
                error_code="LOAD_NODE_TAR_MISSING",
                log=log,
            )
            arch_result = self._check_command(
                target=target,
                label="Load Node architecture",
                command="uname -m",
                error_code="LOAD_NODE_RUNTIME_ARCH_UNSUPPORTED",
                log=log,
            )
            arch_lines = combined_output(arch_result).splitlines()
            runtime_arch = runtime_architecture(arch_lines[0] if arch_lines else "")
            if runtime_arch is None:
                log.append("[error] Load Node architecture is not supported by P0 runtime artifacts.")
                return failed("LOAD_NODE_RUNTIME_ARCH_UNSUPPORTED", log)
            artifact = self._runtime_artifact(runtime_arch)
            if artifact is None:
                log.append("[error] Matching runtime artifact or checksum sidecar is unavailable.")
                return failed("LOAD_NODE_RUNTIME_ARTIFACT_MISSING", log)
            log.append(f"[info] Runtime artifact selected for {artifact.artifact_arch} version {artifact.version}.")
            self._install_runtime(target=target, runner_home=runner_home, artifact=artifact, log=log)
            self._upload_runner(target=target, runner_home=runner_home, log=log)
            runner_version = self._probe_runner(target=target, runner_home=runner_home, log=log)
        except CommandCheckFailure as exc:
            return failed(exc.error_code, log)
        except paramiko.AuthenticationException:
            log.append("[error] SSH authentication failed.")
            return failed("LOAD_NODE_SSH_AUTH_FAILED", log)
        except SshHostKeyUntrustedError:
            log.append("[error] SSH host key is untrusted.")
            return failed("LOAD_NODE_SSH_HOST_KEY_UNTRUSTED", log)
        except SshHostKeyChangedError:
            log.append("[error] SSH host key changed.")
            return failed("LOAD_NODE_SSH_HOST_KEY_CHANGED", log)
        except (TimeoutError, socket.timeout):
            log.append("[error] SSH operation timed out.")
            return failed("LOAD_NODE_SSH_TIMEOUT", log)
        except (OSError, paramiko.SSHException):
            log.append("[error] SSH host was unreachable.")
            return failed("LOAD_NODE_SSH_UNREACHABLE", log)
        except Exception:
            log.append("[error] Unexpected initialization failure.")
            return failed("LOAD_NODE_INIT_FAILED", log)

        log.append("[info] Initialization succeeded.")
        return InitResult(
            ok=True,
            log=sanitize_log("\n".join(log)),
            message="Initialization succeeded.",
            runner_version=runner_version,
            bundle_version=BUNDLE_VERSION,
        )

    def _prepare_runner_home(self, *, target: SshTarget, runner_home: str, log: list[str]) -> None:
        paths = [
            runner_home,
            posixpath.join(runner_home, "bin"),
            posixpath.join(runner_home, "runs"),
            posixpath.join(runner_home, "logs"),
            posixpath.join(runner_home, "tmp"),
            posixpath.join(runner_home, "runtimes"),
        ]
        marker = posixpath.join(runner_home, ".surgepilot-node")
        quoted_paths = " ".join(shlex.quote(path) for path in paths)
        command = (
            "set -eu; umask 077; "
            f"for path in {quoted_paths}; do "
            'if [ -L "$path" ]; then exit 1; fi; '
            "done; "
            f"mkdir -p {quoted_paths}; "
            f"for path in {quoted_paths}; do "
            '[ -d "$path" ] && [ ! -L "$path" ]; '
            "done; "
            f"touch {shlex.quote(marker)}; "
            f"chmod 600 {shlex.quote(marker)}; "
            f"test -w {shlex.quote(runner_home)}"
        )
        self._check_command(
            target=target,
            label="Runner home",
            command=command,
            error_code="LOAD_NODE_RUNNER_HOME_UNWRITABLE",
            log=log,
        )
        log.append("[info] SSH connection verified.")
        log.append(f"[info] Runner home prepared at {runner_home}.")

    def _runtime_artifact(self, arch: RuntimeArchitecture) -> RuntimeArtifact | None:
        version = (self.settings.load_node_runtime_version or "").strip()
        if not version:
            return None
        root = Path(self.settings.load_node_runtime_artifact_dir)
        archive = root / f"surgepilot-runtime-{arch.artifact_arch}-{version}.tar.gz"
        sidecar = root / f"{archive.name}.sha256"
        if not archive.is_file() or not sidecar.is_file():
            return None
        digest = local_runtime_artifact_digest(archive, sidecar)
        if digest is None:
            return None
        return RuntimeArtifact(archive, sidecar, digest, arch.artifact_arch, arch.metadata_arch, version)

    def _install_runtime(self, *, target: SshTarget, runner_home: str, artifact: RuntimeArtifact, log: list[str]) -> None:
        if self._runtime_is_installed(target=target, runner_home=runner_home, artifact=artifact):
            log.append("[info] Runtime already installed and verified.")
            return
        remote_archive = safe_join(runner_home, f"tmp/{artifact.archive_path.name}")
        try:
            with artifact.archive_path.open("rb") as source:
                self.adapter.upload_stream(target, remote_path=remote_archive, source=source, mode=0o600)
        except Exception as exc:
            raise CommandCheckFailure("LOAD_NODE_RUNTIME_UPLOAD_FAILED") from exc
        log.append("[info] Runtime artifact uploaded.")
        self._check_command(target=target, label="Runtime checksum", command=runtime_checksum_command(remote_archive, artifact.sha256), error_code="LOAD_NODE_RUNTIME_CHECKSUM_FAILED", log=log, timeout_seconds=self.settings.load_node_runtime_install_timeout_seconds)
        self._check_command(target=target, label="Runtime safe extraction", command=runtime_extract_command(archive_path=remote_archive, runner_home=runner_home, version=artifact.version), error_code="LOAD_NODE_RUNTIME_EXTRACT_FAILED", log=log, timeout_seconds=self.settings.load_node_runtime_install_timeout_seconds)
        tmp_runtime = safe_join(runner_home, f"tmp/runtime-extract-{artifact.version}")
        self._validate_runtime(target=target, runtime_path=tmp_runtime, artifact=artifact, log=log)
        self._check_command(target=target, label="Runtime activation", command=runtime_activation_command(runner_home=runner_home, tmp_runtime=tmp_runtime, version=artifact.version), error_code="LOAD_NODE_RUNTIME_ACTIVATION_FAILED", log=log, timeout_seconds=self.settings.load_node_runtime_install_timeout_seconds)

    def _runtime_is_installed(self, *, target: SshTarget, runner_home: str, artifact: RuntimeArtifact) -> bool:
        current = safe_join(runner_home, "current")
        result = self.adapter.run_command(target, command=installed_runtime_check_command(runner_home=runner_home, version=artifact.version), timeout_seconds=self.settings.load_node_runtime_install_timeout_seconds, output_limit_bytes=4096)
        if not result.ok:
            return False
        result = self.adapter.run_command(target, command=runtime_critical_files_command(current), timeout_seconds=self.settings.load_node_runtime_install_timeout_seconds, output_limit_bytes=4096)
        if not result.ok:
            return False
        checks = [runtime_metadata_command(runtime_path=current, version=artifact.version, metadata_arch=artifact.metadata_arch), f"{shlex.quote(safe_join(current, 'bin/bzt'))} -h", f"{shlex.quote(safe_join(current, f'apache-jmeter-{JMETER_VERSION}/bin/jmeter'))} --version", runtime_plugin_command(current)]
        return all(self.adapter.run_command(target, command=command, timeout_seconds=self.settings.load_node_runtime_install_timeout_seconds, output_limit_bytes=4096).ok for command in checks)

    def _validate_runtime(self, *, target: SshTarget, runtime_path: str, artifact: RuntimeArtifact, log: list[str]) -> None:
        self._check_command(target=target, label="Runtime metadata", command=runtime_metadata_command(runtime_path=runtime_path, version=artifact.version, metadata_arch=artifact.metadata_arch), error_code="LOAD_NODE_RUNTIME_METADATA_INVALID", log=log, timeout_seconds=self.settings.load_node_runtime_install_timeout_seconds)
        self._check_command(target=target, label="Runtime critical files", command=runtime_critical_files_command(runtime_path), error_code="LOAD_NODE_RUNTIME_METADATA_INVALID", log=log, timeout_seconds=self.settings.load_node_runtime_install_timeout_seconds)
        self._check_command(target=target, label="Runtime Taurus", command=f"{shlex.quote(safe_join(runtime_path, 'bin/bzt'))} -h", error_code="LOAD_NODE_RUNTIME_BZT_FAILED", log=log, timeout_seconds=self.settings.load_node_runtime_install_timeout_seconds)
        jmeter_result = self._check_command(target=target, label="Runtime JMeter", command=f"{shlex.quote(safe_join(runtime_path, f'apache-jmeter-{JMETER_VERSION}/bin/jmeter'))} --version", error_code="LOAD_NODE_RUNTIME_JMETER_FAILED", log=log, timeout_seconds=self.settings.load_node_runtime_install_timeout_seconds)
        if JMETER_VERSION not in combined_output(jmeter_result):
            log.append("[error] Runtime JMeter version did not match expected version.")
            raise CommandCheckFailure("LOAD_NODE_RUNTIME_JMETER_FAILED")
        self._check_command(target=target, label="Runtime plugin", command=runtime_plugin_command(runtime_path), error_code="LOAD_NODE_RUNTIME_PLUGIN_MISSING", log=log, timeout_seconds=self.settings.load_node_runtime_install_timeout_seconds)

    def _check_command(
        self,
        *,
        target: SshTarget,
        label: str,
        command: str,
        error_code: str,
        log: list[str],
        timeout_seconds: int | None = None,
    ) -> RemoteCommandResult:
        result = self.adapter.run_command(
            target,
            command=command,
            timeout_seconds=timeout_seconds or self.settings.load_node_init_command_timeout_seconds,
            output_limit_bytes=4096,
        )
        if result.timed_out:
            log.append(f"[error] {label} check timed out.")
            raise CommandCheckFailure("LOAD_NODE_SSH_TIMEOUT")
        if not result.ok:
            log.append(f"[error] {label} check failed.")
            raise CommandCheckFailure(error_code)
        log.append(f"[info] {label} check passed.")
        return result

    def _upload_runner(self, *, target: SshTarget, runner_home: str, log: list[str]) -> None:
        for file in self.runner_bundle.files():
            remote_path = safe_join(runner_home, file.relative_path)
            self.adapter.upload_bytes(
                target,
                remote_path=remote_path,
                content=file.content,
                mode=file.mode,
            )
        log.append("[info] Runner bundle uploaded.")

    def _probe_runner(self, *, target: SshTarget, runner_home: str, log: list[str]) -> str:
        runner_path = safe_join(runner_home, "runner.py")
        result = self._check_command(
            target=target,
            label="Runner bundle",
            command=f"python3 {shlex.quote(runner_path)} version",
            error_code="LOAD_NODE_INIT_FAILED",
            log=log,
        )
        return parse_runner_version(result.stdout_preview)


class CommandCheckFailure(RuntimeError):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


def failed(error_code: str, log: list[str]) -> InitResult:
    return InitResult(
        ok=False,
        log=sanitize_log("\n".join(log)),
        error_code=error_code,
        message="Initialization failed.",
    )


def combined_output(result: RemoteCommandResult) -> str:
    return "\n".join(
        part.strip() for part in [result.stdout_preview, result.stderr_preview] if part.strip()
    )


def safe_remote_path(value: str) -> str:
    if (
        not value
        or not value.startswith("/")
        or value == "/"
        or "\\" in value
        or "\x00" in value
        or "\n" in value
        or "\r" in value
        or "//" in value
        or UNSAFE_REMOTE_PATH_PATTERN.search(value)
        or any(part in {"", ".", ".."} for part in value.split("/")[1:])
    ):
        raise ValueError("Unsafe remote path.")
    return value.rstrip("/")


def safe_join(root: str, relative_path: str) -> str:
    if (
        not relative_path
        or relative_path.startswith("/")
        or "\\" in relative_path
        or "\x00" in relative_path
        or any(part in {"", ".", ".."} for part in relative_path.split("/"))
    ):
        raise ValueError("Unsafe bundle path.")
    joined = posixpath.normpath(posixpath.join(root, relative_path))
    if not joined.startswith(root.rstrip("/") + "/"):
        raise ValueError("Unsafe bundle path.")
    return joined


def parse_runner_version(output: str) -> str:
    line = output.strip().splitlines()[0] if output.strip() else ""
    parts = line.split()
    return parts[-1] if parts else "unknown"


def runtime_architecture(uname_machine: str) -> RuntimeArchitecture | None:
    normalized = uname_machine.strip().lower()
    if normalized in {"x86_64", "amd64"}:
        return RuntimeArchitecture("linux-amd64", "amd64")
    if normalized in {"aarch64", "arm64"}:
        return RuntimeArchitecture("linux-arm64", "arm64")
    return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_sha256_sidecar(path: Path, *, expected_filename: str) -> str | None:
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return None
    for line in lines:
        parts = line.strip().split()
        if parts and re.fullmatch(r"[a-f0-9]{64}", parts[0].lower()) and parts[-1].lstrip("*") == expected_filename:
            return parts[0].lower()
    return None


def local_runtime_artifact_digest(archive: Path, sidecar: Path) -> str | None:
    digest = parse_sha256_sidecar(sidecar, expected_filename=archive.name)
    if digest is None:
        return None
    try:
        return digest if sha256_file(archive) == digest else None
    except OSError:
        return None


def load_node_runtime_artifact_available(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    version = (settings.load_node_runtime_version or "").strip()
    if not version:
        return False
    root = Path(settings.load_node_runtime_artifact_dir)
    return any(local_runtime_artifact_digest(root / f"surgepilot-runtime-{arch}-{version}.tar.gz", root / f"surgepilot-runtime-{arch}-{version}.tar.gz.sha256") is not None for arch in ("linux-amd64", "linux-arm64"))


def load_node_runtime_status(settings: Settings | None = None) -> Literal["ready", "not_configured", "artifact_missing"]:
    settings = settings or get_settings()
    if not (settings.load_node_runtime_version or "").strip():
        return "not_configured"
    return "ready" if load_node_runtime_artifact_available(settings) else "artifact_missing"


def runtime_checksum_command(remote_archive: str, expected_sha256: str) -> str:
    return "python3 - " + f"{shlex.quote(remote_archive)} {shlex.quote(expected_sha256)} <<'PY'\n" + "import hashlib, sys\npath, expected = sys.argv[1], sys.argv[2]\ndigest = hashlib.sha256()\nwith open(path, 'rb') as handle:\n    for chunk in iter(lambda: handle.read(1024 * 1024), b''):\n        digest.update(chunk)\nif digest.hexdigest().lower() != expected.lower():\n    raise SystemExit(1)\nPY"


def installed_runtime_check_command(*, runner_home: str, version: str) -> str:
    current, runtimes = safe_join(runner_home, "current"), safe_join(runner_home, "runtimes")
    return "set -eu; python3 - " + f"{shlex.quote(current)} {shlex.quote(runtimes)} {shlex.quote(version)} <<'PY'\n" + "import os, sys\ncurrent, runtimes, version = sys.argv[1:]\nif not os.path.islink(current): raise SystemExit(1)\ntarget = os.path.abspath(os.path.join(os.path.dirname(current), os.readlink(current)))\nif os.path.commonpath([target, os.path.abspath(runtimes)]) != os.path.abspath(runtimes) or not os.path.basename(target).startswith(version + '-') or not os.path.isdir(target): raise SystemExit(1)\nPY\n"


def runtime_extract_command(*, archive_path: str, runner_home: str, version: str) -> str:
    destination = safe_join(runner_home, f"tmp/runtime-extract-{version}")
    return "python3 - " + f"{shlex.quote(archive_path)} {shlex.quote(destination)} {shlex.quote(runner_home)} <<'PY'\n" + "import os, shutil, sys, tarfile\narchive, destination, runner_home = sys.argv[1:]\nroot, runner_root = os.path.realpath(destination), os.path.realpath(runner_home)\nif root == runner_root or not root.startswith(runner_root + os.sep): raise SystemExit(1)\nos.makedirs(os.path.dirname(root), exist_ok=True); shutil.rmtree(root, ignore_errors=True); os.makedirs(root, mode=0o700)\ndef reject(member):\n    name = member.name; parts = name.split('/')\n    if name.startswith('/') or '\\\\' in name or any(p in ('', '.', '..') for p in parts): raise SystemExit(1)\n    target = os.path.realpath(os.path.join(root, name))\n    if target != root and not target.startswith(root + os.sep): raise SystemExit(1)\n    if not (member.isfile() or member.isdir() or member.issym()): raise SystemExit(1)\n    if member.issym() and (member.linkname.startswith('/') or '\\\\' in member.linkname): raise SystemExit(1)\nwith tarfile.open(archive, 'r:gz') as tar:\n    members = tar.getmembers()\n    for member in members: reject(member)\n    tar.extractall(root, members)\nif not os.path.isfile(os.path.join(root, 'metadata.json')): raise SystemExit(1)\nPY"


def runtime_metadata_command(*, runtime_path: str, version: str, metadata_arch: str) -> str:
    return "python3 - " + f"{shlex.quote(runtime_path)} {shlex.quote(version)} {shlex.quote(metadata_arch)} <<'PY'\n" + f"import json, os, re, sys\nruntime, version, arch = sys.argv[1:]\nwith open(os.path.join(runtime, 'metadata.json'), encoding='utf-8') as handle: metadata = json.load(handle)\nchecks = [metadata.get('name') == 'surgepilot-runtime', metadata.get('version') == version, metadata.get('platform') == 'linux', metadata.get('arch') == arch, metadata.get('taurus') == {TAURUS_VERSION!r}, metadata.get('jmeter') == {JMETER_VERSION!r}, re.fullmatch(r'3\\.(11|12)(\\.\\d+)?', str(metadata.get('python') or '')) is not None, metadata.get('python') != 'system-e2e', metadata.get('plugins') == list({REQUIRED_PLUGINS!r})]\nif not all(checks): raise SystemExit(1)\nPY"


def runtime_critical_files_command(runtime_path: str) -> str:
    return "python3 - " + shlex.quote(runtime_path) + " <<'PY'\nimport os, subprocess, sys\nruntime = sys.argv[1]\npython_path = next((os.path.join(runtime, p) for p in ('python/bin/python3', 'python/bin/python') if os.path.isfile(os.path.join(runtime, p)) and os.access(os.path.join(runtime, p), os.X_OK)), None)\nif python_path is None or not os.path.isfile(os.path.join(runtime, 'bin/bzt')) or not os.path.isfile(os.path.join(runtime, 'apache-jmeter-5.6.3/bin/jmeter')) or not os.path.isfile(os.path.join(runtime, 'apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper')) or not os.path.isfile(os.path.join(runtime, 'python/lib/surgepilot_runner/jmeter_wrapper.py')): raise SystemExit(1)\nprobe = subprocess.run([python_path, '-c', 'import sys; print(sys.executable)'], text=True, stdout=subprocess.PIPE)\nif probe.returncode or not os.path.realpath(probe.stdout.strip()).startswith(os.path.realpath(os.path.join(runtime, 'python')) + os.sep): raise SystemExit(1)\nPY"


def runtime_plugin_command(runtime_path: str) -> str:
    plugin_dir = safe_join(runtime_path, f"apache-jmeter-{JMETER_VERSION}/lib/ext")
    return "python3 - " + shlex.quote(plugin_dir) + " <<'PY'\nimport os, sys, zipfile\nplugin_dir = sys.argv[1]\nrequired = " + repr(REQUIRED_PLUGIN_CLASSES) + "\njars = [name for name in os.listdir(plugin_dir) if name.endswith('.jar')]\nfor prefix, classes in required:\n    matches = [name for name in jars if name.startswith(prefix + '-') ]\n    if len(matches) != 1: raise SystemExit(1)\n    with zipfile.ZipFile(os.path.join(plugin_dir, matches[0])) as jar:\n        if not all(item in jar.namelist() for item in classes): raise SystemExit(1)\nPY"


def runtime_activation_command(*, runner_home: str, tmp_runtime: str, version: str) -> str:
    runtimes, current = safe_join(runner_home, "runtimes"), safe_join(runner_home, "current")
    return "set -eu; python3 - " + f"{shlex.quote(runner_home)} {shlex.quote(runtimes)} {shlex.quote(tmp_runtime)} {shlex.quote(current)} {shlex.quote(version)} <<'PY'\n" + "import os, shutil, sys, uuid\nrunner_home, runtimes, tmp_runtime, current, version = sys.argv[1:]\ntoken = uuid.uuid4().hex[:12]; target = os.path.join(runtimes, f'{version}-{token}'); current_tmp = os.path.join(runner_home, f'.current.{token}.tmp')\nos.replace(tmp_runtime, target)\ntry:\n    if os.path.lexists(current) and not os.path.islink(current): raise SystemExit(1)\n    os.symlink(target, current_tmp); os.replace(current_tmp, current)\nfinally:\n    if os.path.lexists(current_tmp): os.unlink(current_tmp)\nif not os.path.islink(current) or os.readlink(current) != target: raise SystemExit(1)\nPY\n"
