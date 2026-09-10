# P1-05 cURL Import

- Document status: Accepted for implementation
- Stage: P1
- Capability:`curl_import`
- Scope Gate:`docs/sdd/00-product-scope-and-priority.md` §6
- P1 Index:`docs/sdd/slices/P1-README.md`
- Scenario Boundary:`docs/sdd/slices/P0-05-visual-scenario-debug-run.md`
- API Contract Boundary:`docs/sdd/04-api-contract-guidelines.md`
- Security Boundary:`docs/sdd/06-security-permission-workspace.md`
- Frontend Route Boundary:`docs/sdd/08-frontend-routing-and-ui-rules.md`
- Testing Boundary:`docs/sdd/09-testing-and-acceptance-strategy.md`

## 1. Goal

P1-05 Added **cURL -> Single HTTP Step preview import** capability in Visual Scenario Designer. Users can paste a common single HTTP/HTTPS `curl` command, first view the parsed Step preview, Scenario-level `baseUrlSuggestion`, warnings and unsupported options, and then confirm to merge it into the current Scenario draft.

Goal:

1. Reduce the cost for users to manually enter Method, Path, Query, Headers, Body and basic request settings.
2. Keep the import result as the existing Visual Scenario JSON; still save it through the existing Scenario `PATCH` after importing.
3. Clearly prompt the risks of sensitive information such as Authorization, Cookie, API key, etc., and only enter the Scenario draft and save link after confirmation by the user.
4. No new DB tables, no changes to the Runner protocol, no changes to the Run state machine, no new API Catalog / OpenAPI / Test Plan generation links.

P1-05 is an experience enhancement and must not become a pre-dependency of the main link of P0 Scenario -> Test Plan -> Run -> Run Report.

## 2. PRD / Scope Trace

PRD has listed `Import from cURL(P1)` in the Visual Designer feature manifest and requires P1 to prompt for sensitive information risks when cURL import is enabled. `docs/sdd/00-product-scope-and-priority.md` §6 Fixed P1 Import to be a cURL import and made it clear that P1 does not contain any OpenAPI / API Catalog -> Scenario / Test Plan generation links.

This Slice locks in the following conclusions:

1. P1-05 only enables cURL single-step import in Visual Scenario Designer.
2. The API only does parsing and preview; it does not directly create, update or save Scenario.
3. After the web user confirms, the full Scenario draft is still saved via the existing Scenario `PATCH`.
4. `baseUrlSuggestion` is a Scenario-level suggestion, and the target take field is the existing `baseUrlExpression`; it is never a Step field.
5. Step `path` must remain a relative path and start with `/`; URL origin must never be written.
6. It is still in the development stage. This article defines API, Web copy, testing and contracts in the target state without setting up historical clients or old data compatibility layers.

Governance prerequisites:

1. The implementation of P1-05 is authorized only after this document exists as the active P1 Slice SDD.
2. `P1-README.md` is only used as an index; the implementation must not be started directly from the placeholder copy.
3. If the implementation requires API Catalog, OpenAPI upload, OpenAPI Step generation, Postman/JMX/Locust import, Test Plan automatic generation, Runner modification, Secret framework or general desensitization framework, you must first add ADR or update PRD/Scope Gate.

## 3. In Scope

1. API parse endpoint: Add a Scenario domain lightweight parsing interface, input raw cURL text, and output Step draft preview, `baseUrlSuggestion`, warnings and unsupported options.
2. Parser service: Add an independent pure function parser, such as `apps/api/app/services/curl_import.py`, which uses the Python standard library to complete tokenization and field mapping.
3. API schemas: Add cURL parse request / response Pydantic schemas and export them through FastAPI OpenAPI.
4. Web Scenario Designer: Added `Import from cURL` button / modal, supports paste -> parse -> preview -> confirm merge.
5. Merge semantics: Support append imported Step or replace the currently selected Step; mark dirty after confirmation, and ultimately still use the existing `patchScenario`.
6. Sensitive warning: Risk warnings are given for Authorization, Cookie, Set-Cookie, x-api-key, token/password/secret/key class header or body/form key.
7. Tests / verification gates: API parser fixtures, route auth/workspace/CSRF, Web modal and merge behavior, generated contract freshness.

