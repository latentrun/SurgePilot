# P0-05: Visual Scenario and Debug Run

- Documentation status: Draft v1
- Project: SurgePilot performance load testing platform
- Document location: `docs/sdd/slices/P0-05-visual-scenario-debug-run.md`
- Product source: `docs/prd/PRD.md`
- Range constraint: `docs/sdd/00-product-scope-and-priority.md`
- API contract source: `docs/sdd/04-api-contract-guidelines.md`
- Run / Runner Source: `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- Frontend Source: `docs/sdd/08-frontend-routing-and-ui-rules.md`
- Optional local Taurus reference: developer-supplied files under ignored `docs/reference/taurus/` may be used for Taurus/JMeter details, but they are not required in a fresh repository checkout.
- Current delivery target: P0 only
- Scope of application: Visual Scenario CRUD, Visual Step Editor, Scenario Debug Run, Scenario execution snapshot, Taurus requests-scenario mapping, AI Coding, code review, test acceptance

---

## 1. Goal

P0-05 delivers **Visual Scenario** that users can manually create, edit, save and debug with low risk.

Once completed, users can within the current Workspace:

1. Create Visual Scenario;
2. Maintain Scenario basic information, `baseUrlExpression`, Step list, Dependency File reference and minimum execution settings;
3. Use the visual Step Editor to configure HTTP request, headers, query params, body, upload files, extractors, assertions, JSR223/Groovy scripts and request settings;
4. Select an Idle Load Node and optional Env Group to launch Scenario Debug Run;
5. Debug Run uses P0-04 Run state machine, Runner protocol, node lease, stop, heartbeat timeout and artifact ingestion capabilities;
6. After the Debug Run is successfully created, it jumps to `/runs/:runId` and the Run Report is completely presented by P0-07.

The core results of P0-05 are:

```text
Scenario List
  -> Create Scenario
  -> Scenario Designer
  -> Save Visual Scenario
  -> Select optional Env Group and one Idle Load Node
  -> Save and Debug
  -> POST /api/v1/runs
  -> Run(initializing) + Run Snapshot + node lease
  -> Redirect /runs/:runId
```

P0-05 is not a Test Plan editor, not a universal YAML editor, nor API Catalog / Import capabilities.

---

## 2. PRD Trace

| PRD area | P0-05 coverage |
| --- | --- |
| §4 P0 Main Link | Implement the "Create Visual Scenario" and "Debug Run" paragraphs, and hand them over to subsequent P0-06 / P0-07 to complete the Test Plan / Report closed loop. |
| §5.3 Scenario | Only supports Visual Scenario; standalone script scene mode, Postman Collection, raw JMeter JMX uploads are not supported. |
| §5.3 Step fields | Support the P0 minimum subset of Method, Path/URL Preview, Headers, Query Params, Body, Upload Files, Extractors, Assertions, Scripts, and Settings. |
| §5.4 Env Group | Variables are referenced in Scenario; Debug Run can select Env Group; P0 Env Group variables are treated as ordinary variables. |
| §5.5 Dependency File | Scenario can reference ordinary Dependency File; perform snapshots to retain reference relationships; and can detect references before deletion. |
| §5.8 Run | Scenario Debug Run creates Runs of `runType=debug` and `sourceType=debug_scenario`. |
| §6.2 Routes | Implement `/scenarios`, `/scenarios/:scenarioId`; jump to `/runs/:runId` after Debug Run is created. |
| §6.2.1 UI language | The text visible to front-end users is English only, and the i18n framework is not introduced. |

---

## 3. Document Responsibility

### 3.1 This Slice Owns

P0-05 owns:

1. `scenarios` data model for P0 Visual Scenario;
2. `scenario_dependency_file_refs` data model used for delete protection and snapshot construction;
3. Visual Scenario JSON schema used by API, DB, Web and execution builder;
4. Scenario CRUD public APIs;
5. public `POST /api/v1/runs` activation for **Scenario Debug Run only**;
6. short-window Run creation deduplication because Scenario Debug Run is the first public Run creation path;
7. execution snapshot extension for `debug_scenario` Runs;
8. Taurus/JMeter requests-scenario generation contract for P0 Scenario Debug Run;
9. Scenario List and Scenario Designer frontend contract;
10. Save and Debug UX, including unsaved-change handling and low-risk Debug profile;
11. tests and verification requirements for Scenario CRUD, Taurus mapping and Debug Run creation.

### 3.2 Foundation SDDs Remain Authoritative For

| Foundation SDD | Authority retained |
| --- | --- |
| `00-product-scope-and-priority.md` | P0/P1/P2 boundaries and forbidden work. |
| `04-api-contract-guidelines.md` | URL shape, headers, OpenAPI source of truth, error envelope, pagination, CSRF and generated client rules. |
| `05-runner-protocol-and-run-state-machine.md` | Run states, Stop, callback idempotency, node lease, heartbeat timeout, force-kill and Runner protocol. |
| `06-security-permission-workspace.md` | Session, Workspace, role, permission and audit rules. |
| `07-storage-artifacts-minio.md` | MinIO object storage, Dependency File object key and artifact path safety. |
| `08-frontend-routing-and-ui-rules.md` | React/Vite routing, UI stack, generated client usage, copy, polling and P0 routes. |

### 3.3 Later Slice Ownership

| Later Slice | Ownership |
| --- | --- |
| P0-06 Test Plan / Run Now | Test Plan CRUD, Scenario Orchestration, full Load Settings, SLA minimum subset, `runType=standard`, `sourceType=test_plan`, Run Now and Test Plan Debug. |
| P0-07 Run Report / Artifacts / Validity | full Run Report UI/API, KPI summary, safe failure diagnostics, final stats preview, artifacts download/preview and Valid / Invalid marking. |
| P0-08 Overview / Polish | overview quick entries, navigation polish, final production smoke and cross-slice UX consistency. |

---

## 4. In Scope

### 4.1 Backend API

P0-05 backend includes:

1. create, list, detail, patch and soft-delete Visual Scenarios;
2. validate Visual Scenario structure and semantic rules;
3. maintain Scenario revision for optimistic save / debug safety;
4. maintain Dependency File reference rows derived from Scenario content;
5. build immutable Scenario Debug Run snapshot from latest saved Scenario revision;
6. validate optional Env Group references and variable completeness;
7. validate selected Load Node is eligible for manual single-node execution;
8. create Debug Run through `POST /api/v1/runs` with `runType=debug` and `sourceType=debug_scenario`;
9. perform short-window server-side Run creation deduplication;
10. hand the created Run to the P0-04 start request / api-worker / Runner flow.

### 4.2 Data

P0-05 adds or activates:

1. `scenarios` table;
2. `scenario_dependency_file_refs` table;
3. `run_creation_dedup_keys` table or equivalent transactional unique-key mechanism;
4. `runs.source_type='debug_scenario'` product usage;
5. Run Snapshot payload sections for Visual Scenario, Env Group snapshot, Dependency File snapshot and Debug profile.

### 4.3 Frontend

P0-05 frontend includes:

1. `/scenarios` Scenario List page;
2. create Scenario action from Scenario List;
3. `/scenarios/:scenarioId` Scenario Designer page;
4. Visual Step Editor with add, edit, enable/disable, duplicate, delete and reorder;
5. URL Preview derived from `baseUrlExpression`, path and query params;
6. save flow with revision conflict handling;
7. Debug Run panel / modal with optional Env Group selector and required Idle Load Node selector;
8. Save and Debug flow when there are unsaved changes;
9. redirect to `/runs/:runId` after successful Debug Run creation;
10. English-only user copy centralized in feature copy files.

### 4.4 Taurus / JMeter Mapping

P0-05 defines how SurgePilot Visual Scenario maps to Taurus requests-scenario YAML for JMeter execution:

1. one SurgePilot Scenario maps to one Taurus `scenarios.<alias>` requests scenario;
2. Scenario Debug Run maps to one Taurus `execution` item with `executor: jmeter`, `concurrency: 1`, `iterations: 1` and the generated scenario alias;
3. Scenario `baseUrlExpression` maps to Taurus `default-address` after API-side variable validation and Env Group resolution;
4. Step path + query params map to Taurus request `url`;
5. Step headers map to Taurus request `headers`;
6. Step body maps to Taurus request `body` string or dictionary;
7. Step upload files map to Taurus `upload-files` using runner-local bundle paths;
8. Scenario CSV data sources map to Taurus `data-sources`;
9. P0 extractor/assertion/script subsets map only to Taurus/JMeter features explicitly supported by official docs.

### 4.5 Tests

P0-05 requires API, contract, web and fake-runner smoke tests described in §17.

---

## 5. Out of Scope

P0-05 must not implement:

1. API Catalog;
2. OpenAPI / Swagger Spec upload;
3. API Spec detail pages;
4. Creating Test Plans from API operations;
5. cURL import;
6. OpenAPI Step auto-generation;
7. Postman Collection import;
8. original JMeter JMX upload as Scenario mode;
9. independent script Scenario mode;
10. editable Taurus YAML;
11. generated YAML preview;
12. Test Plan CRUD or Scenario Orchestration;
13. Run Now for Test Plans;
14. Schedule Run;
15. auto resource allocation;
16. multi-node execution;
17. node count or selected nodes array;
18. reusable Load Profile templates;
19. reusable script libraries;
20. Env Group Secret type;
21. secret masking / reveal workflow;
22. ZIP / TAR / TGZ automatic extraction;
23. large artifact preview or Run Report details owned by P0-07;
24. Monitoring, Grafana, InfluxDB or Observability routes.

Allowed P0-05 extension points:

1. enum values already required by P0-04 such as `sourceType='debug_scenario'`;
2. internal snapshot fields needed by P0-06 / P0-07 if not exposed as usable P1/P2 UI;
3. server-side schema version fields for future migration;
4. non-clickable documentation notes about future import modes.

---

## 6. Confirmed Decisions

| Area | Decision |
| --- | --- |
| Scenario mode | P0 supports `visual` only. |
| Scenario route | `/scenarios`, `/scenarios/:scenarioId`. |
| Create UI | Create from `/scenarios`, then navigate to `/scenarios/:scenarioId`. No separate `/scenarios/new` route is required in P0. |
| Debug Run entry | Scenario Designer Debug panel/modal. |
| Debug Run API | Activate `POST /api/v1/runs` for `runType=debug`, `sourceType=debug_scenario` only. |
| Run creation dedup | Owned by P0-05 because Scenario Debug Run is the first public Run creation path; P0-06 reuses and extends it. |
| Debug load profile | Fixed low-risk profile: `concurrency=1`, `iterations=1`, no ramp-up, no hold-for, bounded timeout defaults. |
| Load Node selection | Required manual single Idle Load Node; no auto allocation. |
| Env Group for Debug | Optional; required only if unresolved Scenario variables remain after earlier extractors are considered. |
| Saved revision | Debug Run executes latest saved Scenario revision only. Unsaved UI changes require Save and Debug. |
| Scenario versioning | No `scenario_versions` table in P0. Use `revision` integer and immutable Run Snapshot. |
| Scenario deletion | Soft delete. Active Run or active Test Plan reference blocks deletion; historical Run Snapshot does not block deletion. |
| Variable syntax | `${var}`. Variable names use `[A-Za-z_][A-Za-z0-9_]*`. |
| Base URL | Scenario-level `baseUrlExpression`, default `${base_url}`. Step path is relative and starts with `/`. |
| Taurus executor | JMeter requests-scenario generation through Taurus. |
| Scripts | P0 supports minimal request-level JSR223/Groovy before/after scripts as bounded inline script text stored in the Scenario Step. |
| Script scenario mode | Forbidden. JSR223 scripts do not create an independent script Scenario mode. |
| Generated YAML | Internal execution artifact only; not user-editable and not previewed in P0 UI. |
| Debug success navigation | API returns `runId`; Web navigates to `/runs/:runId`. Full report is P0-07. |

---

## 7. Taurus / JMeter Alignment

P0-05 Taurus/JMeter behavior should align with the Taurus/JMeter documentation. Developers may keep local reference copies under ignored `docs/reference/taurus/`, but those files are optional and are not committed.

### 7.1 Taurus Reference Topics

| Optional local reference | Contract area |
| --- | --- |
| `docs/reference/taurus/ExecutionSettings.md` | `execution` options, `concurrency`, `iterations`, `scenario`, load profile boundaries and execution env notes. |
| `docs/reference/taurus/JMeter.md` | requests-scenario syntax, global settings, HTTP request fields, extractors, assertions, JSR223 blocks and logic-block exclusions. |
| `docs/reference/taurus/ConfigSyntax.md` | `${var}` convention, human-readable time units and config-level variable substitution cautions. |
| `docs/reference/taurus/DataSources.md` | CSV `data-sources` structure and supported options. |
| `docs/reference/taurus/jmeter/body-file.yml` | body-file example used only as a reference; P0 UI does not expose body-file as a separate mode. |
| `docs/reference/taurus/jmeter/csv-usage.yml` | CSV data source + `${var}` use in requests. |
| `docs/reference/taurus/jmeter/default-address-trick.yml` | `default-address` + relative request path pattern. |
| `docs/reference/taurus/jmeter/prmctl.yml` | JSR223 examples; implementation uses Taurus `script-text` for user Scenario scripts. |
| `docs/reference/taurus/jmeter/simple-assert.yml` | response assertion shape for requests. |

### 7.2 Mapping Principles

1. SurgePilot stores a product-oriented Visual Scenario JSON, not raw Taurus YAML.
2. The execution builder is the only component allowed to translate Visual Scenario JSON into Taurus YAML.
3. Generated Taurus YAML is an internal execution bundle artifact; it is not a P0 product surface.
4. P0 uses Taurus requests-scenario syntax, not `script: existing.jmx` Scenario syntax.
5. P0 does not expose Taurus logic blocks such as `if`, `once`, `loop`, `while`, `foreach`, `transaction`, `include-scenario`, `action`, or `set-variables` as user-visible Step types.
6. P0 generated YAML must stay within the official fields documented by Taurus for JMeter requests scenarios.
7. If a desired UI field has no clear Taurus/JMeter mapping in the local reference files, P0-05 must leave it out rather than inventing a pseudo-field.

### 7.3 Generated Debug YAML Shape

For Scenario Debug Run, the generated YAML shape is:

```yaml
settings:
  env:

modules:
  jmeter:
    path: /opt/surgepilot/apache-jmeter/bin/jmeter
    version: "5.6.3"
    detect-plugins: false
    force-ctg: false

execution:
- executor: jmeter
  concurrency: 1
  iterations: 1
  scenario: surgepilot_scenario

scenarios:
  surgepilot_scenario:
    default-address: "https://api.example.internal"
    store-cache: true
    store-cookie: true
    keepalive: true
    follow-redirects: true
    retrieve-resources: false
    think-time: 0ms
    timeout: 30s
    variables:
      token: "regular-p0-env-value"
    data-sources:
    - path: files/users.csv
      delimiter: ","
      variable-names: username,password
      loop: true
      random-order: false
    requests:
    - label: "GET /v1/users"
      url: "/v1/users?page=${page}"
      method: GET
      headers:
        Authorization: "Bearer ${token}"
      extract-jsonpath:
        user_id:
          jsonpath: "$.data[0].id"
          default: ""
          match-no: 1
      assert:
      - contains:
        - "200"
        subject: http-code
        regexp: false
```

Rules:

1. `default-address` is resolved by API before bundle generation from `baseUrlExpression` and selected Env Group values.
2. `scenarios.<alias>.variables` carries regular P0 Env Group values for JMeter runtime variable usage.
3. Extractor-produced variables are referenced with the same `${var}` syntax in later requests.
4. If an Env Group variable name conflicts with an extractor variable name, API rejects the Scenario Debug Run with `VALIDATION_ERROR` to avoid pre-run/runtime ambiguity.
5. Real Runner execution depends on a preinstalled Apache JMeter binary on the Load Node; Taurus auto-install is not part of P0 execution.
6. The Load Node's configured Apache JMeter binary path is the deployment source of truth for `modules.jmeter.path`; P0-03 initialization verifies the binary before a node becomes eligible for real Scenario Debug Runs.
7. Scenario Debug Run YAML must include `modules.jmeter.path` from the configured path, `modules.jmeter.version` from the configured version, `modules.jmeter.detect-plugins: false`, and `modules.jmeter.force-ctg: false`.
8. The configured JMeter path is deployment configuration, not a user input and not a Web-visible field.
9. No-download correctness depends on the generated `modules.jmeter.path`, the Load Node's verified JMeter installation, and Runner `bzt -n`; `TAURUS_DISABLE_DOWNLOADS` is not an acceptance criterion.
10. P0 generated paths are runner-bundle-relative paths under the validated Run workspace directory.
11. Generated YAML must never include SSH credentials, runner tokens, MinIO object keys, session cookies or CSRF tokens.

---

## 8. Visual Scenario Model

### 8.1 Product Model

A P0 Visual Scenario contains:

| Field | Required | Notes |
| --- | --- | --- |
| `id` | yes | ULID external business ID. |
| `workspaceId` | yes | Derived from authenticated Workspace context. |
| `scenarioType` | yes | Always `visual` in P0. |
| `name` | yes | 1-120 chars. |
| `description` | no | Nullable, max 2000 chars. |
| `tags` | yes | Empty array allowed, max 10 tags, each 1-32 chars. |
| `baseUrlExpression` | yes | Default `${base_url}`; resolves to Taurus `default-address`. |
| `defaultSettings` | yes | Scenario-level request defaults. |
| `dataSources` | yes | CSV Dependency File references, empty array allowed. |
| `steps` | yes | Ordered Visual Scenario steps, at least one enabled HTTP step required for Debug Run. |
| `revision` | yes | Monotonic integer, starts at 1 and increments on successful PATCH. |
| `createdByUserId` | yes | Actor ID. |
| `updatedByUserId` | yes | Actor ID. |
| `createdAt` / `updatedAt` | yes | ISO 8601 UTC in API responses. |
| `deletedAt` | no | Soft delete marker. |

### 8.2 Scenario Default Settings

`defaultSettings` API shape:

```json
{
  "thinkTimeMs": 0,
  "timeoutMs": 30000,
  "followRedirects": true,
  "keepAlive": true,
  "storeCache": true,
  "storeCookie": true,
  "retrieveResources": false
}
```

Rules:

1. `timeoutMs` hard range: 100-300000.
2. `thinkTimeMs` hard range: 0-600000.
3. `retrieveResources` defaults to `false` in SurgePilot P0 even though Taurus supports retrieving embedded resources. This keeps Debug Run low risk and predictable.
4. UI may expose only `thinkTimeMs`, `timeoutMs`, `followRedirects` and `keepAlive` initially; API schema stores all P0 defaults for deterministic snapshotting.
5. Time values are stored in milliseconds in SurgePilot API and converted to Taurus human-readable time strings such as `500ms`, `1s`, or `30s` during bundle generation. Whole-second values should use second notation, for example `30000` ms becomes `30s`.

### 8.3 Data Sources

`dataSources[]` API shape:

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
  "dependencyFileId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
  "displayName": "users.csv",
  "delimiter": ",",
  "quoted": null,
  "loop": true,
  "variableNames": ["username", "password"],
  "randomOrder": false,
  "enabled": true
}
```

