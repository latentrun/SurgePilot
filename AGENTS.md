# SurgePilot AI Development Instructions

This file is authoritative for AI contribution behavior across the repository. Product behavior and
technical design remain authoritative in the applicable PRD, Foundation/Slice SDDs, and accepted
ADRs. See `docs/sdd/ai-development-governance-optimization-design.md` for this instruction model.

## Mandatory constraints

Every change must satisfy all of these constraints:

1. The applicable accepted product/design sources authorize the work.
2. Approved behavior, persistent data, Run/state-machine safety, idempotency, Workspace isolation,
   credential/path safety, authentication, authorization, and documented fail-closed behavior do
   not regress.
3. Contracts, generated artifacts, tests, and affected design documents agree with the final
   implementation.
4. Material facts come from authoritative documents, code, tests, or real provider/runtime
   behavior. Report required checks that cannot run as `NOT VERIFIED`.

No engineering preference may override these constraints.

## Engineering choices

Among solutions that satisfy every mandatory constraint, use this order:

1. **No over-engineering.** Implement the simplest solution for the current approved need.
2. **User and operational simplicity.** Prefer fewer steps and settings, predictable defaults, and
   direct recovery.
3. **Minimum diff and reuse.** Reuse existing project and upstream primitives. Keep unrelated
   cleanup, renaming, reorganization, and refactoring out of the change.
4. **YAGNI.** Add abstractions, registries, factories, feature flags, compatibility layers, parallel
   implementations, queues, services, or dependencies only for a current approved requirement.
5. **Demand-driven compatibility.** Add historical compatibility only for an identified user,
   persistent-data, or public-contract requirement. Prefer an approved direct migration or
   correction when simpler.
6. **Demand-driven hardening.** Preserve established security controls. Introduce additional
   security platform work through a concrete requirement, defect, or ADR.

Default rule: choose the smallest, simplest, verifiable implementation that satisfies the current
approved design and every mandatory invariant.

## Sources of truth and scope

- Product source: `docs/prd/PRD.md`.
- SDD entry and task discovery: `docs/sdd/README.md`.
- Product scope gate: `docs/sdd/00-product-scope-and-priority.md`.
- P1 and P2 active-Slice discovery: `docs/sdd/slices/P1-README.md` and
  `docs/sdd/slices/P2-README.md`.
- Architecture and ownership: `docs/sdd/01-architecture-overview.md`.
- Repository workflow: `docs/sdd/02-repo-structure-and-dev-workflow.md`.
- API contracts: `docs/sdd/04-api-contract-guidelines.md`.
- Runner protocol and Run state: `docs/sdd/05-runner-protocol-and-run-state-machine.md`.
- Security and Workspace: `docs/sdd/06-security-permission-workspace.md`.
- Storage and artifacts: `docs/sdd/07-storage-artifacts-minio.md`.
- Frontend routing and UI: `docs/sdd/08-frontend-routing-and-ui-rules.md`.
- Testing and acceptance: `docs/sdd/09-testing-and-acceptance-strategy.md`.

A capability is implementable only when an accepted Slice SDD or ADR explicitly authorizes it.
Partial code, routes, navigation, proposals, and future enum values do not activate scope. Indexes
help discover authority but do not authorize implementation by themselves. Existing code is
evidence, not design authority.

If approved product behavior, a public contract, component ownership, persistent data, Run/state
behavior, or an architectural boundary must change, update the owning PRD/SDD/ADR before or in the
same explicitly approved change. Editing a document status does not grant approval. A bug fix that
restores documented behavior does not require unrelated design churn.

## Context loading

Always read this file and the `AGENTS.md` in every affected subtree. Then load the smallest context
that completely governs the task:

<!-- governance-route:named-feature -->
- **Named feature/Slice:** read the named Slice, activating/amending ADRs, and direct Foundation,
  contract, code, and test dependencies.
<!-- governance-route:feature-without-slice -->
- **Feature without a named Slice:** read the SDD entry, scope gate, and relevant P1/P2 index.
  Proceed only when an accepted Slice/ADR clearly authorizes it; otherwise stop at the scope gate.
<!-- governance-route:bug-fix -->
- **Bug fix:** read the owning Foundation or Slice SDD and every amendment that changes the
  established behavior, followed by relevant code, contracts, and tests.
<!-- governance-route:cross-subtree -->
- **Cross-subtree changes:** read each affected nested instruction file and update contract sources
  before consumers.
<!-- governance-route:source-full-stack -->
- **Generic source startup or restart:** read the Cross-platform Distribution and LAN-first sources
  listed by the P2 index, then use `make start-full-stack` or `make restart-full-stack`.
<!-- governance-route:source-preview -->
- **Preview-only UI or control-plane work:** read the Source Preview amendment listed by the P2
  index, use `make start-preview`, and state that preview does not promise Load Node initialization
  or Run execution readiness. Stop it with `make stop-preview`.
<!-- governance-route:two-node-ssh -->
- **Two-node SSH manual demo:** read the Resource Multi-node and Cross-platform Distribution sources,
  then use `make start-full-ssh-e2e`. Use the build variant only when the SSH image must be rebuilt.
<!-- governance-route:tagged-release -->
- **Tagged-release operations:** read the installer and LAN-first sources from the P2 index, plus
  `docs/site/docs/quickstart.md`, `docs/site/docs/startup-modes.md`, and
  `docs/site/docs/configuration.md`.
  Installed releases use `surgepilot up|down|status|logs`; manually extracted bundles use
  `./surgepilot`.
