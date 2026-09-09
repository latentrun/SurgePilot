from dataclasses import dataclass
from typing import Any
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.time import utc_now
from app.models.auth import SystemSetting, User
from app.schemas.auth import SensitiveStatus, SystemSettingsValues
from app.services.load_node_connectivity import LOAD_NODE_API_BASE_URL, configured_load_node_api_base_url, env_load_node_api_base_url, validate_load_node_api_base_url, LoadNodeApiBaseUrlInvalid

ALLOW_SIGNUP = "allowSignup"
LOAD_SOFT_LIMIT = "loadSoftLimitWarningConcurrency"
JMETER_MEMORY_XMX = "jmeterMemoryXmx"
MAX_SCENARIO_ITEMS = "maxScenarioItemsPerTestPlan"
MAX_SLA_RULES = "maxSlaRulesPerTestPlan"
MAX_RUN_DURATION_SECONDS = "maxRunDurationSeconds"
MAX_RAMP_UP_SECONDS = "maxRampUpSeconds"
MAX_DELAY_SECONDS = "maxDelaySeconds"
MAX_ITERATIONS = "maxIterations"
MAX_TARGET_RPS = "maxTargetRps"
DEPENDENCY_FILE_MAX_BYTES = "dependencyFileMaxBytes"
DEPENDENCY_FILE_ALLOWED_EXTENSIONS = "dependencyFileAllowedExtensions"
DEPENDENCY_FILE_PREVIEW_MAX_BYTES = "dependencyFilePreviewMaxBytes"
DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS = "dependencyFilePreviewBinaryDenyExtensions"
SENSITIVE_MARKERS = ("secret", "token", "password", "privatekey", "credential", "key")
MIB = 1024 * 1024
GIB = 1024 * MIB
DEFAULT_PREVIEW_BINARY_DENY_EXTENSIONS = ".png,.jpg,.jpeg,.gif,.webp,.bmp,.ico,.svg,.pdf,.zip,.tar,.gz,.tgz,.bz2,.xz,.7z,.rar,.jar,.war,.class,.so,.dll,.dylib,.exe,.bin,.dat,.woff,.woff2,.ttf,.otf,.eot,.mp3,.mp4,.mov,.avi,.mkv,.webm"


def is_sensitive_setting_key(key: str) -> bool:
    folded = key.replace("_", "").replace("-", "").lower()
    return any(marker in folded for marker in SENSITIVE_MARKERS)


def _error(field: str, message: str) -> AppError:
    return AppError("VALIDATION_ERROR", "Validation failed.", 422, [{"field": field, "code": "INVALID_FIELD", "message": message}])


def _get(db: Session, key: str) -> SystemSetting | None: return db.get(SystemSetting, key)
def get_setting_value(db: Session, key: str, fallback: Any) -> Any:
    row = _get(db, key); return fallback if row is None else row.value_json


def _int(value: Any, key: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high: raise _error(key, f"Value must be an integer between {low} and {high}.")
    return value


def _extensions(value: Any, key: str, maximum: int) -> list[str]:
    values = value.split(",") if isinstance(value, str) else value
    if not isinstance(values, list): raise _error(key, "Value must be an extension list.")
    result: list[str] = []
    for raw in values:
        if not isinstance(raw, str): raise _error(key, "Extensions must be strings.")
        item = raw.strip().lower()
        if item and not item.startswith("."): item = "." + item
        if item and not re.fullmatch(r"\.[a-z0-9][a-z0-9_-]{0,15}", item): raise _error(key, "Extension is invalid.")
        if item and item not in result: result.append(item)
    if len(result) > maximum: raise _error(key, f"At most {maximum} extensions are allowed.")
    return result


def _url(value: Any, key: str) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()): return None
    try: return validate_load_node_api_base_url(value)
    except (LoadNodeApiBaseUrlInvalid, TypeError) as exc: raise _error(key, str(exc)) from exc


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    fallback: Any
    validator: Any


@dataclass(frozen=True)
class EffectiveLoadSettings:
    max_scenario_items_per_test_plan: int
    single_node_concurrency_soft_limit: int
    single_node_concurrency_hard_limit: int
    max_run_duration_seconds: int
    max_ramp_up_seconds: int
    max_delay_seconds: int
    max_iterations: int
    max_target_rps: int
    max_sla_rules_per_test_plan: int


@dataclass(frozen=True)
class DependencyFilePolicy:
    max_bytes: int
    allowed_extensions: list[str]
    preview_max_bytes: int
    preview_binary_deny_extensions: set[str]


