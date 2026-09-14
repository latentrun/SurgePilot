# SurgePilot Agent Instructions

Authoritative source: `docs/sdd/02-repo-structure-and-dev-workflow.md` §12. This file is a synced operational copy. If there is any conflict, follow 02 and update this file.

## Current target

P0 is the completed baseline. P1 work may start only through a named P1 Slice SDD that references `docs/sdd/00-product-scope-and-priority.md` §6 and `docs/sdd/slices/P1-README.md`. The completed P1 Slice surfaces are `docs/sdd/slices/P1-00-monitoring.md`, `docs/sdd/slices/P1-01-resource-multi-node.md` with `docs/sdd/adr/ADR-0009-p1-resource-multi-node.md`, `docs/sdd/slices/P1-03-workspace-admin.md`, `docs/sdd/slices/P1-04-scenario-testplan-polish.md` as amended by `docs/sdd/adr/ADR-0023-remove-scenario-execution-preview.md`, `docs/sdd/slices/P1-05-curl-import.md`, `docs/sdd/slices/P1-06-dependency-preview.md`, and `docs/sdd/slices/P1-08-debug-http-trace.md` through `docs/sdd/adr/ADR-0008-p1-debug-http-trace.md`. P1 work must not regress the P0 execution loop, P0-Stability, contract-first workflow, Workspace isolation, permission enforcement, Runner/API/Web boundaries, and verification gates.

The current delivery target is **P2-02 Public API Substrate and governed Public API AI skill source package implementation plus P2-03 Env Group Secret implementation plus P2-04 Help AI Agents and System OpenAPI Bootstrap**. P2 work may start only when a task names the active P2 Slice SDD and its accepted ADR. The active P2 surfaces are:

- `docs/sdd/slices/P2-00-api-catalog-scalar.md` through `docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md`;
- `docs/sdd/slices/P2-01-openapi-step-generation.md` through `docs/sdd/adr/ADR-0011-p2-openapi-step-generation.md`;
- `docs/sdd/slices/P2-02-public-api-substrate.md` through `docs/sdd/adr/ADR-0012-p2-public-api-substrate.md`;
- `docs/sdd/slices/P2-03-env-group-secret.md` through `docs/sdd/adr/ADR-0014-p2-env-group-secret.md`;
- `docs/sdd/slices/P2-04-help-ai-agents-system-openapi-bootstrap.md` through `docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md`.

P2-03 is limited to Env Group `plain | secret` typed variables, session masked secret read models, session-only secret writes, plain-only public DTOs, the required one-time string-map-to-plain migration `0017_p2_03_env_group_secret`, and public API secret exclusion. It does not authorize Snapshot encryption, key rotation, a reveal API, external Secret Manager integration, or a generic redaction framework. Other P2 capabilities remain out of scope unless separately authorized by an accepted ADR or PRD update.

P2-04 is limited to authenticated Help AI Agents guidance, a session-authenticated request-built Public API AI skill source download, shared runtime/script OpenAPI export, and a best-effort first-Admin import of SurgePilot's own curated Web/business OpenAPI into the Default Workspace API Catalog. It does not authorize user/external automatic OpenAPI ingestion, retries/workers, SDK, MCP, marketplace, installer, release publication, built-in agent runtime, AI generation/tuning/analysis, or API Catalog to Scenario/Test Plan generation.

P1-08 is limited to Debug Run HTTP Trace; it does not authorize Standard Run tracing, Monitoring, Grafana, InfluxDB, JMeter plugins, a generic logging or sanitization framework, runtime tar changes, or standalone Groovy distribution.

## Canonical documents

- Product source: `docs/prd/PRD.md`
- Scope gate: `docs/sdd/00-product-scope-and-priority.md`
- Workflow source: `docs/sdd/02-repo-structure-and-dev-workflow.md`
- P1 governance ADR: `docs/sdd/adr/ADR-0022-p1-governance-start.md`
- P1 Slice index: `docs/sdd/slices/P1-README.md`
- Active Slice: `docs/sdd/slices/P1-08-debug-http-trace.md`
- Active Slice ADR: `docs/sdd/adr/ADR-0008-p1-debug-http-trace.md`
- P2 Slice index: `docs/sdd/slices/P2-README.md`
- P2 API Catalog activation ADR: `docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md`
- P2 API Catalog Slice: `docs/sdd/slices/P2-00-api-catalog-scalar.md`
- P2 OpenAPI Step Generation activation ADR: `docs/sdd/adr/ADR-0011-p2-openapi-step-generation.md`
- P2 OpenAPI Step Generation Slice: `docs/sdd/slices/P2-01-openapi-step-generation.md`
- P2 Public API activation ADR: `docs/sdd/adr/ADR-0012-p2-public-api-substrate.md`
- P2 Public API Slice: `docs/sdd/slices/P2-02-public-api-substrate.md`
- P2 Env Group Secret activation ADR: `docs/sdd/adr/ADR-0014-p2-env-group-secret.md`
- P2 Env Group Secret Slice: `docs/sdd/slices/P2-03-env-group-secret.md`
- P2 Help AI Agents and System OpenAPI Bootstrap activation ADR: `docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md`
- P2 Help AI Agents and System OpenAPI Bootstrap Slice: `docs/sdd/slices/P2-04-help-ai-agents-system-openapi-bootstrap.md`

## Execution rules

- Keep implementation inside the named active Slice.
- Update contracts before consumers; keep API, Web, Runner, and artifact boundaries consistent.
- Preserve P0 behavior and security properties.
- Keep the generated OpenAPI artifacts, generated Web client/types, and bundled Public API AI skill snapshot synchronized with the FastAPI/Pydantic schema source.
- Use the Slice's verifiable Done When criteria before claiming completion.
