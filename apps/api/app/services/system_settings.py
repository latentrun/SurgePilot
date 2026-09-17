from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.time import utc_now
from app.models.auth import SystemSetting, User
from app.schemas.auth import SensitiveStatus, SystemSettingsValues
from app.services.load_node_connectivity import (
    LOAD_NODE_API_BASE_URL,
    LoadNodeApiBaseUrlInvalid,
    configured_load_node_api_base_url,
    env_load_node_api_base_url,
    validate_load_node_api_base_url,
)

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
JMETER_MEMORY_PATTERN = re.compile(r"^[1-9][0-9]*[KMG]$")
EXTENSION_PATTERN = re.compile(r"^\.[a-z0-9][a-z0-9_-]{0,15}$")
MIB = 1024 * 1024
GIB = 1024 * MIB
DEFAULT_PREVIEW_BINARY_DENY_EXTENSIONS = (
    ".png,.jpg,.jpeg,.gif,.webp,.bmp,.ico,.svg,.pdf,.zip,.tar,.gz,.tgz,.bz2,.xz,"
    ".7z,.rar,.jar,.war,.class,.so,.dll,.dylib,.exe,.bin,.dat,.woff,.woff2,.ttf,"
    ".otf,.eot,.mp3,.mp4,.mov,.avi,.mkv,.webm"
)


def is_sensitive_setting_key(key: str) -> bool:
    folded = key.replace("_", "").replace("-", "").lower()
    return any(marker in folded for marker in SENSITIVE_MARKERS)


def _field_error(field: str, message: str, code: str = "INVALID_FIELD") -> dict[str, str]:
    return {"field": field, "code": code, "message": message}


def _validation_error(errors: list[dict[str, str]]) -> AppError:
    return AppError("VALIDATION_ERROR", "Validation failed.", 422, errors)


def _get_setting(db: Session, key: str) -> SystemSetting | None:
    get = getattr(db, "get", None)
    if not callable(get):
        return None
    return get(SystemSetting, key)


def get_setting_value(db: Session, key: str, fallback: Any) -> Any:
    setting = _get_setting(db, key)
    if setting is None:
        return fallback
    return setting.value_json


def _as_bool(value: Any, *, key: str) -> bool:
    if isinstance(value, bool):
        return value
    raise _validation_error([_field_error(key, "Value must be a boolean.")])