Rules:

1. `dependencyFileId` must belong to the same Workspace.
2. Only plain Dependency Files are supported; ZIP / TAR / TGZ auto extraction is forbidden in P0.
3. `delimiter` may be a one-character string or `tab`; omit/null means Taurus/JMeter auto-detection where supported.
4. `variableNames` may be empty; if empty, Taurus/JMeter uses the first CSV line as variable names.
5. `quoted=null` means the generated Taurus YAML omits `quoted` so Taurus/JMeter can auto-detect quoted CSV data.
6. `quoted=true` or `quoted=false` maps to Taurus `quoted: true` or `quoted: false`.
7. `randomOrder=true` is allowed only for JMeter, but P0 Debug Run always uses JMeter, so it is valid.
8. API records a `scenario_dependency_file_refs` row with `refType='data_source'` for each enabled data source.
7. Runner bundle path must be normalized to a safe relative path such as `files/<dependencyFileId>/<safeFilename>`.

### 8.4 Step Model

`steps[]` API shape:

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
  "enabled": true,
  "name": "Create order",
  "method": "POST",
  "path": "/v1/orders",
  "queryParams": [
    { "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7E", "name": "region", "value": "${region}", "enabled": true }
  ],
  "headers": [
    { "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7F", "name": "Authorization", "value": "Bearer ${token}", "enabled": true }
  ],
  "body": {
    "type": "raw",
    "contentType": "application/json",
    "rawText": "{\"sku\":\"${sku}\"}",
    "formFields": []
  },
  "uploadFiles": [],
  "extractors": [],
  "assertions": [],
  "scripts": [],
  "settings": {
    "thinkTimeMs": null,
    "timeoutMs": null,
    "followRedirects": null,
    "keepAlive": null
  }
}
```

Rules:

1. Step `id` is a stable ULID used for UI reordering, dependency refs and snapshot diagnostics.
2. Step order is array order; no separate `order` field is required in API payload.
3. Disabled steps are stored but not included in Debug Run execution snapshot or generated Taurus YAML.
4. At least one enabled step is required to create a Debug Run.
5. `method` values: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS`.
6. `path` must start with `/` and may include `${var}` references. Absolute URLs are not allowed in Step path in P0; use `baseUrlExpression` instead.
7. Query params are encoded by the execution builder into the Taurus request `url` while preserving enabled item order.
8. Duplicate enabled header names are rejected case-insensitively to avoid ambiguous Taurus map generation.
9. Header names must be valid HTTP token names and must not contain control characters.
10. Request body size in Scenario JSON is capped; P0 default maximum raw body text is 256 KiB.
11. Step-level settings override Scenario `defaultSettings` only when non-null.

### 8.5 Body Model

Supported P0 body types:

| `body.type` | Taurus mapping | Notes |
| --- | --- | --- |
| `none` | no `body` field | Default for GET/HEAD. |
| `raw` | `body: <string>` | `contentType` should add or update `Content-Type` header during generation if header is not already set. |
| `form` | `body: {key: value}` | Encoded by JMeter/Taurus as request parameters according to method/content type. |

Rules:

1. P0 does not expose Taurus `body-file` as a separate UI body mode.
2. Large payload files can be attached as `uploadFiles`; future body-file support must remain separate from P0-05 unless explicitly scoped.
3. `GET` and `HEAD` requests with non-`none` body are rejected with `VALIDATION_ERROR`.
4. P0 accepts `form` body only for `POST`, `PUT`, and `PATCH`; use `queryParams` for URL query strings on other methods.
5. `rawText` may contain `${var}` references.
6. Form field names must be non-empty and unique among enabled fields.

### 8.6 Upload Files

`uploadFiles[]` API shape:

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7G",
  "fieldName": "avatar",
  "dependencyFileId": "01HZX3Y9M0E9W7Z6M5QK9S8P7H",
  "mimeType": "image/png",
  "enabled": true
}
```

Taurus mapping:

```yaml
upload-files:
- param: avatar
  path: files/01HZX3Y9M0E9W7Z6M5QK9S8P7H/avatar.png
  mime-type: image/png
```

Rules:

1. `dependencyFileId` must belong to current Workspace.
2. API records `scenario_dependency_file_refs.ref_type='upload_file'` with `step_id`.
3. `fieldName` is required for `POST` because Taurus requires non-empty `param` values for POST upload files.
4. `PUT` may contain only one enabled upload file, matching Taurus documented behavior.
5. Upload file paths in generated YAML are bundle-relative, never MinIO object keys and never server absolute paths.

### 8.7 Extractors

P0 supports only JSONPath and regexp extractors.

`extractors[]` API shape:

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7J",
  "type": "jsonpath",
  "variableName": "user_id",
  "expression": "$.data[0].id",
  "defaultValue": "",
  "matchNo": 1,
  "subject": "body",
  "enabled": true
}
```

Mapping:

| SurgePilot type | Taurus field | Notes |
| --- | --- | --- |
| `jsonpath` | `extract-jsonpath` | Uses full form with `jsonpath`, `default`, `match-no`. |
| `regexp` | `extract-regexp` | Uses full form with `regexp`, `default`, `match-no`, `template`, `subject`. |

Rules:

1. `variableName` must match `[A-Za-z_][A-Za-z0-9_]*`.
2. Extractor variable names must be unique across enabled extractors in one Scenario.
3. Extractor variable names must not conflict with selected Env Group variable names for Debug Run.
4. Regexp extractors must contain at least one capture group unless `template` explicitly references a valid group.
5. P0 does not expose boundary, CSS/JQuery or XPath extractors.
6. Extracted variables are available to later enabled steps only.

### 8.8 Assertions

P0 supports status code, body contains and JSONPath assertions.

`assertions[]` API examples:

```json
[
  {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7K",
    "type": "status_code",
    "expectedStatus": 200,
    "enabled": true
  },
  {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7L",
    "type": "body_contains",
    "contains": "success",
    "regexp": false,
    "not": false,
    "enabled": true
  },
  {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
    "type": "jsonpath_equals",
    "jsonpath": "$.ok",
    "expectedValue": "true",
    "regexp": false,
    "enabled": true
  }
]
```

Mapping:

| SurgePilot type | Taurus mapping |
| --- | --- |
| `status_code` | `assert` full form with `subject: http-code`, `contains: ["200"]`, `regexp: false`. |
| `body_contains` | `assert` full form with `subject: body`. |
| `jsonpath_exists` | `assert-jsonpath` short/full form without expected value. |
| `jsonpath_equals` | `assert-jsonpath` full form with `validate: true` and `expected-value`. |

Rules:

1. `expectedStatus` range: 100-599.
2. `body_contains.contains` max length: 4096 chars.
3. `jsonpath` max length: 2048 chars.
4. P0 does not expose XPath assertions.
5. Assertion failures are execution results, not Scenario validation failures.

### 8.9 JSR223 / Groovy Scripts

P0 supports request-level JSR223/Groovy scripts only.

`scripts[]` API shape:

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
  "execute": "before",
  "language": "groovy",
  "scriptText": "vars.put('token', vars.get('base_token'))",
  "enabled": true
}
```

Taurus mapping:

```yaml
jsr223:
- language: groovy
  execute: before
  script-text: "vars.put('token', vars.get('base_token'))"
  compile-cache: true
