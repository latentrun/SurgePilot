from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = ROOT / ".env.example"
RELEASE_ENV_EXAMPLE = ROOT / "infra/release/.env.example"
E2E_ENV_EXAMPLE = ROOT / ".env.e2e.example"
DOCS_CONFIGURATIONS = (
    ROOT / "docs/site/docs/configuration.md",
    ROOT / "docs/site/docs/zh-CN/configuration.md",
    ROOT / "docs/site/docs/ja/configuration.md",
)
README = ROOT / "README.md"
MAKEFILE = ROOT / "Makefile"
COMPOSE_FILES = [
    ROOT / "infra/docker/docker-compose.yml",
    ROOT / "infra/docker/docker-compose.base.yml",
]
API_DOCKERFILE = ROOT / "apps/api/Dockerfile"
WEB_DOCKERFILE = ROOT / "apps/web/Dockerfile"
SSH_LOAD_NODE_DOCKERFILE = ROOT / "infra/docker/ssh-load-node/Dockerfile"
SSH_LOAD_NODE_DEBIAN12_DOCKERFILE = ROOT / "infra/docker/ssh-load-node-debian12/Dockerfile"
SSH_E2E_COMPOSE = ROOT / "infra/docker/docker-compose.ssh-e2e.yml"
COMPOSE_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::[-?][^}]*)?}")
ASSIGNMENT_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=")
COMMENTED_ASSIGNMENT_PATTERN = re.compile(r"^#\s*([A-Za-z_][A-Za-z0-9_]*)=")
DOCUMENTED_ENV_PATTERN = re.compile(r"`([A-Z][A-Z0-9_]*_[A-Z0-9_]+)`")
ACTIVE_DEPLOYMENT_KEYS = {
    "APP_ENV",
    "COMPOSE_PROJECT_NAME",
    "DATABASE_URL",
    "DEFAULT_WORKSPACE_NAME",
    "SURGEPILOT_API_HOST_PORT",
    "SURGEPILOT_DEMO_LOAD_NODE_ENABLED",
    "SURGEPILOT_HTTP_PORT",
    "SURGEPILOT_RUNTIME_ARCHITECTURES",
    "SURGEPILOT_GRAFANA_ADMIN_USER",
    "SURGEPILOT_MONITORING_INFLUXDB_BUCKET",
    "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT",
    "SURGEPILOT_MONITORING_INFLUXDB_ORG",
    "SURGEPILOT_MONITORING_INFLUXDB_PASSWORD",
    "SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE_HOST",
    "SURGEPILOT_MONITORING_INFLUXDB_USERNAME",
    "MINIO_ACCESS_KEY",
    "MINIO_BUCKET",
    "MINIO_ENDPOINT",
    "MINIO_ROOT_PASSWORD",
    "MINIO_ROOT_USER",
    "MINIO_SECRET_KEY",
    "POSTGRES_HOST_PORT",
    "RUNNER_INTERNAL_TOKEN",
    "SSH_CREDENTIAL_ENCRYPTION_KEY",
}
DIRECT_HOST_ONLY_ACTIVE_KEYS = {"APP_ENV", "DATABASE_URL", "MINIO_ENDPOINT"}
STARTUP_CONTROL_ACTIVE_KEYS = {
    "COMPOSE_PROJECT_NAME",
    "SURGEPILOT_DEMO_LOAD_NODE_ENABLED",
    "SURGEPILOT_HTTP_PORT",
    "SURGEPILOT_RUNTIME_ARCHITECTURES",
}
GENERATED_RUNTIME_KEYS = {
    "LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR",
    "LOAD_NODE_RUNTIME_VERSION",
}
DB_BACKED_FALLBACK_KEYS = {
    "ALLOW_SIGNUP",
    "DEPENDENCY_FILE_ALLOWED_EXTENSIONS",
    "DEPENDENCY_FILE_MAX_BYTES",
    "DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS",
    "DEPENDENCY_FILE_PREVIEW_MAX_BYTES",
    "SURGEPILOT_NODE_API_BASE_URL",
    "SURGEPILOT_JMETER_MEMORY_XMX",
    "SURGEPILOT_MAX_DELAY_SECONDS",
    "SURGEPILOT_MAX_ITERATIONS",
    "SURGEPILOT_MAX_RAMP_UP_SECONDS",
    "SURGEPILOT_MAX_RUN_DURATION_SECONDS",
    "SURGEPILOT_MAX_SCENARIO_ITEMS_PER_TEST_PLAN",
    "SURGEPILOT_MAX_SLA_RULES_PER_TEST_PLAN",
    "SURGEPILOT_MAX_TARGET_RPS",
    "SURGEPILOT_SINGLE_NODE_CONCURRENCY_SOFT_LIMIT",
}
ADVANCED_DEPLOYMENT_KEYS = {
    "SURGEPILOT_SKIP_RUNTIME_PREFLIGHT",
    "LOAD_NODE_DEFAULT_RUNNER_HOME",
    "LOAD_NODE_GENERATED_KEY_TYPE",
    "LOAD_NODE_INIT_COMMAND_TIMEOUT_SECONDS",
    "LOAD_NODE_INIT_LOG_TAIL_BYTES",
    "LOAD_NODE_INIT_TIMEOUT_SECONDS",
    "LOAD_NODE_RUNTIME_INSTALL_TIMEOUT_SECONDS",
    "LOAD_NODE_SSH_CONNECT_TIMEOUT_SECONDS",
    "SURGEPILOT_API_CATALOG_SPEC_MAX_BYTES",
    "SURGEPILOT_DEBUG_TRACE_ARTIFACT_MAX_BYTES",
    "SURGEPILOT_DEBUG_TRACE_BODY_BLOB_MAX_BYTES",
    "SURGEPILOT_DEBUG_TRACE_BODY_BLOB_TOTAL_MAX_BYTES",
    "SURGEPILOT_DEBUG_TRACE_BODY_MAX_BYTES",
    "SURGEPILOT_DEBUG_TRACE_MAX_REQUESTS",
    "SURGEPILOT_DEBUG_TRACE_RECORD_MAX_BYTES",
    "SURGEPILOT_GRAFANA_ROOT_URL",
    "SURGEPILOT_MONITORING_DASHBOARD_SLUG",
    "SURGEPILOT_MONITORING_DASHBOARD_UID",
    "SURGEPILOT_MONITORING_ENABLED",
    "SURGEPILOT_MONITORING_GRAFANA_BASE_PATH",
    "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL",
    "SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED",
    "SURGEPILOT_MONITORING_TIME_PADDING_SECONDS",
    "SURGEPILOT_NODE_COOLDOWN_SECONDS",
    "SURGEPILOT_RUNNER_CALLBACK_RETENTION_DAYS",
    "SURGEPILOT_RUN_ACCEPTED_TIMEOUT_SECONDS",
    "SURGEPILOT_RUN_ARTIFACT_MAX_BYTES",
    "SURGEPILOT_RUN_CONTROL_STALE_SECONDS",
    "SURGEPILOT_RUN_FORCE_KILL_SSH_TIMEOUT_SECONDS",
    "SURGEPILOT_RUN_HEARTBEAT_TIMEOUT_SECONDS",
    "SURGEPILOT_RUN_STOP_GRACE_SECONDS",
    "SURGEPILOT_RUN_TERMINAL_LATE_ARTIFACT_MAX_BYTES",
    "SURGEPILOT_RUN_TERMINAL_LATE_ARTIFACT_SECONDS",
    "SURGEPILOT_SINGLE_NODE_CONCURRENCY_HARD_LIMIT",
    "MINIO_REGION",
    "MINIO_SECURE",
    "RUNTIME_CASUTG_SHA256",
    "RUNTIME_INFLUXDB2_LISTENER_SHA256",
    "RUNTIME_JSON_SHA256",
    "RUNTIME_JMETER_SHA256",
    "RUNTIME_RANDOM_CSV_SHA256",
    "RUNTIME_TST_SHA256",
    "VITE_API_BASE_URL",
}
NON_COMPOSE_ADVANCED_KEYS = {
    "SURGEPILOT_SKIP_RUNTIME_PREFLIGHT",
    "SURGEPILOT_MONITORING_ENABLED",
    "SURGEPILOT_MONITORING_GRAFANA_BASE_PATH",
    "SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED",
    "MINIO_REGION",
    "MINIO_SECURE",
    "RUNTIME_CASUTG_SHA256",
    "RUNTIME_INFLUXDB2_LISTENER_SHA256",
    "RUNTIME_JSON_SHA256",
    "RUNTIME_JMETER_SHA256",
    "RUNTIME_RANDOM_CSV_SHA256",
    "RUNTIME_TST_SHA256",
    "VITE_API_BASE_URL",
}
OPTIONAL_MIRROR_EXAMPLES = {
    "SURGEPILOT_PIP_INDEX_URL": "https://mirrors.aliyun.com/pypi/simple/",
    "SURGEPILOT_NPM_REGISTRY": "https://registry.npmmirror.com/",
    "SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_MIRROR": "http://example.invalid/ubuntu",
    "SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_SECURITY_MIRROR": "http://example.invalid/ubuntu",
    "SURGEPILOT_DOCKER_BUILD_DEBIAN_APT_MIRROR": "http://example.invalid/debian",
    "SURGEPILOT_DOCKER_BUILD_DEBIAN_APT_SECURITY_MIRROR": (
        "http://example.invalid/debian-security"
    ),
}
E2E_BUILD_PROXY_EXAMPLES = {
    "SURGEPILOT_DOCKER_BUILD_HTTP_PROXY": "http://proxy.example.invalid:3128",
    "SURGEPILOT_DOCKER_BUILD_HTTPS_PROXY": "http://proxy.example.invalid:3128",
    "SURGEPILOT_DOCKER_BUILD_NO_PROXY": "localhost,127.0.0.1",
}
COMMENTED_OPTIONAL_KEYS = ADVANCED_DEPLOYMENT_KEYS | set(OPTIONAL_MIRROR_EXAMPLES)
COMPOSE_ENV_OWNERSHIP = {
    "active_deployment": ACTIVE_DEPLOYMENT_KEYS,
    "commented_optional": COMMENTED_OPTIONAL_KEYS,
    "generated_runtime": GENERATED_RUNTIME_KEYS,
    "db_backed_fallback": DB_BACKED_FALLBACK_KEYS,
}
NODE_LOCAL_RUNNER_KEYS = {
    "SURGEPILOT_RUNNER_ARCHIVE_MAX_BYTES",
    "SURGEPILOT_RUNNER_HEARTBEAT_INTERVAL_SECONDS",
    "RUNNER_HOME",
}
HARDCODED_CONTAINER_TOPOLOGY_KEYS = {
    "APP_BASE_URL",
    "SURGEPILOT_RUNNER_BUNDLE_DIR",
    "LOAD_NODE_RUNTIME_ARTIFACT_DIR",
    "SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE",
}
E2E_ACTIVE_KEYS = {
    "KEEP_DATA",
    "KEEP_STACK",
    "SURGEPILOT_E2E_API_ORCHESTRATION_URL",
    "SURGEPILOT_E2E_HOST_IP",
    "SURGEPILOT_E2E_NODE_SSH_HOST",
    "SURGEPILOT_E2E_NODE_SSH_PORT",
    "SURGEPILOT_E2E_TARGET_URL",
    "SURGEPILOT_NODE_API_BASE_URL",
    "SURGEPILOT_SSH_E2E_PORT",
    "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT",
    "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL",
}


