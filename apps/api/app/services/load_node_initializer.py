from __future__ import annotations

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
UNSAFE_REMOTE_PATH_PATTERN = re.compile(r"[\s\\\x00\n\r;&|`$<>]")


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
                label="Taurus runtime",
                command="bzt --version",
                error_code="LOAD_NODE_TAURUS_MISSING",
                log=log,
            )
            self._check_command(
                target=target,
                label="JMeter runtime",
                command="jmeter --version",
                error_code="LOAD_NODE_JMETER_MISSING",
                log=log,
            )
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
