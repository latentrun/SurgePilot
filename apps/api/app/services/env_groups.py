import copy
import re
from typing import Any, Literal, TypedDict

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.ids import new_ulid
from app.core.time import utc_now
from app.models.env_groups import EnvGroup

VARIABLE_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
MAX_VARIABLES = 200
MAX_NAME_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 500
MAX_VARIABLE_VALUE_BYTES = 4096
MASKED_SECRET_DISPLAY_VALUE = "********"

EnvGroupVariableType = Literal["plain", "secret"]


class StoredEnvGroupVariable(TypedDict):
    type: EnvGroupVariableType
    value: str


def field_error(field: str, message: str, code: str = "INVALID_FIELD") -> dict[str, str]:
    return {"field": field, "code": code, "message": message}


def validation_error(details: list[dict[str, str]]) -> AppError:
    return AppError("VALIDATION_ERROR", "Validation failed.", 422, details)


def normalize_name(value: str | None) -> str:
    name = (value or "").strip()
    if not name:
        raise validation_error([field_error("name", "Name is required.")])
    if len(name) > MAX_NAME_LENGTH:
        raise validation_error([field_error("name", "Name must be 120 characters or less.")])
    return name


def normalize_description(value: str | None) -> str | None:
    if value is None:
        return None
    description = value.strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise validation_error(
            [field_error("description", "Description must be 500 characters or less.")]
        )
    return description or None


def variable_field_path(key: str) -> str:
    if VARIABLE_KEY_PATTERN.fullmatch(key):
        return f"variables.{key}"
    return f"variables[{key}]"


def _entry_to_dict(entry: Any) -> dict[str, Any] | None:
    if isinstance(entry, BaseModel):
        return entry.model_dump(exclude_unset=True, by_alias=False)
    if isinstance(entry, dict):
        return dict(entry)
    return None


def _validate_value(value: Any, *, path: str, details: list[dict[str, str]]) -> str | None:
    if not isinstance(value, str):
        details.append(field_error(path, "Variable value must be a string."))
        return None
    if len(value.encode("utf-8")) > MAX_VARIABLE_VALUE_BYTES:
        details.append(field_error(path, "Variable value must be 4096 bytes or less."))
        return None
    return value


def _stored_secret_value(entry: Any) -> str | None:
    if (
        isinstance(entry, dict)
        and entry.get("type") == "secret"
        and isinstance(entry.get("value"), str)
    ):
        return entry["value"]
    return None


def normalize_variables(
    value: Any,
    *,
    existing_variables: dict[str, Any] | None = None,
    allow_secret: bool = True,
    allow_secret_preserve: bool = False,
) -> dict[str, StoredEnvGroupVariable]:
    if value is None:
        raise validation_error([field_error("variables", "Variables are required when present.")])
    if not isinstance(value, dict):
        raise validation_error([field_error("variables", "Variables must be an object.")])
    if len(value) > MAX_VARIABLES:
        raise validation_error(
            [field_error("variables", "Variables must contain at most 200 keys.")]
        )

    details: list[dict[str, str]] = []
    variables: dict[str, StoredEnvGroupVariable] = {}
    existing = existing_variables or {}
    for key, raw_entry in value.items():
        key_text = str(key)
        path = variable_field_path(key_text)
        if not isinstance(key, str) or not VARIABLE_KEY_PATTERN.fullmatch(key):
            details.append(field_error(path, "Variable key is invalid."))
            continue

        entry = _entry_to_dict(raw_entry)
        if entry is None:
            details.append(field_error(path, "Variable entry must be an object."))
            continue
        entry_type = entry.get("type")
        if entry_type not in {"plain", "secret"}:
            details.append(field_error(f"{path}.type", "Variable type must be plain or secret."))
            continue
        if entry_type == "secret" and not allow_secret:
            details.append(field_error(f"{path}.type", "Public API supports plain variables only."))
            continue

        allowed_fields = {"type", "value"}
        unknown = sorted(set(entry) - allowed_fields)
        if unknown:
            details.extend(
                field_error(f"{path}.{field}", "Unknown variable entry field.") for field in unknown
            )
            continue

        if entry_type == "plain":
            if "value" not in entry:
                details.append(field_error(f"{path}.value", "Plain variable value is required."))
                continue
            normalized_value = _validate_value(
                entry.get("value"), path=f"{path}.value", details=details
            )
            if normalized_value is not None:
                variables[key] = {"type": "plain", "value": normalized_value}
            continue

        if "value" in entry:
            normalized_value = _validate_value(
                entry.get("value"), path=f"{path}.value", details=details
            )
            if normalized_value is not None:
                variables[key] = {"type": "secret", "value": normalized_value}
            continue

        preserved_value = _stored_secret_value(existing.get(key))
        if allow_secret_preserve and preserved_value is not None:
            variables[key] = {"type": "secret", "value": preserved_value}
        else:
            details.append(field_error(f"{path}.value", "Secret variable value is required."))

    if details:
        raise validation_error(details)
    return variables


