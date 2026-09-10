from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core.ids import new_ulid
from app.models.auth import DEFAULT_WORKSPACE_ID, User
from app.models.load_nodes import LoadNode
from app.models.runs import Run, RunMonitoringConfig
from app.schemas.load_nodes import LoadNodeCredentialInput
from app.services.load_nodes import create_load_node
from app.core.config import get_settings
from app.services import monitoring as monitoring_service
from app.services.monitoring import (
    build_monitoring_properties,
    create_run_monitoring_snapshot,
    get_monitoring_embed,
    get_run_monitoring_link,
    resolve_monitoring_for_run,
)
from app.services.runs import RunExecutionInput, create_run_execution
from app.services.scenarios import runtime_jmeter_path


def trusted_host_key() -> dict[str, str]:
    return {
        "algorithm": "ssh-ed25519",
        "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        "fingerprintSha256": "SHA256:SurgePilotTrustedHostKey",
    }


def actor() -> User:
    now = datetime.now(UTC)
    return User(
        id=new_ulid(),
        email=f"monitoring-{new_ulid().lower()}@example.com",
        display_name="Monitoring User",
        password_hash="hash",
        role="admin",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )


def credential() -> LoadNodeCredentialInput:
    return LoadNodeCredentialInput(authType="password", password="secret-password")


def idle_node(db_session: Session, user: User) -> LoadNode:
    db_session.add(user)
    db_session.flush()
    node = create_load_node(
        db_session,
        actor=user,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host=f"monitoring-node-{new_ulid().lower()}.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=credential(),
        ssh_host_key=trusted_host_key(),
        maintainer=None,
        remark=None,
    )
    node.status = "idle"
    node.runtime_version = "runtime-test-v1"
    db_session.flush()
    return node


