# Architecture Decision Records

This directory records SurgePilot architecture decisions.

ADR documents explain **why** a decision was made, which alternatives were rejected, and what constraints future work must preserve. SDD documents remain the source for concrete rules, API contracts, data models, and implementation details.

## Index

| ADR | Title | Status | Scope |
| --- | --- | --- | --- |
| [ADR-0001](ADR-0001-monorepo.md) | Monorepo | Accepted | Repository structure and P0 workflow |
| [ADR-0002](ADR-0002-runner-independent-app.md) | Runner Independent App | Accepted | Runner/API/contracts boundary |
| [ADR-0003](ADR-0003-p0-minio-only.md) | P0 MinIO Only | Accepted | Dependency Files and Run Artifacts storage |
| [ADR-0004](ADR-0004-p0-manual-single-node-only.md) | P0 Manual Single Node Only | Accepted | P0 resource selection |
| [ADR-0005](ADR-0005-p0-no-api-catalog-no-monitoring-no-schedule.md) | P0 No API Catalog, Monitoring, or Schedule | Accepted | P0 product boundary |
| [ADR-0006](ADR-0006-p0-separate-api-worker.md) | P0 Separate API Worker | Accepted | Background jobs and self-healing |
| [ADR-0007](ADR-0007-p0-runtime-bootstrap-packaging.md) | P0 Runtime Bootstrap Packaging | Accepted | P0 Load Node runtime packaging and Runner execution path |
| [ADR-0008](ADR-0008-p1-debug-http-trace.md) | P1 Debug HTTP Trace | Accepted | P1 Debug Run diagnostics and Runner artifact boundary |
| [ADR-0009](ADR-0009-p1-resource-multi-node.md) | P1 Resource Multi-node | Accepted | P1 Standard Test Plan multi-node execution |
| [ADR-0010](ADR-0010-p2-api-catalog-scalar.md) | P2 API Catalog Scalar | Accepted | P2 API Catalog documentation asset management and Scalar rendering |
| [ADR-0011](ADR-0011-p2-openapi-step-generation.md) | P2 OpenAPI Step Generation | Accepted | P2 Scenario editor OpenAPI Step draft generation |
| [ADR-0012](ADR-0012-p2-public-api-substrate.md) | P2 Public API Substrate | Accepted | P2-02 programmatic public API and public OpenAPI artifact |
| [ADR-0013](ADR-0013-p2-static-marketing-landing-logo.md) | P2 Static Marketing Landing and Logo | Accepted | Static public `/` Marketing Landing and Logo visual migration only |
| [ADR-0014](ADR-0014-p2-env-group-secret.md) | P2 Env Group Secret | Accepted | P2 Env Group variable type contract, masking boundary, public API exclusion, Run Snapshot temporary security boundary |
| [ADR-0015](ADR-0015-p1-scenario-global-configuration.md) | P1 Scenario Global Configuration Phase A | Accepted | Scenario-level structured Global Configuration Tabs, global headers, Scenario-local non-secret variables, and CSV Data Sources reuse |
| [ADR-0016](ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md) | P2 Help AI Agents and System OpenAPI Bootstrap | Accepted | Authenticated Help AI Agents guidance, Public API AI skill source download, and first-Admin system OpenAPI bootstrap import |
| [ADR-0017](ADR-0017-p2-cross-platform-distribution.md) | P2 Cross-platform Distribution and Full-stack Release Bootstrap | Accepted | Tagged release bundle, multi-architecture application images, and Linux Runtime assets |
| [ADR-0018](ADR-0018-p2-lan-first-release-bootstrap.md) | P2 LAN-first Interactive Release Bootstrap | Accepted | Interactive release host configuration, explicit local-only evaluation, and external-node-first acceptance |
| [ADR-0019](ADR-0019-p2-source-preview-startup.md) | P2 Source Preview Startup | Accepted | Source-only control-plane preview and visible Runtime build progress without changing full/release readiness |
| [ADR-0020](ADR-0020-p2-release-dual-runtime-default.md) | P2 Release Dual-Architecture Runtime Default | Accepted | New tagged-release deployments acquire amd64 and arm64 Runtime sets without an architecture prompt |
| [ADR-0021](ADR-0021-p2-release-up-configuration-confirmation.md) | P2 Release `up` Configuration Confirmation | Accepted | Default-Yes release configuration review and explicit interactive four-field standard-LAN update |
| [ADR-0022](ADR-0022-p1-governance-start.md) | P1 Governance Start | Accepted | P1 governance, Slice SDD kickoff, and agent execution contract |
| [ADR-0023](ADR-0023-remove-scenario-execution-preview.md) | Remove Scenario Execution Preview | Accepted | Test Plan-only Generated YAML Preview product boundary |
| [ADR-0024](ADR-0024-p2-user-local-release-installer.md) | P2 User-local Release Installer | Accepted | Version-pinned, no-sudo platform Release installer plus separate interactive `surgepilot up` |
| [ADR-0025](ADR-0025-public-user-documentation-localization.md) | Public User Documentation Localization | Accepted | Simplified Chinese and Japanese mirrors of the bounded six-page VitePress user guide |
| [ADR-0026](ADR-0026-p2-public-launch-github-pages-seo.md) | P2 Public Launch, GitHub Pages, and SEO | Accepted | Unified VitePress public site, original AI-authored baseline evidence, SEO, and self-hosted indexing boundary |

## Status Values

Use one of these status values:

| Status | Meaning |
| --- | --- |
| `Proposed` | Draft decision under discussion. Do not implement as final contract. |
| `Accepted` | Active decision. Implementation and SDDs must preserve it. |
| `Deprecated` | Decision is obsolete but not directly replaced. New work must not depend on it. |
| `Superseded by ADR-XXXX` | Decision was replaced by another ADR. The replacement ADR must explain the migration. |

## Required ADR Sections

Each ADR must include:

1. `Status`.
2. `Scope`.
3. `Context`.
4. `Options Considered`.
5. `Decision`.
6. `Consequences`.
7. `Related ADRs` when the decision depends on another ADR.
8. `References` to relevant PRD, SDD, Slice, contract, or code paths.

## Reference Policy

1. Reference `docs/prd/PRD.md` when the decision directly follows product scope or priority.
2. Reference Foundation SDDs for architecture, contracts, security, storage, testing, and workflow rules.
3. Reference Slice SDDs when the ADR constrains or explains a concrete P0 slice.
4. Reference related ADRs explicitly instead of relying only on prose.
5. Do not use ADRs to introduce implementation details that belong in SDDs or code.

## Review Rules

Before accepting an ADR change, verify:

1. ADR numbering is unique.
2. Status value is valid.
3. Referenced repository paths exist.
4. The ADR does not conflict with PRD, `00-product-scope-and-priority.md`, or active Slice SDDs.
5. The ADR explains alternatives and consequences, not only the selected result.