def _registry() -> dict[str, SettingDefinition]:
    s = get_settings
    return {
        ALLOW_SIGNUP: SettingDefinition(ALLOW_SIGNUP, lambda: s().allow_signup, lambda v: v if isinstance(v, bool) else (_ for _ in ()).throw(_error(ALLOW_SIGNUP, "Value must be a boolean."))),
        LOAD_SOFT_LIMIT: SettingDefinition(LOAD_SOFT_LIMIT, lambda: s().single_node_concurrency_soft_limit, lambda v: _int(v, LOAD_SOFT_LIMIT, 1, s().single_node_concurrency_hard_limit)),
        JMETER_MEMORY_XMX: SettingDefinition(JMETER_MEMORY_XMX, lambda: s().jmeter_memory_xmx, lambda v: v if isinstance(v, str) and re.fullmatch(r"[1-9][0-9]*[KMG]", v) and int(v[:-1]) * {"K": 1 / 1024, "M": 1, "G": 1024}[v[-1]] >= 512 and int(v[:-1]) * {"K": 1 / 1024, "M": 1, "G": 1024}[v[-1]] <= 32768 else (_ for _ in ()).throw(_error(JMETER_MEMORY_XMX, "Value must be between 512M and 32G."))),
        MAX_SCENARIO_ITEMS: SettingDefinition(MAX_SCENARIO_ITEMS, lambda: s().max_scenario_items_per_test_plan, lambda v: _int(v, MAX_SCENARIO_ITEMS, 1, 100)),
        MAX_SLA_RULES: SettingDefinition(MAX_SLA_RULES, lambda: s().max_sla_rules_per_test_plan, lambda v: _int(v, MAX_SLA_RULES, 0, 50)),
        MAX_RUN_DURATION_SECONDS: SettingDefinition(MAX_RUN_DURATION_SECONDS, lambda: s().max_run_duration_seconds, lambda v: _int(v, MAX_RUN_DURATION_SECONDS, 60, 604800)),
        MAX_RAMP_UP_SECONDS: SettingDefinition(MAX_RAMP_UP_SECONDS, lambda: s().max_ramp_up_seconds, lambda v: _int(v, MAX_RAMP_UP_SECONDS, 0, 604800)),
        MAX_DELAY_SECONDS: SettingDefinition(MAX_DELAY_SECONDS, lambda: s().max_delay_seconds, lambda v: _int(v, MAX_DELAY_SECONDS, 0, 604800)),
        MAX_ITERATIONS: SettingDefinition(MAX_ITERATIONS, lambda: s().max_iterations, lambda v: _int(v, MAX_ITERATIONS, 1, 10000000)),
        MAX_TARGET_RPS: SettingDefinition(MAX_TARGET_RPS, lambda: s().max_target_rps, lambda v: _int(v, MAX_TARGET_RPS, 1, 1000000)),
        DEPENDENCY_FILE_MAX_BYTES: SettingDefinition(DEPENDENCY_FILE_MAX_BYTES, lambda: s().dependency_file_max_bytes, lambda v: _int(v, DEPENDENCY_FILE_MAX_BYTES, MIB, GIB)),
        DEPENDENCY_FILE_ALLOWED_EXTENSIONS: SettingDefinition(DEPENDENCY_FILE_ALLOWED_EXTENSIONS, lambda: _extensions(s().dependency_file_allowed_extensions, DEPENDENCY_FILE_ALLOWED_EXTENSIONS, 100), lambda v: _extensions(v, DEPENDENCY_FILE_ALLOWED_EXTENSIONS, 100)),
        DEPENDENCY_FILE_PREVIEW_MAX_BYTES: SettingDefinition(DEPENDENCY_FILE_PREVIEW_MAX_BYTES, lambda: s().dependency_file_preview_max_bytes, lambda v: _int(v, DEPENDENCY_FILE_PREVIEW_MAX_BYTES, 1024, 5 * MIB)),
        DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS: SettingDefinition(DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS, lambda: _extensions(s().dependency_file_preview_binary_deny_extensions or DEFAULT_PREVIEW_BINARY_DENY_EXTENSIONS, DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS, 200), lambda v: _extensions(v, DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS, 200)),
        LOAD_NODE_API_BASE_URL: SettingDefinition(LOAD_NODE_API_BASE_URL, env_load_node_api_base_url, lambda v: _url(v, LOAD_NODE_API_BASE_URL)),
    }


def _effective(db: Session, key: str) -> Any:
    definition = _registry()[key]; row = _get(db, key)
    return definition.fallback() if row is None else definition.validator(row.value_json)

