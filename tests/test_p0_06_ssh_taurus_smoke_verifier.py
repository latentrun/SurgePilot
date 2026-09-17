from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_p0_06_ssh_taurus_smoke.py"
spec = importlib.util.spec_from_file_location("verify_p0_06_ssh_taurus_smoke", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
smoke = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = smoke
spec.loader.exec_module(smoke)

SCANNED_HOST_KEY = {
    "algorithm": "ssh-ed25519",
    "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIFakeVerifierHostKey",
    "fingerprintSha256": "SHA256:verifierHostKey",
}


def test_short_and_stop_plan_payloads_target_api_from_load_node_container() -> None:
    short_plan = smoke.test_plan_payload(
        scenario_id="01J0000000000000000000000S",
        node_id="01J0000000000000000000000N",
        hold_for_seconds=10,
        plan_name="P0-06 short smoke",
    )
    stop_plan = smoke.test_plan_payload(
        scenario_id="01J0000000000000000000000S",
        node_id="01J0000000000000000000000N",
        hold_for_seconds=30,
        plan_name="P0-06 stop smoke",
    )
    scenario = smoke.scenario_payload()
    env = smoke.env_group_payload()

    assert env == {
        "name": "P0-06 SSH Smoke",
        "variables": {"base_url": {"type": "plain", "value": "http://api:8000"}},
    }
    assert scenario["baseUrlExpression"] == "${base_url}"
    assert scenario["steps"][0]["path"] == "/api/healthz"
    assert scenario["steps"][0]["assertions"][0]["expectedStatus"] == 200
    assert short_plan["scenarioItems"][0]["loadSettings"] == {
        "concurrencyPerNode": 1,
        "rampUpSeconds": 0,
        "holdForSeconds": 10,
        "iterations": None,
        "targetRps": None,
        "steps": None,
        "delaySeconds": 0,
    }
    assert stop_plan["scenarioItems"][0]["loadSettings"]["holdForSeconds"] == 30
    assert short_plan["slaRules"] == []


def test_real_ip_target_and_node_registration_are_parameterized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smoke, "TARGET_URL", "http://192.168.1.20:18080/health")
    monkeypatch.setattr(smoke, "NODE_SSH_HOST", "192.168.1.20")
    monkeypatch.setattr(smoke, "NODE_SSH_PORT", 22322)

    env = smoke.env_group_payload()
    scenario = smoke.scenario_payload()
    node = smoke.load_node_payload(SCANNED_HOST_KEY)

    assert env["variables"] == {"base_url": {"type": "plain", "value": "http://192.168.1.20:18080"}}
    assert scenario["steps"][0]["path"] == "/health"
    assert node["host"] == "192.168.1.20"
    assert node["sshPort"] == 22322
    assert node["sshHostKey"] == SCANNED_HOST_KEY


def test_real_ip_remote_api_defaults_to_host_ip_and_strips_api_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smoke, "E2E_HOST_IP", "192.168.1.20")
    monkeypatch.setenv("SURGEPILOT_P0_06_REMOTE_API_BASE_URL", "http://api:8000")
    monkeypatch.setenv("SURGEPILOT_E2E_API_ORCHESTRATION_URL", "http://192.168.1.20:8000/api")

    assert (
        smoke.derive_api_base_url(
            legacy_env="SURGEPILOT_P0_06_API_BASE_URL",
            legacy_default="http://localhost:8000",
        )
        == "http://192.168.1.20:8000"
    )
    assert (
        smoke.derive_remote_api_base_url(legacy_env="SURGEPILOT_P0_06_REMOTE_API_BASE_URL")
        == "http://192.168.1.20:8000"
    )
    assert smoke.derive_node_api_base_url() == "http://192.168.1.20:8000"


def test_legacy_remote_api_override_applies_only_without_real_ip_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smoke, "E2E_HOST_IP", None)
    monkeypatch.delenv("SURGEPILOT_E2E_API_ORCHESTRATION_URL", raising=False)
    monkeypatch.setenv("SURGEPILOT_P0_06_REMOTE_API_BASE_URL", "http://custom-api:8000/api/")

    assert (
        smoke.derive_remote_api_base_url(legacy_env="SURGEPILOT_P0_06_REMOTE_API_BASE_URL")
        == "http://custom-api:8000"
    )


