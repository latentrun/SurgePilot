from datetime import UTC, datetime
from io import BytesIO
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.ids import new_ulid
from app.core.time import utc_now
from app.models.auth import DEFAULT_WORKSPACE_ID, AuditEvent, SystemSetting, User
from app.models.dependency_files import DependencyFile
from app.models.runs import Run, RunSnapshot
from app.models.scenarios import RunCreationDedupKey, Scenario, ScenarioDependencyFileRef
from app.schemas.scenarios import ScenarioCreateRequest
from app.services import scenarios as scenario_service
from app.services.execution_bundles import build_debug_scenario_execution_bundle
from app.services.dependency_files import delete_dependency_file_metadata
from app.services.scenarios import (
    build_debug_taurus_yaml,
    create_debug_run,
    create_scenario,
    patch_scenario,
    request_label,
)


def test_request_label_retains_step_and_item_ids_when_path_is_long() -> None:
    step_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7D"
    item_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7E"

    label = request_label("GET", "/" + ("long-segment/" * 30), step_id, item_id=item_id)

    assert len(label) <= 200
    assert f"step:{step_id}" in label
    assert f"item:{item_id}" in label


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
) -> DependencyFile:
    file = DependencyFile(
        id=file_id,
        workspace_id=DEFAULT_WORKSPACE_ID,
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
                "dependencyFileId": "01HZX3Y9M0E9W7Z6M5QK9S8P8S",
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
    assert form_refs == {"form_var"}


def test_enabled_script_dependency_ref_blocks_file_deletion_and_uses_script_file(
    db_session: Session,
) -> None:
    user = seed_user(db_session)
    script_file = seed_dependency_file(
        db_session,
        user,
        file_id="01HZX3Y9M0E9W7Z6M5QK9S8P8S",
        filename="setup.groovy",
        content_type="text/x-groovy",
    )
    step = minimal_step()
    step["queryParams"] = []
    step["headers"] = []
    step["scripts"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8T",
            "execute": "before",
            "language": "groovy",
            "dependencyFileId": script_file.id,
            "enabled": True,
        }
    ]

    scenario = create_scenario(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        payload=scenario_payload(steps=[step]),
    )

    refs = db_session.query(ScenarioDependencyFileRef).filter_by(scenario_id=scenario.id).all()
    assert [(ref.dependency_file_id, ref.ref_type, ref.step_id) for ref in refs] == [
        (script_file.id, "script", step["id"])
    ]

    yaml_text = build_debug_taurus_yaml(
        scenario=scenario,
        env_variables={"base_url": "https://api.example.internal"},
        dependency_files=[script_file],
        jmeter_path="/opt/surgepilot/apache-jmeter/bin/jmeter",
        jmeter_version="5.4.2",
    )

    assert f"script-file: {scenario_service.bundle_file_path(script_file)}" in yaml_text
    assert "script-text" not in yaml_text

    with pytest.raises(AppError) as exc_info:
        delete_dependency_file_metadata(db_session, file=script_file, actor_user_id=user.id)

    assert exc_info.value.code == "FILE_IN_USE"


def test_enabled_script_requires_groovy_dependency_file(db_session: Session) -> None:
    user = seed_user(db_session)
    text_file = seed_dependency_file(
        db_session,
        user,
        file_id="01HZX3Y9M0E9W7Z6M5QK9S8P8U",
        filename="setup.txt",
        content_type="text/plain",
    )
    step = minimal_step()
    step["scripts"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8V",
            "execute": "before",
            "language": "groovy",
            "dependencyFileId": text_file.id,
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
    assert exc_info.value.details == [
        {
            "field": "steps[0].scripts[0].dependencyFileId",
            "code": "invalid_script_file",
            "message": "Script Dependency File must be a .groovy file.",
        }
    ]


def test_disabled_script_and_disabled_step_do_not_validate_or_write_script_refs(
    db_session: Session,
) -> None:
    user = seed_user(db_session)
    text_file = seed_dependency_file(
        db_session,
        user,
        file_id="01HZX3Y9M0E9W7Z6M5QK9S8P8W",
        filename="draft.txt",
        content_type="text/plain",
    )
    disabled_script_step = minimal_step("01HZX3Y9M0E9W7Z6M5QK9S8P8X")
    disabled_script_step["scripts"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8Y",
            "execute": "before",
            "language": "groovy",
            "dependencyFileId": text_file.id,
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
            "dependencyFileId": text_file.id,
            "enabled": True,
        }
    ]

    scenario = create_scenario(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        payload=scenario_payload(steps=[disabled_script_step, disabled_step]),
    )

    refs = db_session.query(ScenarioDependencyFileRef).filter_by(scenario_id=scenario.id).all()
    assert [ref.ref_type for ref in refs] == []


