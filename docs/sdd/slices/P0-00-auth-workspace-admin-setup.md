# P0-00: Auth / Workspace / Admin Setup

- Document status: Draft v2 for implementation
- Product: SurgePilot
- Document path: `docs/sdd/slices/P0-00-auth-workspace-admin-setup.md`
- Current delivery target: P0 only
- Slice owner: API / Web / Contracts
- Depends on: `00-product-scope-and-priority.md`, `01-architecture-overview.md`, `02-repo-structure-and-dev-workflow.md`, `04-api-contract-guidelines.md`, `06-security-permission-workspace.md`, `09-testing-and-acceptance-strategy.md`
- Review incorporated: P0-00 Review A/B/C/D, especially 06 hard-conflict fixes for sessions, brute-force lockout, CSRF error codes, audit events, and unit tests.
- Naming note: product and user-facing text use **SurgePilot**. Machine identifiers use the form required by the actual target file or runtime, for example `surgepilot_session`, `surgepilot`, `SURGEPILOT_*`, or a repository package name already locked elsewhere.

---

## 1. Goal

This slice establishes the first executable vertical slice for SurgePilot:

```text
anonymous visitor
  -> setup status check
  -> first administrator registration or login
  -> authenticated session
  -> default Workspace resolved
  -> placeholder Overview confirms current user and Workspace
  -> logout
```

After this slice is done, SurgePilot can prove that local account bootstrap, cookie session authentication, CSRF recovery, default Workspace membership, and generated Web API types work end to end.

This slice intentionally does **not** implement any performance-testing business resource. It only provides the minimum identity and Workspace foundation needed by later P0 slices.

---

## 2. PRD Trace

This slice implements the P0 account and Workspace bootstrap requirements:

1. Email and password registration.
2. Email and password login.
3. Logout.
4. Current user lookup.
5. First successful registered user becomes `admin`.
6. Later registered users become `user`.
7. `ALLOW_SIGNUP=false` blocks self-registration after the first administrator exists.
8. Default Workspace exists and is attached to every user in P0.
9. P0 has Workspace-aware data model from day 1, even though only one default Workspace is exposed.
10. Admin Setup Status is platform-level read-only state, not a business record bound to a Workspace.

This slice creates the foundation for later `createdBy`, `updatedBy`, `triggeredBy`, permission checks, and `x-workspace-id` propagation.

---

## 3. In Scope

### 3.1 Backend

Implement these public API endpoints:

| Endpoint | Method | Auth | CSRF | Purpose |
| --- | --- | --- | --- | --- |
| `/api/v1/setup/status` | `GET` | anonymous | no | Minimal bootstrap status for login/register routing. |
| `/api/v1/auth/register` | `POST` | anonymous | no | Register user; first user becomes Admin; creates session. |
| `/api/v1/auth/login` | `POST` | anonymous | no | Create a new session. |
| `/api/v1/auth/logout` | `POST` | optional session | yes when session exists | Invalidate current session; idempotent. |
| `/api/v1/auth/me` | `GET` | session | no | Return current user and default Workspace. |
| `/api/v1/auth/csrf` | `GET` | session | no | Return current session CSRF token for SPA refresh recovery. |

Implement server-side support for:

1. Argon2id password hashing.
2. Cookie-based PostgreSQL-backed server-side sessions.
3. Absolute session expiry of 7 days.
4. Idle sliding session expiry of 24 hours based on `last_seen_at`.
5. Session-bound CSRF tokens.
6. Multiple active sessions per user.
7. Logout for current session only.
8. Account-level login brute-force guard exactly matching `06-security-permission-workspace.md`.
9. Default Workspace creation through migration.
10. Default Workspace membership for all users.
11. Minimal `audit_events` table aligned with 06.
12. `x-request-id` and unified error response integration.

### 3.2 Data

Create one Alembic migration:

```text
apps/api/migrations/versions/0001_p0_00_auth_workspace.py
```

The migration creates:

1. `users`
2. `sessions`
3. `workspaces`
4. `workspace_members`
5. `audit_events`

The migration also inserts the default Workspace:

```text
id:   01HZW000000000000000000000
name: Default Workspace
```

The name may be overridden at runtime for display by `DEFAULT_WORKSPACE_NAME`, but the migration seed must remain deterministic.

### 3.3 Frontend

Implement the minimum routes:

| Route | Purpose |
| --- | --- |
| `/login` | Email/password login form. |
| `/register` | Email/display name/password registration form. |
| `/overview` | Authenticated placeholder page showing current user and default Workspace. |

The `/overview` route is only a placeholder in this slice. It must not implement the later P0 Overview dashboard cards, run statistics, resource status summaries, or quick-entry business features.

### 3.4 Tests

Implement:

1. Unit tests for security services and Workspace resolution.
2. API tests for register/login/logout/me/csrf/setup status.
3. Database migration test or migration upgrade check.
4. Contract tests for the new OpenAPI operations and schemas.
5. Web typecheck using generated client/types.
6. One Playwright smoke test under `tests/e2e/`:

```text
setup status -> register first Admin -> overview displays user and Workspace -> logout -> login page
```

---

## 4. Out of Scope

This slice must not implement:

1. Setup Wizard or separate `/setup` product flow.
2. `/api/v1/setup/bootstrap` or any endpoint that duplicates `/auth/register`.
3. User avatar, profile editing, password change, or password reset.
4. Email verification.
5. Invitation flow.
6. User Management UI.
7. Admin user list, create user, disable user, enable user, reset password.
8. Workspace switcher.
9. Workspace create/edit/archive APIs or UI.
10. Workspace member management APIs or UI.
11. Workspace-scoped roles.
12. Complex RBAC beyond global `admin` and `user`.
13. OAuth, OIDC, SAML, LDAP, or SSO.
14. CAPTCHA.
15. Generic API rate-limit framework or `X-RateLimit-*` response headers.
16. Full Admin Setup Status health dashboard.
17. MinIO, Load Node, Runner token, concurrency limit, or artifact health checks.
18. Any Scenario, Env Group, Dependency File, Load Node, Test Plan, Run, Report, or Artifact CRUD.
19. Any P1/P2 endpoint hidden behind a feature flag.

Database fields must stay aligned with 06 and should not add unused future fields just because they may help P1.

---

## 5. Key Decisions

| Area | Decision |
| --- | --- |
| Bootstrap UX | Reuse `/register`; no Setup Wizard. |
| First Admin | Backend decides by checking whether any user exists. |
| Register success | Creates session and returns `csrfToken`. |
| Login success | Creates independent session and returns `csrfToken`. |
| Multi-session | Allowed. Logout invalidates only current session. |
| Session expiry | Absolute 7 days + idle 24 hours. |
| CSRF delivery | `register`, `login`, and `/auth/csrf` only. |
| CSRF errors | Use `CSRF_TOKEN_REQUIRED` and `CSRF_TOKEN_INVALID`. |
| Setup status | Anonymous and minimal. |
| Default Workspace | Seeded by migration with fixed ULID. |
| Workspace UI | Read-only current default Workspace display only. |
| User status | P0 only creates `active`; disable/enable is P1. |
| Password policy | Minimum 10 characters, at least one letter, at least one digit. |
| Login brute-force guard | 06-defined account-level step lockout; no time window and no generic rate-limit framework. |
| Session token storage | DB stores SHA-256 hash of high-entropy cookie token. No pepper secret. |
| CSRF token storage | DB stores SHA-256 hash of independent high-entropy CSRF token. No pepper secret. |
| API examples | English messages only. |
| Web API types | Generated from OpenAPI only. |

---

## 6. Data Model

All table and column names use `snake_case`. External business IDs use ULID strings stored as `text` or `char(26)`.

### 6.1 `users`

Purpose: local SurgePilot accounts.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `email` | `text` | yes | Globally unique, normalized lowercase. |
| `display_name` | `text` | yes | Required in P0. |
| `password_hash` | `text` | yes | Argon2id hash only; never returned. |
| `role` | `text` | yes | Global role: `admin` or `user`. |
| `status` | `text` | yes | P0 creates only `active`. |
| `failed_login_count` | `integer` | yes | Account-level brute-force guard. Default `0`. |
| `locked_until` | `timestamptz` | no | Login guard cooldown. |
| `last_login_at` | `timestamptz` | no | Updated on successful login. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |

Constraints:

1. Unique index on normalized `email`.
2. `role in ('admin', 'user')`.
3. `status in ('active')` for P0. Do not implement disabled status behavior yet.
4. `display_name` length should be bounded, recommended `1..120` characters.
5. `email` length should be bounded, recommended max `320` characters.

Implementation notes:

1. Email normalization happens before uniqueness check.
2. API never reveals whether a login failure was caused by missing email, wrong password, or lockout.
3. `password_hash` must never appear in response, logs, audit event details, OpenAPI examples, or test snapshots.
4. `failed_login_window_started_at` must not be added; 06 defines lockout as account-level failure count, not sliding-window state.

### 6.2 `sessions`

Purpose: server-side browser sessions.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | Internal session row ID. |
| `session_token_hash` | `text` | yes | SHA-256 hash of opaque cookie token. Raw token is never stored. |
| `user_id` | `char(26)` | yes | FK to `users.id`. |
| `csrf_token_hash` | `text` | yes | SHA-256 hash of current session CSRF token. |
| `created_at` | `timestamptz` | yes | UTC. |
| `last_seen_at` | `timestamptz` | yes | Updated on authenticated requests. |
| `expires_at` | `timestamptz` | yes | Absolute expiry: created time + 7 days. |
| `revoked_at` | `timestamptz` | no | Set by logout. |

Constraints and indexes:

1. Unique index on `session_token_hash`.
2. Index on `(user_id, revoked_at, expires_at)`.
3. Do not store `ip_address`, `ip_hash`, `user_agent`, or `user_agent_hash` in `sessions`; request source details belong to `audit_events`.

Session validity rule:

```text
active = revoked_at is null
     and expires_at > now()
     and last_seen_at + 24 hours > now()
```

Cookie rules:

| Setting | Value |
| --- | --- |
| Cookie name | `surgepilot_session` |
| `HttpOnly` | yes |
| `SameSite` | `Lax` |
| `Secure` | true in HTTPS production; local HTTP dev may disable |
| `Path` | `/` |
| Absolute TTL | 7 days |
| Idle TTL | 24 hours after `last_seen_at` |

Implementation notes:

1. Cookie token must be high entropy and generated by a secure random generator.
2. DB stores only SHA-256 token hash.
3. No `SESSION_SECRET` or hash pepper is required for P0 token lookup.
4. Every authenticated request may update `last_seen_at`; do not prematurely optimize this away in P0.

### 6.3 `workspaces`

Purpose: P0 default Workspace and future Workspace-aware data boundary.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. Default seed is fixed. |
| `name` | `text` | yes | Default `Default Workspace`. |
| `status` | `text` | yes | P0 creates only `active`. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |

Default seed:

```sql
INSERT INTO workspaces (id, name, status, created_at, updated_at)
VALUES (
  '01HZW000000000000000000000',
  'Default Workspace',
  'active',
  now(),
  now()
);
```

Rules:

1. P0 does not expose Workspace create/edit/archive APIs.
2. P0 does not expose Workspace switching UI.
3. Business data in later slices must reference `workspace_id` from day 1.
4. Do not add unused `slug` in P0; no route, UI, API, or lookup behavior uses it.

### 6.4 `workspace_members`

Purpose: attach users to the default Workspace.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `workspace_id` | `char(26)` | yes | FK to `workspaces.id`. |
| `user_id` | `char(26)` | yes | FK to `users.id`. |
| `joined_at` | `timestamptz` | yes | UTC timestamp for membership creation. |

Constraints:

1. Primary key or unique constraint on `(workspace_id, user_id)`.
2. Do not store a duplicate membership role in P0.

Rules:

1. First Admin registration creates a membership in the default Workspace.
2. Later user registration creates a membership in the default Workspace.
3. Role remains global on `users.role` in P0.
4. P0 does not expose membership management.
5. P0 does not introduce Workspace Owner, Resource Manager, Viewer, or custom roles.

### 6.5 `audit_events`

Purpose: minimal foundation for security-relevant audit and user attribution. This slice creates the table and writes auth-related events, but does not implement an Audit UI or list API.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `workspace_id` | `char(26)` | no | Nullable for platform-level auth/setup events. |
| `actor_user_id` | `char(26)` | no | Nullable for anonymous setup status or failed login with unknown user. |
| `event_type` | `text` | yes | Example: `auth.register`, `auth.login`, `auth.logout`, `auth.login_failed`, `auth.locked`. |
| `target_type` | `text` | no | Example: `user`, `session`, `workspace`. |
| `target_id` | `char(26)` | no | Business ID when applicable. |
| `request_id` | `text` | no | Nullable in schema, but implementation should populate it for API requests. |
| `ip_address` | `text` | no | Normalized request IP when available. Do not use for auth decisions in P0. |
| `user_agent` | `text` | no | Truncated User-Agent when available. |
| `details_json` | `jsonb` | yes | Default `{}`. Must not contain secrets. |
| `created_at` | `timestamptz` | yes | UTC. |

Rules:

1. Use `details_json`, not `metadata`, to align with 06.
2. `request_id` is nullable at DB level but API implementation should always write it.
3. `ip_address` and `user_agent` are for audit context only.
4. Normalize IP and truncate User-Agent before writing.
5. Never store password, password hash, session token, CSRF token, cookie value, SSH credential, runner token, MinIO credential, or encryption key in `details_json`.
6. Audit event list, export, retention cleanup, and UI are out of scope for P0-00.

---

## 7. Environment Variables

P0-00 uses only these slice-relevant environment variables. It intentionally does not introduce session or CSRF pepper secrets.

| Variable | Required | Default / Example | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | yes | `postgresql://surgepilot:surgepilot@localhost:5432/surgepilot` | PostgreSQL connection. |
| `ALLOW_SIGNUP` | yes | `true` | Allows self-registration after bootstrap. |
| `DEFAULT_WORKSPACE_NAME` | no | `Default Workspace` | Display name for the default Workspace. |

Rules:

1. `.env.example` must include these variables with non-secret example values.
2. Real secret values must not be committed.
3. `ALLOW_SIGNUP=false` never blocks the first Admin bootstrap when no user exists.
4. `SESSION_SECRET`, `CSRF_SECRET`, `LOGIN_FAILURE_LIMIT`, `LOGIN_FAILURE_WINDOW_MINUTES`, and `LOGIN_LOCK_MINUTES` are not introduced by this slice.
5. If the team later wants peppered token hashes or configurable lockout thresholds, it must be decided by ADR or a Foundation SDD update, not silently added in P0-00.

---

## 8. API Contract

All API JSON fields use `camelCase`. DB and ORM fields use `snake_case`.

All error responses use:

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Validation failed.",
  "requestId": "req_01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "details": [
    {
      "field": "email",
      "code": "INVALID_EMAIL",
      "message": "Enter a valid email address."
    }
  ]
}
```

API `message` and `details[].message` examples must be English. Frontend localization is by `code`.

### 8.1 Shared Schemas

#### `UserSummary`

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "email": "admin@example.com",
  "displayName": "Admin User",
  "role": "admin",
  "status": "active"
}
```

Rules:

1. `role` is `admin` or `user`.
2. `status` is only `active` in P0.
3. Never return `password`, `passwordHash`, session token, or CSRF token inside `user`.

#### `WorkspaceSummary`

```json
{
  "id": "01HZW000000000000000000000",
  "name": "Default Workspace"
}
```

#### `AuthSessionResponse`

Used by `register` and `login`.

```json
{
  "user": {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    "email": "admin@example.com",
    "displayName": "Admin User",
    "role": "admin",
    "status": "active"
  },
  "defaultWorkspace": {
    "id": "01HZW000000000000000000000",
    "name": "Default Workspace"
  },
  "csrfToken": "csrf_example_token"
}
```

Rules:

1. `csrfToken` is returned only by `register`, `login`, and `/auth/csrf`.
2. Token values in docs and tests must be fake examples.
3. Response header should include the actual `x-workspace-id` when a session is created and default Workspace is resolved.

#### `CurrentUserResponse`

Used by `/auth/me`.

