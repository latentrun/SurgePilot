# 05 Runner Protocol and Run State Machine

- Document status: Draft v3 for implementation planning
- Product: SurgePilot
- Document path: `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- Current delivery target: P1 governance start / P1 Slice kickoff; P1-08 Debug HTTP Trace is active only through ADR-0008 and its Slice SDD
- Applies to: Foundation SDD, Run Slice, Load Node Slice, Runner, API, api-worker, contracts, tests, AI Coding, code review
- Depends on: `docs/prd/PRD.md`, `docs/sdd/00-product-scope-and-priority.md`, `docs/sdd/01-architecture-overview.md`, `docs/sdd/02-repo-structure-and-dev-workflow.md`, `docs/sdd/04-api-contract-guidelines.md`, `docs/sdd/06-security-permission-workspace.md`, `docs/sdd/07-storage-artifacts-minio.md`, `docs/sdd/09-testing-and-acceptance-strategy.md`

---

## 1. Purpose

This article defines the Runner Protocol, Run state machine, callback idempotence, Stop convergence, heartbeat timeout, self-healing, node lease and minimum artifact ingest boundary of the SurgePilot P0 phase.

This article serves three goals:

1. Let API, api-worker, Runner and contracts have a unique understanding of the Run life cycle;
2. Prevent Run from being stuck, Load Node to be permanently busy, terminal status to be overwritten by subsequent callbacks, Stop to be executed repeatedly, and callbacks to be out of order, resulting in state confusion;
3. Prevent the remaining load test process from continuing to send traffic after the Runner loses contact, contaminating the test results of subsequent runs.

This article is Foundation SDD, not a complete implementation description of a Slice. It only locks in global protocols, state machines, transaction boundaries, idempotent rules, and self-healing principles. Specific endpoint request/response, migration files, test files, UI button states, execution bundle manifest and Done When should enter the corresponding Slice SDD.

---

## 2. Authority and Conflict Resolution

### 2.1 Canonical Inputs

This article relies on the following documents:

1. `docs/prd/PRD.md`: The only product source for product scope, terminology, Run life cycle and acceptance criteria;
2. `docs/sdd/00-product-scope-and-priority.md`: P0/P1/P2 scope gate and P0-Stability requirements;
3. `docs/sdd/01-architecture-overview.md`: component boundaries, api-worker, Runner independence, MinIO only and prohibited dependencies;
4. `docs/sdd/02-repo-structure-and-dev-workflow.md`: repository structure, Runner directory, contracts, fake runner and verify workflow;
5. `docs/sdd/04-api-contract-guidelines.md`: REST path, internal runner endpoint, headers, error shape, enum, OpenAPI and contract tests;
6. `docs/sdd/06-security-permission-workspace.md`: Workspace, permissions, audit, runner token and sensitive information rules;
7. `docs/sdd/07-storage-artifacts-minio.md`: MinIO object key, path safety, artifact download and preview rules;
8. `docs/sdd/09-testing-and-acceptance-strategy.md`: Test layering, CI and acceptance strategies.

### 2.2 Conflict Resolution

Conflict handling rules:

1. If this article conflicts with `docs/prd/PRD.md`, the PRD shall control and revise this article.
2. If this article conflicts with `docs/sdd/00-product-scope-and-priority.md`, 00 shall prevail unless 00 conflicts with PRD.
3. If this article conflicts with `docs/sdd/01-architecture-overview.md`, the architectural boundary of 01 shall prevail, and this article shall be revised simultaneously.
4. If this article conflicts with `docs/sdd/04-api-contract-guidelines.md`, the API path, header, error shape, OpenAPI and public contract rules shall prevail in 04; the Run state machine and Runner callback semantics shall prevail in this article, and the old runner-specific details in 04 shall be revised simultaneously.
5. If this article conflicts with `docs/sdd/07-storage-artifacts-minio.md`, the MinIO object key, path normalization, download permission and preview rules shall be subject to 07; the timing of artifact ingest from the Runner to the API shall be subject to this article and shall be revised simultaneously.
6. Slice SDD can refine the implementation fields, test files, endpoint schema and Done When, but must not destroy the state machine, idempotence, self-healing and security boundaries defined in this article.
7. Code implementation must not skip Stop idempotence, callback idempotence, heartbeat timeout, self-healing, force kill or node lease convergence on the grounds of "already implemented", "front-end convenience", "remote command complexity" or "will be added later".


### 2.3 Cross-Document Follow-Ups

The following cross-document updates must be completed before P0-04 implementation begins:

1. Register or confirm these API error codes in `docs/sdd/04-api-contract-guidelines.md` error code registry:
   - `RUN_TERMINAL_STATE` = `409`;
   - `RUNNER_UNAUTHORIZED` = `401`;
   - `RUNNER_FORBIDDEN` = `403`;
   - `RUNNER_CALLBACK_INVALID` = `422`.
2. Align `packages/contracts/runner/runner-callback.schema.json` with this document:
   - callback idempotency uses `eventId`;
   - `seq` is diagnostic only;
   - `schemaVersion` is required and P0 only accepts `"1"`.
3. Ensure Load Node Slice and Storage Slice reflect:
   - `quarantined` node state;
   - post force-kill cooldown;
   - API-mediated artifact upload without Runner MinIO credentials.
4. Register the following audit event types in `docs/sdd/06-security-permission-workspace.md` audit registry:
   - `run.stop_requested`;
   - `run.force_kill`;
   - `load_node.quarantined`.
5. Add explicit handoff requirements for future Foundation docs so they cannot miss this protocol:
   - `docs/sdd/03-domain-model-overview.md` must include Run/LoadNode/RunnerCallbackEvent models with `forcedConvergence` and `requestId` trace fields;
   - `docs/sdd/07-storage-artifacts-minio.md` must include a dedicated path safety section covering upload, key normalization, traversal rejection, download/preview checks and audit-safe diagnostics;
   - `docs/sdd/09-testing-and-acceptance-strategy.md` must include callback idempotency, force-kill/quarantine, and api-worker crash-mid-cleanup recovery matrix (stale lease recovery resumes cleanup or keeps node unavailable).

---

## 3. Confirmed Decisions

| Area | Decision |
| --- | --- |
| Product name | SurgePilot |
| Current target | P1 governance start / P1 Slice kickoff; P0 stability remains non-regression baseline |
| Run states | `initializing`, `running`, `stopping`, `finished`, `failed`, `aborted` |
| Terminal states | `finished`, `failed`, `aborted` |
| API / DB enum values | lower snake case |
| Product/UI labels | Title Case may be used in UI text, for example Initializing / Running |
| Runner callback events | `accepted`, `running`, `heartbeat`, `artifact`, `finished`, `failed`, `aborted` |
| Callback endpoint | `POST /api/internal/v1/runner/callbacks` |
| Artifact upload endpoint | `POST /api/internal/v1/runner/artifacts` |
| Internal runner auth | `x-runner-token` |
| Runner token binding | API validates that `runId` belongs to the Runner identity bound to `x-runner-token` |
| Browser auth / CSRF on runner endpoints | Not required for runner-only endpoints |
| Runner callback schema | `packages/contracts/runner/runner-callback.schema.json` |
| Callback schema version | `"1"` only in P0 |
| Callback idempotency key | `eventId`; API deduplicates by `(run_id, event_id)` |
| Callback `seq` | Required for diagnostics only; not used for state transition decisions |
| State transition authority | API database state + event type; not Runner timestamps |
| Timestamp authority | API `receivedAt`; Runner `eventTime` is stored for display/diagnostics only |
| Terminal overwrite rule | Terminal states cannot be overwritten by late callbacks |
| Runner-reported terminal cleanup | Terminal callbacks must include `processGroupExited`; lease is released only when cleanup is known safe |
| Stop entry | Only user/API Stop moves Run to `stopping` |
| Stop convergence | Normal `aborted` callback, or api-worker forced convergence after grace timeout |
| Heartbeat interval | Runner sends every 15 seconds |
| Heartbeat timeout | 60 seconds without heartbeat while active |
| Worker scan interval | 10 seconds |
| Accepted wait window | 120 seconds after remote start is requested |
| Uncertain remote start cleanup | api-worker marks the allocation failed, retains its lease and Busy node, queues same-allocation force kill, then releases or quarantines the node from that cleanup result |
| Heartbeat timeout cleanup | api-worker marks Run failed, force kills remote process, then releases or quarantines node |
| Stop grace period | 60 seconds |
| Stop grace cleanup | api-worker forces Run aborted, force kills remote process, then releases or quarantines node |
| Force kill SSH timeout | 30 seconds |
| Terminal-callback sanity SSH timeout | 10 seconds when `processGroupExited=false` |
| Post force-kill cooldown | P0 default 5 minutes; configurable by `SURGEPILOT_NODE_COOLDOWN_SECONDS` |
| Stale lease recovery threshold | 2 hours |
| Post-terminal artifact window | 5 minutes after `endedAt`, max 1MB, diagnostics only |
| Process group termination | `SIGTERM`, wait 10 seconds, then `SIGKILL` |
| Node quarantine | Force kill failure, stale process detection, or unknown runner state makes node unavailable |
| Runner MinIO credentials | Forbidden in P0 |
| Runner DB access | Forbidden |
| External queue / Redis / Celery | Forbidden in P0 |
| Resource allocation | Manual single-node only in P0 |
| Fake runner | Allowed for development and smoke, but must share callback client/contract and cannot replace real Runner acceptance |

---

## 4. Scope and Non-Goals

### 4.1 In Scope

This article defines:

1. Run state machine and legal state transition;
2. Mapping of callback event and Run status;
3. callback schema, idempotence, out-of-order processing and size limit;
4. Stop request, remote stop, grace period and forced convergence;
5. heartbeat interval, timeout and accepted wait window;
6. Remote force kill and node quarantine after heartbeat timeout;
7. Runner process group, pidfile, stale process detection;
8. Node lease acquisition, release and stale recovery principles;
9. The boundary between artifact upload and artifact callback;
10. Consistency constraints of fake runner;
11. Minimum testing and review requirements.

### 4.2 Out of Scope

This article does not define:

1. Complete Run to create API request/response schema;
2. Complete Run List / Run Report API schema;
3. Complete Alembic migration file;
4. Specific ORM model, repository, and service file names;
5. Complete fields of execution bundle manifest;
6. Taurus YAML generation rules;
7. MinIO object key algorithm, download permission, preview rules;
8. Field mapping of Run Report summary parser;
9. Front-end page layout, button style and polling strategy;
10. API Catalog, Monitoring, Schedule Run, multi-node, automatic allocation, resource queuing, Kubernetes or non-MinIO storage.

These contents are entered respectively:

- `docs/sdd/03-domain-model-overview.md`: Overview of domain model and table relationships;
- `docs/sdd/07-storage-artifacts-minio.md`: MinIO, artifact object key, path security, download and preview;
- `docs/sdd/09-testing-and-acceptance-strategy.md`: complete test matrix;
- `docs/sdd/slices/P0-03-load-nodes.md`: Load Node status, initialization, re-initialize and node UI;
- `docs/sdd/slices/P0-04-run-state-machine-runner-protocol.md`: specific Run / Runner implementation, migration, API schema, tests and Done When;
- `docs/sdd/slices/P0-07-run-report-artifacts-validity.md`: Run Report, summary parsing, artifact display and validity.

---

## 5. Component Boundary

### 5.1 API

The API is the business status center and is responsible for:

1. Create Run, Run Snapshot and node lease;
2. Receive Runner callback;
3. Execute state conditional transfer;
4. Write the runner callback event record;
5. Receive artifact upload and write to MinIO;
6. Manage artifact metadata;
7. Perform session, CSRF, Workspace and permission verification on public business API;
8. Verify `x-runner-token` on internal runner API;
9. Return a unified error response and `x-request-id`.

The API must not:

1. Execute SSH/SFTP/long time-consuming file upload in Run to create DB transaction;
2. Leave the final status of Run to Runner to decide;
3. Let the terminal status be overwritten by late callback;
4. Directly return the MinIO object key, runner token, SSH credential or server path to the Web;
5. Implement P1/P2 available capabilities.

### 5.2 api-worker

api-worker is an independent process and is responsible for:

1. accepted wait timeout scan;
2. heartbeat timeout scan;
3. stop grace timeout scanning;
4. stale node lease recovery;
5. Remote stop / remote kill cleanup that needs to be retried;
6. Artifact summary parsing or lightweight DB job processing;
7. Write self-healing related audit events and structured logs.

The api-worker can perform bounded SSH cleanup, but must not be a resource queuing system or external task queue replacement.

api-worker must not:

1. As HTTP API;
2. Introduce Redis, Celery, RabbitMQ, Kafka or external queue;
3. Repeatedly perform global scans on multiple instances without holding appropriate DB coordination;
4. After force kill fails, put the node directly back to Idle.

### 5.3 Runner

Runner is a standalone Python application on Load Node, responsible for:

1. Receive execution bundle;
2. Create the Run directory;
3. Write pidfile;
4. Start Taurus/JMeter;
5. Maintain independent process group;
6. Send callback;
7. Upload artifacts to API;
8. Execute the `stop` and `kill` subcommands;
9. Detect predecessor residual pidfile/process at `start`.

Runner must not:

1. Access PostgreSQL;
2. Import API internal code;
3. Hold MinIO direct credentials;
4. Access the Web;
5. Determine the final status of the business;
6. Write `x-runner-token`, SSH credential, MinIO credential, or env secret to the log.

### 5.4 Load Node

Load Node hosts Runner, Taurus/JMeter and run directory. Load Node does not save the platform business status. All business state must be managed by API/PostgreSQL.

---

## 6. Run Lifecycle Overview

P0 Run Now / Debug main process:

```text
User clicks Run Now / Debug
  -> API validates Workspace, permissions, Test Plan / Scenario, Env Group, Dependency Files and selected Load Node
  -> API atomically creates Run Snapshot, Run(initializing), and active node lease
  -> API commits DB transaction
  -> API uploads runner.py / bundle / config / dependency files to the Load Node by SSH/SFTP
  -> API requests remote runner start
  -> runner.py start classifies managed pidfiles/processes
  -> runner.py spawns detached process group and writes pidfile
  -> runner sends accepted callback
  -> detached runner starts Taurus / JMeter
  -> runner sends running callback when load execution actually starts
  -> runner sends heartbeat every 15 seconds
  -> runner uploads artifacts and sends artifact callbacks
  -> runner sends finished / failed / aborted terminal callback
  -> API terminal transition releases node lease and Run Report becomes stable
