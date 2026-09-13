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

`P2-02-public-api-substrate.md` is active through `ADR-0012`. It covers Account self-service API
keys on the browser session surface, PAT Bearer-authenticated public business operations under
`/api/public/v1/*`, the separate public OpenAPI artifact, bounded public Dependency File
operations, and one governed repo-maintained Public API AI skill source package. PAT
create/list/revoke stays session-only and self-only; it does not authorize public key-management
routes, admin-managed keys, an SDK, an MCP server, a skills runtime, or release publication of the
skill.

`P2-03-env-group-secret.md` is active through `ADR-0014`. It covers Env Group `plain | secret`
typed variables, session masked secret read models, session-only secret writes, plain-only public
DTOs, the required one-time string-map-to-plain migration `0017_p2_03_env_group_secret`, and public
API secret exclusion. It does not authorize Snapshot encryption, key rotation, a reveal API, or
external Secret Manager integration.

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

## P2-02 factual backfill

- Session token management lives in `apps/api/app/routes/account_api_tokens.py` with operation IDs `listAccountApiTokens`, `createAccountApiToken`, and `deleteAccountApiToken`; the programmatic routes live in `apps/api/app/routes/public_api.py` under `/public/v1/*`.
- The public OpenAPI artifact is `packages/contracts/openapi/public-api.openapi.json`, the internal artifact is `packages/contracts/openapi/api.openapi.json`, and the bundled skill snapshot is `packages/ai-skills/surgepilot-public-api/references/public-api.openapi.json`. `make generate-contracts` refreshes both artifacts and the skill snapshot, and `make contracts-stale-check` keeps them aligned.
- Verification coverage is in `apps/api/tests/test_p2_02_api_tokens_api.py`, `apps/api/tests/test_p2_02_public_api.py`, `apps/api/tests/test_p2_02_load_node_connectivity.py`, `tests/contract/test_p2_02_public_api_openapi.py`, `apps/web/src/features/account/api-keys.test.tsx`, and `apps/web/src/features/load-nodes/load-node-connectivity-summary.test.tsx`.
- Deployment `.env`/bootstrap/Makefile startup governance, the node-facing startup Make wiring, and the SSH lifecycle verifier (`scripts/verify_p2_02_public_api_lifecycle.py` and `tests/test_p2_02_public_api_lifecycle_verifier.py`) belong to the later startup checkpoint and are not part of R15.

## P2-03 factual backfill

- Typed Env Group variables live in `apps/api/app/schemas/env_groups.py` (`EnvGroupPlainVariableWrite`, `EnvGroupSecretVariableWrite`, `EnvGroupPlainVariableRead`, `EnvGroupSecretVariableRead`, the masked `EnvGroupDetail`, and the plain-only public DTOs); the typed service helpers are `normalize_variables`, `validate_variables`, `validate_public_variables`, `mask_variables`, `public_plain_variables`, `internal_env_values`, `env_group_runtime_values`, `env_group_has_secret_variables`, `reject_public_secret_bearing_group`, and `raise_public_secret_copy_denied` in `apps/api/app/services/env_groups.py`.
- The one-time string-map-to-plain migration is `apps/api/migrations/versions/0017_p2_03_env_group_secret.py` (revision `0017_p2_03`, down_revision `0016_p2_02`); it rewrites `env_groups.variables` in place and creates no table.
- Session routes in `apps/api/app/routes/env_groups.py` return masked detail, and `apps/api/app/routes/public_api.py` keeps public Env Group create/patch/copy plain-only with `ENV_GROUP_SECRET_PUBLIC_COPY_DENIED` for secret-bearing copy.
- Verification coverage is in `apps/api/tests/test_p2_03_env_group_secret.py`, the typed updates in `apps/api/tests/test_p0_01_env_groups_api.py`, `apps/api/tests/test_p0_01_env_groups_service.py`, `apps/api/tests/test_p0_05_scenarios_api.py`, `apps/api/tests/test_p0_06_test_plans_api.py`, `apps/api/tests/test_p1_04_scenario_testplan_polish_api.py`, and `apps/api/tests/test_p2_02_public_api.py`, the contract assertions in `tests/contract/test_p0_01_env_groups_openapi.py` and `tests/contract/test_p2_02_public_api_openapi.py`, and the Web assertions in `apps/web/src/features/env-groups/env-groups.test.tsx`.
- `ENV_GROUP_SECRET_PUBLIC_COPY_DENIED` is registered in `apps/api/app/main.py` and both OpenAPI artifacts, and the bundled `packages/ai-skills/surgepilot-public-api/references/public-api.openapi.json` snapshot stays byte-identical to `packages/contracts/openapi/public-api.openapi.json`.

Other P2 slices remain outside this checkpoint and require their own accepted scope and
implementation history.
