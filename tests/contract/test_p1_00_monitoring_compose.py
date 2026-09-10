from __future__ import annotations

from pathlib import Path

import json

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_compose(name: str) -> dict:
    return yaml.safe_load((ROOT / "infra/docker" / name).read_text(encoding="utf-8"))


def test_full_compose_explicitly_wires_grafana_influxdb_and_api_env() -> None:
    compose = load_compose("docker-compose.yml")
    base = load_compose("docker-compose.base.yml")
    services = compose["services"]
    base_services = base["services"]

    assert "influxdb" in services
    assert "grafana" in services
    assert "influxdb" not in base_services
    assert "grafana" not in base_services
    assert "profiles" not in services["influxdb"]
    assert "profiles" not in services["grafana"]
    assert "grafana/provisioning" in "\n".join(services["grafana"]["volumes"])

    api_env = services["api"]["environment"]
    worker_env = services["api-worker"]["environment"]
    for env in (api_env, worker_env):
        assert env["SURGEPILOT_MONITORING_ENABLED"] == "true"
        assert env["SURGEPILOT_MONITORING_INFLUXDB_INTERNAL_URL"] == "http://influxdb:8086"
        assert env["SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"] == (
            "${SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL:-http://influxdb:8086}"
        )
        assert "SURGEPILOT_MONITORING_INFLUXDB_TOKEN" not in env
    assert api_env["SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED"] == "true"
    assert "SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE" not in api_env
    assert (
        worker_env["SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE"]
        == "/run/secrets/surgepilot_influxdb_token"
    )

    assert services["api"]["depends_on"]["grafana"]["condition"] == "service_started"
    assert services["api-worker"]["depends_on"]["influxdb"]["condition"] == "service_healthy"
    assert services["nginx"]["depends_on"]["grafana"]["condition"] == "service_started"
    assert "surgepilot_influxdb_token" in compose["secrets"]
    assert "surgepilot_influxdb_token" in services["api-worker"]["secrets"]

    grafana_env = services["grafana"]["environment"]
    assert grafana_env["GF_AUTH_ANONYMOUS_ENABLED"] == "true"
    assert grafana_env["GF_AUTH_ANONYMOUS_ORG_ROLE"] == "Viewer"
    assert grafana_env["GF_SECURITY_ALLOW_EMBEDDING"] == "true"
    assert "GF_SECURITY_ADMIN_PASSWORD__FILE" not in grafana_env
    assert "SURGEPILOT_MONITORING_INFLUXDB_TOKEN" not in grafana_env
    assert services["grafana"]["user"] == "0:0"
    assert services["grafana"]["entrypoint"] == [
        "/bin/sh",
        "/etc/surgepilot/grafana-entrypoint.sh",
    ]
    assert (
        "./grafana/entrypoint.sh:/etc/surgepilot/grafana-entrypoint.sh:ro"
        in services["grafana"]["volumes"]
    )
    assert services["grafana"]["tmpfs"] == ["/run/surgepilot:mode=0710,uid=0,gid=0"]
    compose_text = (ROOT / "infra/docker/docker-compose.yml").read_text(encoding="utf-8")
    assert "Keep this file explicit" in compose_text
    assert "docker-compose.monitoring.yml" not in compose_text


def test_grafana_provisioning_matches_dashboard_13644_contract() -> None:
    datasource = (ROOT / "infra/docker/grafana/provisioning/datasources/influxdb.yml").read_text(
        encoding="utf-8"
    )
    assert "uid: InfluxDB-SurgePilot" in datasource
    assert "token: $__file{/run/surgepilot/influxdb-token}" in datasource

    entrypoint = (ROOT / "infra/docker/grafana/entrypoint.sh").read_text(encoding="utf-8")
    assert "source_token=/run/secrets/surgepilot_influxdb_token" in entrypoint
    assert "projected_token=/run/surgepilot/influxdb-token" in entrypoint
    assert 'chown 0:0 "$projected_directory"' in entrypoint
    assert 'chmod 710 "$projected_directory"' in entrypoint
    assert 'cat "$source_token" > "$projected_token"' in entrypoint
    assert 'chmod 400 "$projected_token"' in entrypoint
    assert 'export GF_SECURITY_ADMIN_PASSWORD__FILE="$projected_token"' in entrypoint
    assert "SURGEPILOT_MONITORING_INFLUXDB_TOKEN" not in entrypoint
    assert "exec su -p -s /bin/sh grafana -c 'exec /run.sh'" in entrypoint
    assert "set -x" not in entrypoint

    dashboard = json.loads(
        (ROOT / "infra/docker/grafana/dashboards/surgepilot-jmeter-13644.json").read_text(
            encoding="utf-8"
        )
    )
    assert dashboard["uid"] == "surgepilot-jmeter-13644"
    assert dashboard["panels"]
    run_id_var = next(item for item in dashboard["templating"]["list"] if item["name"] == "runId")
    assert run_id_var["type"] == "query"
    assert run_id_var["datasource"] == {"type": "influxdb", "uid": "InfluxDB-SurgePilot"}
    assert run_id_var["hide"] == 0
    assert run_id_var["includeAll"] is True
    assert run_id_var["allValue"] == ".*"
    assert run_id_var["current"]["text"] == "All"
    assert run_id_var["current"]["value"] == "$__all"
    assert "schema.measurementTagValues" in run_id_var.get("query", "")
    assert 'tag: "runId"' in run_id_var.get("query", "")