```

Rules:

1. Run creation transaction must include Run Snapshot and node lease acquisition.
2. Run creation transaction must not include SSH / SFTP / remote command execution.
3. If remote start fails before accepted callback, API or api-worker must converge the Run to `failed` and release or quarantine the node according to cleanup result.
4. Run List and Run Report must be driven by API state and worker self-healing, not by frontend polling side effects.
5. P0 supports manual single-node execution only.

---

## 7. Run State Model

### 7.1 States

| API / DB value | Product label | Meaning | Terminal |
| --- | --- | --- | --- |
| `initializing` | Initializing | Run is created, resources are leased, runner start is pending or accepted, but load execution has not started | no |
| `running` | Running | Taurus / JMeter execution has actually started | no |
| `stopping` | Stopping | User requested Stop and SurgePilot is converging the Run to cancellation | no |
| `finished` | Finished | Runner completed successfully and final artifacts/report summary can be processed | yes |
| `failed` | Failed | System, runner, test execution, timeout, bundle, startup or infrastructure error | yes |
| `aborted` | Aborted | User Stop was requested and the Run was cancelled or force-converged as cancelled | yes |

Rules:

1. API and DB enum values use lower snake case.
2. UI may display Title Case labels.
3. `finished`, `failed`, and `aborted` are terminal.
4. Terminal state cannot be overwritten by late callbacks.
5. `stopping` is only entered by user/API Stop.

### 7.2 Terminal Semantics

| Terminal state | Meaning |
| --- | --- |
| `finished` | Execution completed without runner/test fatal error. SLA verdict may still be passed or failed. |
| `failed` | SurgePilot, Runner, Load Node, bundle, heartbeat, artifact-critical path, or test execution encountered an error not caused by user Stop. |
| `aborted` | User requested Stop and SurgePilot successfully or forcefully converged the Run as cancelled. |

Rules:

1. `Aborted` means user intent was cancellation.
2. `Failed` means platform, runner, node, startup, heartbeat, bundle or test-layer failure.
3. A Run can be `finished` while SLA verdict is `failed`; SLA failure is not the same as Run state `failed`.
4. Debug Run validity defaults and Run validity are outside this document and belong to Run / Report Slice SDD.

### 7.3 Legal State Transitions

| Current state | Trigger | New state | Notes |
| --- | --- | --- | --- |
| none | Run created | `initializing` | Run Snapshot and node lease created in same DB transaction |
| `initializing` | `accepted` callback | `initializing` | Record `acceptedAt`, `runnerPid`, and latest event only |
| `initializing` | `running` callback | `running` | Load execution has started |
| `initializing` | user/API Stop | `stopping` | Stop is allowed before actual Running |
| `initializing` | `failed` callback | `failed` | Runner-reported terminal event; release lease only if `processGroupExited=true`, otherwise cleanup/quarantine |
| `initializing` | `aborted` callback | `aborted` | Runner-reported terminal event; release lease only if `processGroupExited=true`, otherwise cleanup/quarantine |
| `initializing` | accepted wait timeout | `failed` | reason = `runner_accept_timeout`; cleanup then release/quarantine |
| `running` | `heartbeat` callback | `running` | Update `lastHeartbeatAt` only |
| `running` | `artifact` callback | `running` | Register timeline/metadata only |
| `running` | user/API Stop | `stopping` | Record stop requester and time |
| `running` | `finished` callback | `finished` | Release lease only if `processGroupExited=true`, otherwise cleanup/quarantine |
| `running` | `failed` callback | `failed` | Runner-reported terminal event; release lease only if `processGroupExited=true`, otherwise cleanup/quarantine |
| `running` | `aborted` callback | `aborted` | Runner-reported terminal event; release lease only if `processGroupExited=true`, otherwise cleanup/quarantine |
| `running` | heartbeat timeout | `failed` | reason = `heartbeat_timeout`; force kill then release/quarantine |
| `stopping` | `heartbeat` callback | `stopping` | Update heartbeat only |
| `stopping` | `artifact` callback | `stopping` | Register metadata only |
| `stopping` | `aborted` callback | `aborted` | Normal Stop convergence; release lease only if `processGroupExited=true`, otherwise cleanup/quarantine |
| `stopping` | `failed` callback | `failed` | Only if runner explicitly reports non-stop failure before grace convergence; release lease only if `processGroupExited=true`, otherwise cleanup/quarantine |
| `stopping` | stop grace timeout | `aborted` | `forcedConvergence=true`; force kill then release/quarantine |
| terminal | any callback | unchanged | Store/log event, do not mutate terminal state |

Rules:

1. `accepted` does not mean load execution has started.
2. `heartbeat` and `artifact` never change Run state.
3. `finished` is accepted only from `running`.
4. `failed` can move any non-terminal state to `failed`, except when Stop grace has already force-converged to `aborted`.
5. `aborted` can move `initializing`, `running`, or `stopping` to `aborted`.
6. Ignored callbacks must be logged with reason.
7. Runner terminal callbacks (`finished`, `failed`, `aborted`) must include `details.processGroupExited`.
8. When `processGroupExited=true`, API may release the node lease in the same DB transaction as the terminal transition.
9. When `processGroupExited=false`, API must keep the node unavailable and trigger the shared post-terminal force-kill subroutine in §12.4 before the node can become selectable again.
10. `stale_process_detected` is a safety exception: API marks the Run `failed`, marks the node `quarantined`, and requires the §13.1 quarantine recovery workflow even if a later cleanup attempt removes the process.
11. API/api-worker initiated terminal convergence, for example accepted wait timeout, heartbeat timeout, or stop grace timeout, always requires remote cleanup before the node can become selectable again.

### 7.4 Conditional Update Rule

State transitions must use conditional DB updates instead of read-then-write logic.

Example concept:

```sql
UPDATE runs
SET state = :new_state,
    updated_at = now()
