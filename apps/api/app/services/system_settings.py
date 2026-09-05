from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.dependency_files import parse_allowed_extensions


@dataclass(frozen=True)
class DependencyFilePolicy:
    max_bytes: int
    allowed_extensions: list[str]


def effective_allow_signup(db: Session) -> bool:
    return get_settings().allow_signup


def dependency_file_policy(db: Session) -> DependencyFilePolicy:
    settings = get_settings()
    return DependencyFilePolicy(
        max_bytes=settings.dependency_file_max_bytes,
        allowed_extensions=parse_allowed_extensions(settings.dependency_file_allowed_extensions),
    )
