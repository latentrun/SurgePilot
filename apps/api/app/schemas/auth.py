from datetime import datetime
from typing import Any, Literal

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import ApiSchema

UserRole = Literal["admin", "user"]
UserStatus = Literal["active", "disabled"]
WorkspaceStatus = Literal["active", "archived"]


class UserSummary(ApiSchema):
    id: str
    email: str
    display_name: str
    role: UserRole
    status: UserStatus


class WorkspaceSummary(ApiSchema):
    id: str
    name: str
    status: WorkspaceStatus = "active"
    archived_at: datetime | None = None


class WorkspaceMembershipSummary(ApiSchema):
    kind: Literal["member", "admin_access"]
    joined_at: datetime | None = None


class AvailableWorkspaceSummary(WorkspaceSummary):
    membership: WorkspaceMembershipSummary


class PermissionSummary(ApiSchema):
    can_manage_workspaces: bool
    can_manage_users: bool
    can_manage_system_settings: bool
    can_view_setup_status: bool


class SessionContextResponse(ApiSchema):
    user: UserSummary
    current_workspace: WorkspaceSummary
    available_workspaces: list[AvailableWorkspaceSummary]
    permissions: PermissionSummary
    default_workspace: WorkspaceSummary


class AuthSessionResponse(SessionContextResponse):
    csrf_token: str


class CurrentUserResponse(SessionContextResponse):
    pass


class CsrfTokenResponse(ApiSchema):
    csrf_token: str


class SetupStatusResponse(ApiSchema):
    needs_bootstrap: bool
    allow_signup: bool
    has_default_workspace: bool


class SensitiveStatus(ApiSchema):
    runner_internal_token_configured: bool
    ssh_credential_encryption_key_configured: bool
    minio_credentials_configured: bool


class WorkspaceSwitchRequest(ApiSchema):
    workspace_id: str


class WorkspaceWriteRequest(ApiSchema):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Workspace name is required.")
        return trimmed


class WorkspaceEnvelope(ApiSchema):
    workspace: WorkspaceSummary


class WorkspaceListResponse(ApiSchema):
    workspaces: list[WorkspaceSummary]


class AdminWorkspaceListResponse(ApiSchema):
    workspaces: list[WorkspaceSummary]


class AdminUserCreateRequest(ApiSchema):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    role: UserRole
    status: UserStatus = "active"
    password: str
    workspace_ids: list[str] = Field(default_factory=list)


class AdminUserPatchRequest(ApiSchema):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: UserRole | None = None
    status: UserStatus | None = None


class ResetPasswordRequest(ApiSchema):
    new_password: str


class MembershipReplaceRequest(ApiSchema):
    workspace_ids: list[str]


class AdminUserSummary(UserSummary):
    disabled_at: datetime | None = None
    workspace_ids: list[str] = Field(default_factory=list)


class AdminUserEnvelope(ApiSchema):
    user: AdminUserSummary


class AdminUserListResponse(ApiSchema):
    users: list[AdminUserSummary]


class SystemSettingsValues(ApiSchema):
    allow_signup: bool
    load_soft_limit_warning_concurrency: int
    jmeter_memory_xmx: str
    max_scenario_items_per_test_plan: int
    max_sla_rules_per_test_plan: int
    max_run_duration_seconds: int
    max_ramp_up_seconds: int
    max_delay_seconds: int
    max_iterations: int
    max_target_rps: int
    dependency_file_max_bytes: int
    dependency_file_allowed_extensions: list[str]
    dependency_file_preview_max_bytes: int
    dependency_file_preview_binary_deny_extensions: list[str]
    load_node_api_base_url: str | None = None


class SystemSettingsResponse(ApiSchema):
    settings: SystemSettingsValues
    sensitive_status: SensitiveStatus


class SystemSettingsPatchRequest(ApiSchema):
    allow_signup: bool | None = Field(default=None, examples=[False])
    load_soft_limit_warning_concurrency: int | None = Field(default=None, ge=1, examples=[1000])
    jmeter_memory_xmx: str | None = Field(default=None, pattern=r"^[1-9][0-9]*[KMG]$", examples=["4G"])
    max_scenario_items_per_test_plan: int | None = Field(default=None, ge=1, le=100, examples=[20])
    max_sla_rules_per_test_plan: int | None = Field(default=None, ge=0, le=50, examples=[5])
    max_run_duration_seconds: int | None = Field(default=None, ge=60, le=604800, examples=[86400])
    max_ramp_up_seconds: int | None = Field(default=None, ge=0, le=604800, examples=[300])
    max_delay_seconds: int | None = Field(default=None, ge=0, le=604800, examples=[0])
    max_iterations: int | None = Field(default=None, ge=1, le=10000000, examples=[1000000])
    max_target_rps: int | None = Field(default=None, ge=1, le=1000000, examples=[100000])
    dependency_file_max_bytes: int | None = Field(default=None, ge=1048576, le=1073741824, examples=[104857600])
    dependency_file_allowed_extensions: list[str] | str | None = Field(default=None, examples=[[".csv", ".txt"]])
    dependency_file_preview_max_bytes: int | None = Field(default=None, ge=1024, le=5242880, examples=[65536])
    dependency_file_preview_binary_deny_extensions: list[str] | str | None = Field(default=None, examples=[[".png", ".zip"]])
    load_node_api_base_url: str | None = Field(default=None, examples=["http://192.168.1.50:8080"])

    model_config = ApiSchema.model_config | {"extra": "allow", "json_schema_extra": {"additionalProperties": False}}

    def extra_values(self) -> dict[str, Any]:
        return dict(self.__pydantic_extra__ or {})


class RegisterRequest(ApiSchema):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str


class LoginRequest(ApiSchema):
    email: str | None = None
    password: str | None = None
