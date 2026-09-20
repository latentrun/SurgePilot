from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_api_image_product_version import assert_document_version  # noqa: E402


def test_assert_document_version_accepts_exact_product_version() -> None:
    assert_document_version("runtime OpenAPI", {"info": {"version": "2.3.4"}}, "2.3.4")


@pytest.mark.parametrize("version", [None, "v2.3.4", "2.3.5"])
def test_assert_document_version_rejects_missing_or_mismatched_version(version: object) -> None:
    with pytest.raises(RuntimeError, match="runtime OpenAPI"):
        assert_document_version("runtime OpenAPI", {"info": {"version": version}}, "2.3.4")
