# P0-08: Overview and Polish

- Documentation status: Draft v1
- Project: SurgePilot performance load testing platform
- Document location: `docs/sdd/slices/P0-08-overview-and-polish.md`
- Product source: `docs/prd/PRD.md`
- Range constraint: `docs/sdd/00-product-scope-and-priority.md`
- Front-end rule source: `docs/sdd/08-frontend-routing-and-ui-rules.md`
- Test source: `docs/sdd/09-testing-and-acceptance-strategy.md`
- Security and Workspace Source: `docs/sdd/06-security-permission-workspace.md`
- Current delivery target: P0 only
- Scope of application: Overview, P0 final polish, P0 UX status closing, P0 final acceptance, AI Coding, code review

---

## 1. Goal

P0-08 delivers the Overview page of SurgePilot P0 and the P0 product closure.

This Slice must allow users to quickly understand the execution activities of the current Workspace, P0 result statistics, visible Load Node resource status, and enter the P0 core operation entrance through `/overview` after logging in.

This Slice also closes the P0 page consistency: global navigation, empty state, error state, Loading, anti-re-submission, permission entry and P1/P2 entry leakage check.

P0-08 is not a visual redo, report analysis system, monitoring page or trend analysis stage.

---

## 2. PRD Trace

| PRD area | P0-08 coverage |
| --- | --- |
| Overview | `/overview` Basic overview, recent execution, execution status statistics, resource status summary, quick entry |
| Run statistics | Default statistics only include Valid Standard Run; Debug / Invalid do not enter the default result statistics |
| Resources | Displays the status summary of the Load Node visible to the current user |
| UX | The P0 page has basic empty status, error status, loading, and anti-repetitive submission |
| Scope boundary | Monitoring, Grafana, Schedule, API Catalog, and complex trend analysis are not displayed |

---

## 3. Document Responsibility

### 3.1 This Slice Owns

P0-08 owns:

1. Overview page information structure and display caliber;
2. `GET /api/v1/overview` read-only aggregation API contract;
3. Overview statistical performance boundaries;
4. Cross-page acceptance rules for P0 final polish;
5. P0 navigation finally visible entrance rules;
6. P0 final acceptance checklist.

### 3.2 Foundation SDDs Remain Authoritative For

| Area | Authoritative document |
| --- | --- |
| P0/P1/P2 scope | `docs/sdd/00-product-scope-and-priority.md` |
| Frontend routing, UI stack, query ownership | `docs/sdd/08-frontend-routing-and-ui-rules.md` |
| Testing gates and coverage | `docs/sdd/09-testing-and-acceptance-strategy.md` |
| Auth, Workspace and permission | `docs/sdd/06-security-permission-workspace.md` |
| API contract rules and error shape | `docs/sdd/04-api-contract-guidelines.md` |
| Run state machine and Runner callbacks | `docs/sdd/05-runner-protocol-and-run-state-machine.md` |
| Artifact metadata and path safety | `docs/sdd/07-storage-artifacts-minio.md` |

### 3.3 Prior Slice Dependencies

P0-08 consumes completed P0 Slice contracts only:

1. P0-00 current user and default Workspace context;
2. P0-03 Load Node visibility and status;
3. P0-04 Run state, terminal state, node lease and Stop semantics;
4. P0-05 Debug Run `runType='debug'`;
5. P0-06 Standard Run `runType='standard'`;
6. P0-07 Run List fields, `validity`, `slaResult`, terminal timestamps and artifact summary.

P0-08 must not use P1/P2 Slice documents as implementation input.

---

## 4. In Scope

### 4.1 Backend API

P0-08 implements or finalizes:

| Endpoint | Method | Auth | CSRF | Purpose |
| --- | --- | --- | --- | --- |
| `/api/v1/overview` | `GET` | Required | No | Current Workspace Overview summary |

Backend responsibilities:

1. enforce current user session;
2. resolve current Workspace with the P0 `x-workspace-id` fallback rule;
3. aggregate only current Workspace business data plus user-visible Public Load Nodes;
4. apply the Overview statistics scope defined in this document;
5. return bounded recent Run and resource summaries;
6. never read artifact object content for Overview;
7. never return Load Node credentials, MinIO object keys, session tokens, CSRF tokens or secrets.

### 4.2 Data

P0-08 may add only:

