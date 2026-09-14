import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_OPENAPI = ROOT / "packages/contracts/openapi/api.openapi.json"
PUBLIC_OPENAPI = ROOT / "packages/contracts/openapi/public-api.openapi.json"
WEB_CLIENT = ROOT / "packages/contracts/generated/web-client/index.ts"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def schema_properties(document: dict, name: str) -> dict:
    return document["components"]["schemas"][name]["properties"]


def test_scenario_global_configuration_contracts_are_generated() -> None:
    web_document = load(WEB_OPENAPI)
    public_document = load(PUBLIC_OPENAPI)

    for document in (web_document, public_document):
        for schema_name in ("ScenarioCreateRequest", "ScenarioPatchRequest", "ScenarioDetail"):
            properties = schema_properties(document, schema_name)
            assert "globalHeaders" in properties
            assert "variables" in properties
            assert "globalScripts" not in properties

        summary_properties = schema_properties(document, "ScenarioSummary")
        assert "globalHeaders" not in summary_properties
        assert "variables" not in summary_properties
        for schema_name in (
            "ScenarioDefaultSettings",
            "ScenarioNamedValue",
            "ScenarioVariable",
            "ScenarioDataSource",
            "ScenarioBody",
            "ScenarioUploadFile",
            "ScenarioExtractor",
            "ScenarioAssertion",
            "ScenarioScript",
            "ScenarioStepSettings",
            "ScenarioStep",
        ):
            assert document["components"]["schemas"][schema_name]["additionalProperties"] is False

    public_serialized = json.dumps(public_document, sort_keys=True)
    forbidden_public_material = (
        "globalScripts",
        "secretHash",
        "surgepilot_pat_",
        "ApiTokenCreateRequest",
        "account/api-tokens",
        "x-csrf-token",
        "surgepilot_session",
        "/internal/",
        "objectKey",
        "object_key",
        "serverPath",
        "server_path",
        "runnerToken",
        "runner_token",
    )
    for needle in forbidden_public_material:
        assert needle not in public_serialized


def test_generated_web_client_exposes_scenario_global_configuration_types() -> None:
    web_client_text = WEB_CLIENT.read_text()

    assert "globalHeaders" in web_client_text
    assert "variables" in web_client_text
    assert "globalScripts" not in web_client_text