def env_example_text() -> str:
    return ENV_EXAMPLE.read_text(encoding="utf-8")


def env_example_keys() -> list[str]:
    return assignment_keys(ENV_EXAMPLE)


def assignment_keys(path: Path) -> list[str]:
    keys: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = ASSIGNMENT_PATTERN.match(stripped)
        if match:
            keys.append(match.group(1))
    return keys


def commented_env_example_keys(path: Path = ENV_EXAMPLE) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = COMMENTED_ASSIGNMENT_PATTERN.match(line.strip())
        if match:
            keys.add(match.group(1))
    return keys


def template_keys(path: Path) -> set[str]:
    return set(assignment_keys(path)) | commented_env_example_keys(path)


def compose_texts() -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in COMPOSE_FILES}


def compose_env_vars() -> set[str]:
    variables: set[str] = set()
    for compose in compose_texts().values():
        variables.update(COMPOSE_VAR_PATTERN.findall(compose))
    return variables


def test_env_example_has_no_duplicate_keys() -> None:
    keys = env_example_keys()
    duplicates = sorted({key for key in keys if keys.count(key) > 1})

    assert duplicates == []


def test_repository_keeps_one_deployment_example_and_one_e2e_example() -> None:
    assert {path.name for path in ROOT.glob(".env*.example")} == {
        ".env.e2e.example",
        ".env.example",
    }