1. indexes needed for the Overview API query plan;
2. no new business table by default.

Required index direction for implementation:

1. Result statistics must be covered by an existing or new index equivalent to:

   ```text
   (workspace_id, run_type, validity, state, created_at desc)
   ```

2. Recent Runs must be covered by an existing or new index equivalent to:

   ```text
   (workspace_id, created_at desc, id desc)
   ```

3. Resource Summary must use existing Load Node visibility/status indexes or add an equivalent index over the fields used by visible-node filtering and `status`.
4. Implementation may use a differently ordered composite or partial index only when tests or query-plan review show it satisfies the same bounded-query goal.

P0-08 must not add a cache service, external queue, Redis, materialized metrics subsystem or monitoring datastore.

If a candidate Overview metric cannot be answered through bounded indexed SQL or existing persisted summary rows, P0-08 must not display it. A later Slice may add a persisted database summary only after the metric is explicitly accepted into scope.

### 4.3 Frontend

P0-08 implements or finalizes:

1. `/overview` page with AppLayout;
2. Run Summary section;
3. Recent Runs section;
4. Resource Summary section;
5. Quick Actions section;
6. read-only Default Workspace context display;
7. Overview loading / empty / error / refetch states;
8. Admin navigation visibility for Setup Status;
9. final no-P1/P2-navigation check.

### 4.4 P0 Polish

P0-08 final polish covers only P0 readiness and consistency:

1. list pages expose loading, empty, error and loaded states;
2. forms and destructive actions use pending state and prevent duplicate submission;
3. user-visible errors map stable API error codes and may show request ID;
4. unauthorized Admin UI is not exposed to non-Admin users;
5. P1/P2 clickable entries are absent;
6. UI copy remains English only and centralized according to frontend rules;
7. source-owned UI primitives are reused or minimally extended only when required.

---

## 5. Out of Scope

P0-08 must not implement:

1. API Catalog card, route, upload or import;
2. Monitoring page, Grafana iframe, Grafana link or InfluxDB data path;
3. Schedule Run, Scheduled Job or Upcoming Scheduled Jobs statistics;
4. trend charts, historical regression analysis or capacity baseline;
5. failed requests preview or large CSV pagination;
6. Generated YAML preview;
7. Workspace switcher or Workspace management UI;
8. User Management UI;
9. System Settings UI;
10. Help page, unless a separate P0 Help Slice explicitly exists;
11. new broad UI component library;
12. Redis, Celery, RabbitMQ, Kafka, external queue service or metrics cache;
13. cross-Workspace statistics;
14. artifact-content parsing during Overview request handling.

---

## 6. Confirmed Decisions

| Area | Decision |
| --- | --- |
| Slice type | Overview + P0 final polish |
| Overview API | Add `GET /api/v1/overview` as a lightweight read-only aggregate |
| API source of truth | FastAPI routes and Pydantic schemas remain the OpenAPI source of truth |
| Stats authority | Backend owns Overview statistics scope and filtering |
| Default stats scope | Valid Standard terminal Runs created within the default Overview window |
| Default Overview window | 30 days, exposed in response and UI copy |
| Debug Runs | May appear in Recent Runs, never in default result statistics |
| Invalid Runs | May appear in Recent Runs, never in default result statistics |
| Active Runs | May be shown as activity, separate from result statistics |
| Recent Runs | Default `5`, max `10` |
| Resource summary | Counts current-user-visible Load Nodes only |
| Expensive metrics | Omit in P0 unless backed by persisted DB summary and accepted Slice scope |
| Charts | Not implemented in P0 |
| P0 Help page | Not implemented in P0 |
| Admin navigation | Admin users may see Admin -> Setup Status only |
| Mobile UX | Desktop-first internal tool; narrow screens must remain readable but no full mobile navigation drawer is required |
| UI libraries | No new third-party UI or notification library in P0-08 |

---

## 7. Overview Statistics Contract

### 7.1 Result Statistics Scope

Default result statistics include only Runs matching all conditions:

```text
workspaceId = current workspace
runType = standard
validity = valid
state in finished / failed / aborted
createdAt >= overviewWindowStart
```

Rules:

