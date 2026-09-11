# P2-01 OpenAPI Step Generation Brief

- Document status: Accepted for P2 implementation; P0/P1 shall not implement user visibility capabilities in advance based on this
- Stage: P2
- Capability:`openapi_step_generation`
- Related solutions: P2 OpenAPI Step Generation Brief
- Scope Gate:`docs/sdd/00-product-scope-and-priority.md` §7
- Product Source: `docs/prd/PRD.md` §8.3 OpenAPI Step automatically generated
- P2 Index:`docs/sdd/slices/P2-README.md`
- API Catalog Boundary:`docs/sdd/slices/P2-00-api-catalog-scalar.md`
- Scenario Boundary:`docs/sdd/slices/P0-05-visual-scenario-debug-run.md`
- cURL Import Boundary:`docs/sdd/slices/P1-05-curl-import.md`
- API Contract Boundary:`docs/sdd/04-api-contract-guidelines.md`
- Security Boundary:`docs/sdd/06-security-permission-workspace.md`
- Storage Boundary:`docs/sdd/07-storage-artifacts-minio.md`
- Frontend Route Boundary:`docs/sdd/08-frontend-routing-and-ui-rules.md`
- Testing Boundary:`docs/sdd/09-testing-and-acceptance-strategy.md`
- ADR Boundary: `docs/sdd/adr/ADR-0011-p2-openapi-step-generation.md`; If OpenAPI Step Generation is later expanded to API Catalog operation management, Scenario/Test Plan generation link, background task or independent conversion service, ADR/Scope Gate must be added or updated

## 1. Goal

P2-01 Added **OpenAPI -> HTTP Step draft generation auxiliary capability in the Scenario editor**. The user selects an authorized API Catalog spec in an existing Scenario, selects one or more OpenAPI / Swagger operations, generates multiple editable HTTP Step drafts in the order selected by the user, and inserts the current Scenario draft after preview confirmation.

Goal:

1. Reduce the cost for users to manually enter HTTP `method`, `path`, `queryParams`, `headers` and JSON `body` examples.
2. Fixed OpenAPI Step Generation as a Scenario Editor feature instead of an API Catalog extension feature.
3. Supports selecting multiple operations at one time and stably generating multiple Step drafts; the return order must be equal to the user submission order.
4. Reuse the existing Visual Scenario Step model, Scenario `PATCH` save link, Workspace / permission / CSRF / generated contracts rule.
5. The generated results can be edited, rejected, and deleted; after saving, they are equivalent to handwritten steps.
6. API Catalog spec is only used as an input asset after authorization; the generated results are not bound to the spec life cycle, and the API Catalog is not reversely rewritten.

P2-01 must not become a pre-dependency of the main link of P0/P1 Scenario -> Test Plan -> Run -> Run Report.

## 2. PRD / Scope Trace

`docs/sdd/00-product-scope-and-priority.md` §7 Put `OpenAPI Step Generation` into P2 and require that it not be implemented in advance as an API Catalog -> Scenario/Test Plan generation link.

`docs/prd/PRD.md` §8.3 Fixed:

1. API Catalog is the P2 API document asset management capability.
2. API Catalog does not provide the action of creating Test Plan.
3. API Catalog does not provide an import entry based on API documents.
4. API Catalog does not create, update or generate Scenario/Test Plan.
5. OpenAPI Step can automatically generate a separate item in P2, but it is still not allowed to extend the API Catalog to Scenario/Test Plan to generate links.

This Slice locks in the following conclusions:

1. P2-01 is the Step draft generation in the Scenario editor, not the API Catalog detail page action.
2. Multi-select operation to generate multiple steps at one time is an intentional extension of this Slice to the single operation baseline; this extension only occurs in the Scenario editor and does not change the product link.
3. The Operation list is obtained by the P2-01 backend reading and parsing the authorized spec in the Scenario context; the API Catalog does not add an operation management interface.
4. Scalar is only responsible for P2-00 API Catalog detail page rendering; the back-end parsing and Step mapping of P2-01 must not rely on Scalar, Scalar UI status or browser-side parsing results.
5. P2-01 does not create Scenario, does not generate Test Plan, and does not do coverage/diff/mock/SDK/contract runner.
6. It is still in the development stage; except for the existing OpenAPI / generated contract workflow, no historical client compatibility layer will be introduced.

Governance prerequisites:

1. Authorization is required after P2-01 is activated through `docs/sdd/adr/ADR-0011-p2-openapi-step-generation.md`.
2. P2-01 relies on P2-00 or equivalent accepted API Catalog spec asset contract to provide authorized spec original text and metadata.
3. `P2-README.md` is an index only; implementations may not be launched directly from placeholder copy.
4. If the implementation requires API Catalog operation import, Scenario creation, Test Plan generation, background queue, independent conversion service, rule engine, external API Gateway, Web direct connection to MinIO or new UI component library, you must first update Scope Gate or add ADR.

## 3. In Scope

1. API: Added Scenario-scoped OpenAPI generation endpoints, which are used to list available specs, enumerate operations, and generate ordered Step drafts.
2. Spec source: Reuse API Catalog to save the metadata/content reading and authorization boundaries of spec assets; the Web is not directly connected to MinIO.
3. Parser dependency:API implementation must add `openapi-spec-validator>=0.9.0,<0.10.0` as the direct API dependency for server-side Swagger/OpenAPI validation. JSON/YAML loading may reuse existing repository dependencies, but OpenAPI semantic validation must not be a hand-rolled parser.
4. Operation enumeration: The backend parses operation summaries from the spec and returns user-selectable operation refs.
5. Multi-operation draft generation: The backend generates the same number of HTTP Step drafts in the order of operation refs submitted by the user.
6. Mapping: Generate certain fields, including method, path, query params, required headers, JSON body example/default/minimum sample, step name suggestions and warnings.
7. Web Scenario Designer: Provides three-mode entry in the Add Step area: manual Add Step, Import cURL, From OpenAPI; the first version uses easy-to-understand icons, accessible labels and tooltips that conform to the existing `lucide-react` / `IconActionButton` style to avoid long text extrusion.
8. Preview/confirm: Web supports selecting spec, selecting multiple operations, adjusting order, previewing drafts, confirm insertion or cancellation.
9. Save semantics: After confirming the insertion, only the Web Scenario draft will be modified; the final save will still use the existing Scenario `PATCH /api/v1/scenarios/{scenarioId}`.
10. Tests / verification:API auth/workspace/spec/operation/draft tests, contract tests, Web interaction tests, no API Catalog generation entry tests, spec lifecycle regression tests.

## 4. Out of Scope

