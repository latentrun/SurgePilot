# P1-08 Debug HTTP Trace

- Document status: Accepted for implementation
- Stage: P1
- Capability:`debug_http_trace`
- Scope ADR:`docs/sdd/adr/ADR-0008-p1-debug-http-trace.md`
- Scope Gate:`docs/sdd/00-product-scope-and-priority.md` §6
- P1 Index:`docs/sdd/slices/P1-README.md`
- Runtime Boundary:`docs/sdd/p0-runtime-bootstrap-plan.md` §4/§7/§10
- Optional local Taurus reference: ignored `docs/reference/taurus/JMeter.md` JSR223 Blocks section, if present; otherwise use the upstream Taurus/JMeter documentation.

## 1. Goal

Display HTTP Trace in the Run Report of Debug Run: Each HTTP Request in this debug execution is sent at most once, and the complete controlled details of each request/response are displayed to help users troubleshoot body mismatches, env variable errors, authentication failures, URL errors, and response exceptions.

## 2. PRD / Scope Trace

This ability is not an item in the original P1 fixed list and has been included as an additional P1 ability through `ADR-0008`. It is part of the Run Report diagnostic experience enhancement and not part of the Monitoring, Backend Listener, InfluxDB/Grafana, Universal Log Search, Universal Masking Framework, or Standard Run failed_requests/finalstats previews.

This Slice must comply with:

1. P1 boundary of `docs/sdd/00-product-scope-and-priority.md` §6;
2. `docs/sdd/slices/P1-README.md` Revision Protocol;
3. `docs/sdd/05-runner-protocol-and-run-state-machine.md` artifact ingest and terminal-late boundaries;
4. `docs/sdd/07-storage-artifacts-minio.md` MinIO prefix, path safety, artifact type whitelist and preview boundaries;
5. `docs/sdd/p0-runtime-bootstrap-plan.md` runtime tar and Runner `bzt -n` boundaries.

## 3. In Scope

1. Debug Scenario Run:`runType=debug`, `sourceType=debug_scenario`.
2. Test Plan debugging state: `runType=debug`, `sourceType=test_plan`.
3. Single node, single concurrency, each HTTP request is sent at most once.
4. When the API/worker generates the execution bundle, only JSR223 `script-text` is inlined in the Debug Taurus YAML.
5. Added artifact type: `debug_http_trace`.
6. JSONL trace field:
   - `schemaVersion`
   - `sequence`
   - `label`
   - `url`
   - `method`
   - `requestHeaders`
   - `requestBody`
   - `responseStatus`
   - `responseHeaders`
   - `responseBody`
   - `durationMs`
   - `error`
   - `bodyTruncated`
   - `traceTruncated`
7. Run Report API adds nullable `debugHttpTrace`.
8. Web Run Report displays the `HTTP Trace` sub-block near Failure Diagnostics.
9. Debug trace directional desensitization, truncation, size control and secondary API verification.
10. Added API/Web/contract/runner-adjacent bundle snapshot/e2e acceptance test.

## 4. Out of Scope

1. Standard Run request/response full record.
2. JMeter plug-in, Backend Listener, Monitoring, InfluxDB, Grafana.
3. Universal logs, universal desensitization framework, and log search.
4. Upload or display full JTL without desensitization.
5. Runtime tar content, `metadata.json`, runtime sha256, and init process changes.
6. Independent `.groovy` file SFTP delivery, global script/plugin directory, `~/.bzt-rc`.
7. Large file paging, trend analysis, ZIP/TAR/TGZ unpacking.
8. Editable Taurus YAML.
9. API Catalog, OpenAPI import, OpenAPI Step automatic generation, Schedule Run, Scheduled Job, product Help.

## 5. Preconditions

The following preconditions are completed in this Slice and used as implementation input:

1. ADR Revision: `ADR-0008` accepts `debug_http_trace` as P1 additional ability.
2. Scope Sync: Synchronize `00`, `02`, `AGENTS.md` and `P1-README`.
3. Foundation Sync: Synchronize the artifact whitelist and terminal-late boundaries of `05`; synchronize the artifact type, preview, and storage boundaries of `07`.
4. Runtime Boundary: Explicitly do not modify the P0 runtime tar, metadata, sha256 or init process.
5. Taurus Injection Boundary: Groovy vector is fixed as Taurus YAML inline `jsr223.script-text`.

