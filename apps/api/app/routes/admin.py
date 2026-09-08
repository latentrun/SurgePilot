from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUserDep, DbDep
from app.core.errors import AppError
from app.models.auth import User
from app.schemas.auth import SetupStatusResponse
from app.schemas.common import ErrorResponse
from app.services.system_settings import effective_allow_signup
from app.services.workspaces import has_default_workspace

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
ERROR_RESPONSE = {"model": ErrorResponse}


def require_admin(user: User) -> None:
    if user.role != "admin":
        raise AppError("FORBIDDEN", "Admin access is required.", 403)


@router.get(
    "/setup-status",
    operation_id="getAdminSetupStatus",
    response_model=SetupStatusResponse,
    response_model_by_alias=True,
    response_model_exclude_none=True,
    responses={401: ERROR_RESPONSE, 403: ERROR_RESPONSE},
)
def get_admin_setup_status(db: DbDep, user: CurrentUserDep) -> SetupStatusResponse:
    require_admin(user)
    user_count = db.scalar(select(func.count(User.id))) or 0
    needs_bootstrap = user_count == 0
    return SetupStatusResponse(
        needs_bootstrap=needs_bootstrap,
        allow_signup=True if needs_bootstrap else effective_allow_signup(db),
        has_default_workspace=has_default_workspace(db),
    )