WHERE id = :run_id
  AND state = ANY(:legal_predecessors);
```

Rules:

1. `affected_rows = 1` means the transition was applied.
2. `affected_rows = 0` means the event was duplicate, late, illegal, or already terminal; treat it as idempotent ignore unless the caller is a public action that must return a conflict.
3. Do not add a generic optimistic lock `version` column just for Run state transition in P0.
4. If a transition enters a terminal state and does not require remote cleanup before lease release, release node lease in the same DB transaction.
5. If a transition enters terminal due to heartbeat timeout or stop grace timeout, keep the node unavailable until remote cleanup finishes; see §12.

---

## 8. Runner Callback Protocol

### 8.1 Endpoint

```http
POST /api/internal/v1/runner/callbacks
x-runner-token: <runner token>
Content-Type: application/json
```

Rules:

1. This endpoint is internal runner-only.
2. It must not require browser session cookie.
3. It must not require CSRF token.
4. It must validate `x-runner-token` before parsing or applying payload.
5. It must not be included in the Web generated OpenAPI client.
6. It must return `401 RUNNER_UNAUTHORIZED` for missing or invalid token.
7. It must return `422 RUNNER_CALLBACK_INVALID` for schema-invalid payload.
8. Duplicate valid callback events return success and must not be treated as an error.
9. API must validate that the `runId` in payload belongs to the Runner identity bound to `x-runner-token`; mismatch returns `403 RUNNER_FORBIDDEN`.

### 8.2 Schema Source

The source of truth is:

```text
packages/contracts/runner/runner-callback.schema.json
```

Rules:

1. Runner callback payload must validate against this JSON Schema.
2. API must not require Runner to import API Pydantic classes.
3. Runner must not import API internal schema code.
4. Schema changes must update contract tests.
5. P0 supports `schemaVersion: "1"` only.
6. Unknown `schemaVersion` must return `400 INVALID_REQUEST` or `422 RUNNER_CALLBACK_INVALID`; Slice SDD must choose one status consistently.

### 8.3 Required Base Payload

All callback events must include:

```json
{
  "schemaVersion": "1",
  "eventId": "01J00000000000000000000001",
  "runId": "01J00000000000000000000002",
  "nodeId": "01J00000000000000000000003",
  "eventType": "heartbeat",
  "seq": 4,
  "eventTime": "2030-05-20T04:00:00.000Z",
  "message": "Heartbeat received."
}
```

Fields:

| Field | Required | Rule |
| --- | --- | --- |
| `schemaVersion` | yes | String, `"1"` in P0 |
| `eventId` | yes | ULID generated by Runner per callback event |
| `runId` | yes | ULID of Run |
| `nodeId` | yes | ULID of Load Node |
| `eventType` | yes | One of supported event types |
| `seq` | yes | Monotonic per Run from Runner perspective; diagnostic only |
| `eventTime` | yes | Runner clock time, ISO 8601 UTC string with `Z` |
| `message` | no | Human-readable English fallback, max length bounded |
| `runnerPid` | required for `accepted` | Supervisor process identifier reported by Runner; it is not the workload PGID. Missing value makes the callback schema-invalid. |
| `details` | no | Small event-specific object; no secrets |

Rules:

1. API stores `receivedAt` from API server time and uses it as authoritative ordering time.
2. `eventTime` is stored only for display and diagnostics.
3. State transition must not depend on `eventTime`.
4. `seq` must not decide state transitions.
5. `details` must not contain secrets, credentials, full environment variables, runner token, MinIO credential, SSH credential, server absolute paths, or large logs.
6. Callback body size limit is 8KB.
7. Future large previews such as P1 failed requests must be uploaded as artifacts, not embedded in callback.

### 8.4 Event Types

| Event type | State effect | Required / common details |
| --- | --- | --- |
| `accepted` | Does not change state | Required: `runnerPid`. Common: runner version, pidfile path basename only if needed |
| `running` | `initializing` -> `running` | Taurus/JMeter start confirmation |
| `heartbeat` | No state change | lightweight progress fields only |
| `artifact` | No state change | `artifactId`, `artifactType`, `relativePath`, `sizeBytes`, `sha256` |
| `finished` | `running` -> `finished` | `processGroupExited`, exit code, optional `slaResult` when passfail was evaluated |
| `failed` | non-terminal -> `failed` (incl. `stopping`; see §7.3) | `processGroupExited`, stable reason, safe message, exit code if any, optional `slaResult` |
| `aborted` | `initializing`/`running`/`stopping` -> `aborted` | `processGroupExited`, stop reason, safe message, optional `slaResult` |

Rules:

1. `accepted` records supervisor process acceptance only; it must not move Run to `running`.
2. `accepted.runnerPid` is required, identifies the supervisor, and must not be interpreted as the workload PGID. Missing `runnerPid` makes the callback schema-invalid.
3. `running` is the first event that means load execution actually started.
4. `heartbeat` should update `lastHeartbeatAt`.
5. `artifact` should register event timeline or connect uploaded metadata, but must not determine terminal state.
6. Terminal event handlers must be idempotent.
7. Terminal callbacks must include `details.processGroupExited`; missing value makes the callback schema-invalid.
8. Late terminal events after another terminal state must not overwrite the existing terminal state.
9. Terminal callback `details.slaResult`, when present, must be `passed` or `failed`; P0-07 owns storage and public presentation.

### 8.5 Idempotency

API must persist callback event receipt before applying state transition.

Recommended table concept:

```text
runner_callback_events(
  id,
  run_id,
  event_id,
  node_id,
  event_type,
  seq,
  event_time,
  received_at,
  request_id,
  payload_json,
  payload_sha256
)

