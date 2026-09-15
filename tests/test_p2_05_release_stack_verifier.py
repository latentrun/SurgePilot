from __future__ import annotations

import io
from pathlib import Path
import sys
import urllib.error
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import verify_p2_05_release_stack  # noqa: E402


def test_release_scenario_is_bounded_to_configured_lan_health_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        verify_p2_05_release_stack,
        "TARGET_URL",
        "http://192.168.1.20:8080/api/healthz",
    )
    payload = verify_p2_05_release_stack.scenario_payload()

    assert payload["baseUrlExpression"] == "${base_url}"
    assert payload["dataSources"] == []
    assert len(payload["steps"]) == 1
    assert payload["steps"][0]["method"] == "GET"
    assert payload["steps"][0]["path"] == "/api/healthz"
    assert verify_p2_05_release_stack.target_origin() == "http://192.168.1.20:8080"
    assert "password" not in str(payload).lower()


def test_target_origin_rejects_non_http_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verify_p2_05_release_stack, "TARGET_URL", "demo-load-node")

    with pytest.raises(RuntimeError, match="absolute HTTP URL"):
        verify_p2_05_release_stack.target_origin()


def test_release_standard_plan_uses_initialized_private_node() -> None:
    payload = verify_p2_05_release_stack.standard_plan_payload(
        scenario_id="scenario-1",
        env_group_id="env-1",
        node_id="node-1",
    )

    assert payload["envGroupId"] == "env-1"
    assert payload["resource"] == {"poolType": "private", "selectedNodeId": "node-1"}
    assert payload["scenarioItems"][0]["scenarioId"] == "scenario-1"
    assert payload["scenarioItems"][0]["loadSettings"]["holdForSeconds"] == 6


