from hashlib import sha256
from io import BytesIO

import pytest
from httpx import AsyncClient

from app.services.api_catalog import (
    api_catalog_object_key,
    parse_api_spec,
)
from app.services.storage import PutResult, StorageClient, StoredObjectStream


class MemoryStorage(StorageClient):
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):
        payload = stream.read()
        assert len(payload) <= size_limit
        self.objects[(bucket, object_key)] = payload
        return PutResult(len(payload), sha256(payload).hexdigest())

    def get_stream(self, *, bucket, object_key):
        payload = self.objects[(bucket, object_key)]
        return StoredObjectStream(None, len(payload), BytesIO(payload))

    def delete_object_best_effort(self, *, bucket, object_key):
        self.objects.pop((bucket, object_key), None)

    def copy_object(self, *, bucket, source_key, destination_key):
        self.objects[(bucket, destination_key)] = self.objects[(bucket, source_key)]

    def health_check(self):
        return True


OPENAPI_JSON = b'{"openapi":"3.1.0","info":{"title":"Orders API","version":"1.0.0"},"paths":{}}'


def test_api_catalog_parser_accepts_openapi_and_rejects_invalid_roots() -> None:
    parsed = parse_api_spec(
        OPENAPI_JSON, filename="orders.json", content_type="application/json"
    )
    assert parsed.source_format == "openapi_json"
    assert parsed.openapi_version == "3.1.0"
    assert parsed.document_title == "Orders API"

    with pytest.raises(Exception) as error:
        parse_api_spec(b'{"info":{"title":"missing root"}}', filename="x.json", content_type=None)
    assert "OpenAPI or Swagger" in str(error.value)


def test_api_catalog_storage_key_is_server_only_and_scoped() -> None:
    workspace_id = "01HZW000000000000000000000"
    spec_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7A"
    assert api_catalog_object_key(
        workspace_id=workspace_id, spec_id=spec_id, filename="orders.json"
    ) == f"api-catalog-specs/{workspace_id}/{spec_id}/orders.json"


@pytest.mark.anyio
async def test_api_catalog_route_contract_and_workspace_boundary(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.routes import api_catalog

    storage = MemoryStorage()
    monkeypatch.setattr(api_catalog, "get_storage_client", lambda: storage)
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": "catalog@example.com", "displayName": "Catalog", "password": "password123"},
    )
    assert registered.status_code == 201
    auth = registered.json()
    headers = {"x-workspace-id": auth["defaultWorkspace"]["id"], "x-csrf-token": auth["csrfToken"]}

    created = await client.post(
        "/api/v1/api-catalog/specs",
        headers=headers,
        files={"file": ("orders.json", OPENAPI_JSON, "application/json")},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["contentUrl"].endswith("/content")
    assert "storageBucket" not in body and "storageObjectKey" not in body
    assert "api-catalog-specs/" not in created.text

    listed = await client.get("/api/v1/api-catalog/specs", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == body["id"]
    assert "contentUrl" not in listed.json()["items"][0]

    content = await client.get(body["contentUrl"], headers=headers)
    assert content.status_code == 200
    assert content.content == OPENAPI_JSON
    assert content.headers["cache-control"] == "private, no-store"

    deleted = await client.delete(
        f"/api/v1/api-catalog/specs/{body['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204
    assert storage.objects == {}

    missing = await client.get(f"/api/v1/api-catalog/specs/{body['id']}", headers=headers)
    assert missing.status_code == 404

    wrong_workspace = await client.get(
        f"/api/v1/api-catalog/specs/{body['id']}",
        headers={"x-workspace-id": "01HZW000000000000000000001"},
    )
    assert wrong_workspace.status_code in {403, 404}
