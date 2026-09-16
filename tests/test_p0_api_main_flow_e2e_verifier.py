from __future__ import annotations

import importlib.util
from http.cookiejar import Cookie, CookieJar
from pathlib import Path
import sys
import urllib.request

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_p0_api_main_flow_e2e.py"
spec = importlib.util.spec_from_file_location("verify_p0_api_main_flow_e2e", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
main_flow = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = main_flow
spec.loader.exec_module(main_flow)

SCANNED_HOST_KEY = {
    "algorithm": "ssh-ed25519",
    "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIFakeVerifierHostKey",
    "fingerprintSha256": "SHA256:verifierHostKey",
}


def secure_session_cookie(domain: str) -> Cookie:
    return Cookie(
        version=0,
        name="surgepilot_session",
        value="session-token",
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=False,
        domain_initial_dot=False,
        path="/",
        path_specified=True,
        secure=True,
        expires=None,
        discard=False,
        comment=None,
        comment_url=None,
        rest={"HttpOnly": None, "SameSite": "Lax"},
        rfc2109=False,
    )


def test_localhost_cookie_policy_replays_secure_session_cookie_over_http() -> None:
    cookie_jar = CookieJar(policy=main_flow.LocalhostSecureCookiePolicy())
    cookie_jar.set_cookie(secure_session_cookie("localhost.local"))

    request = urllib.request.Request("http://localhost:8080/api/v1/load-nodes")
    cookie_jar.add_cookie_header(request)

    assert request.get_header("Cookie") == "surgepilot_session=session-token"


def test_localhost_cookie_policy_keeps_secure_cookie_blocked_for_remote_http() -> None:
    cookie_jar = CookieJar(policy=main_flow.LocalhostSecureCookiePolicy())
    cookie_jar.set_cookie(secure_session_cookie("example.com"))

    request = urllib.request.Request("http://example.com/api/v1/load-nodes")
    cookie_jar.add_cookie_header(request)

    assert request.get_header("Cookie") is None


def test_scenario_and_plan_payloads_cover_env_dependency_and_real_ssh_node() -> None:
    dependency_file_id = "01J0000000000000000000000F"
    scenario_id = "01J0000000000000000000000S"
    node_id = "01J0000000000000000000000N"
    env = main_flow.env_group_payload()
    scenario = main_flow.scenario_payload(dependency_file_id=dependency_file_id)
    plan = main_flow.test_plan_payload(
        scenario_id=scenario_id,
        env_group_id="01J0000000000000000000000E",
        node_id=node_id,
        hold_for_seconds=7,
        plan_name="P0 API Main Flow",
    )

    assert env["variables"] == {"base_url": {"type": "plain", "value": "http://api:8000"}}
    assert scenario["baseUrlExpression"] == "${base_url}"
    assert scenario["dataSources"][0]["dependencyFileId"] == dependency_file_id
    assert scenario["steps"][0]["path"] == "/api/healthz"
    assert scenario["steps"][0]["assertions"][0]["expectedStatus"] == 200
    assert plan["envGroupId"] == "01J0000000000000000000000E"
    assert plan["resource"] == {"poolType": "private", "selectedNodeId": node_id}
    assert plan["scenarioItems"][0]["loadSettings"]["holdForSeconds"] == 7


def test_real_ip_target_and_node_registration_are_parameterized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_flow, "TARGET_URL", "http://192.168.1.20:18080/health")
    monkeypatch.setattr(main_flow, "NODE_SSH_HOST", "192.168.1.20")
    monkeypatch.setattr(main_flow, "NODE_SSH_PORT", 22322)

    env = main_flow.env_group_payload()
    scenario = main_flow.scenario_payload(dependency_file_id="01J0000000000000000000000F")
    node = main_flow.load_node_payload(SCANNED_HOST_KEY)

    assert env["variables"] == {"base_url": {"type": "plain", "value": "http://192.168.1.20:18080"}}
    assert scenario["steps"][0]["path"] == "/health"
    assert node["host"] == "192.168.1.20"
    assert node["sshPort"] == 22322
    assert node["sshHostKey"] == SCANNED_HOST_KEY


