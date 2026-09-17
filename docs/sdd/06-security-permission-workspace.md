# 06 Security, Permission and Workspace

- Documentation status: Draft v2
- Project: SurgePilot performance load testing platform
- Document location: `docs/sdd/06-security-permission-workspace.md`
- Product source: `docs/prd/PRD.md`
- Range constraint: `docs/sdd/00-product-scope-and-priority.md`
- Architecture source: `docs/sdd/01-architecture-overview.md`
- Workflow source: `docs/sdd/02-repo-structure-and-dev-workflow.md`
- API contract source: `docs/sdd/04-api-contract-guidelines.md`
- Current delivery target: P0 baseline + active P2-02 Public API Substrate + P2-03 Env Group Secret + P2-04 Help AI Agents and System OpenAPI Bootstrap + ADR-0013 static Marketing Landing and Logo + P1-09 Scenario Global Configuration authorization
- Scope of application: Foundation SDD, P0-00 Auth / Workspace / Admin Setup, Load Node, Run, API implementation, Web client, AI Coding, Code Review
- Naming instructions: Starting from this article, user-oriented, document description and runtime naming are unified using **SurgePilot**. The existing directory structure, file path and locked project name are retained according to the actual project agreement, and can be cleaned and converged through independent renaming later.

---

## 1. Purpose

This article defines the account, security, permissions, Workspace isolation, and sensitive credential protection rules for the SurgePilot P0 phase.

This article only answers global baseline questions:

1. Security boundaries for local accounts, registration, login, logout and session;
2. The life cycle and verification boundary of CSRF token;
3. `admin` / `user` back-end authorization rules for two-level roles;
4. Default Workspace initialization, parsing and isolation rules;
5. Encryption, update and anti-echo rules for Private Load Node SSH credentials;
6. P0 minimal auditing, error codes, testing and review rules.

This article does not expand on the specific business CRUD fields, does not define the complete endpoint schema, does not define the complete Run state machine, does not define the MinIO object key and path security algorithm, and does not define the complete front-end page interaction.

Enter the specific content:

- `03-domain-model-overview.md`: Overview of domain model and table relationships;
- `04-api-contract-guidelines.md`: API URL, headers, error response, OpenAPI rules;
- `05-runner-protocol-and-run-state-machine.md`: Runner Protocol, Run state machine, Stop, heartbeat, self-healing, node lease;
- `07-storage-artifacts-minio.md`: MinIO, Dependency File, artifacts, path security;
- `09-testing-and-acceptance-strategy.md`: test matrix, CI and acceptance strategy;
- `docs/sdd/slices/*.md`: The specific endpoint, request, response, error code and Done When of each P0 Slice.

---

## 2. Authority and Conflict Resolution

### 2.1 Canonical Inputs

This article relies on the following documents:

1. `docs/prd/PRD.md`: The only product source for product scope, terminology, priority and acceptance criteria;
2. `docs/sdd/00-product-scope-and-priority.md`: P0/P1/P2 scope gate;
3. `docs/sdd/01-architecture-overview.md`: P0 architecture, component boundaries and security basic rules;
4. `docs/sdd/02-repo-structure-and-dev-workflow.md`: repository structure, environment variables, contracts and verify rules;
5. `docs/sdd/04-api-contract-guidelines.md`: REST, headers, OpenAPI, error response and API contract rules.

### 2.2 Conflict Resolution

Conflict handling rules:

1. If this article conflicts with `docs/prd/PRD.md`, the PRD shall prevail.
2. If this article conflicts with `docs/sdd/00-product-scope-and-priority.md`, 00 shall prevail unless 00 conflicts with PRD.
3. If this article conflicts with `docs/sdd/01-architecture-overview.md`, the architectural boundary of 01 shall prevail, and this article shall be revised simultaneously.
4. If this article conflicts with `docs/sdd/04-api-contract-guidelines.md`, the API URL, header, error shape, OpenAPI rules and core error registry shall be subject to 04, and this article shall be revised simultaneously.
5. Slice SDD can add specific endpoints, schemas, permission judgments and error codes, but it cannot destroy the global security and permission rules of this article.
6. Code implementation must not override the rules of this article on the grounds of "already implemented", "front-end convenience", "hidden entrance" or "configuration closed"; the SDD must be revised or the ADR must be recorded first.

---

## 3. Confirmed Security Decisions