unique(run_id, event_id)
```

Rules:

1. `(run_id, event_id)` is the callback idempotency key.
2. If insert fails because the event already exists, return success with duplicate indication and do not re-apply state transition.
3. `seq` is stored for diagnostics and ordering hints only.
4. Missing or non-monotonic `seq` after schema validation should be logged or exposed in diagnostics, but must not block a valid state transition by itself.
5. API may store bounded `payload_json` for diagnostics because callback body is capped at 8KB.
6. Stored payload must not include `x-runner-token`.
7. Duplicate callbacks should not create duplicate artifacts, duplicate audit events, or duplicate lease releases.
8. `runner_callback_events` rows are retained for at most 30 days; api-worker periodically deletes rows older than the retention window.

### 8.6 Out-of-Order Callbacks

Out-of-order callbacks are expected and must be handled by state conditions.

Rules:

1. Always evaluate current DB state plus event type.
2. Do not sort or replay callbacks by `eventTime`.
3. Do not try to reconstruct the Run state by replaying all events in P0.
4. If `heartbeat` arrives after terminal state, store/log and ignore state mutation.
5. If `finished` arrives before `running`, do not mark Run finished; keep Run state unchanged and let timeout/self-healing decide.
6. If `failed` arrives after `finished`, keep `finished` and log ignored late event.
7. If `aborted` arrives after `failed`, keep `failed` and log the ignored late event.
8. Terminal protection in §7.3 already covers the case where the Run was previously force-converged to `aborted`.

### 8.7 Runner Callback Retry

Runner should retry callback delivery on transient API failures.

Recommended retry schedule:

```text
1s, 2s, 4s, 8s, 16s
max attempts: 5
```

Rules:

1. Runner logs final callback delivery failure to local `runner.log`.
2. Runner does not implement a persistent disk callback queue in P0.
3. API heartbeat timeout and worker self-healing are the source of convergence when callback delivery is lost.
4. Runner callback client must use short request timeouts and must not block process cleanup indefinitely.
5. Retry must not include secrets in logs.

---

## 9. Run Creation and Startup Boundary

### 9.1 Atomic Persistence

Run creation must atomically persist:

1. Run row with `state = initializing`;
2. Run Snapshot;
3. selected single Load Node reference;
4. active node lease;
5. execution bundle metadata needed by subsequent SSH/SFTP startup;
6. actor and Workspace context.

Rules:

1. This DB transaction must not execute SSH, SFTP, remote command, MinIO large upload, or long-running work.
2. If transaction fails, no remote runner should be started.
3. If remote startup fails after transaction commits, the Run must converge to `failed` and the node must be released or quarantined depending on cleanup result.
4. Manual single-node selection must be enforced server-side.

### 9.2 Remote Startup

After DB commit, API or a bounded internal job may perform:

1. prepare remote run directory;
2. upload runner package or verify runner availability;
3. upload execution bundle;
4. upload needed dependency files;
5. execute `python runner.py start --run-id <runId>` with the required bundle arguments.

Rules:

1. Remote startup must use credentials stored and protected by Load Node rules.
2. Startup logs must not include SSH password, private key, runner token, MinIO credential, or env secret.
3. If startup command cannot be executed, mark Run `failed` with reason `runner_start_failed`.
4. If startup command executes but no `accepted` callback arrives within 120 seconds, api-worker marks Run `failed` with reason `runner_accept_timeout` and performs cleanup.

### 9.3 Accepted Wait Window

The accepted wait window starts when SurgePilot has requested remote runner start.

```text
accepted timeout = 120 seconds
```

Rules:

1. If `accepted` is not received within the window, Run moves to `failed`.
2. The node must not be made available until cleanup is completed.
3. Cleanup uses the shared post-terminal force-kill subroutine of §12.4 against the Run's `workload.pid` when present. If accepted timeout happens before `workload.pid` is created, cleanup may inspect managed `supervisor.pid` / `workload.pid` files under `RUNNER_HOME/runs` only to decide whether the node is clean or suspicious; it must not kill by generic process name.
4. If startup never reached Runner and no managed pidfile or process can exist, cleanup may be a no-op, but node state must still be decided explicitly.

---

## 10. Runner Process Model

### 10.1 Run Directory

Runner should use one run directory per Run.

Concept:

```text
RUNNER_HOME/
  runs/
    <runId>/
      supervisor.pid
      workload.pid
      logs/
        runner.log
      artifacts/
      bundle/
