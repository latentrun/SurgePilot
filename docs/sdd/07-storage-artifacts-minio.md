# 07 Storage, Artifacts, and MinIO

- Documentation status: v1 Frozen
- Project: SurgePilot performance load testing platform
- Document location: `docs/sdd/07-storage-artifacts-minio.md`
- Product source: `docs/prd/PRD.md`
- Range constraint: `docs/sdd/00-product-scope-and-priority.md`
- Architecture source: `docs/sdd/01-architecture-overview.md`
- API contract source: `docs/sdd/04-api-contract-guidelines.md`
- Runner Source: `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- Security source: `docs/sdd/06-security-permission-workspace.md`
- Current delivery target: P1 governance start / P1 Slice kickoff; P1-08 Debug HTTP Trace is only activated through ADR-0008 and the corresponding Slice SDD
- Scope of application: Foundation SDD, Dependency File Slice, Run / Run Report Slice, Runner artifact upload, API / api-worker, Web client, AI Coding, code review, test acceptance

---

## 1. Purpose

This article defines the object storage, Dependency File, Run Artifact, MinIO access, path security, download proxy, CSV artifact parsing and minimal audit rules for the SurgePilot P0 phase.

This article only answers the global storage baseline question:

1. Why P0 only uses MinIO, and the boundaries between Web, API, Runner and MinIO;
2. The composition of `surgepilot` bucket, object prefix and object key;
3. Upload, download, metadata, permissions and Workspace rules of Dependency File and Run Artifact;
4. Strict verification algorithm of `safeFilename` and `relativePath`;
5. Idempotence, hash verification, terminal-late rules and CSV summary boundaries for artifact upload;
6. P0 does not do preview, cache, life cycle, quota and object storage expansion.

This article does not define complete page interactions, complete endpoint request / response schema, complete DB migration, Run state machine, complete report UI, or specific code organization.

Enter the specific content:

- `docs/sdd/slices/P0-02-*.md` or equivalent Dependency File Slice: Dependency File page, endpoint, request / response, reference relationship and deletion protection;
- `docs/sdd/slices/P0-06-*.md` or equivalent Run / Run Report Slice: Artifacts area of Run Report, CSV summary display, Failure Diagnostics, Final Stats, Done When;
- `docs/sdd/slices/P0-07-*.md` or equivalent Storage implementation Slice: specific table structure, index name, adapter class, test fixture and implementation steps;
- `docs/sdd/09-testing-and-acceptance-strategy.md` : Cross-module test matrix and CI rules.

---

## 2. Authority and Conflict Resolution

### 2.1 Canonical Inputs

This article relies on the following documents:

1. `docs/prd/PRD.md`: The only product source for product scope, terminology, priorities and user mindset;
2. `docs/sdd/00-product-scope-and-priority.md`: P0/P1/P2 scope gate;
3. `docs/sdd/01-architecture-overview.md`: MinIO bucket, prefix, component boundary;
4. `docs/sdd/04-api-contract-guidelines.md`: REST, error response, artifact registration, upload/download API rules;
5. `docs/sdd/05-runner-protocol-and-run-state-machine.md`: Runner artifact upload, artifact type whitelist, terminal-late rules;
6. `docs/sdd/06-security-permission-workspace.md`: Workspace, permissions, sensitive values, audit, error code baseline.

### 2.2 Conflict Resolution

Conflict handling rules:

1. If this article conflicts with `docs/prd/PRD.md`, the PRD shall prevail.
2. If this article conflicts with `docs/sdd/00-product-scope-and-priority.md`, 00 shall prevail unless 00 conflicts with PRD.
3. If this article conflicts with `docs/sdd/01-architecture-overview.md`, the architectural boundary of 01 shall prevail, and this article shall be revised simultaneously.
4. If this article conflicts with `docs/sdd/04-api-contract-guidelines.md`, the API URL, header, error shape, OpenAPI rules and core error registry shall be subject to 04, and this article shall be revised simultaneously.
5. If this article conflicts with `docs/sdd/05-runner-protocol-and-run-state-machine.md`, the Runner protocol, Run state machine, and terminal-late semantics shall prevail with 05, and this article will be revised simultaneously.
6. If this article conflicts with `docs/sdd/06-security-permission-workspace.md`, the cross-cutting security, permissions, and sensitive value rules shall be subject to 06; this article may supplement storage-specific auditing and error codes, but shall not relax the security baseline of 06.
7. Slice SDD can add specific endpoints, schema, indexes, page interactions, and Done When, but it cannot violate the global storage, security, and P0 scope rules of this article.
8. Code implementation must not override the rules of this article on the grounds of "already implemented", "front-end convenience", "hidden entrance" or "configuration closed"; the SDD must be revised or the ADR must be recorded first.

---

## 3. Confirmed Storage Decisions

| Area | P0 Decision |
| --- | --- |
| Storage backend | MinIO only |
| Bucket | Single bucket: `surgepilot` |
| Dependency File prefix | `dependency-files/{workspaceId}/{fileId}/{safeFilename}` |
| Run Artifact prefix | `run-artifacts/{workspaceId}/{runId}/{relativePath}` |
| Web access to MinIO | Web never accesses MinIO directly |
| Presigned URL | Not returned to Web in P0 |
| Object key exposure | Object key is server-side only and never returned to Web |
| Runner MinIO credential | Runner never receives MinIO credentials in P0 |
| API role | API validates auth, Workspace, permission, references, size, hash and path safety, then proxies upload/download |
| Path safety | Strict ASCII allowlist, no normalization, reject on violation |
| Filename i18n | Unicode filename is rejected in P0; user must rename to ASCII-safe filename |
| Dependency File preview | Not implemented in P0 |
| Artifact preview | P0: CSV-derived structured summary only for `final_stats_csv`; P1-08: Debug Run `debug_http_trace` JSONL parsed into Run Report only |
| Download disposition | Always attachment |
| HTTP Range | Not implemented in P0 |
| HTTP cache | `Cache-Control: private, no-store` |
| Artifact hash | API streams and computes SHA-256; mismatch rejects upload |
| Retention / lifecycle | No automatic TTL cleanup, quota, orphan scanner, versioning dependency or lifecycle policy in P0 |
| Bucket bootstrap | API checks bucket availability; it does not auto-create bucket or mutate bucket policy |
| Versioning / SSE | Not required by P0 application contract; deployment may enable them outside application code |
| Non-MinIO storage | P2 only; must not be implemented in P0 |

---

## 4. Scope and Non-Goals

### 4.1 In Scope

P0 must implement or enforce:

1. MinIO-backed Dependency File upload, list, download and delete protection;
2. MinIO-backed Run Artifact metadata, upload from Runner through API, listing and download;
3. single bucket `surgepilot` with fixed prefixes;
4. strict filename and relative path validation;
5. upload and download streaming through API;
6. Dependency File size limit: default `100MB`, configurable by `apps/api`;
7. Artifact size limit: `200MB` per artifact;
8. artifact type whitelist: P0 `taurus_log`, `jmeter_log`, `final_stats_csv`, `run_log`, `artifacts_zip`; P1-08 adds `debug_http_trace` only for Debug HTTP Trace;
9. artifact upload idempotency by `(runId, eventId)` and path conflict protection by `(runId, relativePath)`;
10. artifact SHA-256 and size validation by API;
11. terminal-late diagnostic artifact acceptance exactly as defined by 05;
12. CSV-derived summary for `final_stats_csv`;
13. storage-specific audit events for upload, download and metadata delete actions;
14. storage-specific error codes with fixed HTTP status;
15. unit, API, contract and smoke tests for storage safety boundaries.

### 4.2 Out of Scope

P0 does not implement:

1. local filesystem as Dependency File or artifact storage;
2. AWS S3, Aliyun OSS, GCS or any other object storage adapter;
3. storage adapter plugin framework;
4. direct browser-to-MinIO upload;
5. browser-visible MinIO presigned URL;
6. exposing object key in Web API response;
7. ZIP / TAR / TGZ automatic extraction;
8. Dependency File preview;
9. online file editing;
10. inline artifact rendering in browser;
11. HTTP Range download;
12. artifact log tailing or server-side log search;
13. large CSV pagination for `failed_requests` or `finalstats`;
14. automatic artifact retention cleanup;
15. automatic orphan object scanner;
16. Workspace delete cascade cleanup;
17. per-Workspace storage quota;
18. bucket auto-creation, bucket policy mutation, versioning setup or lifecycle setup in application code;
19. SSE enforcement in application code;
20. generic malware scanning or content disarm;
21. generic sensitive log redaction framework.

Description:

- Deployment may enable MinIO versioning, server-side encryption, backup or lifecycle policy outside application code, but P0 application must not depend on them.
- P0 can perform best-effort cleanup for a failed current upload. That is not a lifecycle or retention system.

---

## 5. Storage Architecture

### 5.1 Component Boundary

P0 storage flow:

```text
Web
  -> API
      -> PostgreSQL metadata
      -> MinIO object storage