## 6. Architecture

```text
API/worker bundle generation
  -> for Debug Run only, build surgepilot.yml with inline JSR223 PostProcessor
  -> Runner executes ${RUNNER_HOME}/current/bin/bzt -n surgepilot.yml
  -> JMeter writes artifacts/debug-http-trace.jsonl with sanitized bounded JSONL
  -> Runner uploads debug_http_trace artifact before terminal callback
  -> API stores artifact via MinIO path-safe run-artifacts prefix
  -> API Run Report reads/parses/sanitizes bounded trace
  -> Web renders HTTP Trace without object key exposure
```

The Runner remains an independent app and does not import API internals. The Web uses generated contracts through `@surgepilot/contracts` and never accesses MinIO directly.

## 7. Bundle / YAML Design

Debug trace injection happens in the API/worker bundle builder only.

Rules:

1. `runType=standard` MUST NOT inject trace JSR223.
2. `runType=debug` and `sourceType in (debug_scenario, test_plan)` MUST inject trace JSR223 at the Taurus scenario/request level so it runs after each HTTP sampler.
3. The injected script MUST be inline `script-text` with `language: groovy`, `execute: after`.
4. The generated YAML MUST keep `modules.jmeter.path` pointed at the selected Load Node runtime JMeter path and continue using Runner `bzt -n`.
5. No standalone Groovy file is added to the bundle.
6. `surgepilot.yml` snapshots MUST prove YAML escaping and indentation remain valid.

Loop/control policy for this Slice:

- Debug Scenario and debug Test Plan execution uses the existing debug load settings normalized to one concurrency and one iteration.
- This Slice does not add complex loop/if/foreach execution semantics. If a future Slice introduces complex flow control, it must define how trace sequence and "each request once" are enforced.

## 8. Artifact Contract

Artifact type:

```text
debug_http_trace
```

Default relative path:

```text
artifacts/debug-http-trace.jsonl
```

Upload rules:

1. Uses existing `POST /api/internal/v1/runner/artifacts`.
2. Uses existing `run-artifacts/{workspaceId}/{runId}/{relativePath}` object key rule.
3. Must pass existing runner token, Run/node binding, path, hash and size validation.
4. Must be uploaded before terminal callback if present.
5. Must not rely on terminal-late artifact acceptance.
6. Object key is never returned to Web.

Limits:

| Config | Default | Purpose |
| --- | ---: | --- |
| `SURGEPILOT_DEBUG_TRACE_MAX_REQUESTS` | `100` | maximum trace entries |
| `SURGEPILOT_DEBUG_TRACE_BODY_MAX_BYTES` | `65536` | maximum request or response body preview bytes |
| `SURGEPILOT_DEBUG_TRACE_ARTIFACT_MAX_BYTES` | `10485760` | maximum debug trace artifact size |

## 9. API Contract

`RunReportDetail` adds:

```json
{
  "debugHttpTrace": null
}
```

When available:

```json
{
  "debugHttpTrace": {
    "status": "available",
    "sourceArtifactId": "01...",
    "entryCount": 2,
    "traceTruncated": false,
    "warnings": [],
    "entries": [
      {
        "sequence": 1,
        "label": "GET /login",
        "method": "GET",
        "url": "https://example.test/login",
        "requestHeaders": {"Authorization": "[REDACTED]"},
        "requestBody": {"contentType": "application/json", "text": "{}", "bodyTruncated": false},
        "responseStatus": 401,
        "responseHeaders": {"Set-Cookie": "[REDACTED]"},
        "responseBody": {"contentType": "application/json", "text": "{\"error\":\"unauthorized\"}", "bodyTruncated": false},
        "durationMs": 123,
        "error": null
      }
    ]
  }
}
```

Unavailable states:

- `null` for Standard Run.
- `null` for active Debug Run before artifact upload.
- `{ "status": "unavailable", ... }` for terminal Debug Run when artifact is missing, malformed, too large or parse failed.

API parser rules:

1. Read at most `SURGEPILOT_DEBUG_TRACE_ARTIFACT_MAX_BYTES + 1` bytes.
2. Reject oversized trace preview as unavailable with a safe warning.
3. Parse JSONL line-by-line with a max of `SURGEPILOT_DEBUG_TRACE_MAX_REQUESTS` entries.
4. Apply second-pass debug-trace sanitizer.
5. Ignore unknown line fields.
6. Never return storage bucket/object key.

## 10. Sanitization and Body Rules

Header redaction names are case-insensitive and include exact names `authorization`, `cookie`, `set-cookie`, `x-api-key`, plus any name containing `token`, `password`, `secret`, or `key`.

Body redaction applies to JSON object keys and form keys containing `token`, `password`, `secret`, or `key`.

Allowed body preview classes:

- `application/json`
- `text/*`
- XML
- `application/x-www-form-urlencoded`
- multipart text parts only when already represented as text by JMeter

Binary-like content is represented as metadata only:

```json
{"contentType":"application/octet-stream","sizeBytes":1024,"sha256Prefix":"abcdef123456"}
```

## 11. Web UX

Run Report keeps `Failure Diagnostics` unchanged for failure summaries. A new `HTTP Trace` block appears near it.

UI behavior:

1. Standard Run: no HTTP Trace block.
2. Debug Run active with no trace yet: lightweight empty state.
3. Debug Run terminal with unavailable trace: safe warning and download-artifacts hint.
4. Available trace: compact list with method, URL, response status and duration.
5. Each row expands to request headers/body and response headers/body.
6. Copy actions copy only API-returned sanitized text.
7. MinIO key and server path are never shown.

## 12. Stability / Security Requirements

1. Workspace and permission checks remain backend-enforced.
2. Artifact path validation continues to use 07 safe relative path rules.
3. Private Load Node credentials and env values must not be returned in plaintext.
4. Trace upload or parse failure must not alter Run terminal state, SLA result, validity, node lease or Stop behavior.
5. Late terminal callbacks must not overwrite terminal Run state.
6. Load Nodes must not remain Busy because debug trace upload/parse failed.

## 13. Tests

Minimum tests:

1. API unit tests for debug trace JSONL parser: redaction, truncation, malformed lines, binary body metadata, max requests.
2. API artifact tests: `debug_http_trace` accepted, unknown types still rejected, path safety unchanged.
3. API Run Report tests: Debug Run returns parsed `debugHttpTrace`; Standard Run returns `null`; malformed/oversized artifact returns unavailable safe summary.
4. Bundle/YAML tests: Debug Scenario and Debug Test Plan include inline JSR223; Standard Run excludes it; YAML snapshot covers indentation/escaping.
5. Contract tests: OpenAPI includes `debugHttpTrace` and generated client is fresh.
6. Web component tests: HTTP Trace block rendering, expanded details, Standard Run hidden state, unavailable state.
7. E2E acceptance: seeded or fake-runner flow opens Run Report and verifies sanitized HTTP Trace details are visible while secrets and object keys are not.

## 14. Done When

This Slice is complete only when:

1. ADR/scope/foundation docs are synchronized.
2. `debug_http_trace` artifact type is accepted only through the documented artifact path.
3. Debug-only YAML injection exists and Standard Run has no trace injection.
4. Run Report API exposes nullable `debugHttpTrace` from generated OpenAPI/contracts.
5. Web consumes generated contracts and renders HTTP Trace as documented.
6. New E2E acceptance test passes.
7. `make generate-contracts` passes.
8. `make verify` passes.
9. Relevant e2e command passes or its environment gap is explicitly recorded.
10. Independent review finds no remaining Slice-blocking issues.

## 15. Implementation Backfill

Implemented engineering facts:

1. ADR-0008 accepted `debug_http_trace` as a scoped P1-08 addition outside the original P1 fixed preview list.
2. API added `SURGEPILOT_DEBUG_TRACE_MAX_REQUESTS`, `SURGEPILOT_DEBUG_TRACE_BODY_MAX_BYTES`, and `SURGEPILOT_DEBUG_TRACE_ARTIFACT_MAX_BYTES`.
3. API stores the final artifact object key as `run-artifacts/{workspaceId}/{runId}/{relativePath}`. To preserve object integrity without streaming uploads inside a DB transaction, upload first writes an internal `.tmp/{artifactId}/...` object, then promotes it to the canonical key under the post-upload DB lock. Commit failures after promotion trigger best-effort canonical object cleanup.
4. API parser and inline Groovy both apply targeted debug-trace redaction for headers, URLs, JSON/form bodies, malformed JSON-like text, and label/error free text.
5. Raw `debug_http_trace` artifacts are internal report inputs: they are not exposed in the public artifact list and are not downloadable through the generic raw artifact endpoint.
6. Runner executes Taurus as `bzt -n surgepilot.yml` and uploads `debug_http_trace` before archive/final-stats candidates.
7. Web renders HTTP Trace only for supported Debug Run sources and copy actions use API-returned sanitized text.

