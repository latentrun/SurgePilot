# P0-04: Run State Machine and Runner Protocol

- Document status: Draft v1 for implementation
- Product: SurgePilot
- Document path: `docs/sdd/slices/P0-04-run-state-machine-runner-protocol.md`
- Current target: P0 only
- Depends on completed slices: P0-00, P0-01, P0-02, P0-03
- Primary foundation SDD: `docs/sdd/05-runner-protocol-and-run-state-machine.md`

---

## 1. Goal

P0-04 makes Run execution safe before Scenario, Test Plan, and Report pages are expanded.

After this slice, SurgePilot can:

1. Persist a Run in the P0 state machine.
2. Atomically bind one Run to one selected Idle Load Node through a node lease.
3. Start, stop, and clean up Runner execution through bounded API / `api-worker` control paths.
4. Accept authenticated Runner callbacks with schema validation, idempotency, and terminal-state protection.
5. Accept Runner artifact uploads through API-mediated MinIO storage without giving Runner MinIO credentials.
6. Recover from accepted timeout, heartbeat timeout, stop grace timeout, stale lease, and force-kill failure without leaving a Load Node permanently Busy.
7. Provide fake-runner smoke flows for local development and CI while preserving the same callback and artifact contracts used by the real Runner.

This slice is a stability slice. It intentionally has little or no new product UI.

---

## 2. PRD Trace

This slice supports the P0 execution stability requirements behind these product capabilities:

| PRD / scope area | P0-04 responsibility |
| --- | --- |
| Run execution | Persist Run state and timestamps. |
| Stop | Provide idempotent Stop API and remote stop convergence. |
| Runner callback | Validate, authenticate, store, and apply callbacks safely. |
| Heartbeat timeout | Detect stale active Runs and force convergence. |
| Node safety | Acquire and release one active node lease per Run. |
| Manual single-node execution | Enforce one selected Load Node server-side. |
| Run Snapshot | Persist a protocol-level snapshot shell for later Scenario / Test Plan slices. |
| Artifacts | Accept Runner-uploaded artifacts through API and MinIO. |
| P0-Stability | Prevent terminal overwrite, duplicate callbacks, permanent Busy nodes, unsafe paths, and credential leaks. |

P0-04 does not complete the user-facing Run Now, Debug Run, or Run Report experience. Those are owned by P0-05, P0-06, and P0-07.

---

## 3. Document Responsibility

### 3.1 This Slice Owns

This document is the implementation contract for:

1. P0 Run state persistence fields needed by the state machine.
2. Node lease persistence and atomic acquisition / release rules.
3. Runner callback schema updates in `packages/contracts/runner/runner-callback.schema.json`.
4. Internal Runner callback and artifact upload endpoints.
5. Public Stop API contract.
6. `api-worker` run-control jobs and timeout scans.
7. Runner CLI behavior for `start`, `stop`, `kill`, and `--fake`.
8. P0-04 tests, smoke coverage, and Done When.

### 3.2 Foundation SDDs Remain Authoritative For

| Document | Authority |
| --- | --- |
| `00-product-scope-and-priority.md` | P0 scope gate and forbidden P1/P2 capabilities. |
| `04-api-contract-guidelines.md` | Public API style, OpenAPI generation, error shape, headers, CSRF, and generated Web client rules. |
| `05-runner-protocol-and-run-state-machine.md` | Run state machine semantics, callback ordering semantics, Stop, heartbeat, force kill, and node lease safety rules. |
| `06-security-permission-workspace.md` | Auth, role rules, Workspace isolation, runner token secrecy, audit safety, and credential safety. |
| `07-storage-artifacts-minio.md` | MinIO object key construction, path validation, artifact limits, terminal-late artifact policy, and download safety. |
| `09-testing-and-acceptance-strategy.md` | Repository-level verification strategy and E2E placement. |

If this Slice conflicts with a Foundation SDD, follow the Foundation SDD and update this Slice.

### 3.3 Later Slice Ownership

| Later slice | Owns |
| --- | --- |
| P0-05 Visual Scenario / Debug Run | Scenario data model, Step CRUD, Debug Run user flow, and Debug Run UI entry. |
| P0-06 Test Plan / Run Now | Test Plan model, load settings, SLA subset, Run Now UI, Run creation public endpoint shape, and short-window Run creation deduplication. |
| P0-07 Run Report / Artifacts / Validity | Report summary, verdict, KPI, artifact list/download UI, validity marking, and report detail APIs. |
| P0-08 Overview / P0 Polish | Overview cards, global empty/error states, route polish, and final P0 acceptance cleanup. |

P0-04 may create non-user-visible tables or nullable columns needed by later P0 slices, but it must not expose later P0 or P1/P2 behavior as usable product features.

---

## 4. In Scope

### 4.1 Backend API

1. Run state model and service-level transition functions.
2. Atomic Run + Run Snapshot shell + node lease acquisition service for already-validated execution input.
3. Node Busy transition when a lease is acquired.
4. Node lease release and node status convergence on terminal, cleanup success, cleanup failure, and stale lease recovery.
5. Public Stop endpoint:
   - `POST /api/v1/runs/{runId}/stop`.
6. Internal Runner endpoints:
   - `POST /api/internal/v1/runner/callbacks`;
   - `POST /api/internal/v1/runner/artifacts`.
7. Runner callback event storage and idempotency by `(runId, eventId)`.
8. Artifact upload metadata and MinIO write path needed for Runner uploads.
9. Audit events:
   - `run.stop_requested`;
   - `run.force_kill`;
   - `load_node.quarantined`;
   - `artifact.uploaded` where artifact upload succeeds.
10. Safe English error messages and stable error codes.

### 4.2 `api-worker`

1. Claim and execute remote start requests.
2. Claim and execute remote stop requests.
3. Accepted wait timeout scan.
4. Heartbeat timeout scan.
5. Stop grace timeout scan.
6. Shared post-terminal force-kill cleanup.
7. Stale lease recovery.
8. Runner callback event retention cleanup for rows older than 30 days.

The worker uses PostgreSQL advisory locks for global scans and row-level claiming for object-level run-control requests.

### 4.3 Runner

1. `runner.py start --run-id <runId>`.
2. `runner.py start --run-id <runId> --fake`.
3. `runner.py stop --run-id <runId>`.
4. `runner.py kill --run-id <runId>`.
5. Detached process group creation for real execution.
6. PID file read/write and stale process detection.
7. Callback client with bounded retry.
8. Artifact upload client using API, not MinIO.
9. Fake-runner scenarios using the same callback client and schema.

### 4.4 Contracts

1. Update `packages/contracts/runner/runner-callback.schema.json` from placeholder to P0 schema v1.
2. Add or update runner callback contract tests.
3. Ensure internal Runner endpoints are excluded from the Web generated OpenAPI client.
4. Ensure public Stop API appears in the generated Web client when implemented.

### 4.5 Tests

1. API service tests for every legal and illegal state transition.
2. API integration tests for Stop, callbacks, artifacts, auth, Workspace, and node lease behavior.
3. Worker tests for timeout scans, cleanup, quarantine, and stale lease recovery.
4. Runner unit tests for CLI, process group, callback client, artifact path safety, stop, and kill.
5. Contract tests for callback schema and OpenAPI/client boundaries.
6. Fake-runner smoke tests for success, failure, Stop, heartbeat timeout, artifact upload, and late callback handling.

---

## 5. Out of Scope

P0-04 must not implement:

1. Scenario Designer, Step CRUD, or Scenario pages.
2. Test Plan Editor, load settings UI, SLA UI, or Run Now page.
3. Public user-facing Run creation endpoint shape for Run Now or Debug Run.
4. Run List page or Run Report page.
5. Artifact download UI, artifact preview UI, report summary parsing UI, or validity marking.
6. API Catalog.
7. OpenAPI / Swagger Spec upload.
8. cURL import.
9. OpenAPI Step generation.
10. Monitoring pages, Grafana, InfluxDB, or live metric charts.
11. Schedule Run or Scheduled Job.
12. Resource Auto allocation.
13. Multi-node execution, Node Count, or Selected Nodes multi-select.
14. Resource queueing or retry scheduler.
15. Workspace switching UI or Workspace management UI.
16. User Management UI or System Settings UI.
17. OAuth, OIDC, SAML, LDAP, or SSO.
18. Env Group Secret type or Secret Snapshot encryption.
19. Non-MinIO storage.
20. Direct browser-to-MinIO upload or presigned URL exposure.
21. Direct Runner-to-MinIO upload.
22. Editable Taurus YAML or generated YAML preview.
23. Automatic installation of missing Taurus/JMeter/Java dependencies on Load Nodes.
24. Kubernetes, Redis, Celery, RabbitMQ, Kafka, or any external queue service.
25. Per-node runner token rotation UI.

---

## 6. Key Decisions

| Area | Decision |
| --- | --- |
| Run states | `initializing`, `running`, `stopping`, `finished`, `failed`, `aborted`. |
| Terminal states | `finished`, `failed`, `aborted`. |
| Startup owner | API persists Run and lease, then `api-worker` claims remote start. The HTTP request must not wait for SSH startup. |
| User-visible Run creation | Not exposed in P0-04. Later slices call the service or define public creation endpoints. |
| Node binding | P0 Run binds to exactly one selected Load Node. |
| Lease protection | Partial unique active lease on `node_id` prevents double allocation. |
| Busy status | Node becomes `busy` only after lease acquisition succeeds. |
| Stop response | First accepted Stop returns `202`; duplicate Stop while `stopping` returns `200`; terminal Stop returns `409 RUN_TERMINAL_STATE`. |
| Callback schema version | P0 accepts `schemaVersion: "1"` only. |
| Callback idempotency | `(runId, eventId)` plus payload hash. Same hash returns success with `duplicate=true`; different hash returns `409 RUNNER_CALLBACK_CONFLICT`. |
| Callback timestamp authority | API `receivedAt` is authoritative for state changes. Runner `eventTime` is diagnostic only. |
| Callback `seq` | Required and diagnostic only. It never decides state transitions. |
| Runner token | P0 uses one deployment-level token from environment. For P0, token binding means valid internal Runner identity plus `runId`, `nodeId`, and active Run / lease matching. |
| Internal endpoints | Runner endpoints use `x-runner-token`, no browser session, no CSRF, and are excluded from the Web generated client. |
| Artifact upload | Runner uploads to API; API validates and streams to MinIO. Runner never receives MinIO credentials. |
| Force kill | One shared cleanup function handles an uncertain remote `start` result, accepted timeout, heartbeat timeout, stop grace timeout, and terminal callback with `processGroupExited=false`. An uncertain `start` keeps the same allocation lease and node Busy until this cleanup succeeds or fails closed. |
| Quarantine | Cleanup failure, timeout, stale process detection, or inconsistent managed pidfile marks node `quarantined`. |
| Quarantine recovery | Admin or authorized private-node operator reruns Load Node initialization; no automatic quarantine recovery in P0. |
| Worker coordination | PostgreSQL advisory locks for global scans; `FOR UPDATE SKIP LOCKED` for run-control request rows. |
| Open-source implementation choices | Use existing FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, MinIO SDK, Click, `jsonschema`, Python stdlib process primitives, and a small HTTP client such as `httpx` for Runner callbacks. Use the P0-03 SSH/SFTP adapter abstraction; do not shell out with unsafe string concatenation. |
| Fake runner | Required for CI and local smoke, shares callback and artifact clients, and cannot replace real or near-real Runner acceptance. |

