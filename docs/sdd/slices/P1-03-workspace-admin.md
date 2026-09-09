# P1-03 Workspace / Admin

- Document status: Accepted for implementation
- Stage: P1
- Capability:`workspace_admin`
- Scope Gate:`docs/sdd/00-product-scope-and-priority.md` §6
- P1 Index:`docs/sdd/slices/P1-README.md`
- API Contract Boundary:`docs/sdd/04-api-contract-guidelines.md`
- Security Boundary:`docs/sdd/06-security-permission-workspace.md`
- Frontend Route Boundary:`docs/sdd/08-frontend-routing-and-ui-rules.md`
- Testing Boundary:`docs/sdd/09-testing-and-acceptance-strategy.md`

## 1. Goal

P1-03 adds P1 Workspace/Admin capabilities to SurgePilot: Workspace switching, creation, renaming, archiving, User Management, and a small amount of non-sensitive System Settings/Setup Status completion.

Goal:

1. After login, refresh, and workspace switch, the web rebuilds the session context from the current user, current workspace, list of accessible workspaces, membership summary, and permissions summary returned by the backend.
2. Web has the most persistent `currentWorkspaceId` local preference; the backend determines in real time whether the Workspace exists, is accessible, is not archived, and whether the resource belongs to the current Workspace.
3. When users switch Workspaces on the resource editing page with unsaved changes, they must first confirm to abandon the changes; after confirmation, clear the partial editing status, temporary preview and draft, and land on the safelist page or Overview of the target Workspace.
4. All business requests continue to use `x-workspace-id`; if the URL, form or asynchronous request still carries the resource ID of other Workspaces, the backend returns `404 RESOURCE_NOT_FOUND` based on resource ownership or `403 WORKSPACE_ACCESS_DENIED` based on permissions.
5. Admin can manage users, Workspaces and non-sensitive settings in the whitelist; ordinary `user` cannot call Admin API.
6. Disabled users cannot log in, and existing sessions must be invalid; the system must protect the last active Admin to avoid governance lock-up.
7. Settings, Setup Status, OpenAPI, logs, errors and web shall not expose `secret` , `token` , `key` , passwords, credentials or ciphertext materials in plain text.

P1-03 is a governance and experience enhancement and must not become a pre-dependency of the main link of P0 Scenario -> Test Plan -> Run -> Run Report.

## 2. PRD / Scope Trace

`docs/sdd/00-product-scope-and-priority.md` §6 Locked P1 Workspace to Workspace switch, create, edit, archive, etc. UI, locked P1 User Management to user list, disable/enable, role modification, create user, reset password, locked P1 System Settings to partially non-sensitive configuration UI.

This Slice locks in the following conclusions:

1. P1-03 only enables P1's listed Workspace/Admin capabilities and does not introduce Owner, resource-level RBAC, complex permission matrix, SSO or permission platform.
2. P0's Workspace-aware data, security boundary, credential echo prevention, path security, and default Workspace main link must not be rolled back.
3. The Workspace list, membership and permission summary of the Web are only UX inputs; the final authorization and resource ownership judgment must be performed on the API backend.
4. `x-workspace-id` is still the business Workspace context delivery method; the Workspace ID does not enter the business route path.
5. FastAPI/Pydantic is still OpenAPI source of truth; Web can only consume generated client/types.
6. It is still in the development stage. This article defines data, API, status and interaction in the target state without setting up historical clients or old data compatibility layers.

Governance prerequisites:

1. This file is authorized to implement P1 Workspace/Admin only after it exists as active P1 Slice SDD.
2. `P1-README.md` is only used as an index; the implementation must not be started directly from the placeholder copy.
3. If the implementation requires Workspace Owner, workspace-scoped roles, resource-level permissions, SSO, invitation emails, OIDC, LDAP, Redis, external queues or permission platforms, you must first add ADR or update PRD/Scope Gate.

## 3. In Scope

1. Workspace management:
   - list available workspaces;
   - resolve current workspace;
   - switch workspace by backend validation;
   - create workspace;
   - rename workspace;
   - archive workspace.
2. Session/current-user context:
   - `/auth/me` or equivalent interface returns the current user, global role, `currentWorkspace`, `availableWorkspaces`, membership summary and permission summary;
   - After login, register, refresh, and switch, the Web session state is reconstructed from the backend response.
3. Frontend workspace UX:
   - header workspace switcher;
   - local `currentWorkspaceId` preference;
   - dirty guard;
   - switch confirmation;
   - target workspace safe landing;
   - stale resource cleanup.
4. User Management:
   - user list/search/filter;
   - create local user;
   - enable/disable user;
   - change global role `admin` / `user`;
   - reset password;
   - maintain workspace memberships as access relations only, without workspace-scoped role semantics.
5. Admin Setup Status and non-sensitive System Settings:
   - expand Admin-only setup status with non-secret configured/missing booleans;
   - keep public setup status minimal and safe for unauthenticated bootstrap checks;
   - expose only explicitly whitelisted non-sensitive settings for update;
   - never edit or echo secrets/tokens/keys.
6. Backend protections:
   - workspace access resolution;
   - archived workspace rejection;
   - cross-workspace resource 404/403 behavior;
   - disabled user session invalidation;
   - last active Admin protection.
7. Tests / verification gates:
   - API, Web, contract and E2E smoke coverage for workspace switching, dirty guard, user management, disabled users, last Admin protection, setup/settings secrecy and P0 regression paths.

## 4. Out of Scope