def test_default_node_api_base_url_uses_valid_compose_fqdn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smoke, "E2E_HOST_IP", None)
    monkeypatch.delenv("SURGEPILOT_E2E_NODE_API_BASE_URL", raising=False)
    monkeypatch.delenv("SURGEPILOT_NODE_API_BASE_URL", raising=False)
    monkeypatch.delenv("SURGEPILOT_E2E_API_ORCHESTRATION_URL", raising=False)

    assert smoke.derive_node_api_base_url() == "http://api.surgepilot.test:8000"


def test_explicit_node_api_url_wins_over_real_ip_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smoke, "E2E_HOST_IP", "192.0.2.10")
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "https://node.example.test:8443")

    assert smoke.derive_node_api_base_url() == "https://node.example.test:8443"


def test_node_response_secret_guard_rejects_plaintext_credentials() -> None:
    safe_response = {
        "id": "01J0000000000000000000000N",
        "credentialConfigured": True,
        "credentialFingerprint": "sha256:abc",
    }
    smoke.assert_no_secret_echo(safe_response)

    with pytest.raises(AssertionError, match="password"):
        smoke.assert_no_secret_echo({**safe_response, "password": "surgepilot"})
    with pytest.raises(AssertionError, match="privateKey"):
        smoke.assert_no_secret_echo({**safe_response, "credential": {"privateKey": "secret"}})


def test_artifact_metadata_guard_requires_safe_metadata_without_public_object_key() -> None:
    smoke.assert_artifact_metadata_safe(
        [
            {
                "id": "01J0000000000000000000000A",
                "artifact_type": "final_stats_csv",
                "relative_path": "artifacts/finalstats.csv",
                "size_bytes": 128,
                "sha256": "a" * 64,
                "storage_key": "run-artifacts/ws/run/artifacts/finalstats.csv",
            }
        ]
    )

    with pytest.raises(AssertionError, match="unsafe relative path"):
        smoke.assert_artifact_metadata_safe(
            [
                {
                    "id": "01J0000000000000000000000A",
                    "artifact_type": "run_log",
                    "relative_path": "../run.log",
                    "size_bytes": 1,
                    "sha256": "a" * 64,
                    "storage_key": "run-artifacts/ws/run/run.log",
                }
            ]
        )
    with pytest.raises(AssertionError, match="sha256"):
        smoke.assert_artifact_metadata_safe(
            [
                {
                    "id": "01J0000000000000000000000A",
                    "artifact_type": "run_log",
                    "relative_path": "logs/run.log",
                    "size_bytes": 1,
                    "sha256": "bad",
                    "storage_key": "run-artifacts/ws/run/logs/run.log",
                }
            ]
        )


def test_remote_process_cleanup_timeout_allows_stop_grace_observed_in_compose() -> None:
    assert smoke.REMOTE_PROCESS_CLEANUP_TIMEOUT_SECONDS == 45


def test_setup_stack_builds_runtime_artifact_before_compose_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run_command(args: list[str], **_kwargs: object):
        calls.append(args)
        return object()

    monkeypatch.setattr(smoke, "run_command", fake_run_command)
    monkeypatch.setattr(smoke, "wait_for_api_health", lambda: None)
    monkeypatch.setattr(smoke, "verify_node_api_reachable", lambda: None)
    monkeypatch.setattr(smoke, "verify_target_reachable", lambda: None)
    monkeypatch.setattr(smoke, "verify_influxdb_node_write_reachable", lambda: None)
    monkeypatch.setattr(smoke, "verify_api_worker_can_reach_node_ssh", lambda: None)

    smoke.setup_stack(build_app=False, build_ssh=False)

    release_calls = [
        call for call in calls if any(item.endswith("release_runtime_artifact.py") for item in call)
    ]
    up_calls = [call for call in calls if "up" in call]
    assert release_calls
    assert up_calls
    assert "--fixed-version" in release_calls[0]
    assert calls.index(release_calls[0]) < calls.index(up_calls[0])