```

Rules:

1. Path layout details may be refined in Slice SDD.
2. Runner must never accept arbitrary absolute paths from API bundle.
3. Artifact relative paths must be validated before upload.
4. Runner log must not include secrets.
5. P0 does not require remote automatic cleanup after every Run.

### 10.2 Detached Process Group

`runner.py start` must spawn a supervisor process for callbacks and must spawn the actual Taurus/JMeter workload in a separate process group.

Rules:

1. On POSIX systems, use `os.setsid`, `start_new_session=True`, or equivalent for the workload.
2. `start` performs managed pidfile/process classification before spawning the supervisor. It automatically removes stale `supervisor.pid` / `workload.pid`, deletes corrupt `supervisor.pid`, archives corrupt `workload.pid` in P0, and refuses to start only when a live managed supervisor or workload is detected.
3. `supervisor.pid` identifies the supervisor and is used by `stop` and start-time stale detection.
4. `workload.pid` identifies the workload PGID and stores the Linux `/proc/<pid>/stat` starttime for PGID reuse protection before force kill.
5. `managed_run` starts Taurus/JMeter with an independent workload process group, writes `workload.pid`, and uses `os.killpg(workload_pgid, signal)` or equivalent for workload cleanup.
6. Terminal callbacks (`finished`, `failed`, `aborted`) must compute `details.processGroupExited` by checking whether the workload PGID has any non-zombie members; Taurus main-process exit alone is not sufficient.
7. Do not kill by broad process name such as `java`, `jmeter`, `bzt`, or `python`.

### 10.3 Stop Command

```bash
python runner.py stop --run-id <runId>
```

Rules:

1. Stop is graceful cancellation requested by the user.
2. Stop must be idempotent.
3. If `supervisor.pid` is missing and no other managed process exists, return success and send/allow `aborted` convergence when possible.
4. Stop sends `SIGTERM` to the supervisor process group and waits long enough for the supervisor to run its workload cleanup, artifact upload, and terminal callback path (default 120 seconds).
5. Stop must not delete `supervisor.pid` or `workload.pid` itself and must not escalate to direct workload cleanup; if the supervisor does not exit before the timeout, Stop returns non-zero so API cleanup can converge through force kill/quarantine.
6. The supervisor handles SIGTERM by terminating the workload PGID with SIGTERM, waiting, and escalating to SIGKILL if needed.
7. If the supervisor has already exited and `workload.pid` still identifies a live workload, Stop may not be able to send an `aborted` callback; the recovery path is the shared force-kill command against `workload.pid`.
8. Stop should cause the Runner to send `aborted` callback when possible.
9. Stop must not delete artifacts that are useful for Run Report.

### 10.4 Kill Command

```bash
python runner.py kill --run-id <runId>
```

Rules:

1. Kill is force cleanup requested after heartbeat timeout, accepted timeout, stop grace timeout, or a Runner terminal callback with `processGroupExited=false`.
2. Kill must be idempotent.
3. Kill reads `workload.pid` for the Run by default and targets only that workload PGID.
4. Before signalling, Kill validates the recorded starttime against `/proc/<pid>/stat` when that leader `/proc` entry exists; mismatch or an unparseable pidfile is suspicious and must return non-zero while preserving the pidfile. If the leader has already exited but the PGID still has non-zombie members, Kill may still signal that existing workload PGID because it has not been reused.
5. Kill sends `SIGTERM` to the workload process group.
6. Kill waits up to 10 seconds.
7. Kill sends `SIGKILL` if the process group is still alive.
8. Kill returns success only when no managed workload process remains; only then may it delete `workload.pid`.
9. Kill does not guarantee a terminal callback; it guarantees only the local workload cleanup result.
10. Kill should not require the detached runner process to be healthy.
11. Kill must not kill unmanaged processes outside the Run's process group.
12. Kill command output must be safe for audit preview and logs.

### 10.5 Stale Process Detection on Start

`runner.py start` must begin with predecessor residue self-check.

Rules:

1. Check whether a managed pidfile exists in the `RUNNER_HOME`.
2. If a pidfile exists, check whether the referenced process or process group is still alive.
3. Check only SurgePilot-managed pidfiles under the `RUNNER_HOME`; do not scan the whole machine for generic `java`, `jmeter`, `bzt`, or `python` processes.
4. If a live managed supervisor or workload process is detected, refuse to start the new Run.
5. Stale pidfiles are automatically removed before start. A stale workload pidfile with a missing leader still blocks start when `/proc` scanning finds same-PGID non-zombie members.
6. A corrupt `supervisor.pid` is deleted before start. A corrupt `workload.pid` is archived as `workload.pid.corrupt.<timestamp>` and start is allowed in P0; atomic pidfile writes make this rare, and P0 accepts the theoretical single-node risk to avoid manual cleanup loops.
7. If the callback client is available, Runner must send a `failed` callback with reason `stale_process_detected` and `processGroupExited=false`; API then applies the normal `failed` transition and marks the node `quarantined`.
8. The accepted wait timeout is only the fallback path when Runner cannot send any callback.
9. Admin must complete the quarantine recovery workflow in §13.1 before the node can be selected again.

Rationale: this prevents the sequence where force kill fails, the node becomes selectable too early, and a user retry creates overlapping load that pollutes test results.

---

## 11. Stop Protocol

### 11.1 Public API Behavior

The public business endpoint is:

```http
POST /api/v1/runs/{runId}/stop
```

Rules:

1. Stop endpoint requires session auth.
2. Stop endpoint requires CSRF token.
3. Stop endpoint requires Workspace resolution and Run access check.
4. Stop can be requested only for `initializing` or `running`.
5. First accepted Stop transitions Run to `stopping`, records `stopRequestedBy` and `stopRequestedAt`, and returns `202 Accepted`.
6. Repeated Stop while `stopping` returns idempotent success and must not enqueue multiple remote stop attempts.
7. Stop on terminal Run returns `409 RUN_TERMINAL_STATE`.
8. Stop must not rely on frontend hiding the button.

### 11.2 Remote Stop Execution

After Run enters `stopping`, SurgePilot must request remote stop.

Recommended implementation:

```text
API transaction:
  update Run initializing/running -> stopping
  create or mark one stop request job/flag
  commit
  return 202

api-worker:
  claim stop request
  SSH to node
  execute python runner.py stop --run-id <runId>
  record result
```

Rules:

1. Remote stop must be attempted at most once at a time per Run.
2. Repeated Stop requests must not create parallel SSH stop attempts.
3. SSH command execution should be bounded by implementation-level timeout.
4. If remote stop command fails, do not immediately mark node Idle.
5. Stop convergence is determined by `aborted` callback or stop grace timeout.

### 11.3 Stop Grace Timeout

```text
stop grace period = 60 seconds
```

If no `aborted` callback arrives within 60 seconds after `stopRequestedAt`, api-worker must force convergence.

Rules:

1. Conditionally update Run from `stopping` to `aborted`.
2. Set `forcedConvergence = true`.
3. Set terminal reason to `stop_grace_timeout`.
4. Keep node unavailable while remote force kill is attempted.
5. Execute `python runner.py kill --run-id <runId>`.
6. Wait up to 30 seconds for SSH command completion.
7. Write `audit_events` entry `run.force_kill`.
8. If kill succeeds, set `last_force_kill_at = now()`, release node lease, and set node state to `idle`. The 5-minute cooldown is enforced at Run selection time per §13.2 Rule 6, not as a node-state transition.
9. If kill fails or times out, release node lease and set node state to `quarantined`.
10. Run remains `aborted` even if cleanup fails; cleanup failure affects node state and audit, not user cancellation semantics.

---

## 12. Heartbeat and Timeout Self-Healing

### 12.1 Heartbeat

Runner sends heartbeat every 15 seconds while active.

Rules:

1. Heartbeat updates `lastHeartbeatAt`.
2. Heartbeat does not change Run state.
3. Heartbeat from unknown Run or mismatched node must be rejected or ignored according to Slice SDD, and logged.
4. Heartbeat after terminal state is stored/logged and ignored for state mutation.
5. Heartbeat payload must stay small and must not include logs or large previews.

### 12.2 Heartbeat Timeout

```text
heartbeat timeout = 60 seconds
api-worker scan interval = 10 seconds
```

Timeout applies to active non-terminal Run states where heartbeat is expected. For `stopping`, stop grace is the primary convergence rule.

When api-worker detects heartbeat timeout:

1. Conditionally update Run to `failed` if it is still `initializing` or `running`.
2. Set reason to `heartbeat_timeout`.
3. Keep node lease active while cleanup is pending.
4. Execute remote force kill:

```bash
python runner.py kill --run-id <runId>
```

5. Wait for SSH completion with hard timeout of 30 seconds.
6. Write `audit_events` entry `run.force_kill` with safe details.
7. If force kill succeeds:
   - set `last_force_kill_at = now()`;
   - release node lease;
   - set node state to `idle`.
   The 5-minute cooldown is enforced at Run selection time per §13.2 Rule 6, not as a node-state transition.
8. If force kill fails or times out:
   - release node lease;
   - set node state to `quarantined`;
   - require the §13.1 quarantine recovery workflow before reuse.

Rules:

1. Do not release the node as Idle before force kill succeeds.
2. Do not start another Run on the node while cleanup is pending.
3. Do not run unbounded SSH cleanup loops.
4. If api-worker crashes after marking Run terminal but before releasing the node lease, stale lease recovery must retry cleanup or keep node unavailable.
5. Cleanup failure must be visible in structured logs and audit, but must not resurrect the Run.

### 12.3 Force Kill Audit Event

P0 audit event type:

```text
run.force_kill
```

Recommended safe details:

```json
{
  "runId": "01J00000000000000000000002",
  "nodeId": "01J00000000000000000000003",
  "reason": "heartbeat_timeout",
  "success": false,
  "exitCode": null,
  "stderrPreview": "SSH command timed out.",
  "timedOut": true
}
```

Rules:

1. `stderrPreview` must be bounded and sanitized.
2. Do not store SSH credential, runner token, env secret, server absolute private key path, or MinIO credential.
3. Audit details must help operators understand why node entered quarantine.
4. Full raw logs stay in server logs or node init logs according to logging policy, not audit details.


### 12.4 Shared Post-Terminal Force-Kill Subroutine

All remote cleanup paths must share one implementation. The implementation accepts the Run, node, reason, target terminal state if not already terminal, and SSH timeout.

Callers:

| Caller | Target Run state | Reason | SSH hard timeout |
| --- | --- | --- | --- |
| accepted wait timeout | `failed` | `runner_accept_timeout` | 30 seconds |
| heartbeat timeout | `failed` | `heartbeat_timeout` | 30 seconds |
| stop grace timeout | `aborted` | `stop_grace_timeout` | 30 seconds |
| terminal callback with `processGroupExited=false` | already set by callback | preserve callback reason | 10 seconds |

Rules:

1. The shared implementation executes:

```bash
python runner.py kill --run-id <runId>
```

2. The command targets `workload.pid` for the Run. It validates starttime when the workload leader `/proc` entry exists and preserves the pidfile on mismatch, malformed state, timeout, or cleanup failure.
3. Workload process-group termination behavior is always `SIGTERM`, wait 10 seconds, then `SIGKILL`.
4. If kill succeeds:
   - set `last_force_kill_at = now()`;
   - release node lease;
   - set node state to `idle`;
   - rely on §13.2 selection-time cooldown before the node can be selected again.
5. If kill fails, times out, or the pidfile state is inconsistent:
   - release node lease;
   - set node state to `quarantined`;
   - require the §13.1 quarantine recovery workflow before reuse.
6. The audit event shape is `run.force_kill`.
7. Stale lease recovery must reuse this same cleanup behavior.
8. `stale_process_detected` must leave the node `quarantined` and require the §13.1 quarantine recovery workflow; it must not automatically return the node to Idle just because a best-effort kill later succeeds.
9. Sections §11.3 and §12.2 describe this same subroutine inline for readability. Any change to the subroutine must be reflected in all three places. Slice SDD implementations must call one shared function rather than re-implementing the steps.

Rationale: one shared subroutine avoids multiple subtly different cleanup implementations, while the 10-second terminal-callback sanity path avoids returning a node to the pool when a Runner-reported terminal event did not prove process group cleanup.

---

## 13. Node Lease and Node State

### 13.1 Lease Purpose

Node lease prevents two Runs from using the same Load Node at the same time.

Recommended table concept:

```text
node_leases(
  id,
  node_id,
  run_id,
  acquired_at,
  released_at
)

