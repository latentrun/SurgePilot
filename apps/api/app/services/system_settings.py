from sqlalchemy.orm import Session

from app.core.config import get_settings


def effective_allow_signup(db: Session) -> bool:
    return get_settings().allow_signup
