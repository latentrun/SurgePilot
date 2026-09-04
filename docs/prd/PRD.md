# SurgePilot Product Requirements

## Product definition

SurgePilot is a performance load-testing platform built on Taurus execution capabilities. It helps engineering, QA, and performance teams turn API and business flows into reusable Scenarios, arrange those Scenarios into Test Plans, execute them on managed Load Nodes, and judge the result from a traceable Run Report.

The product loop is:

```text
Asset accumulation -> Test Plan arrangement -> Run execution -> Report judgment -> Reuse
```

SurgePilot is not a Taurus YAML editor, a simple JMeter launcher, a script-upload utility, or an artifact browser. Taurus is an execution compatibility layer; product language remains centered on the user's test intent.

## Users and goals

- Engineers and QA create reusable request flows, debug them, and inspect failures.
- Performance engineers define load and SLA expectations, execute tests, and judge reports.
- Resource managers register and maintain platform Public Load Nodes.
- Administrators initialize the deployment and review setup health.
- Observers inspect recent Runs and their reports.

The initial milestone must let a user manually create a Scenario and Test Plan, select one available Load Node, start a Run, stop it safely, and inspect the resulting verdict, diagnostics, logs, and artifacts.

## Core concepts

| Concept | Meaning |
| --- | --- |
| Workspace | Isolation boundary for a team's business assets |
| Scenario | Reusable definition of what to test |
| Env Group | Reusable environment variables used by a Scenario or Run |
| Dependency File | Reusable input needed during execution |
| Test Plan | Arrangement of Scenarios, load settings, resources, and SLA rules |
| Load Node | Machine capable of hosting Runner and executing a Run |
| Run | One immutable execution record created from a snapshot |
| Run Report | Verdict-first view of a Run, followed by diagnostics and artifacts |

Every business asset belongs to a Workspace except a Public Load Node, which is platform-owned and visible for eligible Workspace use. Private Load Nodes belong to a Workspace. Platform setup health is also platform-level read-only information, not a Workspace business asset.

## Product requirements

### Reusable assets

Users can create and maintain Env Groups, Dependency Files, visual Scenarios, and Test Plans. Reference checks prevent deletion while an asset is in active use. Scenario describes what to test; Test Plan describes how to execute it and what counts as acceptable.

### Execution

A Run stores an immutable snapshot of the selected Test Plan, its Scenarios, environment, dependencies, load settings, SLA rules, and selected node. Initial execution uses one manually selected Idle Load Node. The product must prevent duplicate starts, conflicting node use, stuck leases, and terminal-state regression.

### Report judgment

Run Report answers, in order: whether execution completed, whether the result passed its SLA, whether the Run is considered valid, and why it failed when it did. Artifacts and logs support diagnosis but are not the report's primary hierarchy.

### Accounts and administration

Local email/password registration initializes the first administrator. Authentication, Workspace isolation, and server-side authorization apply from the start. Admin Setup Status exposes non-secret deployment readiness without weakening normal Workspace checks.

## Initial scope

The initial product includes local accounts, a Default Workspace, Overview, Env Groups, Dependency Files, Load Nodes, visual Scenarios, Test Plans, Run Now and Debug execution, Stop, Run history, Run Report, validity marking, MinIO artifacts, and read-only setup health.

The following are explicitly excluded from the initial milestone:

- automatic or multi-node allocation, resource queues, and scheduled Runs;
- API Catalog, OpenAPI import/generation, and cURL import;
- monitoring integrations, live APM, and time-series dashboards;
- enterprise SSO and complex multi-tenant permissions;
- AI scenario generation, tuning, or report analysis;
- non-MinIO storage and a self-developed replacement for Taurus;
- raw JMX upload, standalone script mode, and editable Taurus YAML.

Future documents may describe these as roadmap items, but initial implementation must not expose routes, endpoints, tables, services, or hidden usable behavior for them.

## Success and acceptance

The initial milestone succeeds when a new user can complete the manual closed loop without needing Taurus-specific knowledge, distinguish Scenario, Test Plan, Run state, SLA verdict, and validity, and recover safely from Stop, runner timeout, and node failure paths. The same flow must be testable with a fake Runner and accepted with a real SSH Runner profile.