```json
{
  "user": {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    "email": "admin@example.com",
    "displayName": "Admin User",
    "role": "admin",
    "status": "active"
  },
  "defaultWorkspace": {
    "id": "01HZW000000000000000000000",
    "name": "Default Workspace"
  }
}
```

### 8.2 `GET /api/v1/setup/status`

Purpose: allow the SPA to decide whether to show first-Admin registration copy or normal login/register copy before authentication.

Authentication: anonymous.

CSRF: not required.

Request headers: no session required; no `x-workspace-id` required.

Response `200 OK`:

```json
{
  "needsBootstrap": true,
  "allowSignup": true,
  "hasDefaultWorkspace": true
}
```

Field semantics:

| Field | Meaning |
| --- | --- |
| `needsBootstrap` | `true` when no user exists. |
| `allowSignup` | Effective signup availability. Must be `true` when `needsBootstrap=true`, even if `ALLOW_SIGNUP=false`. |
| `hasDefaultWorkspace` | Whether the default Workspace seed exists. |

Rules:

1. This endpoint must not return user count, admin email, environment name, build version, secret configuration, MinIO state, Load Node state, or concurrency limits.
2. This endpoint is intentionally smaller than the later Admin Setup Status page.
3. Full Admin-only Setup Status health checks are out of scope for P0-00.
4. If `hasDefaultWorkspace=false`, the UI may show a generic setup error. The fix is migration/seed recovery, not a Setup Wizard.

### 8.3 `POST /api/v1/auth/register`

Purpose: register a local account and create an authenticated session.

Authentication: anonymous.

CSRF: not required because no session exists before registration.

Request:

```json
{
  "email": "admin@example.com",
  "displayName": "Admin User",
  "password": "password123"
}
```

Validation:

| Field | Rule |
| --- | --- |
| `email` | Required, valid email, normalized lowercase, max 320 chars. |
| `displayName` | Required, trimmed, 1..120 chars. |
| `password` | Required, min 10 chars, at least one letter, at least one digit. |

Role assignment:

1. If no user exists at commit time, create the user as `admin`.
2. If at least one user exists, create the user as `user`, unless signup is disabled.
3. Use a transaction and database lock or equivalent serialization guard to prevent two concurrent first users from both becoming Admin.

Response `201 Created`:

```json
{
  "user": {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    "email": "admin@example.com",
    "displayName": "Admin User",
    "role": "admin",
    "status": "active"
  },
  "defaultWorkspace": {
    "id": "01HZW000000000000000000000",
    "name": "Default Workspace"
  },
  "csrfToken": "csrf_example_token"
}
```

Response headers:

1. `Set-Cookie: surgepilot_session=...; HttpOnly; SameSite=Lax; Path=/; Secure` in HTTPS production.
2. `x-request-id`.
3. `x-workspace-id: 01HZW000000000000000000000`.
4. `Cache-Control: no-store`.

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `VALIDATION_ERROR` | 422 | Invalid email format, missing field, invalid displayName. |
| `EMAIL_ALREADY_EXISTS` | 409 | Normalized email already exists. |
| `PASSWORD_POLICY_VIOLATION` | 422 | Password does not satisfy policy. |
| `SIGNUP_DISABLED` | 403 | At least one Admin exists and `ALLOW_SIGNUP=false`. |
| `WORKSPACE_REQUIRED` | 400 | Default Workspace cannot be resolved. |
| `INTERNAL_ERROR` | 500 | Unexpected failure. |

Idempotency:

1. Registration is not idempotent.
2. Repeating the same email returns `EMAIL_ALREADY_EXISTS` after the first success.

Audit events:

1. Write `auth.register` after successful commit.
2. Do not include password or token values.

### 8.4 `POST /api/v1/auth/login`

Purpose: create a new session for an existing local user.

Authentication: anonymous.

CSRF: not required because the caller may not have a session.

Request:

```json
{
  "email": "admin@example.com",
  "password": "password123"
}
```

Response `200 OK`:

```json
{
  "user": {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    "email": "admin@example.com",
    "displayName": "Admin User",
    "role": "admin",
    "status": "active"
  },
  "defaultWorkspace": {
    "id": "01HZW000000000000000000000",
    "name": "Default Workspace"
  },
  "csrfToken": "csrf_example_token"
}
```

Response headers:

1. `Set-Cookie: surgepilot_session=...; HttpOnly; SameSite=Lax; Path=/; Secure` in HTTPS production.
2. `x-request-id`.
3. `x-workspace-id: 01HZW000000000000000000000`.
4. `Cache-Control: no-store`.

Rules:

1. Every successful login creates a new independent session row.
2. Existing sessions for the same user remain valid.
3. `last_login_at` is updated on success.
4. Failed attempts use the same public error code and message regardless of cause.
5. Lockout state must not be revealed publicly.
6. Login success resets `failed_login_count` to `0` and clears `locked_until`.
7. Unknown-user, locked-user, and wrong-password paths all perform one Argon2 verification using either the stored password hash or a fixed dummy hash to reduce login timing enumeration risk.

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `VALIDATION_ERROR` | 422 | Invalid request shape. |
| `INVALID_CREDENTIALS` | 401 | Email missing, password wrong, user not login-eligible, or locked by brute-force guard. |
| `WORKSPACE_REQUIRED` | 400 | Default Workspace cannot be resolved. |

`INVALID_CREDENTIALS` is defined by `06-security-permission-workspace.md`; this slice reuses it and does not register it as a slice-specific code.

Login brute-force guard:

```text
failed_login_count < 5       -> no lock
5 <= failed_login_count < 10 -> locked_until = now + 5 minutes
failed_login_count >= 10     -> locked_until = now + 30 minutes
```

Rules:

1. Scope is account-level using `users.failed_login_count` and `users.locked_until`.
2. There is no sliding time window column.
3. No Redis, external rate-limit service, or generic IP limit framework in P0.
4. No CAPTCHA in P0.
5. No `X-RateLimit-*` headers in P0.
6. Lockout returns `INVALID_CREDENTIALS`.
7. Triggering lockout writes `auth.locked` audit event.

Audit events:

1. Write `auth.login` on success.
2. Optionally write `auth.login_failed` with non-sensitive details.
3. Write `auth.locked` when the failure count enters a lock tier.

### 8.5 `POST /api/v1/auth/logout`

Purpose: invalidate the current session.

Authentication: optional. A request without a valid session still succeeds.

CSRF: required when a valid session exists. If no valid session exists, return `204` without CSRF validation.

Request body: empty.

Response `204 No Content`.

Rules:

1. Logout is idempotent.
2. Current session row is marked `revoked_at=now()`.
3. Response clears `surgepilot_session` cookie.
4. Other sessions for the same user remain active.
5. No JSON body is returned.

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `CSRF_TOKEN_REQUIRED` | 403 | Valid session exists but `x-csrf-token` is missing for logout. |
| `CSRF_TOKEN_INVALID` | 403 | Valid session exists but `x-csrf-token` does not match current session. |

### 8.6 `GET /api/v1/auth/me`

Purpose: restore authenticated user state after page load.

Authentication: required.

CSRF: not required.

Response `200 OK`:

```json
{
  "user": {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    "email": "admin@example.com",
    "displayName": "Admin User",
    "role": "admin",
    "status": "active"
  },
  "defaultWorkspace": {
    "id": "01HZW000000000000000000000",
    "name": "Default Workspace"
  }
}
```

Response headers:

1. `x-workspace-id` is the resolved default Workspace ID.
2. `Cache-Control: no-store`.

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Missing, expired, revoked, idle-expired, or invalid session. |
| `WORKSPACE_REQUIRED` | 400 | Default Workspace cannot be resolved. |

Rules:

1. `/auth/me` does not return `csrfToken`.
2. SPA should call `/auth/csrf` separately only when it needs to recover CSRF token after refresh.
3. `/auth/me` must treat `last_seen_at + 24h < now()` as idle-expired.

### 8.7 `GET /api/v1/auth/csrf`

Purpose: recover the current session CSRF token after SPA refresh.

Authentication: required.

CSRF: not required.

Response `200 OK`:

```json
{
  "csrfToken": "csrf_example_token"
}
```

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Missing, expired, revoked, idle-expired, or invalid session. |

Rules:

1. Only returns a token when an active session exists.
2. Rotates the session CSRF token and invalidates the previous token.
3. Does not attach CSRF token to every GET response.
4. Token value must not be logged or stored in test snapshots.

---

## 9. Error Code Registry Additions

This slice registers only these slice-specific error codes:

| Code | HTTP | Message example | Trigger | UX branch |
| --- | --- | --- | --- | --- |
| `EMAIL_ALREADY_EXISTS` | 409 | `Email already exists.` | Registration email already used. | Offer login. |
| `PASSWORD_POLICY_VIOLATION` | 422 | `Password does not meet the policy.` | Password misses length, letter, or digit rule. | Highlight password field. |
| `SIGNUP_DISABLED` | 403 | `Signup is disabled.` | `ALLOW_SIGNUP=false` after bootstrap. | Tell user to contact administrator. |

This slice reuses these Foundation 06 / core error codes without re-registering them here:

| Code | Use |
| --- | --- |
| `INVALID_CREDENTIALS` | Login failure and lockout. |
| `UNAUTHENTICATED` | Missing, expired, revoked, or idle-expired session. |
| `WORKSPACE_REQUIRED` | Default Workspace cannot be resolved. |
| `CSRF_TOKEN_REQUIRED` | Missing CSRF token for authenticated browser write request. |
| `CSRF_TOKEN_INVALID` | CSRF token does not match current session. |
| `VALIDATION_ERROR` | Generic field validation failure. |

Do not add separate public codes for:

1. `PASSWORD_TOO_SHORT`
2. `PASSWORD_MISSING_DIGIT`
3. `PASSWORD_MISSING_LETTER`
4. `ACCOUNT_LOCKED`
5. `USER_NOT_FOUND`
6. `EMAIL_NOT_VERIFIED`

Password detail may be returned in field-level validation details, but login failure must remain generic.

---

## 10. Security and Permission Rules

### 10.1 Password Storage

1. Use Argon2id.
2. Follow the minimum Argon2id parameter baseline in 06.
3. Never store plaintext or reversible encrypted passwords.
4. Never log password input.
5. Never return password hash.
6. Keep password policy simple for P0.

### 10.2 Session Security

1. Session cookie must be opaque and high entropy.
2. Store only SHA-256 hash of the session token server-side.
3. `surgepilot_session` is `HttpOnly`.
4. `SameSite=Lax` is required.
5. `Secure` is required in HTTPS production.
6. Expired, idle-expired, or revoked sessions return `UNAUTHENTICATED`.
7. Absolute session TTL is 7 days.
8. Idle sliding expiry is 24 hours from `last_seen_at`.
9. Sessions table must not store IP address or User-Agent data.

### 10.3 CSRF