Runner
  -> API internal runner endpoint
      -> PostgreSQL metadata
      -> MinIO object storage
```

Rules:

1. Web uploads Dependency Files to API, not to MinIO.
2. Web downloads Dependency Files and Run Artifacts from API, not from MinIO.
3. Runner uploads artifacts to API, not to MinIO.
4. Runner does not receive MinIO endpoint, access key, secret key, bucket name or presigned URL.
5. API is the only application component that reads and writes MinIO in P0.
6. api-worker may parse stored CSV artifacts, but it must use server-side storage adapter credentials and must not expose object keys.
7. PostgreSQL stores metadata and coordination state; MinIO stores file bytes.
8. PostgreSQL metadata is authoritative for permissions, Workspace ownership and UI listing.
9. MinIO object existence alone must never grant access.

### 5.2 Bucket and Prefixes

P0 uses exactly one bucket:

```text
surgepilot
```

Object prefixes:

```text
dependency-files/{workspaceId}/{fileId}/{safeFilename}
run-artifacts/{workspaceId}/{runId}/{relativePath}
```

Rules:

1. `workspaceId`, `fileId`, and `runId` are ULID strings generated or validated by the API.
2. `safeFilename` is produced by the filename validator in §7.
3. `relativePath` is produced by the artifact relative path validator in §7.
4. Prefixes are stable P0 contracts and must not be changed by Slice SDD without updating this document.
5. Object keys are internal storage implementation details.
6. Object keys must not be returned in Web API response, OpenAPI examples, audit details or frontend logs.
7. Server logs may include object keys only at debug level for operator diagnosis and must not include MinIO credentials.
8. Public API should use business IDs: `dependencyFileId`, `artifactId`, `runId`, `workspaceId`.

### 5.3 Bucket Availability

API startup and Setup Status must check storage availability.

Rules:

1. API checks that MinIO endpoint is reachable.
2. API checks that bucket `surgepilot` exists and is readable/writable with configured server credential.
3. API does not auto-create the bucket in P0.
4. API does not mutate bucket policy, versioning, encryption or lifecycle settings.
5. If the bucket is missing or inaccessible, upload/download APIs must return `503 STORAGE_UNAVAILABLE`.
6. Setup Status should show storage health without exposing endpoint credentials.
7. The application may still start in a degraded mode for Setup Status visibility, but it must not report storage as ready.

### 5.4 Storage Configuration

P0 follows the environment variable names defined by `02-repo-structure-and-dev-workflow.md`. Do not introduce local aliases in 07 unless 02 is updated in the same change.

Recommended server-side configuration names:

| Config | Required | Rule |
| --- | --- | --- |
| `MINIO_ENDPOINT` | yes | Server-side endpoint only |
| `MINIO_ACCESS_KEY` | yes | Server-side secret; never returned |
| `MINIO_SECRET_KEY` | yes | Server-side secret; never returned |
| `MINIO_BUCKET` | yes | Must default to `surgepilot`; P0 should not support multiple buckets |
| `MINIO_REGION` | no | Optional, for S3-compatible SDK compatibility |
| `MINIO_SECURE` | yes | Deployment-level HTTP/HTTPS choice |
| `DEPENDENCY_FILE_MAX_BYTES` | no | Default `100MB` |
| `ARTIFACT_MAX_BYTES` | no | Default and maximum P0 value `200MB` |

Rules:

1. Config values containing credentials are secrets.
2. Config values must not appear in Web responses, public OpenAPI examples, audit details or frontend bundle.
3. P0 does not add a Web UI for editing MinIO configuration.
4. P0 does not support changing storage backend at runtime.
5. If a future Foundation revision standardizes a `SURGEPILOT_*` prefix, 02 and 07 must be updated together; Slice SDD must not independently create both prefixed and unprefixed variants.

---

## 6. Metadata Model Requirements

This section defines minimum semantic fields. Exact table names, column names, indexes and migrations belong to Slice SDD.

### 6.1 Dependency File Metadata

Dependency File metadata must represent at least:

| Field | Rule |
| --- | --- |
| `id` | ULID business ID |
| `workspace_id` | Required; all queries filter by it |
| `filename` | Safe display filename, validated by §7 |
| `content_type` | Client-provided or detected best effort; not trusted for security |
| `size_bytes` | Actual uploaded size |
| `sha256` | Recommended; API should compute while streaming |
| `storage_bucket` | Internal only; not returned to Web unless explicitly allowed by Slice, normally omitted |
| `storage_object_key` | Internal only; never returned to Web |
| `status` | At least distinguish available vs deleted / failed if Slice needs it |
| `created_by` | User ID |
| `created_at` | UTC timestamp |
| `deleted_at` | Nullable, if soft delete is used |
| `deleted_by` | Nullable user ID |

Rules:

1. `workspace_id` is mandatory from day 1.
2. Metadata response to Web must not include `storage_object_key`.
3. `filename` must already be safe; Web must not need to sanitize it for storage safety.
4. Dependency File upload creates a new file ID. P0 does not require in-place binary replacement.
5. If a later Slice adds a replace action, it must preserve Run snapshot immutability and cannot mutate bytes referenced by historical Runs.
6. Deletion is metadata-level and protected by reference checks; P0 does not require physical MinIO object deletion.

### 6.2 Artifact Metadata

Artifact metadata must represent at least:

| Field | Rule |
| --- | --- |
| `id` | ULID artifact ID |
| `workspace_id` | Required; copied from Run |
| `run_id` | Required |
| `node_id` | Required |
| `event_id` | Runner upload idempotency key |
| `artifact_type` | One of P0 whitelist |
| `relative_path` | Safe relative path validated by §7 |
| `display_filename` | Last segment of `relative_path` |
| `content_type` | Best effort; not trusted for security |
| `size_bytes` | Actual uploaded size |
| `sha256` | API-computed hash, must match Runner declaration |
| `storage_bucket` | Internal only |
| `storage_object_key` | Internal only; never returned to Web |
| `status` | `uploading`, `available`, `failed` or equivalent |
| `terminal_late` | Boolean, true only for accepted diagnostic late artifact |
| `created_at` | UTC timestamp |
| `available_at` | UTC timestamp when object is safe to download |

Rules:

1. Artifact metadata must be tied to the Run's Workspace, not to a Workspace supplied by Runner.
2. Runner-supplied `runId` and `nodeId` must be validated against the Runner identity bound to `x-runner-token`.
3. Web lists and downloads artifacts by `artifactId`, never by object key.
4. Artifacts with `status != available` must not be downloadable.
5. Failed upload metadata may be retained for debugging, but it must not appear as a normal downloadable artifact in the Web UI.
6. `storage_object_key` must not appear in Web API response, audit details or frontend code.

### 6.3 Report Summary Metadata

CSV-derived report summary metadata must represent only what P0 Run Report needs.

Recommended minimum semantic fields:

| Field | Rule |
| --- | --- |
| `run_id` | Required |
| `workspace_id` | Required |
| `source_artifact_id` | Required |
| `summary_type` | `final_stats` in P0 |
| `summary_json` | Bounded structured data |
| `truncated` | True when parser stopped because of row or size limit |
| `parse_status` | `pending`, `parsed`, `failed` or equivalent |
| `parse_error_code` | Safe error code only, nullable |
| `created_at` | UTC timestamp |
| `updated_at` | UTC timestamp |

Rules:

1. Summary is derived data and can be regenerated from the source artifact.
2. Summary must not be treated as a replacement for raw artifact download.
3. Summary parsing failure must not change Run terminal state.
4. Summary parsing failure should show a safe "summary unavailable" state in Run Report while preserving raw artifact download.

---

## 7. Path and Filename Safety

### 7.1 Design Principle

P0 uses strict allowlist validation and rejects unsafe input immediately.

Rules:

1. Do not call `os.path.normpath`, `Path.resolve`, URL decode loops or equivalent normalization as the primary defense.
2. Do not attempt to repair unsafe paths.
3. Do not silently rewrite user paths except deriving `display_filename` from an already safe `relativePath`.
4. Reject invalid filename or path with a fixed error code.
5. The same validator must be reused by upload, registration, download and tests.

### 7.2 Safe Filename

`safeFilename` is used for Dependency File object key and download filename.

Allowed pattern:

```text
^[A-Za-z0-9._-]+$
```

Additional rules:

1. Length must be between 1 and 255 characters.
2. Filename must not be `.` or `..`.
3. Filename must not contain `/` or `\`.
4. Filename must not contain whitespace, control characters, Unicode, emoji, colon, quote, angle bracket, pipe or shell metacharacters outside the allowlist.
5. Filename must not be trimmed and accepted; if leading/trailing whitespace exists, reject it.
6. Filename case is preserved.
7. Invalid filename returns `400 INVALID_FILENAME`.
8. Slice SDD may add a business-sensitive filename blocklist such as `.env`, `.git*`, `id_rsa*` or `*.pem` for a specific upload surface; the storage validator does not enforce business semantics and only defines the cross-cutting path safety floor.

Examples:

| Input | Result |
| --- | --- |
| `users.csv` | accept |
| `payload_01.json` | accept |
| `cert-prod.pem` | accept |
| `../users.csv` | reject |
| `/tmp/users.csv` | reject |
| `users archive.csv` | reject |
| `user.csv` | reject |
| `a\\b.csv` | reject |
| `.env` | accept at storage-validator level; a business Slice may reject it through a sensitive-name blocklist |

Slice SDD may further restrict allowed business file extensions, but it must not weaken this storage validator.

### 7.3 Safe Artifact Relative Path

`relativePath` is used for Run Artifact object key under a specific Run.

Allowed pattern:

```text
^[A-Za-z0-9._/-]+$
```

Additional rules:

1. Length must be between 1 and 512 characters.
2. Path must not start with `/`.
3. Path must not end with `/`.
4. Path must not contain `//`.
5. Path must not contain `\`.
6. Path must not contain `:`.
7. Each segment must be between 1 and 255 characters.
8. No segment may be `.` or `..`.
9. No segment may contain whitespace, control characters, Unicode, emoji or characters outside the allowlist.
10. Path case is preserved.
11. Invalid path returns `400 INVALID_ARTIFACT_PATH`.

Examples:

| Input | Result |
| --- | --- |
| `logs/taurus.log` | accept |
| `jmeter/finalstats.csv` | accept |
| `failed_requests.csv` | accept as a safe relative path example only; not a P0 artifact type |
| `../finalstats.csv` | reject |
| `/var/log/x.log` | reject |
| `logs//taurus.log` | reject |
| `logs/../../x` | reject |
| `logs\\taurus.log` | reject |
| `logs/user.log` | reject |