def test_node_preflight_reports_env_name_and_url(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_command(*_args: object, **_kwargs: object) -> None:
        raise smoke.SmokeFailure("connection refused")

    monkeypatch.setattr(smoke, "run_command", fake_run_command)

    with pytest.raises(
        smoke.SmokeFailure,
        match=r"SURGEPILOT_E2E_TARGET_URL=http://192\.168\.1\.20:18080/health",
    ):
        smoke.verify_url_reachable_from_node(
            env_name="SURGEPILOT_E2E_TARGET_URL",
            url="http://192.168.1.20:18080/health",
        )


def test_node_preflight_uses_python_none_for_optional_body_fragment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run_command(args: list[str], **_kwargs: object) -> object:
        calls.append(args)
        return object()

    monkeypatch.setattr(smoke, "run_command", fake_run_command)

    smoke.verify_url_reachable_from_node(
        env_name="SURGEPILOT_E2E_TARGET_URL",
        url="http://192.168.1.20:18080/health",
    )

    assert "expected_body_fragment = None" in calls[0][-1]
    assert "expected_body_fragment = null" not in calls[0][-1]


def test_influxdb_node_write_preflight_uses_health_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def fake_verify_url_reachable_from_node(*, env_name: str, url: str, **_kwargs: object) -> None:
        calls.append((env_name, url))

    monkeypatch.setattr(smoke, "INFLUXDB_NODE_WRITE_URL", "http://192.168.1.20:18086")
    monkeypatch.setattr(
        smoke, "verify_url_reachable_from_node", fake_verify_url_reachable_from_node
    )

    smoke.verify_influxdb_node_write_reachable()

    assert calls == [
        ("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "http://192.168.1.20:18086/health")
    ]


def test_stack_context_keep_data_does_not_delete_volumes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run_command(args: list[str], **_kwargs: object):
        calls.append(args)
        return object()

    monkeypatch.setattr(smoke, "run_command", fake_run_command)
    monkeypatch.setattr(smoke, "setup_stack", lambda **_kwargs: None)

    with smoke.stack_context(build_app=False, build_ssh=False, keep_stack=False, keep_data=True):
        pass

    assert calls[-1] == smoke.compose_cmd("down")


def test_run_command_provides_runtime_artifact_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_env: dict[str, str] = {}

    class Result:
        returncode = 0
        stdout = ""

    def fake_run(*_args, **kwargs):
        captured_env.update(kwargs["env"])
        return Result()

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)

    smoke.run_command(["true"])

    assert captured_env["LOAD_NODE_RUNTIME_VERSION"] == smoke.RUNTIME_VERSION
    assert captured_env["LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR"] == str(
        smoke.RUNTIME_ARTIFACT_HOST_DIR
    )
    assert captured_env["SURGEPILOT_E2E_NODE_SSH_HOST"] == smoke.NODE_SSH_HOST
    assert captured_env["SURGEPILOT_E2E_NODE_SSH_PORT"] == str(smoke.NODE_SSH_PORT)
    assert captured_env["RUNNER_INTERNAL_TOKEN"] == smoke.TEST_RUNNER_INTERNAL_TOKEN
    assert captured_env["MINIO_ACCESS_KEY"] == smoke.MINIO_ACCESS_KEY
    assert captured_env["MINIO_SECRET_KEY"] == smoke.MINIO_SECRET_KEY
    assert captured_env["MINIO_ROOT_USER"] == smoke.MINIO_ACCESS_KEY
    assert captured_env["MINIO_ROOT_PASSWORD"] == smoke.MINIO_SECRET_KEY
    assert captured_env["MINIO_BUCKET"] == smoke.MINIO_BUCKET


def test_runtime_bootstrap_verification_checks_current_and_bundle_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run_command(args: list[str], **_kwargs: object):
        calls.append(args)
        return object()

    monkeypatch.setattr(smoke, "run_command", fake_run_command)

    smoke.verify_runtime_bootstrap("run_01")

    command = calls[0][-1]
    assert "current/bin/bzt" in command
    assert "current/apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper" in command
    assert "~/.bzt/jmeter-taurus" in command