def test_user_configuration_reference_covers_source_and_release_templates() -> None:
    expected = template_keys(ENV_EXAMPLE) | template_keys(RELEASE_ENV_EXAMPLE)

    for configuration in DOCS_CONFIGURATIONS:
        documented = set(DOCUMENTED_ENV_PATTERN.findall(configuration.read_text(encoding="utf-8")))

        assert documented == expected, configuration.relative_to(ROOT)


def test_env_example_active_keys_match_deployment_ownership() -> None:
    assert set(env_example_keys()) == ACTIVE_DEPLOYMENT_KEYS


def test_env_example_comment_keys_match_non_active_ownership() -> None:
    expected = COMMENTED_OPTIONAL_KEYS | GENERATED_RUNTIME_KEYS | DB_BACKED_FALLBACK_KEYS

    assert commented_env_example_keys() == expected


def test_e2e_env_example_contains_only_test_overrides() -> None:
    assert set(assignment_keys(E2E_ENV_EXAMPLE)) == E2E_ACTIVE_KEYS


def test_compose_env_ownership_categories_do_not_overlap() -> None:
    categories = list(COMPOSE_ENV_OWNERSHIP.values())
    for index, category in enumerate(categories):
        for other in categories[index + 1 :]:
            assert category.isdisjoint(other)


def test_runner_internal_token_has_single_authoritative_example() -> None:
    assert env_example_keys().count("RUNNER_INTERNAL_TOKEN") == 1

    for compose_file, compose in compose_texts().items():
        assert "RUNNER_INTERNAL_TOKEN: change-me" not in compose, compose_file
        assert (
            compose.count(
                "RUNNER_INTERNAL_TOKEN: ${RUNNER_INTERNAL_TOKEN:?RUNNER_INTERNAL_TOKEN is required}"
            )
            == 2
        ), compose_file

        parsed = yaml.safe_load(compose)
        assert "RUNNER_INTERNAL_TOKEN" not in parsed["services"]["api-migrate"]["environment"]
        assert "RUNNER_INTERNAL_TOKEN" in parsed["services"]["api"]["environment"]
        assert "RUNNER_INTERNAL_TOKEN" in parsed["services"]["api-worker"]["environment"]


