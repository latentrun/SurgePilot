# P2-02 Public API Substrate

- Document status: Accepted for P2-02 implementation scope by `docs/sdd/adr/ADR-0012-p2-public-api-substrate.md`
- Stage: P2
- Capability:`public_api_substrate`
- Scope Gate:`docs/sdd/00-product-scope-and-priority.md` §7, amended by ADR-0012 for this Slice only
- API Contract Boundary:`docs/sdd/04-api-contract-guidelines.md`
- Run State Boundary:`docs/sdd/05-runner-protocol-and-run-state-machine.md`
- Security Boundary:`docs/sdd/06-security-permission-workspace.md`
- Storage Boundary:`docs/sdd/07-storage-artifacts-minio.md`
- ADR:`docs/sdd/adr/ADR-0012-p2-public-api-substrate.md`

## 1. Core Decision

P2-02 establishes the SurgePilot programmatic public API substrate.

The public API is **not** the token-management surface. PAT create/list/revoke belongs to the browser session API:

```http
GET    /api/v1/account/api-tokens
POST   /api/v1/account/api-tokens
DELETE /api/v1/account/api-tokens/{tokenId}
```

The UI route is:

```text
/account/api-keys
```

This page is Account / self-service, shared by `user` and `admin`. It is not an Admin page. Admin users on this page manage only their own tokens.

`/api/public/v1/*` assumes the caller already has a PAT and authenticates with `Authorization: Bearer <PAT>`. PAT creation must not appear under `/api/public/v1/*`; doing so would create a first-PAT bootstrap deadlock and wrongly expose token management as a programmatic API capability.

## 2. In Scope

### 2.1 Browser session token management

1. Add the Account self-service UI route `/account/api-keys`.
2. Add session-authenticated API routes under `/api/v1/account/api-tokens`.
3. Allow both `user` and `admin` roles to manage only their own API tokens.
4. Return PAT plaintext only once from the create response.
5. Require CSRF for session-authenticated token writes.

### 2.2 Public API

P2-02 exposes only the business operations required by external programs after a PAT already exists:

1. Public route prefix `/api/public/v1/*`.
2. PAT Bearer authentication for public routes.
3. PAT scope checks, actor user status checks, Workspace membership checks and Workspace allowlist checks.
4. Public read endpoints for Scenario, Test Plan, Run, Run Report and Load Node summary data.
5. Env Group structured create / patch / delete / copy.
6. Scenario structured create / patch / delete using existing `steps_json` validation and service rules.
7. Test Plan structured create / patch / delete using existing service rules.
8. Run create, Run stop, Run get/list and Run Report get using the existing Run service and state machine.
9. Independent generated public OpenAPI artifact: `packages/contracts/openapi/public-api.openapi.json`.
10. Automated public OpenAPI exclusion checks in `make verify`.
11. One repo-maintained Public API AI skill source package under `packages/ai-skills/surgepilot-public-api/`, aligned only to the generated public OpenAPI artifact and verified in `make verify`.
12. Bounded Dependency File list/upload/delete using the existing Dependency File service, storage, validation, audit, Workspace and reference-protection rules.

Public PAT scopes are limited to:

| Scope | Allows |
| --- | --- |
| `read` | Public read of authorized Scenario, Test Plan, Run, Report and Load Node summaries. |
| `config:write` | Env Group, Scenario and Test Plan structured create/patch/delete; Env Group copy. |
| `run` | Create Run, stop Run, query Run lifecycle and report references. |
| `dependency:write` | Upload and delete Dependency Files through the bounded public Dependency File routes. |

### 2.3 Load Node API connectivity setting

P2-02 authorizes a minimal node-facing API origin configuration because the public API substrate and remote runners must not keep depending on browser or Compose-local addresses.

