# SurgePilot SDD Writing and Development Promotion Guidance Document

- Document status: Draft / for reference by subsequent SDD Pack and P0 development organizations
- Scope of application: Guide SurgePilot from PRD to SDD, repository skeleton, P0 vertical slice development and subsequent acceptance

---

## 1. Analysis conclusion


1. **Adjust "one large SDD" to "SDD Pack + Rolling Slice SDD"**

   SurgePilot's PRD has a large scope, covering many fields such as Web, API, Runner, Load Node, MinIO, Run state machine, permissions, Workspace, Artifacts, etc. If it is written as a huge SDD, subsequent AI development will be interfered with by irrelevant context, and it will be easier to expand P1/P2.

   A more reasonable way is:

   ```text
   PRD
     ↓
   Foundation SDD Pack
     ↓
   Repository skeleton / Contract / AGENTS.md / Verification command
     ↓
   P0 Slice SDD Rolling Supplement
     ↓
   Implement, test, review, and refill documents by vertical slices
   ```

2. **Downgrade external tool suggestions to optional processes instead of strong project dependencies**

   The external practices mentioned in the `analysis document` have reference value for the process of "clarification, planning, implementation, verification, and review". But the SurgePilot project's specifications should not rely on a specific tool. The project should be settled to:

   - `docs/sdd/` Document system;
   - `AGENTS.md` development constraints;
   - `packages/contracts` contract;
   - `make verify` or equivalent verification command;
   - Done When for each Slice.

In conclusion, you should not immediately enter "full development of the backend" or "write all detailed SDDs at once". The Foundation SDD should be completed before M0/P0-00 is started, and the detailed Slice SDD should be developed 1-2 slices ahead.

---

## 2. Why does this idea match PRD?

### 2.1 Match with the product main link

PRD clarifies that the first version of SurgePilot's closed loop is:

```text
Asset accumulation
  ↓
Test plan orchestration
  ↓
Load testing execution
  ↓
Report judgment
  ↓
Reuse iteration
```

`analysis document` It is recommended to advance by vertical slicing instead of completing the backend first, then the frontend, and then the Runner. This is consistent with PRD's closed-loop mind. Each P0 slice should try to form a verifiable end-to-end capability, rather than just completing a certain layer of technical implementation.

### 2.2 Matches P0-Core / P0-Stability

PRD clarifies that P0 is not only "running", but also must complete P0-Stability at the same time:

- Run snapshot;
- Run state machine;
- Stop idempotent;
- Runner callback is idempotent;
- Runner heartbeat timeout;
- Node release;
- Permission verification;
- Workspace isolation;
- Dependency File / artifacts path security;
- Private Load Node credentials are not echoed textually.

Therefore, `analysis document` is correct to emphasize that Runner Protocol, Run state machine, Node lease, Artifacts, permissions and path security must be designed in advance. These should not be made up as "late optimization".

### 2.3 Match with P0/P1/P2 boundary

The PRD has clarified:

- P0: Manually create Scenario/Test Plan, single-node execution, Run Report, MinIO artifacts, default Workspace, and local account;
- P1: API Catalog, cURL import, Monitoring, multi-node, Schedule Run, Workspace UI, User Management;
- P2: OIDC, Secret, desensitized, non-MinIO storage.

`analysis document` It is recommended to specifically write `00-product-scope-and-priority.md` in SDD to prevent AI from opportunistically implementing P1/P2 at P0. This is very necessary.

### 2.4 Matching with AI development methods

The most common problems in AI development are:

- The context is too large;
- unclear boundaries;
- File and interface guessing;
- Claim completion without verification;
- P1/P2 functions are implemented in advance;
- The contracts of front-end, back-end and Runner are inconsistent.

The SDD Pack, ADR, Slice SDD, AGENTS.md, Done When, plan first and then implement, and verify by slice proposed by `analysis document` are exactly aimed at these risks.

---

## 3. Things that need to be corrected or emphasized

### 3.1 PRD is still the only source of product wording

Subsequent SDD can refine the engineering implementation, but cannot cover the product boundaries of the PRD. If an SDD conflicts with a PRD, `docs/prd/PRD.md` should take precedence and be explicitly revised back to the PRD or ADR.