def test_ssh_credential_encryption_key_is_required_by_api_services() -> None:
    required_value = (
        "SSH_CREDENTIAL_ENCRYPTION_KEY: "
        "${SSH_CREDENTIAL_ENCRYPTION_KEY:?SSH_CREDENTIAL_ENCRYPTION_KEY is required}"
    )

    for compose_file, compose in compose_texts().items():
        assert compose.count(required_value) == 2, compose_file

        parsed = yaml.safe_load(compose)
        assert (
            "SSH_CREDENTIAL_ENCRYPTION_KEY" not in parsed["services"]["api-migrate"]["environment"]
        )
        assert "SSH_CREDENTIAL_ENCRYPTION_KEY" in parsed["services"]["api"]["environment"]
        assert "SSH_CREDENTIAL_ENCRYPTION_KEY" in parsed["services"]["api-worker"]["environment"]


def test_api_runtime_services_disable_uv_dependency_sync() -> None:
    for compose_file in COMPOSE_FILES:
        services = yaml.safe_load(compose_file.read_text(encoding="utf-8"))["services"]

        assert services["api"]["environment"]["UV_NO_SYNC"] == "1"
        assert services["api-worker"]["environment"]["UV_NO_SYNC"] == "1"
        assert "UV_NO_SYNC" not in services["api-migrate"]["environment"]


def test_api_migrate_receives_only_migration_required_configuration() -> None:
    for compose_file in COMPOSE_FILES:
        services = yaml.safe_load(compose_file.read_text(encoding="utf-8"))["services"]

        assert set(services["api-migrate"]["environment"]) == {"APP_ENV", "DATABASE_URL"}


def test_compose_variables_are_documented_in_env_example() -> None:
    owned = set().union(*COMPOSE_ENV_OWNERSHIP.values())

    assert sorted(compose_env_vars() - owned) == []


def test_documented_deployment_and_db_fallback_keys_reach_compose() -> None:
    compose_variables = compose_env_vars()

    assert (
        ACTIVE_DEPLOYMENT_KEYS - DIRECT_HOST_ONLY_ACTIVE_KEYS - STARTUP_CONTROL_ACTIVE_KEYS
        <= compose_variables
    )
    assert DB_BACKED_FALLBACK_KEYS <= compose_variables
    assert ADVANCED_DEPLOYMENT_KEYS - NON_COMPOSE_ADVANCED_KEYS <= compose_variables


def test_api_and_worker_share_minio_client_credentials() -> None:
    expected_access_key = "${MINIO_ACCESS_KEY:-minioadmin}"
    expected_secret_key = "${MINIO_SECRET_KEY:-minioadmin}"

    for compose_file in COMPOSE_FILES:
        services = yaml.safe_load(compose_file.read_text(encoding="utf-8"))["services"]
        for service_name in ("api", "api-worker"):
            environment = services[service_name]["environment"]
            assert environment["MINIO_ACCESS_KEY"] == expected_access_key
            assert environment["MINIO_SECRET_KEY"] == expected_secret_key


def test_db_backed_fallbacks_are_comments_not_active_assignments() -> None:
    assert DB_BACKED_FALLBACK_KEYS <= commented_env_example_keys()
    assert DB_BACKED_FALLBACK_KEYS.isdisjoint(env_example_keys())


def test_generated_runtime_values_are_comments_not_active_assignments() -> None:
    assert GENERATED_RUNTIME_KEYS <= commented_env_example_keys()
    assert GENERATED_RUNTIME_KEYS.isdisjoint(env_example_keys())


def test_container_topology_and_node_local_runner_values_are_not_deployment_assignments() -> None:
    active = set(env_example_keys())

    assert HARDCODED_CONTAINER_TOPOLOGY_KEYS.isdisjoint(active)
    assert NODE_LOCAL_RUNNER_KEYS.isdisjoint(active)


def test_web_containers_do_not_set_runtime_vite_api_base_url() -> None:
    for compose_file in COMPOSE_FILES:
        compose = yaml.safe_load(compose_file.read_text(encoding="utf-8"))
        web = compose["services"]["web"]
        assert "VITE_API_BASE_URL" not in web.get("environment", {})
        assert web["build"]["args"]["VITE_API_BASE_URL"] == "${VITE_API_BASE_URL:-}"

    dockerfile = WEB_DOCKERFILE.read_text(encoding="utf-8")
    assert "ARG VITE_API_BASE_URL=" in dockerfile


def test_optional_build_mirror_examples_are_documented_as_comments() -> None:
    text = env_example_text()

    for key, example in OPTIONAL_MIRROR_EXAMPLES.items():
        assert f"# {key}={example}" in text
        assert key not in env_example_keys()


def test_ssh_e2e_build_proxy_examples_are_documented_as_comments() -> None:
    text = E2E_ENV_EXAMPLE.read_text(encoding="utf-8")

    for key, example in E2E_BUILD_PROXY_EXAMPLES.items():
        assert f"# {key}={example}" in text
        assert key not in commented_env_example_keys(ENV_EXAMPLE)
        assert key not in env_example_keys()