1. Workspace Owner role.
2. Workspace-scoped roles such as `owner`, `manager`, `viewer`.
3. Resource-level RBAC, creator-only permissions, sharing model or approval workflow.
4. Complex permission matrix or custom authorization platform.
5. OAuth, OIDC, SAML, LDAP, SSO, SCIM, external IdP provisioning or group/claim mapping.
6. Email invitation, email verification, forgot-password mail flow or outbound email service.
7. Self-service user profile editing beyond existing auth context.
8. Secret/token/key plaintext editing, display, copy, export or API echo.
9. Env Group Secret, Secret Snapshot encryption, key rotation or general-purpose secret governance.
10. Redis, Celery, Kafka, RabbitMQ, external queues or distributed cache for admin workflows.
11. Cross-workspace automatic migration of unsaved drafts, resource IDs, editor state or temporary previews.
12. Making archived workspaces readable as historical archives in normal business UI.
13. P1 Monitoring, P1 Resource Multi-node, Scenario/TestPlan Polish, cURL Import, Dependency Preview, Run Report Preview or Debug HTTP Trace behavior changes.
14. P2 Schedule, Help, API Catalog, ZIP/TAR/TGZ extraction, OIDC/SSO or enterprise security extensions.

## 5. Preconditions

Before implementing P1-03, the following must be met:

1. P0 auth/session/CSRF/default Workspace baseline has been stabilized.
2. Business APIs are marked as Workspace-aware Query, Create, Update, Delete, Download, Stop and Validity by `x-workspace-id`.
3. The backend has global role `admin` / `user` checked, and ordinary users cannot call the Admin API.
4. Current Web API client uses generated OpenAPI client/types and does not hand-write API shape.
5. P1 governance has been started through `docs/sdd/adr/ADR-0022-p1-governance-start.md`, and this file has been marked as active Slice SDD in `P1-README.md`.
6. P1-03 implementation must include a DB migration before exposing disable/archive writes: `ck_users_status` must allow `active` and `disabled`, `ck_workspaces_status` must allow `active` and `archived`, `users.disabled_at` must be added, and `workspaces.archived_at` must be added.

## 6. Locked Core Decisions

| ID | Decision |
| --- | --- |
| WAD-01 | The API is the sole arbiter of workspace, membership, role, status, and resource ownership. |
| WAD-02 | Web maximum persistence `currentWorkspaceId` local preference; this value has no authorization implications. |
| WAD-03 | `GET /api/v1/auth/me` or equivalent session context endpoint must return `currentWorkspace` and `availableWorkspaces`. |
| WAD-04 | Workspace switch endpoint only validates and returns target session context; does not create server-side current-workspace sticky state. |
| WAD-05 | Business requests continue to send `x-workspace-id`; the business route path does not contain the Workspace ID. |
| WAD-06 | When the Header points to Workspace B and the resource ID belongs to Workspace A, the backend must not automatically repair to A; it must return 404 or 403. |
| WAD-07 | Dirty edit page Switching Workspace must be cancelable; clean up the editing status and navigate after confirmation. |
| WAD-08 | After switching, the safe landing point is priority to the resource list page corresponding to the target Workspace; when it cannot be classified, it falls to `/overview`. |
| WAD-09 | Workspace archive is a status change, not a physical deletion. |
| WAD-10 | Archived Workspace shall not be used as the current workspace, nor shall it accept new business writes. |
| WAD-11 | The system must retain at least one active workspace; archiving the last active workspace must be rejected. |
| WAD-12 | Global `admin` / `user` continues to be the only role model; workspace membership only expresses access relationships, not roles. |
| WAD-13 | Admin can access all active Workspaces for management; ordinary users can only access active membership workspaces. |
| WAD-14 | User disable must prevent subsequent logins and invalidate the user's existing sessions. |
| WAD-15 | Disabling, downgrading, or removing membership must not leave the system without an active Admin. |
| WAD-16 | Reset password A new password is provided by Admin; the API does not generate or return a temporary password. |
| WAD-17 | Sensitive settings only return configured/missing/fingerprint-safe metadata, not plaintext, ciphertext, nonce, tag or key id. |
| WAD-18 | The Web's permission digest can only control UX affordance; APIs must repeatedly perform permission checks. |
| WAD-19 | This Slice does not introduce new open source runtime dependencies; it continues to use FastAPI/Pydantic, React, TanStack Query, React Hook Form, Zod and generated contracts. |
| WAD-20 | `system_settings.allowSignup` is the runtime source of truth after P1-03 migration; `ALLOW_SIGNUP` seeds or falls back only when the DB row is absent. |

## 7. Architecture

```text
Browser startup / refresh
  -> Web reads optional local currentWorkspaceId preference
  -> Web calls GET /api/v1/auth/me?preferredWorkspaceId=<id>
  -> API authenticates session, checks user status, resolves current workspace
  -> API returns user + currentWorkspace + availableWorkspaces + permissions
  -> Web rebuilds auth/workspace state and configures generated API client calls
  -> business APIs send x-workspace-id=currentWorkspace.id

User selects another workspace
  -> Web checks dirty guards for current route
  -> if dirty: show abandon-and-switch / cancel dialog
  -> on confirm: Web calls switch endpoint
  -> API validates access and active status
  -> Web persists returned workspace id as local preference
  -> Web clears route-local edit state, previews and drafts
  -> Web navigates to safe landing in the target workspace
```

Component boundaries:

| Component | Responsibility | Forbidden |
| --- | --- | --- |
| API | Authenticate session; enforce user status; resolve Workspace; authorize Admin APIs; validate resource Workspace ownership; expose FastAPI/Pydantic OpenAPI contracts. | Trusting Web cached workspace/role/membership; returning secret values; auto-rewriting resource IDs across Workspaces. |
| Web | Render switcher, Admin pages, dirty guard, safe landing, form validation and generated-client calls. | Treating local preference or permissions summary as authoritative; direct DB/MinIO access; hidden handcrafted API calls. |
| Contracts | Export OpenAPI from FastAPI and generate Web client/types. | Hand-writing OpenAPI or generated client files. |
| Database | Store users, sessions, workspaces, memberships, settings and audit events. | Encoding workspace roles or resource-level permissions in P1-03. |

## 8. Data Contracts

### 8.1 `workspaces`

