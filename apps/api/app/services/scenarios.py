"""P0-05 Visual Scenario service and Taurus requests-scenario execution builder.

This module implements the P0 Scenario service contract from
``docs/sdd/slices/P0-05-visual-scenario-debug-run.md``:

- Pydantic-normalized Scenario create/patch content with structural and
  semantic validation of the Visual Scenario JSON (headers, body, upload
  files, extractors, assertions, inline JSR223/Groovy scripts and Step
  settings).
- Optimistic Scenario revision handling: PATCH requires ``expectedRevision``
  and increments ``revision`` on success.
- Transactional maintenance of ``scenario_dependency_file_refs`` rows derived
  from enabled CSV data sources and enabled Step upload files, and deletion
  protection for Dependency Files referenced by live Scenarios.
- Scenario soft-delete protection while active ``debug_scenario`` Runs exist.
- The execution builder that maps a saved Visual Scenario plus validated Env
  Group variables into a canonical Taurus requests-scenario YAML document for
  JMeter execution (alias ``surgepilot_scenario``).

P0 scripts are request-level inline JSR223/Groovy text stored in the Scenario
Step JSON and mapped to Taurus ``jsr223`` ``script-text`` entries. The
``script`` Dependency File reference type and script-file handling are
introduced by a later migration and are intentionally absent here.
"""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any
from urllib.parse import quote
from urllib.parse import unquote
from urllib.parse import urlparse

import yaml
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.ids import new_ulid
from app.core.time import utc_now
from app.models.auth import User
from app.models.dependency_files import DependencyFile
from app.models.runs import Run
from app.models.scenarios import Scenario, ScenarioDependencyFileRef
from app.schemas.scenarios import ScenarioCreateRequest, ScenarioPatchRequest

VARIABLE_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
VARIABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
REGEXP_TEMPLATE_GROUP_PATTERN = re.compile(r"\$(\d+)\$")
HTTP_TOKEN_PATTERN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
ACTIVE_RUN_STATES = {"initializing", "running", "stopping"}
SCENARIO_ALIAS = "surgepilot_scenario"
UNSAFE_URL_CHAR_PATTERN = re.compile(r"[\x00-\x20\x7f]")


def request_label(method: str, path: str) -> str:
    """Build the bounded Taurus request label from Step method and path."""
    return f"{method} {path}"[:200]


def field_error(field: str, message: str, code: str = "invalid_field") -> dict[str, str]:
    return {"field": field, "code": code, "message": message}


def validation_error(details: list[dict[str, str]]) -> AppError:
    return AppError("VALIDATION_ERROR", "Validation failed.", 422, details)


def _pydantic_content(payload: dict[str, Any], *, patch: bool = False) -> dict[str, Any]:
    model = ScenarioPatchRequest if patch else ScenarioCreateRequest
    try:
        return model.model_validate(payload).model_dump(by_alias=True, mode="json")
    except ValidationError as exc:
        raise validation_error(
            [
                field_error(
                    ".".join(str(part) for part in error["loc"]),
                    "Invalid field value.",
                    "invalid_field",
                )
                for error in exc.errors()
            ]
        ) from exc


def _active_items(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if item.get("enabled", True)]


def _extract_variables(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, str):
        found.update(VARIABLE_PATTERN.findall(value))
    elif isinstance(value, list):
        for item in value:
            found.update(_extract_variables(item))
    elif isinstance(value, dict):
        for item in value.values():
            found.update(_extract_variables(item))
    return found


def _extract_enabled_step_variables(step: dict[str, Any]) -> set[str]:
    found = _extract_variables(step.get("path"))
    for key in ("queryParams", "headers"):
        for item in _active_items(step.get(key, [])):
            found.update(_extract_variables(item))
    body = step.get("body") or {"type": "none"}
    if body.get("type") == "raw":
        found.update(_extract_variables(body.get("contentType")))
        found.update(_extract_variables(body.get("rawText")))
    elif body.get("type") == "form":
        for field in _active_items(body.get("formFields", [])):
            found.update(_extract_variables(field))
    for assertion in _active_items(step.get("assertions", [])):
        found.update(_extract_variables(assertion))
    return found