1. `debug` Runs are excluded from default result statistics.
2. `invalid` Runs are excluded from default result statistics.
3. `initializing`, `running` and `stopping` Runs are excluded from result statistics.
4. P0 result statistics use Run fields and persisted report summary metadata only.
5. Result statistics must treat `state`, `validity` and `slaResult` as independent fields.
6. `slaResult='failed'` is not the same as `state='failed'` and must not be conflated in copy or UI logic.

### 7.2 Active Run Activity Scope

Active Run activity may count Runs matching:

```text
workspaceId = current workspace
state in initializing / running / stopping
createdAt >= overviewWindowStart
```

Rules:

1. Active activity may include `debug` and `standard` Runs.
2. Active activity is displayed separately from result statistics.
3. Active activity must not be used to compute pass rate, failure rate or SLA result counts.

### 7.3 Recent Runs Scope

Recent Runs shows bounded execution activity:

```text
workspaceId = current workspace
sort = -createdAt
limit <= 10
```

Rules:

1. Recent Runs may include Debug, Standard, Valid and Invalid Runs.
2. Recent Runs must show badges or labels for `runType`, `state`, `validity` and `slaResult` when available.
3. Recent Runs must link only to `/runs/:runId`.
4. Recent Runs must not link to Monitoring, Grafana, Schedule or Generated YAML.

### 7.4 Resource Summary Scope

Resource Summary counts current-user-visible Load Nodes:

1. Workspace Private Load Nodes in the current Workspace;
2. Public Load Nodes visible under P0 Load Node visibility rules;
3. archived nodes are excluded by default;
4. credentials are never returned.

Status buckets:

```text
uninitialized
initializing
idle
busy
offline
quarantined
disabled
```

Rules:

1. Resource Summary is an operational status summary, not a resource allocation planner.
2. P0-08 must not add Auto allocation, multi-node execution, Node Count or Selected Nodes UI.
3. If a status value is unknown to the frontend, it must be displayed as a safe unknown badge, not hidden silently.

---

## 8. Overview Performance Contract

Overview must remain fast enough to be used as the authenticated landing page.

Rules:

1. `GET /api/v1/overview` must be a lightweight read-only endpoint.
2. The endpoint must use bounded, indexed SQL queries or already persisted summary rows.
3. The endpoint must not read, download, parse or inspect MinIO objects.
4. The endpoint must not parse `final_stats_csv`, `bzt.log`, `artifacts_zip` or failed request files.
5. The endpoint must not perform unbounded historical scans for metrics.
6. The endpoint must not compute trend series, percentiles from raw artifact content or cross-Run artifact-derived aggregates.
7. The Recent Runs response limit default is `5`; the maximum allowed value is `10`.
8. The default statistics window is `30` days and must be visible to users.
9. If an Overview metric cannot be served within the lightweight query boundary, the metric must be omitted or returned as unavailable instead of slowing page refresh.
10. P0-08 must not introduce Redis, external cache, background metrics queue or a separate analytics datastore.
11. If a later Slice needs expensive Overview data, it must first persist a bounded database summary and update the relevant SDD or ADR.

Recommended local/dev performance target:

```text
GET /api/v1/overview p95 < 300ms for small-list development datasets
```

This target is a lightweight smoke target, not a formal platform performance benchmark.

---

## 9. API Contract

### 9.1 Shared Schemas

#### `OverviewResultRunScope`

P0 value:

```text
valid_standard_terminal_runs
```

Rules:

1. `OverviewResultRunScope` is a closed Literal / enum in the API schema, not free text.
2. P0 exposes only `valid_standard_terminal_runs`.
3. Future values require a later Slice to update this contract and generated clients.

#### `OverviewResponse`