| Area | Decision |
| --- | --- |
| Product name in this document | SurgePilot |
| P0 auth model | Local email + password |
| First Admin bootstrap | Always allowed when no user exists; bypasses `ALLOW_SIGNUP` |
| First user | First successful registered user becomes `admin` |
| Later users | Default role is `user` |
| Signup switch | `ALLOW_SIGNUP=true` by default; after bootstrap, `false` means no additional self-signup in P0 |
| Admin-created users / invite links | Not implemented in P0 |
| User management UI / API | Not implemented in P0 |
| Email verification / password reset | Not implemented in P0 |
| Roles | Only global `admin` and `user` |
| Resource-level owner permission | Not implemented in P0 |
| Workspace model | One Default Workspace in P0; business data is Workspace-aware from day 1 |
| Workspace implementation | Single PostgreSQL database and schema; business tables carry `workspace_id`; application layer enforces filters |
| PostgreSQL RLS | Not implemented in P0 |
| Multi-schema / multi-database tenancy | Not implemented in P0 |
| Workspace membership | Use `workspace_members`; P0 auto-adds every user to Default Workspace; no membership UI/API |
| Workspace header | `x-workspace-id`; no Workspace ID in route path |
| Missing Workspace header in P0 | Resolve to current user's Default Workspace; fail only when no default can be resolved |
| Session storage | PostgreSQL-backed server-side sessions |
| Session cookie name | `surgepilot_session` |
| Session cookie path | `/` |
| Session expiry | Absolute expiry 7 days + idle sliding expiry 24 hours |
| Session invalidation | Logout invalidates current session server-side |
| Password hashing | Argon2id |
| Password policy | Minimum 10 characters; must contain at least one letter and one digit |
| Login brute-force guard | Account-level failure count and lockout; no Redis / IP rate-limit framework |
| Public login failure response | Generic `INVALID_CREDENTIALS`; do not reveal whether email exists or account is locked |
| CSRF | Session-bound CSRF token; `x-csrf-token` on browser write requests after session exists |
| CSRF exempt writes | Register, login, pre-session bootstrap endpoints, and P2-02 PAT Bearer public API writes under `/api/public/v1/*` |
| CSRF token retrieval | A dedicated Auth API may return token; login may also return `csrfToken` to save one round trip |
| P2-02 Account credentials page | `/account/api-keys`; self-service for `user` and `admin`, not Admin navigation |
| P2-02 Account credential API | `/api/v1/account/api-tokens`; session-authenticated and self-only |
| P2-02 Account credential CSRF | `POST` and `DELETE` require `x-csrf-token`; `GET` does not |
| P2-02 public API auth | `/api/public/v1/*` requires PAT Bearer and must not accept browser cookie session |
| P2-02 public scopes | `read`, `config:write`, `run`, `dependency:write`; no `tokens:write`; `dependency:write` only governs public Dependency File upload/delete |
| P2-02 public Workspace fallback | Explicit `x-workspace-id`, or single Workspace from PAT allowlist only; no browser default fallback |
| Private Load Node credential storage | AES-256-GCM using Python `cryptography`; key from environment variable |
| Credential encryption key | `SSH_CREDENTIAL_ENCRYPTION_KEY`, base64 encoded 32 bytes |
| Credential update | Explicit action endpoint; credentials are write-only and must be re-entered fully |
| Credential rotation | Not implemented in P0 |
| Audit log | Minimal security and execution-control events; no UI and no auto cleanup in P0 |
| General sensitive data masking framework | Not implemented in P0; obvious secret leakage is still forbidden |

Description:

1. `ALLOW_SIGNUP=false` will close the new user entrance of P0 after there is an Admin. Since P0 does not implement Admin user creation or invitations, this is an explicit "closed/single admin mode" deployment choice.
2. Setup Status must prompt this status to avoid the deployer mistakenly thinking that users can still be added through the UI/API.
3. If the deployment target requires the cooperation of multiple people, P0 recommends keeping `ALLOW_SIGNUP=true` and relying on password policies, login blast protection, and intranet deployment boundaries to reduce risks.

---

## 4. Scope and Non-Goals

### 4.1 In Scope

P0 must implement or enforce:

1. local signup / login / logout / current user identity;
2. First Admin bootstrap and default User assignment;
3. PostgreSQL-backed server-side sessions;
4. Argon2id password hashing and basic password policy;
5. account-level login brute-force protection;
6. session-bound CSRF protection for browser write APIs;
7. backend role checks for `admin` / `user`;
8. Default Workspace initialization and application-layer data isolation;
9. Private Load Node credential encryption and write-only behavior;
10. minimal audit events for security-relevant actions.

### 4.2 Out of Scope

P0 does not implement:

1. OAuth / OIDC / SAML / LDAP / SSO;
2. email verification, email invite, forgot-password mail flow;
3. Admin user management UI or Admin-created user API;
4. Workspace switching UI, Workspace member management, Workspace owner roles;
5. resource-level owner / creator permission model;
6. PostgreSQL RLS, multi-schema tenancy, multi-database tenancy;
7. Redis, distributed cache, external rate-limit service;
8. IP-based global rate-limit framework;
9. secret Env Group, secret snapshot encryption, key rotation;
10. general-purpose log redaction framework;
11. audit log UI, audit export, audit retention cleanup.

---

## 5. Authentication and Account Model

### 5.1 Account Fields

P0 User needs to express at least:

| Field | Rule |
| --- | --- |
| `id` | ULID string |
| `email` | globally unique; stored lower-case |
| `password_hash` | Argon2id hash only; never returned |
| `display_name` | non-secret display field |
| `role` | `admin` or `user` |
| `status` | P0 may store `active`; disable/enable behavior is P1 |
| `created_at` | UTC timestamp |
| `last_login_at` | UTC timestamp, nullable |
| `failed_login_count` | integer, for account-level lockout |
| `locked_until` | UTC timestamp, nullable |

Rules:

1. Unify lower-case and trim when registering and logging in via email.
2. Email uniqueness is guaranteed by database unique constraints.
3. The API must not return `password_hash`.
4. P0 does not expose user disable / enable API; if the `status` field is retained, P0 only requires new users to be `active`.
5. When P1 enables user disabling, user login, old session processing and testing must be additionally disabled.

