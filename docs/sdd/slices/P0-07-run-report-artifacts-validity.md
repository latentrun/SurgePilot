# P0-07: Run Report, Artifacts, and Validity

- Documentation status: Draft v1
- Project: SurgePilot performance load testing platform
- Document location: `docs/sdd/slices/P0-07-run-report-artifacts-validity.md`
- Product source: `docs/prd/PRD.md`
- Range constraint: `docs/sdd/00-product-scope-and-priority.md`
- API contract source: `docs/sdd/04-api-contract-guidelines.md`
- Run / Runner Source: `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- Security / Workspace Source: `docs/sdd/06-security-permission-workspace.md`
- Storage / Artifacts Source: `docs/sdd/07-storage-artifacts-minio.md`
- Frontend Source: `docs/sdd/08-frontend-routing-and-ui-rules.md`
- Optional local Taurus reference: developer-supplied files under ignored `docs/reference/taurus/` may be used for Taurus artifact/report details, but they are not required in a fresh repository checkout.
- Current delivery target: P0 only
- Scope of application: Run List, Run Report, final stats summary, artifact list/download, artifacts.zip download, Validity mutation, Report polling, AI Coding, code review, test acceptance

---

## 1. Goal

P0-07 delivers the report closed loop after Run execution.

Once completed, users can within the current Workspace:

1. View the Run List and enter the details page of any visible Run;
2. Determine the execution status, SLA Result, Validity, running time and security failure reasons at the top of the Run Report;
3. View KPI Summary and Final Stats Preview based on Taurus `final-stats` CSV;
4. View the readable summary of the Run Snapshot and understand the Scenario / Test Plan / Env Group / Load Settings / SLA / Node used in this execution;
5. Expand the Artifacts area to view the file list and download logs, CSV and `artifacts.zip`;
6. Manually switch Valid / Invalid and record the operator and time;
7. Observe the status through safe polling in the Initializing / Running / Stopping state, and do not drive state convergence by the frontend.

The core results of P0-07 are:

```text
Run List
  -> Run Report (/runs/:runId)
  -> Verdict Summary
  -> KPI Summary from final_stats_csv
  -> Final Stats Preview
  -> Snapshot Summary
  -> Collapsible Artifacts
  -> Valid / Invalid mutation