1. All write requests with an authenticated browser session require `x-csrf-token`, except anonymous register/login.
2. CSRF token is independent high-entropy random material bound to the server-side session and compared with constant-time digest comparison.
3. `register` and `login` return a CSRF token because they create a session.
4. `/auth/csrf` rotates and returns the token for refresh recovery.
5. No automatic per-write rotation.
6. No CSRF token in every GET response.
7. Missing token returns `CSRF_TOKEN_REQUIRED`.
8. Non-matching token returns `CSRF_TOKEN_INVALID`.

### 10.4 Authorization

P0-00 only needs these authorization rules:

| Action | Rule |
| --- | --- |
| Read setup status | Anonymous allowed. |
| Register first user | Always allowed if no user exists. |
| Register later user | Allowed only when `ALLOW_SIGNUP=true`. |
| Login | Anonymous allowed. |
| Logout | Current session only; optional session for idempotency. |
| Read `/auth/me` | Active session required. |
| Read `/auth/csrf` | Active session required. |
| Access placeholder `/overview` | Active session required. |

Admin-only Setup Status page and full Admin navigation can be introduced later. P0-00 may show minimal Admin label on `/overview`, but it must not expose management features.

### 10.5 Workspace Handling

1. `/setup/status`, `/auth/register`, and `/auth/login` do not require incoming `x-workspace-id`.
2. After session creation, API resolves the default Workspace and returns `x-workspace-id` in response headers.
3. `/auth/me` resolves the default Workspace from session user membership.
4. Web stores current Workspace in application state and sends `x-workspace-id` on later authenticated business APIs.
5. Missing `x-workspace-id` in P0 business APIs falls back to user default Workspace, but later slices must still document Workspace behavior explicitly.

---

## 11. Frontend Design

### 11.1 Routing

Implement these routes:

```text
/login
/register
/overview
```

Routing rules:

1. Anonymous user visiting `/overview` redirects to `/login`.
2. Authenticated user visiting `/login` or `/register` redirects to `/overview`.
3. Login success redirects to `/overview`.
4. Register success redirects to `/overview`.
5. Logout success redirects to `/login`.
6. Unknown routing behavior belongs to the routing Foundation doc or later UI slice; do not build a full app shell here.

P0-00 must not pull later shared Web infrastructure into this slice merely to match the eventual application shell. The R00 baseline does not yet contain the shared router, Tailwind styling foundation, or shared logo component used by the later frozen Web implementation. Until those shared dependencies are introduced by their own slices, P0-00 uses dependency-neutral browser-history routing and minimal semantic markup inside the auth components themselves. It must not introduce a one-off auth-only stylesheet or other disposable UI foundation solely for this slice.

### 11.2 Setup Status Usage

On app load for anonymous auth pages:

1. Call `GET /api/v1/setup/status`.
2. If `needsBootstrap=true`, show registration-oriented copy such as `Create Administrator`.
3. If `needsBootstrap=false`, show normal login/register copy.
4. If `allowSignup=false`, hide or disable ordinary registration entry after bootstrap.
5. If `hasDefaultWorkspace=false`, show a generic setup error and do not provide an in-browser repair flow.

This is copy and routing logic only. It is not a Setup Wizard.

### 11.3 Login Page

Fields:

1. Email.
2. Password.

Behavior:

1. Uses generated API client/types.
2. Shows field-level validation errors when available.
3. Shows generic login error for `INVALID_CREDENTIALS`.
4. Does not reveal account existence.
5. Disables submit while request is pending.
6. Does not persist CSRF token to localStorage.

### 11.4 Register Page

Fields:

1. Email.
2. Display name.
3. Password.

Behavior:

1. Uses the same page for first Admin and later self-registration.
2. When `needsBootstrap=true`, change button copy to `Create Administrator`.
3. When `needsBootstrap=false`, button copy can be `Create account`.
4. Shows `EMAIL_ALREADY_EXISTS` as a branch that offers login.
5. Shows `PASSWORD_POLICY_VIOLATION` on password field.
6. Shows `SIGNUP_DISABLED` as a contact-administrator message.
7. Does not implement invite code, email verification, profile upload, or setup steps.

### 11.5 Placeholder Overview

The placeholder Overview displays only:

1. Current user display name.
2. Current user email.
3. Current user role.
4. Default Workspace name.
5. Logout action.

It must not show:

1. Run statistics.
2. Resource summaries.
3. Quick links to Scenario/Test Plan/Run creation.
4. Admin health dashboard.
5. User management links.
6. Workspace switcher.

### 11.6 Client State

Recommended minimal client state:

```text
AuthState:
  user
  defaultWorkspace
  csrfToken in memory only
```

Rules:

1. Session is represented by cookie, not localStorage token.
2. CSRF token should stay in memory. If lost on refresh, call `/auth/csrf`.
3. The generated API client should attach `x-csrf-token` to write requests after login/register/csrf recovery.
4. The generated API client should attach `x-workspace-id` after default Workspace is known.
5. Web must not read `surgepilot_session` directly.

---

## 12. Implementation Plan

Recommended order:

1. Add migration `0001_p0_00_auth_workspace.py`.
2. Add ORM models and repository helpers.
3. Add password hashing utility using Argon2id.
4. Add session service and cookie handling.
5. Add CSRF service.
6. Add account-level login brute-force guard using 06 step lockout.
7. Add Pydantic schemas.
8. Add FastAPI routes.
9. Export OpenAPI and generate Web client/types.
10. Implement Web auth pages and placeholder Overview using generated client/types.
11. Add unit tests.
12. Add API tests.
13. Add contract tests.
14. Add Playwright smoke test.
15. Run `make verify` or documented bootstrap verification subset.