### 5.2 Signup and Bootstrap Rules

Rules:

1. When the system does not have any users, the first successfully registered user must become `admin`.
2. First Admin bootstrap must bypass `ALLOW_SIGNUP`, otherwise the deployment with closed registration cannot be initialized.
3. When the system already has a user and `ALLOW_SIGNUP=true`, the subsequent registered user defaults to `user`.
4. When the system already has users and `ALLOW_SIGNUP=false`, P0 does not allow ordinary users to self-register.
5. P0 does not implement Admin to create users, invite links or reset passwords.
6. P0-00 Slice is responsible for defining specific Auth endpoints, request / response schema, form verification and UX.
7. Setup Status must display the `ALLOW_SIGNUP` status, and indicate "P0 has no new user entry" when there is an Admin and `ALLOW_SIGNUP=false`.
8. ADR-0016/P2-04 may use the serialized first-user decision only as an explicit return value from `register_user`. The service keeps ownership of the registration commit; the route must not infer the bootstrap event from `role == "admin"`.
9. The P2-04 system OpenAPI import runs only after registration commit, through an independent `SessionLocal` transaction. OpenAPI generation, MinIO writes, and API Catalog creation must not occur under the first-user table lock or nested registration transaction.
10. P2-04 import failure is best-effort and must not revoke or roll back the successfully committed first Admin, membership, session, or registration audit.

### 5.3 Login Behavior Rules

Rules:

1. A server-side session must be created for successful login.
2. If the login is successful, the CSRF token can be returned at the same time, reducing one front-end request.
3. A generic error must be used if login fails, and the existence of the email must not be exposed.
4. If the password is incorrect, the email does not exist, or the account is in the lockout period, the same type of `INVALID_CREDENTIALS` should be returned to the client.
5. Audit logs must be written for lock period hits and newly triggered locks, but the lock status must not be exposed through public error codes.
6. `failed_login_count` and `locked_until` must be reset after successful login.
7. The login response must not return the session cookie value; the cookie value is only set through the `Set-Cookie` header.

### 5.4 Logout and Current User Rules

Rules:

1. Logout must delete or invalidate the current server-side session.
2. Logout does not require invalidating sessions on other devices.
3. P0 does not implement "logout all devices".
4. Current-user API must return the current user identity, role and default Workspace context.
5. Current-user API does not consume `x-workspace-id`, nor does it require business Workspace resolution.
6. Current-user API does not return session token, CSRF token, password hash, credential or other secrets.

---

## 6. Password Storage and Policy

### 6.1 Password Hashing

P0 must use an Argon2id to hold the password hash.

Recommended Python library: `argon2-cffi` .

P0 lowest parameter baseline:

```text
memory_cost >= 19456 KiB
time_cost >= 2
parallelism >= 1
hash_len >= 32 bytes
salt_len >= 16 bytes
```

Rules:

1. Do not save clear text passwords.
2. Do not use reversible encryption to save login passwords.
3. Unsalted hash is not allowed.
4. MD5, SHA1, SHA256, bcrypt-sha256 homemade combinations, etc. are not allowed to be used instead of Argon2id.
5. Parameters can be improved in Slice SDD or implementation, but must not be lower than the baseline of this article.
6. If the password hash verify fails, generic login failure must occur, and the underlying exception must not be leaked.

### 6.2 Password Policy

P0 password rules:

| Rule | Decision |
| --- | --- |
| Minimum length | 10 characters |
| Required categories | At least one letter and one digit |
| Special character | Not required |
| Upper/lower case mix | Not required |
| Password history | Not implemented in P0 |
| Breached password check | Not implemented in P0 |

Rules:

1. Password policy errors are expressed in field validation during registration or future password change scenarios.
2. API error message still uses English fallback as 04.
3. The frontend can prompt locally, but the backend must force verification.

### 6.3 Password Change and Reset

P0 does not implement:

1. self-service password change;
2. forgot password;
3. email reset link;
4. Admin reset password.

If subsequent P1 introduces password changes or password resets, the following must be added:

1. Re-verify the old password or Admin permission;
2. Password policy verification;
3. Whether to invalidate other sessions;
4. `auth.password_changed` or `auth.password_reset` audit event;
5. Related API contracts and E2E tests.

---

## 7. Session Model

### 7.1 Session Storage

P0 uses a PostgreSQL-backed session.

Recommended minimum fields:

| Field | Rule |
| --- | --- |
| `id` | ULID or internal random ID |
| `session_token_hash` | recommended; hash of cookie token |
| `user_id` | FK to users |
| `csrf_token_hash` | recommended; hash of random CSRF token bound to this session |
| `created_at` | UTC timestamp |
| `last_seen_at` | UTC timestamp |
| `expires_at` | UTC timestamp |
| `revoked_at` | UTC timestamp, nullable |

Rules:

1. Store high-entropy random session token in Cookie.
2. It is recommended to save `session_token_hash` and `csrf_token_hash` in DB instead of clear text session token or clear text CSRF token; if the token is saved directly, the reason must be explained in Slice Review.
3. Session lookup executes `SHA-256(cookie session token)` and then matches `session_token_hash`, and checks `revoked_at`, `expires_at` and idle expiry at the same time.
4. After CSRF verification is executed, `SHA-256(x-csrf-token)` matches the `csrf_token_hash` of the current session.
5. Each authenticated request can update `last_seen_at` without premature P0 performance optimization.
6. P0 does not repeatedly store `ip_address` / `user_agent` in the sessions table; if auditing is required, write audit_events.