```json
{
  "generatedAt": "2030-06-07T10:30:00Z",
  "workspace": {
    "id": "01HY...",
    "name": "Default Workspace"
  },
  "statsScope": {
    "windowDays": 30,
    "windowStartedAt": "2030-05-08T00:00:00Z",
    "resultRunScope": "valid_standard_terminal_runs",
    "recentRunLimit": 5
  },
  "runStats": {
    "resultRuns": {
      "total": 12,
      "byState": {
        "finished": 10,
        "failed": 1,
        "aborted": 1
      },
      "bySlaResult": {
        "passed": 8,
        "failed": 2,
        "notEvaluated": 2
      }
    },
    "activeRuns": {
      "total": 1,
      "initializing": 0,
      "running": 1,
      "stopping": 0
    }
  },
  "recentRuns": [
    {
      "id": "01HY...",
      "runType": "standard",
      "sourceType": "test_plan",
      "sourceName": "Checkout smoke test",
      "state": "finished",
      "validity": "valid",
      "slaResult": "passed",
      "createdAt": "2030-06-07T10:00:00Z",
      "startedAt": "2030-06-07T10:01:00Z",
      "endedAt": "2030-06-07T10:05:00Z",
      "durationMs": 240000,
      "artifactCount": 3,
      "hasArtifactsZip": true
    }
  ],
  "resourceSummary": {
    "totalVisibleNodes": 3,
    "byStatus": {
      "uninitialized": 0,
      "initializing": 0,
      "idle": 2,
      "busy": 1,
      "offline": 0,
      "quarantined": 0,
      "disabled": 0
    }
  }
}
```

Schema rules:

1. All JSON fields use camelCase.
2. Time fields are UTC ISO 8601 strings with `Z`.
3. `statsScope.resultRunScope` must use the `OverviewResultRunScope` Literal / enum and must be `valid_standard_terminal_runs` in P0.
4. `statsScope.windowDays` must be `30` unless a later SDD explicitly changes the P0 default.
5. `recentRuns` maximum length is `10`; default response length is `5`.
6. `recentRuns` may reuse the public Run List item schema if the generated OpenAPI type remains clear and stable.
7. `resourceSummary.byStatus` must include all P0 Load Node status keys with integer counts.
8. Unknown enum values must not be invented for P0 Overview.
9. The API must not return secrets, object keys, credential fingerprints, SSH private keys, passwords or raw failure logs.

### 9.2 `GET /api/v1/overview`

Request:

```http
GET /api/v1/overview
x-workspace-id: 01HY...
```

Query parameters:

| Name | Type | Required | Rule |
| --- | --- | --- | --- |
| `recentLimit` | integer | No | Default `5`; min `1`; max `10` |

Response:

| Status | Body | Rule |
| --- | --- | --- |
| `200` | `OverviewResponse` | Overview summary for current Workspace |
| `400` | `ErrorResponse` | Workspace cannot be resolved |
| `401` | `ErrorResponse` | Missing or invalid session |
| `403` | `ErrorResponse` | User is not a member of the resolved Workspace |
| `422` | `ErrorResponse` | Invalid query parameter |

Rules:

1. Missing `x-workspace-id` follows the P0 default Workspace fallback rule.
2. Response must set `x-workspace-id` to the resolved Workspace ID.
3. The endpoint is read-only and does not require CSRF.
4. Backend must enforce Workspace filtering before aggregation.
5. Backend must apply Load Node visibility rules before resource aggregation.
6. Backend must not expose internal Runner endpoints or internal callback schemas in the Web generated client.
7. OpenAPI operation ID should be `getOverview`.

### 9.3 Error Code Registry Additions

P0-08 should prefer existing core errors:

| Code | Usage |
| --- | --- |
| `WORKSPACE_REQUIRED` | No default Workspace can be resolved |
| `UNAUTHORIZED` | Missing or invalid session |
| `FORBIDDEN` | User cannot access the resolved Workspace |
| `VALIDATION_ERROR` | Invalid `recentLimit` or other query parameter |

P0-08 should not add metric-specific error codes unless implementation exposes an actionable user-facing failure.

---

## 10. Frontend Contract

### 10.1 Route and Navigation

| Page | Route | Layout | Rule |
| --- | --- | --- | --- |
| Overview | `/overview` | AppLayout | Auth required |

Navigation rules:

1. `/` redirects to `/overview` for authenticated users.
2. `/overview` remains the login and register success target.
3. Global navigation includes Overview, Scenarios, Test Plans, Runs, Assets, Resources.
4. Admin users may see Admin navigation linking only to `/admin/setup-status`.
5. Non-Admin users must not see Admin navigation.
6. Backend permission checks remain required even when frontend hides Admin navigation.
7. Help is not linked in P0 unless a real P0 Help page exists.
8. No P1/P2 navigation entry may be clickable in P0.

### 10.2 Overview Layout

Overview sections must appear in this order:

1. page header with Default Workspace context and statistics window;
2. Run Summary;
3. Recent Runs;
4. Resource Summary;
5. Quick Actions.

