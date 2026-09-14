# ADR-0015: P1 Scenario Global Configuration Phase A

- Status: Accepted
- Scope: Scenario-level structured global configuration for Settings, Global Headers, Scenario-local Variables, and CSV Data Sources

## Context

SurgePilot Scenario editing currently keeps common HTTP request configuration close to individual Steps. Existing P1-04 Scenario / Test Plan polish authorizes Clone, Archive, Test Plan read-only execution preview, and tag polish, but it does not authorize Scenario-level global headers or Scenario-local default variables. `ADR-0023` removes the separate Scenario Preview surface.

Taurus requests-based JMeter scenarios support scenario-level `headers`, `variables`, `default-address`, default request settings, and `data-sources`. SurgePilot must keep the user-facing mental model structured around Scenario editing while generating Taurus/JMeter YAML through the API. It must not expose an editable Taurus YAML expert surface.

Phase A needs a governance boundary because the requested feature introduces new Scenario persisted fields and generated-contract changes. `globalScripts` is explicitly out of scope and remains a Phase B candidate that would require separate security review.

## Options Considered

### Option A: Standalone P1-09 Slice for Scenario Global Configuration Phase A

Accepted.

This keeps the P1-04 Clone / Archive / Tags and amended Test Plan Preview boundaries stable while creating an explicit authorization source for new Scenario global headers and Scenario-local variables. It also makes the `globalScripts` exclusion testable because Phase A has its own ADR and Slice boundary.

### Option B: Reopen P1-04 and fold the new capability into its completed Slice

Rejected.

P1-04 already records completed implementation facts for Clone, Archive, Test Plan read-only Preview, and tags. Reopening it as the implementation source for new persisted Scenario fields would blur completed backfill facts with a new unimplemented capability.

### Option C: Add generic editable Taurus YAML or expert settings panel

Rejected.

This would violate the SurgePilot structured Scenario mental model and would activate out-of-scope Taurus/JMeter expert capabilities such as properties, `settings.env`, `jsr223`, JMX upload, and script-library behavior.

## Decision

1. Create a standalone Slice SDD: `docs/sdd/slices/P1-09-scenario-global-configuration.md`.
2. Activate only Phase A Scenario Global Configuration Tabs:
   - `Settings`
   - `Headers`
   - `Variables`
   - `Data Sources`
3. Reuse existing Scenario CRUD, revision, Dependency File, Debug Run, Env Group variable, generated contract, and Taurus builder paths. Test Plan Preview may consume the saved Scenario through its existing reference.
4. Keep Settings and Data Sources as organized existing capabilities; add only `globalHeaders` and Scenario-local non-secret `variables` as new Scenario configuration fields.
5. Map enabled `globalHeaders` to Taurus scenario-level `headers`.
6. Merge enabled Scenario-local `variables` with Env Group variables for execution, with Env Group variables overriding Scenario-local defaults.
7. Keep Step-level headers as request-level Taurus headers; request-level headers override scenario-level global headers by Taurus/JMeter semantics.
8. Keep `Content-Type` controlled by existing Step raw body content type behavior; global headers must not reverse-infer Step body content type.
9. Keep CSV Data Sources on the existing `dataSources` model and same-Workspace Dependency File reference boundary.
10. Keep FastAPI/Pydantic as the OpenAPI source of truth; Web consumers must use generated `@surgepilot/contracts` client/types only.
11. Do not add editable Taurus YAML, JMX upload, API Catalog generation, Schedule, multi-node, Secret, logic blocks, runtime script libraries, JMeter expert property panels, new runtime dependencies, k6/Locust abstractions, or Phase B `globalScripts` schema/storage/dependency refs.

## Consequences

1. Implementation authorization exists only after `ADR-0015`, `docs/sdd/slices/P1-09-scenario-global-configuration.md`, `docs/sdd/00-product-scope-and-priority.md`, `docs/sdd/02-repo-structure-and-dev-workflow.md`, `docs/sdd/slices/P1-README.md`, and `AGENTS.md` are synchronized.
2. Scenario schema, service, Web draft state, generated contracts, and tests must add `globalHeaders` and `variables` without adding `globalScripts`.
3. Debug Run variable validation and Test Plan Preview through saved Scenario references must include Scenario-local variables in the same available-variable set used by final Taurus mapping.
4. Current public structured Scenario routes reuse business DTOs for create, patch, and detail; these non-secret fields therefore enter `public-api.openapi.json` for those DTOs. Scenario list routes remain lightweight and this ADR does not require `ScenarioSummary` to return full `globalHeaders` or `variables` arrays.
5. Phase A does not extend `RunSnapshotScenarioItem`; execution uses existing Scenario content / execution bundle / Taurus builder paths, not the run report summary item, to carry Scenario global configuration.
6. Phase B `globalScripts` remains unimplemented and must not be pre-modeled in Phase A database fields, API schemas, generated contracts, checklist, dependency refs, tests, or Web surfaces.

## Related ADRs

- `docs/sdd/adr/ADR-0022-p1-governance-start.md` requires named accepted Slice SDDs before new P1 capabilities are implemented.
- `docs/sdd/adr/ADR-0012-p2-public-api-substrate.md` governs public API substrate boundaries.
- `docs/sdd/adr/ADR-0014-p2-env-group-secret.md` governs Env Group secret handling; this ADR adds only non-secret Scenario-local variables.
- `docs/sdd/adr/ADR-0023-remove-scenario-execution-preview.md` removes Scenario Preview while retaining Test Plan Preview.

## References

- `docs/sdd/slices/P1-09-scenario-global-configuration.md`
- `docs/sdd/slices/P1-04-scenario-testplan-polish.md`
- `docs/sdd/00-product-scope-and-priority.md`
- `docs/sdd/04-api-contract-guidelines.md`
- `docs/sdd/06-security-permission-workspace.md`
- `docs/sdd/08-frontend-routing-and-ui-rules.md`
- `docs/sdd/09-testing-and-acceptance-strategy.md`
- Optional local Taurus/JMeter references under ignored `docs/reference/taurus/`, if present; otherwise use the upstream Taurus/JMeter documentation.
- `AGENTS.md`