def create_standard_run(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Run:
    monkeypatch.setenv("SURGEPILOT_MONITORING_ENABLED", "true")
    monkeypatch.setenv(
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "https://node-write.example.test"
    )
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_INTERNAL_URL", "http://influxdb:8086")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_ORG", "surgepilot")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_BUCKET", "jmeter")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED", "true")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN", "secret-token")
    user = actor()
    node = idle_node(db_session, user)
    run = create_run_execution(
        db_session,
        RunExecutionInput(
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            selected_node_id=node.id,
            run_type="standard",
            source_type="test_plan",
            source_id=new_ulid(),
            snapshot_payload={"sourceType": "test_plan", "runType": "standard"},
        ),
    )
    db_session.flush()
    return run


def test_monitoring_model_has_minimal_non_secret_columns(db_session: Session) -> None:
    tables = inspect(db_session.bind).get_table_names()
    assert "run_monitoring_configs" in tables
    assert "monitoring_settings" not in tables
    columns = {
        column["name"] for column in inspect(db_session.bind).get_columns("run_monitoring_configs")
    }
    assert {
        "run_id",
        "workspace_id",
        "status",
        "disabled_reason",
        "influxdb_node_write_url",
        "dashboard_uid",
        "grafana_base_path",
        "created_at",
    }.issubset(columns)
    assert (
        not {
            "token",
            "token_ciphertext",
            "token_fingerprint",
            "influxdb_internal_url",
            "source_scope",
            "warning_code",
            "listener_params",
        }
        & columns
    )


def test_debug_run_is_always_dynamic_disabled_without_monitoring_row(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_MONITORING_ENABLED", "true")
    monkeypatch.setenv(
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "https://node-write.example.test"
    )
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_INTERNAL_URL", "http://influxdb:8086")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_ORG", "surgepilot")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_BUCKET", "jmeter")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED", "true")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN", "secret-token")
    user = actor()
    node = idle_node(db_session, user)

    run = create_run_execution(
        db_session,
        RunExecutionInput(
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            selected_node_id=node.id,
            run_type="debug",
            source_type="debug_scenario",
            source_id=new_ulid(),
            snapshot_payload={"sourceType": "debug_scenario", "runType": "debug"},
        ),
    )
    create_run_monitoring_snapshot(db_session, run=run)
    resolved = resolve_monitoring_for_run(db_session, run=run)

    assert resolved.status == "disabled"
    assert resolved.disabled_reason == "debug_run_not_monitored"
    assert resolved.enabled_for_run is False
    assert (
        db_session.scalar(select(RunMonitoringConfig).where(RunMonitoringConfig.run_id == run.id))
        is None
    )


def test_standard_enabled_run_persists_non_secret_snapshot_and_safe_links(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = create_standard_run(db_session, monkeypatch)

    row = db_session.scalar(select(RunMonitoringConfig).where(RunMonitoringConfig.run_id == run.id))
    assert row is not None
    assert row.status == "enabled"
    assert row.influxdb_node_write_url == "https://node-write.example.test"
    assert row.dashboard_uid == "surgepilot-jmeter-13644"
    assert row.grafana_base_path == "/grafana"
    assert "secret-token" not in repr(row.__dict__)
    assert "influxdb:8086" not in repr(row.__dict__)

    link = get_run_monitoring_link(db_session, workspace_id=DEFAULT_WORKSPACE_ID, run_id=run.id)
    assert link.enabled_for_run is True
    assert link.status == "enabled"
    assert link.platform_monitoring_url is not None
    assert link.iframe_url is not None
    assert f"runId={run.id}" in link.platform_monitoring_url
    assert f"var-runId={run.id}" in link.iframe_url
    assert "&kiosk&" in link.iframe_url
    assert "kiosk=tv" not in link.iframe_url
    assert "theme=dark" in link.iframe_url
    assert "secret-token" not in link.model_dump_json()
    assert "node-write" not in link.model_dump_json()
    assert "influxdb" not in link.model_dump_json()


def test_sidebar_monitoring_embed_defaults_to_dark_recent_window_without_run_id(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_MONITORING_ENABLED", "true")
    monkeypatch.setenv(
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "https://node-write.example.test"
    )
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_INTERNAL_URL", "http://influxdb:8086")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_ORG", "surgepilot")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_BUCKET", "jmeter")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED", "true")
    now = datetime(2030, 6, 22, 10, 30, 0, tzinfo=UTC)
    monkeypatch.setattr(monitoring_service, "utc_now", lambda: now)

    embed = get_monitoring_embed(db_session, workspace_id=DEFAULT_WORKSPACE_ID, run_id=None)

    assert embed.enabled is True
    assert embed.status == "ready"
    assert embed.run_id is None
    assert embed.from_ == str(int(now.timestamp() * 1000) - 5 * 60 * 1000)
    assert embed.to == "now"
    assert embed.iframe_url is not None
    assert "theme=dark" in embed.iframe_url
    assert "&kiosk&" in embed.iframe_url
    assert "kiosk=tv" not in embed.iframe_url
    assert "var-runId" not in embed.iframe_url
    assert "now-" not in embed.iframe_url


def test_monitoring_embed_preserves_explicit_window_without_run_id(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_MONITORING_ENABLED", "true")
    monkeypatch.setenv(
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "https://node-write.example.test"
    )
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_INTERNAL_URL", "http://influxdb:8086")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_ORG", "surgepilot")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_BUCKET", "jmeter")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED", "true")

    embed = get_monitoring_embed(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_id=None,
        from_="1906703945000",
        to="1906704370000",
    )

    assert embed.from_ == "1906703945000"
    assert embed.to == "1906704370000"
    assert embed.iframe_url is not None
    assert "from=1906703945000" in embed.iframe_url
    assert "to=1906704370000" in embed.iframe_url


def test_api_settings_uses_presence_flag_without_reading_token_plaintext(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("secret-token-from-file\n", encoding="utf-8")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN", "secret-token-from-env")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE", str(token_file))
    monkeypatch.delenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED", raising=False)

    settings = get_settings()

    assert settings.monitoring_influxdb_token_configured is False
    assert not hasattr(settings, "monitoring_influxdb_token")


def test_standard_config_error_persists_without_secret_upload_properties(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_MONITORING_ENABLED", "true")
    monkeypatch.delenv("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", raising=False)
    user = actor()
    node = idle_node(db_session, user)
    run = create_run_execution(
        db_session,
        RunExecutionInput(
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            selected_node_id=node.id,
            run_type="standard",
            source_type="test_plan",
            source_id=new_ulid(),
            snapshot_payload={"sourceType": "test_plan", "runType": "standard"},
        ),
    )

    row = db_session.scalar(select(RunMonitoringConfig).where(RunMonitoringConfig.run_id == run.id))
    assert row is not None
    assert row.status == "config_error"
    assert row.disabled_reason is None
    assert row.influxdb_node_write_url is None
    assert (
        build_monitoring_properties(db_session, run_id=run.id, node_id=None, monitoring_token=None)
        is None
    )

    link = get_run_monitoring_link(db_session, workspace_id=DEFAULT_WORKSPACE_ID, run_id=run.id)
    assert link.status == "config_error"
    assert link.disabled_reason is None
    assert link.iframe_url is None
    assert link.platform_monitoring_url is None


def test_standard_config_error_when_enabled_but_token_presence_is_missing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_MONITORING_ENABLED", "true")
    monkeypatch.setenv(
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "https://node-write.example.test"
    )
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_INTERNAL_URL", "http://influxdb:8086")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_ORG", "surgepilot")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_BUCKET", "jmeter")
    monkeypatch.delenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN", raising=False)
    monkeypatch.delenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE", raising=False)
    monkeypatch.delenv("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED", raising=False)
    user = actor()
    node = idle_node(db_session, user)

    run = create_run_execution(
        db_session,
        RunExecutionInput(
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            selected_node_id=node.id,
            run_type="standard",
            source_type="test_plan",
            source_id=new_ulid(),
            snapshot_payload={"sourceType": "test_plan", "runType": "standard"},
        ),
    )

    row = db_session.scalar(select(RunMonitoringConfig).where(RunMonitoringConfig.run_id == run.id))
    assert row is not None
    assert row.status == "config_error"
    assert row.disabled_reason is None
    assert row.influxdb_node_write_url is None
    assert (
        build_monitoring_properties(db_session, run_id=run.id, node_id=None, monitoring_token=None)
        is None
    )


def test_standard_run_without_monitoring_enabled_does_not_create_snapshot(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SURGEPILOT_MONITORING_ENABLED", raising=False)
    user = actor()
    node = idle_node(db_session, user)

    run = create_run_execution(
        db_session,
        RunExecutionInput(
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            selected_node_id=node.id,
            run_type="standard",
            source_type="test_plan",
            source_id=new_ulid(),
            snapshot_payload={"sourceType": "test_plan", "runType": "standard"},
        ),
    )

    assert (
        db_session.scalar(select(RunMonitoringConfig).where(RunMonitoringConfig.run_id == run.id))
        is None
    )
    link = get_run_monitoring_link(db_session, workspace_id=DEFAULT_WORKSPACE_ID, run_id=run.id)
    assert link.status == "not_configured"
    assert link.disabled_reason == "not_configured"


def test_all_taurus_bundles_use_surgepilot_jmeter_wrapper() -> None:
    assert runtime_jmeter_path("/opt/surgepilot/runner") == (
        "/opt/surgepilot/runner/current/apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper"
    )


@pytest.mark.anyio
async def test_monitoring_public_endpoints_and_session_check_do_not_leak_secrets(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "monitoring-api@example.com",
            "displayName": "Monitoring API",
            "password": "password123",
        },
    )
    assert register.status_code == 201
    workspace_id = register.json()["defaultWorkspace"]["id"]
    run = create_standard_run(db_session, monkeypatch)

    embed = await client.get(
        "/api/v1/monitoring/embed",
        params={"runId": run.id},
        headers={"x-workspace-id": workspace_id},
    )
    assert embed.status_code == 200
    assert embed.json()["status"] == "ready"
    assert embed.json()["iframeUrl"].startswith("/grafana/")
    assert "secret-token" not in embed.text
    assert "node-write" not in embed.text
    assert "influxdb" not in embed.text

    link = await client.get(
        f"/api/v1/runs/{run.id}/monitoring", headers={"x-workspace-id": workspace_id}
    )
    assert link.status_code == 200
    assert link.json()["status"] == "enabled"
    assert link.json()["platformMonitoringUrl"].startswith("/observability/monitoring?")
    assert "secret-token" not in link.text

    session_check = await client.get("/api/internal/v1/session-check")
    assert session_check.status_code == 204