---

## 7. State Machine Contract

P0-04 implements the state machine from `05-runner-protocol-and-run-state-machine.md`.

### 7.1 States

| State | Meaning | Terminal |
| --- | --- | --- |
| `initializing` | Run exists, resources are leased, remote start or accepted callback is pending, but load execution has not started. | no |
| `running` | Runner has confirmed Taurus/JMeter execution has started. | no |
| `stopping` | A user requested Stop and SurgePilot is converging cancellation. | no |
| `finished` | Runner completed successfully from the Run-state perspective. SLA verdict may still fail later. | yes |
| `failed` | System, Runner, node, bundle, heartbeat, startup, artifact-critical path, or test execution failed. | yes |
| `aborted` | User Stop was requested and SurgePilot converged cancellation. | yes |

Rules:

1. API and DB values use lower snake case.
2. Terminal states cannot be overwritten by later callbacks, worker scans, or Stop requests.
3. `stopping` is entered only by the public Stop API or equivalent authenticated API action.
4. `finished` is accepted only from `running`.
5. `heartbeat` and `artifact` callbacks never change Run state.
6. `accepted` never changes Run state to `running`.

### 7.2 Legal Transitions

| Current state | Trigger | New state | Notes |
| --- | --- | --- | --- |
| none | Run service creates execution | `initializing` | Run, snapshot shell, node lease, and Busy node update are atomic. |
| `initializing` | `accepted` callback | `initializing` | Record `acceptedAt`, Runner-reported supervisor `runnerPid`, and latest callback metadata. Workload PGID remains Runner-local in `workload.pid`. |
| `initializing` | `running` callback | `running` | Record `startedAt` using API time. |
| `initializing` | Stop API | `stopping` | Record requester and enqueue one stop request. |
| `initializing` | `failed` callback | `failed` | Release lease only if cleanup is proven safe. |
| `initializing` | `aborted` callback | `aborted` | Release lease only if cleanup is proven safe. |
| `initializing` | accepted wait timeout | `failed` | reason `runner_accept_timeout`; force cleanup. |
| `running` | `heartbeat` callback | `running` | Update `lastHeartbeatAt` only. |
| `running` | `artifact` callback | `running` | Artifact metadata/timeline only. |
| `running` | Stop API | `stopping` | Record requester and enqueue one stop request. |
| `running` | `finished` callback | `finished` | Release lease only if cleanup is proven safe. |
| `running` | `failed` callback | `failed` | Release lease only if cleanup is proven safe. |
| `running` | `aborted` callback | `aborted` | Release lease only if cleanup is proven safe. |
| `running` | heartbeat timeout | `failed` | reason `heartbeat_timeout`; force cleanup. |
| `stopping` | `heartbeat` callback | `stopping` | Update `lastHeartbeatAt` only. |
| `stopping` | `artifact` callback | `stopping` | Artifact metadata/timeline only. |
| `stopping` | `aborted` callback | `aborted` | Normal Stop convergence. |
| `stopping` | `failed` callback | `failed` | Allowed only before worker force-converged to `aborted`. |
| `stopping` | stop grace timeout | `aborted` | reason `stop_grace_timeout`, `forcedConvergence=true`; force cleanup. |
| terminal | any callback | unchanged | Store/log callback when valid; no state mutation. |

### 7.3 Conditional Update Rule

All state changes use conditional DB updates.

Concept:

```sql
UPDATE runs
SET state = :new_state,
    updated_at = now()
WHERE id = :run_id
  AND state = ANY(:legal_predecessors);
```

Rules:

1. `affected_rows = 1` means the transition applied.
2. `affected_rows = 0` means duplicate, late, illegal, or already terminal.
3. Duplicate, late, or illegal Runner callbacks return a successful callback response unless schema/auth/idempotency conflict rules require an error.
4. Public user actions return business errors for invalid user action, for example terminal Stop.
5. Terminal transition and lease release occur in the same transaction only when process cleanup is already proven safe.
6. Timeout and unsafe-terminal cleanup paths keep the node unavailable until force-kill result is known.

### 7.4 Reason Values

P0-04 persists stable reason values for failed/aborted diagnostics:

```text
runner_start_failed
runner_start_timeout
runner_accept_timeout
heartbeat_timeout
stop_grace_timeout
stale_process_detected
bundle_invalid
bundle_upload_failed
runner_callback_invalid
runner_exit_nonzero
artifact_upload_failed
node_unreachable
unknown_runner_error
```

Rules:

1. Reason values are lower snake case.
2. Reason values are not public API error codes.
3. User-facing messages are safe English fallback text.
4. No response, log, callback detail, or audit detail may expose secrets, full stderr, stack traces, SSH credentials, runner token, MinIO credentials, or server absolute private-key paths.

---

## 8. Data Model

Exact ORM names may follow repository conventions, but the persisted concepts and constraints below are required.

### 8.1 `runs`

Purpose: authoritative business state for one execution.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `workspace_id` | `char(26)` | yes | Workspace boundary. |
| `run_type` | `text` | yes | `debug` or `standard`. Later slices define user-facing defaults. |
| `state` | `text` | yes | P0 state enum. |
| `source_type` | `text` | yes | `protocol_smoke`, `debug_scenario`, or `test_plan`. P0-04 uses `protocol_smoke` only in tests/dev helpers. |
| `source_id` | `char(26)` | no | Scenario or Test Plan ID when later slices create real Runs. |
| `selected_node_id` | `char(26)` | yes | The single Load Node selected for this Run. |
| `triggered_by_user_id` | `char(26)` | yes | Authenticated actor. |
| `accepted_at` | `timestamptz` | no | API received time for accepted callback. |
| `started_at` | `timestamptz` | no | API received time for running callback. |
| `ended_at` | `timestamptz` | no | API time when terminal state applied. |
| `last_heartbeat_at` | `timestamptz` | no | Latest accepted heartbeat API received time. |
| `last_callback_event_id` | `char(26)` | no | Latest stored callback event for diagnostics. |
| `stop_requested_at` | `timestamptz` | no | First accepted Stop time. |
| `stop_requested_by_user_id` | `char(26)` | no | Actor that requested Stop. |
| `failure_reason` | `text` | no | Stable lower snake case reason. |
| `failure_message` | `text` | no | Safe bounded English message. |
| `forced_convergence` | `boolean` | yes | Default `false`. |
| `runner_pid` | `integer` | no | Supervisor process identifier reported by accepted callback `runnerPid`; it is not the workload PGID. Stop/Kill use Runner-local `supervisor.pid` and `workload.pid` files on the Load Node. |
| `remote_start_requested_at` | `timestamptz` | no | Set when remote start request is queued. |
| `remote_start_attempted_at` | `timestamptz` | no | Set when worker starts SSH/SFTP startup. |
| `remote_start_completed_at` | `timestamptz` | no | Set after remote start command returns successfully. |
| `last_force_kill_at` | `timestamptz` | no | Copied to node or used for diagnostics when cleanup succeeds. |
| `validity` | `text` | no | Nullable compatibility field for P0-07; P0-04 does not expose or mutate it. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |

Constraints and indexes:

1. `state in ('initializing', 'running', 'stopping', 'finished', 'failed', 'aborted')`.
2. `run_type in ('debug', 'standard')`.
3. `source_type in ('protocol_smoke', 'debug_scenario', 'test_plan')`.
4. `validity is null or validity in ('valid', 'invalid')`.
5. FK `workspace_id -> workspaces.id`.
6. FK `selected_node_id -> load_nodes.id`.
7. FK `triggered_by_user_id -> users.id`.
8. Index `(workspace_id, created_at desc, id desc)`.
9. Index `(workspace_id, state, created_at desc, id desc)`.
10. Index `(state, last_heartbeat_at)` for worker scans.
11. Index `(state, remote_start_requested_at, accepted_at)` for accepted timeout scans.
12. Index `(state, stop_requested_at)` for stop grace scans.

Rules:

1. `runs.workspace_id` is always set from authenticated context, not from client payload alone.
2. Public API response fields use camelCase.
3. DB fields use snake case.
4. P0-04 does not expose `validity`; P0-07 owns validity semantics and UI.
5. P0-04 does not add schedule, queue, node count, selected nodes array, or auto-allocation fields.
6. `protocol_smoke` is allowed only for tests, CI, and local developer helpers guarded by `SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS=true`.
7. Production product APIs must not create `protocol_smoke` Runs, and later report queries must exclude them unless the same test/dev guard is enabled.

### 8.2 `run_snapshots`

Purpose: immutable execution snapshot shell tied to one Run.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `workspace_id` | `char(26)` | yes | Same Workspace as Run. |
| `run_id` | `char(26)` | yes | Unique FK to Run. |
| `snapshot_version` | `integer` | yes | P0-04 uses `1`. |
| `snapshot_hash` | `text` | yes | SHA-256 over canonical JSON. |
| `snapshot_json` | `jsonb` | yes | Immutable snapshot payload. |
| `created_at` | `timestamptz` | yes | UTC. |

Constraints:

1. Unique `(run_id)`.
2. FK `run_id -> runs.id`.
3. FK `workspace_id -> workspaces.id`.
4. `snapshot_version = 1` in P0.

Rules:

1. P0-04 snapshot payload must contain at least:
   - `runType`;
   - `sourceType`;
   - `sourceId` when present;
   - selected Load Node identity snapshot;
   - actor ID;
   - creation time;
   - protocol schema version.
2. Later slices extend `snapshot_json` with Scenario, Test Plan, Env Group, Dependency File, Load Settings, SLA, and Resource Request details.
3. Snapshot payload is immutable after Run creation.
4. Snapshot must not contain plaintext SSH credentials, runner token, MinIO credentials, session values, CSRF token, or Env Group Secret values.

### 8.3 `node_leases`

Purpose: prevent concurrent use of one Load Node.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `workspace_id` | `char(26)` | yes | Run Workspace. |
| `node_id` | `char(26)` | yes | Leased Load Node. |
| `run_id` | `char(26)` | yes | Owning Run. |
| `acquired_at` | `timestamptz` | yes | UTC. |
| `released_at` | `timestamptz` | no | Null means active. |
| `release_reason` | `text` | no | `finished`, `failed`, `aborted`, `force_kill_success`, `force_kill_failed`, `stale_recovery`, or safe equivalent. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |

Constraints and indexes:

1. FK `workspace_id -> workspaces.id`.
2. FK `node_id -> load_nodes.id`.
3. FK `run_id -> runs.id`.
4. Unique `(run_id)`.
5. Partial unique index on `(node_id)` where `released_at is null`.
6. Index `(released_at, acquired_at)` for stale lease recovery.

Rules:

1. Acquiring a lease and setting `load_nodes.status='busy'` happen in the same DB transaction as Run creation.
2. Selection requires node state `idle`, no active lease, not archived, visible to current Workspace, and not within force-kill cooldown.
3. Releasing a lease alone does not make a node selectable if node state is `disabled`, `offline`, or `quarantined`.
4. Cleanup failure releases the lease but sets the node to `quarantined`.
5. Worker crash after terminal transition but before release is recovered by stale lease recovery.

### 8.4 `runner_callback_events`

