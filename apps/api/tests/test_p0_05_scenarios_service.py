from datetime import UTC, datetime

import pytest
import yaml
from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.time import utc_now
from app.models.auth import DEFAULT_WORKSPACE_ID, User, Workspace
from app.models.dependency_files import DependencyFile
from app.models.runs import Run
from app.models.scenarios import Scenario, ScenarioDependencyFileRef
from app.schemas.scenarios import ScenarioCreateRequest
from app.services import scenarios as scenario_service
from app.services.dependency_files import delete_dependency_file_metadata
from app.services.scenarios import (
    build_debug_taurus_yaml,
    create_scenario,
    delete_scenario,
    patch_scenario,
    request_label,
)

OTHER_WORKSPACE_ID = "01HZX3Y9M0E9W7Z6M5QK9S8P9W"


def minimal_step(step_id: str = "01HZX3Y9M0E9W7Z6M5QK9S8P7D") -> dict:
    return {
        "id": step_id,
        "enabled": True,
        "name": "List users",
        "method": "GET",
        "path": "/v1/users",
        "queryParams": [
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7E",
                "name": "page",
                "value": "${page}",
                "enabled": True,
            }
        ],
        "headers": [
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
                "name": "Authorization",
                "value": "Bearer ${token}",
                "enabled": True,
            }
        ],
        "body": {"type": "none", "contentType": None, "rawText": None, "formFields": []},
        "uploadFiles": [],
        "extractors": [
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7J",
                "type": "jsonpath",
                "variableName": "user_id",
                "expression": "$.data[0].id",
                "defaultValue": "",
                "matchNo": 1,
                "subject": "body",
                "enabled": True,
            }
        ],
        "assertions": [
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7K",
                "type": "status_code",
                "expectedStatus": 200,
                "enabled": True,
            }
        ],
        "scripts": [],
        "settings": {
            "thinkTimeMs": None,
            "timeoutMs": None,
            "followRedirects": None,
            "keepAlive": None,
        },
    }


def scenario_payload(**overrides: object) -> dict:
    payload = {
        "name": "Checkout flow",
        "description": "Critical checkout APIs",
        "tags": ["checkout"],
        "baseUrlExpression": "${base_url}",
        "defaultSettings": {
            "thinkTimeMs": 0,
            "timeoutMs": 30000,
            "followRedirects": True,
            "keepAlive": True,
            "storeCache": True,
            "storeCookie": True,
            "retrieveResources": False,
        },
        "dataSources": [],
        "steps": [minimal_step()],
    }
    payload.update(overrides)
    return payload


