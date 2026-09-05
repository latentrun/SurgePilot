from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def error_payload(
    code: str,
    message: str,
    request_id: str,
    details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message, "requestId": request_id}
    if details is not None:
        payload["details"] = details
    return payload


def error_headers(request: Request, request_id: str) -> dict[str, str]:
    headers = {"x-request-id": request_id, "Cache-Control": "no-store"}
    workspace_id = getattr(request.state, "workspace_id", None)
    if workspace_id:
        headers["x-workspace-id"] = workspace_id
    return headers


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, request_id, exc.details),
        headers=error_headers(request, request_id),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    details = [
        {
            "field": ".".join(str(part) for part in error["loc"] if part != "body"),
            "code": "INVALID_FIELD",
            "message": "Invalid field value.",
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_payload("VALIDATION_ERROR", "Validation failed.", request_id, details),
        headers=error_headers(request, request_id),
    )
