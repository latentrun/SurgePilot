# P1 Slice writing brief / thin index

## Purpose / Usage

This document is only a P1 Slice writing brief and scope index. It does not replace the PRD, `docs/sdd/00-product-scope-and-priority.md`, `AGENTS.md`, ADRs, or any real Slice SDD.

P1 governance has started via `docs/sdd/adr/ADR-0022-p1-governance-start.md`, but this README still remains an index. It does not authorize implementation by itself.

Current conflict to avoid: older P1 index wording can become stale when real Slice SDDs are added or renumbered. Downstream P1 Slice authors must follow the authoritative references below instead of copying old candidate names or old P0-only wording from this README.

## Authoritative References

Use only these references for P1 Slice drafting decisions:

- P1 governance start: `docs/sdd/adr/ADR-0022-p1-governance-start.md`.
- P1 Debug HTTP Trace scope addition: `docs/sdd/adr/ADR-0008-p1-debug-http-trace.md`.
- P1 Scenario execution preview removal: `docs/sdd/adr/ADR-0023-remove-scenario-execution-preview.md`.
- P1 scope: `docs/sdd/00-product-scope-and-priority.md` §6.
- P1 fixed boundaries: `docs/sdd/00-product-scope-and-priority.md` §6 fixed-boundary list.
- P1 Slice split guidance and P0 non-prerequisite rule: `docs/sdd/00-product-scope-and-priority.md` §6.
- Agent constraints for architecture, contracts, language, and verification gates: `AGENTS.md`.

## P1 Slice Index

The following files are the current P1 Slice index. Real active Slice SDDs are authoritative only for their own scoped capability.

1. `docs/sdd/slices/P1-00-monitoring.md` -- active Slice SDD for deployment-level P1 Monitoring: JMeter Backend Listener / InfluxDB write config bridge + same-origin Grafana iframe.
2. `docs/sdd/slices/P1-03-workspace-admin.md` -- active Slice SDD for P1 Workspace / Admin.
3. `docs/sdd/slices/P1-01-resource-multi-node.md` -- active Slice SDD for P1 Resource Multi-node; design frozen and Accepted for implementation.
4. `docs/sdd/slices/P1-04-scenario-testplan-polish.md` -- active Slice SDD for P1 Scenario / Test Plan polish, amended by `ADR-0023` to retain Generated YAML Preview only on Test Plan.
5. `docs/sdd/slices/P1-05-curl-import.md` -- active Slice SDD for P1 cURL Import.
6. `docs/sdd/slices/P1-06-dependency-preview.md` -- active Slice SDD for P1 Dependency File Preview.
7. `docs/sdd/slices/P1-08-debug-http-trace.md` -- active Slice SDD for P1 Debug HTTP Trace.

Active P1 Slice SDDs at this revision:

- `P1-00-monitoring.md`, governed by the P1 scope gate and limited to deployment-level config, Standard Run InfluxDB writes, and a read-only Grafana entry.
- `P1-03-workspace-admin.md`, governed by the P1 scope gate.
- `P1-01-resource-multi-node.md`, governed by `ADR-0009`.
- `P1-04-scenario-testplan-polish.md`, governed by the P1 scope gate and amended by `ADR-0023` to keep only the Test Plan read-only Generated YAML Preview.
- `P1-05-curl-import.md`, governed by the P1 scope gate.
- `P1-06-dependency-preview.md`, governed by the P1 scope gate.
- `P1-08-debug-http-trace.md`, governed by `ADR-0008`.

Do not expand placeholders into implementation design, schemas, migrations, or generated-contract details inside this README.

## Cross-cutting Constraints

Contract-first rules, Workspace isolation, permission checks, Runner/Web/API boundaries, language rules, and verification gates remain governed by the authoritative references above. This README intentionally does not restate those rules.

P1 placeholder or index documents must not create clickable P1 UI, callable P1 API behavior, or P1 execution dependencies. Implementation requires a real active P1 Slice SDD.

P1 capabilities must not become prerequisites for the P0 execution loop.

## Revision Protocol

This README must not independently enlarge P1 scope. Any new or changed P1 capability must first update the PRD or add a confirmed ADR, then synchronize `docs/sdd/00-product-scope-and-priority.md`, `docs/sdd/02-repo-structure-and-dev-workflow.md`, `AGENTS.md`, and this index where applicable.

The P1 governance start gate is recorded in `docs/sdd/adr/ADR-0022-p1-governance-start.md`. If another document still contains stale P0-only target wording, treat it as requiring sync before using that file as execution input for a P1 task.

Before submitting changes to this README, verify that it still avoids stale P1/P2 candidate repetition, full forbidden-matrix duplication, and implementation design.
