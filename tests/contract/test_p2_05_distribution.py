from __future__ import annotations

from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_source_full_stack_has_internal_demo_node_without_default_host_ssh_port() -> None:
    compose = yaml.safe_load((ROOT / "infra/docker/docker-compose.yml").read_text(encoding="utf-8"))
    base_compose = yaml.safe_load(
        (ROOT / "infra/docker/docker-compose.base.yml").read_text(encoding="utf-8")
    )
    services = compose["services"]

    demo = services["demo-load-node"]
    assert demo["profiles"] == ["demo"]
    assert "ports" not in demo
    assert demo["hostname"] == "demo-load-node"
    assert services["api"]["environment"]["SURGEPILOT_NODE_API_BASE_URL"] == (
        "${SURGEPILOT_NODE_API_BASE_URL:-http://api.surgepilot.test:8000}"
    )
    assert services["api-worker"]["environment"][
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"
    ] == ("${SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL:-http://influxdb:8086}")
    for source_services in (services, base_compose["services"]):
        assert source_services["minio"]["image"] == (
            "quay.io/minio/minio:RELEASE.2025-04-22T22-12-26Z"
        )
        assert source_services["minio-init"]["image"] == (
            "quay.io/minio/mc:RELEASE.2025-04-16T18-13-26Z"
        )


def test_release_compose_is_digest_pinned_and_contains_no_application_build_contexts() -> None:
    compose_path = ROOT / "infra/release/docker-compose.release.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = compose["services"]

    assert set(services) == {
        "postgres",
        "minio",
        "minio-init",
        "api-migrate",
        "api",
        "api-worker",
        "web",
        "nginx",
        "influxdb",
        "grafana",
        "demo-load-node",
    }
    for name in ("api-migrate", "api", "api-worker", "web", "demo-load-node"):
        assert "build" not in services[name]
    assert services["api"]["image"] == "@@API_IMAGE@@"
    assert services["web"]["image"] == "@@WEB_IMAGE@@"
    assert services["demo-load-node"]["image"] == "@@DEMO_NODE_IMAGE@@"
    assert services["minio"]["image"] == ("quay.io/minio/minio:RELEASE.2025-04-22T22-12-26Z")
    assert services["minio-init"]["image"] == ("quay.io/minio/mc:RELEASE.2025-04-16T18-13-26Z")
    assert services["nginx"]["ports"] == [
        "${SURGEPILOT_HTTP_PORT:?SURGEPILOT_HTTP_PORT is required}:80"
    ]
    assert services["influxdb"]["ports"] == [
        "${SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT:?SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT is required}:8086"
    ]
    for name in ("api", "api-worker"):
        environment = services[name]["environment"]
        assert environment["SURGEPILOT_NODE_API_BASE_URL"] == (
            "${SURGEPILOT_NODE_API_BASE_URL:?SURGEPILOT_NODE_API_BASE_URL is required}"
        )
        assert environment["SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"] == (
            "${SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL:?"
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL is required}"
        )
        assert environment["SESSION_COOKIE_SECURE"] == (
            "${SESSION_COOKIE_SECURE:?SESSION_COOKIE_SECURE is required}"
        )
        assert environment["SURGEPILOT_MONITORING_INFLUXDB_INTERNAL_URL"] == "http://influxdb:8086"
    assert services["grafana"]["user"] == "0:0"
    assert services["grafana"]["entrypoint"] == [
        "/bin/sh",
        "/etc/surgepilot/grafana-entrypoint.sh",
    ]
    assert "GF_SECURITY_ADMIN_PASSWORD__FILE" not in services["grafana"]["environment"]
    assert (
        "./grafana/entrypoint.sh:/etc/surgepilot/grafana-entrypoint.sh:ro"
        in services["grafana"]["volumes"]
    )
    assert services["grafana"]["tmpfs"] == ["/run/surgepilot:mode=0710,uid=0,gid=0"]
    for name in ("api", "web", "postgres", "minio", "demo-load-node"):
        assert "ports" not in services[name]


