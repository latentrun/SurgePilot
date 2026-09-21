import subprocess
from pathlib import Path
import socket


ROOT = Path(__file__).resolve().parents[2]
TEST_SSH_CREDENTIAL_ENCRYPTION_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="


def free_host_ports() -> tuple[int, int]:
    ports: list[int] = []
    while len(ports) < 2:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            port = int(listener.getsockname()[1])
        if port not in ports:
            ports.append(port)
    return ports[0], ports[1]


def test_make_help_lists_e2e_and_contract_stale_commands() -> None:
    result = subprocess.run(
        ["make", "help"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "make verify-e2e" in result.stdout
    assert "make contracts-stale-check" in result.stdout
    assert "make verify-runtime-compat" in result.stdout
    assert "make ai-skill-tests" in result.stdout


def test_contracts_stale_check_includes_public_api_skill_snapshot() -> None:
    makefile = (ROOT / "Makefile").read_text()
    stale_block = makefile.split("\ncontracts-stale-check:", maxsplit=1)[1].split(
        "\n\nverify:", maxsplit=1
    )[0]

    assert "cp -R packages/contracts/openapi" in makefile
    assert 'diff -ru "$$tmp_dir/openapi" packages/contracts/openapi' in makefile
    assert 'diff -ru "$$tmp_dir/generated" packages/contracts/generated' in makefile
    assert (
        "cp packages/ai-skills/surgepilot-public-api/references/public-api.openapi.json" in makefile
    )
    assert (
        'diff -u "$$tmp_dir/public-api-skill.openapi.json" '
        "packages/ai-skills/surgepilot-public-api/references/public-api.openapi.json" in makefile
    )
    assert "@set -e;" in stale_block
    assert "trap 'rm -rf" in stale_block


def test_makefile_refreshes_and_tests_public_api_skill() -> None:
    makefile = (ROOT / "Makefile").read_text()
    generate_block = makefile.split("\ngenerate-contracts:", maxsplit=1)[1].split(
        "\nlint:", maxsplit=1
    )[0]
    test_block = makefile.split("\ntest:", maxsplit=1)[1].split("\napi-coverage:", maxsplit=1)[0]

    assert (
        "cp packages/contracts/openapi/public-api.openapi.json "
        "packages/ai-skills/surgepilot-public-api/references/public-api.openapi.json"
        in generate_block
    )
    assert "$(MAKE) ai-skill-tests" in test_block
    assert "ai-skill-tests:" in makefile
    assert "pytest packages/ai-skills/surgepilot-public-api/tests -q" in makefile


def test_default_verify_excludes_runner_ssh_smoke_and_keeps_explicit_guard() -> None:
    makefile = (ROOT / "Makefile").read_text()
    verify_line = next(line for line in makefile.splitlines() if line.startswith("verify:"))
    runner_ssh_test = (ROOT / "apps/api/tests/test_p0_04_runner_ssh_e2e.py").read_text()

    assert "verify-runner-ssh" not in verify_line
    assert "verify-runner-ssh:" in makefile
    assert 'os.environ.get("SURGEPILOT_SSH_E2E") != "1"' in runner_ssh_test


def test_default_pytest_collection_includes_top_level_verifier_tests() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text()

    assert 'testpaths = ["apps/api/tests", "apps/runner/tests", "tests"]' in pyproject


def test_default_verify_includes_top_level_verifier_tests() -> None:
    makefile = (ROOT / "Makefile").read_text()
    test_block = makefile.split("\ntest:", maxsplit=1)[1].split("\napi-coverage:", maxsplit=1)[0]
    verifier_block = makefile.split("\nverifier-tests:", maxsplit=1)[1].split(
        "\npython-patch-coverage:", maxsplit=1
    )[0]

    assert "$(MAKE) verifier-tests" in test_block
    assert "tests/test_p0_api_main_flow_e2e_verifier.py" in verifier_block
    assert "tests/test_p0_06_ssh_taurus_smoke_verifier.py" in verifier_block
    assert "tests/test_p1_00_monitoring_remote_node_write_verifier.py" in verifier_block
    assert "tests/test_p1_01_ssh_two_node_smoke_verifier.py" in verifier_block
    assert "tests/test_release_runtime_artifact.py" in verifier_block
    assert "tests/test_verify_runtime_compat_node.py" in verifier_block
    assert "tests/test_bootstrap_deployment_env.py" in verifier_block
    assert "--cov=scripts.bootstrap_deployment_env" in verifier_block
    assert "--cov-branch --cov-append" in verifier_block
    assert "--cov-fail-under=90" in verifier_block


def test_source_full_stack_validates_explicit_external_node_urls_before_runtime() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    for target, following in (
        ("_start-full-stack:", "restart-full-stack:"),
        ("_restart-full-stack:", "stop-full-stack:"),
    ):
        block = makefile.split(target, maxsplit=1)[1].split(following, maxsplit=1)[0]
        validation = block.index("scripts/release_preflight.py validate-external")
        runtime = block.index("$(MAKE) release-runtime")
        assert validation < runtime


def test_source_full_stack_prints_bounded_progress_phases() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    block = makefile.split("\n_start-full-stack:", maxsplit=1)[1].split(
        "\n\nrestart-full-stack:", maxsplit=1
    )[0]

    assert "[1/3] Validating source full-stack configuration" in block
    assert "[2/3] Preparing the Load Node Runtime" in block
    assert "[3/3] Building and starting the complete source stack" in block


def test_makefile_has_canonical_user_start_targets() -> None:
    makefile = (ROOT / "Makefile").read_text()

    assert (
        'BOOTSTRAP_DEPLOYMENT_ENV=python3 scripts/bootstrap_deployment_env.py --root "$(CURDIR)"'
        in makefile
    )
    assert "release-runtime:" in makefile
    assert (
        "RUNTIME_ARTIFACT_HOST_DIR ?= $(CURDIR)/.surgepilot/runtime-artifacts/default" in makefile
    )
    assert "SURGEPILOT_SKIP_RUNTIME_PREFLIGHT" in makefile
    assert (
        "COMPOSE_FULL_SSH_E2E=$(COMPOSE_FULL) "
        "-f infra/docker/docker-compose.ssh-e2e.yml --profile ssh-e2e" in makefile
    )
    assert "start-full-stack:" in makefile
    assert "start-preview:" in makefile
    assert "stop-preview:" in makefile
    assert "restart-full-stack:" in makefile
    assert "stop-full-stack:" in makefile
    assert "FULL_SSH_E2E_RUNTIME_VERSION ?= p0-e2e" in makefile
    assert "FULL_SSH_E2E_RUNTIME_BUILD_DIR ?=" in makefile
    assert "FULL_SSH_E2E_RUNTIME_CACHE_DIR ?=" in makefile
    assert "FULL_SSH_E2E_RUNTIME_ENV_FILE ?=" in makefile
    assert "FULL_SSH_E2E_SSH_CREDENTIAL_ENCRYPTION_KEY ?=" in makefile
    assert "seed-full-ssh-e2e-runtime:" in makefile
    assert "scripts/run_runtime_builder.py" in makefile
    assert '--fixed-version "$(FULL_SSH_E2E_RUNTIME_VERSION)"' in makefile
    assert "scripts/seed_runtime_artifact_from_ssh_image.py" not in makefile
    assert "verify-runtime-compat:" in makefile
    assert "ssh-load-node-debian12" in makefile
    assert "SURGEPILOT_SSH_E2E_PORT=0" in makefile
    assert "SURGEPILOT_SSH_E2E_DEBIAN12_PORT=0" in makefile
    assert "trap cleanup EXIT" in makefile
    assert "cleanup()" in makefile
    assert "FULL_SSH_E2E_APP_BUILD_SERVICES=api-migrate api api-worker web" in makefile
    assert "_start-full-ssh-e2e: seed-full-ssh-e2e-runtime" in makefile
    assert "$(COMPOSE_FULL_SSH_E2E) build $(FULL_SSH_E2E_APP_BUILD_SERVICES)" in makefile
    assert "start-full-ssh-e2e-build:" in makefile
    assert "restart-full-ssh-e2e:" in makefile
    assert "restart-full-ssh-e2e-build:" in makefile
    assert "stop-full-ssh-e2e:" in makefile
    assert "dev-compose: start-full-stack" in makefile
    assert "$(MAKE) release-runtime" in makefile
    assert 'LOAD_NODE_RUNTIME_VERSION="$$LOAD_NODE_RUNTIME_VERSION"' in makefile
    assert "$(COMPOSE_FULL) config >/dev/null" in makefile
    assert "$(COMPOSE_FULL) up -d --build" in makefile
    assert "$(COMPOSE_FULL_SSH_E2E) up -d --no-build" in makefile

    start_block = makefile.split("\nstart-full-stack:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]
    assert start_block.index("$(BOOTSTRAP_DEPLOYMENT_ENV)") < start_block.index(
        "$(MAKE) _start-full-stack-with-env"
    )
    assert (
        "_start-full-stack-with-env:\n\t$(DEPLOYMENT_ENV_RUN) $(MAKE) _start-full-stack" in makefile
    )

    restart_block = makefile.split("\nrestart-full-stack:", maxsplit=1)[1].split(
        "\n\n", maxsplit=1
    )[0]
    assert restart_block.index("$(BOOTSTRAP_DEPLOYMENT_ENV)") < restart_block.index(
        "$(MAKE) _restart-full-stack-with-env"
    )
    assert (
        "_restart-full-stack-with-env:\n\t$(DEPLOYMENT_ENV_RUN) $(MAKE) _restart-full-stack"
        in makefile
    )

    start_build_block = makefile.split("\nstart-full-ssh-e2e-build:", maxsplit=1)[1].split(
        "\n\n", maxsplit=1
    )[0]
    assert "$(NODE_FACING_STARTUP) $(MAKE) _start-full-ssh-e2e-build" in start_build_block
    assert "build ssh-load-node" not in start_build_block

    restart_build_block = makefile.split("\nrestart-full-ssh-e2e-build:", maxsplit=1)[1].split(
        "\n\n", maxsplit=1
    )[0]
    assert "$(NODE_FACING_STARTUP) $(MAKE) _restart-full-ssh-e2e-build" in restart_build_block
    assert "$(COMPOSE_FULL_SSH_E2E) down" not in restart_build_block


def test_make_help_lists_canonical_user_start_targets() -> None:
    result = subprocess.run(
        ["make", "help"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "make start-full-stack" in result.stdout
    assert "make start-preview" in result.stdout
    assert "make stop-preview" in result.stdout
    assert "without Runtime or Demo readiness" in result.stdout
    assert "make release-runtime" in result.stdout
    assert "make restart-full-stack" in result.stdout
    assert "preflights the Load Node runtime before stopping" in result.stdout
    assert "make stop-full-stack" in result.stdout
    assert "make start-full-ssh-e2e" in result.stdout
    assert "make start-full-ssh-e2e-build" in result.stdout
    assert "make restart-full-ssh-e2e" in result.stdout
    assert "make restart-full-ssh-e2e-build" in result.stdout
    assert "make stop-full-ssh-e2e" in result.stdout
    assert "using existing local SSH image" in result.stdout
    assert "start Monitoring plus the Demo Load Node" in result.stdout
    assert "make dev-compose" in result.stdout
    assert "Alias for start-full-stack" in result.stdout


def test_source_preview_bootstraps_then_uses_process_local_incomplete_topology(
    tmp_path: Path,
) -> None:
    api_port, influxdb_port = free_host_ports()
    preview_runtime_dir = tmp_path / "preview-runtime"
    compose_log = tmp_path / "compose.log"
    compose = tmp_path / "compose-preview"
    compose.write_text(
        "#!/bin/sh\n"
        'printf "%s|demo=%s|profiles=%s|version=%s|runtime=%s\\n" "$*" '
        '"${SURGEPILOT_DEMO_LOAD_NODE_ENABLED-unset}" '
        '"${COMPOSE_PROFILES-unset}" '
        '"${LOAD_NODE_RUNTIME_VERSION-unset}" '
        '"${LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR-unset}" >> "$PREVIEW_COMPOSE_LOG"\n',
        encoding="utf-8",
    )
    compose.chmod(0o755)

    result = subprocess.run(
        [
            "make",
            "start-preview",
            "SURGEPILOT_TOOLCHAIN_ACTIVE=1",
            "BOOTSTRAP_DEPLOYMENT_ENV=true",
            f"SURGEPILOT_API_HOST_PORT={api_port}",
            f"SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT={influxdb_port}",
            f"SURGEPILOT_NODE_API_BASE_URL=http://192.0.2.10:{api_port}",
            f"SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://192.0.2.10:{influxdb_port}",
            f"SSH_CREDENTIAL_ENCRYPTION_KEY={TEST_SSH_CREDENTIAL_ENCRYPTION_KEY}",
            "SURGEPILOT_DEMO_LOAD_NODE_ENABLED=true",
            "LOAD_NODE_RUNTIME_VERSION=must-not-leak",
            f"PREVIEW_RUNTIME_ARTIFACT_HOST_DIR={preview_runtime_dir}",
            f"PREVIEW_COMPOSE_LOG={compose_log}",
            f"COMPOSE_PREVIEW={compose}",
            "COMPOSE_PROFILES=demo",
            "RUNTIME_RELEASE_COMMAND=sh -c 'echo RUNTIME_SHOULD_NOT_RUN; exit 42'",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert preview_runtime_dir.is_dir()
    assert preview_runtime_dir.stat().st_mode & 0o777 == 0o700
    assert "RUNTIME_SHOULD_NOT_RUN" not in result.stdout
    assert compose_log.read_text(encoding="utf-8").splitlines() == [
        f"config|demo=false|profiles=|version=|runtime={preview_runtime_dir}",
        (
            "--profile demo stop demo-load-node|demo=false|profiles=|version=|"
            f"runtime={preview_runtime_dir}"
        ),
        f"up -d --build|demo=false|profiles=|version=|runtime={preview_runtime_dir}",
    ]
    assert "SurgePilot Preview started." in result.stdout
    assert "Web: http://localhost:8080" in result.stdout
    assert "Grafana: http://localhost:8080/grafana/" in result.stdout
    assert "Load Node Runtime: not prepared" in result.stdout
    assert "Demo Load Node: disabled" in result.stdout
    assert "make start-full-stack" in result.stdout


def test_source_preview_clears_native_compose_profiles_from_effective_services(
    tmp_path: Path,
) -> None:
    api_port, influxdb_port = free_host_ports()
    preview_runtime_dir = tmp_path / "preview-runtime"
    services_log = tmp_path / "services.log"
    compose = tmp_path / "compose-preview"
    compose.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "config" ]; then\n'
        f'  docker compose -f "{ROOT / "infra/docker/docker-compose.yml"}" '
        'config --services > "$PREVIEW_SERVICES_LOG"\n'
        "fi\n",
        encoding="utf-8",
    )
    compose.chmod(0o755)

    result = subprocess.run(
        [
            "make",
            "start-preview",
            "SURGEPILOT_TOOLCHAIN_ACTIVE=1",
            "BOOTSTRAP_DEPLOYMENT_ENV=true",
            f"SURGEPILOT_API_HOST_PORT={api_port}",
            f"SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT={influxdb_port}",
            f"SURGEPILOT_NODE_API_BASE_URL=http://192.0.2.10:{api_port}",
            f"SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://192.0.2.10:{influxdb_port}",
            f"SSH_CREDENTIAL_ENCRYPTION_KEY={TEST_SSH_CREDENTIAL_ENCRYPTION_KEY}",
            "RUNNER_INTERNAL_TOKEN=preview-test-token",
            f"PREVIEW_RUNTIME_ARTIFACT_HOST_DIR={preview_runtime_dir}",
            f"PREVIEW_SERVICES_LOG={services_log}",
            f"COMPOSE_PREVIEW={compose}",
            "COMPOSE_PROFILES=demo",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    services = set(services_log.read_text(encoding="utf-8").splitlines())
    assert services == {
        "postgres",
        "api-migrate",
        "influxdb",
        "grafana",
        "minio",
        "minio-init",
        "api",
        "api-worker",
        "web",
        "nginx",
    }
    assert "demo-load-node" not in services


def test_stop_preview_uses_preview_compose_without_deleting_volumes(tmp_path: Path) -> None:
    compose_log = tmp_path / "compose.log"
    compose = tmp_path / "compose-preview"
    compose.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" > "$PREVIEW_COMPOSE_LOG"\n',
        encoding="utf-8",
    )
    compose.chmod(0o755)

    result = subprocess.run(
        [
            "make",
            "stop-preview",
            f"PREVIEW_COMPOSE_LOG={compose_log}",
            f"COMPOSE_PREVIEW={compose}",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert compose_log.read_text(encoding="utf-8") == "down\n"
    assert "-v" not in compose_log.read_text(encoding="utf-8")


def test_source_preview_validation_fails_before_creating_runtime_mount(tmp_path: Path) -> None:
    preview_runtime_dir = tmp_path / "preview-runtime"

    result = subprocess.run(
        [
            "make",
            "start-preview",
            "SURGEPILOT_TOOLCHAIN_ACTIVE=1",
            "BOOTSTRAP_DEPLOYMENT_ENV=true",
            "SURGEPILOT_NODE_API_BASE_URL=http://192.0.2.10:8080",
            f"PREVIEW_RUNTIME_ARTIFACT_HOST_DIR={preview_runtime_dir}",
            "COMPOSE_PREVIEW=sh -c 'echo COMPOSE_SHOULD_NOT_RUN; exit 0'",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "must be set together" in result.stderr
    assert not preview_runtime_dir.exists()
    assert "COMPOSE_SHOULD_NOT_RUN" not in result.stdout
    assert "COMPOSE_SHOULD_NOT_RUN" not in result.stderr


def test_official_full_stack_targets_print_access_summary() -> None:
    for target, status in (
        ("start-full-stack", "started"),
        ("restart-full-stack", "restarted"),
    ):
        api_port, influxdb_port = free_host_ports()
        result = subprocess.run(
            [
                "make",
                target,
                "SURGEPILOT_TOOLCHAIN_ACTIVE=1",
                "BOOTSTRAP_DEPLOYMENT_ENV=true",
                f"SURGEPILOT_API_HOST_PORT={api_port}",
                f"SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT={influxdb_port}",
                f"SURGEPILOT_NODE_API_BASE_URL=http://192.0.2.10:{api_port}",
                f"SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://192.0.2.10:{influxdb_port}",
                f"SSH_CREDENTIAL_ENCRYPTION_KEY={TEST_SSH_CREDENTIAL_ENCRYPTION_KEY}",
                "SURGEPILOT_SKIP_RUNTIME_PREFLIGHT=1",
                "COMPOSE_FULL=sh -c 'exit 0'",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        assert result.returncode == 0, result.stderr
        assert f"SurgePilot {status} successfully." in result.stdout
        assert "Web: http://localhost:8080" in result.stdout
        assert "Grafana: http://localhost:8080/grafana/" in result.stdout
        assert (
            "Next: register the first Admin account, then register and initialize the Demo Load Node."
            in result.stdout
        )


def test_full_e2e_uses_clean_environment_targets() -> None:
    makefile = (ROOT / "Makefile").read_text()
    verify_e2e_block = makefile.split("\nverify-e2e:", maxsplit=1)[1].split(
        "\nverify-runner-ssh:", maxsplit=1
    )[0]

    assert "$(MAKE) verify-p0-api-main-flow-e2e\n" in verify_e2e_block
    assert "$(MAKE) verify-p0-06-runner-ssh\n" in verify_e2e_block
    assert "verify-p0-api-main-flow-e2e-fast" not in verify_e2e_block
    assert "verify-p0-06-runner-ssh-fast" not in verify_e2e_block
    assert "tests/e2e/p0_03_load_nodes.spec.ts" in verify_e2e_block
    assert "tests/e2e/p0_03_load_node_registration_error.spec.ts" in verify_e2e_block


def test_real_ip_e2e_targets_prefix_env_with_env_command() -> None:
    makefile = (ROOT / "Makefile").read_text()

    for target in (
        "verify-p0-api-main-flow-e2e",
        "verify-p0-api-main-flow-e2e-fast",
        "verify-p0-06-runner-ssh",
        "verify-p0-06-runner-ssh-fast",
    ):
        block = makefile.split(f"\n{target}:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]
        assert "env $${HOST_IP:+SURGEPILOT_E2E_HOST_IP=" in block
        assert (
            "SURGEPILOT_E2E_API_ORCHESTRATION_URL=$${SURGEPILOT_E2E_API_ORCHESTRATION_URL:-http://$${HOST_IP}:8000}"
            in block
        )

    remote_write_block = makefile.split("\nverify-p1-00-monitoring-remote-node-write:", maxsplit=1)[
        1
    ].split("\n\n", maxsplit=1)[0]
    assert "SURGEPILOT_NODE_API_BASE_URL" in remote_write_block
    assert "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL" in remote_write_block
    assert "SURGEPILOT_E2E_HOST_IP" not in remote_write_block


def test_ssh_load_node_dockerfiles_do_not_embed_runtime_artifacts() -> None:
    for relative_path in (
        "infra/docker/ssh-load-node/Dockerfile",
        "infra/docker/ssh-load-node-debian12/Dockerfile",
    ):
        dockerfile = (ROOT / relative_path).read_text()

        assert "openjdk-17-jre-headless" in dockerfile
        assert "python3-click" in dockerfile
        assert "bzt==" not in dockerfile
        assert "apache-jmeter" not in dockerfile
        assert "repo1.maven.org" not in dockerfile
        assert "python3-pip" not in dockerfile
        assert "gcc" not in dockerfile
        assert "openjdk-17-jdk-headless" not in dockerfile


def test_start_full_stack_fails_fast_when_runtime_release_fails_with_stale_env(
    tmp_path: Path,
) -> None:
    api_port, influxdb_port = free_host_ports()
    env_file = tmp_path / "runtime.env"
    env_file.write_text(
        f"LOAD_NODE_RUNTIME_VERSION=stale\nLOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR={tmp_path}\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "make",
            "start-full-stack",
            "SURGEPILOT_TOOLCHAIN_ACTIVE=1",
            "BOOTSTRAP_DEPLOYMENT_ENV=true",
            f"SURGEPILOT_API_HOST_PORT={api_port}",
            f"SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT={influxdb_port}",
            f"SURGEPILOT_NODE_API_BASE_URL=http://192.0.2.10:{api_port}",
            f"SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://192.0.2.10:{influxdb_port}",
            f"SSH_CREDENTIAL_ENCRYPTION_KEY={TEST_SSH_CREDENTIAL_ENCRYPTION_KEY}",
            f"RUNTIME_ENV_FILE={env_file}",
            "RUNTIME_RELEASE_COMMAND=sh -c 'echo release failed >&2; exit 42'",
            "COMPOSE_FULL=sh -c 'echo COMPOSE_SHOULD_NOT_RUN; exit 0'",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "release failed" in result.stderr
    assert "COMPOSE_SHOULD_NOT_RUN" not in result.stdout
    assert "COMPOSE_SHOULD_NOT_RUN" not in result.stderr


def test_restart_full_stack_preflights_before_stopping_existing_stack() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    block = makefile.split("\n_restart-full-stack:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]
    official_branch = block.split("else \\", maxsplit=1)[1]

    assert official_branch.index("$(MAKE) release-runtime") < official_branch.index(
        "$(COMPOSE_FULL) down"
    )


def test_restart_full_stack_skip_preflight_stops_on_down_failure(tmp_path: Path) -> None:
    api_port, influxdb_port = free_host_ports()
    compose = tmp_path / "compose-full"
    compose.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "down" ]; then echo down failed >&2; exit 42; fi\n'
        'echo "UP_SHOULD_NOT_RUN $*"\n',
        encoding="utf-8",
    )
    compose.chmod(0o755)

    result = subprocess.run(
        [
            "make",
            "restart-full-stack",
            "SURGEPILOT_TOOLCHAIN_ACTIVE=1",
            "BOOTSTRAP_DEPLOYMENT_ENV=true",
            f"SURGEPILOT_API_HOST_PORT={api_port}",
            f"SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT={influxdb_port}",
            f"SURGEPILOT_NODE_API_BASE_URL=http://192.0.2.10:{api_port}",
            f"SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://192.0.2.10:{influxdb_port}",
            f"SSH_CREDENTIAL_ENCRYPTION_KEY={TEST_SSH_CREDENTIAL_ENCRYPTION_KEY}",
            "SURGEPILOT_SKIP_RUNTIME_PREFLIGHT=1",
            f"COMPOSE_FULL={compose}",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "down failed" in result.stderr
    assert "UP_SHOULD_NOT_RUN" not in result.stdout
    assert "UP_SHOULD_NOT_RUN" not in result.stderr