## 4. Out of Scope

1. API Catalog, OpenAPI / Swagger upload, API Spec detail page, OpenAPI Step auto-generation or API -> Scenario/Test Plan generation.
2. Import from Postman Collection, JMX, Locust, HAR, YAML, Taurus YAML or other formats.
3. Batch import multiple Steps, batch asset import or automatically create Test Plan.
4. Local file path reading, automatic uploading Dependency File, `@file` body automatic reading or multipart file upload mapping.
5. Execute any shell commands, initiate network requests, DNS resolution, and call the real `curl`.
6. Secret Env Group, universal secret masking/reveal workflow, and universal log desensitization framework.
7. Runner, api-worker, Run Snapshot, Run state machine, Taurus builder or load node behavior changes.
8. You can edit Taurus YAML or reversely generate Scenario from YAML.
9. New DB table, migration, persistence raw cURL, audit details record raw cURL.
10. New open-source runtime dependency.

## 5. Preconditions

1. P0 Visual Scenario already has `baseUrlExpression`, `steps[]`, `queryParams`, `headers`, `body`, `uploadFiles`, `assertions`, `scripts` and step-level `settings` models.
2. Step `path` must start with `/`, absolute URLs are never accepted; URL origin can only enter the Scenario level `baseUrlExpression` suggestion.
3. Scenario CRUD already has `PATCH /api/v1/scenarios/{scenarioId}` and revision checks; P1-05 does not add a new save transport.
4. Business APIs continue to use cookie session, `x-workspace-id` and browser write CSRF.
5. Web API calls continue to use `@surgepilot/contracts` through generated client/types; handwritten request/response types are not allowed.
6. Existing Scenario checksums and Taurus built links continue to be used as back-up constraints for execution after saving.
7. There are no historical compatibility issues at the current development stage; there is no need to be compatible with old cURL import endpoints, old response schema or old clients.

## 6. Locked Core Decisions

| ID | Decision |
| --- | --- |
| CURL-01 | P1-05 is a Visual Scenario Designer import feature, not an API Catalog or Test Plan generation feature. |
| CURL-02 | Parsing happens API-side; confirmation and Scenario draft merge happen Web-side. |
| CURL-03 | The parse endpoint is preview-only and must not persist raw cURL, Scenario changes, audit details, Run data, artifacts or logs containing raw input. |
| CURL-04 | Confirmed import still saves through existing Scenario `PATCH`; no new Scenario save endpoint is added. |
| CURL-05 | `baseUrlSuggestion` maps only to Scenario `baseUrlExpression` when the user explicitly applies it. |
| CURL-06 | Imported Step data must use existing Visual Scenario fields only; no new Step field is introduced. |
| CURL-07 | Step IDs and child item IDs are materialized by Web merge logic using existing Scenario model helpers; API parse response must not become the source of persisted IDs. |
| CURL-08 | Parser implementation uses Python standard library only, primarily `shlex` and `urllib.parse`; no `curlconverter`-style dependency is added in P1. |
| CURL-09 | Parser must never execute shell, invoke `curl`, read local files, perform DNS, or make network calls. |
| CURL-10 | Unsupported cURL options are reported as warnings or validation details; they are not silently treated as executed behavior. |
| CURL-11 | Sensitive values pasted by the user may appear in the same-user preview and saved Scenario after confirmation, but the API and Web must warn before confirmation and must not log or audit raw values. |
| CURL-12 | P1-05 does not change Runner protocol, Run state machine, snapshot schema, Taurus YAML builder contracts or Dependency File upload contracts. |
| CURL-13 | No DB migration or historical compatibility layer is required in the current development stage. |

## 7. Architecture

