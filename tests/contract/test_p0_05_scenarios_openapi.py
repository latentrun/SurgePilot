import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "packages/contracts/openapi/api.openapi.json"
WEB_CLIENT = ROOT / "packages/contracts/generated/web-client/index.ts"


def load_openapi() -> dict:
    return json.loads(OPENAPI.read_text())


def test_scenario_crud_public_contract_is_generated() -> None:
    openapi = load_openapi()

    collection = openapi["paths"]["/v1/scenarios"]
    detail = openapi["paths"]["/v1/scenarios/{scenarioId}"]

    assert collection["get"]["operationId"] == "listScenarios"
    assert collection["post"]["operationId"] == "createScenario"
    assert detail["get"]["operationId"] == "getScenario"
    assert detail["patch"]["operationId"] == "patchScenario"
    assert detail["delete"]["operationId"] == "deleteScenario"

    detail_parameters = {parameter["name"] for parameter in detail["get"]["parameters"]}
    assert "scenarioId" in detail_parameters
    assert "scenario_id" not in detail_parameters

    create_parameters = {parameter["name"] for parameter in collection["post"]["parameters"]}
    assert "x-csrf-token" in create_parameters
    assert "x-workspace-id" in create_parameters

    list_parameters = {
        parameter["name"]: parameter for parameter in collection["get"]["parameters"]
    }
    assert list_parameters["sort"]["schema"]["enum"] == [
        "-updatedAt",
        "updatedAt",
        "name",
        "-name",
    ]


def test_public_debug_run_contract_is_generated_for_scenario_source() -> None:
    openapi = load_openapi()
    operation = openapi["paths"]["/v1/runs"]["post"]

    assert operation["operationId"] == "createRun"
    assert "201" in operation["responses"]
    assert "200" in operation["responses"]

    codes = set(openapi["info"]["x-surgepilot-error-codes"])
    assert "SCENARIO_REVISION_CONFLICT" in codes

    schemas = openapi["components"]["schemas"]
    create_schema = schemas["RunCreateRequest"]
    properties = create_schema["properties"]
    assert "runType" in properties
    assert "sourceType" in properties
    assert "expectedSourceRevision" in properties
    assert "selectedNodeId" in properties
    assert "selected_node_id" not in properties


def test_generated_web_client_exposes_scenarios_without_internal_runner() -> None:
    web_client_text = WEB_CLIENT.read_text()

    assert '"/v1/scenarios"' in web_client_text
    assert '"/v1/scenarios/{scenarioId}"' in web_client_text
    assert '"/v1/runs"' in web_client_text
    assert "runner/callbacks" not in web_client_text
    assert "runner/artifacts" not in web_client_text