def test_monitoring_secret_mount_ownership_stays_deployment_level() -> None:
    compose = load_compose("docker-compose.yml")

    assert (
        compose["secrets"]["surgepilot_influxdb_token"]["file"]
        == "${SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE_HOST:-./monitoring/influxdb-token.example}"
    )
    assert (
        compose["services"]["api-worker"]["environment"][
            "SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE"
        ]
        == "/run/secrets/surgepilot_influxdb_token"
    )
    token_example = (ROOT / "infra/docker/monitoring/influxdb-token.example").read_text(
        encoding="utf-8"
    )
    assert token_example.strip() == "surgepilot-dev-token-change-me"


def test_nginx_proxies_grafana_behind_api_session_check_and_blocks_influxdb() -> None:
    config = (ROOT / "infra/docker/nginx/default.conf").read_text(encoding="utf-8")

    assert "location /grafana/" in config
    assert "auth_request /api/internal/v1/session-check;" in config
    assert "resolver 127.0.0.11 valid=10s ipv6=off;" in config
    assert "set $grafana_upstream http://grafana:3000;" in config
    assert "proxy_pass $grafana_upstream;" in config
    assert "proxy_pass http://grafana:3000;" not in config
    assert "location /influxdb/" not in config
    assert "proxy_pass http://influxdb" not in config
    assert "SURGEPILOT_MONITORING_INFLUXDB_TOKEN" not in config
    assert "influxdb-token" not in config


def test_monitoring_compose_smoke_script_uses_full_stack_and_checks_session_gate() -> None:
    script = (ROOT / "scripts/verify_p1_00_monitoring_compose.py").read_text(encoding="utf-8")

    assert 'os.environ.setdefault("RUNNER_INTERNAL_TOKEN", "surgepilot-e2e-runner-token")' in script
    assert '"MINIO_ACCESS_KEY": TEST_MINIO_ACCESS_KEY' in script
    assert '"MINIO_SECRET_KEY": TEST_MINIO_SECRET_KEY' in script
    assert '"MINIO_ROOT_USER": TEST_MINIO_ACCESS_KEY' in script
    assert '"MINIO_ROOT_PASSWORD": TEST_MINIO_SECRET_KEY' in script
    assert '"MINIO_BUCKET": TEST_MINIO_BUCKET' in script
    assert '"SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": INFLUXDB_NODE_WRITE_URL' in script
    assert "docker-compose.yml" in script
    assert "docker-compose.monitoring.yml" not in script
    assert "/api/healthz" in script
    assert "/health" in script
    assert "/grafana/" in script
    assert "theme=dark" in script
    assert "expected_status=(401, 403)" in script
    assert "/api/v1/monitoring/embed" in script
    assert "/grafana/api/datasources/uid/InfluxDB-SurgePilot" in script
    assert "http://influxdb:8086" in script
    assert "/grafana/api/dashboards/uid/surgepilot-jmeter-13644" in script


def test_makefile_exposes_monitoring_compose_verification() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "verify-p1-00-monitoring-compose:" in makefile
    assert "verify_p1_00_monitoring_compose.py" in makefile


def test_full_stack_compose_build_references_exist() -> None:
    compose = load_compose("docker-compose.yml")

    assert compose["services"]["api"]["build"]["dockerfile"] == "apps/api/Dockerfile"
    assert compose["services"]["api-worker"]["build"]["dockerfile"] == "apps/api/Dockerfile"
    assert compose["services"]["web"]["build"]["dockerfile"] == "apps/web/Dockerfile"
    assert (ROOT / "apps/api/Dockerfile").is_file()
    assert (ROOT / "apps/web/Dockerfile").is_file()
    assert (ROOT / "apps/web/nginx.conf").is_file()
    assert (ROOT / "infra/docker/nginx/default.conf").is_file()