```text
Scenario Designer
  -> user opens Import from cURL modal
  -> user pastes one cURL command
  -> Web calls generated parseScenarioCurlImport client with x-workspace-id + CSRF
  -> API authenticates session, resolves Workspace and parses rawCurl in memory only
  -> API returns step draft preview + baseUrlSuggestion + warnings + unsupportedOptions
  -> Web renders preview and risk warnings
  -> user confirms append or replace and optionally applies baseUrlSuggestion
  -> Web materializes IDs and merges into Scenario draft
  -> Scenario draft is dirty but not persisted yet
  -> existing Save uses PATCH /api/v1/scenarios/{scenarioId}
  -> existing Scenario validation, revision, snapshot and Taurus builder chain applies later
```

Component boundaries:

| Component | Responsibility | Forbidden |
| --- | --- | --- |
| API routes | Expose preview-only cURL parse endpoint; enforce session, Workspace, CSRF, OpenAPI schemas and safe error responses. | Persisting raw cURL; updating Scenario; bypassing Scenario `PATCH`; returning stack traces or server paths. |
| Parser service | Tokenize and map a bounded whitelist of common cURL options to a Scenario-compatible Step draft and warnings. | Shell execution, `curl` execution, network calls, DNS lookup, local file reads, heavyweight dependencies. |
| Scenario services | Remain the save-time validation and persistence boundary through existing create/patch behavior. | Special-casing imported Steps after save; adding import-specific DB state. |
| Contracts | Generate Web client/types from FastAPI/Pydantic after schema/route changes. | Hand-editing OpenAPI or generated TypeScript as source of truth. |
| Web Scenario Designer | Render modal, preview, warnings and merge choices; materialize IDs; mark draft dirty; save via existing `patchScenario`. | Pure frontend cURL parser; custom fetch type shapes; automatic save after parse; hidden API Catalog flows. |
| Runner / DB | No change. | Any P1-05 dependency on Runner, Run state, snapshots, migrations or node execution. |

## 8. API Contract

### 8.1 Endpoint

| Method | Path | Operation ID | Response | Contract |
| --- | --- | --- | --- | --- |
| `POST` | `/api/v1/scenarios/curl-import/parse` | `parseScenarioCurlImport` | `200 CurlImportParseResponse` | Parse one raw cURL command into a Scenario Step draft preview. Requires session, Workspace and CSRF. Persists nothing. |

Rules:

1. Register the static `curl-import/parse` route before dynamic Scenario routes in `apps/api/app/routes/scenarios.py` for readability and future-proofing. The current `/{scenarioId}` route is a single-segment route and does not match `/curl-import/parse`; this ordering rule avoids confusion if future Scenario child routes are added.
2. The endpoint belongs to the Scenario route domain because the output is a Scenario Step draft; it does not create an `imports` resource.
3. The endpoint requires `x-workspace-id` like other Workspace-aware business APIs.
4. The endpoint requires `x-csrf-token` even though it does not persist data, because it is a browser POST carrying sensitive user input.
5. The response should attach `x-workspace-id` on success, matching Scenario API response-header behavior.
6. No raw cURL, parsed sensitive header values, parsed body text or unsupported option values may be written to normal logs or audit details.
7. Error responses must use the repository error envelope and must not include raw command excerpts, stack traces, local paths or parser internals.

### 8.2 Request schema

`CurlImportParseRequest`:

| Field | Type | Required | Contract |
| --- | --- | --- | --- |
| `rawCurl` | string | yes | Raw cURL text pasted by the user. Trimmed length must be between 1 and 300000 characters. It is processed in memory only and never persisted. |

Rules:

1. Empty or whitespace-only input returns `422 VALIDATION_ERROR`.
2. Inputs over the bound return `422 VALIDATION_ERROR` before tokenization.
3. The `rawCurl` limit is intentionally higher than the existing Scenario raw body limit so a body that is still legal for `ScenarioBody.rawText` can include normal cURL syntax overhead. Parsed body output must still respect the existing Scenario raw body limit.
4. The parser should normalize CRLF to LF and support Unix multiline continuation with trailing `\`.
5. Windows caret continuation (`^`) may be detected and reported with a warning when the remaining tokens can still be parsed; it is not a full Windows shell compatibility contract.

### 8.3 Response schema

`CurlImportParseResponse`:

| Field | Type | Required | Contract |
| --- | --- | --- | --- |
| `step` | `CurlImportStepDraft` | yes | Request-only Step draft preview. It excludes persistent `id` fields and is materialized by Web before merging. |
| `baseUrlSuggestion` | string or null | yes | URL origin suggestion such as `https://api.example.com`. Web may apply it to Scenario `baseUrlExpression` only after user confirmation. |
| `warnings` | `CurlImportWarning[]` | yes | User-visible warnings, including sensitive value risks and non-fatal inference. Values must be safe to display. |
| `unsupportedOptions` | `CurlImportUnsupportedOption[]` | yes | Unsupported cURL option names and reason codes. Values supplied to unsupported options must not be echoed. |