Purpose: durable callback receipt, diagnostics, and idempotency.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `workspace_id` | `char(26)` | yes | Derived from Run. |
| `run_id` | `char(26)` | yes | Callback Run. |
| `node_id` | `char(26)` | yes | Callback node. |
| `event_id` | `char(26)` | yes | Runner idempotency key. |
| `event_type` | `text` | yes | P0 callback event type. |
| `seq` | `integer` | yes | Diagnostic sequence. |
| `event_time` | `timestamptz` | yes | Runner clock time; diagnostic only. |
| `received_at` | `timestamptz` | yes | API clock time; authoritative for stored timestamps. |
| `request_id` | `text` | yes | API request ID. |
| `payload_sha256` | `text` | yes | Hash of canonical payload without headers. |
| `payload_json` | `jsonb` | yes | Bounded callback body, stored only after the API accepts a callback request within the 8KB limit. |
| `duplicate_count` | `integer` | yes | Default `0`. |
| `last_duplicate_at` | `timestamptz` | no | Updated on duplicate retry. |
| `ignored_reason` | `text` | no | Set when valid event did not mutate state. |
| `created_at` | `timestamptz` | yes | UTC. |

Constraints and indexes:

1. Unique `(run_id, event_id)`.
2. `event_type in ('accepted', 'running', 'heartbeat', 'artifact', 'finished', 'failed', 'aborted')`.
3. Index `(run_id, received_at desc, id desc)`.
4. Index `(created_at)` for 30-day retention cleanup.

Rules:

1. Store callback receipt before applying state transition.
2. Duplicate same hash returns success and does not re-apply transition.
3. Duplicate different hash returns `409 RUNNER_CALLBACK_CONFLICT`.
4. Callback request bodies larger than 8KB return `422 RUNNER_CALLBACK_INVALID` and are not stored or applied.
5. `payload_json` must not contain runner token because the token is a header and is never stored.
6. Valid late callbacks are stored/logged but cannot mutate terminal state.
7. Retention cleanup deletes rows older than 30 days through `api-worker`.

### 8.5 `run_control_requests`

Purpose: bounded run-control work queue for remote start, stop, and cleanup. This is not a resource scheduler.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `workspace_id` | `char(26)` | yes | Run Workspace. |
| `run_id` | `char(26)` | yes | Target Run. |
| `node_id` | `char(26)` | yes | Target Load Node. |
| `action` | `text` | yes | `start`, `stop`, or `force_kill`. |
| `reason` | `text` | no | Required for `force_kill`; safe reason value. |
| `status` | `text` | yes | `pending`, `running`, `succeeded`, `failed`, `cancelled`. |
| `run_after` | `timestamptz` | yes | Claimable after this time. |
| `claimed_at` | `timestamptz` | no | Worker claim time. |
| `claimed_by` | `text` | no | Worker identity. |
| `attempt_count` | `integer` | yes | Default `0`. |
| `last_error_code` | `text` | no | Safe code. |
| `last_error_message` | `text` | no | Safe bounded English message. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |
| `finished_at` | `timestamptz` | no | UTC. |

Constraints and indexes:

1. `action in ('start', 'stop', 'force_kill')`.
2. `status in ('pending', 'running', 'succeeded', 'failed', 'cancelled')`.
3. Partial unique active request:
   - one active `start` per Run;
   - one active `stop` per Run;
   - one active `force_kill` per Run.
4. Index `(status, run_after, created_at)` for worker claiming.

Rules:

1. Worker claims rows with `FOR UPDATE SKIP LOCKED`.
2. `start` is enqueued after Run transaction commits.
3. Stop API enqueues one `stop` request only after transitioning Run to `stopping`.
4. Timeouts and unsafe terminal callbacks enqueue or directly claim one `force_kill` path through the shared cleanup function.
5. Failed run-control requests do not create resource queue behavior; they update safe state and rely on timeout/stale recovery rules.

### 8.6 `run_artifacts`

Purpose: metadata for Runner-uploaded artifacts. P0-04 creates upload metadata; P0-07 owns user-facing listing, download, preview, and report summaries.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID artifact ID. |
| `workspace_id` | `char(26)` | yes | Derived from Run. |
| `run_id` | `char(26)` | yes | Owning Run. |
| `node_id` | `char(26)` | yes | Source node. |
| `event_id` | `char(26)` | yes | Upload idempotency key. |
| `artifact_type` | `text` | yes | P0 whitelist. |
| `relative_path` | `text` | yes | Safe relative path. |
| `display_filename` | `text` | yes | Derived from final path segment. |
| `size_bytes` | `bigint` | yes | Actual validated size. |
| `sha256` | `text` | yes | Actual validated SHA-256. |
| `content_type` | `text` | no | Safe server-derived or allowed value. |
| `storage_key` | `text` | yes | Server-only MinIO object key. Never returned to Web. |
| `status` | `text` | yes | `available` or `failed`. |
| `terminal_late` | `boolean` | yes | Default `false`. |
| `created_at` | `timestamptz` | yes | UTC. |

Constraints and indexes:

1. Unique `(run_id, event_id)`.
2. Unique `(run_id, relative_path)` for available artifacts.
3. `artifact_type in ('taurus_log', 'jmeter_log', 'final_stats_csv', 'run_log', 'artifacts_zip')`.
4. `status in ('available', 'failed')`.
5. Index `(workspace_id, run_id, created_at desc, id desc)`.

Rules:

1. `workspace_id` is copied from Run, never trusted from Runner input.
2. `storage_key` is never returned to Web, logged in normal logs, or stored in audit details.
3. Failed upload validation must not create downloadable metadata.
4. Duplicate `(runId, eventId)` returns existing `artifactId` if the first upload succeeded.
5. Duplicate `(runId, relativePath)` with different type, size, or hash returns `409 ARTIFACT_PATH_CONFLICT`.
6. Terminal-late artifact policy follows `07-storage-artifacts-minio.md` exactly.

### 8.7 `load_nodes` Additions

P0-03 already reserves some fields. P0-04 owns using or adding:

| Column | Rule |
| --- | --- |
| `current_run_id` | Set when node becomes Busy; cleared when lease is safely released. Add FK to `runs.id` after Runs table exists. |
| `last_heartbeat_at` | Optional node-facing mirror of current Run heartbeat for list display; Run heartbeat remains authoritative. |
| `last_force_kill_at` | Set after successful force kill; selection enforces cooldown. |
| `last_status_reason` | Safe reason such as `heartbeat_timeout`, `force_kill_failed`, or `stale_process_detected`. |

Rules:

1. P0-04 may set `status='busy'` only when active lease exists.
2. P0-04 may set `status='idle'` only after cleanup is safe and node is not disabled/offline/quarantined.
3. P0-04 sets `status='quarantined'` after cleanup failure, stale process detection, or inconsistent managed process state.
4. P0-03 update/archive/disable rules for Busy and Quarantined nodes remain in force.

### 8.8 Migration Order

Alembic migration order for this slice is fixed:

1. Create `runs` and other new P0-04 tables first.
2. Add `load_nodes.current_run_id -> runs.id` foreign key only after `runs` exists.
3. Keep the migration reversible without dropping P0-03 Load Node data.
4. Downgrade must drop the `load_nodes.current_run_id` foreign key before dropping `runs` or other referenced P0-04 tables.

---

## 9. API Contract

### 9.1 Public Stop API

```http
POST /api/v1/runs/{runId}/stop
x-workspace-id: <workspace id>
x-csrf-token: <csrf token>
```

Operation ID:

```text
stopRun
```

Auth and headers:

| Requirement | Rule |
| --- | --- |
| Session | Required. |
| CSRF | Required. |
| Workspace | Required or resolved to default Workspace per P0 rule. |
| Role | User and Admin may stop Runs in the current Workspace. |

Response `202 Accepted` for first accepted Stop:

```json
{
  "id": "01J00000000000000000000002",
  "state": "stopping",
  "stopRequestedAt": "2030-06-01T10:00:00.000Z",
  "duplicate": false
}
```

Response `200 OK` for duplicate Stop while already `stopping`:

```json
{
  "id": "01J00000000000000000000002",
  "state": "stopping",
  "stopRequestedAt": "2030-06-01T10:00:00.000Z",
  "duplicate": true
}
```

Errors:

| Condition | Status | Code |
| --- | --- | --- |
| Not logged in | 401 | `UNAUTHENTICATED` |
| Missing/invalid CSRF | 403 | `FORBIDDEN` |
| Workspace cannot be resolved | 400 | `WORKSPACE_REQUIRED` |
| Workspace access denied | 403 | `WORKSPACE_ACCESS_DENIED` |
| Run not found in Workspace | 404 | `RESOURCE_NOT_FOUND` |
| Run terminal | 409 | `RUN_TERMINAL_STATE` |
| Run in a non-stoppable non-terminal state | 409 | `RUN_STOP_NOT_ALLOWED` |

Rules:

1. Stop is allowed only from `initializing` and `running`.
2. Stop transitions Run to `stopping` and records first requester/time.
3. Duplicate Stop while `stopping` is successful and must not create parallel remote stop attempts.
4. Stop does not synchronously wait for remote process exit.
5. Stop writes `run.stop_requested` audit event only for the first accepted Stop.
6. Stop on terminal state never mutates the Run.

### 9.2 Internal Runner Callback API

```http
POST /api/internal/v1/runner/callbacks
x-runner-token: <runner token>
Content-Type: application/json
```

This endpoint is internal and must be excluded from the Web generated OpenAPI client.

Success response for applied callback:

```json
{
  "accepted": true,
  "duplicate": false,
  "stateChanged": true,
  "currentState": "running"
}
```

Success response for duplicate callback:

```json
{
  "accepted": true,
  "duplicate": true,
  "stateChanged": false,
  "currentState": "running"
}
```

Success response for valid late or ignored callback:

```json
{
  "accepted": true,
  "duplicate": false,
  "stateChanged": false,
  "currentState": "finished",
  "ignoredReason": "terminal_state_protected"
}
```

Errors:

| Condition | Status | Code |
| --- | --- | --- |
| Missing or invalid runner token | 401 | `RUNNER_UNAUTHORIZED` |
| Valid token but `runId` / `nodeId` is not allowed | 403 | `RUNNER_FORBIDDEN` |
| Malformed JSON or schema-invalid callback | 422 | `RUNNER_CALLBACK_INVALID` |
| Same `(runId,eventId)` with different payload hash | 409 | `RUNNER_CALLBACK_CONFLICT` |
| Unknown Run that cannot be associated safely | 404 | `RESOURCE_NOT_FOUND` |

Rules:

1. Validate runner token before applying payload.
2. P0 runner token is a deployment-level token. For P0, token binding means valid internal Runner identity plus `runId`, `nodeId`, current Run, and current or recently terminal lease relationship matching.
3. The endpoint does not use browser cookies or CSRF.
4. Request body limit is 8KB.
5. Duplicate valid callbacks return success.
6. `RUNNER_CALLBACK_CONFLICT` is activated by this slice and must be registered during implementation.
7. Unknown `schemaVersion` returns `422 RUNNER_CALLBACK_INVALID`.
8. Internal endpoint examples must never contain real runner token values.

### 9.3 Callback Schema v1

Source of truth:

```text
packages/contracts/runner/runner-callback.schema.json
```

Base payload:

```json
{
  "schemaVersion": "1",
  "eventId": "01J00000000000000000000001",
  "runId": "01J00000000000000000000002",
  "nodeId": "01J00000000000000000000003",
  "runtimeVersion": "runtime-test-v1",
  "eventType": "heartbeat",
  "seq": 4,
  "eventTime": "2030-06-01T10:00:00.000Z",
  "message": "Heartbeat received.",
  "details": {}
}
```

