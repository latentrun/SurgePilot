from __future__ import annotations

from dataclasses import replace
import os
import shlex
import pytest


from app.core.config import get_settings
from app.core.ids import new_ulid
from app.services.load_nodes import CredentialPlaintext
from app.services.run_control_executor import RemoteExecutorOptions, RemoteRunControlExecutor
from app.services.runs import RunControlCommand
from app.services.ssh_remote import ParamikoSshSftpAdapter, SshTarget, scan_ssh_host_key

pytestmark = pytest.mark.skipif(
    os.environ.get("SURGEPILOT_SSH_E2E") != "1",
    reason="near-real SSH/SFTP runner smoke is opt-in",
)

RUNNER_HOME = "/opt/surgepilot/runner"


def ssh_env() -> tuple[str, int, str, str]:
    return (
        os.environ.get("SURGEPILOT_SSH_E2E_HOST", "127.0.0.1"),
        int(os.environ.get("SURGEPILOT_SSH_E2E_PORT", "22322")),
        os.environ.get("SURGEPILOT_SSH_E2E_USER", "surgepilot"),
        os.environ.get("SURGEPILOT_SSH_E2E_PASSWORD", "surgepilot"),
    )


def credential() -> CredentialPlaintext:
    return CredentialPlaintext(auth_type="password", password=ssh_env()[3])


def target() -> SshTarget:
    host, port, user, _password = ssh_env()
    scanned = scan_ssh_host_key(host=host, port=port, timeout_seconds=5)
    return SshTarget(
        host=host,
        port=port,
        username=user,
        credential=credential(),
        connect_timeout_seconds=5,
        trusted_host_key_algorithm=scanned.algorithm,
        trusted_host_key_public_key=scanned.public_key,
        trusted_host_key_fingerprint_sha256=scanned.fingerprint_sha256,
    )


def command(run_id: str, action: str) -> RunControlCommand:
    ssh_target = target()
    runner_action = "kill" if action == "force_kill" else action
    runner_shell = (
        f"PATH={shlex.quote(RUNNER_HOME)}/bin:$PATH "
        f"python3 {shlex.quote(RUNNER_HOME)}/runner.py {runner_action} --run-id {run_id}"
    )
    return RunControlCommand(
        request_id=new_ulid(),
        action=action,
        run_id=run_id,
        node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        reason="ssh_e2e",
        source_type="protocol_smoke",
        host=ssh_target.host,
        ssh_port=ssh_target.port,
        ssh_user=ssh_target.username,
        runner_home=RUNNER_HOME,
        trusted_host_key_algorithm=ssh_target.trusted_host_key_algorithm,
        trusted_host_key_public_key=ssh_target.trusted_host_key_public_key,
        trusted_host_key_fingerprint_sha256=ssh_target.trusted_host_key_fingerprint_sha256,
        argv=("bash", "-lc", runner_shell),
    )


def prepare_fake_workload(adapter: ParamikoSshSftpAdapter, run_id: str) -> None:
    adapter.upload_text(
        target(),
        remote_path=f"{RUNNER_HOME}/current/bin/bzt",
        content="#!/bin/sh\ntrap 'exit 143' TERM INT\nsleep 60\n",
        mode=0o755,
    )
    adapter.upload_text(
        target(),
        remote_path=f"{RUNNER_HOME}/runs/{run_id}/bundle/surgepilot.yml",
        content="execution: []\n",
        mode=0o644,
    )


def process_is_stopped_command(run_id: str) -> str:
    pidfile = f"{RUNNER_HOME}/runs/{run_id}/workload.pid"
    return (
        f"test ! -f {pidfile} && exit 0; "
        f'pgid=$(python3 -c \'import json; print(json.load(open("{pidfile}"))["pid"])\'); '
        "if kill -0 -$pgid 2>/dev/null; then exit 1; else exit 0; fi"
    )


def assert_api_base_url_reachable(
    adapter: ParamikoSshSftpAdapter, ssh_target: SshTarget, api_base_url: str
) -> None:
    probe = shlex.join(
        (
            "python3",
            "-c",
            (
                "import urllib.request; "
                f"urllib.request.urlopen({api_base_url + '/api/healthz'!r}, timeout=3).read()"
            ),
        )
    )
    result = adapter.run_command(ssh_target, command=probe, timeout_seconds=5)
    assert result.ok, result.stderr_preview or result.stdout_preview


def node_api_base_url(adapter: ParamikoSshSftpAdapter, ssh_target: SshTarget, api_port: int) -> str:
    resolve = shlex.join(
        (
            "python3",
            "-c",
            "import socket; print(socket.gethostbyname('host.docker.internal'))",
        )
    )
    result = adapter.run_command(ssh_target, command=resolve, timeout_seconds=5)
    assert result.ok, result.stderr_preview or result.stdout_preview
    host = result.stdout_preview.strip()
    assert host
    return f"http://{host}:{api_port}"


def test_remote_run_control_executor_start_stop_and_force_kill(
    reachable_node_api_port: int,
) -> None:
    adapter = ParamikoSshSftpAdapter()
    ssh_target = target()
    assert adapter.run_command(ssh_target, command="true", timeout_seconds=5).ok is True
    api_base_url = node_api_base_url(adapter, ssh_target, reachable_node_api_port)
    assert_api_base_url_reachable(adapter, ssh_target, api_base_url)
    settings = replace(
        get_settings(),
        surgepilot_node_api_base_url=api_base_url,
        runner_internal_token="",
        load_node_ssh_connect_timeout_seconds=5,
        runner_force_kill_ssh_timeout_seconds=20,
    )
    executor = RemoteRunControlExecutor(
        credential_resolver=lambda _node_id: credential(),
        adapter=adapter,
        settings=settings,
        options=RemoteExecutorOptions(command_timeout_seconds=20),
    )

    run_id = new_ulid()
    prepare_fake_workload(adapter, run_id)
    start = executor.execute(command(run_id, "start"))
    assert start.ok is True
    pidfiles = adapter.run_command(
        target(),
        command=(
            f"test -f {RUNNER_HOME}/runs/{run_id}/supervisor.pid "
            f"&& test -f {RUNNER_HOME}/runs/{run_id}/workload.pid"
        ),
        timeout_seconds=5,
    )
    assert pidfiles.ok is True

    stop = executor.execute(command(run_id, "stop"))
    assert stop.ok is True
    stopped = adapter.run_command(
        target(), command=process_is_stopped_command(run_id), timeout_seconds=5
    )
    assert stopped.ok is True

    repeated_kill = executor.execute(command(run_id, "force_kill"))
    assert repeated_kill.ok is True

    force_run_id = new_ulid()
    prepare_fake_workload(adapter, force_run_id)
    assert executor.execute(command(force_run_id, "start")).ok is True
    force_kill = executor.execute(command(force_run_id, "force_kill"))
    assert force_kill.ok is True
    force_stopped = adapter.run_command(
        target(), command=process_is_stopped_command(force_run_id), timeout_seconds=5
    )
    assert force_stopped.ok is True
