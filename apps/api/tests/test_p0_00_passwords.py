import pytest

from app.services.passwords import (
    PasswordPolicyError,
    hash_password,
    validate_password,
    verify_password,
)


def test_argon2id_hash_verifies_and_never_stores_plaintext() -> None:
    password_hash = hash_password("password123")

    assert password_hash.startswith("$argon2id$")
    assert "password123" not in password_hash
    assert verify_password("password123", password_hash)
    assert not verify_password("wrong-password123", password_hash)


@pytest.mark.parametrize("password", ["short1", "passwordonly", "1234567890"])
def test_password_policy_rejects_short_or_missing_required_category(password: str) -> None:
    with pytest.raises(PasswordPolicyError):
        validate_password(password)


def test_password_policy_accepts_minimum_valid_password() -> None:
    validate_password("password123")
