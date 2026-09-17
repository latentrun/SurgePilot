# P0-03: Load Nodes

- Document status: Draft v1 for implementation
- Product: SurgePilot
- Document path: `docs/sdd/slices/P0-03-load-nodes.md`
- Current delivery target: P0 only
- Slice owner: API / Web / Contracts / Runner Integration / Security
- Depends on: `docs/prd/PRD.md`, `docs/sdd/00-product-scope-and-priority.md`, `docs/sdd/01-architecture-overview.md`, `docs/sdd/02-repo-structure-and-dev-workflow.md`, `docs/sdd/04-api-contract-guidelines.md`, `docs/sdd/05-runner-protocol-and-run-state-machine.md`, `docs/sdd/06-security-permission-workspace.md`, `docs/sdd/08-frontend-routing-and-ui-rules.md`, `docs/sdd/09-testing-and-acceptance-strategy.md`, `docs/sdd/adr/ADR-0004-p0-manual-single-node-only.md`
- Optional context only if directly needed: `docs/sdd/03-domain-model-overview.md`, `docs/sdd/07-storage-artifacts-minio.md`

---

## 1. Goal

This slice implements P0 Load Node management.

After this slice is done, an authenticated user can:

1. View Load Nodes available to the current Workspace.
2. Register a Workspace Private Load Node.
3. Register a Public Load Node when the actor is Admin.
4. Configure SSH connection metadata and credentials without later plaintext credential exposure.
5. Initialize a node through the API and `api-worker`.
6. View initialization status and sanitized initialization logs.
7. Edit safe metadata and connection settings.
8. Disable, enable, or archive a node within P0 permission boundaries.

P0-03 creates the Load Node asset, credential safety boundary, initialization workflow, public/private management rules, API contract, UI contract, and tests.

P0-03 does **not** implement Run creation, node lease acquisition, Runner callbacks, heartbeat timeout convergence, or Run-driven Busy release. Those belong to `P0-04 Run State Machine / Runner Protocol`.

---

## 2. PRD Trace

This slice implements the P0 Load Nodes / Resources requirement.

Product meaning:

| Product concept | Contract in this slice |
| --- | --- |
| Load Node | A machine reachable by SSH that can later run SurgePilot Runner and Taurus/JMeter workload execution. |
| Public Load Node | Platform-level node managed by Admin and selectable by Workspaces in later Run slices. |
| Workspace Private Load Node | Workspace-owned node registered and managed by users in the current Workspace. |
| Manual single-node | P0 supports only explicit single-node selection in later Run/Test Plan slices. P0-03 must not add auto allocation or multi-node behavior. |
| Initialization | API schedules initialization; `api-worker` connects by SSH, prepares `runnerHome`, checks required runtime dependencies, records sanitized logs, and marks node available only after success. |
| Credential safety | Passwords, private keys, and private key passphrases are encrypted at rest and never returned after submission. Admin also cannot view Private node plaintext credentials. |
| Initialization logs | Users can inspect sanitized initialization output for troubleshooting. Secrets must be redacted. |
| Node status | UI shows stable status badges from contracts. Busy and quarantine status values are defined for P0 stability, but Busy transitions are completed in P0-04. |

This slice establishes the data and API shape needed by P0-04, P0-06, and P0-07.

---

## 3. Document Responsibility

This Slice SDD owns the concrete P0-03 contract for:

1. Load Node data model.
2. Public vs Workspace Private node boundary.
3. SSH credential model and encryption requirements.
4. Load Node create, list, detail, update, credential update, initialize, init-log, disable, enable, and archive endpoints.
5. Load Node frontend route behavior under `/resources/load-nodes` and `/resources/load-nodes/new`.
6. Load Node status values exposed to Web.
7. Initialization worker behavior and sanitized initialization logs.
8. Load Node permission checks.
9. Load Node tests and Done When.

This document must not redefine global rules owned by Foundation SDDs:

| Concern | Source of truth |
| --- | --- |
| P0/P1/P2 scope gate | `00-product-scope-and-priority.md` |
| Architecture and `api-worker` boundary | `01-architecture-overview.md` |
| Repository layout, migrations, contracts, commands | `02-repo-structure-and-dev-workflow.md` |
| REST, headers, pagination, OpenAPI, error shape | `04-api-contract-guidelines.md` |
| Runner state machine, node lease, heartbeat, cleanup, quarantine convergence | `05-runner-protocol-and-run-state-machine.md` |
| Auth, CSRF, role, Workspace, Private credential handling | `06-security-permission-workspace.md` |
| Frontend routing, UI stack, query ownership | `08-frontend-routing-and-ui-rules.md` |
| Verification gates and test layer ownership | `09-testing-and-acceptance-strategy.md` |
| P0 manual single-node decision | `adr/ADR-0004-p0-manual-single-node-only.md` |

---

## 4. In Scope

### 4.1 Backend

Implement these public API endpoints:

| Endpoint | Method | Auth | CSRF | Purpose |
| --- | --- | --- | --- | --- |
| `/api/v1/load-nodes` | `GET` | session | no | List visible Load Nodes. |
| `/api/v1/load-nodes` | `POST` | session | yes | Register a Public or Workspace Private Load Node. |
| `/api/v1/load-nodes/{loadNodeId}` | `GET` | session | no | Get one Load Node. |
| `/api/v1/load-nodes/{loadNodeId}` | `PATCH` | session | yes | Update metadata and safe connection fields, not credentials. |
| `/api/v1/load-nodes/{loadNodeId}` | `DELETE` | session | yes | Archive a Load Node when safe. |
| `/api/v1/load-nodes/{loadNodeId}/credentials` | `POST` | session | yes | Replace full SSH credential material. |
| `/api/v1/load-nodes/{loadNodeId}/initialize` | `POST` | session | yes | Queue node initialization through `api-worker`. |
| `/api/v1/load-nodes/{loadNodeId}/init-attempts` | `GET` | session | no | List initialization attempts for one node. |
| `/api/v1/load-nodes/{loadNodeId}/init-attempts/{attemptId}` | `GET` | session | no | Get sanitized initialization log details. |
| `/api/v1/load-nodes/{loadNodeId}/disable` | `POST` | session | yes | Disable a node so it cannot be selected for future Runs. |
| `/api/v1/load-nodes/{loadNodeId}/enable` | `POST` | session | yes | Re-enable a disabled node, requiring re-initialization before selection. |

Backend support includes:

1. Workspace-aware Private node queries and writes.
2. Public node permission checks requiring Admin for create, edit, delete/archive, initialize, disable, and enable.
3. Current Workspace Private node management by authenticated users with Workspace access.
4. A single `scope` contract field with values `public` and `workspace`.
5. SSH credential encryption with AES-256-GCM using `SSH_CREDENTIAL_ENCRYPTION_KEY`.
6. Write-only password, private key, and passphrase behavior.
7. Platform-generated keypair support.
8. Safe host, SSH port, SSH user, and `runnerHome` validation.
9. Soft archive instead of physical hard delete.
10. Disable/enable actions.
11. Initialization attempts stored with sanitized log tail.
12. `api-worker` initialization jobs without Celery, Redis, RabbitMQ, Kafka, or external queues.
13. Stable status values, including P0-04-ready `busy` and `quarantined`.
14. Audit events for credential lifecycle, node changes, initialization, disable, enable, and archive.
15. OpenAPI export and generated Web client updates.

### 4.2 Data

Create one Alembic migration after P0-02:

```text
apps/api/migrations/versions/0004_p0_03_load_nodes.py
```

The migration creates:

1. `load_nodes` table.
2. `load_node_credentials` table.
3. `load_node_initialization_attempts` table.
4. Indexes and constraints needed for Workspace filtering, Public filtering, status filtering, and safe uniqueness.

### 4.3 Frontend

Implement the P0 routes:

| Route | Layout | Purpose |
| --- | --- | --- |
| `/resources/load-nodes` | `AppLayout` | List, search, filter, initialize, disable/enable, archive, and view logs. |
| `/resources/load-nodes/new` | `AppLayout` | Register a Load Node with SSH credential setup. |

Frontend support includes:

1. One Load Nodes list page, not separate Public and Private pages.
2. Search and filters for `scope` and `status`.
3. Status badges using contract enum values.
4. Role-aware action visibility, while backend remains authoritative.
5. Register form with Public/Private scope choice.
6. Credential input modes: password, uploaded private key, generated keypair.
7. One-time or repeatable display of generated public key for installation on the node.
8. Edit metadata and safe connection settings.
9. Credential replacement form that never displays existing plaintext credentials.
10. Initialization action and sanitized log viewer.
11. Disable/enable actions.
12. Archive confirmation with Busy-state error handling.
13. Loading, empty, error, validation, and disabled submitting states.

### 4.4 Tests

Implement:

1. API unit tests for validators, status transitions, permission branching, credential encryption/decryption service, and credential redaction.
2. API integration tests for all Load Node endpoints.
3. Worker tests for initialization job success, failure, timeout, log redaction, and idempotent queue behavior.
4. Contract tests for OpenAPI operation IDs, schemas, headers, error responses, and forbidden credential fields.
5. Web component/page tests for list, filters, registration, credential modes, initialization logs, disable/enable, archive, and permission-driven action states.
6. One lightweight Playwright smoke test for registering a Private node record and exercising the list/log UI with fake initialization behavior.

---

## 5. Out of Scope

This slice must not implement:

1. Run creation.
2. Run Snapshot capture.
3. Test Plan resource configuration.
4. Manual Run node selection UI.
5. Node lease acquisition or release.
6. Runner callback endpoints.
7. Runner heartbeat ingestion.
8. Heartbeat timeout convergence.
9. Stop behavior.
10. Force-kill cleanup.
11. Run-driven Busy transitions.
12. Artifact collection.
13. Real execution bundle upload for a Run.
14. Auto resource allocation.
15. Multi-node execution.
16. Node Count.
17. Selected Nodes multi-select.
18. Resource queueing.
19. Scheduler or scheduled jobs.
20. Monitoring pages.
21. Grafana iframe or Open in Grafana.
22. InfluxDB write path or datasource management.
23. Kubernetes, Redis, Celery, RabbitMQ, Kafka, or external queue services.
24. Generic remote command execution UI.
25. Browser direct SSH or direct Load Node access.
26. Workspace switching UI.
27. Workspace management UI.
28. User management UI.
29. Secret reveal, credential export, or credential download.
30. Partial credential update semantics.
31. Generic PATCH of credential fields.
32. Key rotation.
33. Env Group Secret type.
34. Tags.
35. Labels.
36. Public node approval workflows.
37. Quota, capacity planning, or node reservation.
38. Automatic dependency installation for Java, JMeter, Taurus, Python, or system packages.
39. SSH bastion/jump host support.
40. Windows Load Node support.
41. Local agent enrollment without SSH.
42. Audit log UI.
43. P1/P2 user-visible navigation or placeholder pages.

P0-03 may create extension-safe status values and columns needed by later P0 slices, but it must not expose usable P1/P2 behavior.

---

## 6. Key Decisions

| Area | Decision |
| --- | --- |
| Resource name | `load-nodes` |
| Frontend list route | `/resources/load-nodes` |
| Frontend create route | `/resources/load-nodes/new` |
| API route shape | One `/api/v1/load-nodes` resource with `scope` branching. |
| Scope enum | `public`, `workspace` |
| User-facing copy | Show `public` as Public and `workspace` as Private. |
| Public Workspace model | No virtual Public Workspace. `scope=public` has `workspace_id=NULL`. |
| Private Workspace model | `scope=workspace` has `workspace_id=current Workspace ID`. |
| Public management | Admin only. |
| Private management | Authenticated current Workspace users and Admins with current Workspace access. |
| List visibility | Authenticated users see Public nodes and current Workspace Private nodes. |
| P0 Admin global view | P0 has one visible Default Workspace; do not add cross-Workspace UI. |
| Credential auth types | `password`, `private_key`, `generated_key` |
| Credential storage | Separate `load_node_credentials` table, no `workspace_id`, no response exposure of secret material. |
| Credential update | Explicit action endpoint replacing full credential material. |
| Generated keypair | API generates keypair, stores encrypted private key, and returns/stores public key for node installation. |
| Encryption | AES-256-GCM using Python `cryptography`; key from `SSH_CREDENTIAL_ENCRYPTION_KEY`. |
| Key rotation | Not implemented in P0. |
| Initialization execution | `api-worker` asynchronous job, coordinated through PostgreSQL. |
| Initialization depth | SSH/SFTP connect, prepare runner home, verify base prerequisites, push and activate the matching self-contained SurgePilot runtime from api-worker local artifacts, probe runtime-contained Taurus/JMeter/plugins and Runner, record sanitized logs. No automatic OS package, pip, Taurus, JMeter, plugin, or native-extension installation. |
| Runner home | Configurable `runnerHome`, default `/opt/surgepilot/runner`, strict POSIX path validation. |
| Status enum | `uninitialized`, `initializing`, `idle`, `busy`, `offline`, `quarantined`, `disabled` |
| Archive behavior | Metadata archive via `archived_at`; list excludes archived by default. |
| Busy delete behavior | Reject archive/delete when `status=busy`. |
| Disable behavior | Disable prevents later selection. Busy disable is rejected in P0-03. |
| Enable behavior | Enable moves node to `uninitialized`; re-initialization is required before selection. |
| Tags | Not implemented in P0. |
| Logs | Store bounded sanitized initialization log tail, not raw unbounded output. |
| Web storage access | Web never connects to Load Nodes directly. |
| Audit | Credential lifecycle and node management actions emit audit events without secrets. |

