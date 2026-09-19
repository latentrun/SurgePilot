from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROOT_INSTRUCTIONS = ROOT / "AGENTS.md"
NESTED_INSTRUCTIONS = (
    ROOT / "apps/api/AGENTS.md",
    ROOT / "apps/runner/AGENTS.md",
    ROOT / "apps/web/AGENTS.md",
    ROOT / "packages/contracts/AGENTS.md",
)
ACTIVE_SLICE_PATHS = (
    "docs/sdd/slices/P0-00-auth-workspace-admin-setup.md",
    "docs/sdd/slices/P0-01-env-groups.md",
    "docs/sdd/slices/P0-02-dependency-files-minio.md",
    "docs/sdd/slices/P0-03-load-nodes.md",
    "docs/sdd/slices/P0-04-run-state-machine-runner-protocol.md",
    "docs/sdd/slices/P0-05-visual-scenario-debug-run.md",
    "docs/sdd/slices/P0-06-test-plan-run-now.md",
    "docs/sdd/slices/P0-07-run-report-artifacts-validity.md",
    "docs/sdd/slices/P0-08-overview-and-polish.md",
    "docs/sdd/slices/P1-00-monitoring.md",
    "docs/sdd/slices/P1-01-resource-multi-node.md",
    "docs/sdd/slices/P1-03-workspace-admin.md",
    "docs/sdd/slices/P1-04-scenario-testplan-polish.md",
    "docs/sdd/slices/P1-05-curl-import.md",
    "docs/sdd/slices/P1-06-dependency-preview.md",
    "docs/sdd/slices/P1-08-debug-http-trace.md",
    "docs/sdd/slices/P1-09-scenario-global-configuration.md",
    "docs/sdd/slices/P2-00-api-catalog-scalar.md",
    "docs/sdd/slices/P2-01-openapi-step-generation.md",
    "docs/sdd/slices/P2-02-public-api-substrate.md",
    "docs/sdd/slices/P2-03-env-group-secret.md",
    "docs/sdd/slices/P2-04-help-ai-agents-system-openapi-bootstrap.md",
    "docs/sdd/slices/P2-05-cross-platform-distribution.md",
    "docs/sdd/slices/P2-06-lan-first-deployment-usability.md",
    "docs/sdd/slices/P2-07-public-launch-github-pages-seo.md",
)


def _section(markdown: str, heading: str) -> str:
    marker = f"## {heading}"
    start = markdown.index(marker) + len(marker)
    remainder = markdown[start:]
    end = remainder.find("\n## ")
    return remainder if end == -1 else remainder[:end]


def _named_bullets(markdown: str, heading: str) -> dict[str, str]:
    routes: dict[str, str] = {}
    current: str | None = None
    for line in _section(markdown, heading).splitlines():
        if line.startswith("- **") and ":**" in line:
            label, body = line[4:].split(":**", maxsplit=1)
            current = label
            routes[current] = body.strip()
        elif current and line.startswith("  "):
            routes[current] = f"{routes[current]} {line.strip()}"
        elif line.strip():
            current = None
    return routes


