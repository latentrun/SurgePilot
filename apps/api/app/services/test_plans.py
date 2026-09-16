from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
import re
from typing import Any

import yaml
from fastapi import Request
from pydantic import ValidationError
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.ids import is_ulid, new_ulid
from app.core.time import utc_now
from app.models.auth import User
from app.models.dependency_files import DependencyFile
from app.models.env_groups import EnvGroup
from app.services.env_groups import env_group_runtime_values, internal_env_values
from app.models.load_nodes import LoadNode
from app.models.runs import Run
from app.models.scenarios import RunCreationDedupKey, Scenario, ScenarioDependencyFileRef
from app.models.test_plans import TestPlan, TestPlanScenarioItem, TestPlanSlaRule
from app.schemas.common import ExecutionPreviewResponse, ExecutionPreviewWarning
from app.schemas.test_plans import TestPlanCreateRequest
from app.services.audit import write_audit_event
from app.services.load_nodes import visible_node_filters
from app.services.runs import RunExecutionInput, create_run_execution
from app.services.system_settings import (
    EffectiveLoadSettings,
    effective_load_settings,
    jmeter_memory_xmx,
)
from app.services.scenarios import (
    ACTIVE_RUN_STATES,
    DEFAULT_DEDUP_WINDOW_SECONDS,
    _enabled_dependency_files,
    _scenario_snapshot,
    build_debug_taurus_document_from_content,
    field_error,
    invalid_preview_mode,
    PREVIEW_RUNNER_HOME,
    RUNTIME_JMETER_VERSION,
    runtime_jmeter_path,
    request_label,
    safe_preview_yaml,
    taurus_modules,
    taurus_settings,
    validation_error,
)

RC_SUBJECT_PATTERN = re.compile(r"^rc(?:\d{3}|\d\?\?|\*)$")
DURATION_SUBJECTS = {"avg_rt", "p90", "p95", "p99"}
PERCENT_SUBJECTS = {"fail", "succ"}
COUNT_SUBJECTS = {"hits"}
BYTE_SUBJECTS = {"bytes"}
ACTIVE_RUN_STATES_LIST = list(ACTIVE_RUN_STATES)


LoadSettings = Settings | EffectiveLoadSettings


@dataclass(frozen=True)
class TestPlanRunResult:
    run: Run
    deduplicated: bool
    status_code: int


@dataclass(frozen=True)
class ValidatedPlanContext:
    test_plan: TestPlan
    env_group: EnvGroup | None
    node: LoadNode | None
    scenario_rows: dict[str, Scenario]
    scenario_taurus_docs: dict[str, dict[str, Any]]
    dependency_files: list[dict[str, Any]]
    enabled_items: list[TestPlanScenarioItem]
    expected_concurrency: int
    standard_load_settings_by_item_id: dict[str, dict[str, Any]]
    debug_load_settings_by_item_id: dict[str, dict[str, Any]]
    jmeter_memory_xmx: str


def _resource_value(resource_request: object, snake_name: str, camel_name: str) -> Any:
    if isinstance(resource_request, dict):
        return resource_request.get(camel_name, resource_request.get(snake_name))
    return getattr(resource_request, snake_name, None)


def _normalize_resource_request_override(resource_request: object | None) -> dict[str, Any] | None:
    if resource_request is None:
        return None
    mode = _resource_value(resource_request, "mode", "mode")
    selected_node_ids = list(
        _resource_value(resource_request, "selected_node_ids", "selectedNodeIds") or []
    )
    node_count = _resource_value(resource_request, "node_count", "nodeCount")
    pool_type = _resource_value(resource_request, "pool_type", "poolType")
    concurrency_per_node = _resource_value(
        resource_request, "concurrency_per_node", "concurrencyPerNode"
    )
    if mode not in {"manual", "auto"}:
        raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
    if pool_type not in {None, "public", "private"}:
        raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
    if mode == "manual":
        if node_count is not None or not selected_node_ids:
            raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
        if len(set(selected_node_ids)) != len(selected_node_ids):
            raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
    if mode == "auto":
        if selected_node_ids or not isinstance(node_count, int) or node_count <= 0:
            raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
    return {
        "mode": mode,
        "selectedNodeIds": selected_node_ids,
        "selectedNodeId": selected_node_ids[0] if selected_node_ids else None,
        "nodeCount": node_count if mode == "auto" else None,
        "poolType": pool_type,
        "concurrencyPerNode": concurrency_per_node,
    }


def _apply_resource_request_override(
    snapshot_payload: dict[str, Any], *, run_type: str, resource_request: object | None
) -> dict[str, Any]:
    override = _normalize_resource_request_override(resource_request)
    resource = dict(snapshot_payload.get("resourceRequest") or {})
    if override is None:
        return resource
    if run_type != "standard":
        raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
    resource["mode"] = override["mode"]
    resource["selectedNodeIds"] = override["selectedNodeIds"]
    resource["selectedNodeId"] = override["selectedNodeId"]
    resource["nodeCount"] = override["nodeCount"]
    if override.get("poolType") is not None:
        resource["poolType"] = override["poolType"]
    if override["concurrencyPerNode"] is not None:
        resource["expectedConcurrencyPerNode"] = override["concurrencyPerNode"]
    snapshot_payload["resourceRequest"] = resource
    return resource