`CurlImportStepDraft`:

| Field | Type | Contract |
| --- | --- | --- |
| `enabled` | boolean | Defaults to `true`. |
| `name` | string | Human-readable default label such as `GET /v1/orders`; max 120 chars. |
| `method` | `GET | POST | PUT | PATCH | DELETE | HEAD | OPTIONS` | Explicit `-X/--request` wins; body implies `POST` only when method was not explicit. |
| `path` | string | URL path only, starts with `/`; includes neither scheme nor host. |
| `queryParams` | `CurlImportNamedValueDraft[]` | URL query parameters and supported `--get` data parameters, preserving source order where practical. |
| `headers` | `CurlImportNamedValueDraft[]` | Supported headers from `-H/--header`, `--user-agent` and supported cookie shorthand. Duplicate enabled names are invalid case-insensitively; this is not enforced by the `ScenarioStep` Pydantic schema alone, so the parser must enforce it directly or reuse the existing Scenario content validation before returning preview. |
| `body` | `CurlImportBodyDraft` | Existing Scenario body shape without IDs. |
| `settings` | `CurlImportStepSettingsDraft` | Only supported cURL options mapped to existing Step settings. |

`CurlImportNamedValueDraft`:

| Field | Type | Contract |
| --- | --- | --- |
| `name` | string | Header, query or form field name. |
| `value` | string | Parsed value. |
| `enabled` | boolean | Defaults to `true`. |

`CurlImportBodyDraft`:

| Field | Type | Contract |
| --- | --- | --- |
| `type` | `none | raw | form` | Uses existing Scenario body type set. |
| `contentType` | string or null | Derived from `Content-Type` header or body inference. |
| `rawText` | string or null | Raw body text when `type=raw`; must stay within existing Scenario raw body limit. |
| `formFields` | `CurlImportNamedValueDraft[]` | Used for `application/x-www-form-urlencoded` bodies. |

`CurlImportStepSettingsDraft`:

| Field | Type | Contract |
| --- | --- | --- |
| `timeoutMs` | integer or null | Derived from supported timeout option and constrained to existing Step setting range. |
| `followRedirects` | boolean or null | Derived from `--location` / `-L` when present. |
| `keepAlive` | boolean or null | May be set only for directly supported cURL options; otherwise null. |
| `thinkTimeMs` | null | cURL import does not infer think time. |

Fields intentionally not returned in `CurlImportStepDraft`:

1. `id` and child `id` fields: Web materializes them.
2. `uploadFiles`: cURL import does not upload files.
3. `extractors`, `assertions`, `scripts`: cURL import does not infer validation or scripts. Web may preserve the existing `newStep()` default assertion when materializing a new imported Step.

### 8.4 Error and warning contract

`CurlImportWarning`:

| Field | Type | Contract |
| --- | --- | --- |
| `code` | string | Stable warning code. |
| `message` | string | English user-facing fallback. |
| `field` | string or null | Optional field path such as `headers[0].name`. |

`CurlImportUnsupportedOption`:

| Field | Type | Contract |
| --- | --- | --- |
| `option` | string | cURL option name such as `--compressed` or `-F`. |
| `reasonCode` | string | Stable reason code. |
| `message` | string | English fallback. Must not echo option value. |

Top-level error behavior:

| Condition | Response |
| --- | --- |
| Empty, too long, shell tokenization failure, missing URL, multiple URLs, non-HTTP URL, unsupported method, duplicate header after mapping, body incompatible with method, or body over Scenario limit | `422 VALIDATION_ERROR` with safe details. |
| Unsupported but ignorable option | `200` with `unsupportedOptions[]` and warning. |
| Internal parser bug | Existing safe 5xx behavior; never include raw cURL, stack trace or local path in response. |