### 7.4 Display Filename

Artifact `display_filename` is derived from the last segment of `relativePath`.

Rules:

1. Do not accept a separate Runner-supplied display filename for artifacts in P0.
2. If `relativePath = logs/taurus.log`, display filename is `taurus.log`.
3. The derived display filename is already safe because every segment passed the same allowlist.
4. Download `Content-Disposition` must use this safe display filename.

### 7.5 Path Safety Review Rules

Reviewers must reject code that:

1. Concatenates unvalidated user path into object key.
2. Performs validation only in frontend.
3. Allows `..`, absolute path, backslash or Unicode path.
4. Uses normalization as the main defense.
5. Returns raw server path or MinIO object key in API errors.
6. Logs invalid raw path together with secrets or credentials.

---

## 8. Dependency File Flow

### 8.1 Upload Flow

P0 Dependency File upload flow:

```text
Web multipart upload
  -> API auth + CSRF + Workspace
  -> filename and size validation
  -> stream to MinIO while computing sha256
  -> create metadata
  -> return business metadata only
```

Rules:

1. Web must be authenticated.
2. Browser write request must pass CSRF unless the endpoint is explicitly exempt by 06; Dependency File upload is not exempt.
3. API resolves Workspace from `x-workspace-id` or Default Workspace according to 06.
4. API validates current user can create Dependency File in the current Workspace.
5. API validates `safeFilename` using §7.2.
6. API enforces default `100MB` limit unless Slice explicitly configures a lower or equivalent limit.
7. API streams file bytes to MinIO and must not read the entire file into memory.
8. API computes `sha256` and actual `size_bytes` while streaming.
9. API creates metadata only when upload succeeds.
10. API response returns only business metadata such as `id`, `filename`, `sizeBytes`, `contentType`, `sha256`, `createdAt` if exposed by Slice.
11. API response must not return MinIO credentials, presigned URL or object key.