Rules:

1. The page title is `Overview`.
2. The statistics window must be visible, for example `Last 30 days`.
3. Result statistics copy must clearly indicate Valid Standard Runs.
4. Active Run activity must be visually separate from result statistics.
5. Recent Runs must show `runType`, `state`, `validity` and `slaResult` where available.
6. Empty Overview still shows Quick Actions.
7. No card may mention Monitoring, Grafana, Schedule, API Catalog or Upcoming Scheduled Jobs in P0.

### 10.3 Run Summary UX

Run Summary shows:

1. total Valid Standard terminal Runs in the Overview window;
2. terminal state counts;
3. SLA result counts;
4. active Run count as separate activity.

Rules:

1. UI must not label `state='finished'` as `Passed`.
2. UI must not label `slaResult='failed'` as process failure.
3. `notEvaluated` must be displayed as a neutral state.
4. Zero values must display as `0`, not as missing data.
5. Missing or unavailable metric values must show a clear unavailable state.

### 10.4 Recent Runs UX

Recent Runs shows at most 5 Runs by default.

Rules:

1. Each row links to `/runs/:runId`.
2. Debug and Invalid Runs must be visibly labeled when present.
3. Artifact availability may be shown only as a count or ZIP availability flag.
4. Artifact download remains on Run Report, not on Overview.
5. If no Runs exist, show an empty state that guides the user to create or run a Test Plan.
6. Empty state must not suggest API Catalog import or Schedule Run in P0.

### 10.5 Resource Summary UX

Resource Summary shows:

1. total visible Load Nodes;
2. Idle count;
3. Busy count;
4. Offline count;
5. Uninitialized / initializing / quarantined / disabled counts when non-zero or useful.

Rules:

1. Resource Summary links only to `/resources/load-nodes`.
2. It must not expose Private Load Node credentials, credential fingerprints or generated keys.
3. It must not offer Auto allocation, multi-node execution or node count configuration.
4. If there are no visible nodes, guide the user to Register Load Node.

### 10.6 Quick Actions

P0 Quick Actions:

| Action | Route | Rule |
| --- | --- | --- |
| Create Scenario | `/scenarios` or create action in Scenario List | P0 only |
| Create Test Plan | `/test-plans` or create action in Test Plan List | P0 only |
| View Runs | `/runs` | P0 only |
| Manage Load Nodes | `/resources/load-nodes` | P0 only |

Rules:

1. API Catalog is not a Quick Action in P0.
2. Schedule Run is not a Quick Action in P0.
3. Monitoring is not a Quick Action in P0.
4. Help is not a Quick Action in P0 unless separately implemented in P0.

### 10.7 Loading, Empty and Error States

Rules:

1. Overview uses TanStack Query for business data fetching.
2. Overview does not use React Router loader for normal business data.
3. Initial load shows LoadingSkeleton or clear loading text.
4. Refetching preserves existing content and shows a lightweight refresh state.
5. API error state explains what failed and what to do next.
6. Error state may show request ID.
7. Error state must not expose stack traces, SQL, tokens, object keys, server paths or raw exception text.
8. Empty states must remain actionable and P0-scoped.

### 10.8 Responsive and Accessibility Rules

P0-08 is desktop-first.

Rules:

1. Common laptop and desktop widths must not horizontally overflow.
2. Narrow screens must keep core content readable.
3. A full mobile navigation drawer is not required in P0.
4. Buttons and links must be keyboard reachable.
5. Form controls must retain labels.
6. Loading states must not trap keyboard focus.
7. Heading hierarchy should remain semantic and stable.

---

## 11. Security, Permission and Workspace Rules

### 11.1 Authentication and CSRF

Rules:

1. `GET /api/v1/overview` requires an authenticated session.
2. `GET /api/v1/overview` is read-only and does not require CSRF.
3. Overview write actions are only links to existing P0 routes; they do not create resources directly.

### 11.2 Workspace Enforcement

Rules:

1. Overview Run statistics and Recent Runs must be filtered by current Workspace.
2. Missing `x-workspace-id` uses the P0 default Workspace fallback rule.
3. Cross-Workspace Run data must not contribute to any Overview count.
4. Cross-Workspace Run data must not appear in Recent Runs.
5. Response must include the resolved `x-workspace-id` header.