def test_real_ip_remote_api_defaults_to_host_ip_and_strips_api_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_flow, "E2E_HOST_IP", "192.168.1.20")
    monkeypatch.setenv("SURGEPILOT_P0_API_E2E_REMOTE_API_BASE_URL", "http://api:8000")
    monkeypatch.setenv("SURGEPILOT_E2E_API_ORCHESTRATION_URL", "http://192.168.1.20:8000/api")

    assert (
        main_flow.derive_api_base_url(
            legacy_env="SURGEPILOT_P0_API_E2E_API_BASE_URL",
            legacy_default="http://localhost:8000",
        )
        == "http://192.168.1.20:8000"
    )
    assert (
        main_flow.derive_remote_api_base_url(legacy_env="SURGEPILOT_P0_API_E2E_REMOTE_API_BASE_URL")
        == "http://192.168.1.20:8000"
    )
    assert main_flow.derive_node_api_base_url() == "http://192.168.1.20:8000"


def test_legacy_remote_api_override_applies_only_without_real_ip_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_flow, "E2E_HOST_IP", None)
    monkeypatch.delenv("SURGEPILOT_E2E_API_ORCHESTRATION_URL", raising=False)
    monkeypatch.setenv("SURGEPILOT_P0_API_E2E_REMOTE_API_BASE_URL", "http://custom-api:8000/api/")

    assert (
        main_flow.derive_remote_api_base_url(legacy_env="SURGEPILOT_P0_API_E2E_REMOTE_API_BASE_URL")
        == "http://custom-api:8000"
    )


def test_default_node_api_base_url_uses_valid_compose_fqdn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_flow, "E2E_HOST_IP", None)
    monkeypatch.delenv("SURGEPILOT_E2E_NODE_API_BASE_URL", raising=False)
    monkeypatch.delenv("SURGEPILOT_NODE_API_BASE_URL", raising=False)
    monkeypatch.delenv("SURGEPILOT_E2E_API_ORCHESTRATION_URL", raising=False)

    assert main_flow.derive_node_api_base_url() == "http://api.surgepilot.test:8000"


def test_explicit_node_api_url_wins_over_real_ip_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_flow, "E2E_HOST_IP", "192.0.2.10")
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "https://node.example.test:8443")

    assert main_flow.derive_node_api_base_url() == "https://node.example.test:8443"


def test_public_response_guards_reject_secret_and_storage_internal_leaks() -> None:
    main_flow.assert_no_forbidden_keys(
        {
            "id": "01J0000000000000000000000N",
            "credentialConfigured": True,
            "authType": "password",
            "artifact": {"downloadUrl": "/api/v1/runs/r/artifacts/a/download"},
        }
    )

    with pytest.raises(AssertionError, match="password"):
        main_flow.assert_no_forbidden_keys({"credential": {"password": "surgepilot"}})
    with pytest.raises(AssertionError, match="storageObjectKey"):
        main_flow.assert_no_forbidden_keys({"artifact": {"storageObjectKey": "run-artifacts/x"}})
    with pytest.raises(AssertionError, match="presignedUrl"):
        main_flow.assert_no_forbidden_keys({"artifact": {"presignedUrl": "http://minio/x"}})
    with pytest.raises(AssertionError, match="sensitive public value"):
        main_flow.assert_no_forbidden_keys({"message": "minioadmin"})
    with pytest.raises(AssertionError, match="sensitive public value"):
        main_flow.assert_no_forbidden_keys(
            {"details": "run-artifacts/01J0000000000000000000000W/run.log"}
        )


def test_public_response_guard_allows_user_controlled_env_variable_names() -> None:
    main_flow.assert_no_forbidden_keys({"variables": {"token": "plain-public-variable"}})

    with pytest.raises(AssertionError, match="sensitive public value"):
        main_flow.assert_no_forbidden_keys({"variables": {"token": "minioadmin"}})


def test_finished_report_guard_requires_final_stats_and_parsed_kpis() -> None:
    report = {
        "verdict": {"state": "finished"},
        "snapshot": {
            "scenarioCount": 1,
            "dependencyFileCount": 1,
            "resourceRequest": {
                "poolType": "private",
                "selectedNodeId": "01J0000000000000000000000N",
            },
        },
        "artifactsSummary": {
            "count": 1,
            "hasArtifactsZip": False,
            "hasFinalStatsCsv": False,
            "latestAvailableAt": None,
        },
        "kpiSummary": {"status": "missing"},
        "finalStatsPreview": {"status": "missing", "truncated": False, "rows": []},
    }

    with pytest.raises(AssertionError, match="final stats"):
        main_flow.assert_report_safe_and_complete(report, expected_state="finished")


