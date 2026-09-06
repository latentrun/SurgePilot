import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "packages/contracts/runner/runner-callback.schema.json"
ULID_1 = "01HZX3Y9M0E9W7Z6M5QK9S8P7A"
ULID_2 = "01HZX3Y9M0E9W7Z6M5QK9S8P7B"
ULID_3 = "01HZX3Y9M0E9W7Z6M5QK9S8P7C"
ULID_PATTERN = "^[0-9A-HJKMNP-TV-Z]{26}$"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def valid_payload(event_type: str) -> dict:
    payload = {
        "schemaVersion": "1",
        "eventId": ULID_1,
        "runId": ULID_2,
        "nodeId": ULID_3,
        "runtimeVersion": "runtime-test-v1",
        "eventType": event_type,
        "seq": 1,
        "eventTime": "2030-06-01T10:00:00.000Z",
        "message": "Callback received.",
        "details": {},
    }
    if event_type == "accepted":
        payload["runnerPid"] = 1234
    if event_type == "artifact":
        payload["details"] = {
            "artifactId": ULID_1,
            "artifactType": "run_log",
            "relativePath": "logs/runner.log",
            "sizeBytes": 12,
            "sha256": "a" * 64,
        }
    if event_type in {"finished", "failed", "aborted"}:
        payload["details"] = {"processGroupExited": True, "reason": "unknown_runner_error"}
    return payload


def test_runner_callback_schema_is_valid_json_schema() -> None:
    schema = load_schema()

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)


def test_runner_callback_schema_requires_protocol_identity_fields() -> None:
    schema = load_schema()

    assert set(schema["required"]) == {
        "schemaVersion",
        "eventType",
        "eventId",
        "runId",
        "nodeId",
        "runtimeVersion",
        "seq",
        "eventTime",
    }
    assert "occurredAt" not in schema["properties"]


def test_runner_callback_schema_constrains_ulid_identity_fields() -> None:
    schema = load_schema()

    for field in ["eventId", "runId", "nodeId"]:
        assert schema["properties"][field]["pattern"] == ULID_PATTERN

    artifact_rule = next(
        rule
        for rule in schema["allOf"]
        if rule["if"]["properties"]["eventType"].get("const") == "artifact"
    )
    artifact_details = artifact_rule["then"]["properties"]["details"]
    assert artifact_details["properties"]["artifactId"]["pattern"] == ULID_PATTERN


@pytest.mark.parametrize(
    "event_type",
    ["accepted", "running", "heartbeat", "artifact", "finished", "failed", "aborted"],
)
def test_runner_callback_schema_accepts_valid_examples_for_all_event_types(
    event_type: str,
) -> None:
    validator = Draft202012Validator(load_schema())

    validator.validate(valid_payload(event_type))


@pytest.mark.parametrize(
    "event_time",
    ["2030-06-01T10:00:00+00:00", "2030-06-01T10:00:00.000+08:00", "2030-06-01 10:00:00Z"],
)
def test_runner_callback_schema_requires_utc_z_event_time(event_time: str) -> None:
    validator = Draft202012Validator(load_schema())
    payload = valid_payload("heartbeat")
    payload["eventTime"] = event_time

    with pytest.raises(ValidationError):
        validator.validate(payload)


@pytest.mark.parametrize(
    "missing_field",
    [
        "schemaVersion",
        "eventType",
        "eventId",
        "runId",
        "nodeId",
        "runtimeVersion",
        "seq",
        "eventTime",
    ],
)
def test_runner_callback_schema_rejects_missing_required_fields(missing_field: str) -> None:
    validator = Draft202012Validator(load_schema())
    payload = valid_payload("heartbeat")
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        validator.validate(payload)


def test_runner_callback_schema_rejects_unknown_schema_version() -> None:
    validator = Draft202012Validator(load_schema())
    payload = valid_payload("heartbeat")
    payload["schemaVersion"] = "2"

    with pytest.raises(ValidationError):
        validator.validate(payload)


def test_runner_callback_schema_rejects_unknown_event_type() -> None:
    validator = Draft202012Validator(load_schema())
    payload = valid_payload("heartbeat")
    payload["eventType"] = "paused"

    with pytest.raises(ValidationError):
        validator.validate(payload)


def test_runner_callback_schema_rejects_invalid_ulid_identity_values() -> None:
    validator = Draft202012Validator(load_schema())
    payload = valid_payload("heartbeat")
    payload["eventId"] = "not-a-valid-ulid"

    with pytest.raises(ValidationError):
        validator.validate(payload)


def test_runner_callback_schema_requires_runner_pid_for_accepted() -> None:
    validator = Draft202012Validator(load_schema())
    payload = valid_payload("accepted")
    payload.pop("runnerPid")

    with pytest.raises(ValidationError):
        validator.validate(payload)


def test_runner_callback_schema_restricts_artifact_type_and_disallows_storage_key() -> None:
    validator = Draft202012Validator(load_schema())
    payload = valid_payload("artifact")
    payload["details"]["artifactType"] = "debug_dump"

    with pytest.raises(ValidationError):
        validator.validate(payload)

    payload = valid_payload("artifact")
    payload["details"]["storageKey"] = "artifacts/workspace/run/object"
    with pytest.raises(ValidationError):
        validator.validate(payload)


@pytest.mark.parametrize("event_type", ["finished", "failed", "aborted"])
def test_runner_callback_schema_requires_process_group_exited_for_terminal(
    event_type: str,
) -> None:
    validator = Draft202012Validator(load_schema())
    payload = valid_payload(event_type)
    payload["details"].pop("processGroupExited")

    with pytest.raises(ValidationError):
        validator.validate(payload)


@pytest.mark.parametrize("event_type", ["failed", "aborted"])
def test_runner_callback_schema_requires_reason_for_failed_and_aborted(event_type: str) -> None:
    validator = Draft202012Validator(load_schema())
    payload = valid_payload(event_type)
    payload["details"].pop("reason")

    with pytest.raises(ValidationError):
        validator.validate(payload)


@pytest.mark.parametrize("reason", ["Runner Exit", "runner-exit", "runner.exit", "RunnerExit"])
def test_runner_callback_schema_restricts_reason_to_lower_snake_case(reason: str) -> None:
    validator = Draft202012Validator(load_schema())
    payload = valid_payload("failed")
    payload["details"]["reason"] = reason

    with pytest.raises(ValidationError):
        validator.validate(payload)


def test_runner_callback_schema_allows_finished_without_reason() -> None:
    validator = Draft202012Validator(load_schema())
    payload = valid_payload("finished")
    payload["details"].pop("reason")

    validator.validate(payload)