def validate_variables(value: Any) -> dict[str, StoredEnvGroupVariable]:
    return normalize_variables(value)


def validate_public_variables(value: Any) -> dict[str, StoredEnvGroupVariable]:
    return normalize_variables(value, allow_secret=False)


def mask_variables(variables: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key, raw_entry in dict(variables or {}).items():
        entry = raw_entry if isinstance(raw_entry, dict) else {}
        if entry.get("type") == "secret":
            result[str(key)] = {
                "type": "secret",
                "hasValue": isinstance(entry.get("value"), str),
                "displayValue": MASKED_SECRET_DISPLAY_VALUE,
            }
        elif entry.get("type") == "plain" and isinstance(entry.get("value"), str):
            result[str(key)] = {"type": "plain", "value": entry["value"]}
    return result


def public_plain_variables(variables: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for key, raw_entry in dict(variables or {}).items():
        entry = raw_entry if isinstance(raw_entry, dict) else {}
        if entry.get("type") == "plain" and isinstance(entry.get("value"), str):
            result[str(key)] = {"type": "plain", "value": entry["value"]}
    return result


def internal_env_values(variables: dict[str, Any] | None) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, raw_entry in dict(variables or {}).items():
        if isinstance(raw_entry, str):
            # Internal snapshots use a flat env map; this is not a runtime write contract
            # for env_groups.variables after P2-03 migration.
            values[str(key)] = raw_entry
            continue
        entry = raw_entry if isinstance(raw_entry, dict) else {}
        if entry.get("type") in {"plain", "secret"} and isinstance(entry.get("value"), str):
            values[str(key)] = entry["value"]
    return values


def env_group_runtime_values(group: EnvGroup | None) -> dict[str, str]:
    return internal_env_values(group.variables if group is not None else None)


def env_group_has_secret_variables(group: EnvGroup | None) -> bool:
    if group is None:
        return False
    return any(
        isinstance(entry, dict) and entry.get("type") == "secret"
        for entry in dict(group.variables or {}).values()
    )


def reject_public_secret_bearing_group(group: EnvGroup) -> None:
    if env_group_has_secret_variables(group):
        raise validation_error(
            [
                field_error(
                    "variables",
                    "Public API cannot modify Env Groups that contain secret variables.",
                )
            ]
        )


def raise_public_secret_copy_denied() -> None:
    raise AppError(
        "ENV_GROUP_SECRET_PUBLIC_COPY_DENIED",
        "Public API cannot copy Env Groups that contain secret variables.",
        409,
    )


def _raise_name_conflict() -> None:
    raise AppError("ENV_GROUP_NAME_CONFLICT", "Env Group name already exists.", 409)


def ensure_name_available(
    db: Session, *, workspace_id: str, name: str, exclude_env_group_id: str | None = None
) -> None:
    statement = select(EnvGroup.id).where(
        EnvGroup.workspace_id == workspace_id,
        func.lower(EnvGroup.name) == name.lower(),
    )
    if exclude_env_group_id is not None:
        statement = statement.where(EnvGroup.id != exclude_env_group_id)
    if db.scalar(statement) is not None:
        _raise_name_conflict()


def _existing_lower_names(db: Session, workspace_id: str) -> set[str]:
    return {
        name
        for name in db.scalars(
            select(func.lower(EnvGroup.name)).where(EnvGroup.workspace_id == workspace_id)
        )
    }


def duplicate_name_for(source_name: str, existing_lower_names: set[str]) -> str:
    prefix = "Copy of "
    suffix = ""
    number = 1
    while True:
        max_source_length = MAX_NAME_LENGTH - len(prefix) - len(suffix)
        candidate = f"{prefix}{source_name[:max_source_length]}{suffix}"
        if candidate.lower() not in existing_lower_names:
            return candidate
        number += 1
        suffix = f" ({number})"


class EnvGroupReferenceChecker:
    def __init__(self, db: Session | None = None, *, workspace_id: str | None = None) -> None:
        self.db = db
        self.workspace_id = workspace_id

    def is_in_use(self, env_group_id: str) -> bool:
        if self.db is None:
            return False
        if self.workspace_id is None:
            raise ValueError("workspace_id is required when checking Env Group references")
        from app.services.test_plans import test_plan_references_env_group

        return test_plan_references_env_group(
            self.db, workspace_id=self.workspace_id, env_group_id=env_group_id
        )


def create_env_group(
    db: Session,
    *,
    workspace_id: str,
    actor_user_id: str,
    name: str,
    description: str | None,
    variables: Any,
    allow_secret: bool = True,
) -> EnvGroup:
    now = utc_now()
    normalized_name = normalize_name(name)
    ensure_name_available(db, workspace_id=workspace_id, name=normalized_name)
    group = EnvGroup(
        id=new_ulid(),
        workspace_id=workspace_id,
        name=normalized_name,
        description=normalize_description(description),
        variables=normalize_variables(variables, allow_secret=allow_secret),
        created_by=actor_user_id,
        updated_by=actor_user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(group)
    try:
        db.flush()
    except IntegrityError as exc:
        raise _raise_name_conflict() from exc
    return group


def get_env_group(db: Session, *, workspace_id: str, env_group_id: str) -> EnvGroup:
    group = db.scalar(
        select(EnvGroup).where(EnvGroup.id == env_group_id, EnvGroup.workspace_id == workspace_id)
    )
    if group is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    return group


def update_env_group(
    db: Session,
    *,
    group: EnvGroup,
    actor_user_id: str,
    fields: dict[str, Any],
    allow_secret: bool = True,
    allow_secret_preserve: bool = True,
) -> EnvGroup:
    if "name" in fields:
        if fields["name"] is None:
            raise validation_error([field_error("name", "Name cannot be null.")])
        normalized_name = normalize_name(fields["name"])
        ensure_name_available(
            db,
            workspace_id=group.workspace_id,
            name=normalized_name,
            exclude_env_group_id=group.id,
        )
        group.name = normalized_name
    if "description" in fields:
        group.description = normalize_description(fields["description"])
    if "variables" in fields:
        group.variables = normalize_variables(
            fields["variables"],
            existing_variables=group.variables,
            allow_secret=allow_secret,
            allow_secret_preserve=allow_secret_preserve,
        )
    group.updated_by = actor_user_id
    group.updated_at = utc_now()
    try:
        db.flush()
    except IntegrityError as exc:
        raise _raise_name_conflict() from exc
    return group


def duplicate_env_group(
    db: Session,
    *,
    source: EnvGroup,
    actor_user_id: str,
) -> EnvGroup:
    existing_lower_names = _existing_lower_names(db, source.workspace_id)
    for _attempt in range(20):
        name = duplicate_name_for(source.name, existing_lower_names)
        try:
            with db.begin_nested():
                duplicated = create_env_group(
                    db,
                    workspace_id=source.workspace_id,
                    actor_user_id=actor_user_id,
                    name=name,
                    description=source.description,
                    variables=copy.deepcopy(source.variables),
                )
            return duplicated
        except AppError as exc:
            if exc.code != "ENV_GROUP_NAME_CONFLICT":
                raise
            existing_lower_names.add(name.lower())
    _raise_name_conflict()


def delete_env_group(
    db: Session,
    *,
    group: EnvGroup,
    reference_checker: EnvGroupReferenceChecker | None = None,
) -> None:
    checker = reference_checker or EnvGroupReferenceChecker()
    if checker.is_in_use(group.id):
        raise AppError("ENV_GROUP_IN_USE", "Env Group is in use and cannot be deleted.", 409)
    db.delete(group)
    db.flush()
