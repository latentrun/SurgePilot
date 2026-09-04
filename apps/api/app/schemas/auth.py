from typing import Literal

from pydantic import EmailStr, Field

from app.schemas.common import ApiSchema

UserRole = Literal["admin", "user"]
UserStatus = Literal["active"]


class UserSummary(ApiSchema):
    id: str
    email: str
    display_name: str
    role: UserRole
    status: UserStatus


class WorkspaceSummary(ApiSchema):
    id: str
    name: str


class AuthSessionResponse(ApiSchema):
    user: UserSummary
    default_workspace: WorkspaceSummary
    csrf_token: str


class CurrentUserResponse(ApiSchema):
    user: UserSummary
    default_workspace: WorkspaceSummary


class CsrfTokenResponse(ApiSchema):
    csrf_token: str


class SetupStatusResponse(ApiSchema):
    needs_bootstrap: bool
    allow_signup: bool
    has_default_workspace: bool


class RegisterRequest(ApiSchema):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str


class LoginRequest(ApiSchema):
    email: str | None = None
    password: str | None = None