def _as_int(value: Any, *, key: str, min_value: int, max_value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _validation_error([_field_error(key, "Value must be an integer.")])
    if value < min_value or value > max_value:
        raise _validation_error(
            [_field_error(key, f"Value must be between {min_value} and {max_value}.")]
        )
    return value


def _memory_to_mib(value: str) -> int:
    amount = int(value[:-1])
    unit = value[-1]
    if unit == "K":
        return amount // 1024
    if unit == "M":
        return amount
    return amount * 1024


def _jmeter_memory(value: Any, *, key: str) -> str:
    if not isinstance(value, str) or not JMETER_MEMORY_PATTERN.fullmatch(value):
        raise _validation_error(
            [_field_error(key, "Value must match ^[1-9][0-9]*[KMG]$ with an uppercase unit.")]
        )
    mib = _memory_to_mib(value)
    if mib < 512 or mib > 32 * 1024:
        raise _validation_error([_field_error(key, "Value must be between 512M and 32G.")])
    return value


def _extension_list(value: Any, *, key: str, max_items: int) -> list[str]:
    if isinstance(value, str):
        raw_values = value.split(",")
    elif isinstance(value, list):
        raw_values = value
    else:
        raise _validation_error([_field_error(key, "Value must be an extension list.")])
    normalized: list[str] = []
    for raw in raw_values:
        if not isinstance(raw, str):
            raise _validation_error([_field_error(key, "Extensions must be strings.")])
        extension = raw.strip().lower()
        if not extension:
            continue
        if not extension.startswith("."):
            extension = f".{extension}"
        if not EXTENSION_PATTERN.fullmatch(extension):
            raise _validation_error([_field_error(key, "Extension is invalid.")])
        if extension not in normalized:
            normalized.append(extension)
    if len(normalized) > max_items:
        raise _validation_error([_field_error(key, f"At most {max_items} extensions are allowed.")])
    return normalized


def _load_node_api_base_url(value: Any, *, key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _validation_error([_field_error(key, "Value must be a URL string.")])
    if not value.strip():
        return None
    try:
        return validate_load_node_api_base_url(value)
    except LoadNodeApiBaseUrlInvalid as exc:
        raise _validation_error([_field_error(key, str(exc))]) from exc


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    fallback: Callable[[], Any]
    validator: Callable[[Any], Any]


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


def _settings():
    return get_settings()


def _registry() -> dict[str, SettingDefinition]:
    return {
        ALLOW_SIGNUP: SettingDefinition(
            ALLOW_SIGNUP,
            lambda: _settings().allow_signup,
            lambda value: _as_bool(value, key=ALLOW_SIGNUP),
        ),
        LOAD_SOFT_LIMIT: SettingDefinition(
            LOAD_SOFT_LIMIT,
            lambda: _settings().single_node_concurrency_soft_limit,
            lambda value: _as_int(
                value,
                key=LOAD_SOFT_LIMIT,
                min_value=1,
                max_value=_settings().single_node_concurrency_hard_limit,
            ),
        ),
        JMETER_MEMORY_XMX: SettingDefinition(
            JMETER_MEMORY_XMX,
            lambda: _settings().jmeter_memory_xmx,
            lambda value: _jmeter_memory(value, key=JMETER_MEMORY_XMX),
        ),
        MAX_SCENARIO_ITEMS: SettingDefinition(
            MAX_SCENARIO_ITEMS,
            lambda: _settings().max_scenario_items_per_test_plan,
            lambda value: _as_int(value, key=MAX_SCENARIO_ITEMS, min_value=1, max_value=100),
        ),
        MAX_SLA_RULES: SettingDefinition(
            MAX_SLA_RULES,
            lambda: _settings().max_sla_rules_per_test_plan,
            lambda value: _as_int(value, key=MAX_SLA_RULES, min_value=0, max_value=50),
        ),
        MAX_RUN_DURATION_SECONDS: SettingDefinition(
            MAX_RUN_DURATION_SECONDS,
            lambda: _settings().max_run_duration_seconds,
            lambda value: _as_int(
                value, key=MAX_RUN_DURATION_SECONDS, min_value=60, max_value=604800
            ),
        ),
        MAX_RAMP_UP_SECONDS: SettingDefinition(
            MAX_RAMP_UP_SECONDS,
            lambda: _settings().max_ramp_up_seconds,
            lambda value: _as_int(value, key=MAX_RAMP_UP_SECONDS, min_value=0, max_value=604800),
        ),
        MAX_DELAY_SECONDS: SettingDefinition(
            MAX_DELAY_SECONDS,
            lambda: _settings().max_delay_seconds,
            lambda value: _as_int(value, key=MAX_DELAY_SECONDS, min_value=0, max_value=604800),
        ),
        MAX_ITERATIONS: SettingDefinition(
            MAX_ITERATIONS,
            lambda: _settings().max_iterations,
            lambda value: _as_int(value, key=MAX_ITERATIONS, min_value=1, max_value=10000000),
        ),
        MAX_TARGET_RPS: SettingDefinition(
            MAX_TARGET_RPS,
            lambda: _settings().max_target_rps,
            lambda value: _as_int(value, key=MAX_TARGET_RPS, min_value=1, max_value=1000000),
        ),
        DEPENDENCY_FILE_MAX_BYTES: SettingDefinition(
            DEPENDENCY_FILE_MAX_BYTES,
            lambda: _settings().dependency_file_max_bytes,
            lambda value: _as_int(
                value, key=DEPENDENCY_FILE_MAX_BYTES, min_value=MIB, max_value=GIB
            ),
        ),
        DEPENDENCY_FILE_ALLOWED_EXTENSIONS: SettingDefinition(
            DEPENDENCY_FILE_ALLOWED_EXTENSIONS,
            lambda: _extension_list(
                _settings().dependency_file_allowed_extensions,
                key=DEPENDENCY_FILE_ALLOWED_EXTENSIONS,
                max_items=100,
            ),
            lambda value: _extension_list(
                value, key=DEPENDENCY_FILE_ALLOWED_EXTENSIONS, max_items=100
            ),
        ),
        DEPENDENCY_FILE_PREVIEW_MAX_BYTES: SettingDefinition(
            DEPENDENCY_FILE_PREVIEW_MAX_BYTES,
            lambda: _settings().dependency_file_preview_max_bytes,
            lambda value: _as_int(
                value, key=DEPENDENCY_FILE_PREVIEW_MAX_BYTES, min_value=1024, max_value=5 * MIB
            ),
        ),
        DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS: SettingDefinition(
            DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS,
            lambda: _extension_list(
                _settings().dependency_file_preview_binary_deny_extensions
                or DEFAULT_PREVIEW_BINARY_DENY_EXTENSIONS,
                key=DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS,
                max_items=200,
            ),
            lambda value: _extension_list(
                value, key=DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS, max_items=200
            ),
        ),
        LOAD_NODE_API_BASE_URL: SettingDefinition(
            LOAD_NODE_API_BASE_URL,
            lambda: env_load_node_api_base_url(),
            lambda value: _load_node_api_base_url(value, key=LOAD_NODE_API_BASE_URL),
        ),
    }


def _definition(key: str) -> SettingDefinition:
    return _registry()[key]


def _effective(db: Session, key: str) -> Any:
    definition = _definition(key)
    setting = _get_setting(db, key)
    if setting is None:
        return definition.fallback()
    return definition.validator(setting.value_json)


def _merged_effective_values(db: Session, values: dict[str, Any]) -> dict[str, Any]:
    return {key: values[key] if key in values else _effective(db, key) for key in _registry()}


def _validate_cross_fields(db: Session, values: dict[str, Any]) -> None:
    effective = _merged_effective_values(db, values)
    max_bytes = int(effective[DEPENDENCY_FILE_MAX_BYTES])
    preview_max = int(effective[DEPENDENCY_FILE_PREVIEW_MAX_BYTES])
    if preview_max > max_bytes:
        raise _validation_error(
            [
                _field_error(
                    DEPENDENCY_FILE_PREVIEW_MAX_BYTES,
                    "Preview max bytes must not exceed upload max bytes.",
                )
            ]
        )
    duration_max = int(effective[MAX_RUN_DURATION_SECONDS])
    ramp_up_max = int(effective[MAX_RAMP_UP_SECONDS])
    if ramp_up_max > duration_max:
        raise _validation_error(
            [_field_error(MAX_RAMP_UP_SECONDS, "Ramp-up limit must not exceed duration limit.")]
        )


def effective_allow_signup(db: Session) -> bool:
    return bool(_effective(db, ALLOW_SIGNUP))


def load_soft_limit_warning_concurrency(db: Session) -> int:
    return int(_effective(db, LOAD_SOFT_LIMIT))


def jmeter_memory_xmx(db: Session) -> str:
    return str(_effective(db, JMETER_MEMORY_XMX))


def effective_load_settings(db: Session) -> EffectiveLoadSettings:
    settings = get_settings()
    return EffectiveLoadSettings(
        max_scenario_items_per_test_plan=int(_effective(db, MAX_SCENARIO_ITEMS)),
        single_node_concurrency_soft_limit=int(_effective(db, LOAD_SOFT_LIMIT)),
        single_node_concurrency_hard_limit=settings.single_node_concurrency_hard_limit,
        max_run_duration_seconds=int(_effective(db, MAX_RUN_DURATION_SECONDS)),
        max_ramp_up_seconds=int(_effective(db, MAX_RAMP_UP_SECONDS)),
        max_delay_seconds=int(_effective(db, MAX_DELAY_SECONDS)),
        max_iterations=int(_effective(db, MAX_ITERATIONS)),
        max_target_rps=int(_effective(db, MAX_TARGET_RPS)),
        max_sla_rules_per_test_plan=int(_effective(db, MAX_SLA_RULES)),
    )


def dependency_file_policy(db: Session) -> DependencyFilePolicy:
    return DependencyFilePolicy(
        max_bytes=int(_effective(db, DEPENDENCY_FILE_MAX_BYTES)),
        allowed_extensions=list(_effective(db, DEPENDENCY_FILE_ALLOWED_EXTENSIONS)),
        preview_max_bytes=int(_effective(db, DEPENDENCY_FILE_PREVIEW_MAX_BYTES)),
        preview_binary_deny_extensions=set(
            _effective(db, DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS)
        ),
    )


def current_settings(db: Session) -> SystemSettingsValues:
    return SystemSettingsValues(
        allow_signup=effective_allow_signup(db),
        load_soft_limit_warning_concurrency=load_soft_limit_warning_concurrency(db),
        jmeter_memory_xmx=jmeter_memory_xmx(db),
        max_scenario_items_per_test_plan=int(_effective(db, MAX_SCENARIO_ITEMS)),
        max_sla_rules_per_test_plan=int(_effective(db, MAX_SLA_RULES)),
        max_run_duration_seconds=int(_effective(db, MAX_RUN_DURATION_SECONDS)),
        max_ramp_up_seconds=int(_effective(db, MAX_RAMP_UP_SECONDS)),
        max_delay_seconds=int(_effective(db, MAX_DELAY_SECONDS)),
        max_iterations=int(_effective(db, MAX_ITERATIONS)),
        max_target_rps=int(_effective(db, MAX_TARGET_RPS)),
        dependency_file_max_bytes=int(_effective(db, DEPENDENCY_FILE_MAX_BYTES)),
        dependency_file_allowed_extensions=list(_effective(db, DEPENDENCY_FILE_ALLOWED_EXTENSIONS)),
        dependency_file_preview_max_bytes=int(_effective(db, DEPENDENCY_FILE_PREVIEW_MAX_BYTES)),
        dependency_file_preview_binary_deny_extensions=list(
            _effective(db, DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS)
        ),
        load_node_api_base_url=configured_load_node_api_base_url(db),
    )


def sensitive_status() -> SensitiveStatus:
    settings = get_settings()
    return SensitiveStatus(
        runner_internal_token_configured=bool(settings.runner_internal_token),
        ssh_credential_encryption_key_configured=bool(settings.ssh_credential_encryption_key),
        minio_credentials_configured=bool(settings.minio_access_key and settings.minio_secret_key),
    )


def update_settings(db: Session, *, values: dict[str, Any], actor: User) -> SystemSettingsValues:
    registry = _registry()
    normalized: dict[str, Any] = {}
    for key, value in values.items():
        if is_sensitive_setting_key(key):
            raise AppError(
                "SENSITIVE_SETTING_VALUE_FORBIDDEN",
                "Sensitive settings cannot be edited through this API.",
                400,
            )
        definition = registry.get(key)
        if definition is None:
            raise AppError("SETTING_NOT_EDITABLE", "Setting is not editable.", 400)
        normalized[key] = definition.validator(value)
    _validate_cross_fields(db, normalized)
    now = utc_now()
    for key, value in normalized.items():
        row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        if key == LOAD_NODE_API_BASE_URL and value is None:
            if row is not None:
                db.delete(row)
            continue
        if row is None:
            row = SystemSetting(
                key=key,
                value_json=value,
                updated_by_user_id=actor.id,
                updated_at=now,
            )
            db.add(row)
        else:
            row.value_json = value
            row.updated_by_user_id = actor.id
            row.updated_at = now
    db.flush()
    return current_settings(db)
