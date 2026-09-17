from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
import json
from threading import Barrier
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.api_catalog import ApiCatalogSpec
from app.models.auth import Workspace, WorkspaceMember
from app.models.scenarios import Scenario
from app.schemas.scenarios import (
    OpenApiGeneratedStepDraft,
    OpenApiOperationRef,
    OpenApiStepDraftGenerateRequest,
)
from app.services import openapi_step_generation as osg
from app.services.storage import PutResult, StorageClient, StoredObjectStream


class FakeStorage(StorageClient):
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, str | None]] = {}
        self.fail_get = False
        self.get_calls = 0

    def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):
        data = stream.read()
        self.objects[(bucket, object_key)] = (data, content_type)
        return PutResult(size_bytes=len(data), sha256=sha256(data).hexdigest())

    def get_stream(self, *, bucket, object_key):
        self.get_calls += 1
        if self.fail_get or (bucket, object_key) not in self.objects:
            from app.services.storage import StorageError

            raise StorageError()
        payload, content_type = self.objects[(bucket, object_key)]
        return StoredObjectStream(
            content_type=content_type,
            size_bytes=len(payload),
            stream=BytesIO(payload),
        )

    def delete_object_best_effort(self, *, bucket, object_key):
        self.objects.pop((bucket, object_key), None)

    def copy_object(self, *, bucket, source_key, destination_key):
        self.objects[(bucket, destination_key)] = self.objects[(bucket, source_key)]

    def health_check(self):
        return True


@pytest.fixture()
def fake_storage(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    from app.routes import api_catalog, scenarios

    storage = FakeStorage()
    monkeypatch.setattr(
        osg,
        "_PARSED_DOCUMENT_CACHE",
        osg.ParsedOpenApiDocumentCache(capacity=osg.PARSED_DOCUMENT_CACHE_CAPACITY),
    )
    monkeypatch.setattr(api_catalog, "get_storage_client", lambda: storage)
    monkeypatch.setattr(scenarios, "get_storage_client", lambda: storage)
    return storage


async def register(client: AsyncClient, email: str = "openapi-generation@example.com"):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": "OpenAPI User", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["csrfToken"], body["defaultWorkspace"]["id"], body["user"]["id"]


def scenario_payload(name: str = "Orders flow") -> dict:
    return {
        "name": name,
        "description": None,
        "tags": [],
        "baseUrlExpression": "${base_url}",
        "defaultSettings": {
            "thinkTimeMs": 0,
            "timeoutMs": 30000,
            "followRedirects": True,
            "keepAlive": True,
            "storeCache": True,
            "storeCookie": True,
            "retrieveResources": False,
        },
        "dataSources": [],
        "steps": [
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
                "enabled": True,
                "name": "Existing step",
                "method": "GET",
                "path": "/health",
                "queryParams": [],
                "headers": [],
                "body": {"type": "none", "contentType": None, "rawText": None, "formFields": []},
                "uploadFiles": [],
                "extractors": [],
                "assertions": [],
                "scripts": [],
                "settings": {
                    "thinkTimeMs": None,
                    "timeoutMs": None,
                    "followRedirects": None,
                    "keepAlive": None,
                },
            }
        ],
    }


OPENAPI_31 = {
    "openapi": "3.1.0",
    "info": {"title": "Orders API", "version": "1.0.0"},
    "paths": {
        "/orders/{orderId}": {
            "get": {
                "operationId": "getOrder",
                "summary": "Get one order",
                "tags": ["orders"],
                "responses": {"200": {"description": "OK"}},
                "parameters": [
                    {
                        "name": "orderId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "include",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string", "default": "items"},
                    },
                    {
                        "name": "traceId",
                        "in": "header",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "Authorization",
                        "in": "header",
                        "required": True,
                        "schema": {"type": "string", "example": "Bearer secret"},
                    },
                ],
            }
        },
        "/orders": {
            "post": {
                "operationId": "createOrder",
                "summary": "Create order",
                "tags": ["orders"],
                "responses": {"201": {"description": "Created"}},
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["sku", "quantity"],
                                "properties": {
                                    "sku": {"type": "string", "example": "SKU-1"},
                                    "quantity": {"type": "integer", "minimum": 1},
                                    "note": {"type": "string"},
                                },
                            }
                        }
                    },
                },
            }
        },
    },
}

SWAGGER_20 = {
    "swagger": "2.0",
    "info": {"title": "Legacy API", "version": "1.0"},
    "paths": {
        "/legacy": {
            "post": {
                "operationId": "createLegacy",
                "responses": {"200": {"description": "OK"}},
                "parameters": [
                    {
                        "name": "payload",
                        "in": "body",
                        "required": True,
                        "schema": {
                            "type": "object",
                            "properties": {"name": {"type": "string", "default": "demo"}},
                        },
                    }
                ],
            }
        }
    },
}

