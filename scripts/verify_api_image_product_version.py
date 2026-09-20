"""Fail closed when an API image does not contain one coherent product version."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


SKILL_OPENAPI_PATH = Path(
    "/opt/surgepilot/ai-skills/surgepilot-public-api/references/public-api.openapi.json"
)


def assert_baked_product_version(baked: str | None, expected: str | None) -> str:
    if not baked:
        raise RuntimeError("API image product version is missing")
    if not expected:
        raise RuntimeError("Expected product version is required")
    if baked != expected:
        raise RuntimeError(
            f"API image product version mismatch: expected {expected}, got {baked!r}"
        )
    return expected


def assert_document_version(name: str, document: dict[str, Any], expected: str) -> None:
    actual = document.get("info", {}).get("version")
    if actual != expected:
        raise RuntimeError(f"{name} version mismatch: expected {expected}, got {actual!r}")


def verify_api_image_product_version() -> None:
    expected = assert_baked_product_version(
        os.environ.get("SURGEPILOT_PRODUCT_VERSION"),
        os.environ.get("SURGEPILOT_EXPECTED_PRODUCT_VERSION"),
    )

    from app.main import app
    from app.services.openapi_export import _export_document

    runtime = app.openapi()
    assert_document_version("runtime OpenAPI", runtime, expected)
    assert_document_version(
        "curated internal OpenAPI", _export_document(runtime, public=False), expected
    )
    assert_document_version(
        "curated public OpenAPI", _export_document(runtime, public=True), expected
    )
    try:
        skill_document = json.loads(SKILL_OPENAPI_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("AI skill OpenAPI is unavailable or invalid") from exc
    assert_document_version("AI skill OpenAPI", skill_document, expected)


def main() -> int:
    verify_api_image_product_version()
    print("API image product version identity verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