1. `Generate Scenario` , `Generate Test Plan` , `Import operations` or `From OpenAPI` entry on the API Catalog detail page.
2. Create Scenario, update Scenario, save Scenario, generate Test Plan, create Run or trigger Debug Run.
3. API -> Scenario/Test Plan generation chain, operation import, coverage analysis, version diff, breaking-change analysis.
4. API Catalog operation-level persistence, operation search index, operation ownership model or API Catalog lifecycle extension.
5. Mock server, contract runner, SDK generation, OpenAPI registry, schema registry, API governance lint platform.
6. Assertion seed, response assertion generation, extractor generation, script generation, Taurus YAML preview, editable Taurus YAML.
7. `application/x-www-form-urlencoded`, `multipart/form-data`, file upload mapping, Dependency File auto-upload, remote `$ref` fetching or external URL resolution.
8. Queue, asynchronous task, background worker, independent conversion service, rule engine, microservice split, external API Gateway.
9. Web-side OpenAPI parser, Web direct MinIO, presigned URL, bucket/object key/server path are exposed.
10. DB table name, column type, index, migration script, complete ORM/Pydantic/TS type handwritten design.

## 5. Relationship to P2 API Catalog

| Item | P2 API Catalog | P2 OpenAPI Step Generation |
| --- | --- | --- |
| Product mental model | API documentation asset management | Scenario Step editing helper |
| User entry | `/api-catalog` list and detail | Scenario editor add-step panel |
| Owned data | Spec metadata and raw spec content | Scenario draft / persisted Scenario Steps |
| Allowed actions | Upload, list, detail/content, delete | Parse spec, select operations, preview drafts, insert drafts |
| Forbidden actions | Generate Scenario/Test Plan | Manage spec lifecycle |

Contracts:

1. API Catalog provides only authorized spec asset source data: metadata and raw content proxy/storage access through API server; P2-01 does not depend on P2-00 detail page metadata/card layout or Scalar-rendered DOM state.
2. P2-01 reads spec assets through API-side services in Scenario context; it must not require API Catalog to persist operation-level records or expose operation actions on the detail page.
3. Deleting or replacing a spec affects future P2-01 selection/parsing only; it must not mutate already generated Scenario Steps.
4. Generated Steps are ordinary Scenario Steps after user confirmation and save.
5. The API Catalog detail page must not render P2-01 actions.
6. Scalar-rendered API Reference state is not an input to generation. P2-01 depends only on the authorized spec asset contract, not on the old or current P2-00 detail UI structure.

## 6. Preconditions

1. P2-00 or an equivalent accepted API Catalog spec asset contract exists and provides current Workspace spec metadata plus server-side raw content access; the Scenario editor must not scrape or couple to API Catalog detail-page UI structure.
2. Scenario CRUD exists with `GET /api/v1/scenarios/{scenarioId}` and `PATCH /api/v1/scenarios/{scenarioId}` revision-based save semantics.
3. Visual Scenario Step fields include `method`, `path`, `queryParams`, `headers`, `body`, `settings`, `assertions`, `scripts` and `uploadFiles`.
4. Step `path` must remain relative and start with `/`; API generation must not write URL origin into Step path.
5. Business APIs continue to use `/api/v1`, cookie session auth, `x-workspace-id`, write `x-csrf-token`, `x-request-id`, camelCase JSON, lower snake case enum values and the existing `{code, message, requestId, details?}` error envelope.
6. API remains the only server-side owner of PostgreSQL metadata, MinIO access, Workspace filtering and storage safety decisions.
7. Web must call API through generated contracts from `@surgepilot/contracts` and must not import generated files by relative path.
8. Web must not access PostgreSQL, MinIO, Load Nodes, runner endpoints or storage credentials directly.
9. Existing Scenario validation and Taurus builder remain the save/execution-time authority after generated Steps are inserted and saved.

## 7. Locked Core Decisions

| ID | Decision |
| --- | --- |
| OSG-01 | P2-01 is a Scenario editor Step draft generation feature, not an API Catalog feature. |
| OSG-02 | API Catalog spec assets are inputs only; P2-01 does not manage spec lifecycle and does not add operation-level API Catalog resources. |
| OSG-03 | Operation enumeration and Step draft generation happen API-side after auth, Scenario edit permission, Workspace and spec ownership checks. |
| OSG-04 | Web performs selection, ordering, preview, confirmation and insertion into local Scenario draft; persistence still uses existing Scenario `PATCH`. |
| OSG-05 | Multi-operation generation is supported in the first version; response order must exactly match request `operationRefs` order. |
| OSG-06 | Generated Step drafts use existing Scenario Step fields only. They exclude persistent `id` fields and are materialized by Web before insertion. |
| OSG-07 | No generated Step is bound to source spec lifecycle after insertion/save; spec delete/update must not rewrite Scenario Steps. |
| OSG-08 | Generation fills only deterministic request fields and returns warnings for low-confidence or unsupported mappings. |
| OSG-09 | Public auth/common headers must not be generated with cleartext values. Security-derived headers are omitted or represented only as safe placeholders with warnings. |
| OSG-10 | First version does not generate assertions, extractors, scripts, upload files, response validation or Test Plan content. |
| OSG-11 | API implementation must use `openapi-spec-validator>=0.9.0,<0.10.0` as the direct server-side Swagger/OpenAPI validation dependency; only bounded operation enumeration and operation-to-Step mapping are SurgePilot custom logic. |
| OSG-12 | No queue, async job, independent conversion service, new UI component library, direct MinIO access, Runner change or DB migration is required by this Slice. |

## 8. Architecture

```text
Scenario Designer
  -> user opens add-step mode chooser
  -> user chooses From OpenAPI
  -> Web loads Scenario-scoped available spec sources
  -> user selects one API Catalog spec
  -> Web requests operation summaries for that spec in the Scenario context
  -> API validates session, Workspace, Scenario edit permission and spec ownership
  -> API reads raw spec through server-side storage boundary
  -> API parses spec and returns operation summaries
  -> user selects one or more operations and orders them
  -> Web submits selected operation refs and insertion position for preview
  -> API re-validates Scenario + spec, parses/locates operations and maps them to Step drafts
  -> API returns ordered drafts + warnings + preview metadata, persisting nothing
  -> user confirms insertion or cancels
  -> Web materializes IDs, inserts drafts into local Scenario draft and marks it dirty
  -> existing Save uses PATCH /api/v1/scenarios/{scenarioId}
  -> existing Scenario validation, revision, snapshot and Taurus builder chain applies later
```

Component boundaries:

| Component | Responsibility | Forbidden |
| --- | --- | --- |
| Scenario OpenAPI generation router | Expose Scenario-scoped spec source, operation list and draft generation endpoints; enforce session, Workspace, CSRF for POST, Scenario edit permission and safe errors. | Updating Scenario, creating Scenario/Test Plan/Run, bypassing Scenario `PATCH`, returning storage internals. |
| API Catalog service boundary | Provide authorized spec metadata/content to API server code. | Operation-level management, generation buttons, spec lifecycle callbacks into Scenario. |
| OpenAPI parser service | Parse Swagger 2.0 / OpenAPI 3.0 / 3.1 documents, enumerate operations, resolve local `$ref` enough for request examples, return warnings for unsupported constructs. | Remote `$ref` fetches, network calls, custom full parser, lint/governance platform, persisted operation cache. |
| Step draft mapper | Convert selected operations into existing Scenario-compatible Step drafts and warnings. | Assertion/extractor/script/Test Plan generation, cleartext auth header generation, Step lifecycle binding to spec. |
| `@surgepilot/contracts` | Generated Web client/types from FastAPI/Pydantic after API schema changes. | Hand-edited OpenAPI or generated TypeScript as source of truth. |
| Web Scenario Designer | Render icon-based add-step modes, spec selector, operation selector, order controls, preview and confirm/cancel insertion; materialize IDs; save via existing `patchScenario`. | Web-side OpenAPI parser, direct MinIO fetch, automatic save, API Catalog detail-page generation UI. |
| Runner / Run / Test Plan domains | No change. | Any dependency on P2-01 parsing or source spec state. |

## 9. API Contract

### 9.1 Endpoints

| Method | Path | Operation ID | Response | Contract |
| --- | --- | --- | --- | --- |
| `GET` | `/api/v1/scenarios/{scenarioId}/openapi-step-generation/specs` | `listScenarioOpenApiSpecSources` | `200 OpenApiSpecSourceListResponse` | Return API Catalog spec sources available for the editable Scenario's Workspace. Requires session, Workspace and Scenario read/edit access. |
| `GET` | `/api/v1/scenarios/{scenarioId}/openapi-step-generation/specs/{specId}/operations` | `listScenarioOpenApiOperations` | `200 OpenApiOperationListResponse` | Parse the selected spec and return operation summaries. Requires same Scenario/spec Workspace validation. |
| `POST` | `/api/v1/scenarios/{scenarioId}/openapi-step-generation/drafts` | `generateScenarioOpenApiStepDrafts` | `200 OpenApiStepDraftPreviewResponse` | Generate ordered Step draft previews from selected operation refs. Requires session, Workspace, CSRF and Scenario edit access. Persists nothing. |

Rules:

1. Routes belong to the Scenario route domain because outputs are Scenario Step drafts.
2. Route paths must not include `workspaceId`; Workspace is resolved from `x-workspace-id` / existing default Workspace rules.
3. `scenarioId` and `specId` must be ULID business IDs.
4. The POST endpoint requires `x-csrf-token` even though it does not persist data, because it is a browser POST that derives editable Scenario content.
5. All endpoints must validate that the Scenario and spec are in the same Workspace before reading spec content or returning operation information.
6. Operation list and draft generation may parse the spec on demand; they must not persist operation records or generated drafts.
7. Response headers must include `x-request-id`; successful Workspace-aware responses should attach `x-workspace-id` consistently with existing business APIs.
8. API examples must not include production hostnames, secrets, object keys, bucket names, MinIO URLs or local paths.
9. API responses must not include Scenario IDs other than the path context, Test Plan IDs, Run IDs or generation affordances outside Scenario Step insertion.

### 9.2 Spec source response

`OpenApiSpecSourceListResponse`:

| Field | Required | Contract |
| --- | --- | --- |
| `items` | yes | `OpenApiSpecSourceSummary[]`; only specs in the Scenario Workspace and visible to the user. |
| `total` | yes | Total matching sources. |
| `limit` | yes | Effective limit. |
| `offset` | yes | Effective offset. |

`OpenApiSpecSourceSummary`:

| Field | Required | Contract |
| --- | --- | --- |
| `id` | yes | API Catalog spec ULID. |
| `name` | yes | Display name. |
| `filename` | yes | Safe original filename for display only. |
| `sourceFormat` | yes | Existing API Catalog format enum such as `openapi_json`, `openapi_yaml`, `swagger_json`, `swagger_yaml`. |
| `documentTitle` | yes | Parsed title or safe fallback. |
| `documentVersion` | yes | Parsed version or safe fallback. |
| `status` | yes | Must be suitable for generation only when `available`. |
| `updatedAt` | yes | ISO 8601 UTC string with `Z`. |

Representative response:

```json
{
  "items": [
    {
      "id": "01J0Y6T6H2Y0S9V4W8M7N6P5Q4",
      "name": "Orders API",
      "filename": "orders-openapi.yaml",
      "sourceFormat": "openapi_yaml",
      "documentTitle": "Orders API",
      "documentVersion": "1.0.0",
      "status": "available",
      "updatedAt": "2030-06-24T05:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### 9.3 Operation list response

`OpenApiOperationListResponse`:

| Field | Required | Contract |
| --- | --- | --- |
| `spec` | yes | `OpenApiSpecSourceSummary` for display context. |
| `items` | yes | `OpenApiOperationSummary[]`; order follows spec path order, then HTTP method order defined by implementation. |
| `warnings` | yes | Non-fatal spec-level parse/mapping warnings. |

`OpenApiOperationSummary`:

| Field | Required | Contract |
| --- | --- | --- |
| `ref` | yes | `OpenApiOperationRef`; submitted unchanged for draft generation. |
| `method` | yes | Uppercase HTTP method supported by existing Scenario model. |
| `path` | yes | Original OpenAPI path template such as `/users/{id}`. |
| `operationId` | no | Raw operationId when present and safe to display. Not a unique identifier. |
| `summary` | no | Safe operation summary for display. |
| `tags` | yes | Safe string tags from the spec. |
| `displayName` | yes | Suggested display string, for example `GET /users/{id}` or `List users`. |
| `hasRequestBody` | yes | Whether a request body exists. |
| `supportedForGeneration` | yes | `false` when method/path/body shape cannot be mapped to an HTTP Step draft. |
| `warningCodes` | yes | Stable warning codes for known limitations. |

`OpenApiOperationRef`:

| Field | Required | Contract |
| --- | --- | --- |
| `method` | yes | Uppercase HTTP method. |
| `path` | yes | Original OpenAPI path template. |
| `operationId` | no | Included only for trace/display validation; API must locate by method + path and may verify operationId if provided. |

Representative response:

```json
{
  "spec": {
    "id": "01J0Y6T6H2Y0S9V4W8M7N6P5Q4",
    "name": "Orders API",
    "filename": "orders-openapi.yaml",
    "sourceFormat": "openapi_yaml",
    "documentTitle": "Orders API",
    "documentVersion": "1.0.0",
    "status": "available",
    "updatedAt": "2030-06-24T05:00:00Z"
  },
  "items": [
    {
      "ref": {
        "method": "GET",
        "path": "/orders/{orderId}",
        "operationId": "getOrder"
      },
      "method": "GET",
      "path": "/orders/{orderId}",
      "operationId": "getOrder",
      "summary": "Get one order",
      "tags": ["orders"],
      "displayName": "Get one order",
      "hasRequestBody": false,
      "supportedForGeneration": true,
      "warningCodes": []
    }
  ],
  "warnings": []
}
```

### 9.4 Draft generation request

`OpenApiStepDraftGenerateRequest`:

| Field | Required | Contract |
| --- | --- | --- |
| `specId` | yes | API Catalog spec ULID. Must belong to the same Workspace as `scenarioId`. |
| `operationRefs` | yes | Ordered `OpenApiOperationRef[]`; length must be between 1 and the configured first-version limit. The response order must match this order. |
| `insert` | yes | `OpenApiStepInsertPlan`; used by Web preview and confirm flow only. API does not persist insertion. |

`OpenApiStepInsertPlan`:

| Field | Required | Contract |
| --- | --- | --- |
| `mode` | yes | `append`, `before_step` or `after_step`. |
| `stepId` | conditional | Required for `before_step` / `after_step`; must reference an existing Step in the current Scenario draft known to Web. API may echo it but must not persist. |

Rules:

1. `operationRefs` order is authoritative.
2. Duplicate operation refs in one request return `422 VALIDATION_ERROR`.
3. Unsupported methods return `422 VALIDATION_ERROR` unless the operation list already marks them as unsupported and Web prevents selection.
4. The first-version limit should be small enough for synchronous request/response UX; implementation must document the final limit in Implementation Backfill.
5. The endpoint does not compare against current unsaved Scenario content; Web remains responsible for inserting into its local draft and resolving client-side ordering.

Representative request:

```json
{
  "specId": "01J0Y6T6H2Y0S9V4W8M7N6P5Q4",
  "operationRefs": [
    {
      "method": "GET",
      "path": "/orders/{orderId}",
      "operationId": "getOrder"
    },
    {
      "method": "POST",
      "path": "/orders",
      "operationId": "createOrder"
    }
  ],
  "insert": {
    "mode": "after_step",
    "stepId": "01J0Y6V2Q7X8P9N0M1A2B3C4D5"
  }
}
```

### 9.5 Draft generation response

`OpenApiStepDraftPreviewResponse`:

| Field | Required | Contract |
| --- | --- | --- |
| `spec` | yes | `OpenApiSpecSourceSummary` display context. |
| `items` | yes | Ordered `OpenApiGeneratedStepDraftItem[]`; same length and order as request `operationRefs` when all operations are supported. |
| `insert` | yes | Echoed `OpenApiStepInsertPlan`. |
| `warnings` | yes | Request-level warnings not tied to a single operation. |

`OpenApiGeneratedStepDraftItem`:

| Field | Required | Contract |
| --- | --- | --- |
| `operationRef` | yes | Submitted operation ref. |
| `step` | yes | `OpenApiGeneratedStepDraft`; excludes persistent IDs. |
| `source` | yes | Preview-only source metadata. Web may display it, but persisted Scenario Step must not rely on it. |
| `warnings` | yes | Operation-specific warnings. |

`OpenApiGeneratedStepDraft`:

| Field | Type | Contract |
| --- | --- | --- |
| `enabled` | boolean | Defaults to `true`. |
| `name` | string | Derived from `operationId`, `summary`, or `METHOD path`; max 120 chars. |
| `method` | `GET | POST | PUT | PATCH | DELETE | HEAD | OPTIONS` | Existing Scenario HTTP method enum only. |
| `path` | string | Relative path starting with `/`; OpenAPI path params convert from `{id}` to `${id}`. |
| `queryParams` | `OpenApiGeneratedNamedValueDraft[]` | Required query params, plus optional params only when example/default exists. |
| `headers` | `OpenApiGeneratedNamedValueDraft[]` | Required non-common headers that are safe to generate. No cleartext auth headers. |
| `body` | `OpenApiGeneratedBodyDraft` | JSON body only in first version; unsupported media types leave body empty and emit warnings. |
| `settings` | `OpenApiGeneratedStepSettingsDraft` | First version returns null settings unless an accepted mapping exists. |

`OpenApiGeneratedNamedValueDraft`:

| Field | Type | Contract |
| --- | --- | --- |
| `name` | string | Header/query/form field name. |
| `value` | string | Example/default value or safe `${variableName}` placeholder. |
| `enabled` | boolean | Defaults to `true`. |

`OpenApiGeneratedBodyDraft`:

| Field | Type | Contract |
| --- | --- | --- |
| `type` | `none | raw | form` | First version uses `none` or `raw`; `form` is reserved for a later accepted enhancement. |
| `contentType` | string or null | `application/json` when JSON body is generated. |
| `rawText` | string or null | Pretty JSON example/default/minimum sample within existing Scenario raw body limit. |
| `formFields` | `OpenApiGeneratedNamedValueDraft[]` | Empty in first version. |

`OpenApiGeneratedStepSettingsDraft`:

| Field | Type | Contract |
| --- | --- | --- |
| `timeoutMs` | null | OpenAPI generation does not infer timeouts in first version. |
| `followRedirects` | null | OpenAPI generation does not infer redirects in first version. |
| `keepAlive` | null | OpenAPI generation does not infer keep-alive in first version. |
| `thinkTimeMs` | null | OpenAPI generation does not infer think time. |

Fields intentionally not returned inside `step`:

1. `id` and child `id` fields: Web materializes them.
2. `uploadFiles`: first version does not map file uploads.
3. `extractors`, `assertions`, `scripts`: first version does not infer response validation, extraction or scripts.
4. API Catalog storage fields or object references.

Representative response:

```json
{
  "spec": {
    "id": "01J0Y6T6H2Y0S9V4W8M7N6P5Q4",
    "name": "Orders API",
    "filename": "orders-openapi.yaml",
    "sourceFormat": "openapi_yaml",
    "documentTitle": "Orders API",
    "documentVersion": "1.0.0",
    "status": "available",
    "updatedAt": "2030-06-24T05:00:00Z"
  },
  "items": [
    {
      "operationRef": {
        "method": "GET",
        "path": "/orders/{orderId}",
        "operationId": "getOrder"
      },
      "step": {
        "enabled": true,
        "name": "Get one order",
        "method": "GET",
        "path": "/orders/${orderId}",
        "queryParams": [],
        "headers": [],
        "body": {
          "type": "none",
          "contentType": null,
          "rawText": null,
          "formFields": []
        },
        "settings": {
          "timeoutMs": null,
          "followRedirects": null,
          "keepAlive": null,
          "thinkTimeMs": null
        }
      },
      "source": {
        "operationId": "getOrder",
        "summary": "Get one order"
      },
      "warnings": [
        {
          "code": "PATH_VARIABLE_PLACEHOLDER_REQUIRED",
          "message": "Fill orderId before running this Step.",
          "field": "step.path"
        }
      ]
    }
  ],
  "insert": {
    "mode": "after_step",
    "stepId": "01J0Y6V2Q7X8P9N0M1A2B3C4D5"
  },
  "warnings": []
}
```

### 9.6 Error and warning contract

Top-level error behavior:

| Condition | HTTP | Code | Contract |
| --- | ---: | --- | --- |
| Missing/invalid auth | 401 | existing auth code | Existing auth middleware behavior. |
| Missing/unresolvable Workspace | 400 | `WORKSPACE_REQUIRED` | Existing Workspace behavior when no default can be resolved. |
| Scenario not found or no access | 404 or 403 | existing scenario/access code | Must not leak cross-Workspace existence. |
| Spec not found in Scenario Workspace | 404 | `RESOURCE_NOT_FOUND` | Must not leak cross-Workspace spec existence. |
| Spec status not available | 422 | `API_SPEC_NOT_AVAILABLE` | Spec cannot be used for generation. |
| Spec parse fails | 422 | `API_SPEC_PARSE_FAILED` | Safe parse details only. |
| Unsupported spec version/root | 422 | `UNSUPPORTED_API_SPEC_FORMAT` | Safe format message. |
| Operation ref missing from spec | 422 | `OPENAPI_OPERATION_NOT_FOUND` | Field-level details include operation index, method and path only. |
| Operation cannot map to HTTP Step | 422 | `OPENAPI_OPERATION_UNSUPPORTED` | Safe reason code. |
| Too many operation refs | 422 | `VALIDATION_ERROR` | Include configured limit. |
| Storage unavailable while reading spec | 503 | `STORAGE_UNAVAILABLE` | No bucket/object key/path in response. |
| Internal mapper bug | existing safe 5xx | existing safe code | Never include raw spec excerpts, stack traces or storage internals. |

`OpenApiStepGenerationWarning`:

| Field | Type | Contract |
| --- | --- | --- |
| `code` | string | Stable warning code. |
| `message` | string | English user-facing fallback. |
| `field` | string or null | Optional response field path such as `items[0].step.body.rawText`. |

Required warning codes:

| Code | Meaning |
| --- | --- |
| `PATH_VARIABLE_PLACEHOLDER_REQUIRED` | OpenAPI `{param}` converted to `${param}` and requires user value. |
| `QUERY_PARAMETER_PLACEHOLDER_REQUIRED` | Required query parameter had no example/default and uses `${paramName}`. |
| `HEADER_PARAMETER_PLACEHOLDER_REQUIRED` | Required non-auth header had no example/default and uses `${headerName}`. |
| `AUTH_HEADER_NOT_GENERATED` | Authorization/Cookie/API key/security-scheme header was omitted or replaced by a safe placeholder. |
| `OPTIONAL_PARAMETER_SKIPPED` | Optional parameter without example/default was not generated. |
| `JSON_BODY_EXAMPLE_GENERATED` | JSON body was generated from example/default/minimum schema. |
| `JSON_BODY_EXAMPLE_MISSING` | JSON request body exists but no safe example/default/minimum sample was generated. |
| `UNSUPPORTED_BODY_MEDIA_TYPE` | Request body media type is out of first-version scope. |
| `UNSUPPORTED_PARAMETER_STYLE` | Parameter style/explode combination cannot be safely mapped to named values. |
| `REMOTE_REF_NOT_RESOLVED` | Remote `$ref` was not fetched or resolved. |
| `RESPONSE_ASSERTION_NOT_GENERATED` | Responses are visible as preview metadata/warning only; assertions are not generated. |

## 10. Parser and Mapping Contract

### 10.1 Parser dependency

Dependency contract:

| Item | Contract |
| --- | --- |
| Direct dependency | Add `openapi-spec-validator>=0.9.0,<0.10.0` to `apps/api/pyproject.toml` as the API app's direct server-side Swagger/OpenAPI validation dependency. |
| Purpose | Validate complete Swagger/OpenAPI documents and provide version-aware validation before SurgePilot enumerates operations or maps operations to Step drafts. |
| Supported baseline | Implementation must validate representative Swagger / OpenAPI 2.0, OpenAPI 3.0 and OpenAPI 3.1 specs. OpenAPI 3.2 may be accepted when the dependency supports it, but P2-01 acceptance is not blocked on 3.2-specific features. |
| Explicit validators | Implementation should use version-aware validator classes such as `OpenAPIV2SpecValidator`, `OpenAPIV30SpecValidator` and `OpenAPIV31SpecValidator` when mapping validation failures to stable business error codes. Automatic version detection may be used only when it produces the same error-contract behavior. |
| SurgePilot-owned logic | Operation enumeration, operation ref matching, sample generation and operation-to-Step mapping remain bounded SurgePilot helper logic after dependency validation. |
| Transitive dependency | `openapi-schema-validator` remains transitive through `openapi-spec-validator`; do not add it as a direct dependency unless P2-01 implementation imports it directly. |
| Direct schema-validator trigger | Add `openapi-schema-validator>=0.9.0,<0.10.0` directly only if implementation validates generated JSON body samples against requestBody schemas, then record that decision in Implementation Backfill. |
| Forbidden | Do not call `validate_url()`, do not accept user-supplied spec URLs, do not pass remote `base_uri`, do not fetch remote `$ref`, do not add a Web parser, and do not introduce an external conversion service. |
| Fallback | If `openapi-spec-validator>=0.9.0,<0.10.0` cannot satisfy the Swagger 2.0 / OpenAPI 3.0 / OpenAPI 3.1 validation baseline safely, implementation must stop and add an ADR before choosing another parser stack. |

JSON/YAML byte loading may reuse existing `PyYAML` and Python JSON behavior, but OpenAPI semantic validation must not be reduced to ad-hoc dictionary walking. Bounded dictionary traversal is allowed only after validation for operation enumeration and operation-to-Step mapping.

### 10.2 Supported first-version mapping

| OpenAPI input | Step draft contract |
| --- | --- |
| HTTP method | Existing Scenario `HttpMethod` enum. Unsupported methods are not generated. |
| Path template `/users/{id}` | Step `path` `/users/${id}` and warning requiring user value. |
| Operation `operationId` / `summary` | Step `name` suggestion, max 120 chars. |
| Required path parameters | Converted through path placeholders only; not duplicated as query params. |
| Required query parameters | Generated as enabled query values; example/default wins, otherwise `${paramName}` with warning. |
| Optional query parameters | Generated only when example/default exists; otherwise skipped with warning. |
| Required header parameters | Generated only for non-auth/common headers; example/default wins, otherwise `${headerName}` with warning. |
| Auth/common/security headers | Omitted or safe placeholder only; never cleartext. |
| JSON request body example | Pretty JSON `body.rawText`, `body.type=raw`, `contentType=application/json`. |
| JSON schema default/minimum sample | Generated only when safe and bounded. Object samples include required and optional properties whose child schemas can be sampled by the bounded rules; empty/unsupported/recursive-only objects stay empty with warning. |
| Unsupported request body media type | Body stays empty; operation warning explains unsupported media type. |
| Responses | No assertion seed; only preview metadata/warnings may mention that no response assertion was generated. |

Mapping invariants:

1. Mapper must not call operation `servers[]`, root `servers[]` or external URLs.
2. Mapper must not fetch remote `$ref` URLs.
3. Mapper must not generate secrets from examples/security schemes into Step values.
4. Mapper must not generate Step paths that lack a leading `/`.
5. Mapper must not generate Step fields outside the existing Scenario Step model.
6. Mapper must not generate raw body beyond the existing Scenario raw body size limit.
7. Mapper must not generate duplicate enabled header names case-insensitively.
8. Mapper must preserve request operation order exactly.

## 11. Web and UX Contract

### 11.1 Add Step entry modes

The Scenario Designer add-step control must expose three user-selectable modes when both P1 cURL Import and P2 OpenAPI Step Generation are active:

| Mode | Meaning | Contract |
| --- | --- | --- |
| Manual | Add a blank HTTP Step | Existing `newStep()` behavior. |
| cURL | Import one Step from cURL | Existing P1-05 cURL import behavior. |
| From OpenAPI | Generate one or more Step drafts from API Catalog spec operations | P2-01 behavior. |

UI rules:

1. Because three labels are long, the compact entry may use three icon-first buttons.
2. Icons must come from the existing Web icon system, currently `lucide-react`; no new icon package is introduced.
3. Icon-only or icon-primary controls must include accessible names such as `Add Step`, `Import cURL`, and `From OpenAPI`.
4. Tooltip or adjacent short copy should clarify each mode without creating hidden or unlabeled controls.
5. The three modes must remain within existing Scenario Designer layout and Tailwind token rules; no new UI component library or theme provider.
6. When P2-01 is inactive, the `From OpenAPI` mode must not be clickable or exposed as a hidden usable route.

### 11.2 From OpenAPI panel

Flow contract:

1. User opens `From OpenAPI` from the Scenario editor.
2. Web calls `listScenarioOpenApiSpecSources` and renders available API Catalog specs.
3. User selects one spec.
4. Web calls `listScenarioOpenApiOperations` and renders selectable operation summaries.
5. User selects one or more supported operations.
6. Web supports user-controlled ordering before generation.
7. Web calls `generateScenarioOpenApiStepDrafts` with ordered operation refs and desired insert position.
8. Web renders ordered Step draft previews and warnings.
9. User confirms insertion or cancels.
10. On confirm, Web materializes IDs, inserts drafts into the local Scenario draft, and marks the draft dirty.
11. Existing Scenario save, revision conflict handling and validation apply.

Preview rules:

1. Preview must show warnings before insertion.
2. Preview must make generated placeholders visible, especially `${var}` path/query/header values.
3. Preview must show that generated Steps are editable and not saved until the Scenario is saved.
4. Preview must not present API Catalog lifecycle actions.
5. Cancel must leave the Scenario draft unchanged.

## 12. Data and Storage Model

P2-01 does not introduce a required persisted data model.

Conceptual transient objects:

| Object | Visibility | Contract |
| --- | --- | --- |
| `OpenApiOperationSummary` | API/Web transient | Displayable operation metadata parsed from one authorized spec in Scenario context. |
| `OpenApiOperationRef` | API/Web transient | Method + path + optional operationId used to select operations. Not persisted as a Catalog resource. |
| `OpenApiGeneratedStepDraft` | API/Web transient | Scenario-compatible draft without persistent IDs. |
| `OpenApiStepGenerationWarning` | API/Web transient | Stable warning code and safe message. |
| `source` metadata | API/Web preview only | May explain where a draft came from; must not create a lifecycle binding to the spec. |

Persistence invariants:

1. Generated Steps are persisted only if the user confirms insertion and later saves the Scenario through existing Scenario `PATCH`.
2. Persisted Steps must be valid ordinary Scenario Steps.
3. Persisted Steps must not require source spec existence to run, edit, clone, delete or display.
4. Spec deletion/update must not cascade into Scenario Steps.
5. P2-01 does not require a DB table, migration, background job table or operation cache.
6. If implementation later adds optional persisted non-lifecycle source metadata, it must update the Scenario model contract and prove spec delete/update still does not mutate Steps.

## 13. Security and Privacy Requirements

1. API must enforce auth, Workspace and Scenario edit permission before returning spec sources, operations or drafts.
2. API must validate spec and Scenario belong to the same Workspace before storage reads.
3. API must not expose MinIO bucket, object key, presigned URL, MinIO endpoint, server path or storage credentials.
4. API must not log full spec content, generated body examples, security examples, header values, cookies, tokens, CSRF tokens or raw generated Step bodies.
5. Logs may include `scenarioId`, `specId`, safe operation count, request ID, safe status code and stable warning/error codes.
6. Parser must not fetch remote references, contact spec `servers[]`, validate endpoint reachability or execute code snippets.
7. Security schemes and auth/common headers must not generate cleartext secrets.
8. Error responses must not leak parser stack traces, spec excerpts, object keys, bucket names, local paths or cross-Workspace existence.
9. Web must not cache raw spec content outside normal browser/API request behavior and must not store generated drafts until user confirms and saves Scenario.
10. Preview may display generated request data to the same authorized user; this is not a generic sensitive masking framework.

## 14. Observability and Audit

1. No new metrics are required for P2-01.
2. Existing request ID logging is sufficient for basic troubleshooting.
3. A minimal audit event is not required because operation listing and draft generation persist nothing.
4. If implementation adds audit events for generation preview, audit details must include only safe metadata such as `scenarioId`, `specId`, operation count and warning codes; no spec content or generated request body.
5. Web preview interactions are not product analytics inputs in P2-01.

## 15. Compatibility and Migration

1. No DB migration is required by P2-01.
2. No existing Scenario, Test Plan, Run, Runner, Artifact or Dependency File migration is required.
3. No generated-contract compatibility layer or legacy route alias is required in the current development stage.
4. Existing `/api/v1` conventions, Workspace header rules, error envelope and generated-contract workflow remain unchanged.
5. Existing Scenario Step validation remains authoritative when the user saves generated Steps.
6. If implementation later needs operation cache persistence, remote `$ref` resolution, form/multipart generation or response assertion generation, that is a separate ADR/Scope Gate change.

## 16. Tests and Acceptance Criteria

### 16.1 API route and service tests

Minimum coverage:

1. `GET /api/v1/scenarios/{scenarioId}/openapi-step-generation/specs` returns only specs in the current Scenario Workspace.
2. Spec source listing requires authenticated session and Workspace.
3. Operation listing validates Scenario access and same-Workspace spec ownership before storage read.
4. Operation listing supports representative Swagger 2.0, OpenAPI 3.0 and OpenAPI 3.1 documents.
5. Operation listing returns method/path/operationId/summary/tags/displayName and `supportedForGeneration` safely.
6. Draft generation requires authenticated session, Workspace, CSRF and Scenario edit access.
7. Draft generation rejects cross-Workspace spec and Scenario combinations without existence leak.
8. Draft generation rejects missing operation refs, duplicate refs, unsupported methods and too many operations with safe errors.
9. Multi-operation request with three refs returns exactly three items in the same order.
10. Path params convert from `{id}` to `${id}` and generate warnings.
11. Required query/header params map to editable named values with example/default or placeholders.
12. Optional params without example/default are skipped with warnings.
13. JSON request body example/default/minimum sample maps to `body.type=raw`, `contentType=application/json`, bounded `rawText`.
14. Unsupported media type leaves body empty and returns warning.
15. Auth/security headers are not generated with cleartext values.
16. Spec delete/update does not mutate existing Scenario Steps.
17. API Catalog detail/content/list/delete behavior remains unchanged.

### 16.2 Contract tests

1. OpenAPI contains operation IDs `listScenarioOpenApiSpecSources`, `listScenarioOpenApiOperations` and `generateScenarioOpenApiStepDrafts`.
2. JSON field names are camelCase and enum values are lower snake case.
3. List responses use `items` envelopes where applicable.
4. Error responses use `{code, message, requestId, details?}`.
5. Generated client/types are refreshed through `make generate-contracts`.
6. Contract stale check fails when OpenAPI or generated artifacts are stale.

### 16.3 Web tests

1. Scenario Designer shows manual Add Step, Import cURL and From OpenAPI modes as icon-based accessible controls when their scopes are active.
2. `From OpenAPI` has accessible name and tooltip/copy; it uses existing icon system and no new UI library.
3. `From OpenAPI` is not exposed when P2-01 is inactive.
4. Spec selector loads Scenario-scoped spec sources through generated client/types.
5. Operation selector supports selecting multiple operations and changing order.
6. Preview shows ordered generated drafts and warnings.
7. Confirm insertion materializes IDs, inserts Steps at the selected position, marks draft dirty and does not call Scenario `PATCH` automatically.
8. Cancel leaves Scenario draft unchanged.
9. Saving generated Steps still uses existing Scenario save flow.
10. API Catalog pages expose no Generate Scenario/Test Plan/Import operations entry.

### 16.4 Non-regression checks

1. Manual Add Step behavior remains unchanged.
2. P1 cURL Import behavior remains unchanged.
3. Scenario create/get/patch/delete behavior remains unchanged outside inserted draft content.
4. Test Plan create/update/run-now behavior remains unchanged.
5. Run state machine, Runner callbacks and Taurus builder tests require no behavior changes.
6. Dependency File upload/preview/download/delete behavior remains unchanged.
7. P0/P1 routes do not gain clickable OpenAPI Step Generation entries before P2 activation.

## 17. Done When

P2-01 is complete only when:

1. `docs/sdd/slices/P2-01-openapi-step-generation.md` is active through `docs/sdd/adr/ADR-0011-p2-openapi-step-generation.md` and indexed by `P2-README.md`.
2. Scenario-scoped spec source, operation list and draft generation APIs exist under `/api/v1/scenarios/{scenarioId}/openapi-step-generation/...` with generated OpenAPI contracts.
3. API implementation adds `openapi-spec-validator>=0.9.0,<0.10.0` as the direct server-side Swagger/OpenAPI validation dependency and records the resolved package version in Implementation Backfill.
4. Operation enumeration is derived from authorized spec content in Scenario context and does not add API Catalog operation resources.
5. Multi-operation generation returns ordered Step drafts matching request order.
6. Generated Step drafts use existing Scenario Step fields, exclude persistent IDs and are materialized by Web.
7. Confirmed generated Steps save only through existing Scenario `PATCH`.
8. API Catalog detail page exposes no Scenario/Test Plan/OpenAPI import generation entry.
9. Generated Steps do not bind to spec lifecycle; spec delete/update does not rewrite them.
10. No Test Plan, Run, assertion, extractor, script, SDK, mock, coverage or API Catalog operation management behavior is introduced.
11. No queue, independent conversion service, microservice, external API Gateway, direct MinIO Web access or new UI component library is introduced.
12. API route/service tests, contract tests, Web tests and non-regression tests pass.
13. Repository-level validation target is run before implementation merge:

```bash
make generate-contracts
make verify
```

If local infrastructure prevents full `make verify`, the implementation PR must state the closest subset run and exact limitation.

## 18. Implementation Backfill

Implementation must backfill the following after code is written and verified:

1. Final API files and route registration path.
2. Final resolved `openapi-spec-validator` package version, supported OpenAPI / Swagger coverage and known limitations.
3. Final schema names and generated operation names if they differ from §9.
4. Final API Catalog service/content read integration points.
5. Final operation selection limit.
6. Final request body example generation rules and size limits.
7. Final warning/error code names if they differ from §9.6.
8. Final Web feature module paths, icon choices and add-step mode wiring.
9. Final tests added or extended.
10. Verification commands run and any environment gaps.
11. Implementation differences from this SDD, if any; differences that expand scope require ADR/Scope Gate update before merge.


### 18.1 Implementation Backfill

Implemented facts:

1. API route registration lives in `apps/api/app/routes/scenarios.py` under the existing Scenario router prefix `/api/v1/scenarios`. The new operation IDs are `listScenarioOpenApiSpecSources`, `listScenarioOpenApiOperations`, and `generateScenarioOpenApiStepDrafts`.
2. API schemas live in `apps/api/app/schemas/scenarios.py`; parser/mapper logic lives in `apps/api/app/services/openapi_step_generation.py`. No DB migration, background job, API Catalog operation resource, Runner change, or Test Plan/Run change was added.
3. The API app direct dependency is `openapi-spec-validator>=0.9.0,<0.10.0`; the lock resolved `openapi-spec-validator==0.9.0` and transitive `openapi-schema-validator==0.9.0`.
4. The first-version synchronous generation limit is 20 operation refs per request, enforced by `OpenApiStepDraftGenerateRequest.operationRefs`.
5. Supported validation coverage includes Swagger 2.0, OpenAPI 3.0, and OpenAPI 3.1 through `OpenAPIV2SpecValidator`, `OpenAPIV30SpecValidator`, and `OpenAPIV31SpecValidator`. OpenAPI 3.2-specific behavior remains out of scope.
6. Focused API/service verification is recorded in `apps/api/tests/test_p2_01_openapi_step_generation.py`: operation enumeration preserves HTTP order, draft generation preserves caller order, path placeholders/body samples/auth warnings are bounded, duplicate/missing operations are rejected, and the Scenario generation routes enforce session, Workspace and CSRF boundaries.
7. Contract verification is recorded in `tests/contract/test_p2_01_openapi_step_generation_openapi.py`; it checks the three Scenario-scoped operation IDs, the 20-operation request limit, generated Web client presence, and the absence of API Catalog generation/import operations.
8. Web interaction and lifecycle regression coverage is in `apps/web/src/features/scenarios/scenarios.test.tsx`; it verifies spec selection, operation preview, local insertion without an automatic Scenario `PATCH`, and that API Catalog pages expose no generation actions.
6. The mapper resolves local `$ref` values only. OpenAPI validation uses no remote resolver handlers, and the mapper does not fetch remote `$ref`, spec `servers[]`, or external URLs.
7. JSON body generation uses explicit media examples/examples, schema example/default, or bounded samples for object properties whose child schemas can be safely sampled. Optional-only JSON objects now generate raw JSON when at least one optional child is safely sampleable; empty, unsupported, recursive-only, over-depth, or over-size samples still return `JSON_BODY_EXAMPLE_MISSING`. Form, multipart, file upload, assertions, extractors, scripts, response assertions, and Taurus YAML generation remain out of scope.
8. Review hardening maps OpenAPI 3.x `security` / `components.securitySchemes` and Swagger 2.0 `security` / `securityDefinitions` for API key, basic, bearer, OAuth2/OpenID Connect-style credential requirements to `AUTH_HEADER_NOT_GENERATED` warnings without generating cleartext credential values.
9. Review hardening skips named values for unsupported parameter serialization such as array/object query/header parameters, `deepObject`, matrix/label/pipe/space-delimited styles, and other non-scalar first-version shapes, returning `UNSUPPORTED_PARAMETER_STYLE` warnings instead of unsafe stringification.
10. Web wrappers live in `apps/web/src/app/api-client.ts`; Scenario draft materialization lives in `apps/web/src/features/scenarios/model.ts`; the Scenario Designer From OpenAPI UI lives in `apps/web/src/features/scenarios/pages/scenario-designer-page.tsx`.
11. Scenario Designer resolves OpenAPI generation requests with `session.currentWorkspace.id ?? session.defaultWorkspace.id`; this matches the P2 API Catalog current-Workspace behavior and avoids using the default Workspace after an explicit Workspace switch.
12. Web insertion is local-only until the user uses the existing Scenario Save action, which still calls `patchScenario`.
13. Independent review hardening added after the initial implementation: Scenario-scoped spec source listing returns only `available` API Catalog specs, recursive local schema sampling is bounded, Swagger 2.0 non-JSON `consumes` leaves the body empty with a warning, OpenAPI-generated Steps materialize without assertions, the Web operation selector communicates/enforces the 20-operation limit, security-scheme credentials emit `AUTH_HEADER_NOT_GENERATED` without generated secrets, unsupported parameter serialization emits `UNSUPPORTED_PARAMETER_STYLE` without unsafe named-value stringification, and optional-heavy JSON object bodies sample safe optional properties instead of incorrectly falling back to missing body.
14. Tests added: `apps/api/tests/test_p2_01_openapi_step_generation.py`, `tests/contract/test_p2_01_openapi_step_generation_openapi.py`, Scenario Designer coverage in `apps/web/src/features/scenarios/scenarios.test.tsx`, and Playwright smoke `tests/e2e/p2_01_openapi_step_generation.spec.ts`.
15. Supplemental verifier added: `scripts/surgepilot_e2e_helpers.py` materializes preview-only OpenAPI Step drafts into Scenario `PATCH`-safe Steps for API-level E2E automation, mirroring the Web materialization boundary without changing P2-01 API behavior. `scripts/verify_p2_01_openapi_two_node_e2e.py` exercises API Catalog upload, OpenAPI Step draft generation, materialized Scenario save, and a P1-01 two-node Standard Run. `make verify-p2-01-openapi-two-node-e2e` runs this opt-in SSH E2E verifier; it is not part of default `make verify`.
16. `apps/api/app/services/openapi_step_generation.py` now keeps a process-local LRU cache with a fixed capacity of 8 successful `ParsedOpenApiDocument` values. The cache key is `(workspace_id, spec.id, spec.sha256, spec.status)`; lookup and eviction are protected by a thread lock. Scenario access, Workspace resolution, spec ownership lookup, and `status == available` validation still complete before a cached document can be reused. Parse, validation, and storage failures are never cached.
17. Cached parsed documents are shared as immutable inputs to enumeration and draft mapping. API tests verify repeated generation returns identical results without mutating the cached document, SHA/status/Workspace key changes do not reuse the wrong entry, failures retain the existing error code/status/message/details, LRU eviction remains bounded, and concurrent mixed cache access does not corrupt entries or exceed capacity. The cache is intentionally non-persistent and per API process; each worker may perform its own cold validation, and concurrent cold misses may duplicate validation without changing correctness.
18. Scenario Designer OpenAPI spec and operation queries use a 30-second `staleTime`. The modal shows explicit spec/operation loading copy and disables affected selectors, operation choices, and preview generation while their query is fetching. Closing and immediately reopening the modal can reuse fresh query data, while draft generation remains an authoritative uncached POST.

Verification commands run during implementation:

```bash
make generate-contracts
uv run --project apps/api pytest apps/api/tests/test_p2_01_openapi_step_generation.py -q
uv run pytest tests/contract/test_p2_01_openapi_step_generation_openapi.py -q
pnpm --filter @surgepilot/web test -- src/features/scenarios/scenarios.test.tsx
pnpm --filter @surgepilot/web typecheck
uv run --all-packages ruff check apps/api/app/main.py apps/api/app/routes/scenarios.py apps/api/app/schemas/scenarios.py apps/api/app/services/openapi_step_generation.py apps/api/tests/test_p2_01_openapi_step_generation.py tests/contract/test_p2_01_openapi_step_generation_openapi.py
uv run --all-packages ruff format --check apps/api/app/main.py apps/api/app/routes/scenarios.py apps/api/app/schemas/scenarios.py apps/api/app/services/openapi_step_generation.py apps/api/tests/test_p2_01_openapi_step_generation.py tests/contract/test_p2_01_openapi_step_generation_openapi.py
pnpm --filter @surgepilot/web lint
pnpm --filter @surgepilot/web test -- src/features/scenarios/scenarios.test.tsx
pnpm exec playwright test tests/e2e/p2_01_openapi_step_generation.spec.ts --project=chrome
make verify
```

Performance-cache follow-up verification:

```bash
make generate-contracts
uv run --project apps/api pytest apps/api/tests/test_p2_01_openapi_step_generation.py -q
uv run pytest tests/contract/test_p2_01_openapi_step_generation_openapi.py -q
pnpm exec vitest run src/features/scenarios/scenarios.test.tsx --no-file-parallelism
pnpm --filter @surgepilot/web typecheck
pnpm --filter @surgepilot/web lint
make verify
```

`make generate-contracts` produced no OpenAPI or generated Web client diff because this optimization does not change schemas, routes, or response shapes.
