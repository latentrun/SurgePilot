import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "packages/contracts/openapi/api.openapi.json"
WEB_CLIENT = ROOT / "packages/contracts/generated/web-client/index.ts"


def load_openapi() -> dict:
    return json.loads(OPENAPI.read_text())


def test_curl_import_parse_public_contract_is_generated() -> None:
    openapi = load_openapi()
    operation = openapi["paths"]["/v1/scenarios/curl-import/parse"]["post"]

    assert operation["operationId"] == "parseScenarioCurlImport"
    assert "200" in operation["responses"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert parameters["x-csrf-token"]["required"] is True
    assert parameters["x-workspace-id"]["required"] is False

    schemas = openapi["components"]["schemas"]
    request_properties = schemas["CurlImportParseRequest"]["properties"]
    response_properties = schemas["CurlImportParseResponse"]["properties"]
    step_properties = schemas["CurlImportStepDraft"]["properties"]
    assert "rawCurl" in request_properties
    assert "raw_curl" not in request_properties
    assert "baseUrlSuggestion" in response_properties
    assert "unsupportedOptions" in response_properties
    assert "queryParams" in step_properties
    assert "query_params" not in step_properties
    assert "id" not in step_properties
    assert schemas["ScenarioNamedValue"]["properties"]["value"]["maxLength"] == 65_536
    assert schemas["CurlImportNamedValueDraft"]["properties"]["value"]["maxLength"] == 65_536


def test_generated_web_client_exposes_curl_import_without_internal_runner() -> None:
    web_client_text = WEB_CLIENT.read_text()

    assert '"/v1/scenarios/curl-import/parse"' in web_client_text
    assert "parseScenarioCurlImport" in web_client_text
    assert "runner/callbacks" not in web_client_text
    assert "runner/artifacts" not in web_client_text