def _regexp_group_count(expression: str) -> int | None:
    try:
        return re.compile(expression).groups
    except re.error:
        return None


def _regexp_template_references_valid_group(template: str, group_count: int) -> bool:
    value = template.strip()
    if value.isdecimal():
        group_number = int(value)
        return 1 <= group_number <= group_count
    references = [int(item) for item in REGEXP_TEMPLATE_GROUP_PATTERN.findall(value)]
    return bool(references) and all(1 <= item <= group_count for item in references)


def _safe_bundle_filename(filename: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    if not safe or safe in {".", ".."}:
        return "file"
    return safe[:255]


def bundle_file_path(file: DependencyFile) -> str:
    return f"files/{file.id}/{_safe_bundle_filename(file.filename)}"


def ms_to_taurus_time(milliseconds: int) -> str:
    if milliseconds == 0:
        return "0ms"
    seconds, ms = divmod(milliseconds, 1000)
    if seconds and ms:
        return f"{seconds}s{ms}ms"
    if seconds:
        return f"{seconds}s"
    return f"{ms}ms"


def _validate_tags(tags: list[str]) -> list[str]:
    details: list[dict[str, str]] = []
    normalized: list[str] = []
    for index, tag in enumerate(tags):
        value = str(tag).strip()
        if not value or len(value) > 32:
            details.append(
                field_error(f"tags[{index}]", "Tag must be 1-32 characters.", "invalid_tag")
            )
        elif value not in normalized:
            normalized.append(value)
    if details:
        raise validation_error(details)
    return normalized


def _validate_dependency_files(
    db: Session, *, workspace_id: str, content: dict[str, Any]
) -> dict[str, DependencyFile]:
    ids: set[str] = set()
    for data_source in content["dataSources"]:
        if data_source.get("enabled", True):
            ids.add(data_source["dependencyFileId"])
    for step in content["steps"]:
        if not step.get("enabled", True):
            continue
        for upload in step.get("uploadFiles", []):
            if upload.get("enabled", True):
                ids.add(upload["dependencyFileId"])
    if not ids:
        return {}
    files = {
        file.id: file
        for file in db.scalars(
            select(DependencyFile).where(
                DependencyFile.workspace_id == workspace_id,
                DependencyFile.id.in_(ids),
                DependencyFile.status == "available",
            )
        )
    }
    missing = sorted(ids - files.keys())
    if missing:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    return files


def validate_scenario_content(
    content: dict[str, Any], *, require_enabled_step: bool = False
) -> dict[str, Any]:
    details: list[dict[str, str]] = []
    content = dict(content)
    if not content.get("name", "").strip():
        details.append(field_error("name", "Scenario name is required.", "required_field"))
    content["tags"] = _validate_tags(content.get("tags", []))
    for data_source_index, data_source in enumerate(content.get("dataSources", [])):
        delimiter = data_source.get("delimiter")
        if delimiter is not None and delimiter != "tab" and len(delimiter) != 1:
            details.append(
                field_error(
                    f"dataSources[{data_source_index}].delimiter",
                    "CSV delimiter must be a single character or tab.",
                    "invalid_delimiter",
                )
            )
        for variable_index, variable_name in enumerate(data_source.get("variableNames", [])):
            if not VARIABLE_NAME_PATTERN.fullmatch(variable_name):
                details.append(
                    field_error(
                        f"dataSources[{data_source_index}].variableNames[{variable_index}]",
                        "Variable name is invalid.",
                        "invalid_variable_name",
                    )
                )
    enabled_step_count = 0
    reserved_variable_names: set[str] = set()
    for data_source in _active_items(content.get("dataSources", [])):
        reserved_variable_names.update(data_source.get("variableNames", []) or [])
    extractor_names: set[str] = set()
    step_ids_seen: set[str] = set()
    for step_index, step in enumerate(content.get("steps", [])):
        prefix = f"steps[{step_index}]"
        step_id = step.get("id")
        if step_id in step_ids_seen:
            details.append(
                field_error(f"{prefix}.id", "Step IDs must be unique.", "duplicate_step_id")
            )
        else:
            step_ids_seen.add(step_id)
        enabled = step.get("enabled", True)
        if enabled:
            enabled_step_count += 1
        else:
            continue
        headers_seen: set[str] = set()
        for header_index, header in enumerate(step.get("headers", [])):
            if not header.get("enabled", True):
                continue
            name = header.get("name", "")
            lower_name = name.lower()
            if not HTTP_TOKEN_PATTERN.fullmatch(name):
                details.append(
                    field_error(
                        f"{prefix}.headers[{header_index}].name",
                        "Header name is invalid.",
                        "invalid_header_name",
                    )
                )
            if lower_name in headers_seen:
                details.append(
                    field_error(
                        f"{prefix}.headers[{header_index}].name",
                        "Header names must be unique within a Step.",
                        "duplicate_header",
                    )
                )
            headers_seen.add(lower_name)
        body = step.get("body", {"type": "none"})
        if step.get("method") in {"GET", "HEAD"} and body.get("type") != "none":
            details.append(
                field_error(
                    f"{prefix}.body.type",
                    "GET and HEAD requests cannot have a body.",
                    "body_not_allowed",
                )
            )
        if body.get("type") == "form" and step.get("method") not in {"POST", "PUT", "PATCH"}:
            details.append(
                field_error(
                    f"{prefix}.body.type",
                    "Form bodies are allowed only for POST, PUT and PATCH.",
                    "body_not_allowed",
                )
            )
        form_names: set[str] = set()
        for field_index, field in enumerate(body.get("formFields", [])):
            if not field.get("enabled", True):
                continue
            name = field.get("name", "")
            if name in form_names:
                details.append(
                    field_error(
                        f"{prefix}.body.formFields[{field_index}].name",
                        "Form field names must be unique.",
                        "duplicate_form_field",
                    )
                )
            form_names.add(name)
        uploads = _active_items(step.get("uploadFiles", []))
        if step.get("method") == "PUT" and len(uploads) > 1:
            details.append(
                field_error(
                    f"{prefix}.uploadFiles",
                    "PUT requests can include only one upload file.",
                    "too_many_upload_files",
                )
            )
        for extractor_index, extractor in enumerate(step.get("extractors", [])):
            if not extractor.get("enabled", True):
                continue
            name = extractor.get("variableName", "")
            if not VARIABLE_NAME_PATTERN.fullmatch(name):
                details.append(
                    field_error(
                        f"{prefix}.extractors[{extractor_index}].variableName",
                        "Extractor variable name is invalid.",
                        "invalid_variable_name",
                    )
                )
            if name in reserved_variable_names or name in extractor_names:
                details.append(
                    field_error(
                        f"{prefix}.extractors[{extractor_index}].variableName",
                        "Extractor variable conflicts with another variable.",
                        "variable_conflict",
                    )
                )
            extractor_names.add(name)
            if extractor["type"] == "regexp":
                group_count = _regexp_group_count(extractor["expression"])
                if group_count is None:
                    details.append(
                        field_error(
                            f"{prefix}.extractors[{extractor_index}].expression",
                            "Regexp extractor expression is invalid.",
                            "invalid_regexp",
                        )
                    )
                elif group_count < 1:
                    details.append(
                        field_error(
                            f"{prefix}.extractors[{extractor_index}].expression",
                            "Regexp extractor must include at least one capture group.",
                            "regexp_capture_group_required",
                        )
                    )
                elif extractor.get("template") is not None and not (
                    _regexp_template_references_valid_group(
                        extractor["template"],
                        group_count,
                    )
                ):
                    details.append(
                        field_error(
                            f"{prefix}.extractors[{extractor_index}].template",
                            "Regexp extractor template must reference an existing capture group.",
                            "invalid_regexp_template",
                        )
                    )
        for assertion_index, assertion in enumerate(step.get("assertions", [])):
            if not assertion.get("enabled", True):
                continue
            assertion_type = assertion.get("type")
            if assertion_type == "status_code" and assertion.get("expectedStatus") is None:
                details.append(
                    field_error(
                        f"{prefix}.assertions[{assertion_index}].expectedStatus",
                        "Expected status is required.",
                        "required_field",
                    )
                )
            elif (
                assertion_type == "body_contains" and not (assertion.get("contains") or "").strip()
            ):
                details.append(
                    field_error(
                        f"{prefix}.assertions[{assertion_index}].contains",
                        "Contains text is required.",
                        "required_field",
                    )
                )
            elif (
                assertion_type == "jsonpath_exists"
                and not (assertion.get("jsonpath") or "").strip()
            ):
                details.append(
                    field_error(
                        f"{prefix}.assertions[{assertion_index}].jsonpath",
                        "JSONPath is required.",
                        "required_field",
                    )
                )
            elif assertion_type == "jsonpath_equals":
                if not (assertion.get("jsonpath") or "").strip():
                    details.append(
                        field_error(
                            f"{prefix}.assertions[{assertion_index}].jsonpath",
                            "JSONPath is required.",
                            "required_field",
                        )
                    )
                if assertion.get("expectedValue") is None or assertion.get("expectedValue") == "":
                    details.append(
                        field_error(
                            f"{prefix}.assertions[{assertion_index}].expectedValue",
                            "Expected value is required.",
                            "required_field",
                        )
                    )
        for script_index, script in enumerate(step.get("scripts", [])):
            if not script.get("enabled", True):
                continue
            if not (script.get("scriptText") or "").strip():
                details.append(
                    field_error(
                        f"{prefix}.scripts[{script_index}].scriptText",
                        "Script text is required.",
                        "script_text_required",
                    )
                )
    if require_enabled_step and enabled_step_count == 0:
        details.append(
            field_error("steps", "At least one enabled Step is required.", "enabled_step_required")
        )
    if details:
        raise validation_error(details)
    return content


def _replace_dependency_refs(
    db: Session,
    *,
    scenario: Scenario,
    files: dict[str, DependencyFile],
    content: dict[str, Any],
) -> None:
    db.query(ScenarioDependencyFileRef).filter(
        ScenarioDependencyFileRef.scenario_id == scenario.id
    ).delete(synchronize_session=False)
    now = utc_now()
    refs: list[ScenarioDependencyFileRef] = []
    seen: set[tuple[str, str, str | None]] = set()
    for data_source in content["dataSources"]:
        if not data_source.get("enabled", True):
            continue
        key = (data_source["dependencyFileId"], "data_source", None)
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            ScenarioDependencyFileRef(
                id=new_ulid(),
                workspace_id=scenario.workspace_id,
                scenario_id=scenario.id,
                dependency_file_id=data_source["dependencyFileId"],
                ref_type="data_source",
                step_id=None,
                created_at=now,
            )
        )
    for step in content["steps"]:
        if not step.get("enabled", True):
            continue
        for upload in step.get("uploadFiles", []):
            if not upload.get("enabled", True):
                continue
            key = (upload["dependencyFileId"], "upload_file", step["id"])
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                ScenarioDependencyFileRef(
                    id=new_ulid(),
                    workspace_id=scenario.workspace_id,
                    scenario_id=scenario.id,
                    dependency_file_id=upload["dependencyFileId"],
                    ref_type="upload_file",
                    step_id=step["id"],
                    created_at=now,
                )
            )
    _ = files
    db.add_all(refs)


