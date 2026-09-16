# SurgePilot Agent Instructions

Authoritative source: `docs/sdd/02-repo-structure-and-dev-workflow.md` §12. This file is a synced operational copy. If there is any conflict, follow 02 and update this file.

## Purpose

This file is the execution contract for AI contributors. It routes context, enforces active scope, defines the contract-first workflow, and declares verification gates.

This file is not a product README. Do not duplicate PRD or SDD content here.

## Current target

The current delivery target is **P2-02 Public API Substrate and governed Public API AI skill source package implementation plus P2-03 Env Group Secret implementation plus P2-04 Help AI Agents and System OpenAPI Bootstrap plus P2-05 Cross-platform Distribution, Full-stack Release Bootstrap, ADR-0019 Source Preview Startup, and ADR-0024 User-local Release Installer plus P2-06 LAN-first Release Bootstrap Usability, ADR-0020 Release Dual-Architecture Runtime Default, ADR-0021 Release `up` Configuration Confirmation, and ADR-0024 User-local Release Installer plus P2-07 Public Launch, GitHub Pages, and SEO** plus **ADR-0013 static Marketing Landing and Logo** plus **P1-09 Scenario Global Configuration SDD authorization** plus the **localized Public User Documentation MVP**.

P0 is the completed baseline. P1 work may start only through a named P1 Slice SDD that references `docs/sdd/00-product-scope-and-priority.md` §6 and `docs/sdd/slices/P1-README.md`. P1-09 Scenario Global Configuration Phase A remains limited to `docs/sdd/slices/P1-09-scenario-global-configuration.md` as activated by `docs/sdd/adr/ADR-0015-p1-scenario-global-configuration.md`. P2-00 API Catalog Scalar remains limited to `docs/sdd/slices/P2-00-api-catalog-scalar.md` as activated by `docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md`. P2-01 OpenAPI Step Generation remains limited to `docs/sdd/slices/P2-01-openapi-step-generation.md` as activated by `docs/sdd/adr/ADR-0011-p2-openapi-step-generation.md`. The current P2 work is limited to `docs/sdd/slices/P2-02-public-api-substrate.md` as activated by `docs/sdd/adr/ADR-0012-p2-public-api-substrate.md`, `docs/sdd/slices/P2-03-env-group-secret.md` as activated by `docs/sdd/adr/ADR-0014-p2-env-group-secret.md`, `docs/sdd/slices/P2-04-help-ai-agents-system-openapi-bootstrap.md` as activated by `docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md`, `docs/sdd/slices/P2-05-cross-platform-distribution.md` as activated by `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md` and amended for source preview by `docs/sdd/adr/ADR-0019-p2-source-preview-startup.md` plus user-local installation by `docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md`, `docs/sdd/slices/P2-06-lan-first-deployment-usability.md` as activated by `docs/sdd/adr/ADR-0018-p2-lan-first-release-bootstrap.md` and amended by `docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md`, `docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md`, plus `docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md`, and `docs/sdd/slices/P2-07-public-launch-github-pages-seo.md` as activated by `docs/sdd/adr/ADR-0026-p2-public-launch-github-pages-seo.md`, plus static Marketing Landing / Logo as activated by `docs/sdd/adr/ADR-0013-p2-static-marketing-landing-logo.md`.

The Public User Documentation MVP remains localized through `docs/sdd/adr/ADR-0025-public-user-documentation-localization.md` and is published only through the bounded P2-07 amendment in `docs/sdd/adr/ADR-0026-p2-public-launch-github-pages-seo.md`. It retains `docs/site`, the exact `docs/site` pnpm workspace entry, six authoritative English user pages, exact `zh-CN` and `ja` mirrors, native locale navigation, Configuration template-key coverage, exact locale page-set and relative-link checks. P2-07 moves those same page sets below `/docs/`, `/docs/zh-CN/`, and `/docs/ja/` inside one VitePress Pages site rooted at `https://latentrun.github.io/SurgePilot/`; it also authorizes only the bounded static marketing homepage, original AI-authored baseline evidence, explicitly labelled synthetic Landing dashboard/Run/Distributed mesh UI demonstrations, publication SEO/social metadata, self-hosted Web `noindex`, demo/social assets, public-readiness review, and a gated Pages deployment after private acceptance. Hosted SurgePilot, a seventh user page, automatic translation/language redirection, product localization, a custom domain, blog/CMS, programmatic SEO, API/AI Skill user-doc sections, contributor architecture navigation, fabricated benchmark/adoption/status/Star claims, and multi-version documentation remain inactive. `docs/sdd` and `docs/prd` stay outside the user-documentation main navigation.

P1 work must not regress:

- P0-Core: the minimal internal MVP flow.
- P0-Stability: state machine safety, stop idempotency, runner heartbeat, permission checks, workspace isolation, path safety, and credential safety.

Do not treat P0-Stability as later cleanup.

Current active P1 Slice implementations require a named, accepted Slice SDD. `P1-00-monitoring` is allowed only through `docs/sdd/slices/P1-00-monitoring.md`; `P1-01-resource-multi-node` is allowed only through `docs/sdd/slices/P1-01-resource-multi-node.md` and `docs/sdd/adr/ADR-0009-p1-resource-multi-node.md`; `P1-09-scenario-global-configuration` is allowed only through `docs/sdd/slices/P1-09-scenario-global-configuration.md` and `docs/sdd/adr/ADR-0015-p1-scenario-global-configuration.md`; other P1 capabilities remain bounded by their own accepted Slice SDDs and ADRs. Current active P2 implementations are `P2-00-api-catalog-scalar` through `ADR-0010`, `P2-01-openapi-step-generation` through `ADR-0011`, `P2-02-public-api-substrate` through `ADR-0012`, `P2-03-env-group-secret` through `ADR-0014`, `P2-04-help-ai-agents-system-openapi-bootstrap` through `ADR-0016`, `P2-05-cross-platform-distribution` through `ADR-0017` plus source preview through `ADR-0019` and user-local installation through `ADR-0024`, `P2-06-lan-first-deployment-usability` through `ADR-0018` plus its new-release Runtime default through `ADR-0020`, release `up` configuration confirmation through `ADR-0021`, and separate installation through `ADR-0024`, `P2-07-public-launch-github-pages-seo` through `ADR-0026`, and static Marketing Landing / Logo through `ADR-0013`; other P2 capabilities remain inactive.

