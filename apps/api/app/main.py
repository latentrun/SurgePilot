from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi

from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.core.middleware import request_context_middleware
from app.routes import auth, setup

app = FastAPI(
    title="SurgePilot API",
    version="0.1.0",
    servers=[{"url": "/api"}],
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url=None,
)

app.middleware("http")(request_context_middleware)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)

app.include_router(setup.router)
app.include_router(auth.router)


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title, version=app.version, routes=app.routes, servers=app.servers
    )
    for path_item in openapi_schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            if operation.get("operationId") in {"getSetupStatus"}:
                operation.get("responses", {}).pop("422", None)
            for parameter in operation.get("parameters", []):
                if parameter.get("in") == "header" and parameter.get("name") == "x-csrf-token":
                    parameter["required"] = True
                    parameter["schema"] = {"type": "string", "title": "X-Csrf-Token"}

    schemas = openapi_schema.get("components", {}).get("schemas", {})
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]


@app.get("/api/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