def test_api_image_build_mirror_args_are_wired() -> None:
    dockerfile = API_DOCKERFILE.read_text(encoding="utf-8")
    assert "ARG PIP_INDEX_URL=https://pypi.org/simple" in dockerfile
    assert "ARG UV_INDEX_URL=https://pypi.org/simple" in dockerfile
    assert "ENV PIP_INDEX_URL=${PIP_INDEX_URL}" in dockerfile
    assert "ENV UV_INDEX_URL=${UV_INDEX_URL}" in dockerfile

    for compose_file, compose in compose_texts().items():
        assert "PIP_INDEX_URL: ${SURGEPILOT_PIP_INDEX_URL:-https://pypi.org/simple}" in compose, (
            compose_file
        )
        assert "UV_INDEX_URL: ${SURGEPILOT_PIP_INDEX_URL:-https://pypi.org/simple}" in compose, (
            compose_file
        )


def test_web_image_build_mirror_arg_is_wired() -> None:
    dockerfile = WEB_DOCKERFILE.read_text(encoding="utf-8")
    assert "ARG NPM_REGISTRY=https://registry.npmjs.org/" in dockerfile
    assert 'pnpm config set registry "$NPM_REGISTRY"' in dockerfile

    for compose_file, compose in compose_texts().items():
        assert "NPM_REGISTRY: ${SURGEPILOT_NPM_REGISTRY:-https://registry.npmjs.org/}" in compose, (
            compose_file
        )


def test_ssh_load_node_apt_build_mirror_args_are_wired() -> None:
    ubuntu_dockerfile = SSH_LOAD_NODE_DOCKERFILE.read_text(encoding="utf-8")
    debian_dockerfile = SSH_LOAD_NODE_DEBIAN12_DOCKERFILE.read_text(encoding="utf-8")
    ssh_compose = SSH_E2E_COMPOSE.read_text(encoding="utf-8")

    for dockerfile in (ubuntu_dockerfile, debian_dockerfile):
        assert "ARG APT_MIRROR" in dockerfile
        assert "ARG APT_SECURITY_MIRROR" in dockerfile
        assert "must start with http:// or https://" in dockerfile
        assert "must not contain whitespace" in dockerfile
        assert "escape_sed_replacement()" in dockerfile
        assert "sed 's/[\\\\&|]/\\\\&/g'" in dockerfile
        assert "[ -d /etc/apt/sources.list.d ]" in dockerfile
        assert "apt-get -o Acquire::Retries=3 update" in dockerfile
        assert "apt-get -o Acquire::Retries=3 install" in dockerfile

    assert r"archive\\.ubuntu\\.com/ubuntu" in ubuntu_dockerfile
    assert r"security\\.ubuntu\\.com/ubuntu" in ubuntu_dockerfile
    assert 'apt_security_mirror="$apt_mirror"' in ubuntu_dockerfile
    assert r"deb\\.debian\\.org/debian" in debian_dockerfile
    assert "debian-security" in debian_dockerfile
    assert 'apt_security_mirror="$apt_mirror"' not in debian_dockerfile
    assert "APT_MIRROR: ${SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_MIRROR:-}" in ssh_compose
    assert (
        "APT_SECURITY_MIRROR: ${SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_SECURITY_MIRROR:-}"
        in ssh_compose
    )
    assert "APT_MIRROR: ${SURGEPILOT_DOCKER_BUILD_DEBIAN_APT_MIRROR:-}" in ssh_compose
    assert (
        "APT_SECURITY_MIRROR: ${SURGEPILOT_DOCKER_BUILD_DEBIAN_APT_SECURITY_MIRROR:-}"
        in ssh_compose
    )


def test_runtime_host_dir_defaults_are_compose_specific_and_sample_is_generated_only() -> None:
    full = COMPOSE_FILES[0].read_text(encoding="utf-8")
    base = COMPOSE_FILES[1].read_text(encoding="utf-8")

    assert (
        "${LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR:-../../.surgepilot/runtime-artifacts/default}"
        in full
    )
    assert "${LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR:-/tmp/surgepilot-runtime-artifacts}" in base
    assert "# LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR=" in env_example_text()
    assert "LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR" not in env_example_keys()


