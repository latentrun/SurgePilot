from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.core.config import validate_ssh_credential_encryption_key
from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.core.middleware import request_context_middleware
from app.routes import (
    auth,
    dependency_files,
    env_groups,
    load_nodes,
    runner_internal,
    runs,
    setup,
)
from app.services.storage import get_storage_client


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    validate_ssh_credential_encryption_key()
    yield


app = FastAPI(
    title="SurgePilot API",
    version="0.1.0",
    servers=[{"url": "/api"}],
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.middleware("http")(request_context_middleware)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)

app.include_router(setup.router)
app.include_router(auth.router)
app.include_router(env_groups.router)
app.include_router(dependency_files.router)
app.include_router(load_nodes.router)
app.include_router(runs.router)
app.include_router(runner_internal.router)


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
            if operation.get("operationId") in {
                "getSetupStatus",
                "listEnvGroups",
                "listDependencyFiles",
            }:
                operation.get("responses", {}).pop("422", None)
            for parameter in operation.get("parameters", []):
                if parameter.get("in") == "header" and parameter.get("name") == "x-csrf-token":
                    parameter["required"] = True
                    parameter["schema"] = {"type": "string", "title": "X-Csrf-Token"}

    openapi_schema.setdefault("info", {}).setdefault("x-surgepilot-error-codes", []).extend(
        [
            "ENV_GROUP_NAME_CONFLICT",
            "ENV_GROUP_IN_USE",
            "INVALID_FILENAME",
            "DEPENDENCY_FILE_NAME_CONFLICT",
            "PAYLOAD_TOO_LARGE",
            "STORAGE_UNAVAILABLE",
            "FILE_IN_USE",
            "LOAD_NODE_PUBLIC_ADMIN_REQUIRED",
            "LOAD_NODE_CONFLICT",
            "LOAD_NODE_BUSY",
            "LOAD_NODE_ACTION_NOT_ALLOWED",
            "LOAD_NODE_CREDENTIAL_REQUIRED",
            "LOAD_NODE_CREDENTIAL_INVALID",
            "LOAD_NODE_HOST_INVALID",
            "LOAD_NODE_RUNNER_HOME_INVALID",
            "LOAD_NODE_SSH_TIMEOUT",
            "LOAD_NODE_SSH_AUTH_FAILED",
            "LOAD_NODE_SSH_HOST_KEY_SCAN_FAILED",
            "LOAD_NODE_SSH_HOST_KEY_MISMATCH",
            "LOAD_NODE_SSH_HOST_KEY_UNTRUSTED",
            "LOAD_NODE_SSH_HOST_KEY_CHANGED",
            "LOAD_NODE_SSH_UNREACHABLE",
            "LOAD_NODE_RUNNER_HOME_UNWRITABLE",
            "LOAD_NODE_PYTHON_MISSING",
            "LOAD_NODE_JAVA_MISSING",
            "LOAD_NODE_TAURUS_MISSING",
            "LOAD_NODE_JMETER_MISSING",
            "LOAD_NODE_INIT_FAILED",
            "CREDENTIAL_DECRYPT_FAILED",
            "RUN_STOP_NOT_ALLOWED",
            "RUN_TERMINAL_STATE",
            "RUNNER_UNAUTHORIZED",
            "RUNNER_FORBIDDEN",
            "RUNNER_CALLBACK_INVALID",
            "RUNNER_CALLBACK_CONFLICT",
            "INVALID_ARTIFACT_PATH",
            "INVALID_ARTIFACT_TYPE",
            "ARTIFACT_SIZE_MISMATCH",
            "ARTIFACT_HASH_MISMATCH",
            "ARTIFACT_PATH_CONFLICT",
            "ARTIFACT_NOT_READY",
            "RUN_CONTROL_CONFLICT",
        ]
    )
    schemas = openapi_schema.get("components", {}).get("schemas", {})
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]


@app.get("/api/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/readyz", include_in_schema=False)
async def readyz() -> JSONResponse:
    if not get_storage_client().health_check():
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return JSONResponse(status_code=200, content={"status": "ready"})
