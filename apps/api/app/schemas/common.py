from pydantic import BaseModel, ConfigDict
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
