# P2-00 API Catalog Scalar

- Document status: Accepted for P2-00 implementation; P0/P1 shall not implement user visibility capabilities in advance based on this
- Stage: P2
- Capability:`api_catalog`
- Related solutions: P2 API Catalog Scalar renderer selection and boundary brief
- Scope Gate:`docs/sdd/00-product-scope-and-priority.md` §7
- P2 Index:`docs/sdd/slices/P2-README.md`
- API Contract Boundary:`docs/sdd/04-api-contract-guidelines.md`
- Security Boundary:`docs/sdd/06-security-permission-workspace.md`
- Storage Boundary:`docs/sdd/07-storage-artifacts-minio.md`
- Frontend Route Boundary:`docs/sdd/08-frontend-routing-and-ui-rules.md`
- Testing Boundary:`docs/sdd/09-testing-and-acceptance-strategy.md`
- ADR Boundary: `docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md`; If you subsequently change the Scalar access form, dependency strategy, or the boundary between Catalog and Scenario/Test Plan, you must add or update the ADR/Scope Gate

## 1. Goal

P2-00 adds **API Catalog document asset management** capabilities. Users can upload OpenAPI / Swagger spec, view the asset list, open the details page, and delete assets in the Workspace; the details page uses **Scalar API Reference** to render the saved spec, providing a basic readable, searchable, and expandable API Reference experience.

Goal:

1. Explicitly limit the API Catalog to documentation asset management: `upload / list / detail / delete` .
2. The backend continues to manage spec original text, metadata, permissions, Workspace and storage boundaries; the Web is not directly connected to MinIO.
3. The details page only sends the authorized spec content proxy URL to Scalar for rendering.
4. Scalar only serves as a detail page OpenAPI / Swagger renderer, and does not become an API client, request sender, contract generator, Scenario/Test Plan generator or independent document service.
5. All Web API access continues through FastAPI/Pydantic OpenAPI exports and `@surgepilot/contracts` generated client/types.

P2-00 must not become a pre-dependency of the main link of P0/P1 Scenario -> Test Plan -> Run -> Run Report.

## 2. PRD / Scope Trace

`docs/sdd/00-product-scope-and-priority.md` §7 Fixed P2 `API Catalog` to "API document asset management, only upload / list / details / delete" and clarify:

1. `P2 API Catalog is documentation asset management only; it does not create, update, or generate Scenario/Test Plan.`
2. P2 API Catalog does not include version diff, operation import, coverage analysis or API -> Scenario/Test Plan generation.
3. Even if the automatic generation of OpenAPI Step is classified into P2, it cannot be implemented in advance as the API Catalog -> Scenario/Test Plan generation link.

`docs/sdd/08-frontend-routing-and-ui-rules.md` has listed `/api-catalog` and `/api-catalog/:specId` as P1/P2 planned routes; before P2 is officially activated, clickable navigation, available placeholder pages, or available routes must not be added.

This Slice locks in the following conclusions:

1. The default selection of P2-00 is Scalar API Reference. It does not develop its own OpenAPI renderer, nor does it use Swagger UI as the default solution.
2. The resource boundary of the API Catalog is the `apiCatalogSpec` document asset; no operation is imported, no Step is generated, no Scenario is created, and no Test Plan is created.
3. The Scalar configuration must turn off the real request sending entrance, including the `Test Request` / `Try it` class capabilities.
4. Scalar must not directly read MinIO, object key, bucket, presigned URL, server path or external proxy.
5. P2-00 can add Web routes `/api-catalog` and `/api-catalog/:specId`, but only access navigation when P2 active Slice is implemented.
6. It is still in the development stage; except for the existing OpenAPI / generated contract workflow, no historical compatibility layer will be introduced.

Governance prerequisites:

1. P2-00 has been activated by `docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md` as a separate accepted implementation decision.
2. `P2-README.md` is an index only; implementations may not be launched directly from placeholder copy.
3. If the implementation requires API -> Scenario/Test Plan generation, operation import, coverage analysis, OpenAPI Step generation, background tasks, queues, external API Gateway, independent docs service, external object storage backend, self-developed renderer or a second set of UI themes, you must first update the Scope Gate or add a new ADR.

## 3. In Scope

1. API: Added `upload / list / detail / content / delete` public business APIs of API Catalog spec asset.
2. Upload validation: Backend execution authentication, Workspace, CSRF, size, JSON/YAML parsing, OpenAPI/Swagger root shape, safe filename/content type constraints.
3. Storage: The original spec text is saved as a controlled asset, and existing MinIO/metadata boundaries are prioritized for reuse; Web and Scalar are only read through API authorization agents.
4. Data model: Added minimal conceptual model `ApiCatalogSpec`, which only records metadata, Workspace ownership, storage reference, security status and parsing summary.
5. Web: `/api-catalog` list page and `/api-catalog/:specId` detail page are added after P2 activation.
6. Renderer: detail page renders the saved spec using `@scalar/api-reference-react` or equivalent Scalar API Reference integration.
7. Scalar hardening: Close request sending, Agent/MCP, hosted proxy, auth persistence, developer tools and non-SurgePilot topic switching entrances.
8. Contracts: FastAPI/Pydantic schema is the true source of API contract; `@surgepilot/contracts` is generated after OpenAPI export, and the Web does not hand-write the request/response type.
9. Tests / verification:API route/storage/contract tests, Web route/component tests, Scalar disabled-request assertions, no MinIO direct access assertions.