```

Rules:

1. P0 only allows `language='groovy'` in the API, even though Taurus supports more languages.
2. `execute` values: `before`, `after`.
3. Enabled scripts must contain non-empty `scriptText`. API rejects empty or over-limit script text with `VALIDATION_ERROR`. Script text is treated as Groovy code and is not scanned for `${var}` references.
4. Script text is stored in the Scenario Step JSON, is included in immutable Run Snapshots, and does not create `scenario_dependency_file_refs` rows.
5. UI must show a clear warning that JSR223/Groovy executes on the selected Load Node as part of JMeter.
6. JSR223 scripts do not create an independent script Scenario mode and must not be represented as a separate Scenario type.
7. Generated Taurus embeds script text through the official JSR223 `script-text` field with `compile-cache: true`; script text never becomes a bundle file and never enters MinIO object storage.

---

## 9. Data Model

### 9.1 `scenarios`

Purpose: current editable Visual Scenario definition.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `workspace_id` | `char(26)` | yes | Workspace boundary. |
| `scenario_type` | `text` | yes | `visual` only in P0. |
| `name` | `text` | yes | 1-120 chars. |
| `description` | `text` | no | Nullable. |
| `tags_json` | `jsonb` | yes | JSON array of strings. |
| `base_url_expression` | `text` | yes | Default `${base_url}`. |
| `default_settings_json` | `jsonb` | yes | Shape in §8.2. |
| `data_sources_json` | `jsonb` | yes | Shape in §8.3. |
| `steps_json` | `jsonb` | yes | Shape in §8.4-§8.9. |
| `visual_schema_version` | `integer` | yes | `1` in P0. |
| `revision` | `integer` | yes | Starts at 1, increments on PATCH. |
| `created_by_user_id` | `char(26)` | yes | FK users. |
| `updated_by_user_id` | `char(26)` | yes | FK users. |
| `deleted_at` | `timestamptz` | no | Soft delete marker. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |

Constraints and indexes:

1. FK `workspace_id -> workspaces.id`.
2. FK `created_by_user_id -> users.id`.
3. FK `updated_by_user_id -> users.id`.
4. `scenario_type in ('visual')` for P0.
5. `visual_schema_version = 1` for P0.
6. `revision >= 1`.
7. Index `(workspace_id, deleted_at, updated_at desc, id desc)`.
8. Index `(workspace_id, lower(name))` for search.

Rules:

1. Scenario data is always filtered by `workspace_id` and `deleted_at is null` in public APIs.
2. API responses use camelCase.
3. DB columns use snake_case.
4. PATCH uses `expectedRevision` to prevent overwriting another saved edit.
5. Scenario JSON must not contain MinIO object keys, SSH credentials, runner tokens, session cookies or CSRF tokens.

### 9.2 `scenario_dependency_file_refs`

Purpose: fast Dependency File reference checks and snapshot construction.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `workspace_id` | `char(26)` | yes | Same Workspace as Scenario and Dependency File. |
| `scenario_id` | `char(26)` | yes | FK scenarios. |
| `dependency_file_id` | `char(26)` | yes | FK dependency_files. |
| `ref_type` | `text` | yes | `data_source` or `upload_file`. |
| `step_id` | `char(26)` | no | Step ID for upload file refs; null for scenario data source refs. |
| `created_at` | `timestamptz` | yes | UTC. |

Constraints and indexes:

1. FK `scenario_id -> scenarios.id`.
2. FK `dependency_file_id -> dependency_files.id`.
3. `ref_type in ('data_source', 'upload_file')`.
4. Unique `(scenario_id, dependency_file_id, ref_type, step_id)`.
5. Index `(workspace_id, dependency_file_id)` for delete protection.
6. Index `(workspace_id, scenario_id)` for snapshot construction.

Rules:

1. Rows are replaced transactionally on Scenario create/update from the validated Scenario JSON.
2. Disabled data sources and disabled upload file entries do not create reference rows.
3. Cross-Workspace Dependency File references are rejected.
4. Dependency File delete must check this table and return `FILE_IN_USE` or `RESOURCE_IN_USE` according to the owning Slice registry.

### 9.3 `run_creation_dedup_keys`

Purpose: server-side short-window deduplication for public Run creation.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `workspace_id` | `char(26)` | yes | Workspace boundary. |
| `dedup_key_hash` | `text` | yes | SHA-256 over canonical dedup input. |
| `run_id` | `char(26)` | yes | Created Run. |
| `expires_at` | `timestamptz` | yes | P0 default `created_at + 30 seconds`. |
| `created_at` | `timestamptz` | yes | UTC. |

Constraints and indexes:

1. FK `workspace_id -> workspaces.id`.
2. FK `run_id -> runs.id`.
3. Unique `(workspace_id, dedup_key_hash)`.
4. Index `(expires_at)` for cleanup.

Dedup key input for P0-05 Scenario Debug Run:

```json
{
  "workspaceId": "<workspace>",
  "triggeredByUserId": "<user>",
  "runType": "debug",
  "sourceType": "debug_scenario",
  "sourceId": "<scenarioId>",
  "scenarioRevision": 3,
  "envGroupId": "<envGroupId-or-null>",
  "selectedNodeId": "<loadNodeId>",
  "snapshotHash": "<sha256>"
}
```

Rules:

1. Deduplication window default: 30 seconds.
2. Deduplication happens after auth, Workspace, permission, Scenario, Env Group and Load Node visibility checks.
3. Deduplication lookup happens before returning `LOAD_NODE_BUSY` for the same user/source/node/snapshot in the short window.
4. A dedup hit returns the existing Run and does not create another node lease or start request.
5. Dedup hit must re-check `workspace_id` equality before returning the Run.
6. Expired dedup rows may be deleted opportunistically by the Run creation service and periodically by `api-worker`.
7. P0 does not introduce a generic `Idempotency-Key` middleware.
8. P0-06 must reuse this mechanism for Test Plan Run Now and Test Plan Debug.

### 9.4 Run Snapshot Extension

For `sourceType='debug_scenario'`, `run_snapshots.snapshot_json` extends P0-04 shell with:

```json
{
  "snapshotVersion": 1,
  "runType": "debug",
  "sourceType": "debug_scenario",
  "sourceId": "01HZX3Y9M0E9W7Z6M5QK9S8P7P",
  "sourceRevision": 3,
  "debugProfile": {
    "executor": "jmeter",
    "concurrency": 1,
    "iterations": 1,
    "rampUp": null,
    "holdFor": null
  },
  "scenario": {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7P",
    "name": "Checkout flow",
    "scenarioType": "visual",
    "baseUrlExpression": "${base_url}",
    "defaultSettings": {},
    "dataSources": [],
    "steps": []
  },
  "envGroup": {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7Q",
    "name": "Staging",
    "variables": {
      "base_url": "https://staging.example.internal"
    }
  },
  "dependencyFiles": [
    {
      "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7R",
      "filename": "users.csv",
      "sizeBytes": 1234,
      "sha256": "...",
      "refType": "data_source",
      "stepId": null
    }
  ]
}
```

Rules:

1. Snapshot is immutable after Run creation.
2. Snapshot copies the saved Scenario revision used by Debug Run.
3. Snapshot copies P0 Env Group regular variable values because P0 has no Secret type.
4. Snapshot must not include future P2 secret encryption fields as active behavior.
5. Snapshot must not include MinIO object keys, storage credentials, SSH credentials, runner token, session cookie or CSRF token.
6. Snapshot dependency file entries use safe metadata only; worker resolves object storage access through API-owned storage adapters.

---

## 10. API Contract

All public APIs use:

1. `/api/v1` prefix;
2. cookie session auth;
3. `x-workspace-id` for Workspace-aware business resources;
4. `x-csrf-token` for `POST`, `PATCH` and `DELETE`;
5. camelCase JSON fields;
6. generated OpenAPI as source of frontend client/types.

### 10.1 Shared Enums

```text
ScenarioType = visual
HttpMethod = GET | POST | PUT | PATCH | DELETE | HEAD | OPTIONS
BodyType = none | raw | form
ExtractorType = jsonpath | regexp
AssertionType = status_code | body_contains | jsonpath_exists | jsonpath_equals
ScriptExecute = before | after
ScriptLanguage = groovy
RunType = debug | standard
RunSourceType = protocol_smoke | debug_scenario | test_plan
```

P0-05 activates only:

1. `ScenarioType.visual`;
2. `RunType.debug` for public create;
3. `RunSourceType.debug_scenario` for public create.

### 10.2 `ScenarioSummary`

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "name": "Checkout flow",
  "description": "Critical checkout APIs",
  "tags": ["checkout", "p0"],
  "scenarioType": "visual",
  "stepCount": 4,
  "enabledStepCount": 4,
  "dependencyFileCount": 1,
  "revision": 3,
  "createdAt": "2030-06-01T12:00:00.000Z",
  "updatedAt": "2030-06-01T12:30:00.000Z"
}
```

### 10.3 `ScenarioDetail`