Base fields:

| Field | Required | Rule |
| --- | --- | --- |
| `schemaVersion` | yes | String const `"1"`. |
| `eventId` | yes | ULID generated by Runner per callback event. |
| `runId` | yes | ULID of Run. |
| `nodeId` | yes | ULID of Load Node. |
| `runtimeVersion` | yes | Actual activated Runtime metadata version read by Runner after Runtime validation. API verifies it against the allocation and Load Node expectation. |
| `eventType` | yes | `accepted`, `running`, `heartbeat`, `artifact`, `finished`, `failed`, or `aborted`. |
| `seq` | yes | Non-negative integer, monotonic from Runner perspective, diagnostic only. |
| `eventTime` | yes | ISO 8601 UTC string with `Z`, Runner clock time. |
| `message` | no | Safe English fallback, bounded length. |
| `runnerPid` | conditional | Required for `accepted`; positive integer identifying the Runner supervisor process, stored as `runner_pid`. It is not the workload PGID. |
| `details` | no | Event-specific object, max bounded size, no secrets. |

Event-specific requirements:

| Event type | Additional required fields | Details rules |
| --- | --- | --- |
| `accepted` | `runnerPid` | `runnerPid` identifies the Runner supervisor process. Workload PGID is not reported to API and remains in Runner-local `workload.pid`. |
| `running` | none | May include safe execution engine name/version. |
| `heartbeat` | none | May include small progress counters only. |
| `artifact` | `details.artifactId`, `details.artifactType`, `details.relativePath`, `details.sizeBytes`, `details.sha256` | Must not include MinIO object key. |
| `finished` | `details.processGroupExited` | May include `exitCode` and summary artifact pointer. |
| `failed` | `details.processGroupExited`, `details.reason` | `reason` uses stable lower snake case; safe message only. |
| `aborted` | `details.processGroupExited`, `details.reason` | Used for user Stop or forced cancellation convergence. |

Rules:

1. The schema must reject unknown `eventType` values.
2. The schema must reject unknown top-level fields unless explicitly allowed by schema version.
3. `details` must not contain credentials, tokens, full environment variables, server absolute paths, large logs, object keys, or file bytes.
4. `message` and safe detail messages must be English fallback text.
5. `eventTime` and `seq` are stored for diagnostics and never decide state transitions.
6. P0 implementation must replace the current placeholder field `occurredAt` with `eventTime`.
7. Contract tests must include one valid example per event type and invalid examples for missing required conditional fields.
8. Remote Run control verifies `current/metadata.json` before uploading Runner, bundle, environment, or Monitoring properties. Missing or mismatched Runtime identity fails closed and requires reinitialization.
9. Runner Runtime validation and every terminal path, including a race-time Runtime mismatch, remain inside the Runner terminal cleanup boundary.

### 9.4 Internal Runner Artifact Upload API

```http
POST /api/internal/v1/runner/artifacts
x-runner-token: <runner token>
Content-Type: multipart/form-data
```

This endpoint is internal and must be excluded from the Web generated OpenAPI client.

Required multipart fields:

| Field | Rule |
| --- | --- |
| `schemaVersion` | String const `"1"`. |
| `eventId` | ULID idempotency key for this upload. |
| `runId` | ULID. |
| `nodeId` | ULID. |
| `artifactType` | P0 whitelist only. |
| `relativePath` | Safe relative path under the current Run directory. |
| `sha256` | Declared hex SHA-256. |
| `sizeBytes` | Declared size in bytes. |
| `file` | One uploaded file. |

Success response:

```json
{
  "artifactId": "01J00000000000000000000005",
  "duplicate": false
}
```

Errors:

| Condition | Status | Code |
| --- | --- | --- |
| Missing or invalid runner token | 401 | `RUNNER_UNAUTHORIZED` |
| Valid token but Run / Node mismatch | 403 | `RUNNER_FORBIDDEN` |
| Unknown artifact type | 400 | `INVALID_ARTIFACT_TYPE` |
| Unsafe `relativePath` | 400 | `INVALID_ARTIFACT_PATH` |
| Non-terminal upload larger than 200MB | 413 | `PAYLOAD_TOO_LARGE` |
| Actual size does not match `sizeBytes` | 400 | `ARTIFACT_SIZE_MISMATCH` |
| Actual SHA-256 does not match `sha256` | 400 | `ARTIFACT_HASH_MISMATCH` |
| Duplicate path with different type, size, or hash | 409 | `ARTIFACT_PATH_CONFLICT` |
| Duplicate event still in progress | 409 | `ARTIFACT_NOT_READY` |
| Terminal-late policy violation | 409 | `RUN_TERMINAL_STATE` |
| MinIO unavailable | 503 | `STORAGE_UNAVAILABLE` |

Rules:

1. Runner never receives MinIO credentials, bucket names, object keys, or presigned URLs.
2. API derives Workspace from Run.
3. API streams upload to MinIO while computing actual size and SHA-256.
4. API response returns `artifactId` only; it does not return object key.
5. API must not read the entire artifact into memory.
6. Failed validation must not create downloadable artifact metadata.
7. Artifact upload failure must not leave Run permanently `running` or `stopping`; state convergence remains governed by callbacks and worker timeouts.
8. Terminal-late acceptance and rejection must follow `07-storage-artifacts-minio.md`.
9. After a successful upload, Runner should send an `artifact` callback, but uploaded metadata remains valid even if the artifact callback is lost.

### 9.5 Public Run Creation Boundary

P0-04 creates a backend execution service, not a user-facing creation endpoint.

Rules:

1. The service accepts already-validated execution input from later P0 slices.
2. The service atomically creates Run, Run Snapshot shell, node lease, and Busy node state.
3. P0-04 tests may use service-level fixtures or a non-product test helper to create protocol smoke Runs.
4. No clickable Run Now, Debug Run, or public creation UI is introduced in P0-04.
5. P0-06 owns public Run Now endpoint shape and short-window Run creation deduplication.

### 9.6 Error Code Additions Activated by P0-04

P0-04 activates these codes if not already present in `04` or `07`:

| Code | Status | Meaning |
| --- | --- | --- |
| `RUNNER_CALLBACK_CONFLICT` | 409 | Same `(runId,eventId)` was received with a different payload hash. |
| `INVALID_ARTIFACT_PATH` | 400 | Artifact `relativePath` is not P0 safe. |
| `INVALID_ARTIFACT_TYPE` | 400 | Artifact type is not in the P0 whitelist. |
| `ARTIFACT_SIZE_MISMATCH` | 400 | Uploaded artifact actual size differs from declared `sizeBytes`. |
| `ARTIFACT_HASH_MISMATCH` | 400 | Uploaded artifact actual SHA-256 differs from declared `sha256`. |
| `ARTIFACT_PATH_CONFLICT` | 409 | Same Run already has the same `relativePath` with different content or type. |
| `ARTIFACT_NOT_READY` | 409 | Known artifact upload or summary metadata is not ready to return. |

Rules:

1. Implementation must update the central registry before returning a new error code.
2. Error messages are safe English fallback text.
3. Error details must not include runner token, SSH credentials, MinIO object key, server path, or raw exception text.

---

## 10. Runner, Worker, and Remote Execution Contract

### 10.1 Run Creation and Remote Startup

Flow:

```text
Later Slice service/API validates execution input
  -> create Run Snapshot shell
  -> create Run(state=initializing)
  -> acquire node lease
  -> set Load Node busy/currentRunId
  -> enqueue run_control_requests(action=start)
  -> commit transaction
  -> api-worker claims start request
  -> api-worker uploads runner/bundle/dependency files by SSH/SFTP
  -> api-worker executes runner.py start --run-id <runId>
  -> Runner sends accepted callback
```

Rules:

1. DB transaction must not execute SSH, SFTP, remote shell commands, or large MinIO operations.
2. If DB transaction fails, remote Runner must not start.
3. If remote startup fails after commit, Run converges to `failed` with `runner_start_failed` and cleanup decides node `idle` or `quarantined`.
4. Start request execution must use the P0-03 SSH/SFTP adapter abstraction and decrypted credentials only in transient memory.
5. Remote command arguments must be quoted or passed through library-supported execution APIs; no unsafe string concatenation.
6. All remote paths must be under validated `runnerHome`.
7. Once the remote Runner `start` invocation begins, a timeout or transport failure has an uncertain process result and must quarantine the node through the existing recovery path. Before that boundary, failed or partially completed secret uploads require compensating deletion; an uncertain deletion result also quarantines the node.
8. The Runtime-expectation migration must refuse to run while any Run is `initializing`, `running`, or `stopping`; it must not infer a legacy execution identity from mutable Load Node state.

### 10.2 Accepted Wait Timeout

Constants:

| Setting | P0 default |
| --- | --- |
| Accepted wait timeout | 120 seconds after remote start requested. |
| Worker scan interval | 10 seconds. |

Rules:

1. If no `accepted` callback arrives within the accepted wait window, worker conditionally marks Run `failed` with reason `runner_accept_timeout`.
2. Node remains unavailable while cleanup runs.
3. Cleanup uses the shared force-kill function.
4. If cleanup succeeds, release lease and set node `idle` subject to selection cooldown.
5. If cleanup fails or process state is inconsistent, release lease and set node `quarantined`.

### 10.3 Runner CLI

Commands:

```bash
python runner.py start --run-id <runId>
python runner.py start --run-id <runId> --fake
python runner.py stop --run-id <runId>
python runner.py kill --run-id <runId>
```

Rules:

1. `start` creates one run directory under `RUNNER_HOME/runs/<runId>`.
2. `start` checks SurgePilot-managed pidfiles before starting new execution.
3. Real `start` creates a supervisor process; the supervisor writes `supervisor.pid` and starts the Taurus/JMeter workload in an independent process group using POSIX process primitives such as `start_new_session=True` / `os.setsid`.
4. `workload.pid` stores the workload PGID plus Linux starttime for force-kill reuse protection; `accepted.runnerPid` and `runner_pid` identify only the supervisor.
5. `stop` is graceful and idempotent, signals only the supervisor, and does not delete pidfiles or directly force-kill workload.
6. `kill` is force cleanup and idempotent; it targets only `workload.pid` and does not guarantee callback delivery.
7. `stop` and `kill` never target generic process names such as `java`, `jmeter`, `bzt`, or `python`.
8. CLI output and logs must not include runner token, SSH credentials, MinIO credentials, env secrets, or full sensitive paths.
9. P0 real Runner may use a simple Taurus/JMeter subprocess flow; it must not become a custom load-generation engine.

### 10.4 Process Termination

Rules:

1. `stop` sends `SIGTERM` to the supervisor process group and waits up to the bounded supervisor cleanup timeout for supervisor exit (default 120 seconds).
2. The supervisor handles Stop by terminating the workload PGID with `SIGTERM`, waiting, and escalating that workload PGID to `SIGKILL` when needed.
3. `stop` returns non-zero if the supervisor does not exit within its bound; API cleanup then converges through `kill` / quarantine.
4. `kill` reads `workload.pid`, validates starttime when the workload leader `/proc` entry exists, sends `SIGTERM`, waits up to 10 seconds, then sends `SIGKILL` if needed.
5. `kill` returns success only when no managed workload process remains; only then may it delete `workload.pid`.
6. Missing pidfile with no managed process is a successful idempotent cleanup.
7. Missing pidfile with suspicious SurgePilot-managed process state is failure and must lead to quarantine.
8. Live managed supervisor/workload residue detected on `start` sends a `failed` callback with reason `stale_process_detected` when possible and prevents new execution; confirmed stale/corrupt pidfile residue is self-healed as defined in the foundation SDD.