## 4. Out of Scope

1. API -> Scenario/Test Plan generation, Scenario creation/update, Test Plan creation/update.
2. OpenAPI operation import, OpenAPI Step auto-generation, operation-to-step mapping, operation coverage analysis.
3. Version diff, spec version graph, breaking-change analysis, schema registry, SDK generation, mock server, MCP server, AI Agent chat.
4. Online spec editing, spec merge, spec lint rule configuration, custom docs authoring, Markdown docs hosting.
5. Independent document service, external API Gateway, external Scalar hosted docs, Scalar Registry, Scalar hosted proxy, reverse proxy as request sender.
6. Web direct connection MinIO, presigned URL, bucket/object key/server path are exposed.
7. New microservices, queues, background worker preprocessing, cache platform, object-storage abstraction beyond current MinIO boundary.
8. The second set of UI component system, the second set of theme provider, hard-coded colors, and P0/P1 dark mode implementation.
9. Runner, api-worker, Run Snapshot, Run state machine, Taurus builder or Load Node behavior changes.
10. DB table name, column type, index, migration script, complete ORM/Pydantic/TS type handwritten design.
11. User-provided, externally fetched, scheduled, startup-reconciled, background automatic OpenAPI ingestion, and the P2-04 first-Admin system OpenAPI bootstrap.

## 5. Preconditions

1. Business APIs continue to use `/api/v1`, cookie session auth, `x-workspace-id`, write `x-csrf-token`, `x-request-id`, camelCase JSON, lower snake case enum values and the existing `{code, message, requestId, details?}` error envelope.
2. API remains the only server-side owner of PostgreSQL metadata, MinIO access, Workspace filtering and storage safety decisions.
3. Web must call API through generated contracts from `@surgepilot/contracts` and must not import generated files by relative path.
4. Web must not access PostgreSQL, MinIO, Load Nodes, runner endpoints or storage credentials directly.
5. Existing storage rules remain: Web receives no bucket, object key, presigned URL, MinIO URL or server path.
6. Current `AppLayout` nav groups and Tailwind / CSS variable token rules remain authoritative; API Catalog must fit into existing layout rather than introducing a new shell.
7. Scalar dependency version, import mode and bundle strategy must be pinned through the implementation PR according to the repository package policy; if the integration cannot satisfy §10 hardening, implementation must stop and add an ADR before shipping.

## 6. Locked Core Decisions

| ID | Decision |
| --- | --- |
| APC-01 | P2-00 implements documentation asset management only: upload, list, detail, content proxy and delete. |
| APC-02 | Scalar API Reference is the default detail-page renderer for saved OpenAPI / Swagger specs. |
| APC-03 | SurgePilot API owns spec storage, metadata, auth, Workspace enforcement, validation and content proxying. |
| APC-04 | Web and Scalar must never receive MinIO bucket, object key, presigned URL, MinIO endpoint, server path or storage credentials. |
| APC-05 | Scalar must render from an authorized same-origin API `contentUrl`; it must not use MinIO direct links or external hosted proxy URLs. |
| APC-06 | Scalar request sending is disabled with `hideTestRequestButton: true`; Catalog must expose no Test Request / Try it / real request execution path. |
| APC-07 | Scalar Agent, MCP integration, hosted proxy, auth persistence and developer tools are disabled or omitted. |
| APC-08 | API Catalog never creates, updates, imports or generates Scenario, Step, Test Plan, Run, artifact, assertion, script or Taurus YAML behavior. |
| APC-09 | The upload endpoint validates only enough to store and render a documentation asset safely; it is not a full OpenAPI governance, linting, diff or compatibility platform. |
| APC-10 | Delete affects only the API Catalog spec asset and stored spec content; it must not cascade into Scenario, Test Plan, Run or Artifact domains. |
| APC-11 | No DB table/column/index detail is locked in this SDD; implementation must backfill actual storage facts after reading code and migrations. |
| APC-12 | No independent docs service, queue, microservice, API Gateway, second theme provider or self-built OpenAPI renderer is introduced. |

## 7. Architecture