def test_verify_release_stack_runs_lan_debug_and_standard_monitoring_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    password_file = tmp_path / "demo-password.secret"
    password_file.write_text("release-password\n", encoding="utf-8")
    influx_token_file = tmp_path / "influx-token.secret"
    influx_token_file.write_text("influx-token\n", encoding="utf-8")
    monkeypatch.setenv("SURGEPILOT_E2E_NODE_SSH_PASSWORD_FILE", str(password_file))
    monkeypatch.setenv("SURGEPILOT_E2E_INFLUXDB_TOKEN_FILE", str(influx_token_file))
    monkeypatch.setenv("SURGEPILOT_E2E_INFLUXDB_QUERY_URL", "http://192.168.1.20:8086")
    session = object()
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        verify_p2_05_release_stack,
        "register_user",
        lambda label: calls.append(("register", label)) or session,
    )
    monkeypatch.setattr(
        verify_p2_05_release_stack,
        "scan_load_node_ssh_host_key",
        lambda actual_session, *, host, ssh_port: (
            {
                "algorithm": "ssh-ed25519",
                "publicKey": "AAAATEST",
                "fingerprintSha256": "SHA256:test",
            }
            if actual_session is session and host == "demo-load-node" and ssh_port == 22
            else pytest.fail("unexpected host-key scan inputs")
        ),
    )

    def create_json(actual_session: object, path: str, payload: dict) -> dict:
        assert actual_session is session
        calls.append((path, payload))
        if path == "/api/v1/load-nodes":
            assert payload["credential"] == {
                "authType": "password",
                "password": "release-password",
            }
            return {"id": "node-1"}
        if path == "/api/v1/env-groups":
            assert payload["variables"]["base_url"]["value"] == ("http://api.surgepilot.test:8000")
            return {"id": "env-1"}
        if path == "/api/v1/scenarios":
            return {"id": "scenario-1", "revision": 3}
        if path == "/api/v1/runs":
            if payload["runType"] == "debug":
                assert payload["selectedNodeId"] == "node-1"
                assert payload["expectedSourceRevision"] == 3
                return {"id": "debug-run-1"}
            assert payload == {
                "runType": "standard",
                "sourceType": "test_plan",
                "sourceId": "plan-1",
                "expectedSourceRevision": 5,
            }
            return {"id": "standard-run-1"}
        if path == "/api/v1/test-plans":
            assert payload["resource"]["selectedNodeId"] == "node-1"
            return {"id": "plan-1", "revision": 5, "runnable": True}
        return pytest.fail(f"unexpected create path: {path}")

    monkeypatch.setattr(verify_p2_05_release_stack, "create_json", create_json)
    monkeypatch.setattr(
        verify_p2_05_release_stack,
        "initialize_node",
        lambda actual_session, node_id: (
            calls.append(("initialize", node_id))
            if actual_session is session
            else pytest.fail("unexpected initialization session")
        ),
    )
    monkeypatch.setattr(
        verify_p2_05_release_stack,
        "poll_report_state",
        lambda actual_session, run_id, states, timeout: (
            {"verdict": {"state": "finished"}}
            if actual_session is session
            and run_id in {"debug-run-1", "standard-run-1"}
            and states == {"finished"}
            and timeout == 300
            else pytest.fail("unexpected report polling inputs")
        ),
    )
    monitored: list[str] = []
    monkeypatch.setattr(
        verify_p2_05_release_stack,
        "wait_for_monitoring_points",
        lambda run_id: monitored.append(run_id),
    )
    monitoring_calls: list[str] = []

    def get_json(actual_session: object, path: str) -> dict:
        assert actual_session is session
        monitoring_calls.append(path)
        if path == "/api/v1/runs/standard-run-1/monitoring":
            return {
                "runId": "standard-run-1",
                "enabledForRun": True,
                "status": "enabled",
                "platformMonitoringUrl": (
                    "/observability/monitoring?runId=standard-run-1&from=1&to=2"
                ),
                "iframeUrl": "/grafana/d/surgepilot?var-runId=standard-run-1",
                "dashboardUid": "surgepilot",
            }
        if path == "/api/v1/monitoring/embed":
            return {"status": "ready", "iframeUrl": "/grafana"}
        return pytest.fail(f"unexpected monitoring path: {path}")

    monkeypatch.setattr(verify_p2_05_release_stack, "get_json", get_json)

    verify_p2_05_release_stack.verify_release_stack()

    assert ("initialize", "node-1") in calls
    assert monitored == ["standard-run-1"]
    assert monitoring_calls == [
        "/api/v1/runs/standard-run-1/monitoring",
        "/api/v1/monitoring/embed",
    ]
    assert [item[0] for item in calls if isinstance(item[0], str)][-1] == "/api/v1/runs"