def test_finished_report_guard_requires_successful_health_check_kpis() -> None:
    report = {
        "verdict": {"state": "finished"},
        "snapshot": {
            "scenarioCount": 1,
            "dependencyFileCount": 1,
            "resourceRequest": {
                "poolType": "private",
                "selectedNodeId": "01J0000000000000000000000N",
            },
        },
        "artifactsSummary": {
            "count": 1,
            "hasArtifactsZip": False,
            "hasFinalStatsCsv": True,
            "latestAvailableAt": "2030-01-01T00:00:00Z",
        },
        "kpiSummary": {
            "status": "parsed",
            "sourceArtifactId": "01J0000000000000000000000A",
            "totalRequests": 1,
            "failedRequests": 1,
            "errorRate": 100.0,
            "averageResponseTimeMs": 10.0,
            "p90Ms": 10.0,
            "p95Ms": 10.0,
            "p99Ms": 10.0,
            "throughputPerSecond": None,
            "missingReasons": [],
        },
        "finalStatsPreview": {
            "status": "parsed",
            "truncated": False,
            "rows": [
                {
                    "label": "GET API health",
                    "totalRequests": 1,
                    "successRequests": 0,
                    "failedRequests": 1,
                    "errorRate": 100.0,
                    "averageResponseTimeMs": 10.0,
                    "p90Ms": 10.0,
                    "p95Ms": 10.0,
                    "p99Ms": 10.0,
                    "responseCodeCounts": {"500": 1},
                }
            ],
            "warnings": [],
        },
    }

    with pytest.raises(AssertionError, match="successful health-check KPI"):
        main_flow.assert_report_safe_and_complete(report, expected_state="finished")


def test_finished_report_poll_waits_for_async_final_stats_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pending_report = {
        "verdict": {"state": "finished"},
        "artifactsSummary": {"hasFinalStatsCsv": True},
        "kpiSummary": {"status": "pending"},
        "finalStatsPreview": {"status": "pending"},
    }
    parsed_report = {
        "verdict": {"state": "finished"},
        "artifactsSummary": {"hasFinalStatsCsv": True},
        "kpiSummary": {"status": "parsed"},
        "finalStatsPreview": {"status": "parsed"},
    }
    reports = [pending_report, parsed_report]
    calls: list[str] = []

    def fake_get_json(_session: main_flow.ApiSession, path: str) -> dict:
        calls.append(path)
        return reports.pop(0)

    monkeypatch.setattr(main_flow, "get_json", fake_get_json)
    monkeypatch.setattr(main_flow.time, "sleep", lambda _seconds: None)
    session = main_flow.ApiSession(
        csrf_token="csrf",
        workspace_id="01J0000000000000000000000W",
        email="user@example.com",
        opener=object(),
    )

    report = main_flow.poll_finished_report_complete(
        session, "01J0000000000000000000000R", timeout_seconds=10
    )

    assert report is parsed_report
    assert calls == [
        "/api/v1/runs/01J0000000000000000000000R",
        "/api/v1/runs/01J0000000000000000000000R",
    ]


def test_finished_report_poll_fails_fast_when_summary_parse_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failed_report = {
        "verdict": {"state": "finished"},
        "artifactsSummary": {"hasFinalStatsCsv": True},
        "kpiSummary": {"status": "failed"},
        "finalStatsPreview": {"status": "pending"},
    }
    sleeps: list[int] = []

    def fake_get_json(_session: main_flow.ApiSession, _path: str) -> dict:
        return failed_report

    monkeypatch.setattr(main_flow, "get_json", fake_get_json)
    monkeypatch.setattr(main_flow.time, "sleep", lambda seconds: sleeps.append(seconds))
    session = main_flow.ApiSession(
        csrf_token="csrf",
        workspace_id="01J0000000000000000000000W",
        email="user@example.com",
        opener=object(),
    )

    with pytest.raises(main_flow.E2EFailure, match="failed to parse"):
        main_flow.poll_finished_report_complete(
            session, "01J0000000000000000000000R", timeout_seconds=10
        )

    assert sleeps == []