```text
API Catalog list page
  -> Web calls listApiCatalogSpecs through generated client
  -> API authenticates session, resolves Workspace and returns metadata envelope

Upload flow
  -> user selects one OpenAPI / Swagger JSON or YAML file
  -> Web posts multipart form through generated uploadApiCatalogSpec client with x-workspace-id + x-csrf-token
  -> API validates auth, Workspace, size, filename, content type, parseability and OpenAPI/Swagger root shape
  -> API stores raw spec as controlled MinIO asset and persists metadata
  -> API returns ApiCatalogSpecResponse without storage internals

Detail/render flow
  -> Web opens /api-catalog/:specId
  -> Web calls getApiCatalogSpec through generated client
  -> API validates auth + Workspace and returns metadata + contentUrl
  -> Web passes same-origin contentUrl into Scalar configuration
  -> Scalar fetches spec through API content proxy using the current browser session
  -> Scalar renders documentation only, with request sending and external integrations disabled

Delete flow
  -> Web calls deleteApiCatalogSpec with x-workspace-id + x-csrf-token
  -> API validates auth + Workspace
  -> API deletes or tombstones the Catalog metadata and removes / invalidates the stored spec object according to existing storage conventions
  -> Scenario, Test Plan, Run and Artifact domains are unchanged
```

Component boundaries:

| Component | Responsibility | Forbidden |
| --- | --- | --- |
| `apps/api/app/routes/api_catalog.py` or equivalent API Catalog router | Expose upload/list/detail/content/delete, enforce auth, Workspace, CSRF for writes, safe errors and OpenAPI schemas. | Scenario/Test Plan generation, operation import, returning storage internals, stack traces or server paths. |
| API Catalog service | Validate basic OpenAPI/Swagger asset shape, store spec through existing storage client, resolve metadata in current Workspace. | Full lint platform, diff engine, background importer, generated Step mapping, external API calls. |
| Storage service boundary | Continue owning server-side MinIO object writes/reads/deletes or invalidation. | Browser-visible storage access, object-key exposure, presigned URL, new storage backend abstraction. |
| `@surgepilot/contracts` | Generated Web client/types from FastAPI OpenAPI. | Hand-edited OpenAPI or generated TypeScript as source of truth. |
| Web API Catalog feature module | Render list/upload/delete/detail states and hand authorized `contentUrl` to Scalar. | Hand-written API types, direct MinIO fetch, hidden generation buttons, custom OpenAPI renderer. |
| Scalar renderer | Render readable/searchable/expandable API Reference from one authorized spec. | Sending real requests, persisting auth, Agent/MCP/chat, proxying to external targets, owning spec storage. |
| Runner / Run / Scenario / Test Plan domains | No change. | Any dependency on API Catalog asset existence or Scalar rendering. |

## 8. API Contract

### 8.1 Endpoints

| Method | Path | Operation ID | Response | Contract |
| --- | --- | --- | --- | --- |
| `GET` | `/api/v1/api-catalog/specs` | `listApiCatalogSpecs` | `200 ApiCatalogSpecListResponse` | Return current Workspace spec metadata list. Requires session and Workspace. |
| `POST` | `/api/v1/api-catalog/specs` | `uploadApiCatalogSpec` | `201 ApiCatalogSpecResponse` | Upload one OpenAPI / Swagger JSON/YAML spec as a controlled asset. Requires session, Workspace and CSRF. |
| `GET` | `/api/v1/api-catalog/specs/{specId}` | `getApiCatalogSpec` | `200 ApiCatalogSpecResponse` | Return one spec metadata record plus same-origin `contentUrl`. Requires session and Workspace. |
| `GET` | `/api/v1/api-catalog/specs/{specId}/content` | `getApiCatalogSpecContent` | `200` raw JSON/YAML spec content | Stream or return the authorized stored spec content for Scalar rendering. Requires session and Workspace. |
| `DELETE` | `/api/v1/api-catalog/specs/{specId}` | `deleteApiCatalogSpec` | `204` or `200 ApiCatalogSpecDeleteResponse` | Delete one API Catalog spec asset only. Requires session, Workspace and CSRF. |

Rules:

1. Route paths must not include `workspaceId`; Workspace is resolved from `x-workspace-id` / existing default Workspace rules.
2. `specId` must be a ULID business ID and use `{specId}` path parameter naming.
3. Upload and delete require `x-csrf-token`; list/detail/content are GET reads and do not require CSRF.
4. List response must use an envelope with `items`; bare arrays are forbidden.
5. API JSON fields are camelCase; enum values are lower snake case.
6. The content endpoint must perform the same auth + Workspace filtering as detail before reading storage.
7. The content endpoint may return `application/json`, `application/yaml`, `text/yaml` or `application/octet-stream` only as a download-safe/read-safe proxy response; it must not return storage metadata.
8. Response headers must include `x-request-id`; successful Workspace-aware responses should attach `x-workspace-id` consistently with existing business APIs.
9. OpenAPI examples must use harmless demo specs and must not include production hostnames, secrets, object keys, bucket names, MinIO URLs or local paths.
10. No API response may include operation-level import hints, Scenario IDs, Test Plan IDs, Run IDs or generation affordance fields.

### 8.2 Upload request contract

`ApiCatalogSpecUploadRequest` is a multipart form request:

| Field | Required | Contract |
| --- | --- | --- |
| `file` | yes | One JSON or YAML OpenAPI / Swagger document. The API enforces a configured max upload size before parsing. |
| `name` | no | Optional display name. If omitted, API derives a safe display name from `info.title` or the safe filename. |