1. Add one non-sensitive DB-backed System Setting field: `loadNodeApiBaseUrl`.
2. Add one bootstrap env fallback: `SURGEPILOT_NODE_API_BASE_URL`.
3. Keep `SURGEPILOT_API_BASE_URL` only as the runner wire variable written by api-worker into a Run-specific `.surgepilot.env`.
4. Effective order is DB `loadNodeApiBaseUrl` > env `SURGEPILOT_NODE_API_BASE_URL` > missing. `APP_BASE_URL` is not a fallback.
5. Values must be absolute `http` or `https` origins. Paths other than empty or `/`, credentials, query, and fragment are invalid. Localhost, loopback, wildcard, link-local, `host.docker.internal`, and single-label hostnames are invalid.
6. The setting affects only future remote Run starts at start execution time. Running Runs and already-written runner env files are not changed.
7. Missing or invalid configuration returns `RUN_CONTROL_INVALID_API_BASE_URL` and does not start the runner. Stop and force-kill do not depend on this setting.
8. Register and initialize Load Node flows may continue when the summary is missing or invalid, but must warn that future remote Runs will be blocked. Changing this URL does not require Load Node re-initialization.
9. Add a session-authenticated, non-Admin-only, read-only summary endpoint under `/api/v1/load-nodes/connectivity-summary`. It is for Web guidance only, does not prove network reachability, and must not appear in `public-api.openapi.json`.
10. Official Make startup targets may derive `SURGEPILOT_NODE_API_BASE_URL` from one unambiguous host publish address and the configured `SURGEPILOT_API_HOST_PORT` when no final URL override is supplied. This is a process fallback only: it must not overwrite an existing DB `loadNodeApiBaseUrl`, and raw `docker compose` does not promise host-address discovery.
11. Host discovery must fail fast when it produces zero or multiple candidates. The error must ask the operator to set the final `SURGEPILOT_NODE_API_BASE_URL`; no public host-only intermediate variable is added.
12. Official Make preflight treats an unset or empty published API port as the Compose default, rejects non-canonical host-port syntax before runtime/build side effects, and passes the effective decimal port to the child Make process. If multiple policy-table default routes include any route without an explicit source address, discovery must fail closed rather than reuse a route lookup that lacks that table's rule context.

### 2.4 Bounded Dependency File public extension

P2-02 authorizes only this Dependency File public surface:

1. `GET /api/public/v1/dependency-files` with `read`.
2. `POST /api/public/v1/dependency-files` multipart upload with `dependency:write`.
3. `DELETE /api/public/v1/dependency-files/{dependencyFileId}` with `dependency:write`.
4. Existing `dependency_file_allowed_extensions`, max-size, safe filename/path, SHA-256, MinIO object-key generation, audit, Workspace isolation and reference-protection rules apply unchanged.
5. `.groovy` remains required only where existing Scenario script-reference validation requires it.
6. Public Dependency File detail, preview, download, replacement and generic binary/multipart APIs remain out of scope.

## 3. Out of Scope

1. `tokens:write` public scope.
2. PAT create/list/revoke under `/api/public/v1/*`.
3. Token-on-token rotation.
4. Admin-managed tokens for other users in Phase A.
5. New RBAC model or custom authorization platform.
6. Scenario clone or Test Plan clone.
7. API Catalog, OpenAPI/Swagger upload, API Spec page, API -> Scenario/Test Plan generation, OpenAPI Step auto-generation or Scenario/Test Plan generation chains.
8. Schedule Run, Scheduled Job, Help outside ADR-0016/P2-04, Grafana datasource/dashboard management, InfluxDB management and editable Taurus YAML.
9. Artifact binary download or streaming in the first public API substrate.
10. MCP server, skills runtime, SDK platform, host-specific installer, marketplace publishing, release artifact publication, API Gateway, microservice split, queue, Redis, Celery, RabbitMQ or Kafka. The only authorized skill asset is the repo-maintained source package defined in §11; ADR-0016/P2-04 adds only a session-authenticated request-built source zip.
11. Direct access by external programs to PostgreSQL, MinIO, Runner callback endpoint, Load Node SSH, internal `/api/internal/*`, object keys, server paths or runner tokens.

Admin-managed tokens for other users are out of scope for Phase A. This is not a permanent product prohibition; it requires a later governance item with explicit admin UX, audit and permission contracts.

## 4. Route and UI Contracts

### 4.1 Account self-service UI

| Route | User roles | Contract |
| --- | --- | --- |
| `/account/api-keys` | `user`, `admin` | Current logged-in user manages only their own PATs. |

Rules:

1. The route must not live under `/admin/*`.
2. The route must not reuse Admin navigation in a way that makes it inaccessible to normal users.
3. Admins must not see or manage other users' PATs through this page.
4. The page may show token metadata, expiry, Workspace allowlist, scopes, last used time and revoked state.
5. The page must show plaintext PAT only immediately after successful creation.

### 4.2 Browser session token API

| Method | Path | Auth | CSRF | Contract |
| --- | --- | --- | --- | --- |
| `GET` | `/api/v1/account/api-tokens` | Cookie session | No | List current user's token metadata only. |
| `POST` | `/api/v1/account/api-tokens` | Cookie session | Yes | Create current user's token and return plaintext once. |
| `DELETE` | `/api/v1/account/api-tokens/{tokenId}` | Cookie session | Yes | Revoke current user's token. |

Rules:

1. These routes are Web/business session APIs, not programmatic public APIs.
2. These routes must appear only in `packages/contracts/openapi/api.openapi.json`.
3. These routes and their token-management schemas must be excluded from `packages/contracts/openapi/public-api.openapi.json`.
4. Session writes must validate `x-csrf-token`.
5. `GET` does not require CSRF because it is a safe read.
6. All operations are self-only. `tokenId` must resolve to a token owned by the current session user or return the existing safe not-found/access-denied behavior.
7. Admin's use of other people's tokens is not implemented in this Slice.

### 4.3 Programmatic public API

Public routes use:

```http
Authorization: Bearer surgepilot_pat_<publicId>_<secret>
x-workspace-id: <workspaceId>
```

Rules:

1. Public routes must not accept browser cookie session auth.
2. Public routes must not require or validate CSRF tokens.
3. Public writes must validate PAT scope, actor user status, Workspace membership and Workspace allowlist.
4. Public routes must not read browser session state, local storage preferred Workspace or default Workspace fallback.
5. Public routes must not expose token-management operations.

## 5. PAT Data Contract

PAT storage and metadata remain unchanged by moving creation to the session API.

| Field | Contract |
| --- | --- |
| `publicId` | Non-secret token identifier used for lookup and audit correlation. |
| `secretHash` | Server-side hash of the secret part only; never returned. |
| `actorUserId` | User represented by the PAT. |
| `scopes` | Lower snake case capability list. P2-02 allows only `read`, `config:write`, `run`, `dependency:write`. |
| `workspaceAllowlist` | Workspace IDs this PAT may access. Empty allowlist is forbidden. |
| `expiresAt` | Required expiry timestamp or governance-approved bounded maximum. |
| `revokedAt` | Revocation timestamp; revoked tokens are invalid immediately. |
| `lastUsedAt` | Safe operational metadata; update must not log token values. |

Plaintext format:

```text
surgepilot_pat_<publicId>_<secret>
```

Rules:

1. Plaintext PAT is returned only once from `POST /api/v1/account/api-tokens`.
2. Plaintext PAT, PAT secret, `secretHash` and `Authorization` header are sensitive values.
3. PAT plaintext, hashes and examples must not appear in logs, audit details, public OpenAPI, public examples or test snapshots.
4. Disabled actor user, expired token, revoked token or lost Workspace membership invalidates the PAT.
5. Missing scope returns a stable scope-denied error.
6. PAT permissions are the intersection of token scope, actor active status, actor role, Workspace membership and token Workspace allowlist.

## 6. Workspace Contract

Public PAT requests must resolve Workspace as follows:

1. If `x-workspace-id` is present, it must be in the token allowlist and the actor must still be a member.
2. If `x-workspace-id` is absent and the token allowlist contains exactly one Workspace, that Workspace is used.
3. If `x-workspace-id` is absent and the token allowlist contains more than one Workspace, return `400 WORKSPACE_REQUIRED`.
4. Public requests must not use browser current session, browser local storage, preferred Workspace or default Workspace fallback.
5. Public route paths must not contain Workspace ID.

## 7. Public API Contract

Representative Phase A endpoints:

| Method | Path | Operation ID | Scope | Contract |
| --- | --- | --- | --- | --- |
| `GET` | `/api/public/v1/scenarios/{scenarioId}` | `publicGetScenario` | `read` | Return conservative Scenario detail visible in current Workspace. |
| `POST` | `/api/public/v1/scenarios` | `publicCreateScenario` | `config:write` | Create structured Scenario through existing Scenario service. |
| `PATCH` | `/api/public/v1/scenarios/{scenarioId}` | `publicPatchScenario` | `config:write` | Patch structured Scenario through existing revision/service validation. |
| `DELETE` | `/api/public/v1/scenarios/{scenarioId}` | `publicDeleteScenario` | `config:write` | Delete only through existing reference protection. |
| `POST` | `/api/public/v1/env-groups` | `publicCreateEnvGroup` | `config:write` | Create Env Group through existing service. |
| `PATCH` | `/api/public/v1/env-groups/{envGroupId}` | `publicPatchEnvGroup` | `config:write` | Patch Env Group through existing service. |
| `DELETE` | `/api/public/v1/env-groups/{envGroupId}` | `publicDeleteEnvGroup` | `config:write` | Delete through existing reference protection. |
| `POST` | `/api/public/v1/env-groups/{envGroupId}/copy` | `publicCopyEnvGroup` | `config:write` | Copy Env Group because copy is P0-Core. |
| `GET` | `/api/public/v1/test-plans/{testPlanId}` | `publicGetTestPlan` | `read` | Return conservative Test Plan detail. |
| `POST` | `/api/public/v1/test-plans` | `publicCreateTestPlan` | `config:write` | Create Test Plan through existing service. |
| `PATCH` | `/api/public/v1/test-plans/{testPlanId}` | `publicPatchTestPlan` | `config:write` | Patch Test Plan through existing service. |
| `DELETE` | `/api/public/v1/test-plans/{testPlanId}` | `publicDeleteTestPlan` | `config:write` | Delete through existing reference protection. |
| `POST` | `/api/public/v1/runs` | `publicCreateRun` | `run` | Create Run through existing Run service and state machine. |
| `POST` | `/api/public/v1/runs/{runId}/stop` | `publicStopRun` | `run` | Stop Run through existing idempotent Stop service. |
| `GET` | `/api/public/v1/runs/{runId}` | `publicGetRun` | `read` or `run` | Return public Run detail. |
| `GET` | `/api/public/v1/runs/{runId}/report` | `publicGetRunReport` | `read` or `run` | Return structured report and artifact references only. |
| `GET` | `/api/public/v1/load-nodes` | `publicListLoadNodes` | `read` | Return LoadNodeSummary-like data without credentials. |
| `GET` | `/api/public/v1/dependency-files` | `publicListDependencyFiles` | `read` | List available Dependency Files in the resolved Workspace with existing in-use projection. |
| `POST` | `/api/public/v1/dependency-files` | `publicUploadDependencyFile` | `dependency:write` | Upload one Dependency File through existing bounded multipart/storage validation. |
| `DELETE` | `/api/public/v1/dependency-files/{dependencyFileId}` | `publicDeleteDependencyFile` | `dependency:write` | Delete through existing Workspace and reference protection. |

Rules:

1. Public routes call existing application/service layers.
2. Public routes must not direct-delete DB rows or bypass service-level reference protection.
3. Public response schemas are stricter than Web schemas and omit internal audit-only fields, credential material, object keys, server paths and runner tokens.
4. Public routes must not expose Scenario/Test Plan clone, cURL import, OpenAPI Step Generation, Schedule Run, API Catalog generation or editable Taurus YAML through alternate fields.

## 8. Run and Stability Invariants

Public Run routes must enter the existing Run service/state machine.

Done-When for Run API:

1. Run creation transaction includes snapshot and node lease.
2. Terminal state is not overwritten by late callback.
3. Callback idempotency remains keyed by `eventId` / `(run_id, event_id)`.
4. Stop repeated requests are idempotent.
5. Stop against terminal Run returns the existing consistent terminal error behavior.
6. Runner token binding still validates `runId` and Runner identity.
7. Heartbeat timeout, stop grace timeout and terminal callback with `processGroupExited=false` enter shared cleanup paths.
8. Node lease and Busy state are released or quarantined through existing rules.
9. Stale lease recovery never puts a node back to Idle before cleanup safety is known.
10. Public API never exposes runner callback endpoint or runner token.

## 9. OpenAPI and Contract Export

Required artifacts:

```text
packages/contracts/openapi/api.openapi.json
packages/contracts/openapi/public-api.openapi.json
```

