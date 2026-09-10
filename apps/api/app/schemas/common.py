from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class ApiSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class FieldError(ApiSchema):
    field: str
    code: str
    message: str


class ErrorResponse(ApiSchema):
    code: str
    message: str
    request_id: str
    details: list[FieldError] | None = None


class CloneRequest(ApiSchema):
    model_config = ConfigDict(
        alias_generator=ApiSchema.model_config["alias_generator"],
        populate_by_name=True,
        extra="forbid",
    )

    name: str | None = Field(default=None, min_length=1, max_length=120, pattern=r".*\S.*")

    @field_validator("name")
    @classmethod
    def trim_blank_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


class ExecutionPreviewWarning(ApiSchema):
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=300)
    field: str | None = Field(default=None, max_length=120)
    severity: Literal["info", "warning"]


class ExecutionPreviewResponse(ApiSchema):
    source_type: Literal["test_plan"]
    source_id: str
    source_revision: int
    mode: Literal["debug", "standard"]
    format: Literal["yaml"]
    content: str
    warnings: list[ExecutionPreviewWarning]