| Column | Type | Required | Contract |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `name` | `text` | yes | Display name, trimmed, 1..120 characters. |
| `status` | `text` | yes | `active` or `archived`. |
| `archived_at` | `timestamptz` | no | Set when status becomes `archived`; null while active. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |

Rules:

1. `status='archived'` Workspaces are excluded from normal business route navigation and current workspace resolution.
2. Archive must fail when it would leave zero active Workspaces.
3. Create workspace must create the workspace as `active` and add the creating Admin to `workspace_members`.
4. Rename must trim and validate name length before persistence.
5. Physical delete is not exposed.
6. Migration must replace the existing single-value `ck_workspaces_status` with a constraint allowing exactly `active` and `archived`, and must add nullable `archived_at`.
7. Active Workspace names must be unique after trimming and case folding. This must be enforced by a database-level uniqueness mechanism, for example a partial unique index on `lower(name)` where `status='active'`, plus API validation that maps conflicts to `409 WORKSPACE_NAME_CONFLICT`.

### 8.2 `workspace_members`

| Column | Type | Required | Contract |
| --- | --- | --- | --- |
| `workspace_id` | `char(26)` | yes | FK to `workspaces.id`. |
| `user_id` | `char(26)` | yes | FK to `users.id`. |
| `joined_at` | `timestamptz` | yes | UTC. |

Rules:

1. Unique key remains `(workspace_id, user_id)`.
2. Membership means access relation only; it does not contain role, owner, permission level or resource scope.
3. For `user` role, available Workspaces are active Workspaces with membership.
4. For `admin` role, available Workspaces include all active Workspaces; membership summary may indicate whether the row exists.
5. User Management may update a user's membership set, but must not introduce workspace-scoped role fields.
6. Removing a user's last accessible active Workspace must be rejected unless the user is disabled.

### 8.3 `users`

| Column | Type | Required | Contract |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `email` | `text` | yes | Globally unique, normalized lowercase. |
| `display_name` | `text` | yes | 1..120 characters. |
| `password_hash` | `text` | yes | Argon2id hash only; never returned. |
| `role` | `text` | yes | `admin` or `user`. |
| `status` | `text` | yes | `active` or `disabled`. |
| `disabled_at` | `timestamptz` | no | Set when status becomes `disabled`; null while active. |
| `failed_login_count` | `integer` | yes | Existing account-level login guard. |
| `locked_until` | `timestamptz` | no | Existing account-level login guard. |
| `last_login_at` | `timestamptz` | no | Updated on successful login. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |

Rules:

1. Disabled users cannot log in.
2. Existing sessions for a disabled user must be revoked or treated as invalid before serving authenticated APIs.
3. Role changes must preserve at least one active Admin.
4. If a role change makes an active user become `user`, API must verify the user has at least one active Workspace membership after the patch; otherwise return `409 USER_WORKSPACE_REQUIRED`.
5. Password reset writes a new Argon2id hash and revokes the target user's sessions.
6. API responses must not return `password_hash`, raw password, generated password, session token, CSRF token or reset token.
7. Migration must replace the existing single-value `ck_users_status` with a constraint allowing exactly `active` and `disabled`, and must add nullable `disabled_at`.

### 8.4 `system_settings`

P1-03 may add a small DB-backed settings table only for explicitly writable non-sensitive settings.

| Column | Type | Required | Contract |
| --- | --- | --- | --- |
| `key` | `text` | yes | Stable setting key primary key. |
| `value_json` | `jsonb` | yes | Non-sensitive value only. |
| `updated_by_user_id` | `char(26)` | no | Admin actor who last changed it. |
| `updated_at` | `timestamptz` | yes | UTC. |

Allowed writable keys:

| Key | Type | Contract | Effective behavior |
| --- | --- | --- | --- |
| `allowSignup` | boolean | Controls whether non-bootstrap self-registration is allowed. | Request-level hot effect; first-admin bootstrap remains independent. |
| `loadNodeApiBaseUrl` | string or null | Non-sensitive http/https origin used by remote Load Nodes to call SurgePilot API; DB value overrides the `SURGEPILOT_NODE_API_BASE_URL` deployment fallback. | Affects future remote Run start only. Missing or invalid configuration blocks Run start fail-closed; registration, initialization, and already-started Runs are unchanged. |
| `loadSoftLimitWarningConcurrency` | integer | UI/API warning threshold for soft concurrency confirmation; must be `>= 1` and `<= SURGEPILOT_SINGLE_NODE_CONCURRENCY_HARD_LIMIT`. | Request-level hot effect for Test Plan guard, summary, preview, and start-run validation. |
| `jmeterMemoryXmx` | string | JMeter heap size matching `^[1-9][0-9]*[KMG]$`, normalized to 512 MiB through 32 GiB. | Stored into future new Run snapshots only; existing snapshots/bundles/running Runs are not changed. |
| `maxScenarioItemsPerTestPlan` | integer | Enabled Scenario item policy limit, `1..100`. | Request-level hot effect for create/clone/update/preview/start-run validation. |
| `maxSlaRulesPerTestPlan` | integer | Enabled SLA rule policy limit, `0..50`. | Request-level hot effect for create/clone/update/preview/start-run validation. |
| `maxRunDurationSeconds` | integer | Test Plan duration limit, `60..604800`. | Request-level hot effect for Test Plan load settings validation. |
| `maxRampUpSeconds` | integer | Ramp-up limit, `0..604800`; must not exceed the duration limit. | Request-level hot effect for Test Plan load settings validation. |
| `maxDelaySeconds` | integer | Delay limit, `0..604800`. | Request-level hot effect for Test Plan load settings validation. |
| `maxIterations` | integer | Iteration limit, `1..10000000`. | Request-level hot effect for Test Plan load settings validation. |
| `maxTargetRps` | integer | Target RPS limit, `1..1000000`. | Request-level hot effect for Test Plan load settings validation. |
| `dependencyFileMaxBytes` | integer | Upload policy, `1048576..1073741824` bytes. | Request-level hot effect for new upload content-length gate and stored file size validation. |
| `dependencyFileAllowedExtensions` | string array | Upload allowlist; normalized lowercase dot-prefixed extensions, max 100 entries; empty list means unrestricted. | Request-level hot effect for new uploads only. |
| `dependencyFilePreviewMaxBytes` | integer | Preview read limit, `1024..5242880` bytes and not greater than `dependencyFileMaxBytes`. | Request-level hot effect for preview requests only. |
| `dependencyFilePreviewBinaryDenyExtensions` | string array | Preview denylist; normalized lowercase dot-prefixed extensions, max 200 entries. | Request-level hot effect for preview requests only. |

