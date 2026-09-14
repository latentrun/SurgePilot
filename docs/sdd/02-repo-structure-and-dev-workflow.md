# 02. Repository Structure and Development Workflow

- Current delivery target: P2-02 Public API Substrate, P2-03 Env Group Secret, and P2-04 Help AI Agents and System OpenAPI Bootstrap under their accepted Slice ADRs

## Repository layout

```text
apps/
  api/                 FastAPI application, worker entrypoint, and migrations
  runner/              independent Runner application
  web/                 React application
packages/
  contracts/           OpenAPI output, generated Web client, Runner JSON Schemas
infra/
  docker/              Compose and container support
tests/
  contract/            cross-application contract checks
  e2e/                 end-to-end and real/fake Runner profiles
docs/
  prd/                 product requirements
  sdd/                 foundation, ADR, and Slice design documents
Makefile                stable repository commands
```

Applications must not import another application's private internals. Web consumes the generated client from `packages/contracts`; Runner and API communicate through versioned HTTP and JSON contracts.

## Root command contract

The repository exposes stable commands for bootstrap, development, contract generation, lint, type checking, tests, verification, and E2E verification. `make verify` is the default local and CI gate. `make verify-e2e` owns fake-Runner and configured real-SSH acceptance. Exact commands may begin as an M0 bootstrap subset but must retain their names as implementation grows.

## Contract-first workflow

1. Update the API schema or Runner JSON Schema source.
2. Generate committed OpenAPI, client, and schema artifacts.
3. Implement producers and consumers.
4. Add tests for behavior and contract freshness.
5. Run the root verification entrypoint.

Generated files are never edited by hand. Verification fails when generated artifacts are stale.

## Local development

Dependencies run in Docker Compose while Web, API, api-worker, and Runner may run from source. Environment examples contain placeholders only; real credentials and local overrides are ignored by version control. Database changes use append-only Alembic revisions rather than runtime schema creation.

## Scope discipline

Each change follows design -> schema/contracts -> backend -> Runner/Web -> generated artifacts -> tests -> factual documentation. Repository scaffolding must not introduce routes, services, dependencies, tables, or configuration for excluded future capability.

P0 is the completed baseline. P1 work may start only when the task names a real P1 Slice SDD and its accepted scope source; each Slice must include verifiable Done When criteria. P1 must not regress the P0 execution loop, P0-Stability, contract-first workflow, Workspace isolation, permission enforcement, Runner/API/Web boundaries, or verification gates. P2 remains out of scope unless separately authorized by an accepted ADR or PRD update; the active P2 Slice surfaces are listed in `docs/sdd/00-product-scope-and-priority.md` §7 and `docs/sdd/slices/P2-README.md`.

## 12. AI Coding / AGENTS.md Workflow

`AGENTS.md` is a synced operational copy of this document and must be updated whenever the active Slice or ADR authorization surface changes.

### 12.1 Required AGENTS.md files

The repository keeps a root `AGENTS.md` plus the application/package-level `AGENTS.md` files created during M0.

### 12.2 Root AGENTS.md minimum content

During P1/P2, `AGENTS.md` must list the current real P1/P2 Slice SDD. Accepted capabilities can only be implemented through the respective real Slice SDD and must not be directly authorized by placeholder or index content. Monitoring can only be implemented through `docs/sdd/slices/P1-00-monitoring.md`; Resource Multi-node only through `docs/sdd/slices/P1-01-resource-multi-node.md` and `docs/sdd/adr/ADR-0009-p1-resource-multi-node.md`; Scenario/Test Plan Polish only through `docs/sdd/slices/P1-04-scenario-testplan-polish.md` as amended by `docs/sdd/adr/ADR-0023-remove-scenario-execution-preview.md`; cURL Import only through `docs/sdd/slices/P1-05-curl-import.md`; Dependency File Preview only through `docs/sdd/slices/P1-06-dependency-preview.md`; Debug HTTP Trace only through `docs/sdd/slices/P1-08-debug-http-trace.md`.

P2-00 API Catalog Scalar can only be implemented through `docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md` and `docs/sdd/slices/P2-00-api-catalog-scalar.md`. P2-01 OpenAPI Step Generation can only be implemented through `docs/sdd/adr/ADR-0011-p2-openapi-step-generation.md` and `docs/sdd/slices/P2-01-openapi-step-generation.md`. P2-02 Public API Substrate can only be implemented through `docs/sdd/adr/ADR-0012-p2-public-api-substrate.md` and `docs/sdd/slices/P2-02-public-api-substrate.md`. P2-03 Env Group Secret can only be implemented through `docs/sdd/adr/ADR-0014-p2-env-group-secret.md` and `docs/sdd/slices/P2-03-env-group-secret.md`; it authorizes only Env Group typed variables, session masked reads, session-only secret writes, plain-only public DTOs, the required one-time migration, and public API secret exclusion, and does not authorize Snapshot encryption, key rotation, a reveal API, external Secret Manager integration, or a generic redaction framework. P2-04 Help AI Agents and System OpenAPI Bootstrap can only be implemented through `docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md` and `docs/sdd/slices/P2-04-help-ai-agents-system-openapi-bootstrap.md`; it authorizes only authenticated Help, the session request-built skill source download, shared runtime/script OpenAPI export, and first-Admin best-effort system curated OpenAPI import. No other P2 capability is activated.