def test_release_defaults_are_lan_first_and_external_overlay_is_removed() -> None:
    env_example = (ROOT / "infra/release/.env.example").read_text(encoding="utf-8")
    wrapper = (ROOT / "infra/release/surgepilot").read_text(encoding="utf-8")
    bundle_builder = (ROOT / "scripts/build_release_bundle.py").read_text(encoding="utf-8")

    assert "SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false" in env_example
    assert "SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64" in env_example
    assert "SURGEPILOT_RUNTIME_ARCHITECTURES=auto" not in env_example
    source_env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "SURGEPILOT_RUNTIME_ARCHITECTURES=auto" in source_env_example
    assert "SESSION_COOKIE_SECURE=false" in env_example
    assert "SURGEPILOT_NODE_API_BASE_URL=http://192.168.1.20:8080" in env_example
    assert "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://192.168.1.20:8086" in env_example
    assert "docker-compose.external-node.yml" not in wrapper
    assert "docker-compose.external-node.yml" not in bundle_builder
    assert not (ROOT / "infra/release/docker-compose.external-node.yml").exists()


def test_release_wrapper_is_posix_shell_and_does_not_require_host_python_or_jq() -> None:
    wrapper = (ROOT / "infra/release/surgepilot").read_text(encoding="utf-8")

    assert wrapper.startswith("#!/bin/sh\n")
    assert "python3" not in wrapper
    assert "jq" not in wrapper
    assert "docker compose" in wrapper
    assert "COMMAND_NAME=${SURGEPILOT_COMMAND_NAME:-./surgepilot}" in wrapper
    assert "$COMMAND_NAME up" in wrapper
    assert "--wait" in wrapper
    assert "down -v" not in wrapper


def test_release_workflow_is_tag_only_native_runtime_and_create_only() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "v*.*.*" in workflow
    assert "ubuntu-24.04-arm" in workflow
    assert "scripts/run_runtime_builder.py" in workflow
    assert "linux/amd64,linux/arm64" not in workflow
    assert "contents: write" in workflow
    assert "packages: write" in workflow
    assert "id-token: write" not in workflow
    assert "--draft" in workflow
    assert "buildx imagetools create" in workflow
    assert "already exists" in workflow
    assert "manifest unknown" in workflow
    assert "Unable to determine whether" in workflow
    assert "staging-$GITHUB_SHA-$arch" in workflow

    preflight = workflow.split("\n  preflight:\n", maxsplit=1)[1].split(
        "\n  verify:\n", maxsplit=1
    )[0]
    repository_guard = 'test "$GITHUB_REPOSITORY" = "$CANONICAL_REPOSITORY"'
    assert "CANONICAL_REPOSITORY: latentrun/SurgePilot" in workflow
    assert repository_guard in preflight
    assert preflight.index(repository_guard) < preflight.index("release_probe=")

    publish = workflow.split("\n  publish:\n", maxsplit=1)[1]
    assert "name: image-digests" in publish
    assert "tar -xOf" in publish
    assert "image-digests.json" in publish
    assert 'imagetools create --tag "$image:$TAG" "$image@$digest"' in publish
    assert 'inspect "$image:staging-$GITHUB_SHA" --format' not in publish

    release_smoke = workflow.split("\n  release-smoke:\n", maxsplit=1)[1].split(
        "\n  publish:\n", maxsplit=1
    )[0]
    assert "docker/login-action@" not in release_smoke
    assert "GHCR packages must allow anonymous pulls" in release_smoke

    anonymous_inspect = (
        'DOCKER_CONFIG="$anonymous_config" docker buildx imagetools inspect "$image@$digest"'
    )
    assert anonymous_inspect in publish
    assert publish.index(anonymous_inspect) < publish.index("gh release edit")

    tag_check = 'test "$(git rev-parse "$TAG^{commit}")" = "$GITHUB_SHA"'
    assert publish.count(tag_check) == 1
    tag_assertion = "\n          assert_release_tag_unchanged\n"
    assert publish.count(tag_assertion) == 2
    assert publish.index(tag_assertion) < publish.index("gh release create")
    assert publish.rindex(tag_assertion) < publish.index("gh release edit")

    preflight = workflow.split("\n  preflight:\n", maxsplit=1)[1].split(
        "\n  verify:\n", maxsplit=1
    )[0]
    public_bootstrap_probe = (
        'DOCKER_CONFIG="$anonymous_config" docker buildx imagetools inspect '
        '"$image:package-bootstrap"'
    )
    assert public_bootstrap_probe in preflight
    assert preflight.index(public_bootstrap_probe) < preflight.index(
        'assert_image_absent "$image:$TAG"'
    )


