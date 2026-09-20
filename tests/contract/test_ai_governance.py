from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROOT_INSTRUCTIONS = ROOT / "AGENTS.md"
NESTED_INSTRUCTIONS = (
    ROOT / "apps/api/AGENTS.md",
    ROOT / "apps/runner/AGENTS.md",
    ROOT / "apps/web/AGENTS.md",
    ROOT / "packages/contracts/AGENTS.md",
)
V1_SLICE_PATHS = (
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
V1_ADR_PATHS = (
    "docs/sdd/adr/ADR-0001-monorepo.md",
    "docs/sdd/adr/ADR-0002-runner-independent-app.md",
    "docs/sdd/adr/ADR-0003-p0-minio-only.md",
    "docs/sdd/adr/ADR-0004-p0-manual-single-node-only.md",
    "docs/sdd/adr/ADR-0005-p0-no-api-catalog-no-monitoring-no-schedule.md",
    "docs/sdd/adr/ADR-0006-p0-separate-api-worker.md",
    "docs/sdd/adr/ADR-0007-p0-runtime-bootstrap-packaging.md",
    "docs/sdd/adr/ADR-0008-p1-debug-http-trace.md",
    "docs/sdd/adr/ADR-0009-p1-resource-multi-node.md",
    "docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md",
    "docs/sdd/adr/ADR-0011-p2-openapi-step-generation.md",
    "docs/sdd/adr/ADR-0012-p2-public-api-substrate.md",
    "docs/sdd/adr/ADR-0013-p2-static-marketing-landing-logo.md",
    "docs/sdd/adr/ADR-0014-p2-env-group-secret.md",
    "docs/sdd/adr/ADR-0015-p1-scenario-global-configuration.md",
    "docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md",
    "docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md",
    "docs/sdd/adr/ADR-0018-p2-lan-first-release-bootstrap.md",
    "docs/sdd/adr/ADR-0019-p2-source-preview-startup.md",
    "docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md",
    "docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md",
    "docs/sdd/adr/ADR-0022-p1-governance-start.md",
    "docs/sdd/adr/ADR-0023-remove-scenario-execution-preview.md",
    "docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md",
    "docs/sdd/adr/ADR-0025-public-user-documentation-localization.md",
    "docs/sdd/adr/ADR-0026-p2-public-launch-github-pages-seo.md",
)


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _route(markdown: str, route_id: str) -> str:
    marker = f"<!-- governance-route:{route_id} -->"
    start = markdown.index(marker) + len(marker)
    remainder = markdown[start:]
    end = remainder.find("<!-- governance-route:")
    return _normalized(remainder if end == -1 else remainder[:end])


def test_accepted_governance_design_is_discoverable_from_sdd_entry() -> None:
    design_path = ROOT / "docs/sdd/ai-development-governance-optimization-design.md"
    design = design_path.read_text(encoding="utf-8")
    sdd_entry = (ROOT / "docs/sdd/README.md").read_text(encoding="utf-8")

    assert all(term in design for term in ("Decision status", "Accepted", "#37-#41"))
    assert design_path.name in sdd_entry
    assert "v1.0.0-governing-document-lifecycle-audit.md" in sdd_entry
    for lifecycle_state in ("Draft", "Accepted", "Superseded"):
        assert lifecycle_state in sdd_entry
    for lifecycle_source in (design, sdd_entry):
        normalized = _normalized(lifecycle_source)
        assert "does not authorize product implementation" in normalized
        assert "transition it to **Accepted**" in normalized
        assert "metadata only records approval that already exists" in normalized


def test_root_is_the_bounded_instruction_authority() -> None:
    agents = ROOT_INSTRUCTIONS.read_text(encoding="utf-8")
    workflow = (ROOT / "docs/sdd/02-repo-structure-and-dev-workflow.md").read_text(encoding="utf-8")

    assert len(agents.encode()) < 20 * 1024
    assert all(term in agents for term in ("authoritative", "PRD", "SDD", "ADR"))
    assert "synced operational copy" not in agents
    assert "## Current target" not in agents
    assert "## Slice context router" not in agents
    assert "## Service startup contract" not in agents
    assert all(term in workflow for term in ("AI Instruction Architecture", "/AGENTS.md", "20 KiB"))
    assert "synced operational copy" not in workflow


def test_new_implementation_tasks_start_from_current_origin_main() -> None:
    agents = ROOT_INSTRUCTIONS.read_text(encoding="utf-8")
    workflow = (ROOT / "docs/sdd/02-repo-structure-and-dev-workflow.md").read_text(encoding="utf-8")

    normalized_agents = _normalized(agents)
    assert "git fetch origin" in normalized_agents
    assert "1 task = 1 branch + 1 worktree + 1 PR" in normalized_agents
    assert "Start from the current `origin/main`" in normalized_agents
    assert "Create a dedicated task branch from `origin/main`" in normalized_agents
    assert "Create a dedicated worktree for that branch" in normalized_agents
    assert "Perform all implementation work inside that worktree" in normalized_agents
    assert "Never implement new work directly on `main`" in normalized_agents
    assert "Never reuse another task's branch or worktree" in normalized_agents
    assert "existing open PR" in normalized_agents

    normalized_workflow = _normalized(workflow)
    assert "root `/AGENTS.md` **Git workspace rule**" in normalized_workflow
    assert "sole authority for branch, worktree, and base-ref preparation" in normalized_workflow


def test_instruction_contract_covers_task_outcomes() -> None:
    agents = ROOT_INSTRUCTIONS.read_text(encoding="utf-8")
    task_outcomes = {
        "feature-without-slice": (
            "accepted Slice/ADR",
            "otherwise stop at the scope gate",
        ),
        "bug-fix": (
            "every amendment",
            "code, contracts, and tests",
        ),
        "cross-subtree": (
            "each affected nested instruction",
            "contract sources before consumers",
        ),
        "source-full-stack": (
            "make start-full-stack",
            "make restart-full-stack",
        ),
        "source-preview": (
            "make start-preview",
            "make stop-preview",
            "does not promise Load Node initialization or Run execution readiness",
        ),
        "two-node-ssh": (
            "Resource Multi-node",
            "make start-full-ssh-e2e",
        ),
        "tagged-release": (
            "docs/site/docs/quickstart.md",
            "docs/site/docs/startup-modes.md",
            "docs/site/docs/configuration.md",
            "surgepilot up|down|status|logs",
            "./surgepilot",
        ),
    }
    for route_id, required_terms in task_outcomes.items():
        route = _route(agents, route_id)
        assert all(term in route for term in required_terms), route_id


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
    current_slice_paths = tuple(
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / "docs/sdd/slices").glob("P[12]-*.md"))
        if not path.name.endswith("README.md")
    )
    for slice_path in current_slice_paths:
        if "/P1-" in slice_path:
            assert slice_path in p1_index
        elif "/P2-" in slice_path:
            assert slice_path in p2_index
        assert Path(slice_path).name not in root_instructions


def test_v1_release_audit_has_concrete_bounded_source_inventory() -> None:
    audit = (ROOT / "docs/sdd/v1.0.0-governing-document-lifecycle-audit.md").read_text(
        encoding="utf-8"
    )

    assert all(
        term in audit
        for term in (
            "Audit status",
            "Complete",
            "Baseline tag",
            "`v1.0.0`",
            "Baseline commit",
            "`37cc8e4",
            "independent",
            "baseline identity is pinned to that commit SHA",
            "grant approval",
        )
    )

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
    for source in (*foundation_sources, *V1_SLICE_PATHS, *V1_ADR_PATHS):
        assert f"`{source}`" in audit, source

    assert all(term in audit for term in ("Future or inactive", "Placeholder", "non-goals"))
    assert "NOT VERIFIED" in audit
    assert "external real-node" in audit
