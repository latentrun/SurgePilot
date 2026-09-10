# P1-01 Resource Multi-node

- Document status: Accepted for implementation
- Stage: P1
- Capability:`resource_multi_node`
- Scope ADR:`docs/sdd/adr/ADR-0009-p1-resource-multi-node.md`
- Scope Gate:`docs/sdd/00-product-scope-and-priority.md` §6
- P1 Index:`docs/sdd/slices/P1-README.md`
- API Contract Boundary:`docs/sdd/04-api-contract-guidelines.md`
- Runner Boundary:`docs/sdd/05-runner-protocol-and-run-state-machine.md`
- Security Boundary:`docs/sdd/06-security-permission-workspace.md`
- Artifact Boundary:`docs/sdd/07-storage-artifacts-minio.md`
- Testing Boundary:`docs/sdd/09-testing-and-acceptance-strategy.md`

## 1. Goal

P1-01 freezes the Resource Multi-node design for Standard Test Plan Runs.

The user still sees one logical Run. Internally, the API assigns one allocation per Load Node, starts one node-local Runner execution per allocation, aggregates node status/artifacts/SLA verdicts, and releases or quarantines resources without weakening P0 stability.

This Slice is only about P1 Standard Test Plan Run resource execution. It is not a scheduler platform, Debug Run expansion, Monitoring semantics change, or resource matching system.

## 2. PRD / Scope Trace

`docs/sdd/00-product-scope-and-priority.md` §6 allows P1 Resource Auto allocation, multi-node execution, Node Count, and Selected Nodes. `ADR-0009` accepts the architecture for this Slice.

Locked trace:

1. P1-01 applies only to Standard Test Plan Runs.
2. P0 manual single-node behavior remains valid and must not regress.
3. Debug Run remains single-node; P1-08 Debug HTTP Trace remains single-node and is not changed here.
4. P1 Monitoring does not gain multi-node aggregation semantics from this Slice.
5. If implementation needs Debug multi-node, Monitoring aggregation, queues, labels, resource matching, or distributed JMeter, a new accepted ADR or scope update is required first.

## 3. In Scope

1. Standard Test Plan resource request modes:
   - `manual` with distinct `selectedNodeIds`;
   - `auto` with `nodeCount`;
   - `concurrencyPerNode` or an equivalent normalized per-node load setting.
2. Atomic API allocation for all requested nodes before execution starts.
3. `Run` as the logical execution object plus allocation-level execution state.
4. Multi-node node leases while preserving one active lease per node.
5. Allocation-aware start, stop, force-kill, timeout, cleanup, and stale lease recovery.
6. Runner callback and artifact aggregation by token node equality plus allocation membership.
7. Redacted Run Detail / Run Report resource projection through generated OpenAPI and generated Web client.
8. Node-level and Run-level SLA verdict aggregation for allocated nodes.

## 4. Out of Scope

P1-01 must not introduce:

1. Debug Run multi-node behavior.
2. Monitoring multi-node semantics, Grafana datasource management, or InfluxDB management.
3. Resource queueing, background waiting for capacity, fair-share scheduling, retry allocation, autoscaling, or cloud procurement.
4. Load Node labels, tags, capacity labels, CPU/memory/region matching, or resource matching DSL.
5. Distributed JMeter controller/worker topology.
6. Redis, Celery, RabbitMQ, Kafka, external queues, Kubernetes, or a scheduler service.
7. Global concurrency automatic splitting. Workload is copied to each node and per-node load is explicit.
8. OpenAPI / API Catalog capabilities or Scenario/Test Plan generation from API specs.
9. Editable Taurus YAML.

## 5. Preconditions

1. `ADR-0009` is Accepted.
2. P1-01 is listed in `P1-README.md` as an active Slice SDD.
3. P0-Core and P0-Stability are the baseline: state machine safety, Stop idempotency, heartbeat timeout, permission checks, workspace isolation, path safety, credential safety, and runner boundary rules remain mandatory.
4. Existing Runner callback schema remains the protocol source unless Foundation 05 or a later ADR explicitly changes it.
5. Web work must consume generated client/types from `@surgepilot/contracts` only.

