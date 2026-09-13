from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.ids import new_ulid
from app.models.auth import DEFAULT_WORKSPACE_ID, User
from app.models.env_groups import EnvGroup
from app.services.env_groups import (
    EnvGroupReferenceChecker,
    create_env_group,
    duplicate_name_for,
    duplicate_env_group,
    env_group_has_secret_variables,
    normalize_description,
    normalize_name,
    normalize_variables,
    validate_public_variables,
    validate_variables,
)


class FakeNestedSession:
    def begin_nested(self):  # noqa: ANN201
        return self

    def __enter__(self):  # noqa: ANN201
        return None

    def __exit__(self, exc_type, exc, traceback):  # noqa: ANN001, ANN201
        _ = exc_type, exc, traceback
        return False


def test_env_group_name_and_description_validation() -> None:
    assert normalize_name("  Staging  ") == "Staging"
    assert normalize_description("  Staging variables  ") == "Staging variables"
    assert normalize_description("") is None
    assert normalize_description(None) is None

    with pytest.raises(AppError) as empty_name:
        normalize_name("   ")
    assert empty_name.value.code == "VALIDATION_ERROR"
    assert empty_name.value.details == [
        {"field": "name", "code": "INVALID_FIELD", "message": "Name is required."}
    ]

    with pytest.raises(AppError) as long_name:
        normalize_name("a" * 121)
    assert long_name.value.details[0]["field"] == "name"

    with pytest.raises(AppError) as long_description:
        normalize_description("a" * 501)
    assert long_description.value.details[0]["field"] == "description"


def test_variable_validation_rules_and_field_paths() -> None:
    assert validate_variables(
        {
            "BASE_URL": {"type": "plain", "value": "https://example.test"},
            "EMPTY": {"type": "plain", "value": ""},
        }
    ) == {
        "BASE_URL": {"type": "plain", "value": "https://example.test"},
        "EMPTY": {"type": "plain", "value": ""},
    }

    invalid_payload = {
        "bad-key": {"type": "plain", "value": "value"},
        "NUMBER": {"type": "plain", "value": 1},
        "TOO_LONG": {"type": "plain", "value": "x" * 4097},
    }
    with pytest.raises(AppError) as invalid:
        validate_variables(invalid_payload)

    assert invalid.value.code == "VALIDATION_ERROR"
    assert {detail["field"] for detail in invalid.value.details or []} == {
        "variables[bad-key]",
        "variables.NUMBER.value",
        "variables.TOO_LONG.value",
    }

    with pytest.raises(AppError) as too_many:
        validate_variables({f"KEY_{index}": {"type": "plain", "value": ""} for index in range(201)})
    assert too_many.value.details[0]["field"] == "variables"

    with pytest.raises(AppError) as not_object:
        validate_variables(["KEY=value"])
    assert not_object.value.details[0]["field"] == "variables"


def test_typed_variable_validation_rejects_invalid_entry_shapes() -> None:
    with pytest.raises(AppError) as invalid_entries:
        validate_variables(
            {
                "OLD": "legacy-value",
                "TYPE": {"type": "protected", "value": "value"},
                "UNKNOWN": {"type": "secret", "value": "secret-value", "displayValue": "********"},
                "MISSING": {"type": "plain"},
            }
        )

    assert {detail["field"] for detail in invalid_entries.value.details or []} == {
        "variables.OLD",
        "variables.TYPE.type",
        "variables.UNKNOWN.displayValue",
        "variables.MISSING.value",
    }
    assert "secret-value" not in str(invalid_entries.value.details)


def test_secret_preserve_requires_existing_secret_value() -> None:
    with pytest.raises(AppError) as missing_existing_secret:
        normalize_variables(
            {"TOKEN": {"type": "secret"}},
            existing_variables={"TOKEN": {"type": "plain", "value": "plain-value"}},
            allow_secret_preserve=True,
        )

    assert missing_existing_secret.value.details == [
        {
            "field": "variables.TOKEN.value",
            "code": "INVALID_FIELD",
            "message": "Secret variable value is required.",
        }
    ]


