from enum import StrEnum

from app.schemas.common import ApiSchema


class DependencyFilePreviewKind(StrEnum):
    text = "text"
    unsupported = "unsupported"


class DependencyFilePreviewUnavailableReason(StrEnum):
    binary_content = "binary_content"
    decode_failed = "decode_failed"
    storage_unavailable = "storage_unavailable"


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


class DependencyFilePreviewResponse(ApiSchema):
    id: str
    filename: str
    content_type: str | None
    size_bytes: int
    sha256: str
    preview_kind: DependencyFilePreviewKind
    can_preview: bool
    truncated: bool
    max_bytes: int
    text: str | None
    reason: DependencyFilePreviewUnavailableReason | None