def seed_user(db_session: Session) -> User:
    user = User(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        email="scenario-service@example.com",
        display_name="Scenario User",
        password_hash="hash",
        role="admin",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.flush()
    return user


def seed_dependency_file(
    db_session: Session,
    user: User,
    *,
    file_id: str = "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
    filename: str = "users.csv",
    content_type: str = "text/csv",
    workspace_id: str = DEFAULT_WORKSPACE_ID,
) -> DependencyFile:
    file = DependencyFile(
        id=file_id,
        workspace_id=workspace_id,
        filename=filename,
        content_type=content_type,
        size_bytes=16,
        sha256="a" * 64,
        storage_bucket="surgepilot",
        storage_object_key=f"dependency-files/not-returned/{filename}",
        status="available",
        created_by=user.id,
        created_at=datetime.now(UTC),
    )
    db_session.add(file)
    db_session.flush()
    return file


def seed_scenario(db_session: Session, user: User, **overrides: object) -> Scenario:
    return create_scenario(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        payload=scenario_payload(**overrides),
    )


def env_variables() -> dict[str, str]:
    return {
        "base_url": "https://api.example.internal",
        "token": "regular-token",
        "page": "first",
    }


def test_request_label_is_bounded_to_documented_length() -> None:
    label = request_label("GET", "/" + ("long-segment/" * 30))
    assert len(label) <= 200
    assert label.startswith("GET /")
    assert label == ("GET /" + ("long-segment/" * 30))[:200]


def test_ms_to_taurus_time_uses_compact_human_readable_units() -> None:
    assert scenario_service.ms_to_taurus_time(0) == "0ms"
    assert scenario_service.ms_to_taurus_time(500) == "500ms"
    assert scenario_service.ms_to_taurus_time(30_000) == "30s"
    assert scenario_service.ms_to_taurus_time(1_500) == "1s500ms"


def test_create_patch_and_dependency_refs_are_transactional(db_session: Session) -> None:
    user = seed_user(db_session)
    file = seed_dependency_file(db_session, user)
    payload = scenario_payload(
        dataSources=[
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
                "dependencyFileId": file.id,
                "displayName": file.filename,
                "delimiter": ",",
                "quoted": None,
                "loop": True,
                "variableNames": ["page"],
                "randomOrder": False,
                "enabled": True,
            }
        ]
    )

    scenario = create_scenario(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, payload=payload
    )

    assert scenario.revision == 1
    refs = db_session.query(ScenarioDependencyFileRef).filter_by(scenario_id=scenario.id).all()
    assert [(ref.dependency_file_id, ref.ref_type, ref.step_id) for ref in refs] == [
        (file.id, "data_source", None)
    ]

    updated = patch_scenario(
        db_session,
        scenario=scenario,
        actor=user,
        expected_revision=1,
        payload=scenario_payload(name="Checkout smoke", dataSources=[]),
    )

    assert updated.revision == 2
    assert updated.name == "Checkout smoke"
    assert (
        db_session.query(ScenarioDependencyFileRef).filter_by(scenario_id=scenario.id).all() == []
    )


def test_upload_file_refs_create_upload_file_rows_but_inline_scripts_do_not(
    db_session: Session,
) -> None:
    user = seed_user(db_session)
    csv_file = seed_dependency_file(db_session, user)
    upload_file = seed_dependency_file(
        db_session, user, file_id="01HZX3Y9M0E9W7Z6M5QK9S8P7D", filename="orders.json"
    )
    step = minimal_step("01HZX3Y9M0E9W7Z6M5QK9S8P7E")
    step["method"] = "POST"
    step["queryParams"] = []
    step["headers"] = []
    step["body"] = {"type": "none", "contentType": None, "rawText": None, "formFields": []}
    step["uploadFiles"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
            "fieldName": "payload",
            "dependencyFileId": upload_file.id,
            "mimeType": "application/json",
            "enabled": True,
        }
    ]
    step["scripts"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7G",
            "execute": "before",
            "language": "groovy",
            "scriptText": "vars.put('trace', '1')",
            "enabled": True,
        }
    ]
    scenario = create_scenario(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        payload=scenario_payload(
            dataSources=[
                {
                    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
                    "dependencyFileId": csv_file.id,
                    "displayName": csv_file.filename,
                    "delimiter": ",",
                    "quoted": None,
                    "loop": True,
                    "variableNames": ["page"],
                    "randomOrder": False,
                    "enabled": True,
                }
            ],
            steps=[step],
        ),
    )

    refs = db_session.query(ScenarioDependencyFileRef).filter_by(scenario_id=scenario.id).all()
    assert sorted((ref.dependency_file_id, ref.ref_type, ref.step_id) for ref in refs) == [
        (csv_file.id, "data_source", None),
        (upload_file.id, "upload_file", step["id"]),
    ]


def test_disabled_dependency_file_entries_are_ignored_for_refs(db_session: Session) -> None:
    user = seed_user(db_session)
    file = seed_dependency_file(db_session, user)
    scenario = create_scenario(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        payload=scenario_payload(
            dataSources=[
                {
                    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
                    "dependencyFileId": "01HZX3Y9M0E9W7Z6M5QK9S8P9Q",
                    "displayName": "ignored.csv",
                    "delimiter": ",",
                    "quoted": None,
                    "loop": True,
                    "variableNames": [],
                    "randomOrder": False,
                    "enabled": False,
                }
            ]
        ),
    )

    assert (
        db_session.query(ScenarioDependencyFileRef).filter_by(scenario_id=scenario.id).all() == []
    )


