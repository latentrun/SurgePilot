# P1-04 Scenario / Test Plan Polish

- Document status: Accepted for implementation
- Stage: P1
- Capability:`scenario_testplan_polish`
- Scope Gate:`docs/sdd/00-product-scope-and-priority.md` §6
- P1 Index:`docs/sdd/slices/P1-README.md`
- API Contract Boundary:`docs/sdd/04-api-contract-guidelines.md`
- Security Boundary:`docs/sdd/06-security-permission-workspace.md`
- Frontend Route Boundary:`docs/sdd/08-frontend-routing-and-ui-rules.md`
- Testing Boundary:`docs/sdd/09-testing-and-acceptance-strategy.md`
- Preview amendment: `docs/sdd/adr/ADR-0023-remove-scenario-execution-preview.md`; Scenario Preview is removed and Test Plan Preview remains.
- Related follow-up Slice: `docs/sdd/slices/P1-09-scenario-global-configuration.md`, licensed separately by `docs/sdd/adr/ADR-0015-p1-scenario-global-configuration.md`; does not change Clone / Archive / Tags or the amended Test Plan Preview boundary of this Slice.

## 1. Goal

P1-04 adds lightweight management and diagnosability polish to Scenario/Test Plan: Clone, Archive semantics, a read-only Test Plan Generated YAML/execution config preview, and existing tags experience organization.

Goal:

1. Users can clone new objects from existing Scenario/Test Plan to reduce repeated configurations.
2. The deletion mentality of Scenario/Test Plan is unified into Archive; the object is hidden from the active list, but the historical Run Snapshot/Run Report remains self-consistent.
3. Users can view the read-only YAML / execution config preview generated from the saved Test Plan revision for troubleshooting and configuration confirmation.
4. Scenario remains a structured visual editor with Debug Run; it does not expose a Generated YAML Preview.
5. Scenario / Test Plan tags maintain lightweight metadata positioning and only polish existing input, display, errors and empty states.
6. P1-04 does not extend to the version system, YAML editor, API Catalog, scheduling, multi-node or resource templates.

P1-04 is for experience improvement and efficiency enhancement and must not become a pre-dependency of the main link of P0 Scenario -> Test Plan -> Run -> Run Report.

## 2. PRD / Scope Trace

`docs/sdd/00-product-scope-and-priority.md` §6 locks P1 Scenario/Test Plan polish to Clone, Archive, Test Plan-only Read-Only Generated YAML/Execute Configuration Preview, and Existing Lightweight Tags.

This Slice locks in the following conclusions:

1. P1-04 only enables Scenario/Test Plan polish, and does not introduce API Catalog, OpenAPI Step automatic generation, API -> Scenario/Test Plan generation link or cURL Import.
2. Archive reuses the existing `DELETE` + soft delete path; does not add a new `/archive` action endpoint.
3. Test Plan Preview is read-only and is only generated from saved revisions; the frontend must not construct Taurus YAML, edit YAML, or write back in reverse.
4. Scenario Generated YAML Preview and its API contract are not product capabilities. Scenario Debug Run continues to accept its existing Env Group input.
5. Tags only cover the existing `tags` field of Scenario/Test Plan; do not extend to Env Group, Dependency File, Load Node, Run or other assets.
6. FastAPI/Pydantic is still OpenAPI source of truth; Web can only consume generated client/types.
7. It is still in the development stage. This article defines API, Web copy, testing and contracts in the target state without setting up historical clients or old data compatibility layers.

Governance prerequisites:

1. The implementation of P1-04 is authorized only after this document exists as the active P1 Slice SDD.
2. `P1-README.md` is only used as an index; the implementation must not be started directly from the placeholder copy.
3. If the implementation requires API Catalog, OpenAPI upload, OpenAPI Step generation, Schedule, Monitoring, multi-node, Reusable Load Profile, Bulk Apply, Secret, OIDC, resource template or editable YAML, you must first add ADR or update PRD/Scope Gate.

## 3. In Scope

