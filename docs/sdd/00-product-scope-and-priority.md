# 00. Product Scope and Priority

## Purpose

This document is the initial milestone scope gate. It prevents future-product ideas from becoming partially implemented before the core execution loop and its safety properties are complete.

## Initial delivery target

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
