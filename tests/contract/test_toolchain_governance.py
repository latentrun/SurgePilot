from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_TOOLS = {
    "python": "3.12",
    "node": "22",
    "pnpm": "11.3.0",
    "uv": "0.12.17",
}
EXPECTED_MISE_ARTIFACTS = {
    "mise-v2026.9.11-linux-arm64.tar.gz": (
        "d781ce1b4daad6ead469b0a57fef4bfb49c4e02025dc88111ff1bfaa8c90aad9"
    ),
    "mise-v2026.9.11-linux-x64.tar.gz": (
        "02a19e4a5eda23cda916503ad09dbc608a249fe7a7d5686c5a74ff3a7ce3b7e0"
    ),
    "mise-v2026.9.11-macos-arm64.tar.gz": (
        "34e8296f932c1d6f3b84d924bbb9f2841336d7bee1c373005d479e13664cb6c0"
    ),
    "mise-v2026.9.11-macos-x64.tar.gz": (
        "46a67b050d53f1ee795353f8ff5ecfd79328a1f6415f4b3ede79ecda7223f969"
    ),
}


def test_repository_toolchain_declaration_matches_ecosystem_metadata() -> None:
    mise = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    root_python = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    api_python = tomllib.loads((ROOT / "apps/api/pyproject.toml").read_text(encoding="utf-8"))
    runner_python = tomllib.loads((ROOT / "apps/runner/pyproject.toml").read_text(encoding="utf-8"))

    assert mise == {"tools": EXPECTED_TOOLS}
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.12"
    assert (ROOT / ".nvmrc").read_text(encoding="utf-8").strip() == "22"
    assert package["packageManager"] == "pnpm@11.3.0"
    assert root_python["tool"]["ruff"]["target-version"] == "py312"
    assert api_python["project"]["requires-python"] == ">=3.12"
    assert runner_python["project"]["requires-python"] == ">=3.12"


def test_pinned_mise_artifact_manifest_matches_the_accepted_adr() -> None:
    manifest = ROOT / "scripts/toolchain-mise.sha256"
    actual = {
        artifact.removeprefix("./"): digest
        for digest, artifact in (
            line.split() for line in manifest.read_text(encoding="utf-8").splitlines()
        )
    }
    adr = (ROOT / "docs/sdd/adr/ADR-0028-contributor-toolchain-mise.md").read_text(encoding="utf-8")

    assert actual == EXPECTED_MISE_ARTIFACTS
    for artifact, digest in EXPECTED_MISE_ARTIFACTS.items():
        assert artifact in adr
        assert digest in adr


def test_mise_lockfiles_cannot_silently_change_series_policy() -> None:
    assert not list(ROOT.glob("mise*.lock"))


def test_wrapper_contains_complete_mise_and_uv_isolation_controls() -> None:
    wrapper = (ROOT / "scripts/toolchain").read_text(encoding="utf-8")
    required_assignments = {
        "MISE_SYSTEM_DATA_DIR": "$SURGEPILOT_TOOLCHAIN_DATA_ROOT/mise-system",
        "MISE_LOCKFILE": "false",
        "MISE_ENABLE_TOOLS": "python,node,pnpm,uv",
        "MISE_OVERRIDE_CONFIG_FILENAMES": "mise.toml",
        "MISE_OVERRIDE_TOOL_VERSIONS_FILENAMES": "none",
        "MISE_AUTO_ENV": "false",
        "MISE_AUTO_INSTALL": "0",
        "MISE_EXEC_AUTO_INSTALL": "0",
        "MISE_NOT_FOUND_AUTO_INSTALL": "0",
        "MISE_TASK_RUN_AUTO_INSTALL": "0",
        "MISE_NOT_FOUND_SYSTEM_FALLBACK": "0",
        "UV_PYTHON_DOWNLOADS": "never",
        "UV_NO_MANAGED_PYTHON": "1",
    }

    for name, value in required_assignments.items():
        assert f"{name}={value}" in wrapper


def make_environment(tmp_path: Path) -> dict[str, str]:
    commands = tmp_path / "commands"
    commands.mkdir(parents=True)
    versions = {
        "python": "Python 3.12.11",
        "uv": "uv 0.12.17",
        "node": "v22.18.0",
        "pnpm": "11.3.0",
    }
    for name, version in versions.items():
        path = commands / name
        path.write_text(f"#!/bin/sh\nprintf '%s\\n' '{version}'\n", encoding="utf-8")
        path.chmod(0o755)
    environment = os.environ.copy()
    environment.pop("SURGEPILOT_TOOLCHAIN_ACTIVE", None)
    environment.update(
        {
            "HOME": str(tmp_path / "home"),
            "PATH": f"{commands}{os.pathsep}{environment['PATH']}",
            "SURGEPILOT_TOOLCHAIN_MODE": "external",
            "SURGEPILOT_TOOLCHAIN_EXTERNAL_TOOLS": "python,uv,node,pnpm",
        }
    )
    return environment


