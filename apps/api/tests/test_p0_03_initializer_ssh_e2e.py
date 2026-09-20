from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import os
import pytest

from app.core.config import get_settings
from app.core.product_version import PRODUCT_VERSION
from app.models.load_nodes import LoadNode
from app.services.load_node_initializer import RealLoadNodeInitializer
from app.services.load_nodes import CredentialPlaintext
from app.services.ssh_remote import ParamikoSshSftpAdapter, SshTarget, scan_ssh_host_key

pytestmark = pytest.mark.skipif(
    os.environ.get("SURGEPILOT_SSH_E2E") != "1",
    reason="real SSH initializer smoke is opt-in",
)

RUNNER_HOME = "/opt/surgepilot/runner"


def ssh_env() -> tuple[str, int, str, str]:
    return (
        os.environ.get("SURGEPILOT_SSH_E2E_HOST", "127.0.0.1"),
        int(os.environ.get("SURGEPILOT_SSH_E2E_PORT", "22322")),
        os.environ.get("SURGEPILOT_SSH_E2E_USER", "surgepilot"),
        os.environ.get("SURGEPILOT_SSH_E2E_PASSWORD", "surgepilot"),
    )


def target() -> SshTarget:
    host, port, user, password = ssh_env()
    scanned = scan_ssh_host_key(host=host, port=port, timeout_seconds=5)
    return SshTarget(
        host=host,
        port=port,
        username=user,
        credential=CredentialPlaintext(auth_type="password", password=password),
        connect_timeout_seconds=5,
        trusted_host_key_algorithm=scanned.algorithm,
        trusted_host_key_public_key=scanned.public_key,
        trusted_host_key_fingerprint_sha256=scanned.fingerprint_sha256,
    )


def node() -> LoadNode:
    host, port, user, _password = ssh_env()
    return LoadNode(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
        scope="workspace",
        workspace_id="01HZW000000000000000000000",
        host=host,
        ssh_port=port,
        ssh_user=user,
        runner_home=RUNNER_HOME,
        auth_type="password",
        ssh_host_key_algorithm=target().trusted_host_key_algorithm,
        ssh_host_key_public_key=target().trusted_host_key_public_key,
        ssh_host_key_fingerprint_sha256=target().trusted_host_key_fingerprint_sha256,
        ssh_host_key_trusted_at=datetime.now(UTC),
        ssh_host_key_trusted_by="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        status="initializing",
        created_by="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    )


def test_real_initializer_success_path_over_ssh() -> None:
    adapter = ParamikoSshSftpAdapter()
    settings = replace(
        get_settings(),
        load_node_ssh_connect_timeout_seconds=5,
        load_node_init_command_timeout_seconds=60,
    )

    result = RealLoadNodeInitializer(adapter=adapter, settings=settings).initialize(
        node(), target().credential
    )

    assert result.ok is True
    assert result.runner_version == PRODUCT_VERSION
    assert result.bundle_version == "p0-03"
    assert "Runner bundle uploaded" in result.log
    marker = adapter.run_command(
        target(), command=f"test -f {RUNNER_HOME}/.surgepilot-node", timeout_seconds=5
    )
    assert marker.ok is True
    runner_version = adapter.run_command(
        target(), command=f"python3 {RUNNER_HOME}/runner.py version", timeout_seconds=5
    )
    assert runner_version.ok is True
    assert f"SurgePilot Runner {PRODUCT_VERSION}" in runner_version.stdout_preview
