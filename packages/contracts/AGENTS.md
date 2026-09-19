# Contracts Agent Instructions

Scope: `packages/contracts/**`.

Inherits `/AGENTS.md`. This file adds contract-specific constraints and review rules. Consult
`docs/sdd/04-api-contract-guidelines.md` for public or internal contract changes.

- OpenAPI and generated clients are produced from API-owned FastAPI/Pydantic sources and are never
  hand-edited.
- Changes under generated OpenAPI/client paths come from `make generate-contracts`; stale checks
  must fail when committed artifacts disagree with their source.
- Browser/session, public PAT, and internal Runner surfaces remain explicitly separated.
- Web consumes this package only through the `@surgepilot/contracts` workspace dependency.
- Runner callbacks follow the governed Runner callback schema and protocol.

## Code Review Rules

- Flag generated changes without the corresponding source-schema change.
- Flag internal, session-only, token-management, plaintext-secret, or Runner routes leaking into the
  public artifact.
- Flag public operations that lack stable identifiers or governing scope.
- Flag consumer changes submitted with stale contract artifacts.
