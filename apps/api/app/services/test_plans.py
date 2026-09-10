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
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.ids import is_ulid, new_ulid
from app.core.time import utc_now
from app.models.auth import User
from app.models.env_groups import EnvGroup
from app.models.load_nodes import LoadNode
from app.models.runs import Run
from app.models.scenarios import RunCreationDedupKey, Scenario
from app.models.test_plans import TestPlan, TestPlanScenarioItem, TestPlanSlaRule
from app.schemas.common import ExecutionPreviewResponse, ExecutionPreviewWarning
from app.schemas.test_plans import TestPlanCreateRequest
from app.services.audit import write_audit_event
from app.services.env_groups import env_group_runtime_values, internal_env_values
from app.services.runs import RunExecutionInput, create_run_execution
from app.services.scenarios import (
    ACTIVE_RUN_STATES,
    DEFAULT_DEDUP_WINDOW_SECONDS,
    SCENARIO_ALIAS,
    _enabled_dependency_files,
    build_debug_taurus_document_from_content,
    field_error,
    invalid_preview_mode,
    request_label,
    safe_preview_yaml,
    validation_error,
)

RC_SUBJECT_PATTERN = re.compile(r"^rc(?:\d{3}|\d\?\?|\*)$")
DURATION_SUBJECTS = {"avg_rt", "p90", "p95", "p99"}
PERCENT_SUBJECTS = {"fail", "succ"}
COUNT_SUBJECTS = {"hits"}
BYTE_SUBJECTS = {"bytes"}
ACTIVE_RUN_STATES_LIST = list(ACTIVE_RUN_STATES)
JMETER_PROTOCOL_HANDLERS = {"http": "bzt.jmx.http.HTTPProtocolHandler"}
TAURUS_MODULE_CLASS_ALIASES = {
    "local": "bzt.modules.provisioning.Local",
    "consolidator": "bzt.modules.aggregator.ConsolidatingAggregator",
    "final-stats": "bzt.modules.reporting.FinalStatus",
    "console": "bzt.modules.console.ConsoleStatusReporter",
    "passfail": "bzt.modules.passfail.PassFailStatus",
}
# P0-03/P0-05 runtime baseline: the Load Node's configured Apache JMeter
# deployment is the source of truth for ``modules.jmeter.path``/``version``.
# P0-06 must not redefine the JMeter runtime independently.
JMETER_RUNTIME_PATH = (
    "/opt/surgepilot/runner/current/apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper"
)
JMETER_RUNTIME_VERSION = "5.6.3"