def test_cross_workspace_dependency_file_is_rejected(db_session: Session) -> None:
    user = seed_user(db_session)
    db_session.add(
        Workspace(
            id=OTHER_WORKSPACE_ID,
            name="Other Workspace",
            status="active",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    db_session.flush()
    other_file = seed_dependency_file(
        db_session, user, file_id="01HZX3Y9M0E9W7Z6M5QK9S8P9Q", workspace_id=OTHER_WORKSPACE_ID
    )

    with pytest.raises(AppError) as exc_info:
        create_scenario(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            payload=scenario_payload(
                dataSources=[
                    {
                        "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
                        "dependencyFileId": other_file.id,
                        "displayName": other_file.filename,
                        "delimiter": ",",
                        "quoted": None,
                        "loop": True,
                        "variableNames": ["page"],
                        "randomOrder": False,
                        "enabled": True,
                    }
                ]
            ),
        )

    assert exc_info.value.code == "RESOURCE_NOT_FOUND"


def test_scenario_validation_rejects_duplicate_headers_and_get_body(db_session: Session) -> None:
    user = seed_user(db_session)
    invalid_step = minimal_step()
    invalid_step["headers"] = [
        {"id": "01HZX3Y9M0E9W7Z6M5QK9S8P7F", "name": "Accept", "value": "json", "enabled": True},
        {"id": "01HZX3Y9M0E9W7Z6M5QK9S8P7G", "name": "accept", "value": "text", "enabled": True},
    ]
    invalid_step["body"] = {
        "type": "raw",
        "contentType": "application/json",
        "rawText": "{}",
        "formFields": [],
    }

    with pytest.raises(Exception) as exc_info:
        create_scenario(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            payload=scenario_payload(steps=[invalid_step]),
        )

    error = exc_info.value
    assert getattr(error, "code") == "VALIDATION_ERROR"
    detail_codes = {detail["code"] for detail in error.details}
    assert "duplicate_header" in detail_codes
    assert "body_not_allowed" in detail_codes


def test_scenario_validation_rejects_duplicate_step_ids(db_session: Session) -> None:
    user = seed_user(db_session)
    duplicate_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7D"

    first = minimal_step(duplicate_id)
    second = minimal_step(duplicate_id)
    second["extractors"] = []
    second["queryParams"] = []
    second["headers"] = []

    with pytest.raises(AppError) as exc_info:
        create_scenario(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            payload=scenario_payload(steps=[first, second]),
        )

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert {detail["code"] for detail in exc_info.value.details} == {"duplicate_step_id"}


def test_put_with_multiple_enabled_upload_files_is_rejected(db_session: Session) -> None:
    user = seed_user(db_session)
    first_file = seed_dependency_file(db_session, user)
    second_file = seed_dependency_file(
        db_session, user, file_id="01HZX3Y9M0E9W7Z6M5QK9S8P9R", filename="payload.json"
    )
    step = minimal_step()
    step["method"] = "PUT"
    step["queryParams"] = []
    step["headers"] = []
    step["uploadFiles"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P9S",
            "fieldName": "one",
            "dependencyFileId": first_file.id,
            "enabled": True,
        },
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P9T",
            "fieldName": "two",
            "dependencyFileId": second_file.id,
            "enabled": True,
        },
    ]

    with pytest.raises(AppError) as exc_info:
        create_scenario(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            payload=scenario_payload(steps=[step]),
        )

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert {detail["code"] for detail in exc_info.value.details} == {"too_many_upload_files"}


def test_scenario_schema_rejects_blank_name_and_invalid_csv_delimiter() -> None:
    with pytest.raises(ValidationError):
        ScenarioCreateRequest.model_validate(scenario_payload(name="   "))

    with pytest.raises(ValidationError):
        ScenarioCreateRequest.model_validate(
            scenario_payload(
                dataSources=[
                    {
                        "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
                        "dependencyFileId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
                        "displayName": "users.csv",
                        "delimiter": "::",
                        "quoted": None,
                        "loop": True,
                        "variableNames": ["page"],
                        "randomOrder": False,
                        "enabled": True,
                    }
                ]
            )
        )


