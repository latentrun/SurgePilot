# P1-09 Scenario Global Configuration Phase A

- Document status: Accepted for implementation by `docs/sdd/adr/ADR-0015-p1-scenario-global-configuration.md`.
- Phase: P1
- Capability: `scenario_global_configuration`
- Scope Gate: `docs/sdd/00-product-scope-and-priority.md` §6, row `Scenario/Test Plan polish`
- P1 Index: `docs/sdd/slices/P1-README.md`
- Related Slice: `docs/sdd/slices/P1-04-scenario-testplan-polish.md`
- ADR: `docs/sdd/adr/ADR-0015-p1-scenario-global-configuration.md`
- Preview amendment: `docs/sdd/adr/ADR-0023-remove-scenario-execution-preview.md`
- API Contract Boundary: `docs/sdd/04-api-contract-guidelines.md`
- Security Boundary: `docs/sdd/06-security-permission-workspace.md`
- Frontend Route Boundary: `docs/sdd/08-frontend-routing-and-ui-rules.md`
- Testing Boundary: `docs/sdd/09-testing-and-acceptance-strategy.md`
- Optional local Taurus references: ignored `docs/reference/taurus/` copies for JMeter, Data Sources, Config Syntax, and Execution Settings, if present; otherwise use the upstream Taurus/JMeter documentation.

## 1. Core Decision

P1-09 adds Scenario-level Global Configuration Phase A as a structured Scenario editor surface with exactly four Tabs:

1. `Settings`
2. `Headers`
3. `Variables`
4. `Data Sources`

`Settings` and `Data Sources` are existing Scenario capabilities reorganized into the Global Configuration surface. `Headers` and Scenario-local `Variables` are new Phase A capabilities.

The user still edits structured Scenario fields. The API remains responsible for generating Taurus/JMeter YAML. This Slice must not expose Taurus YAML editing or a Taurus expert panel.

`globalScripts` is a Phase B candidate only. It must not enter Phase A schema, persisted fields, dependency references, generated contracts, checklist items, tests, Web copy, or implementation steps.

## 2. Scope Trace

| Source | Contract in this Slice |
| --- | --- |
| `ADR-0015` | Authorizes Phase A Global Configuration Tabs and forbids `globalScripts` pre-modeling. |
| `00-product-scope-and-priority.md` §6 `Scenario/Test Plan polish` | Extends Scenario polish with a structured Scenario-level Global Configuration editor; does not change Test Plan behavior except through existing Scenario references. |
| `P1-04 Scenario / Test Plan Polish` | Reuses generated-contract boundaries and Test Plan Preview through saved Scenario references; `ADR-0023` removes Scenario Preview. P1-09 does not reopen Clone, Archive, or tag semantics. |
| `P0-05 Visual Scenario / Debug Run` | Reuses Scenario CRUD, revision, Debug Run, Dependency File, and Taurus builder paths. |
| `P0-01 Env Groups` and `P2-03 Env Group Secret` | Scenario-local variables are plain non-secret defaults only; Env Group variables override them at execution. |
| `P2-02 Public API Substrate` | Current public structured Scenario list/get/create/patch routes exist and reuse Scenario business DTOs; non-secret `globalHeaders` and `variables` therefore enter public OpenAPI create/patch/detail DTOs, while list summary remains lightweight. |

## 3. In Scope

1. Scenario Global Configuration entry at the top of Scenario Designer with Tabs `Settings`, `Headers`, `Variables`, and `Data Sources`; default Tab is `Settings`.
2. `Settings` Tab reorganizes the existing `baseUrlExpression` and `defaultSettings` controls without adding expert JMeter options.
3. `Headers` Tab adds Scenario-level global HTTP headers as `globalHeaders` using the existing named-value row style.
4. `Variables` Tab adds Scenario-local non-secret default variables as `variables` using the existing named-value row style.
5. `Data Sources` Tab reuses existing CSV `dataSources`; it must not introduce a second data-source model.
6. Backend schemas, conceptual persistence, clone materialization, Debug Run, Test Plan Preview through Scenario references, and Taurus builder mapping for `globalHeaders` and `variables`.
7. Static variable-reference validation that includes Scenario-local variables, Env Group variables, explicit CSV variable names, and earlier extractors in the same effective available set.
8. OpenAPI/contract regeneration from FastAPI/Pydantic, with Web consuming generated `@surgepilot/contracts` client/types only.
9. API, Taurus builder, Test Plan Preview, Web, and contract tests listed in this Slice.

