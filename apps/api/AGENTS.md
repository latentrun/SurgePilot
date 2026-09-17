# API Agent Notes

- Follow root `AGENTS.md` and `docs/sdd/02-repo-structure-and-dev-workflow.md`.
- This file is subordinate to `/AGENTS.md`; when conflicts occur, follow root AGENTS and the referenced SDD.
- Follow root verification gates and `docs/sdd/09-testing-and-acceptance-strategy.md` for test expectations.
- API owns auth, authorization, Workspace enforcement, database, MinIO access, and audit-relevant decisions.
- Keep public business routes under `/api/v1`; keep health endpoints at `/api/healthz` and `/api/readyz`.
- API JSON fields use `camelCase`; DB columns, ORM fields, and migrations use `snake_case`.
- External business IDs are ULID strings; store ULID IDs in the DB as `text` or `char(26)`, not PostgreSQL `uuid`.
- FastAPI/Pydantic routes are the OpenAPI source of truth; run `make generate-contracts` after API schema changes.
- ADR-0016/P2-04 skill download is a session-authenticated, non-Workspace account read that appears only in `api.openapi.json`; its source-unavailable code stays route-local. The first-Admin system OpenAPI import must run after registration commit in an independent session and must never affect registration success.
- Do not import Web or Runner internals; add P1 endpoints only when a named accepted P1 Slice SDD is active, and keep them inside that Slice.
