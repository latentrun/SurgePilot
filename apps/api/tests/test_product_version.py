from __future__ import annotations

from importlib import metadata

import pytest


def test_product_version_accepts_canonical_core_and_one_optional_prefix() -> None:
    from app.core.product_version import normalize_product_version

    assert normalize_product_version("1.2.3") == "1.2.3"
    assert normalize_product_version("v1.2.3") == "1.2.3"
    assert normalize_product_version("10.20.30") == "10.20.30"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "v",
        "vv1.2.3",
        "01.2.3",
        "1.02.3",
        "1.2.03",
        "1.2",
        "1.2.3.4",
        "dev",
        "validation-abc",
        "0.0.0",
        " 1.2.3",
        "1.2.3\n",
    ],
)
def test_product_version_rejects_noncanonical_values(value: str) -> None:
    from app.core.product_version import normalize_product_version

    with pytest.raises(RuntimeError, match="product version"):
        normalize_product_version(value)


def test_product_version_uses_explicit_environment_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import product_version

    monkeypatch.setenv("SURGEPILOT_PRODUCT_VERSION", "v2.3.4")
    monkeypatch.setattr(
        product_version.metadata,
        "version",
        lambda _name: pytest.fail("package fallback must not run"),
    )

    assert product_version.resolve_product_version() == "2.3.4"


@pytest.mark.parametrize("environment_value", [None, ""])
def test_product_version_falls_back_to_installed_api_metadata(
    monkeypatch: pytest.MonkeyPatch, environment_value: str | None
) -> None:
    from app.core import product_version

    if environment_value is None:
        monkeypatch.delenv("SURGEPILOT_PRODUCT_VERSION", raising=False)
    else:
        monkeypatch.setenv("SURGEPILOT_PRODUCT_VERSION", environment_value)
    monkeypatch.setattr(product_version.metadata, "version", lambda name: "3.4.5")

    assert product_version.resolve_product_version() == "3.4.5"


def test_product_version_fails_when_installed_metadata_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import product_version

    monkeypatch.delenv("SURGEPILOT_PRODUCT_VERSION", raising=False)

    def missing(_name: str) -> str:
        raise metadata.PackageNotFoundError("surgepilot-api")

    monkeypatch.setattr(product_version.metadata, "version", missing)

    with pytest.raises(RuntimeError, match="surgepilot-api package metadata is unavailable"):
        product_version.resolve_product_version()


@pytest.mark.parametrize("installed", ["v1.2.3", "01.2.3", "0.0.0", "dev"])
def test_product_version_rejects_invalid_installed_metadata(
    monkeypatch: pytest.MonkeyPatch, installed: str
) -> None:
    from app.core import product_version

    monkeypatch.delenv("SURGEPILOT_PRODUCT_VERSION", raising=False)
    monkeypatch.setattr(product_version.metadata, "version", lambda _name: installed)

    with pytest.raises(RuntimeError, match="product version"):
        product_version.resolve_product_version()


def test_product_version_does_not_fall_back_for_invalid_explicit_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import product_version

    monkeypatch.setenv("SURGEPILOT_PRODUCT_VERSION", "validation-deadbeef")
    monkeypatch.setattr(
        product_version.metadata,
        "version",
        lambda _name: pytest.fail("invalid explicit input must fail closed"),
    )

    with pytest.raises(RuntimeError, match="product version"):
        product_version.resolve_product_version()