def test_public_variable_validation_rejects_secret_and_none_secret_check_is_false() -> None:
    with pytest.raises(AppError) as public_secret:
        validate_public_variables({"TOKEN": {"type": "secret", "value": "secret-value"}})

    assert public_secret.value.details == [
        {
            "field": "variables.TOKEN.type",
            "code": "INVALID_FIELD",
            "message": "Public API supports plain variables only.",
        }
    ]
    assert env_group_has_secret_variables(None) is False


def test_duplicate_name_generation_preserves_prefix_suffix_and_length() -> None:
    assert duplicate_name_for("Staging", set()) == "Copy of Staging"
    assert duplicate_name_for("Staging", {"copy of staging"}) == "Copy of Staging (2)"

    source = "A" * 120
    generated = duplicate_name_for(source, {"copy of " + ("a" * 112)})

    assert generated == f"Copy of {'A' * 108} (2)"
    assert len(generated) == 120


def test_duplicate_env_group_retries_generated_name_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    source = SimpleNamespace(
        name="Staging",
        workspace_id=DEFAULT_WORKSPACE_ID,
        description=None,
        variables={"BASE_URL": {"type": "plain", "value": "https://example.test"}},
    )

    monkeypatch.setattr(
        "app.services.env_groups._existing_lower_names", lambda _db, _workspace_id: set()
    )

    def fake_create_env_group(_db, *, name, **kwargs):  # noqa: ANN001
        _ = kwargs
        calls.append(name)
        if len(calls) == 1:
            raise AppError("ENV_GROUP_NAME_CONFLICT", "Env Group name already exists.", 409)
        return SimpleNamespace(name=name)

    monkeypatch.setattr("app.services.env_groups.create_env_group", fake_create_env_group)

    duplicated = duplicate_env_group(
        FakeNestedSession(),  # type: ignore[arg-type]
        source=source,  # type: ignore[arg-type]
        actor_user_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    )

    assert calls == ["Copy of Staging", "Copy of Staging (2)"]
    assert duplicated.name == "Copy of Staging (2)"


def test_duplicate_env_group_propagates_unexpected_create_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = SimpleNamespace(
        name="Staging",
        workspace_id=DEFAULT_WORKSPACE_ID,
        description=None,
        variables={"BASE_URL": {"type": "plain", "value": "https://example.test"}},
    )

    monkeypatch.setattr(
        "app.services.env_groups._existing_lower_names", lambda _db, _workspace_id: set()
    )

    def fake_create_env_group(_db, *, name, **kwargs):  # noqa: ANN001
        _ = name, kwargs
        raise AppError("VALIDATION_ERROR", "Validation failed.", 422)

    monkeypatch.setattr("app.services.env_groups.create_env_group", fake_create_env_group)

    with pytest.raises(AppError) as exc_info:
        duplicate_env_group(
            FakeNestedSession(),  # type: ignore[arg-type]
            source=source,  # type: ignore[arg-type]
            actor_user_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        )

    assert exc_info.value.code == "VALIDATION_ERROR"


def test_duplicate_env_group_reports_conflict_after_retry_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    source = SimpleNamespace(
        name="Staging",
        workspace_id=DEFAULT_WORKSPACE_ID,
        description=None,
        variables={"BASE_URL": {"type": "plain", "value": "https://example.test"}},
    )

    monkeypatch.setattr(
        "app.services.env_groups._existing_lower_names", lambda _db, _workspace_id: set()
    )

    def fake_create_env_group(_db, *, name, **kwargs):  # noqa: ANN001
        _ = kwargs
        calls.append(name)
        raise AppError("ENV_GROUP_NAME_CONFLICT", "Env Group name already exists.", 409)

    monkeypatch.setattr("app.services.env_groups.create_env_group", fake_create_env_group)

    with pytest.raises(AppError) as exc_info:
        duplicate_env_group(
            FakeNestedSession(),  # type: ignore[arg-type]
            source=source,  # type: ignore[arg-type]
            actor_user_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        )

    assert exc_info.value.code == "ENV_GROUP_NAME_CONFLICT"
    assert len(calls) == 20
    assert calls[-1] == "Copy of Staging (20)"