def iso_z(value) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _num(value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    return value


def _canonical_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    details: list[dict[str, str]] = []
    for index, tag in enumerate(tags):
        value = str(tag).strip()
        if not value or len(value) > 32:
            details.append(
                field_error(f"tags[{index}]", "Tag must be 1-32 characters.", "invalid_tag")
            )
            continue
        if value not in normalized:
            normalized.append(value)
    if details:
        raise validation_error(details)
    return normalized


def _pydantic_create_payload(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return TestPlanCreateRequest.model_validate(payload).model_dump(by_alias=True, mode="json")
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


def _load_settings_dict(item: TestPlanScenarioItem) -> dict[str, Any]:
    return {
        "concurrencyPerNode": item.concurrency_per_node,
        "rampUpSeconds": item.ramp_up_seconds,
        "holdForSeconds": item.hold_for_seconds,
        "iterations": item.iterations,
        "targetRps": _num(item.target_rps),
        "steps": item.steps,
        "delaySeconds": item.delay_seconds,
    }


def _load_settings_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "concurrencyPerNode": payload.get("concurrencyPerNode", 1),
        "rampUpSeconds": payload.get("rampUpSeconds", 0),
        "holdForSeconds": payload.get("holdForSeconds"),
        "iterations": payload.get("iterations"),
        "targetRps": payload.get("targetRps"),
        "steps": payload.get("steps"),
        "delaySeconds": payload.get("delaySeconds", 0),
    }


def debug_load_settings() -> dict[str, Any]:
    return {
        "concurrencyPerNode": 1,
        "rampUpSeconds": 0,
        "holdForSeconds": None,
        "iterations": 1,
        "targetRps": None,
        "steps": None,
        "delaySeconds": 0,
    }


def expected_concurrency_per_node(run_mode: str, items: list[dict[str, Any]]) -> int:
    enabled = [item for item in items if item.get("enabled", True)]
    if not enabled:
        return 0
    values = [int(item["loadSettings"]["concurrencyPerNode"]) for item in enabled]
    if run_mode == "parallel":
        return sum(values)
    return max(values)


def _expected_concurrency_for_rows(run_mode: str, rows: list[TestPlanScenarioItem]) -> int:
    return expected_concurrency_per_node(
        run_mode,
        [{"enabled": row.enabled, "loadSettings": _load_settings_dict(row)} for row in rows],
    )


def sla_condition_symbol(condition: str) -> str:
    return {"gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "eq": "="}[condition]


def _format_number(value: Any) -> str:
    decimal = Decimal(str(value))
    if decimal == decimal.to_integral_value():
        return str(int(decimal))
    return format(decimal.normalize(), "f")


def _format_count_value(value: Any) -> int | float:
    decimal = Decimal(str(value))
    if decimal == decimal.to_integral_value():
        return int(decimal)
    return float(decimal)


def sla_threshold_text(threshold: dict[str, Any]) -> str | int | float:
    value = _format_number(threshold["value"])
    unit = threshold["unit"]
    if unit == "percent":
        return f"{value}%"
    if unit == "count":
        return _format_count_value(threshold["value"])
    if unit == "b":
        return f"{value}B"
    if unit == "kb":
        return f"{value}kB"
    if unit == "mb":
        return f"{value}MB"
    return f"{value}{unit}"


def _sla_threshold(rule: TestPlanSlaRule) -> dict[str, Any]:
    return {"value": _num(rule.threshold_value), "unit": rule.threshold_unit}


def _sla_rule_dict(rule: TestPlanSlaRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "enabled": rule.enabled,
        "subject": rule.subject,
        "label": rule.label,
        "condition": rule.condition,
        "threshold": _sla_threshold(rule),
        "timeframeLogic": rule.timeframe_logic,
        "timeframeSeconds": rule.timeframe_seconds,
        "action": rule.action,
    }


def _validate_load_settings(
    settings_payload: dict[str, Any], *, field_prefix: str, settings: LoadSettings
) -> None:
    details: list[dict[str, str]] = []
    concurrency = int(settings_payload["concurrencyPerNode"])
    ramp = int(settings_payload["rampUpSeconds"])
    hold = settings_payload.get("holdForSeconds")
    iterations = settings_payload.get("iterations")
    target_rps = settings_payload.get("targetRps")
    steps = settings_payload.get("steps")
    delay = int(settings_payload["delaySeconds"])
    if concurrency > settings.single_node_concurrency_hard_limit:
        details.append(
            field_error(
                f"{field_prefix}.concurrencyPerNode",
                "Concurrency exceeds the hard single-node limit.",
                "single_node_concurrency_hard_limit",
            )
        )
    if ramp > settings.max_ramp_up_seconds:
        details.append(
            field_error(f"{field_prefix}.rampUpSeconds", "Ramp-up is too long.", "max_ramp_up")
        )
    if delay > settings.max_delay_seconds:
        details.append(
            field_error(f"{field_prefix}.delaySeconds", "Delay is too long.", "max_delay")
        )
    if hold is not None and int(hold) > settings.max_run_duration_seconds:
        details.append(
            field_error(f"{field_prefix}.holdForSeconds", "Hold-for is too long.", "max_duration")
        )
    if iterations is not None and int(iterations) > settings.max_iterations:
        details.append(
            field_error(f"{field_prefix}.iterations", "Iterations is too high.", "max_iterations")
        )
    if target_rps is not None and float(target_rps) > settings.max_target_rps:
        details.append(
            field_error(f"{field_prefix}.targetRps", "Target RPS is too high.", "max_target_rps")
        )
    if (hold is None) == (iterations is None):
        details.append(
            field_error(
                field_prefix,
                "Exactly one termination mode is required: hold-for or iterations.",
                "termination_mode_required",
            )
        )
    if steps is not None and ramp <= 0:
        details.append(
            field_error(f"{field_prefix}.steps", "Steps require ramp-up.", "steps_require_ramp_up")
        )
    if target_rps is not None and hold is None:
        details.append(
            field_error(
                f"{field_prefix}.targetRps",
                "Target RPS requires a duration-based run.",
                "target_rps_requires_duration",
            )
        )
    if details:
        raise validation_error(details)


def _subject_allowed(subject: str) -> bool:
    return (
        subject in DURATION_SUBJECTS
        or subject in PERCENT_SUBJECTS
        or subject in COUNT_SUBJECTS
        or subject in BYTE_SUBJECTS
        or bool(RC_SUBJECT_PATTERN.fullmatch(subject))
    )


def _validate_sla_rule(rule: dict[str, Any], *, field_prefix: str) -> None:
    subject = str(rule["subject"]).lower()
    unit = rule["threshold"]["unit"]
    details: list[dict[str, str]] = []
    if not _subject_allowed(subject):
        details.append(
            field_error(
                f"{field_prefix}.subject", "SLA subject is not supported.", "unsupported_subject"
            )
        )
    elif subject in DURATION_SUBJECTS and unit not in {"ms", "s"}:
        details.append(
            field_error(
                f"{field_prefix}.threshold.unit", "Duration SLA requires ms or s.", "invalid_unit"
            )
        )
    elif subject in PERCENT_SUBJECTS and unit != "percent":
        details.append(
            field_error(
                f"{field_prefix}.threshold.unit", "Percentage SLA requires percent.", "invalid_unit"
            )
        )
    elif subject in COUNT_SUBJECTS and unit != "count":
        details.append(
            field_error(
                f"{field_prefix}.threshold.unit", "Hits SLA requires count.", "invalid_unit"
            )
        )
    elif subject in BYTE_SUBJECTS and unit not in {"b", "kb", "mb"}:
        details.append(
            field_error(
                f"{field_prefix}.threshold.unit", "Bytes SLA requires a byte unit.", "invalid_unit"
            )
        )
    elif subject.startswith("rc") and unit not in {"percent", "count"}:
        details.append(
            field_error(
                f"{field_prefix}.threshold.unit",
                "Response-code SLA requires percent or count.",
                "invalid_unit",
            )
        )
    if details:
        raise validation_error(details)


def _validate_unique_child_ids(payload: dict[str, Any]) -> None:
    details: list[dict[str, str]] = []
    child_specs = (
        (
            "scenarioItems",
            "Scenario item ID must be unique within the Test Plan.",
        ),
        (
            "slaRules",
            "SLA Rule ID must be unique within the Test Plan.",
        ),
    )
    for field_name, message in child_specs:
        seen: set[str] = set()
        for index, item in enumerate(payload.get(field_name, [])):
            child_id = item.get("id")
            if child_id is None:
                continue
            if child_id in seen:
                details.append(
                    field_error(f"{field_name}[{index}].id", message, "duplicate_child_id")
                )
            seen.add(child_id)
    if details:
        raise validation_error(details)


def _normalize_plan_children(payload: dict[str, Any]) -> None:
    scenario_items = [dict(item) for item in payload.get("scenarioItems", [])]
    for item in scenario_items:
        item["id"] = item.get("id") or new_ulid()
    payload["scenarioItems"] = scenario_items

    sla_rules = [dict(rule) for rule in payload.get("slaRules", [])]
    for rule in sla_rules:
        label = rule.get("label")
        rule["label"] = label.strip() or None if isinstance(label, str) else None
    payload["slaRules"] = sla_rules


def _generated_sampler_labels(payload: dict[str, Any], scenarios: dict[str, Scenario]) -> set[str]:
    labels: set[str] = set()
    for item in payload.get("scenarioItems", []):
        if not item.get("enabled", True):
            continue
        scenario = scenarios.get(item["scenarioId"])
        if scenario is None:
            continue
        for step in scenario.steps_json or []:
            if not step.get("enabled", True):
                continue
            labels.add(
                request_label(
                    step["method"],
                    step["path"],
                    step["id"],
                    item_id=item["id"],
                )
            )
    return labels


def _validate_sla_rule_labels(rules: list[dict[str, Any]], allowed_labels: set[str]) -> None:
    details = [
        field_error(
            f"slaRules[{index}].label",
            "SLA Rule label must match a generated sampler label.",
            "unknown_sampler_label",
        )
        for index, rule in enumerate(rules)
        if rule.get("enabled", True) and rule.get("label") and rule["label"] not in allowed_labels
    ]
    if details:
        raise validation_error(details)


def _validate_payload_references(
    db: Session, *, workspace_id: str, payload: dict[str, Any], settings: LoadSettings
) -> None:
    _normalize_plan_children(payload)
    _validate_unique_child_ids(payload)
    if payload.get("envGroupId") is not None:
        env_group = db.scalar(
            select(EnvGroup).where(
                EnvGroup.id == payload["envGroupId"], EnvGroup.workspace_id == workspace_id
            )
        )
        if env_group is None:
            raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    resource = payload.get("resource") or {}
    mode = resource.get("mode") or "manual"
    pool_type = resource.get("poolType")
    selected_ids = list(
        resource.get("selectedNodeIds")
        or ([resource.get("selectedNodeId")] if resource.get("selectedNodeId") else [])
    )
    if mode == "manual" and resource.get("nodeCount") is not None:
        raise validation_error(
            [
                field_error(
                    "resource.nodeCount",
                    "Manual resource mode must not include node count.",
                    "conflicting_field",
                )
            ]
        )
    if mode == "auto" and selected_ids:
        raise validation_error(
            [
                field_error(
                    "resource.selectedNodeIds",
                    "Auto resource mode must not include selected nodes.",
                    "conflicting_field",
                )
            ]
        )
    if mode == "manual" and (
        any(not isinstance(node_id, str) or not is_ulid(node_id) for node_id in selected_ids)
        or len(set(selected_ids)) != len(selected_ids)
    ):
        raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
    if mode == "manual" and selected_ids:
        if pool_type is None:
            raise validation_error(
                [
                    field_error(
                        "resource.poolType",
                        "Pool type is required when a node is selected.",
                        "required_field",
                    )
                ]
            )
        nodes = db.scalars(
            select(LoadNode).where(
                LoadNode.id.in_(selected_ids),
                LoadNode.archived_at.is_(None),
            )
        ).all()
        by_id = {node.id: node for node in nodes}
        for selected_id in selected_ids:
            node = by_id.get(selected_id)
            if node is None:
                raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
            if pool_type == "public" and node.scope != "public":
                raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
            if pool_type == "private" and not (
                node.scope == "workspace" and node.workspace_id == workspace_id
            ):
                raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    scenario_ids = [item["scenarioId"] for item in payload.get("scenarioItems", [])]
    scenarios: dict[str, Scenario] = {}
    if scenario_ids:
        rows = db.scalars(
            select(Scenario).where(
                Scenario.id.in_(scenario_ids),
                Scenario.workspace_id == workspace_id,
                Scenario.deleted_at.is_(None),
                Scenario.scenario_type == "visual",
            )
        ).all()
        found = {row.id for row in rows}
        if any(scenario_id not in found for scenario_id in scenario_ids):
            raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
        scenarios = {row.id: row for row in rows}
    enabled_scenario_count = sum(
        1 for item in payload.get("scenarioItems", []) if item.get("enabled", True)
    )
    if enabled_scenario_count > settings.max_scenario_items_per_test_plan:
        raise validation_error(
            [field_error("scenarioItems", "Too many enabled Scenario items.", "too_many_scenarios")]
        )
    enabled_sla_count = 0
    for index, rule in enumerate(payload.get("slaRules", [])):
        if rule.get("enabled", True):
            enabled_sla_count += 1
            _validate_sla_rule(rule, field_prefix=f"slaRules[{index}]")
    if enabled_sla_count > settings.max_sla_rules_per_test_plan:
        raise validation_error(
            [field_error("slaRules", "Too many enabled SLA Rules.", "too_many_sla_rules")]
        )
    _validate_sla_rule_labels(
        payload.get("slaRules", []), _generated_sampler_labels(payload, scenarios)
    )
    for index, item in enumerate(payload.get("scenarioItems", [])):
        load_settings = _load_settings_from_payload(item.get("loadSettings") or {})
        if item.get("enabled", True):
            _validate_load_settings(
                load_settings,
                field_prefix=f"scenarioItems[{index}].loadSettings",
                settings=settings,
            )


def _replace_children(db: Session, *, plan: TestPlan, payload: dict[str, Any], now) -> None:
    db.query(TestPlanScenarioItem).filter(TestPlanScenarioItem.test_plan_id == plan.id).delete(
        synchronize_session=False
    )
    db.query(TestPlanSlaRule).filter(TestPlanSlaRule.test_plan_id == plan.id).delete(
        synchronize_session=False
    )
    ordered_items = sorted(payload.get("scenarioItems", []), key=lambda item: item.get("order", 0))
    for position, item in enumerate(ordered_items):
        settings_payload = _load_settings_from_payload(item.get("loadSettings") or {})
        db.add(
            TestPlanScenarioItem(
                id=item.get("id") or new_ulid(),
                workspace_id=plan.workspace_id,
                test_plan_id=plan.id,
                scenario_id=item["scenarioId"],
                enabled=item.get("enabled", True),
                position=position,
                concurrency_per_node=settings_payload["concurrencyPerNode"],
                ramp_up_seconds=settings_payload["rampUpSeconds"],
                hold_for_seconds=settings_payload.get("holdForSeconds"),
                iterations=settings_payload.get("iterations"),
                target_rps=settings_payload.get("targetRps"),
                steps=settings_payload.get("steps"),
                delay_seconds=settings_payload["delaySeconds"],
                created_at=now,
                updated_at=now,
            )
        )
    for position, rule in enumerate(payload.get("slaRules", [])):
        threshold = rule["threshold"]
        db.add(
            TestPlanSlaRule(
                id=rule.get("id") or new_ulid(),
                workspace_id=plan.workspace_id,
                test_plan_id=plan.id,
                enabled=rule.get("enabled", True),
                position=position,
                subject=str(rule["subject"]).lower(),
                label=(rule.get("label") or None),
                condition=rule["condition"],
                threshold_value=threshold["value"],
                threshold_unit=threshold["unit"],
                timeframe_logic=rule.get("timeframeLogic"),
                timeframe_seconds=rule.get("timeframeSeconds"),
                action=rule.get("action", "continue"),
                created_at=now,
                updated_at=now,
            )
        )


def create_test_plan(
    db: Session, *, workspace_id: str, actor: User, payload: dict[str, Any]
) -> TestPlan:
    settings = effective_load_settings(db)
    payload = dict(payload)
    payload["tags"] = _normalize_tags(payload.get("tags") or [])
    _validate_payload_references(db, workspace_id=workspace_id, payload=payload, settings=settings)
    now = utc_now()
    resource = payload.get("resource") or {}
    plan = TestPlan(
        id=new_ulid(),
        workspace_id=workspace_id,
        name=payload["name"].strip(),
        description=payload.get("description"),
        tags_json=payload["tags"],
        env_group_id=payload.get("envGroupId"),
        run_mode=payload.get("runMode") or "sequential",
        pool_type=resource.get("poolType"),
        selected_node_id=resource.get("selectedNodeId")
        or (resource.get("selectedNodeIds") or [None])[0],
        resource_mode=resource.get("mode") or "manual",
        selected_node_ids_json=resource.get("selectedNodeIds")
        or ([resource.get("selectedNodeId")] if resource.get("selectedNodeId") else []),
        node_count=resource.get("nodeCount"),
        revision=1,
        created_by=actor.id,
        updated_by=actor.id,
        created_at=now,
        updated_at=now,
    )
    db.add(plan)
    db.flush()
    _replace_children(db, plan=plan, payload=payload, now=now)
    db.flush()
    return plan


def clone_test_plan(
    db: Session, *, workspace_id: str, test_plan_id: str, actor: User, name: str | None
) -> TestPlan:
    source = get_test_plan(db, workspace_id=workspace_id, test_plan_id=test_plan_id)
    items, rules = _rows_for_plan(db, plan_id=source.id)
    payload = {
        "name": name or f"Copy of {source.name}",
        "description": source.description,
        "tags": list(source.tags_json or []),
        "envGroupId": source.env_group_id,
        "runMode": source.run_mode,
        "resource": {
            "mode": source.resource_mode,
            "poolType": source.pool_type,
            "selectedNodeId": source.selected_node_id,
            "selectedNodeIds": list(source.selected_node_ids_json or []),
            "nodeCount": source.node_count,
        },
        "scenarioItems": [
            {
                "id": new_ulid(),
                "scenarioId": item.scenario_id,
                "enabled": item.enabled,
                "order": item.position,
                "loadSettings": _load_settings_dict(item),
            }
            for item in items
        ],
        "slaRules": [
            {
                **_sla_rule_dict(rule),
                "id": new_ulid(),
            }
            for rule in rules
        ],
    }
    settings = effective_load_settings(db)
    payload = _pydantic_create_payload(payload)
    payload["tags"] = _normalize_tags(payload.get("tags") or [])
    _validate_payload_references(db, workspace_id=workspace_id, payload=payload, settings=settings)
    now = utc_now()
    resource = payload["resource"]
    clone = TestPlan(
        id=new_ulid(),
        workspace_id=workspace_id,
        name=payload["name"].strip(),
        description=payload.get("description"),
        tags_json=payload["tags"],
        env_group_id=payload.get("envGroupId"),
        run_mode=payload.get("runMode") or "sequential",
        pool_type=resource.get("poolType"),
        selected_node_id=resource.get("selectedNodeId")
        or (resource.get("selectedNodeIds") or [None])[0],
        resource_mode=resource.get("mode") or "manual",
        selected_node_ids_json=resource.get("selectedNodeIds")
        or ([resource.get("selectedNodeId")] if resource.get("selectedNodeId") else []),
        node_count=resource.get("nodeCount"),
        revision=1,
        created_by=actor.id,
        updated_by=actor.id,
        deleted_by=None,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.add(clone)
    db.flush()
    _replace_children(db, plan=clone, payload=payload, now=now)
    db.flush()
    return clone


def get_test_plan(db: Session, *, workspace_id: str, test_plan_id: str) -> TestPlan:
    plan = db.scalar(
        select(TestPlan).where(
            TestPlan.id == test_plan_id,
            TestPlan.workspace_id == workspace_id,
            TestPlan.deleted_at.is_(None),
        )
    )
    if plan is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    return plan


def patch_test_plan(
    db: Session,
    *,
    plan: TestPlan,
    actor: User,
    expected_revision: int,
    payload: dict[str, Any],
) -> TestPlan:
    locked = db.scalar(
        select(TestPlan)
        .where(
            TestPlan.id == plan.id,
            TestPlan.workspace_id == plan.workspace_id,
            TestPlan.deleted_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    if locked.revision != expected_revision:
        raise AppError(
            "TEST_PLAN_REVISION_CONFLICT",
            "Test Plan was updated by another request. Reload and try again.",
            409,
        )
    settings = effective_load_settings(db)
    payload = dict(payload)
    payload["tags"] = _normalize_tags(payload.get("tags") or [])
    _validate_payload_references(
        db, workspace_id=locked.workspace_id, payload=payload, settings=settings
    )
    now = utc_now()
    resource = payload.get("resource") or {}
    locked.name = payload["name"].strip()
    locked.description = payload.get("description")
    locked.tags_json = payload["tags"]
    locked.env_group_id = payload.get("envGroupId")
    locked.run_mode = payload.get("runMode") or "sequential"
    locked.pool_type = resource.get("poolType")
    locked.resource_mode = resource.get("mode") or "manual"
    locked.selected_node_ids_json = resource.get("selectedNodeIds") or (
        [resource.get("selectedNodeId")] if resource.get("selectedNodeId") else []
    )
    locked.node_count = resource.get("nodeCount")
    locked.selected_node_id = resource.get("selectedNodeId") or (
        locked.selected_node_ids_json[0] if locked.selected_node_ids_json else None
    )
    locked.revision += 1
    locked.updated_by = actor.id
    locked.updated_at = now
    _replace_children(db, plan=locked, payload=payload, now=now)
    db.flush()
    return locked


def list_test_plans(
    db: Session,
    *,
    workspace_id: str,
    page: int,
    page_size: int,
    search: str | None,
    tag: str | None,
    sort: str,
) -> tuple[list[TestPlan], int]:
    statement = select(TestPlan).where(
        TestPlan.workspace_id == workspace_id, TestPlan.deleted_at.is_(None)
    )
    count_statement = select(func.count(TestPlan.id)).where(
        TestPlan.workspace_id == workspace_id, TestPlan.deleted_at.is_(None)
    )
    if search:
        pattern = f"%{search.lower()}%"
        statement = statement.where(func.lower(TestPlan.name).like(pattern))
        count_statement = count_statement.where(func.lower(TestPlan.name).like(pattern))
    if sort == "updatedAt":
        statement = statement.order_by(TestPlan.updated_at.asc(), TestPlan.id.asc())
    elif sort == "name":
        statement = statement.order_by(func.lower(TestPlan.name).asc(), TestPlan.id.asc())
    elif sort == "-name":
        statement = statement.order_by(func.lower(TestPlan.name).desc(), TestPlan.id.desc())
    else:
        statement = statement.order_by(TestPlan.updated_at.desc(), TestPlan.id.desc())
    if tag:
        rows = [plan for plan in db.scalars(statement) if tag in (plan.tags_json or [])]
        total = len(rows)
        start = (page - 1) * page_size
        return rows[start : start + page_size], total
    total = db.scalar(count_statement) or 0
    rows = list(db.scalars(statement.offset((page - 1) * page_size).limit(page_size)))
    return rows, total


def _rows_for_plan(
    db: Session, *, plan_id: str
) -> tuple[list[TestPlanScenarioItem], list[TestPlanSlaRule]]:
    items = list(
        db.scalars(
            select(TestPlanScenarioItem)
            .where(TestPlanScenarioItem.test_plan_id == plan_id)
            .order_by(TestPlanScenarioItem.position.asc(), TestPlanScenarioItem.id.asc())
        )
    )
    rules = list(
        db.scalars(
            select(TestPlanSlaRule)
            .where(TestPlanSlaRule.test_plan_id == plan_id)
            .order_by(TestPlanSlaRule.position.asc(), TestPlanSlaRule.id.asc())
        )
    )
    return items, rules


def _scenario_map(
    db: Session, *, workspace_id: str, items: list[TestPlanScenarioItem]
) -> dict[str, Scenario]:
    ids = sorted({item.scenario_id for item in items})
    if not ids:
        return {}
    rows = db.scalars(
        select(Scenario).where(
            Scenario.id.in_(ids),
            Scenario.workspace_id == workspace_id,
            Scenario.deleted_at.is_(None),
        )
    ).all()
    return {row.id: row for row in rows}


def _node_for_plan(db: Session, plan: TestPlan) -> LoadNode | None:
    if plan.selected_node_id is None:
        return None
    return db.get(LoadNode, plan.selected_node_id)


def _resource_pool_condition(*, workspace_id: str, pool_type: str | None):
    if pool_type == "public":
        return LoadNode.scope == "public"
    if pool_type == "private":
        return and_(LoadNode.scope == "workspace", LoadNode.workspace_id == workspace_id)
    return visible_node_filters(workspace_id=workspace_id)


def _visible_nodes_for_pool(
    db: Session, *, workspace_id: str, pool_type: str | None, node_ids: list[str]
) -> dict[str, LoadNode]:
    if not node_ids:
        return {}
    nodes = db.scalars(
        select(LoadNode).where(
            LoadNode.id.in_(node_ids),
            LoadNode.archived_at.is_(None),
            visible_node_filters(workspace_id=workspace_id),
            _resource_pool_condition(workspace_id=workspace_id, pool_type=pool_type),
        )
    ).all()
    return {node.id: node for node in nodes}


def _auto_idle_capacity(db: Session, plan: TestPlan) -> int:
    return int(
        db.scalar(
            select(func.count(LoadNode.id)).where(
                LoadNode.archived_at.is_(None),
                LoadNode.status == "idle",
                LoadNode.runtime_version == (get_settings().load_node_runtime_version or ""),
                visible_node_filters(workspace_id=plan.workspace_id),
                _resource_pool_condition(workspace_id=plan.workspace_id, pool_type=plan.pool_type),
            )
        )
        or 0
    )


def _batch_auto_idle_capacity(
    db: Session,
    *,
    workspace_id: str,
    pool_types: set[str | None],
    runtime_version: str,
) -> dict[str | None, int]:
    capacities: dict[str | None, int] = {}
    for pool_type in pool_types:
        capacities[pool_type] = int(
            db.scalar(
                select(func.count(LoadNode.id)).where(
                    LoadNode.archived_at.is_(None),
                    LoadNode.status == "idle",
                    LoadNode.runtime_version == runtime_version,
                    visible_node_filters(workspace_id=workspace_id),
                    _resource_pool_condition(workspace_id=workspace_id, pool_type=pool_type),
                )
            )
            or 0
        )
    return capacities


def _env_for_plan(db: Session, plan: TestPlan) -> EnvGroup | None:
    if plan.env_group_id is None:
        return None
    return db.scalar(
        select(EnvGroup).where(
            EnvGroup.id == plan.env_group_id, EnvGroup.workspace_id == plan.workspace_id
        )
    )


@dataclass(frozen=True)
class _TestPlanListBatchData:
    items_by_plan_id: dict[str, list[TestPlanScenarioItem]]
    rules_by_plan_id: dict[str, list[TestPlanSlaRule]]
    scenarios: dict[str, Scenario]
    env_groups: dict[str, EnvGroup]
    nodes: dict[str, LoadNode]
    updated_by_users: dict[str, User]
    dependency_files_by_scenario_id: dict[str, list[DependencyFile]]
    auto_idle_capacity_by_pool_type: dict[str | None, int]
    effective_settings: EffectiveLoadSettings
    runtime_settings: Settings
    jmeter_memory_xmx: str


def _rows_for_plan_ids(
    db: Session, *, plan_ids: list[str]
) -> tuple[dict[str, list[TestPlanScenarioItem]], dict[str, list[TestPlanSlaRule]]]:
    items_by_plan_id: dict[str, list[TestPlanScenarioItem]] = {plan_id: [] for plan_id in plan_ids}
    rules_by_plan_id: dict[str, list[TestPlanSlaRule]] = {plan_id: [] for plan_id in plan_ids}
    if not plan_ids:
        return items_by_plan_id, rules_by_plan_id
    items = db.scalars(
        select(TestPlanScenarioItem)
        .where(TestPlanScenarioItem.test_plan_id.in_(plan_ids))
        .order_by(
            TestPlanScenarioItem.test_plan_id.asc(),
            TestPlanScenarioItem.position.asc(),
            TestPlanScenarioItem.id.asc(),
        )
    ).all()
    for item in items:
        items_by_plan_id.setdefault(item.test_plan_id, []).append(item)
    rules = db.scalars(
        select(TestPlanSlaRule)
        .where(TestPlanSlaRule.test_plan_id.in_(plan_ids))
        .order_by(
            TestPlanSlaRule.test_plan_id.asc(),
            TestPlanSlaRule.position.asc(),
            TestPlanSlaRule.id.asc(),
        )
    ).all()
    for rule in rules:
        rules_by_plan_id.setdefault(rule.test_plan_id, []).append(rule)
    return items_by_plan_id, rules_by_plan_id


def _dependency_files_by_scenario_ids(
    db: Session, *, workspace_id: str, scenario_ids: set[str]
) -> dict[str, list[DependencyFile]]:
    dependency_files_by_scenario_id: dict[str, list[DependencyFile]] = {
        scenario_id: [] for scenario_id in scenario_ids
    }
    if not scenario_ids:
        return dependency_files_by_scenario_id
    rows = db.execute(
        select(ScenarioDependencyFileRef.scenario_id, DependencyFile)
        .join(DependencyFile, DependencyFile.id == ScenarioDependencyFileRef.dependency_file_id)
        .where(
            ScenarioDependencyFileRef.workspace_id == workspace_id,
            ScenarioDependencyFileRef.scenario_id.in_(scenario_ids),
            DependencyFile.status == "available",
        )
    ).all()
    for scenario_id, dependency_file in rows:
        dependency_files_by_scenario_id.setdefault(scenario_id, []).append(dependency_file)
    return dependency_files_by_scenario_id


def _batch_test_plan_list_data(
    db: Session, *, workspace_id: str, plans: list[TestPlan]
) -> _TestPlanListBatchData:
    plan_ids = [plan.id for plan in plans]
    items_by_plan_id, rules_by_plan_id = _rows_for_plan_ids(db, plan_ids=plan_ids)
    scenario_ids = {
        item.scenario_id for items in items_by_plan_id.values() for item in items if item.enabled
    }
    scenarios = (
        {
            scenario.id: scenario
            for scenario in db.scalars(
                select(Scenario).where(
                    Scenario.id.in_(scenario_ids),
                    Scenario.workspace_id == workspace_id,
                    Scenario.deleted_at.is_(None),
                )
            ).all()
        }
        if scenario_ids
        else {}
    )
    env_ids = sorted({plan.env_group_id for plan in plans if plan.env_group_id})
    env_groups = (
        {
            env_group.id: env_group
            for env_group in db.scalars(
                select(EnvGroup).where(
                    EnvGroup.id.in_(env_ids), EnvGroup.workspace_id == workspace_id
                )
            ).all()
        }
        if env_ids
        else {}
    )
    node_ids = sorted(
        {
            node_id
            for plan in plans
            for node_id in (
                list(plan.selected_node_ids_json or [])
                or ([plan.selected_node_id] if plan.selected_node_id else [])
            )
        }
    )
    nodes = (
        {
            node.id: node
            for node in db.scalars(
                select(LoadNode).where(
                    LoadNode.id.in_(node_ids),
                    visible_node_filters(workspace_id=workspace_id),
                )
            ).all()
        }
        if node_ids
        else {}
    )
    user_ids = sorted({plan.updated_by for plan in plans if plan.updated_by})
    updated_by_users = (
        {user.id: user for user in db.scalars(select(User).where(User.id.in_(user_ids))).all()}
        if user_ids
        else {}
    )
    auto_pool_types = {
        plan.pool_type for plan in plans if plan.resource_mode == "auto" and plan.node_count
    }
    runtime_settings = get_settings()
    return _TestPlanListBatchData(
        items_by_plan_id=items_by_plan_id,
        rules_by_plan_id=rules_by_plan_id,
        scenarios=scenarios,
        env_groups=env_groups,
        nodes=nodes,
        updated_by_users=updated_by_users,
        dependency_files_by_scenario_id=_dependency_files_by_scenario_ids(
            db, workspace_id=workspace_id, scenario_ids=scenario_ids
        ),
        auto_idle_capacity_by_pool_type=_batch_auto_idle_capacity(
            db,
            workspace_id=workspace_id,
            pool_types=auto_pool_types,
            runtime_version=runtime_settings.load_node_runtime_version or "",
        )
        if auto_pool_types
        else {},
        effective_settings=effective_load_settings(db),
        runtime_settings=runtime_settings,
        jmeter_memory_xmx=jmeter_memory_xmx(db),
    )


def _scenario_preflight_reasons(
    db: Session,
    *,
    plan: TestPlan,
    enabled_items: list[TestPlanScenarioItem],
    scenarios: dict[str, Scenario],
    env_group: EnvGroup | None = None,
    node: LoadNode | None = None,
    runtime_settings: Settings | None = None,
    memory_xmx: str | None = None,
    dependency_files_by_scenario_id: dict[str, list[DependencyFile]] | None = None,
) -> list[str]:
    if env_group is None and plan.env_group_id is not None:
        env_group = _env_for_plan(db, plan)
    env_variables = env_group_runtime_values(env_group)
    settings = runtime_settings or get_settings()
    if node is None:
        node = _node_for_plan(db, plan)
    runner_home = node.runner_home if node is not None else settings.load_node_default_runner_home
    active_memory_xmx = memory_xmx or jmeter_memory_xmx(db)
    reasons: list[str] = []
    for item in enabled_items:
        scenario = scenarios.get(item.scenario_id)
        if scenario is None:
            continue
        if dependency_files_by_scenario_id is None:
            dependency_models = [
                file for _ref, file in _enabled_dependency_files(db, scenario=scenario)
            ]
        else:
            dependency_models = dependency_files_by_scenario_id.get(scenario.id, [])
        try:
            build_debug_taurus_document_from_content(
                scenario_content=_scenario_content(scenario),
                env_variables=env_variables,
                dependency_files=dependency_models,
                jmeter_path=runtime_jmeter_path(runner_home),
                jmeter_version=RUNTIME_JMETER_VERSION,
                memory_xmx=active_memory_xmx,
            )
        except AppError as exc:
            detail_codes = {
                detail.get("code") for detail in (exc.details or []) if isinstance(detail, dict)
            }
            reason = (
                "missing_variables"
                if "missing_variable" in detail_codes
                else "scenario_not_runnable"
            )
            if reason not in reasons:
                reasons.append(reason)
    return reasons


def not_runnable_reasons(
    db: Session,
    plan: TestPlan,
    items: list[TestPlanScenarioItem] | None = None,
    rules: list[TestPlanSlaRule] | None = None,
    batch: _TestPlanListBatchData | None = None,
) -> list[str]:
    if items is None or rules is None:
        if batch is None:
            loaded_items, loaded_rules = _rows_for_plan(db, plan_id=plan.id)
        else:
            loaded_items = batch.items_by_plan_id.get(plan.id, [])
            loaded_rules = batch.rules_by_plan_id.get(plan.id, [])
        items = loaded_items if items is None else items
        rules = loaded_rules if rules is None else rules
    reasons: list[str] = []
    enabled = [item for item in items if item.enabled]
    enabled_rules = [rule for rule in rules if rule.enabled]
    if not enabled:
        reasons.append("no_enabled_scenarios")
    settings = batch.effective_settings if batch is not None else effective_load_settings(db)
    if len(enabled) > settings.max_scenario_items_per_test_plan:
        reasons.append("too_many_scenarios")
    if len(enabled_rules) > settings.max_sla_rules_per_test_plan:
        reasons.append("too_many_sla_rules")
    if plan.pool_type is None:
        reasons.append("load_node_required")
    elif plan.resource_mode == "manual" and not (
        plan.selected_node_ids_json or ([plan.selected_node_id] if plan.selected_node_id else [])
    ):
        reasons.append("load_node_required")
    elif plan.resource_mode == "auto" and not plan.node_count:
        reasons.append("load_node_required")
    elif plan.resource_mode == "manual":
        node = (
            batch.nodes.get(plan.selected_node_id)
            if batch is not None and plan.selected_node_id is not None
            else _node_for_plan(db, plan)
        )
        if node is None or node.archived_at is not None:
            reasons.append("load_node_unavailable")
        elif plan.pool_type == "public" and node.scope != "public":
            reasons.append("load_node_unavailable")
        elif plan.pool_type == "private" and not (
            node.scope == "workspace" and node.workspace_id == plan.workspace_id
        ):
            reasons.append("load_node_unavailable")
        elif node.status != "idle" or node.runtime_version != (
            (
                batch.runtime_settings if batch is not None else get_settings()
            ).load_node_runtime_version
            or ""
        ):
            reasons.append("load_node_not_idle")
    elif (
        batch.auto_idle_capacity_by_pool_type.get(plan.pool_type)
        if batch is not None
        else _auto_idle_capacity(db, plan)
    ) < int(plan.node_count or 0):
        reasons.append("load_node_capacity_unavailable")
    scenario_rows = (
        {
            item.scenario_id: batch.scenarios[item.scenario_id]
            for item in enabled
            if item.scenario_id in batch.scenarios
        }
        if batch is not None
        else _scenario_map(db, workspace_id=plan.workspace_id, items=enabled)
    )
    if any(item.scenario_id not in scenario_rows for item in enabled):
        reasons.append("scenario_unavailable")
    env_group = (
        batch.env_groups.get(plan.env_group_id)
        if batch is not None and plan.env_group_id is not None
        else _env_for_plan(db, plan)
    )
    if plan.env_group_id is not None and env_group is None:
        reasons.append("env_group_unavailable")
    expected = _expected_concurrency_for_rows(plan.run_mode, enabled)
    if enabled and expected > settings.single_node_concurrency_hard_limit:
        reasons.append("single_node_concurrency_hard_limit")
    if not any(
        reason in reasons
        for reason in {"no_enabled_scenarios", "scenario_unavailable", "env_group_unavailable"}
    ):
        reasons.extend(
            reason
            for reason in _scenario_preflight_reasons(
                db,
                plan=plan,
                enabled_items=enabled,
                scenarios=scenario_rows,
                env_group=env_group,
                node=(
                    batch.nodes.get(plan.selected_node_id)
                    if batch is not None and plan.selected_node_id is not None
                    else None
                ),
                runtime_settings=batch.runtime_settings if batch is not None else None,
                memory_xmx=batch.jmeter_memory_xmx if batch is not None else None,
                dependency_files_by_scenario_id=(
                    batch.dependency_files_by_scenario_id if batch is not None else None
                ),
            )
            if reason not in reasons
        )
    return reasons


def _guard(db: Session, plan: TestPlan, items: list[TestPlanScenarioItem]) -> dict[str, Any]:
    settings = effective_load_settings(db)
    expected = _expected_concurrency_for_rows(plan.run_mode, items)
    return {
        "expectedConcurrencyPerNode": expected,
        "softConcurrencyPerNodeLimit": settings.single_node_concurrency_soft_limit,
        "hardConcurrencyPerNodeLimit": settings.single_node_concurrency_hard_limit,
        "requiresHighConcurrencyConfirmation": expected
        > settings.single_node_concurrency_soft_limit,
    }


def detail_payload(db: Session, plan: TestPlan) -> dict[str, Any]:
    items, rules = _rows_for_plan(db, plan_id=plan.id)
    scenarios = _scenario_map(db, workspace_id=plan.workspace_id, items=items)
    reasons = not_runnable_reasons(db, plan, items, rules)
    scenario_items = []
    for item in items:
        scenario = scenarios.get(item.scenario_id)
        scenario_items.append(
            {
                "id": item.id,
                "scenarioId": item.scenario_id,
                "scenarioName": scenario.name if scenario else None,
                "scenarioRevision": scenario.revision if scenario else None,
                "enabledStepCount": len(
                    [
                        step
                        for step in (scenario.steps_json if scenario else [])
                        if step.get("enabled", True)
                    ]
                ),
                "updatedAt": iso_z(scenario.updated_at) if scenario else None,
                "enabled": item.enabled,
                "order": item.position,
                "loadSettings": _load_settings_dict(item),
            }
        )
    return {
        "id": plan.id,
        "name": plan.name,
        "description": plan.description,
        "tags": plan.tags_json or [],
        "envGroupId": plan.env_group_id,
        "runMode": plan.run_mode,
        "resource": {
            "mode": plan.resource_mode,
            "poolType": plan.pool_type,
            "selectedNodeId": plan.selected_node_id,
            "selectedNodeIds": list(plan.selected_node_ids_json or []),
            "nodeCount": plan.node_count,
        },
        "scenarioItems": scenario_items,
        "slaRules": [_sla_rule_dict(rule) for rule in rules],
        "runGuard": _guard(db, plan, items),
        "runnable": not reasons,
        "notRunnableReasons": reasons,
        "revision": plan.revision,
        "createdAt": iso_z(plan.created_at),
        "updatedAt": iso_z(plan.updated_at),
    }


def summary_payload(db: Session, plan: TestPlan) -> dict[str, Any]:
    items, rules = _rows_for_plan(db, plan_id=plan.id)
    env = _env_for_plan(db, plan)
    node = _node_for_plan(db, plan)
    reasons = not_runnable_reasons(db, plan, items, rules)
    expected = _expected_concurrency_for_rows(plan.run_mode, items)
    settings = effective_load_settings(db)
    updated_by = db.get(User, plan.updated_by)
    return {
        "id": plan.id,
        "name": plan.name,
        "description": plan.description,
        "tags": plan.tags_json or [],
        "runMode": plan.run_mode,
        "envGroup": {"id": env.id, "name": env.name} if env else None,
        "resource": {
            "mode": plan.resource_mode,
            "poolType": plan.pool_type,
            "selectedNodeId": plan.selected_node_id,
            "selectedNodeIds": list(plan.selected_node_ids_json or []),
            "nodeCount": plan.node_count,
            "selectedNodeName": node.host if node else None,
            "allocatedNodeCount": len(plan.selected_node_ids_json or [])
            if plan.resource_mode == "manual"
            else plan.node_count,
            "selectedNodeStatus": node.status if node else None,
        },
        "scenarioItemCount": len(items),
        "enabledScenarioItemCount": len([item for item in items if item.enabled]),
        "slaRuleCount": len([rule for rule in rules if rule.enabled]),
        "expectedConcurrencyPerNode": expected,
        "requiresHighConcurrencyConfirmation": expected
        > settings.single_node_concurrency_soft_limit,
        "runnable": not reasons,
        "notRunnableReasons": reasons,
        "revision": plan.revision,
        "updatedAt": iso_z(plan.updated_at),
        "updatedBy": {"id": updated_by.id, "displayName": updated_by.display_name}
        if updated_by
        else None,
    }


def summary_payloads(
    db: Session, *, workspace_id: str, plans: list[TestPlan]
) -> list[dict[str, Any]]:
    if not plans:
        return []
    batch = _batch_test_plan_list_data(db, workspace_id=workspace_id, plans=plans)
    payloads: list[dict[str, Any]] = []
    for plan in plans:
        items = batch.items_by_plan_id.get(plan.id, [])
        rules = batch.rules_by_plan_id.get(plan.id, [])
        env = batch.env_groups.get(plan.env_group_id) if plan.env_group_id is not None else None
        node = batch.nodes.get(plan.selected_node_id) if plan.selected_node_id is not None else None
        reasons = not_runnable_reasons(db, plan, items, rules, batch=batch)
        expected = _expected_concurrency_for_rows(plan.run_mode, items)
        updated_by = batch.updated_by_users.get(plan.updated_by)
        payloads.append(
            {
                "id": plan.id,
                "name": plan.name,
                "description": plan.description,
                "tags": plan.tags_json or [],
                "runMode": plan.run_mode,
                "envGroup": {"id": env.id, "name": env.name} if env else None,
                "resource": {
                    "mode": plan.resource_mode,
                    "poolType": plan.pool_type,
                    "selectedNodeId": plan.selected_node_id,
                    "selectedNodeIds": list(plan.selected_node_ids_json or []),
                    "nodeCount": plan.node_count,
                    "selectedNodeName": node.host if node else None,
                    "allocatedNodeCount": len(plan.selected_node_ids_json or [])
                    if plan.resource_mode == "manual"
                    else plan.node_count,
                    "selectedNodeStatus": node.status if node else None,
                },
                "scenarioItemCount": len(items),
                "enabledScenarioItemCount": len([item for item in items if item.enabled]),
                "slaRuleCount": len([rule for rule in rules if rule.enabled]),
                "expectedConcurrencyPerNode": expected,
                "requiresHighConcurrencyConfirmation": expected
                > batch.effective_settings.single_node_concurrency_soft_limit,
                "runnable": not reasons,
                "notRunnableReasons": reasons,
                "revision": plan.revision,
                "updatedAt": iso_z(plan.updated_at),
                "updatedBy": {"id": updated_by.id, "displayName": updated_by.display_name}
                if updated_by
                else None,
            }
        )
    return payloads


def delete_test_plan(db: Session, *, plan: TestPlan, actor: User) -> None:
    locked = db.scalar(
        select(TestPlan)
        .where(
            TestPlan.id == plan.id,
            TestPlan.workspace_id == plan.workspace_id,
            TestPlan.deleted_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    active_run = db.scalar(
        select(Run.id)
        .where(
            Run.workspace_id == locked.workspace_id,
            Run.source_type == "test_plan",
            Run.source_id == locked.id,
            Run.state.in_(ACTIVE_RUN_STATES_LIST),
        )
        .limit(1)
    )
    if active_run is not None:
        raise AppError("RESOURCE_IN_USE", "Resource is in use and cannot be deleted.", 409)
    now = utc_now()
    locked.deleted_at = now
    locked.deleted_by = actor.id
    locked.updated_by = actor.id
    locked.updated_at = now
    db.flush()


def _preview_warning(
    code: str, message: str, *, field: str | None = None, severity: str = "warning"
) -> ExecutionPreviewWarning:
    return ExecutionPreviewWarning(code=code, message=message, field=field, severity=severity)


def get_test_plan_execution_preview(
    db: Session, *, workspace_id: str, test_plan_id: str, run_type: str | None
) -> ExecutionPreviewResponse:
    if run_type not in {"debug", "standard"}:
        raise invalid_preview_mode("runType")
    plan = get_test_plan(db, workspace_id=workspace_id, test_plan_id=test_plan_id)
    settings = effective_load_settings(db)
    ctx = _validate_run_context(
        db,
        plan=plan,
        run_type=run_type,
        settings=settings,
        confirm_high_concurrency=True,
    )
    _items, rules = _rows_for_plan(db, plan_id=plan.id)
    snapshot = _snapshot_payload(ctx, run_type=run_type, rules=rules)
    document = build_test_plan_taurus_document_from_snapshot(
        snapshot,
        jmeter_path=runtime_jmeter_path(PREVIEW_RUNNER_HOME),
        jmeter_version=RUNTIME_JMETER_VERSION,
    )
    variable_values = [
        value
        for scenario_document in ctx.scenario_taurus_docs.values()
        for value in internal_env_values(scenario_document.get("variables") or {}).values()
    ]
    content, warnings = safe_preview_yaml(document, variable_values=variable_values)
    if (
        run_type == "standard"
        and ctx.expected_concurrency > settings.single_node_concurrency_soft_limit
    ):
        warnings.append(
            _preview_warning(
                "soft_limit_exceeded",
                "Saved load settings exceed the configured single-node soft limit.",
                field="scenarioItems",
                severity="warning",
            )
        )
    return ExecutionPreviewResponse(
        source_type="test_plan",
        source_id=plan.id,
        source_revision=plan.revision,
        mode=run_type,
        format="yaml",
        content=content,
        warnings=warnings,
    )


def test_plan_references_env_group(db: Session, *, workspace_id: str, env_group_id: str) -> bool:
    return (
        db.scalar(
            select(TestPlan.id)
            .where(TestPlan.workspace_id == workspace_id, TestPlan.env_group_id == env_group_id)
            .limit(1)
        )
        is not None
    )


def test_plan_references_scenario(db: Session, *, workspace_id: str, scenario_id: str) -> bool:
    return (
        db.scalar(
            select(TestPlanScenarioItem.id)
            .join(TestPlan, TestPlan.id == TestPlanScenarioItem.test_plan_id)
            .where(
                TestPlanScenarioItem.workspace_id == workspace_id,
                TestPlanScenarioItem.scenario_id == scenario_id,
                TestPlan.deleted_at.is_(None),
            )
            .limit(1)
        )
        is not None
    )


def _scenario_content(scenario: Scenario) -> dict[str, Any]:
    return _scenario_snapshot(scenario)


def _validate_run_context(
    db: Session,
    *,
    plan: TestPlan,
    run_type: str,
    settings: LoadSettings,
    confirm_high_concurrency: bool,
    resource_request: dict[str, Any] | None = None,
) -> ValidatedPlanContext:
    items, rules = _rows_for_plan(db, plan_id=plan.id)
    enabled_items = [item for item in items if item.enabled]
    if not enabled_items:
        raise AppError("TEST_PLAN_NOT_RUNNABLE", "Test Plan is not runnable.", 409)
    if len(enabled_items) > settings.max_scenario_items_per_test_plan:
        raise validation_error(
            [field_error("scenarioItems", "Too many enabled Scenario items.", "too_many_scenarios")]
        )
    enabled_rules = [rule for rule in rules if rule.enabled]
    if run_type == "standard" and len(enabled_rules) > settings.max_sla_rules_per_test_plan:
        raise validation_error(
            [field_error("slaRules", "Too many enabled SLA Rules.", "too_many_sla_rules")]
        )
    plan_node_ids = list(
        plan.selected_node_ids_json or ([plan.selected_node_id] if plan.selected_node_id else [])
    )
    requested_node_ids = plan_node_ids
    resource_mode = plan.resource_mode
    node_count = plan.node_count
    if run_type == "standard" and resource_request is not None:
        resource_mode = str(resource_request.get("mode") or resource_mode)
        requested_node_ids = list(resource_request.get("selectedNodeIds") or [])
        node_count = resource_request.get("nodeCount")
    if (
        run_type == "standard"
        and resource_mode == "manual"
        and len(set(requested_node_ids)) != len(requested_node_ids)
    ):
        raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
    if run_type == "standard" and resource_mode == "manual" and node_count is not None:
        raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
    if run_type == "standard" and resource_mode == "auto" and requested_node_ids:
        raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
    if plan.pool_type is None:
        raise AppError("TEST_PLAN_NOT_RUNNABLE", "Test Plan is missing Load Node resources.", 409)
    node = _node_for_plan(db, plan)
    if resource_mode == "manual":
        if not requested_node_ids:
            raise AppError(
                "TEST_PLAN_NOT_RUNNABLE", "Test Plan is missing a selected Load Node.", 409
            )
        visible_nodes = _visible_nodes_for_pool(
            db,
            workspace_id=plan.workspace_id,
            pool_type=plan.pool_type,
            node_ids=requested_node_ids,
        )
        if any(node_id not in visible_nodes for node_id in requested_node_ids):
            raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
        if plan.selected_node_id not in requested_node_ids:
            node = visible_nodes[requested_node_ids[0]]
    elif not node_count:
        raise AppError("TEST_PLAN_NOT_RUNNABLE", "Test Plan is missing Load Node count.", 409)
    elif _auto_idle_capacity(db, plan) < int(node_count):
        raise AppError(
            "LOAD_NODE_CAPACITY_UNAVAILABLE",
            "Not enough Load Nodes are available.",
            409,
            [
                {
                    "requested": str(node_count),
                    "available": str(_auto_idle_capacity(db, plan)),
                }
            ],
        )
    env_group = _env_for_plan(db, plan)
    if plan.env_group_id is not None and env_group is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    env_variables = env_group_runtime_values(env_group)
    scenarios = _scenario_map(db, workspace_id=plan.workspace_id, items=enabled_items)
    if any(item.scenario_id not in scenarios for item in enabled_items):
        raise AppError("TEST_PLAN_NOT_RUNNABLE", "Referenced Scenario is unavailable.", 409)
    expected = _expected_concurrency_for_rows(plan.run_mode, enabled_items)
    if (
        run_type == "standard"
        and resource_request
        and resource_request.get("concurrencyPerNode") is not None
    ):
        expected = int(resource_request["concurrencyPerNode"])
    if run_type == "standard" and expected > settings.single_node_concurrency_hard_limit:
        raise validation_error(
            [
                field_error(
                    "scenarioItems",
                    "Expected concurrency exceeds the hard limit.",
                    "single_node_concurrency_hard_limit",
                )
            ]
        )
    if (
        run_type == "standard"
        and expected > settings.single_node_concurrency_soft_limit
        and not confirm_high_concurrency
    ):
        raise AppError(
            "LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED",
            "Expected single-node concurrency exceeds the configured soft limit.",
            409,
            [
                {
                    "field": "scenarioItems",
                    "code": "single_node_concurrency_soft_limit",
                    "message": "Confirm that this run should start with high single-node concurrency.",
                    "meta": {
                        "expectedConcurrencyPerNode": expected,
                        "softLimit": settings.single_node_concurrency_soft_limit,
                    },
                }
            ],
        )
    dependency_files: list[dict[str, Any]] = []
    seen_dependency_ids: set[str] = set()
    scenario_taurus_docs: dict[str, dict[str, Any]] = {}
    for item in enabled_items:
        scenario = scenarios[item.scenario_id]
        dependency_rows = _enabled_dependency_files(db, scenario=scenario)
        dependency_models = [file for _ref, file in dependency_rows]
        content = _scenario_content(scenario)
        doc = build_debug_taurus_document_from_content(
            scenario_content=content,
            env_variables=env_variables,
            dependency_files=dependency_models,
            jmeter_path=runtime_jmeter_path(
                (node.runner_home if node is not None else PREVIEW_RUNNER_HOME)
            ),
            jmeter_version=RUNTIME_JMETER_VERSION,
            memory_xmx=jmeter_memory_xmx(db),
            test_plan_item_id=item.id,
        )
        scenario_taurus_docs[item.id] = doc["scenarios"]["surgepilot_scenario"]
        for ref, file in dependency_rows:
            if file.id in seen_dependency_ids:
                continue
            seen_dependency_ids.add(file.id)
            dependency_files.append(
                {
                    "id": file.id,
                    "filename": file.filename,
                    "sizeBytes": file.size_bytes,
                    "sha256": file.sha256,
                    "refType": ref.ref_type,
                    "stepId": ref.step_id,
                    "scenarioId": ref.scenario_id,
                }
            )
    standard_load_settings_by_item_id = {
        item.id: _load_settings_dict(item) for item in enabled_items
    }
    if (
        run_type == "standard"
        and resource_request
        and resource_request.get("concurrencyPerNode") is not None
    ):
        standard_load_settings_by_item_id = {
            item_id: {**settings_payload, "concurrencyPerNode": expected}
            for item_id, settings_payload in standard_load_settings_by_item_id.items()
        }
    for index, item in enumerate(enabled_items):
        settings_payload = (
            standard_load_settings_by_item_id[item.id]
            if run_type == "standard"
            else debug_load_settings()
        )
        _validate_load_settings(
            settings_payload,
            field_prefix=f"scenarioItems[{index}].loadSettings",
            settings=settings,
        )
    for index, rule in enumerate(enabled_rules):
        _validate_sla_rule(_sla_rule_dict(rule), field_prefix=f"slaRules[{index}]")
    _validate_sla_rule_labels(
        [_sla_rule_dict(rule) for rule in enabled_rules],
        {
            request["label"]
            for scenario_document in scenario_taurus_docs.values()
            for request in scenario_document.get("requests", [])
            if request.get("label")
        },
    )
    return ValidatedPlanContext(
        test_plan=plan,
        env_group=env_group,
        node=node,
        scenario_rows=scenarios,
        scenario_taurus_docs=scenario_taurus_docs,
        dependency_files=dependency_files,
        enabled_items=enabled_items,
        expected_concurrency=expected,
        standard_load_settings_by_item_id=standard_load_settings_by_item_id,
        debug_load_settings_by_item_id={item.id: debug_load_settings() for item in enabled_items},
        jmeter_memory_xmx=jmeter_memory_xmx(db),
    )


def _snapshot_payload(
    ctx: ValidatedPlanContext, *, run_type: str, rules: list[TestPlanSlaRule]
) -> dict[str, Any]:
    plan = ctx.test_plan
    env_snapshot = None
    if ctx.env_group is not None:
        env_snapshot = {
            "id": ctx.env_group.id,
            "name": ctx.env_group.name,
            "variables": env_group_runtime_values(ctx.env_group),
        }
    enabled_rules = [_sla_rule_dict(rule) for rule in rules if rule.enabled]
    if run_type == "debug":
        sla_mode = "not_evaluated"
        rule_snapshot: list[dict[str, Any]] = []
    elif enabled_rules:
        sla_mode = "passfail"
        rule_snapshot = enabled_rules
    else:
        sla_mode = "not_configured"
        rule_snapshot = []
    scenario_items: list[dict[str, Any]] = []
    for item in ctx.enabled_items:
        scenario = ctx.scenario_rows[item.scenario_id]
        scenario_items.append(
            {
                "itemId": item.id,
                "order": item.position,
                "scenarioId": scenario.id,
                "scenarioRevision": scenario.revision,
                "scenarioName": scenario.name,
                "loadSettings": (
                    ctx.debug_load_settings_by_item_id
                    if run_type == "debug"
                    else ctx.standard_load_settings_by_item_id
                )[item.id],
                "visualScenario": ctx.scenario_taurus_docs[item.id],
            }
        )
    snapshot = {
        "schemaVersion": 1,
        "runType": run_type,
        "sourceType": "test_plan",
        "sourceId": plan.id,
        "sourceRevision": plan.revision,
        "validityDefault": "invalid" if run_type == "debug" else "valid",
        "slaEvaluationMode": sla_mode,
        "testPlan": {
            "id": plan.id,
            "name": plan.name,
            "description": plan.description,
            "tags": plan.tags_json or [],
            "revision": plan.revision,
            "runMode": "sequential" if run_type == "debug" else plan.run_mode,
        },
        "envGroup": env_snapshot,
        "resourceRequest": {
            "mode": plan.resource_mode if run_type == "standard" else "manual",
            "poolType": plan.pool_type,
            "selectedNodeId": plan.selected_node_id,
            "selectedNodeIds": list(
                plan.selected_node_ids_json
                or ([plan.selected_node_id] if plan.selected_node_id else [])
            )
            if run_type == "standard"
            else ([plan.selected_node_id] if plan.selected_node_id else []),
            "nodeCount": plan.node_count
            if run_type == "standard" and plan.resource_mode == "auto"
            else None,
            "expectedConcurrencyPerNode": ctx.expected_concurrency if run_type == "standard" else 1,
        },
        "scenarioItems": scenario_items,
        "jmeterMemoryXmx": ctx.jmeter_memory_xmx,
        "dependencyFiles": ctx.dependency_files,
        "slaRules": rule_snapshot,
    }
    document = build_test_plan_taurus_document_from_snapshot(
        snapshot,
        jmeter_path=runtime_jmeter_path(
            (ctx.node.runner_home if ctx.node is not None else PREVIEW_RUNNER_HOME)
        ),
        jmeter_version=RUNTIME_JMETER_VERSION,
    )
    yaml_text = yaml.safe_dump(document, sort_keys=False, allow_unicode=False)
    snapshot["generatedYaml"] = {
        "artifactRelativePath": "execution/generated.yml",
        "sha256": hashlib.sha256(yaml_text.encode()).hexdigest(),
    }
    return snapshot


def _scenario_alias(item_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", item_id)
    return f"scenario_{safe}"


def _execution_item(item: dict[str, Any]) -> dict[str, Any]:
    settings = item["loadSettings"]
    result: dict[str, Any] = {
        "executor": "jmeter",
        "scenario": _scenario_alias(item["itemId"]),
        "concurrency": settings["concurrencyPerNode"],
    }
    if settings.get("rampUpSeconds", 0) > 0:
        result["ramp-up"] = f"{settings['rampUpSeconds']}s"
    if settings.get("holdForSeconds") is not None:
        result["hold-for"] = f"{settings['holdForSeconds']}s"
    if settings.get("iterations") is not None:
        result["iterations"] = settings["iterations"]
    if settings.get("targetRps") is not None:
        result["throughput"] = settings["targetRps"]
    if settings.get("steps") is not None:
        result["steps"] = settings["steps"]
    if settings.get("delaySeconds", 0) > 0:
        result["delay"] = f"{settings['delaySeconds']}s"
    return result


def _passfail_criteria(rule: dict[str, Any]) -> dict[str, Any]:
    subject = rule["subject"]
    if subject == "avg_rt":
        subject = "avg-rt"
    criteria: dict[str, Any] = {
        "subject": subject,
        "condition": sla_condition_symbol(rule["condition"]),
        "threshold": sla_threshold_text(rule["threshold"]),
        "stop": rule.get("action") == "stop",
        "fail": True,
    }
    if rule.get("label"):
        criteria["label"] = rule["label"]
    if rule.get("timeframeLogic"):
        criteria["logic"] = rule["timeframeLogic"]
    if rule.get("timeframeSeconds"):
        criteria["timeframe"] = f"{rule['timeframeSeconds']}s"
    return criteria


def build_test_plan_taurus_document_from_snapshot(
    snapshot: dict[str, Any], *, jmeter_path: str, jmeter_version: str
) -> dict[str, Any]:
    scenario_items = snapshot.get("scenarioItems") or []
    force_ctg = snapshot.get("runType") == "standard" and any(
        item.get("loadSettings", {}).get("steps") is not None for item in scenario_items
    )
    sequential = (
        snapshot.get("runType") == "debug"
        or snapshot.get("testPlan", {}).get("runMode") == "sequential"
    )
    env_values = dict((snapshot.get("envGroup") or {}).get("variables") or {})
    criteria = (
        [
            _passfail_criteria(rule)
            for rule in snapshot.get("slaRules") or []
            if rule.get("enabled", True)
        ]
        if snapshot.get("runType") == "standard"
        else []
    )
    memory_xmx = str(snapshot.get("jmeterMemoryXmx") or get_settings().jmeter_memory_xmx)
    modules = taurus_modules(
        jmeter_path=jmeter_path,
        jmeter_version=jmeter_version,
        force_ctg=force_ctg,
        sequential=sequential,
        memory_xmx=memory_xmx,
        include_passfail=bool(criteria),
    )
    settings = taurus_settings(env_values)
    scenarios = {
        _scenario_alias(item["itemId"]): item.get("visualScenario") or {} for item in scenario_items
    }
    document: dict[str, Any] = {
        "settings": settings,
        "modules": modules,
        "provisioning": "local",
        "scenarios": scenarios,
        "execution": [_execution_item(item) for item in scenario_items],
        "reporting": [
            {"module": "final-stats", "dump-csv": "artifacts/finalstats.csv"},
            {"module": "console"},
        ],
    }
    if criteria:
        document["reporting"].append({"module": "passfail", "criteria": criteria})
    return document


def create_test_plan_run(
    db: Session,
    *,
    workspace_id: str,
    actor: User,
    request: Request | None = None,
    source_id: str,
    expected_source_revision: int,
    run_type: str,
    confirm_high_concurrency: bool = False,
    resource_request: object | None = None,
    dedup_window_seconds: int = DEFAULT_DEDUP_WINDOW_SECONDS,
) -> TestPlanRunResult:
    if run_type not in {"debug", "standard"}:
        raise validation_error(
            [field_error("runType", "Run type is not supported.", "unsupported_run_type")]
        )
    plan = db.scalar(
        select(TestPlan)
        .where(
            TestPlan.id == source_id,
            TestPlan.workspace_id == workspace_id,
            TestPlan.deleted_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if plan is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    if plan.revision != expected_source_revision:
        raise AppError(
            "TEST_PLAN_REVISION_CONFLICT",
            "Test Plan was updated by another request. Reload and try again.",
            409,
        )
    settings = effective_load_settings(db)
    _items, rules = _rows_for_plan(db, plan_id=plan.id)
    normalized_resource_request = _normalize_resource_request_override(resource_request)
    if run_type == "standard" and normalized_resource_request is not None:
        normalized_resource_request["poolType"] = plan.pool_type
    ctx = _validate_run_context(
        db,
        plan=plan,
        run_type=run_type,
        settings=settings,
        confirm_high_concurrency=confirm_high_concurrency,
        resource_request=normalized_resource_request,
    )
    snapshot_payload = _snapshot_payload(ctx, run_type=run_type, rules=rules)
    resource = _apply_resource_request_override(
        snapshot_payload, run_type=run_type, resource_request=normalized_resource_request
    )
    snapshot_hash = _canonical_hash(snapshot_payload)
    dedup_input = {
        "workspaceId": workspace_id,
        "triggeredByUserId": actor.id,
        "runType": run_type,
        "sourceType": "test_plan",
        "sourceId": plan.id,
        "sourceRevision": plan.revision,
        "resourceMode": resource.get("mode", "manual") if run_type == "standard" else "manual",
        "selectedNodeIds": list(resource.get("selectedNodeIds") or []),
        "nodeCount": resource.get("nodeCount"),
        "snapshotHash": snapshot_hash,
    }
    dedup_hash = _canonical_hash(dedup_input)
    now = utc_now()
    db.query(RunCreationDedupKey).filter(RunCreationDedupKey.expires_at <= now).delete(
        synchronize_session=False
    )
    existing_run = _find_existing_dedup_run(
        db, workspace_id=workspace_id, dedup_hash=dedup_hash, now=now
    )
    if existing_run is not None:
        return TestPlanRunResult(existing_run, True, 200)
    try:
        run = create_run_execution(
            db,
            RunExecutionInput(
                workspace_id=workspace_id,
                actor=actor,
                selected_node_id=plan.selected_node_id or "",
                run_type=run_type,
                source_type="test_plan",
                source_id=plan.id,
                snapshot_payload=snapshot_payload,
                selected_node_ids=tuple(resource.get("selectedNodeIds") or ()),
                resource_mode=resource.get("mode", "manual")
                if run_type == "standard"
                else "manual",
                pool_type=resource.get("poolType") if run_type == "standard" else None,
                node_count=resource.get("nodeCount") if run_type == "standard" else None,
            ),
        )
    except AppError as exc:
        if exc.code == "LOAD_NODE_BUSY":
            db.rollback()
            existing_run = _find_existing_dedup_run(
                db, workspace_id=workspace_id, dedup_hash=dedup_hash, now=now
            )
            if existing_run is not None:
                return TestPlanRunResult(existing_run, True, 200)
        raise
    run.validity = "invalid" if run_type == "debug" else "valid"
    write_audit_event(
        db,
        event_type="run.debug_requested" if run_type == "debug" else "run.standard_requested",
        request=request,
        actor_user_id=actor.id,
        workspace_id=workspace_id,
        target_type="run",
        target_id=run.id,
        details={
            "runId": run.id,
            "workspaceId": workspace_id,
            "testPlanId": plan.id,
            "testPlanRevision": plan.revision,
            "nodeId": plan.selected_node_id,
            "requestedBy": actor.id,
            "expectedConcurrencyPerNode": ctx.expected_concurrency,
        },
    )
    db.add(
        RunCreationDedupKey(
            id=new_ulid(),
            workspace_id=workspace_id,
            dedup_key_hash=dedup_hash,
            run_id=run.id,
            expires_at=now + timedelta(seconds=dedup_window_seconds),
            created_at=now,
        )
    )
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        existing_run = _find_existing_dedup_run(
            db, workspace_id=workspace_id, dedup_hash=dedup_hash, now=now
        )
        if existing_run is not None:
            return TestPlanRunResult(existing_run, True, 200)
        raise exc
    return TestPlanRunResult(run, False, 201)


def _find_existing_dedup_run(db: Session, *, workspace_id: str, dedup_hash: str, now) -> Run | None:
    existing = db.scalar(
        select(RunCreationDedupKey).where(
            RunCreationDedupKey.workspace_id == workspace_id,
            RunCreationDedupKey.dedup_key_hash == dedup_hash,
            RunCreationDedupKey.expires_at > now,
        )
    )
    if existing is None:
        return None
    return db.scalar(select(Run).where(Run.id == existing.run_id, Run.workspace_id == workspace_id))
