from datetime import datetime
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.schemas.scenarios import OpenApiOperationRef, OpenApiStepInsertPlan
from app.services.openapi_step_generation import (
    enumerate_operations,
    generate_drafts,
    validate_document,
)
SPEC_ID = "01HZX3Y9M0E9W7Z6M5QK9S8P7A"


def spec_metadata() -> SimpleNamespace:
    return SimpleNamespace(
        id=SPEC_ID,
        name="Orders API",
        filename="orders.json",
        source_format="openapi_json",
        openapi_version="3.1.0",
        document_title="Orders API",
        document_version="1.0.0",
        status="available",
        updated_at=datetime(2030, 1, 1),
    )


OPENAPI_DOCUMENT = {
    "openapi": "3.1.0",
    "info": {"title": "Orders API", "version": "1.0.0"},
    "components": {
        "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}},
        "schemas": {"Order": {"type": "object", "properties": {"sku": {"type": "string", "example": "A1"}}}},
    },
    "paths": {
        "/orders/{orderId}": {
            "get": {
                "operationId": "getOrder",
                "summary": "Get order",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {"name": "orderId", "in": "path", "required": True, "schema": {"type": "string"}},
                    {"name": "include", "in": "query", "required": True, "schema": {"type": "string", "example": "items"}},
                ],
            },
        },
        "/orders": {
            "post": {
                "operationId": "createOrder",
                "summary": "Create order",
                "requestBody": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/Order"}}}},
            },
        },
    },
}


def test_operation_listing_and_ordered_drafts_map_only_transient_steps() -> None:
    parsed = validate_document(OPENAPI_DOCUMENT)
    operations, warnings = enumerate_operations(parsed)

    assert warnings == []
    assert [(item.method, item.path) for item in operations] == [
        ("GET", "/orders/{orderId}"),
        ("POST", "/orders"),
    ]
    assert operations[1].has_request_body is True

    result = generate_drafts(
        spec=spec_metadata(),
        parsed=parsed,
        operation_refs=[
            OpenApiOperationRef(method="POST", path="/orders", operation_id="createOrder"),
            OpenApiOperationRef(method="GET", path="/orders/{orderId}", operation_id="getOrder"),
        ],
        insert=OpenApiStepInsertPlan(mode="append"),
    )

    assert [item.step.method for item in result.items] == ["POST", "GET"]
    assert result.items[0].step.body.raw_text == '{\n  "sku": "A1"\n}'
    assert result.items[1].step.path == "/orders/${orderId}"
    assert {warning.code for warning in result.items[1].warnings} == {
        "PATH_VARIABLE_PLACEHOLDER_REQUIRED",
        "AUTH_HEADER_NOT_GENERATED",
    }
    assert not hasattr(result.items[0].step, "id")
    assert result.spec.id == SPEC_ID


def test_generated_drafts_are_transient_across_spec_lifecycle_changes() -> None:
    parsed = validate_document(OPENAPI_DOCUMENT)
    ref = OpenApiOperationRef(method="POST", path="/orders", operation_id="createOrder")
    first = generate_drafts(
        spec=spec_metadata(), parsed=parsed, operation_refs=[ref], insert=OpenApiStepInsertPlan(mode="append")
    )
    changed_document = {**OPENAPI_DOCUMENT, "info": {"title": "Orders API v2", "version": "2.0.0"}}
    second = generate_drafts(
        spec=SimpleNamespace(**{**vars(spec_metadata()), "document_title": "Orders API v2", "document_version": "2.0.0"}),
        parsed=validate_document(changed_document), operation_refs=[ref], insert=OpenApiStepInsertPlan(mode="append")
    )

    assert first.items[0].step.name == second.items[0].step.name
    assert first.spec.document_version == "1.0.0"
    assert second.spec.document_version == "2.0.0"


def test_generation_rejects_duplicate_or_missing_operations() -> None:
    parsed = validate_document(OPENAPI_DOCUMENT)
    ref = OpenApiOperationRef(method="GET", path="/orders/{orderId}", operation_id="getOrder")
    with pytest.raises(Exception, match="Duplicate"):
        generate_drafts(
            spec=spec_metadata(), parsed=parsed, operation_refs=[ref, ref], insert=OpenApiStepInsertPlan(mode="append")
        )
    with pytest.raises(Exception, match="not found"):
        generate_drafts(
            spec=spec_metadata(),
            parsed=parsed,
            operation_refs=[OpenApiOperationRef(method="DELETE", path="/orders")],
            insert=OpenApiStepInsertPlan(mode="append"),
        )


@pytest.mark.anyio
async def test_generation_routes_require_auth_workspace_and_csrf(client: AsyncClient) -> None:
    scenario_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7B"
    path = f"/api/v1/scenarios/{scenario_id}/openapi-step-generation/specs"

    assert (await client.get(path)).status_code == 401

    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": "p201@example.com", "displayName": "P2-01", "password": "password123"},
    )
    assert registered.status_code == 201
    body = registered.json()
    headers = {"x-workspace-id": body["defaultWorkspace"]["id"]}
    assert (await client.get(path, headers={**headers, "x-workspace-id": "01HZW000000000000000000001"})).status_code == 403

    draft = f"/api/v1/scenarios/{scenario_id}/openapi-step-generation/drafts"
    response = await client.post(
        draft,
        headers=headers,
        json={"specId": SPEC_ID, "operationRefs": [{"method": "GET", "path": "/orders"}], "insert": {"mode": "append"}},
    )
    assert response.status_code == 403