## 4. Out of Scope

This Slice must not implement:

1. Editable Taurus YAML, YAML import, YAML apply, JMX upload, or reverse write-back from generated YAML.
2. API Catalog generation chain, OpenAPI operation management, Scenario creation from API Catalog, Test Plan generation, or Schedule Run.
3. Multi-node execution, resource matching, Load Profile templates, or runtime load-profile editor changes.
4. Secret Scenario variables, mask/reveal, secret copy, PAT/plaintext token examples, `secretHash`, or a Scenario-level secret store.
5. Logic blocks, `set-variables`, `include-scenario`, runtime script library, scenario-level `jsr223`, or Phase B `globalScripts`.
6. JMeter properties, system properties, DNS cache manager, random source IP, resource regex, content encoding, concurrent resource pool size, or other expert JMeter panels not already modeled in `defaultSettings`.
7. New runtime dependencies, new middleware, queues, Redis, Celery, RabbitMQ, Kafka, Kubernetes, or microservice split.
8. k6, Locust, Gatling, Postman, or executor abstraction work.
9. Inline CSV editor, remote CSV URL, CSV encoding field, ZIP/TAR/TGZ extraction, or automatic Dependency File upload entry from this Tab.
10. Changes to Test Plan schema or Run Snapshot schema. P1-09 may affect Test Plan execution only through existing Scenario references and execution bundle/Taurus builder paths; it must not redesign Test Plan schema or pre-model Run Report snapshot summary fields.

## 5. Preconditions

1. Existing Scenario CRUD, revision, clone, Debug Run, Dependency File reference validation, Taurus builder behavior, and Test Plan Preview through Scenario references are available.
2. Existing Scenario schema contains `baseUrlExpression`, `defaultSettings`, `dataSources`, and Step-level named-value headers.
3. Existing `ScenarioNamedValue` row style can be reused for `globalHeaders` and `variables` conceptually, subject to validation rules in this Slice.
4. Current `/api/public/v1/scenarios` structured Scenario list/get/create/patch routes exist and reuse `ScenarioListResponse`, `ScenarioDetail`, `ScenarioCreateRequest`, and `ScenarioPatchRequest`.
5. Current `RunSnapshotScenarioItem` contains only `scenarioName` and `loadSettings`; it is a run report summary item, not full Scenario editable content.
6. Existing CSV `dataSources` already reference same-Workspace Dependency Files.
7. FastAPI/Pydantic remains the OpenAPI source of truth; OpenAPI artifacts and generated Web client/types are outputs, not design inputs.
8. SurgePilot is still in active development; this Slice does not define historical data or legacy client compatibility behavior.

## 6. Locked Decisions

| ID | Decision |
| --- | --- |
| SGC-01 | Phase A Tabs are fixed to `Settings`, `Headers`, `Variables`, and `Data Sources`. |
| SGC-02 | `Settings` keeps `baseUrlExpression` -> Taurus `default-address` and current `defaultSettings`; it does not add expert JMeter settings. |
| SGC-03 | `globalHeaders` is Scenario-level HTTP headers only. |
| SGC-04 | Global header names must be valid HTTP tokens and case-insensitively unique within one Scenario. |
| SGC-05 | Step headers remain request-level headers; same-name Step headers override global headers. |
| SGC-06 | `Content-Type` remains controlled by existing Step raw body content type logic and is not inferred from `globalHeaders`. |
| SGC-07 | Scenario-local `variables` are non-secret defaults only. |
| SGC-08 | Variable names use `[A-Za-z_][A-Za-z0-9_]*`. |
| SGC-09 | Effective execution variables are Scenario-local enabled variables plus Env Group variables; Env Group variables win on duplicate names. |
| SGC-10 | Disabled `globalHeaders` and `variables` remain stored and remain subject to same-row-family uniqueness validation; disabled headers are not scanned for required references, and disabled variables do not satisfy `${var}` reference validation. |
| SGC-11 | Static variable validation must include Scenario-local variables in the same available set as final Taurus generation. |
| SGC-12 | Explicit CSV `variableNames` are validated with the same Scenario variable-name rule; header-based CSV is conservatively allowed because the API does not read CSV content to infer headers. |
| SGC-13 | Extractor names must not conflict with Scenario-local variables, Env Group variables, explicit CSV variables, or earlier extractor names. |
| SGC-14 | `dataSources` remains the only CSV Data Sources model. |
| SGC-15 | `globalScripts` is not represented anywhere in Phase A. |
| SGC-16 | Web must use generated contract types and must not handwrite request/response shapes. |
| SGC-17 | Test Plan Preview uses API safe projection; Web never generates Taurus YAML. Scenario has no Preview surface. |
| SGC-18 | Test Plan Preview accepts unified redaction of merged variables in Phase A to avoid source-confusion between Scenario-local and Env Group-derived values. |
| SGC-19 | This Slice introduces no new open-source runtime dependency. |