## Canonical documents

- Product source: `docs/prd/PRD.md`
- SDD entry: `docs/sdd/README.md`
- Scope gate: `docs/sdd/00-product-scope-and-priority.md`
- P1 governance ADR: `docs/sdd/adr/ADR-0022-p1-governance-start.md`
- P1 Slice index: `docs/sdd/slices/P1-README.md`
- P2 Slice index: `docs/sdd/slices/P2-README.md`
- P2 API Catalog activation ADR: `docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md`
- P2 OpenAPI Step Generation activation ADR: `docs/sdd/adr/ADR-0011-p2-openapi-step-generation.md`
- P2 Public API activation ADR: `docs/sdd/adr/ADR-0012-p2-public-api-substrate.md`
- P2 Env Group Secret activation ADR: `docs/sdd/adr/ADR-0014-p2-env-group-secret.md`
- P2 Env Group Secret Slice: `docs/sdd/slices/P2-03-env-group-secret.md`
- P2 Help AI Agents and System OpenAPI Bootstrap ADR: `docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md`
- P2 Help AI Agents and System OpenAPI Bootstrap Slice: `docs/sdd/slices/P2-04-help-ai-agents-system-openapi-bootstrap.md`
- P2 Cross-platform Distribution activation ADR: `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md`
- P2 Source Preview Startup amendment ADR: `docs/sdd/adr/ADR-0019-p2-source-preview-startup.md`
- P2 Cross-platform Distribution Slice: `docs/sdd/slices/P2-05-cross-platform-distribution.md`
- P2 LAN-first Release Bootstrap activation ADR: `docs/sdd/adr/ADR-0018-p2-lan-first-release-bootstrap.md`
- P2 Release Dual-Architecture Runtime Default amendment ADR: `docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md`
- P2 Release `up` Configuration Confirmation amendment ADR: `docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md`
- P2 User-local Release Installer amendment ADR: `docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md`
- Public User Documentation Localization ADR: `docs/sdd/adr/ADR-0025-public-user-documentation-localization.md`
- P2 Public Launch, GitHub Pages, and SEO ADR: `docs/sdd/adr/ADR-0026-p2-public-launch-github-pages-seo.md`
- P2 Public Launch, GitHub Pages, and SEO Slice: `docs/sdd/slices/P2-07-public-launch-github-pages-seo.md`
- Public Launch proposal: `docs/sdd/public-launch-github-pages-and-star-growth-plan.md`
- P2 LAN-first Release Bootstrap Slice: `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`
- P1 Scenario Global Configuration ADR: `docs/sdd/adr/ADR-0015-p1-scenario-global-configuration.md`
- P1 Scenario Preview removal ADR: `docs/sdd/adr/ADR-0023-remove-scenario-execution-preview.md`
- P1 Scenario Global Configuration Slice: `docs/sdd/slices/P1-09-scenario-global-configuration.md`
- P2 static Marketing Landing and Logo ADR: `docs/sdd/adr/ADR-0013-p2-static-marketing-landing-logo.md`
- Architecture: `docs/sdd/01-architecture-overview.md`
- Repo workflow: `docs/sdd/02-repo-structure-and-dev-workflow.md`
- Frontend routing and UI: `docs/sdd/08-frontend-routing-and-ui-rules.md`
- API contracts: `docs/sdd/04-api-contract-guidelines.md`
- Runner protocol: `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- Security and workspace: `docs/sdd/06-security-permission-workspace.md`
- Storage and artifacts: `docs/sdd/07-storage-artifacts-minio.md`
- Testing strategy: `docs/sdd/09-testing-and-acceptance-strategy.md`

## Context loading rule

Default context for any development task:

1. Read this `AGENTS.md`.
2. Read `docs/sdd/README.md`.
3. Read `docs/sdd/00-product-scope-and-priority.md`.
4. Read the active Slice SDD.
5. Read only the relevant Foundation SDD, ADR, contract files, code, and tests.

Do not read the full PRD, full SDD pack, and all Slice SDD files for every task.

If additional documents are required to resolve a direct dependency or conflict, read the smallest necessary file, state why it was needed, and do not expand implementation scope beyond the active Slice.

Do not use P1/P2 placeholder documents as implementation input. P1 implementation requires a real active P1 Slice SDD; P2 documents remain roadmap-only unless a separate accepted governance change explicitly activates them. `P2-00-api-catalog-scalar.md` is active only through `ADR-0010`; `P2-01-openapi-step-generation.md` is active only through `ADR-0011`; `P2-02-public-api-substrate.md` is active only through `ADR-0012`; `P2-03-env-group-secret.md` is active only through `ADR-0014`; `P2-04-help-ai-agents-system-openapi-bootstrap.md` is active only through `ADR-0016`; `P2-05-cross-platform-distribution.md` is active only through `ADR-0017` plus source preview through `ADR-0019` and user-local installation through `ADR-0024`; `P2-06-lan-first-deployment-usability.md` is active only through `ADR-0018` plus its new-release Runtime default through `ADR-0020`, release `up` configuration confirmation through `ADR-0021`, and separate installation through `ADR-0024`; `P2-07-public-launch-github-pages-seo.md` is active only through `ADR-0026`; static Marketing Landing / Logo is active only through `ADR-0013`; none activates any other P2 capability.

## Slice context router

Use this table as the default routing map. The active issue may narrow the list further.

| Slice | Required context | Optional context only if directly needed |
| --- | --- | --- |
| M0 repo scaffold | `01-architecture-overview.md`, `02-repo-structure-and-dev-workflow.md`, `04-api-contract-guidelines.md`, `09-testing-and-acceptance-strategy.md` | ADR files under `docs/sdd/adr/` |
| P0-00 Auth / Workspace / Admin Setup | `slices/P0-00-auth-workspace-admin-setup.md`, `06-security-permission-workspace.md`, `04-api-contract-guidelines.md` | `02-repo-structure-and-dev-workflow.md`, `08-frontend-routing-and-ui-rules.md`, `09-testing-and-acceptance-strategy.md` |
| P0-01 Env Groups | `slices/P0-01-env-groups.md`, `06-security-permission-workspace.md`, `04-api-contract-guidelines.md` | `03-domain-model-overview.md`, `08-frontend-routing-and-ui-rules.md` |
| P0-02 Dependency Files and MinIO | `slices/P0-02-dependency-files-minio.md`, `07-storage-artifacts-minio.md`, `04-api-contract-guidelines.md`, `adr/ADR-0003-p0-minio-only.md` | `06-security-permission-workspace.md` |
| P0-03 Load Nodes | `slices/P0-03-load-nodes.md`, `06-security-permission-workspace.md`, `04-api-contract-guidelines.md`, `adr/ADR-0004-p0-manual-single-node-only.md` | `05-runner-protocol-and-run-state-machine.md`, `01-architecture-overview.md` |
| P0-04 Run State Machine / Runner Protocol | `slices/P0-04-run-state-machine-runner-protocol.md`, `05-runner-protocol-and-run-state-machine.md`, `04-api-contract-guidelines.md`, `adr/ADR-0002-runner-independent-app.md`, `adr/ADR-0004-p0-manual-single-node-only.md` | `01-architecture-overview.md`, `09-testing-and-acceptance-strategy.md` |
| P0-05 Visual Scenario / Debug Run | `slices/P0-05-visual-scenario-debug-run.md`, `04-api-contract-guidelines.md`, `05-runner-protocol-and-run-state-machine.md`, `08-frontend-routing-and-ui-rules.md` | Prior completed Slice docs only for explicit integration dependencies |
| P0-06 Test Plan / Run Now | `slices/P0-06-test-plan-run-now.md`, `04-api-contract-guidelines.md`, `05-runner-protocol-and-run-state-machine.md`, `06-security-permission-workspace.md` | Prior completed Slice docs only for explicit Scenario or Run dependencies |
| P0-07 Run Report / Artifacts / Validity | `slices/P0-07-run-report-artifacts-validity.md`, `07-storage-artifacts-minio.md`, `05-runner-protocol-and-run-state-machine.md`, `04-api-contract-guidelines.md`, `adr/ADR-0003-p0-minio-only.md` | `09-testing-and-acceptance-strategy.md` |
| P0-08 Overview / P0 Polish | `slices/P0-08-overview-and-polish.md`, `08-frontend-routing-and-ui-rules.md`, `09-testing-and-acceptance-strategy.md`, `06-security-permission-workspace.md` | Touched Slice docs only for concrete fixes |
| P1 Slice kickoff | `slices/P1-README.md`, `00-product-scope-and-priority.md`, `adr/ADR-0022-p1-governance-start.md` | Relevant Foundation SDD only after the real P1 Slice SDD identifies the dependency |
| P1 Monitoring | `slices/P1-00-monitoring.md`, `00-product-scope-and-priority.md`, `slices/P1-README.md`, `adr/ADR-0022-p1-governance-start.md`, `04-api-contract-guidelines.md`, `05-runner-protocol-and-run-state-machine.md`, `08-frontend-routing-and-ui-rules.md`, `09-testing-and-acceptance-strategy.md`, `p0-runtime-bootstrap-plan.md` | `02-repo-structure-and-dev-workflow.md` only for AGENTS/workflow sync; `06-security-permission-workspace.md`, `07-storage-artifacts-minio.md`, and relevant existing Run, Runner, Runtime, Web, compose, Nginx, and artifact code/tests only while implementing touched areas |
| P1 Resource Multi-node | `slices/P1-01-resource-multi-node.md`, `adr/ADR-0009-p1-resource-multi-node.md`, `00-product-scope-and-priority.md`, `slices/P1-README.md`, `adr/ADR-0022-p1-governance-start.md`, `04-api-contract-guidelines.md`, `05-runner-protocol-and-run-state-machine.md`, `06-security-permission-workspace.md`, `07-storage-artifacts-minio.md`, `08-frontend-routing-and-ui-rules.md`, `09-testing-and-acceptance-strategy.md` | `02-repo-structure-and-dev-workflow.md` only for AGENTS/workflow sync; relevant Test Plan Run, Load Node, Run state, Runner callback, artifact, report, and Web resource UI code/tests only while implementing touched areas; optional local ignored Taurus/JMeter references only when confirming per-node local execution boundaries |
| P1 Workspace / Admin | `slices/P1-03-workspace-admin.md`, `00-product-scope-and-priority.md`, `slices/P1-README.md`, `adr/ADR-0022-p1-governance-start.md`, `04-api-contract-guidelines.md`, `06-security-permission-workspace.md`, `08-frontend-routing-and-ui-rules.md`, `09-testing-and-acceptance-strategy.md` | `02-repo-structure-and-dev-workflow.md` only for AGENTS/workflow sync; relevant existing code/tests only while implementing touched areas |
| P1 Scenario / TestPlan Polish | `slices/P1-04-scenario-testplan-polish.md`, `adr/ADR-0023-remove-scenario-execution-preview.md`, `00-product-scope-and-priority.md`, `slices/P1-README.md`, `adr/ADR-0022-p1-governance-start.md`, `04-api-contract-guidelines.md`, `06-security-permission-workspace.md`, `08-frontend-routing-and-ui-rules.md`, `09-testing-and-acceptance-strategy.md` | `02-repo-structure-and-dev-workflow.md` only for AGENTS/workflow sync; relevant existing Scenario/Test Plan code/tests only while implementing touched areas; `05-runner-protocol-and-run-state-machine.md` or optional local ignored Taurus/JMeter references only when confirming Test Plan preview builder boundaries |
| P1 Scenario Global Configuration | `slices/P1-09-scenario-global-configuration.md`, `adr/ADR-0015-p1-scenario-global-configuration.md`, `adr/ADR-0023-remove-scenario-execution-preview.md`, `slices/P1-04-scenario-testplan-polish.md`, `00-product-scope-and-priority.md`, `slices/P1-README.md`, `04-api-contract-guidelines.md`, `06-security-permission-workspace.md`, `08-frontend-routing-and-ui-rules.md`, `09-testing-and-acceptance-strategy.md` | `02-repo-structure-and-dev-workflow.md` only for AGENTS/workflow sync; optional local ignored Taurus/JMeter references if present; `slices/P0-05-visual-scenario-debug-run.md`, `slices/P0-01-env-groups.md`, `slices/P2-02-public-api-substrate.md`, `slices/P2-03-env-group-secret.md`, relevant Scenario schema/service, contracts, Scenario Designer, Dependency File, Env Group, Run Snapshot, and tests only while implementing touched areas |
| P1 cURL Import | `slices/P1-05-curl-import.md`, `00-product-scope-and-priority.md`, `slices/P1-README.md`, `adr/ADR-0022-p1-governance-start.md`, `04-api-contract-guidelines.md`, `06-security-permission-workspace.md`, `08-frontend-routing-and-ui-rules.md`, `09-testing-and-acceptance-strategy.md` | `02-repo-structure-and-dev-workflow.md` only for AGENTS/workflow sync; `slices/P0-05-visual-scenario-debug-run.md` and relevant existing Scenario code/tests only while implementing touched areas |
| P1 Dependency File Preview | `slices/P1-06-dependency-preview.md`, `00-product-scope-and-priority.md`, `slices/P1-README.md`, `adr/ADR-0022-p1-governance-start.md`, `04-api-contract-guidelines.md`, `06-security-permission-workspace.md`, `07-storage-artifacts-minio.md`, `08-frontend-routing-and-ui-rules.md`, `09-testing-and-acceptance-strategy.md` | `02-repo-structure-and-dev-workflow.md` only for AGENTS/workflow sync; relevant existing Dependency File code/tests only while implementing touched areas |
| P1 Debug HTTP Trace | `slices/P1-08-debug-http-trace.md`, `adr/ADR-0008-p1-debug-http-trace.md`, `05-runner-protocol-and-run-state-machine.md`, `07-storage-artifacts-minio.md`, `04-api-contract-guidelines.md`, `08-frontend-routing-and-ui-rules.md`, `09-testing-and-acceptance-strategy.md` | `p0-runtime-bootstrap-plan.md`; optional local ignored Taurus/JMeter references only for inline JSR223/runtime-boundary confirmation |
| P2 API Catalog Scalar | `slices/P2-00-api-catalog-scalar.md`, `adr/ADR-0010-p2-api-catalog-scalar.md`, `00-product-scope-and-priority.md`, `slices/P2-README.md`, `04-api-contract-guidelines.md`, `06-security-permission-workspace.md`, `07-storage-artifacts-minio.md`, `08-frontend-routing-and-ui-rules.md`, `09-testing-and-acceptance-strategy.md` | `02-repo-structure-and-dev-workflow.md` only for AGENTS/workflow sync; relevant existing storage, API route, contract, Web AppLayout/route, and test code only while implementing touched areas |
| P2 OpenAPI Step Generation | `slices/P2-01-openapi-step-generation.md`, `adr/ADR-0011-p2-openapi-step-generation.md`, `00-product-scope-and-priority.md`, `slices/P2-README.md`, `slices/P2-00-api-catalog-scalar.md`, `adr/ADR-0010-p2-api-catalog-scalar.md`, `04-api-contract-guidelines.md`, `06-security-permission-workspace.md`, `07-storage-artifacts-minio.md`, `08-frontend-routing-and-ui-rules.md`, `09-testing-and-acceptance-strategy.md`, `slices/P0-05-visual-scenario-debug-run.md`, `slices/P1-05-curl-import.md` | `02-repo-structure-and-dev-workflow.md` only for AGENTS/workflow sync; relevant existing API Catalog, Scenario route/service, Scenario Designer, contract, Web AppLayout/route, cURL import, and test code only while implementing touched areas; optional local ignored Taurus/JMeter references only if confirming generated Step execution compatibility |
| P2 Public API Substrate | `slices/P2-02-public-api-substrate.md`, `adr/ADR-0012-p2-public-api-substrate.md`, `00-product-scope-and-priority.md`, `slices/P2-README.md`, `04-api-contract-guidelines.md`, `06-security-permission-workspace.md`, `05-runner-protocol-and-run-state-machine.md`, `07-storage-artifacts-minio.md`, `08-frontend-routing-and-ui-rules.md`, `09-testing-and-acceptance-strategy.md` | `02-repo-structure-and-dev-workflow.md` only for AGENTS/workflow sync; relevant existing auth/session, OpenAPI export, API route, contract, Web account route, Run service, Load Node, Dependency File and test code only while implementing touched areas |
| P2 Env Group Secret | `slices/P2-03-env-group-secret.md`, `adr/ADR-0014-p2-env-group-secret.md`, `slices/P0-01-env-groups.md`, `slices/P2-02-public-api-substrate.md`, `00-product-scope-and-priority.md`, `slices/P2-README.md`, `04-api-contract-guidelines.md`, `06-security-permission-workspace.md`, `05-runner-protocol-and-run-state-machine.md`, `07-storage-artifacts-minio.md`, `09-testing-and-acceptance-strategy.md` | `02-repo-structure-and-dev-workflow.md` only for AGENTS/workflow sync; relevant Env Group schemas/routes/services, Run Snapshot, Execution Bundle, Run Report, public OpenAPI export, generated contracts, and Web Env Group code/tests only while implementing touched areas |
| P2 Help AI Agents and System OpenAPI Bootstrap | `slices/P2-04-help-ai-agents-system-openapi-bootstrap.md`, `adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md`, `slices/P2-00-api-catalog-scalar.md`, `adr/ADR-0010-p2-api-catalog-scalar.md`, `slices/P2-02-public-api-substrate.md`, `adr/ADR-0012-p2-public-api-substrate.md`, `00-product-scope-and-priority.md`, `slices/P2-README.md`, `04-api-contract-guidelines.md`, `06-security-permission-workspace.md`, `08-frontend-routing-and-ui-rules.md`, `09-testing-and-acceptance-strategy.md` | `02-repo-structure-and-dev-workflow.md` only for AGENTS/workflow sync; relevant Help/AppLayout/tabs, auth registration, OpenAPI export, API Catalog service/model/storage, skill source/Docker, generated contracts, and tests only while implementing touched areas |
| P2 Cross-platform Distribution | `slices/P2-05-cross-platform-distribution.md`, `adr/ADR-0017-p2-cross-platform-distribution.md`, `adr/ADR-0019-p2-source-preview-startup.md` when changing source preview, `adr/ADR-0024-p2-user-local-release-installer.md` when changing installation, `adr/ADR-0007-p0-runtime-bootstrap-packaging.md`, `p0-runtime-bootstrap-plan.md`, `00-product-scope-and-priority.md`, `slices/P2-README.md`, `02-repo-structure-and-dev-workflow.md`, `05-runner-protocol-and-run-state-machine.md`, `06-security-permission-workspace.md`, `09-testing-and-acceptance-strategy.md` | `slices/P1-00-monitoring.md`, `slices/P2-02-public-api-substrate.md`, `adr/ADR-0012-p2-public-api-substrate.md`, and relevant Make, bootstrap, Runtime builder, Compose, Dockerfile, release workflow, SSH Demo node, README, and verifier code/tests only while implementing touched areas |
| P2 LAN-first Release Bootstrap | `slices/P2-06-lan-first-deployment-usability.md`, `adr/ADR-0018-p2-lan-first-release-bootstrap.md`, `adr/ADR-0020-p2-release-dual-runtime-default.md`, `adr/ADR-0021-p2-release-up-configuration-confirmation.md`, `adr/ADR-0024-p2-user-local-release-installer.md`, `slices/P2-05-cross-platform-distribution.md`, `adr/ADR-0017-p2-cross-platform-distribution.md`, `slices/P1-00-monitoring.md`, `slices/P2-02-public-api-substrate.md`, `02-repo-structure-and-dev-workflow.md`, `05-runner-protocol-and-run-state-machine.md`, `06-security-permission-workspace.md`, `09-testing-and-acceptance-strategy.md` | Relevant release wrapper, bootstrap/preflight, release Compose/env/README, API session configuration, workflows, and focused tests only; source Compose code only for regression proof |
| P2 Public Launch, GitHub Pages, and SEO | `slices/P2-07-public-launch-github-pages-seo.md`, `adr/ADR-0026-p2-public-launch-github-pages-seo.md`, `adr/ADR-0025-public-user-documentation-localization.md`, `adr/ADR-0013-p2-static-marketing-landing-logo.md`, `public-launch-github-pages-and-star-growth-plan.md`, `00-product-scope-and-priority.md`, `02-repo-structure-and-dev-workflow.md`, `08-frontend-routing-and-ui-rules.md`, `09-testing-and-acceptance-strategy.md`, `slices/P2-05-cross-platform-distribution.md`, `slices/P2-06-lan-first-deployment-usability.md` | `docs/site`, root README/localizations, `apps/web` index plus Marketing Landing only for `noindex`, visual-reference parity, exact public Docs/repository targets, and truthful presentation-label corrections, GitHub metadata/workflows, release assets, and focused tests only while implementing the touched P2-07 PR |
| Public User Documentation MVP | `00-product-scope-and-priority.md`, `02-repo-structure-and-dev-workflow.md`, `adr/ADR-0025-public-user-documentation-localization.md`, `README.md`, `slices/P2-05-cross-platform-distribution.md`, `slices/P2-06-lan-first-deployment-usability.md` | Relevant Make targets, release wrapper/installer, Web routes/copy, completed P0/P1/P2 Slice SDDs, VitePress locale configuration, and tests only while verifying statements included in the six authoritative English pages, their exact `zh-CN` / `ja` mirrors, locale-relative links, and source/release `.env.example` reference coverage |

## Required workflow

For any feature touching more than one app:

1. Read the relevant Slice SDD first.
2. Output an implementation plan before editing code.
3. Update contracts before consumers.
4. Keep the change limited to the active Slice.
5. Run verification commands before final response.
6. Update the Slice SDD or ADR only when implementation facts changed.

Simple bug fixes may be implemented directly, but they must still obey scope, contracts, tests, and verification gates.

Final responses must include:

- Changed files.
- Verification commands and results.
- Remaining risks or `None`.

## Service startup contract

When the user asks to start, restart, boot, run, or bring up SurgePilot services from a source checkout without explicitly narrowing the scope, use the official source full-stack entry:

```bash
make start-full-stack
```

On the first run, when root `.env` is absent, this entry creates `.env` from `.env.example`, persists explicitly inherited bootstrap identity/credential values, replaces remaining bootstrap placeholders with cryptographically random values, and creates private Monitoring token, Demo password, and Demo SSH host-key state with owner-only permissions. Concurrent first-run processes may accept one safely published winner. Existing `.env`, secret files, and complete Demo identities are never overwritten, rotated, or repaired automatically; unsafe ownership, permissions, symlinks, partial identities, empty files, and conflicting inherited values fail closed. It then runs `make release-runtime`, which builds or reuses the Runtime inside the native Linux Docker builder, validates the full source Compose configuration, and starts P1 Monitoring plus the Compose-internal Demo Load Node. Restart preflight completes before the existing stack is stopped.

Source full-stack startup uses Compose-internal API and InfluxDB origins for the Demo node. Every external Load Node requires explicit final `SURGEPILOT_NODE_API_BASE_URL` and `SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL` values, regardless of the Demo enable switch. Do not reintroduce automatic host-interface discovery or a public host-only intermediate variable.

When the user explicitly asks only to open the login page, inspect UI/pages, or review the
control plane without Runtime/Demo readiness, use:

```bash
make start-preview
```

This source-only entry uses the same secure `.env` bootstrap and Monitoring-capable source Compose
topology, but skips Runtime preparation and the Demo profile through process-local values that do
not rewrite `.env`. State clearly that Setup Status may report `not_configured` and that Load Node
initialization and Run execution readiness are not promised. Use `make stop-preview` to stop it.

When a user installs a tagged P2-05/P2-06 release through ADR-0024, use `surgepilot up`, `surgepilot down`, `surgepilot status`, or `surgepilot logs`; a manually extracted bundle uses the `./surgepilot` spelling. The installer runs without `sudo`, never modifies shell configuration, and never calls `up` inside the download pipeline. On a missing release `.env`, `up` requires an interactive host shell, confirms the host/ports without asking for Runtime architectures, persists `amd64,arm64`, validates both Runtime sets before service startup, and fails closed in non-TTY automation unless a complete `.env` is pre-provisioned. Every valid `up` prints the bounded non-secret effective configuration before Runtime fetch. Interactive startup uses default-Yes `[Y/n]`: accepting current state is read-only, while No repeats first-run entry or opens a standard-LAN loop that updates only four allowlisted network fields after normalized review and Yes. That update validates a private candidate and final reviewed SHA-256, then uses standard `os.replace`; simultaneous manual same-user editing in the final syscall window is unsupported, with no backup or automatic rollback. A post-replacement directory-fsync failure halts before Runtime/Compose and requires inspection of `.env`. Non-interactive existing startup prints the summary but never prompts or rewrites; automatic rewriting remains forbidden. Advanced HTTPS No requires explicit manual `.env` editing. Runtime, Demo, cookie, credentials, secrets, and other non-network state remain authoritative. Explicit `localhost`, `127.0.0.1`, or `::1` is a warned local-evaluation choice for the persisted node-facing URLs; it does not make Docker's published ports loopback-only. Non-loopback remains the LAN/external-node path and required smoke contract. Release Compose pulls immutable image digests, fetches validated Runtime assets, publishes the configured Nginx and authenticated InfluxDB ports on host interfaces, disables Demo by default, and never builds application source. Source startup does not use the release confirmation or rewrite path.

`SURGEPILOT_SKIP_RUNTIME_PREFLIGHT=1 make start-full-stack` is an explicit local manual/debug runtime opt-out only. It does not skip first-run deployment bootstrap. That path does not promise default runtime readiness; Setup Status may report `not_configured` or `artifact_missing` when the version or artifact is absent.

Do not substitute smoke, base, SSH E2E, verifier, or test-only compose profiles for a generic user-facing startup request.

If the user asks for a complete demo, Load Node/Run verification, or Runtime readiness, use a full-stack target. Preview is sufficient only for explicit login-page, UI/page, Monitoring/Grafana, or control-plane inspection without execution readiness.

If the user asks for two SSH Load Nodes and manual review/demo, use:

```bash
make start-full-ssh-e2e
```

This target is the manual-review fast path: it reuses the existing local `docker-ssh-load-node:latest` image, builds or reuses the `p0-e2e` Runtime through `scripts/run_runtime_builder.py --fixed-version`, disables the internal Demo profile, builds only the app/web images, and starts two SSH E2E Load Nodes with Compose `--no-build`.

Use lightweight smoke, SSH E2E, or verifier targets only when the user explicitly asks for automated verification, CI-style smoke, or a narrowed E2E test.

## P1 active-scope guardrails

If this section conflicts with `docs/sdd/00-product-scope-and-priority.md`, follow that SDD and update this synced copy.

P1 work is allowed only when an explicit P1 task names the active P1 Slice SDD. Do not implement these unless an explicit P1/P2 task and accepted scope source allows them:

- API Catalog (P2 documentation asset management only; not P1).
- OpenAPI / Swagger Spec upload.
- API Spec detail pages.
- Creating Test Plans from API operations.
- Any OpenAPI / API Catalog → Scenario/Test Plan generation chain.
- OpenAPI Step auto-generation outside active `P2-01-openapi-step-generation`.
- Schedule Run (P2).
- Scheduled Job (P2).
- Upcoming Scheduled Jobs statistics (P2).
- Product Help page outside active `P2-04-help-ai-agents-system-openapi-bootstrap`.
- Public API skill download outside P2-04. P2-05 authorizes platform release bundles, application images, checksummed Linux Runtime assets, and their bounded bootstrap only; standalone AI skill release, signing, skill installer, marketplace, SDK, MCP server, or skills runtime remain forbidden.
- User/external automatic OpenAPI ingestion, retry worker, startup reconciliation, or API Catalog import beyond the P2-04 first-Admin system curated OpenAPI exception.
- OAuth 2.0.
- OIDC.
- SAML.
- LDAP.
- Env Group Secret work outside active `P2-03-env-group-secret`.
- Env Group tags and Dependency File tags (removed from all stages).
- Secret Snapshot encryption and key rotation outside active `P2-03` temporary internal runtime boundary.
- Non-MinIO storage.
- ZIP / TAR / TGZ automatic extraction (P2).
- Editable Taurus YAML.

P1 allowed areas remain limited to the P1 scope gate and accepted ADR additions. Examples include cURL import, Monitoring read-only entry plus JMeter Backend Listener / InfluxDB write config, Resource multi-node, Workspace/Admin UI, Scenario/TestPlan polish, Dependency single-file preview, Run Report preview, and ADR-0008/P1-08 Debug HTTP Trace. Each allowed area still requires its own real Slice SDD before implementation.

Forbidden infrastructure unless separately authorized:

- Kubernetes.
- Redis.
- Celery.
- RabbitMQ.
- Kafka.
- External queue services.
- Microservice split.
- Complex API Gateway policy layer.
- Custom authorization platform.
- Custom UI component library.

Allowed extension points:

- P1-09 Scenario Global Configuration Phase A is allowed only for structured `Settings` / `Headers` / `Variables` / `Data Sources` Tabs through `ADR-0015`; Phase B `globalScripts`, editable Taurus YAML, Scenario Secret variables, JMeter expert panels, Test Plan schema redesign, Schedule, multi-node, script libraries, and API Catalog generation remain forbidden unless separately authorized.
- P1/P2 README or roadmap documents.
- Future enum values if not activated outside the active Slice.
- Non-user-visible compatibility fields if they do not create usable out-of-scope behavior.
- Navigation planning in docs, but no clickable usable entry outside the active Slice.
- P1 no longer includes any OpenAPI / API Catalog → Scenario/Test Plan generation chain; P1 Import means cURL import only.
- P1 Monitoring excludes Grafana datasource management, Dashboard editing, and InfluxDB management; it is limited to JMeter Backend Listener + InfluxDB write config and read-only Monitoring entry.
- P1 Debug HTTP Trace is limited to Debug Run `debug_http_trace` artifact parsing and Run Report display; Standard Run request/response tracing, JMeter plugins, Backend Listener, Monitoring, generic logging/sanitization framework, runtime tar changes, and standalone Groovy SFTP distribution remain forbidden.

## Architecture constraints

- The repo is a monorepo for P0/P1.
- `apps/runner` is an independent application.
- Runner must not import `apps/api` internal code.
- API and Runner communicate through `packages/contracts` and documented protocol only.
- Web must not invent API shapes outside OpenAPI/contracts.
- Web must not access PostgreSQL, MinIO, or Load Nodes directly.
- API owns database, MinIO access, auth, authorization, workspace enforcement, and audit-relevant decisions.
- Runner owns process execution behavior and reports through runner protocol callbacks.
- Fake runner may be used for development and tests, but cannot replace final real or near-real Runner acceptance.

## Contract-first rules

- FastAPI routes and Pydantic schemas are the OpenAPI source of truth.
- `packages/contracts/openapi/api.openapi.json` is an exported artifact and must not be handwritten.
- Do not create handwritten `openapi.yaml` as the primary contract source.
- Web client/types must be generated from exported OpenAPI.
- P2-02 adds `packages/contracts/openapi/public-api.openapi.json` as a second generated artifact for external programmatic consumers.
- P2-02 authorizes only the repo-maintained source package at `packages/ai-skills/surgepilot-public-api/`; it must use the bundled snapshot copied from `public-api.openapi.json`, accept allowlisted public `operationId` values only, require explicit Workspace context and write confirmation, and remain outside Web static assets or release distribution. P2-04 may expose the same source as a session-authenticated request-built zip, but does not create a release/version/update channel.
- ADR-0016/P2-04 adds `GET /api/v1/account/ai-skill/download` only to the Web/business artifact; it is current-user session auth, not Workspace-scoped, and its route-local `AI_SKILL_SOURCE_NOT_AVAILABLE` code must not enter `info.x-surgepilot-error-codes` or `public-api.openapi.json`.
- P2-04 system OpenAPI bootstrap must call the shared API-owned `_export_document(app.openapi(), public=False)` behavior, use an independent post-registration `SessionLocal` transaction, deduplicate by Default Workspace active SHA-256, and preserve registration success on every import failure path.
- ADR-0017/P2-05 authorizes only the platform release bundle, three SurgePilot-owned multi-architecture application image packages, architecture-specific Linux Runtime assets, and the bounded `./surgepilot` lifecycle entry. Release Compose must use immutable image digests and no application build contexts; the Public API AI skill must not become a standalone release artifact.
- ADR-0018/P2-06 amends only the release startup contract: interactive first-run host persistence,
  Demo-off default, strict cookie transport, default InfluxDB publication, an explicit warned
  loopback-origin exception, and non-interactive smoke `.env` fixtures. ADR-0020 changes only new
  tagged-release deployments to default to `amd64,arm64` without an architecture prompt; existing
  Runtime values and all four accepted advanced Runtime values remain authoritative. ADR-0021
  requires bounded pre-Runtime display for every valid `up`; interactive default-Yes is read-only,
  explicit No/re-entry/Yes may update only four allowlisted standard-LAN network fields through a
  final reviewed-SHA check and standard `os.replace`,
  non-interactive startup never rewrites, and advanced HTTPS is manual-edit-only. Both selected
  Runtime sets validate before Compose startup. Automatic repair, secrets/non-network changes, and
  source startup changes remain forbidden. Source startup remains native-only and root
  `.env.example` remains `auto`. Loopback changes persisted node-facing URLs, not the
  all-interface published-port bind. These ADRs add no P2-02, API, DB, migration, Web, OpenAPI,
  Workspace, permission, Runner protocol, Runtime-format, or public GitHub publication capability.
- ADR-0013 adds only a static public `/` Marketing Landing and Logo migration. ADR-0026/P2-07 narrowly authorizes its exact public Docs/repository targets and truthful open-source/self-hosted/illustrative presentation labels; neither authorizes API, DB, migrations, runner, contracts, SDK, MCP, Help, Community, API Guide, hosted status, or external runtime design assets.
- ADR-0014 / P2-03 adds Env Group typed secret handling only within its Slice contract; public OpenAPI must use plain-only Env Group DTOs and must not expose hidden-value fields, masked-read fields, secret write/copy examples, or reconstructable protected-variable fields.
- The public OpenAPI artifact must not include `/api/v1/account/api-tokens`, token-management schemas, PAT plaintext fields, `secretHash`, example token values, browser session/CSRF routes, or internal runner routes.
- Web must consume generated client/types through the `@surgepilot/contracts` workspace dependency.
- Web must not import generated files through relative paths into `packages/contracts/generated/...`.
- Internal runner endpoints must not enter the Web generated client.
- Run `make generate-contracts` after API schema changes.
- `make verify` must fail when generated contracts or OpenAPI artifacts are stale.

## Naming and data conventions

- API JSON fields: `camelCase`.
- DB columns, migrations, and ORM fields: `snake_case`.
- API enum values: lower `snake_case`.
- External business IDs: ULID strings.
- Store ULID IDs as `text` or `char(26)`, not PostgreSQL `uuid`.
- Time format: ISO 8601 UTC string with `Z`.
- Workspace context: `x-workspace-id` header; route paths must not contain workspace ID.
- Missing `x-workspace-id`: fall back to the user's default Workspace only where the active Slice and security SDD allow it; otherwise return `400 WORKSPACE_REQUIRED` when no default can be resolved.
- P2-02 public API Workspace context: require explicit `x-workspace-id`, except a PAT allowlist with exactly one Workspace may resolve automatically; never read browser session, preferred Workspace, local storage, or default Workspace fallback.
- Auth: cookie-based session for Web/business APIs; PAT Bearer only for `/api/public/v1/*`.
- Write CSRF: `x-csrf-token` on browser session write APIs, including `/api/v1/account/api-tokens` `POST` and `DELETE`; PAT Bearer public writes do not use CSRF.
- P2-02 public scopes: `read`, `config:write`, `run`, `dependency:write`; `dependency:write` is limited to public Dependency File upload/delete, while list uses `read`. `tokens:write`, token-on-token, and admin-managed tokens remain forbidden.
- Runner auth: `x-runner-token` on internal runner endpoints.
- Request ID: API generates and returns `x-request-id`.
- Package names should use the `@surgepilot/*` workspace namespace where applicable.

## Image build sources

- API Docker images may accept opt-in build mirrors through `PIP_INDEX_URL` and `UV_INDEX_URL`, wired from `SURGEPILOT_PIP_INDEX_URL` in Compose.
- Web Docker images may accept an opt-in npm mirror through `NPM_REGISTRY`, wired from `SURGEPILOT_NPM_REGISTRY` in Compose.
- SSH Load Node Docker images may accept opt-in apt mirrors through `APT_MIRROR` and `APT_SECURITY_MIRROR`, wired from `SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_*` and `SURGEPILOT_DOCKER_BUILD_DEBIAN_APT_*` in Compose.
- Defaults must remain upstream PyPI/npm/apt; mirror examples in `.env.example` stay commented and are for restricted build networks only.
- Build mirror variables are not runtime System Settings and must not be shown or edited in the System Settings UI.

## Language rules

- Source code must use English.
- Identifiers, comments, logs, API messages, error messages, examples, seed data, test names, and commit messages must use English.
- API `message` fields are English fallback text, not i18n keys.
- Frontend localization should key off stable error `code` values, not API `message` text.
- SDD prose may be Chinese, but code examples inside docs must use English.

## Verification gates

Prefer the repository-level commands:

```bash
make generate-contracts
make verify
```

During Slice work, if full `make verify` is not available or the active Slice narrows validation, run the closest available subset, state the gap, and keep the implementation on a path that converges to `make verify`.

The P0-final target state for `make verify` includes at least:

- lint and format checks.
- typecheck.
- API unit/integration tests.
- Web unit/component tests.
- Runner unit/protocol tests.
- line and branch coverage gates.
- patch coverage gate.
- contract tests.
- generated contract freshness checks.
- OpenAPI stale check.
- public API schema checks.

`make verify` does not include real SSH E2E and does not include full browser Playwright E2E by default unless a Slice explicitly adds a stable lightweight smoke check.

Use this for nightly, release, or main-merge validation:

```bash
make verify-e2e
```

P0 final `make verify-e2e` should include:

- Playwright P0 happy path.
- Playwright Stop path.
- fake-runner full-flow smoke.
- real SSH runner smoke when the environment profile provides an SSH-capable Load Node.

## Documentation backfill

After each Slice implementation, update the corresponding Slice SDD only for engineering facts:

- Actual implementation differences from the SDD.
- New or adjusted API contract.
- New tests and verification commands.
- Remaining risks.
- Preconditions that later Slices must know.

If a major architecture choice is made, add or update an ADR.

Do not use documentation backfill to expand product scope.

## Review checklist

Before claiming completion, verify:

- The change stays inside the active Slice.
- No out-of-scope P1/P2 user-visible capability was introduced.
- API contracts were updated before consumers.
- Web uses `@surgepilot/contracts`.
- Runner does not import API internals.
- Workspace and permission checks are enforced on the backend.
- Path safety is covered for Dependency Files and artifacts.
- Private Load Node credentials are never returned in plaintext.
- Run state transitions are safe against late callbacks.
- Stop behavior is idempotent.
- Load Nodes cannot remain permanently Busy after failure paths.
- Relevant tests and verification commands passed.