---

## 7. Data Model

### 7.1 `load_nodes`

Purpose: Public or Workspace Private node metadata and selection-facing status.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `scope` | `text` | yes | `public` or `workspace`. |
| `workspace_id` | `char(26)` | conditional | `NULL` for Public; current Workspace ID for Private. |
| `host` | `text` | yes | SSH host/IP. Must not include URL scheme, slash, whitespace, or shell control characters. |
| `ssh_port` | `integer` | yes | `1..65535`. |
| `ssh_user` | `text` | yes | Linux SSH username. |
| `runner_home` | `text` | yes | Absolute POSIX path; default `/opt/surgepilot/runner`. |
| `auth_type` | `text` | yes | `password`, `private_key`, or `generated_key`. Duplicated for list filtering/display; secret material is in credential table. |
| `maintainer` | `text` | no | Free text contact, max length controlled by API. |
| `remark` | `text` | no | Free text note, max length controlled by API. |
| `status` | `text` | yes | Load Node status enum. |
| `last_status_reason` | `text` | no | Stable short reason code or message fallback. No secrets. |
| `runner_version` | `text` | no | Last detected Runner version. |
| `bundle_version` | `text` | no | Last detected Runner/bootstrap bundle version. |
| `last_initialized_at` | `timestamptz` | no | Last successful initialization time. |
| `last_checked_at` | `timestamptz` | no | Last initialization or health-check probe time. |
| `last_heartbeat_at` | `timestamptz` | no | Reserved for P0-04 Runner heartbeat; null in P0-03 except future backfill. |
| `current_run_id` | `char(26)` | no | Reserved for P0-04; null in P0-03. P0-03 creates this nullable column without an FK. P0-04 adds the FK when the Runs table exists. |
| `last_init_attempt_id` | `char(26)` | no | Optional FK to latest init attempt. |
| `created_by` | `char(26)` | yes | FK to `users.id`. |
| `updated_by` | `char(26)` | no | FK to `users.id`. |
| `archived_by` | `char(26)` | no | FK to `users.id`. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |
| `archived_at` | `timestamptz` | no | UTC; non-null means hidden from normal lists and unavailable for selection. |

Constraints:

1. Primary key on `id`.
2. `scope in ('public', 'workspace')`.
3. `status in ('uninitialized', 'initializing', 'idle', 'busy', 'offline', 'quarantined', 'disabled')`.
4. `auth_type in ('password', 'private_key', 'generated_key')`.
5. `ssh_port between 1 and 65535`.
6. `scope='public'` requires `workspace_id IS NULL`.
7. `scope='workspace'` requires `workspace_id IS NOT NULL`.
8. FK from `workspace_id` to `workspaces.id`.
9. FK from `created_by`, `updated_by`, and `archived_by` to `users.id`.
10. Active node uniqueness prevents accidental duplicate registration:
    - Public: unique active `(scope, lower(host), ssh_port, lower(ssh_user))` where `scope='public' and archived_at is null`.
    - Workspace: unique active `(workspace_id, lower(host), ssh_port, lower(ssh_user))` where `scope='workspace' and archived_at is null`.
11. Index on `(scope, status, created_at desc, id desc)` for Public lists.
12. Index on `(workspace_id, status, created_at desc, id desc)` for Private lists.
13. Index on `(archived_at)` or partial active indexes as needed.

Rules:

1. `id`, `workspace_id`, `created_by`, `updated_by`, `archived_by`, `last_init_attempt_id`, and `current_run_id` are ULID strings.
2. P0-03 creates `current_run_id` as a nullable `char(26)` column without a foreign key.
3. P0-04 owns adding the `current_run_id` foreign key after the Runs table exists.
4. Archived nodes are not selectable and are excluded from normal list results.
5. `busy` is a reserved status in P0-03; only P0-04 Run/lease logic may set or clear it.
6. `quarantined` is a reserved safety status in P0-03; P0-04 owns force-kill and stale-process quarantine entry rules.

### 7.2 `load_node_credentials`

Purpose: Store encrypted SSH credential material separate from ordinary node response data.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `node_id` | `char(26)` | yes | PK and FK to `load_nodes.id`. |
| `auth_type` | `text` | yes | Must match the node auth type. |
| `password_ciphertext` | `bytea` or `text` | conditional | AES-GCM encrypted password for `password`. |
| `private_key_ciphertext` | `bytea` or `text` | conditional | AES-GCM encrypted private key for `private_key` or `generated_key`. |
| `private_key_passphrase_ciphertext` | `bytea` or `text` | no | AES-GCM encrypted passphrase when supplied. |
| `generated_public_key` | `text` | no | Public key for `generated_key`. Not secret. |
| `credential_fingerprint` | `text` | no | Non-secret fingerprint for generated public-key credentials only. Must be null for password credentials and P0 private-key uploads. |
| `encryption_key_version` | `text` | no | Optional P0 marker. When null, treat as `v1`. No rotation in P0. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |
| `updated_by` | `char(26)` | yes | FK to `users.id`. |

Constraints:

1. Primary key on `node_id`.
2. FK from `node_id` to `load_nodes.id` with delete restricted by archive semantics.
3. `auth_type in ('password', 'private_key', 'generated_key')`.
4. For `auth_type='password'`, `password_ciphertext` is required and private key ciphertext is null.
5. For `auth_type='private_key'`, `private_key_ciphertext` is required and password ciphertext is null.
6. For `auth_type='generated_key'`, `private_key_ciphertext` and `generated_public_key` are required and password ciphertext is null.
7. FK from `updated_by` to `users.id`.
8. Do not store `workspace_id` in this table; Workspace is derived through `load_nodes`.

Rules:

1. API list/get responses must not return ciphertext, nonce, tag, encrypted blobs, passphrase, password, private key, or key ID.
2. API returns `credentialConfigured`, `authType`, `credentialFingerprint`, and `generatedPublicKey` when `authType='generated_key'`; password and uploaded private-key credentials return `credentialFingerprint=null`.
3. `generatedPublicKey` is public material and is displayed so users can install it in `authorized_keys`.
4. Decryption is allowed only in the initialization and later run-start service paths.
5. Decrypted material must stay in local variables and must not be logged, audited, serialized, or attached to exceptions.
6. `load_nodes.auth_type` and `load_node_credentials.auth_type` must match.
7. Create and credential-replacement operations update the node row and credential row in one database transaction.
8. If credential replacement fails, neither `load_nodes.auth_type` nor `load_node_credentials` changes.
9. `encryption_key_version` does not imply key rotation support in P0.

### 7.3 `load_node_initialization_attempts`

Purpose: Track asynchronous initialization attempts and sanitized troubleshooting logs.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `node_id` | `char(26)` | yes | FK to `load_nodes.id`. |
| `status` | `text` | yes | `queued`, `running`, `succeeded`, or `failed`. |
| `requested_by` | `char(26)` | yes | FK to `users.id`. |
| `started_at` | `timestamptz` | no | UTC. |
| `finished_at` | `timestamptz` | no | UTC. |
| `error_code` | `text` | no | Stable error code when failed. |
| `message` | `text` | no | English fallback text, no secrets. |
| `sanitized_log_tail` | `text` | no | Bounded redacted log tail. |
| `runner_version` | `text` | no | Version detected by this attempt. |
| `bundle_version` | `text` | no | Bundle/bootstrap version detected by this attempt. |
| `request_id` | `text` | no | Request ID that queued the attempt. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |

Constraints:

1. Primary key on `id`.
2. FK from `node_id` to `load_nodes.id`.
3. FK from `requested_by` to `users.id`.
4. `status in ('queued', 'running', 'succeeded', 'failed')`.
5. Index on `(node_id, created_at desc, id desc)`.
6. Index on `(status, created_at)` for worker claiming.

Rules:

1. Store only bounded logs. Default tail limit: `64 KiB`.
2. Redact passwords, private key material, passphrases, bearer tokens, CSRF tokens, MinIO secrets, and environment values matching sensitive patterns before persisting.
3. Do not store raw SSH command strings if they include sensitive data.
4. If initialization output exceeds the tail limit, keep the most recent sanitized lines and indicate truncation.

### 7.4 Initialization Attempt Claiming

P0-03 claims queued initialization attempts directly from `load_node_initialization_attempts` using PostgreSQL row-level claiming:

```sql
SELECT *
FROM load_node_initialization_attempts
WHERE status = 'queued'
ORDER BY created_at
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

Rules:

1. P0-03 does not require or create a generic `background_jobs` table for Load Node initialization.
2. No in-process long-running worker runs inside the FastAPI web process.
3. No external queue service is introduced.
4. Row-level claiming prevents more than one `api-worker` process from executing the same queued attempt concurrently.
5. A claimed attempt is updated from `queued` to `running` in the same transaction that claims it.
6. A `running` attempt that exceeds `LOAD_NODE_INIT_TIMEOUT_SECONDS` without a terminal update is marked `failed` with `LOAD_NODE_INIT_FAILED`, and the node is marked `offline`.
7. An `initializing` node older than `LOAD_NODE_INIT_TIMEOUT_SECONDS` with no active queued or running attempt is recovered to `offline` with `LOAD_NODE_INIT_FAILED`.

---

## 8. Status Model

### 8.1 Load Node Status Values

| Status | Meaning | Selectable for Run | P0-03 owners |
| --- | --- | --- | --- |
| `uninitialized` | Node metadata and credential exist, but initialization has not succeeded. | no | P0-03 create/enable/failure paths. |
| `initializing` | Initialization attempt is queued or running. | no | P0-03 worker. |
| `idle` | Node passed initialization and can be selected by later Run/Test Plan flows. | yes, later P0-06/P0-04 rules apply | P0-03 initialization success. |
| `busy` | Node is leased by a Run. | no | Reserved for P0-04. P0-03 must not set this except tests/fixtures. |
| `offline` | Node is known unavailable because initialization or probe failed. | no | P0-03 initialization failure. |
| `quarantined` | Node is unsafe due to stale process, force-kill failure, or unknown runner state. | no | Reserved for P0-04 cleanup safety. |
| `disabled` | Actor disabled node so it cannot be selected. | no | P0-03 disable action. |

### 8.2 P0-03 Status Transitions

| From | Trigger | To | Notes |
| --- | --- | --- | --- |
| none | create node | `uninitialized` | Credential may be configured in same request. |
| `uninitialized` | initialize requested | `initializing` | Creates init attempt. |
| `offline` | initialize requested | `initializing` | Retrying after failure. |
| `idle` | initialize requested with `force=true` | `initializing` | Explicit re-initialization. |
| `disabled` | enable | `uninitialized` | Requires re-initialization before selection. |
| `uninitialized`, `idle`, `offline` | successful PATCH | `uninitialized` | Any accepted metadata or connection update invalidates initialization. |
| `initializing` | init success | `idle` | Writes versions and timestamps. |
| `initializing` | init failure | `offline` | Writes reason and sanitized logs. |
| `uninitialized`, `idle`, `offline`, `quarantined` | disable | `disabled` | `busy` and `initializing` are rejected. |
| `uninitialized`, `idle`, `offline`, `disabled`, `quarantined` | archive | archived | `busy` and `initializing` are rejected; archived rows excluded from normal lists. |

Rules:

1. P0-03 must not change a node from `busy` to another status. P0-04 owns Busy release.
2. P0-03 rejects initialization and archive while `status=busy`.
3. P0-03 rejects PATCH and credential replacement while `status=initializing`, `busy`, `quarantined`, or `disabled`.
4. `quarantined` clearance rules that result from Run cleanup are owned by `05-runner-protocol-and-run-state-machine.md` and P0-04. P0-03 defines the status value and displays it.
5. A disabled node must never be selectable until re-enabled and successfully initialized again.
6. A quarantined node requires Admin-confirmed residual process and Monitoring secret cleanup, followed by disable → enable → initialize; direct initialization from `quarantined` is not allowed.

---

## 9. API Contract

All public paths below are mounted under the API prefix `/api/v1`. OpenAPI exported paths use `/v1/...` according to existing contract generation rules.

All JSON fields use `camelCase`.

All write endpoints require `x-csrf-token`.

All business endpoints require Workspace context. Missing `x-workspace-id` falls back to the user's default Workspace according to `04-api-contract-guidelines.md` and `06-security-permission-workspace.md`.

### 9.1 Shared Schemas

#### `LoadNodeScope`

```json
"public" | "workspace"
```

#### `LoadNodeStatus`

```json
"uninitialized" | "initializing" | "idle" | "busy" | "offline" | "quarantined" | "disabled"
```

#### `LoadNodeAuthType`

```json
"password" | "private_key" | "generated_key"
```

#### `LoadNodeSummary`

```json
{
  "id": "01J00000000000000000000003",
  "scope": "workspace",
  "workspaceId": "01HZW000000000000000000000",
  "host": "10.0.2.15",
  "sshPort": 22,
  "sshUser": "surgepilot",
  "runnerHome": "/opt/surgepilot/runner",
  "authType": "private_key",
  "credentialConfigured": true,
  "credentialFingerprint": null,
  "generatedPublicKey": null,
  "maintainer": "Performance Team",
  "remark": "Staging private node",
  "status": "idle",
  "lastStatusReason": null,
  "runnerVersion": "0.1.0",
  "bundleVersion": "p0-03",
  "runtimeVersion": "runtime-test-v1",
  "lastInitializedAt": "2030-05-31T10:00:00Z",
  "lastCheckedAt": "2030-05-31T10:00:00Z",
  "lastHeartbeatAt": null,
  "currentRunId": null,
  "lastInitAttemptId": "01J00000000000000000000004",
  "createdAt": "2030-05-31T09:00:00Z",
  "updatedAt": "2030-05-31T10:00:00Z"
}
```

Rules:

1. `workspaceId` is `null` for Public nodes.
2. `generatedPublicKey` is populated only for generated-key nodes. It is public key material, not a secret.
3. Response schemas must not include password, private key, private key passphrase, encrypted blobs, nonce, tag, key ID, or raw SSH command text.
4. `runtimeVersion` is the activated Runtime metadata version recorded by successful initialization. `null` means the node requires initialization and is not runnable.

#### `LoadNodeDetail`

Same fields as `LoadNodeSummary`, plus bounded latest initialization attempt summary:

```json
{
  "latestInitAttempt": {
    "id": "01J00000000000000000000004",
    "status": "succeeded",
    "startedAt": "2030-05-31T09:59:00Z",
    "finishedAt": "2030-05-31T10:00:00Z",
    "errorCode": null,
    "message": "Initialization succeeded."
  }
}
```

#### `LoadNodeCredentialInput`

Password mode:

```json
{
  "authType": "password",
  "password": "submitted-once"
}
```

Uploaded private key mode:

```json
{
  "authType": "private_key",
  "privateKey": "-----BEGIN OPENSSH PRIVATE KEY-----\n...",
  "privateKeyPassphrase": "optional-submitted-once"
}
```

Generated key mode:

```json
{
  "authType": "generated_key"
}
```

Rules:

1. Credential input is accepted only in request bodies.
2. Credential input must not appear in OpenAPI examples with real-looking secret values.
3. Empty strings are invalid credential values.
4. Updating credentials requires a full replacement through `/credentials`.
5. Generic PATCH must not accept credential fields.

### 9.2 `GET /api/v1/load-nodes`

Purpose: List visible active Load Nodes.

Query parameters:

| Name | Required | Meaning |
| --- | --- | --- |
| `scope` | no | `public`, `workspace`, or omitted for both visible scopes. |
| `status` | no | One `LoadNodeStatus` value. |
| `q` | no | Search over `host`, `sshUser`, `maintainer`, and `remark`. |
| `includeArchived` | no | Boolean. Default `false`. Admin-only for Public archived rows; current Workspace only for Private. |
| `limit` | no | Offset pagination limit. |
| `offset` | no | Offset pagination offset. |
| `sort` | no | `createdAt`, `-createdAt`, `host`, `status`, `lastCheckedAt`, `-lastCheckedAt`. Default `-createdAt`. |

Response `200`:

```json
{
  "items": [
    {
      "id": "01J00000000000000000000003",
      "scope": "workspace",
      "workspaceId": "01HZW000000000000000000000",
      "host": "10.0.2.15",
      "sshPort": 22,
      "sshUser": "surgepilot",
      "runnerHome": "/opt/surgepilot/runner",
      "authType": "private_key",
      "credentialConfigured": true,
      "credentialFingerprint": null,
      "generatedPublicKey": null,
      "maintainer": "Performance Team",
      "remark": "Staging private node",
      "status": "idle",
      "lastStatusReason": null,
      "runnerVersion": "0.1.0",
      "bundleVersion": "p0-03",
      "lastInitializedAt": "2030-05-31T10:00:00Z",
      "lastCheckedAt": "2030-05-31T10:00:00Z",
      "lastHeartbeatAt": null,
      "currentRunId": null,
      "lastInitAttemptId": "01J00000000000000000000004",
      "createdAt": "2030-05-31T09:00:00Z",
      "updatedAt": "2030-05-31T10:00:00Z"
    }
  ],
  "limit": 20,
  "offset": 0,
  "total": 1
}
```

Permission rules:

1. All authenticated users with current Workspace access may list Public nodes and current Workspace Private nodes.
2. Public list rows do not expose secret material.
3. Private list rows are filtered to the current Workspace.
4. Cross-Workspace Private nodes are not returned.

Errors:

| Code | HTTP | Meaning |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | No valid session. |
| `WORKSPACE_REQUIRED` | 400 | Workspace cannot be resolved. |
| `WORKSPACE_ACCESS_DENIED` | 403 | Actor cannot access requested Workspace. |
| `VALIDATION_ERROR` | 422 | Invalid query parameter. |

### 9.3 `POST /api/v1/load-nodes`

Purpose: Register a Load Node.

Request:

```json
{
  "scope": "workspace",
  "host": "10.0.2.15",
  "sshPort": 22,
  "sshUser": "surgepilot",
  "runnerHome": "/opt/surgepilot/runner",
  "credential": {
    "authType": "private_key",
    "privateKey": "submitted-once",
    "privateKeyPassphrase": "optional-submitted-once"
  },
  "maintainer": "Performance Team",
  "remark": "Staging private node"
}
```

Response `201`: `LoadNodeDetail`.

Rules:

1. `scope='public'` requires Admin.
2. `scope='workspace'` creates the node in the resolved current Workspace.
3. `workspaceId` is never accepted in the body for P0.
4. New nodes start as `uninitialized`.
5. Credential material is encrypted before commit.
6. The response must not return submitted secrets.
7. For `authType='generated_key'`, the response includes `generatedPublicKey`.
8. Duplicate active host/port/user in the same scope is rejected.

Errors:

| Code | HTTP | Meaning |
| --- | --- | --- |
| `LOAD_NODE_PUBLIC_ADMIN_REQUIRED` | 403 | Non-Admin attempted Public node creation. |
| `LOAD_NODE_CONFLICT` | 409 | Active node with same host/port/user already exists in scope. |
| `LOAD_NODE_CREDENTIAL_REQUIRED` | 422 | Missing credential material for selected auth type. |
| `LOAD_NODE_CREDENTIAL_INVALID` | 422 | Invalid password/key/passphrase format. |
| `LOAD_NODE_HOST_INVALID` | 422 | Host failed validation. |
| `LOAD_NODE_RUNNER_HOME_INVALID` | 422 | Runner home path failed validation. |
| `VALIDATION_ERROR` | 422 | Other validation failure. |

### 9.4 `GET /api/v1/load-nodes/{loadNodeId}`

Purpose: Get one visible Load Node.

Path parameters:

| Name | Meaning |
| --- | --- |
| `loadNodeId` | ULID string. |

Response `200`: `LoadNodeDetail`.

Rules:

1. Public nodes are visible to authenticated users.
2. Private nodes must belong to the current Workspace.
3. Cross-Workspace Private lookup returns `404 RESOURCE_NOT_FOUND`.
4. Secret material is never returned.

Errors:

| Code | HTTP | Meaning |
| --- | --- | --- |
| `RESOURCE_NOT_FOUND` | 404 | Node not found or not visible. |
| `VALIDATION_ERROR` | 422 | Invalid ULID. |

### 9.5 `PATCH /api/v1/load-nodes/{loadNodeId}`

Purpose: Update safe metadata and connection fields.

Request:

```json
{
  "host": "10.0.2.16",
  "sshPort": 22,
  "sshUser": "surgepilot",
  "runnerHome": "/opt/surgepilot/runner",
  "maintainer": "Performance Team",
  "remark": "Updated note"
}
```

Rules:

1. `scope`, `workspaceId`, `authType`, credential fields, status, and current run fields are not patchable.
2. Public node update requires Admin.
3. Private node update requires current Workspace access.
4. PATCH is accepted only when status is `uninitialized`, `idle`, or `offline`.
5. PATCH is rejected when status is `initializing`, `busy`, `quarantined`, or `disabled`.
6. Any successful PATCH sets status to `uninitialized`, because the node must be re-initialized before selection.

Response `200`: `LoadNodeDetail`.

Errors:

| Code | HTTP | Meaning |
| --- | --- | --- |
| `LOAD_NODE_PUBLIC_ADMIN_REQUIRED` | 403 | Non-Admin attempted Public node update. |
| `LOAD_NODE_BUSY` | 409 | Node is Busy and cannot be updated. |
| `LOAD_NODE_ACTION_NOT_ALLOWED` | 409 | Current node status does not allow PATCH. |
| `LOAD_NODE_CONFLICT` | 409 | Updated host/port/user conflicts with active node. |
| `RESOURCE_NOT_FOUND` | 404 | Node not found or not visible. |
| `VALIDATION_ERROR` | 422 | Invalid input. |

### 9.6 `DELETE /api/v1/load-nodes/{loadNodeId}`

Purpose: Archive a Load Node.

Rules:

1. This is metadata archive, not physical destruction of remote files.
2. Public node archive requires Admin.
3. Private node archive requires current Workspace access.
4. `status=busy` and `status=initializing` are rejected.
5. Archived nodes are not selectable and are excluded from normal list results.
6. Credentials remain encrypted in DB for audit/history unless a future retention policy removes them. P0 does not implement credential shredding.

Response `204`: empty body.

Errors:

| Code | HTTP | Meaning |
| --- | --- | --- |
| `LOAD_NODE_PUBLIC_ADMIN_REQUIRED` | 403 | Non-Admin attempted Public node archive. |
| `LOAD_NODE_BUSY` | 409 | Busy node cannot be archived. |
| `LOAD_NODE_ACTION_NOT_ALLOWED` | 409 | Current node status does not allow archive. |
| `RESOURCE_NOT_FOUND` | 404 | Node not found or not visible. |

### 9.7 `POST /api/v1/load-nodes/{loadNodeId}/credentials`

Purpose: Replace the full SSH credential material.

Request:

```json
{
  "credential": {
    "authType": "password",
    "password": "submitted-once"
  }
}
```

Response `200`: `LoadNodeDetail`.

Rules:

1. This action replaces the complete credential set.
2. Empty strings are invalid.
3. There is no partial keep-existing behavior.
4. Public node credential update requires Admin.
5. Private node credential update requires current Workspace access.
6. Credential replacement is accepted only when status is `uninitialized`, `idle`, or `offline`.
7. Credential replacement is rejected when status is `initializing`, `busy`, `quarantined`, or `disabled`.
8. Successful credential replacement updates `load_nodes.auth_type` and `load_node_credentials.auth_type` in the same database transaction.
9. Successful credential replacement moves the node to `uninitialized`, requiring re-initialization.
10. Response does not return submitted secret material.
11. For generated keypair replacement, the new `generatedPublicKey` is returned and stored.

Errors:

| Code | HTTP | Meaning |
| --- | --- | --- |
| `LOAD_NODE_CREDENTIAL_REQUIRED` | 422 | Missing material for selected auth type. |
| `LOAD_NODE_CREDENTIAL_INVALID` | 422 | Credential parse/format failure. |
| `LOAD_NODE_BUSY` | 409 | Busy node credential cannot be changed. |
| `LOAD_NODE_ACTION_NOT_ALLOWED` | 409 | Current node status does not allow credential replacement. |
| `LOAD_NODE_PUBLIC_ADMIN_REQUIRED` | 403 | Non-Admin attempted Public credential update. |
| `RESOURCE_NOT_FOUND` | 404 | Node not found or not visible. |

### 9.8 `POST /api/v1/load-nodes/{loadNodeId}/initialize`

Purpose: Queue Load Node initialization.

Request:

```json
{
  "force": false
}
```

Response `202`:

```json
{
  "node": {
    "id": "01J00000000000000000000003",
    "status": "initializing"
  },
  "attempt": {
    "id": "01J00000000000000000000004",
    "status": "queued",
    "message": "Initialization queued."
  }
}
```

Rules:

1. Public node initialization requires Admin.
2. Private node initialization requires current Workspace access.
3. Initialization is rejected while `status=busy`.
4. When status is `initializing`, the endpoint returns `202` with the existing latest active attempt; it does not create another attempt.
5. `force` has no effect while status is `initializing`.
6. When status is `uninitialized` or `offline`, the endpoint creates a new initialization attempt.
7. When status is `idle`, the endpoint creates a re-initialization attempt only when `force=true`.
8. When status is `idle` and `force=false`, the endpoint returns `409 LOAD_NODE_ACTION_NOT_ALLOWED`.
9. `force=true` never overrides `busy`, `initializing`, `disabled`, or `quarantined`.
10. Initialization reads/decrypts credentials only inside the worker execution path.
11. Initialization status is persisted before the worker starts remote SSH operations.
12. Clearing `quarantined` must obey the quarantine safety rule from `05-runner-protocol-and-run-state-machine.md` and the implementing P0-04 Slice. P0-03 does not clear quarantine through this endpoint.

Errors:

| Code | HTTP | Meaning |
| --- | --- | --- |
| `LOAD_NODE_BUSY` | 409 | Busy node cannot be initialized. |
| `LOAD_NODE_ACTION_NOT_ALLOWED` | 409 | Current node status or `force` value does not allow initialization. |
| `LOAD_NODE_CREDENTIAL_REQUIRED` | 422 | Node has no usable credential. |
| `LOAD_NODE_PUBLIC_ADMIN_REQUIRED` | 403 | Non-Admin attempted Public initialization. |
| `RESOURCE_NOT_FOUND` | 404 | Node not found or not visible. |

### 9.9 `GET /api/v1/load-nodes/{loadNodeId}/init-attempts`

Purpose: List initialization attempts for a node.

Query parameters:

| Name | Required | Meaning |
| --- | --- | --- |
| `limit` | no | Offset pagination limit. |
| `offset` | no | Offset pagination offset. |

Response `200`:

```json
{
  "items": [
    {
      "id": "01J00000000000000000000004",
      "nodeId": "01J00000000000000000000003",
      "status": "succeeded",
      "startedAt": "2030-05-31T09:59:00Z",
      "finishedAt": "2030-05-31T10:00:00Z",
      "errorCode": null,
      "message": "Initialization succeeded.",
      "createdAt": "2030-05-31T09:58:59Z"
    }
  ],
  "limit": 20,
  "offset": 0,
  "total": 1
}
```

Rules:

1. Visibility follows the parent Load Node.
2. List summaries do not include full log tail by default.

### 9.10 `GET /api/v1/load-nodes/{loadNodeId}/init-attempts/{attemptId}`

Purpose: Get initialization attempt detail and sanitized log tail.

Response `200`:

```json
{
  "id": "01J00000000000000000000004",
  "nodeId": "01J00000000000000000000003",
  "status": "succeeded",
  "startedAt": "2030-05-31T09:59:00Z",
  "finishedAt": "2030-05-31T10:00:00Z",
  "errorCode": null,
  "message": "Initialization succeeded.",
  "sanitizedLogTail": "[info] Connected to host\n[info] Runner home prepared\n[info] Dependency check passed\n",
  "runnerVersion": "0.1.0",
  "bundleVersion": "p0-03",
  "createdAt": "2030-05-31T09:58:59Z",
  "updatedAt": "2030-05-31T10:00:00Z"
}
```

Rules:

1. `sanitizedLogTail` must be redacted and bounded.
2. Secret values must never be returned.
3. Attempt must belong to the parent node.

### 9.11 `POST /api/v1/load-nodes/{loadNodeId}/disable`

Purpose: Disable a Load Node.

Request:

```json
{
  "reason": "Temporarily unavailable for maintenance."
}
```

Rules:

1. Public node disable requires Admin.
2. Private node disable requires current Workspace access.
3. Busy and initializing node disable is rejected in P0-03.
4. Disabled nodes are not selectable.
5. `reason` is stored as `lastStatusReason` after length validation and secret redaction.

Response `200`: `LoadNodeDetail`.

Errors:

| Code | HTTP | Meaning |
| --- | --- | --- |
| `LOAD_NODE_BUSY` | 409 | Busy node cannot be disabled by P0-03. |
| `LOAD_NODE_ACTION_NOT_ALLOWED` | 409 | Current node status does not allow disable. |
| `LOAD_NODE_PUBLIC_ADMIN_REQUIRED` | 403 | Non-Admin attempted Public disable. |
| `RESOURCE_NOT_FOUND` | 404 | Node not found or not visible. |

### 9.12 `POST /api/v1/load-nodes/{loadNodeId}/enable`

Purpose: Enable a previously disabled Load Node.

Rules:

1. Public node enable requires Admin.
2. Private node enable requires current Workspace access.
3. Only `status=disabled` can be enabled.
4. Enabling sets status to `uninitialized`.
5. A successful initialization is required before the node becomes `idle`.

Response `200`: `LoadNodeDetail`.

Errors:

| Code | HTTP | Meaning |
| --- | --- | --- |
| `LOAD_NODE_PUBLIC_ADMIN_REQUIRED` | 403 | Non-Admin attempted Public enable. |
| `LOAD_NODE_BUSY` | 409 | Busy node cannot be enabled by P0-03. |
| `LOAD_NODE_ACTION_NOT_ALLOWED` | 409 | Current node status does not allow enable. |
| `RESOURCE_NOT_FOUND` | 404 | Node not found or not visible. |

### 9.13 Error Code Registry Additions

P0-03 adds these error codes:

| Code | HTTP | Meaning |
| --- | --- | --- |
| `LOAD_NODE_PUBLIC_ADMIN_REQUIRED` | 403 | Public Load Node operation requires Admin. |
| `LOAD_NODE_CONFLICT` | 409 | Active node uniqueness conflict. |
| `LOAD_NODE_BUSY` | 409 | Node is Busy and action is unsafe. |
| `LOAD_NODE_ACTION_NOT_ALLOWED` | 409 | Current node status or request mode does not allow the action. |
| `LOAD_NODE_CREDENTIAL_REQUIRED` | 422 | Credential material is missing. |
| `LOAD_NODE_CREDENTIAL_INVALID` | 422 | Credential material is malformed or unsupported. |
| `LOAD_NODE_HOST_INVALID` | 422 | Host failed validation. |
| `LOAD_NODE_RUNNER_HOME_INVALID` | 422 | Runner home failed path validation. |
| `LOAD_NODE_SSH_TIMEOUT` | 422 | Initialization attempt could not connect before timeout. Exposed on init attempt, not normally as immediate HTTP response. |
| `LOAD_NODE_SSH_AUTH_FAILED` | 422 | Initialization attempt failed SSH authentication. Exposed on init attempt. |
| `LOAD_NODE_SSH_UNREACHABLE` | 422 | Initialization attempt could not reach host. Exposed on init attempt. |
| `LOAD_NODE_RUNNER_HOME_UNWRITABLE` | 422 | Initialization attempt could not create or write runner home. Exposed on init attempt. |
| `LOAD_NODE_PYTHON_MISSING` | 422 | Initialization attempt did not find required Python runtime. Exposed on init attempt. |
| `LOAD_NODE_JAVA_MISSING` | 422 | Initialization attempt did not find required Java runtime. Exposed on init attempt. |
| `LOAD_NODE_TAURUS_MISSING` | 422 | Compatibility code only; if retained after Runtime Bootstrap, it must map to runtime-contained Taurus checks and must not mean missing system `bzt`. Prefer `LOAD_NODE_RUNTIME_BZT_FAILED` for new failures. |
| `LOAD_NODE_JMETER_MISSING` | 422 | Compatibility code only; if retained after Runtime Bootstrap, it must map to runtime-contained JMeter checks and must not mean missing system JMeter. Prefer `LOAD_NODE_RUNTIME_JMETER_FAILED` for new failures. |
| `LOAD_NODE_TAR_MISSING` | 422 | Initialization attempt did not find `tar` or equivalent extraction support required for runtime activation. Exposed on init attempt. |
| `LOAD_NODE_RUNTIME_ARTIFACT_MISSING` | 422 | api-worker cannot find a matching local runtime artifact or sidecar checksum for the target architecture/version. Exposed on init attempt. |
| `LOAD_NODE_RUNTIME_ARCH_UNSUPPORTED` | 422 | Target `uname -m` does not map to a P0 supported runtime architecture. Exposed on init attempt. |
| `LOAD_NODE_RUNTIME_UPLOAD_FAILED` | 422 | SFTP upload of the runtime archive failed. Exposed on init attempt. |
| `LOAD_NODE_RUNTIME_CHECKSUM_FAILED` | 422 | Whole-archive SHA256 verification failed. Exposed on init attempt. |
| `LOAD_NODE_RUNTIME_EXTRACT_FAILED` | 422 | Archive extraction failed or safe-extract validation rejected the archive. Exposed on init attempt. |
| `LOAD_NODE_RUNTIME_METADATA_INVALID` | 422 | Runtime metadata is missing or does not match expected version, architecture, or component versions. Exposed on init attempt. |
| `LOAD_NODE_RUNTIME_BZT_FAILED` | 422 | Runtime-contained `bin/bzt -h` failed. Exposed on init attempt. |
| `LOAD_NODE_RUNTIME_JMETER_FAILED` | 422 | Runtime-contained JMeter `--version` failed. Exposed on init attempt. |
| `LOAD_NODE_RUNTIME_PLUGIN_MISSING` | 422 | Required runtime-contained JMeter plugin jar is missing. Exposed on init attempt. |
| `LOAD_NODE_RUNTIME_ACTIVATION_FAILED` | 422 | Verified runtime could not be moved or activated through the atomic `current` symlink. Exposed on init attempt. |
| `LOAD_NODE_INIT_FAILED` | 500 | Unexpected initialization worker failure. Normal remote validation failures use the specific attempt error codes above. |
| `CREDENTIAL_DECRYPT_FAILED` | 500 | Decryption failed due server config or data corruption; no low-level detail returned. |

---

## 10. Initialization Worker Contract

### 10.1 Execution Boundary

Initialization runs in `api-worker`, not the FastAPI request process.

Request path:

```text
POST /load-nodes/{id}/initialize
  -> API validates auth, Workspace, role, node state, credential presence
  -> API creates or reuses initialization attempt
  -> API marks node initializing
  -> api-worker claims attempt
  -> api-worker decrypts credential locally
  -> api-worker connects by SSH/SFTP
  -> api-worker prepares runner home
  -> api-worker verifies base prerequisites and target architecture
  -> api-worker pushes, verifies, safely extracts, and atomically activates the matching Runtime Bootstrap artifact
  -> api-worker verifies runtime-contained Taurus/JMeter/plugins and Runner
  -> api-worker writes sanitized logs and terminal attempt status
  -> api-worker marks node idle or offline
