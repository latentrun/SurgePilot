from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path


def load_smoke_stack_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "verify_smoke_stack.py"
    spec = importlib.util.spec_from_file_location("verify_smoke_stack", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_stack_does_not_wait_on_one_shot_migration_services(monkeypatch):
    smoke_stack = load_smoke_stack_module()
    calls: list[list[str]] = []

    def fake_run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr=None)

    monkeypatch.delenv("SURGEPILOT_SMOKE_KEEP_STACK", raising=False)
    monkeypatch.setattr(smoke_stack, "run", fake_run)
    monkeypatch.setattr(smoke_stack, "wait_for_healthz", lambda: None)
    monkeypatch.setattr(smoke_stack, "assert_worker_is_clean", lambda: None)

    assert smoke_stack.main() == 0

    assert calls[0] == ["up", "-d", "--build"]
    assert "--wait" not in calls[0]
    assert calls[-1] == ["down", "-v"]


def test_smoke_stack_supplies_a_test_only_runner_token(monkeypatch):
    smoke_stack = load_smoke_stack_module()
    captured_env: dict[str, str] = {}

    def fake_subprocess_run(*_args, **kwargs):
        captured_env.update(kwargs["env"])
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=None)

    monkeypatch.delenv("RUNNER_INTERNAL_TOKEN", raising=False)
    monkeypatch.setattr(smoke_stack.subprocess, "run", fake_subprocess_run)

    smoke_stack.run(["config"])

    assert captured_env["RUNNER_INTERNAL_TOKEN"] == smoke_stack.TEST_RUNNER_INTERNAL_TOKEN
    assert captured_env["MINIO_ACCESS_KEY"] == smoke_stack.TEST_MINIO_ACCESS_KEY
    assert captured_env["MINIO_SECRET_KEY"] == smoke_stack.TEST_MINIO_SECRET_KEY
    assert captured_env["MINIO_ROOT_USER"] == smoke_stack.TEST_MINIO_ACCESS_KEY
    assert captured_env["MINIO_ROOT_PASSWORD"] == smoke_stack.TEST_MINIO_SECRET_KEY
    assert captured_env["MINIO_BUCKET"] == smoke_stack.TEST_MINIO_BUCKET
