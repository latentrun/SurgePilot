# P0-01: Env Groups

- Document status: Draft v2 for implementation
- Product: SurgePilot
- Document path: `docs/sdd/slices/P0-01-env-groups.md`
- Current delivery target: P0 only
- Slice owner: API / Web / Contracts
- Depends on: `docs/prd/PRD.md`, `docs/sdd/00-product-scope-and-priority.md`, `docs/sdd/04-api-contract-guidelines.md`, `docs/sdd/06-security-permission-workspace.md`, `docs/sdd/08-frontend-routing-and-ui-rules.md`, `docs/sdd/09-testing-and-acceptance-strategy.md`
- Optional context only if directly needed: `docs/sdd/03-domain-model-overview.md`

---

## 1. Goal

This slice implements Workspace-aware Env Group management for P0.

After this slice is done, an authenticated user can:

1. View Env Groups in the current Workspace.
2. Create an Env Group.
3. Edit an Env Group name, description, and variables.
4. Duplicate an Env Group.
5. Delete an Env Group when it is not in use.
6. See stable placeholder reference state through `inUse`.

An Env Group is a reusable named set of environment variables used by later Scenario, Test Plan, and Run Snapshot slices. P0-01 creates the asset and API/UI contract only; it does not attach Env Groups to Scenario, Test Plan, Run, or Runner execution.

---

## 2. PRD Trace

This slice implements the P0 Env Groups asset requirement.

Product meaning:

| Product concept | Contract in this slice |
| --- | --- |
| Env Group | A Workspace-scoped reusable group of non-secret environment variables. |
| Variable | A string key/value pair intended to become execution environment input in later slices. |
| Reference display | `inUse` is returned by API and displayed by Web. In P0-01 it is always `false`. |
| Delete protection | Delete uses a backend reference-check boundary and returns `ENV_GROUP_IN_USE` when references exist. In P0-01 references do not exist yet. |

This slice establishes the data and API shape needed by later slices. The later slice that first creates real Env Group references must update the reference check and the relevant Slice SDD.

---

## 3. Document Responsibility

This Slice SDD owns the concrete P0-01 contract for:

1. Env Group data model.
2. Env Group API endpoints, request schemas, response schemas, and slice-specific error codes.
3. Env Group frontend route behavior under `/assets/env-groups`.
4. Env Group validation rules.
5. Env Group tests and Done When.

This document must not redefine global rules owned by Foundation SDDs:

| Concern | Source of truth |
| --- | --- |
| P0/P1/P2 scope gate | `00-product-scope-and-priority.md` |
| REST, headers, pagination, OpenAPI, error shape | `04-api-contract-guidelines.md` |
| Auth, CSRF, role, Workspace, sensitive value handling | `06-security-permission-workspace.md` |
| Frontend routing, UI stack, query ownership | `08-frontend-routing-and-ui-rules.md` |
| Verification gates and test layer ownership | `09-testing-and-acceptance-strategy.md` |

---

## 4. In Scope

### 4.1 Backend

Implement these public API endpoints:

| Endpoint | Method | Auth | CSRF | Purpose |
| --- | --- | --- | --- | --- |
| `/api/v1/env-groups` | `GET` | session | no | List Env Groups in the current Workspace. |
| `/api/v1/env-groups` | `POST` | session | yes | Create an Env Group. |
| `/api/v1/env-groups/{envGroupId}` | `GET` | session | no | Get one Env Group including variables. |
| `/api/v1/env-groups/{envGroupId}` | `PATCH` | session | yes | Partially update name, description, or replace variables. |
| `/api/v1/env-groups/{envGroupId}` | `DELETE` | session | yes | Delete an Env Group when not in use. |
| `/api/v1/env-groups/{envGroupId}/duplicate` | `POST` | session | yes | Duplicate an Env Group in the current Workspace. |

Backend support includes:

1. Workspace-aware queries and writes.
2. API-level validation for name, description, and variables.
3. Case-insensitive Env Group name uniqueness within a Workspace.
4. `variables` stored as a JSONB object.
5. Full replacement semantics for `variables` when the `variables` field is present in `PATCH`.
6. `inUse` response field with P0-01 value `false`.
7. Future-ready delete protection boundary returning `ENV_GROUP_IN_USE` when references exist.
8. OpenAPI export and generated Web client updates.

### 4.2 Data

Create one Alembic migration after P0-00:

```text
apps/api/migrations/versions/0002_p0_01_env_groups.py
```

The migration creates:

1. `env_groups` table.
2. Workspace/name uniqueness index.
3. Workspace list query indexes.

