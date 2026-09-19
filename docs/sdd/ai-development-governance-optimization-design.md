# AI Development Governance Optimization Design

- Decision status: Accepted for implementation
- Change control: Frozen for Issues #37-#41; later design changes require explicit approval
- Approved: 2026-09-19
- Target repository: `latentrun/SurgePilot`
- Product/runtime behavior impact: None

## 1. Decision

SurgePilot treats repository instructions as an engineering control plane. The current root
`AGENTS.md` is larger than Codex's default combined project-instruction budget, duplicates product
and design sources, and competes with more local instructions for context.

Replace that model with this hierarchy:

```text
PRD / Foundation SDD / Slice SDD / ADR
    Approved product behavior and technical design

Root AGENTS.md
    Repository-wide AI engineering policy, invariants, workflow, and completion gates

Nested AGENTS.md
    Stable constraints and review rules for one subtree

Indexes / runbooks / focused SDD sections
    Detailed task-specific scope and operating procedures loaded on demand
```

The root file is an AI engineering constitution. It is not a release-history ledger, a complete
Slice registry, or a deployment runbook.

## 2. Decision model

### 2.1 Mandatory constraints

Every implementation must satisfy all of these constraints:

1. Work is authorized by the applicable accepted product/design sources.
2. Approved behavior, persistent data, state-machine safety, idempotency, Workspace isolation,
   credential/path safety, authentication, authorization, and documented fail-closed behavior do
   not regress.
3. Contracts, generated artifacts, tests, and affected design documents agree with the final
   implementation.
4. Material facts are verified from authoritative documents, code, tests, or real provider/runtime
   behavior. Required checks that cannot run are reported as `NOT VERIFIED`.

No engineering preference may override these constraints.

### 2.2 Engineering choice order

Among solutions that satisfy every mandatory constraint, choose in this order:

1. **No over-engineering.** Use the simplest solution that satisfies the current approved need.
2. **User and operational simplicity.** Prefer fewer steps, fewer settings, predictable defaults,
   and direct recovery.
3. **Minimum diff and reuse.** Reuse existing project and upstream primitives; avoid unrelated
   cleanup, renaming, reorganization, or refactoring.
4. **YAGNI.** Add abstractions, registries, factories, feature flags, compatibility layers,
   parallel implementations, queues, services, or dependencies only for a current approved need.
5. **Demand-driven compatibility.** Add historical compatibility only for an identified user,
   persistent-data, or public-contract requirement. Prefer an approved direct migration or
   correction when it is simpler.
6. **Demand-driven hardening.** Preserve all established security controls. Introduce additional
   security platform work through a concrete requirement, defect, or ADR.

Default rule: choose the smallest, simplest, verifiable implementation that satisfies the current
approved design and every mandatory invariant.

## 3. Authority and lifecycle

### 3.1 Responsibility by artifact

| Artifact | Owns | Does not own |
| --- | --- | --- |
| PRD | Product behavior, scope, and product non-goals | AI workflow mechanics |
| Foundation SDD | Stable cross-cutting technical design | Dynamic task instructions |
| Slice SDD | One bounded capability's approved behavior and design | Repository-wide AI policy |
| ADR | One explicit design decision or amendment | General coding style |
| Root `AGENTS.md` | AI contribution policy and repository-wide invariants | Roadmap history and detailed runbooks |
| Nested `AGENTS.md` | Stable rules for one subtree | Root repetition and unrelated scope history |
| Index/runbook | Task discovery or detailed operational procedure | Always-on repository policy |

Existing code is evidence, not design authority. When code conflicts with an accepted design, the
conflict must be resolved explicitly rather than silently treating either side as correct.

### 3.2 Lifecycle state

Use lifecycle state and release-baseline membership as separate fields:

- **Draft**: may be edited and reviewed when explicitly requested, but does not authorize product
  implementation. Explicit approval may transition it to **Accepted**; changing metadata only
  records approval that already exists.
