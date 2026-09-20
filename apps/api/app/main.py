from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi

from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.core.config import validate_ssh_credential_encryption_key
from app.core.middleware import request_context_middleware
from app.core.product_version import PRODUCT_VERSION
from app.services.storage import get_storage_client
from app.routes import (
    account_ai_skill,
    account_api_tokens,
    admin,
    api_catalog,
    auth,
    dependency_files,
    env_groups,
    load_nodes,
    monitoring,
    overview,
    public_api,
    runner_internal,
    runs,
    scenarios,
    setup,
    test_plans,
    workspaces,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    validate_ssh_credential_encryption_key()
    yield


app = FastAPI(
    title="SurgePilot API",
    version=PRODUCT_VERSION,
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
app.include_router(account_ai_skill.router)
app.include_router(account_api_tokens.router)
app.include_router(workspaces.router)
app.include_router(env_groups.router)
app.include_router(dependency_files.router)
app.include_router(load_nodes.router)
app.include_router(monitoring.router)
app.include_router(overview.router)
app.include_router(admin.router)
app.include_router(api_catalog.router)
app.include_router(scenarios.router)
app.include_router(test_plans.router)
app.include_router(runs.router)
app.include_router(public_api.router)
app.include_router(runner_internal.router)
app.include_router(monitoring.internal_router)


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
                "listEnvGroups",
                "listDependencyFiles",
                "listTestPlans",
                "getAdminSetupStatus",
                "listWorkspaces",
                "adminListWorkspaces",
                "adminArchiveWorkspace",
                "adminListUsers",
                "adminGetUser",
                "adminReplaceUserWorkspaces",
                "adminGetSystemSettings",
                "listApiCatalogSpecs",
                "listScenarioOpenApiSpecSources",
                "getLoadNodeConnectivitySummary",
                "downloadPublicApiAiSkill",
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
            "ENV_GROUP_SECRET_PUBLIC_COPY_DENIED",
            "INVALID_FILENAME",
            "DEPENDENCY_FILE_NAME_CONFLICT",
            "PAYLOAD_TOO_LARGE",
            "API_SPEC_TOO_LARGE",
            "API_SPEC_PARSE_FAILED",
            "UNSUPPORTED_API_SPEC_FORMAT",
            "API_SPEC_NOT_AVAILABLE",
            "OPENAPI_OPERATION_NOT_FOUND",
            "OPENAPI_OPERATION_UNSUPPORTED",
            "STORAGE_UNAVAILABLE",
            "FILE_IN_USE",
            "LOAD_NODE_PUBLIC_ADMIN_REQUIRED",
            "LOAD_NODE_CONFLICT",
            "LOAD_NODE_BUSY",
            "LOAD_NODE_ACTION_NOT_ALLOWED",
            "LOAD_NODE_UNAVAILABLE",
            "LOAD_NODE_CAPACITY_UNAVAILABLE",
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
            "LOAD_NODE_TAR_MISSING",
            "LOAD_NODE_TAURUS_MISSING",
            "LOAD_NODE_JMETER_MISSING",
            "LOAD_NODE_RUNTIME_ARTIFACT_MISSING",
            "LOAD_NODE_RUNTIME_ARCH_UNSUPPORTED",
            "LOAD_NODE_RUNTIME_UPLOAD_FAILED",
            "LOAD_NODE_RUNTIME_CHECKSUM_FAILED",
            "LOAD_NODE_RUNTIME_EXTRACT_FAILED",
            "LOAD_NODE_RUNTIME_METADATA_INVALID",
            "LOAD_NODE_RUNTIME_BZT_FAILED",
            "LOAD_NODE_RUNTIME_JMETER_FAILED",
            "LOAD_NODE_RUNTIME_PLUGIN_MISSING",
            "LOAD_NODE_RUNTIME_ACTIVATION_FAILED",
            "LOAD_NODE_INIT_FAILED",
            "CREDENTIAL_DECRYPT_FAILED",
            "SCENARIO_REVISION_CONFLICT",
            "INVALID_EXECUTION_PREVIEW_MODE",
            "RUN_CREATION_NOT_ALLOWED",
            "RUN_CONTROL_SSH_HOST_KEY_UNTRUSTED",
            "RUN_CONTROL_SSH_HOST_KEY_CHANGED",
            "RUN_CONTROL_INVALID_API_BASE_URL",
            "RESOURCE_REQUEST_INVALID",
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
            "TEST_PLAN_REVISION_CONFLICT",
            "TEST_PLAN_NOT_RUNNABLE",
            "LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED",
            "WORKSPACE_ARCHIVED",
            "WORKSPACE_NOT_FOUND",
            "WORKSPACE_NAME_CONFLICT",
            "WORKSPACE_LAST_ACTIVE_REQUIRED",
            "USER_NOT_FOUND",
            "USER_EMAIL_CONFLICT",
            "USER_DISABLED",
            "USER_LAST_ACTIVE_ADMIN",
            "USER_WORKSPACE_REQUIRED",
            "SETTING_NOT_EDITABLE",
            "SENSITIVE_SETTING_VALUE_FORBIDDEN",
            "PUBLIC_TOKEN_SCOPE_DENIED",
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