1. Scenario polish:clone saved Scenario;archive Scenario through existing `DELETE` route semantics;polish existing tags input, display, copy and errors;do not expose Generated YAML Preview.
2. Test Plan polish:clone saved Test Plan;archive Test Plan through existing `DELETE` route semantics;expose read-only debug / standard execution preview;polish existing tags input, display, copy and errors.
3. API / contracts:add clone endpoints;keep the Test Plan preview endpoint and schema;remove the Scenario preview endpoint;keep existing `DELETE` endpoints as the archive transport;generate contracts from FastAPI/Pydantic via the repository workflow.
4. Backend services:copy persisted business content;reuse existing Taurus document builders for Test Plan Preview;apply a safe preview projection;keep Workspace, CSRF, session, revision, soft-delete and reference validation boundaries.
5. Web:list/detail affordances for Clone and Archive;Test Plan editor read-only Preview panel;no Scenario Preview panel;centralized English copy;generated client only.
6. Tests / verification gates:API, contract and Web tests for clone, archive, preview and tag polish;`make generate-contracts` and `make verify` before implementation merge.

## 4. Out of Scope

1. API Catalog, OpenAPI / Swagger upload, OpenAPI Step automatic generation or API -> Scenario/Test Plan generation.
2. cURL Import; that belongs to the P1 cURL Import Slice.
3. Editable Taurus YAML, YAML import, YAML apply, YAML diff/merge, reverse write-back, or a full YAML editor.
4. New version history, branch/version graph, restore point, rollback, compare revisions or revision browser.
5. Restore archived Scenario/Test Plan, `includeArchived`, archived list, recycle bin, physical delete UI or permanent-delete contract.
6. New tag filtering UI, global tag service, tag management backend, tag color taxonomy or tag autocomplete backed by a new service.
7. Tags for Env Group, Dependency File, Load Node, Run or other assets.
8. Schedule Run, Scheduled Job, Monitoring, multi-node execution, Resource matching, Load Profile template, Bulk Apply, Secret, OIDC/SSO or enterprise security extensions.
9. Starting a Run, acquiring a node lease, creating a Run Snapshot, writing artifacts or updating node status from preview.
10. New open-source runtime dependencies.

## 5. Preconditions

1. P0 Scenario CRUD, revision, Workspace filtering and soft delete are available in `apps/api/app/models/scenarios.py`, `apps/api/app/routes/scenarios.py`, and `apps/api/app/services/scenarios.py`.
2. P0 Test Plan CRUD, revision, Workspace filtering and soft delete are available in `apps/api/app/models/test_plans.py`, `apps/api/app/routes/test_plans.py`, and `apps/api/app/services/test_plans.py`.
3. Scenario and Test Plan schemas already expose `tags`; P1-04 must reuse and polish those fields rather than adding a new tag model.
4. Existing Taurus document builders are the implementation source for Test Plan Preview output. Test Plan Preview uses `apps/api/app/services/test_plans.py` and the shared Scenario builder functions it already composes.
5. Existing Scenario Debug Run accepts optional Env Group input for variable resolution and remains independent of the removed Scenario Preview surface.
6. Business APIs continue to use `x-workspace-id`, session auth, and `x-csrf-token` on writes.
7. Current Web API calls continue to be generated from `@surgepilot/contracts`; no handcrafted HTTP shape may be introduced.
8. No database migration is required for P1-04 unless implementation discovers that a deployed development database is missing already-modeled P0 columns. The target model uses existing `revision`, `tags_json`, `deleted_at`, `created_by` / `updated_by` fields.

## 6. Locked Core Decisions

