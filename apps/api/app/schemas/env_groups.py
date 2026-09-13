from typing import Annotated, Literal

from pydantic import ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema

from app.schemas.common import ApiSchema


def omit_secret_write_default(schema: dict) -> None:
    schema.get("properties", {}).get("value", {}).pop("default", None)


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


class EnvGroupPlainVariableWrite(ApiSchema):
    model_config = ConfigDict(
        alias_generator=ApiSchema.model_config["alias_generator"],
        populate_by_name=True,
        extra="forbid",
    )

    type: Literal["plain"]
    value: str


class EnvGroupSecretVariableWrite(ApiSchema):
    model_config = ConfigDict(
        alias_generator=ApiSchema.model_config["alias_generator"],
        populate_by_name=True,
        extra="forbid",
        json_schema_extra=omit_secret_write_default,
    )

    type: Literal["secret"]
    value: str | SkipJsonSchema[None] = None


EnvGroupVariableWrite = Annotated[
    EnvGroupPlainVariableWrite | EnvGroupSecretVariableWrite, Field(discriminator="type")
]


class EnvGroupPlainVariableRead(ApiSchema):
    type: Literal["plain"]
    value: str


class EnvGroupSecretVariableRead(ApiSchema):
    type: Literal["secret"]
    has_value: bool
    display_value: str


EnvGroupVariableRead = Annotated[
    EnvGroupPlainVariableRead | EnvGroupSecretVariableRead, Field(discriminator="type")
]


class EnvGroupDetail(EnvGroupSummary):
    variables: dict[str, EnvGroupVariableRead]


class EnvGroupListResponse(ApiSchema):
    items: list[EnvGroupSummary]
    page: int
    page_size: int
    total: int


class EnvGroupCreateRequest(ApiSchema):
    name: str
    description: str | None = None
    variables: dict[str, EnvGroupVariableWrite] = Field(default_factory=dict)


class EnvGroupPatchRequest(ApiSchema):
    name: str | None = None
    description: str | None = None
    variables: dict[str, EnvGroupVariableWrite] | None = None


class PublicEnvGroupCreateRequest(ApiSchema):
    name: str
    description: str | None = None
    variables: dict[str, EnvGroupPlainVariableWrite] = Field(default_factory=dict)


class PublicEnvGroupPatchRequest(ApiSchema):
    name: str | None = None
    description: str | None = None
    variables: dict[str, EnvGroupPlainVariableWrite] | None = None


class PublicEnvGroupDetail(EnvGroupSummary):
    variables: dict[str, EnvGroupPlainVariableRead]
