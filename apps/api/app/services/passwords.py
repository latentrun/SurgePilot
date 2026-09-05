from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, VerifyMismatchError


class PasswordPolicyError(ValueError):
    pass


_password_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19456,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def validate_password(password: str) -> None:
    if len(password) < 10:
        raise PasswordPolicyError("Password must be at least 10 characters.")
    if not any(character.isalpha() for character in password):
        raise PasswordPolicyError("Password must contain at least one letter.")
    if not any(character.isdigit() for character in password):
        raise PasswordPolicyError("Password must contain at least one digit.")


def hash_password(password: str) -> str:
    validate_password(password)
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, Argon2Error):
        return False