| ID | Decision |
| --- | --- |
| STP-01 | P1-04 is a light polish Slice for Scenario / Test Plan only. |
| STP-02 | Clone creates a new object with a new ID and `revision=1`; it does not create a new version of the source. |
| STP-03 | Clone copies persisted business content only; it must not copy Run records, Run Snapshots, dedup keys, active run state, artifacts, or audit history. |
| STP-04 | Test Plan clone preserves references to existing same-Workspace Scenarios; it must not clone referenced Scenarios. |
| STP-05 | Archive is the product meaning of the existing `DELETE` routes; no `/archive` route is added. |
| STP-06 | Existing `DELETE` OpenAPI operation IDs remain stable unless implementation already needs regeneration for another reason; summaries, descriptions, Web copy and tests use Archive semantics. |
| STP-07 | Archived Scenario / Test Plan records are excluded from active lists, detail reads and clone sources; archived Test Plans are also excluded from Preview. |
| STP-08 | P1-04 does not expose restore, includeArchived, archived-list, recycle-bin or permanent-delete behavior. |
| STP-09 | Test Plan Preview is read-only and generated by the API from persisted revision state. |
| STP-10 | Web must never assemble, mutate, submit or reverse-apply preview YAML. |
| STP-11 | Scenario does not expose a Generated YAML Preview UI or API endpoint; Debug Run remains the Scenario execution-diagnostics action. |
| STP-12 | Test Plan preview supports only `runType=debug` and `runType=standard`. |
| STP-13 | Unsupported preview mode values return a stable 4xx error with code `INVALID_EXECUTION_PREVIEW_MODE`. |
| STP-14 | Preview must not create Run, Run Snapshot, RunCreationDedupKey, artifact metadata, node lease, node status transition or runner callback state. |
| STP-15 | Preview output must not expose sensitive runtime values, private infrastructure references, server absolute paths or internal temporary paths. |
| STP-16 | Preview warnings describe static build-time configuration only; they must not claim runtime result, node availability, scheduling status or monitoring state. |
| STP-17 | Tags remain a bounded string list on Scenario / Test Plan; no new tag entity, tag table or tag service is introduced. |
| STP-18 | This Slice introduces no new open-source runtime dependency. |

## 7. Architecture

```text
Clone
  -> Web calls generated clone client with x-workspace-id + CSRF
  -> API authenticates session and resolves Workspace
  -> API reads source where deleted_at is null and workspace_id matches
  -> service validates referenced business content
  -> service creates a new Scenario/Test Plan with new ID, revision=1 and current actor
  -> API returns created detail response

Archive
  -> Web asks for Archive confirmation, not Delete confirmation
  -> Web calls the generated DELETE client with x-workspace-id + CSRF
  -> API authenticates session and resolves Workspace
  -> service applies existing soft-delete protection
  -> service sets deleted_at and actor/update fields
  -> active lists no longer return the item

Preview
  -> Web opens a read-only panel for the saved Test Plan
  -> Web calls the generated Test Plan preview client for the saved Test Plan ID
  -> API reads the persisted Test Plan by Workspace and deleted_at is null
  -> service builds Taurus document through existing builders
  -> service projects generated document to safe read-only YAML text + metadata + warnings
  -> Web renders content in <pre> or read-only textarea with no apply action
```

Component boundaries:

| Component | Responsibility | Forbidden |
| --- | --- | --- |
| API routes | Expose clone, archive-through-DELETE and Test Plan preview endpoints; enforce session, CSRF for writes, `x-workspace-id`, OpenAPI schemas and stable error codes. | Adding `/archive` or Scenario Preview; returning handwritten schemas outside FastAPI/Pydantic; allowing preview to mutate run or node state. |
| Services | Copy persisted content, revalidate references, rebuild dependency refs / child rows, perform soft delete, reuse Taurus builders for Test Plan Preview. | Copying run state; cloning cross-Workspace references; starting runner work; returning sensitive runtime or internal path data. |
| Contracts | Generate client/types from OpenAPI after route/schema changes. | Hand-editing generated client/types or OpenAPI as source. |
| Web | Render Clone, Archive, tags polish and Test Plan read-only Preview using generated client/types and centralized copy. | Scenario Preview; constructing YAML in the browser; editable YAML submit; custom fetch shapes; tag service UI. |
| Database | Persist existing Scenario / Test Plan records and soft-delete fields. | New tag tables; new version graph; Run Snapshot mutation from preview. |

## 8. API Contracts

### 8.1 Scenario endpoints

| Method | Path | Operation ID | Response | Contract |
| --- | --- | --- | --- | --- |
| `POST` | `/api/v1/scenarios/{scenarioId}/clone` | `cloneScenario` | `201 ScenarioDetail` | Clone a visible Scenario in the current Workspace. Requires CSRF. |
| `DELETE` | `/api/v1/scenarios/{scenarioId}` | `deleteScenario` | `204` | Archive a Scenario through the existing DELETE transport. Requires CSRF. |

