from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.core.ids import is_ulid
from app.schemas.common import ApiSchema

ApiTokenScope = Literal["read", "config:write", "run", "dependency:write"]
ALLOWED_API_TOKEN_SCOPES = {"read", "config:write", "run", "dependency:write"}


class ApiTokenCreateRequest(ApiSchema):
    model_config = ConfigDict(
        alias_generator=ApiSchema.model_config["alias_generator"],
        populate_by_name=True,
        extra="forbid",
    )

    name: str = Field(min_length=1, max_length=120)
    scopes: list[ApiTokenScope] = Field(min_length=1, max_length=4)
    workspace_allowlist: list[str] = Field(min_length=1, max_length=50)
    expires_at: datetime

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Name is required.")
        return trimmed

    @field_validator("workspace_allowlist")
    @classmethod
    def validate_workspace_allowlist(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for workspace_id in value:
            if not is_ulid(workspace_id):
                raise ValueError("Invalid Workspace ID.")
            if workspace_id not in normalized:
                normalized.append(workspace_id)
        if not normalized:
            raise ValueError("At least one Workspace is required.")
        return normalized

    @model_validator(mode="after")
    def validate_unique_scopes(self) -> "ApiTokenCreateRequest":
        if len(set(self.scopes)) != len(self.scopes):
            raise ValueError("Scopes must be distinct.")
        return self


class ApiTokenMetadata(ApiSchema):
    id: str
    public_id: str
    name: str
    scopes: list[ApiTokenScope]
    workspace_allowlist: list[str]
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None


class ApiTokenCreated(ApiTokenMetadata):
    plaintext: str


class ApiTokenCreateResponse(ApiSchema):
    token: ApiTokenCreated


class ApiTokenListResponse(ApiSchema):
    items: list[ApiTokenMetadata]