def test_make_verify_injects_test_only_required_secrets() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert "VERIFY_RUNNER_INTERNAL_TOKEN ?= surgepilot-verification-token" in makefile
    assert (
        "VERIFY_SSH_CREDENTIAL_ENCRYPTION_KEY ?= "
        "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=" in makefile
    )
    assert "VERIFY_MINIO_ENV=MINIO_BUCKET=surgepilot" in makefile
    assert "MINIO_SECRET_KEY=surgepilot-verification-minio-secret" in makefile
    assert (
        "VERIFY_COMPOSE_ENV=RUNNER_INTERNAL_TOKEN=$(VERIFY_RUNNER_INTERNAL_TOKEN) "
        "SSH_CREDENTIAL_ENCRYPTION_KEY=$(VERIFY_SSH_CREDENTIAL_ENCRYPTION_KEY)" in makefile
    )
    assert "$(VERIFY_COMPOSE_ENV) $(COMPOSE_DEV)" in makefile
    assert "$(VERIFY_COMPOSE_ENV) $(COMPOSE_SMOKE) config" in makefile
    assert "$(VERIFY_COMPOSE_ENV) $(COMPOSE_FULL) config" in makefile
    assert "$(VERIFY_COMPOSE_ENV) $(COMPOSE_SSH_E2E) up" in makefile
    assert "$(VERIFY_COMPOSE_ENV) $(COMPOSE_SSH_E2E) down" in makefile
    assert "$(VERIFY_COMPOSE_ENV) $(COMPOSE_DEV) up -d minio minio-init" in makefile
    assert "$(VERIFY_MINIO_ENV) MINIO_ENDPOINT=http://localhost:9000 pnpm e2e" in makefile
    assert "$(VERIFY_COMPOSE_ENV) $(COMPOSE_DEV) stop minio minio-init" in makefile
    assert "$(VERIFY_COMPOSE_ENV) $(COMPOSE_DEV) rm -f -v minio minio-init" in makefile
    assert "$(VERIFY_COMPOSE_ENV) $(COMPOSE_BASE)" in makefile
    assert (
        "$(VERIFY_COMPOSE_ENV) uv run --all-packages python "
        "scripts/verify_runtime_compat_node.py" in makefile
    )
    full_ssh_env = next(
        line for line in makefile.splitlines() if line.startswith("FULL_SSH_E2E_ENV=")
    )
    assert "$(VERIFY_COMPOSE_ENV)" in full_ssh_env


def test_make_host_and_runtime_targets_load_the_root_deployment_env() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert (
        'BOOTSTRAP_DEPLOYMENT_ENV=python3 scripts/bootstrap_deployment_env.py --root "$(CURDIR)"'
        in makefile
    )
    assert (
        "DEPLOYMENT_ENV_RUN=$(if $(wildcard $(CURDIR)/.env),uv run --all-packages dotenv "
        '-f "$(CURDIR)/.env" run --no-override --,)' in makefile
    )
    assert "dev-web:\n\t$(DEPLOYMENT_ENV_RUN) pnpm --filter @surgepilot/web dev" in makefile
    assert "dev-api:\n\t$(DEPLOYMENT_ENV_RUN) cd apps/api" not in makefile
    assert (
        "dev-api:\n\t$(DEPLOYMENT_ENV_RUN) uv run --directory apps/api fastapi dev app/main.py"
        in makefile
    )
    assert (
        "dev-worker:\n\t$(DEPLOYMENT_ENV_RUN) uv run --directory apps/api python -m app.worker"
        in makefile
    )
    assert "release-runtime:\n\t$(DEPLOYMENT_ENV_RUN) $(MAKE) _release-runtime" in makefile
    assert (
        "start-full-stack:\n\t$(BOOTSTRAP_DEPLOYMENT_ENV)\n"
        "\t$(MAKE) _start-full-stack-with-env" in makefile
    )
    assert (
        "start-preview:\n\t$(BOOTSTRAP_DEPLOYMENT_ENV)\n"
        "\t$(MAKE) _start-preview-with-env" in makefile
    )
    assert "_start-preview-with-env:\n\t$(DEPLOYMENT_ENV_RUN) $(MAKE) _start-preview" in makefile
    assert (
        "_start-full-stack-with-env:\n\t$(DEPLOYMENT_ENV_RUN) $(MAKE) _start-full-stack" in makefile
    )
    assert (
        "restart-full-stack:\n\t$(BOOTSTRAP_DEPLOYMENT_ENV)\n"
        "\t$(MAKE) _restart-full-stack-with-env" in makefile
    )
    assert (
        "_restart-full-stack-with-env:\n\t$(DEPLOYMENT_ENV_RUN) $(MAKE) _restart-full-stack"
        in makefile
    )
    assert (
        "seed-full-ssh-e2e-runtime:\n"
        "\t$(DEPLOYMENT_ENV_RUN) $(MAKE) _seed-full-ssh-e2e-runtime" in makefile
    )
    assert (
        "start-full-ssh-e2e:\n\t$(FULL_SSH_E2E_ENV) $(DEPLOYMENT_ENV_RUN) "
        "$(NODE_FACING_STARTUP) "
        "$(MAKE) _start-full-ssh-e2e" in makefile
    )
    assert (
        "restart-full-ssh-e2e:\n\t$(FULL_SSH_E2E_ENV) $(DEPLOYMENT_ENV_RUN) "
        "$(NODE_FACING_STARTUP) "
        "$(MAKE) _restart-full-ssh-e2e" in makefile
    )
    assert (
        "start-full-ssh-e2e-build:\n\t$(FULL_SSH_E2E_ENV) $(DEPLOYMENT_ENV_RUN) "
        "$(NODE_FACING_STARTUP) "
        "$(MAKE) _start-full-ssh-e2e-build" in makefile
    )
    assert (
        "restart-full-ssh-e2e-build:\n\t$(FULL_SSH_E2E_ENV) $(DEPLOYMENT_ENV_RUN) "
        "$(NODE_FACING_STARTUP) "
        "$(MAKE) _restart-full-ssh-e2e-build" in makefile
    )
    assert (
        "migrate:\n\t$(DEPLOYMENT_ENV_RUN) uv run --directory apps/api alembic upgrade head"
        in makefile
    )
    assert (
        "migration:\n\t$(DEPLOYMENT_ENV_RUN) uv run --directory apps/api alembic revision"
        in makefile
    )
    assert "$(VERIFY_MINIO_ENV) $(MAKE) verify-p0-api-main-flow-e2e" in makefile
    assert "$(VERIFY_MINIO_ENV) $(MAKE) verify-p0-06-runner-ssh" in makefile