def test_scenario_runtime_validation_rejects_blank_name_and_invalid_delimiter() -> None:
    with pytest.raises(AppError) as blank_name:
        scenario_service.validate_scenario_content(scenario_payload(name="   "))

    assert blank_name.value.code == "VALIDATION_ERROR"
    assert {detail["code"] for detail in blank_name.value.details} == {"required_field"}

    with pytest.raises(AppError) as invalid_delimiter:
        scenario_service.validate_scenario_content(
            scenario_payload(
                dataSources=[
                    {
                        "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
                        "dependencyFileId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
                        "displayName": "users.csv",
                        "delimiter": "::",
                        "quoted": None,
                        "loop": True,
                        "variableNames": ["page"],
                        "randomOrder": False,
                        "enabled": True,
                    }
                ]
            )
        )

    assert invalid_delimiter.value.code == "VALIDATION_ERROR"
    assert {detail["code"] for detail in invalid_delimiter.value.details} == {"invalid_delimiter"}


def test_scenario_runtime_validation_rejects_empty_enabled_assertion_fields() -> None:
    step = minimal_step()
    step["assertions"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8K",
            "type": "body_contains",
            "contains": "",
            "regexp": False,
            "not": False,
            "enabled": True,
        },
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8L",
            "type": "jsonpath_exists",
            "jsonpath": "",
            "enabled": True,
        },
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8M",
            "type": "jsonpath_equals",
            "jsonpath": "$.ok",
            "expectedValue": "",
            "regexp": False,
            "enabled": True,
        },
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8N",
            "type": "jsonpath_equals",
            "jsonpath": "  ",
            "expectedValue": "ok",
            "regexp": False,
            "enabled": True,
        },
    ]

    with pytest.raises(AppError) as exc_info:
        scenario_service.validate_scenario_content(scenario_payload(steps=[step]))

    assert exc_info.value.code == "VALIDATION_ERROR"
    fields = {detail["field"] for detail in exc_info.value.details}
    assert "steps[0].assertions[0].contains" in fields
    assert "steps[0].assertions[1].jsonpath" in fields
    assert "steps[0].assertions[2].expectedValue" in fields
    assert "steps[0].assertions[3].jsonpath" in fields


def test_enabled_script_requires_non_blank_script_text(db_session: Session) -> None:
    user = seed_user(db_session)
    step = minimal_step()
    step["scripts"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8V",
            "execute": "before",
            "language": "groovy",
            "scriptText": "   ",
            "enabled": True,
        }
    ]

    with pytest.raises(AppError) as exc_info:
        create_scenario(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            payload=scenario_payload(steps=[step]),
        )

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert {detail["code"] for detail in exc_info.value.details} == {"script_text_required"}


def test_disabled_script_and_disabled_step_skip_script_validation(
    db_session: Session,
) -> None:
    user = seed_user(db_session)
    disabled_script_step = minimal_step("01HZX3Y9M0E9W7Z6M5QK9S8P8X")
    disabled_script_step["scripts"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8Y",
            "execute": "before",
            "language": "groovy",
            "scriptText": "   ",
            "enabled": False,
        }
    ]
    disabled_step = minimal_step("01HZX3Y9M0E9W7Z6M5QK9S8P8Z")
    disabled_step["enabled"] = False
    disabled_step["scripts"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P9A",
            "execute": "after",
            "language": "groovy",
            "scriptText": "",
            "enabled": True,
        }
    ]

    scenario = create_scenario(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        payload=scenario_payload(steps=[disabled_script_step, disabled_step]),
    )

    assert scenario.id