REMOTE_REF_OPENAPI = {
    "openapi": "3.1.0",
    "info": {"title": "Remote Ref API", "version": "1.0.0"},
    "paths": {
        "/remote": {
            "post": {
                "operationId": "createRemote",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "https://example.invalid/schema.json"}
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "https://example.invalid/schema.json"}
                            }
                        },
                    }
                },
            }
        }
    },
}


def seed_spec(
    db_session: Session,
    fake_storage: FakeStorage,
    *,
    workspace_id: str,
    spec_id: str,
    document: dict,
    filename: str = "orders.json",
    status: str = "available",
) -> ApiCatalogSpec:
    payload = json.dumps(document).encode("utf-8")
    object_key = f"api-catalog-specs/{workspace_id}/{spec_id}/{filename}"
    fake_storage.objects[("surgepilot", object_key)] = (payload, "application/json")
    now = datetime.now(UTC)
    spec = ApiCatalogSpec(
        id=spec_id,
        workspace_id=workspace_id,
        name=document["info"]["title"],
        filename=filename,
        content_type="application/json",
        source_format="swagger_json" if "swagger" in document else "openapi_json",
        openapi_version=str(document.get("openapi") or document.get("swagger")),
        document_title=document["info"]["title"],
        document_version=str(document["info"].get("version") or "unknown"),
        size_bytes=len(payload),
        sha256=sha256(payload).hexdigest(),
        status=status,
        validation_message=None,
        storage_bucket="surgepilot",
        storage_object_key=object_key,
        created_by="01HZX3Y9M0E9W7Z6M5QK9S8P7U",
        created_at=now,
        updated_at=now,
    )
    db_session.add(spec)
    db_session.flush()
    return spec


@pytest.mark.anyio
async def test_openapi_step_generation_lists_specs_operations_and_ordered_drafts(
    client: AsyncClient, db_session: Session, fake_storage: FakeStorage
) -> None:
    csrf, workspace_id, user_id = await register(client)
    created = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    assert created.status_code == 201
    scenario_id = created.json()["id"]
    spec = seed_spec(
        db_session,
        fake_storage,
        workspace_id=workspace_id,
        spec_id="01HZX3Y9M0E9W7Z6M5QK9S8P7S",
        document=OPENAPI_31,
    )
    seed_spec(
        db_session,
        fake_storage,
        workspace_id=workspace_id,
        spec_id="01HZX3Y9M0E9W7Z6M5QK9S8P7W",
        document=SWAGGER_20,
        filename="invalid.json",
        status="invalid",
    )

    specs = await client.get(
        f"/api/v1/scenarios/{scenario_id}/openapi-step-generation/specs",
        headers={"x-workspace-id": workspace_id},
    )
    assert specs.status_code == 200
    assert specs.headers["x-workspace-id"] == workspace_id
    assert specs.json()["total"] == 1
    assert specs.json()["items"] == [
        {
            "id": spec.id,
            "name": "Orders API",
            "filename": "orders.json",
            "sourceFormat": "openapi_json",
            "documentTitle": "Orders API",
            "documentVersion": "1.0.0",
            "status": "available",
            "updatedAt": spec.updated_at.isoformat().replace("+00:00", "Z"),
        }
    ]

    operations = await client.get(
        f"/api/v1/scenarios/{scenario_id}/openapi-step-generation/specs/{spec.id}/operations",
        headers={"x-workspace-id": workspace_id},
    )
    assert operations.status_code == 200
    operation_body = operations.json()
    assert [item["displayName"] for item in operation_body["items"]] == [
        "Get one order",
        "Create order",
    ]
    assert operation_body["items"][0]["ref"] == {
        "method": "GET",
        "path": "/orders/{orderId}",
        "operationId": "getOrder",
    }

    drafts = await client.post(
        f"/api/v1/scenarios/{scenario_id}/openapi-step-generation/drafts",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "specId": spec.id,
            "operationRefs": [
                {"method": "POST", "path": "/orders", "operationId": "createOrder"},
                {"method": "GET", "path": "/orders/{orderId}", "operationId": "getOrder"},
            ],
            "insert": {"mode": "after_step", "stepId": "01HZX3Y9M0E9W7Z6M5QK9S8P7D"},
        },
    )
    assert drafts.status_code == 200
    body = drafts.json()
    assert body["insert"] == {"mode": "after_step", "stepId": "01HZX3Y9M0E9W7Z6M5QK9S8P7D"}
    assert [item["operationRef"]["operationId"] for item in body["items"]] == [
        "createOrder",
        "getOrder",
    ]
    created_step = body["items"][0]["step"]
    assert created_step["name"] == "Create order"
    assert created_step["method"] == "POST"
    assert created_step["path"] == "/orders"
    assert created_step["body"]["type"] == "raw"
    assert created_step["body"]["contentType"] == "application/json"
    assert json.loads(created_step["body"]["rawText"]) == {
        "sku": "SKU-1",
        "quantity": 1,
        "note": "string",
    }
    assert "id" not in created_step
    get_step = body["items"][1]["step"]
    assert get_step["path"] == "/orders/${orderId}"
    assert get_step["queryParams"] == [{"name": "include", "value": "items", "enabled": True}]
    assert get_step["headers"] == [{"name": "traceId", "value": "${traceId}", "enabled": True}]
    warning_codes = {warning["code"] for item in body["items"] for warning in item["warnings"]}
    assert "PATH_VARIABLE_PLACEHOLDER_REQUIRED" in warning_codes
    assert "HEADER_PARAMETER_PLACEHOLDER_REQUIRED" in warning_codes
    assert "AUTH_HEADER_NOT_GENERATED" in warning_codes

    db_session.expire_all()
    unchanged = db_session.scalar(select(Scenario).where(Scenario.id == scenario_id))
    assert unchanged is not None
    assert len(unchanged.steps_json) == 1
    assert unchanged.steps_json[0]["name"] == "Existing step"