### 8.2 List and Detail Flow

Rules:

1. List queries must filter by `workspace_id`.
2. Detail queries must filter by both `id` and `workspace_id`.
3. Cross-Workspace ID access must return `RESOURCE_NOT_FOUND` or equivalent hidden-by-boundary response, not raw permission leakage.
4. Deleted metadata must not appear in normal lists unless a Slice explicitly implements an admin/debug view, which is not required in P0.
5. P0 does not show object key, bucket, storage credential or server path.

### 8.3 Download Flow

P0 Dependency File download flow:

```text
Web GET download by dependencyFileId
  -> API auth + Workspace + permission + reference visibility
  -> metadata lookup
  -> MinIO get object
  -> stream response as attachment
```

Rules:

1. Web downloads by Dependency File business ID.
2. API validates auth, Workspace and permission before reading MinIO.
3. API reads MinIO only after metadata is found and accessible.
4. API streams response and must not read the entire object into memory.
5. `Content-Disposition` must be `attachment` with safe filename.
6. `Cache-Control` must be `private, no-store`.
7. HTTP Range is not implemented in P0.
8. If metadata exists but object read fails due to storage outage, return `503 STORAGE_UNAVAILABLE` with a safe message.
9. Error response must not expose object key or MinIO internal error.

### 8.4 Delete Protection

Dependency File delete in P0 is metadata-level and protected.

Rules:

1. Delete must validate auth, CSRF, Workspace and permission.
2. Delete must refuse when the file is referenced by active Scenario, Test Plan, Run Snapshot or any other P0 reference defined by the relevant Slice.
3. Exact reference graph and user-facing error copy belong to Dependency File Slice.
4. Delete should soft-delete metadata or mark status as deleted.
5. P0 does not require physical deletion from MinIO.
6. Historical Run snapshots must remain reproducible and must not be broken by Dependency File deletion.
7. Deleting metadata must write a storage audit event.

---

## 9. Run Artifact Flow

### 9.1 Runner Upload Contract

Runner uploads one artifact per request through API multipart upload.

Required multipart fields are owned by 05 and include:

| Field | Rule |
| --- | --- |
| `schemaVersion` | Must be `"1"` |
| `eventId` | ULID idempotency key |
| `runId` | ULID |
| `nodeId` | ULID |
| `artifactType` | Accepted whitelist; `debug_http_trace` is P1-08 only |
| `relativePath` | Safe relative path under current Run directory |
| `sha256` | Hex SHA-256 declared by Runner |
| `sizeBytes` | Declared file size |
| `file` | Single file |

Rules:

1. Runner endpoint uses `x-runner-token`, not browser session.
2. Runner endpoint does not use CSRF.
3. API validates Runner identity and confirms the submitted `runId` and `nodeId` belong to that Runner binding. If token is valid but binding check fails, return `403 RUNNER_FORBIDDEN`.
4. API derives `workspace_id` from the Run record, not from Runner input.
5. Unknown artifact type returns `400 INVALID_ARTIFACT_TYPE`.
6. Invalid `relativePath` returns `400 INVALID_ARTIFACT_PATH`.
7. Declared `sizeBytes` above `200MB` returns `413 PAYLOAD_TOO_LARGE`.
8. Actual uploaded size above `200MB` must stop or fail the upload and return `413 PAYLOAD_TOO_LARGE`.

### 9.2 Upload Pipeline

P0 artifact upload flow:

```text
Runner multipart upload
  -> API validates runner token, run, node, state, type, size, path
  -> API checks idempotency by (runId, eventId)
  -> API streams file to MinIO while computing actual size and sha256
  -> API compares actual size and sha256 with declared fields
  -> API creates or updates artifact metadata as available
  -> API may enqueue / run CSV summary parsing for CSV artifact types
  -> API returns artifactId only
```

Rules:

1. API must stream upload and must not read the entire file into memory.
2. API must compute SHA-256 server-side while streaming.
3. API must compute actual bytes server-side while streaming.
4. If actual size does not match declared `sizeBytes`, reject with `400 ARTIFACT_SIZE_MISMATCH`.
5. If actual SHA-256 does not match declared `sha256`, reject with `400 ARTIFACT_HASH_MISMATCH`.
6. Failed hash or size validation must not create a downloadable artifact.
7. API should best-effort delete the object written during the failed current upload.
8. If best-effort delete fails, log a safe operator warning; do not expose the object through metadata.
9. Upload metadata must not be visible as downloadable until the object is fully written and validation succeeds.
10. API returns `artifactId` and must not return object key.

### 9.3 Artifact Idempotency

P0 uses two related keys:

| Key | Purpose |
| --- | --- |
| `(runId, eventId)` | Request retry idempotency |
| `(runId, relativePath)` | Path-level duplicate / conflict protection |

Rules:

1. Duplicate `(runId, eventId)` after a successful upload returns the existing `artifactId`.
2. Duplicate `(runId, eventId)` while the original upload is still in progress may return `409 ARTIFACT_NOT_READY` or equivalent retryable response.
3. A new `eventId` with an existing `(runId, relativePath)` and identical `artifactType`, `sizeBytes` and `sha256` may return the existing `artifactId`.
4. A new `eventId` with an existing `(runId, relativePath)` but different type, size or hash must be rejected with `409 ARTIFACT_PATH_CONFLICT`.
5. API must not overwrite an available artifact object in P0.
6. Artifact registration failure must not leave Run permanently stuck in running or stopping; Run convergence remains governed by 05.
7. Exact unique constraints and retry locking belong to Storage or Run Slice SDD.

### 9.4 Terminal-Late Artifacts

Rules:

1. Before Run terminal state, Runner artifacts are accepted if all validations pass.
2. After Run reaches terminal state, API may accept diagnostic artifacts only within 5 minutes of `endedAt` and only when actual and declared size are both below `1MB`. P1 `debug_http_trace` must not use this terminal-late path; it must be uploaded before terminal callback when present.
3. Terminal-late accepted artifacts must set `terminal_late = true` or equivalent metadata.
4. Terminal-late artifacts must not change Run state, verdict, SLA result, node lease, or ended timestamp.
5. Terminal-late rejection uses fixed status mapping. Slice SDD must not choose a different mapping.

| Condition | Response |
| --- | --- |
| Run not terminal and artifact exceeds the general `200MB` limit | `413 PAYLOAD_TOO_LARGE` |
| Run is terminal and upload is outside the 5-minute terminal-late window | `409 RUN_TERMINAL_STATE` |
| Run is terminal and upload is inside the 5-minute window but declared or actual size is `>= 1MB` | `409 RUN_TERMINAL_STATE` |
| Run is terminal and upload is inside the 5-minute window but violates validation that does not depend on terminal-late policy, such as invalid path, hash mismatch, or unknown artifact type | Use the specific validation error for that validation |

Terminal-late policy takes precedence over the general artifact size limit after a Run is terminal. This keeps `RUN_TERMINAL_STATE` as the stable signal for diagnostics rejected because the Run has already ended.

### 9.5 Artifact List and Download

Rules:

1. Web lists artifacts through Run Report APIs by Run ID or equivalent business route, not by object key.
2. API list queries must filter by Run ID and Workspace.
3. Artifact metadata returned to Web may include `id`, `artifactType`, `relativePath`, `displayFilename`, `sizeBytes`, `sha256`, `createdAt`, `terminalLate` and `downloadUrl` if Slice uses a business API URL.
4. Artifact metadata returned to Web must not include `storage_bucket` or `storage_object_key`.
5. Web downloads artifact by `artifactId`.
6. API validates auth, Workspace, Run visibility and artifact status before reading MinIO.
7. Download response must be attachment, no-store, stream-only, no Range.
8. If artifact metadata exists but `status != available`, return `409 ARTIFACT_NOT_READY`.
9. If artifact object cannot be read due to storage outage, return `503 STORAGE_UNAVAILABLE`.
10. Error response must not include object key, server path or MinIO internal error.

---

## 10. Artifact CSV Summary and Preview

### 10.1 Allowed P0 Summary Types

P0 may derive structured report data only from:

1. `final_stats_csv`.

P1-08 may additionally derive Debug Run HTTP Trace data only from:

1. `debug_http_trace` JSONL.

Rules:

1. `taurus_log`, `jmeter_log`, `run_log` and `artifacts_zip` are download-only in P0/P1-08.
2. P0 does not implement log preview, log tailing, log search or inline rendering.
3. P0 does not parse arbitrary CSV Dependency Files.
4. P0 does not implement large CSV pagination; bounded `final_stats_csv` summary only.
5. `failed_requests_csv` preview depends on a JMeter plugin output contract and is separate from P1-08 `debug_http_trace`.
6. `debug_http_trace` preview is limited to Run Report `debugHttpTrace` and must use debug-trace-specific parsing, size bounds and sanitization; it is not a general inline artifact renderer.

### 10.2 Final Stats Summary

For `final_stats_csv`, API or api-worker should parse enough data to support Run Report KPI and Final Stats.

Rules:

1. Parser must be streaming or memory-bounded.
2. Parser must tolerate missing optional columns by marking summary parse as failed or partial, not by crashing the worker.
3. Parser must not trust CSV content as HTML.
4. Values displayed in Web must be escaped by normal frontend rendering rules.
5. Summary parsing failure must not block raw artifact download.
6. Summary parsing failure must not change Run terminal state.

### 10.3 Failed Requests Preview Deferral

`failed_requests_csv` preview is not implemented in P0.

Rules:

1. P0 does not require Runner to upload `failed_requests_csv`.
2. P0 does not parse or display `failed_requests_csv`.
3. P0 does not expose a failed requests table placeholder that implies hidden P0 behavior.
4. P1 may define the JMeter plugin output contract, upload type, bounded preview, pagination and UI.

### 10.4 Summary Freshness

Rules:

1. Summary must reference `source_artifact_id`.
2. If the same artifact upload retry returns an existing artifact, summary must not duplicate records.
3. If summary parse is pending, Run Report may show `ARTIFACT_NOT_READY` or a UI-level pending state for summary only.
4. Raw artifact download should be available once artifact status is `available`, even if summary parsing is still pending.

---

## 11. Download Response Rules

### 11.1 Headers

All P0 storage downloads must use:

```http
Content-Disposition: attachment; filename="<safeFilename>"
Cache-Control: private, no-store
```

Rules:

1. `filename` must be safe ASCII from §7.
2. Do not use `inline` in P0.
3. Do not support `?inline=1` in P0.
4. Do not support HTTP Range in P0.
5. Do not expose object key in headers.
6. `Content-Type` may use stored content type or `application/octet-stream`; it must not weaken attachment behavior.

### 11.2 Streaming

Rules:

1. API must stream MinIO object to HTTP response.
2. API must not read entire objects into memory.
3. Streaming chunk size should be bounded and implementation-owned.
4. If streaming fails after response starts, API should log safe operator details with request ID.
5. Error body can only be returned before response body starts; do not attempt to send partial JSON after streaming bytes.

### 11.3 Browser and Web Client

Rules:

1. Web must call generated API client or stable download route from OpenAPI.
2. Web must not construct object key.
3. Web must not store object key.
4. Web must treat storage download errors using standard API error shape when available.
5. Web must not attempt to preview Dependency Files in P0.
6. Web must not render arbitrary artifact bytes inline. P1-08 may render only API-parsed and sanitized `debugHttpTrace` data, never raw object bytes or object keys.

---

## 12. Permission, Workspace, and Sensitive Data

### 12.1 Workspace Rules

Rules:

1. Dependency File metadata must carry `workspace_id`.
2. Artifact metadata must carry `workspace_id` copied from Run.
3. Dependency File list/detail/update/delete queries must filter by `workspace_id`.
4. Artifact list/download queries must filter by both Run ownership and `workspace_id`.
5. API must never trust frontend-sent Workspace for cross-resource ownership without DB validation.
6. Cross-Workspace resource access should return `RESOURCE_NOT_FOUND` or equivalent hidden-by-boundary response.
7. Setup Status is the only platform-level storage health view and must not expose business objects across Workspace.

### 12.2 Permission Rules

Rules:

1. Authenticated users may manage Dependency Files in their current Workspace according to Slice permission rules.
2. Artifact upload is internal Runner-only and uses `x-runner-token`.
3. Browser users cannot upload Run Artifacts directly in P0.
4. Artifact download requires user access to the Run's Workspace and Run Report.
5. Admin role does not bypass Private Workspace boundaries beyond rules explicitly allowed by 06 and relevant Slices.
6. Backend permission is authoritative; frontend hidden navigation is not sufficient.

### 12.3 Sensitive Data Rules

Rules:

1. MinIO access key and secret key are server-side secrets.
2. MinIO object key is server-side storage logic and must not be returned to Web.
3. Runner token must not appear in audit details, logs, Web response or OpenAPI examples.
4. Server absolute path must not appear in API response.
5. MinIO internal error details must not appear in API response.
6. CSV content may contain user data; audit details must not include CSV row content.
7. Logs may include business IDs, request ID, Workspace ID, artifact ID and safe error code.
8. Logs must not include file bytes, credentials, token values or secret headers.

---

## 13. Lifecycle, Retention, and Deletion

### 13.1 P0 Retention Decision

P0 does not implement automatic storage lifecycle management.

Rules:

1. No time-based artifact cleanup in application code.
2. No capacity-based cleanup in application code.
3. No per-Workspace storage quota in P0.
4. No automatic orphan object scanner in P0.
5. No Workspace delete cascade cleanup in P0.
6. No dependency on MinIO lifecycle policy for correctness.
7. Deployment may configure backup or lifecycle outside application code, but that is not part of P0 application contract.

### 13.2 Object Deletion

Rules:

1. Dependency File user delete is metadata-level with reference protection.
2. P0 does not require physical MinIO object deletion for user delete.
3. Run Artifact user delete is not a P0 user-facing feature.
4. Best-effort deletion of a failed current upload is allowed as implementation hygiene.
5. Best-effort deletion failure must not expose the object to users if metadata is not available.
6. If a future Slice implements physical deletion, it must define audit, retry, failure state and recovery behavior before implementation.

---

## 14. Audit Events

### 14.1 Purpose

P0 storage audit log supports minimum security traceability for file ingress, egress and metadata deletion. It is not a SIEM, report UI, export system or retention framework.

This section intentionally extends 06's minimum audit coverage for storage-specific actions while keeping details bounded and safe.

### 14.2 Required Storage Audit Events

P0 must write audit events for:

| Event type | Actor | Required safe details |
| --- | --- | --- |
| `dependency_file.uploaded` | user | `dependencyFileId`, `workspaceId`, `filename`, `sizeBytes`, `sha256`, `requestId` |
| `dependency_file.downloaded` | user | `dependencyFileId`, `workspaceId`, `filename`, `sizeBytes`, `requestId` |
| `dependency_file.deleted` | user | `dependencyFileId`, `workspaceId`, `filename`, `requestId` |
| `artifact.uploaded` | runner/internal | `artifactId`, `runId`, `nodeId`, `workspaceId`, `artifactType`, `relativePath`, `sizeBytes`, `sha256`, `terminalLate`, `requestId` |
| `artifact.downloaded` | user | `artifactId`, `runId`, `workspaceId`, `artifactType`, `relativePath`, `sizeBytes`, `requestId` |

Rules:

1. Audit details must not include MinIO object key.
2. Audit details must not include MinIO credentials.
3. Audit details must not include Runner token.
4. Audit details must not include file content or CSV row content.
5. Audit details must not include raw MinIO internal error.
6. Failed upload/download attempts may be logged as structured application logs; Slice may add failed audit events if needed, but P0 does not require a full failed-operation audit matrix.
7. P0 does not implement audit log UI, export or cleanup.

### 14.3 Audit Failure Behavior

P0 default behavior:

1. If upload, download or metadata delete succeeds but the audit write fails, the user operation still returns its normal success response, such as `200 OK` or `204 No Content`.
2. The audit failure must be logged at `ERROR` level in the application log.
3. The log must include `requestId`, actor ID when available, Workspace ID when available, event type and resource ID.
4. The log must not include MinIO credentials, runner token, object key, file content or raw storage exception details that would leak internals.
5. The log message must be structured enough for a future manual replay or compensation script.
6. Slice SDD must test that audit failure does not silently disappear and does not leak secrets.

Rationale: P0 requires minimal auditability, but it does not introduce a durable outbox or SIEM pipeline. Blocking user-visible storage operations only because audit persistence failed would add operational fragility without providing a complete recovery story.

---

## 15. API Error Codes

Storage errors must follow the 04 error shape:

```json
{
  "code": "ERROR_CODE",
  "message": "Safe English fallback",
  "requestId": "...",
  "details": {}
}
```

### 15.1 Relationship with the 04 Core Registry

04 remains the owner of API error shape, HTTP status classes and the global principle that each error code maps to one fixed status.

§15.3 defines a bounded P0 storage extension to the 04 core registry. These storage codes are part of the single implementation error-code registry and count toward the global error-code budget. Slice SDD must not add duplicate semantic codes, change the status mapping, or create arbitrary storage-specific codes outside this registry.

If the implementation keeps one physical registry table or constants file, the same change set that adopts 07 must register the codes in §15.3 there as storage extensions.

Rules:

1. Slice SDD must use the codes in §15.2 and §15.3 before proposing any new storage-specific code.
2. A Slice may not change the HTTP status of any code listed here.
3. A Slice may not duplicate a code with a different meaning.
4. A Slice may only propose a new storage code when UI behavior, contract tests or workflow branching cannot be expressed with an existing code.
5. New storage codes must update this section or 04 in the same PR as the Slice proposal.
6. Slice SDD must not introduce a different code for a meaning already covered by §15.2 or §15.3.

### 15.2 Inherited 04 Codes Used by Storage

