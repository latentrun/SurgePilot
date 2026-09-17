import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.anyio
async def test_healthz_returns_ok() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_app_startup_rejects_malformed_ssh_credential_encryption_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SSH_CREDENTIAL_ENCRYPTION_KEY", "not-base64")

    with pytest.raises(ValueError, match="SSH_CREDENTIAL_ENCRYPTION_KEY"):
        async with app.router.lifespan_context(app):
            pass


@pytest.mark.anyio
async def test_readyz_returns_ready_when_storage_probe_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class HealthyStorage:
        def health_check(self) -> bool:
            return True

    import app.main as main_module

    monkeypatch.setattr(main_module, "get_storage_client", lambda: HealthyStorage(), raising=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.anyio
async def test_readyz_returns_503_when_storage_probe_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class UnhealthyStorage:
        def health_check(self) -> bool:
            return False

    import app.main as main_module

    monkeypatch.setattr(
        main_module, "get_storage_client", lambda: UnhealthyStorage(), raising=False
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/readyz")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


@pytest.mark.anyio
async def test_openapi_customization_uses_public_error_contract() -> None:
    app.openapi_schema = None
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/openapi.json")

    assert response.status_code == 200
    document = response.json()
    assert "HTTPValidationError" not in document["components"]["schemas"]
    assert "ValidationError" not in document["components"]["schemas"]
    assert "422" not in document["paths"]["/api/v1/env-groups"]["get"]["responses"]
    create_params = {
        parameter["name"]: parameter
        for parameter in document["paths"]["/api/v1/env-groups"]["post"]["parameters"]
    }
    assert create_params["x-csrf-token"]["required"] is True
    assert create_params["x-csrf-token"]["schema"] == {
        "type": "string",
        "title": "X-Csrf-Token",
    }
    error_codes = set(document["info"]["x-surgepilot-error-codes"])
    assert "LOAD_NODE_SSH_HOST_KEY_MISSING" not in error_codes
    assert {
        "LOAD_NODE_SSH_HOST_KEY_SCAN_FAILED",
        "LOAD_NODE_SSH_HOST_KEY_MISMATCH",
        "LOAD_NODE_SSH_HOST_KEY_UNTRUSTED",
        "LOAD_NODE_SSH_HOST_KEY_CHANGED",
        "RUN_CONTROL_SSH_HOST_KEY_UNTRUSTED",
        "RUN_CONTROL_SSH_HOST_KEY_CHANGED",
    }.issubset(error_codes)
    assert "/api/v1/load-nodes/ssh-host-key/scan" in document["paths"]
    assert "/api/public/v1/load-nodes/ssh-host-key/scan" not in document["paths"]