## 6. Locked Core Decisions

1. One user-facing Run remains one logical Run.
2. Multi-node execution is represented by Run-Node allocations, not by creating separate user-facing Runs.
3. Runner stays node-local and does not make global scheduling, lease, or terminal-state decisions.
4. API owns resource validation, allocation, lease lifecycle, callback validation, state aggregation, report projection, and permission enforcement.
5. Allocation is fail-fast and atomic: partial Run creation is not allowed.
6. Stop is one logical user action broadcast to all non-terminal allocations and remains idempotent.
7. Callback idempotency remains Foundation 05 semantics: `(runId, eventId)`, where `eventId` is a globally unique Runner-generated event ID.
8. Multi-node location is determined by `nodeId` plus allocation membership, not by changing the callback idempotency key.
9. Runner token or equivalent runner credential must be node-bound before multi-node execution can be enabled.
10. Public API naming uses `nodeIndex` and `totalNodes`; do not introduce `shardIndex` / `totalShards` for P1 Resource.

## 7. Architecture

The architecture is a narrow extension of the P0 execution model:

1. API validates the resource request and current Workspace visibility/permissions.
2. API creates the logical Run, redacted run snapshot, allocation rows, active leases, and allocation-aware control requests in one DB transaction.
3. API worker/control executor starts one local Runner execution per allocation after the allocation transaction commits.
4. Runner reports node-local events and artifacts with one `runId` and one `nodeId`.
5. API validates runner identity, maps the event to an allocation, updates allocation state, and derives logical Run state.
6. Web displays only the public redacted projection from generated OpenAPI.

No SSH, SFTP, remote command, artifact transfer, or external process execution may run inside the allocation transaction.

## 8. Resource Request Contract

Resource request is normalized before Run creation.

Representative request examples:

```json
{"resourceRequest":{"mode":"manual","selectedNodeIds":["node_01","node_02"],"concurrencyPerNode":100}}
{"resourceRequest":{"mode":"auto","nodeCount":2,"concurrencyPerNode":100}}
```

Locked validation:

1. `manual selectedNodeIds` requires a distinct, bounded non-empty set of visible selectable nodes.
2. `auto nodeCount` requires a bounded positive node count.
3. `manual + nodeCount` must be rejected.
4. `auto + selectedNodeIds` must be rejected.
5. `concurrencyPerNode` or the equivalent normalized load setting is per node.
6. P1-01 does not split global concurrency across nodes; it copies the workload to each allocated node.
7. Current Workspace invisible nodes return not-found or an equivalent safe response.
8. Current Workspace visible but unavailable nodes return `LOAD_NODE_UNAVAILABLE` or an equivalent `409` response.
9. Auto capacity failure returns a capacity unavailable response without leaking invisible cross-Workspace nodes.

## 9. Allocation Strategy

Allocation invariants:

1. All requested nodes are selected, locked, leased, and linked to allocations atomically.
2. Manual mode only uses the validated visible nodes requested by the user.
3. Auto mode selects currently visible Idle nodes deterministically from existing stable columns; P1-01 does not add usage-history scoring or matching fields.
4. If any requested manual node is unavailable, no Run, lease, or allocation is created.
5. If auto cannot find enough eligible nodes, no Run, lease, or allocation is created.
6. One node cannot have two active leases.
7. One logical Run may hold multiple node leases through its allocations.
8. Allocation success does not imply remote process success; remote start is handled after commit.

## 10. Data Model

P1-01 keeps the model conceptual in this frozen SDD. Exact ORM and migration fields belong to implementation PRs.

Required invariants and representative fields:

1. `Run` remains the logical execution object; single-node and multi-node executions are both represented through allocation rows.
2. A `run_node_allocations` model, or an equivalent concept, records one allocation per assigned node.
3. Representative allocation fields include `runId`, `nodeId`, `nodeIndex`, `totalNodes`, lifecycle state, timing markers, heartbeat marker, terminal reason, cleanup/quarantine result, and safe artifact/report references.
4. The migration invariant is: node_leases.run_id is no longer unique because one Run can hold multiple leases.
5. Active lease uniqueness remains on `node_id` so a node cannot be leased by two Runs at the same time.
6. The invariant is: control requests must be allocation-aware so start/stop/force_kill target the correct node and Run.
7. Implementations may add internal helper fields, but helper fields do not become the public contract source.
8. `runs.selected_node_id` may remain as the denormalized primary selected node for list/detail summaries; allocation rows are the execution source of truth.

## 11. Run Snapshot

Run Snapshot captures execution facts needed for reproducibility, diagnostics, and report projection, but public responses expose only a redacted projection.

Rules:

1. Internal snapshot may include resource request, allocated node IDs, allocation IDs, node ordering, and execution metadata required by API/worker/report internals.
2. Public Run Detail / Run Report must not expose hostnames, `sshUser`, `runnerHome`, server paths, runner tokens, credentials, private env values, dependency file server paths, or MinIO object keys.
3. Public resource projection uses `resourceRequest`, `allocatedNodes`, `nodeIndex`, `totalNodes`, node state, safe timestamps, safe terminal reason, cleanup/quarantine status, artifact grouping, and SLA verdicts.
4. Public node execution projection is allocation-backed; implementations should not synthesize fallback node rows.

## 12. Execution Protocol

Execution principles:

1. API transaction performs only validation, allocation, lease/control-request persistence, and snapshot persistence.
2. SSH/SFTP/remote command execution must not occur inside the allocation transaction.
3. Worker processes one start request per allocation with bounded local concurrency.
4. Runner execution remains node-local; each Runner runs local Taurus/JMeter for the copied workload.
5. The first accepted/running allocation may move the logical Run to active state, but the logical Run becomes terminal only after every allocation is terminal.
6. Any non-Stop allocation failure makes the logical Run final candidate `failed` and triggers cleanup for remaining non-terminal allocations.
7. User Stop intent produces `aborted` only when no non-Stop failure has already made the Run failed.
8. Late terminal callbacks must not overwrite an already terminal logical Run.
9. SLA verdict aggregation is separate from logical Run terminal state.
10. In P1-01 all allocated nodes are required nodes.
11. Any required node SLA `failed` makes Run-level SLA `failed`.
12. Missing or malformed required node verdict cannot be aggregated as Run-level `passed`.

## 13. Stop / Force Kill / Timeout

Stop and cleanup are per-allocation but user-visible as one logical Run action.

Rules:

1. Stop broadcasts one stop intent/control request to every non-terminal allocation.
2. Repeated Stop calls must not duplicate control requests or corrupt terminal allocation state.
3. Force-kill targets the allocation's node-local managed process only.
4. Accepted wait timeout is per allocation; if `accepted` does not arrive after remote start request, that allocation fails with an accepted-timeout reason and cleanup is attempted.
5. Heartbeat timeout is per allocation and must release, cleanup, or quarantine that node according to existing safety rules.
6. Stop versus timeout races preserve Stop intent for allocations not already failed.
7. A node with uncertain cleanup must remain unavailable/quarantined rather than being marked Idle prematurely.
8. Stale lease recovery must not mark the logical Run `finished` only because leases were released.

## 14. Runner Callback and Artifact Validation

Runner callback schema remains `packages/contracts/runner/runner-callback.schema.json` unless Foundation 05 or a later ADR changes it.

Security gate:

```text
authenticated runner node == payload nodeId
and payload nodeId is allocated to payload runId
```

Locked rules:

1. Runner token or equivalent credential must be node-bound before multi-node execution is enabled.
2. A shared runner token must not be used for multi-node callbacks or artifacts.
3. Token for node A reporting node B must be rejected even when both nodes are allocated to the same Run.
4. Unallocated node reporting a Run must be rejected.
5. Callback idempotency remains `(runId, eventId)`.
6. Duplicate event with identical payload remains idempotent; duplicate event with conflicting payload remains conflict.
7. Allocation lookup uses `runId + nodeId` after token-node equality succeeds.
8. Artifact upload validation uses the same token-node equality plus allocation membership rule.
9. Artifact metadata may be node-aware internally, but public artifact responses remain redacted.
10. Tests must cover node A attempting to report node B and being rejected.

If implementation discovers that the callback idempotency key must change, P1-01 must stop and update Foundation 05 or add an ADR first.

## 15. API Contract

FastAPI/Pydantic source schemas remain the OpenAPI source of truth; generated OpenAPI and Web client are artifacts.

Public contract requirements:

1. Run creation accepts normalized `resourceRequest` only for Standard Test Plan Runs.
2. Raw API input must reject conflicting resource fields, including `manual + nodeCount` and `auto + selectedNodeIds`.
3. Error shape remains `{code, message, requestId, details?}` with English fallback messages.
4. Representative error codes: `RESOURCE_REQUEST_INVALID`, `LOAD_NODE_UNAVAILABLE`, `LOAD_NODE_CAPACITY_UNAVAILABLE`, and `RUN_CREATION_NOT_ALLOWED` or existing equivalents.
5. Details may include safe requested/available counts but must not disclose cross-Workspace private node existence.
6. Run Detail / Run Report expose redacted `resourceRequest`, redacted `allocatedNodes`, allocation summary counts, node-level status/artifacts/SLA verdicts, and Run-level SLA verdict.
7. Public responses must not include host, `sshUser`, `runnerHome`, server paths, runner tokens, credentials, private env values, or MinIO object keys.
8. Web must use generated contracts from `@surgepilot/contracts` and must not hand-write P1-01 response shapes.

## 16. Run Report / Final Stats

Run Report remains an extension of the existing report surface, not a new report engine.

Rules:

1. Report shows a Resource section with one row per allocation.
2. Each row uses `nodeIndex` / `totalNodes`, safe node display name/ID, state, safe timestamps, last heartbeat, terminal reason, cleanup/quarantine status, artifact group, and node SLA verdict.
3. Artifacts are grouped by node/allocation.
4. Aggregate final stats may be shown only when all required node artifacts are present and the metric is mathematically safe to combine.
5. Safe aggregates include counts, sums, and derived rates from sums.
6. Percentile latency, throughput curves, and cross-node trend aggregation are deferred unless a later Slice defines safe semantics.
7. Missing or malformed node artifacts produce warnings and prevent false Run-level pass reporting where verdict data is incomplete.
8. Report parsing failure must not alter Run terminal state, Stop behavior, lease release, quarantine, or Valid/Invalid behavior.

## 17. Web UX

Web UX is contract-driven and backend-authoritative.

1. Standard Test Plan resource UI supports manual multi-select, auto node count, and per-node load setting.
2. Manual selector shows only current Workspace visible nodes; visible unavailable nodes may show safe disabled reasons.
3. Debug Run UI remains single-node and must not show P1-01 multi-node controls.
4. Web rejects obvious invalid combinations before submit, but backend validation is authoritative.
5. Manual mode UI must not send `nodeCount`; auto mode UI must not send `selectedNodeIds`.
6. Run List may show compact logical Run status plus node count summary.
7. Run Report shows detailed allocation rows and safe warnings.
8. Stop remains one button and explains that SurgePilot is stopping all active nodes.
9. Web must not display server paths, credentials, tokens, MinIO object keys, hostnames, runner homes, or low-level stack traces.

## 18. Security / Workspace / Permission Requirements

Security invariants:

1. Backend enforces Workspace isolation for resource request, allocation, Run Detail, Run Report, artifact download, and node list.
2. Public Load Nodes follow existing visibility rules; private nodes require matching Workspace.
3. Current Workspace invisible nodes return not-found or an equivalent safe response.
4. Current Workspace visible but unavailable nodes return `LOAD_NODE_UNAVAILABLE` or equivalent `409`.
5. Auto allocation must not consider invisible private nodes.
6. Backend permission checks remain authoritative; UI hiding is not authorization.
7. Runner callback/artifact endpoints are internal runner-only and validate runner credentials before mutation.
8. Runner credential identity must bind to the same `nodeId` in the payload before allocation lookup.
9. No shared token may allow one allocated node to submit callbacks/artifacts for another allocated node.
10. Logs and audit events may record safe IDs, allocation summaries, Stop requests, force-kill decisions, and quarantine reasons, but not secrets, raw credentials, private env values, server paths, MinIO object keys, or node connection details.

## 19. Migration / Compatibility Plan

Migration is limited to supporting P1-01 without expanding execution scope.

1. Add `run_node_allocations` or equivalent allocation storage.
2. Relax `node_leases.run_id` uniqueness while preserving active uniqueness per `node_id`.
3. Make control requests allocation-aware where needed.
4. New Standard and Debug Run executions must create allocation rows, including the single-node case.
5. Existing single-node fields may remain as denormalized display/source fields, but they are not an execution authority.
6. Public Run Report node rows are allocation-backed and exposed through `allocatedNodes` only.
7. Normal Alembic downgrade policy applies; data safety is more important than perfect down-conversion of multi-node Runs.

## 20. Implementation Milestones

1. Governance freeze:
   - keep `ADR-0009`, this Slice SDD, and `P1-README.md` synchronized as Accepted / active / frozen for implementation.
2. Contracts and persistence:
   - add source API schemas, allocation storage, lease/control-request adjustments, redacted projection, generated OpenAPI/client, and token-node-binding tests.
3. Allocation transaction:
   - implement manual and auto validation, atomic allocation/lease/control-request creation, and race tests.
4. Worker/control executor:
   - make start/stop/force_kill allocation-aware without adding Redis/Celery/Kafka/external queues.
5. Callback aggregation and recovery:
   - enforce token node equality plus allocation membership, aggregate allocation states and SLA verdicts, and preserve late-terminal protection.
6. Web/report:
   - add generated-contract-driven resource UI and redacted Run Report allocation summary.
7. Verification:
   - prove contracts, non-SSH regression, fake-runner multi-node smoke, and real SSH two-node acceptance.

## 21. Tests

Minimum verification coverage:

1. Resource contract rejects invalid combinations, including `manual + nodeCount`, `auto + selectedNodeIds`, duplicate selected nodes, and unsupported Debug multi-node.
2. Atomic allocation succeeds only when all requested nodes can be leased; failures create no partial Run/lease/allocation state.
3. One Run can hold multiple leases while one node cannot hold multiple active leases.
4. Runner callback/artifact validation enforces token node equality plus allocation membership, including node A attempting to report node B.
5. Callback idempotency remains `(runId, eventId)` and conflicting duplicate payloads remain conflicts.
6. Logical Run terminal state waits for all allocations; any non-Stop allocation failure makes the Run failed.
7. Stop is idempotent and creates at most one effective stop intent per active allocation.
8. Heartbeat timeout, accepted timeout, force-kill cleanup, and stale lease recovery are per allocation.
9. Quarantine prevents uncertain nodes from returning to Idle prematurely.
10. Public response redaction excludes host, `sshUser`, `runnerHome`, server paths, tokens, credentials, private env values, and MinIO object keys.
11. Public contract uses `nodeIndex` / `totalNodes` and generated Web client remains fresh.
12. SLA aggregation treats all allocated nodes as required; any failed, missing, or malformed required node verdict prevents Run-level passed.
13. Fake-runner multi-node smoke covers success, one-node failure, token-node mismatch rejection, and report redaction.
14. Real SSH two-node acceptance proves two distinct nodes execute one Standard Test Plan Run and converge Stop/cleanup safely.

## 22. Verification Matrix

