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

`P2-04-help-ai-agents-system-openapi-bootstrap.md` is active through `ADR-0016`. It covers
authenticated Help AI Agents guidance, a session-authenticated request-built Public API AI skill
source download, shared runtime/script OpenAPI export, and a best-effort first-Admin import of
SurgePilot's own curated Web/business OpenAPI into the Default Workspace API Catalog. It does not
authorize user/external automatic ingestion, retries/workers, SDK, MCP, marketplace, installer,
release publication, built-in agent runtime, AI generation/tuning/analysis, or API Catalog to
Scenario/Test Plan generation.

`P2-05-cross-platform-distribution.md` is active through `ADR-0017`, its source-preview amendment
`ADR-0019`, and its user-local platform Release installer amendment `ADR-0024`. It covers one
complete tagged-release mode: GHCR multi-architecture SurgePilot application images, a bounded
GitHub Release bundle, a version-pinned user-local installer and bundle checksum, native-built
Linux amd64/arm64 Runtime assets, release Compose plus `surgepilot up`, complete source Compose plus
`make start-full-stack`, and a source-only control-plane preview through `make start-preview`. It
does not authorize Kubernetes, package-manager or system installers, Docker Hub mirroring, an
all-in-one image, native macOS Load Nodes/Runtime, automatic upgrades, a Runtime UI/catalog,
signing or SBOM publication, or standalone Public API AI skill release.

`P2-06-lan-first-deployment-usability.md` is active through `ADR-0018`, its new-release Runtime
default amendment `ADR-0020`, its release `up` configuration confirmation amendment `ADR-0021`,
and its separate installation amendment `ADR-0024` as release-path amendments to P2-05. It covers
the tagged-release LAN-first startup contract only: an interactive first-run host/port confirmation
with a warned canonical-loopback evaluation exception, persisted node-facing URL/port consistency,
Demo off by default, required node-facing origins, default authenticated InfluxDB publication, a
strict session-cookie transport value, non-interactive complete-`.env` fixtures, a new-release
`amd64,arm64` Runtime default without an architecture prompt, and read-only default-Yes release
`up` configuration review with explicit interactive four-field standard-LAN updates. ADR-0017
decisions 7 and 8 are superseded only as those amendments specify. It does not authorize network
discovery, a Web/API configuration surface, automatic or non-interactive rewriting, advanced-HTTPS
quick editing, non-network changes, source-startup changes, package-manager/system installers, or
public workflow dispatch capability.

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

## P2-04 factual backfill

- Help is registered by the pathname switch in `apps/web/src/App.tsx` and rendered by `apps/web/src/features/help/pages/help-page.tsx`; the account download wrapper is `downloadPublicApiAiSkill` and the API route is `apps/api/app/routes/account_ai_skill.py`.
- `apps/api/app/services/skill_bundle.py` owns `default_skill_bundle_dir()` and resolves the container path first, then the repository fallback. Each authenticated request builds `surgepilot-public-api-skill.zip` from the governed source package without a Workspace header, persistence, or cache.
- `apps/api/app/services/openapi_export.py` owns normalization, Web/public path filtering, schema reachability pruning, public error-code pruning, and `_export_document`; `scripts/export_openapi.py` and `apps/api/app/services/system_openapi_bootstrap.py` use that shared implementation.
- `apps/api/app/services/system_openapi_bootstrap.py` owns `build_curated_openapi_payload()`, `import_system_openapi()`, and `bootstrap_system_openapi_best_effort()`. The auth route invokes the wrapper only after an explicit `first_user=True` result, using an independent session and best-effort MinIO compensation.
- Focused verification is recorded in `apps/api/tests/test_p2_04_openapi_export.py`, `apps/api/tests/test_p2_04_ai_skill.py`, `apps/api/tests/test_p2_04_system_openapi_bootstrap.py`, `tests/contract/test_p2_04_help_ai_agents_openapi.py`, `apps/web/src/features/help/help.test.tsx`, and `tests/e2e/p2_04_help_ai_agents.spec.ts`. Contract refresh uses `make generate-contracts`; the checkpoint's targeted verification commands are `make test`, `make lint`, `make contracts-stale-check`, `make verify`, and the focused Playwright command recorded in the Slice SDD.

## P2-06 factual backfill

- P2-06 is release-path only. The tagged-release wrapper is `infra/release/surgepilot`, the release Compose file is `infra/release/docker-compose.release.yml`, and the configuration, bootstrap, and node-facing helpers are `scripts/release_preflight.py`, `scripts/bootstrap_deployment_env.py`, and `scripts/node_facing_startup.py`.
- Verification coverage is in `tests/test_release_wrapper.py`, `tests/test_release_preflight.py`, `tests/test_bootstrap_deployment_env.py`, `tests/test_node_facing_startup.py`, `tests/test_release_installer.py`, `tests/contract/test_p2_05_distribution.py`, `tests/contract/test_env_example_drift.py`, and `apps/api/tests/test_p0_00_services.py`; the environment-dependent LAN smoke is `scripts/verify_p2_05_release_stack.py` with `tests/test_p2_05_release_stack_verifier.py`.
- The interaction contract is: a missing release `.env` requires an interactive host shell, the confirmed host and port values are persisted with Demo off, `amd64,arm64`, and `SESSION_COOKIE_SECURE=false`, a complete existing `.env` is described and read-only by default, an explicit `No` opens the standard-LAN four-field update, and non-interactive startup never prompts or rewrites.
- Native Linux amd64/arm64 LAN external-node acceptance and the installer workflow smoke require native runners, Docker networking, and real SSH nodes, so they remain outside default `make verify`.

Other P2 slices remain outside this checkpoint and require their own accepted scope and
implementation history.
