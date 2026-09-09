# 05. Runner Protocol and Run State Machine

## Component responsibilities

API owns Run state, snapshots, node leases, Workspace checks, callback deduplication, artifact metadata, and terminal convergence. api-worker owns timeout scans and bounded compensation. Runner owns remote Taurus/JMeter process control, callbacks, heartbeat, Stop/kill commands, and artifact transfer to API. Runner does not access PostgreSQL, MinIO, browser sessions, or API internals.

## States

| State | Meaning | Terminal |
| --- | --- | --- |
| `initializing` | Snapshot and lease exist; remote start is pending or accepted | no |
| `running` | Load execution has started | no |
| `stopping` | Stop was requested and cancellation is converging | no |
| `finished` | Execution completed successfully at the process level | yes |
| `failed` | Startup, infrastructure, runner, timeout, or test execution failed | yes |
| `aborted` | User-requested Stop converged to cancellation | yes |

SLA failure does not make the lifecycle state `failed`; a completed Run may be `finished` with a failed SLA verdict.

## Legal transitions

| Current | Trigger | Next |
| --- | --- | --- |
| none | Run created | `initializing` |
| `initializing` | `accepted` | `initializing` |
| `initializing` | `running` | `running` |
| `initializing` | Stop | `stopping` |
| `running` | Stop | `stopping` |
| `initializing` or `running` | `failed` | `failed` |
| `initializing`, `running`, or `stopping` | `aborted` | `aborted` |
| `running` | `finished` | `finished` |
| `running` | heartbeat or artifact | `running` |
| `stopping` | heartbeat or artifact | `stopping` |
| `stopping` | `failed` | `failed` |
| `initializing` | acceptance timeout | `failed` |
| `running` | heartbeat timeout | `failed` |
| `stopping` | Stop grace timeout | `aborted` |
| terminal | any callback | unchanged |

`accepted` records that Runner took responsibility but keeps the Run `initializing`; it does not mean load execution began. Both `initializing -> stopping` and `running -> stopping` are valid. Heartbeat and artifact events never change state. Terminal states cannot be overwritten.

Transitions use conditional database updates against legal predecessors. A zero-row update is treated as an idempotent duplicate, late event, or illegal/out-of-order event and is recorded for diagnosis rather than forcing state backward.

## Callback contract

Runner sends versioned JSON events to `POST /api/internal/v1/runner/callbacks` with `schemaVersion`, `eventId`, `runId`, diagnostic `seq`, `eventType`, and `eventTime`. Event types are `accepted`, `running`, `heartbeat`, `artifact`, `finished`, `failed`, and `aborted`.

API receiving time and current database state are authoritative. `(runId, eventId)` is unique. A duplicate event returns success without replaying effects. Out-of-order events are applied only when legal for the current state. A terminal callback includes whether its process group has exited; the lease is not released until cleanup is known safe.

## Start and Stop races

Run, snapshot, and node lease are committed before SSH/SFTP begins. Stop may arrive while startup is still underway: it moves `initializing` to `stopping`, records user intent, and causes any late `accepted` or `running` callback to be ignored for state transition. Startup code must check current state before and after remote start and invoke Stop/cleanup if cancellation won the race. Repeated Start-side work is allocation-bound and must not create a second remote process.

Stop sends a bounded remote termination request. Runner sends `SIGTERM` to the process group, waits a grace interval, then uses `SIGKILL` if needed. Repeated Stop is safe. If normal `aborted` does not arrive, api-worker force-converges and performs cleanup. Cleanup failure quarantines the node instead of making it Idle.

## Self-healing and leases

Runner emits periodic heartbeats while active. api-worker scans for acceptance timeout, heartbeat timeout, Stop grace timeout, and stale leases using PostgreSQL coordination so multiple workers do not duplicate ownership. A terminal transition and safe lease release are atomic when possible; uncertain process state keeps the node unavailable until bounded kill succeeds or quarantine is recorded.

## Acceptance focus

Tests must cover every legal transition, terminal immutability, duplicate and out-of-order callbacks, `accepted` remaining `initializing`, Stop from both active states, Stop-before-accepted and Stop/start races, concurrent duplicate callbacks, timeout convergence, lease release, cleanup failure quarantine, and fake/real Runner contract parity.

## Artifact ingest boundary

Runner uploads one artifact per request to `POST /api/internal/v1/runner/artifacts` using the bound `x-runner-token`. The API validates the Run/node binding, schema version, event idempotency key, safe relative path, declared size, SHA-256 and artifact type before storing bytes and metadata. The Runner never receives MinIO credentials and the API returns an artifact identifier, not an object key.

The public artifact type whitelist is:

```text
taurus_log
jmeter_log
final_stats_csv
run_log
artifacts_zip
```

P1-08 additionally permits two scoped internal ingest types for the Debug Run sources covered by `docs/sdd/adr/ADR-0008-p1-debug-http-trace.md` and `docs/sdd/slices/P1-08-debug-http-trace.md`: `debug_http_trace` and `debug_http_body_blob`. `debug_http_trace` is the bounded JSONL report input. `debug_http_body_blob` is an internal-only sanitized request/response body sidecar for large text bodies. Neither type enters the public artifact enum, list, filter, or count; `debug_http_trace` is not downloadable through the generic raw artifact endpoint, and body blobs use only the dedicated Run Report download route after API authorization. Unknown types remain rejected; this addition does not authorize other P1/P2 artifact types.

Both P1-08 internal types are pre-terminal artifacts. When present, Runner must upload the trace and any body sidecars before sending the terminal callback. They must not use the terminal-late diagnostics path. Upload or parse failure must not change terminal Run state, verdict, lease cleanup or Stop convergence.

After a Run is terminal, the API may accept only bounded diagnostic artifacts within five minutes of `endedAt` and below the configured 1MB terminal-late limit. Such artifacts are marked terminal-late, do not change Run state, and are rejected with `RUN_TERMINAL_STATE` outside that policy. This terminal-late rule never makes either P1-08 internal type a terminal-late artifact.