### 4.3 Frontend

Implement the P0 route:

| Route | Layout | Purpose |
| --- | --- | --- |
| `/assets/env-groups` | `AppLayout` | List, create, edit, duplicate, and delete Env Groups. |

Frontend support includes:

1. List view.
2. Create form.
3. Edit form with variables table.
4. Duplicate action button.
5. Delete confirmation.
6. `ENV_GROUP_IN_USE` error handling branch.
7. Loading, empty, error, validation, and disabled submitting states.
8. AppLayout global navigation entry and active state for `Assets -> Env Groups`.

### 4.4 Tests

Implement:

1. API unit tests for validators and service rules.
2. API integration tests for all Env Group endpoints.
3. Contract tests for OpenAPI operation IDs, schemas, headers, and error responses.
4. Web component/page tests for list, create, edit, duplicate, delete, and error states.
5. One lightweight Playwright smoke test covering create, edit variables, duplicate, and delete.

---

## 5. Out of Scope

This slice must not implement:

1. Secret Env Group variables.
2. Variable masking, reveal buttons, copy restrictions, encryption, key rotation, or secret snapshots.
3. Scenario, Test Plan, Run, Runner, Taurus, or execution bundle integration.
4. Run Snapshot capture of Env Group values.
5. Real reference counting from Scenario, Test Plan, or Run.
6. Env Group selector in Scenario or Test Plan UI.
7. Import or export of `.env`, JSON, YAML, CSV, or shell files.
8. Tags, archive, restore, history, diff, versioning, or soft-delete API behavior.
9. Bulk create, bulk delete, or bulk variable import.
10. Owner-only or resource-level permission model.
11. Admin-only Env Group management.
12. Audit log UI or audit list API.
13. `PUT /api/v1/env-groups/{envGroupId}`.
14. P1/P2 user-visible navigation or placeholder pages.
15. PostgreSQL trigram extension or trigram index.
16. New runtime environment variables.

P0-01 may create extension-safe fields and service boundaries only when they are required by this slice contract. It must not expose usable P1/P2 behavior.

---

## 6. Key Decisions

| Area | Decision |
| --- | --- |
| Resource name | `env-groups` |
| Frontend route | `/assets/env-groups` |
| Workspace | Required business resource; route path does not contain Workspace ID. |
| Permissions | Any authenticated `admin` or `user` with current Workspace access may CRUD Env Groups. |
| Variables storage | `variables` JSONB object on `env_groups`. |
| Variable key | Must match `^[A-Za-z_][A-Za-z0-9_]{0,63}$`. |
| Variable value | String only; empty string allowed; UTF-8 length must be `<= 4096` bytes. |
| Max variables per group | `200`. |
| Variable update | If `variables` appears in `PATCH`, the whole variables object is replaced. |
| PATCH content type | `Content-Type: application/merge-patch+json` is not required; server behavior must still distinguish missing fields from explicit `null`. |
| `PUT` | Not implemented in P0-01. |
| Name uniqueness | Case-insensitive unique within one Workspace. |
| List variables | List endpoint does not return variable values. |
| Detail variables | Detail endpoint returns variable values. |
| Variable order | API treats variables as an object; Web displays keys in ascending lexical order. |
| Duplicate | `POST :duplicate` creates a new Env Group with copied variables. |
| Duplicate default name | `Copy of {sourceName}`, then `Copy of {sourceName} (2)`, `(3)`, and so on if needed. |
| Duplicate name truncation | Preserve `Copy of ` and numeric suffix; truncate the source name to the first fitting characters so generated name length is `<= 120`; do not add ellipsis. |
| Delete protection | Backend must check `inUse`; P0-01 always returns `false`. |
| In-use error | `ENV_GROUP_IN_USE` is registered and handled by Web. |
| Secrets | No Secret type in P0-01. |
| Environment variables | This slice introduces no new runtime environment variables. |
| Audit | Ordinary Env Group CRUD does not require P0 audit events. |

---

## 7. Data Model

### 7.1 `env_groups`

Purpose: Workspace-scoped reusable environment variable groups.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `workspace_id` | `char(26)` | yes | FK to `workspaces.id`. |
| `name` | `text` | yes | Display name; unique case-insensitively within Workspace. |
| `description` | `text` | no | Nullable. |
| `variables` | `jsonb` | yes | JSON object of string keys to string values. Default `{}`. |
| `created_by` | `char(26)` | yes | FK to `users.id`. |
| `updated_by` | `char(26)` | yes | FK to `users.id`. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |

Constraints:

1. Primary key on `id`.
2. FK from `workspace_id` to `workspaces.id`.
3. FK from `created_by` to `users.id`.
4. FK from `updated_by` to `users.id`.
5. `jsonb_typeof(variables) = 'object'`.
6. Unique index on `(workspace_id, lower(name))`.
7. Index on `(workspace_id, created_at desc, id desc)`.
8. Index on `(workspace_id, updated_at desc, id desc)`.
9. Do not add a PostgreSQL trigram extension or trigram index for P0-01 search.

Rules:

1. `id`, `workspace_id`, `created_by`, and `updated_by` are ULID strings.
2. API creates `id`; callers cannot supply it.
3. API writes `workspace_id` from the resolved Workspace context.
4. API writes `created_by` and `updated_by` from the current user.
5. API updates `updated_by` and `updated_at` on successful `PATCH` and duplicate target creation.
6. API must not expose DB `snake_case` field names.
7. P0-01 hard deletes rows when delete succeeds.
8. P0-01 does not add `deleted_at`, `archived_at`, `version`, `tags`, or owner-only permission fields.

### 7.2 Name and Description Rules

| Field | Rule |
| --- | --- |
| `name` | Required, trimmed, length `1..120`. |
| `name` uniqueness | Unique by `lower(name)` within the same Workspace. |
| `description` | Optional, trimmed when present, length `0..500`; empty string may be stored as `null`. |

Rules:

1. API validation is authoritative.
2. Web validation must mirror API validation for user feedback only.
3. Name conflict returns `ENV_GROUP_NAME_CONFLICT`.
4. Name uniqueness is scoped to Workspace; the same name may exist in another Workspace.
5. Name comparisons for uniqueness are case-insensitive.
6. Name display preserves caller-provided case after trimming.

### 7.3 Variables Rules

API shape:

```json
{
  "BASE_URL": "https://example.test",
  "TOKEN": "example-token"
}
```

Rules:

1. `variables` must be a JSON object.
2. Keys must be unique by JSON object semantics.
3. Keys must match `^[A-Za-z_][A-Za-z0-9_]{0,63}$`.
4. Values must be strings.
5. Empty string values are allowed.
6. `null`, boolean, number, object, and array values are rejected.
7. Each value must be `<= 4096` bytes when encoded as UTF-8.
8. Each group may contain at most `200` variables.
9. Key validation does not trim keys; invalid keys are rejected.
10. Value validation does not trim values.
11. API error details must identify the relevant field path such as `variables.BASE_URL` or `variables[bad-key]`.
12. Variables are non-secret in P0-01.

---

## 8. API Contract

All public business endpoints are under `/api/v1` at runtime and `/v1` in the exported OpenAPI paths.

All response JSON fields use `camelCase`.

All authenticated business responses must include:

1. `x-request-id`.
2. `x-workspace-id` for the resolved Workspace.
3. `Cache-Control: no-store`.

### 8.1 Shared Schemas

#### `EnvGroupSummary`

Used by list endpoint.

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "name": "Staging",
  "description": "Staging environment variables.",
  "variableCount": 2,
  "inUse": false,
  "createdBy": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
  "updatedBy": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
  "createdAt": "2030-05-18T03:14:15.123Z",
  "updatedAt": "2030-05-18T03:14:15.123Z"
}
```

Rules:

1. `variables` must not appear in `EnvGroupSummary`.
2. `variableCount` is the number of keys in `variables`.
3. `inUse` is always `false` in P0-01.

#### `EnvGroupDetail`

Used by get, create, patch, and duplicate responses.

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "name": "Staging",
  "description": "Staging environment variables.",
  "variables": {
    "BASE_URL": "https://example.test",
    "TOKEN": "example-token"
  },
  "variableCount": 2,
  "inUse": false,
  "createdBy": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
  "updatedBy": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
  "createdAt": "2030-05-18T03:14:15.123Z",
  "updatedAt": "2030-05-18T03:14:15.123Z"
}
```

Rules:

1. `variables` appears only in detail responses.
2. Variable values in examples must be fake and non-secret.

#### `EnvGroupListResponse`

```json
{
  "items": [],
  "page": 1,
  "pageSize": 20,
  "total": 0
}
```

Rules:

1. List response uses offset pagination.
2. `items` is always an array.
3. `total` is required in P0-01.
4. P0-01 data volume is expected to be small enough for offset pagination and `total`; if future data volume grows, the owning slice must reassess pagination under `04-api-contract-guidelines.md`.

### 8.2 `GET /api/v1/env-groups`

Purpose: list Env Groups in the current Workspace.

Authentication: required session.