def effective_allow_signup(db: Session) -> bool: return bool(_effective(db, ALLOW_SIGNUP))
def load_soft_limit_warning_concurrency(db: Session) -> int: return int(_effective(db, LOAD_SOFT_LIMIT))
def jmeter_memory_xmx(db: Session) -> str: return str(_effective(db, JMETER_MEMORY_XMX))

def effective_load_settings(db: Session) -> EffectiveLoadSettings:
    return EffectiveLoadSettings(int(_effective(db, MAX_SCENARIO_ITEMS)), int(_effective(db, LOAD_SOFT_LIMIT)), get_settings().single_node_concurrency_hard_limit, int(_effective(db, MAX_RUN_DURATION_SECONDS)), int(_effective(db, MAX_RAMP_UP_SECONDS)), int(_effective(db, MAX_DELAY_SECONDS)), int(_effective(db, MAX_ITERATIONS)), int(_effective(db, MAX_TARGET_RPS)), int(_effective(db, MAX_SLA_RULES)))

def dependency_file_policy(db: Session) -> DependencyFilePolicy:
    return DependencyFilePolicy(int(_effective(db, DEPENDENCY_FILE_MAX_BYTES)), list(_effective(db, DEPENDENCY_FILE_ALLOWED_EXTENSIONS)), int(_effective(db, DEPENDENCY_FILE_PREVIEW_MAX_BYTES)), set(_effective(db, DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS)))

def current_settings(db: Session) -> SystemSettingsValues:
    return SystemSettingsValues(allow_signup=effective_allow_signup(db), load_soft_limit_warning_concurrency=load_soft_limit_warning_concurrency(db), jmeter_memory_xmx=jmeter_memory_xmx(db), max_scenario_items_per_test_plan=int(_effective(db, MAX_SCENARIO_ITEMS)), max_sla_rules_per_test_plan=int(_effective(db, MAX_SLA_RULES)), max_run_duration_seconds=int(_effective(db, MAX_RUN_DURATION_SECONDS)), max_ramp_up_seconds=int(_effective(db, MAX_RAMP_UP_SECONDS)), max_delay_seconds=int(_effective(db, MAX_DELAY_SECONDS)), max_iterations=int(_effective(db, MAX_ITERATIONS)), max_target_rps=int(_effective(db, MAX_TARGET_RPS)), dependency_file_max_bytes=int(_effective(db, DEPENDENCY_FILE_MAX_BYTES)), dependency_file_allowed_extensions=list(_effective(db, DEPENDENCY_FILE_ALLOWED_EXTENSIONS)), dependency_file_preview_max_bytes=int(_effective(db, DEPENDENCY_FILE_PREVIEW_MAX_BYTES)), dependency_file_preview_binary_deny_extensions=list(_effective(db, DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS)), load_node_api_base_url=configured_load_node_api_base_url(db))

def sensitive_status() -> SensitiveStatus:
    s = get_settings(); return SensitiveStatus(runner_internal_token_configured=bool(s.runner_internal_token), ssh_credential_encryption_key_configured=bool(s.ssh_credential_encryption_key), minio_credentials_configured=bool(s.minio_access_key and s.minio_secret_key))

def update_settings(db: Session, *, values: dict[str, Any], actor: User) -> SystemSettingsValues:
    registry = _registry(); normalized: dict[str, Any] = {}
    for key, value in values.items():
        if is_sensitive_setting_key(key): raise AppError("SENSITIVE_SETTING_VALUE_FORBIDDEN", "Sensitive settings cannot be edited through this API.", 400)
        definition = registry.get(key)
        if definition is None: raise AppError("SETTING_NOT_EDITABLE", "Setting is not editable.", 400)
        normalized[key] = definition.validator(value)
    effective = {key: normalized.get(key, _effective(db, key)) for key in registry}
    if int(effective[DEPENDENCY_FILE_PREVIEW_MAX_BYTES]) > int(effective[DEPENDENCY_FILE_MAX_BYTES]) or int(effective[MAX_RAMP_UP_SECONDS]) > int(effective[MAX_RUN_DURATION_SECONDS]): raise AppError("VALIDATION_ERROR", "Validation failed.", 422)
    now = utc_now()
    for key, value in normalized.items():
        row = _get(db, key)
        if key == LOAD_NODE_API_BASE_URL and value is None:
            if row is not None: db.delete(row)
        elif row is None: db.add(SystemSetting(key=key, value_json=value, updated_by_user_id=actor.id, updated_at=now))
        else: row.value_json = value; row.updated_by_user_id = actor.id; row.updated_at = now
    db.flush(); return current_settings(db)