`ScenarioDetail` includes all `ScenarioSummary` fields plus editable content:

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "name": "Checkout flow",
  "description": "Critical checkout APIs",
  "tags": ["checkout", "p0"],
  "scenarioType": "visual",
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
  "dataSources": [],
  "steps": [],
  "revision": 3,
  "createdAt": "2030-06-01T12:00:00.000Z",
  "updatedAt": "2030-06-01T12:30:00.000Z"
}
```

Rules:

1. Detail does not include deleted Scenarios.
2. Detail does not include MinIO object keys.
3. Detail may include Dependency File IDs and display filenames needed by the editor.

### 10.4 `GET /api/v1/scenarios`

Purpose: list current Workspace Scenarios.

Query params:

| Param | Required | Notes |
| --- | --- | --- |
| `page` | no | Offset pagination, default 1. |
| `pageSize` | no | Default 20, max 100. |
| `search` | no | Case-insensitive name search. |
| `tag` | no | Exact tag filter, repeated params allowed only if implementation supports AND semantics. |
| `sort` | no | P0 allowed: `-updatedAt`, `updatedAt`, `name`, `-name`. Default `-updatedAt`. |

Response: list envelope from `04` with `items: ScenarioSummary[]`.

Rules:

1. Filter by current Workspace.
2. Exclude soft-deleted rows.
3. Use offset pagination because Scenario list is human-managed and expected to be small in P0.
4. Unknown sort returns `INVALID_QUERY_PARAMETER`.

### 10.5 `POST /api/v1/scenarios`

Purpose: create Visual Scenario.

Request:

```json
{
  "name": "Checkout flow",
  "description": "Critical checkout APIs",
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
  "dataSources": [],
  "steps": [
    {
      "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
      "enabled": true,
      "name": "List products",
      "method": "GET",
      "path": "/v1/products",
      "queryParams": [],
      "headers": [],
      "body": { "type": "none", "contentType": null, "rawText": null, "formFields": [] },
      "uploadFiles": [],
      "extractors": [],
      "assertions": [
        { "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7K", "type": "status_code", "expectedStatus": 200, "enabled": true }
      ],
      "scripts": [],
      "settings": { "thinkTimeMs": null, "timeoutMs": null, "followRedirects": null, "keepAlive": null }
    }
  ]
}
```

Response:

- `201 Created`
- body: `ScenarioDetail`

Rules:

1. API sets `workspaceId`, `scenarioType`, `revision`, actor IDs and timestamps.
2. API may allow creating a draft Scenario with zero steps, but Debug Run requires at least one enabled step.
3. API validates Dependency File references and creates `scenario_dependency_file_refs` in the same transaction.
4. API returns `VALIDATION_ERROR` for invalid Step structure.

### 10.6 `GET /api/v1/scenarios/{scenarioId}`

Purpose: fetch editable Scenario detail.

Rules:

1. Lookup by `(workspace_id, id, deleted_at is null)`.
2. Cross-Workspace IDs return `RESOURCE_NOT_FOUND`.
3. Response body: `ScenarioDetail`.

### 10.7 `PATCH /api/v1/scenarios/{scenarioId}`

Purpose: update Scenario.

Request includes full editable Scenario content plus `expectedRevision`:

```json
{
  "expectedRevision": 3,
  "name": "Checkout flow",
  "description": "Critical checkout APIs",
  "tags": ["checkout", "smoke"],
  "baseUrlExpression": "${base_url}",
  "defaultSettings": {},
  "dataSources": [],
  "steps": []
}
```

Response:

- `200 OK`
- body: updated `ScenarioDetail`

Rules:

1. P0 PATCH for Scenario editor behaves as replace-editable-content, not sparse nested JSON merge. This avoids ambiguous nested Step merge semantics.
2. `expectedRevision` is required.
3. If `expectedRevision` does not match current `revision`, return `409 SCENARIO_REVISION_CONFLICT`.
4. On success, increment `revision` by 1.
5. Replace `scenario_dependency_file_refs` transactionally.
6. Active Runs using older snapshots are not modified.

### 10.8 `DELETE /api/v1/scenarios/{scenarioId}`

Purpose: soft-delete Scenario.

Response:

- `204 No Content`

Rules:

1. Lookup by `(workspace_id, id, deleted_at is null)`.
2. If Scenario is referenced by an active or non-deleted Test Plan, return `RESOURCE_IN_USE`.
3. If Scenario has an active Run in `initializing`, `running` or `stopping`, return `RESOURCE_IN_USE`.
4. Historical Run Snapshots do not block deletion.
5. Soft delete sets `deleted_at` and updates `updated_at`.
6. Soft-deleted Scenarios cannot be Debug Run sources.

### 10.9 `POST /api/v1/runs` for Scenario Debug Run

Purpose: create a Scenario Debug Run.

P0-05 request:

```json
{
  "runType": "debug",
  "sourceType": "debug_scenario",
  "sourceId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "expectedSourceRevision": 3,
  "envGroupId": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
  "selectedNodeId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C"
}
```

Response:

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7R",
  "state": "initializing",
  "runType": "debug",
  "sourceType": "debug_scenario",
  "sourceId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "selectedNodeId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
  "createdAt": "2030-06-01T12:40:00.000Z",
  "deduplicated": false
}
```

Status codes:

| Status | Meaning |
| --- | --- |
| `201 Created` | New Debug Run created. |
| `200 OK` | Short-window dedup hit; existing Run returned with `deduplicated: true`. |
| `400 WORKSPACE_REQUIRED` | Workspace context cannot be resolved. |
| `401 UNAUTHENTICATED` | Not logged in. |
| `403 FORBIDDEN` or `WORKSPACE_ACCESS_DENIED` | Actor cannot create Runs in current Workspace. |
| `404 RESOURCE_NOT_FOUND` | Scenario, Env Group or Load Node not visible in Workspace. |
| `409 SCENARIO_REVISION_CONFLICT` | `expectedSourceRevision` is stale. |
| `409 LOAD_NODE_BUSY` | Selected node is already leased and request is not a dedup hit. |
| `422 VALIDATION_ERROR` | Scenario cannot be executed, variables are missing, or request shape is invalid. |

Rules:

1. P0-05 rejects any public request where `runType != debug`.
2. P0-05 rejects any public request where `sourceType != debug_scenario`.
3. `sourceId` must be a non-deleted Scenario in current Workspace.
4. `expectedSourceRevision` is required and must match current Scenario `revision`.
5. `selectedNodeId` is required and must identify an eligible Idle Load Node visible to the Workspace.
6. `envGroupId` is optional. If provided, it must identify an Env Group in current Workspace.
7. API validates variable references against selected Env Group variables and earlier extractor outputs.
8. API validates Dependency File references and includes safe metadata in the Run Snapshot.
9. API atomically creates Run Snapshot, Run, node lease, Busy node state, dedup key and start request according to P0-04 transaction rules.
10. API does not execute SSH/SFTP or start Runner inside the DB transaction.
11. Debug Run fixed load profile cannot be overridden by client payload in P0-05.
12. Web must navigate to `/runs/:runId` on success.

### 10.10 Error Code Registry

P0-05 uses this registered central error code in addition to existing core codes:

| Code | Status | Meaning |
| --- | --- | --- |
| `SCENARIO_REVISION_CONFLICT` | 409 | Scenario was modified after the client loaded or saved it. |

Rules:

1. `SCENARIO_REVISION_CONFLICT` is registered in `04` before implementation returns it.
2. Use existing `VALIDATION_ERROR` with field-level `details` for missing variables, invalid steps, invalid body, invalid extractor, invalid assertion and invalid script content.
3. Use existing `RESOURCE_NOT_FOUND` for cross-Workspace Scenario, Env Group, Dependency File and Load Node IDs.
4. Use existing `RESOURCE_IN_USE` for Scenario deletion protection.
5. Use existing `LOAD_NODE_BUSY` for non-dedup Run creation against a leased Load Node.
6. Error messages and details must not include script text, Env Group values, MinIO object keys, server paths, SSH credentials or runner tokens.

Example revision conflict:

```json
{
  "code": "SCENARIO_REVISION_CONFLICT",
  "message": "Scenario was updated by another request. Reload and try again.",
  "requestId": "req_01HZX3Y9M0E9W7Z6M5QK9S8P7S"
}
```

Example missing variable validation:

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Scenario contains unresolved variables.",
  "details": [
    {
      "field": "steps[1].headers[0].value",
      "code": "missing_variable",
      "message": "Variable token is not provided by the selected Env Group or earlier extractors."
    }
  ],
  "requestId": "req_01HZX3Y9M0E9W7Z6M5QK9S8P7T"
}
```

---

## 11. Execution Builder Contract

### 11.1 Inputs

The execution builder receives already-authorized and already-validated input:

1. saved Scenario row;
2. selected Env Group snapshot or null;
3. selected Load Node snapshot;
4. dependency file metadata and storage access handles owned by API;
5. fixed Debug profile;
6. Run ID and runner bundle root.

### 11.2 Validation Before Bundle Generation

The builder or service must reject:

1. zero enabled steps;
2. unresolved variables not provided by Env Group or earlier extractors;
3. Env Group variable name conflict with extractor variable name;
4. invalid `baseUrlExpression` resolution;
5. resolved base URL without `http://` or `https://` scheme;
6. resolved base URL with path traversal or control characters;
7. Step path not starting with `/`;
8. duplicate enabled headers in one Step;
9. upload file reference outside current Workspace;
10. upload file unsafe bundle path;
11. `PUT` Step with more than one enabled upload file;
12. request body on `GET` or `HEAD`;
13. invalid JSR223 script content (empty or over-limit `scriptText`, unsupported `language`, or invalid `execute`);
14. YAML generation that would require unsupported Taurus fields.