CSRF: not required.

Query parameters:

| Parameter | Required | Default | Rule |
| --- | --- | --- | --- |
| `page` | no | `1` | Integer, `>= 1`. |
| `pageSize` | no | `20` | Integer, `1..100`. |
| `q` | no | none | Optional search over name only. Trimmed. Max 120 chars. |
| `sort` | no | `-createdAt` | Allowed: `name`, `createdAt`, `-createdAt`. |

Rules:

1. `sort=-name` is not supported in P0-01.
2. Unknown query parameters return `INVALID_QUERY_PARAMETER`.
3. Unknown sort fields return `INVALID_QUERY_PARAMETER`.
4. Search is case-insensitive over `name` only.
5. Response items must not include `variables`.
6. Query must filter by resolved Workspace.

Response `200 OK`:

```json
{
  "items": [
    {
      "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
      "name": "Staging",
      "description": "Staging environment variables.",
      "variableCount": 2,
      "inUse": false,
      "createdBy": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
      "updatedBy": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
      "createdAt": "2030-05-18T03:14:15.123Z",
      "updatedAt": "2030-05-18T03:14:15.123Z"
    }
  ],
  "page": 1,
  "pageSize": 20,
  "total": 1
}
```

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Missing or invalid session. |
| `WORKSPACE_REQUIRED` | 400 | Workspace cannot be resolved. |
| `WORKSPACE_ACCESS_DENIED` | 403 | User cannot access requested Workspace. |
| `INVALID_QUERY_PARAMETER` | 400 | Invalid `page`, `pageSize`, `q`, `sort`, or unknown query parameter. |

### 8.3 `POST /api/v1/env-groups`

Purpose: create an Env Group in the current Workspace.

Authentication: required session.

CSRF: required.

Request:

```json
{
  "name": "Staging",
  "description": "Staging environment variables.",
  "variables": {
    "BASE_URL": "https://example.test",
    "TOKEN": "example-token"
  }
}
```

Validation:

| Field | Rule |
| --- | --- |
| `name` | Required, trimmed, length `1..120`, unique case-insensitively in Workspace. |
| `description` | Optional, trimmed, max 500 chars. |
| `variables` | Optional; defaults to `{}`. Must satisfy variables rules. |

Response `201 Created`: `EnvGroupDetail`.

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Missing or invalid session. |
| `CSRF_TOKEN_REQUIRED` | 403 | Missing CSRF token. |
| `CSRF_TOKEN_INVALID` | 403 | Invalid CSRF token. |
| `WORKSPACE_REQUIRED` | 400 | Workspace cannot be resolved. |
| `WORKSPACE_ACCESS_DENIED` | 403 | User cannot access requested Workspace. |
| `VALIDATION_ERROR` | 422 | Invalid field shape or variable rules. |
| `ENV_GROUP_NAME_CONFLICT` | 409 | Name already exists in the current Workspace ignoring case. |

### 8.4 `GET /api/v1/env-groups/{envGroupId}`

Purpose: get one Env Group including variables.

Authentication: required session.

CSRF: not required.

Path parameters:

| Parameter | Rule |
| --- | --- |
| `envGroupId` | ULID string. |

Response `200 OK`: `EnvGroupDetail`.

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Missing or invalid session. |
| `WORKSPACE_REQUIRED` | 400 | Workspace cannot be resolved. |
| `WORKSPACE_ACCESS_DENIED` | 403 | User cannot access requested Workspace. |
| `RESOURCE_NOT_FOUND` | 404 | Env Group does not exist or is outside the current Workspace. |
| `VALIDATION_ERROR` | 422 | Invalid `envGroupId` format. |

### 8.5 `PATCH /api/v1/env-groups/{envGroupId}`

Purpose: update name, description, or replace variables.

Authentication: required session.

CSRF: required.

Content-Type:

1. `application/json` is allowed.
2. `application/merge-patch+json` is allowed but not required.
3. Server semantics must follow RFC 7396-style field presence handling for this resource: missing means unchanged; explicit `null` means clear only when nullable.

Request example:

```json
{
  "name": "Staging Updated",
  "description": null,
  "variables": {
    "BASE_URL": "https://staging.example.test"
  }
}
```

PATCH semantics:

| Input | Meaning |
| --- | --- |
| Missing `name` | Preserve existing name. |
| `name: null` | Reject with `VALIDATION_ERROR`. |
| Missing `description` | Preserve existing description. |
| `description: null` | Clear description. |
| Missing `variables` | Preserve existing variables. |
| `variables: null` | Reject with `VALIDATION_ERROR`. |
| `variables: {}` | Replace variables with empty object. |
| `variables: {...}` | Replace the whole variables object. |