Read-only display keys:

| Key | Type | Contract |
| --- | --- | --- |
| `runnerInternalTokenConfigured` | boolean | Existing configured/missing status only. |
| `sshCredentialEncryptionKeyConfigured` | boolean | Existing configured/missing status only. |
| `minioCredentialsConfigured` | boolean | Existing configured/missing status only. |

Rules:

1. Any key not listed in the writable table above is read-only or unsupported in P1-03.
2. `singleNodeConcurrencyHardLimit` is intentionally not writable and must not appear in System Settings UI. Lowering it can make existing Test Plans fail save/preview/run validation and requires separate Slice/ADR governance.
3. Keys containing `secret`, `token`, `password`, `privateKey`, `credential` or `key` must be rejected as writable settings before registry lookup.
4. Deployment secrets remain environment-managed and can appear in Setup Status/System Settings only as boolean configured/missing states.
5. Monitoring tokens, Grafana/Influx admin passwords, database credentials and MinIO secrets must not enter System Settings UI, OpenAPI responses or audit payloads as plaintext.
6. After P1-03 migration, `system_settings.allowSignup` is the runtime source of truth for non-bootstrap signup decisions and setup status reporting.
7. `ALLOW_SIGNUP` remains a deployment seed/fallback only: migration should initialize the DB row from `Settings.allow_signup`, and runtime may read the env value only if the DB row is absent or before migrations have created `system_settings`.
8. Bootstrap remains independent of the signup switch: when no user exists, public setup status may report signup/bootstrap allowed and the bootstrap flow may create the first Admin even if `allowSignup=false`.
9. Admin updates to writable settings must write only `system_settings`; they must not rewrite environment variables or require process restart.
10. `SURGEPILOT_JMETER_MEMORY_XMX` remains an env fallback/seed. Run creation must copy the effective value to the Run snapshot; execution bundle generation must read the snapshot value and may use env fallback only for old snapshots missing the field.
11. Dependency File policy changes affect future upload/preview requests only; existing stored files are not rewritten.
12. Build-time or stack-construction settings such as `VITE_*`, compose ports, volumes, DB/MinIO/Influx/Grafana initialization values and token files are not runtime editable System Settings.
13. `.env.example` and compose examples must stay drift-checked: no duplicate `RUNNER_INTERNAL_TOKEN`, all required `docker-compose.yml` `${VAR}` examples documented, no Web runtime `VITE_API_BASE_URL` environment override, and optional build mirror examples remain outside the required runtime drift set.

## 9. Session Context and Workspace Resolution Contract

### 9.1 Session context request

`GET /api/v1/auth/me` accepts one optional query parameter:

| Query parameter | Type | Required | Contract |
| --- | --- | --- | --- |
| `preferredWorkspaceId` | ULID string | no | Client-side local preference submitted during startup or refresh. This is not authorization and is not the business `x-workspace-id` header. |

Rules:

1. Web sends `preferredWorkspaceId` only from the local `currentWorkspaceId` preference.
2. Web must not send `x-workspace-id` to `/auth/me`; `/auth/me` is session context, not a Workspace-scoped business resource request.
3. Missing, malformed, archived, inaccessible or nonexistent `preferredWorkspaceId` is treated as a preference miss. API must resolve a deterministic accessible active Workspace when one exists and return it as `currentWorkspace`.
4. Preference miss must not return `400`, `403` or `422` by itself. API returns an error only when no accessible active Workspace can be resolved or the session/user is invalid.
5. Web must replace or clear the local preference when the returned `currentWorkspace.id` differs from `preferredWorkspaceId`.

Example:

```http
GET /api/v1/auth/me?preferredWorkspaceId=01J00000000000000000000002
```

### 9.2 Session context response

Conceptual response shape:

```json
{
  "user": {
    "id": "01J00000000000000000000001",
    "email": "admin@example.test",
    "displayName": "Admin",
    "role": "admin",
    "status": "active"
  },
  "currentWorkspace": {
    "id": "01HZW000000000000000000000",
    "name": "Default Workspace",
    "status": "active"
  },
  "availableWorkspaces": [
    {
      "id": "01HZW000000000000000000000",
      "name": "Default Workspace",
      "status": "active",
      "membership": {
        "kind": "member",
        "joinedAt": "2030-06-15T00:00:00Z"
      }
    }
  ],
  "permissions": {
    "canManageWorkspaces": true,
    "canManageUsers": true,
    "canManageSystemSettings": true,
    "canViewSetupStatus": true
  }
}
```

Rules:

1. Response JSON uses `camelCase`.
2. `availableWorkspaces` includes only active Workspaces.
3. `currentWorkspace` must be one of `availableWorkspaces`.
4. Permissions summary is a UX hint and must not be used as the only authorization check.
5. If a stored or requested preferred workspace is archived, missing or inaccessible, API must either return another accessible active workspace or return a stable error when none exists.
6. If the user is disabled, session context must fail with `401 UNAUTHENTICATED` or `403 USER_DISABLED`; it must not return a usable context.

### 9.3 Resolution order

When resolving current workspace for session context:

1. If `preferredWorkspaceId` is present and resolves to an active accessible Workspace, use it.
2. If `preferredWorkspaceId` is missing, malformed, archived, inaccessible or nonexistent, choose the user's first deterministic available active Workspace.
3. If no active Workspace is available, return `400 WORKSPACE_REQUIRED` or `403 WORKSPACE_ACCESS_DENIED` according to the failure reason.