### 10.5 Callback Client

Rules:

1. Runner callback client sends JSON to `/api/internal/v1/runner/callbacks` with `x-runner-token` header.
2. Runner token comes only from environment or runner config file with safe permissions.
3. Use short HTTP timeouts.
4. Retry transient callback failures with bounded backoff: 1s, 2s, 4s, 8s, 16s, max 5 attempts.
5. P0 does not implement a persistent disk callback queue.
6. Lost callbacks are handled by API heartbeat/timeout convergence.
7. Logs for callback failure must redact token and payload secrets.

### 10.6 Artifact Upload Client

Rules:

1. Runner uploads artifacts to `/api/internal/v1/runner/artifacts` using multipart upload and `x-runner-token`.
2. Runner computes SHA-256 and size before or while uploading.
3. Runner validates artifact relative paths before upload.
4. Runner uploads only P0 artifact types:
   - `taurus_log`;
   - `jmeter_log`;
   - `final_stats_csv`;
   - `run_log`;
   - `artifacts_zip`.
5. `failed_requests_csv` is deferred to P1 because it depends on a JMeter plugin output contract.
6. Runner does not upload large logs inside callback payloads.
7. Runner does not delete useful artifacts during Stop.

### 10.7 Fake Runner

Minimum fake scenarios:

1. `accepted -> running -> heartbeat -> artifact -> finished`.
2. `accepted -> running -> failed`.
3. `accepted -> running -> Stop -> aborted`.
4. `accepted -> running -> heartbeat timeout` by stopping heartbeats.
5. Artifact upload failure warning path.
6. Late callback after terminal is ignored.

Rules:

1. Fake runner lives under `apps/runner`.
2. Fake runner uses the same callback client as real Runner.
3. Fake runner uses the same artifact upload client where artifacts are involved.
4. Fake runner uses the same JSON Schema contract.
5. Fake runner must run in CI without SSH, Taurus, JMeter, or external network beyond the local API test server.
6. Fake runner must not replace real or near-real Runner acceptance for process group, SSH/SFTP startup, Stop, Kill, and artifact ingestion.

### 10.8 `api-worker` Tasks

| Task | Trigger | Coordination | Outcome |
| --- | --- | --- | --- |
| Remote start | `run_control_requests(action=start)` | Row-level claim | Starts Runner or fails Run safely. |
| Remote stop | `run_control_requests(action=stop)` | Row-level claim | Executes `runner.py stop`; final state waits for callback or grace timeout. |
| Accepted timeout scan | Periodic | Advisory lock | Marks stale initializing Run failed and force-cleans node. |
| Heartbeat timeout scan | Periodic | Advisory lock | Marks stale active Run failed and force-cleans node. |
| Stop grace scan | Periodic | Advisory lock | Force-converges stopping Run to aborted and force-cleans node. |
| Stale lease recovery | Periodic | Advisory lock | Retries cleanup or keeps node unavailable/quarantined. |
| Callback retention cleanup | Periodic | Advisory lock | Deletes callback event rows older than 30 days. |

Rules:

1. Worker must be safe if more than one process is accidentally started.
2. Worker tasks must be idempotent after crash and retry.
3. Worker must not become a resource scheduler or queue system.
4. Worker must not release a node to Idle before cleanup result is known.
5. Worker must write safe structured logs for applied and ignored actions.

### 10.9 Shared Force-Kill Cleanup

Callers:

| Caller | Run state target | Reason | SSH hard timeout |
| --- | --- | --- | --- |
| Accepted wait timeout | `failed` | `runner_accept_timeout` | 30 seconds |
| Heartbeat timeout | `failed` | `heartbeat_timeout` | 30 seconds |
| Stop grace timeout | `aborted` | `stop_grace_timeout` | 30 seconds |
| Terminal callback with `processGroupExited=false` | Already set by callback | Preserve callback reason | 10 seconds |
| Stale lease recovery | Existing terminal or safe terminal target | Preserve or `stale_lease_recovery` | 30 seconds |

Rules:

1. Shared cleanup executes `python runner.py kill --run-id <runId>` through the SSH adapter.
2. If kill succeeds, set `last_force_kill_at`, release lease, clear `current_run_id`, and set node `idle` unless disabled/offline/quarantined by another rule.
3. If kill fails, times out, or managed process state is inconsistent, release lease and set node `quarantined`.
4. Write `run.force_kill` audit event for every force-kill attempt.
5. Write `load_node.quarantined` audit event when node enters quarantine.
6. Run terminal state is not reverted if cleanup fails.
7. Selection cooldown is enforced at Run selection time; do not add a `cooling_down` node state.

---

## 11. Frontend Contract

P0-04 does not add a new user-facing page.

Rules:

1. No new clickable navigation item is added for Run Now, Debug Run, Run List, or Run Report in P0-04.
2. Public Stop API is generated into `@surgepilot/contracts` for later UI slices.
3. Web must not call `/api/internal/v1/runner/...`.
4. Web must not invent Run, callback, or artifact shapes outside generated contracts.
5. Later slices may add Stop buttons only against `initializing` / `running` Runs and must rely on backend errors for authority.
6. If a temporary developer-only page is used locally, it must not be shipped as P0 product UI and must not create P1/P2 capability.

---

## 12. Security, Permission, and Workspace Rules

### 12.1 Browser APIs

1. Public Stop requires session auth.
2. Public Stop requires CSRF.
3. Public Stop resolves and validates Workspace.
4. Run detail lookup for Stop filters by both `runId` and `workspaceId`; cross-Workspace IDs return `RESOURCE_NOT_FOUND`.
5. User and Admin can stop Runs in the current Workspace.
6. Backend permission checks are authoritative; UI visibility is not a permission boundary.

### 12.2 Internal Runner APIs

1. Runner endpoints require `x-runner-token`.
2. Runner endpoints do not use browser cookies or CSRF.
3. Runner token is configured through environment/config and never returned to Web.
4. P0 single runner token is accepted only with matching Run, Node, and lease/terminal-late relationship.
5. Runner token must not appear in logs, audit details, error details, artifacts, public OpenAPI examples, test snapshots, or frontend bundles.

### 12.3 Credential Safety

1. API/worker use P0-03 credential decryption service for SSH only in transient memory.
2. SSH credential plaintext, private keys, passphrases, encrypted blobs, AES nonce/tag/key IDs, and generated private keys are never returned in Run APIs.
3. Remote startup, stop, and kill logs must be sanitized.
4. Runner never receives Load Node SSH credentials from API payloads.

### 12.4 Artifact and Path Safety

1. Artifact `relativePath` validation follows `07-storage-artifacts-minio.md`.
2. Absolute paths, `..`, `.`, empty segments, backslashes, double slashes, drive letters, colon, and Unicode paths are rejected in P0.
3. MinIO object key is server-only.
4. Artifact audit details include business IDs and safe relative path only, not object key or file content.

### 12.5 Audit Events

Required events:

| Event | Trigger | Safe details |
| --- | --- | --- |
| `run.stop_requested` | First accepted Stop | `runId`, `nodeId`, `workspaceId`, `requestedBy`, `requestId`. |
| `run.force_kill` | Any force-kill attempt | `runId`, `nodeId`, `reason`, `success`, `timedOut`, bounded `stderrPreview`. |
| `load_node.quarantined` | Node enters quarantine | `nodeId`, `runId`, `workspaceId`, `reason`, recovery hint. |
| `artifact.uploaded` | Artifact upload succeeds | `artifactId`, `runId`, `nodeId`, `workspaceId`, `artifactType`, `relativePath`, `sizeBytes`, `sha256`, `terminalLate`, `requestId`. |

Rules:

1. Audit details must not include credentials, tokens, object keys, raw file bytes, raw logs, or stack traces.
2. Audit UI/export remains out of scope.

---

## 13. Configuration

| Name | Default | Rule |
| --- | --- | --- |
| `RUNNER_INTERNAL_TOKEN` | none | Required for internal Runner APIs and Runner client. |
| `SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS` | `false` | Allows `source_type=protocol_smoke` only for tests, CI, and local developer helpers. Must remain false for production product APIs. |
| `SURGEPILOT_RUNNER_CALLBACK_TIMEOUT_SECONDS` | `5` | Runner HTTP callback/upload request timeout. |
| `SURGEPILOT_RUNNER_HEARTBEAT_INTERVAL_SECONDS` | `15` | Runner sends heartbeat while active. |
| `SURGEPILOT_RUN_HEARTBEAT_TIMEOUT_SECONDS` | `60` | Worker heartbeat timeout threshold. |
| `SURGEPILOT_RUN_ACCEPTED_TIMEOUT_SECONDS` | `120` | Accepted wait window after remote start request. |
| `SURGEPILOT_RUN_STOP_GRACE_SECONDS` | `60` | Stop grace before forced abort convergence. |
| `SURGEPILOT_RUN_FORCE_KILL_SSH_TIMEOUT_SECONDS` | `30` | Force-kill SSH hard timeout. |
| `SURGEPILOT_TERMINAL_CALLBACK_CLEANUP_TIMEOUT_SECONDS` | `10` | Cleanup timeout for terminal callback with `processGroupExited=false`. |
| `SURGEPILOT_NODE_COOLDOWN_SECONDS` | `300` | Selection-time cooldown after force kill success. |
| `SURGEPILOT_RUNNER_CALLBACK_RETENTION_DAYS` | `30` | Callback event retention. |
| `SURGEPILOT_RUN_ARTIFACT_MAX_BYTES` | `209715200` | 200MB non-terminal artifact limit. |
| `SURGEPILOT_RUN_TERMINAL_LATE_ARTIFACT_MAX_BYTES` | `1048576` | 1MB terminal-late diagnostic limit. |
| `SURGEPILOT_RUN_TERMINAL_LATE_ARTIFACT_SECONDS` | `300` | 5-minute terminal-late artifact window. |

Rules:

1. Missing `RUNNER_INTERNAL_TOKEN` makes Runner internal endpoint readiness fail or reject all Runner requests.
2. Do not add System Settings UI for these values in P0.
3. Config values must be read through the app's existing configuration pattern, not scattered as hard-coded constants.

---

## 14. Tests

### 14.1 API Unit / Service Tests

Cover:

1. Run creation service creates Run, snapshot, lease, Busy node atomically.
2. Node lease unique index prevents double allocation.
3. `accepted` records `acceptedAt` and Runner-reported supervisor `runnerPid` without changing Run to `running`; workload PGID remains Runner-local and is not stored in API state.
4. `running` moves `initializing -> running`.
5. `heartbeat` updates `lastHeartbeatAt` only.
6. `artifact` does not change state.
7. `finished` only applies from `running`.
8. `failed` applies from non-terminal states according to state machine rules.
9. `aborted` applies from `initializing`, `running`, and `stopping`.
10. Terminal state cannot be overwritten.
11. Illegal transitions are ignored or rejected according to callback vs public action rules.
12. Terminal callback with `processGroupExited=true` releases lease transactionally.
13. Terminal callback with `processGroupExited=false` keeps node unavailable and schedules cleanup.
14. Duplicate callback same payload hash is successful and no-op.
15. Duplicate callback different hash returns `RUNNER_CALLBACK_CONFLICT`.
16. Callback schema invalid maps to `RUNNER_CALLBACK_INVALID`.
17. Runner token missing/invalid maps to `RUNNER_UNAUTHORIZED`.
18. Run / Node mismatch maps to `RUNNER_FORBIDDEN`.