## 7. Conceptual Data Contract

P1-09 intentionally defines conceptual fields and invariants only. Exact table names, ORM fields, Pydantic implementation classes, generated TypeScript names, and migration filenames are implementation backfill items after code reading.

### 7.1 Scenario global header entry

`globalHeaders` is an ordered list of named-value entries.

| Field | Required | Contract |
| --- | --- | --- |
| `id` | yes | Stable client row identifier scoped to the Scenario document. |
| `name` | yes | HTTP header name; must match HTTP token syntax; case-insensitively unique among enabled and disabled rows in the same Scenario. |
| `value` | yes | Plain string value; may contain `${var}` references. |
| `enabled` | yes | Disabled rows persist in the draft but do not generate Taurus `headers` and do not participate in required reference checks. |

Rules:

1. Header name comparison is case-insensitive for duplicate detection.
2. Header names preserve user-entered casing for display and generated YAML keys.
3. Empty enabled header names are invalid.
4. `Content-Type` in `globalHeaders` is allowed as an HTTP header but must not change Step body modeling; Step raw body `contentType` behavior remains authoritative when the Step has no explicit request-level `Content-Type`.
5. Header values are non-secret. Documentation, examples, and tests must not use real credentials, PATs, or secret-like token values.

### 7.2 Scenario-local variable entry

`variables` is an ordered list of Scenario-local default variable entries.

| Field | Required | Contract |
| --- | --- | --- |
| `id` | yes | Stable client row identifier scoped to the Scenario document. |
| `name` | yes | Variable name matching `[A-Za-z_][A-Za-z0-9_]*`; unique across enabled and disabled Scenario-local variable rows. |
| `value` | yes | Plain non-secret string default value. |
| `enabled` | yes | Disabled rows persist in the draft but do not generate Taurus `variables` and do not satisfy reference validation. |

Rules:

1. Scenario-local variables are not a Secret feature.
2. Scenario-local variable values are plain strings and are redacted in Test Plan Preview safe projection after merging with Env Group variables.
3. No `type`, `secret`, `masked`, `hasValue`, `displayValue`, `secretHash`, reveal, or copy semantics are allowed on these entries.
4. Env Group variables with the same name override Scenario-local defaults only for effective execution and Test Plan Preview generation. The stored Scenario content remains unchanged.

### 7.3 Existing fields retained in Global Configuration

| Field | Tab | Contract |
| --- | --- | --- |
| `baseUrlExpression` | `Settings` | Continues mapping to Taurus `default-address` after existing resolution and URL validation. |
| `defaultSettings` | `Settings` | Continues carrying current default request settings: think time, timeout, redirects, keepalive, cache/cookie, and retrieve resources as currently modeled. |
| `dataSources` | `Data Sources` | Continues using same-Workspace Dependency File references and existing CSV mapping. |

## 8. API Contracts

### 8.1 Scenario schema changes

The following business schemas must include `globalHeaders` and `variables` as camelCase JSON fields:

1. `ScenarioEditableContent`
2. `ScenarioCreateRequest`
3. `ScenarioPatchRequest`
4. `ScenarioDetail`

`ScenarioSummary` remains a lightweight list summary by default and must not include full `globalHeaders` or `variables` arrays. If implementation later needs list-visible configuration presence, it may add explicitly designed lightweight derived fields only after documenting the reason; it must not default to returning full configuration arrays from list responses.

Rules:

1. Existing `extra="forbid"` behavior remains. Taurus-native fields such as `headers`, `jsr223`, `properties`, `settings.env`, and `globalScripts` must be rejected if submitted outside accepted SurgePilot fields.
2. Current public structured Scenario routes reuse `ScenarioCreateRequest`, `ScenarioPatchRequest`, and `ScenarioDetail`; therefore `globalHeaders` and `variables` must appear in both `api.openapi.json` and `public-api.openapi.json` for create, patch, and detail DTOs.
3. `ScenarioListResponse` continues to contain lightweight `ScenarioSummary` items; public list responses do not expose full `globalHeaders` or `variables` arrays.
4. Phase A must not extend `RunSnapshotScenarioItem`. Runtime execution uses existing Scenario content / execution bundle / Taurus builder paths, not the run report summary item, to carry Scenario global configuration.
5. API JSON field names are camelCase: `globalHeaders`, `variables`, `baseUrlExpression`, `defaultSettings`, `dataSources`.
6. The API must reject unknown fields and must not silently preserve Phase B or Taurus-native fields.

### 8.2 Representative create request

```http
POST /api/v1/scenarios
Content-Type: application/json
x-workspace-id: 01J0Y6T6H2Y0S9V4W8M7N6P5Q8
x-csrf-token: <csrf>
```

```json
{
  "name": "Checkout API",
  "description": "Debug checkout flow",
  "tags": ["checkout"],
  "baseUrlExpression": "${base_url}",
  "defaultSettings": {
    "thinkTimeMs": 0,
    "timeoutMs": 30000,
    "followRedirects": true,
    "keepAlive": true,
    "storeCache": true,
    "storeCookie": true,
    "retrieveResources": false
  },
  "globalHeaders": [
    {
      "id": "01J0Y6T6H2Y0S9V4W8M7N6P5Q8",
      "name": "X-API-Version",
      "value": "${api_version}",
      "enabled": true
    }
  ],
  "variables": [
    {
      "id": "01J0Y6T6H2Y0S9V4W8M7N6P5Q9",
      "name": "api_version",
      "value": "v1",
      "enabled": true
    }
  ],
  "dataSources": [],
  "steps": [
    {
      "id": "01J0Y6T6H2Y0S9V4W8M7N6P5QA",
      "enabled": true,
      "name": "Create order",
      "method": "POST",
      "path": "/orders",
      "queryParams": [],
      "headers": [],
      "body": { "type": "none", "contentType": null, "rawText": null, "formFields": [] },
      "uploadFiles": [],
      "extractors": [],
      "assertions": [],
      "scripts": [],
      "settings": {}
    }
  ]
}
```

The same business DTOs are reused by the current public structured Scenario create/patch/detail paths under `/api/public/v1/scenarios`, so `globalHeaders` and `variables` must enter both `packages/contracts/openapi/api.openapi.json` and `packages/contracts/openapi/public-api.openapi.json`; list summary schemas remain lightweight and do not include full configuration arrays.

### 8.3 Detail response boundary

`ScenarioDetail` must expose the complete saved Scenario editable content, including `globalHeaders`, `variables`, `baseUrlExpression`, `defaultSettings`, `dataSources`, and `steps`. The generated OpenAPI schema is the authoritative response shape; this Slice intentionally avoids freezing a long detail JSON fixture that can drift from DTO evolution.

`ScenarioSummary` remains the lightweight list shape and does not include full `globalHeaders` or `variables` arrays.

### 8.4 Error contracts

| Case | Status | Code | Contract |
| --- | --- | --- | --- |
| Duplicate global header name ignoring case | `422` | `VALIDATION_ERROR` | Field path points to `globalHeaders`. |
| Invalid global header name | `422` | `VALIDATION_ERROR` | Detail type is `invalid_header_name` or existing equivalent validation detail. |
| Invalid Scenario variable name | `422` | `VALIDATION_ERROR` | Field path points to `variables`. |
| Duplicate Scenario variable name | `422` | `VALIDATION_ERROR` | Field path points to `variables`. |
| Explicit CSV `variableNames` invalid | `422` | `VALIDATION_ERROR` | Field path points to `dataSources[*].variableNames`. |
| `${var}` reference missing from effective available set | `422` | `VALIDATION_ERROR` | Reuse debug builder validation family; must include references from `globalHeaders`, base URL, Step path/query/header/body/assertions, and enabled entries only. |
| Extractor name conflicts with Scenario variable, Env Group variable, explicit CSV variable, or earlier extractor | `422` | `VALIDATION_ERROR` | Detail type is `variable_conflict` or existing equivalent. |
| Submitted `globalScripts` or Taurus-native unsupported field | `422` | `VALIDATION_ERROR` | Rejected by `extra="forbid"` or explicit schema validation. |

