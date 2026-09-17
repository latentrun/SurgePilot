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
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    active_keys = {
        line.split("=", 1)[0]
        for line in env_example.splitlines()
        if line and not line.startswith("#") and "=" in line
    }

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
    assert "SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE_HOST" in active_keys
    assert "SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE" not in active_keys
    assert "SURGEPILOT_MONITORING_INFLUXDB_TOKEN=" not in env_example


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


def test_makefile_uses_base_for_light_profiles_and_full_for_dev_stack() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "COMPOSE_BASE=docker compose -f infra/docker/docker-compose.base.yml" in makefile
    assert "COMPOSE_FULL=docker compose -f infra/docker/docker-compose.yml" in makefile
    assert (
        "COMPOSE_FULL_SSH_E2E=$(COMPOSE_FULL) "
        "-f infra/docker/docker-compose.ssh-e2e.yml --profile ssh-e2e" in makefile
    )
    assert "dev-compose: start-full-stack" in makefile
    assert "release-runtime:" in makefile
    assert "start-full-stack:" in makefile
    assert "NODE_FACING_STARTUP=" in makefile
    assert "scripts/node_facing_startup.py" in makefile
    assert (
        "_start-full-stack-with-env:\n\t$(DEPLOYMENT_ENV_RUN) $(MAKE) _start-full-stack" in makefile
    )
    assert "$(MAKE) release-runtime" in makefile
    assert 'LOAD_NODE_RUNTIME_VERSION="$$LOAD_NODE_RUNTIME_VERSION"' in makefile
    assert "$(COMPOSE_FULL) config >/dev/null" in makefile
    assert "$(COMPOSE_FULL) up -d --build" in makefile
    assert "SURGEPILOT_SKIP_RUNTIME_PREFLIGHT" in makefile
    assert "seed-full-ssh-e2e-runtime:" in makefile
    assert "FULL_SSH_E2E_RUNTIME_BUILD_DIR ?=" in makefile
    assert "FULL_SSH_E2E_RUNTIME_CACHE_DIR ?=" in makefile
    assert "FULL_SSH_E2E_RUNTIME_ENV_FILE ?=" in makefile
    assert '--fixed-version "$(FULL_SSH_E2E_RUNTIME_VERSION)"' in makefile
    assert "scripts/seed_runtime_artifact_from_ssh_image.py" not in makefile
    assert "start-full-ssh-e2e: seed-full-ssh-e2e-runtime" in makefile
    assert "$(COMPOSE_FULL_SSH_E2E) build $(FULL_SSH_E2E_APP_BUILD_SERVICES)" in makefile
    assert "$(COMPOSE_FULL_SSH_E2E) up -d --no-build" in makefile
    assert "scripts/verify_full_ssh_e2e_node_connectivity.py" in makefile
    assert "start-full-ssh-e2e-build:" in makefile
    assert "verify_p1_00_monitoring_compose.py" in makefile
    assert "verify-p1-00-monitoring-ssh" in makefile
    assert "verify-p1-00-monitoring-remote-node-write" in makefile
    assert "SURGEPILOT_P1_MONITORING_REMOTE_WRITE" in makefile
    assert "Skipped is not release/nightly green evidence" in makefile
    assert "exit 77" in makefile
    assert "verify_p1_00_monitoring_remote_node_write.py --build-app" in makefile
    remote_write_block = makefile.split("\nverify-p1-00-monitoring-remote-node-write:", maxsplit=1)[
        1
    ].split("\n\n", maxsplit=1)[0]
    assert "SURGEPILOT_NODE_API_BASE_URL" in remote_write_block
    assert "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL" in remote_write_block
    assert "HOST_IP" not in remote_write_block
    assert "SURGEPILOT_E2E_HOST_IP" not in remote_write_block


def test_full_stack_compose_mounts_runtime_artifact_dir_for_api_and_worker() -> None:
    compose = load_compose("docker-compose.yml")
    expected_mount = (
        "${LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR:-../../.surgepilot/runtime-artifacts/default}"
        ":/opt/surgepilot/runtime-artifacts:ro"
    )

    for service_name in ("api", "api-worker"):
        service = compose["services"][service_name]
        environment = service["environment"]
        assert environment["LOAD_NODE_RUNTIME_VERSION"] == "${LOAD_NODE_RUNTIME_VERSION:-}"
        assert environment["LOAD_NODE_RUNTIME_ARTIFACT_DIR"] == "/opt/surgepilot/runtime-artifacts"
        assert expected_mount in service["volumes"]