Rules:

1. FastAPI/Pydantic remains the only OpenAPI source of truth.
2. Web/business artifact may include `/api/v1/account/api-tokens` and its session schemas.
3. Public artifact must include only `/api/public/v1/*` operations or the ADR-approved normalized equivalent.
4. Public artifact must exclude `/api/v1/account/api-tokens`, token-management routes and token-management schemas.
5. Public artifact must exclude PAT plaintext fields, `secretHash`, Authorization header examples, example token values and any field that can reconstruct the secret.
6. Public artifact must exclude browser-only session/csrf routes, internal runner routes and Web-only management routes.
7. Public artifact must exclude internal/session-only Load Node SSH host-key trust workflow error codes (`LOAD_NODE_SSH_HOST_KEY_SCAN_FAILED`, `LOAD_NODE_SSH_HOST_KEY_MISMATCH`, `LOAD_NODE_SSH_HOST_KEY_UNTRUSTED`, `LOAD_NODE_SSH_HOST_KEY_CHANGED`) while the Web/business artifact keeps them.
8. `make generate-contracts` or its successor generates both artifacts.
9. `make verify` or its successor fails if either artifact is stale or if the public artifact violates token-management / secret exclusion rules.
10. Operation IDs in the public artifact are stable and do not collide with Web operation IDs.

Current implementation note: `scripts/export_openapi.py` currently keeps `/api/v1/*` and drops other `/api/*` paths. P2-02 implementation must update export behavior before adding public routes.

## 10. Error Contract

Public routes use the existing error envelope:

```json
{
  "code": "WORKSPACE_ACCESS_DENIED",
  "message": "Workspace access denied.",
  "requestId": "req_01J0Y6T6H2Y0S9V4W8M7N6P5Q8",
  "details": null
}
```

Representative public error codes:

| Code | HTTP status | Contract |
| --- | --- | --- |
| `UNAUTHENTICATED` | `401` | Missing, malformed, expired, revoked or invalid PAT. Message must not reveal which part failed. |
| `PUBLIC_TOKEN_SCOPE_DENIED` | `403` | PAT lacks required scope. |
| `WORKSPACE_REQUIRED` | `400` | Workspace cannot be resolved from explicit header or single-workspace token allowlist. |
| `WORKSPACE_ACCESS_DENIED` | `403` | Header Workspace outside allowlist or actor membership. |
| `RESOURCE_NOT_FOUND` | `404` | Resource missing or hidden by Workspace boundary. |
| `VALIDATION_ERROR` | `422` | Schema or field validation failed; details are bounded and safe. |
| `DEPENDENCY_FILE_EXTENSION_NOT_ALLOWED` | `422` | Dependency File upload extension is not allowed. |
| `PAYLOAD_TOO_LARGE` | `413` | Dependency File upload exceeds configured size. |
| `RUN_TERMINAL_STATE` | `409` | Stop or mutation conflicts with terminal Run according to existing Run rules. |

Rules:

1. New public-specific codes must be registered in the repository error code registry before implementation.
2. Error `details` must not contain PAT plaintext, PAT secret hash, Authorization header, CSRF token, runner token, credentials, SQL, tracebacks, object keys or server paths.
3. External tools depend on stable `code`; do not vary codes by English message text.

## 11. AI Adapter / MCP / Skills Boundary