### 11.3 Bundle Contents

P0 Scenario Debug Run bundle contains:

```text
bundle/
├── surgepilot.yml
├── files/
│   └── <dependencyFileId>/
│       └── <safeFilename>
└── manifest.json
```

Rules:

1. `surgepilot.yml` is generated by API/worker from snapshot content.
2. `manifest.json` contains safe diagnostic metadata such as Scenario ID, Scenario revision, Run ID and dependency file hashes.
3. Dependency Files are copied or streamed from MinIO through API-owned storage code to the Load Node bundle.
4. Bundle relative paths are normalized and must not contain `..`, absolute path prefixes, backslashes, control characters or empty segments.
5. Runner executes Taurus from the bundle directory so relative paths resolve consistently.
6. Bundle content must not include MinIO credentials, runner token or SSH credentials.

### 11.4 Generated YAML Rules

1. YAML top-level sections allowed in P0-05: `settings`, `modules`, `execution`, and `scenarios`.
2. `modules.jmeter` is required for real Runner execution and must set the configured JMeter `path`, configured JMeter `version`, `detect-plugins: false`, and `force-ctg: false` for Scenario Debug Run.
3. `execution` is always an array.
4. Scenario alias is deterministic and safe, for example `surgepilot_scenario`.
5. Request labels are derived from Step names and methods, bounded to 200 chars.
6. Query params are URL-encoded by builder; variable expressions `${var}` are preserved.
7. Header and body string values may contain `${var}` expressions.
8. `default-address` is concrete after Env Group resolution; Step path remains relative.
9. Disabled Step children are omitted.
10. JSR223 `compile-cache` defaults to `true`.
11. Builder maps Scenario default settings to Taurus scenario-level names: `storeCache -> store-cache`, `storeCookie -> store-cookie`, `keepAlive -> keepalive`, `followRedirects -> follow-redirects`, `retrieveResources -> retrieve-resources`, `thinkTimeMs -> think-time`, and `timeoutMs -> timeout`; it must not emit camelCase setting names in YAML.
12. Builder maps API `dataSources[].variableNames` to Taurus `data-sources[].variable-names` as a delimiter-separated string, for example `["username", "password"]` becomes `variable-names: username,password`.
13. Builder maps API `dataSources[].quoted` to Taurus `data-sources[].quoted` only when the value is `true` or `false`; when `quoted` is `null`, the generated YAML must omit the `quoted` key so Taurus/JMeter can auto-detect it.
14. Builder converts SurgePilot millisecond settings to compact Taurus time strings; whole-second values use `s` notation.
15. The builder must produce stable canonical YAML for snapshot hash / test comparisons.

### 11.5 JMeter Offline Runtime Contract

1. Load Node initialization must verify the configured Apache JMeter binary exists, is executable, and matches the configured P0 JMeter version before the node can be selected for real Scenario Debug Runs.
2. The P0 default configured JMeter version is Apache JMeter 5.6.3, which requires Java 8 or later.
3. Scenario Debug Run YAML must point `modules.jmeter.path` to the verified binary path.
4. Scenario Debug Run YAML must set `detect-plugins: false`; P0-05 generated YAML must not rely on JMeter Plugins Manager network access.
5. Scenario Debug Run YAML must set `force-ctg: false` because P0-05 Debug profile does not use Taurus `steps` and must not require Custom Thread Groups plugins.
6. Worker/Runner must fail the Run with a safe startup failure reason if the configured JMeter binary is missing at execution time.
7. Taurus auto-install and plugin auto-detection are not valid P0 acceptance paths.
8. No-download correctness depends on the generated `modules.jmeter.path`, the Load Node's verified JMeter installation, and Runner `bzt -n`; environment guards such as `TAURUS_DISABLE_DOWNLOADS` are not acceptance criteria.

### 11.6 Runner Boundary

P0-05 does not change P0-04 Runner protocol.

Rules:

1. API/worker owns bundle generation and safe Dependency File staging.
2. Runner receives bundle and starts Taurus/JMeter according to P0-04 remote start contract.
3. Runner must not import API internals.
4. Runner must not access PostgreSQL or MinIO directly.
5. Runner callbacks and artifacts still use `/api/internal/v1/runner/...` and `x-runner-token` only.
6. Fake runner tests for P0-05 must share callback client and contract with real Runner path where possible.

---

## 12. Variable Resolution Rules

### 12.1 Variable Sources

Variables can come from:

1. selected Env Group variables;
2. CSV data source variables declared by `variableNames` or the CSV first row;
3. extractors from earlier enabled Steps.

P0-05 does not support:

1. secret variables;
2. user-defined global variables outside Env Group or Scenario data sources;
3. computed variables other than JSR223 runtime code;
4. cross-Scenario variables.

### 12.2 Validation Algorithm

For Debug Run creation:

1. initialize `availableVariables` with selected Env Group variable names, or empty set if no Env Group is selected;
2. add enabled data source variable names when explicitly configured;
3. scan enabled Steps in order;
4. for each Step, collect `${var}` references in path, query param values, header values, body values and assertion/extractor fields where runtime variables are supported; JSR223 `scriptText` is treated as Groovy code and is not scanned for `${var}` references;
5. any referenced `var` absent from `availableVariables` is a validation error, unless it is a known JMeter built-in expression explicitly allowlisted by implementation;
6. after validating the Step, add extractor `variableName` values from that Step to `availableVariables` for later Steps;
7. reject extractor names that conflict with Env Group variable names or earlier extractor names;
8. reject variable names outside `[A-Za-z_][A-Za-z0-9_]*`.

Rules:

1. Variable validation happens on Debug Run creation, not only on Scenario save, because Env Group selection is part of execution input.
2. Scenario save may warn about unresolved variables but must allow saving reusable Scenarios.
3. API is the authority for execution validation; frontend validation is only assistive.
4. P0 does not log variable values from Env Group.

### 12.3 Base URL Resolution

Rules:

1. `baseUrlExpression` may reference Env Group variables.
2. `baseUrlExpression` must not reference extractor variables because it is resolved before request execution.
3. API resolves `baseUrlExpression` to `default-address` before generating YAML.
4. Resolved base URL must use `http://` or `https://`.
5. API must not make network calls to the resolved base URL during validation.
6. Runner/JMeter performs actual target requests from the selected Load Node.

---

## 13. Frontend Contract

### 13.1 Routes and Navigation

P0-05 implements:

| Page | Route | Layout |
| --- | --- | --- |
| Scenario List | `/scenarios` | `AppLayout` |
| Scenario Designer | `/scenarios/:scenarioId` | `AppLayout` |

Rules:

1. Routes are feature-owned under `apps/web/src/features/scenarios/routes.tsx` or equivalent established structure.
2. Root router only aggregates route objects.
3. Business data uses TanStack Query, not React Router loaders.
4. Web consumes generated types/client through `@surgepilot/contracts` only.
5. No P1/P2 clickable routes are added.
6. Debug Run success navigates to `/runs/:runId`; if P0-07 report page is not fully implemented yet, route handoff may show only a minimal Run-owned handoff view and must not expose P1/P2 capability.

### 13.2 Scenario List Page

Page capabilities:

1. list Scenarios with name, tags, enabled step count, dependency file count and updated time;
2. search by name;
3. sort by updated time or name;
4. create Scenario;
5. open Scenario Designer;
6. delete Scenario with confirmation;
7. show empty, loading, error and permission states.

Rules:

1. Create Scenario uses a small form for name, description and optional base URL expression.
2. On successful create, navigate to `/scenarios/:scenarioId`.
3. Delete confirmation warns that historical Run Reports keep snapshots.
4. Delete blocked by references shows stable copy based on `RESOURCE_IN_USE`.

### 13.3 Scenario Designer Page

Page sections:

1. Scenario header: name, tags, revision, save status;
2. Global context: `baseUrlExpression`, URL preview helper, default request settings;
3. Dependency files: data sources list and per-step upload file selectors;
4. Step list: add, duplicate, delete, enable/disable and reorder;
5. Step editor: method, path, query params, headers, body, upload files, extractors, assertions, scripts and settings;
6. Debug panel/modal: Env Group selector, Load Node selector, Save and Debug action.

Rules:

1. UI labels use product terms Scenario, Visual Scenario, Step and Debug Run.
2. User-facing copy is English only.
3. Unsaved changes must be visible.
4. Navigating away with unsaved changes prompts the user.
5. Debug action is disabled until the Scenario has at least one enabled Step and a selected Idle Load Node.
6. If there are unsaved changes, primary action is `Save and Debug`; the frontend must save first, then call `POST /api/v1/runs` with the returned revision.
7. Frontend must not execute Debug Run against local unsaved draft content.
8. Frontend must not build Taurus YAML.
9. Frontend must not call internal Runner endpoints.
10. Frontend must not display generated YAML preview in P0.

### 13.4 Step Editor UX

Minimum controls:

1. Method select;
2. Path input with URL Preview;
3. Query Params key/value table;
4. Headers key/value table;
5. Body type tabs: None, Raw, Form;
6. Upload Files selector from current Workspace Dependency Files;
7. Extractors editor for JSONPath and Regexp;
8. Assertions editor for Status Code, Body Contains, JSONPath Exists and JSONPath Equals;
9. Scripts editor for Groovy Before / After;
10. Settings editor for think time and timeout overrides.

Rules:

1. The Step Editor may be implemented with source-owned UI primitives only.
2. Monaco or heavy code editors are not introduced in P0.
3. Script editor uses a plain text area for bounded Groovy `before`/`after` script text; no file selector is used for Step scripts in P0.
4. Reorder should preserve Step IDs.
5. Duplicate Step creates new Step and child IDs.
6. Field-level validation uses generated contract validation where available and frontend Zod only for UX assistance.
7. API validation errors are mapped by `details[].field` where possible.

### 13.5 Debug Panel UX

Debug panel shows:

1. selected Env Group, optional;
2. selected Load Node, required;
3. fixed Debug profile copy: `1 virtual user - 1 iteration`;
4. warning if Scenario has unresolved variables for the selected Env Group;
5. warning if Scenario contains JSR223/Groovy scripts;
6. submit state and duplicate-submission protection.

Rules:

1. Load Node selector only shows eligible Idle nodes from generated Load Node API types.
2. If no Idle nodes are available, show a link to `/resources/load-nodes` and do not auto allocate.
3. Frontend prevents duplicate clicks, but API dedup remains authoritative.
4. On `201` or dedup `200`, navigate to `/runs/:runId`.
5. On `SCENARIO_REVISION_CONFLICT`, show reload prompt.
6. On `LOAD_NODE_BUSY`, refresh Load Node options.
7. On `VALIDATION_ERROR`, keep the user on the page and show field errors where possible.

---

## 14. Security, Permission, and Workspace Rules

### 14.1 Authentication and CSRF

1. Scenario list/detail require session auth.
2. Scenario create/update/delete require session auth and CSRF.
3. Debug Run create requires session auth and CSRF.
4. Missing session returns `UNAUTHENTICATED`.
5. Missing or invalid CSRF on writes returns the central CSRF error defined by the auth slice.

### 14.2 Workspace Enforcement

1. All Scenario queries filter by current Workspace.
2. `x-workspace-id` is used for workspace-aware APIs according to `04`.
3. Missing `x-workspace-id` may fall back to default Workspace per P0 rules.
4. Cross-Workspace Scenario, Env Group, Dependency File and Load Node IDs return `RESOURCE_NOT_FOUND` or `WORKSPACE_ACCESS_DENIED` according to Foundation rules.
5. Run Snapshot `workspace_id` equals Run and Scenario Workspace.

### 14.3 Authorization

P0 permissions:

1. Admin and User can create, edit, delete and Debug Run Scenarios in their current Workspace.
2. Backend enforces permissions; frontend hiding is not authority.
3. Public Load Node vs Private Load Node visibility follows P0-03.
4. Debug Run can only use Load Nodes visible to the current Workspace and eligible for manual single-node execution.

### 14.4 Dependency File Safety

1. Scenario may reference only current Workspace Dependency Files.
2. API never returns MinIO object keys to Web.
3. Runner bundle paths are generated by API/worker and normalized.
4. Bundle paths must be under the Run directory.
5. Dependency File filenames shown in UI are display-only and must not be used as trusted paths.
6. ZIP / TAR / TGZ auto extraction is forbidden in P0.

### 14.5 Script Safety

1. JSR223/Groovy scripts execute on the selected Load Node as part of JMeter.
2. UI must warn users before Debug Run when enabled scripts exist.
3. API enforces script size limits.
4. API and worker logs must not include Groovy script text.
5. Scripts are not scanned for secrets in P0; users must treat Env Group variables as regular P0 variables.
6. P0 does not provide sandboxing, per-script permissions or script library management.

### 14.6 URL and Network Safety

1. API validates URL syntax but does not call target URLs.
2. Actual target requests originate from the selected Load Node.
3. P0 does not implement SSRF protection for user-authored load-test targets beyond Workspace authorization and Load Node selection because the product purpose is to generate internal HTTP traffic.
4. Future enterprise network allow/deny policies are P2 unless explicitly reprioritized.

### 14.7 Audit Events

P0-05 follows `06` §14.3: ordinary Scenario CRUD does not require full P0 audit coverage.

P0-05 uses this execution-control audit event registered in `06`:

| Event | Trigger | Sensitive data rule |
| --- | --- | --- |
| `run.debug_requested` | Scenario Debug Run requested | Include run ID, scenario ID, revision, selected node ID and request ID; no Env values, Step body, script text, credentials or storage paths. |

Rules:

1. Scenario create/update/delete may use normal structured application logs, but P0-05 must not require audit log UI or audit export.
2. If implementation decides to audit Scenario CRUD later, it must first update `06` and keep details safe and bounded.

---

## 15. Contract-First Workflow

Implementation order:

1. Update API Pydantic schemas and route contracts first.
2. Export OpenAPI with `make generate-contracts`.
3. Generate Web client/types in `packages/contracts`.
4. Implement Web using `@surgepilot/contracts` imports only.
5. Add/adjust contract tests to prevent stale OpenAPI or handwritten API shapes.

Rules:

1. `packages/contracts/openapi/api.openapi.json` is generated, not handwritten.
2. Web must not import generated files through relative paths.
3. Internal Runner endpoints must not enter the Web generated client.
4. Web must not invent Scenario or Run request shapes outside generated contracts.
5. `SCENARIO_REVISION_CONFLICT` must remain registered in the central error registry before implementation returns it.

---

## 16. Implementation Notes and Handoffs

### 16.1 P0-04 Handoff

P0-05 uses P0-04 services for:

1. atomic Run + Run Snapshot + node lease creation;
2. Load Node Busy state updates;
3. start request creation;
4. callback state convergence;
5. Stop idempotency;
6. heartbeat timeout;
7. force-kill cleanup and quarantine.

P0-05 must not reimplement Run state transitions.

### 16.2 P0-06 Handoff

P0-06 must reuse or extend:

1. `POST /api/v1/runs` request/response infrastructure;
2. Run creation dedup mechanism;
3. Visual Scenario snapshot embedding;
4. Taurus request scenario generation;
5. selected single-node validation.

P0-06 adds:

1. Test Plan source validation;
2. `runType=standard`;
3. `sourceType=test_plan`;
4. full Load Settings;
5. SLA minimum subset;
6. Test Plan Debug and Run Now UX.

### 16.3 P0-07 Handoff

P0-07 consumes:

1. Run IDs created by Scenario Debug Run;
2. `debug_scenario` Run Snapshot payload;
3. artifacts uploaded by Runner;
4. generated Taurus/JMeter final stats artifacts. Failed requests plugin artifacts are deferred to P1.

P0-07 owns:

1. Run Report detail API/UI;
2. artifact list/download/preview;
3. validity marking;
4. KPI summary and failure preview.

---

## 17. Tests

### 17.1 API Unit Tests

Required:

1. Scenario validation accepts minimal valid Scenario.
2. Scenario validation rejects invalid method.
3. Scenario validation rejects Step path not starting `/`.
4. Scenario validation rejects duplicate enabled headers case-insensitively.
5. Scenario validation rejects GET/HEAD body.
6. Scenario validation rejects PUT with multiple enabled upload files.
7. Scenario validation rejects invalid variable names.
8. Scenario validation rejects over-limit raw body and rejects invalid script content such as empty or over-limit `scripts[].scriptText`.
9. Dependency File reference extraction creates only expected `data_source` and `upload_file` refs; inline JSR223 scripts do not create refs.
10. Variable resolution accepts Env Group variables and earlier extractor variables.
11. Variable resolution rejects missing variables.
12. Variable resolution rejects Env Group/extractor variable name conflicts.
13. Taurus builder maps status code assertion to `assert` with `subject: http-code`.
14. Taurus builder maps JSONPath extractor to `extract-jsonpath` full form.
15. Taurus builder maps upload files to safe bundle-relative paths.
16. Taurus builder maps `defaultSettings.followRedirects` to `follow-redirects` and never emits camelCase setting names in YAML.
17. Taurus builder maps `variableNames` to `variable-names` for CSV data sources.
18. Taurus builder omits `quoted` for `quoted=null` and emits `quoted: true/false` only for non-null values.
19. Taurus builder converts `timeoutMs=30000` to `timeout: 30s` in generated YAML.
20. Taurus builder emits `modules.jmeter.path`, `version`, `detect-plugins: false` and `force-ctg: false`.
21. Taurus builder never emits MinIO object keys or server absolute paths.
17. Snapshot builder excludes credentials and includes Scenario revision.
18. Dedup key hash is stable for canonical equivalent input.