```

Rules:

1. API request must not block on full remote initialization.
2. Worker uses `load_node_initialization_attempts` row-level claiming from §7.4 to avoid duplicate attempt execution.
3. Worker must set `started_at` and `finished_at`.
4. Worker must set terminal attempt status exactly once.
5. Worker must handle retry safely when an earlier attempt failed.
6. Worker must not log or persist decrypted credential material.

### 10.2 Initialization Steps

P0 initialization uses Runtime Bootstrap. System Taurus and system JMeter are no longer valid P0 initialization success criteria after Runtime Bootstrap is active. A node may become `idle` only after api-worker verifies base prerequisites, installs or reuses the configured self-contained SurgePilot runtime, verifies runtime-contained Taurus/JMeter/plugins, and verifies the Runner.

P0 initialization sequence:

1. Validate node is still visible, active, and not Busy.
2. Load and decrypt credential material only in the worker execution path.
3. Establish SSH/SFTP connection with configured host, port, user, and credential.
4. Create and validate `runnerHome` and required subdirectories:
   - `bin`
   - `runs`
   - `logs`
   - `tmp`
   - `runtimes`
5. Write or verify a SurgePilot node marker under `runnerHome`.
6. Check base prerequisites:
   - POSIX shell basics.
   - `uname -m`.
   - `python3 --version` for SurgePilot Runner.
   - `java -version` for runtime-contained JMeter.
   - `tar --version` or equivalent tar availability.
7. Map target architecture to a supported P0 runtime artifact architecture:
   - `x86_64` or `amd64` -> `linux-amd64` / metadata `amd64`.
   - `aarch64` or `arm64` -> `linux-arm64` / metadata `arm64`.
8. Select `surgepilot-runtime-linux-<arch>-<version>.tar.gz` and `surgepilot-runtime-linux-<arch>-<version>.tar.gz.sha256` from the api-worker local read-only artifact directory.
9. Fail safely if the matching artifact or sidecar checksum is missing.
10. Upload the runtime archive to `runnerHome/tmp/` using SFTP `upload_stream`.
11. Verify whole-archive SHA256 on the uploaded archive.
12. Safely extract the archive into a temporary directory under `runnerHome`.
13. Validate `metadata.json`:
    - `name=surgepilot-runtime`.
    - configured `version` matches `LOAD_NODE_RUNTIME_VERSION`.
    - `platform=linux`.
    - `arch` matches detected Load Node architecture.
    - Taurus version is `1.16.50`.
    - JMeter version is `5.6.3`.
    - required plugins are exactly `jpgc-casutg`, `jpgc-json`, `jpgc-tst`,
      `bzm-random-csv`, and `jmeter-plugin-influxdb2-listener`.
14. Check critical files exist:
    - `<tmp-runtime>/python/`.
    - `<tmp-runtime>/bin/bzt`.
    - `<tmp-runtime>/apache-jmeter-5.6.3/bin/jmeter`.
    - all five required plugin jars under the runtime JMeter tree, with their contract classes.
15. Run `<tmp-runtime>/bin/bzt -h`.
16. Run `<tmp-runtime>/apache-jmeter-5.6.3/bin/jmeter --version`.
17. Move the verified runtime to a unique activation directory `runnerHome/runtimes/<version>-<activation-id>/` without touching the existing active target.
18. Create a temporary symlink to the verified activation directory and atomically replace `runnerHome/current` with that symlink. Only after the switch succeeds may the previous active runtime directory be removed.
19. Upload or verify the Runner bundle.
20. Probe Runner version through the system Python boundary.
21. Mark attempt `succeeded` and node `idle` only if all checks pass.
22. Mark attempt `failed` and node `offline` if checks fail.

The sequence may skip upload and install when `runnerHome/current` points to an existing runtime activation directory for `<version>` and the current runtime passes metadata/version/architecture plus runtime readiness checks.

Rules:

1. P0-03 does not install missing OS packages or dependencies automatically.
2. Runtime Bootstrap removes the need to preinstall Taurus, JMeter, JMeter plugins, `pip`, `gcc`, or `python3-dev` on Load Nodes.
3. The default Load Node base prerequisite baseline is Ubuntu >= 24.04 or Debian >= 12, `tar`, Java >= 11 with Java 17 recommended, system Python >= 3.12 for SurgePilot `runner.py`, and POSIX shell basics.
4. Python used by Taurus comes from the runtime artifact; system Python is used only to run SurgePilot `runner.py`.
5. Initialization must not fall back to system Taurus, system JMeter, or Taurus/JMeter auto-download.
6. P0-03 does not start a Run.
7. P0-03 does not leave a long-running process on the node.
8. All remote paths must be under validated `runnerHome`.
9. SSH host keys must be verified through system known hosts and optional configured known hosts; unknown hosts are rejected.
10. SSH commands must avoid shell injection by using safe quoting or library-supported execution patterns.
11. Runtime artifacts are deployment assets, not Workspace Dependency Files and not Run artifacts. They must be selected by target Load Node architecture, not api-worker architecture.
12. Initialization must not download a runtime from the Load Node and must not require network access from the Load Node.
13. Before implementation freeze, the team must record real target Load Node evidence for `uname -m`, `/etc/os-release`, `java -version`, `python3 --version`, and `tar --version`.

### 10.3 Initialization Failure Mapping

| Failure | Attempt status | Node status | Error code |
| --- | --- | --- | --- |
| SSH connection timeout | `failed` | `offline` | `LOAD_NODE_SSH_TIMEOUT` |
| SSH authentication failure | `failed` | `offline` | `LOAD_NODE_SSH_AUTH_FAILED` |
| Host unreachable | `failed` | `offline` | `LOAD_NODE_SSH_UNREACHABLE` |
| Runner home invalid or not writable | `failed` | `offline` | `LOAD_NODE_RUNNER_HOME_UNWRITABLE` |
| Missing Python | `failed` | `offline` | `LOAD_NODE_PYTHON_MISSING` |
| Missing Java | `failed` | `offline` | `LOAD_NODE_JAVA_MISSING` |
| Unsupported Load Node architecture | `failed` | `offline` | `LOAD_NODE_RUNTIME_ARCH_UNSUPPORTED` |
| Missing local runtime artifact or checksum | `failed` | `offline` | `LOAD_NODE_RUNTIME_ARTIFACT_MISSING` |
| Runtime upload failure | `failed` | `offline` | `LOAD_NODE_RUNTIME_UPLOAD_FAILED` |
| Runtime checksum failure | `failed` | `offline` | `LOAD_NODE_RUNTIME_CHECKSUM_FAILED` |
| Runtime safe extraction failure | `failed` | `offline` | `LOAD_NODE_RUNTIME_EXTRACT_FAILED` |
| Runtime metadata invalid | `failed` | `offline` | `LOAD_NODE_RUNTIME_METADATA_INVALID` |
| Runtime Taurus probe failure | `failed` | `offline` | `LOAD_NODE_RUNTIME_BZT_FAILED` |
| Runtime JMeter probe failure | `failed` | `offline` | `LOAD_NODE_RUNTIME_JMETER_FAILED` |
| Runtime plugin missing | `failed` | `offline` | `LOAD_NODE_RUNTIME_PLUGIN_MISSING` |
| Runtime atomic activation failure | `failed` | `offline` | `LOAD_NODE_RUNTIME_ACTIVATION_FAILED` |
| SSH host key untrusted during initialization | `failed` | `uninitialized` | `LOAD_NODE_SSH_HOST_KEY_UNTRUSTED` |
| SSH host key changed during initialization | `failed` | `uninitialized` | `LOAD_NODE_SSH_HOST_KEY_CHANGED` |
| Decryption failure | `failed` | unchanged or `offline` | `CREDENTIAL_DECRYPT_FAILED` |
| Unexpected worker error | `failed` | `offline` | `LOAD_NODE_INIT_FAILED` |

Failure messages must be English fallback text and must not include secrets.

### 10.4 Runtime Configuration

P0-03 introduces or uses these API/worker settings:

| Setting | Default | Meaning |
| --- | --- | --- |
| `SSH_CREDENTIAL_ENCRYPTION_KEY` | none | Base64-encoded 32-byte AES-GCM master key. Required for API/worker readiness when Load Node credentials are enabled. |
| `LOAD_NODE_DEFAULT_RUNNER_HOME` | `/opt/surgepilot/runner` | Default runner home shown in Web and applied by API. |
| SSH host key trust | Load Node product data | SSH host keys are scanned and explicitly trusted per Load Node. System or file `known_hosts` state is not part of the product execution path. |
| `LOAD_NODE_SSH_CONNECT_TIMEOUT_SECONDS` | `15` | SSH connection timeout. |
| `LOAD_NODE_INIT_COMMAND_TIMEOUT_SECONDS` | `30` | Per-command timeout for remote initialization probes. |
| `LOAD_NODE_INIT_TIMEOUT_SECONDS` | `120` | Overall initialization attempt timeout. |
| `LOAD_NODE_RUNTIME_ARTIFACT_DIR` | `/opt/surgepilot/runtime-artifacts` | Local read-only runtime artifact directory on api-worker. |
| `LOAD_NODE_RUNTIME_VERSION` | none | Runtime artifact version required for initialization. Official `make start-full-stack` injects the computed `make release-runtime` value; low-level compose/manual deployment must set it explicitly or Setup Status remains not configured. |
| `LOAD_NODE_RUNTIME_INSTALL_TIMEOUT_SECONDS` | `120` | Timeout for upload, verify, extract, and activation. |
| `LOAD_NODE_INIT_LOG_TAIL_BYTES` | `65536` | Sanitized log tail persistence limit. |
| `LOAD_NODE_GENERATED_KEY_TYPE` | `ed25519` | Preferred generated SSH key type. |

Rules:

1. Missing or malformed `SSH_CREDENTIAL_ENCRYPTION_KEY` must make credential-dependent API/worker paths not ready or fail fast according to the app's configuration pattern.
2. Do not silently store credentials unencrypted.
3. Do not fall back to a hard-coded encryption key.

4. `LOAD_NODE_JMETER_PATH` and `LOAD_NODE_JMETER_VERSION` are removed from production Runtime Bootstrap configuration; P0 initialization and Run execution derive JMeter from the selected Load Node runtime as `<runnerHome>/current/apache-jmeter-5.6.3/bin/jmeter`.
5. Version switching or rollback is performed only by external deployment processes that adjust the api-worker local artifact directory or `LOAD_NODE_RUNTIME_VERSION`; it is not Runtime Bootstrap product behavior and not an automatic rollback capability in api-worker or Load Node initialization logic.

### 10.5 Runtime Bootstrap Artifact Contract

Runtime artifacts are read by api-worker from:

```text
LOAD_NODE_RUNTIME_ARTIFACT_DIR=/opt/surgepilot/runtime-artifacts
```

The selected runtime version is configured by:

```text
LOAD_NODE_RUNTIME_VERSION=<version>
```

Runtime artifacts use this naming convention:

```text
surgepilot-runtime-linux-<arch>-<version>.tar.gz
surgepilot-runtime-linux-<arch>-<version>.tar.gz.sha256
```

Supported P0 architecture mappings:

| `uname -m` | Runtime artifact arch | Metadata arch |
| --- | --- | --- |
| `x86_64` | `linux-amd64` | `amd64` |
| `amd64` | `linux-amd64` | `amd64` |
| `aarch64` | `linux-arm64` | `arm64` |
| `arm64` | `linux-arm64` | `arm64` |

The Runtime Bootstrap artifact contains runtime Python for Taurus, Taurus `1.16.50`, Apache JMeter `5.6.3`, the exact plugin set `jpgc-casutg`, `jpgc-json`, `jpgc-tst`, `bzm-random-csv`, and `jmeter-plugin-influxdb2-listener`, `bin/bzt`, `apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper`, `metadata.json`, and a whole-archive SHA256 sidecar. The CASUTG jar retains its upstream `jmeter-plugins-casutg-*` filename so Taurus `1.16.50` recognizes CTG support.

### 10.6 Init Hard Rules, Safe Extraction, and Failure Safety

P0 initialization must not run these commands or equivalent actions on the Load Node:

```text
pip install
python -m pip install
apt install
curl
wget
online plugin install
native extension compile
```

Allowed runtime readiness checks are whole-archive SHA256, safe extraction, metadata validation, runtime `bzt -h`, runtime `jmeter --version`, required plugin jar/class validation, and atomic symlink activation.

Safe extraction must reject absolute paths, `..` traversal, symlink escape, hardlink escape where supported by tar metadata, writes outside `runnerHome`, and shell interpolation of unquoted runtime paths. Sanitized logs must not expose SSH credentials, private keys, passwords, passphrases, bearer tokens, CSRF tokens, MinIO secrets, runtime artifact credentials, secret environment variables, or full api-worker internal artifact directory details.

Runtime installation is idempotent and failure-safe:

1. If `current` already points to an activation directory whose metadata/version/arch and runtime readiness checks pass, api-worker may skip upload and activation.
2. Upload, SHA256, extraction, metadata, `bzt`, JMeter, plugin, candidate-move, or temporary-symlink failures must not affect an existing `current` runtime.
3. Only a fully verified runtime may replace `current`; the new runtime directory is distinct from the active target until the symlink switch succeeds.
4. `current` is changed by atomic symlink replacement. The previous active runtime directory may be removed only after the switch succeeds, and cleanup failure must not roll back the already-active new runtime.
5. Runtime Bootstrap, product UI, API, api-worker, and Load Node initialization logic do not automatically switch back to an older version, restore deployment config, perform general old-version garbage collection, or orchestrate gray release/rollback.

### 10.7 Runner and Taurus YAML Handoff

P0 Run execution must use the activated runtime `bzt`:

```bash
${RUNNER_HOME}/current/bin/bzt -n surgepilot.yml
```

Rules:

1. `RUNNER_HOME` is injected by api-worker through the Runner execution contract.
2. Runner does not rely on system `PATH` to locate `bzt`.
3. Runner does not import api-worker internals.
4. The system Python boundary remains only for SurgePilot Runner itself.
5. `-n` skips `/etc/bzt.d` and `~/.bzt-rc` as defense-in-depth.
6. Generated Taurus YAML must be self-contained for `bzt -n` and declare the Taurus module class aliases, HTTP protocol handler, and `settings.aggregator` that would otherwise come from Taurus global config.

Execution bundle generation must write a Load Node specific JMeter path:

```yaml
modules:
  jmeter:
    path: <runnerHome>/current/apache-jmeter-5.6.3/bin/jmeter
    version: "5.6.3"
    detect-plugins: false
    fix-log4j: false
    fix-jars: false
    force-ctg: false