| Code | HTTP status | Storage use |
| --- | --- | --- |
| `VALIDATION_ERROR` | 422 | Generic field-level validation when no storage-specific branch is needed |
| `RUNNER_CALLBACK_INVALID` | 422 | Malformed runner payload before storage processing |
| `RESOURCE_NOT_FOUND` | 404 | Dependency File, Artifact or Run does not exist or is hidden by Workspace boundary |
| `FILE_IN_USE` | 409 | Dependency File cannot be deleted because it is referenced |
| `PAYLOAD_TOO_LARGE` | 413 | Dependency File or Run Artifact exceeds the configured non-terminal upload limit |
| `RUN_TERMINAL_STATE` | 409 | Terminal-late artifact upload violates terminal Run policy |
| `STORAGE_UNAVAILABLE` | 503 | MinIO endpoint, credential or bucket is unavailable |
| `UNAUTHENTICATED` | 401 | Browser user is not logged in |
| `RUNNER_UNAUTHORIZED` | 401 | Runner token is missing or invalid |
| `RUNNER_FORBIDDEN` | 403 | Authenticated Runner is not bound to the submitted Run or runner-owned resource |
| `FORBIDDEN` | 403 | Browser user lacks permission |
| `WORKSPACE_REQUIRED` | 400 | Workspace cannot be resolved |
| `WORKSPACE_ACCESS_DENIED` | 403 | User cannot access Workspace |

### 15.3 Bounded Storage Extension Registry

| Code | HTTP status | Meaning |
| --- | --- | --- |
| `INVALID_FILENAME` | 400 | Dependency File filename is not P0 safe |
| `INVALID_ARTIFACT_PATH` | 400 | Artifact `relativePath` is not P0 safe |
| `INVALID_ARTIFACT_TYPE` | 400 | Artifact type is not in the P0 whitelist |
| `ARTIFACT_SIZE_MISMATCH` | 400 | Uploaded artifact actual size differs from declared `sizeBytes` |
| `ARTIFACT_HASH_MISMATCH` | 400 | Uploaded artifact actual SHA-256 differs from declared `sha256` |
| `ARTIFACT_PATH_CONFLICT` | 409 | Same Run already has the same `relativePath` with different content or type |
| `ARTIFACT_NOT_READY` | 409 | Artifact metadata or summary exists but is not yet available for download or display |

Rules:

1. `INVALID_FILENAME` and `INVALID_ARTIFACT_PATH` are path-safety failures, not general form validation.
2. `ARTIFACT_NOT_READY` is for known metadata that is pending or unavailable; missing or inaccessible resources use `RESOURCE_NOT_FOUND`.
3. `ARTIFACT_HASH_MISMATCH` and `ARTIFACT_SIZE_MISMATCH` are integrity failures and must not be silently converted into successful artifact metadata.
4. Do not create `ARTIFACT_TOO_LARGE`; use `PAYLOAD_TOO_LARGE` for non-terminal upload size limits and `RUN_TERMINAL_STATE` for terminal-late policy failures.
5. Do not introduce separate Dependency File hash mismatch codes in P0 unless a Slice explicitly adds client-provided Dependency File hashes.

### 15.4 Future Sync with 04

For P0, §15.3 is the authoritative storage-domain active registry for `INVALID_ARTIFACT_PATH` and `ARTIFACT_NOT_READY`; 04 §13.3 lists them as non-active future-code examples only.

Once 04 §13 promotes `INVALID_ARTIFACT_PATH` or `ARTIFACT_NOT_READY` from future codes to the active registry, remove the duplicate row from §15.3 and keep one source of truth.

## 16. Implementation Guidance

### 16.1 Storage Adapter

Recommended internal abstraction:

```text
StorageAdapter
  put_stream(bucket, object_key, stream, size_limit) -> PutResult(size_bytes, sha256)
  get_stream(bucket, object_key) -> stream metadata + iterator
  delete_object_best_effort(bucket, object_key) -> result
  health_check() -> status
```

Rules:

1. P0 implementation may be MinIO-specific behind this adapter.
2. Do not implement a user-selectable storage backend interface in P0.
3. Adapter must not log credentials.
4. Adapter must support streaming upload and download.
5. Adapter must surface safe domain errors to API layer.

### 16.2 Transaction Boundary

Rules:

1. Do not hold long DB transactions while streaming large files if avoidable.
2. Do not perform remote MinIO upload inside a transaction that also locks Run or Node rows for long periods.
3. Use short DB transactions for idempotency row creation, metadata state transition and final availability marking.
4. Metadata must not become downloadable before MinIO upload and hash validation succeed.
5. Exact transaction design belongs to Slice SDD, but it must preserve the semantics in §8 and §9.

### 16.3 Memory and Backpressure

Rules:

1. Upload and download must be streaming.
2. API must use bounded buffers.
3. CSV parser must be streaming or memory-bounded.
4. Tests should include files larger than typical memory-friendly examples, without requiring huge fixtures in git.
5. P0 does not require resumable upload.

### 16.4 Content Type

Rules:

1. Client-provided `Content-Type` is metadata only.
2. Do not trust `Content-Type` for security decisions.
3. Download uses attachment; content type should not cause inline rendering.
4. CSV parser should be selected by artifact type, not by content type alone.

---

## 17. Tests

### 17.1 Unit Tests

P0 storage unit tests must cover:

1. valid safe filename examples;
2. invalid filename examples: Unicode, whitespace, slash, backslash, `.` and `..`;
3. valid artifact relative path examples;
4. invalid artifact path examples: absolute path, `..`, `.`, `//`, backslash, Unicode, colon;
5. object key construction for Dependency File;
6. object key construction for Run Artifact;
7. object key construction never normalizes unsafe path into safe path;
8. SHA-256 streaming calculation;
9. size counting and size mismatch detection;
10. artifact type whitelist validation;
11. terminal-late policy helper;
12. Content-Disposition filename generation;
13. CSV summary parser bounded row behavior;
14. summary truncation flag;
15. safe error mapping for MinIO failures.

### 17.2 API Tests

P0 storage API tests must cover:

1. Dependency File upload success;
2. Dependency File upload rejects invalid filename;
3. Dependency File upload rejects oversized file with `PAYLOAD_TOO_LARGE`;
4. Dependency File upload requires auth and CSRF;
5. Dependency File list filters by Workspace;
6. Dependency File download streams attachment and no-store;
7. Dependency File download does not expose object key;
8. Dependency File delete refuses referenced file;
9. Dependency File delete writes audit event;
10. Runner artifact upload success;
11. Runner artifact upload rejects invalid Runner token;
12. Runner artifact upload rejects Run / Node mismatch with `RUNNER_FORBIDDEN`;
13. Runner artifact upload rejects invalid artifact type;
14. Runner artifact upload rejects invalid relative path;
15. Runner artifact upload rejects size mismatch;
16. Runner artifact upload rejects SHA mismatch;
17. duplicate `(runId, eventId)` returns existing artifact;
18. duplicate `(runId, relativePath)` with different hash returns conflict;
19. terminal-late artifact within policy is accepted as diagnostic;
20. terminal-late artifact outside policy returns `RUN_TERMINAL_STATE`;
21. artifact download requires user access to Run Workspace;
22. artifact download streams attachment and no-store;
23. artifact download does not expose object key;
24. storage outage maps to `STORAGE_UNAVAILABLE` safely;
25. upload/download audit events do not contain credentials or object keys.