def _num(value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    return value


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
    settings_payload: dict[str, Any], *, field_prefix: str, settings: Settings
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
            labels.add(request_label(step["method"], step["path"]))
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
    db: Session, *, workspace_id: str, payload: dict[str, Any], settings: Settings
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
    pool_type = resource.get("poolType")
    selected_node_id = resource.get("selectedNodeId")
    if selected_node_id is not None:
        if not is_ulid(selected_node_id):
            raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
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
        node = db.scalar(
            select(LoadNode).where(
                LoadNode.id == selected_node_id,
                LoadNode.archived_at.is_(None),
            )
        )
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
    settings = get_settings()
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
        selected_node_id=resource.get("selectedNodeId"),
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
            "poolType": source.pool_type,
            "selectedNodeId": source.selected_node_id,
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
    settings = get_settings()
    payload = _pydantic_create_payload(payload)
    payload["tags"] = _normalize_tags(payload.get("tags") or [])
    _validate_payload_references(db, workspace_id=workspace_id, payload=payload, settings=settings)
    now = utc_now()
    resource = payload["resource"]
    selected_node_ids = list(source.selected_node_ids_json or [])
    if not selected_node_ids and source.selected_node_id:
        selected_node_ids = [source.selected_node_id]
    clone = TestPlan(
        id=new_ulid(),
        workspace_id=workspace_id,
        name=payload["name"].strip(),
        description=payload.get("description"),
        tags_json=payload["tags"],
        env_group_id=payload.get("envGroupId"),
        run_mode=payload.get("runMode") or "sequential",
        pool_type=resource.get("poolType"),
        selected_node_id=resource.get("selectedNodeId"),
        resource_mode=source.resource_mode,
        selected_node_ids_json=selected_node_ids,
        node_count=source.node_count,
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
    settings = get_settings()
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
    locked.selected_node_id = resource.get("selectedNodeId")
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


def _env_for_plan(db: Session, plan: TestPlan) -> EnvGroup | None:
    if plan.env_group_id is None:
        return None
    return db.scalar(
        select(EnvGroup).where(
            EnvGroup.id == plan.env_group_id, EnvGroup.workspace_id == plan.workspace_id
        )
    )


def not_runnable_reasons(
    db: Session,
    plan: TestPlan,
    items: list[TestPlanScenarioItem] | None = None,
    rules: list[TestPlanSlaRule] | None = None,
) -> list[str]:
    if items is None or rules is None:
        loaded_items, loaded_rules = _rows_for_plan(db, plan_id=plan.id)
        items = loaded_items if items is None else items
        rules = loaded_rules if rules is None else rules
    reasons: list[str] = []
    enabled = [item for item in items if item.enabled]
    enabled_rules = [rule for rule in rules if rule.enabled]
    if not enabled:
        reasons.append("no_enabled_scenarios")
    settings = get_settings()
    if len(enabled) > settings.max_scenario_items_per_test_plan:
        reasons.append("too_many_scenarios")
    if len(enabled_rules) > settings.max_sla_rules_per_test_plan:
        reasons.append("too_many_sla_rules")
    if plan.pool_type is None:
        reasons.append("load_node_required")
    elif plan.selected_node_id is None:
        reasons.append("load_node_required")
    else:
        node = _node_for_plan(db, plan)
        if node is None or node.archived_at is not None:
            reasons.append("load_node_unavailable")
        elif plan.pool_type == "public" and node.scope != "public":
            reasons.append("load_node_unavailable")
        elif plan.pool_type == "private" and not (
            node.scope == "workspace" and node.workspace_id == plan.workspace_id
        ):
            reasons.append("load_node_unavailable")
        elif node.status != "idle":
            reasons.append("load_node_not_idle")
    scenario_rows = _scenario_map(db, workspace_id=plan.workspace_id, items=enabled)
    if any(item.scenario_id not in scenario_rows for item in enabled):
        reasons.append("scenario_unavailable")
    env_group = _env_for_plan(db, plan)
    if plan.env_group_id is not None and env_group is None:
        reasons.append("env_group_unavailable")
    expected = _expected_concurrency_for_rows(plan.run_mode, enabled)
    if enabled and expected > settings.single_node_concurrency_hard_limit:
        reasons.append("single_node_concurrency_hard_limit")
    return reasons


def _guard(db: Session, plan: TestPlan, items: list[TestPlanScenarioItem]) -> dict[str, Any]:
    settings = get_settings()
    expected = _expected_concurrency_for_rows(plan.run_mode, items)
    return {
        "expectedConcurrencyPerNode": expected,
        "softConcurrencyPerNodeLimit": settings.single_node_concurrency_soft_limit,
        "hardConcurrencyPerNodeLimit": settings.single_node_concurrency_hard_limit,
        "requiresHighConcurrencyConfirmation": expected
        > settings.single_node_concurrency_soft_limit,
    }


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
    settings = get_settings()
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
        jmeter_path=JMETER_RUNTIME_PATH,
        jmeter_version=JMETER_RUNTIME_VERSION,
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


def _taurus_settings(env: dict[str, str]) -> dict[str, Any]:
    return {
        "artifacts-dir": "artifacts",
        "aggregator": "consolidator",
        "env": env,
    }


def _taurus_modules(
    *,
    jmeter_path: str,
    jmeter_version: str,
    force_ctg: bool,
    sequential: bool = False,
    memory_xmx: str = "4G",
    include_passfail: bool = False,
) -> dict[str, Any]:
    local_module: dict[str, Any] = {"class": TAURUS_MODULE_CLASS_ALIASES["local"]}
    if sequential:
        local_module["sequential"] = True
    modules: dict[str, Any] = {
        "jmeter": {
            "class": "bzt.modules.jmeter.JMeterExecutor",
            "path": jmeter_path,
            "version": jmeter_version,
            "detect-plugins": False,
            "memory-xmx": memory_xmx,
            "force-ctg": force_ctg,
            "fix-log4j": False,
            "fix-jars": False,
            "protocol-handlers": dict(JMETER_PROTOCOL_HANDLERS),
        },
        "local": local_module,
        "consolidator": {"class": TAURUS_MODULE_CLASS_ALIASES["consolidator"]},
        "final-stats": {"class": TAURUS_MODULE_CLASS_ALIASES["final-stats"]},
        "console": {"class": TAURUS_MODULE_CLASS_ALIASES["console"]},
    }
    if include_passfail:
        modules["passfail"] = {"class": TAURUS_MODULE_CLASS_ALIASES["passfail"]}
    return modules


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
    modules = _taurus_modules(
        jmeter_path=jmeter_path,
        jmeter_version=jmeter_version,
        force_ctg=force_ctg,
        sequential=sequential,
        memory_xmx=memory_xmx,
        include_passfail=bool(criteria),
    )
    settings = _taurus_settings(env_values)
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


def iso_z(value) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def debug_load_settings() -> dict[str, Any]:
    """Fixed low-risk load profile applied to every enabled Scenario item."""
    return {
        "concurrencyPerNode": 1,
        "rampUpSeconds": 0,
        "holdForSeconds": None,
        "iterations": 1,
        "targetRps": None,
        "steps": None,
        "delaySeconds": 0,
    }


@dataclass(frozen=True)
class TestPlanRunResult:
    """Outcome of a Test Plan Run Now / Debug creation request.

    ``deduplicated`` is ``True`` when the request hit the short-window dedup
    key and the already-created Run is returned with status 200 instead of 201.
    """

    run: Run
    deduplicated: bool
    status_code: int


@dataclass(frozen=True)
class ValidatedPlanContext:
    test_plan: TestPlan
    env_group: EnvGroup | None
    env_variables: dict[str, str]
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
    if mode not in {"manual", "auto"}:
        raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
    if mode == "manual":
        if node_count is not None or not selected_node_ids:
            raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
        if len(set(selected_node_ids)) != len(selected_node_ids):
            raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
    elif selected_node_ids or not isinstance(node_count, int) or node_count <= 0:
        raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
    return {
        "mode": mode,
        "selectedNodeIds": selected_node_ids,
        "selectedNodeId": selected_node_ids[0] if selected_node_ids else None,
        "nodeCount": node_count if mode == "auto" else None,
    }


def _apply_resource_request_override(
    snapshot_payload: dict[str, Any], *, resource_request: dict[str, Any] | None
) -> dict[str, Any]:
    resource = dict(snapshot_payload.get("resourceRequest") or {})
    if resource_request is not None:
        resource.update(resource_request)
    snapshot_payload["resourceRequest"] = resource
    return resource


def detail_payload(db: Session, plan: TestPlan) -> dict[str, Any]:
    items, rules = _rows_for_plan(db, plan_id=plan.id)
    scenarios = _scenario_map(db, workspace_id=plan.workspace_id, items=items)
    reasons = not_runnable_reasons(db, plan, items, rules)
    scenario_items: list[dict[str, Any]] = []
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
            "poolType": plan.pool_type,
            "selectedNodeId": plan.selected_node_id,
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
    settings = get_settings()
    updated_by = db.get(User, plan.updated_by)
    return {
        "id": plan.id,
        "name": plan.name,
        "description": plan.description,
        "tags": plan.tags_json or [],
        "runMode": plan.run_mode,
        "envGroup": {"id": env.id, "name": env.name} if env else None,
        "resource": {
            "poolType": plan.pool_type,
            "selectedNodeId": plan.selected_node_id,
            "selectedNodeName": node.host if node else None,
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
    _ = workspace_id
    return [summary_payload(db, plan) for plan in plans]


def _validate_run_context(
    db: Session,
    *,
    plan: TestPlan,
    run_type: str,
    settings: Settings,
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
    if plan.pool_type is None:
        raise AppError("TEST_PLAN_NOT_RUNNABLE", "Test Plan is missing Load Node resources.", 409)
    requested_node_ids = list(
        (plan.selected_node_ids_json or ([plan.selected_node_id] if plan.selected_node_id else []))
    )
    resource_mode = plan.resource_mode
    node_count = plan.node_count
    if run_type == "standard" and resource_request is not None:
        resource_mode = resource_request["mode"]
        requested_node_ids = list(resource_request["selectedNodeIds"])
        node_count = resource_request["nodeCount"]
    if resource_mode == "auto" and run_type == "standard":
        if not node_count:
            raise AppError("TEST_PLAN_NOT_RUNNABLE", "Test Plan is missing Load Node count.", 409)
    elif not requested_node_ids:
        raise AppError(
            "TEST_PLAN_NOT_RUNNABLE", "Test Plan is missing a selected Load Node.", 409
        )
    if not (run_type == "standard" and resource_mode == "auto"):
        node = _node_for_plan(db, plan)
        if requested_node_ids and (plan.selected_node_id not in requested_node_ids):
            node = db.get(LoadNode, requested_node_ids[0])
        if node is None or node.archived_at is not None:
            raise AppError("TEST_PLAN_NOT_RUNNABLE", "Selected Load Node is unavailable.", 409)
        if plan.pool_type == "public" and node.scope != "public":
            raise AppError("TEST_PLAN_NOT_RUNNABLE", "Selected Load Node is unavailable.", 409)
        if plan.pool_type == "private" and not (
            node.scope == "workspace" and node.workspace_id == plan.workspace_id
        ):
            raise AppError("TEST_PLAN_NOT_RUNNABLE", "Selected Load Node is unavailable.", 409)
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
        and expected > settings.single_node_concurrency_hard_limit
    ):
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
        content = {
            "name": scenario.name,
            "baseUrlExpression": scenario.base_url_expression,
            "defaultSettings": scenario.default_settings_json,
            "dataSources": scenario.data_sources_json,
            "steps": scenario.steps_json,
        }
        doc = build_debug_taurus_document_from_content(
            scenario_content=content,
            env_variables=env_variables,
            dependency_files=dependency_models,
            jmeter_path=JMETER_RUNTIME_PATH,
            jmeter_version=JMETER_RUNTIME_VERSION,
        )
        scenario_taurus_docs[item.id] = doc["scenarios"][SCENARIO_ALIAS]
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
        env_variables=env_variables,
        scenario_rows=scenarios,
        scenario_taurus_docs=scenario_taurus_docs,
        dependency_files=dependency_files,
        enabled_items=enabled_items,
        expected_concurrency=expected,
        standard_load_settings_by_item_id=standard_load_settings_by_item_id,
        debug_load_settings_by_item_id={item.id: debug_load_settings() for item in enabled_items},
        jmeter_memory_xmx=settings.jmeter_memory_xmx,
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
            "variables": ctx.env_variables,
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
    snapshot: dict[str, Any] = {
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
            "mode": plan.resource_mode,
            "poolType": plan.pool_type,
            "selectedNodeId": plan.selected_node_id,
            "selectedNodeIds": list(
                plan.selected_node_ids_json
                or ([plan.selected_node_id] if plan.selected_node_id else [])
            ),
            "nodeCount": plan.node_count,
            "expectedConcurrencyPerNode": ctx.expected_concurrency
            if run_type == "standard"
            else 1,
        },
        "scenarioItems": scenario_items,
        "jmeterMemoryXmx": ctx.jmeter_memory_xmx,
        "dependencyFiles": ctx.dependency_files,
        "slaRules": rule_snapshot,
    }
    document = build_test_plan_taurus_document_from_snapshot(
        snapshot,
        jmeter_path=JMETER_RUNTIME_PATH,
        jmeter_version=JMETER_RUNTIME_VERSION,
    )
    yaml_text = yaml.safe_dump(document, sort_keys=False, allow_unicode=False)
    snapshot["generatedYaml"] = {
        "artifactRelativePath": "execution/generated.yml",
        "sha256": hashlib.sha256(yaml_text.encode()).hexdigest(),
    }
    return snapshot


def _find_existing_dedup_run(
    db: Session, *, workspace_id: str, dedup_hash: str, now
) -> Run | None:
    existing_dedup = db.scalar(
        select(RunCreationDedupKey).where(
            RunCreationDedupKey.workspace_id == workspace_id,
            RunCreationDedupKey.dedup_key_hash == dedup_hash,
            RunCreationDedupKey.expires_at > now,
        )
    )
    if existing_dedup is None:
        return None
    return db.scalar(
        select(Run).where(Run.id == existing_dedup.run_id, Run.workspace_id == workspace_id)
    )


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
    """Create a Test Plan Standard Run Now or Debug Run.

    The caller owns the transaction. This function validates the saved Test
    Plan against the P0-06 run guardrails (single visible Idle Load Node, Env
    Group and Scenario references, concurrency soft/hard limits and SLA
    Rules), snapshots the immutable execution context, and atomically creates
    the Run + Snapshot + node lease through ``create_run_execution``. A
    short-window dedup key collapses repeated user retries onto the same Run.
    """
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
    settings = get_settings()
    _items, rules = _rows_for_plan(db, plan_id=plan.id)
    normalized_resource_request = _normalize_resource_request_override(resource_request)
    if run_type == "debug" and normalized_resource_request is not None:
        raise AppError("RESOURCE_REQUEST_INVALID", "Resource request is invalid.", 422)
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
        snapshot_payload, resource_request=normalized_resource_request
    )
    snapshot_hash = _canonical_hash(snapshot_payload)
    dedup_input = {
        "workspaceId": workspace_id,
        "triggeredByUserId": actor.id,
        "runType": run_type,
        "sourceType": "test_plan",
        "sourceId": plan.id,
        "sourceRevision": plan.revision,
        "resourceMode": resource.get("mode"),
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
                selected_node_id=resource.get("selectedNodeId") or plan.selected_node_id or "",
                run_type=run_type,
                source_type="test_plan",
                source_id=plan.id,
                snapshot_payload=snapshot_payload,
                selected_node_ids=tuple(resource.get("selectedNodeIds") or ()),
                resource_mode=resource.get("mode", "manual") if run_type == "standard" else "manual",
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