def create_scenario(
    db: Session, *, workspace_id: str, actor: User, payload: dict[str, Any]
) -> Scenario:
    content = validate_scenario_content(_pydantic_content(payload))
    files = _validate_dependency_files(db, workspace_id=workspace_id, content=content)
    now = utc_now()
    scenario = Scenario(
        id=new_ulid(),
        workspace_id=workspace_id,
        scenario_type="visual",
        name=content["name"].strip(),
        description=(content.get("description") or None),
        tags_json=content["tags"],
        base_url_expression=content["baseUrlExpression"],
        default_settings_json=content["defaultSettings"],
        data_sources_json=content["dataSources"],
        steps_json=content["steps"],
        visual_schema_version=1,
        revision=1,
        created_by_user_id=actor.id,
        updated_by_user_id=actor.id,
        created_at=now,
        updated_at=now,
    )
    db.add(scenario)
    db.flush()
    _replace_dependency_refs(db, scenario=scenario, files=files, content=content)
    db.flush()
    return scenario


def get_scenario(db: Session, *, workspace_id: str, scenario_id: str) -> Scenario:
    scenario = db.scalar(
        select(Scenario).where(
            Scenario.id == scenario_id,
            Scenario.workspace_id == workspace_id,
            Scenario.deleted_at.is_(None),
        )
    )
    if scenario is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    return scenario