def _metadata(markdown: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in markdown.split("\n## ", maxsplit=1)[0].splitlines():
        if line.startswith("- ") and ": " in line:
            key, value = line[2:].split(": ", maxsplit=1)
            result[key] = value
    return result


def test_accepted_governance_design_is_discoverable_from_sdd_entry() -> None:
    design_path = ROOT / "docs/sdd/ai-development-governance-optimization-design.md"
    design = design_path.read_text(encoding="utf-8")
    sdd_entry = (ROOT / "docs/sdd/README.md").read_text(encoding="utf-8")
    metadata = _metadata(design)

    assert metadata["Decision status"].startswith("Accepted")
    assert "#37-#41" in metadata["Change control"]
    assert design_path.name in sdd_entry
    assert "v1.0.0-governing-document-lifecycle-audit.md" in sdd_entry
    lifecycle = _section(sdd_entry, "Document lifecycle")
    for lifecycle_state in ("Draft", "Accepted", "Superseded"):
        assert lifecycle_state in lifecycle


def test_root_is_the_bounded_instruction_authority() -> None:
    agents = ROOT_INSTRUCTIONS.read_text(encoding="utf-8")
    workflow = (ROOT / "docs/sdd/02-repo-structure-and-dev-workflow.md").read_text(encoding="utf-8")
    introduction = agents.split("\n## ", maxsplit=1)[0]

    assert len(agents.encode()) < 20 * 1024
    assert "authoritative" in introduction
    assert "PRD" in introduction and "SDD" in introduction and "ADR" in introduction
    assert "synced operational copy" not in agents
    assert "## Current target" not in agents
    assert "## Slice context router" not in agents
    assert "## Service startup contract" not in agents
    instruction_architecture = _section(workflow, "12. AI Instruction Architecture")
    assert "/AGENTS.md" in instruction_architecture
    assert "20 KiB" in instruction_architecture
    assert "synced operational copy" not in workflow


def test_task_routes_produce_the_required_development_behavior() -> None:
    agents = ROOT_INSTRUCTIONS.read_text(encoding="utf-8")
    routes = _named_bullets(agents, "Context loading")

    unauthorized = routes["Feature without a named Slice"]
    assert all(
        token in unauthorized for token in ("scope gate", "P1/P2 index", "accepted Slice/ADR")
    )
    assert "stop" in unauthorized

    bug_fix = routes["Bug fix"]
    assert all(
        token in bug_fix
        for token in ("Foundation", "Slice SDD", "amendment", "code", "contracts", "tests")
    )

    cross_subtree = routes["Cross-subtree changes"]
    assert "each affected nested instruction" in cross_subtree
    assert "contract sources before consumers" in cross_subtree

    source_startup = routes["Generic source startup or restart"]
    assert "make start-full-stack" in source_startup
    assert "make restart-full-stack" in source_startup

    preview = routes["Preview-only UI or control-plane work"]
    assert "make start-preview" in preview and "make stop-preview" in preview
    assert all(token in preview for token in ("Load Node", "Run execution", "does not promise"))

    ssh_demo = routes["Two-node SSH manual demo"]
    assert "make start-full-ssh-e2e" in ssh_demo
    assert "Resource Multi-node" in ssh_demo

    release = routes["Tagged-release operations"]
    for path in (
        "docs/site/docs/quickstart.md",
        "docs/site/docs/startup-modes.md",
        "docs/site/docs/configuration.md",
    ):
        assert path in release
    assert "surgepilot up|down|status|logs" in release
    assert "./surgepilot" in release


def test_nested_instructions_are_small_local_deltas() -> None:
    root_size = len(ROOT_INSTRUCTIONS.read_bytes())

    for path in NESTED_INSTRUCTIONS:
        content = path.read_text(encoding="utf-8")
        assert len(content.encode()) < 4 * 1024, path
        assert root_size + len(content.encode()) < 32 * 1024, path
        assert "Scope: `" in content
        assert "Inherits `/AGENTS.md`" in content
        assert "ADR-" not in content


def test_scope_indexes_own_dynamic_slice_discovery() -> None:
    root_instructions = ROOT_INSTRUCTIONS.read_text(encoding="utf-8")
    p1_index = (ROOT / "docs/sdd/slices/P1-README.md").read_text(encoding="utf-8")
    p2_index = (ROOT / "docs/sdd/slices/P2-README.md").read_text(encoding="utf-8")

    assert "docs/sdd/slices/P1-README.md" in root_instructions
    assert "docs/sdd/slices/P2-README.md" in root_instructions
    for slice_path in ACTIVE_SLICE_PATHS:
        if "/P1-" in slice_path:
            assert slice_path in p1_index
        elif "/P2-" in slice_path:
            assert slice_path in p2_index
        assert Path(slice_path).name not in root_instructions


def test_v1_release_audit_has_concrete_bounded_source_inventory() -> None:
    audit = (ROOT / "docs/sdd/v1.0.0-governing-document-lifecycle-audit.md").read_text(
        encoding="utf-8"
    )
    metadata = _metadata(audit)

    assert metadata["Audit status"] == "Complete"
    assert metadata["Baseline tag"] == "`v1.0.0`"
    assert metadata["Baseline commit"].startswith("`37cc8e4")
    audit_rule = _section(audit, "1. Audit rule")
    assert all(term in audit_rule for term in ("independent", "immutable", "grant approval"))

    foundation_sources = (
        "docs/prd/PRD.md",
        "docs/sdd/00-product-scope-and-priority.md",
        "docs/sdd/01-architecture-overview.md",
        "docs/sdd/02-repo-structure-and-dev-workflow.md",
        "docs/sdd/03-domain-model-overview.md",
        "docs/sdd/04-api-contract-guidelines.md",
        "docs/sdd/05-runner-protocol-and-run-state-machine.md",
        "docs/sdd/06-security-permission-workspace.md",
        "docs/sdd/07-storage-artifacts-minio.md",
        "docs/sdd/08-frontend-routing-and-ui-rules.md",
        "docs/sdd/09-testing-and-acceptance-strategy.md",
    )
    adr_sources = tuple(
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / "docs/sdd/adr").glob("ADR-*.md"))
    )
    for source in (*foundation_sources, *ACTIVE_SLICE_PATHS, *adr_sources):
        assert f"`{source}`" in audit, source

    exclusions = _section(audit, "6. Baseline exclusions")
    assert all(term in exclusions for term in ("Future or inactive", "Placeholder", "non-goals"))
    verification = _section(audit, "9. Verification boundary")
    assert "NOT VERIFIED" in verification
    assert "external real-node" in verification