Rules:

1. API error fallback messages remain English.
2. Web must route save errors to the first Tab that contains an invalid field.
3. Missing variables from header-based CSV are conservatively allowed when explicit `variableNames` are omitted because the API does not read CSV contents to infer headers.

## 9. Taurus/JMeter Mapping

### 9.1 Scenario-level mapping

Existing mapping remains:

| SurgePilot field | Taurus field |
| --- | --- |
| `baseUrlExpression` | `scenarios.surgepilot_scenario.default-address` |
| `defaultSettings.thinkTimeMs` | `scenarios.surgepilot_scenario.think-time` |
| `defaultSettings.timeoutMs` | `scenarios.surgepilot_scenario.timeout` |
| `defaultSettings.followRedirects` | `scenarios.surgepilot_scenario.follow-redirects` |
| `defaultSettings.keepAlive` | `scenarios.surgepilot_scenario.keepalive` |
| `defaultSettings.storeCache` | `scenarios.surgepilot_scenario.store-cache` |
| `defaultSettings.storeCookie` | `scenarios.surgepilot_scenario.store-cookie` |
| `defaultSettings.retrieveResources` | `scenarios.surgepilot_scenario.retrieve-resources` |
| `dataSources` | `scenarios.surgepilot_scenario.data-sources` |

New Phase A mapping:

| SurgePilot field | Taurus field |
| --- | --- |
| enabled `globalHeaders` | `scenarios.surgepilot_scenario.headers` |
| enabled Scenario-local `variables` merged with Env Group variables | `scenarios.surgepilot_scenario.variables` |

Representative generated fragment:

```yaml
scenarios:
  surgepilot_scenario:
    default-address: "https://staging.example.test"
    headers:
      X-API-Version: "${api_version}"
    variables:
      api_version: v1
    data-sources:
      - path: files/users.csv
        variable-names: username,password
```

Rules:

1. Env Group variables override Scenario-local variables before generating `scenarios.surgepilot_scenario.variables`.
2. Disabled `globalHeaders`, disabled `variables`, and disabled `dataSources` do not generate Taurus output; disabled `variables` also do not satisfy `${var}` reference validation.
3. Step-level headers continue to generate request-level `headers`; Taurus request-level local headers override global headers.
4. The builder must not generate scenario-level `jsr223` from Phase A fields.
5. The builder must not map Scenario-local variables to Taurus top-level `settings.env`; `settings.env` is Taurus subprocess environment/config substitution and is not the SurgePilot Scenario variable model.
6. Execution/load profile fields such as `concurrency`, `ramp-up`, `hold-for`, `iterations`, and `throughput` remain Test Plan/execution concerns, not Scenario Global Configuration.

### 9.2 Static variable reference validation

Effective available variable set for Debug validation and Test Plan Preview build must include:

1. enabled Scenario-local `variables`;
2. Env Group variables selected for Debug/Run or saved on the previewed Test Plan;
3. explicit CSV `dataSources.variableNames` from enabled data sources;
4. extractor names from earlier enabled extractors in Step order.

Reference sources that must be scanned:

1. `baseUrlExpression`;
2. enabled `globalHeaders.value`;
3. enabled Step path;
4. enabled Step query param names and values;
5. enabled Step header values;
6. enabled Step body raw text and form field names/values;
7. enabled assertion values where `${var}` syntax can appear.

Rules:

1. Header-based CSV sources without explicit `variableNames` cause conservative allowance for otherwise unresolved names after Scenario/Env/extractor validation, matching current behavior.
2. Disabled `variables` do not satisfy references, even though their names still participate in Scenario-local duplicate checks.
3. Disabled `globalHeaders` are not scanned for required references.
4. Extractor names are added only after their Step position is reached; later references may use earlier extractors, but earlier fields must not use later extractors.
5. Extractor conflicts are checked before adding the extractor to the available set.
6. Validation and builder available-variable semantics must stay aligned.