def patch_scenario(
    db: Session,
    *,
    scenario: Scenario,
    actor: User,
    expected_revision: int,
    payload: dict[str, Any],
) -> Scenario:
    current = db.scalar(
        select(Scenario)
        .where(
            Scenario.id == scenario.id,
            Scenario.workspace_id == scenario.workspace_id,
            Scenario.deleted_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if current is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    scenario = current
    if scenario.revision != expected_revision:
        raise AppError(
            "SCENARIO_REVISION_CONFLICT",
            "Scenario was updated by another request. Reload and try again.",
            409,
        )
    content = validate_scenario_content(
        _pydantic_content({**payload, "expectedRevision": expected_revision}, patch=True)
    )
    content.pop("expectedRevision", None)
    files = _validate_dependency_files(db, workspace_id=scenario.workspace_id, content=content)
    scenario.name = content["name"].strip()
    scenario.description = content.get("description") or None
    scenario.tags_json = content["tags"]
    scenario.base_url_expression = content["baseUrlExpression"]
    scenario.default_settings_json = content["defaultSettings"]
    scenario.data_sources_json = content["dataSources"]
    scenario.steps_json = content["steps"]
    scenario.revision += 1
    scenario.updated_by_user_id = actor.id
    scenario.updated_at = utc_now()
    _replace_dependency_refs(db, scenario=scenario, files=files, content=content)
    db.flush()
    return scenario


def list_scenarios(
    db: Session,
    *,
    workspace_id: str,
    page: int,
    page_size: int,
    search: str | None,
    tag: list[str],
    sort: str,
) -> tuple[list[Scenario], int]:
    statement = select(Scenario).where(
        Scenario.workspace_id == workspace_id, Scenario.deleted_at.is_(None)
    )
    count_statement = select(func.count(Scenario.id)).where(
        Scenario.workspace_id == workspace_id, Scenario.deleted_at.is_(None)
    )
    if search:
        pattern = f"%{search.lower()}%"
        statement = statement.where(func.lower(Scenario.name).like(pattern))
        count_statement = count_statement.where(func.lower(Scenario.name).like(pattern))
    if sort == "updatedAt":
        statement = statement.order_by(Scenario.updated_at.asc(), Scenario.id.asc())
    elif sort == "name":
        statement = statement.order_by(func.lower(Scenario.name).asc(), Scenario.id.asc())
    elif sort == "-name":
        statement = statement.order_by(func.lower(Scenario.name).desc(), Scenario.id.desc())
    else:
        statement = statement.order_by(Scenario.updated_at.desc(), Scenario.id.desc())
    normalized_tags = [item for item in tag if item]
    if normalized_tags:
        matched = [
            scenario
            for scenario in db.scalars(statement)
            if all(item in (scenario.tags_json or []) for item in normalized_tags)
        ]
        total = len(matched)
        start = (page - 1) * page_size
        items = matched[start : start + page_size]
        return items, total
    total = db.scalar(count_statement) or 0
    items = list(db.scalars(statement.offset((page - 1) * page_size).limit(page_size)))
    return items, total


def delete_scenario(db: Session, *, scenario: Scenario, actor: User) -> None:
    locked = db.scalar(
        select(Scenario)
        .where(
            Scenario.id == scenario.id,
            Scenario.workspace_id == scenario.workspace_id,
            Scenario.deleted_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    scenario = locked
    active_run = db.scalar(
        select(Run.id)
        .where(
            Run.workspace_id == scenario.workspace_id,
            Run.source_type == "debug_scenario",
            Run.source_id == scenario.id,
            Run.state.in_(list(ACTIVE_RUN_STATES)),
        )
        .limit(1)
    )
    if active_run is not None:
        raise AppError("RESOURCE_IN_USE", "Resource is in use and cannot be deleted.", 409)
    now = utc_now()
    scenario.deleted_at = now
    scenario.updated_by_user_id = actor.id
    scenario.updated_at = now
    db.flush()


def _resolve_expression(expression: str, variables: dict[str, str]) -> str:
    missing = [name for name in VARIABLE_PATTERN.findall(expression) if name not in variables]
    if missing:
        raise validation_error(
            [
                field_error(
                    "baseUrlExpression",
                    "Variable is not provided by the selected Env Group.",
                    "missing_variable",
                )
                for _name in missing
            ]
        )
    return VARIABLE_PATTERN.sub(lambda match: variables[match.group(1)], expression)


def _validate_resolved_base_url(value: str) -> None:
    parsed = urlparse(value)
    invalid = parsed.scheme not in {"http", "https"} or not parsed.netloc
    invalid = invalid or bool(UNSAFE_URL_CHAR_PATTERN.search(value))
    decoded_segments = [unquote(segment) for segment in (parsed.path or "").split("/")]
    invalid = invalid or any(segment in {".", ".."} for segment in decoded_segments)
    if invalid:
        raise validation_error(
            [
                field_error(
                    "baseUrlExpression",
                    (
                        "Resolved Base URL must use http or https without unsafe "
                        "characters or path traversal."
                    ),
                    "invalid_url",
                )
            ]
        )


def _validate_debug_variables(content: dict[str, Any], env_variables: dict[str, str]) -> None:
    details: list[dict[str, str]] = []
    available = set(env_variables.keys())
    extractor_names: set[str] = set()
    has_header_based_csv_source = False
    for data_source in _active_items(content.get("dataSources", [])):
        variable_names = data_source.get("variableNames") or []
        if variable_names:
            available.update(variable_names)
        else:
            has_header_based_csv_source = True
    initial_references = _extract_variables(content.get("baseUrlExpression"))
    if not has_header_based_csv_source:
        for name in sorted(initial_references - available):
            details.append(
                field_error(
                    "baseUrlExpression",
                    (
                        f"Variable {name} is not provided by the selected Env Group, "
                        "CSV variables or earlier extractors."
                    ),
                    "missing_variable",
                )
            )
    for step_index, step in enumerate(_active_items(content.get("steps", []))):
        references = _extract_enabled_step_variables(step)
        if not has_header_based_csv_source:
            for name in sorted(references - available):
                details.append(
                    field_error(
                        f"steps[{step_index}]",
                        (
                            f"Variable {name} is not provided by the selected Env Group, "
                            "CSV variables or earlier extractors."
                        ),
                        "missing_variable",
                    )
                )
        for extractor in _active_items(step.get("extractors", [])):
            name = extractor["variableName"]
            if name in available or name in extractor_names:
                details.append(
                    field_error(
                        f"steps[{step_index}].extractors",
                        "Extractor variable conflicts with another variable.",
                        "variable_conflict",
                    )
                )
            extractor_names.add(name)
            available.add(name)
    if details:
        raise validation_error(details)


def _request_url(step: dict[str, Any]) -> str:
    params = []
    for item in _active_items(step.get("queryParams", [])):
        name = quote(item["name"], safe="${}")
        value = quote(item.get("value", ""), safe="${}/:")
        params.append(f"{name}={value}")
    return step["path"] + ("?" + "&".join(params) if params else "")


def _request_body(step: dict[str, Any]) -> Any | None:
    body = step.get("body") or {"type": "none"}
    if body.get("type") == "raw":
        return body.get("rawText") or ""
    if body.get("type") == "form":
        return {
            item["name"]: item.get("value", "")
            for item in _active_items(body.get("formFields", []))
        }
    return None


def _request_headers(step: dict[str, Any]) -> dict[str, str]:
    headers = {
        item["name"]: item.get("value", "") for item in _active_items(step.get("headers", []))
    }
    body = step.get("body") or {}
    content_type = body.get("contentType")
    if (
        body.get("type") == "raw"
        and content_type
        and not any(name.lower() == "content-type" for name in headers)
    ):
        headers["Content-Type"] = content_type
    return headers


def _request_extractors(step: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    jsonpath: dict[str, Any] = {}
    regexp: dict[str, Any] = {}
    for extractor in _active_items(step.get("extractors", [])):
        if extractor["type"] == "jsonpath":
            jsonpath[extractor["variableName"]] = {
                "jsonpath": extractor["expression"],
                "default": extractor.get("defaultValue") or "",
                "match-no": extractor.get("matchNo", 1),
            }
        elif extractor["type"] == "regexp":
            regexp[extractor["variableName"]] = {
                "regexp": extractor["expression"],
                "default": extractor.get("defaultValue") or "",
                "match-no": extractor.get("matchNo", 1),
                "template": extractor.get("template") or 1,
                "subject": extractor.get("subject") or "body",
            }
    if jsonpath:
        result["extract-jsonpath"] = jsonpath
    if regexp:
        result["extract-regexp"] = regexp
    return result


def _request_assertions(step: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    response_asserts: list[dict[str, Any]] = []
    jsonpath_asserts: list[dict[str, Any]] = []
    for assertion in _active_items(step.get("assertions", [])):
        if assertion["type"] == "status_code":
            response_asserts.append(
                {
                    "contains": [str(assertion["expectedStatus"])],
                    "subject": "http-code",
                    "regexp": False,
                }
            )
        elif assertion["type"] == "body_contains":
            response_asserts.append(
                {
                    "contains": [assertion.get("contains") or ""],
                    "subject": "body",
                    "regexp": assertion.get("regexp", False),
                    "not": assertion.get("not", False),
                }
            )
        elif assertion["type"] == "jsonpath_exists":
            jsonpath_asserts.append(assertion.get("jsonpath") or "$")
        elif assertion["type"] == "jsonpath_equals":
            jsonpath_asserts.append(
                {
                    "jsonpath": assertion.get("jsonpath") or "$",
                    "validate": True,
                    "expected-value": assertion.get("expectedValue") or "",
                    "regexp": assertion.get("regexp", False),
                }
            )
    if response_asserts:
        result["assert"] = response_asserts
    if jsonpath_asserts:
        result["assert-jsonpath"] = jsonpath_asserts
    return result


def _request_scripts(step: dict[str, Any]) -> list[dict[str, Any]]:
    scripts = []
    for script in _active_items(step.get("scripts", [])):
        scripts.append(
            {
                "language": script["language"],
                "execute": script["execute"],
                "script-text": script["scriptText"],
                "compile-cache": True,
            }
        )
    return scripts


def _request_uploads(
    step: dict[str, Any], files: dict[str, DependencyFile]
) -> list[dict[str, Any]]:
    uploads = []
    for upload in _active_items(step.get("uploadFiles", [])):
        file = files[upload["dependencyFileId"]]
        item = {"param": upload["fieldName"], "path": bundle_file_path(file)}
        if upload.get("mimeType"):
            item["mime-type"] = upload["mimeType"]
        uploads.append(item)
    return uploads


def build_debug_taurus_document_from_content(
    *,
    scenario_content: dict[str, Any],
    env_variables: dict[str, str],
    dependency_files: list[DependencyFile],
    jmeter_path: str,
    jmeter_version: str,
) -> dict[str, Any]:
    """Translate an already-authorized Scenario into a Taurus YAML document."""
    validate_scenario_content(scenario_content, require_enabled_step=True)
    _validate_debug_variables(scenario_content, env_variables)
    default_address = _resolve_expression(scenario_content["baseUrlExpression"], env_variables)
    _validate_resolved_base_url(default_address)
    files = {file.id: file for file in dependency_files}
    settings = scenario_content["defaultSettings"]
    scenario_doc: dict[str, Any] = {
        "default-address": default_address,
        "store-cache": settings["storeCache"],
        "store-cookie": settings["storeCookie"],
        "keepalive": settings["keepAlive"],
        "follow-redirects": settings["followRedirects"],
        "retrieve-resources": settings["retrieveResources"],
        "think-time": ms_to_taurus_time(settings["thinkTimeMs"]),
        "timeout": ms_to_taurus_time(settings["timeoutMs"]),
        "variables": env_variables,
    }
    data_sources = []
    for data_source in _active_items(scenario_content["dataSources"]):
        file = files[data_source["dependencyFileId"]]
        item: dict[str, Any] = {
            "path": bundle_file_path(file),
            "loop": data_source.get("loop", True),
        }
        if data_source.get("delimiter"):
            item["delimiter"] = data_source["delimiter"]
        if data_source.get("quoted") is not None:
            item["quoted"] = data_source["quoted"]
        if data_source.get("variableNames"):
            item["variable-names"] = ",".join(data_source["variableNames"])
        item["random-order"] = data_source.get("randomOrder", False)
        data_sources.append(item)
    if data_sources:
        scenario_doc["data-sources"] = data_sources
    requests = []
    for step in _active_items(scenario_content["steps"]):
        request: dict[str, Any] = {
            "label": request_label(step["method"], step["path"]),
            "url": _request_url(step),
            "method": step["method"],
        }
        headers = _request_headers(step)
        if headers:
            request["headers"] = headers
        body = _request_body(step)
        if body is not None:
            request["body"] = body
        uploads = _request_uploads(step, files)
        if uploads:
            request["upload-files"] = uploads
        step_settings = step.get("settings") or {}
        if step_settings.get("thinkTimeMs") is not None:
            request["think-time"] = ms_to_taurus_time(step_settings["thinkTimeMs"])
        if step_settings.get("timeoutMs") is not None:
            request["timeout"] = ms_to_taurus_time(step_settings["timeoutMs"])
        if step_settings.get("followRedirects") is not None:
            request["follow-redirects"] = step_settings["followRedirects"]
        if step_settings.get("keepAlive") is not None:
            request["keepalive"] = step_settings["keepAlive"]
        request.update(_request_extractors(step))
        request.update(_request_assertions(step))
        scripts = _request_scripts(step)
        if scripts:
            request["jsr223"] = scripts
        requests.append(request)
    scenario_doc["requests"] = requests
    return {
        "settings": {"env": {}},
        "modules": {
            "jmeter": {
                "path": jmeter_path,
                "version": jmeter_version,
                "detect-plugins": False,
                "force-ctg": False,
            }
        },
        "execution": [
            {"executor": "jmeter", "concurrency": 1, "iterations": 1, "scenario": SCENARIO_ALIAS}
        ],
        "scenarios": {SCENARIO_ALIAS: scenario_doc},
    }


def build_debug_taurus_yaml_from_content(
    *,
    scenario_content: dict[str, Any],
    env_variables: dict[str, str],
    dependency_files: list[DependencyFile],
    jmeter_path: str,
    jmeter_version: str,
) -> str:
    document = build_debug_taurus_document_from_content(
        scenario_content=scenario_content,
        env_variables=env_variables,
        dependency_files=dependency_files,
        jmeter_path=jmeter_path,
        jmeter_version=jmeter_version,
    )
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=False)


def build_debug_taurus_document(
    *,
    scenario: Scenario,
    env_variables: dict[str, str],
    dependency_files: list[DependencyFile],
    jmeter_path: str,
    jmeter_version: str,
) -> dict[str, Any]:
    content = {
        "name": scenario.name,
        "baseUrlExpression": scenario.base_url_expression,
        "defaultSettings": scenario.default_settings_json,
        "dataSources": scenario.data_sources_json,
        "steps": scenario.steps_json,
    }
    return build_debug_taurus_document_from_content(
        scenario_content=content,
        env_variables=env_variables,
        dependency_files=dependency_files,
        jmeter_path=jmeter_path,
        jmeter_version=jmeter_version,
    )


def build_debug_taurus_yaml(
    *,
    scenario: Scenario,
    env_variables: dict[str, str],
    dependency_files: list[DependencyFile],
    jmeter_path: str,
    jmeter_version: str,
) -> str:
    document = build_debug_taurus_document(
        scenario=scenario,
        env_variables=env_variables,
        dependency_files=dependency_files,
        jmeter_path=jmeter_path,
        jmeter_version=jmeter_version,
    )
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=False)