def test_scenario_script_rejects_inline_script_text_schema() -> None:
    step = minimal_step()
    step["scripts"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P9B",
            "execute": "before",
            "language": "groovy",
            "scriptText": "vars.put('x', '1')",
            "enabled": True,
        }
    ]

    with pytest.raises(ValidationError):
        ScenarioCreateRequest.model_validate(scenario_payload(steps=[step]))


def test_regexp_template_helpers_validate_group_references() -> None:
    assert scenario_service._regexp_group_count("token=(\\w+)") == 1
    assert scenario_service._regexp_group_count("[") is None
    assert scenario_service._regexp_template_references_valid_group("1", 1) is True
    assert scenario_service._regexp_template_references_valid_group("$1$", 1) is True
    assert scenario_service._regexp_template_references_valid_group("$2$", 1) is False
    assert scenario_service._regexp_template_references_valid_group("literal", 1) is False


def test_disabled_steps_are_not_execution_validated(db_session: Session) -> None:
    user = seed_user(db_session)
    disabled_invalid_step = minimal_step("01HZX3Y9M0E9W7Z6M5QK9S8P8D")
    disabled_invalid_step["enabled"] = False
    disabled_invalid_step["headers"] = [
        {"id": "01HZX3Y9M0E9W7Z6M5QK9S8P8F", "name": "Bad Header", "value": "x", "enabled": True}
    ]
    disabled_invalid_step["body"] = {
        "type": "raw",
        "contentType": "application/json",
        "rawText": "{}",
        "formFields": [],
    }
    disabled_invalid_step["uploadFiles"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8G",
            "dependencyFileId": "01HZX3Y9M0E9W7Z6M5QK9S8P8H",
            "fieldName": "file",
            "enabled": True,
        }
    ]

    scenario = create_scenario(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        payload=scenario_payload(steps=[minimal_step(), disabled_invalid_step]),
    )

    assert scenario.id
    assert (
        db_session.query(ScenarioDependencyFileRef).filter_by(scenario_id=scenario.id).all() == []
    )


def test_disabled_step_children_do_not_contribute_missing_variables(db_session: Session) -> None:
    user = seed_user(db_session)
    step = minimal_step()
    step["method"] = "POST"
    step["queryParams"] = []
    step["headers"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8F",
            "name": "X-Draft",
            "value": "${draft_token}",
            "enabled": False,
        }
    ]
    step["body"] = {
        "type": "form",
        "contentType": None,
        "rawText": None,
        "formFields": [
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8G",
                "name": "draft",
                "value": "${draft_form_value}",
                "enabled": False,
            }
        ],
    }
    step["scripts"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8H",
            "execute": "before",
            "language": "groovy",
            "dependencyFileId": "01HZX3Y9M0E9W7Z6M5QK9S8P8S",
            "enabled": False,
        }
    ]
    step["assertions"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8J",
            "type": "body_contains",
            "contains": "${draft_assertion_value}",
            "regexp": False,
            "not": False,
            "enabled": False,
        }
    ]
    step["extractors"] = []

    scenario = create_scenario(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        payload=scenario_payload(steps=[step]),
    )

    yaml_text = build_debug_taurus_yaml(
        scenario=scenario,
        env_variables={"base_url": "https://api.example.internal"},
        dependency_files=[],
        jmeter_path="/opt/surgepilot/apache-jmeter/bin/jmeter",
        jmeter_version="5.4.2",
    )

    assert "draft_token" not in yaml_text