unique(node_id) where released_at is null
```

Rules:

1. P0 Run uses exactly one selected Load Node.
2. Acquiring node lease and creating Run must happen in the same DB transaction.
3. Active lease is represented by `released_at IS NULL`.
4. A partial unique index on `(node_id) WHERE released_at IS NULL` is enough in P0.
5. PostgreSQL advisory lock is not required for object-level node lease if the unique index and transaction are correct.
6. Load Node selection must require both:
   - node state is selectable, usually `idle`;
   - no active node lease exists.

### 13.2 Node States Required by This Document

P0 Load Node Slice may define the full list. This document requires at least:

| State | Meaning | Selectable for new Run |
| --- | --- | --- |
| `uninitialized` | Node is registered but not initialized | no |
| `idle` | Node is initialized and available | yes |
| `busy` | Node is currently leased or executing | no |
| `offline` | Node is unreachable or health check failed | no |
| `disabled` | Admin disabled the node | no |
| `quarantined` | SurgePilot detected possible unmanaged process or unknown runner state | no |

Rules:

1. `quarantined` is required by heartbeat timeout and stale process defense.
2. Quarantined node must not be selectable for new Runs.
3. Admin must manually confirm and clean residual SurgePilot-managed processes and the Run Monitoring secret before changing a quarantined node.
4. After that confirmation, Admin must disable the node, enable it back to `uninitialized`, and request initialization before it can return to `idle`; direct `quarantined -> initializing` is not allowed.
5. Node state and lease are both checked; releasing lease alone does not make a node selectable.
6. Load Node selection must also satisfy `(last_force_kill_at IS NULL OR last_force_kill_at < now() - cooldown)`.
7. Cooldown is a selectability filter, not a node-state transition; do not introduce a `cooling_down` state in P0.
8. P0 default cooldown is 5 minutes; implementation may expose `SURGEPILOT_NODE_COOLDOWN_SECONDS` but must not add a System Settings UI for this in P0.
9. `quarantined` is a node state, not a Run `failure_reason`.

### 13.3 Lease Release

Terminal callback path with `processGroupExited=true`:

1. Insert callback event idempotently.
2. Conditionally transition Run to terminal.
3. In the same DB transaction:
   - set `runs.ended_at`;
   - release active node lease;
   - set node state to `idle` unless the node has been disabled/offline/quarantined by another rule.

Terminal callback path with `processGroupExited=false`:

1. Insert callback event idempotently.
2. Conditionally transition Run to terminal.
3. Keep node lease active and node unavailable.
4. Trigger the shared post-terminal force-kill subroutine in §12.4.
5. Release or quarantine the node only after cleanup result is known.

Timeout / forced cleanup path:

1. Transition Run to terminal.
2. Keep node unavailable while force kill runs.
3. Release active node lease only after force kill result is known.
4. Set node to `idle` only if cleanup succeeds.
5. Set node to `quarantined` if cleanup fails or times out.

### 13.4 Stale Lease Recovery

api-worker must scan for stale leases.

Rules:

1. If Run is terminal and lease remains active because worker crashed mid-cleanup, retry cleanup or keep node unavailable.
2. If Run is terminal and cleanup is known complete, release lease.
3. If active lease has no corresponding Run or inconsistent Run state, mark node `quarantined` and require operator recovery.
4. P0 recommended stale cleanup threshold for terminal Run with unreleased lease is 2 hours unless Slice SDD chooses a stricter threshold.
5. Stale lease recovery must use PostgreSQL coordination to avoid duplicate global scans if multiple workers are ever started.

---

## 14. Artifact Ingest Boundary

### 14.1 Artifact Upload Endpoint

```http
POST /api/internal/v1/runner/artifacts
x-runner-token: <runner token>
Content-Type: multipart/form-data
```

The Runner uploads one artifact per request.

Required multipart fields should include:

| Field | Required | Rule |
| --- | --- | --- |
| `schemaVersion` | yes | `"1"` |
| `eventId` | yes | ULID idempotency key for this upload |
| `runId` | yes | ULID |
| `nodeId` | yes | ULID |
| `artifactType` | yes | Accepted whitelist (`debug_http_trace` is P1-only and only active under `P1-08-debug-http-trace`) |
| `relativePath` | yes | Safe relative path under current Run directory |
| `sha256` | yes | Hex SHA-256 of uploaded file |
| `sizeBytes` | yes | Must match uploaded file |
| `file` | yes | Single file |

Rules:

1. Runner does not hold MinIO credentials.
2. API writes uploaded file to MinIO.
3. API creates artifact metadata.
4. API returns an `artifactId` and does not need to return MinIO object key.
5. Duplicate `(run_id, event_id)` upload returns the existing `artifactId` without duplicating storage or metadata.
6. Single artifact file size limit is 200MB in P0.
7. API must validate that the `runId` in multipart fields belongs to the Runner identity bound to `x-runner-token`; mismatch returns `403 RUNNER_FORBIDDEN`.
8. After a Run is terminal, API may accept small diagnostic artifacts only within 5 minutes of `endedAt` and only when `sizeBytes < 1MB`. This terminal-late acceptance is for diagnostics only and does not affect Run state. P1 `debug_http_trace` must be uploaded before terminal callback when present and must not rely on this terminal-late path.
9. Terminal late artifacts outside that window are rejected with `409 RUN_TERMINAL_STATE`.
10. Slice SDD may tune thresholds but must not change the semantic rule: terminal late artifact acceptance is bounded and diagnostic-only.
11. API must validate `relativePath`; full path normalization rules belong to 07.

### 14.2 Artifact Type Whitelist

P0 accepted artifact types:

```text
taurus_log
jmeter_log
final_stats_csv
run_log
artifacts_zip
```

P1 `P1-08-debug-http-trace` additionally accepts:

```text
debug_http_trace
```

Rules:

1. Unknown artifact type is rejected. `debug_http_trace` is accepted only as a P1 Slice artifact type and does not authorize any other P1/P2 artifact type.
2. Runner should upload raw Taurus/JMeter outputs where practical.
3. API / api-worker may parse CSV artifacts into report summary tables.
4. Runner is not required to convert `finalstats.csv` into JSON in P0.
5. 07 or P0-07 may add preview/report-derived metadata, but must not make Runner hold MinIO credentials.
6. `failed_requests_csv` depends on a JMeter plugin output contract and remains separate from `debug_http_trace`.
7. `debug_http_trace` must be uploaded before terminal callback when present; it is not a terminal-late diagnostics artifact.

### 14.3 Artifact Callback Event

After a successful upload, Runner should send an `artifact` callback:

```json
{
  "schemaVersion": "1",
  "eventId": "01J00000000000000000000004",
  "runId": "01J00000000000000000000002",
  "nodeId": "01J00000000000000000000003",
  "eventType": "artifact",
  "seq": 5,
  "eventTime": "2030-05-20T04:00:10.000Z",
  "message": "Artifact uploaded.",
  "details": {
    "artifactId": "01J00000000000000000000005",
    "artifactType": "final_stats_csv",
    "relativePath": "artifacts/finalstats.csv",
    "sizeBytes": 2048,
    "sha256": "..."
  }
}
```

Rules:

1. Artifact upload success is the source of file persistence.
2. Artifact callback is useful for Run timeline, diagnostics, and UI refresh.
3. Missing artifact callback after successful upload must not lose the artifact metadata.
4. Artifact callback must not change Run state.
5. Artifact callback must not contain MinIO object key.

### 14.4 Terminal and Artifact Failure

Rules:

1. Artifact upload failure must not leave Run permanently `running` or `stopping`.
2. If critical final artifacts are missing, Run may still become terminal and Run Report should show warning.
3. Artifact summary parsing failures belong to report summary jobs, not Run state machine, unless the Slice SDD explicitly defines a fatal artifact requirement.
4. Large previews must be artifacts or report summary rows, not callback payload.

---

## 15. Error Reasons and Safe Messages

### 15.1 Stable Reason Values

Recommended P0 reason values:

```text
runner_start_failed
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