### 3.2 This document is only placed in the PRD directory as a guide for advancement

This file is located at `docs/prd/` and is used to guide subsequent work. Real SDD files are still recommended to be created at:

```text
docs/sdd/
```

Do not continue to pile up complete SDDs in the `docs/prd/` directory to avoid mixing PRD, guidance documents and engineering design document responsibilities.

### 3.3 Foundation SDD should be short and hard, do not write it as a second PRD

Foundation SDD should clearly write:

- Architectural boundaries;
- Contract rules;
- state machine;
- permissions;
- storage;
- test;
- Prohibited matters.

It should not repeat all page descriptions of the PRD, nor should it expand all P1/P2 details in advance.

### 3.4 Fake Runner is necessary scaffolding, but it cannot replace Runner acceptance

In the early stage of P0, fake runner can be used to open up the Run state machine and UI process, but the final acceptance of P0 must cover the real or close to real Runner protocol:

- accepted;
- running;
- heartbeat;
- artifact;
- finished;
- failed;
- aborted;
- stop idempotent;
- heartbeat timeout self-healing.

### 3.5 P0-04 should not be dragged until after page development

Run state machine and Runner Protocol are the parts with the highest technical risk. It can be implemented after the minimum structure of the Load Node, but it cannot be added after the Scenario/Test Plan/Report are completed.

---

## 4. Recommended document structure

It is recommended to create the following SDD Pack later:

```text
docs/
  prd/
    PRD.md
    SurgePilotSDDPlanningGuide.md

  sdd/
    README.md
    00-product-scope-and-priority.md
    01-architecture-overview.md
    02-repo-structure-and-dev-workflow.md
    03-domain-model-overview.md
    04-api-contract-guidelines.md
    05-runner-protocol-and-run-state-machine.md
    06-security-permission-workspace.md
    07-storage-artifacts-minio.md
    08-frontend-routing-and-ui-rules.md
    09-testing-and-acceptance-strategy.md

    adr/
      ADR-0001-monorepo.md
      ADR-0002-runner-independent-app.md
      ADR-0003-p0-minio-only.md
      ADR-0004-p0-manual-single-node-only.md
      ADR-0005-p0-no-api-catalog-no-monitoring-no-schedule.md

    slices/
      P0-00-auth-workspace-admin-setup.md
      P0-01-env-groups.md
      P0-02-dependency-files-minio.md
      P0-03-load-nodes.md
      P0-04-run-state-machine-runner-protocol.md
      P0-05-visual-scenario-debug-run.md
      P0-06-test-plan-run-now.md
      P0-07-run-report-artifacts-validity.md
      P0-08-overview-and-polish.md
      P1-README.md
      P2-README.md
```

---

## 5. Three types of SDD document responsibilities

### 5.1 Foundation SDD: Global Engineering Rules

Place it directly under `docs/sdd/`.

It answers:

- What parts does the system consist of;
- Web/API/Runner/contracts/infra boundaries;
- How to constrain P0/P1/P2;
- How the API contract is defined;
- How Runner communicates with API;
- How the Run status flows;
- How to deal with Workspace and permissions;
- How to handle MinIO, Dependency File, and artifacts;
- What are the test and acceptance commands.

### 5.2 ADR: Record of major architectural decisions

Place under `docs/sdd/adr/`.

It answers:

- Why choose monorepo;
- Why Runner is an independent application;
- Why P0 only supports MinIO;
- Why P0 only supports manual single node;
- Why does P0 not do API Catalog, Monitoring, and Schedule Run.

The ADR should document the context, alternatives, final decision, and impact and should not be written as feature implementation details.

### 5.3 Slice SDD: a developable functional slice

Place under `docs/sdd/slices/`.

It answers how a certain function is implemented:

- target;
- PRD source;
- within range;
- out of range;
- Data model;
- API contract;
- Front-end page;
- Runner/Storage/External dependencies;
- Permissions and security;
- Testing requirements;
- Done When.

Slice is a task statement for AI or R&D execution. It should be small enough, clear enough, testable, and acceptable.

---

## 6. Foundation SDD startup threshold

Before starting M0/P0-00 development, at least the following should be completed:

1. `00-product-scope-and-priority.md` Write clear P0/P1/P2 and prohibited items.
2. `01-architecture-overview.md` Write down the boundaries of Web, API, Runner, MinIO, DB, Load Node, and contracts.
3. `02-repo-structure-and-dev-workflow.md` Write down the repository structure, operation mode and verification commands.
4. `04-api-contract-guidelines.md` Write down REST, error codes, paging, workspace context, and OpenAPI rules.
5. `05-runner-protocol-and-run-state-machine.md` Write the state machine, callback, stop, heartbeat, self-healing, node lease.
6. `06-security-permission-workspace.md` Write the Admin/User, default Workspace, and Private Load Node credential rules.
7. `07-storage-artifacts-minio.md` Write MinIO only, object key, path security, and artifacts metadata.
8. `09-testing-and-acceptance-strategy.md` Write down the verification methods of API, Web, Runner, Contract, and E2E.
9. `AGENTS.md` First version rules available.
10. `P0-00-auth-workspace-admin-setup.md` is completed and can be used as the first development slice.

You can start development once you reach the above threshold, without waiting for all P0 Slice SDDs to be written.

---

## 7. Recommended development sequence

It is recommended to proceed in the following order:

| Phases | Objectives | Key Outputs |
| --- | --- | --- |
| M0 | Repository skeleton | monorepo, web/api/runner scaffold, contracts, infra, AGENTS.md, verify command |
| P0-00 | Account / Workspace / Admin Setup | Registration, login, first Admin, default Workspace, Setup Status, basic permissions |
| P0-01 | Env Groups | CRUD, workspace aware, pre-reference structure |
| P0-02 | Dependency Files + MinIO | Upload, download, deletion protection, MinIO only, path security |
| P0-03 | Load Nodes | Public/Private, credentials not echoed, status, initialization log |
| P0-04 | Run state machine + Runner Protocol | Run creation, node lease, callback idempotent, heartbeat, stop, fake runner |
| P0-05 | Visual Scenario + Debug Run | Scenario Designer minimum available, Step CRUD, Debug Run |
| P0-06 | Test Plan + Run Now | Test Plan Editor, Scenario Orchestration, Manual Single Node, SLA Subset, Run Snapshot |
| P0-07 | Run Report + Artifacts + Validity | Verdict, KPI, failed_requests, finalstats, artifacts, Valid/Invalid |
| P0-08 | Overview + P0 convergence | Overview, empty state, error state, permission completion, self-healing completion |

Key principles:

- P0-Stability does not wait for P0-Core to complete before replenishing;
- Runner Protocol and Run state machine must be preceded;
- API contracts take precedence over front-end and back-end consumers;
- Each slice must have a test and a Done When;
- P1/P2 only allows placeholders and extension points, and user-visible capabilities are not allowed in P0.

---

## 8. Each Slice SDD fixed template

Each subsequent `docs/sdd/slices/P0-xx-xxx.md` is recommended to use the following structure:

```markdown
# P0-xx: name

## 1. Goal
What can the user or system do after this slice is completed.

## 2. PRD Trace
Chapters, procedures and acceptance criteria corresponding to `docs/prd/PRD.md`.

## 3. In Scope
This time it is clear what to achieve.

## 4. Out of Scope
This time it is clear what is not implemented, especially P1/P2.

## 5. Data Model
Table, field, index, workspaceId, audit field, reference relationship.

## 6. API Contract
Interface, request, response, error code, permission error, paging or filtering.

## 7. Frontend
Pages, routes, components, states, empty states, error states, interaction constraints.

## 8. Runner / Storage / External Dependency
Whether it involves Runner, MinIO, SSH, Taurus, fake runner.

## 9. Security
Authentication, authorization, Workspace, path security, sensitive fields, and credential echo.

## 10. Tests
API testing, front-end testing, runner testing, contract testing, E2E or smoke testing.

## 11. Done When
Completion conditions. It must be verifiable, you can't just write "function completed".
```

---

## 9. AI Development Issue Template

When handing it over to AI or R&D for execution later, don't just say "achieve P0". Small scope tasks should be used.

