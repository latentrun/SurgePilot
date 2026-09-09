# 00. Product Scope and Priority

## Purpose

This document is the initial milestone scope gate. It prevents future-product ideas from becoming partially implemented before the core execution loop and its safety properties are complete.

## Current delivery target

P0 is the completed baseline. The current delivery target is **P1 governance start / P1 Slice kickoff** under `docs/sdd/adr/ADR-0022-p1-governance-start.md`.

P1 implementation may begin only through a named P1 Slice SDD with verifiable Done When criteria. P1 must preserve the P0 execution loop, P0-Stability requirements, contract-first workflow, Workspace isolation, permission enforcement, Runner/API/Web boundaries, and verification gates. P2 remains out of scope unless separately authorized by an accepted ADR or PRD update.

```text
Default Workspace
  -> local registration and login
  -> reusable Env Group, Dependency File, and Load Node
  -> visual Scenario
  -> Test Plan
  -> manual selection of one Idle Load Node
  -> Debug or Run Now
  -> Run Report and artifacts
  -> validity judgment
```

Core behavior and stability ship together. A runnable flow is incomplete without immutable snapshots, callback idempotency, safe Stop, heartbeat timeout convergence, node lease cleanup, authorization, and file-path safety.

## Included capability

- Local accounts, first-admin initialization, and a Default Workspace.
- Workspace-aware assets and Private Load Nodes; platform-owned Public Load Nodes.
- Visual Scenario and Test Plan authoring.
- Manual single-node Debug and standard Runs.
- Run state, Stop, immutable execution snapshot, node lease, and self-healing worker.
- Verdict-first Run Report, validity, logs, final statistics, and downloadable artifacts.
- MinIO-backed Dependency Files and Run Artifacts through the API.
- Read-only platform Setup Status.

## Explicit exclusions

The initial milestone does not implement API Catalog, import/generation flows, Monitoring, Grafana or InfluxDB, Schedule Run, automatic allocation, multi-node execution, resource queues, Kubernetes, Redis or an external task queue, enterprise SSO, secret Env Groups, non-MinIO storage, or AI generation and analysis.

An excluded capability is still implemented if it exists only as a hidden API, route, migration, disabled service, or feature-flagged usable path. Roadmap wording in documents is allowed; executable surface is not.

## Scope-change rule

Feature work may refine initial behavior but may not expand this boundary. A scope change requires an explicit product update or accepted ADR and a focused Slice SDD before implementation.

## 6. P1 scope and fixed boundaries

P1 is the post-P0 stage for experience improvement and efficiency enhancement. P1 does not become a prerequisite for the completed P0 execution loop. The authoritative P1 scope is the PRD, as refined by accepted ADRs and the named Slice SDD for the capability being implemented.

The retained P1 range includes:

- Scenario and Test Plan polish, including Clone, Archive, lightweight tags, and Test Plan-only read-only execution configuration preview. Scenario Preview remains excluded.
- Resource Multi-node, Workspace/Admin, cURL Import, Dependency File Preview, Run Report Preview, Monitoring, and Debug HTTP Trace when each is activated by its own accepted Slice source.
- Debug HTTP Trace only for Debug Run, governed by `docs/sdd/adr/ADR-0008-p1-debug-http-trace.md` and `docs/sdd/slices/P1-08-debug-http-trace.md`.

P1 fixed boundaries are:

- P1 Import means cURL import only. P1 does not activate API Catalog or any OpenAPI/API Catalog-to-Scenario or Test Plan generation flow.
- P1 does not include Schedule Run, Scheduled Job, an in-product Help page, Dependency File archive extraction, or enterprise authentication/security extensions.
- Debug HTTP Trace applies only to Debug Run. It does not add Standard Run tracing, JMeter plugins, Backend Listener, Monitoring, a generic logging or sanitization framework, or runtime tar changes.
- A P1 capability must not become a prerequisite for the P0 closed loop.

Recommended Slice boundaries are Monitoring, Resource Multi-node, Workspace/Admin, Scenario/Test Plan Polish, cURL Import, Dependency Preview, Run Report Preview, and Debug HTTP Trace. Each implementation requires a named real Slice SDD with verifiable Done When criteria; this scope section does not authorize implementation by itself.
