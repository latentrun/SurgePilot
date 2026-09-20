from __future__ import annotations

from importlib import metadata
from pathlib import Path
import re


_CANONICAL_PRODUCT_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


def _validate_product_version(value: str) -> str:
    if value == "0.0.0" or _CANONICAL_PRODUCT_VERSION.fullmatch(value) is None:
        raise RuntimeError(f"Invalid SurgePilot Runner product version: {value!r}.")
    return value


def resolve_product_version(*, version_file: Path | None = None) -> str:
    path = version_file or Path(__file__).with_name("VERSION")
    if path.exists():
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise RuntimeError("SurgePilot Runner product version file is unreadable.") from exc
        if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
            raise RuntimeError("Invalid SurgePilot Runner product version file.")
        try:
            value = raw[:-1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError("Invalid SurgePilot Runner product version file.") from exc
        return _validate_product_version(value)

    try:
        installed = metadata.version("surgepilot-runner")
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError("surgepilot-runner package metadata is unavailable.") from exc
    return _validate_product_version(installed)
