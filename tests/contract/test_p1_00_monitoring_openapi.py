import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "packages/contracts/openapi/api.openapi.json"
WEB_CLIENT = ROOT / "packages/contracts/generated/web-client/index.ts"


def load_openapi() -> dict:
    return json.loads(OPENAPI.read_text())


def test_monitoring_public_contracts_are_generated() -> None:
    openapi = load_openapi()

    embed = openapi["paths"]["/v1/monitoring/embed"]["get"]
    assert embed["operationId"] == "getMonitoringEmbed"
    embed_params = {parameter["name"] for parameter in embed["parameters"]}
    assert {"x-workspace-id", "runId", "from", "to"}.issubset(embed_params)

    run_link = openapi["paths"]["/v1/runs/{runId}/monitoring"]["get"]
    assert run_link["operationId"] == "getRunMonitoringLink"
    run_link_params = {parameter["name"] for parameter in run_link["parameters"]}
    assert {"x-workspace-id", "runId"}.issubset(run_link_params)

    schemas = openapi["components"]["schemas"]
    assert "MonitoringEmbedResponse" in schemas
    assert "RunMonitoringLinkResponse" in schemas
    assert "iframeUrl" in schemas["MonitoringEmbedResponse"]["properties"]
    assert "platformMonitoringUrl" in schemas["RunMonitoringLinkResponse"]["properties"]


def test_monitoring_forbidden_contracts_and_internal_session_check_are_absent() -> None:
    openapi_text = OPENAPI.read_text()
    web_client_text = WEB_CLIENT.read_text()

    assert "/v1/monitoring/settings" not in openapi_text
    assert "/v1/monitoring/status" not in openapi_text
    assert "/api/internal/v1/session-check" not in openapi_text
    assert "session-check" not in web_client_text
    assert "tokenConfigured" not in openapi_text
    assert "influxdbNodeWriteUrl" not in openapi_text
    assert "influxdbInternalUrl" not in openapi_text