### 14.2 API Integration Tests

Cover:

1. Stop first call returns `202` and writes `run.stop_requested` audit event.
2. Stop duplicate while `stopping` returns `200` with `duplicate=true` and creates no parallel stop request.
3. Stop terminal returns `409 RUN_TERMINAL_STATE`.
4. Stop cross-Workspace Run returns `RESOURCE_NOT_FOUND`.
5. Stop requires CSRF.
6. Internal callback endpoint does not require session or CSRF.
7. Internal artifact upload success writes MinIO object and metadata.
8. Artifact upload rejects invalid token.
9. Artifact upload rejects Run / Node mismatch.
10. Artifact upload rejects invalid type/path/size/hash.
11. Duplicate artifact event returns existing `artifactId`.
12. Path conflict returns `ARTIFACT_PATH_CONFLICT`.
13. Terminal-late artifact policy matches `07`.
14. API responses and audit details exclude object key and secrets.

### 14.3 Worker Tests

Use fake SSH/SFTP adapter by default.

Cover:

1. Start request success executes remote start and leaves Run `initializing` until callbacks arrive.
2. Start request SSH failure marks Run `failed` and releases/quarantines node according to cleanup result.
3. Accepted timeout marks Run `failed` with `runner_accept_timeout`.
4. Heartbeat timeout marks Run `failed` with `heartbeat_timeout`.
5. Stop grace timeout marks Run `aborted` with `forcedConvergence=true`.
6. Force kill success releases lease and returns node to `idle` with cooldown timestamp.
7. Force kill timeout/failure releases lease and marks node `quarantined`.
8. Worker crash after terminal before release is recovered by stale lease recovery.
9. Advisory lock prevents duplicate global scans.
10. Row-level claim prevents duplicate start/stop requests.
11. Callback retention cleanup deletes only rows older than retention.
12. Safe logs/audit redact credentials and token values.

### 14.4 Runner Unit Tests

Cover:

1. CLI help lists `start`, `stop`, and `kill`.
2. Fake start uses same callback client contract.
3. Callback payloads include required base fields.
4. Callback retry backoff is bounded.
5. Artifact upload computes SHA-256 and size.
6. Artifact relative path validator rejects unsafe examples.
7. Process group creation writes pidfile.
8. Stop is idempotent when pidfile is missing and no managed process exists.
9. Kill is idempotent and targets only managed process group.
10. Stale managed process detection refuses start.
11. Runner logs do not include runner token or credential-like values.

### 14.5 Contract Tests

Cover:

1. Valid callback schema examples for all event types.
2. Missing `schemaVersion` rejected.
3. Unknown `schemaVersion` rejected.
4. Missing `eventId` rejected.
5. Missing `nodeId` rejected.
6. Missing `seq` rejected.
7. Invalid `eventType` rejected.
8. Missing `runnerPid` for `accepted` rejected.
9. Missing `details.processGroupExited` for terminal callbacks rejected.
10. Oversized callback rejected by API test.
11. Schema examples use camelCase.
12. Internal Runner endpoints are excluded from Web generated client.
13. Public Stop API is present in generated Web client.
14. Generated contracts are fresh after `make generate-contracts`.

### 14.6 Web Tests

P0-04 does not require new page/component tests.

Required checks:

1. Generated client exposes `stopRun` when implementation adds the endpoint.
2. Generated client does not expose internal Runner endpoints.
3. Web source checks fail if `apps/web` references `/api/internal/v1/runner` or equivalent internal Runner endpoint strings.
4. No P0-04 route/nav item exposes Run Now, Debug Run, Run Report, Monitoring, Schedule, or multi-node UI.
5. Bundle-level verification that production frontend artifacts do not contain internal Runner endpoint strings is deferred to P0-08 unless P0-04 changes frontend build tooling.

### 14.7 Smoke / E2E Tests

P0-04 smoke should cover:

1. Fake runner success flow reaches `finished`.
2. Fake runner failed flow reaches `failed`.
3. Stop flow reaches `aborted` and releases node safely.
4. Heartbeat timeout reaches `failed` and executes force cleanup.
5. Force-kill failure quarantines node.
6. Stale process detection quarantines node.
7. Artifact upload creates metadata without exposing object key.
8. Late callback after terminal does not change visible state.

Real or near-real SSH Runner smoke belongs to `make verify-e2e`, not default `make verify`, unless the environment explicitly provides an SSH-capable Load Node.

---

## 15. Verification Commands

Implementation must run:

```bash
make generate-contracts
make verify
```

When real SSH Runner environment is available, run:

```bash
make verify-e2e
```

P0-04-specific subsets during development may include:

```bash
uv run --all-packages pytest apps/api/tests -k "run or runner or artifact or lease or worker"
uv run --all-packages pytest apps/runner/tests
uv run --all-packages pytest tests/contract
pnpm --filter @surgepilot/contracts test
```

Rules:

1. Final completion still prefers repository-level `make verify`.
2. Generated contracts must be committed after API schema or callback schema changes.
3. If `make verify-e2e` is skipped because no SSH-capable node is configured, final response must state that explicitly.

---

## 16. Done When

P0-04 is done when:

1. Run state enum and transition service are implemented with conditional DB updates.
2. Run creation service atomically creates Run Snapshot shell, Run, active node lease, and Busy node state.
3. Active lease unique constraint prevents two Runs from leasing the same node.
4. Stop API is implemented with required auth, CSRF, Workspace, idempotency, and error semantics.
5. Runner callback schema v1 is implemented in `packages/contracts/runner/runner-callback.schema.json`.
6. Internal callback endpoint validates token, schema, Run/Node binding, idempotency, and terminal protection.
7. Internal artifact upload endpoint validates token, Run/Node binding, type, path, size, hash, idempotency, and terminal-late policy.
8. Runner never receives MinIO credentials and Web never receives object keys.
9. `api-worker` handles remote start, remote stop, accepted timeout, heartbeat timeout, stop grace timeout, force kill, stale lease recovery, and callback retention cleanup.
10. Cleanup success releases node safely; cleanup failure quarantines node.
11. Runner CLI supports `start`, `start --fake`, `stop`, and `kill` with process group safety.
12. Fake runner smoke covers success, failure, Stop, heartbeat timeout, artifact upload, and late callback behavior.
13. Required audit events are written with safe details.
14. No P1/P2 capability is introduced.
15. Public OpenAPI and generated Web client include only public business APIs; internal Runner endpoints are excluded.
16. Tests listed in §14 pass or are explicitly documented as environment-gated where appropriate.
17. `make generate-contracts` and `make verify` pass.
18. Slice implementation backfill is updated only for actual implementation differences, new tests, and remaining risks.

---

## 17. Review Checklist

Before accepting P0-04 implementation, verify:

### 17.1 Scope

- [ ] No user-facing Run Now, Debug Run, Run Report, Monitoring, Schedule, auto allocation, multi-node, or API Catalog capability was introduced.
- [ ] No Redis, Celery, RabbitMQ, Kafka, Kubernetes, or external queue service was introduced.
- [ ] No editable Taurus YAML or generated YAML preview was introduced.

### 17.2 State Machine

- [ ] Run states are limited to the six P0 states.
- [ ] Terminal states cannot be overwritten by callbacks, Stop, or worker scans.
- [ ] `accepted` does not mean Running.
- [ ] `heartbeat` and `artifact` do not mutate state.
- [ ] State transitions use conditional updates.

### 17.3 Node Lease and Cleanup

- [ ] Run creation and lease acquisition are atomic.
- [ ] Active lease unique constraint exists.
- [ ] Node Busy is set only with active lease.
- [ ] Node Idle is restored only after safe cleanup.
- [ ] Force-kill failure or inconsistent managed process state quarantines the node.
- [ ] Stale lease recovery exists.
- [ ] Cooldown is a selection filter, not a node state.

### 17.4 Runner Protocol

- [ ] Callback schema uses `eventTime`, `eventId`, `nodeId`, `seq`, and `schemaVersion` v1.
- [ ] Callback idempotency uses `(runId,eventId)`, not `seq`.
- [ ] Duplicate same-payload callback is success.
- [ ] Duplicate different-payload callback returns `RUNNER_CALLBACK_CONFLICT`.
- [ ] Runner does not import API internals.
- [ ] Runner does not access PostgreSQL or MinIO directly.

### 17.5 Stop and Timeout

- [ ] First Stop returns `202`; duplicate Stopping Stop returns `200`; terminal Stop returns `409`.
- [ ] Repeated Stop does not create parallel stop requests.
- [ ] Accepted timeout converges to `failed`.
- [ ] Heartbeat timeout converges to `failed`.
- [ ] Stop grace timeout converges to `aborted` with `forcedConvergence=true`.

### 17.6 Artifacts

- [ ] Runner uploads artifacts through API only.
- [ ] Artifact type whitelist is enforced.
- [ ] Relative path safety follows `07`.
- [ ] Size and SHA-256 are validated server-side.
- [ ] Duplicate event and duplicate path behavior matches this SDD.
- [ ] MinIO object key is not returned to Web or audit details.

### 17.7 Security and Logs

- [ ] Browser APIs enforce session, CSRF, Workspace, and permission checks.
- [ ] Runner APIs enforce token and Run/Node binding.
- [ ] SSH credentials are decrypted only in transient memory.
- [ ] Runner token, SSH credentials, MinIO credentials, object keys, and secrets are redacted from logs, errors, audit details, artifacts, and snapshots.
- [ ] Audit events are present and bounded.

### 17.8 Verification

- [ ] `make generate-contracts` was run after API/schema changes.
- [ ] `make verify` passed.
- [ ] `make verify-e2e` was run when SSH-capable environment was available, or skipped with explicit reason.

---

## 18. Implementation Backfill


### 18.1 Actual implementation differences