Rules:

1. `{scenarioId}` remains the path parameter name.
2. Clone and archive must attach `x-workspace-id` response header when successful.
3. `DELETE /api/v1/scenarios/{scenarioId}` remains the only archive transport; the OpenAPI summary/description and Web copy must say Archive, not permanent delete.
4. The existing `deleteScenario` operation ID may remain. P1-04 changes the product semantics and copy to Archive; it does not require an operation ID migration.
5. `/api/v1/scenarios/{scenarioId}/execution-preview` is not exposed. No `profile` or `envGroupId` preview query contract exists for Scenario.

### 8.2 Test Plan endpoints

| Method | Path | Operation ID | Response | Contract |
| --- | --- | --- | --- | --- |
| `POST` | `/api/v1/test-plans/{testPlanId}/clone` | `cloneTestPlan` | `201 TestPlanDetail` | Clone a visible Test Plan in the current Workspace. Requires CSRF. |
| `DELETE` | `/api/v1/test-plans/{testPlanId}` | `deleteTestPlan` | `204` | Archive a Test Plan through the existing DELETE transport. Requires CSRF. |
| `GET` | `/api/v1/test-plans/{testPlanId}/execution-preview?runType=debug` | `getTestPlanExecutionPreview` | `200 ExecutionPreviewResponse` | Return safe read-only debug preview for the saved Test Plan revision. |
| `GET` | `/api/v1/test-plans/{testPlanId}/execution-preview?runType=standard` | `getTestPlanExecutionPreview` | `200 ExecutionPreviewResponse` | Return safe read-only standard preview for the saved Test Plan revision. |

Rules:

1. `{testPlanId}` remains the path parameter name.
2. Clone and archive must attach `x-workspace-id` response header when successful.
3. `DELETE /api/v1/test-plans/{testPlanId}` remains the only archive transport; no `/archive` route is allowed.
4. The existing `deleteTestPlan` operation ID may remain. P1-04 changes the product semantics and copy to Archive; it does not require an operation ID migration.
5. Test Plan preview only supports `runType=debug|standard`; omitted or unsupported values fail with `INVALID_EXECUTION_PREVIEW_MODE`.
6. Standard preview may surface static high-concurrency warning metadata, but it must not require high-concurrency confirmation because it does not start a Run.

### 8.3 Clone request

`CloneRequest` is shared by Scenario and Test Plan clone endpoints.

| Field | Type | Required | Contract |
| --- | --- | --- | --- |
| `name` | `string | null` | no | Optional replacement name. Trimmed. If omitted or blank, API uses `Copy of <source name>` and validates the final name with the same length and nonblank rules as create. |

Rules:

1. Clone request must use `extra="forbid"` Pydantic behavior like existing create/patch payloads.
2. Clone does not accept `expectedRevision`; it reads the currently visible persisted source revision.
3. Clone does not accept Workspace ID in the body or path.

### 8.4 Execution preview response

`ExecutionPreviewResponse` is returned only by the Test Plan preview endpoint.

| Field | Type | Required | Contract |
| --- | --- | --- | --- |
| `sourceType` | `"test_plan"` | yes | Source kind used for preview. |
| `sourceId` | `string` | yes | Source ULID. |
| `sourceRevision` | `integer` | yes | Persisted revision used to build preview. |
| `mode` | `"debug" | "standard"` | yes | Effective Test Plan preview mode. |
| `format` | `"yaml"` | yes | Preview content format. |
| `content` | `string` | yes | Safe read-only YAML text. |
| `warnings` | `ExecutionPreviewWarning[]` | yes | Static warnings, empty when none. |

Rules:

1. Response metadata excludes Env Group variables and other runtime secret values.
2. If generated content contains variable-derived values, the safe projection rules apply before serialization. Sensitive values must be redacted rather than returned verbatim.

`ExecutionPreviewWarning`:

| Field | Type | Required | Contract |
| --- | --- | --- | --- |
| `code` | `string` | yes | Stable lower snake case warning code. |
| `message` | `string` | yes | English user-facing fallback message. |
| `field` | `string | null` | no | Optional source field path when applicable. |
| `severity` | `"info" | "warning"` | yes | Static warning severity. No `error` severity; validation failures use error responses. |

Allowed warning examples: `default_value_applied`, `optional_section_omitted`, `runtime_path_redacted`, `soft_limit_exceeded`.

Forbidden warning examples: node availability claims, pass/fail claims, schedule state claims, monitoring reachability claims.

## 9. Clone Contracts

### 9.1 Scenario clone

1. Source Scenario must be visible in the current Workspace and `deleted_at is null`; otherwise return `404 RESOURCE_NOT_FOUND`.
2. API creates a new Scenario row with a new ULID, same `workspace_id`, `scenario_type='visual'`, `revision=1`, current actor fields, and fresh timestamps.
3. API copies persisted business content: description, normalized tags, base URL expression, default settings, data sources, steps, and visual schema version.
4. API uses the clone request name when provided; otherwise the name is `Copy of <source name>` and must pass the same validation as create.
5. Scenario clone must rebuild `ScenarioDependencyFileRef` rows for the new Scenario from copied content. It must not point dependency refs at the source Scenario ID.
6. Scenario clone may preserve visual step IDs inside the cloned Scenario JSON because they are scoped to the Scenario document, not global business records.
7. Scenario clone must not copy active Run checks, Run records, Run Snapshots, dedup keys, artifacts, audit events, or `deleted_at`.
8. Source Scenario must not be mutated and its revision must not change.

### 9.2 Test Plan clone

1. Source Test Plan must be visible in the current Workspace and `deleted_at is null`; otherwise return `404 RESOURCE_NOT_FOUND`.
2. API creates a new Test Plan row with a new ULID, same `workspace_id`, `revision=1`, current actor fields, fresh timestamps, `deleted_at=null`, and `deleted_by=null`.
3. API copies persisted business content: description, normalized tags, `env_group_id`, run mode, resource config, scenario item content, and SLA rule content.
4. API uses the clone request name when provided; otherwise the name is `Copy of <source name>` and must pass the same validation as create.
5. Test Plan clone must preserve `scenario_id` references to existing same-Workspace Scenarios; it must not clone Scenario records.
6. Test Plan clone must regenerate Test Plan child row IDs for scenario items and SLA rules. It must not reuse source child row IDs as database IDs.
7. Test Plan clone must revalidate that referenced Scenarios, Env Group and Load Node are still visible and belong to the current Workspace. If a reference is no longer valid, clone fails using existing `RESOURCE_NOT_FOUND` / validation semantics.
8. Test Plan clone must not copy Runs, Run Snapshots, dedup keys, artifacts, audit events, `deleted_at` or `deleted_by`.
9. Source Test Plan must not be mutated and its revision must not change.

## 10. Archive Contracts

1. Archive uses the existing `DELETE` method and returns `204 No Content` on success.
2. OpenAPI summary/description and Web copy must use Archive / Archived wording. User-facing copy must not say permanent delete.
3. Archive writes only soft-delete state: Scenario sets `deleted_at`, `updated_by_user_id`, `updated_at`; Test Plan sets `deleted_at`, `deleted_by`, `updated_by`, `updated_at`.
4. Active list endpoints must exclude archived records through `deleted_at is null` filters.
5. Detail and clone endpoints must treat archived records as not visible and return `404 RESOURCE_NOT_FOUND`; Test Plan Preview applies the same rule to archived Test Plans.
6. Scenario archive must keep existing protection against active debug runs and visible Test Plan references. A Scenario referenced by a visible Test Plan must not be archived.
7. Test Plan archive must keep existing protection against active runs sourced from that Test Plan.
8. Archive does not change Run Snapshot, Run Report, artifact metadata, historical validity, or saved source snapshots.
9. Archive is not a governance log or recycle bin in P1-04. Restore, archived list and permanent-delete controls are explicitly not implemented.

## 11. Execution Preview Contracts

### 11.1 Shared rules