### 11.3 Permission Enforcement

Rules:

1. Frontend may hide Admin navigation from non-Admin users.
2. Backend permission checks remain authoritative.
3. Non-Admin users must not be able to access Admin Setup Status through frontend-only checks.
4. Overview must not add new role or resource-level permission models.

### 11.4 Sensitive Data

Overview API and UI must not expose:

1. session cookie values;
2. CSRF tokens;
3. password hashes;
4. Private Load Node SSH passwords or private keys;
5. generated key private material;
6. credential fingerprints unless already exposed by Load Node detail contracts and explicitly needed;
7. MinIO object keys;
8. runner tokens;
9. raw logs or raw artifact contents.

### 11.5 Audit Events

P0-08 Overview read access does not require audit events.

Rules:

1. Overview must not create audit noise for normal page refresh.
2. Existing audit events from Stop, Run creation, validity change and Load Node operations remain owned by their respective Slices.

---

## 12. Contract Rules

Rules:

1. FastAPI and Pydantic schemas are the source of truth for `GET /api/v1/overview`.
2. `packages/contracts/openapi/api.openapi.json` must be generated, not handwritten.
3. Web must consume generated types through `@surgepilot/contracts`.
4. Web must not invent the Overview response shape outside OpenAPI.
5. `make generate-contracts` must be run after API schema changes.
6. Internal runner endpoints must not enter the Web generated client.
7. API fields use camelCase; database columns use snake_case.

---

## 13. Cross-Slice Handoff Contracts

### 13.1 P0-03 Load Nodes

P0-08 consumes Load Node visibility and status only.

Rules:

1. P0-08 must not change Load Node credential behavior.
2. P0-08 must not change initialization, disable, enable or archive semantics.
3. P0-08 may require indexes only if Overview queries need them.

### 13.2 P0-07 Run Reports

P0-08 consumes Run List fields, validity, SLA result, terminal timestamps and artifact summary.

Rules:

1. P0-08 must treat `state`, `validity` and `slaResult` independently.
2. P0-08 must exclude Invalid Runs from default result statistics.
3. P0-08 must not add Monitoring or Grafana report links.
4. P0-08 must not read raw artifact content.

### 13.3 Later P1/P2 Slices

Later Slices may add:

1. API Catalog quick action;
2. Monitoring / Grafana card;
3. Schedule / Upcoming Scheduled Jobs card;
4. trend charts or persisted analytics summaries;
5. Help page.

Rules:

1. These entries remain non-clickable and absent from P0 implementation.
2. Adding them requires the later Slice to update navigation, API, tests and scope documents.

---

## 14. Tests

### 14.1 API Unit Tests

Required coverage:

1. result statistics include only Valid Standard terminal Runs;
2. Debug Runs are excluded from result statistics;
3. Invalid Runs are excluded from result statistics;
4. active Run counts are separate from result statistics;
5. SLA result counts do not conflate with Run state counts;
6. Overview window filters by `createdAt` using the configured 30-day window;
7. resource status summary counts only visible nodes;
8. Overview service does not call artifact storage readers or final stats parsers.

### 14.2 API Integration Tests

Required coverage:

1. `GET /api/v1/overview` requires authentication;
2. missing `x-workspace-id` resolves to default Workspace;
3. response sets `x-workspace-id`;
4. cross-Workspace Runs are excluded from all Run counts and Recent Runs;
5. cross-Workspace Private Load Nodes are excluded from resource counts;
6. user-visible Public Load Nodes are included according to P0 visibility rules;
7. `recentLimit` defaults to `5`;
8. `recentLimit` rejects values above `10`;
9. no sensitive fields are returned;
10. endpoint does not mutate database state.

### 14.3 Contract Tests

Required coverage:

1. OpenAPI includes `GET /api/v1/overview` with operation ID `getOverview`;
2. generated Web client/types include `OverviewResponse` or equivalent schema;
3. Overview public schemas use camelCase;
4. `statsScope.resultRunScope` is generated as a closed Literal / enum, not an unconstrained free-text string;
5. internal runner endpoints remain absent from Web generated client;
6. generated contracts are fresh after `make generate-contracts`.

### 14.4 Web Tests

Required coverage:

1. `/overview` renders page title and Default Workspace context;
2. Run Summary displays the `Last 30 days` scope;
3. Valid Standard statistics are labeled clearly;
4. Debug / Invalid recent Runs render visible badges;
5. zero-value statistics render as `0`;
6. missing or unavailable values render safe unavailable copy;
7. Recent Runs empty state links to P0 Run / Test Plan flow only;
8. Resource Summary empty state links to Register Load Node;
9. Quick Actions exclude API Catalog, Schedule, Monitoring and Help;
10. non-Admin user does not see Admin navigation;
11. Admin user sees only Setup Status under Admin;
12. no P1/P2 clickable entries appear in P0 navigation or Overview.

### 14.5 P0 Polish Tests

Required coverage across touched pages:

1. list loading / empty / error states render;
2. submit buttons disable or show pending state during mutation;
3. destructive actions remain guarded while pending;
4. error UI maps stable API error codes instead of raw message branching;
5. request ID can be displayed when available;
6. no stack traces, SQL errors, credentials, object keys or server paths appear in user-visible error states.

### 14.6 E2E / Smoke Tests

Required coverage:

1. P0 authenticated happy path lands on Overview;
2. Overview quick actions navigate to P0 routes only;
3. Recent Run link opens Run Report;
4. Admin Setup Status is reachable for Admin users only;
5. P0 happy path and Stop path remain covered by `make verify-e2e` when release/main-merge environment is available.

---

## 15. Verification Commands

Required after implementation:

```bash
make generate-contracts
make verify
```

Recommended targeted commands during implementation:

```bash
uv run --all-packages pytest apps/api/tests -k "overview"
pnpm --filter @surgepilot/web test -- --run apps/web/src/features/overview
uv run --all-packages pytest tests/contract -k "overview or openapi"
```

Release/main-merge validation:

```bash
make verify-e2e
```

Rules:

1. Documentation-only changes may use a reduced CI path only when no code, contracts, generated clients or workflow files changed.
2. Any implementation of `GET /api/v1/overview` must run `make generate-contracts` and the relevant generated-client freshness checks.
3. P0 final acceptance should use `make verify` as the default hard gate.

---

## 16. Done When

P0-08 is done when:

1. `GET /api/v1/overview` is implemented as a lightweight read-only API;
2. Overview API applies current Workspace filtering and Load Node visibility rules;
3. Overview default result statistics include only Valid Standard terminal Runs in the 30-day window;
4. Debug and Invalid Runs may appear only in Recent Runs with visible labels;
5. Overview API does not read or parse artifact object content;
6. Overview implementation uses the required indexes or records exact existing equivalent indexes in backfill;
7. Overview page renders Run Summary, Recent Runs, Resource Summary and Quick Actions;
8. Overview shows the statistics window and clear scope copy;
9. Overview Quick Actions link only to P0 routes;
10. Admin navigation exposes only Setup Status for Admin users;
11. non-Admin users do not see Admin navigation and backend permissions still enforce access;
12. P0 pages have loading, empty, error and pending states according to frontend rules;
13. no P1/P2 clickable entry is present in P0 UI;
14. OpenAPI and generated Web contracts are fresh;
15. required API, Web and contract tests pass;
16. `make generate-contracts` passes;
17. `make verify` passes or any environment-specific gap is documented with exact failing command and reason;
18. Slice implementation backfill records engineering facts only.

---

## 17. Review Checklist

### 17.1 Scope

- [ ] Overview does not implement P1/P2 capabilities.
- [ ] No Monitoring, Grafana, Schedule, API Catalog, Help or Generated YAML link is clickable.
- [ ] No new external cache, queue or analytics datastore is introduced.

### 17.2 API and Contracts

- [ ] API shape is generated from FastAPI / Pydantic.
- [ ] Web uses generated `@surgepilot/contracts` types.
- [ ] Overview response fields use camelCase.
- [ ] `statsScope.resultRunScope` is generated as a closed Literal / enum.
- [ ] Internal runner endpoints remain internal.

### 17.3 Performance

- [ ] Overview queries are bounded and indexed.
- [ ] Result statistics and Recent Runs use the required composite indexes or documented equivalent query plans.
- [ ] Recent Runs default is `5` and max is `10`.
- [ ] No artifact object content is read for Overview.
- [ ] Expensive metrics are omitted or backed by persisted DB summary.

### 17.4 Security and Workspace