@pytest.mark.anyio
async def test_openapi_step_generation_enforces_workspace_csrf_and_safe_errors(
    client: AsyncClient, db_session: Session, fake_storage: FakeStorage
) -> None:
    csrf, workspace_id, user_id = await register(client, "openapi-generation-security@example.com")
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    assert scenario.status_code == 201
    scenario_id = scenario.json()["id"]
    other_workspace = Workspace(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        name="Other Workspace",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(other_workspace)
    db_session.add(
        WorkspaceMember(
            workspace_id=other_workspace.id, user_id=user_id, joined_at=datetime.now(UTC)
        )
    )
    other_spec = seed_spec(
        db_session,
        fake_storage,
        workspace_id=other_workspace.id,
        spec_id="01HZX3Y9M0E9W7Z6M5QK9S8P7T",
        document=OPENAPI_31,
        filename="other.json",
    )
    spec = seed_spec(
        db_session,
        fake_storage,
        workspace_id=workspace_id,
        spec_id="01HZX3Y9M0E9W7Z6M5QK9S8P7V",
        document=SWAGGER_20,
        filename="legacy.json",
    )

    cross = await client.get(
        f"/api/v1/scenarios/{scenario_id}/openapi-step-generation/specs/{other_spec.id}/operations",
        headers={"x-workspace-id": workspace_id},
    )
    assert cross.status_code == 404
    assert cross.json()["code"] == "RESOURCE_NOT_FOUND"
    assert "api-catalog-specs" not in cross.text

    no_csrf = await client.post(
        f"/api/v1/scenarios/{scenario_id}/openapi-step-generation/drafts",
        headers={"x-workspace-id": workspace_id},
        json={
            "specId": spec.id,
            "operationRefs": [{"method": "POST", "path": "/legacy", "operationId": "createLegacy"}],
            "insert": {"mode": "append"},
        },
    )
    assert no_csrf.status_code == 403
    assert no_csrf.json()["code"] == "CSRF_TOKEN_REQUIRED"

    duplicate = await client.post(
        f"/api/v1/scenarios/{scenario_id}/openapi-step-generation/drafts",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "specId": spec.id,
            "operationRefs": [
                {"method": "POST", "path": "/legacy", "operationId": "createLegacy"},
                {"method": "POST", "path": "/legacy", "operationId": "createLegacy"},
            ],
            "insert": {"mode": "append"},
        },
    )
    assert duplicate.status_code == 422
    assert duplicate.json()["code"] == "VALIDATION_ERROR"

    swagger_draft = await client.post(
        f"/api/v1/scenarios/{scenario_id}/openapi-step-generation/drafts",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "specId": spec.id,
            "operationRefs": [{"method": "POST", "path": "/legacy", "operationId": "createLegacy"}],
            "insert": {"mode": "append"},
        },
    )
    assert swagger_draft.status_code == 200
    assert json.loads(swagger_draft.json()["items"][0]["step"]["body"]["rawText"]) == {
        "name": "demo"
    }

    cached_but_wrong_workspace = await client.get(
        f"/api/v1/scenarios/{scenario_id}/openapi-step-generation/specs/{spec.id}/operations",
        headers={"x-workspace-id": other_workspace.id},
    )
    assert cached_but_wrong_workspace.status_code == 404
    assert cached_but_wrong_workspace.json()["code"] == "RESOURCE_NOT_FOUND"

    spec.sha256 = "f" * 64
    db_session.flush()
    fake_storage.fail_get = True
    outage = await client.get(
        f"/api/v1/scenarios/{scenario_id}/openapi-step-generation/specs/{spec.id}/operations",
        headers={"x-workspace-id": workspace_id},
    )
    assert outage.status_code == 503
    assert outage.json()["code"] == "STORAGE_UNAVAILABLE"
    assert "api-catalog-specs" not in outage.text


