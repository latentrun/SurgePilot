from app.schemas.common import ApiSchema


class DependencyFileSummary(ApiSchema):
    id: str
    filename: str
    content_type: str | None = None
    size_bytes: int
    sha256: str
    in_use: bool
    created_by: str
    created_at: str


class DependencyFileDetail(DependencyFileSummary):
    pass


class DependencyFileListResponse(ApiSchema):
    items: list[DependencyFileSummary]
    page: int
    page_size: int
    total: int