1. Reasons use lower snake case.
2. Reasons are not necessarily public API error codes.
3. Public API error codes still follow 04.
4. User-facing messages must be safe and understandable.
5. Low-level stderr, stack traces, credentials, tokens and server paths must not be returned to Web.

### 15.2 Failed vs Aborted

Rules:

1. Use `failed` for system, runner, node, startup, heartbeat, bundle, upload, or test execution errors.
2. Use `aborted` when user Stop was requested and SurgePilot converged cancellation, even if forced convergence was needed.
3. Stop grace timeout should set `aborted` with `forcedConvergence=true` and reason `stop_grace_timeout`.
4. Heartbeat timeout without user Stop should set `failed` with reason `heartbeat_timeout`.

---

## 16. Minimal Data Requirements

This section defines required concepts, not complete migrations.

### 16.1 `runs`

Run storage must support at least:

| Field concept | Purpose |
| --- | --- |
| `id` | ULID |
| `workspace_id` | Workspace boundary |
| `state` | Run state lower snake case |
| `run_type` | Standard / Debug, defined by Slice |
| `validity` | Valid / Invalid, defined by Report Slice |
| `triggered_by_user_id` | Actor |
| `node_id` | Selected Load Node |
| `accepted_at` | API received time for accepted event |
| `started_at` | API received time for running event |
| `ended_at` | Terminal time |
| `last_heartbeat_at` | API received time for latest heartbeat |
| `stop_requested_at` | Stop request time |
| `stop_requested_by_user_id` | Stop requester |
| `failure_reason` | Stable reason for failed/aborted diagnostics |
| `failure_message` | Safe bounded message |
| `forced_convergence` | Whether worker forced terminal convergence |
| `runner_pid` | Required after accepted callback; process ID reported by Runner |
| `created_at`, `updated_at` | UTC timestamps |

Rules:

1. Field names in DB use `snake_case`.
2. API JSON uses `camelCase`.
3. Exact field list, constraints and migration files belong to Slice SDD.
4. Do not add unused P1/P2 scheduling, multi-node or distributed queue fields in P0.

### 16.2 `runner_callback_events`

See §8.5.

### 16.3 `node_leases`

See §13.1.

### 16.4 Artifact Metadata

Artifact metadata must include enough to support Run Report and safe download:

| Field concept | Purpose |
| --- | --- |
| `id` | Artifact ID |
| `workspace_id` | Workspace boundary |
| `run_id` | Run owner |
| `node_id` | Source node |
| `artifact_type` | P0 whitelist |
| `relative_path` | Display/source relative path |
| `size_bytes` | Size |
| `sha256` | Integrity |
| `content_type` | Safe content type |
| `storage_key` | Server-only MinIO key |
| `created_at` | Upload time |

Rules:

1. Web must not receive `storage_key`.
2. Object key details belong to 07.
3. Artifact metadata is Workspace-aware.

---

## 17. Fake Runner

Fake runner is allowed and required for efficient P0 development.

Rules:

1. Fake runner lives under `apps/runner`.
2. Fake runner must share the same callback client module as real Runner.
3. Fake runner must use the same callback schema.
4. Fake runner must not implement a second, incompatible callback protocol.
5. Fake mode may be enabled by `python runner.py start --fake` or an equivalent CLI flag.
6. Test scenarios should be text-driven, for example YAML scripts, but exact file names belong to Slice SDD.
7. Fake runner may be used for Web/API smoke, Run List / Run Report local development, and contract tests.
8. Fake runner must not spawn real Taurus/JMeter, must not require reachable SSH, and must be able to run in CI without external network access.
9. In CI and unit tests, fake runner may be invoked in-process by the test harness importing the runner package, bypassing SSH entirely. The `--fake` CLI flag covers local development where developers still want to run `runner.py` as a separate process.
10. Fake runner cannot replace real or near-real Runner acceptance for process group, stop, kill, SSH/SFTP startup, Taurus/JMeter execution, and artifact ingestion.

Minimum P0 fake scenarios:

1. accepted -> running -> heartbeat -> artifact -> finished;
2. accepted -> running -> failed;
3. accepted -> running -> stop -> aborted;
4. accepted -> running -> heartbeat timeout;
5. accepted -> running -> artifact upload failure warning;
6. late callback after terminal is ignored.

---

## 18. Security and Logging

### 18.1 Runner Token

Rules:

1. Internal runner endpoints require `x-runner-token`.
2. Runner token comes from environment/configuration.
3. Runner token must not appear in Web response, public OpenAPI examples, logs, audit details, test snapshots, artifacts, or frontend bundle.
4. Invalid runner token returns `RUNNER_UNAUTHORIZED`.

### 18.2 Audit Events

P0 must audit execution-control events where they affect state or safety.

Required event types introduced by this document:

```text
run.stop_requested
run.force_kill
load_node.quarantined
```

Recommended event details are safe, bounded, and secret-free.

Rules:

1. Stop request audit should include actor, Run ID, node ID and Workspace ID.
2. Force kill audit should include reason, success, timeout flag and bounded stderr preview.
3. Node quarantine audit should include reason and operator recovery hint.
4. `load_node.quarantined` is a node-scoped audit event; correlate it to the triggering Run through `details.runId`.
5. Audit must not include credentials, runner token, MinIO credentials, private key path, full env, full stderr, or full logs.

### 18.3 Structured Logs

Required log cases:

1. Run state transition applied;
2. Run state transition ignored and reason;
3. duplicate callback ignored;
4. late callback ignored after terminal;
5. Stop requested;
6. remote stop attempt result;
7. heartbeat timeout detected;
8. force kill attempt result;
9. node entered quarantine;
10. stale pidfile/process detected;
11. artifact upload accepted/rejected.

Logs must include when available:

```text
requestId
runId
nodeId
workspaceId
eventId
eventType
stateBefore
stateAfter
reason
durationMs
```

Logs must not include secrets.

---

## 19. API and Contract Boundary Summary

### 19.1 Public Business APIs

Public business APIs remain under:

```text
/api/v1/...
```

This document only requires:

```http
POST /api/v1/runs/{runId}/stop
```

Other Run creation/list/detail/report endpoints are defined by Slice SDD.

### 19.2 Internal Runner APIs

Internal runner APIs are:

```http
POST /api/internal/v1/runner/callbacks
POST /api/internal/v1/runner/artifacts
```