## 10. UI / UX Contracts

1. Scenario Designer keeps the Global Configuration entry at the top of the page.
2. Opening Global Configuration shows Tabs in this order: `Settings`, `Headers`, `Variables`, `Data Sources`.
3. Default Tab is `Settings`.
4. `Settings` displays current Base URL and default request settings.
5. `Headers` displays `name` / `value` / `enabled` rows and empty state `No global headers.`.
6. `Variables` displays `name` / `value` / `enabled` rows and empty state `No scenario variables.`.
7. `Variables` shows helper copy that values are ordinary non-secret Scenario defaults.
8. `Data Sources` reuses the current CSV Data Sources form and empty state `No CSV data sources.`.
9. Validation failure after `Done` or page `Save` must switch to the first Tab with an error.
10. Global Configuration edits modify only the current Scenario draft and set `dirty=true`.
11. The modal uses `Done` and `Cancel`; `Done` closes the modal but does not persist to the API.
12. Page-level `Save` remains the only persistent save action.
13. Debug keeps existing save-and-debug behavior: if the Scenario is dirty, save first, then create Debug Run.
14. Scenario Designer does not display Generated YAML Preview or preview-only Env Group controls.
15. Web must not add `Apply YAML`, `Edit YAML`, `Import YAML`, `Run from preview`, or equivalent actions.
16. Web copy remains English and should live with existing feature copy conventions.

## 11. Security and Privacy Constraints

1. `globalHeaders` and Scenario-local `variables` are non-secret fields.
2. API docs, OpenAPI examples, fixtures, and tests must not use real secrets, PATs, plaintext tokens, or `secretHash`.
3. No masking/reveal/copy-secret semantics are added for Scenario-local variables.
4. Test Plan Preview continues using API safe projection. Phase A accepts unified redaction of variables after Scenario-local and Env Group variables are merged.
5. Scenario does not add a Generated YAML Preview or any new plaintext display surface.
6. Same-Workspace enforcement remains required for Dependency Files and Env Groups used during Debug/Run and Test Plan Preview.
7. Web must not decide authorization or scope by hiding UI controls only; backend validation remains authoritative.
8. Public API artifacts must not expose `globalScripts`, secret fields, token-management routes, PAT plaintext fields, `secretHash`, browser session/CSRF routes, internal runner routes, runner token/object key/server path, internal storage paths, or real secret examples.

## 12. Contracts and Generated Artifacts

1. FastAPI/Pydantic schemas remain the OpenAPI source of truth.
2. After API schema changes, implementation must run `make generate-contracts`.
3. Implementation must commit regenerated `packages/contracts/openapi/api.openapi.json`, `packages/contracts/openapi/public-api.openapi.json`, and `packages/contracts/generated/` Web client/types.
4. Do not handwrite or directly edit OpenAPI artifacts or generated TypeScript.
5. Web must import generated client/types through the `@surgepilot/contracts` workspace dependency.
6. Current public structured Scenario create/patch/read routes reuse `ScenarioCreateRequest`, `ScenarioPatchRequest`, and `ScenarioDetail`; `globalHeaders` and `variables` therefore must enter `public-api.openapi.json` as non-secret fields for those DTOs.
7. Current public Scenario list route returns `ScenarioListResponse` with lightweight `ScenarioSummary`; it must not include full `globalHeaders` or `variables` arrays in list items by default.
8. Public OpenAPI exclusion checks must continue to reject `globalScripts`, secret fields, `secretHash`, PAT plaintext, browser session/CSRF routes, runner/internal routes, runner object keys, server paths, and real secret examples.
9. `make contracts-stale-check` must cover both `packages/contracts/openapi/` and `packages/contracts/generated/` so that `api.openapi.json`, `public-api.openapi.json`, and generated Web client/types cannot drift.

## 13. Implementation Sequence

0. Governance Step 0: accept `ADR-0015`; sync the scope gate, P1 index, directly affected
   Foundation sources, and this Slice before implementation. Root `AGENTS.md` routes P1 discovery to
   the index and changes only when a stable repository-wide invariant or routing branch changes. If
   governance is not accepted, implementation must stop.
