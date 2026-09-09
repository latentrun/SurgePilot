# SurgePilot Agent Instructions

Authoritative source: `docs/sdd/02-repo-structure-and-dev-workflow.md`. This file is the synced operational copy for the current reconstruction checkpoint.

## Current target

P0 is the completed baseline. The current delivery target is **P1 governance start / P1 Slice kickoff**, authorized by `docs/sdd/adr/ADR-0022-p1-governance-start.md`.

P1 work may start only when an explicit task names a real P1 Slice SDD and its accepted scope source. The active first Slice is `docs/sdd/slices/P1-08-debug-http-trace.md`, governed by `docs/sdd/adr/ADR-0008-p1-debug-http-trace.md`. P1 work must preserve the P0 execution loop, P0-Stability, contract-first workflow, Workspace isolation, permission enforcement, Runner/API/Web boundaries, and verification gates.

P2 remains out of scope unless separately authorized by an accepted ADR or PRD update. P1-08 is limited to Debug Run HTTP Trace; it does not authorize Standard Run tracing, Monitoring, Grafana, InfluxDB, JMeter plugins, a generic logging or sanitization framework, runtime tar changes, or standalone Groovy distribution.

## Canonical documents

- Product source: `docs/prd/PRD.md`
- Scope gate: `docs/sdd/00-product-scope-and-priority.md`
- Workflow source: `docs/sdd/02-repo-structure-and-dev-workflow.md`
- P1 governance ADR: `docs/sdd/adr/ADR-0022-p1-governance-start.md`
- P1 Slice index: `docs/sdd/slices/P1-README.md`
- Active Slice: `docs/sdd/slices/P1-08-debug-http-trace.md`
- Active Slice ADR: `docs/sdd/adr/ADR-0008-p1-debug-http-trace.md`

## Execution rules

- Keep implementation inside the named active Slice.
- Update contracts before consumers; keep API, Web, Runner, and artifact boundaries consistent.
- Preserve P0 behavior and security properties.
- Do not add migrations, product code, routes, services, or generated contracts for this design-only atomic.
- Use the Slice's verifiable Done When criteria before claiming completion.