```

P0-07 is not Monitoring, not a Grafana page, not a Taurus artifacts file manager, not a failed requests plugin preview, not a trend analysis system.

---

## 2. PRD Trace

| PRD area | P0-07 coverage |
| --- | --- |
| §4 P0 Main Link | Implement the closed loop of "Debug Run / Run Now → View Run Report / artifacts → Mark Valid / Invalid". |
| §5.8 Run | Shows Run state, runType, validity, SLA Result, triggerer, time, heartbeat, Snapshot, nodes and artifacts. |
| §5.9 Report | Report is not a new entity; P0-07 renders Run details as Run Report. |
| §6.2 Routes | Implements `/runs` and `/runs/:runId`. |
| §8.8 Runs / Reports | Implement Run List, Run Report, Stop status display, Validity switching and artifacts empty status. |
| §9.3 Run conclusion field relationship | The three types of conclusions, Status, SLA Result, and Validity, are displayed independently and cannot be inferred from each other. |
| §9.4 Run Validity | Standard Run defaults to Valid; Debug Run defaults to Invalid; users can manually switch in Run Report. |
| §9.8 Run Snapshot | Historical Run Report is displayed based on the snapshot at the time of creation and is not affected by subsequent asset modifications. |
| §11.3 Artifact and Report Availability | Display final stats, existing artifacts, and clear pending / unavailable status after Run. |
| §12.6 Report Acceptance | Answer acceptance questions such as status, SLA, Validity, Run Type, source, key indicators, report files, artifacts, nodes, etc. |

P0-07 Boundary for failed requests:

1. P0-07 does not implement `failed_requests.csv` preview, parsing, upload requirements or UI display.
2. Failed request preview depends on the installed JMeter plug-in output, which is specified by P1 Slice.
3. P0-07 still displays security failure reasons, Runner/api-worker convergence reasons, summary warnings and downloadable logs/artifacts, preventing the Run Report from leaving only the artifact list.

---

## 3. Document Responsibility

### 3.1 This Slice Owns

P0-07 owns:

1. Run List public API and UI;
2. Run Report public API and UI;
3. report summary table / JSON shape for `final_stats_csv`;
4. KPI derivation from Taurus `final-stats` CSV;
5. SLA Result storage and presentation rules;
6. artifact list, collapsed UI section and download route;
7. `artifacts_zip` as a P0 download-only artifact type;
8. Valid / Invalid mutation endpoint, UI and audit event;
9. Report polling start / stop behavior;
10. P0-07 tests, verification commands and Done When.

### 3.2 Foundation SDDs Remain Authoritative For

| Document | Remains authoritative for |
| --- | --- |
| `04-api-contract-guidelines.md` | REST URL shape, OpenAPI generation, error shape, cursor pagination, camelCase JSON, CSRF and Workspace headers. |
| `05-runner-protocol-and-run-state-machine.md` | Run state transitions, terminal state rules, callback idempotency, heartbeat timeout, Stop, node lease, artifact callback semantics. |
| `06-security-permission-workspace.md` | Auth, role model, Workspace resolution, CSRF, audit safety, sensitive values. |
| `07-storage-artifacts-minio.md` | MinIO-only boundary, artifact path safety, object key secrecy, upload/download streaming, size/hash checks, storage error codes. |
| `08-frontend-routing-and-ui-rules.md` | Route structure, TanStack Query, Run Report polling baseline, no P1/P2 navigation. |

### 3.3 Prior Slice Dependencies

P0-07 consumes:

1. P0-04 Run states, node lease and runner callback records;
2. P0-04 / 07 artifact ingest metadata;
3. P0-05 `debug_scenario` Run Snapshot;
4. P0-06 `test_plan` Run Snapshot and `slaEvaluationMode`;
5. P0-05 / P0-06 default validity values on Run creation;
6. P0-03 Load Node display metadata, excluding credentials.

### 3.4 Later Slice Ownership

Later Slices own:

1. P0-08 Overview cards and default statistics that consume Valid Runs;
2. P0-08 final polish for empty states and cross-page consistency;
3. P1 failed requests plugin output, `failed_requests.csv` preview and large CSV pagination;
4. P1 Monitoring / Grafana / InfluxDB links;
5. P1 Generated YAML read-only preview;
6. P2 secret-aware Run Snapshot encryption and redaction.

---

## 4. In Scope

### 4.1 Backend API

P0-07 implements or finalizes:

1. `GET /api/v1/runs` cursor-paginated Run List;
2. `GET /api/v1/runs/{runId}` Run Report detail;
3. `GET /api/v1/runs/{runId}/artifacts` artifact list for the Run;
4. `GET /api/v1/runs/{runId}/artifacts/{artifactId}/download` API-mediated artifact download;
5. `PATCH /api/v1/runs/{runId}/validity` Valid / Invalid mutation;
6. final stats summary parser entrypoint triggered after `final_stats_csv` artifact availability;
7. storage of `slaResult` and final stats summary status;
8. audit event `run.validity_changed`;
9. OpenAPI export and generated Web client update for public endpoints only.

### 4.2 Data

P0-07 may add or finalize:

1. `runs.sla_result`;
2. `runs.validity_updated_by_user_id`;
3. `runs.validity_updated_at`;
4. `run_report_summaries` for bounded derived summary data;
5. `run_artifacts.artifact_type='artifacts_zip'` as P0 download-only artifact;
6. indexes needed for Run List cursor pagination and Run Report lookup.

P0-07 does not change Run state enum values.

### 4.3 Frontend

P0-07 implements:

1. `/runs` Run List page;
2. `/runs/:runId` Run Report page;
3. Verdict Summary section;
4. KPI Summary section;
5. safe Failure Diagnostics section without `failed_requests.csv` preview;
6. Final Stats Preview section;
7. Snapshot Summary section;
8. collapsible Artifacts section;
9. Nodes section;
10. Validity mutation control;
11. state-based Stop / Refresh actions;
12. pending, empty and unavailable states.

### 4.4 Taurus / JMeter Mapping

P0-07 aligns with Taurus artifact and reporting behavior. Developers may keep local reference copies under ignored `docs/reference/taurus/`, but those files are optional and are not committed.

1. Taurus creates an artifacts directory on each tool start and stores logs, merged/effective configs and executor outputs there.
2. Taurus `final-stats` reporter is enabled by default and supports `dump-csv` for final cumulative stats.
3. P0 execution must ensure a `final_stats_csv` artifact is uploaded when Taurus produces the configured final stats CSV.
4. P0-07 parses only the uploaded `final_stats_csv` artifact.
5. P0-07 does not parse `bzt.log` for KPI values.
6. P0-07 does not invent a `failed_requests.csv` format.
7. P0-07 does not depend on Taurus cloud, BlazeMeter, InfluxDB reporter or Monitoring modules.

### 4.5 Tests

P0-07 must add tests for:

1. Run List Workspace filtering and cursor pagination;
2. Run Report detail response shape and state / SLA / validity independence;
3. final stats CSV parser success, partial data, parse failure and bounded memory behavior;
4. artifact list and download permission / Workspace / status checks;
5. `artifacts_zip` metadata as download-only artifact;
6. Validity mutation, CSRF, Workspace filtering and audit event;
7. Web polling, section ordering, collapsed artifacts and empty states;
8. OpenAPI / generated client freshness.

---

## 5. Out of Scope

P0-07 does not implement:

1. `failed_requests.csv` upload requirement, parser, preview or UI table;
2. JMeter plugin installation or plugin-specific failed request file contract;
3. generic log preview, log tailing, log search or inline log rendering;
4. Report HTML inline rendering;
5. `report_html` as a P0 artifact type;
6. ZIP / TAR / TGZ extraction, manifest inspection or per-entry download;
7. direct browser-to-MinIO download or presigned URL;
8. object key, bucket or MinIO endpoint exposure;
9. HTTP Range download;
10. large CSV pagination;
11. Trend comparison, baseline, regression analysis or capacity analytics;
12. Monitoring page, Grafana iframe, Open Monitoring, InfluxDB datasource or time-series query;
13. Schedule Run, Scheduled Job or Upcoming Scheduled Jobs statistics;
14. multi-node execution, node count, selected nodes list or cross-node metric aggregation;
15. Generated YAML preview or editable Taurus YAML;
16. API Catalog, cURL import or OpenAPI Step generation;
17. audit log UI or audit export.

Allowed P0 extension points:

1. API may include stable enum values required by active P0 contracts.
2. P0 may store summary parser status and warnings for later UI polish.
3. P0 may expose artifact `downloadUrl` as an API business URL, not as a MinIO URL.
4. P0 may show a disabled non-clickable copy note that failed request preview is not available in P0, but must not link to a P1 page.

---

## 6. Confirmed Decisions

| Area | Decision |
| --- | --- |
| Report entity | No separate Report entity; Run detail is the Run Report. |
| Run List route | `/runs` |
| Run Report route | `/runs/:runId` |
| Run Report API | `GET /api/v1/runs/{runId}` |
| Status authority | `runs.state`, updated only by API state machine / worker, not frontend. |
| SLA Result values | `passed`, `failed`, `not_evaluated` |
| Validity values | `valid`, `invalid` |
| Default validity | Standard Run defaults `valid`; Debug Run defaults `invalid` at Run creation. |
| Validity mutation | Any authenticated user with current Workspace access may change visible Run validity in P0. |
| Validity audit | `run.validity_changed` is required. |
| Final stats source | Taurus `final-stats` `dump-csv` uploaded as `final_stats_csv`. |
| KPI source | Derived from parsed `final_stats_csv`; missing values show `N/A` with reason. |
| Taurus CSV `throughput` column | Treat as total sample count per Taurus reference, not TPS. |
| Failure diagnostics | P0 shows safe `failureReason`, `failureMessage`, forced convergence and artifact/summary warnings. |
| Failed requests preview | P1; P0-07 does not parse or display `failed_requests.csv`. |
| `artifacts_zip` | P0 download-only artifact type. No extraction or preview. |
| Artifact section UI | Collapsible; show count and important file badges before expansion. |
| Artifact download | API proxy only; attachment; no-store; no Range. |
| Summary parser | API / api-worker bounded parser; no Redis, Celery or external queue. |
| Report polling | Poll active states every 5s; stop normal polling on terminal state; capped fallback summary polling. |
| Monitoring entry | Not shown in P0. |
| Report HTML | Not rendered inline in P0. |

---

## 7. Taurus / JMeter Alignment

### 7.1 Taurus Reference Topics

| Optional local reference | P0-07 contract area |
| --- | --- |
| `docs/reference/taurus/CommandLine.md` | Taurus artifacts directory creation and key files such as `bzt.log`, `merged.yml`, `effective.yml`; Taurus exit code semantics. |
| `docs/reference/taurus/ArtifactsDir.md` | Common artifacts such as `bzt.log`, `effective.*`, `merged.*`, executor logs and request data files. |
| `docs/reference/taurus/ConfigSyntax.md` | `settings.artifacts-dir` and `TAURUS_ARTIFACTS_DIR` environment variable. |
| `docs/reference/taurus/Reporting.md` | `final-stats` reporter and `dump-csv` fields. |
| `docs/reference/taurus/PassFail.md` | Taurus passfail module subjects and criteria semantics used by P0-06 SLA Rules. |

### 7.2 Final Stats Artifact Requirement

P0 execution must produce a Taurus final stats CSV when Taurus reaches report generation.

Recommended generated YAML fragment:

```yaml
reporting:
  - module: final-stats
    dump-csv: final_stats.csv
