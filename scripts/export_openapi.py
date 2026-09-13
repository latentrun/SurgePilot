import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / "apps/api"
WEB_OUTPUT_PATH = ROOT / "packages/contracts/openapi/api.openapi.json"
PUBLIC_OUTPUT_PATH = ROOT / "packages/contracts/openapi/public-api.openapi.json"


def main() -> None:
    sys.path.insert(0, str(API_PATH))
    from app.services.openapi_export import _export_document
    from app.main import app

    WEB_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    source = app.openapi()
    WEB_OUTPUT_PATH.write_text(
        json.dumps(_export_document(source, public=False), indent=2, sort_keys=True) + "\n"
    )
    PUBLIC_OUTPUT_PATH.write_text(
        json.dumps(_export_document(source, public=True), indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
