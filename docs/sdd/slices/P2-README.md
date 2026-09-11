# P2 Slice index

P2 capabilities require a named accepted Slice SDD and its governing ADR. This index does not
activate later capabilities by itself.

## Active reconstruction surface

`P2-00-api-catalog-scalar.md` is active through `ADR-0010`. It covers documentation asset
management only: upload, list, detail, authorized content proxy, delete, and read-only Scalar
rendering. It does not authorize Scenario/Test Plan generation, operation import, request sending,
or the P2-04 system OpenAPI bootstrap exception governed by `ADR-0016`.

`P2-01-openapi-step-generation.md` is active through `ADR-0011`. It covers Scenario-editor
OpenAPI Step draft generation from authorized API Catalog spec assets; it does not authorize
API Catalog generation actions, Scenario/Test Plan generation, remote fetches, or conversion
services.

## P2-00 factual backfill

- API routes live in `apps/api/app/routes/api_catalog.py` and are registered by `apps/api/app/main.py`.
- Metadata is persisted by `apps/api/app/models/api_catalog.py` and migration
  `apps/api/migrations/versions/0015_p2_00_api_catalog.py`; raw content remains behind the existing
  server-side storage boundary under `api-catalog-specs/{workspaceId}/{specId}/{safeFilename}`.
- The generated source of truth is `packages/contracts/openapi/api.openapi.json`, with generated
  client/types consumed by the Web API client.
- The Web routes are `/api-catalog` and `/api-catalog/:specId`; Scalar is pinned to
  `@scalar/api-reference-react@0.9.47` and receives only the same-origin content URL.
- Verification coverage is in `apps/api/tests/test_p2_00_api_catalog_api.py`,
  `packages/contracts/tests/api-catalog-openapi.test.mjs`, and
  `apps/web/src/features/api-catalog/api-catalog.test.tsx`.

## P2-01 factual backfill

- Scenario-scoped generation is registered in `apps/api/app/routes/scenarios.py`; parsing and mapping are in `apps/api/app/services/openapi_step_generation.py`, with schemas in `apps/api/app/schemas/scenarios.py`.
- The focused verification set is `apps/api/tests/test_p2_01_openapi_step_generation.py`, `tests/contract/test_p2_01_openapi_step_generation_openapi.py`, and the OpenAPI interaction test in `apps/web/src/features/scenarios/scenarios.test.tsx`.
- P2-01 remains transient: confirming a preview changes only the in-memory Scenario draft; the existing Scenario save/PATCH flow remains the persistence boundary. API Catalog deletion or replacement does not rewrite generated Steps, and API Catalog detail has no generation/import action.

Other P2 slices remain outside this checkpoint and require their own accepted scope and
implementation history.