def test_readme_uses_the_concise_deployment_quickstart_and_doc_router() -> None:
    readme = README.read_text(encoding="utf-8")

    ordered_sections = (
        "## Highlights",
        "## What SurgePilot Does",
        "## Built 100% by AI",
        "## Architecture",
        "## Main Capabilities",
        "## AI-Native: Drive SurgePilot From Your Agent",
        "## Quick Start",
        "### Start from source",
        "## Benchmarking New Models With This Repository",
        "## Documentation",
        "### For users",
        "### For contributors and reviewers",
        "## Contributing",
        "## License",
    )
    section_indexes = [readme.index(section) for section in ordered_sections]
    assert section_indexes == sorted(section_indexes)

    for removed_section in (
        "## AI-Native Operation",
        "## Your First Load Test",
        "## Local Development",
        "## Verification & Contracts",
        "## Governance & Contributing",
        "## Documentation Map",
    ):
        assert removed_section not in readme

    source_start = readme.index("### Start from source")
    source_end = readme.index("## Benchmarking New Models With This Repository", source_start)
    source_quickstart = readme[source_start:source_end]
    source_text = " ".join(source_quickstart.split())
    setup_index = source_quickstart.index("make setup")
    start_index = source_quickstart.index("make start-full-stack")
    preview_index = source_quickstart.index("make start-preview")

    assert setup_index < start_index < preview_index
    assert "For development or a complete local source execution path" in source_text
    assert "native Linux Runtime" in source_text
    assert "without Runtime or Run readiness" in source_text
    assert "Prerequisites: Docker Engine/Desktop 26 or newer" in readme
    assert "downloads validated Linux Runtime assets" in readme
    assert "New release deployments keep the Demo Load Node disabled by default" in readme
    assert "cp .env.example .env" not in readme
    assert (
        "curl -fsSL https://github.com/latentrun/SurgePilot/releases/latest/download/"
        "install.sh | sh" in readme
    )
    assert "surgepilot up" in readme
    assert "Coming soon — not yet available" not in readme
    assert "https://surgepilot.dev/install.sh |" not in readme


def test_source_preview_governance_is_synchronized_with_authoritative_workflow() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    workflow = (ROOT / "docs/sdd/02-repo-structure-and-dev-workflow.md").read_text(encoding="utf-8")

    assert (
        "P2-05-cross-platform-distribution.md` is active only through `ADR-0017` plus source "
        "preview through `ADR-0019`" in agents
    )
    assert "ADR-0019-p2-source-preview-startup.md" in workflow
    assert (
        "P2-05 is allowed only through ADR-0017, source preview through ADR-0019, user-local "
        "installation through ADR-0024" in workflow
    )
    assert (
        "P2-05 authorizes only the complete GHCR/GitHub Release platform distribution"
        not in workflow
    )


