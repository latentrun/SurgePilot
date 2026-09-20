from __future__ import annotations

from importlib import metadata
import os
import re


_CANONICAL_PRODUCT_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


def normalize_product_version(value: str) -> str:
    normalized = value.removeprefix("v")
    return validate_product_version(normalized, source_value=value)


def validate_product_version(value: str, *, source_value: str | None = None) -> str:
    if value == "0.0.0" or _CANONICAL_PRODUCT_VERSION.fullmatch(value) is None:
        raise RuntimeError(f"Invalid SurgePilot product version: {source_value or value!r}.")
    return value


def resolve_product_version() -> str:
    configured = os.environ.get("SURGEPILOT_PRODUCT_VERSION")
    if configured:
        return normalize_product_version(configured)
    try:
        installed = metadata.version("surgepilot-api")
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError("surgepilot-api package metadata is unavailable.") from exc
    return validate_product_version(installed)


PRODUCT_VERSION = resolve_product_version()