Rules:

1. Variables are never merged key-by-key.
2. Server implementation must use `exclude_unset=True` or equivalent field-presence tracking.
3. Server must not use truthy/falsy checks to decide patch behavior.
4. Successful response returns `EnvGroupDetail`.

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Missing or invalid session. |
| `CSRF_TOKEN_REQUIRED` | 403 | Missing CSRF token. |
| `CSRF_TOKEN_INVALID` | 403 | Invalid CSRF token. |
| `WORKSPACE_REQUIRED` | 400 | Workspace cannot be resolved. |
| `WORKSPACE_ACCESS_DENIED` | 403 | User cannot access requested Workspace. |
| `RESOURCE_NOT_FOUND` | 404 | Env Group does not exist or is outside the current Workspace. |
| `VALIDATION_ERROR` | 422 | Invalid field value, invalid variable rules, or explicit `null` for non-nullable field. |
| `ENV_GROUP_NAME_CONFLICT` | 409 | New name already exists in the current Workspace ignoring case. |

### 8.6 `DELETE /api/v1/env-groups/{envGroupId}`

Purpose: delete an Env Group when it is not in use.

Authentication: required session.

CSRF: required.

Response `204 No Content` on success.

Rules:

1. Delete checks Workspace before checking references.
2. Cross-Workspace access returns `RESOURCE_NOT_FOUND`.
3. Delete uses a reference-check service boundary even though P0-01 always reports not in use.
4. When reference-check reports in use, return `ENV_GROUP_IN_USE`.
5. Successful delete hard deletes the row.
6. Delete is not a soft-delete API.

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Missing or invalid session. |
| `CSRF_TOKEN_REQUIRED` | 403 | Missing CSRF token. |
| `CSRF_TOKEN_INVALID` | 403 | Invalid CSRF token. |
| `WORKSPACE_REQUIRED` | 400 | Workspace cannot be resolved. |
| `WORKSPACE_ACCESS_DENIED` | 403 | User cannot access requested Workspace. |
| `RESOURCE_NOT_FOUND` | 404 | Env Group does not exist or is outside the current Workspace. |
| `ENV_GROUP_IN_USE` | 409 | Env Group is referenced and cannot be deleted. |
| `VALIDATION_ERROR` | 422 | Invalid `envGroupId` format. |

### 8.7 `POST /api/v1/env-groups/{envGroupId}/duplicate`

Purpose: duplicate an Env Group in the current Workspace.

Authentication: required session.

CSRF: required.

Request body: empty in P0-01.

Response `201 Created`: `EnvGroupDetail` for the new Env Group.

Rules:

1. Source Env Group must be in the current Workspace.
2. Duplicate copies `description` and `variables`.
3. Duplicate generates a new `id`.
4. Duplicate sets `created_by` and `updated_by` to the current user.
5. Duplicate sets new timestamps.
6. Duplicate does not copy future reference state.
7. Duplicate generated name uses the rules in Section 6.
8. Duplicate generated name must satisfy the same uniqueness and length constraints as user-supplied names.

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Missing or invalid session. |
| `CSRF_TOKEN_REQUIRED` | 403 | Missing CSRF token. |
| `CSRF_TOKEN_INVALID` | 403 | Invalid CSRF token. |
| `WORKSPACE_REQUIRED` | 400 | Workspace cannot be resolved. |
| `WORKSPACE_ACCESS_DENIED` | 403 | User cannot access requested Workspace. |
| `RESOURCE_NOT_FOUND` | 404 | Env Group does not exist or is outside the current Workspace. |
| `VALIDATION_ERROR` | 422 | Invalid `envGroupId` format. |

### 8.8 Error Code Registry Additions

This slice registers these slice-specific error codes:

| Code | HTTP | Message example | Trigger | UX branch |
| --- | --- | --- | --- | --- |
| `ENV_GROUP_NAME_CONFLICT` | 409 | `Env Group name already exists.` | Name already exists in current Workspace ignoring case. | Highlight name field. |
| `ENV_GROUP_IN_USE` | 409 | `Env Group is in use and cannot be deleted.` | Delete protection boundary reports references. | Explain that referenced Env Groups cannot be deleted. |

This slice reuses these existing error codes:

| Code | Use |
| --- | --- |
| `UNAUTHENTICATED` | Missing or invalid session. |
| `FORBIDDEN` | Reserved for generic forbidden actions if needed. |
| `WORKSPACE_REQUIRED` | Workspace context cannot be resolved. |
| `WORKSPACE_ACCESS_DENIED` | User cannot access requested Workspace. |
| `RESOURCE_NOT_FOUND` | Resource missing or hidden by Workspace boundary. |
| `VALIDATION_ERROR` | Field-level validation failure. |
| `INVALID_QUERY_PARAMETER` | Invalid list query parameter. |
| `CSRF_TOKEN_REQUIRED` | Missing CSRF token for write request. |
| `CSRF_TOKEN_INVALID` | Invalid CSRF token for write request. |

Do not add separate public codes for individual variable validation failures. Use `VALIDATION_ERROR` with field-level details.

---

## 9. Frontend Contract

### 9.1 Route and Navigation

Route:

```text
/assets/env-groups
```

Rules:

1. Route is protected by authenticated AppLayout.
2. AppLayout global navigation shows and highlights `Assets -> Env Groups` for this route.
3. Other P1/P2 navigation entries remain hidden.
4. No detail route is introduced in P0-01.
5. No `/assets/env-groups/:envGroupId` route is introduced.
6. Unknown or future actions remain inaccessible.
7. Business data is fetched with TanStack Query, not React Router loader data.

### 9.2 Page Behavior

The page contains:

1. Header with title `Env Groups`.
2. Create button.
3. Search input for `q`.
4. Table with name, description, variable count, reference state, updated time, and actions.
5. Create/edit drawer or modal.
6. Delete confirmation dialog.

Table actions:

| Action | Rule |
| --- | --- |
| Edit | Opens detail form and loads variables from detail endpoint. |
| Duplicate | Calls duplicate endpoint and refreshes list. |
| Delete | Opens confirmation; calls delete endpoint only after confirmation. |

Rules:

1. List page uses summary endpoint and must not depend on variables being present.
2. Edit form loads detail endpoint before showing variable values.
3. Duplicate does not require a naming dialog in P0-01.
4. Delete confirmation must include the Env Group name.
5. Submit buttons are disabled while mutation is pending.
6. Repeated clicks must not submit duplicate mutations.
7. UI copy is English only.

### 9.3 Create/Edit Form

Fields:

1. Name.
2. Description.
3. Variables table.

Variables table columns:

| Column | Rule |
| --- | --- |
| Key | Text input, validates regex. |
| Value | Text input or textarea, string only. |
| Actions | Remove row. |

Rules:

1. Form validation mirrors API rules.
2. Variable keys are displayed in ascending lexical order after loading detail.
3. Empty variables are allowed.
4. Empty string values are allowed.
5. Key duplicates are blocked before submit.
6. Form submission sends `variables` as an object.
7. Edit submission sends the whole variables object, not a per-key delta.
8. Field-level API errors are mapped back to matching fields when possible.

### 9.4 UI States

Required states:

1. Loading list.
2. Empty list.
3. List API error with retry.
4. Loading detail for edit.
5. Detail not found.
6. Create pending.
7. Patch pending.
8. Duplicate pending.
9. Delete pending.
10. Validation error.
11. Name conflict.
12. Env Group in use.

Required error branches:

| Code | Frontend behavior |
| --- | --- |
| `ENV_GROUP_NAME_CONFLICT` | Highlight name and show conflict message. |
| `ENV_GROUP_IN_USE` | Keep row, close or keep delete dialog with clear explanation. |
| `VALIDATION_ERROR` | Show field-level messages. |
| `UNAUTHENTICATED` | Follow global auth recovery. |
| `WORKSPACE_ACCESS_DENIED` | Show access denied state. |
| `RESOURCE_NOT_FOUND` | Show not found and refresh list when relevant. |

---

## 10. Security, Permission, and Workspace Rules

### 10.1 Authentication and CSRF

1. All endpoints require an active session.
2. `GET` endpoints do not require CSRF.
3. `POST`, `PATCH`, and `DELETE` endpoints require `x-csrf-token`.
4. CSRF failures use `CSRF_TOKEN_REQUIRED` or `CSRF_TOKEN_INVALID`.
5. No endpoint returns session token, CSRF token, cookie value, or password hash.

### 10.2 Authorization

| Action | User | Admin | Rule |
| --- | --- | --- | --- |
| List Env Groups | Yes | Yes | Current Workspace only. |
| Create Env Group | Yes | Yes | Current Workspace only. |
| Get Env Group | Yes | Yes | Current Workspace only. |
| Patch Env Group | Yes | Yes | Current Workspace only. |
| Delete Env Group | Yes | Yes | Current Workspace only and not in use. |
| Duplicate Env Group | Yes | Yes | Current Workspace only. |