```

Rules:

1. The execution builder or runner may choose the exact safe file location inside the Run artifact collection directory.
2. The Runner must upload the actual file generated by Taurus as `artifactType=final_stats_csv`.
3. The uploaded `relativePath` must pass `07-storage-artifacts-minio.md` artifact path validation.
4. Recommended uploaded `relativePath` is `artifacts/final_stats.csv` when the runner stores Taurus final stats under the Run artifacts directory.
5. P0-07 must not display the generated Taurus YAML as a user-visible preview.
6. P0-07 must not parse `bzt.log` as the primary KPI source.
7. If final stats CSV is missing, Run Report shows `N/A` KPI values and a safe missing summary reason.

### 7.3 Final Stats CSV Field Mapping

Taurus `Reporting.md` defines these `dump-csv` fields relevant to P0:

| Taurus field | P0 report meaning |
| --- | --- |
| `label` | sample group label; empty label represents total of all labels |
| `concurrency` | average number of Virtual Users; P0 may ignore it or store it as non-primary summary metadata, but must not expose multi-node or node-count behavior from it |
| `throughput` | total sample count, used as P0 `totalRequests` |
| `succ` | successful sample count |
| `fail` | failed sample count, used as P0 `failedRequests`; Taurus `Reporting.md` describes this field as "saved samples", but the surrounding `succ` / `fail` semantics are not-failed / failed sample counters |
| `avg_rt` | average response time |
| `stdev_rt` | standard deviation of response time, optional display |
| `avg_ct` | average connect time, optional display |
| `avg_lt` | average latency, optional display |
| `perc_90.0` | P90 response time, used as P0 `p90Ms` when present |
| `perc_95.0` | P95 response time, used as P0 `p95Ms` when present |
| `perc_99.0` | P99 response time, used as P0 `p99Ms` when present |
| `perc_*` | other percentile columns; parser may preserve only bounded preview / summary fields required by P0 |
| `rc_*` | response code count columns |
| `bytes` | total download size; P0 may ignore it or store it as non-primary summary metadata |

Rules:

1. `totalRequests` is derived from the total row `throughput` value.
2. `failedRequests` is derived from the total row `fail` value.
3. `errorRate` is computed as `failedRequests / totalRequests` when `totalRequests > 0`.
4. `averageResponseTimeMs` is derived from `avg_rt` after unit normalization selected by implementation tests.
5. `p90Ms`, `p95Ms` and `p99Ms` are derived from total-row `perc_90.0`, `perc_95.0` and `perc_99.0` after the same response-time unit normalization used for `avg_rt`.
6. Missing or unparsable percentile columns produce stable missing / warning codes and must not fail the whole summary parse.
7. P0 does not compute TPS from Taurus CSV `throughput`, because the Taurus reference describes it as total count.
8. Parser must treat unknown extra columns as optional and must not fail only because extra `rc_*`, `perc_*`, `concurrency` or `bytes` columns exist.
9. Parser failure must not change Run state or block raw artifact download.

### 7.4 SLA Result Boundary

P0-06 owns SLA Rule storage and Taurus passfail YAML generation.

P0-07 owns the final `slaResult` shown in Run List and Run Report.

Rules:

1. `slaEvaluationMode=not_evaluated` results in `slaResult=not_evaluated`.
2. `slaEvaluationMode=not_configured` results in `slaResult=not_evaluated`.
3. `slaEvaluationMode=passfail` may result in `passed` or `failed` only when the Runner or API can determine passfail outcome from the completed execution.
4. Runner terminal callback `details.slaResult` may carry `passed` or `failed` for `finished`, `failed` or `aborted` events.
5. API validates `details.slaResult` when present and stores it on the Run.
6. If `slaEvaluationMode=passfail` but no trusted SLA outcome exists by report time, API returns `slaResult=not_evaluated` with `slaResultReason=missing_sla_result`.
7. `slaResult=failed` must not change `state=finished` to `state=failed`.
8. Debug Runs must not evaluate SLA and must show `not_evaluated`.
9. For required node allocations, any explicit `failed` verdict produces `failed`, all explicit `passed` verdicts produce `passed`, and every incomplete combination produces `not_evaluated` with `missing_sla_result`.

Example terminal callback details extension:

```json
{
  "processGroupExited": true,
  "exitCode": 0,
  "slaResult": "passed"
}
```

---

## 8. Data Model

### 8.1 `runs` Extensions

P0-07 requires the Run model to represent:

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `sla_result` | `text` | yes | `passed`, `failed`, `not_evaluated`; default `not_evaluated`. |
| `sla_result_reason` | `text` | no | Safe lower snake case reason, nullable. |
| `validity_updated_by_user_id` | `char(26)` | no | FK users; null until manually changed. |
| `validity_updated_at` | `timestamptz` | no | UTC timestamp of manual validity change. |

Constraints and indexes:

1. `sla_result in ('passed', 'failed', 'not_evaluated')`.
2. `validity in ('valid', 'invalid')` remains required once P0-05 / P0-06 Run creation is active.
3. `validity_updated_by_user_id` references `users.id` with `ondelete restrict` or equivalent safe behavior.
4. Existing Run List indexes may be extended for `(workspace_id, created_at desc, id desc)` and common filters.

Rules:

1. `state`, `sla_result` and `validity` are independent fields.
2. Updating validity must not alter state, SLA result, timestamps from runner lifecycle or node lease.
3. Updating SLA result must not alter state, validity or node lease.
4. API JSON uses camelCase: `slaResult`, `slaResultReason`, `validityUpdatedBy`, `validityUpdatedAt`.

### 8.2 `run_report_summaries`

Purpose: bounded derived report data from uploaded artifacts.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `workspace_id` | `char(26)` | yes | Copied from Run. |
| `run_id` | `char(26)` | yes | FK `runs.id`. |
| `source_artifact_id` | `char(26)` | yes | FK `run_artifacts.id`. |
| `summary_type` | `text` | yes | P0: `final_stats`. |
| `summary_json` | `jsonb` | yes | Bounded structured summary. |
| `truncated` | `boolean` | yes | True if parser stopped because of bounds. |
| `parse_status` | `text` | yes | `pending`, `parsed`, `failed`. |
| `parse_error_code` | `text` | no | Safe code only, no raw parser exception. |
| `created_at` | `timestamptz` | yes | UTC. |
| `updated_at` | `timestamptz` | yes | UTC. |

Constraints and indexes:

1. `summary_type in ('final_stats')` for P0.
2. `parse_status in ('pending', 'parsed', 'failed')`.
3. Unique `(run_id, source_artifact_id, summary_type)`.
4. Index `(workspace_id, run_id, summary_type)`.
5. Index `(parse_status, created_at)` if api-worker claims pending rows.

Rules:

1. Summary is derived data and may be regenerated from the source artifact.
2. Summary never replaces raw artifact download.
3. Summary parse failure must not change Run state.
4. Summary parse failure must not block artifact download.
5. Summary JSON must not include MinIO object key, server absolute path, raw stack trace or unescaped HTML.
6. P0 stores only bounded rows needed by Run Report.

### 8.3 Final Stats Summary JSON

Recommended `summary_json` shape:

```json
{
  "schemaVersion": 1,
  "total": {
    "label": null,
    "totalRequests": 1200,
    "successRequests": 1188,
    "failedRequests": 12,
    "errorRate": 0.01,
    "averageResponseTimeMs": 153.2,
    "p90Ms": 420.0,
    "p95Ms": 610.0,
    "p99Ms": 950.0,
    "responseCodeCounts": {
      "200": 1188,
      "500": 12
    }
  },
  "rows": [
    {
      "label": "GET /checkout",
      "totalRequests": 400,
      "successRequests": 396,
      "failedRequests": 4,
      "errorRate": 0.01,
      "averageResponseTimeMs": 188.4,
      "p90Ms": 500.0,
      "p95Ms": 700.0,
      "p99Ms": 980.0,
      "responseCodeCounts": {
        "200": 396,
        "500": 4
      }
    }
  ],
  "warnings": []
}
```

Rules:

1. `schemaVersion` is `1` in P0.
2. `total.label` is `null` for the empty-label total row.
3. If no empty-label row exists, parser may choose the first row as `total` only when tests document the behavior; otherwise parse fails with `FINAL_STATS_TOTAL_ROW_MISSING`.
4. `rows` must be bounded; recommended max `200` rows.
5. `warnings` contains stable codes only, not raw CSV content.
6. Values that cannot be parsed become missing and create a safe warning; parser must not fabricate numeric values.
7. `p90Ms`, `p95Ms` and `p99Ms` are nullable only when the corresponding `perc_90.0`, `perc_95.0` or `perc_99.0` total-row value is missing or unparsable.

### 8.4 Artifact Metadata Extension

`run_artifacts.artifact_type` P0 values:

```text
taurus_log
jmeter_log
final_stats_csv
run_log
artifacts_zip
```

Rules:

1. `artifacts_zip` is download-only.
2. API must not extract `artifacts_zip`.
3. API must not preview `artifacts_zip` inline.
4. `failed_requests_csv` is not part of P0-07.
5. Object key remains server-only as defined by 07.

---

## 9. API Contract

### 9.1 Shared Enums

```text
RunState = initializing | running | stopping | finished | failed | aborted
RunType = debug | standard
RunSourceType = protocol_smoke | debug_scenario | test_plan
RunValidity = valid | invalid
SlaResult = passed | failed | not_evaluated
RunArtifactType = taurus_log | jmeter_log | final_stats_csv | run_log | artifacts_zip
ReportSummaryStatus = pending | parsed | failed | missing
```

Rules:

1. API enum values use lower snake case.
2. `protocol_smoke` remains internal / compatibility only and must not become a public P0 product action.
3. `failed_requests_csv` must not appear in P0 public artifact enum, OpenAPI examples or Web UI.

### 9.2 `RunListItem`

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7R",
  "state": "finished",
  "runType": "standard",
  "sourceType": "test_plan",
  "sourceId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "sourceName": "Checkout Load Test",
  "sourceRevision": 4,
  "tags": ["checkout"],
  "validity": "valid",
  "slaResult": "passed",
  "triggeredBy": {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7U",
    "email": "qa@example.com"
  },
  "selectedNode": {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
    "name": "private-node-1",
    "scope": "workspace"
  },
  "createdAt": "2030-06-03T08:00:00.000Z",
  "startedAt": "2030-06-03T08:00:05.000Z",
  "endedAt": "2030-06-03T08:05:10.000Z",
  "durationMs": 305000,
  "artifactCount": 4,
  "hasArtifactsZip": true
}
```

