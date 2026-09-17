import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_OPENAPI = ROOT / "packages/contracts/openapi/api.openapi.json"
PUBLIC_OPENAPI = ROOT / "packages/contracts/openapi/public-api.openapi.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def test_ai_skill_download_is_documented_only_in_web_openapi() -> None:
    web = load(WEB_OPENAPI)
    public = load(PUBLIC_OPENAPI)

    operation = web["paths"]["/v1/account/ai-skill/download"]["get"]
    assert operation["operationId"] == "downloadPublicApiAiSkill"
    assert "application/zip" in operation["responses"]["200"]["content"]
    assert operation["responses"]["503"]["content"]["application/json"]["example"]["code"] == (
        "AI_SKILL_SOURCE_NOT_AVAILABLE"
    )
    assert "AI_SKILL_SOURCE_NOT_AVAILABLE" not in web["info"]["x-surgepilot-error-codes"]

    public_text = json.dumps(public, sort_keys=True)
    assert "/v1/account/ai-skill/download" not in public["paths"]
    assert "AI_SKILL_SOURCE_NOT_AVAILABLE" not in public_text


def test_api_image_copies_only_governed_ai_skill_source_for_p2_04() -> None:
    dockerfile = (ROOT / "apps/api/Dockerfile").read_text()

    assert (
        "COPY packages/ai-skills/surgepilot-public-api "
        "/opt/surgepilot/ai-skills/surgepilot-public-api" in dockerfile
    )
    assert "COPY scripts " not in dockerfile
    assert "api.openapi.json" not in dockerfile