def run_make(tmp_path: Path, *goals: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", "-n", *goals],
        cwd=ROOT,
        env=make_environment(tmp_path),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_make_dispatches_required_and_mixed_goals_once(tmp_path: Path) -> None:
    required = run_make(tmp_path / "required", "setup")
    mixed = run_make(tmp_path / "mixed", "help", "setup")

    assert required.returncode == 0, required.stderr
    assert mixed.returncode == 0, mixed.stderr
    assert required.stdout.count("scripts/toolchain exec --") == 1
    assert mixed.stdout.count("scripts/toolchain exec --") == 1
    assert "make help setup" in mixed.stdout


def test_make_reentry_preserves_overrides_jobserver_and_recursive_sentinel(
    tmp_path: Path,
) -> None:
    environment = make_environment(tmp_path)
    overridden = subprocess.run(
        ["make", "-n", "-j2", "dev-api", "DEPLOYMENT_ENV_RUN=custom-prefix"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    recursive = subprocess.run(
        ["make", "-n", "-j2", "test"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert overridden.returncode == 0, overridden.stderr
    assert "custom-prefix uv run" in overridden.stdout
    assert "jobserver unavailable" not in overridden.stderr
    assert recursive.returncode == 0, recursive.stderr
    assert recursive.stdout.count("scripts/toolchain exec --") == 1
    assert "jobserver unavailable" not in recursive.stderr


def test_make_free_and_default_goals_never_dispatch(tmp_path: Path) -> None:
    free = run_make(tmp_path / "free", "help", "dev")
    default = run_make(tmp_path / "default")

    assert free.returncode == 0, free.stderr
    assert default.returncode == 0, default.stderr
    assert "scripts/toolchain" not in free.stdout
    assert "scripts/toolchain" not in default.stdout


def test_make_rejects_mixed_management_goals_before_recipes(tmp_path: Path) -> None:
    result = run_make(tmp_path / "mixed-management", "toolchain-check", "help")

    assert result.returncode != 0
    assert "must be requested alone" in result.stderr
    assert "scripts/toolchain" not in result.stdout


def test_make_captures_original_xdg_before_temporary_runtime_default() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    capture = makefile.index("ORIGINAL_XDG_DATA_HOME :=")
    runtime_default = makefile.index("export XDG_DATA_HOME ?= /tmp/surgepilot-xdg-data")
    assert capture < runtime_default
    assert "surgepilot-contributor-toolchain" in makefile


def workflow_jobs(path: Path) -> dict[str, object]:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    return workflow["jobs"]


def test_ci_setup_actions_match_repository_tool_versions() -> None:
    expected_setups = {
        "actions/setup-python@": ("python-version", "3.12"),
        "actions/setup-node@": ("node-version", "22"),
        "pnpm/action-setup@": ("version", "11.3.0"),
        "astral-sh/setup-uv@": ("version", "0.12.17"),
    }
    setup_counts = dict.fromkeys(expected_setups, 0)

    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        for job_name, job_value in workflow_jobs(path).items():
            for step in dict(job_value).get("steps", []):
                action = str(step.get("uses", ""))
                for prefix, (field, expected) in expected_setups.items():
                    if not action.startswith(prefix):
                        continue
                    setup_counts[prefix] += 1
                    actual = str(step.get("with", {}).get(field, ""))
                    assert actual == expected, (
                        f"{path.name}:{job_name} must configure {prefix} {field}={expected}"
                    )

    assert all(count > 0 for count in setup_counts.values())


def test_ci_external_make_jobs_declare_validated_tools() -> None:
    workflow_paths = sorted((ROOT / ".github/workflows").glob("*.yml"))
    make_jobs = 0
    for path in workflow_paths:
        for job_name, job_value in workflow_jobs(path).items():
            job = dict(job_value)
            steps = job.get("steps", [])
            if not any(
                re.search(r"\bmake [A-Za-z0-9_-]+", str(step.get("run", ""))) for step in steps
            ):
                continue
            if job_name == "managed-toolchain-smoke":
                continue
            make_jobs += 1
            environment = job.get("env", {})
            assert environment.get("SURGEPILOT_TOOLCHAIN_MODE") == "external"
            declared = str(environment.get("SURGEPILOT_TOOLCHAIN_EXTERNAL_TOOLS", "")).split(",")
            assert declared and all(tool in EXPECTED_TOOLS for tool in declared)
            assert len(declared) == len(set(declared))

    assert make_jobs > 0


def test_release_validation_has_native_managed_fresh_clone_smoke() -> None:
    jobs = workflow_jobs(ROOT / ".github/workflows/release-validation.yml")
    smoke = jobs["managed-toolchain-smoke"]
    steps = smoke["steps"]
    uses = "\n".join(str(step.get("uses", "")) for step in steps)
    commands = "\n".join(str(step.get("run", "")) for step in steps)

    assert smoke["strategy"]["matrix"]["runner"] == ["ubuntu-24.04", "macos-14"]
    assert "setup-python" not in uses
    assert "setup-node" not in uses
    assert "setup-uv" not in uses
    assert "pnpm/action-setup" not in uses
    for command in (
        "make toolchain-install",
        "make toolchain-check",
        "make setup",
        "make toolchain-tests",
    ):
        assert command in commands


def test_ci_jobs_using_host_python_provision_python_312_in_the_same_job() -> None:
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        for job_name, job_value in workflow_jobs(path).items():
            steps = dict(job_value).get("steps", [])
            commands = "\n".join(str(step.get("run", "")) for step in steps)
            if not re.search(r"(^|[\s;&|])python3?(?:\s|$)", commands):
                continue
            setup_steps = [
                step
                for step in steps
                if str(step.get("uses", "")).startswith("actions/setup-python@")
            ]
            assert len(setup_steps) == 1, f"{path.name}:{job_name} must set up Python once"
            assert setup_steps[0].get("with", {}).get("python-version") == "3.12"