Rules:

1. `sourceName`, `sourceRevision` and `tags` are read from Run Snapshot, not from current mutable Scenario / Test Plan rows.
2. `selectedNode` must not include SSH username, password, private key, passphrase or runner token.
3. `durationMs` is computed from `startedAt` or `createdAt` to `endedAt` / current server time according to implementation rules; null is allowed when not enough timestamps exist.
4. `artifactCount` counts available artifacts visible to the user.
5. `hasArtifactsZip` is true only when an available `artifacts_zip` exists.

### 9.3 `GET /api/v1/runs`

Purpose: cursor-paginated Run List.

Query parameters:

| Parameter | Rule |
| --- | --- |
| `state` | Optional RunState filter. |
| `validity` | Optional RunValidity filter. |
| `runType` | Optional RunType filter. |
| `sourceType` | Optional RunSourceType filter. |
| `q` | Optional keyword search over Run ID and snapshot source name; max 120 chars. |
| `tag` | Optional exact tag filter over snapshot tags; max 50 chars. |
| `recentHours` | Optional positive integer; P0 UI may use `24`. |
| `cursor` | Optional opaque cursor. |
| `limit` | Optional, default `20`, max `100`. |
| `sort` | Only `-createdAt` in P0. |

Response:

```json
{
  "items": [],
  "nextCursor": null
}
```

Status codes:

| Status | Meaning |
| --- | --- |
| `200 OK` | List returned. |
| `400 WORKSPACE_REQUIRED` | Workspace context cannot be resolved. |
| `401 UNAUTHENTICATED` | Not logged in. |
| `403 WORKSPACE_ACCESS_DENIED` | User cannot access Workspace. |
| `422 VALIDATION_ERROR` | Invalid filter or cursor. |

Rules:

1. Query must filter by current Workspace.
2. Cross-Workspace Runs must not leak through list, count, cursor or keyword search.
3. Cursor must be opaque to Web.
4. P0 supports only descending created time sort.
5. If `tag` is expensive without a JSON index, implementation may enforce a small limit and document a bounded query plan in tests; do not add a separate tag service in P0.

### 9.4 `RunReportDetail`

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7R",
  "verdict": {
    "state": "finished",
    "runType": "standard",
    "sourceType": "test_plan",
    "validity": "valid",
    "slaResult": "passed",
    "slaResultReason": null,
    "durationMs": 305000,
    "triggeredBy": {
      "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7U",
      "email": "qa@example.com"
    },
    "createdAt": "2030-06-03T08:00:00.000Z",
    "acceptedAt": "2030-06-03T08:00:02.000Z",
    "startedAt": "2030-06-03T08:00:05.000Z",
    "endedAt": "2030-06-03T08:05:10.000Z",
    "lastHeartbeatAt": "2030-06-03T08:05:00.000Z",
    "failureReason": null,
    "failureMessage": null,
    "forcedConvergence": false,
    "warnings": []
  },
  "kpiSummary": {
    "status": "parsed",
    "sourceArtifactId": "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
    "totalRequests": 1200,
    "failedRequests": 12,
    "errorRate": 0.01,
    "averageResponseTimeMs": 153.2,
    "p90Ms": 420.0,
    "p95Ms": 610.0,
    "p99Ms": 950.0,
    "throughputPerSecond": null,
    "missingReasons": []
  },
  "failureDiagnostics": {
    "failureReason": null,
    "failureMessage": null,
    "hasFailedRequestsPreview": false,
    "notes": []
  },
  "finalStatsPreview": {
    "status": "parsed",
    "truncated": false,
    "rows": []
  },
  "snapshot": {
    "schemaVersion": 1,
    "sourceName": "Checkout Load Test",
    "sourceRevision": 4,
    "envGroupName": "Staging",
    "runMode": "sequential",
    "scenarioCount": 1,
    "slaRuleCount": 1,
    "dependencyFileCount": 0,
    "resourceRequest": {
      "mode": "manual",
      "poolType": "workspace",
      "selectedNodeId": "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
      "expectedConcurrencyPerNode": 10
    }
  },
  "nodes": [
    {
      "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
      "name": "private-node-1",
      "scope": "workspace",
      "poolType": "workspace",
      "stateAtReport": "idle"
    }
  ],
  "artifactsSummary": {
    "count": 4,
    "hasArtifactsZip": true,
    "hasFinalStatsCsv": true,
    "latestAvailableAt": "2030-06-03T08:05:20.000Z"
  }
}
```

Rules:

1. Response must not include MinIO object keys, bucket names, runner token, SSH credentials, server absolute paths or raw private key material.
2. `snapshot` is a curated display summary, not the raw `run_snapshots.snapshot_json` dump.
3. API may include more snapshot display fields only if they come from immutable snapshot and do not expose credentials or generated YAML preview.
4. `kpiSummary.status` values: `parsed`, `pending`, `failed`, `missing`.
5. `missingReasons` uses stable lower snake case values such as `final_stats_missing`, `summary_pending`, `summary_parse_failed`, `percentile_column_missing`, `percentile_value_invalid`.
6. `failureDiagnostics.hasFailedRequestsPreview` is always false in P0.
7. Empty / unavailable sections must be represented explicitly; Web must not infer by missing fields.

### 9.5 `GET /api/v1/runs/{runId}`

Purpose: return Run Report detail.

Status codes:

| Status | Meaning |
| --- | --- |
| `200 OK` | Run Report returned. |
| `400 WORKSPACE_REQUIRED` | Workspace context cannot be resolved. |
| `401 UNAUTHENTICATED` | Not logged in. |
| `403 WORKSPACE_ACCESS_DENIED` | User cannot access Workspace. |
| `404 RESOURCE_NOT_FOUND` | Run does not exist or is hidden by Workspace boundary. |
| `422 VALIDATION_ERROR` | Invalid Run ID. |

Rules:

1. Lookup by `(workspace_id, run_id)`.
2. Cross-Workspace Run IDs return `RESOURCE_NOT_FOUND` where possible.
3. Active Runs may return partial report sections with pending / missing statuses.
4. Terminal Runs with pending summary may still return report detail and let Web perform capped summary polling.
5. This endpoint must not trigger state transitions, node lease release or artifact parsing as a side effect.

### 9.6 `RunArtifactItem`

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
  "artifactType": "final_stats_csv",
  "relativePath": "artifacts/final_stats.csv",
  "displayFilename": "final_stats.csv",
  "sizeBytes": 2048,
  "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "contentType": "text/csv",
  "terminalLate": false,
  "createdAt": "2030-06-03T08:05:18.000Z",
  "availableAt": "2030-06-03T08:05:18.000Z",
  "downloadUrl": "/api/v1/runs/01HZX3Y9M0E9W7Z6M5QK9S8P7R/artifacts/01HZX3Y9M0E9W7Z6M5QK9S8P7F/download"
}
```