Recommended warning codes:

| Code | Meaning |
| --- | --- |
| `SENSITIVE_HEADER_PRESENT` | A header name looks sensitive, such as Authorization, Cookie, Set-Cookie, x-api-key, token/password/secret/key. |
| `SENSITIVE_BODY_FIELD_PRESENT` | A form or JSON key looks sensitive. |
| `METHOD_INFERRED_FROM_BODY` | Method was inferred as POST because body data exists and no explicit method was provided. |
| `BASE_URL_SUGGESTED` | URL origin was parsed and can be applied to Scenario `baseUrlExpression`. |
| `UNSUPPORTED_OPTION_IGNORED` | An option was not mapped but did not block a useful preview. |
| `LOCAL_FILE_REFERENCE_UNSUPPORTED` | The command refers to a local file path or `@file`; P1-05 does not read or upload local files. |
| `WINDOWS_CARET_CONTINUATION_UNSUPPORTED` | Windows caret continuation may not have been fully interpreted. |

## 9. Parser Contract

### 9.1 Supported P1 whitelist

| cURL input | Contract |
| --- | --- |
| `curl <url>` | Create a GET Step with path/query split from the URL. |
| `--url <url>` | Treat as the URL source. |
| `-X`, `--request` | Set HTTP method when it is one of the existing Scenario `HttpMethod` values. |
| `-H`, `--header` | Parse `Name: value` headers into Step headers. Invalid header syntax returns validation error. |
| `-A`, `--user-agent` | Map to `User-Agent` header. |
| `-b`, `--cookie` with inline cookie text | Map to `Cookie` header and emit sensitive warning. File-based cookie jars are unsupported. |
| `-I`, `--head` | Map to method `HEAD`. |
| `--data`, `--data-raw`, `--data-binary`, `-d` | Map to raw or form body. Infer `POST` if method is not explicit. `@file` is unsupported. |
| `--data-urlencode` | Map to form field when possible; otherwise raw body with warning. |
| `-G`, `--get` | Convert supported data fields into query params and keep method GET unless overridden safely. |
| `-L`, `--location` | Set `settings.followRedirects=true`. |
| `--max-time <seconds>` | Convert to `settings.timeoutMs` when within existing Scenario Step timeout range. |

### 9.2 Unsupported / warning behavior

1. `-F`, `--form`, `--form-string`, `--upload-file` and multipart file upload syntax are unsupported in P1-05.
2. Any token that implies local file reads, including `@path`, `--config`, cookie jar file paths or CA/client certificate files, must not be read. The parser returns an unsupported option warning or validation error depending on whether a safe Step preview remains possible.
3. Shell expansions, environment substitutions, command substitution, pipes, redirects, process substitution and multiple shell commands are unsupported.
4. Multiple URLs in one command are invalid for P1-05 because the Slice imports exactly one HTTP Step.
5. Non-HTTP schemes such as `file:`, `ftp:`, `sftp:` or `ws:` are invalid for P1-05.
6. `--compressed`, `--connect-timeout`, TLS flags, proxy flags, retry flags and authentication helpers may be reported as unsupported; they must not be guessed into Runner behavior.
7. Unsupported options must not be silently applied to Scenario settings.

### 9.3 Mapping rules

1. URL parsing:
   - `scheme://host[:port]` becomes `baseUrlSuggestion`.
   - path becomes Step `path`; empty path becomes `/`.
   - query string becomes `queryParams[]` in URL order when practical.
2. Method parsing:
   - Explicit method wins.
   - If no method is explicit and body data exists, method becomes `POST` with `METHOD_INFERRED_FROM_BODY` warning.
   - `GET` or `HEAD` with body is invalid unless `-G/--get` moves supported data into query params.