- **Accepted**: approved authority within its stated scope.
- **Superseded**: replaced; it names the replacement source.

A **released baseline** is pinned to a verified commit SHA resolved from its named release tag. A
live document may say which release and which bounded sections it governed, but release membership
does not activate future scope contained in the same document. Do not use `Frozen` as a substitute
for lifecycle state. If the term is used, it means only that a commit-pinned baseline or an accepted
decision is change-controlled.

Editing a status field does not approve a document. Approval comes from an explicit user decision or
an already accepted governance mechanism such as an ADR. An AI may record that approval after it
exists; it may not create approval by editing metadata.

### 3.3 Design changes

When work changes approved product behavior, public contract semantics, component ownership,
persistent data, Run/state behavior, or an accepted architectural boundary:

1. update the owning PRD/SDD/ADR before or in the same approved change;
2. review the design against the mandatory constraints and engineering choice order;
3. obtain or record approval through the repository's governance mechanism;
4. implement the smallest matching change;
5. update contracts, generated artifacts, tests, and affected documentation;
6. verify that implementation and design agree.

A bug fix that restores documented existing behavior does not require unrelated design churn.

## 4. Instruction architecture and budgets

### 4.1 Root instructions

The root `AGENTS.md` contains only stable rules needed by nearly every development task:

- authority and decision model;
- scope activation and context routing;
- stable component ownership and security invariants;
- contract-first workflow;
- implementation workflow and verification gates;
- language and generated-file rules;
- definition of done and repository-wide review rules.

It must remain below 20 KiB. Shorter is preferred when it preserves complete routing and invariants;
12-18 KiB is guidance, not a filling target.

### 4.2 Nested instructions

Each nested `AGENTS.md`:

- declares its filesystem scope;
- inherits the root instructions;
- contains only stable local constraints and local review rules;
- points to a focused source only when most work in that subtree needs it;
- omits dynamic release/Slice history and root repetition;
- normally remains below 4 KiB.

Every root-plus-child instruction chain must remain below Codex's default 32 KiB combined budget.
More local instructions specialize or tighten the root for their subtree; they cannot weaken a
repository-wide invariant. Apparent conflict is a documentation defect to resolve before
implementation.

### 4.3 Detailed procedures

Active Slice registries, release startup details, installer behavior, public-launch procedures,
environment-specific E2E procedures, and long scope matrices live in their owning indexes, SDDs,
ADRs, or runbooks. Root instructions contain concise trigger-based pointers to them.

## 5. Context routing

Load the smallest context that completely governs the task:

| Task | Required route |
| --- | --- |
| Named feature/Slice | Root and every affected nested `AGENTS.md`; named Slice; its activating/amending ADRs; direct Foundation, contract, code, and test dependencies |
| Feature without a named Slice | SDD entry, scope gate, and relevant P1/P2 index; proceed only if an accepted Slice/ADR clearly authorizes it, otherwise stop at the scope gate |
| Bug in established behavior | Owning Foundation or Slice SDD plus every amendment that changes that behavior; relevant code/contracts/tests |
| Cross-subtree change | Root plus each affected subtree's `AGENTS.md`; update contract sources before consumers |
| Generic source startup/restart | Cross-platform Distribution and LAN-first startup sources; use the official full-stack entry |
| Preview-only UI/control-plane request | Source Preview amendment and its operating source; use the official preview entry and state its readiness limits |
| Two-node SSH manual demo | Resource Multi-node and Cross-platform Distribution sources; use the official two-node SSH manual-review entry |
| Tagged-release install/start/stop/status/logs | User-local installer and LAN-first release sources plus `docs/site/docs/quickstart.md`, `docs/site/docs/startup-modes.md`, and `docs/site/docs/configuration.md` |
| Governance/instruction change | This design, repository/workflow SDD, SDD entry/indexes, affected instructions, and governance tests |