1. P0-04 implements the SDD six-state Run model (`initializing`, `running`, `stopping`, `finished`, `failed`, `aborted`). The prompt's alternative `pending/starting/succeeded/stopped/error` wording was treated as non-authoritative because it conflicts with this Slice SDD and the foundation Runner state machine.
2. Public Run creation remains service-only. A guarded `create_protocol_smoke_run` helper is available only when `SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS=true` for tests and developer smoke flows.
3. The P0 worker claims run-control requests, builds a safe runner command, executes an injectable run-control executor outside the database transaction, and only then marks the request succeeded or failed. The production/default worker executor now uses Paramiko-backed SSH/SFTP with decrypted Load Node credentials held only in transient memory; automated tests inject fake adapters or fake executors for deterministic coverage.
4. Artifact upload metadata is stored through the existing storage adapter and returns only `artifactId` plus duplicate status. MinIO object keys remain server-only.
5. `api-worker` now runs P0-03 initialization recovery and P0-04 Run sweeps in one process, with a separate P0-04 advisory lock namespace (`9404`) and row-level claiming for run-control requests.
6. Follow-up review fix: timeout sweeps now force-converge Run state and enqueue shared `force_kill` cleanup without releasing the active node lease; the node remains Busy until force-kill completion releases it or force-kill failure quarantines it. Heartbeat timeout scanning also covers `running` Runs whose `started_at` is stale before the first heartbeat arrives.
7. Follow-up review fix: `api-worker` no longer marks `start`, `stop`, or `force_kill` run-control requests succeeded before execution. It now builds a `RunControlCommand`, invokes an injectable executor outside the DB transaction, records failures, and prevents stale `start`/`stop` requests from executing after the Run has moved out of the matching state.
8. Follow-up implementation, later revised: real SSH/SFTP run-control execution is implemented with `paramiko`, node-level trusted SSH host-key data, `RejectPolicy` for unknown or changed host keys, a small runner bundle uploader, per-run remote env files with `0600` permissions, safe `shlex` command assembly, bounded command timeout, sanitized stderr previews, and an opt-in Ubuntu 24.04 SSH Load Node smoke profile.
9. Hardening follow-up: Stop now resolves and locks the latest Run row inside the service before mutation, preventing stale browser actions from overwriting terminal state.
10. Hardening follow-up: stale `start` and `stop` run-control requests are cancelled when their target Run state makes them obsolete; they no longer force `runner_start_failed` or quarantine nodes after a legitimate Stop or terminal convergence.
11. Hardening follow-up: stale `running` run-control requests are recovered by the worker. Stale `force_kill` claims are reset to `pending` for retry, while obsolete `start`/`stop` claims are safely cancelled.
12. Hardening follow-up: stale terminal leases now enqueue the shared `force_kill` cleanup path instead of directly releasing nodes to Idle. Nodes remain unavailable until cleanup succeeds or quarantine is applied.
13. Hardening follow-up: terminal-late artifact upload now enforces the 5-minute diagnostic window and 1MB size bound, and validation mismatch after object write triggers best-effort object deletion.
14. Hardening follow-up: Runner callback runtime validation now uses the shared JSON Schema before Pydantic parsing, keeping API behavior aligned with `packages/contracts/runner/runner-callback.schema.json`.
15. Runner reality/boundary hardening follow-up: non-fake `runner.py start` now spawns a detached managed supervisor instead of a passive sleep placeholder. The supervisor sends `accepted`, `running`, heartbeat, and terminal callbacks. Stop targets the supervisor recorded in `supervisor.pid`; Kill targets only the workload process group recorded in `workload.pid`.
16. Runner reality/boundary hardening follow-up: Runner CLI now validates `runId` as a safe path segment, scans only SurgePilot-managed pidfiles under `RUNNER_HOME/runs`, refuses live stale managed processes before start, rejects invalid/self PGIDs, removes pidfiles after cleanup, and the SSH executor installs an env-file cleanup trap before sourcing `.surgepilot.env`.
17. Contract/test completion follow-up: Runner callback schema now constrains identity fields to the P0 ULID pattern, restricts artifact callback `artifactType` to the P0 whitelist, and requires `details.reason` for `failed` and `aborted` callbacks while keeping `finished` reason optional.
18. Verification follow-up: `make verify-runner-ssh` provides the near-real SSH/SFTP Runner smoke. Review hardening removed this Docker/SSH smoke from the default `make verify` gate; it remains explicit through `make verify-runner-ssh` and release/nightly `make verify-e2e`.
19. Review hardening follow-up: `stale_process_detected` now remains a quarantine-required cleanup reason, so successful force-kill releases the active lease but leaves the Load Node `quarantined` until Admin-confirmed residual cleanup followed by disable → enable → initialize.
20. Review hardening follow-up: accepted-but-not-running Runs now converge through the heartbeat/startup timeout sweep with reason `runner_start_timeout`, enqueue shared `force_kill`, and keep the node unavailable until cleanup completion.
21. Review hardening follow-up: Stop/Kill with a missing target pidfile is idempotent only when no other live SurgePilot-managed pidfile exists under `RUNNER_HOME/runs`; suspicious managed pidfiles fail the command so API cleanup can quarantine.
22. Review hardening follow-up: fake-runner success now uses the API-mediated artifact upload client for a small `run_log` and emits an `artifact` callback after upload success. Runner still receives no MinIO credentials.
23. Review hardening follow-up: Run creation now has a minimal internal `create_run_execution()` service for already-validated inputs. `create_protocol_smoke_run()` is only a guarded wrapper and no user-facing creation endpoint was added.
24. Review hardening follow-up: Stop OpenAPI path parameter is aligned to `{runId}`; Run artifact storage keys now use `run-artifacts/{workspaceId}/{runId}/{relativePath}`; callback `eventTime` requires UTC `Z`; terminal `details.reason` is constrained to lower snake case.
25. Review hardening follow-up: Runner process-control pidfiles are split into `supervisor.pid` and `workload.pid`. `accepted.runnerPid` is the supervisor process identifier only. `workload.pid` stores the local workload PGID and Linux `/proc/<pid>/stat` starttime for force-kill reuse protection. Non-fake Taurus execution starts with `start_new_session=True`; supervisor Stop sends SIGTERM to the supervisor and lets the supervisor terminate the workload PGID; `kill` targets only `workload.pid`; terminal callbacks compute `details.processGroupExited` by scanning `/proc` for non-zombie members of the workload PGID. Kill rejects starttime mismatch when the workload leader still exists, while allowing cleanup when the leader has exited but same-PGID non-zombie children remain.
26. Review hardening follow-up: `runner.py start` now self-heals confirmed stale pidfiles before launching, deletes corrupt `supervisor.pid`, archives corrupt `workload.pid` as `workload.pid.corrupt.<timestamp>`, and refuses only live managed supervisor/workload residue. If corrupt workload pidfile archival fails, start refuses to launch so the node can be quarantined instead of silently ignoring persistent residue. Pidfile writes use atomic same-directory replace with fsync. The default Stop supervisor wait is 120 seconds so the supervisor can finish SIGTERM/SIGKILL workload cleanup, artifact upload, and terminal reporting. If a supervisor has already exited while `workload.pid` still points at a live workload, the documented recovery path is `runner.py kill`, not repeated Stop.
27. macOS review follow-up: `ProcessGroupProbe` keeps Linux `/proc` scanning for non-zombie same-PGID detection, but falls back to POSIX `killpg(pgid, 0)` / `kill(pid, 0)` when `/proc` is unavailable so local developer gates can run on macOS. Runner tests that spawn real processes and require Linux `/proc` are guarded out of non-Linux default test runs; fake runner callbacks do not perform real process-group probing and may report `processGroupExited=true` because no workload process group is created in fake mode.

### 18.2 New or adjusted contracts

1. Added public `POST /api/v1/runs/{runId}/stop` (`stopRun`) with session, Workspace, and CSRF protection.
2. Added internal `POST /api/internal/v1/runner/callbacks` and `POST /api/internal/v1/runner/artifacts` with `x-runner-token`; both are excluded from exported public OpenAPI and the generated Web client.
3. Replaced the Runner callback placeholder with schema v1 using `eventTime`, `eventId`, `runId`, `nodeId`, `seq`, `eventType`, optional `message`, conditional `runnerPid`, and terminal `details.processGroupExited`.
4. Added Run persistence tables, Run Snapshot shell, node leases, callback receipts, run-control requests, artifact metadata, `load_nodes.last_force_kill_at`, and `load_nodes.current_run_id -> runs.id` (`ON DELETE SET NULL`).
5. Added P0-04 error codes for Stop, Runner auth/callbacks, artifacts, and run-control conflicts to the OpenAPI error-code registry.
6. Public Stop OpenAPI now documents both first Stop `202` and duplicate Stop `200` success responses.
7. Runner callback JSON Schema now explicitly encodes P0 ULID identity fields, P0 artifact type enum values, and failed/aborted terminal reason requirements.
8. Runner callback JSON Schema now requires UTC `Z` `eventTime` values and lower-snake-case terminal `details.reason` values.
9. Public Stop OpenAPI path parameter is `{runId}`.
10. Runner artifact object keys follow the storage SDD prefix `run-artifacts/{workspaceId}/{runId}/{relativePath}`.

### 18.3 Tests and verification commands

Automated coverage added:

1. Service tests for Run creation, snapshot/lease/Busy atomicity, lease conflict, guarded protocol smoke creation, transition table coverage, accepted/running/heartbeat/artifact/terminal callbacks, duplicate callback conflict, late terminal protection, Stop idempotency, timeout convergence, quarantine release, token validation, artifact validation/idempotency/conflict, and stale lease recovery.
   - Follow-up: added focused assertions that accepted/heartbeat/stop-grace timeout sweeps keep nodes unavailable until force-kill completion, force-kill failure quarantines nodes, and heartbeat timeout catches a `running` Run before its first heartbeat.
2. API tests for Stop CSRF/Workspace/idempotency/terminal behavior, Runner callback token layering without browser CSRF/session, artifact upload validation, and object-key non-exposure.
3. Worker tests for start request claiming, run-control executor invocation, executor failure handling, accepted-timeout convergence, force-kill execution after timeout, stale lease recovery, retention cleanup, and advisory-lock namespace separation from P0-03.
4. SSH/SFTP executor unit tests cover runner bundle upload, per-run env file creation, safe shell command construction, timeout/failure mapping, credential/token redaction, Paramiko channel draining, SFTP parent directory creation, password auth configuration, and unsupported private-key rejection.
5. Near-real SSH smoke uses an opt-in Ubuntu 24.04 container as a remote Load Node and validates real SSH/SFTP upload plus remote `start`, `stop`, idempotent repeated `kill`, and `force_kill` process cleanup.
6. Runner tests for `start --fake`, `stop`, `kill`, scoped pidfile writing, idempotent missing-pidfile cleanup, and artifact relative-path validation.
7. Contract tests for callback schema v1, public `stopRun`, P0-04 error codes, generated contract freshness, and absence of internal Runner endpoints from public OpenAPI/Web client.
8. Hardening tests added for service-level Stop locking, stale start cancellation, stale `force_kill` recovery after worker crash, stale terminal lease cleanup through `force_kill`, terminal-late artifact window/size policy, artifact object cleanup after validation mismatch, and runtime callback JSON Schema rejection.
9. Runner reality/boundary tests added for unsafe `runId` rejection, cross-Run live managed pidfile detection, non-fake managed callback flow, detached start plus Kill cleanup, self-PGID refusal, and SSH env-file cleanup trap coverage.
10. Contract/test completion added schema tests for ULID patterns, artifact type enum, artifact `storageKey` rejection, failed/aborted reason requirements, and finished-without-reason acceptance; API tests for callback body limit, duplicate callback conflict, artifact token/node/type/size/hash errors, duplicate artifact events, path conflicts, and response non-exposure; Runner tests for bounded callback backoff without token logging and shared-schema-valid fake/managed/stale callbacks.
11. Runner process cleanup tests cover fake `/proc` process-group probing, zombie leader with live same-PGID child, zombie-only groups, workload pidfile starttime validation, terminal callback `processGroupExited=false` when workload children survive Taurus main-process exit, Stop preserving pidfiles while signalling only the supervisor, Kill deleting `workload.pid` only after successful cleanup, Kill allowing cleanup when the workload leader is gone but same-PGID children remain, and Kill preserving/rejecting suspicious workload pidfiles.

Verification commands run successfully:

```bash
make generate-contracts
uv run --all-packages pytest apps/api/tests/test_p0_04_runs_service.py apps/api/tests/test_p0_04_runs_api.py apps/api/tests/test_p0_04_runs_worker.py apps/runner/tests/test_cli.py tests/contract/test_runner_callback_schema.py tests/contract/test_p0_04_runs_openapi.py -q
uv run --all-packages pytest apps/api/tests/test_p0_04_run_control_executor.py apps/api/tests/test_p0_04_runner_bundle.py apps/api/tests/test_p0_04_ssh_remote.py apps/api/tests/test_p0_04_runs_service.py apps/api/tests/test_p0_04_runs_api.py apps/api/tests/test_p0_04_runs_worker.py --cov=app.services.runs --cov=app.services.run_control_executor --cov=app.services.runner_bundle --cov=app.services.ssh_remote --cov=app.worker --cov-branch --cov-report=term-missing --cov-report=annotate:cov_annotate -q
make verify-runner-ssh
make verify
cd apps/api && DATABASE_URL=postgresql://surgepilot:surgepilot@localhost:5432/surgepilot uv run alembic upgrade head
```

Coverage summary from the P0-04 targeted pass: `apps/api/app/services/runs.py` 97% line coverage with 95% branch coverage, `run_control_executor.py` 93%, `runner_bundle.py` 95%, `ssh_remote.py` 98%, and targeted total 93%. Repository API total coverage during `make verify`: 93.84%; staged diff coverage: 97%; SSH smoke: 1 passed.

### 18.4 Remaining risks or known gaps

1. The near-real SSH/SFTP Runner smoke is not part of the default `make verify` gate after the review hardening. Environments that need Docker/SSH validation must run `make verify-runner-ssh` or `make verify-e2e` explicitly; the SSH pytest files remain guarded by `SURGEPILOT_SSH_E2E=1`.
2. The SSH smoke and managed child validate the P0 Runner process-control, callback, heartbeat, Stop, and Kill path, not a full Taurus/JMeter dependency installation or real load generation; automatic installation of missing Taurus/JMeter/Java dependencies remains out of scope for P0-04.
3. P0-04 intentionally does not expose Run creation, Run list, Run report, artifact download/preview, Scenario, or Test Plan UI/API behavior; later slices must bind their public creation/reporting contracts to these services.
4. Terminal-late artifact policy is implemented at the metadata boundary used by P0-04; P0-07 still owns user-facing artifact listing/download/preview semantics.
5. P0 real Load Nodes and SSH smoke targets remain Linux-first. Non-Linux local development uses POSIX `killpg(pgid, 0)` / `kill(pid, 0)` fallback so default test gates can run on macOS, but that fallback does not provide Linux `/proc` zombie filtering or same-PGID member scanning.

### 18.5 Preconditions for later P0 slices

1. P0-05/P0-06 must call the Run creation service with already-validated Scenario/Test Plan input and exactly one visible `idle` Load Node.
2. P0-06 must keep `SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS=false` for production user-facing APIs and must not expose `protocol_smoke` Runs as product Runs.
3. P0-07 may read `run_artifacts` metadata but must not return `storage_key` or expose direct MinIO access.
4. Quarantined Load Nodes require Admin-confirmed residual process and Monitoring secret cleanup followed by disable → enable → initialize; no automatic quarantine recovery should be added without a later Slice/ADR.
5. Runner integrations must continue using `packages/contracts/runner/runner-callback.schema.json` and must not import `apps/api` internals or access PostgreSQL/MinIO directly.

Do not use backfill to expand product scope.

## 18A. P0-04 Independent Review Report


### 18A.1 Coverage review (`pytest-coverage`)

- Ran targeted annotated coverage: `uv run --all-packages pytest apps/api/tests/test_p0_04_run_control_executor.py apps/api/tests/test_p0_04_runner_bundle.py apps/api/tests/test_p0_04_ssh_remote.py apps/api/tests/test_p0_04_runs_service.py apps/api/tests/test_p0_04_runs_api.py apps/api/tests/test_p0_04_runs_worker.py --cov=app.services.runs --cov=app.services.run_control_executor --cov=app.services.runner_bundle --cov=app.services.ssh_remote --cov=app.worker --cov-branch --cov-report=term-missing --cov-report=annotate:cov_annotate -q`.
- Result: 41 passed; `apps/api/app/services/runs.py` has 97% line coverage and 95% branch coverage, satisfying the required state-machine threshold (line >=95%, branch >=90%). The new SSH executor modules are also covered: `run_control_executor.py` 93%, `runner_bundle.py` 95%, `ssh_remote.py` 98%.
- Repository `make verify` result: API/contract 179 passed, 4 skipped; Runner 5 passed; Web Vitest 23 passed; total API coverage 93.84%; staged diff coverage 97%; contract stale check passed.

### 18A.2 Python testing review (`python-testing-patterns`)

- P0-04 API/service/worker tests use deterministic direct timestamps or injected `now` arguments for timeout behavior; no P0-04 test uses sleep-based timing.
- Grep found no `sleep` calls in P0-04 tests. Production Runner/worker retry loops still use bounded sleeps, outside test timing assertions.
- Concurrent/duplicate paths are tested through deterministic DB uniqueness, row claiming, duplicate callback replay, and repeated Stop calls rather than wall-clock races.
- Test helpers are function-scoped; no mutable global test state was introduced.

### 18A.3 FastAPI/API contract review (`fastapi`)

- Internal Runner routes are declared with `include_in_schema=False`; generated public OpenAPI and `@surgepilot/contracts` Web client contain `stopRun` and do not contain `runner/callbacks` or `runner/artifacts`.
- Browser Stop uses session auth, Workspace resolution, and `x-csrf-token`; internal Runner endpoints use only `x-runner-token` and do not depend on cookie session or CSRF.
- Error responses use the existing `{code, message, requestId, details?}` shape with safe English fallback messages.

### 18A.4 PostgreSQL schema review (`postgresql-table-design`)

- `node_leases` has unique `(run_id)` and partial unique active lease on `(node_id) WHERE released_at IS NULL`.
- `run_control_requests` has partial unique active request on `(run_id, action)` for `pending/running` work.
- Run, callback, control-request, artifact, and Load Node status fields use text plus CHECK constraints, with FK indexes and query indexes for worker scans.
- `load_nodes.current_run_id` is linked to `runs.id` with `ON DELETE SET NULL`; terminal convergence is still service-owned and does not rely on deleting Runs.
- P0-04 advisory lock namespace `9404` is distinct from P0-03 initialization lock `9303`.

### 18A.5 Docker/api-worker review (`docker-expert`)

- Docker Compose keeps one `api-worker` service, using the same API image and `python -m app.worker` entrypoint.
- `api-worker` depends on healthy PostgreSQL and completed MinIO initialization, and has `restart: unless-stopped` plus explicit P0-04 timeout/retention environment defaults.
- Added an `ssh-e2e` profile with a single Ubuntu 24.04 SSH Load Node container, healthcheck, and port default `22322` to avoid common local SSH port conflicts. This profile is now executed by default through `make verify`.
- No Redis, Celery, RabbitMQ, Kafka, Kubernetes, or external queue service was introduced.

### 18A.6 Architecture and scope review

- No `apps/web` source files, navigation, or user-facing P1/P2 capabilities were added.
- Runner remains independent and imports no `apps/api` internal modules.
- API owns database, storage, Workspace/permission checks, Runner token validation, callback idempotency, and artifact metadata.
- P0-03 handoff is preserved: P0-04 owns Busy lease release and quarantine on Run cleanup, while quarantine recovery remains Admin-confirmed residual cleanup followed by the existing disable → enable → initialize transitions.
- P0-05/P0-06/P0-07 handoff points remain service/contract-level only.

### 18A.7 Follow-up review fixes


- Confirmed the review comments were valid against SDD cleanup safety rules.
- Fixed timeout convergence so `_force_converge` no longer releases the node lease or returns a Busy node to Idle before the shared `force_kill` run-control path completes.
- Fixed stale lease recovery so it does not release a terminal Run's lease while an active `force_kill` request is still pending or running.
- Fixed heartbeat timeout scanning to include `running` Runs with stale `started_at` and no first heartbeat.
- Added deterministic unit coverage for force-kill success release, force-kill failure quarantine, and no-first-heartbeat timeout.

### 18A.8 Run-control execution follow-up


- Confirmed the review comment was valid: the previous worker path reloaded a claimed request and completed it without invoking a runner/SSH execution boundary.
- Added `RunControlCommand`, `RunControlExecutionResult`, an injectable `RunControlExecutor`, and a default fake SSH/SFTP executor for deterministic P0 tests.
- Updated `api-worker` to execute run-control work outside database transactions, then complete the request according to executor success or failure.
- Start executor failure now marks the Run `failed`, records request error metadata, releases the lease, and quarantines the node.
- Stale `start` or `stop` requests are not executed after the Run leaves the matching state.
- Full real SSH/SFTP command execution was completed in the follow-up implementation described in §18A.9.

### 18A.9 Real SSH/SFTP executor follow-up


- Implemented `ParamikoSshSftpAdapter`, `RunnerBundle`, and `RemoteRunControlExecutor` as the default `api-worker` run-control executor. The API decrypts SSH credentials only when executing a bounded command and does not pass SSH credentials to Runner payloads.
- The executor uploads the independent `apps/runner` bundle, writes a per-run `.surgepilot.env` with mode `0600`, sources it through a `set -eu` shell path, removes the env file before `exec`, and assembles all remote command arguments through `shlex`.
- Paramiko command execution now drains stdout/stderr through the channel instead of blocking on `ChannelFile.read()`, preventing hangs on commands with empty output and bounding sanitized previews.
- Added deterministic unit tests for upload/env/command safety, timeout and remote failure mapping, channel draining, SFTP directory creation, bundle discovery, unsupported key material, and credential/token non-leakage.
- Added `infra/docker/ssh-load-node` and `make verify-runner-ssh` for an Ubuntu 24.04 SSH/SFTP smoke that validates remote `start`, `stop`, repeated `kill`, and `force_kill`. The review hardening keeps this as an explicit SSH/E2E gate instead of running it from default `make verify`.

### 18A.10 Final independent review conclusion

No P0/P1 blocking issues remain after the review fixes above.

### 18A.11 Review Backfill

1. Internal artifact upload validates `x-runner-token` before parsing multipart form data.
2. Artifact upload rejects oversized `Content-Length` before multipart parsing after token validation; exact artifact byte limits are still enforced by storage streaming.
3. Artifact storage keys follow the canonical storage SDD prefix `run-artifacts/{workspaceId}/{runId}/{relativePath}`; duplicate path handling is enforced by the run-row lock and `(runId, relativePath)` conflict checks rather than artifact-ID path segments.
4. Artifact metadata finalization uses a short DB transaction after storage upload, reducing Run row lock time during slow MinIO writes.
5. Callback payload/details are recursively sanitized before persistence and hashing, including camelCase sensitive keys such as `apiKey`.
6. Callback outcomes now have structured logs for applied, duplicate, and ignored callbacks.
7. Generated Taurus YAML includes `reporting.final-stats.dump-csv: artifacts/finalstats.csv`, aligning the Runner's expected `finalstats.csv` artifact with Taurus configuration.
8. Runner bundle discovery now checks configured/container bundle directories before any repository-layout fallback, so the Docker `api-worker` uses `SURGEPILOT_RUNNER_BUNDLE_DIR=/opt/surgepilot/runner-bundle` without assuming host-source parent depth.
9. Added `make verify-smoke-compose`, which starts the full smoke Docker Compose stack after an `api-migrate` sidecar runs `alembic upgrade head`, checks `/api/healthz`, and fails if `api-worker` startup logs contain cycle failures, tracebacks, or `IndexError`.