3. Header parsing:
   - Header names must satisfy existing HTTP token rules.
   - Duplicate enabled header names are invalid case-insensitively.
   - This duplicate-header rule is not enforced by the `ScenarioStep` Pydantic schema alone. The parser must either enforce it directly or validate a temporary Scenario-compatible content payload through the existing Scenario service validation before returning preview.
   - Header value is preserved for same-user preview and possible Scenario save, but sensitive-name warning must be emitted.
4. Body parsing:
   - `application/json` or JSON-looking text maps to `body.type=raw`, `contentType=application/json` when no stricter content type is present.
   - `application/x-www-form-urlencoded` maps to `body.type=form` when it can be parsed into unique form field names.
   - Other text body maps to `body.type=raw` with the best available `contentType`.
   - Body text must respect the existing Scenario raw body limit.
5. Step name:
   - Default name should be `<METHOD> <path>` truncated to the existing 120-char limit.
6. Validation:
   - The service must validate the mapped preview by constructing a server-only Scenario-compatible Step with temporary ULIDs and running the existing Scenario Step / content validation path where practical.
   - Temporary validation IDs are not returned to Web and are not persisted.

## 10. Web UX Contract

### 10.1 Entry point

1. Scenario Designer header or Step list actions add an English `Import from cURL` control.
2. The control opens a modal; it does not navigate to a new route.
3. The modal is disabled only while parse is in progress or the Scenario detail is unavailable.

### 10.2 Modal flow

1. User pastes raw cURL text into a textarea.
2. User clicks `Preview import`.
3. Web calls `parseScenarioCurlImport` through the generated API client with `x-workspace-id` and `x-csrf-token`.
4. Web displays:
   - Method + path preview.
   - Query params, headers and body summary.
   - `baseUrlSuggestion` with an explicit apply control.
   - warnings and unsupported options.
   - a sensitive information warning whenever returned warnings include sensitive risk codes.
5. User chooses `Append after selected Step` or `Replace selected Step`.
6. User confirms; Web merges into local draft and closes or resets the modal.
7. Web marks the Scenario draft dirty. It does not save automatically.

### 10.3 Merge semantics

Append:

1. Web materializes a new Step from existing `newStep()` defaults.
2. Web overlays imported method, path, query params, headers, body and settings.
3. Web generates new Step and child IDs using existing Scenario model helpers.
4. The imported Step is inserted after the currently selected Step; if none is selected, append at the end.
5. The new imported Step becomes selected.

Replace:

1. Web preserves the selected Step list position.
2. Web may preserve the selected Step `id` because this is a Web-side draft replacement decision, but child IDs for query/header/form items must be regenerated.
3. Replace resets request-only imported fields from the preview and clears upload files, extractors and scripts.
4. Replace should use the existing default assertion behavior for a new Step unless the implementation explicitly decides the replacement should have no assertions and updates tests accordingly.
5. If no Step is selected, replace behaves as append.

`baseUrlSuggestion`:

1. Web must never write `baseUrlSuggestion` into Step `path`.
2. Web may offer `Apply to Global Config` or equivalent copy that writes the suggestion to draft `baseUrlExpression`.
3. Applying `baseUrlSuggestion` must require explicit user confirmation in the modal.
4. The UI may default the apply option to checked only when current `baseUrlExpression` is the default `${base_url}`; it must not silently overwrite a customized value.

### 10.4 Copy and state

1. User-facing copy is English only and should live in the Scenario feature copy file.
2. Parse errors should map stable API codes to actionable modal messages.
3. Sensitive warning copy must say that pasted credentials may be saved into the Scenario if the user confirms and saves.
4. Unsupported options must be shown as not imported rather than hidden.
5. Unsaved-change navigation guards continue to use the existing Scenario Designer dirty state.

## 11. Security and Privacy Constraints