1. Preview is a read-only diagnostic view built from persisted source state at the current source revision.
2. Preview must use API services and existing Taurus document builders. Web must not construct YAML.
3. Preview must not mutate database state except normal read-only request tracing. It must not create a Run, Run Snapshot, RunCreationDedupKey, node lease, artifact metadata or audit event for execution.
4. Preview must not contact execution, storage-write, monitoring or scheduler services.
5. Preview must not require selected node to be idle, because no node lease is acquired.
6. Preview may validate saved references and explicitly supplied preview inputs required for building the static document. Missing or cross-Workspace references use existing `RESOURCE_NOT_FOUND`, `TEST_PLAN_NOT_RUNNABLE` or `VALIDATION_ERROR` semantics.
7. Preview content is a safe projection of generated execution YAML. Runtime-only or sensitive fields must be removed, redacted or replaced before returning `content`.
8. Preview is not a byte-for-byte runtime artifact contract when fields are redacted; the runtime bundle generated during an actual Run remains authoritative for execution.
9. Preview may return safe relative bundle paths already part of the Taurus document, if they are not internal storage keys or server absolute paths.
10. Preview failures must be stable API errors, not partial YAML with hidden errors.

### 11.2 Scenario boundary

1. Scenario does not expose a Generated YAML Preview panel or execution-preview endpoint.
2. Scenario Debug Run continues to use the existing validation, optional Env Group input, Taurus generation, Run creation, and execution path.
3. Test Plan Preview may naturally include saved Scenario content through Test Plan Scenario references; this does not create a Scenario Preview contract.

### 11.3 Test Plan preview

1. Test Plan preview supports exactly `runType=debug|standard`.
2. Test Plan preview reads a visible Test Plan from the current Workspace and uses its current `revision` as `sourceRevision`.
3. `runType=debug` uses Debug Run semantics for execution settings and does not evaluate SLA pass/fail rules.
4. `runType=standard` uses saved Test Plan run mode, load settings, Env Group, selected Load Node reference and enabled SLA rules.
5. Standard preview must not require the high-concurrency confirmation flag because no Run is started. If saved concurrency exceeds the soft limit, preview returns a static warning.
6. Test Plan preview must validate Scenario, Env Group and Load Node references enough to build the static document, but must not claim the selected node is idle or reserve it.
7. Test Plan preview response has `sourceType="test_plan"`, `mode` equal to the requested run type, and `format="yaml"`.

## 12. Tags Polish Contracts

1. Scenario / Test Plan tags remain `list[str]` on existing create, patch, detail, summary and list schemas.
2. Tags must continue to be trimmed, deduplicated in input order, bounded to at most 10 entries, and each tag must be 1..32 characters after trim.
3. API errors for invalid tags use existing validation shape with field paths such as `tags[0]`.
4. Web forms should accept comma-separated text, trim values, drop empty segments before submit, and surface API validation errors with human-readable copy.
5. Web lists and detail pages should render tags as lightweight chips. Empty tags should render an explicit empty state such as `No tags`, not a blank layout gap.
6. P1-04 must not add a tag filter UI. Existing API tag query behavior may remain but must not be expanded into a new product surface in this Slice.
7. P1-04 must not introduce global tag colors, tag ownership, tag rename, tag delete, tag search/autocomplete service or tag analytics.

## 13. Web UX Contracts

1. List rows for Scenario and Test Plan must expose Clone and Archive actions using generated client calls.
2. Archive confirmation copy must state that the item will be hidden from active lists and that historical Run Reports keep saved snapshots.
3. Error copy for `RESOURCE_IN_USE` must explain that the item cannot be archived while it is referenced by active execution state or visible dependent resources.
4. Clone success should navigate to the cloned detail/editor route.
5. Preview panel belongs only on the saved Test Plan editor page: `apps/web/src/features/test-plans/pages/test-plan-editor-page.tsx`.
6. Scenario Designer must not render Generated YAML Preview, Preview environment, or Preview YAML controls.
7. Test Plan Preview must be disabled or clearly stale while local edits are unsaved. Users must save before previewing the latest changes.
8. Preview rendering must use `<pre>` or a read-only textarea. No heavy code editor dependency is introduced.
9. Web must not show buttons or copy such as `Apply YAML`, `Save YAML`, `Import YAML`, `Edit generated YAML`, or `Run from preview`.
10. Web copy remains English and centralized in feature copy files.
11. Web must invalidate relevant list/detail queries after clone or archive.