The deterministic fallback ordering must be stable, for example `created_at asc, id asc`. Web must replace local preference with the returned `currentWorkspace.id`.

### 9.4 Business request workspace rules

1. Business APIs require `x-workspace-id` after Web has session context.
2. Header missing may still fall back only where the foundation security/API contracts permit; P1 Web must not rely on missing-header fallback.
3. Header invalid format returns `400 WORKSPACE_REQUIRED`.
4. Header valid but inaccessible returns `403 WORKSPACE_ACCESS_DENIED`.
5. Header valid but archived returns `403 WORKSPACE_ARCHIVED`.
6. Resource ID not found in the resolved Workspace returns `404 RESOURCE_NOT_FOUND`.
7. API must not follow the resource ID to another Workspace or mutate the Web's current Workspace on behalf of the request.

## 10. API Contract

All endpoints follow `/api/v1`, generated OpenAPI, cookie session auth, `x-csrf-token` for browser writes and unified error response rules.

### 10.1 Auth/session endpoints

| Endpoint | Method | Auth | CSRF | Purpose |
| --- | --- | --- | --- | --- |
| `/api/v1/auth/me?preferredWorkspaceId={workspaceId}` | `GET` | session | no | Return session context using an optional local workspace preference. |
| `/api/v1/workspaces/switch` | `POST` | session | yes | Validate a target Workspace and return session context for it. |

`GET /api/v1/auth/me` query contract:

| Query parameter | Required | Contract |
| --- | --- | --- |
| `preferredWorkspaceId` | no | Optional ULID preference. Invalid or unavailable values fall back as defined in §9.1 and §9.3. |

`POST /api/v1/workspaces/switch` request:

```json
{
  "workspaceId": "01J00000000000000000000002"
}
```

Rules:

1. Switch does not write server-side sticky current workspace state.
2. Switch response must be the same session context shape as `/auth/me`.
3. Switch must reject archived or inaccessible workspaces.
4. Switch must not clear or mutate server-side business drafts because P1-03 does not define cross-workspace draft migration.

### 10.2 Workspace endpoints

| Endpoint | Method | Auth | CSRF | Role | Purpose |
| --- | --- | --- | --- | --- | --- |
| `/api/v1/workspaces` | `GET` | session | no | any | List available active Workspaces for the actor. |
| `/api/v1/admin/workspaces` | `GET` | session | no | admin | List all Workspaces, including archived when requested. |
| `/api/v1/admin/workspaces` | `POST` | session | yes | admin | Create active Workspace. |
| `/api/v1/admin/workspaces/{workspaceId}` | `PATCH` | session | yes | admin | Rename Workspace. |
| `/api/v1/admin/workspaces/{workspaceId}/archive` | `POST` | session | yes | admin | Archive Workspace. |

Create request:

```json
{
  "name": "Payments Team"
}
```

Patch request:

```json
{
  "name": "Core Platform"
}
```

Archive response:

```json
{
  "workspace": {
    "id": "01J00000000000000000000002",
    "name": "Payments Team",
    "status": "archived",
    "archivedAt": "2030-06-15T00:00:00Z"
  }
}
```

Rules:

1. Admin list may include `status=active|archived|all` filter.
2. Normal workspace list excludes archived workspaces.
3. Create and rename must validate normalized name uniqueness among active workspaces, case-insensitive.
4. Archive must reject the current last active Workspace.
5. Archive must not delete business rows, artifacts or audit events.
6. Create and rename must rely on the DB-level active-name uniqueness mechanism for concurrency safety; application pre-checks are advisory and must not be the only protection.

### 10.3 User Management endpoints

| Endpoint | Method | Auth | CSRF | Role | Purpose |
| --- | --- | --- | --- | --- | --- |
| `/api/v1/admin/users` | `GET` | session | no | admin | List/search users. |
| `/api/v1/admin/users` | `POST` | session | yes | admin | Create local user. |
| `/api/v1/admin/users/{userId}` | `GET` | session | no | admin | Read user detail. |
| `/api/v1/admin/users/{userId}` | `PATCH` | session | yes | admin | Update display name, role or status. |
| `/api/v1/admin/users/{userId}/reset-password` | `POST` | session | yes | admin | Set a new password and revoke sessions. |
| `/api/v1/admin/users/{userId}/workspaces` | `PUT` | session | yes | admin | Replace workspace membership access set. |

Create request:

```json
{
  "email": "user@example.test",
  "displayName": "User",
  "role": "user",
  "status": "active",
  "password": "ChangeMe12345",
  "workspaceIds": ["01HZW000000000000000000000"]
}
```

Patch request:

```json
{
  "displayName": "Updated User",
  "role": "admin",
  "status": "active"
}
```

Reset password request:

```json
{
  "newPassword": "ChangeMe12345"
}
```

Membership replacement request:

```json
{
  "workspaceIds": ["01HZW000000000000000000000"]
}
```

Rules:

1. Only Admin may call User Management endpoints.
2. Email normalization and password policy match the P0 auth baseline.
3. Create user does not send email and does not return password.
4. Disable user revokes all active sessions for that user.
5. Reset password revokes all active sessions for that user.
6. Disabling or downgrading the last active Admin must return `409 USER_LAST_ACTIVE_ADMIN`.
7. `PATCH /api/v1/admin/users/{userId}` must run final-state validation after applying role/status changes in memory and before commit.
8. If PATCH changes an active Admin to active `user`, the target user must have at least one active Workspace membership after the patch; otherwise return `409 USER_WORKSPACE_REQUIRED`.
9. Replacing memberships must reject archived workspace IDs and unknown workspace IDs.
10. Active non-admin users must have at least one active workspace membership.
11. Admin users may be granted explicit memberships, but global Admin access is not represented as a workspace role.