Rules:

1. `downloadUrl` is a business API route, not a MinIO URL.
2. `relativePath` is safe display metadata already validated by API.
3. Response must not include `storageBucket`, `storageObjectKey`, server path or MinIO endpoint.
4. Artifacts with `status != available` must not appear as normal downloadable items.
5. `artifacts_zip` may appear with the same item shape and is download-only.

### 9.7 `GET /api/v1/runs/{runId}/artifacts`

Purpose: list available artifacts for a Run.

Response:

```json
{
  "items": [],
  "nextCursor": null
}
```

Query parameters:

| Parameter | Rule |
| --- | --- |
| `artifactType` | Optional RunArtifactType filter. |
| `cursor` | Optional opaque cursor. |
| `limit` | Optional, default `50`, max `100`. |
| `sort` | Only `createdAt` or `-createdAt`; default `createdAt`. |

Status codes:

| Status | Meaning |
| --- | --- |
| `200 OK` | List returned. |
| `400 WORKSPACE_REQUIRED` | Workspace context cannot be resolved. |
| `401 UNAUTHENTICATED` | Not logged in. |
| `403 WORKSPACE_ACCESS_DENIED` | User cannot access Workspace. |
| `404 RESOURCE_NOT_FOUND` | Run does not exist or is hidden by Workspace boundary. |
| `422 VALIDATION_ERROR` | Invalid Run ID, filter, cursor or limit. |

Rules:

1. Query filters by Run ID and Workspace.
2. `artifactType=failed_requests_csv` returns `422 VALIDATION_ERROR` in P0 public API.
3. The list may be long; Web must render it inside a collapsible Artifacts section.

### 9.8 `GET /api/v1/runs/{runId}/artifacts/{artifactId}/download`

Purpose: download one available artifact through API proxy.

Response:

- `200 OK`
- body: streamed bytes
- headers follow `07-storage-artifacts-minio.md`:
  - `Content-Disposition: attachment`
  - `Cache-Control: private, no-store`
  - no `Accept-Ranges` support in P0

Status codes:

| Status | Meaning |
| --- | --- |
| `200 OK` | Artifact streamed. |
| `400 WORKSPACE_REQUIRED` | Workspace context cannot be resolved. |
| `401 UNAUTHENTICATED` | Not logged in. |
| `403 WORKSPACE_ACCESS_DENIED` | User cannot access Workspace. |
| `404 RESOURCE_NOT_FOUND` | Run or artifact does not exist or is hidden by Workspace boundary. |
| `409 ARTIFACT_NOT_READY` | Artifact metadata exists but is not available. |
| `503 STORAGE_UNAVAILABLE` | MinIO object cannot be read. |
| `422 VALIDATION_ERROR` | Invalid Run ID or Artifact ID. |

Rules:

1. API validates Run ownership, Workspace and artifact status before reading MinIO.
2. API downloads by `artifactId`, not by object key or relative path.
3. API must stream and must not read entire artifact into memory.
4. Error response must not include object key, server path or MinIO internal error.
5. Browser must not receive MinIO credentials or presigned URLs.

### 9.9 `PATCH /api/v1/runs/{runId}/validity`

Purpose: manually set Run validity.

Request:

```json
{
  "validity": "invalid"
}
```

Response:

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7R",
  "validity": "invalid",
  "validityUpdatedAt": "2030-06-03T09:00:00.000Z",
  "validityUpdatedBy": {
    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7U",
    "email": "qa@example.com"
  }
}
```

Status codes:

| Status | Meaning |
| --- | --- |
| `200 OK` | Validity changed or idempotently already at requested value. |
| `400 WORKSPACE_REQUIRED` | Workspace context cannot be resolved. |
| `401 UNAUTHENTICATED` | Not logged in. |
| `403 CSRF_TOKEN_REQUIRED` | Missing CSRF token. |
| `403 CSRF_TOKEN_INVALID` | Invalid CSRF token. |
| `403 WORKSPACE_ACCESS_DENIED` | User cannot access Workspace. |
| `404 RESOURCE_NOT_FOUND` | Run does not exist or is hidden by Workspace boundary. |
| `422 VALIDATION_ERROR` | Invalid Run ID or validity value. |

Rules:

1. Validity update is a browser write and requires CSRF.
2. Lookup by `(workspace_id, run_id)`.
3. P0 allows validity mutation for active and terminal Runs visible in the current Workspace.
4. Repeating the same validity value is idempotent and returns `200 OK`.
5. Every successful request writes or confirms `validity_updated_at` and `validity_updated_by_user_id`.
6. API writes audit event `run.validity_changed` only when the value changes.
7. Validity mutation must not alter Run state, SLA result, artifacts, node lease or snapshot.

### 9.10 Error Code Registry

P0-07 uses existing error codes from 04, 06 and 07 before adding new ones.

| Code | Status | P0-07 use |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Browser user not logged in. |
| `CSRF_TOKEN_REQUIRED` | 403 | Missing CSRF on validity write. |
| `CSRF_TOKEN_INVALID` | 403 | Invalid CSRF on validity write. |
| `WORKSPACE_REQUIRED` | 400 | Workspace cannot be resolved. |
| `WORKSPACE_ACCESS_DENIED` | 403 | User cannot access Workspace. |
| `RESOURCE_NOT_FOUND` | 404 | Run or artifact missing or hidden by Workspace. |
| `VALIDATION_ERROR` | 422 | Invalid IDs, filters, cursors or request body. |
| `ARTIFACT_NOT_READY` | 409 | Artifact exists but is not available. |
| `STORAGE_UNAVAILABLE` | 503 | MinIO unavailable for download. |

P0-07 does not add a new public error code unless implementation proves UI branching cannot use this registry.

---

## 10. Backend Processing Rules

### 10.1 Final Stats Summary Creation

Trigger:

```text
final_stats_csv artifact available
  -> create or reuse run_report_summaries row
  -> parse bounded CSV
  -> store parsed / failed result