def test_csv_header_based_data_source_allows_runtime_header_variables(
    db_session: Session,
) -> None:
    user = seed_user(db_session)
    file = seed_dependency_file(db_session, user)
    step = minimal_step()
    step["path"] = "/v1/users/${page}"
    step["queryParams"] = []
    step["headers"] = []
    step["extractors"] = []
    scenario = create_scenario(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        payload=scenario_payload(
            dataSources=[
                {
                    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
                    "dependencyFileId": file.id,
                    "displayName": file.filename,
                    "delimiter": ",",
                    "quoted": None,
                    "loop": True,
                    "variableNames": [],
                    "randomOrder": False,
                    "enabled": True,
                }
            ],
            steps=[step],
        ),
    )

    yaml_text = build_debug_taurus_yaml(
        scenario=scenario,
        env_variables={"base_url": "https://api.example.internal"},
        dependency_files=[file],
        jmeter_path="/opt/surgepilot/apache-jmeter/bin/jmeter",
        jmeter_version="5.4.2",
    )

    assert "data-sources:" in yaml_text
    assert "variable-names" not in yaml_text
    assert "${page}" in yaml_text


def test_declared_csv_variable_names_satisfy_debug_variable_validation(
    db_session: Session,
) -> None:
    user = seed_user(db_session)
    file = seed_dependency_file(db_session, user)
    step = minimal_step()
    step["queryParams"] = []
    step["headers"] = []
    step["path"] = "/v1/users/${page}"
    step["extractors"] = []
    scenario = create_scenario(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        payload=scenario_payload(
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
            steps=[step],
        ),
    )

    yaml_text = build_debug_taurus_yaml(
        scenario=scenario,
        env_variables={"base_url": "https://api.example.internal"},
        dependency_files=[file],
        jmeter_path="/opt/surgepilot/apache-jmeter/bin/jmeter",
        jmeter_version="5.4.2",
    )

    assert "variable-names: page" in yaml_text


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


def test_debug_taurus_builder_rejects_unsafe_resolved_base_urls() -> None:
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


def test_csv_data_source_variable_names_must_be_valid_identifiers(db_session: Session) -> None:
    user = seed_user(db_session)
    file = seed_dependency_file(db_session, user)

    with pytest.raises(AppError) as exc_info:
        create_scenario(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            payload=scenario_payload(
                dataSources=[
                    {
                        "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
                        "dependencyFileId": file.id,
                        "displayName": file.filename,
                        "delimiter": ",",
                        "quoted": None,
                        "loop": True,
                        "variableNames": ["user-id", ""],
                        "randomOrder": False,
                        "enabled": True,
                    }
                ]
            ),
        )

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert {detail["code"] for detail in exc_info.value.details} == {"invalid_variable_name"}


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
    create_scenario(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        payload=scenario_payload(
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
        ),
    )

    with pytest.raises(AppError) as exc_info:
        delete_dependency_file_metadata(db_session, file=file, actor_user_id=user.id)

    assert exc_info.value.code == "FILE_IN_USE"


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


