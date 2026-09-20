# 04 API Contract Guidelines

- Document status: Draft
- Project: SurgePilot performance load testing platform
- Document location: `docs/sdd/04-api-contract-guidelines.md`
- Product source: `docs/prd/PRD.md`
- Range constraint: `docs/sdd/00-product-scope-and-priority.md`
- Architecture source: `docs/sdd/01-architecture-overview.md`
- Workflow source: `docs/sdd/02-repo-structure-and-dev-workflow.md`
- Current delivery target: P0 baseline + active P2-02 Public API Substrate + P2-03 Env Group Secret + P2-04 Help AI Agents and System OpenAPI Bootstrap + ADR-0013 static Marketing Landing and Logo + P1-09 Scenario Global Configuration authorization
- Scope of application: Foundation SDD, Slice SDD, M0 repository skeleton, API implementation, Web client generation, Runner callback, Contract tests, AI Coding, code review
- Review status of this version: Reasonable opinions of 04 Review 1 / Review 2 / Review 3 / Follow-up Review have been absorbed

---

## 1. Purpose

This document defines the API contract rules of the SurgePilot P0 stage for R&D and AI Coding to abide by when implementing API, Web, Runner callback, and contract tests.

This article only answers:

1. URL, version, naming, request and response conventions of REST API;
2. How to transfer Workspace context;
3. How to express API JSON fields, IDs, times, and enumerations;
4. How to maintain unified error response and error code registry;
5. How to design paging, filtering, and sorting;
6. How FastAPI / Pydantic generates OpenAPI;
7. How does the Web generate client/types based on OpenAPI;
8. Runner callback, Stop, artifact and other contract boundaries across component interfaces;
9. How API contracts are tested and reviewed.

This article is not a complete API Reference. It does not list the fields of all P0 business interfaces one by one, nor does it expand the complete domain model, complete permission matrix, complete Runner state machine or complete MinIO object key rules.

These contents are entered respectively:

- `03-domain-model-overview.md`: Domain model overview;
- `05-runner-protocol-and-run-state-machine.md`: Runner Protocol, Run state machine, Stop, heartbeat, self-healing, node lease;
- `06-security-permission-workspace.md`: account, permissions, Workspace, security;
- `07-storage-artifacts-minio.md`: MinIO, Dependency File, artifacts, path security;
- `09-testing-and-acceptance-strategy.md`: test matrix, CI and acceptance strategy;
- `docs/sdd/slices/*.md`: The specific API endpoint, request, response, error code and Done When of each P0 Slice.

---

## 2. Authority and Conflict Resolution

### 2.1 Canonical Inputs

This article relies on the following documents:

1. `docs/prd/PRD.md`: The only product source for product scope, terminology, priority and acceptance criteria;
2. `docs/sdd/00-product-scope-and-priority.md`: P0/P1/P2 scope gate;
3. `docs/sdd/01-architecture-overview.md`: P0 architecture, component boundaries, contracts and security basic rules;
4. `docs/sdd/02-repo-structure-and-dev-workflow.md`: repository structure, contracts directory, generation command and stale check;
5. `docs/prd/SurgePilotSDDPlanningGuide.md` or equivalent planning guide: SDD Pack and AI Coding advancement methods.

### 2.2 Conflict Resolution

Conflict handling rules:

1. If this article conflicts with `docs/prd/PRD.md`, the PRD shall prevail.
2. If this article conflicts with `docs/sdd/00-product-scope-and-priority.md`, 00 shall prevail unless 00 conflicts with PRD.
3. If this article conflicts with `docs/sdd/01-architecture-overview.md`, the architectural boundary of 01 shall prevail, and this article shall be revised simultaneously.
4. If this article conflicts with `docs/sdd/02-repo-structure-and-dev-workflow.md`, the locked repository, contracts, build commands and verify rules in 02 shall prevail, and this article shall be revised simultaneously.
5. Slice SDD can add specific endpoints, schemas, and error codes, but it cannot violate the global contract rules of this article.
6. Code implementation must not override the rules of this article on the grounds of "already implemented", "generation tool requirements" or "front-end convenience"; the SDD must be revised or the ADR must be recorded first.

---

## 3. Confirmed API Decisions

| Area | Decision |
| --- | --- |
| API style | REST |
| Public business URL prefix | `/api/v1/...` for browser/session business APIs |
| Programmatic public API prefix | `/api/public/v1/...` for P2-02 PAT Bearer APIs only |
| Account token-management API | `/api/v1/account/api-tokens`; browser session self-service only |
| Account AI skill download API | `/api/v1/account/ai-skill/download`; browser session read, current-user access, not Workspace-scoped |
| OpenAPI `servers.url` | `/api` |
| OpenAPI business paths | Start with `/v1/...` for Web/business artifact |
| Public OpenAPI paths | With `servers.url=/api`, public OpenAPI paths start with `/public/v1/...` for normalized `/api/public/v1/...` runtime URLs |
| Public OpenAPI artifact | `packages/contracts/openapi/public-api.openapi.json` for P2-02 `/api/public/v1/*` programmatic consumers |
| Web base URL | `VITE_API_BASE_URL=/api` |
| Health endpoints | `/api/healthz`, `/api/readyz` |
| Internal runner URL prefix | `/api/internal/v1/runner/...` |
| Workspace context | `x-workspace-id` header; route path must not contain workspace ID |
| Missing `x-workspace-id` in P0 browser APIs | Fallback to user default Workspace; `400 WORKSPACE_REQUIRED` only when no default can be resolved |
| Missing `x-workspace-id` in P2-02 public APIs | Use the single Workspace in PAT allowlist only when allowlist size is one; otherwise `400 WORKSPACE_REQUIRED`; no browser default fallback |
| Auth | Cookie-based session for Web/business APIs; PAT Bearer for `/api/public/v1/*` |
| CSRF | `x-csrf-token` on browser session write requests; PAT Bearer public writes do not use CSRF |
| Runner auth | `x-runner-token` on internal runner endpoints |
| Request ID | API generates and returns `x-request-id` |
| JSON field naming | API uses `camelCase`; DB uses `snake_case` |
| API enum value naming | lower snake case |
| External business IDs | ULID string |
| DB storage for ULID IDs | `text` or `char(26)`, not PostgreSQL `uuid` |
| Time format | ISO 8601 UTC string with `Z` |
| Error shape | `{code, message, requestId, details?}` |
| API error message language | English only |
| i18n strategy | Front end localizes by `code`; API `message` is English fallback |
| Field validation errors | `details: [{field, code, message}]` |
| PATCH semantics | missing = unchanged; `null` = clear only when nullable; otherwise `422 VALIDATION_ERROR` |
| Pagination | Offset for small CRUD lists; cursor for Run / Artifact / Audit / callback-like lists |
| Sorting | `sort=createdAt` and `sort=-createdAt` |
| OpenAPI source | FastAPI routes and Pydantic schemas are the source of truth |
| Hand-written OpenAPI as source of truth | Forbidden |
| Web API types | Generated from OpenAPI only |
| List response | Envelope with `items`; bare arrays forbidden |
| Path parameter naming | Use `{resourceId}` style such as `{scenarioId}`; bare `{id}` forbidden |
| Soft delete | Not exposed as API behavior in P0 |
| File download | API proxy; Web does not receive MinIO credentials, presigned URLs, or object keys |
| Rate limit framework | Not implemented in P0; login brute-force guard belongs to `06-security-permission-workspace.md` |
| ETag / conditional request | P1 extension point only; not implemented in P0 |

---

## 4. Scope and Non-Goals

### 4.1 In Scope

This article constrains the following:

1. Public business API URL and versioning;
2. Internal runner endpoint boundary;
3. Workspace header;
4. HTTP method usage;
5. request / response naming;
6. ID, time, enum, nullable, PATCH semantics;
7. list envelope, pagination, filtering, sorting;
8. unified error response;
9. minimum core error code registry;
10. FastAPI/Pydantic OpenAPI export;
11. Web generated client usage;
12. Runner callback contract boundary;
13. Idempotent requirements for Stop, Run creation, and artifact registration;
14. API contract tests and review checklist.