def test_release_dual_runtime_default_governance_is_synchronized() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    workflow = (ROOT / "docs/sdd/02-repo-structure-and-dev-workflow.md").read_text(encoding="utf-8")
    adr_index = (ROOT / "docs/sdd/adr/README.md").read_text(encoding="utf-8")
    distribution_adr = (ROOT / "docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md").read_text(
        encoding="utf-8"
    )
    dual_runtime_adr = (
        ROOT / "docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md"
    ).read_text(encoding="utf-8")
    distribution_slice = (ROOT / "docs/sdd/slices/P2-05-cross-platform-distribution.md").read_text(
        encoding="utf-8"
    )
    normalized_distribution_adr = " ".join(distribution_adr.split())
    normalized_distribution_slice = " ".join(distribution_slice.split())

    assert "ADR-0020-p2-release-dual-runtime-default.md" in agents
    assert "ADR-0020-p2-release-dual-runtime-default.md" in workflow
    assert "ADR-0020-p2-release-dual-runtime-default.md" in adr_index
    assert "new tagged-release deployments default to `amd64,arm64`" in workflow
    assert "ADR-0020-p2-release-dual-runtime-default.md" in distribution_adr
    assert "ADR-0017 Decision 8" in dual_runtime_adr
    assert (
        "Decision 8 is partially superseded by `ADR-0020` only for the missing-`.env` "
        "tagged-release default and first-run Runtime architecture prompt"
        in normalized_distribution_adr
    )
    assert "SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64" in distribution_adr
    assert (
        "Existing `.env` values remain authoritative, and `auto`, `amd64`, `arm64`, and "
        "`amd64,arm64` remain accepted advanced values" in normalized_distribution_adr
    )
    assert (
        "`SURGEPILOT_RUNTIME_ARCHITECTURES=auto` remains the normal default"
        not in normalized_distribution_adr
    )
    assert "ADR-0020-p2-release-dual-runtime-default.md" in distribution_slice
    assert "SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64" in distribution_slice
    assert "does not ask for Runtime architectures" in distribution_slice
    assert "Existing release `.env` files remain authoritative" in distribution_slice
    assert (
        "`auto`, `amd64`, `arm64`, and `amd64,arm64` remain accepted advanced values"
        in normalized_distribution_slice
    )
    assert "native `auto` development-validation smoke" in distribution_slice
    assert "formal dual-default tagged-release smoke" in distribution_slice

    stale_normative_claims = (
        "The normal complete release uses the default Runtime architecture value `auto`.",
        "collect explicit LAN/port/Runtime inputs",
        "The first-run quickstart asks for the Runtime set with `auto` as the default.",
        "`SURGEPILOT_RUNTIME_ARCHITECTURES=auto` is the only normal default",
        "prompts for one LAN host, HTTP port, InfluxDB port, and Runtime set",
        "using the same location and file set as the formal `release-smoke` job",
    )
    for claim in stale_normative_claims:
        assert claim not in normalized_distribution_slice


def test_release_up_configuration_confirmation_governance_is_synchronized() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    workflow = (ROOT / "docs/sdd/02-repo-structure-and-dev-workflow.md").read_text(encoding="utf-8")
    adr_index = (ROOT / "docs/sdd/adr/README.md").read_text(encoding="utf-8")
    adr_0017 = (ROOT / "docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md").read_text(
        encoding="utf-8"
    )
    adr_0018 = (ROOT / "docs/sdd/adr/ADR-0018-p2-lan-first-release-bootstrap.md").read_text(
        encoding="utf-8"
    )
    adr_0020 = (ROOT / "docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md").read_text(
        encoding="utf-8"
    )
    adr_0021 = (
        ROOT / "docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md"
    ).read_text(encoding="utf-8")
    p2_05 = (ROOT / "docs/sdd/slices/P2-05-cross-platform-distribution.md").read_text(
        encoding="utf-8"
    )
    p2_06 = (ROOT / "docs/sdd/slices/P2-06-lan-first-deployment-usability.md").read_text(
        encoding="utf-8"
    )

    assert "ADR-0021-p2-release-up-configuration-confirmation.md" in agents
    assert "ADR-0021-p2-release-up-configuration-confirmation.md" in workflow
    assert "ADR-0021-p2-release-up-configuration-confirmation.md" in adr_index
    assert "ADR-0021-p2-release-up-configuration-confirmation.md" in p2_05
    assert (
        "interactive No/re-entry/Yes may update only four standard-LAN network fields"
        in " ".join(p2_05.split())
    )
    assert "Use this configuration? [Y/n]" in p2_06
    assert "four allowlisted network fields" in p2_06
    assert "automatic and non-interactive rewriting remains forbidden" in adr_0021
    normalized_adr = " ".join(adr_0021.split())
    normalized_p2_05 = " ".join(p2_05.split())
    normalized_p2_06 = " ".join(p2_06.split())
    normalized_workflow = " ".join(workflow.split())
    normalized_agents = " ".join(agents.split())
    for document in (normalized_adr, normalized_p2_05, normalized_p2_06):
        assert "standard `os.replace`" in document
        assert "simultaneous manual same-user editing" in document.lower()
    assert "not a strict compare-and-swap" in normalized_adr
    assert "no backup or automatic rollback" in normalized_adr
    assert "updated but durability could not be confirmed; inspect `.env`" in normalized_adr
    assert "final pre-replacement SHA-256 check" in normalized_workflow
    assert "standard `os.replace`" in normalized_agents
    stale_strict_guarantees = (
        "Any failure leaves the original file intact",
        "any failure leaves the original intact",
        "atomic commit boundary",
        "strict compare-and-swap guarantee",
    )
    for claim in stale_strict_guarantees:
        assert claim not in adr_0021
        assert claim not in p2_06
    for document in (adr_0017, adr_0018, adr_0020):
        assert "ADR-0021-p2-release-up-configuration-confirmation.md" in document


def test_env_example_keeps_only_final_node_facing_url_overrides() -> None:
    env_example = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "# SURGEPILOT_NODE_API_BASE_URL=http://192.168.1.20:8080" in env_example
    assert "# SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://192.168.1.20:8086" in env_example
    assert "SURGEPILOT_MONITORING_INFLUXDB_INTERNAL_URL" not in env_example
    assert "SURGEPILOT_HOST_IP" not in env_example
    assert "SURGEPILOT_HOST_IP" not in env_example
    assert "default complete stack uses Compose-internal origins" in env_example
    assert "derive" not in env_example