def test_debug_run_snapshot_filters_disabled_steps_and_records_audit(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = seed_user(db_session)
    script_file = seed_dependency_file(
        db_session,
        user,
        file_id="01HZX3Y9M0E9W7Z6M5QK9S8P8S",
        filename="setup.groovy",
        content_type="text/x-groovy",
    )
    enabled_step = {**minimal_step(), "queryParams": [], "headers": [], "extractors": []}
    enabled_step["scripts"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8T",
            "execute": "before",
            "language": "groovy",
            "dependencyFileId": script_file.id,
            "enabled": True,
        }
    ]
    disabled_step = {**minimal_step("01HZX3Y9M0E9W7Z6M5QK9S8P8D"), "enabled": False}
    disabled_step["body"] = {
        "type": "raw",
        "contentType": "application/json",
        "rawText": '{"draft":"should-not-snapshot"}',
        "formFields": [],
    }
    scenario = create_scenario(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        payload=scenario_payload(
            baseUrlExpression="https://api.example.internal",
            steps=[enabled_step, disabled_step],
        ),
    )
    db_session.add(
        SystemSetting(
            key="jmeterMemoryXmx",
            value_json="6G",
            updated_by_user_id=user.id,
            updated_at=utc_now(),
        )
    )
    db_session.flush()
    captured: dict[str, object] = {}

    def fake_create_run_execution(db: Session, execution) -> Run:
        captured["snapshot"] = execution.snapshot_payload
        now = utc_now()
        run = Run(
            id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
            workspace_id=execution.workspace_id,
            run_type="debug",
            state="initializing",
            source_type="debug_scenario",
            source_id=execution.source_id,
            selected_node_id=execution.selected_node_id,
            triggered_by_user_id=user.id,
            forced_convergence=False,
            remote_start_requested_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(run)
        db.flush()
        db.add(
            RunSnapshot(
                id="01HZX3Y9M0E9W7Z6M5QK9S8P7Q",
                run_id=run.id,
                workspace_id=execution.workspace_id,
                snapshot_version=1,
                snapshot_hash=scenario_service._snapshot_hash(execution.snapshot_payload),
                snapshot_json=execution.snapshot_payload,
                created_at=now,
            )
        )
        db.flush()
        return run

    monkeypatch.setattr(scenario_service, "create_run_execution", fake_create_run_execution)

    result = create_debug_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=scenario.id,
        expected_source_revision=scenario.revision,
        env_group_id=None,
        selected_node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
    )

    snapshot = captured["snapshot"]
    assert isinstance(snapshot, dict)
    assert [step["id"] for step in snapshot["scenario"]["steps"]] == [enabled_step["id"]]
    assert snapshot["dependencyFiles"] == [
        {
            "id": script_file.id,
            "filename": script_file.filename,
            "sizeBytes": script_file.size_bytes,
            "sha256": script_file.sha256,
            "refType": "script",
            "stepId": enabled_step["id"],
        }
    ]
    assert snapshot["jmeterMemoryXmx"] == "6G"
    assert "should-not-snapshot" not in str(snapshot)
    db_session.get(SystemSetting, "jmeterMemoryXmx").value_json = "8G"
    db_session.flush()

    class MemoryStorage:
        def get_stream(self, *, bucket: str, object_key: str):
            assert bucket == script_file.storage_bucket
            assert object_key == script_file.storage_object_key
            return SimpleNamespace(stream=BytesIO(b"vars.put('trace_id', 'abc')"), size_bytes=25)

    monkeypatch.setattr(
        "app.services.execution_bundles.get_storage_client", lambda: MemoryStorage()
    )
    bundle_files = build_debug_scenario_execution_bundle(
        db_session,
        run_id=result.run.id,
        runner_home="/opt/surgepilot/runner",
        settings=scenario_service.get_settings(),
    )
    bundle_by_path = {item.relative_path: item for item in bundle_files}
    script_bundle_path = scenario_service.bundle_file_path(script_file)
    assert script_bundle_path in bundle_by_path
    generated_yaml = bundle_by_path["surgepilot.yml"].content.decode()
    assert "memory-xmx: 6G" in generated_yaml
    assert "memory-xmx: 8G" not in generated_yaml
    manifest = json.loads(bundle_by_path["manifest.json"].content.decode())
    assert manifest["dependencyFiles"] == [
        {
            "id": script_file.id,
            "filename": script_file.filename,
            "sizeBytes": script_file.size_bytes,
            "sha256": script_file.sha256,
            "bundlePath": script_bundle_path,
        }
    ]
    yaml_text = bundle_by_path["surgepilot.yml"].content.decode()
    assert f"script-file: {script_bundle_path}" in yaml_text
    event = db_session.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "run.debug_requested")
    )
    assert event is not None
    assert event.target_id == result.run.id
    assert event.details_json["scenarioId"] == scenario.id
    assert "steps" not in event.details_json