1. SurgePilot may maintain one source skill package at `packages/ai-skills/surgepilot-public-api/`; all other skills and MCP integrations remain external adapters/consumers unless separately governed.
2. The package may contain only `SKILL.md`, a public OpenAPI snapshot, an `operationId`-only caller, and tests needed to enforce contract alignment and safety. It must not add a skills runtime, SDK platform, MCP server, prompt library platform, installer, marketplace entry, or release artifact. ADR-0016/P2-04 may expose the same source through a logged-in request-built zip, but that is not a versioned distribution platform.
3. The package contract source is exclusively `packages/contracts/openapi/public-api.openapi.json`. The allowlist must match the current public `operationId` set exactly, and callers must not accept arbitrary request URLs or internal/session operation identifiers.
4. Host agents must display the Workspace, operation ID, target resource and key parameters and obtain explicit user confirmation before writes, including Run create and stop.
5. The client configuration `SURGEPILOT_PUBLIC_API_BASE`, `SURGEPILOT_PAT` and `SURGEPILOT_WORKSPACE_ID` belongs only to the local skill caller. It does not add server-side System Settings.
6. The caller must use explicit Workspace context, must not read browser state or guess another Workspace, and must fail closed for authentication, authorization, Workspace, validation and conflict responses without internal API fallback or cross-Workspace probing.
7. The package must not call PostgreSQL, MinIO, internal runner endpoints, Load Node SSH, browser session/CSRF APIs, Account API-token routes, artifact binary download, Dependency File preview/download, API Catalog generation or secret management. The only file upload allowed is `publicUploadDependencyFile` through the bundled public contract and the caller's dedicated `--file` path.
8. Public Env Group requests and responses remain plain-only. Secret-bearing patch/copy failures stop without fallback to session or internal APIs.
9. Help/download UI is authorized only by ADR-0016/P2-04. Web static exposure, a SurgePilot-provided installer, version selection, signing, checksums and published artifacts remain forbidden. Help may explain how a user-owned local agent consumes the extracted source without defining a SurgePilot installation workflow.
10. The ADR-0016 download endpoint remains a cookie-session `/api/v1/account/*` read API. It must not enter `/api/public/v1/*`, require PAT scope, inject Workspace/user secrets, or change the skill's explicit Workspace and write-confirmation behavior.

## 12. Acceptance Criteria

### 12.1 Browser self-service token management

1. Normal `user` can access `/account/api-keys`.
2. `admin` can access `/account/api-keys` but cannot manage other users' tokens.
3. `GET /api/v1/account/api-tokens` lists only the current user's token metadata.
4. `POST /api/v1/account/api-tokens` requires session auth and CSRF, creates only the current user's token and returns plaintext once.
5. `DELETE /api/v1/account/api-tokens/{tokenId}` requires session auth and CSRF and revokes only the current user's token.
6. PAT plaintext/hash/Authorization value never appears in logs, audit details, OpenAPI examples or public artifact.

### 12.2 Public API

1. `/api/public/v1/*` rejects browser cookie session auth without PAT Bearer.
2. Public PAT write requests do not require CSRF but require scope, actor and Workspace checks.
3. Public scope set is exactly `read`, `config:write`, `run`, `dependency:write`; `dependency:write` is limited to Dependency File upload/delete.
4. `tokens:write` is not accepted in public schemas, docs or examples.
5. Disabled user, revoked token, expired token and removed Workspace membership invalidate PAT access.
6. Missing `x-workspace-id` with multi-Workspace token allowlist returns `WORKSPACE_REQUIRED`.
7. Public request never falls back to browser default Workspace, preferred Workspace or local storage.
8. Public structured writes call existing services and preserve reference protection.
9. Public Run create/stop pass existing state machine and idempotency tests.
10. Public Load Node summary does not include credentials or encrypted credential material.
11. Public Dependency File list/upload/delete use existing Workspace isolation, filename/extension/size/SHA/storage/audit/reference-protection services; public preview/download remain absent.

### 12.3 OpenAPI / verification

1. `api.openapi.json` may contain `/api/v1/account/api-tokens` and session schema.
2. `public-api.openapi.json` does not contain `/api/v1/account/api-tokens`.
3. `public-api.openapi.json` does not contain token-management schema names, PAT plaintext fields, `secretHash`, Authorization header examples, example token values or fields that can reconstruct the secret.
4. `public-api.openapi.json` does not contain internal/session-only Load Node SSH host-key trust workflow error codes.
5. `make verify` fails if the public artifact contains token-management routes/schema or secret-like fields.
6. `make verify` fails if generated OpenAPI artifacts are stale.
7. The repo-maintained skill snapshot matches `packages/contracts/openapi/public-api.openapi.json`, its allowlist covers exactly the current public operations, and its tests enforce forbidden-contract, confirmation, redaction, Workspace and fail-closed behavior.
8. ADR-0016/P2-04 contract tests prove the session download operation appears only in `api.openapi.json`, while `public-api.openapi.json` excludes the path and its route-local source-unavailable error code.

## 13. Implementation Backfill

Implementation PRs must backfill exact file paths and names after code is added:

1. Public router file paths.
2. Account token session router file paths.
3. PAT model/migration/service file paths.
4. Final schema names and generated OpenAPI operation IDs.
5. Final OpenAPI export command behavior and stale-check command.
6. Final test file names for session token management, PAT auth, public schema exclusion, structured write, Run public API and the bounded Dependency File extension.

Backfilled in P2-02 implementation:

1. Public router file path: `apps/api/app/routes/public_api.py`.
2. Account token session router file path: `apps/api/app/routes/account_api_tokens.py`.
3. PAT model/migration/service file paths:
   - Model: `apps/api/app/models/auth.py` (`ApiToken`).
   - Migration: `apps/api/migrations/versions/0016_p2_02_api_tokens.py`.
   - Service: `apps/api/app/services/api_tokens.py`.
   - Public auth dependency: `apps/api/app/api/deps.py` (`PublicApiContextDep` and scope dependencies).
4. Final schema names and generated OpenAPI operation IDs:
   - Session token schemas: `ApiTokenCreateRequest`, `ApiTokenMetadata`, `ApiTokenCreated`, `ApiTokenCreateResponse`, `ApiTokenListResponse`.
   - Public Load Node schemas: `PublicLoadNodeSummary`, `PublicLoadNodeListResponse`.
   - Public Run report schema: `PublicRunReport`; public OpenAPI intentionally excludes `RunReportDetail` and `DebugHttpTrace*`.
   - Session operation IDs: `listAccountApiTokens`, `createAccountApiToken`, `deleteAccountApiToken`.
   - Public operation IDs: `publicListScenarios`, `publicGetScenario`, `publicCreateScenario`, `publicPatchScenario`, `publicDeleteScenario`, `publicCreateEnvGroup`, `publicPatchEnvGroup`, `publicDeleteEnvGroup`, `publicCopyEnvGroup`, `publicListTestPlans`, `publicGetTestPlan`, `publicCreateTestPlan`, `publicPatchTestPlan`, `publicDeleteTestPlan`, `publicListRuns`, `publicCreateRun`, `publicGetRun`, `publicGetRunReport`, `publicStopRun`, `publicListLoadNodes`, `publicListDependencyFiles`, `publicUploadDependencyFile`, `publicDeleteDependencyFile`.
5. Final OpenAPI export command behavior and stale-check command:
   - `scripts/export_openapi.py` exports Web/business `/api/v1/*` paths to `packages/contracts/openapi/api.openapi.json`.
   - `scripts/export_openapi.py` exports programmatic `/api/public/v1/*` paths to `packages/contracts/openapi/public-api.openapi.json`, prunes public component schemas to referenced public schemas, and prunes internal/session-only Load Node SSH host-key trust workflow error codes from the public artifact.
   - `make generate-contracts` regenerates both OpenAPI artifacts and the Web client.
   - `make contracts-stale-check` diffs `packages/contracts/openapi/` and `packages/contracts/generated/`, covering both artifacts.
6. Final test file names:
   - Session token management: `apps/api/tests/test_p2_02_api_tokens_api.py`.
   - PAT auth, scope, Workspace resolution, structured write, Run public API and Load Node public summary: `apps/api/tests/test_p2_02_public_api.py`.
   - Public OpenAPI schema exclusion and Web artifact inclusion: `tests/contract/test_p2_02_public_api_openapi.py`.
   - Account UI component flow: `apps/web/src/features/account/api-keys.test.tsx`.
   - Browser smoke for Account API keys plus public PAT read: `tests/e2e/p2_02_public_api_substrate.spec.ts`.
