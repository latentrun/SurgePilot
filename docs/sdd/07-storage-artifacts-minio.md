# 07. Storage, Artifacts, and MinIO

## Decision and boundary

MinIO is the only initial object storage backend. PostgreSQL stores authoritative metadata and permissions; MinIO stores bytes. API is the only application component with MinIO credentials.

```text
Web -> API -> PostgreSQL metadata
          `-> MinIO bytes

Runner -> internal API -> PostgreSQL metadata
                       `-> MinIO bytes
```

Web and Runner never receive bucket credentials, object keys, or browser-visible presigned URLs. Upload and download stream through API after authentication, Workspace, reference, size, hash, and path checks.

## Object layout

The initial bucket is `surgepilot`.

```text
dependency-files/{workspaceId}/{fileId}/{safeFilename}
run-artifacts/{workspaceId}/{runId}/{relativePath}
```

Object keys are internal and never appear in browser API responses. Metadata IDs and Workspace ownership, not object existence, grant access.

## Path and transfer safety

Filenames and artifact relative paths use a strict ASCII allowlist and are rejected rather than normalized. Absolute paths, empty segments, `.` or `..`, backslashes, control characters, ambiguous separators, and unexpected extensions are rejected. Downloads use attachment disposition and private no-store caching.

API streams content while enforcing configured size limits and computing SHA-256. Runner artifact registration deduplicates by event and rejects a different object for an existing `(runId, relativePath)`. Late diagnostic artifacts may be accepted only within a bounded post-terminal policy and never change terminal Run state.

### Artifact whitelist and P1-08 trace boundary

The public Run artifact whitelist is:

```text
taurus_log
jmeter_log
final_stats_csv
run_log
artifacts_zip
```

P1-08 adds two scoped internal ingest types, and only for the supported Debug Run sources: `debug_http_trace` and `debug_http_body_blob`. The trace is an internal JSONL report input. The body blob is an internal-only sanitized request/response sidecar for large text bodies. Neither type is exposed through the public artifact whitelist, enum, list, filter, or count. `debug_http_trace` is not exposed through the generic raw artifact download surface; `debug_http_body_blob` is downloadable only through the dedicated Run Report route after API workspace, Run, artifact-type, and permission checks. Neither flow exposes a MinIO object key to Web. Unknown artifact types remain rejected.

Both `debug_http_trace` and `debug_http_body_blob` must be uploaded before the Run terminal callback whenever present. They must not rely on terminal-late acceptance. Trace or body-sidecar upload/parse failure must not alter Run terminal state, verdict, SLA result, node lease or Stop behavior.

### Terminal-late artifact boundary

Before terminal state, an artifact is accepted only after the normal Runner-token, Run/node binding, type, path, size and hash checks pass. After terminal state, API may accept diagnostic artifacts only within five minutes of `endedAt`, with both declared and actual size below 1MB. These artifacts are marked `terminal_late` and never change Run state or other terminal facts. Uploads outside that window, or terminal-late uploads at or above the limit, return `409 RUN_TERMINAL_STATE`; validation failures independent of terminal timing retain their specific errors. The P1-08 internal types are pre-terminal only and are not admitted by this terminal-late path.

## Initial behavior

Dependency Files support upload, list, download, and deletion protection. Run Artifacts support Runner upload, metadata listing, download, and structured summary extraction for recognized final statistics. The application checks bucket readiness but does not mutate bucket policy or require versioning, lifecycle, or server-side encryption settings.

Local filesystem storage, additional object stores, direct-to-MinIO browser flows, archive extraction, inline file editing, Range downloads, retention automation, quotas, and storage plugins are outside the initial milestone.