def test_duplicate_env_group_recovers_from_real_unique_flush_conflict(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.env_groups as service

    now = datetime.now(UTC)
    user = User(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P8A",
        email="duplicate-race@example.com",
        display_name="Duplicate Race User",
        password_hash="hash",
        role="user",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.flush()
    source = create_env_group(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor_user_id=user.id,
        name="Staging",
        description=None,
        variables={},
    )
    original_ensure_name_available = service.ensure_name_available
    inserted_racing_row = False

    def racing_ensure_name_available(
        db: Session,
        *,
        workspace_id: str,
        name: str,
        exclude_env_group_id: str | None = None,
    ) -> None:
        nonlocal inserted_racing_row
        original_ensure_name_available(
            db,
            workspace_id=workspace_id,
            name=name,
            exclude_env_group_id=exclude_env_group_id,
        )
        if name == "Copy of Staging" and not inserted_racing_row:
            inserted_racing_row = True
            db.add(
                EnvGroup(
                    id=new_ulid(),
                    workspace_id=workspace_id,
                    name=name,
                    description=None,
                    variables={},
                    created_by=user.id,
                    updated_by=user.id,
                    created_at=now,
                    updated_at=now,
                )
            )

    monkeypatch.setattr(service, "ensure_name_available", racing_ensure_name_available)

    duplicated = duplicate_env_group(db_session, source=source, actor_user_id=user.id)

    assert duplicated.name == "Copy of Staging (2)"
    assert db_session.is_active is True


def test_reference_checker_is_false_for_p0_01() -> None:
    checker = EnvGroupReferenceChecker()

    assert checker.is_in_use("01HZX3Y9M0E9W7Z6M5QK9S8P7A") is False


def test_reference_checker_passes_workspace_scope_to_test_plan_checker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def fake_test_plan_references_env_group(db, *, workspace_id, env_group_id):  # noqa: ANN001
        captured["db"] = db.name
        captured["workspace_id"] = workspace_id
        captured["env_group_id"] = env_group_id
        return True

    monkeypatch.setattr(
        "app.services.test_plans.test_plan_references_env_group",
        fake_test_plan_references_env_group,
    )

    checker = EnvGroupReferenceChecker(
        SimpleNamespace(name="db"),
        workspace_id="01HZX3Y9M0E9W7Z6M5QK9S8P7W",
    )

    assert checker.is_in_use("01HZX3Y9M0E9W7Z6M5QK9S8P7E") is True
    assert captured == {
        "db": "db",
        "workspace_id": "01HZX3Y9M0E9W7Z6M5QK9S8P7W",
        "env_group_id": "01HZX3Y9M0E9W7Z6M5QK9S8P7E",
    }


def test_case_insensitive_name_uniqueness_is_workspace_scoped(db_session: Session) -> None:
    from app.models.env_groups import EnvGroup
    from app.services.env_groups import create_env_group

    now = datetime.now(UTC)
    user = User(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        email="user@example.com",
        display_name="User",
        password_hash="hash",
        role="user",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.flush()

    created = create_env_group(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor_user_id=user.id,
        name="Staging",
        description=None,
        variables={},
    )
    assert created.name == "Staging"

    with pytest.raises(AppError) as conflict:
        create_env_group(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor_user_id=user.id,
            name="staging",
            description=None,
            variables={},
        )
    assert conflict.value.code == "ENV_GROUP_NAME_CONFLICT"

    assert db_session.query(EnvGroup).count() == 1
