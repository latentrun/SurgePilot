from __future__ import annotations

import pytest

from app.services import runner_bundle
from app.services.runner_bundle import RunnerBundle, default_runner_bundle_dir


def make_bundle_dir(tmp_path):
    root = tmp_path / "bundle"
    package_dir = root / "surgepilot_runner"
    package_dir.mkdir(parents=True)
    (root / "runner.py").write_text("print('runner')\n")
    (package_dir / "__init__.py").write_text("\n")
    (package_dir / "cli.py").write_text("print('cli')\n")
    return root


def test_runner_bundle_lists_runner_files_with_modes_and_product_version(tmp_path) -> None:
    root = make_bundle_dir(tmp_path)

    files = RunnerBundle(root, product_version="2.3.4").files()

    assert [file.relative_path for file in files] == [
        "runner.py",
        "surgepilot_runner/__init__.py",
        "surgepilot_runner/cli.py",
        "surgepilot_runner/VERSION",
    ]
    assert files[0].mode == 0o755
    assert files[1].mode == 0o644
    assert files[2].content == b"print('cli')\n"
    assert files[3].content == b"2.3.4\n"
    assert files[3].mode == 0o644


def test_runner_bundle_rejects_missing_required_files(tmp_path) -> None:
    root = tmp_path / "bundle"
    root.mkdir()

    with pytest.raises(FileNotFoundError, match="Runner bundle is missing required files"):
        RunnerBundle(root).files()


def test_default_runner_bundle_dir_prefers_configured_path(tmp_path, monkeypatch) -> None:
    root = make_bundle_dir(tmp_path)
    monkeypatch.setenv("SURGEPILOT_RUNNER_BUNDLE_DIR", str(root))

    assert default_runner_bundle_dir() == root


def test_default_runner_bundle_dir_uses_configured_path_in_container_layout(
    tmp_path, monkeypatch
) -> None:
    root = make_bundle_dir(tmp_path)
    monkeypatch.setenv("SURGEPILOT_RUNNER_BUNDLE_DIR", str(root))
    monkeypatch.setattr(
        runner_bundle,
        "__file__",
        "/app/app/services/runner_bundle.py",
    )

    assert default_runner_bundle_dir() == root