@pytest.mark.anyio
async def test_openapi_step_generation_rejects_remote_refs_without_fetching(
    client: AsyncClient,
    db_session: Session,
    fake_storage: FakeStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import jsonschema_path.handlers.urllib as urllib_handler

    csrf, workspace_id, _user_id = await register(client, "openapi-remote-ref@example.com")
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload("Remote ref scenario"),
    )
    assert scenario.status_code == 201
    scenario_id = scenario.json()["id"]
    spec = seed_spec(
        db_session,
        fake_storage,
        workspace_id=workspace_id,
        spec_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        document=REMOTE_REF_OPENAPI,
        filename="remote-ref.json",
    )

    urlopen_calls = 0

    def fail_urlopen(*_args, **_kwargs):
        nonlocal urlopen_calls
        urlopen_calls += 1
        raise AssertionError("Remote references must not be fetched.")

    monkeypatch.setattr(urllib_handler, "urlopen", fail_urlopen)

    response = await client.get(
        f"/api/v1/scenarios/{scenario_id}/openapi-step-generation/specs/{spec.id}/operations",
        headers={"x-workspace-id": workspace_id},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "API_SPEC_PARSE_FAILED"
    assert urlopen_calls == 0


def test_openapi_step_generation_service_edge_cases(fake_storage: FakeStorage) -> None:
    yaml_spec = SimpleNamespace(source_format="openapi_yaml")
    assert (
        osg.load_payload(
            b"openapi: 3.0.3\ninfo:\n  title: Edge\n  version: '1'\npaths: {}\n",
            spec=yaml_spec,
        )["openapi"]
        == "3.0.3"
    )
    with pytest.raises(AppError, match="API_SPEC_PARSE_FAILED"):
        osg.load_payload(b"openapi: [", spec=yaml_spec)
    with pytest.raises(AppError, match="UNSUPPORTED_API_SPEC_FORMAT"):
        osg.load_payload(b"[]", spec=yaml_spec)
    with pytest.raises(AppError, match="UNSUPPORTED_API_SPEC_FORMAT"):
        osg.validate_document({"info": {"title": "Missing root", "version": "1"}, "paths": {}})
    with pytest.raises(AppError, match="UNSUPPORTED_API_SPEC_FORMAT"):
        osg.validate_document({"openapi": 3.1, "info": {"title": "Bad", "version": "1"}})
    with pytest.raises(AppError, match="UNSUPPORTED_API_SPEC_FORMAT"):
        osg.validate_document({"openapi": "3.2.0", "info": {"title": "Bad", "version": "1"}})
    with pytest.raises(AppError, match="API_SPEC_PARSE_FAILED"):
        osg.validate_document({"openapi": "3.1.0", "paths": {}})
    with pytest.raises(AppError, match="API_SPEC_NOT_AVAILABLE"):
        osg.parse_authorized_spec(SimpleNamespace(status="invalid"), storage=fake_storage)

    assert osg.safe_text(42) == "42"
    empty_paths = osg.ParsedOpenApiDocument(
        document={"paths": []}, version="3.1.0", root_kind="openapi"
    )
    assert osg.enumerate_operations(empty_paths) == ([], [])
    assert osg.resolve_local_ref({}, {"$ref": "https://example.invalid/schema.json"}) == {
        "$ref": "https://example.invalid/schema.json"
    }
    assert osg.resolve_local_ref({"components": {}}, {"$ref": "#/components/missing"}) == {
        "$ref": "#/components/missing"
    }


def test_openapi_step_generation_mapping_edge_cases() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Mapping", "version": "1"},
        "components": {
            "parameters": {
                "PathTrace": {
                    "name": "trace",
                    "in": "header",
                    "required": True,
                    "schema": {"type": "string", "example": "trace-1"},
                }
            },
            "securitySchemes": {
                "HeaderKey": {"type": "apiKey", "in": "header", "name": "X-Api-Key"},
                "BearerAuth": {"type": "http", "scheme": "bearer"},
                "QueryKey": {"type": "apiKey", "in": "query", "name": "api_key"},
            },
        },
        "paths": {
            "/edge": {
                "parameters": [{"$ref": "#/components/parameters/PathTrace"}],
                "post": {
                    "operationId": "edge",
                    "parameters": [
                        {
                            "name": "requiredQuery",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "optionalQuery",
                            "in": "query",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "ids",
                            "in": "query",
                            "required": True,
                            "style": "form",
                            "explode": True,
                            "schema": {"type": "array", "items": {"type": "string"}},
                        },
                        {
                            "name": "filter",
                            "in": "query",
                            "style": "deepObject",
                            "explode": True,
                            "schema": {
                                "type": "object",
                                "properties": {"status": {"type": "string"}},
                            },
                        },
                        {
                            "name": "Accept",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string", "example": "application/json"},
                        },
                        {
                            "name": "optionalHeader",
                            "in": "header",
                            "schema": {"type": "string"},
                        },
                    ],
                    "requestBody": {"content": {"text/plain": {"schema": {"type": "string"}}}},
                    "security": [
                        {"HeaderKey": []},
                        {"BearerAuth": []},
                        {"QueryKey": []},
                    ],
                    "responses": {"200": {"description": "OK"}},
                },
            }
        },
    }
    parsed = osg.ParsedOpenApiDocument(document=document, version="3.1.0", root_kind="openapi")
    ref = OpenApiOperationRef(method="POST", path="/edge", operationId="edge")
    located = osg.locate_operation(parsed, ref, 0)

    query, headers, warnings = osg.map_query_and_headers(parsed, located)
    assert [item.model_dump(by_alias=True) for item in query] == [
        {"name": "requiredQuery", "value": "${requiredQuery}", "enabled": True}
    ]
    assert [item.model_dump(by_alias=True) for item in headers] == [
        {"name": "trace", "value": "trace-1", "enabled": True}
    ]
    assert {
        "QUERY_PARAMETER_PLACEHOLDER_REQUIRED",
        "OPTIONAL_PARAMETER_SKIPPED",
        "UNSUPPORTED_PARAMETER_STYLE",
    }.issubset({warning.code for warning in warnings})

    auth_warnings = osg.security_warnings(parsed, located)
    assert [warning.code for warning in auth_warnings] == [
        "AUTH_HEADER_NOT_GENERATED",
        "AUTH_HEADER_NOT_GENERATED",
        "AUTH_HEADER_NOT_GENERATED",
    ]
    assert {warning.field for warning in auth_warnings} == {"step.headers", "step.queryParams"}

    swagger_security = osg.ParsedOpenApiDocument(
        document={
            "swagger": "2.0",
            "info": {"title": "Legacy Security", "version": "1"},
            "securityDefinitions": {"BasicAuth": {"type": "basic"}},
            "security": [{"BasicAuth": []}],
            "paths": {
                "/secure": {
                    "get": {
                        "operationId": "secure",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        },
        version="2.0",
        root_kind="swagger",
    )
    swagger_auth_warnings = osg.security_warnings(
        swagger_security,
        osg.locate_operation(
            swagger_security,
            OpenApiOperationRef(method="GET", path="/secure", operationId="secure"),
            0,
        ),
    )
    assert [warning.code for warning in swagger_auth_warnings] == ["AUTH_HEADER_NOT_GENERATED"]
    assert osg.parameter_schema({"type": "string", "default": "legacy"}) == {
        "type": "string",
        "default": "legacy",
    }
    assert osg.parameter_value({"type": "integer", "minimum": 10}) == ("10", True)
    assert not osg.has_unsupported_parameter_serialization({"name": "body", "in": "body"})
    assert osg.has_unsupported_parameter_serialization(
        {"name": "id", "in": "query", "style": "matrix", "schema": {"type": "string"}}
    )
    assert osg.has_unsupported_parameter_serialization(
        {"name": "Trace", "in": "header", "style": "form", "schema": {"type": "string"}}
    )
    assert not osg.security_scheme_requires_credential_header("bad")
    assert osg.security_scheme_requires_credential_header(
        {"type": "openIdConnect", "openIdConnectUrl": "https://idp.example.test/.well-known"}
    )
    invalid_security_document = {
        **document,
        "paths": {
            "/edge": {
                "post": {
                    **document["paths"]["/edge"]["post"],
                    "security": [
                        "bad",
                        {1: []},
                        {"Unknown": []},
                        {"HeaderKey": []},
                        {"HeaderKey": []},
                    ],
                }
            }
        },
    }
    invalid_security_parsed = osg.ParsedOpenApiDocument(
        document=invalid_security_document, version="3.1.0", root_kind="openapi"
    )
    invalid_security_warnings = osg.security_warnings(
        invalid_security_parsed,
        osg.locate_operation(
            invalid_security_parsed,
            OpenApiOperationRef(method="POST", path="/edge", operationId="edge"),
            0,
        ),
    )
    assert [warning.code for warning in invalid_security_warnings] == ["AUTH_HEADER_NOT_GENERATED"]

    body, body_warnings = osg.map_body(parsed, located)
    assert body.type == "none"
    assert [warning.code for warning in body_warnings] == ["UNSUPPORTED_BODY_MEDIA_TYPE"]

    recursive_document = {
        "openapi": "3.1.0",
        "info": {"title": "Recursive", "version": "1"},
        "components": {
            "schemas": {
                "Node": {
                    "type": "object",
                    "required": ["child"],
                    "properties": {"child": {"$ref": "#/components/schemas/Node"}},
                }
            }
        },
        "paths": {
            "/nodes": {
                "post": {
                    "operationId": "createNode",
                    "requestBody": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Node"}}
                        }
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    recursive_parsed = osg.ParsedOpenApiDocument(
        document=recursive_document, version="3.1.0", root_kind="openapi"
    )
    recursive_body, recursive_warnings = osg.map_body(
        recursive_parsed,
        osg.locate_operation(
            recursive_parsed,
            OpenApiOperationRef(method="POST", path="/nodes", operationId="createNode"),
            0,
        ),
    )
    assert recursive_body.type == "none"
    assert [warning.code for warning in recursive_warnings] == ["JSON_BODY_EXAMPLE_MISSING"]

    optional_only_document = {
        "openapi": "3.1.0",
        "info": {"title": "Optional Body", "version": "1"},
        "paths": {
            "/optional": {
                "post": {
                    "operationId": "createOptional",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "sku": {"type": "string"},
                                        "quantity": {"type": "integer"},
                                        "enabled": {"type": "boolean"},
                                        "tags": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "metadata": {
                                            "type": "object",
                                            "properties": {"source": {"type": "string"}},
                                        },
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    optional_only_parsed = osg.ParsedOpenApiDocument(
        document=optional_only_document, version="3.1.0", root_kind="openapi"
    )
    optional_only_body, optional_only_warnings = osg.map_body(
        optional_only_parsed,
        osg.locate_operation(
            optional_only_parsed,
            OpenApiOperationRef(method="POST", path="/optional", operationId="createOptional"),
            0,
        ),
    )
    assert optional_only_body.type == "raw"
    assert optional_only_body.content_type == "application/json"
    assert json.loads(optional_only_body.raw_text or "null") == {
        "sku": "string",
        "quantity": 0,
        "enabled": False,
        "tags": ["string"],
        "metadata": {"source": "string"},
    }
    assert [warning.code for warning in optional_only_warnings] == ["JSON_BODY_EXAMPLE_GENERATED"]

    mixed_sample = osg.schema_sample(
        document,
        {
            "type": "object",
            "required": ["requiredName"],
            "properties": {
                "requiredName": {"type": "string"},
                "optionalCount": {"type": "integer"},
                "unknown": {},
            },
        },
    )
    assert mixed_sample == {"requiredName": "string", "optionalCount": 0}

    optional_recursive_document = {
        "openapi": "3.1.0",
        "info": {"title": "Optional Recursive", "version": "1"},
        "components": {
            "schemas": {
                "Node": {
                    "type": "object",
                    "properties": {"child": {"$ref": "#/components/schemas/Node"}},
                }
            }
        },
        "paths": {
            "/optional-nodes": {
                "post": {
                    "operationId": "createOptionalNode",
                    "requestBody": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Node"}}
                        }
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    optional_recursive_parsed = osg.ParsedOpenApiDocument(
        document=optional_recursive_document, version="3.1.0", root_kind="openapi"
    )
    optional_recursive_body, optional_recursive_warnings = osg.map_body(
        optional_recursive_parsed,
        osg.locate_operation(
            optional_recursive_parsed,
            OpenApiOperationRef(
                method="POST",
                path="/optional-nodes",
                operationId="createOptionalNode",
            ),
            0,
        ),
    )
    assert optional_recursive_body.type == "none"
    assert [warning.code for warning in optional_recursive_warnings] == [
        "JSON_BODY_EXAMPLE_MISSING"
    ]

    oversized_document = {
        "openapi": "3.1.0",
        "info": {"title": "Oversized", "version": "1"},
        "paths": {
            "/oversized": {
                "post": {
                    "operationId": "createOversized",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "payload": {
                                            "type": "string",
                                            "default": "x" * (osg.MAX_RAW_BODY_CHARS + 1),
                                        }
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    oversized_parsed = osg.ParsedOpenApiDocument(
        document=oversized_document, version="3.1.0", root_kind="openapi"
    )
    oversized_body, oversized_warnings = osg.map_body(
        oversized_parsed,
        osg.locate_operation(
            oversized_parsed,
            OpenApiOperationRef(method="POST", path="/oversized", operationId="createOversized"),
            0,
        ),
    )
    assert oversized_body.type == "none"
    assert [warning.code for warning in oversized_warnings] == ["JSON_BODY_EXAMPLE_MISSING"]

    swagger_text = osg.ParsedOpenApiDocument(
        document={
            "swagger": "2.0",
            "info": {"title": "Text", "version": "1"},
            "consumes": ["text/plain"],
            "paths": {
                "/text": {
                    "post": {
                        "operationId": "createText",
                        "parameters": [
                            {
                                "name": "body",
                                "in": "body",
                                "schema": {"type": "string", "example": "hello"},
                            }
                        ],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        },
        version="2.0",
        root_kind="swagger",
    )
    swagger_text_body, swagger_text_warnings = osg.map_body(
        swagger_text,
        osg.locate_operation(
            swagger_text,
            OpenApiOperationRef(method="POST", path="/text", operationId="createText"),
            0,
        ),
    )
    assert swagger_text_body.type == "none"
    assert [warning.code for warning in swagger_text_warnings] == ["UNSUPPORTED_BODY_MEDIA_TYPE"]

    assert osg.schema_sample(document, {"enum": ["a"]}) == "a"
    assert osg.schema_sample(document, {"type": "array", "items": {"type": "boolean"}}) == [False]
    assert osg.schema_sample(document, {"type": "string"}) == "string"
    assert osg.schema_sample(document, None) is None
    assert osg.json_body_from_sample(None) is None

    with pytest.raises(AppError, match="OPENAPI_OPERATION_UNSUPPORTED"):
        osg.locate_operation(
            parsed,
            OpenApiOperationRef.model_construct(method="TRACE", path="/edge", operation_id=None),
            0,
        )
    with pytest.raises(AppError, match="OPENAPI_OPERATION_NOT_FOUND"):
        osg.locate_operation(parsed, OpenApiOperationRef(method="GET", path="/missing"), 0)
    with pytest.raises(AppError, match="OPENAPI_OPERATION_NOT_FOUND"):
        osg.locate_operation(
            parsed,
            OpenApiOperationRef(method="POST", path="/edge", operationId="other"),
            0,
        )
    with pytest.raises(AppError, match="VALIDATION_ERROR"):
        osg.ensure_unique_refs([ref, ref])


def test_openapi_step_generation_schema_validators_and_release_conn() -> None:
    with pytest.raises(ValidationError):
        OpenApiOperationRef(method="GET", path="relative")
    with pytest.raises(ValidationError):
        OpenApiStepDraftGenerateRequest(
            specId="01HZX3Y9M0E9W7Z6M5QK9S8P7S",
            operationRefs=[{"method": "GET", "path": "/items"}],
            insert={"mode": "before_step"},
        )
    with pytest.raises(ValidationError):
        OpenApiGeneratedStepDraft(
            enabled=True,
            name="Bad path",
            method="GET",
            path="relative",
            queryParams=[],
            headers=[],
            body={"type": "none", "contentType": None, "rawText": None, "formFields": []},
            settings={
                "timeoutMs": None,
                "followRedirects": None,
                "keepAlive": None,
                "thinkTimeMs": None,
            },
        )

    class StreamWithRelease(BytesIO):
        def __init__(self, payload: bytes) -> None:
            super().__init__(payload)
            self.released = False

        def release_conn(self) -> None:
            self.released = True

    stream = StreamWithRelease(b"{}")

    class StorageWithRelease(StorageClient):
        def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):
            raise NotImplementedError

        def get_stream(self, *, bucket, object_key):
            return StoredObjectStream(content_type=None, size_bytes=2, stream=stream)

        def delete_object_best_effort(self, *, bucket, object_key):
            raise NotImplementedError

        def copy_object(self, *, bucket, source_key, destination_key):
            raise NotImplementedError

        def health_check(self):
            return True

    spec = SimpleNamespace(storage_bucket="bucket", storage_object_key="key")
    assert osg.read_stored_spec(spec, storage=StorageWithRelease()) == b"{}"
    assert stream.released is True


def cache_spec(
    storage: FakeStorage,
    *,
    spec_id: str,
    workspace_id: str,
    document: dict | None = None,
    payload: bytes | None = None,
    status: str = "available",
) -> SimpleNamespace:
    stored_payload = payload if payload is not None else json.dumps(document or OPENAPI_31).encode()
    object_key = f"api-catalog-specs/{workspace_id}/{spec_id}/spec.json"
    storage.objects[("surgepilot", object_key)] = (stored_payload, "application/json")
    return SimpleNamespace(
        id=spec_id,
        workspace_id=workspace_id,
        name="Orders API",
        filename="spec.json",
        document_title="Orders API",
        document_version="1.0.0",
        sha256=sha256(stored_payload).hexdigest(),
        status=status,
        source_format="openapi_json",
        storage_bucket="surgepilot",
        storage_object_key=object_key,
        updated_at=datetime.now(UTC),
    )


def test_parsed_document_cache_hits_and_invalidates_by_workspace_sha_and_status() -> None:
    storage = FakeStorage()
    cache = osg.ParsedOpenApiDocumentCache(capacity=4)
    spec = cache_spec(
        storage,
        spec_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        workspace_id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
    )

    first = osg.parse_authorized_spec(spec, storage=storage, cache=cache)
    second = osg.parse_authorized_spec(spec, storage=storage, cache=cache)

    assert second is first
    assert storage.get_calls == 1

    changed_payload = json.dumps(SWAGGER_20).encode()
    storage.objects[(spec.storage_bucket, spec.storage_object_key)] = (
        changed_payload,
        "application/json",
    )
    spec.sha256 = sha256(changed_payload).hexdigest()
    changed = osg.parse_authorized_spec(spec, storage=storage, cache=cache)
    assert changed.root_kind == "swagger"
    assert storage.get_calls == 2

    other_workspace_spec = cache_spec(
        storage,
        spec_id=spec.id,
        workspace_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        document=SWAGGER_20,
    )
    osg.parse_authorized_spec(other_workspace_spec, storage=storage, cache=cache)
    assert storage.get_calls == 3

    spec.status = "invalid"
    with pytest.raises(AppError) as status_error:
        osg.parse_authorized_spec(spec, storage=storage, cache=cache)
    assert (
        status_error.value.code,
        status_error.value.status_code,
        status_error.value.message,
        status_error.value.details,
    ) == (
        "API_SPEC_NOT_AVAILABLE",
        422,
        "API spec is not available for generation.",
        None,
    )
    assert storage.get_calls == 3


def test_parsed_document_cache_does_not_store_parse_or_validation_failures() -> None:
    storage = FakeStorage()
    cache = osg.ParsedOpenApiDocumentCache(capacity=4)
    spec = cache_spec(
        storage,
        spec_id="01HZX3Y9M0E9W7Z6M5QK9S8P7D",
        workspace_id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
        payload=b'{"openapi":"3.1.0","paths":{}}',
    )

    for _ in range(2):
        with pytest.raises(AppError) as parse_error:
            osg.parse_authorized_spec(spec, storage=storage, cache=cache)
        assert (
            parse_error.value.code,
            parse_error.value.status_code,
            parse_error.value.message,
            parse_error.value.details,
        ) == (
            "API_SPEC_PARSE_FAILED",
            422,
            "The API spec could not be validated.",
            None,
        )

    assert storage.get_calls == 2
    assert len(cache) == 0


def test_parsed_document_cache_is_bounded_and_uses_lru_eviction() -> None:
    storage = FakeStorage()
    cache = osg.ParsedOpenApiDocumentCache(capacity=2)
    specs = [
        cache_spec(
            storage,
            spec_id=f"01HZX3Y9M0E9W7Z6M5QK9S8P{i}",
            workspace_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Z",
        )
        for i in (1, 2, 3)
    ]

    osg.parse_authorized_spec(specs[0], storage=storage, cache=cache)
    osg.parse_authorized_spec(specs[1], storage=storage, cache=cache)
    osg.parse_authorized_spec(specs[0], storage=storage, cache=cache)
    osg.parse_authorized_spec(specs[2], storage=storage, cache=cache)
    osg.parse_authorized_spec(specs[1], storage=storage, cache=cache)

    assert len(cache) == 2
    assert storage.get_calls == 4


def test_parsed_document_cache_remains_bounded_under_concurrent_access() -> None:
    capacity = 4
    worker_count = 8
    cache = osg.ParsedOpenApiDocumentCache(capacity=capacity)
    barrier = Barrier(worker_count)

    def exercise_cache(worker_index: int) -> list[osg.ParsedOpenApiDocument]:
        barrier.wait()
        observed: list[osg.ParsedOpenApiDocument] = []
        for iteration in range(200):
            slot = (worker_index + iteration) % 12
            key = (
                f"workspace-{slot % 3}",
                f"spec-{slot}",
                f"sha-{iteration % 5}",
                "available",
            )
            if iteration % 2 == 0:
                cache.put(
                    key,
                    osg.ParsedOpenApiDocument(
                        document={"worker": worker_index, "iteration": iteration},
                        version="3.1.0",
                        root_kind="openapi",
                    ),
                )
            parsed = cache.get(key)
            if parsed is not None:
                observed.append(parsed)
        return observed

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        observed = [
            parsed
            for worker_documents in executor.map(exercise_cache, range(worker_count))
            for parsed in worker_documents
        ]

    assert observed
    assert all(parsed.root_kind == "openapi" for parsed in observed)
    assert len(cache) <= capacity


def test_cached_document_is_not_mutated_by_repeated_draft_generation() -> None:
    storage = FakeStorage()
    cache = osg.ParsedOpenApiDocumentCache(capacity=2)
    spec = cache_spec(
        storage,
        spec_id="01HZX3Y9M0E9W7Z6M5QK9S8P7F",
        workspace_id="01HZX3Y9M0E9W7Z6M5QK9S8P7G",
    )
    parsed = osg.parse_authorized_spec(spec, storage=storage, cache=cache)
    cached = osg.parse_authorized_spec(spec, storage=storage, cache=cache)
    before = deepcopy(parsed.document)
    refs = [OpenApiOperationRef(method="POST", path="/orders", operationId="createOrder")]
    insert = osg.OpenApiStepInsertPlan(mode="append")

    first = osg.generate_drafts(
        spec=spec,
        parsed=parsed,
        operation_refs=refs,
        insert=insert,
    )
    second = osg.generate_drafts(
        spec=spec,
        parsed=cached,
        operation_refs=refs,
        insert=insert,
    )

    assert cached is parsed
    assert second == first
    assert parsed.document == before