### 7.2 Expiration

P0 uses:

```text
absolute expiry: 7 days after session creation
idle sliding expiry: 24 hours after last_seen_at
```

Rules:

1. When any expiration condition is met, the session becomes invalid.
2. Expired sessions cannot be automatically renewed.
3. Logging out of an ordinary user will only invalidate the current session.
4. P0 does not require the background to regularly clean up expired sessions; it can be cleaned up by subsequent maintenance tasks or manual DB maintenance.

### 7.3 Cookie Attributes

Session cookie:

| Attribute | Decision |
| --- | --- |
| Name | `surgepilot_session` |
| HttpOnly | Required |
| Secure | Required in HTTPS production; may be disabled only for local HTTP dev |
| SameSite | `Lax` |
| Path | `/` |
| Domain | Not set by default |

Rules:

1. API response does not return cookie value.
2. Logs, error details, OpenAPI examples, and test snapshots must not contain real cookie values.
3. The Web does not read the session cookie; the browser automatically carries it.
4. If deployed under the cross-site domain name model, ADR must be added to re-evaluate cookie, CORS and CSRF policies.

---

## 8. Login Brute-Force Protection

P0 uses account dimension failure count and lockout.

Recommended strategy:

```text
failed_login_count < 5       -> no lock
5 <= failed_login_count < 10 -> locked_until = now + 5 minutes
failed_login_count >= 10     -> locked_until = now + 30 minutes
```

Rules:

1. Do not introduce Redis, external rate-limit service or general IP current limiting framework.
2. The explosion-proof status is stored in `users.failed_login_count` and `users.locked_until`.
3. Successful login must clear the failure count and lock time.
4. The lock status still returns generic `INVALID_CREDENTIALS` to the client.
5. Write an audit event when a lock is triggered.
6. P0 does not implement Admin manual unlocking of UI/API; if necessary, it can be repaired by operation and maintenance through SQL.
7. Slice is not allowed to use Nginx rate limit instead of account dimension to prevent blasting.

---

## 9. CSRF Protection

### 9.1 Token Model

P0 uses Synchronizer Token: CSRF token is generated by API and bound to server-side session.

Rules:

1. The session token and CSRF token are generated when the login is successful; DB recommends saving the corresponding hash.
2. CSRF token has the same life cycle as session.
3. After logging out or session expiration, the old CSRF token must expire.
4. P0 does not perform per-request token rotate.
5. CSRF tokens must not be written to logs, error details, real values of OpenAPI examples or test snapshots.

### 9.2 Verification Rule

| Request type | CSRF required |
| --- | --- |
| `GET` / `HEAD` / `OPTIONS` | No |
| Authenticated browser `POST` / `PATCH` / `PUT` / `DELETE` | Yes |
| Register / login / first-admin bootstrap | No |
| Internal runner endpoints | No; use `x-runner-token` |
| P2-02 `/api/public/v1/*` PAT Bearer requests | No; use PAT auth, scope, actor status and Workspace membership checks |
| P2-02 `/api/v1/account/api-tokens` `POST` / `DELETE` | Yes; browser session self-service write |
| P2-02 `/api/v1/account/api-tokens` `GET` | No; safe browser session read |
| Health / readiness | No |

Rules:

1. Write requests must verify `x-csrf-token` unless it is a pre-session Auth endpoint or internal runner endpoint.
2. Register, login and first-admin bootstrap do not have an existing session and are therefore exempt from CSRF; they rely on password policies, account anti-explosion and deployment boundaries to reduce the risk of abuse.
3. Fixed error codes and fixed HTTP status must be used for missing tokens and token mismatches.
4. The Web client must save the CSRF token to JS memory after logging in and not write it to localStorage.
5. After refreshing the page, you can re-obtain the CSRF token of the current session through the Auth API.

---

## 10. Role Model and Permission Rules

### 10.1 Roles

P0 has only two global roles:

| Role | Meaning |
| --- | --- |
| `admin` | Platform administrator for setup checks and Public Load Node management |
| `user` | Normal user in Default Workspace |

Rules:

1. P0 does not introduce fine-grained roles such as Workspace Owner, Resource Manager, and Viewer.
2. P0 does not introduce resource creator / owner permissions.
3. The front-end can hide unauthorized entries, but the back-end must perform final permission verification.
4. Admins may not view or export Private Load Node cleartext credentials.

### 10.2 Permission Matrix

| Operation area | User | Admin | Notes |
| --- | --- | --- | --- |
| Login / logout / current user | Yes | Yes | Authenticated identity only |
| View Default Workspace context | Yes | Yes | P0 only one visible Workspace |
| Scenario / Test Plan / Env Group / Dependency File in current Workspace | Yes | Yes | Workspace filter required |
| Run / Run Report in current Workspace | Yes | Yes | Workspace filter required |
| Register and manage Workspace Private Load Node | Yes | Yes | Only current Workspace private nodes |
| View Private Load Node credential value | No | No | Write-only only |
| Create / edit / delete Public Load Node | No | Yes | Platform resource |
| Disable abnormal Public Load Node for platform safety | No | Yes | Public only; Private node actions stay within current Workspace rules |
| View Admin Setup Status | No | Yes | No secret values |
| Download official Public API AI skill source | Yes | Yes | Current authenticated user access; not Workspace-scoped; archive contains no user or Workspace data |
| User management | No | No | P1 |
| Workspace switching / member management | No | No | P1 |
| Resource-level owner-only delete | No | No | P1/P2 if ever needed |

