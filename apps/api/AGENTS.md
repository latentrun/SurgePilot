# API Agent Instructions

Scope: `apps/api/**`.

Inherits `/AGENTS.md`. This file adds API-specific constraints and review rules.

- API owns authentication, authorization, Workspace enforcement, database and MinIO access, and
  audit-relevant decisions.
- FastAPI routes and Pydantic schemas are the source of generated OpenAPI. Run
  `make generate-contracts` after schema changes.
- Keep browser-session/business, public PAT, health, and internal Runner surfaces separated by the
  governing API contract. A route may omit Workspace context only when its accepted design says so.
- API JSON uses `camelCase`; database, ORM, and migration fields use `snake_case`.
- External business IDs are ULIDs stored as text/`char(26)`, never PostgreSQL UUIDs.
- API does not import Web or Runner internals.

## Code Review Rules

- Flag missing backend Workspace/permission enforcement even when the UI already restricts access.
- Flag secret-bearing, session-only, or internal Runner schemas exposed through public OpenAPI.
- Flag route behavior or error semantics that lack authority in the owning contract/Slice.
- Flag schema changes whose generated OpenAPI and clients were not refreshed.