def test_debug_run_rechecks_dedup_after_busy_race(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = seed_user(db_session)
    scenario = create_scenario(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        payload=scenario_payload(
            baseUrlExpression="https://api.example.internal",
            steps=[{**minimal_step(), "queryParams": [], "headers": [], "extractors": []}],
        ),
    )

    def fake_create_run_execution(db: Session, execution) -> Run:
        now = utc_now()
        run = Run(
            id=new_ulid(),
            workspace_id=execution.workspace_id,
            run_type="debug",
            state="initializing",
            source_type="debug_scenario",
            source_id=execution.source_id,
            selected_node_id=execution.selected_node_id,
            triggered_by_user_id=user.id,
            forced_convergence=False,
            remote_start_requested_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(run)
        db.flush()
        snapshot_hash = scenario_service._snapshot_hash(execution.snapshot_payload)
        dedup_hash = scenario_service._dedup_hash(
            {
                "workspaceId": DEFAULT_WORKSPACE_ID,
                "triggeredByUserId": user.id,
                "runType": "debug",
                "sourceType": "debug_scenario",
                "sourceId": scenario.id,
                "scenarioRevision": scenario.revision,
                "envGroupId": None,
                "selectedNodeId": execution.selected_node_id,
                "snapshotHash": snapshot_hash,
            }
        )
        db.add(
            RunCreationDedupKey(
                id=new_ulid(),
                workspace_id=DEFAULT_WORKSPACE_ID,
                dedup_key_hash=dedup_hash,
                run_id=run.id,
                expires_at=now + scenario_service.timedelta(seconds=30),
                created_at=now,
            )
        )
        db.flush()
        raise AppError("LOAD_NODE_BUSY", "Load Node is busy.", 409)

    monkeypatch.setattr(scenario_service, "create_run_execution", fake_create_run_execution)

    result = create_debug_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=scenario.id,
        expected_source_revision=scenario.revision,
        env_group_id=None,
        selected_node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
    )

    assert result.deduplicated is True
    assert result.status_code == 200


def test_debug_run_rechecks_current_revision_before_snapshot(db_session: Session) -> None:
    user = seed_user(db_session)
    scenario = create_scenario(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        payload=scenario_payload(
            baseUrlExpression="https://api.example.internal",
            steps=[{**minimal_step(), "queryParams": [], "headers": [], "extractors": []}],
        ),
    )
    db_session.execute(
        update(Scenario)
        .where(Scenario.id == scenario.id)
        .values(revision=2)
        .execution_options(synchronize_session=False)
    )

    with pytest.raises(AppError) as exc_info:
        create_debug_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            source_id=scenario.id,
            expected_source_revision=1,
            env_group_id=None,
            selected_node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
        )

    assert exc_info.value.code == "SCENARIO_REVISION_CONFLICT"


def test_taurus_yaml_builder_emits_documented_jmeter_fields(db_session: Session) -> None:
    user = seed_user(db_session)
    scenario = create_scenario(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, payload=scenario_payload()
    )

    yaml_text = build_debug_taurus_yaml(
        scenario=scenario,
        env_variables={
            "base_url": "https://api.example.internal",
            "token": "regular-token",
            "page": "1",
        },
        dependency_files=[],
        jmeter_path="/opt/surgepilot/apache-jmeter/bin/jmeter",
        jmeter_version="5.4.2",
    )

    assert "executor: jmeter" in yaml_text
    assert "concurrency: 1" in yaml_text
    assert "iterations: 1" in yaml_text
    assert "default-address: https://api.example.internal" in yaml_text
    assert "follow-redirects: true" in yaml_text
    assert "keepalive: true" in yaml_text
    assert "timeout: 30s" in yaml_text
    assert "extract-jsonpath:" in yaml_text
    assert "subject: http-code" in yaml_text
    assert "detect-plugins: false" in yaml_text
    assert "memory-xmx: 4G" in yaml_text
    assert "force-ctg: false" in yaml_text
    assert "fix-log4j: false" in yaml_text
    assert "fix-jars: false" in yaml_text
    assert "aggregator: consolidator" in yaml_text
    assert "class: bzt.modules.jmeter.JMeterExecutor" in yaml_text
    assert "http: bzt.jmx.http.HTTPProtocolHandler" in yaml_text
    assert "class: bzt.modules.provisioning.Local" in yaml_text
    assert "class: bzt.modules.aggregator.ConsolidatingAggregator" in yaml_text
    assert "class: bzt.modules.reporting.FinalStatus" in yaml_text
    assert "class: bzt.modules.console.ConsoleStatusReporter" in yaml_text
    assert "module: final-stats" in yaml_text
    assert "dump-csv: artifacts/finalstats.csv" in yaml_text
    assert "storage_object_key" not in yaml_text
    assert "dependency-files/not-returned" not in yaml_text


def test_taurus_yaml_builder_emits_step_keepalive_override(db_session: Session) -> None:
    user = seed_user(db_session)
    step = minimal_step()
    step["settings"] = {
        "thinkTimeMs": None,
        "timeoutMs": None,
        "followRedirects": None,
        "keepAlive": False,
    }
    scenario = create_scenario(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        payload=scenario_payload(steps=[step]),
    )

    yaml_text = build_debug_taurus_yaml(
        scenario=scenario,
        env_variables={
            "base_url": "https://api.example.internal",
            "token": "regular-token",
            "page": "1",
        },
        dependency_files=[],
        jmeter_path="/opt/surgepilot/apache-jmeter/bin/jmeter",
        jmeter_version="5.4.2",
    )

    assert "keepalive: false" in yaml_text