1. Backend schema/model: add Phase A `globalHeaders` and `variables`; do not add `globalScripts`.
2. Backend service: add validation, clone materialization, Debug variable available-set handling, Test Plan Preview composition, and Taurus builder mapping.
3. Dependency refs: keep existing Data Sources Dependency File reference maintenance; do not add script dependency refs.
4. Contracts: run `make generate-contracts`; update internal and public artifacts for the current reused public Scenario DTO boundary.
5. Web model: consume regenerated `@surgepilot/contracts` types; update defaults, draft state, patch payload, and clone materialization without handwritten request/response shapes.
6. Web UI: implement `Settings` / `Headers` / `Variables` / `Data Sources` Tabs in Global Configuration.
7. Tests: add API, builder, Test Plan Preview, Web Tabs, and contract freshness coverage.
8. Docs: only record authorized and implemented engineering facts in Implementation Backfill; do not rewrite this SDD as an implementation diary.

## 14. Test and Acceptance Criteria

API tests must cover:

1. create, patch, detail, clone, and saved content materialization for `globalHeaders` and `variables`.
2. duplicate global header names ignoring case.
3. invalid global header names.
4. invalid Scenario variable names.
5. extractor conflicts with Scenario variable, Env Group variable, explicit CSV variable, or earlier extractor.
6. header value `${var}` missing from the effective available set.
7. Env Group variable overriding Scenario-local variable in the effective generated variables map.
8. Debug variable validation accepting Scenario-local variables.
9. Debug variable validation still rejecting truly missing `${var}`.
10. explicit CSV `variableNames` strict validation.
11. header-based CSV references conservatively allowed when variable names are omitted.
12. Test Plan Preview redacts Env Group-derived and Scenario variables uniformly in Phase A safe projection.
13. Disabled `globalHeaders` and `variables` persist and remain subject to duplicate validation but do not generate output or satisfy reference validation.
14. Phase A does not extend `RunSnapshotScenarioItem`; execution uses existing Scenario content / execution bundle / Taurus builder paths.

Taurus builder tests must cover:

1. scenario-level `headers` generation from enabled `globalHeaders`.
2. scenario-level `variables` generation from enabled Scenario-local variables merged with Env Group variables.
3. Env Group variable override precedence.
4. `data-sources` unchanged from existing rules.
5. Step header generation unchanged and request-level headers preserved.
6. scenario-level `jsr223` not generated by Phase A fields.

Web tests must cover:

1. Global Configuration opens to the `Settings` Tab by default.
2. `Headers`, `Variables`, and `Data Sources` empty states.
3. add, edit, delete, and enabled toggles for `Headers` and `Variables`.
4. existing CSV Data Sources form still works from the `Data Sources` Tab.
5. validation errors route to the first errored Tab.
6. `Done` closes the modal and marks draft dirty without persisting.
7. page `Save` persists Global Configuration fields.
8. Scenario Designer has no Generated YAML Preview controls.
9. no editable YAML or `globalScripts` UI appears.

Contract tests must cover:

1. business OpenAPI artifact includes `globalHeaders` and `variables` in `ScenarioCreateRequest`, `ScenarioPatchRequest`, and `ScenarioDetail`, using camelCase.
2. business and public list schemas keep `ScenarioSummary` lightweight and do not include full `globalHeaders` or `variables` arrays.
3. public OpenAPI artifact includes `globalHeaders` and `variables` in the reused public Scenario create, patch, and detail DTOs.
4. public artifact exclusion checks continue rejecting `globalScripts`, secret fields, token-management, PAT plaintext, `secretHash`, session/CSRF, internal runner, runner object key/server path, and real secret examples.
5. `make contracts-stale-check` detects stale `api.openapi.json`, `public-api.openapi.json`, and generated Web client/types.

Done When:

1. `ADR-0015` is accepted and linked from governance docs.
2. `docs/sdd/slices/P1-09-scenario-global-configuration.md` is active and linked from the P1 index;
   root instructions route unnamed P1 feature work to that index.
3. API schemas, services, contracts, and Web generated-client consumers implement `globalHeaders` and Scenario-local `variables` without `globalScripts`.
4. Taurus builder output contains scenario-level `headers` and merged `variables`, keeps existing `data-sources`, and does not generate scenario-level `jsr223`.
5. Test Plan Preview and Debug variable validation use the same effective available set as the builder.
6. Tests listed above pass and generated contracts are fresh.
7. Review confirms no editable YAML, JMX upload, API Catalog generation chain, Schedule, multi-node, Secret, expert JMeter panel, new dependency, or Phase B script capability entered Phase A.