Rules:

1. Backend authorization is mandatory.
2. Frontend route visibility is not a permission boundary.
3. No owner-only permission is implemented in P0-01.
4. No Admin-only Env Group action is implemented in P0-01.
5. Cross-Workspace resource lookup returns `RESOURCE_NOT_FOUND`.

### 10.3 Workspace Handling

1. All Env Group rows carry `workspace_id`.
2. API route paths do not include Workspace ID.
3. Web sends `x-workspace-id` after it has current Workspace state.
4. Missing `x-workspace-id` falls back to the user's default Workspace in P0.
5. API response includes the resolved `x-workspace-id` header.
6. Queries must filter by resolved Workspace.
7. Create must write resolved Workspace.
8. Patch, delete, get, and duplicate must check resolved Workspace.
9. Cross-Workspace access must not leak resource existence.

### 10.4 Sensitive Value Handling

P0-01 Env Group variables are not Secret variables.

Rules:

1. Do not introduce `type=secret`, `isSecret`, `masked`, `encryptedValue`, `secretRef`, or similar fields.
2. Do not encrypt variables as a P0-01 feature.
3. Do not implement reveal/copy restrictions.
4. Do not place long-lived secrets in examples.
5. API logs must not include variable values.
6. Web logs must not include variable values.
7. Error details must not echo variable values.
8. Test snapshots must not include realistic tokens, passwords, or credentials.
9. OpenAPI examples must use fake values only.
10. P2 Secret Env Group design must be introduced by a future Slice SDD or ADR before implementation.

---

## 11. Runner, Storage, and External Dependency

This slice has no Runner, MinIO, Load Node, SSH, Taurus, or artifact dependency.

Rules:

1. Runner must not import or consume Env Group code in P0-01.
2. P0-01 does not generate Taurus YAML.
3. P0-01 does not create execution bundle manifests.
4. P0-01 does not upload to MinIO.
5. P0-01 does not create Dependency File references.
6. P0-01 does not alter Run state machine, node lease, callback, heartbeat, Stop, or artifact behavior.

Future integration ownership:

| Future concern | Owning slice |
| --- | --- |
| Env Group selected by Test Plan | `P0-06-test-plan-run-now.md` |
| Env Group captured in Run Snapshot | `P0-06-test-plan-run-now.md` |
| Env Group values passed to Runner execution bundle | `P0-04` / `P0-06` contract boundary, as defined by those slices |
| Env Group shown as referenced or in use | First slice that creates real references |

---

## 12. Tests

### 12.1 API Unit Tests

Required coverage:

1. Name validation.
2. Description validation.
3. Variable key regex validation.
4. Variable value type validation.
5. Variable value byte-length validation.
6. Maximum 200 variables validation.
7. `variables` full replacement semantics.
8. Case-insensitive name uniqueness behavior.
9. Duplicate automatic naming behavior and truncation.
10. Reference-check boundary returns not in use in P0-01.

### 12.2 API Integration Tests

Required endpoint coverage:

1. List Env Groups returns only current Workspace rows.
2. List returns summaries without `variables`.
3. List supports `page`, `pageSize`, `q`, and supported `sort` values.
4. List rejects `sort=-name`.
5. Create succeeds with valid variables.
6. Create rejects duplicate name in same Workspace ignoring case.
7. Create allows same name in a different Workspace if the test fixture contains multiple Workspaces.
8. Get returns detail with variables.
9. Get hides cross-Workspace resource with `RESOURCE_NOT_FOUND`.
10. Patch updates name and description.
11. Patch with `variables` replaces the whole object.
12. Patch with missing `variables` preserves existing variables.
13. Patch with `variables: {}` clears variables.
14. Patch rejects `variables: null`.
15. Patch distinguishes missing fields from explicit `null` under both supported content types.
16. Delete succeeds when not in use.
17. Delete returns `ENV_GROUP_IN_USE` when the reference-check boundary reports in use.
18. Duplicate copies description and variables.
19. Duplicate creates unique automatic name.
20. Duplicate truncates generated names deterministically when needed.
21. All write endpoints require CSRF.
22. All endpoints require session.
23. All endpoints enforce Workspace access.

### 12.3 Contract Tests

Required coverage:

1. OpenAPI paths exist under `/v1/env-groups`.
2. Operation IDs are exactly:
   - `listEnvGroups`
   - `createEnvGroup`
   - `getEnvGroup`
   - `patchEnvGroup`
   - `deleteEnvGroup`
   - `duplicateEnvGroup`
