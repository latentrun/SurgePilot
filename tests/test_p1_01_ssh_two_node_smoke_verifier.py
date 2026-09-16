from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPT_DIR / "verify_p1_01_ssh_two_node_smoke.py"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location("verify_p1_01_ssh_two_node_smoke", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
smoke = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = smoke
spec.loader.exec_module(smoke)

SCANNED_HOST_KEY = {
    "algorithm": "ssh-ed25519",
    "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIFakeVerifierHostKey",
    "fingerprintSha256": "SHA256:verifierHostKey",
}


def artifact(
    node_id: str,
    *,
    artifact_type: str = "run_log",
    relative_path: str = "logs/run.log",
    allocation_id: str | None = "allocation-1",
) -> dict:
    return {
        "id": f"artifact-{node_id}-{relative_path}",
        "node_id": node_id,
        "allocation_id": allocation_id,
        "artifact_type": artifact_type,
        "relative_path": relative_path,
        "size_bytes": 128,
        "sha256": "a" * 64,
        "storage_key": f"run-artifacts/ws/run/{node_id}/{relative_path}",
    }


def stub_artifacts(monkeypatch: pytest.MonkeyPatch, artifacts: list[dict]) -> None:
    monkeypatch.setattr(smoke.base, "fetch_all", lambda *_args, **_kwargs: artifacts)
    monkeypatch.setattr(smoke.base, "assert_artifact_metadata_safe", lambda rows: None)
    monkeypatch.setattr(smoke.base, "assert_minio_objects_exist", lambda rows: None)


def test_stopped_run_artifacts_do_not_require_final_stats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = [
        artifact("node-1"),
        artifact("node-2"),
        artifact("node-1", artifact_type="artifacts_zip", relative_path="artifacts/artifacts.zip"),
        artifact("node-2", artifact_type="artifacts_zip", relative_path="artifacts/artifacts.zip"),
    ]
    stub_artifacts(monkeypatch, artifacts)

    smoke.assert_two_node_artifacts("run-1", ["node-1", "node-2"], require_final_stats=False)


def test_finished_run_artifacts_require_final_stats_from_each_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = [artifact("node-1"), artifact("node-2")]
    stub_artifacts(monkeypatch, artifacts)

    with pytest.raises(AssertionError, match="Expected final stats from both nodes"):
        smoke.assert_two_node_artifacts("run-1", ["node-1", "node-2"], require_final_stats=True)


def test_finished_run_artifacts_accept_final_stats_from_each_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = [
        artifact(
            "node-1",
            artifact_type="final_stats_csv",
            relative_path="artifacts/final_stats.csv",
        ),
        artifact(
            "node-2",
            artifact_type="final_stats_csv",
            relative_path="artifacts/finalstats.csv",
        ),
        artifact("node-1", artifact_type="artifacts_zip", relative_path="artifacts/artifacts.zip"),
        artifact("node-2", artifact_type="artifacts_zip", relative_path="artifacts/artifacts.zip"),
    ]
    stub_artifacts(monkeypatch, artifacts)

    smoke.assert_two_node_artifacts("run-1", ["node-1", "node-2"], require_final_stats=True)


def test_two_node_artifacts_require_archive_from_each_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = [artifact("node-1"), artifact("node-2")]
    stub_artifacts(monkeypatch, artifacts)

    with pytest.raises(AssertionError, match="Expected artifacts.zip from both nodes"):
        smoke.assert_two_node_artifacts("run-1", ["node-1", "node-2"], require_final_stats=False)


def test_artifacts_still_require_allocation_ownership_after_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = [
        artifact("node-1", allocation_id=None),
        artifact("node-1", artifact_type="artifacts_zip", relative_path="artifacts/artifacts.zip"),
        artifact("node-2", artifact_type="artifacts_zip", relative_path="artifacts/artifacts.zip"),
    ]
    stub_artifacts(monkeypatch, artifacts)

    with pytest.raises(AssertionError, match="Expected allocation-owned artifacts"):
        smoke.assert_two_node_artifacts("run-1", ["node-1", "node-2"], require_final_stats=False)


def test_load_node_payload_supports_two_real_ip_port_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SURGEPILOT_E2E_NODE_1_SSH_HOST", "192.168.1.3")
    monkeypatch.setenv("SURGEPILOT_E2E_NODE_1_SSH_PORT", "22322")
    monkeypatch.setenv("SURGEPILOT_E2E_NODE_2_SSH_HOST", "192.168.1.3")
    monkeypatch.setenv("SURGEPILOT_E2E_NODE_2_SSH_PORT", "22323")

    node_1 = smoke.load_node_payload("ssh-load-node", SCANNED_HOST_KEY)
    node_2 = smoke.load_node_payload("ssh-load-node-2", SCANNED_HOST_KEY)

    assert node_1["host"] == "192.168.1.3"
    assert node_1["sshPort"] == 22322
    assert node_1["sshHostKey"] == SCANNED_HOST_KEY
    assert node_2["host"] == "192.168.1.3"
    assert node_2["sshPort"] == 22323
    assert node_2["sshHostKey"] == SCANNED_HOST_KEY


def test_load_node_payload_preserves_legacy_single_node_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SURGEPILOT_E2E_NODE_SSH_HOST", "192.168.1.3")
    monkeypatch.setenv("SURGEPILOT_E2E_NODE_SSH_PORT", "22322")

    node_1 = smoke.load_node_payload("ssh-load-node")
    node_2 = smoke.load_node_payload("ssh-load-node-2")

    assert node_1["host"] == "192.168.1.3"
    assert node_1["sshPort"] == 22322
    assert node_2["host"] == "ssh-load-node-2"
    assert node_2["sshPort"] == 22


def test_host_ip_fallback_configures_both_published_node_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smoke.base, "E2E_HOST_IP", "192.168.1.3")
    monkeypatch.delenv("SURGEPILOT_E2E_NODE_1_SSH_HOST", raising=False)
    monkeypatch.delenv("SURGEPILOT_E2E_NODE_1_SSH_PORT", raising=False)
    monkeypatch.delenv("SURGEPILOT_E2E_NODE_2_SSH_HOST", raising=False)
    monkeypatch.delenv("SURGEPILOT_E2E_NODE_2_SSH_PORT", raising=False)

    assert smoke.load_node_target("ssh-load-node").host == "192.168.1.3"
    assert smoke.load_node_target("ssh-load-node").port == 22322
    assert smoke.load_node_target("ssh-load-node-2").host == "192.168.1.3"
    assert smoke.load_node_target("ssh-load-node-2").port == 22323

    smoke.configure_compose_external_node_env()

    assert smoke.os.environ["SURGEPILOT_E2E_NODE_1_SSH_HOST"] == "192.168.1.3"
    assert smoke.os.environ["SURGEPILOT_E2E_NODE_1_SSH_PORT"] == "22322"
    assert smoke.os.environ["SURGEPILOT_E2E_NODE_2_SSH_HOST"] == "192.168.1.3"
    assert smoke.os.environ["SURGEPILOT_E2E_NODE_2_SSH_PORT"] == "22323"