---

## 15. Implementation Backfill

Implementation status: Implemented in branch `feat/p1-09-scenario-global-configuration`.

Engineering facts:

1. Storage uses two new Scenario JSON columns:
   - `scenarios.global_headers_json`
   - `scenarios.variables_json`
2. Migration filename: `apps/api/migrations/versions/0018_p1_09_scenario_global_configuration.py`.
3. API schema classes:
   - `ScenarioEditableContent`, `ScenarioCreateRequest`, `ScenarioPatchRequest`, and `ScenarioDetail` include `globalHeaders` and `variables`.
   - `ScenarioSummary` remains lightweight and does not include full `globalHeaders` or `variables`.
   - `ScenarioVariable` is a non-secret named-value row with the Scenario variable-name length boundary.
   - Nested Scenario content DTOs use forbidden-extra schema config so Taurus-native or secret-like fields such as `settings.env`, `jsr223`, `secret`, or `secretHash` are rejected instead of silently dropped; generated OpenAPI marks these nested schemas with `additionalProperties: false`.
4. Service behavior:
   - `validate_scenario_content` validates global HTTP token names, case-insensitive global header uniqueness, Scenario variable names, Scenario variable uniqueness, explicit CSV variable names, and extractor conflicts with Scenario variables / CSV variables / earlier extractors.
   - Debug and Test Plan Preview validation plus Taurus generation share the same Scenario-local plus Env Group effective-variable set; Env Group values override Scenario-local values.
   - `build_debug_taurus_document_from_content` maps enabled `globalHeaders` to scenario-level `headers` and enabled Scenario variables merged with Env Group values to scenario-level `variables`.
   - Disabled `globalHeaders` and `variables` persist but do not generate Taurus output; disabled variables do not satisfy reference validation.
   - Test Plan Preview safe projection redacts the merged `variables` map and Scenario-derived resolved values in Phase A.
5. Web files:
   - `apps/web/src/features/scenarios/model.ts` carries `globalHeaders` and `variables` in blank and patch payloads.
   - `apps/web/src/features/scenarios/pages/scenario-designer-page.tsx` implements Global Configuration Tabs: `Settings`, `Headers`, `Variables`, `Data Sources`.
   - `apps/web/src/features/scenarios/scenarios.test.tsx` covers tab defaults, global header/variable editing, non-persistent `Done`, Cancel draft restoration, Save payloads, and validation-error tab routing.
   - Save validation failures use save-specific copy; Debug Run validation failures keep Debug-specific copy.
6. Generated contract artifacts updated:
   - `packages/contracts/openapi/api.openapi.json`
   - `packages/contracts/openapi/public-api.openapi.json`
   - `packages/contracts/generated/web-client/index.ts`
7. New tests:
   - `apps/api/tests/test_p1_09_scenario_global_configuration.py`
   - `tests/contract/test_p1_09_scenario_global_configuration_openapi.py`
   - `tests/e2e/p1_09_scenario_global_configuration.spec.ts`
   - Added review-driven coverage for nested unsupported-field rejection on internal/public Scenario DTOs and public OpenAPI strict nested schema output.

Executed verification during implementation:

```bash
make generate-contracts
make contracts-stale-check
make lint
make verify
uv run --all-packages pytest apps/api/tests/test_p0_05_scenarios_service.py apps/api/tests/test_p0_05_scenarios_api.py apps/api/tests/test_p1_04_scenario_testplan_polish_api.py apps/api/tests/test_p2_02_public_api.py apps/api/tests/test_p1_09_scenario_global_configuration.py tests/contract/test_p1_09_scenario_global_configuration_openapi.py tests/contract/test_p2_02_public_api_openapi.py -q
pnpm --filter @surgepilot/web test -- scenarios.test.tsx --runInBand
pnpm exec playwright test tests/e2e/p1_09_scenario_global_configuration.spec.ts --project=chrome
```

Remaining risks: None known. Public OpenAPI inclusion remains fixed to the current reused public Scenario DTO boundary: create, patch, and detail include non-secret `globalHeaders` and `variables`; list summaries remain lightweight.