## 14. Error Handling Contracts

| Case | Status | Code | Contract |
| --- | --- | --- | --- |
| Invalid source ID shape | `422` | `VALIDATION_ERROR` | Use existing ULID validation detail shape. |
| Source missing, cross-Workspace or archived | `404` | `RESOURCE_NOT_FOUND` | Do not reveal whether a resource exists in another Workspace or archived state. |
| Clone request name invalid | `422` | `VALIDATION_ERROR` | Same name constraints as create. |
| Clone reference no longer valid | `404` or `422` | existing code | Reuse current create/patch reference validation semantics. |
| Archive blocked by active run or visible dependency | `409` | `RESOURCE_IN_USE` | Web copy says cannot archive while in use. |
| Unsupported Test Plan preview run type | `400` | `INVALID_EXECUTION_PREVIEW_MODE` | Details field is `runType`. |
| Preview source not runnable/buildable | `409` or `422` | existing code | Reuse builder/run-context validation families; do not return partial YAML. |

Rules:

1. API error messages remain English fallback strings.
2. Web may localize by code later, but P1-04 only centralizes English copy.
3. Preview-specific unsupported mode must not reuse a generic unknown query error if the mode parameter is present but unsupported.

## 15. Security and Privacy Constraints

1. Clone / Archive and Test Plan Preview must all enforce session authentication and Workspace filtering.
2. Clone and Archive are writes and must enforce CSRF.
3. Test Plan Preview is a read, but still requires authenticated current Workspace context.
4. API must not trust Web-hidden actions for authorization. If a user can call the route manually, backend must still enforce all checks.
5. Scenario does not accept a preview-only `envGroupId`; its existing Debug Run Env Group input remains governed by the Debug Run contract.
6. Test Plan Preview must use an explicit safe projection for sensitive/runtime-only fields before serializing YAML to `content`.
7. Tests must assert preview response `content` and metadata do not include sensitive runtime markers, private infrastructure references, raw Env Group sensitive values, or server absolute paths that identify internal runtime locations.
8. No new P1-04 endpoint may return private infrastructure access material, internal object identifiers, or internal storage locations.
9. Clone must not copy deleted/archived state. The cloned object is active unless creation fails.

## 16. Implementation Sequence

1. Add `P1-04` SDD and mark it active in `docs/sdd/slices/P1-README.md`.
2. Add API schemas: `CloneRequest`, `ExecutionPreviewResponse`, `ExecutionPreviewWarning`, and Test Plan preview mode validation.
3. Add route contracts and OpenAPI descriptions for clone, archive-through-DELETE and Test Plan Preview; do not expose Scenario Preview.
4. Implement Scenario clone service and tests.
5. Implement Test Plan clone service and tests.
6. Implement safe execution preview service by reusing existing builders and redacting runtime-only fields.
7. Run `make generate-contracts`.
8. Update Web generated-client consumers, copy, list actions, Test Plan detail Preview panel and tag polish.
9. Add Web component tests and API/contract tests.
10. Run `make verify`.

## 17. Test and Acceptance Criteria

API tests must cover:

1. Scenario clone creates a new ID, `revision=1`, same Workspace, current actor fields, copied content, rebuilt dependency refs and no copied run state.
2. Test Plan clone creates a new ID, `revision=1`, same Workspace, current actor fields, regenerated child IDs, preserved same-Workspace Scenario references and no copied run state.
3. Clone rejects missing, cross-Workspace or archived sources as `404 RESOURCE_NOT_FOUND`.
4. Scenario archive uses `DELETE`, returns `204`, sets soft-delete fields and excludes the Scenario from active list/detail/clone.
5. Test Plan archive uses `DELETE`, returns `204`, sets soft-delete fields and excludes the Test Plan from active list/detail/clone/preview.
6. Archive blocks active runs and visible dependent references with `409 RESOURCE_IN_USE` where existing protection applies.
7. Scenario execution-preview route is absent and requests return `404`.
8. Test Plan Preview accepts `runType=debug|standard`, returns `sourceRevision`, `format="yaml"`, safe `content`, and static `warnings`.
9. Invalid Test Plan Preview modes return `INVALID_EXECUTION_PREVIEW_MODE` with stable status and field details.
10. Test Plan Preview does not create Runs, Run Snapshots, dedup keys, node leases or artifacts.
11. Test Plan Preview does not leak sensitive runtime values, private infrastructure references, Env Group sensitive values or server absolute paths.
12. Tags are trimmed, deduplicated, bounded and surfaced in summary/detail responses.

