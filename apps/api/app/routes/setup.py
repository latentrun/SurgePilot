from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.schemas.auth import SetupStatusResponse
from app.services.system_settings import effective_allow_signup
from app.services.workspaces import has_default_workspace

router = APIRouter(prefix="/api/v1/setup", tags=["setup"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get(
    "/status",
    operation_id="getSetupStatus",
    response_model=SetupStatusResponse,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
def get_setup_status(db: DbDep) -> SetupStatusResponse:
    user_count = db.scalar(select(func.count(User.id))) or 0
    needs_bootstrap = user_count == 0
    return SetupStatusResponse(
        needs_bootstrap=needs_bootstrap,
        allow_signup=True if needs_bootstrap else effective_allow_signup(db),
        has_default_workspace=has_default_workspace(db),
    )