### 10.4 Setup Status and System Settings endpoints

| Endpoint | Method | Auth | CSRF | Role | Purpose |
| --- | --- | --- | --- | --- | --- |
| `/api/v1/setup/status` | `GET` | none | no | public | Existing minimal bootstrap status; must remain safe for unauthenticated callers. |
| `/api/v1/admin/setup-status` | `GET` | session | no | admin | Expanded setup status with no secret values. |
| `/api/v1/admin/system-settings` | `GET` | session | no | admin | Read non-sensitive settings and configured/missing status. |
| `/api/v1/admin/system-settings` | `PATCH` | session | yes | admin | Update whitelisted non-sensitive settings. |

Settings response shape:

```json
{
  "settings": {
    "allowSignup": true,
    "loadSoftLimitWarningConcurrency": 1000,
    "jmeterMemoryXmx": "4G",
    "maxScenarioItemsPerTestPlan": 20,
    "maxSlaRulesPerTestPlan": 5,
    "maxRunDurationSeconds": 86400,
    "maxRampUpSeconds": 86400,
    "maxDelaySeconds": 86400,
    "maxIterations": 1000000,
    "maxTargetRps": 100000,
    "dependencyFileMaxBytes": 104857600,
    "dependencyFileAllowedExtensions": [],
    "dependencyFilePreviewMaxBytes": 65536,
    "dependencyFilePreviewBinaryDenyExtensions": [".png", ".jpg", ".zip"]
  },
  "sensitiveStatus": {
    "runnerInternalTokenConfigured": true,
    "sshCredentialEncryptionKeyConfigured": true,
    "minioCredentialsConfigured": true
  }
}
```

Patch request:

```json
{
  "allowSignup": false,
  "loadSoftLimitWarningConcurrency": 1500,
  "jmeterMemoryXmx": "6G",
  "dependencyFileAllowedExtensions": [".csv", ".txt"]
}
```

Rules:

1. `sensitiveStatus` returns booleans only.
2. API must reject attempts to PATCH unrecognized settings or sensitive-looking keys.
3. Admin Setup Status may report `activeWorkspaceCount`, `archivedWorkspaceCount`, `activeAdminCount`, `allowSignup`, storage availability, a single Load Node runtime status (`ready | not_configured | artifact_missing`) and required secret configured booleans. The official full-stack path is expected to report Load Node Runtime `ready` because `make start-full-stack` runs `make release-runtime` first; low-level compose, manual deployment, explicit preflight opt-out, or deleted artifacts may still surface `not_configured` or `artifact_missing`.
4. Admin Setup Status must not return connection strings, tokens, keys, passwords, bucket credentials, encrypted values, local artifact paths or object keys.
5. Public `GET /api/v1/setup/status` remains limited to unauthenticated bootstrap needs: `needsBootstrap`, effective `allowSignup`, `hasDefaultWorkspace` and coarse `storageAvailable` are allowed; admin-only counts, user/workspace totals beyond existing coarse booleans, secret configured booleans and settings metadata are forbidden.
6. Both public and admin setup status must compute effective `allowSignup` from the same source-of-truth rule in §8.4.

## 11. Frontend UX Contract

### 11.1 Header and session state

1. `AppLayout` header shows the current Workspace name and a switcher when `availableWorkspaces.length > 1` or the actor can manage Workspaces.
2. Header state comes from session context, not from independent cached workspace list authority.
3. On login/register/session refresh/switch, Web must overwrite in-memory auth/workspace state with API response.
4. Web may write `currentWorkspaceId` to localStorage after successful session context resolution or switch.
5. Web must delete or replace local preference when API returns a different `currentWorkspace.id`.

### 11.2 Dirty guard

Routes with editable resource state must register a dirty guard before allowing Workspace switch.

Minimum covered routes:

| Route | Dirty state examples | Safe landing after confirmed switch |
| --- | --- | --- |
| `/scenarios/:scenarioId` | unsaved scenario fields, steps, debug preview state | `/scenarios` |
| `/test-plans/:planId` | unsaved plan fields, orchestration, load settings, SLA edits | `/test-plans` |
| `/assets/env-groups` edit dialog | unsaved env group form values | `/assets/env-groups` |
| `/resources/load-nodes/new` | unsaved node form or credential input | `/resources/load-nodes` |

Rules:

1. If route is dirty, switcher must show a modal with exactly two outcomes: abandon and switch, or cancel switch.
2. Cancel keeps current Workspace and preserves edit state.
3. Abandon clears route-local form state, temporary previews, pending upload selections and non-persisted drafts before navigation.
4. Web must not copy A Workspace resource IDs or drafts into B Workspace.
5. If the current route has no known safe list route, navigate to `/overview`.

### 11.3 Admin routes

P1-03 activates these routes:

| Page | Route | Auth |
| --- | --- | --- |
| Workspace management | `/admin/workspaces` | Admin |
| User management | `/admin/users` | Admin |
| System settings | `/admin/system-settings` | Admin |
| Setup status | `/admin/setup-status` | Admin |

Rules:

1. `/admin` may route to `/admin/setup-status` or an Admin section landing.
2. Non-admin access renders 403 and must not fetch Admin data.
3. Admin pages use generated contracts and TanStack Query.
4. Forms use React Hook Form + Zod or existing repository form convention.
5. User-facing copy remains English.

## 12. Error Handling Contract

P1-03 adds or uses these error codes through the existing unified error shape:

| Code | HTTP | Contract |
| --- | ---: | --- |
| `WORKSPACE_REQUIRED` | 400 | Missing or invalid Workspace context where no fallback can be resolved. |
| `WORKSPACE_ACCESS_DENIED` | 403 | Actor cannot access the requested Workspace. |
| `WORKSPACE_ARCHIVED` | 403 | Workspace exists but cannot be used because it is archived. |
| `WORKSPACE_NOT_FOUND` | 404 | Admin requested a Workspace ID that does not exist. |
| `WORKSPACE_NAME_CONFLICT` | 409 | Active Workspace name conflicts after normalization, including database unique-index conflicts. |
| `WORKSPACE_LAST_ACTIVE_REQUIRED` | 409 | Attempt would leave zero active Workspaces. |
| `RESOURCE_NOT_FOUND` | 404 | Resource does not exist in the resolved Workspace or must be hidden. |
| `USER_NOT_FOUND` | 404 | Admin requested a user ID that does not exist. |
| `USER_EMAIL_CONFLICT` | 409 | Email conflicts after normalization. |
| `USER_DISABLED` | 403 | User is disabled and cannot receive an authenticated context. |
| `USER_LAST_ACTIVE_ADMIN` | 409 | Attempt would leave no active Admin. |
| `USER_WORKSPACE_REQUIRED` | 409 | Active non-admin user would have no active Workspace access. |
| `SETTING_NOT_EDITABLE` | 400 | Requested setting is not in the writable whitelist. |
| `SENSITIVE_SETTING_VALUE_FORBIDDEN` | 400 | Request attempts to edit or submit sensitive material as a setting. |

Rules:

1. API `message` values are English fallback text.
2. Cross-workspace resource access should use `404 RESOURCE_NOT_FOUND` when returning 403 would leak resource existence.
3. Disable/role/membership operations that trigger final Admin protection must use `409 USER_LAST_ACTIVE_ADMIN`.
4. Settings validation must not echo rejected secret-like values in error `details`.
5. Invalid `preferredWorkspaceId` on `/auth/me` is a local preference miss, not a `WORKSPACE_REQUIRED` or validation error by itself.
6. Database integrity errors from the active workspace name uniqueness mechanism must be caught and mapped to `409 WORKSPACE_NAME_CONFLICT` without leaking raw SQL details.

## 13. Security and Privacy Requirements

1. Authorization runs in API backend for every Admin and Workspace-sensitive operation.
2. Disabled users cannot create new sessions, refresh usable session context or call business APIs.
3. Last active Admin protection must count only users with `role='admin'` and `status='active'`.
4. Admin cannot disable self if doing so leaves no other active Admin.
5. Admin cannot downgrade self if doing so leaves no other active Admin.
6. Admin cannot remove the last active Admin path required for governance.
7. Passwords appear only in create/reset request bodies over authenticated Admin APIs; they are never returned.
8. Session cookies, CSRF tokens, password hashes, runner tokens, SSH credentials, MinIO credentials and encryption keys must not appear in API responses, OpenAPI examples, Web state snapshots, logs, audit details or tests.
9. Audit events should record security-relevant admin actions with actor, target type, target id, request id and non-sensitive details.
10. Business resources remain Workspace-isolated after switch, archive, membership change or role change.
11. Public setup status must remain safe for unauthenticated callers and must not expose admin-only counts, sensitive configured booleans or settings metadata.

## 14. Tests

Minimum tests:

1. API session context tests:
   - returns current Workspace and available Workspaces;
   - `preferredWorkspaceId` selects an accessible active Workspace;
   - invalid, archived, missing or inaccessible `preferredWorkspaceId` falls back to deterministic accessible active Workspace;
   - disabled session fails.
2. API workspace tests:
   - Admin create/rename/archive;
   - normal user cannot manage Workspaces;
   - archive last active Workspace rejected;
   - archived Workspace cannot be used as `x-workspace-id`;
   - concurrent create/rename cannot create two active Workspaces with the same case-folded name.
3. Cross-workspace resource tests:
   - B header + A resource ID returns 404 or 403 as documented;
   - API does not auto-rewrite current Workspace.
4. User Management tests:
   - list/search/create;
   - email conflict;
   - disable revokes sessions;
   - reset password revokes sessions;
   - role change;
   - admin-to-user downgrade requires active Workspace membership;
   - last active Admin protection;
   - membership replacement rejects archived/unknown Workspace IDs.
5. Settings and Setup Status tests:
   - only whitelisted non-sensitive settings update;
   - sensitive-looking keys rejected;
   - `system_settings.allowSignup` overrides the env seed after the DB row exists;
   - bootstrap remains allowed when no users exist even if `allowSignup=false`;
   - public setup status remains minimal and does not expose admin-only counts or sensitive configured booleans;
   - response contains configured/missing booleans only where the endpoint is Admin-only;
   - writable System Settings fields validate type/range/cross-field constraints;
   - `singleNodeConcurrencyHardLimit`, Monitoring tokens, Grafana/Influx credentials and secret-like keys are not writable or echoed;
   - DB-backed soft limit, Test Plan policy, Dependency File policy and `jmeterMemoryXmx` snapshot behavior are covered.
6. Migration tests:
   - `ck_users_status` accepts `active` and `disabled` and rejects other values;
   - `ck_workspaces_status` accepts `active` and `archived` and rejects other values;
   - `disabled_at` and `archived_at` columns exist and round-trip;
   - active Workspace case-folded uniqueness is enforced at the database layer.
7. Contract tests:
   - OpenAPI includes new schemas/endpoints/error codes;
   - generated Web client is fresh.
8. Web tests:
   - header switcher uses session context;
   - dirty guard cancel preserves state;
   - abandon-and-switch clears local edit state and lands on safe route;
   - Admin routes block non-admin;
   - User/Workspace/Settings pages use generated API types.
9. E2E smoke:
   - Admin logs in, creates Workspace B, switches from A to B, creates or views a B-scoped list page, switches back to A, verifies no B resource leaks into A;
   - dirty Scenario/Test Plan page switch can be cancelled;
   - disabled user cannot continue using an old session.
10. P0 regression:
   - default Workspace happy path still works;
   - Run/Report/resource security smoke remains green;
   - Private credential and artifact path safety tests remain green.

## 15. Done When

This Slice is complete only when:

