from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "verify_full_ssh_e2e_node_connectivity.py"
)
spec = importlib.util.spec_from_file_location("verify_full_ssh_e2e_node_connectivity", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
connectivity = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = connectivity
spec.loader.exec_module(connectivity)


def test_health_urls_use_only_final_node_facing_origins() -> None:
    assert connectivity.health_urls(
        {
            "SURGEPILOT_NODE_API_BASE_URL": "http://192.168.1.20:18000",
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://192.168.1.20:18086",
            "SURGEPILOT_MONITORING_INFLUXDB_INTERNAL_URL": "http://influxdb:8086",
        }
    ) == [
        (
            "SURGEPILOT_NODE_API_BASE_URL",
            "http://192.168.1.20:18000/api/healthz",
            {"status": "ok"},
        ),
        (
            "SURGEPILOT_NODE_API_BASE_URL identity",
            "http://192.168.1.20:18000/api/openapi.json",
            {"info.title": "SurgePilot API"},
        ),
        (
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL",
            "http://192.168.1.20:18086/health",
            {"name": "influxdb", "status": "pass"},
        ),
    ]


def test_health_urls_require_both_final_urls() -> None:
    with pytest.raises(connectivity.ConnectivityError, match="SURGEPILOT_NODE_API_BASE_URL"):
        connectivity.health_urls(
            {"SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://192.168.1.20:18086"}
        )


def test_verifier_checks_api_and_influxdb_from_both_ssh_nodes() -> None:
    commands: list[list[str]] = []

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        commands.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    connectivity.verify_connectivity(
        {
            "SURGEPILOT_NODE_API_BASE_URL": "http://192.168.1.20:18000",
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://192.168.1.20:18086",
        },
        run=run,
        sleep=lambda _seconds: None,
        attempts=1,
    )

    assert len(commands) == 6
    assert {command[command.index("exec") + 2] for command in commands} == {
        "ssh-load-node",
        "ssh-load-node-2",
    }
    rendered = "\n".join(" ".join(command) for command in commands)
    assert "http://192.168.1.20:18000/api/healthz" in rendered
    assert "http://192.168.1.20:18000/api/openapi.json" in rendered
    assert "http://192.168.1.20:18086/health" in rendered
    assert "http://api:8000" not in rendered
    assert "http://influxdb:8086" not in rendered
    assert '"status": "ok"' in rendered
    assert '"info.title": "SurgePilot API"' in rendered
    assert '"name": "influxdb"' in rendered
    assert '"status": "pass"' in rendered


def test_verifier_fails_after_bounded_retries() -> None:
    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(args, 1, stdout="unreachable", stderr="")

    with pytest.raises(connectivity.ConnectivityError, match="ssh-load-node"):
        connectivity.verify_connectivity(
            {
                "SURGEPILOT_NODE_API_BASE_URL": "http://192.168.1.20:18000",
                "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://192.168.1.20:18086",
            },
            run=run,
            sleep=lambda _seconds: None,
            attempts=2,
        )
