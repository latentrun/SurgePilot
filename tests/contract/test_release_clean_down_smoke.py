from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]


def run_clean_down_fixture(
    tmp_path: Path, *, mode: str
) -> tuple[subprocess.CompletedProcess, int, bool]:
    workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    step = next(
        step
        for step in workflow["jobs"]["upgrade-smoke"]["steps"]
        if step.get("name") == "Upgrade persisted source data and complete a target Run"
    )
    fixture = (
        step["run"]
        .split("make verify-p2-05-release-stack\n", 1)[1]
        .split('if [ -f "$source_compose_backup" ]; then', 1)[0]
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    count_file = tmp_path / "count"
    down_file = tmp_path / "down"
    docker = bin_dir / "docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "path = pathlib.Path(os.environ['PROBE_COUNT'])\n"
        "count = int(path.read_text()) + 1 if path.exists() else 1\n"
        "path.write_text(str(count))\n"
        "mode = os.environ['PROBE_MODE']\n"
        "if mode == 'error': sys.exit(2)\n"
        "if mode == 'invalid': print('invalid JSON'); sys.exit(0)\n"
        "status = 'quiescent' if mode == 'eventually' and count >= 2 else 'blocked'\n"
        "print(json.dumps({'status': status, 'counts': {'reports': int(status == 'blocked')}}))\n"
    )
    docker.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o755)
    surgepilot = bin_dir / "surgepilot"
    surgepilot.write_text('#!/bin/sh\n[ "$1" = down ] || exit 1\ntouch "$DOWN_FILE"\n')
    surgepilot.chmod(0o755)

    result = subprocess.run(
        ["sh", "-c", "set -eu\n" + fixture],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "SOURCE_MODE": "clean_down",
            "SURGEPILOT": str(surgepilot),
            "PROBE_COUNT": str(count_file),
            "PROBE_MODE": mode,
            "DOWN_FILE": str(down_file),
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result, int(count_file.read_text()) if count_file.exists() else 0, down_file.exists()


def test_clean_down_waits_for_pending_work_before_stopping_source(tmp_path: Path) -> None:
    result, attempts, stopped = run_clean_down_fixture(tmp_path, mode="eventually")

    assert result.returncode == 0, result.stderr
    assert attempts == 2
    assert stopped
    assert '"reports": 1' in result.stdout
    assert '"reports": 0' in result.stdout


@pytest.mark.parametrize(
    ("mode", "expected_attempts"), [("blocked", 30), ("error", 1), ("invalid", 1)]
)
def test_clean_down_refuses_to_stop_source_without_quiescence(
    tmp_path: Path, mode: str, expected_attempts: int
) -> None:
    result, attempts, stopped = run_clean_down_fixture(tmp_path, mode=mode)

    assert result.returncode != 0
    assert attempts == expected_attempts
    assert not stopped