### 4.2 Out of Scope

This article does not define:

1. Complete API endpoint list;
2. Complete domain model;
3. Complete database table structure;
4. Complete permission matrix;
5. Complete Runner state machine;
6. Complete MinIO object key verification algorithm;
7. Complete front-end routing and component structure;
8. Complete test matrix;
9. Interfaces for P1/P2 API Catalog, Monitoring, Schedule, multi-workspace UI, OIDC, Secret, non-MinIO storage and other functions.

If AI Coding needs to add a new endpoint or error code when implementing a certain Slice, it must be explained in the API Contract chapter of the corresponding Slice SDD and comply with the rules of this article.

---

## 5. URL and Versioning

### 5.1 Public Business API Rule

P0 business API is used uniformly by the outside world:

```text
/api/v1/{resource}
```

Example:

```http
GET    /api/v1/scenarios
POST   /api/v1/scenarios
GET    /api/v1/scenarios/{scenarioId}
PATCH  /api/v1/scenarios/{scenarioId}
DELETE /api/v1/scenarios/{scenarioId}

GET    /api/v1/runs
POST   /api/v1/runs
GET    /api/v1/runs/{runId}
POST   /api/v1/runs/{runId}/stop
```

Rules:

1. All business APIs must be hung under `/api/v1`.
2. The same resource is not allowed to exist at the same time `/api/scenarios` and `/api/v1/scenarios`.
3. P0 does not allow the introduction of new version prefixes, such as `/api/v2`; any disruptive contract changes must first go through SDD/ADR review.
4. Destructive contract changes must not silently modify existing paths; the migration strategy must be clearly defined through SDD/ADR.
5. The path must not contain the Workspace ID.

### 5.2 OpenAPI Server and Paths

The OpenAPI artifact uses a unique strategy:

```yaml
servers:
  - url: /api

paths:
  /v1/scenarios:
    get:
      operationId: listScenarios
  /v1/scenarios/{scenarioId}:
    get:
      operationId: getScenario
```

Rules:

1. `servers.url` is fixed to `/api`.
2. Business paths must start from `/v1/...`.
3. The base URL of the Web client is fixed to `/api`.
4. The actual combined request of the browser is `/api/v1/...`.
5. Alternative use of `servers.url=/` + `paths=/api/v1/...` is prohibited.
6. It is prohibited to mix two sets of OpenAPI base URL policies in different slices.

P2-02 public OpenAPI artifact rules:

1. `packages/contracts/openapi/api.openapi.json` remains the Web/business artifact and may contain `/api/v1/account/api-tokens` plus session schemas.
2. `packages/contracts/openapi/public-api.openapi.json` is generated for programmatic public consumers.
3. `public-api.openapi.json` must exclude `/api/v1/account/api-tokens`, token-management routes, token-management schemas, PAT plaintext fields, `secretHash`, example token values and any field that can reconstruct a secret.
4. `public-api.openapi.json` must also exclude browser-only session/CSRF routes and internal runner routes.
5. `make verify` must fail when either OpenAPI artifact is stale or when the public artifact violates these exclusion rules.

### 5.3 Health and Readiness

Health endpoint is not part of the business version API.

```http
GET /api/healthz
GET /api/readyz
```

Rules:

1. `/api/healthz` is used for liveness and only verifies that the API process is alive.
2. `/api/readyz` is used for readiness, and P0 required dependencies such as PostgreSQL and MinIO should be verified.
3. Health response does not return secret, token, connection string, and MinIO credential.
4. Health endpoint does not require `x-workspace-id`.
5. Health endpoint does not enter the core usage path of Web generated business client.

### 5.4 Account Token Management and Programmatic Public API

P2-02 adds two separate API surfaces:

```http
GET    /api/v1/account/api-tokens
POST   /api/v1/account/api-tokens
DELETE /api/v1/account/api-tokens/{tokenId}

GET    /api/public/v1/{resource}
POST   /api/public/v1/{resource}
PATCH  /api/public/v1/{resourceId}
DELETE /api/public/v1/{resourceId}
```

Rules:

1. `/api/v1/account/api-tokens` is a browser session self-service API. It is available to `user` and `admin`, but self-only.
2. `POST` and `DELETE` under `/api/v1/account/api-tokens` must validate `x-csrf-token`; `GET` does not require CSRF.
3. `/api/public/v1/*` uses `Authorization: Bearer <PAT>` and must not accept cookie session auth.
4. PAT Bearer public writes do not use CSRF, but must validate PAT scope, actor user status, Workspace membership and Workspace allowlist.
5. P2-02 public scopes are exactly `read`, `config:write`, `run` and `dependency:write`; `dependency:write` is limited to bounded Dependency File upload/delete, while list uses `read`. `tokens:write` is not a public scope.
6. Public PAT Workspace resolution allows explicit `x-workspace-id`, or automatic resolution only when the PAT allowlist has exactly one Workspace.
7. Public PAT Workspace resolution must not read browser current session, local storage preferred Workspace or default Workspace fallback.
8. Public routes must not expose PAT create/list/revoke.

ADR-0016/P2-04 adds one separate browser session source-download route:

```http
GET /api/v1/account/ai-skill/download
```

Rules:

1. The route requires a valid current cookie session and is available to both `user` and `admin`.
2. It is an account-level read, not a Workspace business resource; it must not require or resolve `x-workspace-id`.
3. It does not require CSRF.
4. It returns `application/zip` with `Content-Disposition: attachment; filename="surgepilot-public-api-skill.zip"` and `Cache-Control: private, no-store`.
5. It belongs only to `api.openapi.json`; the normalized public export must exclude it.
6. `AI_SKILL_SOURCE_NOT_AVAILABLE` is documented only in this operation's `503` response and must not be added to `info.x-surgepilot-error-codes` or the public artifact.

### 5.5 OpenAPI Product Version

`docs/sdd/adr/ADR-0027-product-version-and-artifact-identity.md` owns product-version resolution.
FastAPI runtime OpenAPI, the curated Web/business export, and the public export use the same
canonical `X.Y.Z` product version. A formal release tagged `vX.Y.Z` therefore exposes
`info.version: X.Y.Z`; a first-Admin system Catalog import derives the same value through the
curated runtime export.

Generated OpenAPI and the Public API AI skill snapshot are refreshed from FastAPI sources through
`make generate-contracts`. Docker builds do not rewrite or stamp generated contracts. The reserved
validation artifact version `v0.0.0`, registry tags, revisions, and API route prefix `/v1` are not
OpenAPI product versions.

### 5.6 Internal Runner Endpoints

Runner callbacks and runner-only endpoints must use internal prefix:

```http
POST /api/internal/v1/runner/callbacks
POST /api/internal/v1/runner/artifacts
```

Rules:

1. Internal runner endpoints do not belong to Web business API.
2. Internal runner endpoints must verify `x-runner-token`.
3. Internal runner endpoints must be excluded from Web client OpenAPI exports.
4. The source of truth of P0 Runner callback payload contract is `packages/contracts/runner/runner-callback.schema.json`.
5. P0 does not force the generation of Runner HTTP client; if the Runner API surface increases subsequently, 05 or ADR will be used to decide whether to add `runner-api.openapi.json`.
6. Web must not import or call internal runner endpoint.
7. Internal runner endpoint must not rely on browser cookie session or CSRF token.

---

## 6. Resource Naming and HTTP Methods

### 6.1 Resource Names

URL resource segment is pluralized using kebab-case.

Recommended:

```http
GET /api/v1/env-groups
GET /api/v1/dependency-files
GET /api/v1/load-nodes
GET /api/v1/test-plans
GET /api/v1/runs
```

Prohibited:

```http
GET /api/v1/envGroup
GET /api/v1/EnvGroups
GET /api/v1/dependency_file
GET /api/v1/loadNodeList
```

Rules:

1. Use lowercase for URLs.
2. Use kebab-case for multi-word resources.
3. Use plural numbers for collection resources.
4. The action endpoint is only used when the resource status changes and is not suitable for CRUD, such as `POST /api/v1/runs/{runId}/stop`.
5. No callable endpoint is reserved for P1/P2 capabilities.

### 6.2 HTTP Methods

| Method | Use |
| --- | --- |
| `GET` | Read resource or list |
| `POST` | Create resource or execute action |
| `PATCH` | Partial update |
| `PUT` | P0 is not used by default; if full replacement is required, it must be specified in Slice SDD |
| `DELETE` | Delete or soft-delete resource behind API |
| `HEAD` | P0 is not required by default |
| `OPTIONS` | Framework/CORS only |

Rules:

1. `GET` must have no business side effects.
2. `POST` create returns `201 Created` successfully, and action returns `200 OK` or `202 Accepted` successfully.
3. `PATCH` only updates the fields explicitly provided in the request body.
4. Use `204 No Content` when `DELETE` succeeds and does not need to return body.
5. Repeated requests such as Stop, callback, and artifact registration must be idempotent.
6. Do not use `POST /resource/delete` instead of the standard `DELETE` unless explicit action semantics exist and are written to Slice SDD.

### 6.3 Path Parameters

Path parameters must use semantic ID names.

Recommended:

```http
GET /api/v1/scenarios/{scenarioId}
GET /api/v1/test-plans/{testPlanId}
GET /api/v1/runs/{runId}
GET /api/v1/artifacts/{artifactId}/download
```

Prohibited:

```http
GET /api/v1/scenarios/{id}
GET /api/v1/runs/{uuid}
GET /api/v1/load-nodes/{node}
```

Rules:

1. Use `{resourceId}` style, such as `{scenarioId}`, `{runId}`, `{nodeId}`.
2. Do not use bare `{id}`.
3. The path parameter name must be consistent with the OpenAPI schema and generated client.
4. The path parameter value uses ULID string.
5. The API must verify whether the path parameter conforms to the ULID format; if the format is illegal, it returns `400 INVALID_REQUEST` or `422 VALIDATION_ERROR`, which is selected uniformly by Slice SDD.

---

## 7. Workspace Context

### 7.1 Header Rule

P0 uses header to pass Workspace context:

```http
x-workspace-id: 01HZX3Y9M0E9W7Z6M5QK9S8P7A
```

Rules:

1. API route path does not contain Workspace ID.
2. The web must send `x-workspace-id` after knowing the current workspace.
3. P0 only has the default Workspace; if the header is missing, the API must resolve to the default Workspace of the current user.
4. The API response must write back the actual `x-workspace-id` used to facilitate troubleshooting and front-end debugging.
5. The API must verify whether the current user can access the Workspace.
6. When the Workspace header is missing, has a wrong format, or the default Workspace cannot be parsed, `400 WORKSPACE_REQUIRED` is returned.
7. When the Workspace header is legal but the current user does not have permission to access the Workspace, `403 WORKSPACE_ACCESS_DENIED` is returned.
8. After P1 introduces multi-Workspace UI, the business API should be changed to force the client to send an explicit Workspace header; this change must be recorded by the corresponding SDD/ADR.
9. Setup Status is an explicit exception to P0 and can contain both platform-level read-only checks and current Workspace checks.

### 7.2 Workspace-Aware Business Resources

P0 The following business resources must be Workspace-aware:

1. Scenario;
2. Test Plan;
3. Run;
4. Env Group;
5. Dependency File;
6. Private Load Node;
7. Run Snapshot;
8. Artifact metadata;
9. Report summary;
10. Audit event where applicable.

Rules:

1. The query must be filtered by Workspace.
2. Create must write Workspace ID.
3. Operations such as update, delete, download, Stop, Validity mark, etc. must verify the Workspace.
4. Cross-workspace access must not return data from other workspaces.
5. Public Load Node can be a public resource of the platform, but when assigned to Run, it must still pass the permissions and resource rules verification of the current Workspace.

---

## 8. Authentication, CSRF and Headers

### 8.1 Session Auth

P0 uses cookie-based sessions.

Rules:

1. Session cookie must be `HttpOnly`.
2. Session cookie should use `SameSite=Lax`.
3. Production environments where HTTPS is available must have `Secure` enabled.
4. Session must have expiration time.
5. Logout must invalidate the server-side session.
6. The business API returns `401 UNAUTHENTICATED` when not logged in.
7. API response does not return session cookie value.

### 8.2 CSRF

Since P0 uses cookie sessions, write requests must use CSRF tokens.

```http
x-csrf-token: csrf_01HZX3Y9M0E9W7Z6M5QK9S8P7A
```

Rules:

1. `GET`, `HEAD`, `OPTIONS` do not require CSRF token.
2. `POST`, `PATCH`, `PUT`, `DELETE` must verify `x-csrf-token`.
3. CSRF token is generated by API and bound to server-side session.
4. Web obtains the token through `GET /api/v1/auth/csrf` or the clear endpoint corresponding to Slice.
5. CSRF tokens must not be written to logs, error details, real values of OpenAPI examples or test snapshots.
6. Internal runner endpoints do not use CSRF; only use `x-runner-token`.

### 8.3 Runner Internal Token

Runner callback uses internal token.

```http
x-runner-token: runner_internal_token
```

Rules:

1. Runner token can only be configured through environment variables.
2. Runner token must not appear in Web response, OpenAPI public examples, logs, audit events, and error details.
3. The API must first verify `x-runner-token` before processing the callback payload.
4. Invalid Runner token returns `401 RUNNER_UNAUTHORIZED`.
5. Web client OpenAPI does not include runner internal endpoints.

### 8.4 Request ID

The API must generate a request ID for each request and write it back in the response header:

```http
x-request-id: req_01HZX3Y9M0E9W7Z6M5QK9S8P7A
```

Rules:

1. The API must generate a request ID.
2. API response must contain `x-request-id`.
3. The `requestId` of the error response body must be consistent with the header.
4. Structured logs must contain request ID.
5. Request ID must not contain secret, cookie, token or original user input text.
6. P0 does not require the client to generate a request ID.

### 8.5 Cache-Control

The P0 business interface is not cached by default.

```http
Cache-Control: no-store
```

Rules:

1. Authenticated business API returns `Cache-Control: no-store` by default.
2. Whether the file download can be cached is specified by `07-storage-artifacts-minio.md`.
3. Health endpoint can use simpler cache rules, but sensitive status must not be cached.
4. P0 does not implement ETag / If-None-Match.

---

## 9. JSON, Field Naming and Data Types

### 9.1 Field Names

API request/response uses `camelCase`.

Recommended:

```json
{
  "createdAt": "2030-05-18T03:14:15.123Z",
  "updatedBy": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "workspaceId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A"
}
```

DB, migration, ORM model uses `snake_case`.

Recommended:

```sql
created_at
updated_by
workspace_id
```

Pydantic v2 recommended configuration:

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class ApiSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )
```

FastAPI routes must explicitly or default acknowledge output by alias:

```python
@router.get(
    "/v1/env-groups/{envGroupId}",
    response_model=EnvGroupResponse,
    response_model_by_alias=True,
)
async def get_env_group(env_group_id: str) -> EnvGroupResponse:
    ...
```

Rules:

1. Only the `camelCase` field is exposed in OpenAPI.
2. API response does not expose the DB `snake_case` field.
3. Web does not perform snake/camel handwriting conversion.
4. Pydantic schema should not use `serialize_by_alias=True` as the only guarantee; route or serialization helper must ensure alias output.
5. Contract tests must check that the exported OpenAPI field is `camelCase`.

### 9.2 IDs

P0 uses ULID string for external business ID.

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A"
}
```

Rules:

1. All business IDs in the API use string.
2. The ULID must be a 26-character Crockford Base32 representation.
3. DB storage uses `text` or `char(26)`, and PostgreSQL `uuid` is not used.
4. Do not mix UUID v4, UUID v7, and integer ID as external business IDs.
5. Security tokens such as Session ID, CSRF token, runner token, etc. are not business IDs and can use a dedicated secure random format.
6. The front-end must not assume the chronological order of ULIDs as the only sorting basis; the list sorting is still based on the back-end `createdAt` or cursor.

