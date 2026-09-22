from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
DISPATCHER = ROOT / "infra/release/dispatcher"


def install_dispatcher(tmp_path: Path, *, state: str) -> Path:
    install_root = tmp_path / "surgepilot"
    release_root = install_root / ".releases/v1.2.0"
    release_root.mkdir(parents=True)
    dispatcher = install_root / "surgepilot"
    shutil.copy2(DISPATCHER, dispatcher)
    dispatcher.chmod(0o700)
    (install_root / ".release-state").write_text(state, encoding="utf-8")
    (install_root / ".release-state").chmod(0o600)
    wrapper = release_root / "surgepilot"
    wrapper.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "printf '%s|%s|%s|%s|%s\\n' \"$SURGEPILOT_DEPLOYMENT_ROOT\" "
        '"$SURGEPILOT_RELEASE_ROOT" "$SURGEPILOT_RELEASE_PHASE" '
        '"$SURGEPILOT_RELEASE_TARGET" "$SURGEPILOT_RELEASE_BASE"\n'
        'owner="$SURGEPILOT_DEPLOYMENT_ROOT.lock/owner"\n'
        'grep -q "^pid=$SURGEPILOT_LOCK_PID$" "$owner"\n'
        'grep -q "^nonce=$SURGEPILOT_LOCK_NONCE$" "$owner"\n'
        'rm -f "$owner"\n'
        'rmdir "$SURGEPILOT_DEPLOYMENT_ROOT.lock"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    return dispatcher


def test_dispatcher_selects_exact_target_and_holds_lock_through_wrapper(tmp_path: Path) -> None:
    dispatcher = install_dispatcher(
        tmp_path,
        state="schema=1\nphase=prepared\ntarget=v1.2.0\nbase=v1.1.0\n",
    )

    result = subprocess.run([dispatcher, "status"], text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    install_root = dispatcher.parent
    assert result.stdout.strip() == (
        f"{install_root}|{install_root / '.releases/v1.2.0'}|prepared|v1.2.0|v1.1.0"
    )
    assert not Path(f"{install_root}.lock").exists()


def test_dispatcher_rejects_malformed_state_without_stranding_its_lock(tmp_path: Path) -> None:
    dispatcher = install_dispatcher(
        tmp_path,
        state="schema=1\ntarget=v1.2.0\nphase=installed\nbase=none\n",
    )

    result = subprocess.run([dispatcher, "status"], text=True, capture_output=True)

    assert result.returncode != 0
    assert "release state" in result.stderr.lower()
    assert not Path(f"{dispatcher.parent}.lock").exists()


def test_dispatcher_never_reclaims_an_existing_lock(tmp_path: Path) -> None:
    dispatcher = install_dispatcher(
        tmp_path,
        state="schema=1\nphase=stable\ntarget=v1.2.0\nbase=v1.2.0\n",
    )
    lock = Path(f"{dispatcher.parent}.lock")
    lock.mkdir(mode=0o700)
    (lock / "owner").write_text("schema=1\npid=999999\nnonce=stale\n", encoding="utf-8")
    (lock / "owner").chmod(0o600)

    result = subprocess.run([dispatcher, "status"], text=True, capture_output=True)

    assert result.returncode != 0
    assert "stale deployment lock" in result.stderr.lower()
    assert lock.is_dir()
    assert (lock / "owner").is_file()


def test_dispatcher_ignores_injected_internal_environment(tmp_path: Path) -> None:
    dispatcher = install_dispatcher(
        tmp_path,
        state="schema=1\nphase=stable\ntarget=v1.2.0\nbase=v1.2.0\n",
    )
    environment = os.environ.copy()
    environment.update(
        {
            "SURGEPILOT_DEPLOYMENT_ROOT": "/tmp/injected",
            "SURGEPILOT_RELEASE_ROOT": "/tmp/injected",
            "SURGEPILOT_LOCK_NONCE": "injected",
        }
    )

    result = subprocess.run([dispatcher, "status"], env=environment, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(f"{dispatcher.parent}|")


@pytest.mark.parametrize(
    "state",
    [
        "schema=1\nphase=installed\ntarget=v1.2.0\nbase=v1.1.0\n",
        "schema=1\nphase=stable\ntarget=v1.2.0\nbase=v1.1.0\n",
        "schema=1\nphase=prepared\ntarget=v1.2.0\nbase=none\n",
        "schema=1\nphase=stable\ntarget=v01.2.0\nbase=v01.2.0\n",
    ],
)
def test_dispatcher_rejects_invalid_cross_field_state(tmp_path: Path, state: str) -> None:
    dispatcher = install_dispatcher(tmp_path, state=state)

    result = subprocess.run([dispatcher, "status"], text=True, capture_output=True)

    assert result.returncode != 0
    assert "release state" in result.stderr.lower()
    assert not Path(f"{dispatcher.parent}.lock").exists()


def test_dispatcher_rejects_non_private_state_file(tmp_path: Path) -> None:
    dispatcher = install_dispatcher(
        tmp_path,
        state="schema=1\nphase=stable\ntarget=v1.2.0\nbase=v1.2.0\n",
    )
    (dispatcher.parent / ".release-state").chmod(0o644)

    result = subprocess.run([dispatcher, "status"], text=True, capture_output=True)

    assert result.returncode != 0
    assert "release state" in result.stderr.lower()