### 17.2 API Integration Tests

Required:

1. Create Scenario returns `201` and `revision=1`.
2. List Scenarios is Workspace-isolated.
3. Get Scenario cross-Workspace returns `RESOURCE_NOT_FOUND`.
4. PATCH with matching `expectedRevision` increments revision.
5. PATCH with stale revision returns `SCENARIO_REVISION_CONFLICT`.
6. PATCH updates Dependency File refs transactionally.
7. DELETE soft-deletes Scenario and removes it from list.
8. DELETE referenced Scenario returns `RESOURCE_IN_USE`.
9. Debug Run with valid Scenario, Env Group and Idle Load Node creates Run `initializing`.
10. Debug Run creates Run Snapshot with Scenario, Env Group and Dependency File metadata.
11. Debug Run marks selected Load Node Busy through P0-04 lease flow.
12. Duplicate Debug Run request within 30 seconds returns existing Run with `deduplicated=true`.
13. Duplicate Debug Run request does not create a second node lease.
14. Debug Run with busy node and no dedup hit returns `LOAD_NODE_BUSY`.
15. Debug Run stale Scenario revision returns `SCENARIO_REVISION_CONFLICT`.
16. Debug Run missing variable returns `VALIDATION_ERROR` with field details.
17. Debug Run with Env Group from another Workspace returns `RESOURCE_NOT_FOUND`.
18. Debug Run with Dependency File from another Workspace returns `RESOURCE_NOT_FOUND`.

### 17.3 Contract Tests

Required:

1. Scenario endpoints appear in exported OpenAPI under `/v1/scenarios`.
2. Public `POST /v1/runs` includes only P0-05 allowed public create schema until P0-06 extends it.
3. API fields are camelCase.
4. `SCENARIO_REVISION_CONFLICT` appears in documented error responses for save and Debug revision conflicts.
5. Generated Web client exposes Scenario CRUD and public Run create.
6. Generated Web client does not expose `/api/internal/v1/runner/...`.
7. OpenAPI stale check fails when contracts are not regenerated after schema changes.

### 17.4 Web Tests

Required:

1. Scenario List renders loading, empty, error and populated states.
2. Create Scenario submits through generated client and navigates to detail.
3. Scenario Designer loads detail via TanStack Query.
4. Step add, duplicate, delete, enable/disable and reorder preserve expected IDs.
5. URL Preview updates from base URL, path and query params.
6. Save sends `expectedRevision` and handles success.
7. Stale revision error shows reload prompt.
8. Unsaved navigation prompts user.
9. Debug panel requires one Idle Load Node.
10. Save and Debug saves first, then creates Debug Run with returned revision.
11. Debug Run success navigates to `/runs/:runId`.
12. `LOAD_NODE_BUSY` refreshes node options.
13. Script warning appears when enabled JSR223/Groovy scripts exist.
14. Web does not contain internal Runner endpoint strings.
15. Web does not render Generated YAML Preview.

### 17.5 Runner / Smoke Tests

Required fake-runner smoke:

1. Scenario Debug Run happy path reaches `finished` through P0-04 callback flow.
2. Scenario Debug Run failed path reaches `failed`.
3. Stop from Scenario Debug Run reaches `aborted` and releases node safely.
4. Artifact upload from Scenario Debug Run creates metadata without object key exposure.

Real or near-real SSH/Taurus smoke belongs to `make verify-e2e` when an SSH-capable Load Node environment is provided.

---

## 18. Verification Commands

Implementation must run:

```bash
make generate-contracts
make verify
```

When real SSH/Taurus environment is available, run:

```bash
make verify-e2e
```

Targeted commands during implementation may include:

```bash
uv run --all-packages pytest apps/api/tests -k "scenario or debug_run"
uv run --all-packages pytest apps/runner/tests -k "callback or artifact or fake_runner"
pnpm --filter @surgepilot/web test -- scenarios
pnpm --filter @surgepilot/web typecheck
make contracts-stale-check
```

Rules:

1. `make verify` remains the default completion gate.
2. If `make verify-e2e` cannot run due to missing SSH/Taurus environment, final response must state the environment gap.
3. Documentation-only changes may run a lighter grep/format check, but implementation PRs must run the full gates above.

---

## 19. Done When

P0-05 is done when:

1. Scenario CRUD API is implemented with Workspace, auth, CSRF and permission checks.
2. Scenario Pydantic schemas export correct OpenAPI.
3. Web uses generated Scenario and Run client/types through `@surgepilot/contracts`.
4. Visual Scenario stores and returns P0 Step model fields.
5. Scenario revision conflict is enforced on save and Debug Run.
6. Dependency File references are validated, stored and used for delete protection.
7. Scenario Debug Run uses `POST /api/v1/runs` with `runType=debug` and `sourceType=debug_scenario`.
8. Run creation dedup returns existing Run within short window and does not create duplicate leases.
9. Debug Run uses fixed low-risk profile and manual single Idle node selection.
10. Run Snapshot contains Scenario, Env Group, Dependency File and Debug profile data without sensitive infrastructure values.
11. Taurus YAML generation follows the mapping in §7 and §11, including fixed offline JMeter module settings.
12. Generated YAML remains internal and is not editable or previewed in P0 UI.
13. Scenario List and Designer routes follow `08` routing and data-fetching rules.
14. Save and Debug executes only saved Scenario revisions.
15. Debug success navigates to `/runs/:runId`.
16. API, contract, web and smoke tests from §17 pass.
17. `make generate-contracts` and `make verify` pass.
18. No P1/P2 user-visible capability is introduced.

---

## 20. Review Checklist

### 20.1 Scope

- [ ] Does the change stay within Visual Scenario and Scenario Debug Run?
- [ ] Does it avoid API Catalog, cURL import, OpenAPI import and Test Plan Run Now?
- [ ] Does it avoid editable Taurus YAML and Generated YAML Preview?
- [ ] Does it avoid auto allocation, node count, selected nodes array and multi-node execution?
- [ ] Does it avoid Schedule Run and Monitoring?

### 20.2 Contracts

- [ ] Are API schemas source of truth for OpenAPI?
- [ ] Are generated contracts refreshed?
- [ ] Does Web use `@surgepilot/contracts` only?
- [ ] Are API fields camelCase?
- [ ] Are enum values lower snake case where applicable?
- [ ] Are error codes registered before implementation returns them?

### 20.3 Scenario and Taurus

- [ ] Does every UI field map to an official Taurus/JMeter field or remain API-only metadata?
- [ ] Are generated YAML paths bundle-relative and safe?
- [ ] Does generated YAML include fixed `modules.jmeter.path`, `version`, `detect-plugins: false` and `force-ctg: false`?
- [ ] Does the builder map `followRedirects` to `follow-redirects`, map `variableNames` to `variable-names`, omit `quoted` when null, and use compact Taurus time strings?
- [ ] Is `default-address` resolved safely from `baseUrlExpression`?
- [ ] Are unsupported Taurus logic blocks hidden from P0 UI/API?
- [ ] Are JSR223 scripts limited to Groovy before/after blocks with bounded inline `scriptText`?
- [ ] Is generated YAML internal only?

### 20.4 Run and Node Safety

- [ ] Does Debug Run use P0-04 Run state machine service?
- [ ] Does Run creation atomically acquire a single node lease?
- [ ] Does dedup avoid duplicate leases and duplicate starts?
- [ ] Does selected node validation enforce Idle and Workspace visibility?
- [ ] Does Stop remain P0-04-owned and idempotent?

### 20.5 Security

- [ ] Are all public writes protected by CSRF?
- [ ] Are all resources filtered by Workspace?
- [ ] Are Dependency File refs current-Workspace only?
- [ ] Are MinIO object keys never returned to Web?
- [ ] Are SSH credentials, runner tokens and storage credentials excluded from snapshots and logs?
- [ ] Are script text and Env values excluded from audit details and general logs?

### 20.6 Frontend

- [ ] Are routes feature-owned and lazy-loaded?
- [ ] Does business data use TanStack Query?
- [ ] Does Save and Debug save first and use returned revision?
- [ ] Does Debug require one Idle Load Node?
- [ ] Does Debug success navigate to `/runs/:runId`?
- [ ] Does UI copy remain English only and centralized?

### 20.7 Verification

- [ ] `make generate-contracts` was run after API schema changes.
- [ ] `make verify` passed.
- [ ] `make verify-e2e` was run when real SSH/Taurus environment was available.
- [ ] Final response lists changed files, verification commands/results and remaining risks.