### 9.3 Time

API time fields use ISO 8601 UTC strings.

```json
{
  "createdAt": "2030-05-18T03:14:15.123Z",
  "startedAt": "2030-05-18T03:15:00.000Z",
  "endedAt": null
}
```

Rules:

1. API boundaries are unified to UTC.
2. The string must contain `Z`.
3. DB uses `timestamptz`.
4. Do not use Unix epoch milliseconds as the main API format.
5. The front-end is responsible for localized display.
6. If the Duration field needs to express seconds, use a clear field name, such as `durationSeconds`.
7. P0 does not define complex timezone preference API.

### 9.4 Enums

API enum value uses lower snake case.

Recommended:

```json
{
  "status": "running",
  "failureType": "node_unreachable",
  "errorCategory": "auth_failed",
  "scriptResult": "script_error"
}
```

Prohibited:

```json
{
  "status": "Running",
  "failureType": "nodeUnreachable",
  "errorCategory": "AUTH_FAILED"
}
```

P0 core enumeration example:

```text
initializing
running
stopping
finished
failed
aborted
standard
debug
valid
invalid
passed
not_evaluated
auth_failed
node_unreachable
script_error
```

Rules:

1. API enum value uses lower snake case.
2. TypeScript enum / union generated by OpenAPI.
3. DB enum or check constraint can use the same lower snake case.
4. UI labels must not directly reuse enum values, and copywriting should be displayed based on enum mapping on the frontend.
5. The new enum value must be registered in Slice SDD and the contract test must be completed.

### 9.5 Nullable, Optional and PATCH

P0 must distinguish between missing, `null` and value.

Semantics:

| Input | Meaning |
| --- | --- |
| missing | Leave unchanged in PATCH |
| `null` | Clear field if nullable; else `422 VALIDATION_ERROR` |
| value | Set to the provided value |

PATCH request example:

```json
{
  "remark": null,
  "tags": ["smoke", "checkout"]
}
```

Pydantic v2 implementation suggestions:

```python
from pydantic import BaseModel

class UpdateEnvGroupRequest(BaseModel):
    name: str | None = None
    remark: str | None = None

def to_patch_dict(payload: UpdateEnvGroupRequest) -> dict:
    return payload.model_dump(exclude_unset=True)
```

Rules:

1. The PATCH handler must recognize explicitly provided fields using `exclude_unset=True` or an equivalent mechanism.
2. If the field is not allowed to be cleared, explicitly passing in `null` must return `422 VALIDATION_ERROR`.
3. If the clearing semantics are easy to be misused, Slice SDD should prioritize defining action endpoints, such as `POST /api/v1/load-nodes/{nodeId}/clear-credential`, rather than letting `PATCH` bear the high risk of clearing.
4. AI Coding must not use simple truthy/falsy judgment to update fields.
5. Contract tests should cover the key differences of missing and `null`.

---

## 10. Response Envelope Rules

### 10.1 Single Resource Response

The single resource response returns the resource object directly without including a layer of `data`.