Do not load the complete PRD/SDD pack by default. Reading extra documents does not expand task scope.
For tasks touching several directories, read the applicable instruction file in every affected path,
not only the instruction file nearest the initial working directory.

## 6. Scope activation

A capability is implementable only when an accepted Slice SDD or ADR explicitly authorizes it.
Roadmaps, placeholders, proposals, navigation stubs, partial code, and future enum values do not
activate scope. An index helps discover authority but does not authorize implementation by itself.

For feature work, the task or discovery route must identify the active Slice. For bug fixes, restore
documented behavior without adding a new capability. If the sources are inconsistent, resolve the
documentation inconsistency before implementing conflicting behavior.

## 7. Migration design

The authority cutover is one wide governance refactor and must remain green as a unit:

1. add this accepted design to the SDD set;
2. replace the root instruction body with the compact constitution;
3. replace the synchronized copy in the repository/workflow SDD with instruction-architecture
   guidance and pointers;
4. make the SDD entry and P1/P2 indexes sufficient discovery surfaces;
5. update Slice acceptance clauses and revision protocols that require dynamic duplication in root;
6. migrate contract tests that assert copied prose so they verify authority, routing, and retained
   behavior instead;
7. normalize nested instruction files as local deltas;
8. audit the v1.0.0 lifecycle and record bounded release-baseline membership;
9. run task-facing governance scenarios and repository verification.

Deleting old assertions without a replacement acceptance check is not a migration.

## 8. v1.0.0 lifecycle audit

Resolve `v1.0.0` during the audit and record:

- the tag commit;
- which product/Foundation/Slice/ADR sources governed shipped behavior;
- the bounded sections or capabilities included in the released baseline;
- future, inactive, proposal, or known inconsistent content excluded from that baseline;
- any unresolved mismatch as follow-up rather than silently changing history.

The audit resolved `v1.0.0` to commit
`37cc8e4a16590f3c67403312b680a64309e61637`; baseline identity is pinned to that commit SHA. Live
documents use `Draft`, `Accepted`, or `Superseded` and may evolve through explicit design changes.

## 9. Acceptance scenarios

The migration is complete only when these task simulations reach the correct sources and decision:

1. **Small bug**: loads the owning established design and restores behavior without activating scope.
2. **Cross-application contract change**: loads every affected subtree rule and updates contract
   sources before consumers.
3. **Full-stack startup**: selects `make start-full-stack` and preserves Runtime/Demo readiness.
4. **Preview-only startup**: selects `make start-preview` and reports that Run readiness is not
   promised.
5. **Unauthorized capability**: stops at the scope gate even when roadmap text, partial code,
   navigation, or an enum suggests the capability.

Governance tests should observe these public task-facing outcomes and stable authority relationships,
not exact paragraphs or incidental document layout.
Root context routes carry stable `governance-route:*` markers so tests can associate a task trigger
with its required outcome without depending on Markdown headings, list syntax, or editorial labels.

## 10. Definition of done

This governance change is complete when:

- the root instruction file is below 20 KiB and each nested file is below 4 KiB;
- every root-plus-child chain is below 32 KiB;
- one source owns each rule and every moved rule has a trigger-based pointer;
- no synchronized full copy of root instructions remains;
- no dynamic Slice/ADR registry remains in always-on instructions;
- stable component, contract, security, language, generated-file, and verification invariants remain
  enforceable;
- the lifecycle audit distinguishes approval from release inclusion;
- all five acceptance scenarios pass;
- affected contract/documentation checks and full repository verification pass;
- the complete diff contains no product behavior change or unrelated cleanup;
- unavailable required environment checks are explicitly marked `NOT VERIFIED`.

## 11. Work items

- #37 finalizes and freezes this implementation design.
- #38 performs the root authority and routing cutover.
- #39 normalizes nested instructions.
- #40 audits the v1.0.0 document lifecycle.
- #41 verifies the complete migrated governance system.
