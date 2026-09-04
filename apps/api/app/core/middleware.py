from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.core.ids import new_request_id


async def request_context_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = new_request_id()
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    if request.url.path.startswith("/api/v1/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response
