# 03. Domain Model Overview

## Ownership and identity

External business identifiers are ULID strings. Most business records carry `workspace_id` and are queried through a resolved Workspace context. Public Load Nodes are the deliberate exception: they are platform-owned and can be made visible to eligible Workspaces. Private Load Nodes remain Workspace-owned.

## Core model

```text
User --< WorkspaceMember >-- Workspace
                              |--< EnvGroup
                              |--< DependencyFile
                              |--< Scenario --< ScenarioStep
                              |--< TestPlan --< TestPlanScenario >-- Scenario
                              |--< Private LoadNode
                              `--< Run --1 RunSnapshot
                                     |--1 NodeLease >-- LoadNode
                                     |--< RunnerCallbackEvent
                                     `--< Artifact

Platform --------------------------< Public LoadNode
```

- A Scenario defines an ordered reusable business flow.
- A Test Plan references one or more Scenarios and owns load and SLA configuration.
- A Run is an execution record, not a live alias to a Test Plan.
- RunSnapshot captures every execution-relevant value at Run creation.
- NodeLease prevents concurrent use of the selected Load Node.
- RunnerCallbackEvent provides callback deduplication and diagnosis.
- Artifact metadata is authoritative in PostgreSQL; bytes live in MinIO.

## State separation

Run lifecycle (`initializing`, `running`, `stopping`, `finished`, `failed`, `aborted`), SLA verdict (`passed`, `failed`, `not_evaluated`), and user validity (`valid`, `invalid`) answer different questions and remain separate fields.

Detailed columns, constraints, indexes, and endpoint DTOs belong to the Slice that introduces each model. The foundation requires Workspace isolation, immutable Run snapshots, unique active node leases, terminal-state protection, and reference-aware deletion.