### 10.3 Authorization Rules

1. Authorization must run in API backend, not only in Web.
2. Business service methods must receive explicit actor and Workspace context.
3. Do not infer permissions from frontend route visibility.
4. Public Load Node operations must check Admin role.
5. Private Load Node operations must check current Workspace access.
6. Cross-Workspace resource lookup must not leak resource existence.

---

## 11. Workspace Model

### 11.1 P0 Workspace Shape

P0 exposes only one Default Workspace to users, but all business data must be Workspace-aware from day one.

P0 Workspace-aware resources include at least:

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

1. Business queries must be filtered by Workspace.
2. Business creation must write the Workspace ID.
3. Operations such as update, delete, download, Stop, Validity mark, etc. must verify the Workspace.
4. Cross-workspace access must not return data from other workspaces.
5. Admin Setup Status is a platform-level read-only exception, but must not be extended to ordinary business resources.

### 11.2 Default Workspace Initialization

P0 uses Alembic migration seed and a fixed Default Workspace.

It is recommended to fix the seed ID:

```text
01HZW000000000000000000000
```

Rules:

1. The seed ID must be a legal ULID string.
2. The seed ID is written in the migration and is not randomly generated at runtime.
3. The default name is recommended `Default Workspace`.
4. The first Admin joins Default Workspace when registering.
5. Automatically join the Default Workspace during subsequent User registration.
6. Setup Status must check if Default Workspace exists.
7. ADR-0016/P2-04 may create one system-owned API Catalog asset in Default Workspace only after the first Admin and membership commit. The import uses the committed first Admin ID as `created_by`, the committed Default Workspace ID as `workspace_id`, and an independent transaction.

### 11.3 Membership

P0 uses the `workspace_members` table as the source of user-workspace relationships.

Minimal relation:

```text
workspace_members(workspace_id, user_id, joined_at)
unique(workspace_id, user_id)
```

Rules:

1. P0 does not use `users.default_workspace_id` as a second set of sources.
2. P0 The current user's default Workspace is resolved through the user's unique membership.
3. If there is no membership, Workspace resolution fails.
4. P0 does not expose Workspace membership UI/API.
5. P1 multi-workspace UI can be extended on this basis without migrating user table fields.

### 11.4 Workspace Header

Business API usage:

```http
x-workspace-id: <workspaceId>
```

Rules:

1. API route path does not contain Workspace ID.
2. The web must send `x-workspace-id` after knowing the current workspace.
3. When the P0 header is missing, the API resolves to the current user's Default Workspace.
4. The API response must write back the actual `x-workspace-id` used.
5. When the header is missing, has a wrong format, or the default Workspace cannot be parsed, `400 WORKSPACE_REQUIRED` is returned.
   - "Unable to resolve default Workspace" in P0 should generally not occur; if it occurs, it means the Default Workspace seed, membership, or bootstrap data is inconsistent.
6. When the header is legal but the current user does not have permission to access the Workspace, `403 WORKSPACE_ACCESS_DENIED` is returned.
7. When accessing business resources of other Workspaces through resource IDs, it is recommended to return `404 RESOURCE_NOT_FOUND` to avoid leaking the existence of resources.
8. Health, Auth login / logout / register / current-user / CSRF token retrieval does not require business Workspace header.

### 11.5 Public and Private Load Node Boundary

Load Node needs to support both Public and Workspace Private.

Recommended field combinations:

```text
scope: public | workspace
workspace_id: nullable
```

Rules:

1. `scope=public` represents the public node of the platform and can only be managed by Admin.
2. `workspace_id` must be `NULL` when `scope=public` is used.
3. `scope=workspace` represents the Workspace Private node.
4. `workspace_id` must be the current Workspace ID when `scope=workspace` is used.
5. The query must first branch on `scope`, and then decide whether to filter `workspace_id`.
6. Do not use virtual Public Workspace.
7. When a Public Load Node is assigned to a Run, it must still be verified through the Run creation permissions and resource rules of the current Workspace.

---

## 12. Private Load Node Credential Protection

### 12.1 Credential Scope

Private Load Node credentials include but are not limited to:

1. SSH password;
2. SSH private key;
3. private key passphrase;
4. future node bootstrap token if any.

Rules:

1. The credentials must not be echoed back in plain text after being saved.
2. Admins are also not allowed to view or export Private Load Node credentials.
3. API response does not return clear text credentials, ciphertext, nonce, tag or key ID.
4. Web does not persist credentials.
5. MUST NOT appear in credential logs, error details, audit details and test snapshots.

### 12.2 Encryption

P0 uses AES-256-GCM to encrypt credentials.