3. List response is an offset envelope.
4. List item schema does not include `variables`.
5. Detail schema includes `variables`.
6. Write endpoints document CSRF header requirement.
7. Workspace-aware endpoints document `x-workspace-id` behavior.
8. Error responses use the shared error shape.
9. Slice-specific error codes are documented.
10. Generated Web client/types are fresh.

### 12.4 Web Tests

Required coverage:

1. Empty list state.
2. Loading state.
3. API error state with retry.
4. Create form validation.
5. Edit form loads variables and submits full replacement object.
6. Variable table add/remove row behavior.
7. Duplicate action calls generated client mutation and refreshes list.
8. Delete confirmation behavior.
9. AppLayout highlights `Assets -> Env Groups`.
10. P1/P2 navigation entries remain hidden.
11. `ENV_GROUP_NAME_CONFLICT` UI branch.
12. `ENV_GROUP_IN_USE` UI branch.
13. Submit buttons disabled while pending.
14. Web uses generated client/types from `@surgepilot/contracts`.

### 12.5 E2E Smoke

Add one lightweight Playwright smoke under `tests/e2e/`:

```text
authenticated user
  -> opens /assets/env-groups
  -> creates Env Group
  -> edits variables
  -> duplicates Env Group
  -> deletes duplicate
  -> sees original Env Group remains
```

Rules:

1. The smoke must not require real Runner, SSH, MinIO, Taurus, or external network.
2. The smoke may use the existing P0 auth setup path from P0-00.
3. The smoke must use product routes and public APIs.
4. The smoke is wired to `make verify-e2e`; it does not enter the default `make verify` gate.

### 12.6 Verification Commands

Required repository-level commands:

```bash
make generate-contracts
make verify
make verify-e2e
```

Rules:

1. `make generate-contracts` must update OpenAPI and generated Web client/types.
2. `make verify` must fail if generated contracts are stale.
3. If full `make verify` is not yet available in the current repository state, run the closest available subset and state the gap in the implementation final response.
4. `make verify-e2e` must include the P0-01 Playwright smoke when E2E profile is executed.

---

## 13. Done When

P0-01 is done only when all of the following are true:

1. `env_groups` migration exists and applies cleanly after P0-00.
2. Env Group table has Workspace ownership, audit attribution fields, JSONB variables, uniqueness index, and list query indexes.
3. API implements all six endpoints in this Slice SDD.
4. API enforces session, CSRF for writes, Workspace access, and current Workspace filtering.
5. API validates name, description, variable keys, variable values, and variable count.
6. API list response excludes `variables`.
7. API detail responses include `variables`.
8. API `PATCH` replaces the whole variables object when `variables` is present.
9. API implements `duplicate` with automatic name generation and deterministic truncation.
10. API implements delete protection boundary and can return `ENV_GROUP_IN_USE`.
11. P0-01 `inUse` is always `false` unless a later committed slice introduces real references and updates this document.
12. P0-00 has provided a usable `AppLayout` shell; if only placeholder Overview exists, this slice or prerequisite backfill must add the minimal AppLayout shell before Env Groups is considered done.
13. Web implements `/assets/env-groups` with list, create, edit, duplicate, and delete.
14. Web AppLayout navigation shows and highlights `Assets -> Env Groups`.
15. Web handles `ENV_GROUP_NAME_CONFLICT` and `ENV_GROUP_IN_USE`.
16. Web uses generated client/types through `@surgepilot/contracts`.
17. OpenAPI artifact and generated Web client/types are updated.
18. API, contract, Web, and E2E smoke tests required by this document exist.
19. P0-01 Playwright smoke is wired to `make verify-e2e`, not the default `make verify` gate.
20. `make generate-contracts` passes.
21. `make verify` or the current documented closest subset passes.
22. No P1/P2 user-visible capability is introduced.
23. No Secret Env Group behavior is introduced.
24. No Runner, MinIO, Load Node, Run, Scenario, or Test Plan behavior is implemented by this slice.

---

## 14. Handoff to Later Slices

Later slices must treat P0-01 as the source of truth for Env Group resource shape until they explicitly update it.

Required future updates:

1. The first slice that references Env Groups must update the `inUse` computation.
2. The first slice that references Env Groups must define whether delete is blocked by draft Test Plans, historical Run Snapshots, or both.
3. The Run Snapshot slice must define how Env Group variables are captured at Run creation time.
4. The Runner execution bundle slice must define how captured variables are passed to Runner without exposing platform secrets.
5. Any Secret Env Group design must be introduced by a future P2 Slice SDD or ADR and must not reinterpret P0-01 variables as secrets.
