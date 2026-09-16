from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPT_DIR / "verify_p1_00_monitoring_remote_node_write.py"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location(
    "verify_p1_00_monitoring_remote_node_write", SCRIPT_PATH
)
assert spec is not None and spec.loader is not None
monitoring = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = monitoring
spec.loader.exec_module(monitoring)


def test_environment_skip_requires_final_node_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SURGEPILOT_P1_MONITORING_REMOTE_WRITE", "1")
    monkeypatch.delenv("SURGEPILOT_NODE_API_BASE_URL", raising=False)
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "http://192.168.1.20:18086")

    assert "SURGEPILOT_NODE_API_BASE_URL is not set" in (monitoring.environment_skip_reason() or "")


def test_environment_skip_requires_node_write_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SURGEPILOT_P1_MONITORING_REMOTE_WRITE", "1")
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "http://192.168.1.20:18000")
    monkeypatch.delenv("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", raising=False)

    assert "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL is not set" in (
        monitoring.environment_skip_reason() or ""
    )


def test_base_helpers_use_monitoring_full_compose_files() -> None:
    command = monitoring.base.compose_cmd("ps")

    assert "infra/docker/docker-compose.yml" in command
    assert "infra/docker/docker-compose.ssh-e2e.yml" in command
    assert "infra/docker/docker-compose.base.yml" not in command


def test_setup_stack_runs_real_ip_preflights(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(monitoring, "run_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(monitoring.base, "seed_runtime_artifact", lambda: calls.append("seed"))
    monkeypatch.setattr(monitoring.base, "wait_for_api_health", lambda: calls.append("api-health"))
    monkeypatch.setattr(
        monitoring.base,
        "verify_api_worker_can_reach_node_ssh",
        lambda: calls.append("worker-to-ssh"),
    )
    monkeypatch.setattr(
        monitoring.base, "verify_node_api_reachable", lambda: calls.append("node-to-api")
    )
    monkeypatch.setattr(
        monitoring.base, "verify_target_reachable", lambda: calls.append("node-to-target")
    )
    monkeypatch.setattr(
        monitoring.base,
        "verify_influxdb_node_write_reachable",
        lambda: calls.append("node-to-influxdb"),
    )

    monitoring.setup_stack(build_app=False, build_ssh=False)

    assert calls == [
        "seed",
        "api-health",
        "worker-to-ssh",
        "node-to-api",
        "node-to-target",
        "node-to-influxdb",
    ]


def test_keep_data_stops_stack_without_deleting_volumes(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setenv("SURGEPILOT_P1_MONITORING_REMOTE_WRITE", "1")
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "http://192.168.1.20:18000")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "http://192.168.1.20:18086")
    monkeypatch.setattr(
        sys, "argv", ["verify_p1_00_monitoring_remote_node_write.py", "--keep-data"]
    )
    monkeypatch.setattr(monitoring, "setup_stack", lambda **_kwargs: None)
    monkeypatch.setattr(monitoring, "run_smoke", lambda: None)
    monkeypatch.setattr(monitoring, "compose_cmd", lambda *args: ["compose", *args])
    monkeypatch.setattr(
        monitoring,
        "run_command",
        lambda args, **_kwargs: commands.append(args),
    )

    assert monitoring.main() == 0
    assert commands[-1] == ["compose", "down"]


def test_keep_stack_skips_down(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setenv("SURGEPILOT_P1_MONITORING_REMOTE_WRITE", "1")
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "http://192.168.1.20:18000")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "http://192.168.1.20:18086")
    monkeypatch.setattr(
        sys,
        "argv",
        ["verify_p1_00_monitoring_remote_node_write.py", "--keep-stack", "--keep-data"],
    )
    monkeypatch.setattr(monitoring, "setup_stack", lambda **_kwargs: None)
    monkeypatch.setattr(monitoring, "run_smoke", lambda: None)
    monkeypatch.setattr(monitoring, "compose_cmd", lambda *args: ["compose", *args])
    monkeypatch.setattr(
        monitoring,
        "run_command",
        lambda args, **_kwargs: commands.append(args),
    )

    assert monitoring.main() == 0
    assert commands == []