def test_enabled_step_variable_extraction_uses_only_executable_children() -> None:
    raw_step = {
        "path": "/v1/${path_var}",
        "queryParams": [
            {"name": "active", "value": "${query_var}", "enabled": True},
            {"name": "disabled", "value": "${disabled_query}", "enabled": False},
        ],
        "headers": [{"name": "X-Trace", "value": "${header_var}", "enabled": True}],
        "body": {
            "type": "raw",
            "contentType": "application/${content_type_var}",
            "rawText": '{"token": "${body_var}"}',
            "formFields": [],
        },
        "assertions": [{"type": "body_contains", "contains": "${assertion_var}", "enabled": True}],
        "scripts": [
            {
                "execute": "before",
                "language": "groovy",
                "scriptText": "vars.put('x', '${not_a_variable}')",
                "enabled": True,
            }
        ],
    }
    form_step = {
        "path": "/v1/form",
        "queryParams": [],
        "headers": [],
        "body": {
            "type": "form",
            "formFields": [{"name": "field", "value": "${form_var}", "enabled": True}],
        },
        "assertions": [],
        "scripts": [],
    }

    raw_refs = scenario_service._extract_enabled_step_variables(raw_step)
    form_refs = scenario_service._extract_enabled_step_variables(form_step)

    assert {
        "path_var",
        "query_var",
        "header_var",
        "content_type_var",
        "body_var",
        "assertion_var",
    }.issubset(raw_refs)
    assert "disabled_query" not in raw_refs
    assert "not_a_variable" not in raw_refs
    assert form_refs == {"form_var"}


def test_regexp_extractors_must_have_valid_capture_group(db_session: Session) -> None:
    user = seed_user(db_session)
    invalid_step = minimal_step()
    invalid_step["queryParams"] = []
    invalid_step["headers"] = []
    invalid_step["extractors"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7J",
            "type": "regexp",
            "variableName": "csrf_token",
            "expression": "token=[A-Za-z0-9]+",
            "defaultValue": "",
            "matchNo": 1,
            "subject": "body",
            "template": None,
            "enabled": True,
        },
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8J",
            "type": "regexp",
            "variableName": "session_id",
            "expression": "session=([A-Za-z0-9]+)",
            "defaultValue": "",
            "matchNo": 1,
            "subject": "body",
            "template": "$2$",
            "enabled": True,
        },
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8K",
            "type": "regexp",
            "variableName": "broken_regexp",
            "expression": "[",
            "defaultValue": "",
            "matchNo": 1,
            "subject": "body",
            "template": None,
            "enabled": True,
        },
    ]

    with pytest.raises(AppError) as exc_info:
        create_scenario(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            payload=scenario_payload(steps=[invalid_step]),
        )

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert {detail["code"] for detail in exc_info.value.details} == {
        "invalid_regexp",
        "invalid_regexp_template",
        "regexp_capture_group_required",
    }


def test_scenario_dependency_refs_block_dependency_file_deletion(db_session: Session) -> None:
    user = seed_user(db_session)
    file = seed_dependency_file(db_session, user)
    seed_scenario(
        db_session,
        user,
        dataSources=[
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
                "dependencyFileId": file.id,
                "displayName": file.filename,
                "delimiter": ",",
                "quoted": None,
                "loop": True,
                "variableNames": ["page"],
                "randomOrder": False,
                "enabled": True,
            }
        ],
    )

    with pytest.raises(AppError) as exc_info:
        delete_dependency_file_metadata(db_session, file=file, actor_user_id=user.id)

    assert exc_info.value.code == "FILE_IN_USE"


def test_soft_deleted_scenario_no_longer_blocks_dependency_file_delete(
    db_session: Session,
) -> None:
    user = seed_user(db_session)
    file = seed_dependency_file(db_session, user)
    scenario = seed_scenario(
        db_session,
        user,
        dataSources=[
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
                "dependencyFileId": file.id,
                "displayName": file.filename,
                "delimiter": ",",
                "quoted": None,
                "loop": True,
                "variableNames": ["page"],
                "randomOrder": False,
                "enabled": True,
            }
        ],
    )
    delete_scenario(db_session, scenario=scenario, actor=user)

    delete_dependency_file_metadata(db_session, file=file, actor_user_id=user.id)
    assert file.status == "deleted"


