# Contracts Agent Notes

- Follow root `AGENTS.md` and `docs/sdd/04-api-contract-guidelines.md`.
- This file is subordinate to `/AGENTS.md`; when conflicts occur, follow root AGENTS and the referenced SDD.
- Follow root verification gates and `docs/sdd/09-testing-and-acceptance-strategy.md` for test expectations.
- `packages/contracts/openapi/api.openapi.json` is generated from FastAPI and must not be hand-written.
- `packages/contracts/generated/web-client/` is generated from OpenAPI and must not be hand-written.
- Changes under `openapi/` and `generated/` must come from `make generate-contracts`.
- ADR-0016/P2-04 adds the account AI skill download only to the Web/business artifact; the path and route-local `AI_SKILL_SOURCE_NOT_AVAILABLE` code must remain absent from `public-api.openapi.json` and its shared error-code metadata.
- If stale check produces a diff, source schema/API and committed artifacts disagree; submit the generated result or fix the source.
- Package name stays `@surgepilot/contracts`; Web must consume this package through the workspace dependency.
- Runner callback payloads are governed by `runner/runner-callback.schema.json`.