7. The bounded Dependency File public extension is implemented in `apps/api/app/routes/public_api.py` and reuses `app.routes.dependency_files` parsing/projection plus `app.services.dependency_files` storage, audit and reference-protection primitives. No public preview/download is added.
8. Node-facing API origin implementation files: `apps/api/app/services/load_node_connectivity.py`, `apps/api/app/services/system_settings.py`, `apps/api/app/routes/load_nodes.py`, `apps/api/app/services/run_control_executor.py`, and Web reuse in `apps/web/src/features/load-nodes/components/load-node-connectivity-summary.tsx`.
9. Deployment configuration governance now uses one grouped `.env.example` for ordinary deployment, `.env.e2e.example` for test/E2E overrides, generated `.surgepilot/runtime-artifacts/.../runtime.env` for runtime artifact injection, and the existing DB-backed System Settings registry for non-sensitive policy. Full/base Compose consume required root `RUNNER_INTERNAL_TOKEN` and `SSH_CREDENTIAL_ENCRYPTION_KEY` values instead of hardcoded per-service defaults; the SSH credential key is validated as base64-encoded 32 bytes before official startup and by API/api-worker startup. Compose forwards documented DB fallbacks and active bootstrap values, keeps API/api-worker MinIO credentials aligned, limits migration containers to `APP_ENV` and `DATABASE_URL`, and keeps `VITE_API_BASE_URL` build-only. Official Make release/start, full SSH E2E runtime preparation, migration, and host development targets load root `.env` through `python-dotenv --no-override`; verification and verifier scripts inject isolated non-default test Runner/SSH credential/MinIO values. `tests/contract/test_env_example_drift.py`, `tests/contract/test_p1_00_monitoring_compose.py`, verifier tests, Playwright Dependency File coverage, smoke Compose, API main-flow E2E, and SSH/Taurus E2E enforce these ownership and propagation boundaries.
10. The Load Node connectivity follow-up adds the session-only `LoadNodeConnectivitySummary` response and DB-backed `loadNodeApiBaseUrl` System Settings fields to FastAPI/Pydantic. Static origin validation canonicalizes IDNA dot separators, requires canonical IP notation or valid DNS labels, and rejects wildcard, percent-encoded, legacy numeric IP, localhost, loopback, link-local, single-label, and `host.docker.internal` forms without DNS or connectivity probing. `/v1/load-nodes/connectivity-summary`, `LoadNodeConnectivitySummary`, and `loadNodeApiBaseUrl` are exported in internal `packages/contracts/openapi/api.openapi.json` and `packages/contracts/generated/web-client/index.ts`; they are intentionally excluded from `packages/contracts/openapi/public-api.openapi.json`. This follow-up does not expand public API scope, Runner protocol, or public Workspace resolution.
11. `scripts/node_facing_startup.py` is the official Make-only convenience for missing final node-facing URLs. It derives `SURGEPILOT_NODE_API_BASE_URL` from one unambiguous IPv4/IPv6 default-route source address across all routing tables plus `SURGEPILOT_API_HOST_PORT`, preserves explicit final URL overrides, applies the same node-origin host safety rules as the API, rejects API/InfluxDB publish-port collisions before side effects, checks Compose ownership separately for IPv4 and IPv6 published-port conflicts, and allows an existing Compose project to own only its matching bindings during restart. All full SSH start/restart variants, including image-build variants, place the complete SSH E2E environment before root `.env` loading and run URL/port preflight before build or teardown side effects. `Makefile`, `.env.example`, `.env.e2e.example`, `README.md`, and the existing System Settings help copy use the direct API publish-port convention. Raw Compose keeps empty/env fallback semantics and does not perform discovery or overwrite the DB-backed `loadNodeApiBaseUrl`.
12. The repo-maintained Public API AI skill source package is located at `packages/ai-skills/surgepilot-public-api/`. `make generate-contracts` refreshes its bundled public OpenAPI snapshot from the generated canonical artifact, `make contracts-stale-check` detects snapshot drift with fail-fast cleanup, and `make ai-skill-tests` runs `packages/ai-skills/surgepilot-public-api/tests/test_contract.py`, `test_caller.py`, and `test_http_smoke.py` with line/branch coverage before the root patch-coverage gate. The caller refuses redirects, validates each response status/body against the selected operation contract, rejects credential-like response values, and CI validates `SKILL.md` metadata plus its confirmation/fail-closed instructions. No Web route, static asset, API route, database object, Runner behavior, runtime distribution, release artifact or product-visible download is added.
13. `scripts/verify_p2_02_public_api_lifecycle.py` scans and confirms the live SSH host key before creating its Load Node, matching the node-level trust contract already required by the active P2-02 implementation. `tests/test_p2_02_public_api_lifecycle_verifier.py` covers this precondition, and `make verify-p2-02-public-api-lifecycle` remains the real-stack lifecycle acceptance command.
