from __future__ import annotations

import copy
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def sample_openapi() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "SurgePilot API",
            "version": "0.1.0",
            "x-surgepilot-error-codes": [
                "PUBLIC_TOKEN_SCOPE_DENIED",
                "LOAD_NODE_SSH_HOST_KEY_CHANGED",
            ],
        },
        "paths": {
            "/api/v1/scenarios": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/WebResponse"}
                                }
                            }
                        }
                    }
                }
            },
            "/api/public/v1/scenarios": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/PublicResponse"}
                                }
                            }
                        }
                    }
                }
            },
            "/api/internal/v1/runner/callbacks": {"post": {}},
            "/api/healthz": {"get": {}},
        },
        "components": {
            "schemas": {
                "WebResponse": {"type": "object"},
                "PublicResponse": {
                    "type": "object",
                    "properties": {"item": {"$ref": "#/components/schemas/Shared"}},
                },
                "Shared": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "enum": [
                                "PUBLIC_TOKEN_SCOPE_DENIED",
                                "LOAD_NODE_SSH_HOST_KEY_CHANGED",
                            ],
                        }
                    },
                },
                "Unused": {"type": "object"},
            }
        },
    }


def test_shared_openapi_export_preserves_web_and_public_semantics() -> None:
    module = importlib.import_module("app.services.openapi_export")
    source = sample_openapi()
    original = copy.deepcopy(source)

    web = module._export_document(source, public=False)
    public = module._export_document(source, public=True)

    assert source == original
    assert web["servers"] == [{"url": "/api"}]
    assert list(web["paths"]) == ["/v1/scenarios"]
    assert set(web["components"]["schemas"]) == {
        "WebResponse",
        "PublicResponse",
        "Shared",
        "Unused",
    }

    assert public["servers"] == [{"url": "/api"}]
    assert list(public["paths"]) == ["/public/v1/scenarios"]
    assert set(public["components"]["schemas"]) == {"PublicResponse", "Shared"}
    assert public["info"]["x-surgepilot-error-codes"] == ["PUBLIC_TOKEN_SCOPE_DENIED"]
    assert public["components"]["schemas"]["Shared"]["properties"]["code"]["enum"] == [
        "PUBLIC_TOKEN_SCOPE_DENIED"
    ]


def test_export_script_imports_shared_module_instead_of_defining_export_logic() -> None:
    source = (ROOT / "scripts/export_openapi.py").read_text()

    assert "from app.services.openapi_export import _export_document" in source
    assert "def _filter_paths(" not in source
    assert "def _export_document(" not in source