Recommended:

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "name": "Default Env",
  "createdAt": "2030-05-18T03:14:15.123Z"
}
```

Prohibited:

```json
{
  "data": {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A"
  }
}
```

Reason: OpenAPI generated client already has a clear type, and additional envelope has no benefit to P0.

### 10.2 List Response

The list response must use a unified list envelope, and direct return of an array is prohibited.

Offset list:

```json
{
  "items": [],
  "page": 1,
  "pageSize": 20,
  "total": 0
}
```

Cursor list:

```json
{
  "items": [],
  "nextCursor": null,
  "hasMore": false
}
```

Rules:

1. Lists must not directly return arrays.
2. `items` must always be an array.
3. Offset list must return `total`.
4. Cursor list is not required to return `total`.
5. `nextCursor` in the Cursor list is an authoritative field; `hasMore` is only a UI convenience field and must be consistent with `nextCursor`.
6. Run / Artifact / Audit / callback-like list using cursor.
7. Ordinary CRUD management lists use offset by default.
8. An empty list must return an empty array, not `null`.

### 10.3 Empty and Delete Responses

Use when the deletion is successful and no body is needed:

```http
HTTP/1.1 204 No Content
```

Rules:

1. `204` response does not return JSON body.
2. If delete only initiates an asynchronous action, it can return `202 Accepted` and action status.
3. If the resource is referenced and cannot be deleted, return `409 RESOURCE_IN_USE`.
4. Soft delete is an implementation detail of the warehousing layer; the API does not expose the `deletedAt` query parameter or include-deleted switch.
5. P0 does not provide restore deleted resource API.

---

## 11. Pagination, Filtering and Sorting

### 11.1 Pagination Selection Rule

| Resource Type | Pagination |
| --- | --- |
| Env Groups | Offset |
| Dependency Files | Offset |
| Load Nodes | Offset |
| Scenarios | Offset |
| Test Plans | Offset |
| Runs | Cursor |
| Artifacts | Cursor |
| Audit events | Cursor |
| Runner callbacks / event history | Cursor |

Rules:

1. Use offset for ordinary management lists, which is simple and stable.
2. Use cursor for time series, fast-growing, and meaningless lists with deep page turning.
3. Run List uses cursor starting from P0.
4. The same endpoint cannot support offset and cursor at the same time.
5. Slice SDD must know which paging is used for this list.

### 11.2 Offset Pagination

Request:

```http
GET /api/v1/env-groups?page=1&pageSize=20
```

Response:

```json
{
  "items": [],
  "page": 1,
  "pageSize": 20,
  "total": 0
}
```

Rules:

1. `page` starts with 1.
2. The default `pageSize` is determined by the API configuration, and 20 is recommended.
3. `pageSize` must have an upper limit, and the recommended maximum is 100.
4. `total` represents the total number under the current filter.
5. Illegal `page` or `pageSize` returns `400 INVALID_QUERY_PARAMETER`.

### 11.3 Cursor Pagination

Request:

```http
GET /api/v1/runs?cursor=eyJjcmVhdGVkQXQiOiIyMDI2LTA1LTE4VDAzOjE0OjE1LjEyM1oiLCJpZCI6IjAxSFpYIn0&limit=20
```

Response:

```json
{
  "items": [],
  "nextCursor": null,
  "hasMore": false
}
```

Rules:

1. Cursor must be generated by the server.
2. Cursor content should not require front-end understanding.
3. Cursor should be bound to sorting and filtering conditions; the old cursor should become invalid when conditions change.
4. Illegal cursor returns `400 INVALID_CURSOR`.
5. `limit` must have an upper limit, and a maximum of 100 is recommended.
6. The default sorting is `-createdAt`, and uses the `(-createdAt, -id)` composite key as a stable tie-breaker; where `id` is a ULID string, and lexicographic descending order is equivalent to chronological descending order.
7. `nextCursor` is `null` which means there is no next page.

### 11.4 Filtering

Recommended concise query parameter:

```http
GET /api/v1/runs?status=running&validity=valid&runType=standard
```

Rules:

1. Filter fields must be whitelisted.
2. Unknown filter parameter returns `400 INVALID_QUERY_PARAMETER`.
3. Multi-value filter can use comma-separated value, but it must be specified by Slice SDD.
4. Use clear fields for the time range, such as `createdFrom`, `createdTo`.
5. Use the search keyword `q` uniformly.
6. Do not use `filter[status]=running` style as P0 default.
7. It is not allowed to bypass Workspace or permissions through filter.

### 11.5 Sorting

Sorting uses the `sort` parameter.

```http
GET /api/v1/runs?sort=-createdAt
GET /api/v1/env-groups?sort=name
```

Rules:

1. `sort=createdAt` means ascending order.
2. `sort=-createdAt` means descending order.
3. P0 only supports single field sorting by default.
4. Sort field must be whitelisted.
5. Unknown sort field returns `400 INVALID_QUERY_PARAMETER`.
6. The frontend is not allowed to pass any DB column name.
7. The sort of Cursor pagination must be stable and controlled by the backend; Slice SDD can restrict the cursor list from accepting any sort.

---

## 12. Error Response

### 12.1 Error Shape

The P0 API uses a unified error response structure.

```json
{
  "code": "RESOURCE_UNAVAILABLE",
  "message": "The selected node is currently unavailable.",
  "requestId": "req_01HZX3Y9M0E9W7Z6M5QK9S8P7A"
}
```

Fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `code` | yes | Stable machine-readable error code |
| `message` | yes | English fallback message |
| `requestId` | yes | Request ID for troubleshooting |
| `details` | no | Structured details, usually validation errors |

Rules:

1. `code` must be stable and must not change with the copy.
2. `message` always use English, do not write Chinese, and will not be used as i18n key.
3. If the Frontend needs to be localized, i18n mapping must be done based on `code` and necessary `details[].code`.
4. `message` is the English fallback, which can be optimized but cannot contain sensitive information.
5. `requestId` must be consistent with the response header `x-request-id`.
6. Omit the `details` field when no details are available; `details: null` must not be returned.
7. Do not use RFC 7807 as the P0 default error format.
8. Do not return Python exceptions, SQL errors, and stack traces to the frontend.

### 12.2 Field Validation Errors

Field-level validation errors use the `details` array.

```json
{
  "code": "VALIDATION_ERROR",
  "message": "The request contains invalid fields.",
  "requestId": "req_01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "details": [
    {
      "field": "email",
      "code": "INVALID_FORMAT",
      "message": "Enter a valid email address."
    },
    {
      "field": "loadSettings.concurrencyPerNode",
      "code": "VALUE_OUT_OF_RANGE",
      "message": "Concurrency per node must be greater than 0."
    }
  ]
}
```

Rules:

1. `field` uses API JSON field path, which is camelCase.
2. Use dot path for nested fields, such as `loadSettings.concurrencyPerNode`.
3. Array fields can use `steps[0].method`.
4. `details[].code` uses stable upper snake case.
5. `details[].message` uses English.
6. The front-end form should prioritize locating errors based on `field`.
7. AI Coding must not return Pydantic's default error structure directly to the Web.

### 12.3 HTTP Status Mapping

| Status | Use | Example Code |
| --- | --- | --- |
| `400 Bad Request` | Malformed request, invalid query, invalid cursor | `INVALID_REQUEST`, `INVALID_QUERY_PARAMETER`, `INVALID_CURSOR` |
| `401 Unauthorized` | Unauthenticated or invalid runner token | `UNAUTHENTICATED`, `RUNNER_UNAUTHORIZED` |
| `403 Forbidden` | Authenticated but not allowed | `FORBIDDEN`, `WORKSPACE_ACCESS_DENIED`, `RUNNER_FORBIDDEN` |
| `404 Not Found` | Resource not found or intentionally hidden | `RESOURCE_NOT_FOUND` |
| `409 Conflict` | State conflict, reference protection, busy resource | `RESOURCE_IN_USE`, `RUN_TERMINAL_STATE`, `LOAD_NODE_BUSY` |
| `413 Payload Too Large` | Upload too large | `PAYLOAD_TOO_LARGE` |
| `415 Unsupported Media Type` | Unsupported upload or request content type | `UNSUPPORTED_MEDIA_TYPE` |
| `422 Unprocessable Entity` | Semantic validation failed | `VALIDATION_ERROR`, `RUNNER_CALLBACK_INVALID` |
| `500 Internal Server Error` | Unexpected server error | `INTERNAL_ERROR` |
| `503 Service Unavailable` | Dependency unavailable | `STORAGE_UNAVAILABLE` |

Rules:

1. The same error code must always correspond to one type of HTTP status.
2. Do not return all `200 OK` for the convenience of the frontend.
3. Don't disguise permission errors as business successes.
4. Whether cross-workspace resources return 403 or 404 is determined by Slice SDD, but similar resources must be consistent.
5. Successful idempotent processing of repeated callbacks does not use error codes and should return a successful response.

---

## 13. Core Error Code Registry

### 13.1 Registry Principle

P0 only pre-registers core error codes to prevent the error code registry from becoming the entrance to "design a complete API in advance".

Rules:

1. New Slice uses universal codes by default, such as `RESOURCE_NOT_FOUND`.
2. Only when the frontend, contract test or business process must be branched according to resource type, the resource-specific error code is registered.
3. New error codes must be proposed in the API Contract chapter corresponding to Slice SDD before implementation.
4. Code Review must reject unregistered error codes.
5. The error code must use upper snake case.
6. Error code message examples must be in English.
7. A Slice ADR may authorize a route-local code that is documented in that operation's `responses` without adding it to the global `info.x-surgepilot-error-codes` registry. The Slice must explain why the code must remain out of other artifacts and provide automated inclusion/exclusion tests. ADR-0016 uses this rule for `AI_SKILL_SOURCE_NOT_AVAILABLE`.

### 13.2 Core Registry

| Code | Status | Meaning |
| --- | --- | --- |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `INVALID_REQUEST` | 400 | Malformed request body or invalid JSON |
| `VALIDATION_ERROR` | 422 | Field-level or semantic validation failed |
| `INVALID_QUERY_PARAMETER` | 400 | Unknown or invalid query parameter |
| `INVALID_CURSOR` | 400 | Cursor cannot be parsed or does not match current query |
| `UNAUTHENTICATED` | 401 | User is not logged in |
| `FORBIDDEN` | 403 | User does not have required role or permission |
| `RESOURCE_NOT_FOUND` | 404 | Resource does not exist or is hidden |
| `RESOURCE_IN_USE` | 409 | Resource cannot be deleted or changed because it is referenced |
| `SCENARIO_REVISION_CONFLICT` | 409 | Scenario was modified after the client loaded or saved it; reload before saving or starting Debug Run |
| `WORKSPACE_REQUIRED` | 400 | Workspace context cannot be resolved |
| `WORKSPACE_ACCESS_DENIED` | 403 | User cannot access workspace |
| `LOAD_NODE_BUSY` | 409 | Load node is already leased by another Run |
| `RUN_CREATION_NOT_ALLOWED` | 403 | Developer-only or guarded Run creation path is disabled |
| `RUN_TERMINAL_STATE` | 409 | Action is invalid because Run is already terminal (used by Stop-on-terminal and terminal-late artifact upload beyond the 5-minute acceptance window) |
| `RUN_STOP_NOT_ALLOWED` | 409 | Run cannot be stopped in current state |
| `RUNNER_UNAUTHORIZED` | 401 | Runner token missing or invalid |
| `RUNNER_FORBIDDEN` | 403 | Runner token is valid, but the runner is not allowed to access the target Run or runner-owned resource |
| `RUNNER_CALLBACK_INVALID` | 422 | Runner callback payload does not match schema |
| `RUNNER_CALLBACK_CONFLICT` | 409 | Runner callback idempotency key was reused with a different payload |
| `INVALID_ARTIFACT_PATH` | 400 | Artifact `relativePath` is not P0 safe |
| `INVALID_ARTIFACT_TYPE` | 400 | Artifact type is not in the P0 whitelist |
| `ARTIFACT_SIZE_MISMATCH` | 400 | Uploaded artifact actual size differs from declared `sizeBytes` |
| `ARTIFACT_HASH_MISMATCH` | 400 | Uploaded artifact actual SHA-256 differs from declared `sha256` |
| `ARTIFACT_PATH_CONFLICT` | 409 | Same Run already has the same `relativePath` with different content or type |
| `ARTIFACT_NOT_READY` | 409 | Artifact metadata or summary exists but is not ready to return |
| `RUN_CONTROL_CONFLICT` | 409 | Run-control work item already exists for the same Run and action |
| `FILE_IN_USE` | 409 | Dependency File cannot be deleted because it is referenced |
| `PAYLOAD_TOO_LARGE` | 413 | Uploaded payload exceeds configured limit |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Request or upload media type is not supported |
| `STORAGE_UNAVAILABLE` | 503 | MinIO or storage dependency unavailable |

### 13.3 Notes on Common Future Codes

The following are not pre-registered for P0 implementation. Add them only when a Slice proves they are necessary:

```text
INVALID_SORT_FIELD
DUPLICATE_RESOURCE
LOAD_NODE_OFFLINE
LOAD_NODE_UNINITIALIZED
```

Rules:

1. Do not implement these codes just because they are listed as examples.
2. If a Slice adds one, it must define exact status, trigger condition, response example, and contract tests.
3. Repeated idempotent callback success should return `200 OK` and may include `duplicate: true`; it is not an error.
4. P0-04 activated Runner callback and artifact codes are registered in §13.2.

---

## 14. OpenAPI Contract Workflow

### 14.1 Source of Truth

FastAPI routes and Pydantic schemas are the OpenAPI source of truth for the P0 baseline and every active Slice.

```text
FastAPI routes + Pydantic schemas
  -> export OpenAPI
  -> packages/contracts/openapi/api.openapi.json
  -> openapi-typescript / openapi-fetch
  -> packages/contracts/generated/web-client/