def test_release_package_bootstrap_is_manual_bounded_and_non_semantic() -> None:
    workflow_path = ROOT / ".github/workflows/release-package-bootstrap.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(workflow)

    assert parsed[True]["workflow_dispatch"] is None
    assert parsed[True]["push"]["tags"] == ["package-bootstrap-*"]
    assert "packages: write" in workflow
    assert "contents: read" in workflow
    assert "package-bootstrap" in workflow
    assert "gh release" not in workflow
    assert "v*.*.*" not in workflow
    assert "surgepilot-api" in workflow
    assert "surgepilot-web" in workflow
    assert "surgepilot-demo-node" in workflow
    assert "Package settings" in workflow
    assert "refs/remotes/origin/main" in workflow
    assert "git merge-base --is-ancestor" in workflow
    assert parsed["env"]["CANONICAL_REPOSITORY"] == "latentrun/SurgePilot"
    repository_guard = 'test "$GITHUB_REPOSITORY" = "$CANONICAL_REPOSITORY"'
    create_packages = parsed["jobs"]["create-packages"]
    guard_index = next(
        index
        for index, step in enumerate(create_packages["steps"])
        if repository_guard in step.get("run", "")
    )
    login_index = next(
        index
        for index, step in enumerate(create_packages["steps"])
        if str(step.get("uses", "")).startswith("docker/login-action@")
    )
    assert guard_index < login_index


def test_formal_release_rejects_reserved_validation_version() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    preflight = workflow.split("\n  preflight:\n", maxsplit=1)[1].split(
        "\n  verify:\n", maxsplit=1
    )[0]

    assert 'test "$TAG" != "v0.0.0"' in preflight
    assert "reserved for development validation" in preflight


def test_release_workflows_pin_external_actions_to_full_commit_shas() -> None:
    for workflow_name in (
        "release.yml",
        "release-validation.yml",
        "release-package-bootstrap.yml",
    ):
        parsed = yaml.safe_load(
            (ROOT / ".github/workflows" / workflow_name).read_text(encoding="utf-8")
        )
        for job_name, job in parsed["jobs"].items():
            for step in job.get("steps", []):
                action = step.get("uses")
                if action is None or action.startswith("./"):
                    continue
                assert re.fullmatch(r"[^@]+@[a-f0-9]{40}", action), (
                    f"{workflow_name}:{job_name} must pin {action} to a full commit SHA"
                )


def test_release_bundle_workflows_execute_builder_as_repo_module() -> None:
    for workflow_name in ("release.yml", "release-validation.yml"):
        workflow = (ROOT / ".github/workflows" / workflow_name).read_text(encoding="utf-8")
        assert "python -m scripts.build_release_bundle" in workflow
        assert "python scripts/build_release_bundle.py" not in workflow


