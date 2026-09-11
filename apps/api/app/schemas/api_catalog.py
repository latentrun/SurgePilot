from enum import StrEnum

from app.schemas.common import ApiSchema


class ApiCatalogSpecSourceFormat(StrEnum):
    openapi_json = "openapi_json"
    openapi_yaml = "openapi_yaml"
    swagger_json = "swagger_json"
    swagger_yaml = "swagger_yaml"


class ApiCatalogSpecStatus(StrEnum):
    available = "available"
    invalid = "invalid"
    storage_unavailable = "storage_unavailable"


class ApiCatalogSpecSummary(ApiSchema):
    id: str
    name: str
    filename: str
    source_format: ApiCatalogSpecSourceFormat
    document_title: str
    document_version: str
    size_bytes: int
    sha256: str
    status: ApiCatalogSpecStatus
    created_at: str
    updated_at: str


class ApiCatalogSpecResponse(ApiCatalogSpecSummary):
    openapi_version: str
    content_url: str
    validation_message: str | None = None


class ApiCatalogSpecListResponse(ApiSchema):
    items: list[ApiCatalogSpecSummary]
    total: int
    limit: int
    offset: int