Upload validation rules:

1. Empty file, multiple files, over-size file, unsupported extension/content type, invalid JSON/YAML, missing OpenAPI/Swagger root marker or missing `info.title`-compatible metadata returns `422 VALIDATION_ERROR` or a more specific code from §8.5.
2. Supported root markers are OpenAPI 3.x `openapi` and Swagger 2.0 `swagger`.
3. JSON/YAML parser errors must be reported safely without echoing large spec excerpts, local paths or parser stack traces.
4. Upload must compute and store a SHA-256 digest for duplicate/debug visibility, but P2-00 does not require dedupe behavior.
5. Upload does not call external URLs referenced by the spec and does not resolve remote `$ref` values.
6. Upload does not create Scenario, Step, Test Plan, Run, Artifact or background generation jobs.

Representative upload response:

```json
{
  "id": "01J0Y6T6H2Y0S9V4W8M7N6P5Q4",
  "name": "Orders API",
  "filename": "orders-openapi.yaml",
  "sourceFormat": "openapi_yaml",
  "openapiVersion": "3.1.0",
  "documentTitle": "Orders API",
  "documentVersion": "1.0.0",
  "sizeBytes": 48152,
  "sha256": "3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7",
  "status": "available",
  "contentUrl": "/api/v1/api-catalog/specs/01J0Y6T6H2Y0S9V4W8M7N6P5Q4/content",
  "createdAt": "2030-06-24T05:00:00Z",
  "updatedAt": "2030-06-24T05:00:00Z"
}
```

### 8.3 List / detail response contract

`ApiCatalogSpecListResponse`:

| Field | Required | Contract |
| --- | --- | --- |
| `items` | yes | `ApiCatalogSpecSummary[]`; only current Workspace assets. |
| `total` | yes | Total matching assets for offset pagination. |
| `limit` | yes | Effective limit. |
| `offset` | yes | Effective offset. |

`ApiCatalogSpecSummary` representative fields:

| Field | Required | Contract |
| --- | --- | --- |
| `id` | yes | ULID business ID. |
| `name` | yes | User-visible display name or derived safe name. |
| `filename` | yes | Safe original filename for display. |
| `sourceFormat` | yes | `openapi_json`, `openapi_yaml`, `swagger_json` or `swagger_yaml`. |
| `documentTitle` | yes | Title parsed from `info.title` when available; fallback to `name`. |
| `documentVersion` | yes | Version parsed from `info.version` when available; fallback to empty string or `unknown` according to implementation schema. |
| `sizeBytes` | yes | Stored raw spec size. |
| `sha256` | yes | Digest of stored raw spec bytes. |
| `status` | yes | `available`, `invalid` or `storage_unavailable`. |
| `createdAt` / `updatedAt` | yes | ISO 8601 UTC strings with `Z`. |

`ApiCatalogSpecResponse` extends summary with:

| Field | Required | Contract |
| --- | --- | --- |
| `openapiVersion` | yes | OpenAPI or Swagger version string detected at upload. |
| `contentUrl` | yes | Same-origin API proxy URL for Scalar. It is not a MinIO URL, presigned URL or external proxy URL. |
| `validationMessage` | no | Safe English fallback for `invalid` status; must not include full spec excerpts. |

List representative response:

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
      "sizeBytes": 48152,
      "sha256": "3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7",
      "status": "available",
      "createdAt": "2030-06-24T05:00:00Z",
      "updatedAt": "2030-06-24T05:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### 8.4 Delete contract

1. Delete is scoped to the current Workspace and one `specId`.
2. Delete must not expose whether the same `specId` exists in another Workspace.
3. Delete removes or tombstones API Catalog metadata and invalidates/removes the associated storage object according to existing storage conventions.
4. Delete must not mutate Scenario, Test Plan, Run, Run Report, Dependency File or Artifact data.
5. Repeated delete after the asset no longer exists may return existing access-safe `404 RESOURCE_NOT_FOUND`; P2-00 does not require idempotent success.

### 8.5 Error contract

| Condition | HTTP | Code | Contract |
| --- | ---: | --- | --- |
| Missing/invalid auth | 401 | existing auth code | Existing auth middleware behavior. |
| Missing/unresolvable Workspace | 400 | `WORKSPACE_REQUIRED` | Existing Workspace behavior when no default can be resolved. |
| Workspace access denied | 403 | existing workspace/permission code | Existing Workspace enforcement behavior. |
| Invalid `specId` | 422 | `VALIDATION_ERROR` | Field-level details; no storage lookup. |
| Spec not found in current Workspace | 404 | `RESOURCE_NOT_FOUND` | No cross-Workspace existence leak. |
| Upload too large | 413 or 422 | `API_SPEC_TOO_LARGE` | Safe message with configured limit; no content echo. |
| Invalid JSON/YAML or unsupported root | 422 | `API_SPEC_PARSE_FAILED` or `UNSUPPORTED_API_SPEC_FORMAT` | Safe parse/format details only. |
| Storage write/read unavailable | 503 | `STORAGE_UNAVAILABLE` | No bucket/object key/path in response. |
| Scalar render unavailable because content endpoint fails | existing safe error | existing safe code | Web shows detail error state; list remains usable. |