Contract tests must cover:

1. OpenAPI includes clone endpoints and the Test Plan Preview endpoint with generated schemas, and excludes Scenario Preview.
2. OpenAPI descriptions for existing `DELETE` routes use Archive semantics.
3. Generated Web client/types include clone, existing DELETE archive behavior, and Test Plan Preview only.
4. Generated contracts are fresh after `make generate-contracts`.

Web tests must cover:

1. Scenario and Test Plan list rows expose Clone and Archive actions.
2. Archive confirmation copy says Archive and hidden from active lists; it does not say permanent delete.
3. Clone success navigates to the cloned detail/editor page.
4. Scenario Designer has no Generated YAML Preview controls and makes no preview request.
5. Test Plan Preview panel renders read-only YAML from API content and displays warnings.
6. Preview panel has no editable apply/save/import YAML path.
7. Unsaved local edits require save before previewing current generated YAML.
8. Tags render chips and empty state consistently for Scenario and Test Plan.
9. No tag filter UI or global tag management UI is introduced.

Done When:

1. `docs/sdd/slices/P1-04-scenario-testplan-polish.md` is active and linked from `P1-README.md`.
2. API clone, archive semantics and preview contracts are implemented and tested.
3. Web uses generated client/types only and exposes Clone, Archive, Test Plan read-only Preview and tags polish.
4. `make generate-contracts` passes and generated contract changes are committed.
5. `make verify` passes.
6. Review confirms no API Catalog/OpenAPI generation chain, editable YAML, schedule, monitoring, multi-node, tag service or P2 security scope entered P1-04.

---

## 18. Implementation Backfill

Implementation status: completed in branch `feature/p1-04-scenario-testplan-polish`.

Engineering facts:

1. API exposes clone endpoints for Scenario and Test Plan, keeps Archive on the existing `DELETE` transport, and exposes the read-only Test Plan execution preview using generated OpenAPI contracts. `ADR-0023` removes Scenario Preview.
2. Test Plan Preview uses existing Taurus document builders and returns a safe projected YAML string with runtime path and variable-derived value redaction warnings when applicable.
3. Web consumes generated `@surgepilot/contracts` client types through `apps/web/src/app/api-client.ts`, adds Clone / Archive list actions and tag empty states, and keeps the read-only Generated YAML Preview panel only on the saved Test Plan editor page.
4. No restore, archived list, permanent-delete UI, editable YAML, Run-from-preview action, tag filter/service, API Catalog/OpenAPI generation chain, schedule, monitoring, or multi-node execution surface was added in this Slice.

Verification added or extended:

1. `apps/api/tests/test_p1_04_scenario_testplan_polish_api.py` covers clone, archive visibility, Scenario Preview absence, Test Plan Preview safety, invalid Test Plan Preview modes, and non-mutating Preview behavior.
2. `tests/contract/test_p1_04_scenario_testplan_polish_openapi.py` covers OpenAPI paths, Scenario Preview absence, generated schemas/client text, Archive descriptions, and the stable Test Plan Preview error code.
3. `apps/web/src/features/scenarios/scenarios.test.tsx` and `apps/web/src/features/test-plans.test.tsx` cover Clone / Archive actions, no-tags states, Scenario Preview absence, Test Plan read-only Preview behavior, warnings, and forbidden YAML actions.
4. `tests/e2e/p1_04_scenario_testplan_polish.spec.ts` provides a lightweight browser smoke for P1-04 user surfaces.

Remaining risks: None known after repository verification.