Implementation PRs for this Slice must make these gates reproducible:

| Gate | Required command/profile | Required result |
| --- | --- | --- |
| Contract generation | `make generate-contracts` | Generated OpenAPI/Web client include P1-01 public fields and exclude execution internals. |
| Full non-SSH verification | `make verify` | Lint/typecheck/tests/contract freshness/migration checks pass for the implemented scope. |
| Fake-runner multi-node smoke | Implementation-defined target/profile | Multi-node Standard Run finishes; one-node failure fails logical Run; token-node mismatch is rejected; report is redacted. |
| Real SSH two-node acceptance | Implementation-defined SSH target/profile | Two distinct SSH nodes execute one Standard Test Plan Run; Stop converges; leases release or quarantine; report shows redacted node rows and correct SLA verdict. |
| Redaction regression | API/report tests or smoke profile | Public responses never expose host, `sshUser`, `runnerHome`, server paths, tokens, credentials, private env values, or MinIO object keys. |

The fake-runner and real SSH target names may be chosen by implementation PRs, but their purpose and assertions are part of this Slice acceptance.

## 23. Done When

P1-01 is done only when:

1. `ADR-0009`, this Slice SDD, and `P1-README.md` are synchronized as active/frozen for implementation.
2. Standard Test Plan Run supports `manual selectedNodeIds` and `auto nodeCount` through generated OpenAPI and generated Web client.
3. `manual + nodeCount` and `auto + selectedNodeIds` are rejected by backend schema/validation and normal Web UI path.
4. Multi-node allocation is atomic and fail-fast.
5. One logical Run can hold multiple active node leases without allowing node double-lease.
6. Worker start/stop/force_kill is allocation-aware.
7. Runner callbacks/artifacts require node-bound credential equality plus allocation membership.
8. Callback idempotency remains `(runId, eventId)` unless Foundation 05 or a new ADR changes it first.
9. Stop remains idempotent and converges all non-terminal allocations.
10. Heartbeat timeout, accepted timeout, force-kill cleanup, stale lease recovery, and quarantine work per allocation.
11. All allocated nodes are required for SLA aggregation; any failed, missing, or malformed required verdict prevents Run-level passed.
12. Run Report shows redacted allocation summary, per-node status, per-node artifacts, per-node SLA verdicts, and Run-level SLA verdict.
13. Public Run Detail / Run Report never expose execution internals or secrets.
14. Public contract uses `nodeIndex` / `totalNodes`.
15. Web uses `@surgepilot/contracts` generated client/types only.
16. `make generate-contracts`, `make verify`, fake-runner multi-node smoke, and real SSH two-node acceptance are reproducible and pass.
17. P0 single-node Run behavior and Debug Run behavior do not regress.
18. No resource queue, autoscaling, cloud procurement, node labels, resource matching, distributed JMeter controller, Redis/Celery/Kafka, Monitoring multi-node semantics, Debug Run multi-node behavior, global concurrency auto-splitting, or OpenAPI/API Catalog capability is introduced.

## 24. Implementation Backfill

Implementation PR facts:

1. Persistence uses `run_node_allocations` with one allocation row per selected Load Node. `node_leases.run_id` is no longer unique; active node lease uniqueness remains node-scoped.
2. Standard Test Plan Runs accept generated-contract `resourceRequest` overrides for `manual selectedNodeIds` and `auto nodeCount`. Debug Run resource overrides remain rejected.
3. Runner callbacks and artifacts keep the existing Runner callback schema and now require allocation membership. Callbacks/artifacts require an API-signed node-bound runner credential in the form `node:<nodeId>:<signature>`; the master runner secret stays API-local.
4. Run control requests are allocation-aware for start, stop, and force-kill. Stop remains one user-visible action and broadcasts one effective stop intent per non-terminal allocation.
5. Public Run List / Run Report projections expose redacted resource request and allocation summaries only. Public responses use `nodeIndex` / `totalNodes` and do not expose hosts, `sshUser`, `runnerHome`, credentials, runner tokens, server paths, or MinIO object keys.
6. Web uses generated `@surgepilot/contracts` types through the app API client and adds Standard Run resource mode controls, manual multi-select, auto node count, node-count list summary, and Run Report allocation rows. No new UI component system was added.
7. Run Report final stats projection is allocation-aware and fail-closed. When a Run has multiple `run_node_allocations`, KPI Summary no longer selects the latest single `final_stats_csv`; it requires exactly one available `final_stats_csv` per required allocation, validates `artifact.allocation_id` and `artifact.node_id`, and aggregates only mathematically safe non-negative counts, rates from sums, and non-negative weighted-average latency metrics. Malformed or partial parsed contributor fields leave unsafe aggregate fields `null` without throwing or synthesizing false totals. Multi-allocation percentile fields remain `null`, and the Final Stats Preview returns one aggregate total row only. Parsed aggregate advisory warnings are exposed through `finalStatsPreview.warnings`; they are not KPI missing reasons and do not make Failure Diagnostics appear by themselves. `artifactsSummary.hasFinalStatsCsv` still means any available final stats artifact exists, not that KPI coverage is complete.
8. New allocation-aware multi-node final stats fail-closed reason codes added by this fix are: `allocation_pending_for_final_stats`, `final_stats_missing_for_allocations`, `final_stats_missing_for_failed_allocations`, `final_stats_conflict_for_allocations`, `final_stats_allocation_node_mismatch`, `summary_pending_for_allocations`, and `summary_parse_failed_for_allocations`. Existing single-allocation and parser-derived codes such as `final_stats_missing`, `summary_pending`, `summary_parse_failed`, and column/value warnings remain possible on their existing paths.
9. New allocation-aware multi-node final stats warning codes added by this fix are: `percentile_aggregation_unsupported`, `terminal_late_final_stats_used`, `aggregate_rate_denominator_unavailable`, and `aggregate_average_denominator_unavailable`.
10. A Run with exactly one allocation keeps the existing single-allocation projection path. If that allocation is non-terminal and its final stats artifact is not available yet, the projection is `pending` with `allocation_pending_for_final_stats`; it does not fall back to the historical no-allocation `final_stats_missing` path.
11. Runner uploads the existing individual artifact candidates, including the runner log, Taurus/JMeter logs, final-stats CSV variants, and Debug HTTP trace/body blobs, with safe relative-path validation and the existing hard per-artifact upload limit. No diagnostic ZIP artifact is created or uploaded by this checkpoint.
12. Runner deletes a local Run directory only after the individual artifact uploads have no failed result, the terminal callback is acknowledged, and supervisor/workload liveness and pidfile checks are safe. Upload failure, terminal callback non-ACK, live or uncertain workload state, or cleanup filesystem failure preserves the local directory for fail-closed diagnostics. This does not add ZIP extraction, preview, file-tree browsing, or a new API/Web contract.
13. Verification added:
   - `apps/api/tests/test_p1_01_resource_multi_node.py`
   - shared fake Runner multi-node smoke executes one fake Runner flow per allocation, including artifact callbacks, success/failure aggregation, node-bound mismatch rejection, and report redaction
   - `apps/api/tests/test_p0_07_run_report_api.py` allocation-aware final stats regression cases
   - `apps/web/src/features/runs/run-report.test.tsx` allocation-backed node row and redaction regression case
   - `apps/runner/tests/test_cli.py` individual artifact upload, callback ACK, and cleanup gate regression cases
   - `tests/contract/test_p1_01_resource_multi_node_openapi.py`
   - `tests/e2e/p1_01_resource_multi_node.spec.ts`
14. Local verification run for this implementation included `make generate-contracts`, targeted API/contract/Web/E2E checks, `make verify-db`, and `make verify`.
15. Remaining acceptance gap: real SSH two-node acceptance requires an SSH-capable environment profile and was not executed in the local development environment for this PR; the shared fake Runner multi-node smoke is covered by the API verification above.