Hard implementation rule:

```text
No Web code that calls these Auth APIs may be submitted before OpenAPI export and generated Web client/types exist.
```

AI Coding must not implement Web forms against hand-written request/response types. Contract must lead implementation.

---

## 13. Tests

### 13.0 Unit Tests

Create service-level unit tests under `apps/api/tests/`.

Required coverage:

1. Argon2id hash and verify success.
2. Argon2id verify failure.
3. Password policy success and failure.
4. Email normalization and uniqueness helper behavior.
5. First Admin role assignment.
6. Later User role assignment.
7. `ALLOW_SIGNUP=false` after bootstrap rejects new self-signup.
8. First Admin bootstrap bypasses `ALLOW_SIGNUP`.
9. Session creation, lookup, revocation, absolute expiration, and idle expiration.
10. CSRF success, missing token, and invalid token.
11. Login failure count and step lockout state, with separate assertions:
    - 4th failure does not set `locked_until`.
    - 5th failure sets `locked_until` to roughly `now + 5 minutes`.
    - 10th failure sets `locked_until` to roughly `now + 30 minutes`.
12. Workspace membership resolution.
13. Workspace-aware repository filters for auth-owned queries where applicable.

Credential encryption/decryption and credential response serialization tests belong to the Load Node / credential slice, not P0-00.

### 13.1 API Tests

Create tests under `apps/api/tests/` with a `p0_00` marker or naming convention.

Required coverage:

#### Setup status

1. Empty users table returns `needsBootstrap=true`.
2. Existing user returns `needsBootstrap=false`.
3. `ALLOW_SIGNUP=false` still returns `allowSignup=true` when `needsBootstrap=true`.
4. `ALLOW_SIGNUP=false` returns `allowSignup=false` after bootstrap.
5. Response does not expose user count, email, environment, or secrets.

#### Register

1. First registration creates Admin.
2. First registration creates default Workspace membership.
3. Later registration creates User when signup allowed.
4. `ALLOW_SIGNUP=false` blocks later registration.
5. Duplicate email returns `EMAIL_ALREADY_EXISTS`.
6. Invalid password returns `PASSWORD_POLICY_VIOLATION`.
7. Invalid email returns `VALIDATION_ERROR`.
8. Register response sets cookie and returns `csrfToken`.
9. Concurrent first registration cannot create two Admin users.

#### Login

1. Valid credentials create a new session.
2. Multiple logins for same user create multiple active sessions.
3. Invalid credentials return `INVALID_CREDENTIALS`.
4. Missing email / wrong password / lockout all use the same public error branch.
5. Successful login resets failed-login counters and clears `locked_until`.
6. Login returns `csrfToken`.
7. Lockout follows the 06 step thresholds.
8. Lockout writes an audit event without secrets.

#### Logout

1. Valid session logout revokes only current session.
2. Other sessions remain active.
3. Repeated logout returns `204`.
4. No-session logout returns `204`.
5. Logout clears cookie.
6. Missing CSRF returns `CSRF_TOKEN_REQUIRED` when a valid session exists.
7. Invalid CSRF returns `CSRF_TOKEN_INVALID` when a valid session exists.

#### Me and CSRF

1. `/auth/me` returns user and default Workspace for active session.
2. `/auth/me` returns `UNAUTHENTICATED` without session.
3. `/auth/me` returns `UNAUTHENTICATED` for absolute-expired session.
4. `/auth/me` returns `UNAUTHENTICATED` for idle-expired session.
5. `/auth/me` does not return `csrfToken`.
6. `/auth/csrf` returns token for active session.
7. `/auth/csrf` returns `UNAUTHENTICATED` without session.

#### Security

1. Password hash is not returned.
2. Session cookie value is not returned in JSON.
3. CSRF token is returned only by explicit auth endpoints.
4. Error details do not include secrets.
5. Response includes `x-request-id`.
6. `sessions` rows do not include IP or User-Agent columns.
7. Audit events use `details_json`, not `metadata`.

### 13.2 Contract Tests

Required checks:

1. OpenAPI exports successfully.
2. Operation IDs exist and are stable:
   - `getSetupStatus`
   - `register`
   - `login`
   - `logout`
   - `getCurrentUser`
   - `getCsrfToken`
3. OpenAPI uses `/v1/...` paths under server `/api`.
4. Request and response schemas use `camelCase`.
5. Write endpoints document `x-csrf-token` where applicable.
6. Error response schema is consistent.
7. New slice-specific error codes appear in the Slice registry.
8. `INVALID_CREDENTIALS`, `CSRF_TOKEN_REQUIRED`, and `CSRF_TOKEN_INVALID` are referenced but not re-registered by this slice.
9. Generated Web client/types are fresh.

### 13.3 Web Tests

Minimum:

1. Login form renders.
2. Register form renders.
3. Register button copy changes to `Create Administrator` when `needsBootstrap=true`.
4. Placeholder Overview displays user and Workspace from `/auth/me`.
5. Logout clears UI state and routes to `/login`.

### 13.4 E2E Smoke

Create:

```text
tests/e2e/p0_00_auth_workspace.spec.ts
```

Scenario:

```text
Given the database is migrated and has no users
When the browser opens /register
And setup status says bootstrap is needed
And the user registers with email, displayName, and valid password
Then the app navigates to /overview
And /overview shows the user's display name
And /overview shows Default Workspace
When the user clicks logout
Then the app navigates to /login
When the user logs in again
Then /overview shows the same user and Workspace
```

