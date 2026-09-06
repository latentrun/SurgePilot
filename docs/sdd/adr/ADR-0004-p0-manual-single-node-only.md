# ADR-0004: P0 Manual Single Node Only

- Status: Accepted
- Scope: P0 resource selection, Load Nodes, Run creation, and Test Plan execution

## Context

P0 must deliver the internal MVP load-testing loop with predictable resource behavior. The PRD requires users to manually select one available Load Node in P0, while automatic allocation and multi-node execution are P1 capabilities. P0-Stability also requires node lease safety, Stop idempotency, heartbeat timeout convergence, and prevention of permanently Busy nodes. These stability requirements are easier to prove when one Run binds to exactly one selected node.

## Options Considered

1. **Manual single-node execution only**
   - Pros: simplest resource model, deterministic user choice, smaller node lease surface, easier Run Snapshot and report attribution, lower risk for P0 stability.
   - Cons: cannot scale one Run across multiple nodes and requires users to choose a node manually.
2. **Automatic allocation of one node**
   - Pros: less user choice during Run creation.
   - Cons: introduces scheduler policy, fairness, retry, and hidden resource-selection behavior before P0 needs them.
3. **Manual multi-node execution**
   - Pros: supports larger tests earlier.
   - Cons: requires multi-node lease acquisition, partial failure handling, aggregate reports, and more complex Stop/cleanup behavior.
4. **Auto multi-node execution**
   - Pros: closest to future resource pooling.
   - Cons: combines scheduling and distributed execution complexity, which is outside P0.

## Decision

P0 supports only manual selection of one Idle Load Node per Run.

The API must enforce this rule server-side. P0 must not expose Auto allocation, Node Count, Selected Nodes multi-select, multi-node execution, resource queues, or scheduler behavior. Public and Workspace Private nodes may both exist, but a P0 Run selects exactly one node that is visible to the current Workspace, not archived, and currently `idle`. Nodes in `uninitialized`, `initializing`, `busy`, `offline`, `quarantined`, or `disabled` states are not selectable.

P0 reserves `LOAD_NODE_UNAVAILABLE` as the Run/Test Plan resource-selection error code when the selected node is missing, not visible, not `idle`, archived, or otherwise unavailable at Run creation time. The P0-06 Slice owns the final endpoint response shape and registration details.

## Consequences

Positive consequences:

1. Node lease acquisition can be atomic for one node.
2. Run Snapshot stores one selected Load Node reference.
3. Busy release, heartbeat timeout cleanup, Stop convergence, and quarantine rules are easier to reason about.
4. Test Plan and Run Report UI can show one concrete node without aggregate ambiguity.

Costs and constraints:

1. P0 cannot scale a single Run by adding nodes.
2. If no Idle node is available, P0 returns `LOAD_NODE_UNAVAILABLE` instead of queueing.
3. P1 resource work must introduce a new Slice SDD and, if it changes this decision, a superseding ADR.
4. P0 documentation may mention future Auto and multi-node behavior only as non-clickable roadmap content.

## Related ADRs

- `ADR-0002-runner-independent-app.md`
- `ADR-0005-p0-no-api-catalog-no-monitoring-no-schedule.md`
- `ADR-0006-p0-separate-api-worker.md`

## References

- `docs/prd/PRD.md`
- `docs/sdd/00-product-scope-and-priority.md`
- `docs/sdd/01-architecture-overview.md`
- `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- `docs/sdd/slices/P0-03-load-nodes.md`
- `docs/sdd/slices/P0-06-test-plan-run-now.md`