### 17.3 Contract Tests

Contract tests must verify:

1. Web API response schemas exclude `storage_object_key` and MinIO credentials;
2. download endpoints document attachment behavior;
3. upload endpoints document size errors and validation errors;
4. Runner internal endpoints are excluded from public Web OpenAPI if 04/05 require exclusion;
5. storage error codes have fixed HTTP status;
6. generated Web client remains fresh.

### 17.4 E2E / Smoke Tests

P0 smoke should cover:

1. first Admin login -> upload Dependency File -> list -> download;
2. invalid Dependency File filename rejected in UI/API path;
3. create Run or test fixture -> Runner uploads final stats CSV -> Run Report shows summary;
4. Runner uploads `artifacts_zip` -> Run Report shows downloadable artifact only;
5. Runner uploads log artifact -> Run Report shows downloadable artifact only;
6. normal user cannot download artifact from inaccessible Workspace;
7. MinIO unavailable -> Setup Status shows storage unavailable and download/upload fail safely.

---

## 18. Done When

07 preserves the P0 storage baseline and supports accepted P1 artifact-preview Slices only when:

1. The `surgepilot` bucket is checked by API / Setup Status and missing bucket is reported as `STORAGE_UNAVAILABLE`.
2. Dependency Files are stored only in MinIO under the required prefix.
3. Run Artifacts are stored only in MinIO under the required prefix.
4. Web never receives MinIO credentials, presigned URL or object key.
5. Runner never receives MinIO credentials.
6. API upload and download paths are streaming and memory-bounded.
7. Safe filename validator rejects unsafe filename examples in §7.
8. Safe artifact path validator rejects unsafe path examples in §7.
9. Dependency File upload/download/list/delete protection are Workspace-aware.
10. Artifact upload validates Runner token, Run, Node, artifact type, size, SHA-256 and relative path.
11. Duplicate artifact upload by `(runId, eventId)` is idempotent.
12. Duplicate artifact path conflict cannot overwrite an existing artifact.
13. Terminal-late artifact policy follows 05.
14. `final_stats_csv` generates bounded report summaries.
15. Dependency File preview is not implemented.
16. Logs are download-only and not tailed or rendered inline.
17. Downloads use `attachment`, `private, no-store`, no Range.
18. P0 does not implement retention cleanup, quota, orphan scanner, bucket auto-creation or non-MinIO storage.
19. Storage audit events cover upload, download and metadata delete actions with safe details only.
20. Unit, API, contract and smoke tests cover the minimum matrix in §17.

---

## 19. Review Checklist

Reviewers should check:

1. Does the change stay within P0 and avoid non-MinIO storage?
2. Does Web avoid direct MinIO access and presigned URLs?
3. Does Runner avoid MinIO credentials?
4. Are object keys kept out of Web responses, audit details and frontend code?
5. Are all Dependency File queries filtered by Workspace?
6. Are all Artifact queries filtered through Run and Workspace?
7. Is path validation strict allowlist-based rather than normalization-based?
8. Are Unicode, `..`, absolute paths and backslashes rejected?
9. Are upload and download streaming rather than whole-file memory reads?
10. Does artifact upload verify both declared size and SHA-256?
11. Does idempotency prevent duplicate storage and metadata?
12. Does path conflict protection prevent overwriting existing artifacts?
13. Are terminal-late artifacts bounded and diagnostic-only?
14. Is Dependency File preview still absent in P0?
15. Are log artifacts download-only?
16. Are CSV summaries bounded and safe?
17. Do download headers force attachment and no-store?
18. Are Range, inline preview, lifecycle cleanup and quota absent in P0?
19. Are audit details safe and free of credentials, object keys and file content?
20. Are storage error codes registered with fixed HTTP status?
21. Did the Slice avoid putting concrete endpoint schema back into Foundation docs?
22. Are tests added or updated for the relevant storage safety boundary?

---

## 20. AI Coding Rules

AI Coding must follow these rules:

1. Do not add S3, OSS, filesystem or pluggable storage backends in P0.
2. Do not return MinIO object keys to Web.
3. Do not return presigned URLs to Web.
4. Do not give Runner MinIO credentials.
5. Do not implement direct browser-to-MinIO upload.
6. Do not implement Dependency File preview in P0.
7. Do not implement inline artifact rendering in P0.
8. Do not implement log tailing or Range download in P0.
9. Do not implement ZIP / TAR / TGZ extraction in P0.
10. Do not implement automatic lifecycle cleanup, quota or orphan scanner in P0.
11. Do not normalize unsafe paths into safe paths; reject them.
12. Do not accept Unicode filenames or artifact paths in P0.
13. Do not read entire upload/download files into memory.
14. Do not trust client-provided SHA-256, size, content type or Workspace without server validation.
15. Do not let artifact upload overwrite an existing artifact path with different content.
16. Do not let summary parsing failure alter Run terminal state.
17. Do not include credentials, tokens, object keys, file bytes or CSV rows in audit details.
18. Do not move endpoint schemas, UI flows or migration details from Slice SDD into this Foundation SDD.

---

## 21. Foundation vs Slice Boundary

### 21.1 This Document Owns

07 owns global storage rules:

1. MinIO-only P0 decision;
2. bucket and prefix contract;
3. object key construction principles;
4. path and filename safety algorithms;
5. Web/API/Runner storage boundary;
6. upload/download streaming requirements;
7. artifact whitelist and integrity requirements;
8. terminal-late storage implications;
9. CSV summary boundaries;
10. download header policy;
11. retention and lifecycle non-goals;
12. audit and error code baseline;
13. storage test matrix and review checklist.

### 21.2 Slice SDD Owns

Slice SDD owns implementation-specific details:

1. exact endpoint list and route naming;
2. request / response JSON schema;
3. OpenAPI examples;
4. DB table names, column names, indexes and migrations;
5. transaction retry details;
6. UI layout and user-facing copy;
7. concrete Run Report cards and table columns;
8. exact Dependency File reference graph and delete protection UX;
9. exact parser output JSON shape;
10. background worker scheduling, if any;
11. test fixture files and bootstrap commands;
12. Done When for each P0 feature slice.

---