Verification commands added or used:

- `make generate-contracts`
- `make verify`
- `make verify-p1-08-debug-http-trace-e2e`

R11 reconstruction verification backfill:

1. Focused API parser coverage is recorded in `apps/api/tests/test_p1_08_debug_http_trace.py` for targeted redaction, malformed JSONL, request limits, artifact limits, and binary metadata handling.
2. OpenAPI boundary coverage is recorded in `tests/contract/test_p1_08_debug_http_trace_openapi.py`; internal trace artifact types remain absent from the public artifact enum and Runner routes remain absent from the Web contract.
3. Web Run Report polling behavior is covered in `apps/web/src/features/runs/run-report.test.tsx`, while the E2E acceptance shape is recorded in `tests/e2e/p1_08_debug_http_trace.spec.ts`.
4. This reconstruction checkpoint exposes Debug Run HTTP Trace only. Monitoring, multi-node allocation, Workspace/Admin surfaces, and P2 navigation/API are intentionally not introduced by R11.

Remaining risks:

1. Inline Groovy is covered by YAML structure/string tests but not by a real JMeter/Groovy execution test in the default verification gate.
2. Debug trace redaction is intentionally targeted to this artifact and is not a general-purpose log/secret sanitization framework.

## 16. Large Body Guard Addendum

This section serves as a large-body patch for Debug HTTP Trace and is strictly limited to Debug Run HTTP Trace. It does not change Standard Run, does not modify P0 runtime tar, does not introduce JMeter plug-ins, Backend Listener, Monitoring, new middleware or general log/desensitization/preview framework.

### 16.1 Goals

1. Prevent oversized base64, long HTML, overlong JSON string or binary content without Content-Type in the response body from causing JSONL single-line expansion, API parsing OOM or web lag.
2. Keep the small body experience without regression: still display inline and desensitized text.
3. Only return a small preview for large text; use Debug-only sidecar artifact for large bodies that are downloadable but not suitable for inlining; only retain meta information and drop reason for bodies that are too large or unsafe for display.
4. The Web does not touch the MinIO key and only downloads the sidecar through API authorization.

### 16.2 Body Storage State

`DebugHttpTraceBody` Extended status field:

| Field | Values / Meaning |
| --- | --- |
| `bodyStorage` | `inline`, `truncated`, `sidecar`, `dropped` |
| `text` | Compatibility field, used only for inline/truncated masked previews |
| `inlinePreview` | Same as `text`, used for new UI semantics |
| `bodyTruncated` | When the preview is not a complete body, it is `true`, compatible with the old semantics |
| `sizeBytes` | inline/truncated/dropped is the observed body bytes; sidecar is the actual stored sanitized sidecar bytes |
| `sha256Prefix` | 16 hex chars; only used for troubleshooting/deduplication prompts, not as integrity check |
| `downloadArtifactId` | sidecar corresponds to artifact id; does not expose object key |
| `dropReason` | `body_too_large` , `binary_body` , `sidecar_budget_exceeded` , `line_too_large` etc. |

### 16.3 Limits

| Config | Default | Purpose |
| --- | ---: | --- |
| `SURGEPILOT_DEBUG_TRACE_MAX_REQUESTS` | `100` | maximum trace entries |
| `SURGEPILOT_DEBUG_TRACE_BODY_MAX_BYTES` | `65536` | inline/truncated preview bytes |
| `SURGEPILOT_DEBUG_TRACE_RECORD_MAX_BYTES` | `131072` | maximum JSONL line bytes after body guarding |
| `SURGEPILOT_DEBUG_TRACE_ARTIFACT_MAX_BYTES` | `10485760` | maximum JSONL trace artifact bytes |
| `SURGEPILOT_DEBUG_TRACE_BODY_BLOB_MAX_BYTES` | `5242880` | maximum one sidecar body blob |
| `SURGEPILOT_DEBUG_TRACE_BODY_BLOB_TOTAL_MAX_BYTES` | `20971520` | maximum sidecar bytes per trace |