Only this one happy-path smoke is required as E2E in P0-00. Edge cases belong to unit, API, and component tests.

---

## 14. Done When

This slice is done only when all of the following are true:

1. `docs/sdd/slices/P0-00-auth-workspace-admin-setup.md` is merged.
2. Alembic migration creates all five tables and default Workspace seed.
3. `sessions` has no IP or User-Agent columns.
4. `workspaces` has no unused `slug` column.
5. `workspace_members` has no duplicated role column.
6. `audit_events` uses `details_json`, includes `ip_address` and `user_agent`, and keeps `request_id` nullable at DB level.
7. API endpoints are implemented exactly as specified.
8. Passwords use Argon2id.
9. Session cookie is `HttpOnly`, `SameSite=Lax`, and production `Secure`.
10. Session expiry enforces both absolute 7 days and idle 24 hours.
11. CSRF token flow works for register, login, refresh recovery, and authenticated write requests.
12. CSRF failures use `CSRF_TOKEN_REQUIRED` and `CSRF_TOKEN_INVALID`.
13. First user becomes Admin; later users become User.
14. `ALLOW_SIGNUP=false` blocks only post-bootstrap self-registration.
15. Login brute-force guard follows the 06 step thresholds.
16. Multiple sessions per user are supported.
17. Logout invalidates only current session and is idempotent.
18. Web uses generated client/types only.
19. `/login`, `/register`, and placeholder `/overview` work.
20. No P1/P2 auth, user management, Workspace management, Setup Wizard, or business CRUD is implemented.
21. Unit tests for `p0_00` pass.
22. API tests for `p0_00` pass.
23. Contract tests pass.
24. Web typecheck passes.
25. Playwright smoke `tests/e2e/p0_00_auth_workspace.spec.ts` passes.
26. `make generate-contracts` leaves no uncommitted diff in `packages/contracts`.
27. `make verify` passes.

If M0 bootstrap does not yet support the full final `make verify`, this slice must document and pass the temporary verification command, and must state the exact follow-up task that folds it back into `make verify` before P0-01 begins.

Recommended temporary bootstrap minimum:

```bash
make migrate
make generate-contracts
git diff --exit-code packages/contracts
pytest -k "p0_00"
pnpm --filter web typecheck
pnpm e2e -- p0_00_auth_workspace.spec.ts
```

## 15. Implementation Backfill

P0-00 Web implementation facts:

1. Web implements `/login`, `/register`, and `/overview` with React Router and generated `@surgepilot/contracts/web-client` schema types.
2. CSRF is held in memory only; after refresh, logout recovers it through `/auth/csrf`.
3. The placeholder `/overview` shows only current user identity, role, default Workspace name, and logout.
4. `make verify-e2e` runs the P0-00 Playwright smoke `tests/e2e/p0_00_auth_workspace.spec.ts`.
5. The Playwright smoke uses a temporary SQLite database initialized by `scripts/setup_e2e_db.py` and does not require PostgreSQL for this slice-level browser check.

---

## 16. AI Coding Checklist

Before implementing, AI Coding must read:

1. `docs/sdd/00-product-scope-and-priority.md`
2. `docs/sdd/01-architecture-overview.md`
3. `docs/sdd/02-repo-structure-and-dev-workflow.md`
4. `docs/sdd/04-api-contract-guidelines.md`
5. `docs/sdd/06-security-permission-workspace.md`
6. `docs/sdd/slices/P0-00-auth-workspace-admin-setup.md`
7. Relevant `AGENTS.md`

Implementation checklist:

- [ ] Do not invent API shapes.
- [ ] Do not hand-write Web API types.
- [ ] Do not start Web API integration before generated client/types exist.
- [ ] Do not return DB `snake_case` fields from API.
- [ ] Do not expose password hash, session token, CSRF hash, cookie value, or secret values.
- [ ] Do not store IP or User-Agent in `sessions`.
- [ ] Do not add `workspaces.slug` in P0-00.
- [ ] Do not add role to `workspace_members` in P0-00.
- [ ] Do not add `SESSION_SECRET` or `CSRF_SECRET` for token hash pepper in P0-00.
- [ ] Do not implement Setup Wizard.
- [ ] Do not implement User Management UI or endpoints.
- [ ] Do not implement Workspace switching or management.
- [ ] Do not implement OAuth/OIDC/SSO.
- [ ] Do not implement generic rate-limit framework.
- [ ] Do not implement business CRUD in P0-00.
- [ ] Keep API messages and examples in English.
- [ ] Regenerate contracts after API schema changes.
- [ ] Run tests before marking complete.

---

## 16. Final AI Reading Summary

Build only this:

```text
register/login/logout/me/csrf
setup status
users/sessions/workspaces/workspace_members/audit_events migration
default Workspace seed
login/register/placeholder overview
p0_00 unit + API + contract + smoke tests
```

Do not build this:

```text
Setup Wizard
User Management
Workspace switching
Workspace management
profile editing
password reset
email verification
OAuth/OIDC/SSO
CAPTCHA
generic rate limiting
business CRUD
full Admin Setup Status dashboard
unused slug or role columns
session IP/User-Agent columns
```

The correct P0-00 success signal is a small but real vertical slice: first Admin can register, session and CSRF work, absolute and idle expiry are enforced, default Workspace is visible, logout works, and all contracts/tests are fresh.