```markdown
# Issue: P0-xx Name

## Goal
In one sentence, describe what user capabilities or system capabilities are to be completed this time.

## Context
Please read:
- docs/sdd/README.md
- docs/sdd/00-product-scope-and-priority.md
- docs/sdd/slices/P0-xx-xxx.md
- 1-2 Foundation SDDs related to this slice
- Related AGENTS.md
- Related contracts in packages/contracts

## Constraints
- Only P0 is implemented.
- Does not implement explicitly listed P1/P2 capabilities.
- Update contracts first, then implement API and front-end consumers.
- Runner must not import API internal code.
- The change scope is limited to this slice.

## Expected Changes
- apps/api/...
- apps/web/...
- apps/runner/... (if involved)
- packages/contracts/...
- tests/...

## Done When
- Contract update completed.
- API/Web/Runner corresponding test passed.
- Permissions, workspace, error handling coverage.
- lint/typecheck/test/verify passes.
- Final description of modified documents, test results, residual risks.
```

For complex slicing, it is recommended to first require AI to output an implementation plan without modifying the code; the plan can then be implemented after confirmation.

---

## 10. AGENTS.md Suggested Rules

The root directory `AGENTS.md` should write at least:

```markdown
# SurgePilot Agent Instructions

## Current target
The current delivery target is P0 only.

## Canonical documents
- Product source: docs/prd/PRD.md
- SDD entry: docs/sdd/README.md
- Scope rules: docs/sdd/00-product-scope-and-priority.md

## Required workflow
For any feature touching more than one app:
1. Read the relevant Slice SDD first.
2. Output an implementation plan before editing code.
3. Update contracts before consumers.
4. Keep the change limited to the slice.
5. Run verification commands before final response.

## P0 forbidden work
Do not implement these unless the issue explicitly says P1/P2:
- API Catalog
- cURL import
- Monitoring / Grafana / InfluxDB
- Schedule Run
- Multi-node execution
- Resource Auto allocation
- Workspace switching UI
- User Management UI
- System Settings UI
- Env Group Secret
- OIDC / SSO
- Non-MinIO storage

## Architecture constraints
- apps/runner is an independent application.
- runner must not import apps/api internal code.
- API and runner communicate through packages/contracts.
- Frontend must not invent API shapes outside OpenAPI/contracts.
```

Subdirectories can be added separately:

- `apps/api/AGENTS.md`
- `apps/web/AGENTS.md`
- `apps/runner/AGENTS.md`
- `packages/contracts/AGENTS.md`

---

## 11. Refill rules after each slice is completed

After each Slice implementation is completed, the corresponding documentation should be updated:

1. The actual implementation is inconsistent with the original SDD;
2. Newly added or adjusted API contracts;
3. New test and verification commands;
4. Residual risk;
5. Preconditions that need to be known for subsequent Slice;
6. If major architectural choices arise, add ADR.

SDD should be a living document, but updates must serve engineering facts and cannot be used as an opportunity to expand product scope.

---

## 12. Review Checklist

In subsequent SDD or code reviews, check the following first:

- Whether it deviates from the PRD;
- Whether to realize P1/P2 in advance;
- Is the workspaceId or Workspace context missing?
- Is there only a hidden permission entry on the frontend and no verification on the backend?
- Whether to save Run Snapshot;
- Whether to ensure Runner callback is idempotent;
- Whether the Terminal state will be overwritten by late callback;
- Whether Stop is idempotent;
- Whether the Load Node will be permanently Busy;
- Whether Dependency File/artifacts have path traversal risks;
- Whether Private Load Node credentials may be echoed in clear text;
- Whether the frontend guesses the interface rather than based on the contract;
- Test whether state transitions, permissions, errors and boundaries are covered;
- Whether Done When can be verified via command or manual process.

---

## 13. Final recommendations

The subsequent optimal route is:

```text
1. Create docs/sdd Foundation SDD Pack based on PRD.
2. Create ADR, first lock the monorepo, Runner independent, P0 MinIO only, P0 single node, P0 disables P1/P2.
3. Create three Slice SDDs P0-00 / P0-01 / P0-02.
4. Create the repository skeleton, contracts, AGENTS.md and verify command.
5. Develop in vertical slices starting from P0-00.
6. Test, review, and refill SDD/ADR after each slice is completed.
```

One sentence principle:

> **Foundation SDD writes the foundation once and for all; Slice SDD leads to rolling development; the code is advanced according to P0 vertical slices; all completions must be verifiable. **