1. Raw cURL is processed in memory only and must not be persisted to DB, audit details, artifacts or ordinary logs.
2. Normal logs may include request ID, actor ID, workspace ID, parse success/failure, warning codes and unsupported option names; they must not include raw command text, body text, header values or unsupported option values.
3. The parser must never execute the input or resolve external resources.
4. Sensitive values supplied by the user may appear in the same response preview because the user needs to confirm the imported Step; this is not a server-side secret reveal. The API and Web must still emit warnings before confirmation.
5. API error responses must not include stack trace, parser internals, server absolute paths or excerpts of raw cURL.
6. `unsupportedOptions[]` must include option names and reason codes only; it must not echo values that might contain tokens, file paths or credentials.
7. Local file paths from `@file`, `--config`, cert flags or cookie-jar flags must not be read and should not be echoed back.
8. No P1-05 behavior may expose MinIO object keys, Runner internal tokens, environment secrets, session cookies or CSRF values.

## 12. Observability and Diagnostics

1. No new metrics are required for P1-05.
2. If implementation adds structured logs, they must be safe metadata logs only as defined in §11.
3. Parse warnings are user-facing diagnostics, not execution diagnostics; they must not claim that a request will succeed at runtime.
4. Import preview does not validate target host reachability, DNS, TLS, auth correctness or response assertions.

## 13. Compatibility and Migration

1. No database migration is required.
2. No Runner protocol migration is required.
3. No Run Snapshot migration is required.
4. No historical API compatibility layer is required in the current development stage.
5. Generated contracts must be regenerated after API schemas/routes are implemented.

## 14. Test and Acceptance Criteria

### 14.1 API parser tests

Add parser/service fixtures for at least:

1. `curl https://example.test/v1/orders?region=sg` -> GET, `baseUrlSuggestion`, path, query.
2. `curl -X POST -H 'Content-Type: application/json' --data '{"sku":"A1"}' https://example.test/v1/orders` -> POST raw JSON body.
3. `curl -d 'a=1&b=2' https://example.test/form` -> POST form body when content type or body shape supports form mapping.
4. `curl --data-urlencode 'q=hello world' -G https://example.test/search` -> query param mapping.
5. `curl -H 'Authorization: Bearer token' -H 'x-api-key: key' https://example.test/secure` -> sensitive warnings.
6. Duplicate enabled header names -> `VALIDATION_ERROR`.
7. `--location` and valid `--max-time` -> Step settings mapping.
8. `-F file=@local.png` or `--data-binary @payload.json` -> unsupported local file behavior, no file read.
9. Multiple URLs, missing URL, unsupported scheme and malformed command -> safe `VALIDATION_ERROR`.
10. Explicit `GET` or `HEAD` with body and no `-G` -> validation error.
11. A raw cURL command whose body is within the Scenario raw body limit and whose total command length is above 262144 but within the `rawCurl` limit -> parser accepts tokenization and then applies normal body-limit validation.

### 14.2 API route / contract tests

1. Route requires authenticated session.
2. Route resolves or rejects Workspace according to existing Workspace rules.
3. Route requires CSRF.
4. Route returns generated-schema-compatible `CurlImportParseResponse`.
5. Route is not captured by `/{scenarioId}`.
6. Route persists no Scenario and increments no Scenario revision.
7. Error details are safe and do not contain raw command excerpts.
8. `make generate-contracts` updates OpenAPI and generated Web contracts.
9. Contract stale check fails when generated artifacts are stale.

### 14.3 Web tests

1. Scenario Designer shows `Import from cURL` control.
2. Modal submits through generated client wrapper and handles loading/error states.
3. Preview renders method, path, params, headers, body summary, `baseUrlSuggestion`, warnings and unsupported options.
4. Append inserts after selected Step, generates IDs, selects the new Step and marks draft dirty.
5. Replace updates the selected Step position according to §10.3 and marks draft dirty.
6. Applying `baseUrlSuggestion` updates draft `baseUrlExpression` only after explicit confirmation.
7. Modal never auto-saves; Save still calls existing `patchScenario`.
8. Sensitive warning copy is visible when sensitive warning codes are returned.

### 14.4 Non-regression checks

1. Existing Scenario create/get/patch/delete behavior remains unchanged.
2. Existing Scenario validation still rejects invalid imported content at save or debug time.
3. Existing Debug Run and Run Now flows require no changes.
4. Runner tests do not require updates for P1-05 except proving no contract dependency was introduced.

## 15. Done When

P1-05 is complete only when:

1. `docs/sdd/slices/P1-05-curl-import.md` is active and indexed by `P1-README.md`.
2. API parse schemas, route and parser service are implemented with no new runtime dependency.
3. Parse endpoint returns preview/warnings only and persists nothing.
4. Web Scenario Designer supports paste, preview, warnings, append, replace and optional `baseUrlExpression` application.
5. Confirmed imports save only through existing Scenario `PATCH`.
6. No DB migration, Runner protocol change, Run state machine change or Taurus builder change is introduced.
7. API parser/route tests, Web tests and contract freshness checks pass.
8. Repository-level validation target is run before implementation merge:

```bash
make generate-contracts
make verify
```

If local infrastructure prevents full `make verify`, the implementation PR must state the closest subset run and the exact limitation.

## 16. Open Questions

None.

## 17. Implementation Backfill

1. API implementation files:
   - Schemas: `apps/api/app/schemas/scenarios.py`
   - Parser service: `apps/api/app/services/curl_import.py`
   - Route: `apps/api/app/routes/scenarios.py`
2. Final public operation:
   - `POST /api/v1/scenarios/curl-import/parse`
   - Operation ID: `parseScenarioCurlImport`
   - Request schema: `CurlImportParseRequest`
   - Response schema: `CurlImportParseResponse`
3. Web implementation files:
   - Client wrapper/types: `apps/web/src/app/api-client.ts`
   - Step materialization helper: `apps/web/src/features/scenarios/model.ts`
   - Copy: `apps/web/src/features/scenarios/copy.ts`
   - Modal/UI merge flow: `apps/web/src/features/scenarios/pages/scenario-designer-page.tsx`
4. Tests added or extended:
   - `apps/api/tests/test_p1_05_curl_import_service.py`
   - `apps/api/tests/test_p1_05_curl_import_api.py`
   - `tests/contract/test_p1_05_curl_import_openapi.py`
   - `apps/web/src/features/scenarios/scenarios.test.tsx`
   - `tests/e2e/p1_05_curl_import.spec.ts`
5. Generated contracts were refreshed:
   - `packages/contracts/openapi/api.openapi.json`
   - `packages/contracts/generated/web-client/index.ts`
6. Verification commands run during implementation:
   - `uv run --all-packages pytest apps/api/tests/test_p1_05_curl_import_service.py -q`
   - `uv run --all-packages pytest apps/api/tests/test_p1_05_curl_import_api.py tests/contract/test_p1_05_curl_import_openapi.py -q`
   - `pnpm --filter @surgepilot/web test -- scenarios.test.tsx --runInBand`
   - `pnpm --filter @surgepilot/web typecheck`
   - `pnpm --filter @surgepilot/web lint`
   - `pnpm e2e -- tests/e2e/p1_05_curl_import.spec.ts`
7. Implementation differences from the Slice SDD: none currently known. The parser uses Python standard library only and does not add a new runtime dependency.
8. Remaining risks / later-slice notes:
   - cURL parsing remains a P1 whitelist parser, not shell-compatible cURL emulation.
   - Unsupported options are surfaced in the preview and are not mapped to Runner behavior.
   - Confirmed imports may save sensitive values only through the existing user-confirmed Scenario `PATCH` flow.

### 17.1 Review Backfill

1. Scenario named values used by Scenario Steps and cURL import preview now share `SCENARIO_NAMED_VALUE_MAX_LENGTH = 65_536` characters. This supports browser DevTools copy-as-cURL commands with 5KB+ `Cookie` headers while keeping Env Group variable value limits unchanged.
2. cURL import preview construction maps Pydantic preview validation failures to safe `422 VALIDATION_ERROR` responses with the message `Imported Step preview exceeds Scenario limits.` and without echoing raw cURL or Cookie values.
3. The Scenario persistence fields used by cURL-imported Steps remain existing JSONB / SQLite JSON variant fields (`steps_json`, `default_settings_json`, `data_sources_json`); no DB migration or Runner protocol change was introduced.
4. The Scenario Designer cURL import entry is now rendered beside `Add Step` in the Steps sidebar using the short label `Import cURL`; the modal title and internal copy remain `Import from cURL`.