def test_finished_report_poll_fails_fast_when_run_leaves_finished_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running_report = {
        "verdict": {"state": "running"},
        "artifactsSummary": {"hasFinalStatsCsv": True},
        "kpiSummary": {"status": "pending"},
        "finalStatsPreview": {"status": "pending"},
    }
    sleeps: list[int] = []

    def fake_get_json(_session: main_flow.ApiSession, _path: str) -> dict:
        return running_report

    monkeypatch.setattr(main_flow, "get_json", fake_get_json)
    monkeypatch.setattr(main_flow.time, "sleep", lambda seconds: sleeps.append(seconds))
    session = main_flow.ApiSession(
        csrf_token="csrf",
        workspace_id="01J0000000000000000000000W",
        email="user@example.com",
        opener=object(),
    )

    with pytest.raises(main_flow.E2EFailure, match="left finished state"):
        main_flow.poll_finished_report_complete(
            session, "01J0000000000000000000000R", timeout_seconds=10
        )

    assert sleeps == []


def test_artifact_guard_requires_final_stats_download(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_get_json(_session: main_flow.ApiSession, _path: str) -> dict:
        return {
            "items": [
                {
                    "id": "01J0000000000000000000000L",
                    "artifactType": "run_log",
                    "relativePath": "logs/run.log",
                    "displayFilename": "run.log",
                    "sizeBytes": 128,
                    "sha256": "a" * 64,
                    "downloadUrl": "/api/v1/runs/01J0000000000000000000000R/artifacts/01J0000000000000000000000L/download",
                    "terminalLate": False,
                    "createdAt": "2030-01-01T00:00:00Z",
                    "availableAt": "2030-01-01T00:00:01Z",
                },
                {
                    "id": "01J0000000000000000000000F",
                    "artifactType": "final_stats_csv",
                    "relativePath": "artifacts/finalstats.csv",
                    "displayFilename": "finalstats.csv",
                    "sizeBytes": 256,
                    "sha256": "b" * 64,
                    "downloadUrl": "/api/v1/runs/01J0000000000000000000000R/artifacts/01J0000000000000000000000F/download",
                    "terminalLate": False,
                    "createdAt": "2030-01-01T00:00:00Z",
                    "availableAt": "2030-01-01T00:00:01Z",
                },
            ]
        }

    def fake_http_bytes(*args: object, **kwargs: object) -> tuple[bytes, dict[str, str], int]:
        calls.append(str(args[2]))
        return (
            b"label,# Samples,KO,OK,error%,rc_200\nGET API health,1,0,1,0.0,1\n",
            {"content-disposition": "attachment; filename=finalstats.csv"},
            200,
        )

    monkeypatch.setattr(main_flow, "get_json", fake_get_json)
    monkeypatch.setattr(main_flow, "http_bytes", fake_http_bytes)
    session = main_flow.ApiSession(
        csrf_token="csrf",
        workspace_id="01J0000000000000000000000W",
        email="user@example.com",
        opener=object(),
    )

    main_flow.assert_artifact_downloads(session, "01J0000000000000000000000R")

    assert calls == [
        "/api/v1/runs/01J0000000000000000000000R/artifacts/01J0000000000000000000000F/download"
    ]


def test_artifact_public_metadata_guard_requires_safe_download_route() -> None:
    main_flow.assert_public_artifact_metadata_safe(
        [
            {
                "id": "01J0000000000000000000000A",
                "artifactType": "final_stats_csv",
                "relativePath": "artifacts/finalstats.csv",
                "displayFilename": "finalstats.csv",
                "sizeBytes": 128,
                "sha256": "a" * 64,
                "downloadUrl": "/api/v1/runs/01J0000000000000000000000R/artifacts/01J0000000000000000000000A/download",
                "terminalLate": False,
                "createdAt": "2030-01-01T00:00:00Z",
                "availableAt": "2030-01-01T00:00:01Z",
            }
        ]
    )

    with pytest.raises(AssertionError, match="unsafe relative path"):
        main_flow.assert_public_artifact_metadata_safe(
            [
                {
                    "id": "01J0000000000000000000000A",
                    "artifactType": "run_log",
                    "relativePath": "../run.log",
                    "displayFilename": "run.log",
                    "sizeBytes": 1,
                    "sha256": "a" * 64,
                    "downloadUrl": "/api/v1/runs/r/artifacts/a/download",
                }
            ]
        )


def test_setup_stack_builds_runtime_artifact_before_compose_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run_command(args: list[str], **_kwargs: object):
        calls.append(args)
        return object()

    monkeypatch.setattr(main_flow, "run_command", fake_run_command)
    monkeypatch.setattr(main_flow, "wait_for_api_health", lambda: None)
    monkeypatch.setattr(main_flow, "verify_node_api_reachable", lambda: None)
    monkeypatch.setattr(main_flow, "verify_target_reachable", lambda: None)
    monkeypatch.setattr(main_flow, "verify_influxdb_node_write_reachable", lambda: None)

    main_flow.setup_stack(build_app=False, build_ssh=False)

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
        raise main_flow.E2EFailure("connection refused")

    monkeypatch.setattr(main_flow, "run_command", fake_run_command)

    with pytest.raises(
        main_flow.E2EFailure,
        match=r"SURGEPILOT_E2E_TARGET_URL=http://192\.168\.1\.20:18080/health",
    ):
        main_flow.verify_url_reachable_from_node(
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

    monkeypatch.setattr(main_flow, "run_command", fake_run_command)

    main_flow.verify_url_reachable_from_node(
        env_name="SURGEPILOT_E2E_TARGET_URL",
        url="http://192.168.1.20:18080/health",
    )

    assert "expected_body_fragment = None" in calls[0][-1]
    assert "expected_body_fragment = null" not in calls[0][-1]


def test_run_command_provides_runtime_artifact_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_env: dict[str, str] = {}

    class Result:
        returncode = 0
        stdout = ""

    def fake_run(*_args, **kwargs):
        captured_env.update(kwargs["env"])
        return Result()

    monkeypatch.setattr(main_flow.subprocess, "run", fake_run)

    main_flow.run_command(["true"])

    assert captured_env["LOAD_NODE_RUNTIME_VERSION"] == main_flow.RUNTIME_VERSION
    assert captured_env["LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR"] == str(
        main_flow.RUNTIME_ARTIFACT_HOST_DIR
    )
    assert captured_env["SURGEPILOT_E2E_NODE_SSH_HOST"] == main_flow.NODE_SSH_HOST
    assert captured_env["SURGEPILOT_E2E_NODE_SSH_PORT"] == str(main_flow.NODE_SSH_PORT)
    assert captured_env["RUNNER_INTERNAL_TOKEN"] == main_flow.TEST_RUNNER_INTERNAL_TOKEN
    assert captured_env["MINIO_ACCESS_KEY"] == main_flow.MINIO_ACCESS_KEY
    assert captured_env["MINIO_SECRET_KEY"] == main_flow.MINIO_SECRET_KEY
    assert captured_env["MINIO_ROOT_USER"] == main_flow.MINIO_ACCESS_KEY
    assert captured_env["MINIO_ROOT_PASSWORD"] == main_flow.MINIO_SECRET_KEY
    assert captured_env["MINIO_BUCKET"] == main_flow.MINIO_BUCKET


def test_runtime_bootstrap_verification_checks_current_and_bundle_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run_command(args: list[str], **_kwargs: object):
        calls.append(args)
        return object()

    monkeypatch.setattr(main_flow, "run_command", fake_run_command)

    main_flow.verify_runtime_bootstrap("run_01")

    command = calls[0][-1]
    assert "current/bin/bzt" in command
    assert "current/apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper" in command
    assert "~/.bzt/jmeter-taurus" in command
    with pytest.raises(AssertionError, match="downloadUrl"):
        main_flow.assert_public_artifact_metadata_safe(
            [
                {
                    "id": "01J0000000000000000000000A",
                    "artifactType": "run_log",
                    "relativePath": "logs/run.log",
                    "displayFilename": "run.log",
                    "sizeBytes": 1,
                    "sha256": "a" * 64,
                    "downloadUrl": "http://minio/surgepilot/run-artifacts/x",
                }
            ]
        )