def test_run_report_rejects_external_node_host_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SURGEPILOT_E2E_NODE_1_SSH_HOST", "192.168.1.3")
    monkeypatch.setenv("SURGEPILOT_E2E_NODE_1_SSH_PORT", "22322")
    monkeypatch.setenv("SURGEPILOT_E2E_NODE_2_SSH_HOST", "192.168.1.3")
    monkeypatch.setenv("SURGEPILOT_E2E_NODE_2_SSH_PORT", "22323")

    def fake_http_json(_opener: object, _method: str, path: str, **_kwargs: object) -> tuple:
        if path.endswith("/artifacts"):
            return (
                {"items": [{"nodeId": "node-1"}, {"nodeId": "node-2"}]},
                {},
            )
        return (
            {
                "verdict": {"slaResult": "not_evaluated"},
                "allocatedNodes": [
                    {"id": "node-1", "name": "Node 1"},
                    {"id": "node-2", "name": "Node 2", "debugHost": "192.168.1.3"},
                ],
            },
            {},
        )

    monkeypatch.setattr(smoke.base, "http_json", fake_http_json)

    session = SimpleNamespace(opener=object(), workspace_id="workspace-1")
    with pytest.raises(AssertionError, match="192\\.168\\.1\\.3"):
        smoke.assert_run_report(session, "run-1", ["node-1", "node-2"])