```

Rules:

1. Summary parser may run synchronously after artifact upload only if bounded and fast in tests.
2. Preferred P0 implementation uses `api-worker` to claim pending summaries from PostgreSQL.
3. Do not introduce Redis, Celery, RabbitMQ, Kafka or external queue service.
4. Parser must stream or read within bounded size limits.
5. Parser must not load arbitrary large CSV into memory.
6. Parser must not trust CSV content as HTML.
7. Parser errors are stored as safe `parse_error_code` values.
8. Parser failure does not change Run state, SLA result or validity.
9. Raw artifact download remains available once artifact status is available.

### 10.2 Summary Status Rules

| Condition | API status |
| --- | --- |
| No `final_stats_csv` artifact exists | `missing` |
| Artifact exists but summary row pending | `pending` |
| Summary parsed successfully | `parsed` |
| Summary parsing failed | `failed` |

Rules:

1. `kpiSummary` must always be present in Run Report response.
2. Missing metrics use `null` and `missingReasons`, not omitted fields.
3. Web shows `N/A` for null KPI values.
4. Terminal Run with `pending` summary may use capped fallback polling.
5. After fallback polling cap, Web shows `Summary not yet ready` and a manual Refresh action.

### 10.3 Artifact Priority

P0 runner should prioritize upload of:

1. `artifacts_zip` when a complete safe bundle archive is produced;
2. `final_stats_csv`;
3. `taurus_log` for `bzt.log`;
4. `jmeter_log` where available;
5. `run_log` for SurgePilot runner stdout / stderr or equivalent safe log.

Rules:

1. Missing non-critical artifacts must not block terminal Run convergence.
2. Missing `final_stats_csv` affects KPI availability only.
3. Missing `artifacts_zip` affects download availability only.
4. Artifact warnings should be visible in Run Report but must not expose storage paths.

---

## 11. Frontend Contract

### 11.1 Routes and Navigation

P0-07 route modules:

```text
apps/web/src/features/runs/routes.tsx
```

Routes:

| Page | Route | Layout |
| --- | --- | --- |
| Run List | `/runs` | AppLayout |
| Run Report | `/runs/:runId` | AppLayout |

Rules:

1. Root router only aggregates feature route objects.
2. Business data uses TanStack Query, not React Router loaders.
3. Web uses generated client/types from `@surgepilot/contracts` only.
4. Web sends `x-workspace-id` after current Workspace is known.
5. Validity mutation sends `x-csrf-token`.
6. No Monitoring, Grafana, Schedule or Generated YAML routes are added in P0.

### 11.2 Run List Page

Required UI:

1. title: `Runs`;
2. filters: State, Validity, Run Type, Source Type, recent 24 hours;
3. optional search input for Run ID / source name;
4. table or card list with Run ID, source, type, state, validity, SLA result, triggered by, start/end/duration, artifact count;
5. row action: View Report;
6. Stop action only for Initializing / Running;
7. empty state that guides users to create or run a Test Plan / Scenario, without API Catalog or Schedule links.

Rules:

1. Run List uses cursor pagination.
2. Run List must not show Monitoring entry in P0.
3. Run List can show Validity but primary validity mutation may live in Run Report.
4. Stop action follows P0-04 idempotency rules.

### 11.3 Run Report Layout

Run Report section order:

1. Verdict Summary;
2. KPI Summary;
3. Failure Diagnostics;
4. Final Stats Preview;
5. Snapshot Summary;
6. Artifacts;
7. Nodes.

Rules:

1. Verdict Summary is always visible first.
2. Artifacts are troubleshooting material, not the primary conclusion.
3. Each section has loading, empty, unavailable and error states where applicable.
4. Active Runs show status explanation and last refreshed time.
5. Terminal Runs stop normal polling.
6. P0 UI copy is English only.
7. Web validates the minimum report shape before polling, Monitoring lookup, or rendering, including nested arrays and primitive fields it directly iterates, renders, or passes to string/number formatting helpers. Invalid responses use the existing load-error state and do not start a Monitoring request.

### 11.4 Verdict Summary

Verdict Summary displays:

1. Status;
2. Run Type;
3. Validity;
4. SLA Result;
5. Duration;
6. Triggered By;
7. Source;
8. Error Message when available;
9. Last Heartbeat when active or failed by heartbeat timeout;
10. Forced Convergence indicator when true.

Rules:

1. Status, SLA Result and Validity must be visually separate.
2. `finished` must not be rendered as `SLA Passed`.
3. `failed` / `aborted` must not be rendered as `Invalid`.
4. Debug Runs show `Invalid` by default unless manually changed.
5. Known `slaResultReason` values render product-owned safe explanations. Unknown server-provided reason text is not rendered verbatim.
6. Load Node `terminalReason` uses the same product-owned failure allowlist; unknown Runner strings are omitted rather than formatted and rendered.

### 11.5 KPI Summary

Required cards:

1. Total Requests;
2. Failed Requests;
3. Error Rate;
4. Average Response Time.

Optional cards:

1. P90 / P95 / P99 when trusted values exist;
2. TPS only when a future accepted contract provides a trustworthy per-second source.

Rules:

1. Required cards are always rendered.
2. In P0, trusted percentile values are `perc_90.0`, `perc_95.0` and `perc_99.0` parsed from the uploaded Taurus `final_stats_csv`.
3. Missing values show `N/A` and a readable reason.
4. P0 must not compute TPS from Taurus CSV `throughput`.
5. Parse failure shows summary unavailable while keeping artifact download available.

### 11.6 Failure Diagnostics

P0 Failure Diagnostics displays:

1. safe `failureReason`;
2. safe `failureMessage`;
3. heartbeat timeout / accepted wait timeout information when applicable;
4. forced convergence warning when applicable;
5. missing final stats or artifact warnings.

Rules:

1. Do not show `failed_requests.csv` preview in P0.
2. Do not show a failed requests table placeholder that implies hidden P0 functionality.
3. Do not show raw stack traces, server paths, SSH commands, MinIO errors, runner token or credentials.
4. Users investigate detailed failures by downloading logs / artifacts in P0.

### 11.7 Final Stats Preview

Final Stats Preview displays:

1. total row;
2. bounded per-label rows;
3. response-code counts when available;
4. parser status;
5. truncated indicator when applicable.

Rules:

1. Preview rows are derived from `run_report_summaries.summary_json`.
2. Preview does not paginate large CSV in P0.
3. Users can download raw `final_stats_csv` for full inspection.
4. CSV values must be rendered as text, not HTML.

### 11.8 Snapshot Summary

Snapshot Summary displays immutable configuration from `run_snapshots`:

1. source type, name and revision;
2. Test Plan run mode when applicable;
3. Scenario count and item names when bounded;
4. Env Group name and variable count;
5. Dependency File count;
6. Load Settings summary;
7. SLA rule count and readable rules;
8. manual single-node resource request.

Rules:

1. Snapshot display uses immutable snapshot, not current mutable assets.
2. P0 does not show Generated YAML preview.
3. P0 does not show SSH credentials, runner token, MinIO credentials or object keys.
4. P0 should avoid dumping full Step bodies or script text into the report page by default.

### 11.9 Artifacts Section

Artifacts section displays:

1. collapsed header by default;
2. total artifact count;
3. badges for important artifacts: `artifacts.zip`, `final_stats_csv`, logs;
4. expandable list with filename, type, size, created time, terminal-late flag and Download action;
5. empty state when no artifacts exist;
6. unavailable state when storage is down.

Rules:

1. The section is collapsible to prevent long artifact lists from making the report page too long.
2. If artifact count is `0`, show the empty state directly.
3. If artifact count is small, implementation may still keep the list behind an explicit expand action for consistency.
4. Download uses API route and browser attachment download.
5. `artifacts_zip` download does not preview or extract contents.
6. Do not expose object key, bucket, MinIO endpoint, presigned URL or server path.

### 11.10 Nodes Section

Nodes section displays:

1. selected node name;
2. node scope / pool type;
3. current safe node state;
4. last known heartbeat / terminal relation if available.

Rules:

1. P0 has exactly one selected node per Run.
2. Do not add multi-node UI, node count controls or selected nodes list for multiple nodes.
3. Do not show credentials.

### 11.11 Validity Action UX

Rules:

1. Validity action is explicit and visible in Verdict Summary.
2. UI may use segmented control, select or buttons; current value must be clear.
3. Changing validity sends `PATCH /api/v1/runs/{runId}/validity`.
4. Show optimistic pending state only after mutation starts; reconcile with API response.
5. Repeating the same value should not show an error.
6. If mutation fails due to CSRF/session, follow global auth handling.
7. UI copy must clarify that Validity controls analysis inclusion and is not the same as execution success.

### 11.12 Polling

P0-07 follows `08` polling rules:

```text
- Poll only when state is initializing / running / stopping.
- Use refetchInterval = 5000.
- Use refetchIntervalInBackground = false.
- Stop polling immediately after terminal state.
- Terminal states: finished / failed / aborted.
- If terminal state is reached but summary is not ready, continue capped summary polling.
- Fallback summary polling interval: 5000-10000 ms.
- Fallback cap: max 12 attempts or 90 seconds, whichever comes first.
```

Rules:

1. Frontend must not infer terminal state from timeout.
2. Frontend must not release Load Node.
3. Frontend must not mark Run failed.
4. Backend state convergence belongs to Runner callback and api-worker.

---

## 12. Security, Permission, and Workspace Rules

### 12.1 Authentication and CSRF

Rules:

1. All public P0-07 APIs require authenticated browser session.
2. `GET` list/detail/artifact APIs do not require CSRF.
3. `PATCH /api/v1/runs/{runId}/validity` requires CSRF.
4. Internal runner artifact/callback endpoints continue using `x-runner-token`, not browser session.

### 12.2 Workspace Enforcement

Rules:

1. Run List filters by current Workspace.
2. Run Report lookup filters by current Workspace.
3. Artifact list filters by Run ID and current Workspace.
4. Artifact download validates Run and Artifact belong to current Workspace.
5. Validity mutation validates Run belongs to current Workspace.
6. Cross-Workspace resource IDs should return `RESOURCE_NOT_FOUND` where possible.

### 12.3 Authorization

Rules:

1. P0 `user` and `admin` can view Runs / Run Reports in current Workspace.
2. P0 `user` and `admin` can change validity for visible Runs in current Workspace.
3. No resource owner-only rule is introduced in P0.
4. Backend is authoritative; frontend route visibility is not security.

### 12.4 Sensitive Data

P0-07 responses, logs and audit details must not include:

1. SSH password, private key, passphrase or username-password pairs;
2. runner internal token;
3. session token or CSRF token;
4. MinIO endpoint, access key, secret key, bucket or object key;
5. server absolute path;
6. generated YAML preview;
7. raw stack trace;
8. unbounded stderr / stdout;
9. private key material inside snapshots.

Rules:

1. Artifact `relativePath` is safe display metadata, not storage object key.
2. Failure messages must be bounded and safe.
3. Audit details may include IDs, old/new validity values and request ID only.

### 12.5 Path and Artifact Safety

Rules:

1. Artifact upload path safety remains governed by 07.
2. Artifact download by `artifactId` must not accept user-supplied object keys or relative paths.
3. `artifacts_zip` is never extracted in P0.
4. Report HTML is not rendered inline in P0.
5. CSV values are rendered as escaped text.

### 12.6 Audit Events

P0-07 registers:

| Event type | Trigger | Required safe details |
| --- | --- | --- |
| `run.validity_changed` | Validity value changed | `runId`, `workspaceId`, `oldValidity`, `newValidity`, `requestId` when available. |

Rules:

1. Do not write audit event when PATCH is idempotent and value is unchanged.
2. Audit details must not include artifacts, object keys, Env values, Step bodies, script text or credentials.
3. P0 does not implement audit log UI.

---

## 13. Contract Rules

1. FastAPI routes and Pydantic schemas are OpenAPI source of truth.
2. `packages/contracts/openapi/api.openapi.json` must be generated, not handwritten.
3. Web client/types must be regenerated from OpenAPI.
4. Web imports generated client/types through `@surgepilot/contracts` only.
5. Internal runner endpoints remain excluded from Web generated client.
6. Public API JSON uses camelCase.
7. DB columns use snake_case.
8. Route path parameters use `{runId}` and `{artifactId}`, not bare `{id}`.
9. Artifact object keys are not public contract fields.
10. `failed_requests_csv` is not a P0 public API enum value or UI artifact type.
11. `artifacts_zip` must be added consistently to storage, runner callback details and API schemas when implementation begins.

---

## 14. Cross-Slice Handoff Contracts

### 14.1 P0-04 Handoff

P0-07 depends on P0-04 to provide:

1. safe Run state convergence;
2. `lastHeartbeatAt`;
3. `failureReason` / `failureMessage`;
4. `forcedConvergence`;
5. node lease release in terminal states;
6. artifact metadata ingest through API.

P0-07 must not modify P0-04 state transition rules.

### 14.2 P0-05 Handoff

P0-07 consumes `debug_scenario` Run Snapshots.

Rules:

1. Debug Run reports show `runType=debug`.
2. Debug Run reports show `validity=invalid` by default unless manually changed.
3. Debug Run reports show `slaResult=not_evaluated`.
4. Snapshot display uses scenario name/revision and safe execution summary.

### 14.3 P0-06 Handoff

P0-07 consumes `test_plan` Run Snapshots.

Rules:

1. Standard Run reports show saved `slaEvaluationMode`.
2. Test Plan Debug reports show `not_evaluated` SLA.
3. Standard Run with passfail outcome stores and displays `passed` or `failed`.
4. Snapshot display uses Test Plan name/revision, run mode, Scenario items, Load Settings, SLA count and manual selected node.
5. P0-07 does not expose Generated YAML preview.

### 14.4 P0-08 Handoff

P0-08 may consume:

1. Run List APIs;
2. `validity`;
3. `slaResult`;
4. terminal Run timestamps;
5. recent Runs summary;
6. artifact availability summary.

Rules:

1. Overview default statistics should include Valid Standard Runs unless a later SDD narrows the rule.
2. P0-08 must not count Invalid Runs in default statistics.
3. P0-08 must not add Monitoring / Grafana cards in P0.

---

## 15. Tests

### 15.1 API Unit Tests

Required coverage:

1. final stats parser parses total row and per-label rows;
2. final stats parser computes `failedRequests` and `errorRate`;
3. final stats parser treats Taurus `throughput` as total sample count, not TPS;
4. parser returns `FINAL_STATS_TOTAL_ROW_MISSING` or equivalent safe code when total row is missing;
5. parser bounds rows and sets `truncated=true`;
6. parser failure does not mutate Run state;
7. SLA result mapping preserves independence from Run state;
8. validity mutation is idempotent for unchanged value;
9. validity mutation updates actor/time and audit only when value changes.

### 15.2 API Integration Tests

Required coverage:

1. `GET /api/v1/runs` returns only current Workspace Runs;
2. Run List filters by state, validity, runType and sourceType;
3. Run List cursor pagination is stable;
4. `GET /api/v1/runs/{runId}` returns report sections for terminal Run;
5. active Run report returns pending / missing summaries without state mutation;
6. cross-Workspace Run detail returns `RESOURCE_NOT_FOUND` or access-safe error;
7. artifact list hides non-current Workspace artifacts;
8. artifact download streams available artifact;
9. artifact download rejects unavailable artifact with `ARTIFACT_NOT_READY`;
10. artifact download does not expose object key;
11. `artifacts_zip` can be listed and downloaded as download-only;
12. `failed_requests_csv` is not accepted by P0 public artifact filters;
13. validity PATCH requires CSRF;
14. validity PATCH rejects cross-Workspace Run;
15. validity PATCH writes `run.validity_changed` audit event.

### 15.3 Contract Tests

Required coverage:

1. OpenAPI includes Run List, Run Report, artifact list, artifact download and validity endpoints;
2. public schemas include `SlaResult`, `RunValidity`, `RunArtifactType`;
3. public artifact enum includes `artifacts_zip`;
4. public artifact enum excludes `failed_requests_csv` in P0;
5. internal runner endpoints do not enter Web generated client;
6. generated Web client/types are fresh;
7. path params are `{runId}` and `{artifactId}`.

### 15.4 Web Tests

Required coverage:

1. Run List renders empty state;
2. Run List renders filters and rows;
3. Run Report renders Verdict Summary before Artifacts;
4. KPI cards show `N/A` with missing reason;
5. Failure Diagnostics does not render failed requests preview in P0;
6. Artifacts section is collapsible and shows artifact count;
7. expanded artifact list renders download actions;
8. `artifacts_zip` is displayed as download-only;
9. Validity mutation sends CSRF and updates UI from response;
10. active Run polling stops after terminal response;
11. terminal summary fallback polling stops at cap;
12. no Monitoring / Grafana / Schedule / Generated YAML links appear.

### 15.5 Runner / Smoke Tests

Required coverage:

1. fake runner smoke can upload `run_log` and still produce a report with missing KPI state;
2. runner artifact upload can accept `artifacts_zip` after implementation updates the artifact contract;
3. real or near-real Runner smoke uploads `final_stats_csv` when Taurus final stats CSV is produced;
4. artifact callback remains idempotent and does not change Run state;
5. terminal callback with `details.slaResult` stores SLA result without changing Run state.

---

## 16. Verification Commands

After API schema changes:

```bash
make generate-contracts
```

Minimum Slice verification during implementation:

```bash
uv run --all-packages pytest apps/api/tests -k "run_report or artifacts or validity or final_stats"
uv run --all-packages pytest tests/contract -k "runs or artifacts or openapi"
pnpm --filter @surgepilot/web test -- --run
```

Repository verification before claiming Slice completion:

```bash
make verify
```

E2E / release validation when environment supports it:

```bash
make verify-e2e
```

Rules:

1. If `make verify` is temporarily unavailable during implementation, run the closest subset and state the gap.
2. Contract freshness checks must pass after public API schema changes.
3. Real SSH / Taurus smoke remains required for final P0 acceptance where environment profile supports it.

---

## 17. Done When

P0-07 is done when:

1. Run List API returns current Workspace Runs with cursor pagination and filters.
2. Run List UI lets users enter Run Report and does not expose P1/P2 navigation.
3. Run Report API returns Verdict, KPI, Failure Diagnostics, Final Stats, Snapshot, Artifacts Summary and Nodes sections.
4. Run Report UI renders Verdict first and keeps Artifacts in a collapsible section.
5. Status, SLA Result and Validity are stored and displayed as independent concepts.
6. `final_stats_csv` summary is parsed into bounded report data.
7. Required KPI cards always render and show `N/A` with reason when data is missing.
8. P0 does not parse or display `failed_requests.csv`.
9. `artifacts_zip` is supported as a download-only artifact type.
10. Artifact list and download are Workspace-aware and never expose MinIO object keys or credentials.
11. Validity can be switched Valid / Invalid with CSRF and audit coverage.
12. Run Report polling follows active-state and terminal fallback caps.
13. Web uses generated `@surgepilot/contracts` client/types.
14. OpenAPI and generated contracts are fresh.
15. API, contract, Web and runner tests listed in §15 pass.
16. `make verify` passes or a documented environment limitation is stated with the closest passing subset.
17. No P1/P2 user-visible capability is introduced.

---

## 18. Review Checklist

### 18.1 Scope

- [ ] Does the change stay inside P0-07 plus required Foundation alignment?
- [ ] Does it avoid failed requests plugin preview in P0?
- [ ] Does it avoid Monitoring, Grafana, InfluxDB, Schedule, multi-node, API Catalog and Generated YAML preview?
- [ ] Does it avoid turning Run Report into a generic artifacts file manager?

### 18.2 Contracts

- [ ] Are FastAPI/Pydantic schemas the source of OpenAPI?
- [ ] Were contracts generated after API changes?
- [ ] Does Web import generated types through `@surgepilot/contracts`?
- [ ] Are internal runner endpoints excluded from Web client?
- [ ] Does `artifacts_zip` appear consistently where P0 artifact types are declared?
- [ ] Is `failed_requests_csv` excluded from P0 public API/UI?

### 18.3 Report Semantics

- [ ] Are Status, SLA Result and Validity independent?
- [ ] Does `finished` not imply `slaResult=passed`?
- [ ] Does `failed` / `aborted` not imply `validity=invalid`?
- [ ] Do missing KPI values show `N/A` with reason?
- [ ] Does parser failure avoid changing Run state?

### 18.4 Artifacts and Storage

- [ ] Are artifact list and download Workspace-aware?
- [ ] Are MinIO object keys hidden from API, Web, logs and audit details?
- [ ] Is `artifacts_zip` download-only with no extraction?
- [ ] Are downloads attachment and no-store?
- [ ] Does download stream rather than buffering whole artifact?

### 18.5 Security

- [ ] Does validity mutation require CSRF?
- [ ] Are auth and Workspace checks enforced in backend?
- [ ] Are credentials, tokens, MinIO secrets and server paths excluded?
- [ ] Are audit details safe and bounded?

### 18.6 Frontend

- [ ] Is Verdict Summary first?
- [ ] Is Artifacts collapsible?
- [ ] Does active polling stop on terminal state?
- [ ] Is fallback summary polling capped?
- [ ] Are P1/P2 links absent?

### 18.7 Verification

- [ ] Did API tests pass?
- [ ] Did contract tests pass?
- [ ] Did Web tests pass?
- [ ] Did runner artifact / callback tests pass?
- [ ] Did `make generate-contracts` pass after API changes?
- [ ] Did `make verify` pass or is the exact gap documented?

---

## 19. Implementation Backfill

After P0-07 implementation, update this section only for engineering facts:

1. exact migration filenames;
2. exact API schema names if they differ from examples;
3. exact parser bounds;
4. exact test files and commands;
5. accepted implementation differences from this SDD;
6. remaining risks for P0-08.

Do not use backfill to add P1/P2 scope.

### 19.1 Implementation Facts

- Migration added: `apps/api/migrations/versions/0008_p0_07_run_reports.py`.
- Public API schema names match this SDD: `RunListResponse`, `RunListItem`, `RunReportDetail`, `RunArtifactListResponse`, `RunArtifactItem`, `RunValidityPatchRequest`, `RunValidityPatchResponse`, `SlaResult`, `RunValidity`, `RunArtifactType`, and `ReportSummaryStatus`.
- `RunSnapshotSummary` now exposes bounded structured snapshot details for P0 traceability: `scenarioItems[].loadSettings` including `delaySeconds`, `slaRules[]`, `dependencyFileNames`, and `envGroupVariableKeys`. Env Group values and generated YAML remain hidden, and malformed legacy snapshot display values are safely omitted instead of failing report rendering.
- Final stats parser bounds: maximum `2 MiB` CSV input and maximum `200` preview rows in `run_report_summaries.summary_json.rows`.
- Parser implementation stores a `pending` summary row when a `final_stats_csv` artifact is ingested; `api-worker` claims pending summaries, streams the source artifact through the bounded parser, and stores `parsed` / `failed` status without mutating Run state, SLA result, or validity.
- Parser implementation treats non-finite numeric tokens such as `NaN` and `Inf` as invalid values and records warnings rather than letting the worker fail.
- P0 artifact enum now includes `artifacts_zip` and excludes `failed_requests_csv` from public API schemas, generated Web client, Runner callback schema, and Runner upload candidates.
- Runner skips any artifact above a hard `200 MiB` upload limit before reading bytes, matching the P0 API artifact size boundary. It also skips `artifacts_zip` above `SURGEPILOT_RUNNER_ARCHIVE_MAX_BYTES` (default `50 MiB`, clamped to the hard limit) to avoid buffering very large archive files in memory; smaller P0 artifacts continue through the existing API-mediated upload path.
- Added tests:
  - `apps/api/tests/test_p0_07_migrations.py`
  - `apps/api/tests/test_p0_07_final_stats.py`
  - `apps/api/tests/test_p0_07_run_report_api.py`
  - `tests/contract/test_p0_07_run_report_openapi.py`
  - `apps/web/src/features/runs/runs.test.tsx`
  - updated `apps/runner/tests/test_cli.py`
- Targeted verification commands used during implementation:
  - `uv run --all-packages pytest apps/api/tests -k "run_report or artifacts or validity or final_stats"`
  - `uv run --all-packages pytest tests/contract -k "runs or artifacts or openapi"`
  - `pnpm --filter @surgepilot/web test -- --run apps/web/src/features/runs/runs.test.tsx`
  - `uv run --all-packages pytest apps/runner/tests`
  - `make generate-contracts`
- Accepted implementation detail: artifact ingest creates a pending summary row but does not synchronously read MinIO during upload; `api-worker` performs the bounded parse from storage. Raw artifact download remains available regardless of parser status.
- Remaining P0-08 handoff risk: Overview consumers should treat `validity`, `slaResult`, and Run `state` as independent fields and exclude Invalid Runs from default statistics as stated in §14.4.
