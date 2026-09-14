from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUserDep, DbDep
from app.core.errors import AppError
from app.schemas.common import ErrorResponse
from app.services.skill_bundle import SkillBundle, SkillBundleUnavailable


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/account/ai-skill", tags=["account-ai-skill"])
ERROR_RESPONSE = {"model": ErrorResponse}
AI_SKILL_UNAVAILABLE_RESPONSE = {
    "description": "The official AI skill source is not available.",
    "model": ErrorResponse,
    "content": {
        "application/json": {
            "example": {
                "code": "AI_SKILL_SOURCE_NOT_AVAILABLE",
                "message": "AI skill source is not available.",
                "requestId": "01J00000000000000000000000",
            }
        }
    },
}


def _stream_bytes(stream: BytesIO, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
    try:
        while chunk := stream.read(chunk_size):
            yield chunk
    finally:
        stream.close()


@router.get(
    "/download",
    operation_id="downloadPublicApiAiSkill",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Official SurgePilot Public API AI skill source archive.",
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
        },
        401: ERROR_RESPONSE,
        503: AI_SKILL_UNAVAILABLE_RESPONSE,
    },
)
def download_public_api_ai_skill(db: DbDep, _user: CurrentUserDep) -> StreamingResponse:
    db.commit()
    try:
        stream = SkillBundle().build_zip()
    except SkillBundleUnavailable as exc:
        logger.warning("AI skill bundle unavailable: %s", type(exc).__name__)
        raise AppError(
            "AI_SKILL_SOURCE_NOT_AVAILABLE",
            "AI skill source is not available.",
            503,
        ) from exc

    return StreamingResponse(
        _stream_bytes(stream),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="surgepilot-public-api-skill.zip"',
            "Cache-Control": "private, no-store",
        },
    )