<!-- governance-route:governance-change -->
- **Governance or instruction changes:** read the governance optimization design, this file, the
  repository/workflow SDD, relevant indexes, and governance tests.

Do not read the complete PRD/SDD set by default. Extra documents do not expand task scope. If
sources conflict, resolve the documentation inconsistency before implementing conflicting behavior.

## Stable architecture and safety invariants

- The repository is a monorepo. `apps/api`, `apps/web`, and `apps/runner` are separate applications.
- Runner is independent and must not import API internals. API and Runner communicate only through
  documented protocol/contracts.
- Web consumes API shapes through `@surgepilot/contracts`; it does not invent DTOs or access
  PostgreSQL, MinIO, Load Nodes, or Runner endpoints directly.
- API owns database and MinIO access, authentication, authorization, Workspace enforcement, and
  audit-relevant decisions. Runner owns process execution and reports through callbacks.
- Session/business routes remain under `/api/v1`, public PAT routes under `/api/public/v1`, and
  health endpoints at `/api/healthz` and `/api/readyz`.
- Workspace checks and permission checks are enforced by the backend. Private credentials are never
  returned in plaintext.
- Dependency File and artifact paths remain traversal-safe. Run callbacks cannot overwrite terminal
  state, Stop remains idempotent, and failure paths release Load Node leases.
- Fake Runner may support development and tests but cannot replace required real or near-real Runner
  acceptance.

## Contract-first workflow

- FastAPI routes and Pydantic schemas are the source for generated OpenAPI.
- Generated OpenAPI, Web client/types, and Runner callback schemas are never hand-edited.
- Web consumes generated artifacts through the workspace package, never through relative imports
  into generated directories.
- Keep session/business, public PAT, and internal Runner surfaces explicitly separated. Internal or
  secret-bearing schemas must not leak into public OpenAPI.
- Make API schema/contract changes before Runner or Web consumers and run
  `make generate-contracts`.
- `make verify` must detect stale generated contracts and OpenAPI artifacts.

API JSON uses `camelCase`; database/ORM/migration fields use `snake_case`; API enum values use lower
`snake_case`. External business IDs are ULID strings stored as text/`char(26)`. Time values use ISO
8601 UTC with `Z`. Use `x-workspace-id`, `x-csrf-token`, `x-runner-token`, and `x-request-id` according
to their governing contract; do not move Workspace identity into route paths.

## Development workflow

### Git workspace rule

Each new implementation task follows this isolation model:

```text
1 task = 1 branch + 1 worktree + 1 PR
```

Before starting a new implementation task:

1. Run `git fetch origin`.
2. Start from the current `origin/main`.
3. Create a dedicated task branch from `origin/main`.
4. Create a dedicated worktree for that branch.
5. Perform all implementation work inside that worktree.
6. Never implement new work directly on `main`.
7. Never reuse another task's branch or worktree.

Follow-up fixes for an existing open PR stay on that PR's branch, worktree, and PR unless
explicitly requested otherwise.

For a feature touching more than one application:

1. read the governing Slice and affected nested instructions;
2. provide an implementation plan before editing;
3. update contract sources before consumers;
4. keep the change within the accepted Slice;
5. verify focused behavior during implementation and run repository gates before completion;
6. update an SDD/ADR only when design or implementation facts changed.

Simple bug fixes may proceed directly while preserving the same scope, contract, safety, and
verification rules.

Runtime versions are managed with `mise`; respect existing project version declarations and keep
global defaults unchanged. Use `uv` and the project `.venv` for Python dependencies. Keep Node
dependencies project-local and respect the existing package manager and lockfile. Run Java commands
that require `JAVA_HOME` through `mise exec --`. Swift uses the Xcode toolchain.

Use existing repository commands as the executable source of truth. Detailed source/release startup
and recovery semantics belong to their owning SDDs and runbooks; do not copy them into this file.

## Verification and evidence

Prefer repository entry points:

```bash
make generate-contracts
make verify
```

Use `make verify-e2e` for nightly, release, or main-merge validation when the environment provides
its external dependencies. Slice-specific docs may require additional focused checks. Run focused
tests while developing; run the full applicable suite once after the final change.

Before claiming completion:

- review the complete diff and remove unrelated or speculative work;
- confirm the change stays inside accepted scope;
- confirm affected generated artifacts are current;
- verify Workspace, permission, path, credential, Run-state, Stop, and lease-release invariants in
  every touched path;
- record commands and results, including any required check marked `NOT VERIFIED`;
- update the governing Slice only for actual implementation differences, contracts, verification,
  remaining risks, or prerequisites; do not use backfill to expand scope.

Final responses include changed files, verification commands/results, and remaining risks or
`None`.

## Language and generated files

Source code, identifiers, comments, logs, API/error messages, examples, seed data, test names, and
commit messages use English. API `message` is English fallback text; frontend localization keys off
stable error codes. SDD prose may be Chinese, but code examples inside documents use English.

Do not hand-edit generated OpenAPI, generated Web clients/types, compiled output, coverage output,
Runtime artifacts, or vendored dependencies. Change the owning source and regenerate through the
documented command.

## Code Review Rules

Review repository-wide changes for:

- implementation outside accepted scope or behavior not backed by the governing design;
- unnecessary architecture, compatibility, security platform work, dependencies, or parallel paths;
- contract consumers changed before or without their source contract;
- cross-component ownership violations;
- regressions in persistent data, Run state, idempotency, Workspace, permission, credential, or path
  safety;
- generated/source drift, missing verification evidence, or required checks silently skipped;
- unrelated cleanup that obscures the requested change.

Apply additional review rules from every affected nested `AGENTS.md`.