def test_base_compose_mounts_runtime_artifact_dir_for_api_and_worker() -> None:
    compose = load_compose("docker-compose.base.yml")
    expected_mount = (
        "${LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR:-/tmp/surgepilot-runtime-artifacts}"
        ":/opt/surgepilot/runtime-artifacts:ro"
    )

    for service_name in ("api", "api-worker"):
        service = compose["services"][service_name]
        environment = service["environment"]
        assert environment["LOAD_NODE_RUNTIME_VERSION"] == "${LOAD_NODE_RUNTIME_VERSION:-}"
        assert environment["LOAD_NODE_RUNTIME_ARTIFACT_DIR"] == "/opt/surgepilot/runtime-artifacts"
        assert expected_mount in service["volumes"]


def test_remote_node_write_smoke_script_queries_required_measurements() -> None:
    script = (ROOT / "scripts/verify_p1_00_monitoring_remote_node_write.py").read_text(
        encoding="utf-8"
    )

    assert "requestsRaw" in script
    assert "virtualUsers" in script
    assert "testStartEnd" in script
    assert "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL" in script
    assert 'setdefault("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"' not in script
    assert "http://influxdb:8086" not in script
    assert "api/v2/query" in script
    assert "docker-compose.monitoring.yml" not in script

    service = (ROOT / "apps/api/app/services/monitoring.py").read_text(encoding="utf-8")
    properties_start = service.index("def build_monitoring_properties")
    properties_body = service[properties_start:]
    assert "row.influxdb_node_write_url" in properties_body
    assert "SURGEPILOT_NODE_ID" in properties_body
    assert "monitoring_influxdb_internal_url" not in properties_body


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
    assert "theme=dark" in script
    assert "/grafana/api/datasources/uid/InfluxDB-SurgePilot" in script
    assert "http://influxdb:8086" in script
    assert "/grafana/api/dashboards/uid/surgepilot-jmeter-13644" in script


def test_ssh_e2e_compose_includes_debian12_runtime_compat_node() -> None:
    compose = load_compose("docker-compose.ssh-e2e.yml")
    service = compose["services"]["ssh-load-node-debian12"]

    assert service["image"] == "docker-ssh-load-node-debian12:latest"
    assert service["build"]["dockerfile"] == "infra/docker/ssh-load-node-debian12/Dockerfile"
    assert service["profiles"] == ["runtime-compat"]
    assert "${SURGEPILOT_SSH_E2E_DEBIAN12_PORT:-22324}:22" in service["ports"]

    ubuntu_args = compose["services"]["ssh-load-node"]["build"]["args"]
    second_ubuntu_args = compose["services"]["ssh-load-node-2"]["build"]["args"]
    debian_args = service["build"]["args"]
    for args in (ubuntu_args, second_ubuntu_args, debian_args):
        assert args["HTTP_PROXY"] == "${SURGEPILOT_DOCKER_BUILD_HTTP_PROXY:-}"
        assert args["HTTPS_PROXY"] == "${SURGEPILOT_DOCKER_BUILD_HTTPS_PROXY:-}"
        assert args["NO_PROXY"] == "${SURGEPILOT_DOCKER_BUILD_NO_PROXY:-}"
        assert "APT_MIRROR" in args
        assert "APT_SECURITY_MIRROR" in args
    assert ubuntu_args["APT_MIRROR"] == "${SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_MIRROR:-}"
    assert (
        ubuntu_args["APT_SECURITY_MIRROR"]
        == "${SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_SECURITY_MIRROR:-}"
    )
    assert second_ubuntu_args["APT_MIRROR"] == "${SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_MIRROR:-}"
    assert (
        second_ubuntu_args["APT_SECURITY_MIRROR"]
        == "${SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_SECURITY_MIRROR:-}"
    )
    assert debian_args["APT_MIRROR"] == "${SURGEPILOT_DOCKER_BUILD_DEBIAN_APT_MIRROR:-}"
    assert (
        debian_args["APT_SECURITY_MIRROR"]
        == "${SURGEPILOT_DOCKER_BUILD_DEBIAN_APT_SECURITY_MIRROR:-}"
    )
    assert "TAURUS_VERSION" not in ubuntu_args
    assert "JMETER_DOWNLOAD_BASE" not in ubuntu_args
    assert "TAURUS_VERSION" not in second_ubuntu_args
    assert "JMETER_DOWNLOAD_BASE" not in second_ubuntu_args
