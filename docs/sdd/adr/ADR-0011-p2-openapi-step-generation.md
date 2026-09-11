# ADR-0011 P2 OpenAPI Step Generation

- Status: Accepted
- Scope: P2 Scenario editor OpenAPI Step draft generation from authorized API Catalog spec assets
- Active Slice: `docs/sdd/slices/P2-01-openapi-step-generation.md`
- Slice Status: Accepted for implementation; design frozen as the P2-01 Slice SDD
- Supersedes: none
- Depends on: `docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md` for API Catalog spec asset storage and authorized content access
- Does not supersede: P0/P1 execution flow, API Catalog documentation-only boundary, contract-first rules, MinIO-only storage boundary, Runner/API/Web boundaries, Workspace isolation, or P2 exclusions outside OpenAPI Step draft generation

## Context

The PRD and Scope Gate place OpenAPI Step automatic generation in P2. P2-00 introduced API Catalog documentation asset management, but deliberately did not activate API Catalog operation management or any API Catalog -> Scenario/Test Plan generation chain.

`docs/sdd/slices/P2-01-openapi-step-generation.md` defines a bounded Scenario editor helper: users edit an existing Scenario, choose an authorized API Catalog spec, select one or more OpenAPI / Swagger operations, preview generated HTTP Step drafts, and insert those drafts into the local Scenario draft. Persistence still happens only through the existing Scenario save flow.

## Decision

Activate `P2-01-openapi-step-generation` as the current P2 implementation Slice.

The accepted architecture is:

1. Add Scenario-scoped OpenAPI generation endpoints under `/api/v1/scenarios/{scenarioId}/openapi-step-generation/...` for available spec sources, operation summaries, and ordered Step draft previews.
2. Enforce session auth, Workspace context, Scenario edit permission, same-Workspace spec ownership, CSRF for browser POST, and safe error envelopes before any spec content is read or mapped.
3. Reuse API Catalog spec metadata/content as authorized input only; do not add API Catalog operation resources or lifecycle callbacks into Scenario.
4. Perform OpenAPI / Swagger validation server-side with `openapi-spec-validator>=0.9.0,<0.10.0`, then apply bounded SurgePilot-owned enumeration and Step mapping logic.
5. Keep generated Steps transient until the user confirms insertion and later saves the Scenario through the existing Scenario `PATCH` contract.
6. Reuse existing Scenario Step fields, generated contracts, AppLayout, route/module style, Tailwind tokens, CSS variables, source-owned primitives, and lucide icon system.
7. Keep Runner, Run, Test Plan, artifacts, scheduling, Help, SSO, Secret, non-MinIO storage, and API Catalog detail-page actions outside this Slice.

## Boundaries

In scope:

- Scenario-scoped spec source list, operation list, and ordered Step draft generation APIs.
- Server-side validation and bounded parsing of authorized Swagger 2.0 / OpenAPI 3.0 / OpenAPI 3.1 spec documents.
- Deterministic HTTP Step draft mapping for method, relative path, query params, safe headers, JSON body examples/default/minimum samples, warnings, and preview metadata.
- Web Scenario Designer `From OpenAPI` add-step mode with spec selection, multi-operation selection, ordering, preview, confirm, and cancel.
- API, contract, Web, E2E/smoke, and regression tests required by the Slice.

Out of scope:

- API Catalog detail-page `Generate Scenario`, `Generate Test Plan`, `Import operations`, or `From OpenAPI` actions.
- Creating Scenario, updating Scenario outside existing `PATCH`, generating Test Plan, creating Run, triggering Debug Run, or mutating API Catalog assets.
- API Catalog operation persistence/search/ownership, coverage, diff, mock, SDK, contract runner, schema registry, assertions, extractors, scripts, Taurus YAML generation, editable Taurus YAML, form/multipart/file upload mapping, remote `$ref` fetching, queues, background jobs, independent conversion services, external API gateways, direct Web storage access, new UI component systems, or DB migrations.

## Consequences

- `docs/sdd/00-product-scope-and-priority.md`, `docs/sdd/02-repo-structure-and-dev-workflow.md`, `docs/sdd/slices/P2-README.md`, `docs/sdd/slices/P2-01-openapi-step-generation.md`, root `AGENTS.md`, and this ADR must remain synchronized before code implementation proceeds.
- API contracts follow FastAPI/Pydantic schemas -> OpenAPI export -> generated `@surgepilot/contracts` client/types -> Web consumption.
- The implementation must backfill final API files, route registration paths, resolved parser package version, supported spec coverage, tests, verification commands, and risks in the Slice SDD.
- Any future change that adds API Catalog operation management, Scenario/Test Plan generation chains, remote reference fetching, persistence/cache tables, queues, external conversion services, a different storage backend, or a new UI system requires a new or updated ADR/Scope Gate before implementation.

## Implementation Backfill

- P2-01 depends on P2-00 only for authorized spec metadata/content access in the current Workspace. It does not depend on the P2-00 detail page's previous metadata/card layout, current embedded Scalar layout, Scalar DOM state, URL hash state, or browser-side OpenAPI parsing.
- The API Catalog detail page remains free of P2-01 actions: no Generate Scenario, Generate Test Plan, Import operations, or From OpenAPI entry is rendered there.
- Scenario Designer OpenAPI generation requests use the active Workspace (`currentWorkspace.id`, falling back to `defaultWorkspace.id`) and continue to call generated contract wrappers with `x-workspace-id`.
- Review hardening maps OpenAPI 3.x and Swagger 2.0 security schemes to safe `AUTH_HEADER_NOT_GENERATED` warnings without generated credential values, and skips unsupported parameter serialization with `UNSUPPORTED_PARAMETER_STYLE` instead of unsafe named-value stringification.
- Verification backfill: API/service coverage is in `apps/api/tests/test_p2_01_openapi_step_generation.py`, contract freshness and API Catalog operation-boundary checks are in `tests/contract/test_p2_01_openapi_step_generation_openapi.py`, and Scenario Designer preview/insertion plus API Catalog no-entry coverage is in `apps/web/src/features/scenarios/scenarios.test.tsx`. These tests preserve the transient-draft and spec-lifecycle boundaries; they do not authorize later P2 slices.
