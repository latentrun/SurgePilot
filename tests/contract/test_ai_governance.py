from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROOT_INSTRUCTIONS = ROOT / "AGENTS.md"
NESTED_INSTRUCTIONS = (
    ROOT / "apps/api/AGENTS.md",
    ROOT / "apps/runner/AGENTS.md",
    ROOT / "apps/web/AGENTS.md",
    ROOT / "packages/contracts/AGENTS.md",
)


def test_accepted_governance_design_is_discoverable_from_sdd_entry() -> None:
    design = (ROOT / "docs/sdd/ai-development-governance-optimization-design.md").read_text(
        encoding="utf-8"
    )
    sdd_entry = (ROOT / "docs/sdd/README.md").read_text(encoding="utf-8")
    normalized_sdd_entry = " ".join(sdd_entry.split())

    assert "Decision status: Accepted for implementation" in design
    assert "Change control: Frozen for Issues #37-#41" in design
    assert "ai-development-governance-optimization-design.md" in sdd_entry
    for lifecycle_state in ("Draft", "Accepted", "Superseded"):
        assert lifecycle_state in sdd_entry
    assert "Editing lifecycle metadata does not grant approval" in normalized_sdd_entry


def test_root_instructions_are_the_compact_ai_workflow_authority() -> None:
    agents = ROOT_INSTRUCTIONS.read_text(encoding="utf-8")
    workflow = (ROOT / "docs/sdd/02-repo-structure-and-dev-workflow.md").read_text(encoding="utf-8")

    assert len(agents.encode()) < 20 * 1024
    assert "This file is authoritative for AI contribution behavior" in agents
    assert "Mandatory constraints" in agents
    assert "No engineering preference may override these constraints" in agents
    assert "synced operational copy" not in agents
    assert "## Current target" not in agents
    assert "## Slice context router" not in agents
    assert "## Service startup contract" not in agents
    assert "AI Instruction Architecture" in workflow
    assert "does not reproduce `/AGENTS.md`" in workflow
    assert "synced operational copy" not in workflow
    assert "# SurgePilot Agent Instructions" not in workflow


def test_task_routes_cover_representative_governance_scenarios() -> None:
    agents = ROOT_INSTRUCTIONS.read_text(encoding="utf-8")
    normalized_agents = " ".join(agents.split())

    for route in (
        "Feature without a named Slice",
        "Bug fix",
        "Cross-subtree changes",
        "Generic source startup or restart",
        "Preview-only UI or control-plane work",
        "Two-node SSH manual demo",
        "Tagged-release operations",
    ):
        assert route in agents
    assert "make start-full-stack" in agents
    assert "make start-preview" in agents
    assert "make start-full-ssh-e2e" in agents
    assert (
        "does not promise Load Node initialization or Run execution readiness" in normalized_agents
    )
    assert (
        "Partial code, routes, navigation, proposals, and future enum values do not activate scope"
        in agents
    )


def test_nested_instructions_are_small_local_deltas() -> None:
    root_size = len(ROOT_INSTRUCTIONS.read_bytes())

    for path in NESTED_INSTRUCTIONS:
        content = path.read_text(encoding="utf-8")
        assert len(content.encode()) < 4 * 1024, path
        assert root_size + len(content.encode()) < 32 * 1024, path
        assert "Scope: `" in content
        assert "Inherits `/AGENTS.md`" in content
        assert "This file is subordinate" not in content
        assert "ADR-" not in content


def test_scope_indexes_own_dynamic_slice_discovery() -> None:
    p1_index = (ROOT / "docs/sdd/slices/P1-README.md").read_text(encoding="utf-8")
    p2_index = (ROOT / "docs/sdd/slices/P2-README.md").read_text(encoding="utf-8")

    for index in (p1_index, p2_index):
        assert "Dynamic Slice activation belongs in this index" in index
        assert "synchronize `docs/sdd/00-product-scope-and-priority.md`, " not in index


def test_dynamic_scope_sources_no_longer_require_root_duplication() -> None:
    sources = (
        ROOT / "docs/sdd/adr/ADR-0008-p1-debug-http-trace.md",
        ROOT / "docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md",
        ROOT / "docs/sdd/adr/ADR-0011-p2-openapi-step-generation.md",
        ROOT / "docs/sdd/adr/ADR-0014-p2-env-group-secret.md",
        ROOT / "docs/sdd/adr/ADR-0015-p1-scenario-global-configuration.md",
        ROOT / "docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md",
        ROOT / "docs/sdd/slices/P1-08-debug-http-trace.md",
        ROOT / "docs/sdd/slices/P1-09-scenario-global-configuration.md",
        ROOT / "docs/sdd/slices/P2-06-lan-first-deployment-usability.md",
    )

    for path in sources:
        content = path.read_text(encoding="utf-8")
        assert "root `AGENTS.md`" not in content, path
        assert "linked from `P1-README.md` and `AGENTS.md`" not in content, path


def test_v1_release_audit_separates_approval_from_baseline_membership() -> None:
    audit = (ROOT / "docs/sdd/v1.0.0-governing-document-lifecycle-audit.md").read_text(
        encoding="utf-8"
    )

    assert "Baseline tag: `v1.0.0`" in audit
    assert "Baseline commit: `37cc8e4" in audit
    assert "Lifecycle state and release-baseline membership are independent" in audit
    assert "Status-field edits do not grant approval" in audit
    assert "Future or inactive material" in audit
