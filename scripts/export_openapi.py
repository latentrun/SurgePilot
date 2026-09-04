"""Export the browser-facing OpenAPI artifact from the FastAPI application."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / "apps" / "api"
OPENAPI_OUTPUT_PATH = ROOT / "packages" / "contracts" / "openapi" / "api.openapi.json"


def _normalize_path(path: str) -> str | None:
    """Convert runtime /api routes to the published /api + /v1 contract."""

    if path == "/api/v1":
        return "/v1"
    if path.startswith("/api/v1/"):
        return path.removeprefix("/api")
    # Health/docs/OpenAPI and internal routes are not browser business contracts.
    return None


def _export_document(source: dict[str, Any]) -> dict[str, Any]:
    document = copy.deepcopy(source)
    paths = document.get("paths", {})
    document["paths"] = {
        normalized_path: value
        for path, value in paths.items()
        if (normalized_path := _normalize_path(path)) is not None
    }
    # Keep the generated client shape stable while the M0 API has no schemas yet.
    document.setdefault("components", {}).setdefault("schemas", {})
    document["servers"] = [{"url": "/api"}]
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=OPENAPI_OUTPUT_PATH,
        help="OpenAPI artifact path (defaults to packages/contracts/openapi/api.openapi.json).",
    )
    args = parser.parse_args()

    sys.path.insert(0, str(API_PATH))
    from app.main import app

    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(_export_document(app.openapi()), indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
