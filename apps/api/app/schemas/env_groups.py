from pydantic import Field

from app.schemas.common import ApiSchema


class EnvGroupSummary(ApiSchema):
    id: str
    name: str
    description: str | None = None
    variable_count: int
    in_use: bool
    created_by: str
    updated_by: str
    created_at: str
    updated_at: str


class EnvGroupDetail(EnvGroupSummary):
    variables: dict[str, str]


class EnvGroupListResponse(ApiSchema):
    items: list[EnvGroupSummary]
    page: int
    page_size: int
    total: int


class EnvGroupCreateRequest(ApiSchema):
    name: str
    description: str | None = None
    variables: dict[str, str] = Field(default_factory=dict)


class EnvGroupPatchRequest(ApiSchema):
    name: str | None = None
    description: str | None = None
    variables: dict[str, str] | None = None