| Item | Decision |
| --- | --- |
| Library | Python `cryptography` |
| Algorithm | AES-256-GCM |
| Master key | `SSH_CREDENTIAL_ENCRYPTION_KEY` |
| Key format | base64 encoded 32 bytes |
| Nonce | random 96-bit per encryption |
| Key rotation | Not implemented in P0 |

Rules:

1. Does not self-implement encryption algorithms.
2. Not using pycryptodome as the preferred implementation.
3. When the environment variable is missing or has an incorrect format, the API/Worker must fail to start or enter the not-ready state.
4. Decryption failure is due to server configuration or data corruption issues, and the underlying exception should not be returned to the frontend.
5. AAD can use `load-node-credential:v1:{node_id}` as a recommendation but not mandatory for P0.

### 12.3 Credential Storage

It is recommended to store credentials in a separate table or separate JSON field, but it must meet the following requirements:

1. Does not share fields with ordinary Load Node response schema.
2. `workspace_id` is not stored redundantly; Workspace is derived from the `load_nodes` relationship.
3. The list / get API is not allowed to return cryptographic material.
4. Only the service layer connected to the Load Node is allowed to read and decrypt.
5. The decrypted plaintext is only retained in function local variables, and the reference is released as soon as possible after use.

### 12.4 Credential Update

Rules:

1. Credential updates must use explicit action endpoints and cannot be mixed in ordinary fields through general PATCH.
2. To update credentials, complete credentials must be resubmitted.
3. Partial update of password / private key / passphrase is not supported.
4. An empty string must not be interpreted as "keep old value".
5. Log audit events after a successful update, but do not log the credential content.
6. The specific endpoint path, request schema and permission details are defined by Load Node Slice.

---

## 13. Sensitive Value Handling

### 13.1 Sensitive Data Blacklist

| Sensitive value | Allowed location | Forbidden location |
| --- | --- | --- |
| Password plaintext | request body only, transient | response, logs, audit details, snapshots |
| Password hash | DB only | response, logs, OpenAPI examples |
| Session token | HttpOnly cookie only | response body, logs, snapshots |
| CSRF token | Auth response and JS memory; DB hash only | logs, error details, persistent browser storage |
| Runner token | env var and runner request header | Web, public OpenAPI, logs |
| SSH password / private key / passphrase | encrypted DB + transient service memory | response, logs, audit details |
| Credential encryption key | env var only | DB, response, logs, frontend bundle |
| MinIO access / secret key | server env only | Web, response, logs |
| MinIO object key | server-side storage logic | public API response unless explicitly required by 07 |
| Stack trace / SQL error | server logs | API error body |
| Server absolute path | server logs only when needed | API response and frontend |
| AI skill source directory candidates | server-side resolver only | API response, OpenAPI examples, frontend, archive metadata |

### 13.2 Logging Rules

1. Structured logs must include request ID.
2. Logs may include user ID, Workspace ID, resource ID and event type.
3. Logs and audit records may include normalized IP and truncated user agent for abuse investigation.
4. Logs must not include token values, passwords, credentials or encryption keys.
5. P0 does not implement a generic masking framework, but code review must reject obvious secret leaks.
6. P2-04 skill bundle and bootstrap logs may include safe user/Workspace/spec identifiers and a bounded SHA-256 prefix, but must not include candidate filesystem paths, archive bytes, OpenAPI payload, full MinIO object keys, cookies, PATs, or CSRF values.

### 13.3 Error Response Rules

1. Error response must follow 04 shape: `{code, message, requestId, details?}`.
2. `message` must be safe English fallback.
3. `details` must not include raw password, token, credential, SQL, traceback or server path.
4. Auth failure messages must be generic.

---

## 14. Audit Events

### 14.1 Purpose

The goal of the P0 audit log is to support minimal security traceback, not a full SIEM, reporting, or management UI.

### 14.2 Minimal Table Shape

Minimum field recommendations:

| Field | Rule |
| --- | --- |
| `id` | ULID |
| `event_type` | lower dot notation, registered by Slice |
| `actor_user_id` | nullable for failed login unknown user |
| `workspace_id` | nullable for platform-level events |
| `resource_type` | nullable |
| `resource_id` | nullable |
| `request_id` | nullable but recommended |
| `ip_address` | nullable |
| `user_agent` | nullable |
| `details_json` | safe metadata only |
| `created_at` | UTC timestamp |

### 14.3 Required Coverage Principles

P0 must cover the following types of events, the specific `event_type` string is registered by the corresponding Slice:

1. auth lifecycle: registration, login success, login failure, logout, account trigger lock;
2. setup lifecycle: first Admin bootstrap, Default Workspace initialization check;
3. credential lifecycle: Private Load Node credentials are created or updated;
4. platform resource changes: key changes to Public Load Node;
5. Execution control: Run stop request, validity change and other control actions defined by Run Slice.

Rules:

1. Ordinary Scenario / Test Plan / Env Group / Dependency File CRUD does not require full P0 audit.
2. Audit details must not contain credentials, tokens, or sensitive headers.
3. P0 does not implement audit log UI.
4. P0 does not implement automatic retention cleanup.
5. P0 does not implement audit export.

### 14.4 Execution-Control Audit Event Registry (P0 Required)

The following event types are mandatory in P0 for Run safety convergence:

1. `run.debug_requested`;
2. `run.stop_requested`;
3. `run.force_kill`;
4. `load_node.quarantined`.