```

Rules:

1. `jmeter.path` is derived from the selected Load Node `runnerHome`.
2. P0 must not use one global `settings.load_node_jmeter_path` for all nodes.
3. No path service is required for P0; passing `runner_home` into bundle building is sufficient.
4. `TAURUS_DISABLE_DOWNLOADS` is not an acceptance criterion and is not the primary no-download mechanism.
5. `force-ctg` defaults to `false` and is set to `true` only when steps require Concurrent Thread Group.

### 10.8 Runtime Bootstrap Test Expectations

Worker and initializer tests should cover architecture detection and mapping, unsupported architecture, missing local artifact/checksum, SFTP `upload_stream`, whole-archive SHA256 failure, safe extraction rejection for absolute paths / `..` / symlink escape, metadata version and architecture mismatch, runtime `bzt -h` failure, runtime JMeter version failure, required plugin missing, successful atomic `current` switch, valid-runtime reinstall skip, failed install preserving previous `current`, sanitized logs, and the init hard rules forbidding pip, apt, curl, wget, online plugin install, and native compilation.

---

## 11. Frontend Contract

### 11.1 Routes and Navigation

Routes:

```text
/resources/load-nodes
/resources/load-nodes/new
```

Rules:

1. Both routes use `AppLayout`.
2. Both routes require authentication.
3. The Resources navigation group includes Load Nodes.
4. No separate Public/Private page is introduced.
5. No P1/P2 Resources routes are introduced.
6. Business data is fetched with TanStack Query, not React Router loader data.
7. Web uses generated client/types from `@surgepilot/contracts`.
8. Web must not access PostgreSQL, SSH, or Load Nodes directly.

### 11.2 Load Nodes List Page

The list page includes:

1. Page title: `Load Nodes`.
2. Primary action: `Register Load Node`.
3. Search input.
4. Scope filter: All, Public, Private.
5. Status filter based on `LoadNodeStatus` enum.
6. Table or card list with:
   - Host.
   - SSH port.
   - SSH user.
   - Scope.
   - Status badge.
   - Maintainer.
   - Last checked.
   - Runner version.
   - Current Run, displayed as empty/null in P0-03.
7. Row actions:
   - View initialization logs.
   - Initialize / Re-initialize.
   - Edit.
   - Update credentials.
   - Disable / Enable.
   - Archive.
8. Role-aware action visibility:
   - Public management actions visible only to Admin.
   - Private management actions visible to authenticated current Workspace users.
9. Backend errors remain authoritative and must be surfaced.

Empty states:

1. No nodes: guide users to register a Private node; Admin copy may mention Public node registration.
2. No Public nodes: explain Admin can register Public nodes.
3. No Private nodes: explain current Workspace users can register Private nodes.
4. Filtered empty: clear filters action.

### 11.3 Register Load Node Page

The register page includes:

1. Scope selector:
   - Public.
   - Private.
2. Public selection disabled or hidden for non-Admin users.
3. Host/IP field.
4. SSH port field, default `22`.
5. SSH user field.
6. Runner home field, default from API/config contract.
7. Auth type selector:
   - Password.
   - Private key upload/paste.
   - Generate keypair.
8. Credential input panel matching auth type.
9. Maintainer field.
10. Remark field.
11. Submit button.

Rules:

1. Existing credential values are never shown.
2. Password and private key inputs are never persisted in browser storage.
3. Generated public key is shown after successful creation and remains available through node details when `authType='generated_key'`.
4. The page redirects to `/resources/load-nodes` after successful creation unless generated-key UX requires showing the public key confirmation first.
5. Validation errors use API `code` values, not API message text, for localization branching.

### 11.4 Edit and Credential Update UX

Edit and credential update are performed from the list page. P0-03 introduces no separate Load Node detail route.

Edit metadata form:

1. Host.
2. SSH port.
3. SSH user.
4. Runner home.
5. Maintainer.
6. Remark.

Credential update form:

1. Auth type selector.
2. Full credential replacement input.
3. Warning that existing credential cannot be viewed and replacement requires re-initialization.

Rules:

1. Generic edit form must not contain hidden credential fields.
2. Credential form must call `/credentials`.
3. Successful connection or credential changes show that re-initialization is required.

### 11.5 Initialization UX

Initialization UI includes:

1. Initialize or Re-initialize action.
2. Confirmation if node is currently `idle` and re-initialization may make it temporarily unavailable.
3. Status feedback while `initializing`.
4. Link/button to view latest initialization log.
5. Error state that displays stable error code and safe message.

Initialization log viewer includes:

1. Attempt list.
2. Attempt status.
3. Start/finish times.
4. Error code and message.
5. Sanitized log tail in monospace block.
6. Copy log action only if it copies sanitized content.

### 11.6 Status Badge Rules

| Status | Badge tone | Copy |
| --- | --- | --- |
| `uninitialized` | neutral | Uninitialized |
| `initializing` | info/progress | Initializing |
| `idle` | success | Idle |
| `busy` | warning | Busy |
| `offline` | danger | Offline |
| `quarantined` | danger | Quarantined |
| `disabled` | neutral/disabled | Disabled |

Rules:

1. Badge values come from generated contract enum.
2. Do not infer status from frontend timers.
3. Frontend refetches while initializing.
4. Frontend must not set status locally except optimistic UI that is immediately reconciled with API response.

---

## 12. Security, Permission, and Workspace Rules

### 12.1 Public and Private Boundary

Rules:

1. `scope='public'` rows have `workspace_id=NULL`.
2. `scope='workspace'` rows have `workspace_id=current Workspace ID`.
3. Public management operations require Admin.
4. Private management operations require current Workspace access.
5. Private queries must filter by current Workspace.
6. Cross-Workspace Private lookup returns `404 RESOURCE_NOT_FOUND`.
7. No route path contains Workspace ID.
8. Response writes back actual `x-workspace-id` according to global API middleware rules.

### 12.2 Credential Safety

Rules:

1. Password, private key, and passphrase are accepted only in request bodies.
2. Password, private key, and passphrase are encrypted before persistence.
3. The API never returns plaintext credential values.
4. The API never returns encrypted credential blobs.
5. Admin cannot view or export Private plaintext credentials.
6. Logs, audit details, errors, OpenAPI examples, snapshots, and test fixtures must not contain real secrets.
7. Web must not store credentials in localStorage, sessionStorage, IndexedDB, URL query params, or route state that survives refresh.
8. Decryption failure maps to `CREDENTIAL_DECRYPT_FAILED` and must not expose cryptography exception text.
9. Platform-generated private key is secret and follows the same encryption and non-return rules.
10. Platform-generated public key is not secret and is returned for generated-key nodes.

### 12.3 Path and Command Safety

Rules:

1. `runnerHome` must be an absolute POSIX path.
2. `runnerHome` must not be `/`.
3. `runnerHome` must not contain `..`, backslash, NUL, newline, carriage return, shell control characters, or unprintable characters.
4. P0 validation rejects whitespace in `runnerHome` to simplify safe command generation.
5. Remote commands must use safe quoting or library primitives.
6. API must never interpolate raw user input into shell commands without escaping.
7. Initialization must keep all SurgePilot-created files under `runnerHome`.
8. P0-03 must not implement arbitrary command execution.

### 12.4 Host and User Validation

Rules:

1. `host` must be a hostname or IP-like target without scheme, slash, path, query, fragment, whitespace, or shell control characters.
2. `host` max length is 255.
3. `sshPort` is integer `1..65535`.
4. `sshUser` must be a conservative Linux username string matching `^[A-Za-z_][A-Za-z0-9._-]{0,31}$`.
5. `maintainer` and `remark` have length limits and must be sanitized before display.

### 12.5 Audit Events

P0-03 emits audit events for:

1. `load_node.created`.
2. `load_node.updated`.
3. `load_node.archived`.
4. `load_node.disabled`.
5. `load_node.enabled`.
6. `load_node.credential_updated`.
7. `load_node.initialization_requested`.
8. `load_node.initialization_succeeded`.
9. `load_node.initialization_failed`.

Audit event context rules:

1. `load_node.initialization_requested` is emitted in the HTTP request transaction that queues the attempt.
2. `load_node.initialization_requested` uses the current HTTP `requestId`.
3. `load_node_initialization_attempts.request_id` stores the queuing HTTP `requestId`.
4. `load_node.initialization_succeeded` and `load_node.initialization_failed` are emitted by `api-worker`.
5. Worker-emitted initialization audit events include `attemptId`, `requestedBy`, and `queuedRequestId` from the attempt row.
6. Worker-emitted initialization audit events use a worker-generated request/correlation ID when the audit schema requires `requestId`.
7. Worker-emitted initialization audit events do not require browser session, CSRF token, or active HTTP request context.

Audit details include:

1. `nodeId`.
2. `scope`.
3. `workspaceId` when Private.
4. `host`.
5. `sshPort`.
6. `status`.
7. `attemptId`.
8. `errorCode`.

Audit details must not include:

1. Password.
2. Private key.
3. Private key passphrase.
4. Encrypted credential blobs.
5. AES nonce/tag/key IDs.
6. Raw logs containing secrets.

---

## 13. Runner, Run, and Later Slice Handoff

### 13.1 P0-04 Handoff

P0-04 will build on P0-03 by adding:

1. Run state machine.
2. Run Snapshot.
3. Node lease table and atomic lease acquisition.
4. Busy transition when a Run leases a node.
5. Runner callback endpoints.
6. Heartbeat storage in `last_heartbeat_at` or Run-specific tables.
7. Force-kill cleanup.
8. Quarantine transition and clearance rules.
9. Stale lease recovery.
10. Stop idempotency and release behavior.

P0-03 must leave clear service boundaries so P0-04 can reuse:

1. Load Node lookup and authorization.
2. Credential decryption service.
3. SSH connection abstraction.
4. Safe `runnerHome` path handling.
5. Status update helpers that do not override Busy or terminal cleanup rules.

### 13.2 P0-06 Handoff

P0-06 Test Plan / Run Now will use:

1. `GET /load-nodes` with `scope` and `status=idle` filters.
2. Contract enum values for scope and status.
3. Public vs Private selection rules.
4. Manual single-node only behavior.

P0-03 must not add Test Plan UI or Run Now UI.

### 13.3 P0-07 Handoff

P0-07 Run Report uses these P0-03 fields:

1. Node ID.
2. Node host.
3. Node status at execution time from Run Snapshot.
4. Runner version / bundle version if captured by P0-04/P0-06.

P0-03 does not implement report pages.

---

## 14. Tests

### 14.1 API Unit Tests

Cover:

1. `host` validation.
2. `sshPort` validation.
3. `sshUser` validation.
4. `runnerHome` validation.
5. Public/private scope validation.
6. Public row requires `workspace_id=NULL`.
7. Private row requires `workspace_id`.
8. Duplicate active node conflict.
9. Archive allows same host/port/user re-registration.
10. Status transition helper rejects unsafe Busy changes.
11. Credential request validation by auth type.
12. AES-GCM encryption and decryption round trip.
13. Missing/malformed encryption key behavior.
14. Credential response redaction.
15. Generated keypair public/private handling.
16. Initialization log redaction.
17. Initialization log tail truncation.

### 14.2 API Integration Tests

Cover:

1. User lists Public and current Workspace Private nodes.
2. User cannot create Public node.
3. Admin can create Public node.
4. User can create Private node.
5. `workspaceId` in request body is ignored/rejected according to schema.
6. Create response never includes submitted credential material.
7. Get/list response never includes encrypted blobs.
8. Patch metadata works for allowed actor.
9. Any successful PATCH sets status to `uninitialized`.
10. Patch cannot change scope/status/credential fields.
11. Credential update requires full replacement.
12. Credential update synchronizes `load_nodes.auth_type` and `load_node_credentials.auth_type` in one transaction.
13. Credential update moves node to `uninitialized`.
14. Delete archives node and excludes it from default list.
15. Busy node archive/update/credential/init actions are rejected.
16. Duplicate initialize while `initializing` returns existing attempt with `202`.
17. Idle initialize with `force=false` returns `LOAD_NODE_ACTION_NOT_ALLOWED`.
18. Idle initialize with `force=true` creates a re-initialization attempt.
19. Disable and enable behavior.
20. Init attempt list/detail respects parent visibility.
21. Cross-Workspace Private lookup returns 404.
22. Missing CSRF on writes fails.
23. Missing Workspace header falls back to default Workspace.
24. Error shapes match `{code, message, requestId, details?}`.

### 14.3 Worker Tests

Use a fake SSH adapter by default.

Cover:

1. Successful initialization marks attempt `succeeded` and node `idle`.
2. SSH timeout marks attempt `failed` and node `offline`.
3. SSH auth failure redacts credential detail.
4. Missing Python, Java, `tar`, unsupported architecture, missing runtime artifact/checksum, upload, checksum, extraction, metadata, runtime `bzt`, runtime JMeter, plugin, and activation failures map to stable error codes.
5. Runner home creation failure maps to stable error.
6. Worker claim prevents duplicate concurrent execution.
7. Worker crash before completion is recovered by timeout handling: the stale `running` attempt becomes `failed` with `LOAD_NODE_INIT_FAILED`, and the node becomes `offline`.
8. A late initializer completion cannot overwrite a stale/failed attempt or revive the node to `idle` unless the attempt is still the current active `running` attempt.
9. Sanitized log tail is bounded.
10. Decrypted credential values are not logged.
11. Worker-emitted initialization audit events include `attemptId`, `requestedBy`, and `queuedRequestId`.

### 14.4 Contract Tests

Cover:

1. OpenAPI has `/v1/load-nodes` paths and operation IDs.
2. Public API schemas use camelCase.
3. Public API schemas do not expose credential secret fields or encrypted fields.
4. Status enum includes all P0 values.
5. Scope enum is `public | workspace`.
6. Auth type enum is `password | private_key | generated_key`.
7. Error codes are registered.
8. Write operations document CSRF.
9. Business operations document Workspace header.

### 14.5 Web Tests

Cover:

1. Load Nodes list loading state.
2. Empty state.
3. Error state.
4. Search/filter behavior.
5. Status badges for all enum values.
6. Non-Admin cannot choose Public create action.
7. Admin can choose Public create action.
8. Private node registration form validation.
9. Password credential mode.
10. Private key credential mode.
11. Generated keypair mode and public key display.
12. Existing credential is never displayed in edit/update UI.
13. Initialize action and initializing state.
14. Initialization log viewer.
15. Disable/enable actions.
16. Archive confirmation and Busy error display.

### 14.6 E2E / Smoke

Add one lightweight Playwright smoke if the Slice implementation already has stable test infrastructure:

1. Log in.
2. Open `/resources/load-nodes`.
3. Register a Workspace Private node using fake or test-mode initialization backend.
4. Confirm it appears in list.
5. Trigger initialization or fake initialization.
6. Open initialization log viewer.
7. Archive the node.

If full browser smoke is unstable during P0-03, document the gap in implementation backfill and ensure API + Web component coverage exists.

---

## 15. Done When

P0-03 is done when:

1. `docs/sdd/slices/P0-03-load-nodes.md` matches implemented behavior or has implementation backfill.
2. Alembic migration `0004_p0_03_load_nodes.py` exists and applies cleanly after P0-02.
3. `load_nodes`, `load_node_credentials`, and `load_node_initialization_attempts` exist with required constraints.
4. API implements the public Load Node endpoints under `/api/v1/load-nodes`.
5. OpenAPI export includes Load Node schemas and operations under `/v1/load-nodes`.
6. Generated Web client/types are updated and consumed through `@surgepilot/contracts`.
7. Web implements `/resources/load-nodes` and `/resources/load-nodes/new`.
8. Public node management is Admin-only in backend.
9. Private node management is Workspace-aware in backend.
10. Credential material is encrypted at rest.
11. Credential material is never returned by list/get/create/update responses.
12. Credential update uses explicit action endpoint.
13. Generated keypair mode stores private key encrypted and exposes only public key.
14. Initialization is queued and run by `api-worker`, not inside the HTTP request.
15. Initialization logs are sanitized and bounded.
16. Node status badges use generated contract enum values.
17. Busy node unsafe actions are rejected.
18. Disable/enable/archive behavior works.
19. API, worker, contract, and Web tests for this slice pass.
20. `make generate-contracts` passes after API schema changes.
21. `make verify` passes, or any temporary gap is explicitly documented with reason and replacement commands.

---

## 16. Review Checklist

Before claiming completion, verify:

- [ ] The change stays inside P0-03 scope.
- [ ] No Auto allocation, multi-node execution, Node Count, or Selected Nodes multi-select was introduced.
- [ ] No Run state machine, Runner callback, Stop, heartbeat timeout, or artifact behavior was implemented in P0-03.
- [ ] Public node mutations require Admin in backend.
- [ ] Private node queries and mutations are filtered by current Workspace in backend.
- [ ] Cross-Workspace Private node lookup does not leak existence.
- [ ] API responses never include plaintext SSH password, private key, passphrase, or encrypted credential blobs.
- [ ] Admin cannot view or export Private node plaintext credentials.
- [ ] `SSH_CREDENTIAL_ENCRYPTION_KEY` is required and not hard-coded.
- [ ] `runnerHome`, `host`, and `sshUser` validation prevent path and command injection risks.
- [ ] Initialization runs through `api-worker`.
- [ ] Initialization logs are redacted and bounded.
- [ ] Generated OpenAPI is fresh.
- [ ] Web uses generated client/types from `@surgepilot/contracts`.
- [ ] Web does not connect to SSH, PostgreSQL, MinIO, or Load Nodes directly.
- [ ] P1/P2 routes and capabilities were not added.

---

## 17. Implementation Backfill



### 17.1 Actual implementation differences

1. Load Node initialization is executed by the separate `api-worker` process using PostgreSQL row claiming for queued attempts and a PostgreSQL advisory lock around stale running-attempt recovery. The HTTP API only queues attempts.
2. The production P0 initializer performs real SSH/SFTP setup through `ParamikoSshSftpAdapter`: it verifies host keys, decrypts stored credentials only in worker memory, prepares `runnerHome`, and writes sanitized bounded logs. The original implementation checked system Taurus and a configured JMeter path; Runtime Bootstrap supersedes that readiness rule with base-prerequisite checks, local runtime artifact upload, checksum verification, safe extraction, runtime metadata validation, runtime-contained Taurus/JMeter/plugin probes, atomic `current` activation, Runner bundle upload, and Runner version probe before marking the node `idle`. `DeterministicLoadNodeInitializer` remains available only for deterministic unit tests.
3. `current_run_id` is present on `load_nodes` without a foreign key, as required for P0-04. `last_init_attempt_id` has a nullable foreign key to `load_node_initialization_attempts`.
4. Generated-key mode stores the generated private key encrypted and exposes only `generatedPublicKey` plus a non-secret public-key fingerprint in API responses; password and uploaded private-key credentials do not expose fingerprints.
5. The Playwright Load Node smoke covers explicit SSH host-key scan confirmation, registration, initialization UI convergence, sanitized log display, and archive through a deterministic mocked API boundary. Real SSH host-key verification and initialization remain covered by the dedicated API SSH E2E profiles rather than the default browser fixture.
6. Active Load Node lookups exclude archived rows; mutating services also reject archived nodes defensively. `enable` is limited to `disabled -> uninitialized`, and `disable`/`archive` reject `initializing` to avoid orphaning active initialization attempts.
7. `api-worker` executes the remote SSH/SFTP initializer outside the database transaction that claims the attempt; it uses short transactions to claim, decrypt/read inputs, and persist the precomputed result. This avoids holding row locks while remote SSH commands run.
8. The SSH smoke images provide only base OS prerequisites such as SSH, Java, system Python for `runner.py`, `python3-click`, and `tar`; they must not install Taurus, JMeter, JMeter plugins, pip, or compiler toolchains as a separate runtime source. SSH smoke coverage exercises the runtime artifact activation path instead of relying on system Taurus/JMeter.

### 17.2 Final API contract adjustments

1. Public API paths are implemented under `/api/v1/load-nodes`; exported OpenAPI paths are under `/v1/load-nodes`.
2. Added schemas for Load Node summaries/details, credential input and replacement, initialize response, initialization-attempt summaries/details, and list envelopes.
3. List endpoints use offset pagination envelopes with `items`, `limit`, `offset`, and `total`.
4. Public response schemas include `credentialConfigured`, `credentialFingerprint`, and `generatedPublicKey` when applicable. `credentialFingerprint` is null for password and uploaded private-key credentials, and responses exclude password, private key, passphrase, ciphertext, nonce, tag, and encryption key material.
5. Write endpoints require `x-csrf-token`; business endpoints document and honor `x-workspace-id` with Default Workspace fallback.
6. `enableLoadNode` documents `409` responses because only disabled nodes can be enabled and Busy nodes remain protected by P0-04.

### 17.3 Final migration names

1. Added Alembic migration `apps/api/migrations/versions/0004_p0_03_load_nodes.py`.
2. The migration creates `load_nodes`, `load_node_credentials`, and `load_node_initialization_attempts` with P0 constraints, partial uniqueness, status/filter indexes, credential material checks, and `current_run_id` without a Run FK.

### 17.4 Tests and verification commands

Automated coverage added:

1. API service tests: validators, duplicate active node conflict, archive re-registration, credential encryption/decryption, generated keypair handling, credential redaction, log redaction/truncation, status transition guards, force initialization rules, archived mutation rejection, enable-only-from-disabled behavior, and stale attempt recovery.
2. API route tests: Public Admin guard, Private creation/listing, default Workspace fallback, cross-Workspace 404, CSRF write guard, credential redaction, initialize/idempotency, disable/enable, Busy and initializing state guards, archived mutation rejection, archive, and init log visibility.
3. Worker tests: queued attempt processing, stale running attempt recovery, initializer execution outside database transactions, late initializer completion guard, advisory-lock path, default session factory path, and `api-worker` CLI once/loop behavior.
4. Contract tests: `/v1/load-nodes` operation IDs, enum values, CSRF/Workspace headers, camelCase schemas, and absence of credential secret/ciphertext fields.
5. Web tests: list/empty/error/filter states, role-aware Public create visibility, credential modes, generated public key success screen, initialization logs, disable/enable, archive, and credential non-reveal behavior.
6. Playwright smoke: scan and confirm the SSH host key, register a Private Load Node, converge the initialization UI through the mocked browser/API boundary, view sanitized logs, and archive. A companion spec covers actionable `CREDENTIAL_DECRYPT_FAILED` guidance; real API/SSH initialization remains in the dedicated SSH E2E profiles.
7. Real initializer unit tests: base-prerequisite checks, runtime artifact selection/upload, safe extraction, metadata validation, runtime Taurus/JMeter/plugin probes, atomic activation, runner bundle upload, stable error-code mapping, and secret redaction.
8. Optional real SSH smoke: Docker-backed SSH Load Node success path for P0-03 initializer plus P0-04 runner SSH control.

Verification commands run successfully:

```bash
make generate-contracts
make verify
uv run --all-packages pytest apps/api/tests/test_p0_03_load_nodes_service.py apps/api/tests/test_p0_03_load_nodes_api.py apps/api/tests/test_p0_03_load_nodes_worker.py tests/contract/test_p0_03_load_nodes_openapi.py --cov=app.routes.load_nodes --cov=app.services.load_nodes --cov=app.worker --cov-branch --cov-report=term-missing --cov-report=annotate:cov_annotate -q
pnpm exec playwright test tests/e2e/p0_03_load_nodes.spec.ts
make verify-runner-ssh
uv run --all-packages pytest apps/api/tests/test_p0_03_load_node_initializer.py apps/api/tests/test_p0_03_initializer_ssh_e2e.py -q
```

Coverage summary from `make verify`: API total coverage 92.99%; diff coverage 100%; Web Vitest 23 passed; Runner tests 2 passed; Playwright P0-03 smoke 1 passed.

### 17.5 Remaining risks or known gaps

1. The P0-03 initializer verifies setup and the uploaded Runner bootstrap over SSH/SFTP, but it still does not start a Run or execute a Taurus/JMeter load test. Run execution remains owned by later P0 slices.
2. Load Node `busy`, heartbeat, lease release, quarantine entry/clearance, and Run-driven cleanup are still reserved for P0-04.
3. The UI shows generated public key material because it is public installation material; no private key, password, passphrase, or ciphertext is displayed.

### 17.6 Preconditions for later P0 slices

1. P0-04 must reuse backend Load Node visibility/authorization, credential decryption, and safe status helpers; it must not import API internals into `apps/runner`.
2. P0-04 owns adding the `current_run_id` foreign key after the Runs table exists and must preserve the rule that P0-03 does not release `busy` nodes.
3. P0-06 must select exactly one visible `idle` Load Node and must treat all other statuses as unavailable.
4. P0-07 may read node identity/version fields for reports, but artifact access remains API-mediated and must not expose MinIO credentials.

Do not use backfill to expand P0 scope.

## 17A. P0-03 Independent Review Report


### 17A.1 Coverage review (`pytest-coverage`)

- Ran API coverage through `make verify` and a P0-03 annotated coverage pass.
- `make verify` result: 116 API/contract tests passed, 3 skipped; total API coverage 92.40%; diff coverage 100%.
- P0-03 targeted annotated pass result: 22 passed. Reviewed uncovered lines in `routes/load_nodes.py`, `services/load_nodes.py`, and `worker.py`; remaining uncovered branches are negative/defensive branches already covered by repository-level threshold and not P0/P1 blockers.
- Added worker tests during review to cover advisory lock, default session factory, and CLI once/loop paths.

### 17A.2 React/data-fetching review (`vercel-react-best-practices`)

- React Query is used for Load Node list and log data, with polling only while nodes are `initializing`.
- Mutations invalidate the Load Node query boundary instead of manually mutating stale local copies.
- The Web client consumes generated types/functions from `@surgepilot/contracts` and does not use relative imports into generated contract files.
- Review fix: removed an unnecessary `as never` cast from the init-attempt client wrapper and reset transient credential form state whenever the credential modal opens/closes or succeeds.

### 17A.3 UI/UX consistency review (`ui-ux-pro-max` and `frontend-design`)

- Routes reuse `AppLayout`, existing tokens, dark glass surfaces, rounded cards, shadcn/Radix dialog behavior, and P0-00/P0-01/P0-02 spacing/action hierarchy.
- Empty, loading, error, filtered-empty, success, log, edit, credential replacement, archive, disabled action, and Busy-protection states are represented.
- Node statuses are displayed in English as `Uninitialized / Initializing / Idle / Running / Offline / Quarantined / Disabled`.
- UI copy is English-only and uses standard industry terms where appropriate, including SSH-related labels. Raw sanitized setup output remains available in the log viewer for troubleshooting.

### 17A.4 Playwright review (`playwright-cli`)

- Ran `pnpm e2e -- tests/e2e/p0_03_load_nodes.spec.ts tests/e2e/p0_03_load_node_registration_error.spec.ts`.
- Result: 2 passed.
- Covered paths: the mocked browser/API boundary verifies SSH host-key scan and trusted-key propagation, registration, initialization polling from `initializing` to `idle`, sanitized log display, archive, and actionable credential-encryption failure guidance. Real API/SSH host-key verification and initialization remain covered by the dedicated SSH E2E profiles.

### 17A.5 Security review (`fastapi` + manual checklist)

- Credential material is AES-256-GCM encrypted using `SSH_CREDENTIAL_ENCRYPTION_KEY`; plaintext is accepted only on write endpoints and is not returned by API responses.
- Public Load Node mutations require Admin in backend service checks; Private nodes are filtered by current Workspace.
- Cross-Workspace Private lookup returns `RESOURCE_NOT_FOUND`, avoiding existence leaks.
- `host`, `sshUser`, and `runnerHome` validation reject unsafe characters, non-absolute paths, and traversal.
- Browser writes require CSRF through `x-csrf-token`; business requests carry `x-workspace-id` or fall back to the user's default Workspace.
- Runner remains independent; no Web or Runner code receives PostgreSQL, MinIO, or credential-secret access.

### 17A.6 Architecture and scope review

- No Redis, Celery, RabbitMQ, Kafka, Kubernetes, scheduler, auto allocation, multi-node execution, Test Plan, Run Now, Run state machine, Runner callback, Stop, heartbeat, artifact, API Catalog, monitoring, or P1/P2 route was introduced.
- `api-worker` is a separate process and uses PostgreSQL coordination per ADR-0006.
- `apps/runner` does not import API internals.
- P0-04/P0-06/P0-07 handoff points remain explicit and non-user-visible beyond the P0-03 Load Node management surface.

### 17A.7 Review conclusion

No P0/P1 blocking issues remain after the review fixes above.

---

## 17B. P0-03 State Guard Follow-up Review Report


### 17B.1 Review findings assessed

1. `enable` could previously change `busy` or other non-disabled states to `uninitialized`. This was valid because P0-03 must not clear Busy; P0-04 owns Busy release.
2. Archived node protection was incomplete for shared lookup paths. This was valid because archived nodes must be excluded from normal active access and must not accept mutations.
3. `disable` and `archive` could previously act on `initializing` nodes. This was valid because that can leave queued/running initialization attempts to finish or stale-recover after the user-visible state was changed.

### 17B.2 Fix review

1. Active lookup now filters `archived_at is null`; service-layer mutation helpers also reject archived nodes defensively with `RESOURCE_NOT_FOUND`.
2. `enable` now allows only `disabled -> uninitialized`; `busy` returns `LOAD_NODE_BUSY`, and all other non-disabled states return `LOAD_NODE_ACTION_NOT_ALLOWED`.
3. `disable` and `archive` now reject `initializing` with `LOAD_NODE_ACTION_NOT_ALLOWED` and continue to reject `busy` with `LOAD_NODE_BUSY`.
4. The exported OpenAPI contract documents `409` for `enableLoadNode`.
5. Added service and API regression tests for Busy, initializing, and archived state guards.

### 17B.3 Verification

Commands run successfully:

```bash
make generate-contracts
uv run --all-packages pytest apps/api/tests/test_p0_03_load_nodes_service.py apps/api/tests/test_p0_03_load_nodes_api.py tests/contract/test_p0_03_load_nodes_openapi.py -q
make verify
pnpm exec playwright test tests/e2e/p0_03_load_nodes.spec.ts
```

Results:

1. Targeted P0-03 API/service/contract tests: 23 passed.
2. `make verify`: API/contract 123 passed, 3 skipped; API coverage 92.99%; diff coverage 100%; Web Vitest 23 passed; Runner tests 2 passed.
3. Playwright P0-03 smoke: 1 passed.

### 17B.4 Follow-up review conclusion

No P0/P1 blocking issues remain after the state guard fixes.

---

## 17C. P0-03 Review Backfill

1. Private key credentials are parsed with `cryptography` before acceptance; checking only for the text `PRIVATE KEY` is no longer sufficient.
2. Stale initialization recovery is guarded so orphaned or superseded attempts cannot mark a newer healthy node offline.
3. The API schema default for `runnerHome` now follows `LOAD_NODE_DEFAULT_RUNNER_HOME`; the Web registration form no longer hardcodes a competing default.
4. Generated public keys returned after credential replacement are displayed once, matching the first-registration copy behavior.
5. Idle node re-initialization now requires user confirmation in Web.
6. `LOAD_NODE_JMETER_MISSING` is covered by the OpenAPI error registry contract test.

---

## 17D. Runtime Bootstrap Documentation Backfill

1. Runtime Bootstrap is now merged directly into this existing P0-03 Slice SDD instead of being carried by a separate addendum file.
2. `docs/sdd/p0-runtime-bootstrap-plan.md` remains the implementation baseline for packaging, deployment artifact publication, version switching, and rollback boundaries.
3. `docs/sdd/adr/ADR-0007-p0-runtime-bootstrap-packaging.md` remains the single ADR for the runtime packaging decision.
4. The Runtime execution correctness amendment adds only nullable `runtime_version` persistence and corresponding API/Runner contract fields; it does not add API routes, UI routes, or product runtime-management capability.
5. Runtime Bootstrap is P0 execution-loop support only; automatic rollback, runtime catalog, runtime upload UI, gray release, old-runtime cleanup, and automatic OS/package installation remain out of scope.

---

## 18. Handoff to Later Slices

Later slices must know:

1. Load Node status and scope enums are contract-owned by P0-03.
2. `idle` is the only selectable status for P0 manual Run selection, and the persisted `runtimeVersion` must equal the configured `LOAD_NODE_RUNTIME_VERSION`.
3. `busy` and `quarantined` are defined here but completed by P0-04.
4. Public nodes have `workspaceId=null`.
5. Private nodes are filtered by current Workspace.
6. Credential decryption service is backend-only and is reused by run-start logic.
7. `runnerHome` path validation must be reused by run bundle upload and cleanup logic.
8. Initialization does not guarantee a node remains healthy forever; P0-04 heartbeat and cleanup rules still own active Run safety.
9. Generated public key is public and is shown when `authType='generated_key'`; generated private key is secret and never returned.
10. Tags remain out of scope until P1.
11. Later Run slices must execute Taurus through `${RUNNER_HOME}/current/bin/bzt -n surgepilot.yml`, not through system `PATH`.
12. Later bundle-generation slices must derive the Taurus JMeter path from the selected node `runnerHome` as `<runnerHome>/current/apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper`, not from one global preinstalled JMeter setting.
13. Runtime version switching or rollback is an external deployment operation that changes api-worker local artifacts or `LOAD_NODE_RUNTIME_VERSION`; product code and Load Node initialization logic must not implement automatic rollback orchestration.

---

## 17E. Runtime Bootstrap Implementation Backfill

1. P0-03 initialization now installs or reuses a Runtime Bootstrap artifact from api-worker local read-only storage instead of checking system Taurus or system JMeter.
2. The initializer selects `surgepilot-runtime-linux-<arch>-<version>.tar.gz` from `LOAD_NODE_RUNTIME_ARTIFACT_DIR` using `uname -m` mapping and `LOAD_NODE_RUNTIME_VERSION`, uploads the archive through SFTP `upload_stream`, validates SHA256, safely extracts under `runnerHome` with symlink/path traversal escape rejection, checks runtime metadata including supported Python version, verifies self-contained runtime files, probes runtime `bin/bzt -h`, probes runtime JMeter `--version`, verifies the required plugin jar as a non-empty zip/jar, and atomically activates `runnerHome/current` with retry-safe stale-target replacement. A damaged active same-version target is repaired by exchanging it with the fully validated staged candidate before deleting the displaced directory. The already-installed skip path performs the same runtime readiness probes before skipping upload.
3. The implemented settings are `LOAD_NODE_RUNTIME_ARTIFACT_DIR`, `LOAD_NODE_RUNTIME_VERSION`, and `LOAD_NODE_RUNTIME_INSTALL_TIMEOUT_SECONDS`.
4. Run execution handoff uses `${RUNNER_HOME}/current/bin/bzt -n surgepilot.yml`; generated Taurus YAML points to `<runnerHome>/current/apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper`, and the wrapper delegates to adjacent real JMeter. Generated YAML also declares the Taurus module aliases and HTTP protocol handler required by `bzt -n`, and pins JMeter mutation/download-related flags off.
5. E2E acceptance uses production `scripts/release_runtime_artifact.py --fixed-version p0-e2e` with persistent output/build/cache directories to build or reuse the runtime artifact. The former SSH-image seed helper is removed; production startup, SSH E2E, and compatibility verification now share one runtime source, packaging flow, manifest, SHA256, and reuse invariant. First use may need network access for runtime construction; subsequent runs reuse the production builder cache/output. Production runtime artifacts remain release/deployment assets governed by ADR-0007.
6. Verification added: initializer unit tests, run-control bundle tests, Runner CLI tests, E2E verifier tests, plus the P0 SSH/API E2E commands listed in the final PR verification.
7. Successful initialization stores the activated Runtime metadata version on both the attempt and Load Node as `runtimeVersion`. Missing or mismatched Runtime versions make a node non-selectable until reinitialization.
8. Runtime UI, catalog, user upload, MinIO runtime storage, automatic rollback, old-runtime cleanup, online install, and OS package install remain out of scope.
