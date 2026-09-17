import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "packages/contracts/openapi/api.openapi.json"
WEB_CLIENT = ROOT / "packages/contracts/generated/web-client/index.ts"


def load_openapi() -> dict:
    return json.loads(OPENAPI.read_text())


def test_scenario_script_contract_uses_dependency_file_id_not_script_text() -> None:
    schemas = load_openapi()["components"]["schemas"]
    script_properties = schemas["ScenarioScript"]["properties"]

    assert "dependencyFileId" in script_properties
    assert "scriptText" not in script_properties
    assert "dependency_file_id" not in script_properties


def test_generated_web_client_scenario_script_uses_dependency_file_id() -> None:
    web_client_text = WEB_CLIENT.read_text()

    assert "dependencyFileId" in web_client_text
    assert "scriptText" not in web_client_text
