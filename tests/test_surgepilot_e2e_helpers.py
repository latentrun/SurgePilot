from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPT_DIR / "surgepilot_e2e_helpers.py"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location("surgepilot_e2e_helpers", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


ULID_LIKE = re.compile(r"^[A-Z0-9]{26}$")


def test_unique_name_adds_sanitized_unique_suffix() -> None:
    name_1 = helpers.unique_name("OpenAPI Generated Health Scenario")
    name_2 = helpers.unique_name("OpenAPI Generated Health Scenario")

    assert name_1.startswith("OpenAPI Generated Health Scenario ")
    assert name_2.startswith("OpenAPI Generated Health Scenario ")
    assert name_1 != name_2
    assert len(name_1) <= 96
    assert len(name_2) <= 96


def test_unique_name_bounds_long_prefix_and_removes_unsafe_characters() -> None:
    name = helpers.unique_name("  Env/Group: with unsafe ✨ characters " + "x" * 100, max_length=64)

    assert len(name) <= 64
    assert "/" not in name
    assert ":" not in name
    assert "✨" not in name
    assert name.startswith("Env-Group- with unsafe - characters")


def test_materialize_openapi_step_draft_adds_persistable_ids() -> None:
    ids = iter([f"01JTEST00000000000000000{i:02d}" for i in range(1, 8)])
    draft = {
        "enabled": True,
        "name": "GET /health",
        "method": "GET",
        "path": "/health",
        "queryParams": [{"name": "include", "value": "status"}],
        "headers": [{"name": "x-e2e", "value": "true", "enabled": False}],
        "body": {
            "type": "form",
            "contentType": "application/x-www-form-urlencoded",
            "rawText": None,
            "formFields": [{"name": "q", "value": "1"}],
        },
        "settings": {"timeoutMs": 12000, "followRedirects": True, "keepAlive": False},
    }

    step = helpers.materialize_openapi_step_draft(draft, id_factory=lambda: next(ids))

    assert step["id"] == "01JTEST0000000000000000001"
    assert ULID_LIKE.fullmatch(step["id"])
    assert step["queryParams"] == [
        {"id": "01JTEST0000000000000000002", "name": "include", "value": "status", "enabled": True}
    ]
    assert step["headers"] == [
        {"id": "01JTEST0000000000000000003", "name": "x-e2e", "value": "true", "enabled": False}
    ]
    assert step["body"]["formFields"] == [
        {"id": "01JTEST0000000000000000004", "name": "q", "value": "1", "enabled": True}
    ]
    assert step["assertions"] == []
    assert step["uploadFiles"] == []
    assert step["extractors"] == []
    assert step["scripts"] == []
    assert step["settings"] == {
        "thinkTimeMs": None,
        "timeoutMs": 12000,
        "followRedirects": True,
        "keepAlive": False,
    }


def test_materialize_openapi_step_draft_defaults_optional_fields() -> None:
    step = helpers.materialize_openapi_step_draft(
        {"name": "GET /status", "method": "GET", "path": "/status"},
        id_factory=lambda: "01JTEST0000000000000000999",
    )

    assert step["enabled"] is True
    assert step["queryParams"] == []
    assert step["headers"] == []
    assert step["body"] == {
        "type": "none",
        "contentType": None,
        "rawText": None,
        "formFields": [],
    }
    assert step["settings"] == {
        "thinkTimeMs": None,
        "timeoutMs": None,
        "followRedirects": None,
        "keepAlive": None,
    }


def test_materialize_openapi_step_draft_rejects_missing_required_fields() -> None:
    with pytest.raises(ValueError, match="missing required draft field"):
        helpers.materialize_openapi_step_draft({"name": "broken", "method": "GET"})