1. `docs/sdd/slices/P1-README.md` marks `P1-03-workspace-admin.md` as an active Slice SDD.
2. DB migrations widen `users.status` and `workspaces.status`, add `disabled_at` and `archived_at`, add the `system_settings` store, and enforce active Workspace case-insensitive uniqueness at the database layer.
3. FastAPI/Pydantic source schemas define all P1-03 API contracts and generated OpenAPI is fresh.
4. Web consumes generated client/types for all P1-03 pages and state transitions.
5. `/auth/me` or equivalent session context response includes `currentWorkspace`, `availableWorkspaces`, membership summary and permissions summary.
6. `/auth/me` accepts optional `preferredWorkspaceId` query preference and applies the fallback/error behavior defined in this SDD.
7. Workspace switch/create/rename/archive works with backend authorization and archived Workspace guards.
8. Dirty guard supports cancel and abandon-and-switch behavior on editable resource routes.
9. B header + A resource ID is protected by backend 404/403 behavior.
10. User Management supports list/search/create/disable/enable/role/reset-password and last active Admin protection.
11. Admin-to-user downgrade validates active Workspace membership for the resulting active user.
12. Disabled users cannot log in or continue using old sessions.
13. `system_settings.allowSignup` is the effective non-bootstrap signup source of truth after migration, while first-user bootstrap remains available when no users exist.
14. Admin System Settings exposes the accepted writable DB-backed policy keys, excludes hard limit/build-time/stack/secrets settings, and shows only the existing three configured/missing read-only booleans.
15. Test Plan guardrails, Dependency File upload/preview policy and `jmeterMemoryXmx` future-Run snapshot semantics read effective DB-backed values.
16. Public setup status remains minimal, and Admin setup status exposes no secret/token/key plaintext or encrypted material.
17. R1-R6 env/compose governance drift checks pass.
18. `make generate-contracts` passes.
19. `make verify` passes.
20. A P1-03 E2E smoke or closest available Playwright/API smoke passes, or the environment gap is explicitly recorded.
21. Independent review finds no remaining Slice-blocking issues.

## 16. Implementation Backfill

Implemented engineering facts for this Slice:

1. API adds P1-03 session context, Workspace switch/list/admin management, User Management, Admin Setup Status, and System Settings endpoints through FastAPI/Pydantic contracts.
2. DB migration `0011_p1_03_workspace_admin.py` widens user/workspace statuses, adds `disabled_at` and `archived_at`, adds `system_settings`, and enforces active Workspace case-insensitive uniqueness.
3. Runtime `system_settings.allowSignup` is used as the non-bootstrap signup source of truth; public setup status remains minimal, and Admin setup/status/settings expose only boolean configured/missing sensitive status plus the Load Node runtime readiness status enum.
4. System Settings now uses a typed DB-backed registry for the accepted writable policy keys only: signup, load soft-limit warning concurrency, JMeter Xmx, Test Plan strategy limits, and Dependency File upload/preview policy. Sensitive-looking keys are rejected before registry handling, and `singleNodeConcurrencyHardLimit` remains deployment-managed and absent from the writable contract/UI.
5. Test Plan guardrails read `effective_load_settings(db)` at create/clone/update/not-runnable/detail guard/summary/preview/run-validation entry points; Dependency File upload/preview routes read `dependency_file_policy(db)`, including the first content-length upload gate.
6. `jmeterMemoryXmx` is copied into new debug Scenario/Test Plan Run snapshots. Execution bundle generation reads the snapshot value first and uses the environment fallback only for older snapshots without the field.
7. Web consumes generated contracts via `@surgepilot/contracts`, adds AppLayout Workspace switching, Admin routes, Admin 403 rendering, dirty-switch guards for editable routes, and grouped Admin System Settings cards for Access, Load guardrails, JMeter runtime, Dependency files, and read-only deployment status.
8. Env/compose R1-R6 drift was backfilled: `.env.example` has one `RUNNER_INTERNAL_TOKEN`, compose-consumed variables are documented, Web runtime `VITE_API_BASE_URL` was removed from full/base compose, optional API/Web image build mirrors remain build-arg-only and commented in `.env.example`, and Monitoring/Grafana/Influx secrets remain outside System Settings responses/UI.
9. Added API/Web/E2E coverage for P1-03 session context, Workspace/User/Settings governance, disabled session invalidation, last active Admin/Workspace protection, Admin business access to active Workspaces, Workspace switch smoke, Setup Status runtime readiness, System Settings policy UI smoke, env/compose drift checks, DB-backed policy validation, Dependency File policy hot-read behavior, Test Plan guardrail hot-read behavior, and JMeter snapshot behavior.

R12a atomic 5 factual backfill: the reconstructed staging checkpoint now carries focused API coverage in `apps/api/tests/test_p1_03_workspace_admin_api.py`, a Web dirty-switch guard test, the P1-03 OpenAPI/secret-safety contract assertion, the available base-compose drift check, and Playwright smoke coverage in `tests/e2e/p1_03_workspace_admin.spec.ts`. These checks cover the session-context preference fallback, Workspace create/rename/archive and archived access, Admin-only user management, disabled-session invalidation, last-active protections, writable-settings whitelist, secret rejection, generated contract boundaries, and the scoped Web workspace-switch/settings flows. No P1-01/04/05/06/09 or P2 surface is added by this verification atomic.

Verification used during implementation:

- `make setup`
- `make test`
- `uv run --all-packages pytest tests/contract/test_env_example_drift.py -q`
- `uv run --all-packages pytest apps/api/tests/test_p1_03_workspace_admin_api.py -k "system_settings" -q`
- `uv run --all-packages pytest apps/api/tests -k "system_settings or dependency_file or test_plan or jmeter" -q`
- `make generate-contracts`
- `pnpm --filter @surgepilot/web test -- system-settings`
- `pnpm --filter @surgepilot/web typecheck`
- `pnpm --filter @surgepilot/web lint`
- `pnpm e2e -- tests/e2e/p1_03_workspace_admin.spec.ts`
- `make verify`