def test_query_measurements_uses_token_and_parses_flux_csv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "influx-token.secret"
    token_file.write_text("secret-token\n", encoding="utf-8")
    monkeypatch.setenv("SURGEPILOT_E2E_INFLUXDB_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("SURGEPILOT_E2E_INFLUXDB_QUERY_URL", "http://192.168.1.20:8086")
    captured: dict[str, object] = {}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def urlopen(request: urllib.request.Request, timeout: int):
        captured["url"] = request.full_url
        captured["authorization"] = request.headers["Authorization"]
        captured["timeout"] = timeout
        return Response(
            b",result,table,_measurement\n,_result,0,requestsRaw\n"
            b",_result,0,virtualUsers\n,_result,0,testStartEnd\n"
        )

    monkeypatch.setattr(verify_p2_05_release_stack.urllib.request, "urlopen", urlopen)

    assert verify_p2_05_release_stack.query_measurements("run-1") == {
        "requestsRaw",
        "virtualUsers",
        "testStartEnd",
    }
    assert captured == {
        "url": "http://192.168.1.20:8086/api/v2/query?org=surgepilot",
        "authorization": "Token secret-token",
        "timeout": 10,
    }


def test_query_measurements_requires_query_url_and_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SURGEPILOT_E2E_INFLUXDB_QUERY_URL", raising=False)
    with pytest.raises(RuntimeError, match="QUERY_URL is required"):
        verify_p2_05_release_stack.query_measurements("run-1")

    monkeypatch.setenv("SURGEPILOT_E2E_INFLUXDB_QUERY_URL", "http://192.168.1.20:8086")
    monkeypatch.delenv("SURGEPILOT_E2E_INFLUXDB_TOKEN_FILE", raising=False)
    with pytest.raises(RuntimeError, match="TOKEN_FILE is required"):
        verify_p2_05_release_stack.query_measurements("run-1")

    token_file = tmp_path / "empty-token.secret"
    token_file.write_text("\n", encoding="utf-8")
    monkeypatch.setenv("SURGEPILOT_E2E_INFLUXDB_TOKEN_FILE", str(token_file))
    with pytest.raises(RuntimeError, match="token file is empty"):
        verify_p2_05_release_stack.query_measurements("run-1")


def test_query_measurements_reports_influxdb_http_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "influx-token.secret"
    token_file.write_text("secret-token", encoding="utf-8")
    monkeypatch.setenv("SURGEPILOT_E2E_INFLUXDB_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("SURGEPILOT_E2E_INFLUXDB_QUERY_URL", "http://192.168.1.20:8086")

    def fail_query(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            "http://192.168.1.20:8086/api/v2/query",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b"invalid token"),
        )

    monkeypatch.setattr(verify_p2_05_release_stack.urllib.request, "urlopen", fail_query)

    with pytest.raises(RuntimeError, match="401 invalid token"):
        verify_p2_05_release_stack.query_measurements("run-1")


def test_wait_for_monitoring_points_retries_until_measurements_arrive(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    responses = iter([{"requestsRaw"}, verify_p2_05_release_stack.REQUIRED_MEASUREMENTS])
    monotonic_values = iter([0.0, 0.0, 1.0])
    sleeps: list[int] = []
    monkeypatch.setattr(
        verify_p2_05_release_stack, "query_measurements", lambda _run_id: next(responses)
    )
    monkeypatch.setattr(
        verify_p2_05_release_stack.time, "monotonic", lambda: next(monotonic_values)
    )
    monkeypatch.setattr(verify_p2_05_release_stack.time, "sleep", sleeps.append)

    verify_p2_05_release_stack.wait_for_monitoring_points("run-1")

    assert sleeps == [2]
    assert "Waiting for InfluxDB measurements for run-1" in capsys.readouterr().out


def test_wait_for_monitoring_points_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monotonic_values = iter([0.0, 0.0, 121.0])
    monkeypatch.setattr(verify_p2_05_release_stack, "query_measurements", lambda _run_id: set())
    monkeypatch.setattr(
        verify_p2_05_release_stack.time, "monotonic", lambda: next(monotonic_values)
    )
    monkeypatch.setattr(verify_p2_05_release_stack.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="did not publish required InfluxDB measurements"):
        verify_p2_05_release_stack.wait_for_monitoring_points("run-1")


def test_verify_release_stack_rejects_empty_password_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    password_file = tmp_path / "demo-password.secret"
    password_file.write_text("\n", encoding="utf-8")
    monkeypatch.setenv("SURGEPILOT_E2E_NODE_SSH_PASSWORD_FILE", str(password_file))

    with pytest.raises(RuntimeError, match="password file is empty"):
        verify_p2_05_release_stack.verify_release_stack()


@pytest.mark.parametrize(
    ("report", "run_monitoring", "monitoring", "message"),
    [
        ({"verdict": {"state": "failed"}}, None, None, "Debug Run did not finish"),
        (
            {"verdict": {"state": "finished"}},
            {
                "runId": "standard-run-1",
                "enabledForRun": True,
                "status": "enabled",
                "platformMonitoringUrl": "/monitoring?runId=standard-run-1",
                "iframeUrl": "/grafana?var-runId=standard-run-1",
            },
            {"status": "not_configured", "iframeUrl": None},
            "Monitoring entry is not ready",
        ),
        (
            {"verdict": {"state": "finished"}},
            {"runId": "standard-run-1", "enabledForRun": False, "status": "disabled"},
            None,
            "Standard Run Monitoring link is not ready",
        ),
        (
            {"verdict": {"state": "finished"}},
            {
                "runId": "standard-run-1",
                "enabledForRun": True,
                "status": "enabled",
                "platformMonitoringUrl": "/monitoring?runId=standard-run-1",
                "iframeUrl": "/grafana?var-runId=standard-run-1&token=influx-token",
            },
            None,
            "exposed InfluxDB token or node-write URL",
        ),
        (
            {"verdict": {"state": "finished"}, "diagnostic": "influx-token"},
            None,
            None,
            "exposed InfluxDB token or node-write URL",
        ),
        (
            {"verdict": {"state": "finished"}},
            {
                "runId": "standard-run-1",
                "enabledForRun": True,
                "status": "enabled",
                "platformMonitoringUrl": "/monitoring?runId=standard-run-1",
                "iframeUrl": "/grafana?var-runId=standard-run-1",
            },
            {"status": "ready", "iframeUrl": "/grafana", "diagnostic": "influx-token"},
            "exposed InfluxDB token or node-write URL",
        ),
    ],
)
def test_verify_release_stack_reports_acceptance_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    report: dict,
    run_monitoring: dict | None,
    monitoring: dict | None,
    message: str,
) -> None:
    password_file = tmp_path / "demo-password.secret"
    password_file.write_text("release-password", encoding="utf-8")
    influx_token_file = tmp_path / "influx-token.secret"
    influx_token_file.write_text("influx-token", encoding="utf-8")
    monkeypatch.setenv("SURGEPILOT_E2E_NODE_SSH_PASSWORD_FILE", str(password_file))
    monkeypatch.setenv("SURGEPILOT_E2E_INFLUXDB_TOKEN_FILE", str(influx_token_file))
    monkeypatch.setenv("SURGEPILOT_E2E_INFLUXDB_QUERY_URL", "http://192.168.1.20:8086")
    monkeypatch.setattr(verify_p2_05_release_stack, "register_user", lambda _label: object())
    monkeypatch.setattr(
        verify_p2_05_release_stack,
        "scan_load_node_ssh_host_key",
        lambda *_args, **_kwargs: {
            "algorithm": "ssh-ed25519",
            "publicKey": "AAAATEST",
            "fingerprintSha256": "SHA256:test",
        },
    )
    responses = iter(
        [
            {"id": "node-1"},
            {"id": "env-1"},
            {"id": "scenario-1", "revision": 1},
            {"id": "run-1"},
            {"id": "plan-1", "revision": 1, "runnable": True},
            {"id": "standard-run-1"},
        ]
    )
    monkeypatch.setattr(
        verify_p2_05_release_stack, "create_json", lambda *_args, **_kwargs: next(responses)
    )
    monkeypatch.setattr(verify_p2_05_release_stack, "initialize_node", lambda *_args: None)
    monkeypatch.setattr(verify_p2_05_release_stack, "poll_report_state", lambda *_args: report)
    monkeypatch.setattr(
        verify_p2_05_release_stack, "wait_for_monitoring_points", lambda *_args: None
    )
    if run_monitoring is not None:
        monkeypatch.setattr(
            verify_p2_05_release_stack,
            "get_json",
            lambda _session, path: (
                run_monitoring if path == "/api/v1/runs/standard-run-1/monitoring" else monitoring
            ),
        )

    with pytest.raises(RuntimeError, match=message):
        verify_p2_05_release_stack.verify_release_stack()


def test_main_reports_success_and_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(verify_p2_05_release_stack, "verify_release_stack", lambda: None)
    assert verify_p2_05_release_stack.main() == 0
    assert "acceptance passed" in capsys.readouterr().out

    def fail() -> None:
        raise RuntimeError("release unavailable")

    monkeypatch.setattr(verify_p2_05_release_stack, "verify_release_stack", fail)
    assert verify_p2_05_release_stack.main() == 1
    assert "release unavailable" in capsys.readouterr().err