Error examples must use the existing envelope:

```json
{
  "code": "UNSUPPORTED_API_SPEC_FORMAT",
  "message": "The uploaded file must be an OpenAPI or Swagger document.",
  "requestId": "req_01J0Y6T6H2Y0S9V4W8M7N6P5Q4",
  "details": [
    {
      "field": "file",
      "code": "missing_openapi_root",
      "message": "Expected an openapi or swagger root field."
    }
  ]
}
```

## 9. Data and Storage Model

Conceptual entity: `ApiCatalogSpec`.

Representative fields:

| Field | Visibility | Contract |
| --- | --- | --- |
| `id` | API | ULID business ID. |
| `workspaceId` | internal | Required for every asset; never appears in route path. |
| `name` | API | Display name controlled by upload request or parsed metadata. |
| `filename` | API | Safe filename for display; storage path must remain server-side only. |
| `sourceFormat` | API | Lower snake case enum describing OpenAPI/Swagger + JSON/YAML. |
| `documentTitle` / `documentVersion` | API | Parsed from spec `info`; safe display only. |
| `sizeBytes` / `sha256` | API | Stored raw spec metadata. |
| `status` / `validationMessage` | API | Safe renderer/list state; no spec excerpt or internal parser stack. |
| `storageRef` | internal | Existing storage reference sufficient for API server reads; never returned to Web. |
| `createdBy` / `createdAt` / `updatedAt` | API/internal as existing conventions allow | Audit-relevant ownership and timestamps. |

Invariants:

1. Metadata is Workspace-filtered before any storage read.
2. The raw spec is stored as a controlled asset through existing server-side storage client behavior.
3. Web-visible API responses never include `storageBucket`, `storageObjectKey`, bucket name, MinIO URL, presigned URL, server absolute path or storage credentials.
4. `contentUrl` is a same-origin API route and may be regenerated; clients must not persist it as a stable storage identifier.
5. Spec content is documentation input only; it is not trusted execution input, generated-contract input, Scenario input or Test Plan input.
6. Exact DB table name, column types, indexes and migration mechanics are intentionally left to implementation after reading existing models and migrations, then recorded in Implementation Backfill.

## 10. Web and Scalar Renderer Contract

### 10.1 Routes and navigation

| Route | Page | P2 behavior |
| --- | --- | --- |
| `/api-catalog` | API Catalog list | Shows upload action, asset list, status, detail link and delete action. |
| `/api-catalog/:specId` | API Catalog detail | Fetches authorized spec detail for `contentUrl`, uses the embedded-content AppLayout body, and renders Scalar as the primary API Reference surface; safe error states include a Back to API Catalog link. |

Rules:

1. These routes must not be implemented as clickable UI before P2 activation.
2. P2 activation may add an `API Catalog` nav entry using the existing `AppLayout` nav grouping. It must not create a second app shell.
3. Unknown, deleted or cross-Workspace `specId` renders existing Not Found / safe error UI.
4. List and detail pages must use generated API client/types through `@surgepilot/contracts`.
5. Web must not hand-write request/response types or construct storage URLs.

### 10.2 Scalar integration

Dependency contract:

| Item | Contract |
| --- | --- |
| Dependency | Use Scalar API Reference for React rendering, for example `@scalar/api-reference-react`, unless the implementation ADR selects an equivalent official Scalar integration. |
| Scope | Dependency is limited to API Catalog detail-page rendering. |
| Inputs | `contentUrl` from `getApiCatalogSpec`; no MinIO URLs, external proxy URLs or user-entered target URLs. |
| Styling | Import Scalar CSS as required by the official React integration, then constrain container styling through existing Tailwind tokens / CSS variables. |
| Fallback | If Scalar fails to load or render, Web shows a safe read-only error state and keeps list/delete/navigation usable. |

Required Scalar configuration constraints:

```ts
{
  url: contentUrl,
  hideTestRequestButton: true,
  hideClientButton: true,
  documentDownloadType: "none",
  darkMode: true,
  hideDarkModeToggle: false,
  persistAuth: false,
  telemetry: false,
  showDeveloperTools: "never",
  agent: { disabled: true },
  // mcp is omitted by default; if a future integration exposes mcp config, it must be disabled and must not include an external URL.
}
```

Implementation may omit optional disabled objects when the official Scalar integration treats omission as disabled. It must not omit `hideTestRequestButton: true`, and it must not configure MCP with an enabled external URL. `hiddenClients` is intentionally omitted so Scalar can show passive Client Libraries code examples; API Catalog must still hide the API client launch/send affordances and must not configure `proxyUrl`.

Forbidden Scalar configuration:

1. `proxyUrl`, including Scalar hosted proxy or SurgePilot reverse proxy for outgoing target requests.
2. `authentication.securitySchemes` with prefilled credentials.
3. `persistAuth: true`.
4. `showDeveloperTools: "always"` or localhost-only developer tools in production builds.
5. Agent key, MCP URL, custom plugin that sends requests, external registry URL, external hosted docs URL.
6. Any configuration that makes Scalar issue real API calls to user spec `servers[]` targets from API Catalog.

### 10.3 UI behavior

1. Upload UI accepts one file at a time.
2. Upload success returns to or refreshes the list and offers a detail link.
3. Delete uses an explicit confirmation and removes only the selected API Catalog asset.
4. Detail page currently keeps the API Reference focused: it fetches metadata to obtain the safe same-origin `contentUrl`, then renders the Scalar wrapper as the primary content area instead of duplicating a metadata/card header outside Scalar. Safe loading/error states remain SurgePilot-owned UI.
5. The `AppLayout` treats `/api-catalog/:specId` as an embedded-content page, preserving the global sidebar/top bar while removing standard page padding so the Scalar reference can use the available viewport.
6. Search, expand/collapse and schema navigation inside Scalar are allowed when they do not trigger network calls to target APIs.
7. The route must remain documentation-only; any SurgePilot-owned affordance outside Scalar should use clear English such as `Documentation only` when shown.
8. HTML generated from spec descriptions is delegated to Scalar only; SurgePilot must not add custom `dangerouslySetInnerHTML` rendering for spec content outside Scalar.
9. Styling must use Tailwind tokens / CSS variables; no hard-coded page colors and no second theme provider.
10. Scalar may expose its own local background toggle only inside the isolated renderer boundary. Toggle state must not mutate the SurgePilot `AppLayout`, global `body` class/style, or product theme provider.
11. Explicit Scalar sidebar operation navigation may scroll to the matching operation inside the isolated DOM boundary. Tag-only sidebar navigation such as `#tag/<group>` and `#api-1/tag/<group>` must remain delegated to Scalar so it only expands or collapses the group; initial URL fragments and Scalar's passive section-to-hash synchronization must not trigger a SurgePilot-owned scroll, and the wrapper must not replace global History API methods.

## 11. Security and Privacy Requirements

1. API must enforce auth, Workspace and permission checks before metadata or storage content is returned.
2. PostgreSQL metadata remains authoritative for Workspace ownership; object existence in MinIO never grants access.
3. The content endpoint must not be cacheable by shared intermediaries; responses that expose spec content should remain private/no-store unless an accepted ADR changes caching policy.
4. Spec content, upload parse excerpts and Scalar render errors must not be written to ordinary logs, audit details or analytics events.
5. Logs may include `specId`, actor ID, Workspace ID, safe status code, request ID, size, digest prefix and safe validation/error codes.
6. Logs must not include full spec content, secrets from examples, server paths, bucket names, object keys, MinIO endpoints, session cookies or CSRF tokens.
7. API Catalog does not perform generic sensitive-data redaction. Authorized users who can upload/read the spec may see examples embedded in that spec.
8. Upload does not resolve remote references, contact external servers, validate server reachability, execute code snippets or send HTTP requests.
9. Scalar must not receive auth credentials from SurgePilot other than the user's existing same-origin session cookie required to fetch the authorized content endpoint.
10. Error responses must be safe and must not leak parser internals or storage internals.

## 12. Observability and Audit

1. No new metrics are required for P2-00.
2. Existing request ID logging is sufficient for basic troubleshooting.
3. A minimal audit event may be added for `api_catalog_spec.uploaded` and `api_catalog_spec.deleted` only if existing audit conventions make it low-cost and safe; audit details must not include spec content.
4. A view/render audit event is not required.
5. Scalar UI events are not product analytics inputs in P2-00.

## 13. Compatibility and Migration

1. P2-00 may require a DB migration to store API Catalog metadata, but this SDD does not lock the table/column/index shape.
2. No existing Scenario, Test Plan, Run, Runner, Artifact or Dependency File migration is required.
3. No generated-contract compatibility layer or legacy route alias is required in the current development stage.
4. Existing `/api/v1` conventions, Workspace header rules, error envelope and generated-contract workflow remain unchanged.
5. If implementation later needs a non-MinIO storage backend, remote `$ref` resolver, OpenAPI lint platform or operation import model, that is a separate ADR/Scope Gate change.

## 14. Tests and Acceptance Criteria

### 14.1 API route and service tests

Minimum coverage:

1. `POST /api/v1/api-catalog/specs` accepts valid OpenAPI 3.x JSON.
2. Upload accepts valid OpenAPI / Swagger YAML when parser support is present.
3. Upload rejects empty file, multiple files, over-size file, malformed JSON/YAML, unsupported root and unsupported filename/content type with safe errors.
4. Upload requires authenticated session, Workspace and CSRF.
5. Upload stores raw spec through server-side storage and returns no storage internals.
6. `GET /api/v1/api-catalog/specs` returns only current Workspace assets in an `items` envelope.
7. `GET /api/v1/api-catalog/specs/{specId}` returns metadata + same-origin `contentUrl` and no storage internals.
8. `GET /api/v1/api-catalog/specs/{specId}/content` enforces auth + Workspace before storage read.
9. Cross-Workspace detail/content/delete returns access-safe not-found or existing access-safe behavior without existence leak.
10. Storage unavailable returns `STORAGE_UNAVAILABLE` without bucket/object key/path.
11. `DELETE /api/v1/api-catalog/specs/{specId}` affects only API Catalog metadata/storage and leaves Scenario/Test Plan/Run/Artifact data unchanged.
12. Upload does not resolve remote `$ref`, call spec `servers[]`, send network requests or enqueue background jobs.

### 14.2 Contract tests

1. OpenAPI contains operation IDs `listApiCatalogSpecs`, `uploadApiCatalogSpec`, `getApiCatalogSpec`, `getApiCatalogSpecContent` and `deleteApiCatalogSpec`.
2. JSON field names are camelCase and enum values are lower snake case.
3. List response is an envelope with `items`.
4. Error responses use `{code, message, requestId, details?}`.
5. Generated client/types are refreshed through `make generate-contracts`.
6. Contract stale check fails when OpenAPI or generated artifacts are stale.

### 14.3 Web tests

1. `/api-catalog` renders list, empty state, upload action, upload loading/error/success states and delete confirmation when P2 is active.
2. `/api-catalog/:specId` fetches authorized metadata for `contentUrl`, uses the embedded AppLayout body, and passes only `contentUrl` to the Scalar wrapper.
3. Web uses generated client/types from `@surgepilot/contracts`.
4. Detail page shows a safe error state when metadata or content fetch fails.
5. Delete removes only the selected API Catalog row from UI state after API success.
6. Page and component code contain no direct MinIO URL construction, bucket/object key display or storage credential usage.
7. UI styling uses existing layout/tokens and does not add a second theme provider.

### 14.4 Scalar hardening tests

1. Scalar wrapper receives `hideTestRequestButton: true`.
2. Detail UI exposes no `Test Request`, `Try it`, API client send/launch button, Agent, MCP or developer tools affordance. Passive Client Libraries code examples are allowed.
3. Scalar configuration does not include `proxyUrl`, hosted Scalar proxy, auth prefill or `persistAuth: true`.
4. Clicking around the rendered reference does not create real outbound requests to spec `servers[]` targets from API Catalog.
5. Detail page uses same-origin API `contentUrl`, not MinIO direct links or external registry URLs.
6. Scalar load/render failure does not break navigation back to the list.
7. Tag-only sidebar clicks do not trigger wrapper-owned scrolling, while operation sidebar clicks still scroll to the matching operation.
8. The Scalar reference defaults to its dark theme without forcing the toggle state or mutating the SurgePilot AppLayout theme.

### 14.5 Non-regression checks

1. Scenario create/get/patch/delete behavior remains unchanged.
2. Test Plan create/update/run-now behavior remains unchanged.
3. Run state machine, Runner callbacks and Taurus builder tests require no behavior changes.
4. Dependency File upload/preview/download/delete behavior remains unchanged.
5. P0/P1 routes do not gain clickable API Catalog entries before P2 activation.

## 15. Done When

P2-00 is complete only when:

1. `docs/sdd/slices/P2-00-api-catalog-scalar.md` is active through `ADR-0010` and indexed by `P2-README.md`.
2. API Catalog upload/list/detail/content/delete APIs exist under `/api/v1/api-catalog/specs` with generated OpenAPI contracts.
3. Upload validates basic OpenAPI / Swagger asset shape and saves raw spec as a controlled server-side asset.
4. API responses never expose bucket, object key, presigned URL, MinIO endpoint, server path or storage credentials.
5. Web routes `/api-catalog` and `/api-catalog/:specId` are available only when P2 is active.
6. Detail page renders Scalar from same-origin authorized `contentUrl`.
7. Scalar request sending and external integrations are disabled, especially `hideTestRequestButton: true`.
8. No API Catalog behavior creates, updates, imports or generates Scenario, Step, Test Plan, Run, Artifact or Taurus YAML.
9. No independent docs service, queue, microservice, external API Gateway, self-built renderer, second component system or second theme provider is introduced.
10. API route/service tests, contract tests, Web tests and Scalar hardening tests pass.
11. P2-04 first-Admin system OpenAPI bootstrap remains outside this Slice and is not available from the P2-00 API Catalog implementation.
12. Repository-level validation target is run before implementation merge:

```bash
make generate-contracts
make verify
```

If local infrastructure prevents full `make verify`, the implementation PR must state the closest subset run and exact limitation.

## 16. Implementation Backfill

Implementation must backfill the following after code is written and verified:

1. Final API files and route registration path.
2. Final schema names and generated operation names if they differ from §8.
3. Final metadata model and migration file names, without exposing storage internals to Web.
4. Final storage object key convention, kept server-side only.
5. Final upload size setting and supported extension/content-type list.
6. Final Scalar package, version, import mode and CSS integration.
7. Final Web feature module paths and route wiring.
8. Final tests added or extended.
9. Verification commands run and any environment gaps.
10. Implementation differences from this SDD, if any; differences that expand scope require ADR/Scope Gate update before merge.


### 16.1 Implementation Backfill

1. API route registration: `apps/api/app/routes/api_catalog.py` is included from `apps/api/app/main.py` under `/api/v1/api-catalog/specs` with operation IDs from §8.
2. API schemas: `apps/api/app/schemas/api_catalog.py` defines `ApiCatalogSpecSummary`, `ApiCatalogSpecResponse`, and `ApiCatalogSpecListResponse`; generated Web types are exported from `@surgepilot/contracts/web-client`.
3. Metadata model and migration: `apps/api/app/models/api_catalog.py` and `apps/api/migrations/versions/0015_p2_00_api_catalog.py` create `api_catalog_specs` with Workspace ownership, safe display metadata, SHA-256, status, timestamps, and server-only `storage_bucket` / `storage_object_key` fields.
4. Storage object key convention: raw specs are stored server-side under `api-catalog-specs/{workspaceId}/{specId}/{safeFilename}`. This value is never returned to Web or Scalar.
5. Upload limit and supported inputs: `SURGEPILOT_API_CATALOG_SPEC_MAX_BYTES` defaults to `10485760` bytes. Supported extensions are `.json`, `.yaml`, `.yml`; supported content types are JSON/YAML plus empty or `application/octet-stream` browser fallbacks.
6. Scalar package and import mode: Web uses pinned `@scalar/api-reference-react@0.9.47`, imports the Scalar stylesheet as `?inline`, injects it into a Shadow DOM wrapper, and wraps Scalar in `apps/web/src/features/api-catalog/components/scalar-reference.tsx`.
7. Scalar hardening: the wrapper sets `hideTestRequestButton: true`, `hideClientButton: true`, `documentDownloadType: "none"`, `darkMode: true`, `hideDarkModeToggle: false`, `persistAuth: false`, `telemetry: false`, `showDeveloperTools: "never"`, and disabled Agent config; it does not set `proxyUrl`, MCP, `hiddenClients: true`, or `forceDarkModeState`. Passive Client Libraries code examples are visible, while real request sending remains disabled. Scalar CSS is scoped in a Shadow DOM wrapper with a default black Scalar reference canvas, host `body` class/style mutations are restored so the AppLayout theme is not changed by the renderer, body-level Scalar teleport nodes receive sanitized temporary Scalar styles, and Scalar `light-mode` / `dark-mode` changes are mirrored only into the isolated Scalar wrapper and teleport nodes.
8. Web paths and layout: `apps/web/src/features/api-catalog/pages/api-catalog-list-page.tsx`, `apps/web/src/features/api-catalog/pages/api-catalog-detail-page.tsx`, and `apps/web/src/App.tsx` add `/api-catalog` and `/api-catalog/:specId` inside the existing `AppLayout` and Assets navigation. `apps/web/src/app/layouts/app-layout.tsx` classifies API Catalog detail as an embedded-content layout, preserving the app chrome while giving the Scalar reference full-width/full-height content space.
9. Dev routing fact: `apps/web/vite.config.ts` proxies `/api/` rather than `/api` so the `/api-catalog` client route is served by Vite instead of being proxied to FastAPI.
10. Tests added or extended: `apps/api/tests/test_p2_00_api_catalog_api.py`, `apps/web/src/features/api-catalog/api-catalog.test.tsx`, and `packages/contracts/tests/api-catalog-openapi.test.mjs`; focused coverage verifies API lifecycle and Workspace/storage boundaries, generated operation freshness, same-origin Scalar configuration, disabled request sending, and absence of storage internals or generation surfaces.
11. Verification status for this reconstruction worker: the focused test files and documentation were statically inspected; test/build runners were not invoked because this atomic explicitly forbids them. The listed tests remain the targeted verification surface for the checkpoint.
12. Implementation differences from this SDD: none that expand scope. Delete uses soft-deleted metadata plus best-effort object removal; repeated delete returns access-safe `404 RESOURCE_NOT_FOUND`. The detail page intentionally renders Scalar as the primary reference surface rather than duplicating a separate metadata card outside Scalar; this remains documentation-only and does not add generation, Try it, request sending, direct storage access, or Scenario/Test Plan actions.

13. R13 verification backfill: focused API route/service/storage assertions are in
    `apps/api/tests/test_p2_00_api_catalog_api.py`; generated contract freshness and lifecycle
    operation assertions are in `packages/contracts/tests/api-catalog-openapi.test.mjs`; Web route
    and Scalar hardening assertions are in `apps/web/src/features/api-catalog/api-catalog.test.tsx`.
    These checks assert the same-origin content proxy, Workspace boundary, server-only storage
    internals, disabled request/external integrations, and absence of later-slice generation
    surfaces. ADR-0016 remains documentation-only for this reconstruction checkpoint.