def test_consolidated_node_endpoints_configure_two_real_ip_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SURGEPILOT_E2E_NODE_ENDPOINTS", "10.0.0.8:22322,10.0.0.8:22323")
    monkeypatch.delenv("SURGEPILOT_E2E_NODE_1_SSH_HOST", raising=False)
    monkeypatch.delenv("SURGEPILOT_E2E_NODE_1_SSH_PORT", raising=False)
    monkeypatch.delenv("SURGEPILOT_E2E_NODE_2_SSH_HOST", raising=False)
    monkeypatch.delenv("SURGEPILOT_E2E_NODE_2_SSH_PORT", raising=False)

    node_1 = smoke.load_node_payload("ssh-load-node")
    node_2 = smoke.load_node_payload("ssh-load-node-2")

    assert node_1["host"] == "10.0.0.8"
    assert node_1["sshPort"] == 22322
    assert node_2["host"] == "10.0.0.8"
    assert node_2["sshPort"] == 22323


def test_consolidated_node_endpoints_reject_incomplete_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SURGEPILOT_E2E_NODE_ENDPOINTS", "10.0.0.8:22322")

    with pytest.raises(ValueError, match="exactly two"):
        smoke.load_node_targets()


def test_configure_host_minio_endpoint_uses_published_compose_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smoke, "USER_CONFIGURED_MINIO_ENDPOINT", False)
    monkeypatch.setattr(smoke.base, "MINIO_ENDPOINT", "localhost:9000")

    def fake_run_command(args: list[str], *, check: bool = True):
        assert check is False
        if args[-3:] == ["port", "minio", "9000"]:
            return SimpleNamespace(returncode=0, stdout="0.0.0.0:19000\n")
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(smoke.base, "run_command", fake_run_command)

    smoke.configure_host_minio_endpoint()

    assert smoke.base.MINIO_ENDPOINT == "127.0.0.1:19000"


def test_configure_host_minio_endpoint_uses_container_ip_when_port_is_unpublished(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smoke, "USER_CONFIGURED_MINIO_ENDPOINT", False)
    monkeypatch.setattr(smoke.base, "MINIO_ENDPOINT", "localhost:9000")

    def fake_run_command(args: list[str], *, check: bool = True):
        assert check is False
        if args[-3:] == ["port", "minio", "9000"]:
            return SimpleNamespace(returncode=0, stdout="")
        if args[-3:] == ["ps", "-q", "minio"]:
            return SimpleNamespace(returncode=0, stdout="minio-container\n")
        if args[:3] == ["docker", "inspect", "-f"]:
            return SimpleNamespace(returncode=0, stdout="172.20.0.4\n")
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(smoke.base, "run_command", fake_run_command)

    smoke.configure_host_minio_endpoint()

    assert smoke.base.MINIO_ENDPOINT == "172.20.0.4:9000"


def test_configure_host_minio_endpoint_preserves_explicit_user_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smoke, "USER_CONFIGURED_MINIO_ENDPOINT", True)
    monkeypatch.setattr(smoke.base, "MINIO_ENDPOINT", "custom-minio:9000")

    smoke.configure_host_minio_endpoint()

    assert smoke.base.MINIO_ENDPOINT == "custom-minio:9000"
