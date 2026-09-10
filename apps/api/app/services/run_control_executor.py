from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import posixpath
import shlex

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.models.load_nodes import LoadNode
from app.services.load_nodes import (
    CredentialPlaintext,
    credential_for_node,
    decrypt_credential,
    sanitize_log,
)
from app.services.execution_bundles import (
    ExecutionBundleFile,
    build_debug_scenario_execution_bundle,
    build_test_plan_execution_bundle,
)
from app.services.load_node_initializer import safe_join
from app.services.monitoring import build_monitoring_properties
from app.services.runner_bundle import RunnerBundle
from app.services.runs import (
    RunControlCommand,
    RunControlExecutionResult,
    RunControlExecutor,
    sign_runner_node_token,
)
from app.services.ssh_remote import (
    ParamikoSshSftpAdapter,
    SshHostKeyChangedError,
    SshHostKeyUntrustedError,
    SshSftpAdapter,
    SshTarget,
)


CredentialResolver = Callable[[str], CredentialPlaintext]


def _monitoring_token_from_worker_env() -> str | None:
    value = os.environ.get("SURGEPILOT_MONITORING_INFLUXDB_TOKEN")
    if value:
        return value
    file_path = os.environ.get("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE")
    if not file_path:
        return None
    try:
        content = Path(file_path).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return content or None


@dataclass(frozen=True)
class RemoteExecutorOptions:
    command_timeout_seconds: int
    output_limit_bytes: int = 4096