- [ ] Run statistics are Workspace-filtered.
- [ ] Resource Summary uses visible Load Node rules.
- [ ] No credentials, object keys, tokens or raw logs are exposed.
- [ ] Admin visibility is backed by backend permission checks.

### 17.5 UX Polish

- [ ] Loading, empty and error states are present.
- [ ] Pending mutations prevent duplicate submission.
- [ ] Error states are actionable and safe.
- [ ] UI copy is English and P0-scoped.

### 17.6 Verification

- [ ] `make generate-contracts` passed.
- [ ] `make verify` passed or an exact environment-specific gap is documented.
- [ ] Any `make verify-e2e` release/main-merge gap is documented.

---

## 18. Implementation Backfill

After P0-08 implementation, update this section only for engineering facts:

1. exact migration filenames, if any;
2. exact API schema names if they differ from this SDD;
3. exact indexes added for Overview, or exact existing indexes accepted as equivalent for `(workspace_id, run_type, validity, state, created_at desc)` and `(workspace_id, created_at desc, id desc)` query plans;
4. exact test files and verification commands;
5. accepted implementation differences from this SDD;
6. remaining risks for P0 final acceptance.

Do not use backfill to add P1/P2 scope or record author reasoning history.

Implementation facts recorded after P0-08 development:

1. Migration filename: `apps/api/migrations/versions/0009_p0_08_overview_indexes.py`.
2. API schema names match the Slice SDD naming: `OverviewResponse`, `OverviewResultRunScope`, `OverviewStatsScope`, `OverviewRunStats`, `OverviewRecentRun`, and `OverviewResourceSummary`.
3. Overview indexes:
   - Added `ix_runs_workspace_type_validity_state_created` on `runs(workspace_id, run_type, validity, state, created_at desc)` for result statistics.
   - Existing `ix_runs_workspace_created` on `runs(workspace_id, created_at desc, id desc)` is accepted as the Recent Runs index.
   - Existing `ix_load_nodes_scope_status_created` and `ix_load_nodes_workspace_status_created`, plus `ix_load_nodes_archived_at`, are accepted for visible Load Node status summary filtering in P0.
4. API implementation files:
   - `apps/api/app/routes/overview.py`
   - `apps/api/app/schemas/overview.py`
   - `apps/api/app/services/overview.py`
   - `apps/api/app/routes/admin.py` for backend-enforced Admin Setup Status access used by P0 Admin navigation.
5. Frontend implementation files:
   - `apps/web/src/features/overview/pages/overview-page.tsx`
   - `apps/web/src/features/admin/pages/setup-status-page.tsx`
   - `apps/web/src/app/layouts/app-layout.tsx`
   - `apps/web/src/app/router.tsx`
   - `apps/web/src/app/api-client.ts`
6. Test files added or updated:
   - `apps/api/tests/test_p0_08_overview_api.py`
   - `tests/contract/test_p0_08_overview_openapi.py`
   - `apps/web/src/features/overview/overview.test.tsx`
   - `apps/web/src/App.test.tsx`
7. Verification commands run during implementation:
   - `make generate-contracts`
   - `uv run --all-packages pytest apps/api/tests -k "overview"`
   - `pnpm --filter @surgepilot/web test -- apps/web/src/features/overview/overview.test.tsx`
   - `uv run --all-packages pytest tests/contract -k "overview or openapi"`
   - `uv run --all-packages ruff check apps/api apps/runner scripts tests`
   - `uv run --all-packages ruff format --check apps/api apps/runner scripts tests`
   - `pnpm -r lint`
   - `pnpm -r typecheck`
   - `make verify`
   - `make verify-e2e`
8. Accepted implementation differences from the Slice SDD:
   - P0 Admin Setup Status uses the existing minimal `SetupStatusResponse` fields and an Admin-only API route; it does not expand into a full health dashboard.
   - Overview artifact availability is derived from persisted `run_artifacts` metadata only; no artifact object content or object keys are read.
   - Overview and Admin Setup Status read queries disable default retries so loading and safe error states are visible without delayed retry loops.
   - App Layout shows the current user only in the sidebar account card. The top bar no longer repeats the username, and the sidebar card displays a bounded username with the full value in the `title` attribute.
9. Remaining risks for P0 final acceptance: none identified in this implementation backfill.
