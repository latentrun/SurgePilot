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
    reason="near-real SSH/SFTP two-node runner smoke is opt-in",
)

RUNNER_HOME = "/opt/surgepilot/runner"


def ssh_env() -> tuple[str, int, int, str, str]:
    return (
        os.environ.get("SURGEPILOT_SSH_E2E_HOST", "127.0.0.1"),
        int(os.environ.get("SURGEPILOT_SSH_E2E_PORT", "22322")),
        int(os.environ.get("SURGEPILOT_SSH_E2E_2_PORT", "22323")),
        os.environ.get("SURGEPILOT_SSH_E2E_USER", "surgepilot"),
        os.environ.get("SURGEPILOT_SSH_E2E_PASSWORD", "surgepilot"),
    )


def credential() -> CredentialPlaintext:
    return CredentialPlaintext(auth_type="password", password=ssh_env()[4])


def target(port: int) -> SshTarget:
    host, _port_a, _port_b, user, _password = ssh_env()
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


def command(*, run_id: str, action: str, node_id: str, port: int) -> RunControlCommand:
    ssh_target = target(port)
    runner_action = "kill" if action == "force_kill" else action
    runner_shell = (
        f"PATH={shlex.quote(RUNNER_HOME)}/bin:$PATH "
        f"python3 {shlex.quote(RUNNER_HOME)}/runner.py {runner_action} --run-id {run_id}"
    )
    return RunControlCommand(
        request_id=new_ulid(),
        action=action,
        run_id=run_id,
        node_id=node_id,
        reason="ssh_two_node_e2e",
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


def prepare_fake_workload(adapter: ParamikoSshSftpAdapter, port: int, run_id: str) -> None:
    adapter.upload_text(
        target(port),
        remote_path=f"{RUNNER_HOME}/current/bin/bzt",
        content="#!/bin/sh\ntrap 'exit 143' TERM INT\nsleep 60\n",
        mode=0o755,
    )
    adapter.upload_text(
        target(port),
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


def test_remote_run_control_executor_runs_two_distinct_ssh_nodes(
    reachable_node_api_port: int,
) -> None:
    _host, port_a, port_b, _user, _password = ssh_env()
    adapter = ParamikoSshSftpAdapter()
    target_a = target(port_a)
    target_b = target(port_b)
    assert adapter.run_command(target_a, command="true", timeout_seconds=5).ok is True
    assert adapter.run_command(target_b, command="true", timeout_seconds=5).ok is True
    api_base_url = node_api_base_url(adapter, target_a, reachable_node_api_port)
    assert_api_base_url_reachable(adapter, target_a, api_base_url)
    assert_api_base_url_reachable(adapter, target_b, api_base_url)
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
    node_a = new_ulid()
    node_b = new_ulid()
    prepare_fake_workload(adapter, port_a, run_id)
    prepare_fake_workload(adapter, port_b, run_id)

    start_a = executor.execute(command(run_id=run_id, action="start", node_id=node_a, port=port_a))
    start_b = executor.execute(command(run_id=run_id, action="start", node_id=node_b, port=port_b))

    assert start_a.ok is True
    assert start_b.ok is True
    for port in (port_a, port_b):
        pidfiles = adapter.run_command(
            target(port),
            command=(
                f"test -f {RUNNER_HOME}/runs/{run_id}/supervisor.pid "
                f"&& test -f {RUNNER_HOME}/runs/{run_id}/workload.pid"
            ),
            timeout_seconds=5,
        )
        assert pidfiles.ok is True

    stop_a = executor.execute(command(run_id=run_id, action="stop", node_id=node_a, port=port_a))
    stop_b = executor.execute(command(run_id=run_id, action="stop", node_id=node_b, port=port_b))

    assert stop_a.ok is True
    assert stop_b.ok is True
    for port in (port_a, port_b):
        stopped = adapter.run_command(
            target(port), command=process_is_stopped_command(run_id), timeout_seconds=5
        )
        assert stopped.ok is True
