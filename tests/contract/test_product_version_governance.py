from __future__ import annotations

import json
from pathlib import Path
import re
import tomllib


ROOT = Path(__file__).resolve().parents[2]
CANONICAL_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


def test_product_version_authority_and_meaningful_python_metadata_are_lockstep() -> None:
    raw = (ROOT / "VERSION").read_bytes()
    assert raw.endswith(b"\n")
    assert raw.count(b"\n") == 1
    version = raw[:-1].decode("utf-8")
    assert CANONICAL_VERSION.fullmatch(version)
    assert version != "0.0.0"

    for manifest_path in (ROOT / "apps/api/pyproject.toml", ROOT / "apps/runner/pyproject.toml"):
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["project"]["version"] == version


def test_private_workspaces_do_not_declare_product_versions() -> None:
    root_python = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "project" not in root_python

    for manifest_path in (
        ROOT / "package.json",
        ROOT / "apps/web/package.json",
        ROOT / "packages/contracts/package.json",
        ROOT / "docs/site/package.json",
    ):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["private"] is True
        assert "version" not in manifest


def test_generated_openapi_and_skill_snapshot_use_product_version() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").removesuffix("\n")
    paths = (
        ROOT / "packages/contracts/openapi/api.openapi.json",
        ROOT / "packages/contracts/openapi/public-api.openapi.json",
        ROOT / "packages/ai-skills/surgepilot-public-api/references/public-api.openapi.json",
    )

    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document["info"]["version"] == version


def test_product_version_governance_is_discoverable() -> None:
    adr_path = ROOT / "docs/sdd/adr/ADR-0027-product-version-and-artifact-identity.md"
    adr = adr_path.read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    adr_index = (ROOT / "docs/sdd/adr/README.md").read_text(encoding="utf-8")

    assert "Status: Accepted" in adr
    assert "VERSION" in adr
    assert "SURGEPILOT_PRODUCT_VERSION" in adr
    assert adr_path.name in adr_index
    assert "ADR-0027" in agents