def test_release_workflows_validate_and_install_generated_assets() -> None:
    assert (ROOT / "infra/release/install.sh").is_file()

    cases = (
        ("release.yml", "bundle", "installer-smoke", "release-smoke"),
        ("release-validation.yml", "tag-bundle", "tag-installer-smoke", "tag-smoke"),
    )
    for workflow_name, bundle_name, installer_name, stack_name in cases:
        workflow_path = ROOT / ".github/workflows" / workflow_name
        workflow = workflow_path.read_text(encoding="utf-8")
        jobs = yaml.safe_load(workflow)["jobs"]

        bundle = "\n".join(step.get("run", "") for step in jobs[bundle_name]["steps"])
        assert "install.sh" in bundle
        assert ".tar.gz.sha256" in bundle
        assert "sha256sum -c" in bundle

        installer_job = jobs[installer_name]
        assert installer_job["needs"] == bundle_name
        assert installer_job["strategy"]["matrix"]["runner"] == [
            "ubuntu-24.04",
            "macos-14",
        ]
        installer_smoke = "\n".join(step.get("run", "") for step in installer_job["steps"])
        assert "python3 -m http.server" in installer_smoke
        assert "SURGEPILOT_INSTALLER_RELEASE_BASE_URL" in installer_smoke
        assert '"$HOME/.local/bin/surgepilot" --help' in installer_smoke

        stack_smoke = "\n".join(step.get("run", "") for step in jobs[stack_name]["steps"])
        assert "SURGEPILOT_INSTALLER_RELEASE_BASE_URL" in stack_smoke
        assert 'SURGEPILOT="$HOME/.local/bin/surgepilot"' in stack_smoke
        assert '"$SURGEPILOT" up' in stack_smoke
        assert "tar -xzf" not in stack_smoke
        assert "cleanup_status=$?" in stack_smoke
        assert '"$SURGEPILOT" logs || true' in stack_smoke
        assert stack_smoke.index('"$SURGEPILOT" logs || true') < stack_smoke.index(
            '"$SURGEPILOT" down || true'
        )

    formal_jobs = yaml.safe_load(
        (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    )["jobs"]
    assert formal_jobs["publish"]["needs"] == [
        "bundle",
        "installer-smoke",
        "release-smoke",
    ]


def test_release_smokes_prepare_runtime_state_with_owner_only_permissions() -> None:
    workflow_sections = (
        (
            ROOT / ".github/workflows/release.yml",
            "\n  release-smoke:\n",
            "\n  publish:\n",
        ),
        (
            ROOT / ".github/workflows/release-validation.yml",
            "\n  tag-smoke:\n",
            None,
        ),
    )

    for workflow_path, section_start, section_end in workflow_sections:
        workflow = workflow_path.read_text(encoding="utf-8")
        smoke = workflow.split(section_start, maxsplit=1)[1]
        if section_end is not None:
            smoke = smoke.split(section_end, maxsplit=1)[0]

        private_runtime_directory = (
            'install -d -m 700 "$INSTALL_ROOT/.surgepilot" '
            '"$INSTALL_ROOT/.surgepilot/runtime-artifacts"'
        )
        assert private_runtime_directory in smoke
        assert smoke.index(private_runtime_directory) < smoke.index(
            '"$INSTALL_ROOT/.surgepilot/runtime-artifacts/"'
        )


def test_tag_release_smoke_prepositions_both_runtime_sets() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    release_smoke = workflow.split("\n  release-smoke:\n", maxsplit=1)[1].split(
        "\n  publish:\n", maxsplit=1
    )[0]
    release_smoke_job = yaml.safe_load(workflow)["jobs"]["release-smoke"]

    assert "--release-runtime-architectures amd64,arm64" in release_smoke
    runtime_copy = (
        "cp release-assets/surgepilot-runtime-linux-* "
        '"$INSTALL_ROOT/.surgepilot/runtime-artifacts/"'
    )
    assert runtime_copy in release_smoke
    assert release_smoke.index(runtime_copy) < release_smoke.index('"$SURGEPILOT" up')
    assert release_smoke_job["strategy"]["matrix"]["include"] == [
        {"arch": "amd64", "runner": "ubuntu-24.04"},
        {"arch": "arm64", "runner": "ubuntu-24.04-arm"},
    ]
    assert "RELEASE_ARCH" not in release_smoke
    assert "--release-runtime-architectures auto" not in release_smoke


def test_release_readme_explains_prebuilt_runtime_asset_acquisition() -> None:
    readme = (ROOT / "infra/release/README.md").read_text(encoding="utf-8")
    normalized_readme = " ".join(readme.split())

    assert "version-matched, prebuilt GitHub Release assets" in normalized_readme
    assert "downloads them or reuses fully validated cached copies" in normalized_readme
    assert "never compiles Runtime assets on the deployment host" in normalized_readme


def test_release_readme_explains_configuration_confirmation_boundaries() -> None:
    readme = (ROOT / "infra/release/README.md").read_text(encoding="utf-8")
    normalized_readme = " ".join(readme.split())

    assert "Use this configuration? [Y/n]" in readme
    assert "Press Enter to use the displayed configuration." in readme
    assert (
        "For the initial confirmation of an existing `.env`, Yes accepts the current "
        "configuration without rewriting it." in normalized_readme
    )
    assert (
        "On first run, Yes creates an owner-only `.env` from the displayed configuration."
        in normalized_readme
    )
    assert (
        "Choosing No lets you change only the LAN host, HTTP port, and InfluxDB node-write port."
        in normalized_readme
    )
    assert (
        "uses the current LAN host, HTTP port, and InfluxDB node-write port as defaults"
        in normalized_readme
    )
    assert (
        "After a changed direct-LAN proposal is reviewed, Yes atomically replaces only these "
        "four assignments:" in normalized_readme
    )
    for assignment in (
        "SURGEPILOT_HTTP_PORT",
        "SURGEPILOT_NODE_API_BASE_URL",
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT",
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL",
    ):
        assert f"- `{assignment}`" in readme
    assert (
        "All credentials and secrets, Runtime selection, Demo state, cookie policy, comments, "
        "unknown fields, and other non-network values are preserved." in normalized_readme
    )
    assert "Advanced HTTPS configuration must be edited explicitly in .env." in readme
    assert (
        "With a complete valid existing `.env`, non-interactive startup displays the same "
        "non-secret configuration summary and does not prompt or read standard input."
        in normalized_readme
    )
    assert "Non-interactive startup never rewrites an existing .env." in readme
    assert (
        "checks the exact reviewed `.env` SHA-256 immediately before calling standard "
        "`os.replace`." in normalized_readme
    )
    assert (
        "This flow provides no strict compare-and-swap (CAS), locks, backups, or automatic "
        "rollback." in normalized_readme
    )


def test_release_smokes_preprovision_complete_non_loopback_environment() -> None:
    workflow_sections = (
        (
            ROOT / ".github/workflows/release.yml",
            "\n  release-smoke:\n",
            "\n  publish:\n",
            "amd64,arm64",
        ),
        (
            ROOT / ".github/workflows/release-validation.yml",
            "\n  tag-smoke:\n",
            None,
            "auto",
        ),
    )

    for workflow_path, section_start, section_end, runtime_architectures in workflow_sections:
        workflow = workflow_path.read_text(encoding="utf-8")
        smoke = workflow.split(section_start, maxsplit=1)[1]
        if section_end is not None:
            smoke = smoke.split(section_end, maxsplit=1)[0]

        up_index = smoke.index('"$SURGEPILOT" up')
        bootstrap_index = smoke.index('python "$INSTALL_ROOT/scripts/bootstrap_deployment_env.py"')
        compose_config_index = smoke.index('docker compose --env-file "$INSTALL_ROOT/.env"')
        assert bootstrap_index < compose_config_index < up_index
        assert "smoke_host=$(ip -4 route get 1.1.1.1" in smoke
        assert '--release-node-api-base-url "http://$smoke_host:8080"' in smoke
        assert '--release-influxdb-node-write-url "http://$smoke_host:8086"' in smoke
        assert "--release-http-port 8080" in smoke
        assert "--release-influxdb-host-port 8086" in smoke
        assert "--release-demo-enabled true" in smoke
        assert f"--release-runtime-architectures {runtime_architectures}" in smoke
        assert "--session-cookie-secure false" in smoke
        assert "--profile demo config" in smoke
        assert 'SURGEPILOT_E2E_API_ORCHESTRATION_URL="http://$smoke_host:8080"' in smoke
        assert 'SURGEPILOT_E2E_TARGET_URL="http://$smoke_host:8080/api/healthz"' in smoke
        assert 'SURGEPILOT_E2E_INFLUXDB_QUERY_URL="http://$smoke_host:8086"' in smoke
        assert "SURGEPILOT_E2E_INFLUXDB_TOKEN_FILE=" in smoke
        assert "make verify-p2-05-release-stack" in smoke
        before_up = smoke[:up_index]
        assert "SURGEPILOT_NODE_API_BASE_URL=http://localhost" not in before_up
        assert "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://localhost" not in before_up
        up_lines = [
            (index, line)
            for index, line in enumerate(smoke.splitlines())
            if '"$SURGEPILOT" up' in line
        ]
        assert len(up_lines) == 1
        line_index, up_line = up_lines[0]
        smoke_lines = smoke.splitlines()
        assert up_line.strip() == '"$SURGEPILOT" up'
        assert not smoke_lines[line_index - 1].rstrip().endswith(("|", "\\"))


def test_development_release_validation_workflow_contract() -> None:
    workflow_path = ROOT / ".github/workflows/release-validation.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(workflow)

    assert parsed[True]["pull_request"]["branches"] == ["main"]
    assert parsed[True]["push"]["tags"] == ["validation-*"]
    assert parsed["permissions"] == {"contents": "read", "packages": "read"}
    assert parsed["env"]["CANONICAL_REPOSITORY"] == "latentrun/SurgePilot"

    jobs = parsed["jobs"]
    assert set(jobs) == {
        "verify",
        "pr-native",
        "pr-installer-smoke",
        "tag-preflight",
        "tag-native",
        "tag-indexes",
        "tag-bundle",
        "tag-installer-smoke",
        "tag-smoke",
    }
    assert jobs["pr-native"]["strategy"]["fail-fast"] is False
    assert jobs["pr-installer-smoke"]["strategy"] == {
        "fail-fast": False,
        "matrix": {"runner": ["ubuntu-24.04", "macos-14"]},
    }
    tag_condition = "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/validation-')"
    assert jobs["pr-native"]["if"] == "github.event_name == 'pull_request'"
    assert jobs["pr-installer-smoke"]["if"] == "github.event_name == 'pull_request'"
    for name in (
        "tag-preflight",
        "tag-native",
        "tag-indexes",
        "tag-bundle",
        "tag-installer-smoke",
        "tag-smoke",
    ):
        assert jobs[name]["if"] == tag_condition
    assert jobs["pr-native"]["needs"] == "verify"
    assert jobs["pr-installer-smoke"]["needs"] == "verify"
    assert jobs["tag-native"]["needs"] == ["verify", "tag-preflight"]
    assert jobs["tag-indexes"]["needs"] == "tag-native"
    assert jobs["tag-bundle"]["needs"] == "tag-indexes"
    assert jobs["tag-installer-smoke"]["needs"] == "tag-bundle"
    assert jobs["tag-smoke"]["needs"] == "tag-bundle"
    assert all(job.get("permissions", {}).get("contents") != "write" for job in jobs.values())
    package_writers = {
        name for name, job in jobs.items() if job.get("permissions", {}).get("packages") == "write"
    }
    assert package_writers == {"tag-native", "tag-indexes"}

    artifact_uploads = [
        step
        for job in jobs.values()
        for step in job.get("steps", [])
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    ]
    assert artifact_uploads
    assert all(step.get("with", {}).get("retention-days") == 1 for step in artifact_uploads)

    repository_guard = 'test "$GITHUB_REPOSITORY" = "$CANONICAL_REPOSITORY"'
    tag_preflight = jobs["tag-preflight"]["steps"]
    guard_index = next(
        index for index, step in enumerate(tag_preflight) if repository_guard in step.get("run", "")
    )
    buildx_index = next(
        index
        for index, step in enumerate(tag_preflight)
        if str(step.get("uses", "")).startswith("docker/setup-buildx-action@")
    )
    assert guard_index < buildx_index

    bundle_uploads = [
        step
        for step in jobs["tag-bundle"]["steps"]
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    ]
    assert any(
        step.get("with", {}).get("name") == "validation-release-bundle"
        and step.get("with", {}).get("path") == "validation-output/surgepilot-v0.0.0.tar.gz"
        and step.get("with", {}).get("if-no-files-found") == "error"
        for step in bundle_uploads
    )
    assert any(
        step.get("with", {}).get("name") == "validation-release-assets"
        and step.get("with", {}).get("path") == "validation-output/*"
        for step in bundle_uploads
    )

    for name in ("pr-native", "tag-native"):
        steps = jobs[name]["steps"]
        buildx_index = next(
            index
            for index, step in enumerate(steps)
            if str(step.get("uses", "")).startswith("docker/setup-buildx-action@")
        )
        compat_index = next(
            index
            for index, step in enumerate(steps)
            if step.get("name") == "Verify native Ubuntu 24.04 and Debian 12 compatibility"
        )
        assert buildx_index > compat_index

    assert "ubuntu-24.04-arm" in workflow
    assert "fetch-depth: 0" in workflow
    assert "refs/remotes/origin/main" in workflow
    assert "git merge-base --is-ancestor" in workflow
    assert "^validation-[0-9a-f]{12,40}$" in workflow
    assert '[[ "$GITHUB_SHA" == "$suffix"* ]]' in workflow
    assert 'TAG="validation-$GITHUB_SHA"' in workflow
    assert 'ARCH_TAG="$TAG-${{ matrix.arch }}"' in workflow
    assert '--fixed-version "v0.0.0"' in workflow
    assert '--version "v0.0.0"' in workflow
    assert '"$INSTALL_ROOT/.surgepilot/runtime-artifacts"' in workflow
    assert 'DOCKER_CONFIG="$anonymous_config"' in workflow
    assert '"$image:package-bootstrap"' in workflow
    assert "--load" in workflow
    assert "--push" in workflow
    assert "gh release" not in workflow
    assert '--tag "$image:package-bootstrap"' not in workflow
    assert ":v0.0.0" not in workflow


def test_release_bundle_sources_do_not_include_ai_skill_as_standalone_artifact() -> None:
    release_files = "\n".join(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "infra/release").rglob("*")
        if path.is_file()
    )

    assert "packages/ai-skills" not in release_files
    assert "surgepilot-public-api" not in release_files


