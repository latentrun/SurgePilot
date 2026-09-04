import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "packages/contracts/runner/runner-callback.schema.json"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def validator() -> Draft202012Validator:
    return Draft202012Validator(load_schema())


def test_runner_callback_placeholder_is_valid_json_schema() -> None:
    schema = load_schema()

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)


def test_runner_callback_placeholder_reserves_schema_version_one() -> None:
    validator().validate({"schemaVersion": "1"})

    with pytest.raises(ValidationError):
        validator().validate({})

    with pytest.raises(ValidationError):
        validator().validate({"schemaVersion": "2"})