def test_active_debug_run_blocks_scenario_delete(db_session: Session) -> None:
    user = seed_user(db_session)
    scenario = seed_scenario(db_session, user)
    now = utc_now()
    db_session.add(
        Run(
            id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
            workspace_id=DEFAULT_WORKSPACE_ID,
            run_type="debug",
            state="running",
            source_type="debug_scenario",
            source_id=scenario.id,
            selected_node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
            triggered_by_user_id=user.id,
            forced_convergence=False,
            remote_start_requested_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.flush()

    with pytest.raises(AppError) as exc_info:
        delete_scenario(db_session, scenario=scenario, actor=user)

    assert exc_info.value.code == "RESOURCE_IN_USE"


def test_finished_run_does_not_block_scenario_soft_delete(db_session: Session) -> None:
    user = seed_user(db_session)
    scenario = seed_scenario(db_session, user)
    now = utc_now()
    db_session.add(
        Run(
            id="01HZX3Y9M0E9W7Z6M5QK9S8P7S",
            workspace_id=DEFAULT_WORKSPACE_ID,
            run_type="debug",
            state="finished",
            source_type="debug_scenario",
            source_id=scenario.id,
            selected_node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
            triggered_by_user_id=user.id,
            forced_convergence=False,
            remote_start_requested_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.flush()

    delete_scenario(db_session, scenario=scenario, actor=user)
    assert scenario.deleted_at is not None


def test_patch_scenario_rechecks_current_revision_before_update(db_session: Session) -> None:
    user = seed_user(db_session)
    scenario = create_scenario(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, payload=scenario_payload()
    )
    db_session.execute(
        update(Scenario)
        .where(Scenario.id == scenario.id)
        .values(revision=2)
        .execution_options(synchronize_session=False)
    )

    with pytest.raises(AppError) as exc_info:
        patch_scenario(
            db_session,
            scenario=scenario,
            actor=user,
            expected_revision=1,
            payload=scenario_payload(name="Stale update"),
        )

    assert exc_info.value.code == "SCENARIO_REVISION_CONFLICT"


def test_debug_variable_validation_reports_missing_active_reference() -> None:
    content = scenario_payload(
        steps=[
            {
                **minimal_step(),
                "queryParams": [],
                "headers": [],
                "path": "/v1/users/${missing_page}",
                "extractors": [],
            }
        ]
    )

    with pytest.raises(AppError) as exc_info:
        scenario_service._validate_debug_variables(content, {"base_url": "https://api.example"})

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert {detail["code"] for detail in exc_info.value.details} == {"missing_variable"}


def test_debug_variable_validation_accepts_env_and_earlier_extractors() -> None:
    first_step = {**minimal_step("01HZX3Y9M0E9W7Z6M5QK9S8P8E")}
    second_step = {
        **minimal_step("01HZX3Y9M0E9W7Z6M5QK9S8P8F"),
        "path": "/v1/users/${user_id}",
        "queryParams": [],
        "headers": [],
        "extractors": [],
    }
    content = scenario_payload(steps=[first_step, second_step])

    scenario_service._validate_debug_variables(content, env_variables())


def test_debug_variable_validation_rejects_extractor_conflicts_with_env() -> None:
    step = minimal_step()
    step["extractors"][0]["variableName"] = "token"
    content = scenario_payload(steps=[step])

    with pytest.raises(AppError) as exc_info:
        scenario_service._validate_debug_variables(content, env_variables())

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert {detail["code"] for detail in exc_info.value.details} == {"variable_conflict"}


def test_taurus_builder_rejects_unsafe_resolved_base_urls() -> None:
    content = scenario_payload(
        baseUrlExpression="${base_url}",
        steps=[{**minimal_step(), "queryParams": [], "headers": [], "extractors": []}],
    )

    for value in [
        "https://api.example.internal/../admin",
        "https://api.example.internal/%2e%2e/admin",
        "https://api.example.internal/has space",
        "https://api.example.internal/path\nnext",
    ]:
        with pytest.raises(AppError) as exc_info:
            scenario_service.build_debug_taurus_document_from_content(
                scenario_content=content,
                env_variables={"base_url": value},
                dependency_files=[],
                jmeter_path="/opt/surgepilot/apache-jmeter/bin/jmeter",
                jmeter_version="5.4.2",
            )
        assert exc_info.value.code == "VALIDATION_ERROR"
        assert {detail["code"] for detail in exc_info.value.details} == {"invalid_url"}


def test_taurus_yaml_builder_emits_documented_jmeter_fields(db_session: Session) -> None:
    user = seed_user(db_session)
    scenario = seed_scenario(db_session, user)

    yaml_text = build_debug_taurus_yaml(
        scenario=scenario,
        env_variables=env_variables(),
        dependency_files=[],
        jmeter_path="/opt/surgepilot/apache-jmeter/bin/jmeter",
        jmeter_version="5.4.2",
    )
    document = yaml.safe_load(yaml_text)

    assert document["settings"] == {"env": {}}
    modules = document["modules"]["jmeter"]
    assert modules["path"] == "/opt/surgepilot/apache-jmeter/bin/jmeter"
    assert modules["version"] == "5.4.2"
    assert modules["detect-plugins"] is False
    assert modules["force-ctg"] is False

    execution = document["execution"]
    assert execution == [
        {"executor": "jmeter", "concurrency": 1, "iterations": 1, "scenario": "surgepilot_scenario"}
    ]

    scenario_doc = document["scenarios"]["surgepilot_scenario"]
    assert scenario_doc["default-address"] == "https://api.example.internal"
    assert scenario_doc["store-cache"] is True
    assert scenario_doc["store-cookie"] is True
    assert scenario_doc["keepalive"] is True
    assert scenario_doc["follow-redirects"] is True
    assert scenario_doc["retrieve-resources"] is False
    assert scenario_doc["think-time"] == "0ms"
    assert scenario_doc["timeout"] == "30s"
    assert scenario_doc["variables"] == env_variables()

    request = scenario_doc["requests"][0]
    assert request["label"].startswith("GET /v1/users")
    assert request["url"] == "/v1/users?page=first"
    assert request["method"] == "GET"
    assert request["headers"]["Authorization"] == "Bearer ${token}"
    assert request["extract-jsonpath"]["user_id"] == {
        "jsonpath": "$.data[0].id",
        "default": "",
        "match-no": 1,
    }
    assert request["assert"] == [
        {"contains": ["200"], "subject": "http-code", "regexp": False}
    ]
    assert "storeCache" not in yaml_text
    assert "followRedirects" not in yaml_text


def test_taurus_yaml_builder_maps_csv_data_sources(db_session: Session) -> None:
    user = seed_user(db_session)
    file = seed_dependency_file(db_session, user)
    step = minimal_step()
    step["queryParams"] = []
    step["headers"] = []
    step["extractors"] = []
    scenario = seed_scenario(
        db_session,
        user,
        dataSources=[
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
                "dependencyFileId": file.id,
                "displayName": file.filename,
                "delimiter": ",",
                "quoted": None,
                "loop": True,
                "variableNames": ["username", "password"],
                "randomOrder": False,
                "enabled": True,
            }
        ],
        steps=[step],
    )

    document = yaml.safe_load(
        build_debug_taurus_yaml(
            scenario=scenario,
            env_variables={"base_url": "https://api.example.internal"},
            dependency_files=[file],
            jmeter_path="/opt/surgepilot/apache-jmeter/bin/jmeter",
            jmeter_version="5.4.2",
        )
    )
    data_source = document["scenarios"]["surgepilot_scenario"]["data-sources"][0]
    assert data_source["path"] == scenario_service.bundle_file_path(file)
    assert data_source["delimiter"] == ","
    assert data_source["variable-names"] == "username,password"
    assert data_source["loop"] is True
    assert data_source["random-order"] is False
    assert "quoted" not in data_source


def test_taurus_yaml_builder_emits_quoted_only_when_declared(db_session: Session) -> None:
    user = seed_user(db_session)
    file = seed_dependency_file(db_session, user)
    base_data_source = {
        "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
        "dependencyFileId": file.id,
        "displayName": file.filename,
        "delimiter": ",",
        "quoted": True,
        "loop": True,
        "variableNames": ["username"],
        "randomOrder": True,
        "enabled": True,
    }
    scenario = seed_scenario(
        db_session, user, dataSources=[base_data_source], steps=[minimal_step()]
    )

    document = yaml.safe_load(
        build_debug_taurus_yaml(
            scenario=scenario,
            env_variables=env_variables(),
            dependency_files=[file],
            jmeter_path="/opt/surgepilot/apache-jmeter/bin/jmeter",
            jmeter_version="5.4.2",
        )
    )
    data_source = document["scenarios"]["surgepilot_scenario"]["data-sources"][0]
    assert data_source["quoted"] is True
    assert data_source["random-order"] is True


def test_taurus_yaml_builder_maps_upload_files_to_bundle_relative_paths(
    db_session: Session,
) -> None:
    user = seed_user(db_session)
    file = seed_dependency_file(
        db_session, user, file_id="01HZX3Y9M0E9W7Z6M5QK9S8P9X", filename="payload.bin"
    )
    step = minimal_step()
    step["method"] = "PUT"
    step["queryParams"] = []
    step["headers"] = []
    step["extractors"] = []
    step["uploadFiles"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P9V",
            "fieldName": "avatar",
            "dependencyFileId": file.id,
            "mimeType": "application/octet-stream",
            "enabled": True,
        }
    ]
    scenario = seed_scenario(db_session, user, steps=[step])

    yaml_text = build_debug_taurus_yaml(
        scenario=scenario,
        env_variables={"base_url": "https://api.example.internal"},
        dependency_files=[file],
        jmeter_path="/opt/surgepilot/apache-jmeter/bin/jmeter",
        jmeter_version="5.4.2",
    )
    document = yaml.safe_load(yaml_text)
    request = document["scenarios"]["surgepilot_scenario"]["requests"][0]
    expected_path = scenario_service.bundle_file_path(file)
    assert request["upload-files"] == [
        {"param": "avatar", "path": expected_path, "mime-type": "application/octet-stream"}
    ]
    assert expected_path.startswith("files/")
    assert "dependency-files/not-returned" not in yaml_text


def test_taurus_yaml_builder_applies_step_settings_overrides(db_session: Session) -> None:
    user = seed_user(db_session)
    step = minimal_step()
    step["method"] = "POST"
    step["settings"] = {
        "thinkTimeMs": 500,
        "timeoutMs": 1_500,
        "followRedirects": False,
        "keepAlive": False,
    }
    step["body"] = {
        "type": "raw",
        "contentType": "application/json",
        "rawText": '{"ok": true}',
        "formFields": [],
    }
    scenario = seed_scenario(db_session, user, steps=[step])

    document = yaml.safe_load(
        build_debug_taurus_yaml(
            scenario=scenario,
            env_variables=env_variables(),
            dependency_files=[],
            jmeter_path="/opt/surgepilot/apache-jmeter/bin/jmeter",
            jmeter_version="5.4.2",
        )
    )
    request = document["scenarios"]["surgepilot_scenario"]["requests"][0]
    assert request["think-time"] == "500ms"
    assert request["timeout"] == "1s500ms"
    assert request["follow-redirects"] is False
    assert request["keepalive"] is False
    assert request["headers"]["Content-Type"] == "application/json"
    assert request["body"] == '{"ok": true}'


def test_taurus_yaml_builder_maps_inline_script_to_jsr223_script_text(
    db_session: Session,
) -> None:
    user = seed_user(db_session)
    step = minimal_step()
    step["scripts"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8W",
            "execute": "before",
            "language": "groovy",
            "scriptText": "vars.put('trace', 'abc')",
            "enabled": True,
        }
    ]
    scenario = seed_scenario(db_session, user, steps=[step])

    yaml_text = build_debug_taurus_yaml(
        scenario=scenario,
        env_variables=env_variables(),
        dependency_files=[],
        jmeter_path="/opt/surgepilot/apache-jmeter/bin/jmeter",
        jmeter_version="5.4.2",
    )
    document = yaml.safe_load(yaml_text)
    request = document["scenarios"]["surgepilot_scenario"]["requests"][0]
    assert request["jsr223"] == [
        {
            "language": "groovy",
            "execute": "before",
            "script-text": "vars.put('trace', 'abc')",
            "compile-cache": True,
        }
    ]
    assert "script-file" not in yaml_text