def test_demo_node_image_contains_no_default_password_or_host_identity() -> None:
    dockerfile = (ROOT / "infra/docker/demo-load-node/Dockerfile").read_text(encoding="utf-8")
    entrypoint = (ROOT / "infra/docker/demo-load-node/entrypoint.sh").read_text(encoding="utf-8")

    assert 'echo "surgepilot:surgepilot"' not in dockerfile
    assert "passwd -l surgepilot" in dockerfile
    assert "rm -rf /var/lib/apt/lists/* /etc/ssh/ssh_host_*" in dockerfile
    assert "org.opencontainers.image.source" in dockerfile
    assert "/run/secrets/surgepilot_demo_password" in entrypoint
    assert "/run/surgepilot/host-keys" in entrypoint
    assert 'cat "$password_file"' in entrypoint
    assert "printf 'surgepilot:%s\\n' \"$password\" | chpasswd" in entrypoint
    assert "set -x" not in entrypoint


def test_runtime_builder_pins_debian_12_for_java_17_availability() -> None:
    dockerfile = (ROOT / "infra/docker/runtime-builder/Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith("FROM python:3.12-slim-bookworm\n")
    assert "build-essential" in dockerfile
    assert "openjdk-17-jre-headless" in dockerfile
    assert "ENV UV_PROJECT_ENVIRONMENT=/tmp/surgepilot-runtime-builder-venv" in dockerfile
    assert "ENV UV_FROZEN=1" in dockerfile
    assert (
        "COPY infra/docker/runtime-builder/Dockerfile "
        "./infra/docker/runtime-builder/Dockerfile" in dockerfile
    )


def test_api_and_web_release_images_have_oci_labels_and_bounded_release_tools() -> None:
    api = (ROOT / "apps/api/Dockerfile").read_text(encoding="utf-8")
    web = (ROOT / "apps/web/Dockerfile").read_text(encoding="utf-8")

    for dockerfile in (api, web):
        assert "org.opencontainers.image.source" in dockerfile
        assert "org.opencontainers.image.revision" in dockerfile
        assert "org.opencontainers.image.version" in dockerfile
    assert "/opt/surgepilot/release-tools/bootstrap_deployment_env.py" in api
    assert "/opt/surgepilot/release-tools/release_preflight.py" in api
    assert "/opt/surgepilot/release-tools/fetch_runtime_release.py" in api
    assert "COPY . /" not in api