Rules:

1. `run.debug_requested` should capture actor, runId, scenarioId, scenarioRevision, nodeId, workspaceId and requestId when available; it must not include Env values, Step body, script text, credentials or storage paths.
2. `run.stop_requested` should capture actor, runId, nodeId, workspaceId and requestId when available.
3. `run.force_kill` should capture trigger reason, timeout flag, success/failure and bounded stderr preview (no secrets).
4. `load_node.quarantined` should capture reason and recovery hint; correlate triggering Run via `details.runId` when present.
5. Runner token and other secrets must never appear in audit details.


---

## 15. API Error Codes

06 Only crosscut security error codes are locked. 04 Error codes existing in the core registry must not be redefined into other meanings in this article.

### 15.1 Global Security Error Codes

| Code | HTTP status | Meaning |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | User is not logged in or session is invalid |
| `INVALID_CREDENTIALS` | 401 | Email or password is invalid; also used for lockout public response |
| `FORBIDDEN` | 403 | User does not have required role or permission |
| `CSRF_TOKEN_REQUIRED` | 403 | Missing CSRF token for browser write request |
| `CSRF_TOKEN_INVALID` | 403 | CSRF token does not match current session |
| `WORKSPACE_REQUIRED` | 400 | Workspace context cannot be resolved |
| `WORKSPACE_ACCESS_DENIED` | 403 | User cannot access requested Workspace |
| `RESOURCE_NOT_FOUND` | 404 | Resource does not exist or is hidden by Workspace boundary |

Rules:

1. Each error code maps to exactly one HTTP status.
2. `INVALID_CREDENTIALS` intentionally covers unknown email, wrong password and account lockout public responses.
3. P0 public login flow does not expose `ACCOUNT_LOCKED`; lockout is represented to the client as `INVALID_CREDENTIALS` and to operators through audit logs.
4. Slice-specific auth errors such as `EMAIL_ALREADY_EXISTS`, `PASSWORD_POLICY_VIOLATION` and `SIGNUP_DISABLED` must be registered by P0-00 if needed, each with one fixed HTTP status.
5. If a Load Node Slice registers `CREDENTIAL_DECRYPT_FAILED`, it must map to `500` and must not expose the low-level decrypt exception.
6. `RUNNER_UNAUTHORIZED` remains owned by 04 / 05 internal runner contract, not by browser auth.

---

## 16. FastAPI Implementation Guidance

### 16.1 Dependencies

Recommended dependency layers:

```text
get_session_optional()
get_current_user()
get_current_workspace()
require_role("admin")
require_csrf()
```

Rules:

1. `get_current_user()` validates session and returns actor.
2. `get_current_workspace()` resolves `x-workspace-id` or P0 Default Workspace and checks membership.
3. `require_role("admin")` checks backend role before admin operation.
4. `require_csrf()` runs only after a session exists and only for CSRF-protected writes.
5. Pre-session writes such as register and login do not declare `require_csrf()` in their dependency chain.
6. Internal runner endpoints must not use browser session or CSRF dependencies.

### 16.2 Service Context

Business services must explicitly receive actor and workspace context.

Recommended call shape:

```text
service_method(actor=user, workspace=workspace, payload=payload)
```

Rules:

1. Do not read actor or workspace from module globals.
2. Do not trust frontend-sent user ID or role.
3. Do not allow repository methods to run Workspace-aware queries without Workspace filter unless explicitly platform-level.
4. Platform-level queries must be named or documented as platform-level.

### 16.3 Query Rules

1. List queries for Workspace resources must filter by `workspace_id`.
2. Detail queries must filter by both resource ID and `workspace_id`.
3. Update / delete queries must filter by both resource ID and `workspace_id`, or check ownership in the same transaction.
4. Public Load Node queries must branch by `scope`.
5. Private Load Node queries must filter by current Workspace.
6. Cross-Workspace resource IDs should result in `RESOURCE_NOT_FOUND`, not raw permission leakage.

---

## 17. Web Client Rules

1. Web uses generated API client/types from OpenAPI.
2. Web does not hand-write API request/response types.
3. Web sends `x-workspace-id` after current Workspace is known.
4. Web sends `x-csrf-token` for authenticated browser write requests.
5. Web stores CSRF token in memory, not localStorage.
6. Web does not read `surgepilot_session` cookie.
7. Web must treat `UNAUTHENTICATED` as login-expired and clear client-side auth state.
8. Web must not display or store Private Load Node credential values after submission.
9. Web may hide Admin navigation for non-admin users, but backend remains authoritative.

---

## 18. Runner and Internal Token Boundary

Runner callback authentication is separate from browser auth.

Rules:

1. Runner uses `x-runner-token` as defined by 04 / 05.
2. Runner endpoints do not use session cookie.
3. Runner endpoints do not use CSRF token.
4. Runner token is configured through environment variables.
5. Runner token must not appear in Web response, public OpenAPI examples, logs, audit details or frontend bundle.
6. Invalid runner token returns the runner-specific error defined by 04 / 05.
7. Runner must never access PostgreSQL directly.
8. Runner must never receive MinIO credentials in P0.

---

## 19. Tests

### 19.1 Unit Tests

P0 security unit tests must cover:

1. Argon2id hash and verify success;
2. Argon2id verify failure;
3. password policy success and failure;
4. email normalization and uniqueness;
5. first Admin role assignment;
6. later User role assignment;
7. `ALLOW_SIGNUP=false` after bootstrap rejects new self-signup;
8. first Admin bootstrap bypasses `ALLOW_SIGNUP`;
9. session creation, lookup, revocation and expiration;
10. CSRF success, missing token and invalid token;
11. login failure count and lockout state;
12. credential encryption and decryption;
13. credential response serialization excludes secrets;
14. workspace membership resolution;
15. Workspace-aware repository filters.

### 19.2 API Tests

P0 Auth / Workspace API tests must cover:

1. register first Admin;
2. register later User when signup is enabled;
3. reject later self-signup when signup is disabled;
4. login success creates session cookie;
5. login failure uses generic error;
6. logout invalidates session;
7. current-user response excludes secrets;
8. write request without CSRF fails;
9. write request with invalid CSRF fails;
10. pre-session register / login does not require CSRF;
11. missing Workspace header resolves to Default Workspace;
12. malformed Workspace header returns `WORKSPACE_REQUIRED`;
13. inaccessible Workspace returns `WORKSPACE_ACCESS_DENIED`;
14. cross-Workspace resource ID does not leak data;
15. User cannot manage Public Load Nodes;
16. Admin can manage Public Load Nodes;
17. no API returns credential ciphertext or plaintext.

### 19.3 Contract Tests

Contract tests must verify:

1. session cookie is HttpOnly, SameSite=Lax and Path=/;
2. authenticated write APIs document `x-csrf-token` requirement or explicitly mark exception;
3. public OpenAPI excludes internal runner endpoints;
4. response schemas do not expose password hash, session value, runner token or credential fields;
5. security error codes have fixed HTTP status;
6. generated Web client remains fresh.

### 19.4 E2E / Smoke Tests

P0 smoke should cover:

1. first Admin bootstrap → login → current user → Default Workspace resolved;
2. later User signup when enabled → Workspace membership exists;
3. User attempts Admin-only operation and is rejected;
4. Admin views Setup Status without secret values;
5. Private Load Node credential submission → later GET does not reveal value;
6. authenticated write without CSRF is rejected.

---

## 20. Done When

06 is implemented enough for P0 only when:

1. First Admin bootstrap works even if `ALLOW_SIGNUP=false`.
2. Later signup is possible only when `ALLOW_SIGNUP=true`.
3. Setup Status warns when existing Admin + `ALLOW_SIGNUP=false` means no P0 new-user entry.
4. Passwords are stored with Argon2id and never returned.
5. Sessions are PostgreSQL-backed and logout invalidates server-side session.
6. Session cookie is `surgepilot_session`, HttpOnly, SameSite=Lax, Path=/.
7. CSRF is required for authenticated browser writes and exempt for pre-session Auth endpoints.
8. Backend enforces `admin` / `user` permissions.
9. Business data queries are Workspace-aware.
10. Default Workspace is seeded with a fixed ULID.
11. `workspace_members` is the single membership source.
12. Private Load Node credentials are encrypted at rest and write-only.
13. Audit events cover the minimum security-relevant actions.
14. Security error codes have fixed HTTP status and follow 04 error shape.
15. Unit, API, contract and smoke tests cover the minimum matrix in §19.

---

## 21. Review Checklist

Reviewers should check:

1. Does the change stay within P0 and avoid P1/P2 user-visible capabilities?
2. Does it avoid Admin user management UI/API in P0?
3. Does it keep `ALLOW_SIGNUP` behavior clear and non-ambiguous?
4. Does it avoid leaking whether a login email exists?
5. Does it use PostgreSQL sessions without Redis?
6. Does logout invalidate server-side session?
7. Does every protected browser write require CSRF unless explicitly exempt?
8. Does backend enforce role checks, not just frontend navigation?
9. Does every Workspace-aware query filter by Workspace?
10. Does cross-Workspace access avoid data leakage?
11. Are Private Load Node credentials write-only and encrypted?
12. Are sensitive values excluded from responses, logs, audit details and snapshots?
13. Are new error codes registered in the proper registry with one fixed status?
14. Did the Slice avoid putting concrete endpoint details back into Foundation docs?
15. Are tests added or updated for the relevant security boundary?

---

## 22. AI Coding Rules

AI Coding must follow these rules:

1. Do not add OAuth, OIDC, SSO, LDAP or SAML in P0.
2. Do not add user management UI/API in P0.
3. Do not add Workspace switcher or Workspace member management in P0.
4. Do not introduce Redis, Celery or external rate-limit services for auth.
5. Do not store password plaintext or reversible password encryption.
6. Do not return password hash, session token, CSRF token except token retrieval response, runner token or SSH credential.
7. Do not implement Private Load Node credential update through generic PATCH.
8. Do not let Admin view Private Load Node credentials.
9. Do not put Workspace ID in route path.
10. Do not query Workspace-aware resources without Workspace filter.
11. Do not add resource owner / creator permission checks unless a Slice explicitly defines them later.
12. Do not add audit UI, retention cleanup or export in P0.
13. Do not invent new error response shapes.
14. Do not map one error code to multiple HTTP statuses.
15. Do not mark security behavior complete without tests.
