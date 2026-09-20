from __future__ import annotations

from importlib import metadata

import pytest


def test_runner_product_version_prefers_generated_bundle_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from surgepilot_runner import product_version

    version_file = tmp_path / "VERSION"
    version_file.write_text("2.3.4\n", encoding="utf-8")
    monkeypatch.setattr(
        product_version.metadata,
        "version",
        lambda _name: pytest.fail("bundle version must win"),
    )

    assert product_version.resolve_product_version(version_file=version_file) == "2.3.4"


def test_runner_product_version_falls_back_to_installed_metadata_when_bundle_file_is_absent(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from surgepilot_runner import product_version

    monkeypatch.setattr(product_version.metadata, "version", lambda name: "3.4.5")

    assert product_version.resolve_product_version(version_file=tmp_path / "missing") == "3.4.5"


@pytest.mark.parametrize("content", ["v1.2.3\n", "01.2.3\n", "1.2.3", "1.2.3\nextra\n", "0.0.0\n"])
def test_runner_product_version_rejects_invalid_present_bundle_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    from surgepilot_runner import product_version

    version_file = tmp_path / "VERSION"
    version_file.write_text(content, encoding="utf-8")
    monkeypatch.setattr(
        product_version.metadata,
        "version",
        lambda _name: pytest.fail("invalid bundle content must fail closed"),
    )

    with pytest.raises(RuntimeError, match="Runner product version"):
        product_version.resolve_product_version(version_file=version_file)


def test_runner_product_version_fails_when_metadata_is_missing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from surgepilot_runner import product_version

    def missing(_name: str) -> str:
        raise metadata.PackageNotFoundError("surgepilot-runner")

    monkeypatch.setattr(product_version.metadata, "version", missing)

    with pytest.raises(RuntimeError, match="surgepilot-runner package metadata is unavailable"):
        product_version.resolve_product_version(version_file=tmp_path / "missing")


@pytest.mark.parametrize("installed", ["v1.2.3", "01.2.3", "0.0.0", "dev"])
def test_runner_product_version_rejects_invalid_installed_metadata(
    tmp_path, monkeypatch: pytest.MonkeyPatch, installed: str
) -> None:
    from surgepilot_runner import product_version

    monkeypatch.setattr(product_version.metadata, "version", lambda _name: installed)

    with pytest.raises(RuntimeError, match="Runner product version"):
        product_version.resolve_product_version(version_file=tmp_path / "missing")