```

Rules:

1. FastAPI route + Pydantic schema is OpenAPI source of truth.
2. `packages/contracts/openapi/api.openapi.json` is an export artifact and must not be handwritten.
3. Do not create handwritten `openapi.yaml` as the main contract source.
4. Web client/types must be generated from exported OpenAPI.
5. Generated files must be reproducible.
6. `make verify` must check whether generated contracts are stale.

### 14.2 Required Files

OpenAPI artifact path fixed:

```text
packages/contracts/openapi/api.openapi.json
packages/contracts/openapi/public-api.openapi.json
```

`api.openapi.json` is the Web/business OpenAPI artifact. `public-api.openapi.json` is the P2-02 programmatic consumer artifact for `/api/public/v1/*`; because `servers.url=/api`, its normalized OpenAPI paths use `/public/v1/...`.

Web generated client path is fixed:

```text
packages/contracts/generated/web-client/
```

OpenAPI export script path is fixed:

```text
scripts/export_openapi.py
```

Rules:

1. The Export script must import the FastAPI app in `apps/api/app/main.py`.
2. Export script is not written as Makefile inline Python.
3. Export script is not placed in `apps/api/scripts` or `apps/web/scripts`.
4. Web can only use generated client through `@surgepilot/contracts` workspace dependency.
5. Web is not allowed to use relative paths import `packages/contracts/generated/...`.
6. Internal runner endpoints must not enter Web generated client OpenAPI.

### 14.3 Required Commands

Root command:

```bash
make generate-contracts
make verify
```

`make generate-contracts` must be completed:

1. export FastAPI OpenAPI;
2. write `packages/contracts/openapi/api.openapi.json`;
3. run contracts package generation;
4. update `packages/contracts/generated/web-client/`;
5. produce stable output.

`make verify` must check at least:

```bash
make generate-contracts
git diff --exit-code packages/contracts
```

If there is a diff after generation, it means that the API or schema has changed but the contracts have not been committed, and verify must fail.

### 14.4 OpenAPI Quality Rules

Each endpoint must have:

1. stable `operationId`;
2. request schema where applicable;
3. response schema;
4. documented error responses for common non-2xx cases;
5. required headers where applicable;
6. auth requirement;
7. pagination query schema for list endpoint;
8. clear tags;
9. English examples only.

Operation ID rules:

```text
listEnvGroups
createEnvGroup
getEnvGroup
patchEnvGroup
deleteEnvGroup
stopRun
downloadArtifact
```

Prohibited:

```text
read_items_api_v1_env_groups_get
env_groups_get
operation_1
```

### 14.5 Pydantic Schema Rules

Rules:

1. Separate the request schema and response schema, and do not reuse the ORM model with sensitive fields.
2. Response schema does not include password hash, SSH credential, session value, CSRF token, and runner token.
3. Separate Create request and update request.
4. PATCH request must support `exclude_unset=True`.
5. The required fields in OpenAPI schema must be accurate.
6. File upload uses multipart schema, and the fields are specified by the corresponding Slice SDD.
7. `message` and other user-visible text in Examples are in English.
8. Do not let Pydantic's default validation response leak directly to the frontend; it must be converted into a unified error structure.

### 14.6 Web Client Usage

Rules:

1. Handwritten request / response TypeScript types are not allowed on the Web.
2. Web must not guess API response shape.
3. Web must use generated client/types from `@surgepilot/contracts`.
4. Web middleware uniformly injects `x-workspace-id` and `x-csrf-token`.
5. Web must not call `/api/internal/v1/runner/...`.
6. Front-end data layer must derive cache/query keys from generated request parameters or `operationId`, not from manually duplicated URL strings.
7. The specific front-end cache library is determined by `08-frontend-routing-and-ui-rules.md`.

---

## 15. Runner Callback Contract Boundary

### 15.1 Contract Location

Runner callback schema is located at:

```text
packages/contracts/runner/runner-callback.schema.json
```

Rules:

1. Runner callback payload must be constrained by schema.
2. Runner does not import API internal Pydantic schema.
3. The API does not assume that Runner is an internal Python class.
4. Changes to callback schema must first update contracts.
5. Callback schema changes must be supplemented by contract tests.
6. Detailed state machine and event processing rules are placed in `05-runner-protocol-and-run-state-machine.md`.

### 15.2 Minimum Callback Fields

P0 callback contains at least:

```json
{
  "runId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "nodeId": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
  "eventType": "running",
  "eventTime": "2030-05-18T03:14:15.123Z",
  "schemaVersion": "1",
  "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
  "seq": 2,
  "message": "The runner process has started."
}
```

Rules:

1. `runId` and `nodeId` use ULID string.
2. `eventType` uses lower snake case.
3. `eventTime` uses ISO 8601 UTC.
4. `schemaVersion` is fixed to `"1"` at P0.
5. `eventId` is a ULID and must be unique on the same Run.
6. `seq` is a monotonically increasing integer of the runner event stream on the same Run / node and is only used for diagnosis.
7. `message` uses English.
8. `message` must not contain token, credential, env secret or full local sensitive path.
9. Event-specific payload is specified by 05 and schema.

### 15.3 Callback Idempotency

Runner callback must be idempotent.

Recommended business keys:

```text
(runId, eventId)
```

Diagnostic related fields (should not be used as idempotent keys or state migration basis):

```text
(runId, nodeId, seq, eventType, eventTime)
```

Additional rules:

API may log these fields for troubleshooting and correlation, but must not use them to deduplicate callbacks or decide state transitions.

Rules:

1. If the same `(runId, eventId)` arrives repeatedly and the payload is the same, success should be returned without repeated advancement status.
2. Repeated success responses may contain `duplicate: true`.
3. Repeated callback processing is not an error if it is successfully processed, and no error code is used.
4. Inconsistency in the payload of the same `eventId` is a conflict, and the specific error code is determined by 05.
5. Terminal Run must not be overwritten by subsequent callbacks.
6. When callback is ignored, a structured log must be written, including reason, runId, nodeId, eventId, eventType, seq, and requestId.
7. Runner callback does not determine the final business status; API state machine is the only authority.

---

## 16. Stop and Other Idempotent Actions

### 16.1 Stop Run

Stop endpoint:

```http
POST /api/v1/runs/{runId}/stop
```

Rules:

1. Stop can only be triggered for the `initializing` / `running` status.
2. After Stop succeeds, Run enters `stopping`.
3. Repeated Stop must be idempotent and multiple stop processes must not be created.
4. If Run is terminal, return `409 RUN_TERMINAL_STATE`.
5. If Run is already `stopping` but not yet terminal, repeating Stop returns `200 OK` and the current Run status, which is regarded as idempotent success.
6. Stop response must return the current Run status.
7. Stop must not wait synchronously for the remote runner to exit completely.
8. Stop timeout and self-healing are handled by `api-worker`, see 05 for details.

Example response:

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "status": "stopping",
  "stopRequestedAt": "2030-05-18T03:14:15.123Z"
}
```

### 16.2 Run Creation

P0 does not introduce the common `Idempotency-Key` middleware, but Run creation must have minimal server-side anti-duplication mechanism.

Rules:

1. The frontend must prevent repeated submissions, but it cannot rely solely on the frontend.
2. The API must create Run Snapshot, Run, node lease, and mark Load Node Busy in the transaction.
3. Remote SSH/SFTP work must not be performed within a DB transaction.
4. P0-06 must be based on Run Snapshot hash or equivalent business key, and perform server-side deduplication within a short time window, 30 seconds is recommended.
5. When repeated requests hit deduplication, the first created Run should be returned instead of creating the second Run.
6. Deduplication key should at least contain workspaceId, triggeredBy, runType, source object ID, selected node ID, and snapshot hash.
7. Deduplication must not bypass permission, Workspace and node lease verification.
8. The specific unique index or table structure is designed by P0-06 Slice SDD.
9. After Deduplication hits an existing Run, it must be verified again that the `workspaceId` of the Run is strictly equal to the requested Workspace; if they are inconsistent, it will be treated as a cache miss, and Runs must not be reused across Workspaces.

### 16.3 Artifact Registration

Artifact registration must be idempotent.

Recommended business keys:

```text
(runId, relativePath)
```

Rules:

1. If the same safe relative path of the same Run is registered repeatedly, the existing metadata should be updated or returned, as specified by Slice SDD.
2. Absolute paths are not allowed.
3. `..` path traversal is not allowed.
4. It is not allowed to overwrite other Run or other Workspace artifacts.
5. Failure of Artifact registration shall not cause Run to stay in running/stopping permanently.
6. Web is downloaded through artifact ID, not object key.

---

## 17. File Upload and Download API Rules

### 17.1 Dependency File Upload

P0 dependency file upload uses API proxy to write to MinIO.

Rules:

1. Web uploads to API, not MinIO directly.
2. API verifies auth, Workspace, file size, file name and reference relationship.
3. Create metadata after the API is written to MinIO.
4. API response does not return MinIO credential, presigned URL or object key.
5. API response only returns business metadata.
6. The default upload limit is `100MB`, which can be overridden by `apps/api` configuration; if the limit is exceeded, `413 PAYLOAD_TOO_LARGE` will be returned. The specific upper limit can be adjusted by P0-02 Slice, but must be explicitly recorded in the Slice SDD.

Example response:

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "filename": "users.csv",
  "sizeBytes": 1024,
  "contentType": "text/csv",
  "createdAt": "2030-05-18T03:14:15.123Z"
}
```

### 17.2 Artifact Download

Artifact download uses an API proxy.

```http
GET /api/v1/artifacts/{artifactId}/download
```

Rules:

1. Web does not accept MinIO presigned URL.
2. Web does not receive MinIO object key.
3. API checks metadata based on artifact ID.
4. API verification auth, Workspace, Run permission and path safety.
5. The API reads from MinIO and streams to the Web.
6. The file name response header must use safe filename.
7. A unified error response is returned if the download fails; object key or MinIO internal error must not be exposed.

### 17.3 MinIO Object Key Exposure

Hard rules:

1. The MinIO object key must not be returned to the Web under any circumstances.
2. Object key can only be used as an internal implementation detail of API/Worker/storage adapter.
3. Web only sees metadata such as business ID, display file name, size, content type, createdAt, etc.
4. If object key is required for debugging, only server-side structured logs are allowed and must not contain secrets; specific rules are confirmed by 07.

### 17.4 Repo-Owned Source Bundle Download

ADR-0016/P2-04's official AI skill source download is not a MinIO asset download.

Rules:

1. Build the bounded repository-owned zip at request time from the governed source directory.
2. Do not persist the zip, create database metadata, upload it to MinIO, or expose a server filesystem path.
3. The archive must contain only safe source-relative regular files and must exclude caches, bytecode, temporary files, symlinks, and path escapes.
4. Source-unavailable errors use the standard error envelope and must not reveal candidate directories or absolute paths.

---

## 18. Future Extension Points Kept Out of P0

### 18.1 Rate Limit

P0 does not define common rate limit response headers, nor does it implement a common rate limit framework.

Rules:

1. The explosion-proof login failure belongs to `06-security-permission-workspace.md`.
2. `X-RateLimit-*` response headers are not reserved.
3. If subsequent P1/P2 requires a general API rate limit, a new contract must be added through the corresponding SDD/ADR.

### 18.2 ETag and Conditional Requests

P0 does not implement ETag / `If-None-Match` .

Rules:

1. Do not return `ETag` in P0 endpoint.
2. Web is not required to implement conditional request.
3. If P1 has clear benefits from single resource caching, then add it to the corresponding SDD.
4. No unused fields or hidden logic may be reserved for ETag in P0.

---

## 19. API Security Boundaries

### 19.1 Sensitive Values Must Not Be Returned

API response, error response, OpenAPI example, and logs must not return the following values:

1. password;
2. password hash;
3. session cookie value;
4. CSRF token value except the explicit CSRF token endpoint response;
5. runner internal token;
6. SSH password;
7. SSH private key;
8. SSH credential encryption key;
9. MinIO access key / secret key;
10. MinIO object key to Web;
11. environment-provided secrets;
12. stack trace;
13. raw SQL error;
14. server-side absolute path or path fragment containing usernames or container paths, such as `/home/<user>/...` or `/tmp/surgepilot-runner-xxx/...`; Web may receive only safe relative paths explicitly defined by Slice SDD.

### 19.2 Do Not Implement P1/P2 Through API Backdoors

P0 prohibits the first implementation of P1/P2 capabilities through the API, even if the Web does not display it.

Disallow implementation at P0:

1. API Catalog upload / parse / operation import;
2. cURL import;
3. Schedule Run or Scheduled Job;
4. Monitoring / Grafana / InfluxDB management;
5. multi-node execution;
6. auto resource allocation;
7. Workspace switching / create / edit / archive UI endpoints;
8. User Management UI endpoints;
9. OAuth / OIDC / SSO endpoints;
10. Secret Env Var type;
11. non-MinIO storage backend selection;
12. Generated YAML preview or editor endpoint;
13. Postman Collection or JMX upload endpoint.

Allowed:

1. Explain future expansion points in the document;
2. The DB field retains reasonable expansion space, but must not expose available APIs;
3. Route planning can exist in SDD and must not implement callable endpoints;
4. The required internal worker job endpoint for P0 should not exist, and the worker should work through the DB job table or process loop.

---

## 20. Slice SDD API Contract Requirements

Each Slice SDD that touches the API must cover the following in its `API Contract` section, but does not enforce the use of additional nested templates:

1. endpoints;
2. request schemas;
3. response schemas;
4. required headers;
5. query parameters;
6. pagination / filtering / sorting if applicable;
7. error codes;
8. idempotency requirements;
9. contract tests;
10. any deviation from this document and the reason.

Rules:

1. Slice SDD must not copy a huge API subtemplate.
2. Slice SDD should only write the API details required by Slice.
3. New error codes must be proposed in Slice SDD and explain why the core registry is insufficient.
4. The API Contract chapter of Slice SDD must be sufficient to prevent AI Coding from guessing the interface.
5. If a Slice does not involve API, `No API changes` must be specified.

---

## 21. Contract Tests and Done When

### 21.1 Required Contract Tests

P0 contract tests cover at least:

1. OpenAPI can be exported;
2. generated Web client is fresh;
3. Web generated types contain expected operation IDs;
4. no hand-written Web API types for covered endpoints;
5. list response schemas use `items` envelope;
6. error response schema is consistent;
7. validation error details use `{field, code, message}`;
8. `message` examples are English;
9. `x-workspace-id` is documented where required;
10. `x-csrf-token` is documented for write requests;
11. internal runner endpoints are excluded from Web OpenAPI;
12. runner callback schema validates valid events;
13. runner callback schema rejects invalid event payloads;
14. artifact download endpoint does not expose object key;
15. generated contracts are not stale after `make generate-contracts`.

### 21.2 API Implementation Done When

An API-impacting change is not done until:

1. Slice SDD API Contract is updated;
2. FastAPI route and Pydantic schema are implemented;
3. OpenAPI export is refreshed;
4. generated Web client/types are refreshed;
5. contract tests pass;
6. API tests cover auth, Workspace, success, validation error, permission error;
7. relevant Web consumer uses generated client;
8. relevant Runner consumer uses runner schema or documented HTTP contract;
9. `make verify` passes or the Slice SDD documents the temporary bootstrap verification command;
10. final PR notes mention contract changes and any new error codes.

### 21.3 AI Coding Rule

AI Coding must comply with:

1. Do not invent API shapes.
2. Do not hand-write Web request / response types.
3. Do not expose P1/P2 endpoints.
4. Do not return Chinese API messages or Chinese code examples.
5. Do not return secrets.
6. Do not bypass Workspace validation.
7. Do not bypass generated contracts.
8. Do not mark implementation complete without contract freshness check.

---

## 22. Review Checklist

### 22.1 URL and Scope

- [ ] Does the endpoint use `/api/v1/...` for business API?
- [ ] Does OpenAPI use `servers.url=/api` and paths `/v1/...`?
- [ ] Is runner-only API under `/api/internal/v1/runner/...`?
- [ ] Is the endpoint authorized by the current active Slice SDD and ADR where required?
- [ ] Is the endpoint included in or excluded from the correct Web/business, programmatic public, or runner-internal OpenAPI artifact?
- [ ] Does it avoid inactive capabilities outside the authorizing Slice?
- [ ] Is Workspace absent from the route path?

### 22.2 Workspace, Auth and Security

- [ ] Does the endpoint require session auth where needed?
- [ ] Does write API require `x-csrf-token`?
- [ ] Does business API resolve and validate `x-workspace-id`?
- [ ] Does response write back actual `x-workspace-id`?
- [ ] Does runner endpoint require `x-runner-token`?
- [ ] Are secrets excluded from response and logs?
- [ ] Is MinIO object key hidden from Web?

### 22.3 JSON and Schemas

- [ ] Are API fields `camelCase`?
- [ ] Are DB fields kept `snake_case`?
- [ ] Are IDs ULID strings?
- [ ] Are times ISO 8601 UTC?
- [ ] Are enum values lower snake case?
- [ ] Are all example messages in English?
- [ ] Does PATCH distinguish missing from `null`?

### 22.4 Pagination and Query

- [ ] Does list response use `items` envelope?
- [ ] Is bare array response avoided?
- [ ] Is Run / Artifact / Audit list cursor-based?
- [ ] Are filters white-listed?
- [ ] Are sort fields white-listed?
- [ ] Is cursor invalidation handled for changed filter/sort?

### 22.5 Error Handling

- [ ] Does error response use `{code, message, requestId, details?}`?
- [ ] Is `message` English?
- [ ] Is i18n based on `code`, not message parsing?
- [ ] Is `details` omitted when empty?
- [ ] Is the error code in core registry or Slice SDD?
- [ ] Does the same error code map to one status class?
- [ ] Are Pydantic default errors converted?

### 22.6 OpenAPI and Generated Client

- [ ] Is OpenAPI generated from FastAPI/Pydantic?
- [ ] Is hand-written OpenAPI source avoided?
- [ ] Are operation IDs stable?
- [ ] Are generated Web client/types refreshed?
- [ ] Does `make verify` fail on stale contracts?
- [ ] Does Web import from `@surgepilot/contracts`?
- [ ] Are internal runner endpoints excluded from Web generated client?

### 22.7 Idempotency and Runner

- [ ] Is Stop idempotent?
- [ ] Is Run creation protected from duplicate requests server-side?
- [ ] Is Runner callback idempotent?
- [ ] Does callback use `eventId` as the idempotency key?
- [ ] Are duplicate callback successes treated as success, not error?
- [ ] Are terminal states protected from late callbacks?
- [ ] Are ignored callbacks logged with reason?

---

## 23. Review Incorporation Notes

### 23.1 Accepted from Review 1

Accepted:

1. Locked OpenAPI base URL strategy to `servers.url=/api` and paths `/v1/...`.
2. Added the base URL decisions to the confirmed decision table.
3. Removed ambiguous "allowed alternative" base URL strategy.
4. Fixed error code vs HTTP status consistency.
5. Removed `200 or 409` and `409 or 422` status ambiguity.
6. Replaced TanStack Query-specific rule with framework-neutral front-end data layer rule.
7. Removed version-sensitive `serialize_by_alias=True` from the Pydantic base example.
8. Added FastAPI `response_model_by_alias=True` guidance.
9. Added PATCH implementation guidance using `exclude_unset=True`.
10. Added Run creation server-side deduplication requirement.
11. Strengthened Workspace fallback from "may" to "must" in P0.
12. Added path parameter naming, list envelope, soft delete, and API-proxy file download to confirmed decisions.
13. Added multi-word lower snake case enum examples.
14. Clarified `nextCursor` is authoritative and `hasMore` is UI convenience.
15. Standardized absent `details` behavior.
16. Added core-vs-specific error code rule.
17. Explicitly banned MinIO object key exposure to Web.

Partially accepted:

1. Runner endpoint moved to `/api/internal/v1/runner/...`.
2. Internal runner endpoints must be excluded from Web OpenAPI.
3. P0 does not yet require a separate Runner OpenAPI client; runner callback schema remains the P0 source of truth.

### 23.2 Accepted from Review 2

Accepted:

1. Reduced large error registry to a small core registry.
2. Added Slice-driven error code growth rule.
3. Removed rate limit header pre-allocation.
4. Simplified Slice SDD API Contract template into requirements only.
5. Simplified request ID rules by removing client-provided request ID behavior.

Kept intentionally:

1. Workspace header rules remain detailed because Workspace-aware from day 1 is a locked P0 stability requirement.
2. FastAPI/Pydantic OpenAPI source-of-truth and stale checks remain strict because they are core AI Coding guardrails.
3. Runner callback uses `eventId` as the idempotency key; `seq` remains diagnostic-only for observability and troubleshooting.
4. Review checklist remains detailed because it is used by AI and reviewers.

### 23.3 Accepted from Review 3

Accepted as a hard rule:

1. API `message` is always English.
2. API examples must use English only.
3. i18n is by `code`, not by parsing `message`.
4. Chinese user-facing API sample text is forbidden in this document and in generated examples.

---

## 24. Final AI Reading Summary

AI Coding Before implementing any API-related tasks, you must remember:

1. Business API path is `/api/v1/...`.
2. OpenAPI uses `servers.url=/api` and paths `/v1/...`.
3. Internal runner API path is `/api/internal/v1/runner/...` and must not enter Web client.
4. Workspace comes from `x-workspace-id`, not route path.
5. P0 missing Workspace header resolves to user default Workspace and response writes back actual `x-workspace-id`; `WORKSPACE_REQUIRED` is used only when no default Workspace can be resolved or the header is malformed.
6. API JSON uses `camelCase`.
7. DB uses `snake_case`.
8. External business IDs are ULID strings.
9. Time is ISO 8601 UTC.
10. Enum values are lower snake case.
11. Single resource response is direct object.
12. List response uses `items` envelope.
13. Run / Artifact / Audit lists use cursor pagination.
14. Error response is `{code, message, requestId, details?}`.
15. API `message` is always English.
16. Frontend i18n is by `code`.
17. No Chinese text in API examples.
18. Error codes grow through Slice SDD, not by ad hoc implementation.
19. OpenAPI is generated from FastAPI/Pydantic, not hand-written.
20. Web types and client are generated only.
21. `make generate-contracts` and `make verify` must catch stale contracts.
22. Stop, Run creation, Runner callback, and artifact registration must be idempotent.
23. Web never receives MinIO credentials, presigned URLs, or object keys.
24. Do not implement P1/P2 through hidden API endpoints.
