# ADR-0009 P1 Resource Multi-node

- Status: Accepted
- Scope: P1 Standard Test Plan resource allocation, multi-node execution, node lease aggregation, Runner callback aggregation, and Run Report node summary
- Active Slice: `docs/sdd/slices/P1-01-resource-multi-node.md`
- Slice Status: Accepted for implementation; design frozen as the P1-01 Slice SDD
- Supersedes: `ADR-0004` only for P1 Standard Test Plan Runs that opt into `resource_multi_node`
- Does not supersede: P0 manual single-node baseline, Debug Run single-node constraints, P0-Stability, contract-first rules, Runner/API/Web boundaries, Workspace isolation, or P1 fixed exclusions

## Context

P0 intentionally supports only manual selection of one Idle Load Node per Run. `ADR-0004` made that decision to keep the first execution loop predictable and to prove Stop idempotency, callback idempotency, heartbeat timeout cleanup, and node lease convergence before expanding the resource surface.

P0 is now the stable baseline and P1 scope explicitly includes Resource Auto allocation, multi-node execution, Node Count, and Selected Nodes. The current implementation already has multiple Load Nodes as managed assets, but a single Run remains hard-bound to one selected node and one active lease. Moving P1 Resource forward therefore requires an explicit architecture decision that narrows the P1 change to resource allocation and per-node execution aggregation without introducing a scheduler platform.

The key conflict to resolve is not whether P1 may use multiple nodes; the scope gate already allows it. The key decision is how to extend the P0 single-node state machine without rewriting Runner ownership, adding queues, weakening Runner token isolation, or letting a Runner make global scheduling decisions.

## Decision

P1 adds `resource_multi_node` for Standard Test Plan Runs through the active, frozen-for-implementation Slice `docs/sdd/slices/P1-01-resource-multi-node.md`.

The accepted architecture is:

1. Keep `Run` as the logical user-facing execution object.
2. Add a Run-Node allocation/execution concept that records one row per assigned Load Node, including `nodeId`, `nodeIndex`, lifecycle state, runner PID, heartbeat, terminal reason, and cleanup result.
3. Keep the Runner protocol node-local. Runner callbacks continue to carry one `runId` and one `nodeId`; the API signs a node-bound runner credential as `node:<nodeId>:<signature>` and validates both that the authenticated credential resolves to the same node as the payload `nodeId` and that the node belongs to an allocation for that Run, then uses allocation/Run terminal state to decide whether to mutate, store, or ignore the event. The master runner secret never leaves the API.
4. Support two resource request modes for Standard Test Plan Runs:
   - `manual selectedNodes`: the user chooses a bounded, distinct set of currently visible Idle nodes, and the request must not also provide `nodeCount`.
   - `auto nodeCount`: the API fail-fast allocates `N` currently visible Idle nodes in one DB transaction.
5. Acquire all requested node leases atomically. Partial allocation is not allowed: either all leases and allocation rows are created, or the Run is not created.
6. Preserve the existing Run states: `initializing`, `running`, `stopping`, `finished`, `failed`, `aborted`.
7. Use per-allocation sub-states to aggregate callbacks. A logical Run becomes terminal only after all allocations are terminal.
8. Stop broadcasts to every non-terminal allocation and remains idempotent.
9. Treat Run-level SLA verdict as failed when any allocated node reports a failed SLA verdict; SLA verdict aggregation remains separate from the logical Run state.
10. Do not introduce resource queues, fairness scheduling, automatic retry allocation, autoscaling, cloud node purchase, Kubernetes scheduling, Redis, Celery, Kafka, or any external scheduler dependency.

## Boundaries

In scope:

- Standard Test Plan Runs with `resourceRequest.mode` = `manual` or `auto`.
- `nodeCount`, `selectedNodeIds`, `allocatedNodes`, and per-node execution state.
- Multi-node lease acquisition and release.
- Per-node `start`, `stop`, and `force_kill` control requests.
- Runner callback aggregation by authenticated runner token node + `runId` + payload `nodeId` + allocation.
- Run Report allocation summary and node-level artifacts/status.
- Run-level SLA verdict aggregation where any node-level SLA failure fails the Run-level SLA verdict.
- Minimal aggregate final stats where aggregation is mathematically safe.

Out of scope:

- Debug Scenario Run and Test Plan debug-mode multi-node execution.
- Resource queues, background waiting for capacity, fair-share scheduling, auto retry allocation, autoscaling, or cloud resource purchasing.
- Load Node tags, capacity labels, CPU/memory matching, region matching, or resource matching DSL.
- Distributed JMeter controller/worker topology. Each node still runs a local Runner and local Taurus/JMeter execution.
- P1 Monitoring multi-node aggregation semantics.
- P1 Debug HTTP Trace multi-node behavior.

## Consequences

- `ADR-0004` remains authoritative for P0 and for Debug Run unless a later accepted ADR says otherwise.
- P1 Standard Test Plan Run creation must no longer depend on a single `runs.selected_node_id` as the only resource binding. Allocation rows are the execution source of truth; `runs.selected_node_id` may remain only as a denormalized primary selected-node summary.
- `node_leases.run_id` can no longer be unique if one Run may hold multiple active leases. The active uniqueness invariant stays on `node_id WHERE released_at IS NULL`.
- Runner callback and artifact endpoints do not need a schema version bump solely for multi-node because they already include `nodeId`; validation logic changes from single selected node equality to API-signed node-bound credential equality plus membership in the Run's allocations.
- API and Web public contracts must expose only redacted Resource request and allocation summaries through generated OpenAPI. Internal execution metadata such as hosts, SSH users, runner homes, object keys, credentials, tokens, and server paths must not appear in public Run Detail or Run Report responses; Web must not hand-write resource shapes.
- The Slice SDD must provide verification gates covering atomic allocation, callback aggregation, token-node binding, idempotent Stop, timeout cleanup, stale lease recovery, node-level report display, SLA verdict aggregation, fake-runner multi-node smoke, and real SSH two-node acceptance.