`record_max_bytes` can be larger than `body_max_bytes` because the record also contains headers, URL, status, duration, and meta-information. If the record still exceeds the limit, the collection side downgrades it to a synthetic error record; the API side skips overlong lines and adds a warning without throwing 500.

### 16.4 Artifact Contract

Added internal-only artifact type:

```text
debug_http_body_blob
```

Relative path:

```text
artifacts/debug-http-body-blobs/{sequence}-{request|response}.bin
```

Rules:

1. Only Debug Run and `sourceType in (debug_scenario, test_plan)` can be uploaded.
2. Must be uploaded before terminal callback.
3. Do not enter public artifact enum/list/filter/count.
4. The public artifact download endpoint still rejects this type.
5. Added Run Report dedicated download endpoint: `GET /api/v1/runs/{runId}/debug-http-body-blobs/{artifactId}/download`, which uses the API to verify the workspace/run/artifact type and proxy the MinIO stream.
6. `debugHttpTrace` only returns `downloadArtifactId`/metadata, not bucket/object key.

### 16.5 Collector Rules

Inline JSR223 `script-text` does byte-level early decision for each request/response body:

1. Obvious binary or no Content-Type and strict UTF-8 sniff fails: do not inline, log `bodyStorage=dropped` , `dropReason=binary_body` , retain `sizeBytes/sha256Prefix/contentType` .
2. Text/JSON/XML/form is less than `body_max_bytes`: the inline desensitized full text, `bodyStorage=inline`.
3. The text exceeds `body_max_bytes` and does not exceed the sidecar unit/total amount: write sanitized sidecar bytes, JSONL only writes the desensitized prefix, `bodyStorage=sidecar`, `downloadRelativePath`, and `sizeBytes/sha256Prefix` describing the actual sidecar bytes; do not write object key.
4. The text exceeds the sidecar unit or total amount: do not write sidecar, `bodyStorage=dropped`, `dropReason=body_too_large` or `sidecar_budget_exceeded`.
5. JSONL lines must be within `record_max_bytes`; when the limit is exceeded, preview is removed and marked `bodyStorage=dropped`, `dropReason=line_too_large`.

### 16.6 API Parser Rules

1. Read trace artifacts using line-by-line bounded parser instead of reading the entire artifact at once.
2. First do `record_max_bytes` guard for each line, and then JSON decode.
3. Make upper limit control on the number of entries, total read bytes, and parse warnings; if any limit is exceeded, partial trace + warnings will be returned, and 500 will not be returned.
4. Perform secondary directional desensitization and state normalization on body.
5. The API searches for the `debug_http_body_blob` artifact in the same run based on `downloadRelativePath` and maps it to `downloadArtifactId`; if not found, it downgrades to `bodyStorage=dropped`, `dropReason=sidecar_missing`.
6. The API does not return MinIO key and does not directly expose raw trace.

### 16.7 Web UX

1. `inline`: Display desensitized text directly.
2. `truncated`: Display prefix and "Preview truncated" prompt; copy only copies the current preview.
3. `sidecar`: Display size, content type, sha prefix, preview (if existing) and "Download sanitized body" link; do not automatically load the full amount, do not copy sidecar with one click.
4. `dropped`: Displays drop reason and meta information, but does not provide downloading.
5. Use folding and `<pre>` lazy rendering for large text; do not put all sidecars into the DOM.

### 16.8 Tests

Large body acceptance must cover:

1. API parser line-by-line guard for an overlong JSONL line.
2. Sidecar mapping from `downloadRelativePath` to `downloadArtifactId` without object key exposure.
3. Sidecar download endpoint authorization/path/type safety.
4. Groovy snapshot proves body blob thresholds, sidecar path, record max guard and no object key leakage.
5. Web renders sidecar/dropped/truncated body states and download link without copying sidecar full body.
6. E2E seeds a large sanitized response body sidecar artifact and verifies Run Report shows summary/download link and no raw secret/object key.
