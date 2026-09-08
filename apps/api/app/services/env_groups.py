import copy
import re
from typing import Any

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


def normalize_variables(
    value: Any,
) -> dict[str, str]:
    if value is None:
        raise validation_error([field_error("variables", "Variables are required when present.")])
    if not isinstance(value, dict):
        raise validation_error([field_error("variables", "Variables must be an object.")])
    if len(value) > MAX_VARIABLES:
        raise validation_error(
            [field_error("variables", "Variables must contain at most 200 keys.")]
        )

    details: list[dict[str, str]] = []
    variables: dict[str, str] = {}
    for key, val in value.items():
        key_text = str(key)
        path = variable_field_path(key_text)
        if not isinstance(key, str) or not VARIABLE_KEY_PATTERN.fullmatch(key):
            details.append(field_error(path, "Variable key is invalid."))
            continue

        if not isinstance(val, str):
            details.append(field_error(path, "Variable value must be a string."))
            continue

        if len(val.encode("utf-8")) > MAX_VARIABLE_VALUE_BYTES:
            details.append(field_error(path, "Variable value must be 4096 bytes or less."))
            continue

        variables[key] = val

    if details:
        raise validation_error(details)
    return variables


def validate_variables(value: Any) -> dict[str, str]:
    return normalize_variables(value)


def internal_env_values(variables: dict[str, Any] | None) -> dict[str, str]:
    return {str(k): str(v) for k, v in dict(variables or {}).items() if isinstance(v, str)}


def env_group_runtime_values(group: EnvGroup | None) -> dict[str, str]:
    return internal_env_values(group.variables if group is not None else None)


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
) -> EnvGroup:
    now = utc_now()
    normalized_name = normalize_name(name)
    ensure_name_available(db, workspace_id=workspace_id, name=normalized_name)
    group = EnvGroup(
        id=new_ulid(),
        workspace_id=workspace_id,
        name=normalized_name,
        description=normalize_description(description),
        variables=normalize_variables(variables),
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
        group.variables = normalize_variables(fields["variables"])
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