Rules:

1. Excluded from Web generated client.
2. Protected by `x-runner-token`.
3. No browser session.
4. No CSRF.
5. Schema and examples use `camelCase`.
6. Error responses follow 04.

### 19.3 Contract Files

Required contract files:

```text
packages/contracts/runner/runner-callback.schema.json
```

Recommended additional contract file if artifact upload schema needs independent validation:

```text
packages/contracts/runner/runner-artifact-upload.schema.json
```

Rules:

1. Do not hand-write Web API types.
2. Do not let Runner and API drift by copying payload definitions into two unrelated places.
3. Contract tests must validate accepted and rejected callback payloads.

---

## 20. Testing Requirements

### 20.1 API Unit / Service Tests

Must cover:

1. every legal state transition;
2. every illegal transition ignored or rejected correctly;
3. terminal state cannot be overwritten;
4. `accepted` does not move Run to `running`;
5. `heartbeat` updates `lastHeartbeatAt` only;
6. `artifact` does not change state;
7. `finished` accepted only from `running`;
8. `failed` from non-terminal moves to `failed`;
9. `aborted` from active states moves to `aborted`;
10. Stop from `initializing` / `running` moves to `stopping`;
11. duplicate Stop while `stopping` is idempotent;
12. Stop on terminal returns `RUN_TERMINAL_STATE`;
13. duplicate callback by `eventId` is idempotent;
14. out-of-order callback does not corrupt state;
15. terminal callback with `processGroupExited=true` releases the lease transactionally;
16. terminal callback with `processGroupExited=false` keeps node unavailable and triggers cleanup;
17. timeout terminal transition keeps node unavailable until cleanup result.

### 20.2 api-worker Tests

Must cover:

1. accepted wait timeout -> `failed`;
2. heartbeat timeout -> `failed`;
3. heartbeat timeout triggers remote kill;
4. kill success -> lease released and node `idle`;
5. kill failure/timeout -> lease released and node `quarantined`;
6. stop grace timeout -> `aborted` with `forcedConvergence=true`;
7. stop grace timeout triggers remote kill;
8. worker crash/retry does not release node as Idle without cleanup;
9. stale lease recovery;
10. terminal-callback sanity cleanup when `processGroupExited=false`;
11. global scan coordination if multiple workers are started.

### 20.3 Runner Unit Tests

Must cover:

1. callback client sends required fields;
2. callback retry backoff;
3. process group creation;
4. pidfile write/read;
5. stop idempotency;
6. kill idempotency;
7. SIGTERM then SIGKILL escalation;
8. stale pidfile/process detection;
9. safe artifact relative path handling;
10. runner logs do not include token/credential values.

### 20.4 Contract Tests

Must cover:

1. valid callback schema examples for all event types;
2. unknown `schemaVersion` rejected;
3. missing `eventId` rejected;
4. missing `seq` rejected;
5. invalid `eventType` rejected;
6. oversized callback rejected;
7. callback schema examples use `camelCase`;
8. internal runner endpoints excluded from Web generated client;
9. artifact upload rejects unknown artifact type;
10. artifact upload enforces max file size.

### 20.5 E2E / Smoke Tests

P0 smoke should cover at least:

1. fake runner success flow;
2. fake runner failed flow;
3. Stop flow converges to `aborted`;
4. heartbeat timeout flow converges to `failed`;
5. force kill failure quarantines node;
6. stale process detection quarantines node;
7. artifact appears in Run Report after upload;
8. late callback after terminal does not change visible terminal state.

---

## 21. Review Checklist

Before accepting a Slice or PR touching Run / Runner:

### 21.1 Scope

- [ ] Does the change preserve the P0 stability baseline and stay within the active accepted Slice?
- [ ] Does it avoid resource queue, auto allocation and multi-node execution?
- [ ] Does it avoid Monitoring, Schedule Run and API Catalog?
- [ ] Does it avoid Redis, Celery, RabbitMQ, Kafka and Kubernetes?

### 21.2 State Machine

- [ ] Are Run states limited to the six P0 states?
- [ ] Are enum values lower snake case?
- [ ] Does `accepted` avoid moving to `running`?
- [ ] Do `heartbeat` and `artifact` avoid state mutation?
- [ ] Are terminal states protected?
- [ ] Are transitions implemented with conditional updates?

### 21.3 Callback Contract

- [ ] Does callback use `schemaVersion: "1"`?
- [ ] Does callback require `eventId`?
- [ ] Does dedup use `(run_id, event_id)`?
- [ ] Is `seq` diagnostic only?
- [ ] Is API `receivedAt` authoritative?
- [ ] Are duplicate callbacks successful no-ops?
- [ ] Are late callbacks logged with reason?

### 21.4 Stop and Timeout

- [ ] Stop from active states enters `stopping`.
- [ ] Repeated Stop in `stopping` is idempotent.
- [ ] Stop on terminal is handled consistently.
- [ ] Stop grace timeout force-converges to `aborted`.
- [ ] Heartbeat timeout force-converges to `failed`.
- [ ] Timeout cleanup executes `runner.py kill`.
- [ ] Node is not returned to Idle unless kill succeeds.
- [ ] Kill failure/timeout quarantines node.
- [ ] Cooldown is enforced at selection time without adding a `cooling_down` state.

### 21.5 Node Lease

- [ ] Run creation atomically creates node lease.
- [ ] Partial unique active lease prevents double allocation.
- [ ] Load Node selection checks both node state and active lease.
- [ ] Terminal callback releases lease transactionally only when `processGroupExited=true`.
- [ ] Timeout cleanup and terminal-callback cleanup keep node unavailable until cleanup result.
- [ ] Stale lease recovery exists.

### 21.6 Runner

- [ ] Runner does not access DB.
- [ ] Runner does not hold MinIO credentials.
- [ ] Runner does not import API internal code.
- [ ] Runner uses process group.
- [ ] `stop` and `kill` are idempotent.
- [ ] `start` detects stale managed pidfile/process.

### 21.7 Artifacts

- [ ] Runner uploads artifacts through API.
- [ ] Artifact type is P0-whitelisted.
- [ ] Artifact upload is idempotent.
- [ ] Artifact callback does not change Run state.
- [ ] MinIO object key is not returned to Web.
- [ ] Path safety details align with 07.

### 21.8 Security and Logs

- [ ] Runner token is not logged.
- [ ] SSH credential is not logged.
- [ ] Audit details are bounded and secret-free.
- [ ] Force kill and `load_node.quarantined` are audited.
- [ ] Error messages are safe English fallback.

---

## 22. Done When for This Foundation Document

This Foundation SDD is ready for implementation planning when:

1. Run states, terminal semantics and legal transitions are clear.
2. Callback event mapping is unambiguous.
3. Callback schema has `schemaVersion`, `eventId`, `seq`, `eventTime`, `runId`, `nodeId`, and `eventType`.
4. Callback idempotency uses `eventId`, not `seq`.
5. Stop and heartbeat timeout convergence are defined.
6. Remote force kill and node quarantine are defined.
7. Node lease acquisition and release rules are defined.
8. Artifact upload through API is defined without exposing MinIO credentials to Runner.
9. Fake runner boundaries are defined.
10. Tests and review checklist are sufficient for AI Coding.
11. Cross-document updates listed in §2.3 are filed as issues or PRs so that 04 / 06 / 07 and Slice SDDs do not lag behind 05.

---

## 23. Known Risks


1. SSH force kill and late terminal callbacks can race. A Runner may send `finished` after api-worker has already marked the Run `failed` due to heartbeat timeout. This document mitigates the race through conditional terminal updates: late callbacks are stored/logged but must not overwrite terminal state. Runner terminal callbacks must also prove cleanup through `processGroupExited=true` before the node lease is released transactionally.
2. Quarantine recovery depends on Admin-confirmed residual cleanup followed by disable → enable → initialize in P0. This is intentional. Automatic quarantine recovery would become a resource health automation feature and is deferred beyond P0 unless a later SDD explicitly accepts it.
3. Post force-kill cooldown may temporarily reduce available capacity on a single-node deployment. This is accepted because avoiding overlapping load and polluted reports is more important than immediate reuse after an abnormal cleanup.
