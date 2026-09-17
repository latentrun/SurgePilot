# ADR-0001: Monorepo

- Status: Accepted
- Scope: Repository structure, contracts, local development, and P0 delivery workflow

## Context

SurgePilot P0 is a small but multi-component system: Web, API, Runner, contracts, migrations, Docker Compose, and documentation must evolve together. Contract-first development requires API schema changes, generated Web client updates, Runner callback schemas, and tests to remain synchronized. P0 also needs fast local setup for AI and human contributors without introducing microservice release processes.

## Options Considered

1. **Single monorepo**
   - Pros: one change can update API, Web, Runner, contracts, tests, and docs; simpler local development; shared verification commands; easier contract freshness checks.
   - Cons: requires clear ownership boundaries so components do not import each other's internals.
2. **Multiple repositories by application**
   - Pros: independent repository permissions and release cadence.
   - Cons: contract updates span repos, local setup is slower, and P0 coordination overhead increases.
3. **Microservice-style split from the start**
   - Pros: stronger deployment isolation.
   - Cons: violates P0 simplicity, introduces integration and release complexity, and encourages infrastructure that P0 explicitly forbids.

## Decision

P0 uses a monorepo.

The repository contains `apps/web`, `apps/api`, `apps/runner`, `packages/contracts`, `infra`, tests, and SDD/ADR documentation. Monorepo does not mean unrestricted imports. Component boundaries remain mandatory:

1. Web consumes generated client/types through `@surgepilot/contracts` and calls only API.
2. Runner is independent and does not import API internals.
3. API and Runner communicate through documented contracts and HTTP protocol.
4. Generated OpenAPI artifacts live in `packages/contracts` and are refreshed by `make generate-contracts`.
5. Repository-level verification uses `make verify` as the default gate.
6. Architectural boundaries must be backed by mechanical checks where the repository can enforce them. Generated-contract freshness is part of `make verify`; P0 work that creates cross-app import risk must add or preserve static checks such as Web restricted-import lint rules or Python import-boundary tests for Runner/API separation.

## Consequences

Positive consequences:

1. P0 Slice work can update contracts, implementations, tests, and docs in one reviewable change.
2. Contract freshness checks can run in the same CI/worktree as API and Web changes.
3. Local Docker Compose and Make targets cover the whole P0 system.
4. AI contributors have one canonical context and one verification entrypoint.

Costs and constraints:

1. The repo must enforce architectural boundaries through AGENTS instructions, tests, imports, and review.
2. Large unrelated changes must still be scoped by Slice and not committed together.
3. Future repository splits require a superseding ADR and migration plan.
4. Monorepo must not be used as a justification for sharing API internal code with Web or Runner.

## Related ADRs

- `ADR-0002-runner-independent-app.md`
- `ADR-0003-p0-minio-only.md`
- `ADR-0006-p0-separate-api-worker.md`

## References

- `docs/sdd/01-architecture-overview.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `docs/sdd/04-api-contract-guidelines.md`
- `docs/sdd/09-testing-and-acceptance-strategy.md`
- `AGENTS.md`