class RemoteRunControlExecutor(RunControlExecutor):
    """Execute claimed run-control requests over the P0-03 SSH/SFTP adapter.

    ``start`` uploads the runner bundle and a transient env file, then invokes
    ``python3 <runnerHome>/runner.py start --run-id <runId>`` (with ``--fake``
    for protocol-smoke Runs). ``stop`` and ``force_kill`` invoke the matching
    Runner CLI commands. Secrets travel only in the 0600 env file, which the
    remote shell deletes through an EXIT trap; failure paths attempt
    compensating deletion and quarantine the node when the outcome is unknown.
    """

    def __init__(
        self,
        *,
        session_factory: sessionmaker | None = None,
        credential_resolver: CredentialResolver | None = None,
        adapter: SshSftpAdapter | None = None,
        runner_bundle: RunnerBundle | None = None,
        settings: Settings | None = None,
        options: RemoteExecutorOptions | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.credential_resolver = credential_resolver
        self.adapter = adapter or ParamikoSshSftpAdapter()
        self.runner_bundle = runner_bundle or RunnerBundle()
        self.settings = settings or get_settings()
        self.options = options or RemoteExecutorOptions(
            command_timeout_seconds=self.settings.runner_force_kill_ssh_timeout_seconds
        )

    def execute(self, command: RunControlCommand) -> RunControlExecutionResult:
        execution_bundle_files: list[ExecutionBundleFile] | None = None
        if command.action == "start" and command.source_type in {"debug_scenario", "test_plan"}:
            try:
                execution_bundle_files = self._build_execution_bundle(command)
            except Exception:
                return RunControlExecutionResult(
                    ok=False,
                    error_code="RUN_BUNDLE_BUILD_FAILED",
                    message="Run execution bundle could not be prepared.",
                    quarantine_node=False,
                )
        target: SshTarget | None = None
        env_path: str | None = None
        start_invoked = False
        cleanup_required = False
        try:
            credential = self._credential_for(command.node_id)
            target = SshTarget(
                host=command.host,
                port=command.ssh_port,
                username=command.ssh_user,
                credential=credential,
                connect_timeout_seconds=self.settings.load_node_ssh_connect_timeout_seconds,
                trusted_host_key_algorithm=command.trusted_host_key_algorithm,
                trusted_host_key_public_key=command.trusted_host_key_public_key,
                trusted_host_key_fingerprint_sha256=command.trusted_host_key_fingerprint_sha256,
            )
            self._upload_runner(target=target, runner_home=command.runner_home)
            self._upload_execution_bundle(
                target=target, command=command, files=execution_bundle_files
            )
            env_path = self._remote_env_path(command)
            cleanup_required = command.action == "start"
            self.adapter.upload_text(
                target,
                remote_path=env_path,
                content=self._env_file(command),
                mode=0o600,
            )
            self._upload_monitoring_properties_if_needed(target=target, command=command)
            remote_command = self._shell_command(command=command, env_path=env_path)
            start_invoked = command.action == "start"
            result = self.adapter.run_command(
                target,
                command=remote_command,
                timeout_seconds=self.options.command_timeout_seconds,
                output_limit_bytes=self.options.output_limit_bytes,
            )
        except AppError as exc:
            return RunControlExecutionResult(
                ok=False,
                error_code=exc.code,
                message=exc.message,
                quarantine_node=self._failure_requires_quarantine(
                    target=target,
                    command=command,
                    env_path=env_path,
                    cleanup_required=cleanup_required,
                ),
            )
        except SshHostKeyUntrustedError:
            return RunControlExecutionResult(
                ok=False,
                error_code="RUN_CONTROL_SSH_HOST_KEY_UNTRUSTED",
                message="Run control SSH host key verification failed.",
                quarantine_node=self._failure_requires_quarantine(
                    target=target,
                    command=command,
                    env_path=env_path,
                    cleanup_required=cleanup_required,
                ),
            )
        except SshHostKeyChangedError:
            return RunControlExecutionResult(
                ok=False,
                error_code="RUN_CONTROL_SSH_HOST_KEY_CHANGED",
                message="Run control SSH host key verification failed.",
                quarantine_node=self._failure_requires_quarantine(
                    target=target,
                    command=command,
                    env_path=env_path,
                    cleanup_required=cleanup_required,
                ),
            )
        except Exception:
            return RunControlExecutionResult(
                ok=False,
                error_code="RUN_CONTROL_EXECUTION_FAILED",
                message="Run control execution failed.",
                quarantine_node=(
                    False
                    if start_invoked
                    else self._failure_requires_quarantine(
                        target=target,
                        command=command,
                        env_path=env_path,
                        cleanup_required=cleanup_required,
                    )
                ),
                cleanup_required=start_invoked,
            )
        finally:
            self._close_execution_bundle(execution_bundle_files)
        if result.ok:
            return RunControlExecutionResult(ok=True)
        return RunControlExecutionResult(
            ok=False,
            error_code=(
                "RUN_CONTROL_TIMEOUT" if result.timed_out else "RUN_CONTROL_REMOTE_FAILED"
            ),
            message=(
                "Run control command timed out."
                if result.timed_out
                else "Run control command failed."
            ),
            stderr_preview=sanitize_log(
                result.stderr_preview, max_bytes=self.options.output_limit_bytes
            ),
            timed_out=result.timed_out,
            quarantine_node=command.action != "start",
            cleanup_required=command.action == "start",
        )

    def _credential_for(self, node_id: str) -> CredentialPlaintext:
        if self.credential_resolver is not None:
            return self.credential_resolver(node_id)
        if self.session_factory is None:
            raise RuntimeError("Run control executor requires a credential resolver.")
        with self.session_factory() as session:
            return self._credential_from_session(session, node_id=node_id)

    def _credential_from_session(self, session: Session, *, node_id: str) -> CredentialPlaintext:
        node = session.get(LoadNode, node_id)
        if node is None:
            raise RuntimeError("Run control target node was not found.")
        return decrypt_credential(credential_for_node(session, node=node))

    def _upload_runner(self, *, target: SshTarget, runner_home: str) -> None:
        for file in self.runner_bundle.files():
            remote_path = posixpath.join(runner_home, file.relative_path)
            self.adapter.upload_bytes(
                target, remote_path=remote_path, content=file.content, mode=file.mode
            )

    def _build_execution_bundle(self, command: RunControlCommand) -> list[ExecutionBundleFile]:
        if self.session_factory is None:
            raise RuntimeError("Run execution bundle requires a session factory.")
        with self.session_factory() as session:
            if command.source_type == "test_plan":
                return build_test_plan_execution_bundle(
                    session, run_id=command.run_id, runner_home=command.runner_home, settings=self.settings
                )
            return build_debug_scenario_execution_bundle(
                session, run_id=command.run_id, runner_home=command.runner_home, settings=self.settings
            )

    def _upload_execution_bundle(
        self, *, target: SshTarget, command: RunControlCommand,
        files: list[ExecutionBundleFile] | None,
    ) -> None:
        if not files:
            return
        bundle_root = posixpath.join(command.runner_home, "runs", command.run_id, "bundle")
        for file in files:
            remote_path = safe_join(bundle_root, file.relative_path)
            if file.content is not None:
                self.adapter.upload_bytes(target, remote_path=remote_path, content=file.content, mode=file.mode)
            elif file.stream is not None:
                self.adapter.upload_stream(target, remote_path=remote_path, source=file.stream, mode=file.mode)

    def _close_execution_bundle(self, files: list[ExecutionBundleFile] | None) -> None:
        for file in files or []:
            if file.stream is not None:
                file.stream.close()

    def _upload_monitoring_properties_if_needed(
        self, *, target: SshTarget, command: RunControlCommand
    ) -> None:
        if command.action != "start" or self.session_factory is None:
            return
        with self.session_factory() as session:
            content = build_monitoring_properties(
                session,
                run_id=command.run_id,
                node_id=command.node_id,
                monitoring_token=_monitoring_token_from_worker_env(),
                settings=self.settings,
            )
        if content is None:
            return
        secrets_dir = posixpath.join(command.runner_home, "runs", command.run_id, "secrets")
        mkdir_result = self.adapter.run_command(
            target,
            command=f"mkdir -p {shlex.quote(secrets_dir)} && chmod 700 {shlex.quote(secrets_dir)}",
            timeout_seconds=self.settings.load_node_ssh_connect_timeout_seconds,
            output_limit_bytes=512,
        )
        if not mkdir_result.ok:
            raise RuntimeError("Monitoring secret directory could not be prepared.")
        self.adapter.upload_text(
            target,
            remote_path=posixpath.join(secrets_dir, "monitoring.properties"),
            content=content,
            mode=0o600,
        )

    def _failure_requires_quarantine(
        self,
        *,
        target: SshTarget | None,
        command: RunControlCommand,
        env_path: str | None,
        cleanup_required: bool,
    ) -> bool:
        if not cleanup_required or target is None or env_path is None:
            return False
        monitoring_path = posixpath.join(
            command.runner_home,
            "runs",
            command.run_id,
            "secrets",
            "monitoring.properties",
        )
        secrets_dir = posixpath.dirname(monitoring_path)
        try:
            result = self.adapter.run_command(
                target,
                command=(
                    f"rm -f {shlex.quote(env_path)} {shlex.quote(monitoring_path)} && "
                    f"rmdir {shlex.quote(secrets_dir)} && "
                    f"test ! -e {shlex.quote(monitoring_path)}"
                ),
                timeout_seconds=self.options.command_timeout_seconds,
                output_limit_bytes=512,
            )
        except Exception:
            return True
        return not result.ok

    def _remote_env_path(self, command: RunControlCommand) -> str:
        return posixpath.join(command.runner_home, "runs", command.run_id, ".surgepilot.env")

    def _env_file(self, command: RunControlCommand) -> str:
        runner_token = self.settings.runner_internal_token or ""
        if runner_token:
            runner_token = sign_runner_node_token(command.node_id, secret=runner_token)
        values = {
            "RUNNER_INTERNAL_TOKEN": runner_token,
            "SURGEPILOT_NODE_ID": command.node_id,
            "RUNNER_HOME": command.runner_home,
        }
        if command.action == "start":
            api_base_url = self._api_base_url()
            if api_base_url is not None:
                values = {"SURGEPILOT_API_BASE_URL": api_base_url, **values}
        return "".join(f"{name}={shlex.quote(value)}\n" for name, value in values.items())

    def _api_base_url(self) -> str | None:
        value = (self.settings.surgepilot_node_api_base_url or "").strip().rstrip("/")
        return value or None

    def _shell_command(self, *, command: RunControlCommand, env_path: str) -> str:
        runner_command = shlex.join(command.argv)
        quoted_env_path = shlex.quote(env_path)
        cleanup_trap = shlex.quote(f"rm -f {quoted_env_path}")
        return (
            "set -eu; "
            f"mkdir -p {shlex.quote(posixpath.dirname(env_path))} && "
            f"chmod 700 {shlex.quote(posixpath.dirname(env_path))} && "
            f"trap {cleanup_trap} EXIT && "
            f"set -a && . {quoted_env_path} && set +a && "
            f"rm -f {quoted_env_path} && "
            f"cd {shlex.quote(command.runner_home)} && "
            f"exec {runner_command}"
        )
