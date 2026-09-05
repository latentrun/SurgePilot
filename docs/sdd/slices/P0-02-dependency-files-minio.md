# P0-02: Dependency Files and MinIO

- Document status: Draft v1 for implementation
- Product: SurgePilot
- Document path: `docs/sdd/slices/P0-02-dependency-files-minio.md`
- Current delivery target: P0 only
- Slice owner: API / Web / Contracts / Storage
- Depends on: `docs/prd/PRD.md`, `docs/sdd/00-product-scope-and-priority.md`, `docs/sdd/01-architecture-overview.md`, `docs/sdd/02-repo-structure-and-dev-workflow.md`, `docs/sdd/04-api-contract-guidelines.md`, `docs/sdd/06-security-permission-workspace.md`, `docs/sdd/07-storage-artifacts-minio.md`, `docs/sdd/08-frontend-routing-and-ui-rules.md`, `docs/sdd/09-testing-and-acceptance-strategy.md`
- Optional context only if directly needed: `docs/sdd/03-domain-model-overview.md`

---

## 1. Goal

This slice implements Workspace-aware Dependency File management backed by MinIO for P0.

After this slice is done, an authenticated user can:

1. View Dependency Files in the current Workspace.
2. Upload a Dependency File through the API.
3. Download a Dependency File through the API.
4. Delete Dependency File metadata when the file is not in use.
5. See stable placeholder reference state through `inUse`.

A Dependency File is a reusable Workspace-scoped asset used by later Scenario, Test Plan, and Run Snapshot slices. P0-02 creates the asset, metadata, storage, API, UI, and safety contract only. It does not attach Dependency Files to Scenario, Test Plan, Run Snapshot, Runner execution, Taurus YAML generation, or Run Report parsing.

---

## 2. PRD Trace

This slice implements the P0 Dependency Files asset requirement.

Product meaning:

| Product concept | Contract in this slice |
| --- | --- |
| Dependency File | A Workspace-scoped reusable file stored in MinIO and referenced by later load-testing assets. |
| Typical file use | Parameter data, payload examples, certificates, JMeter support files, or other execution dependencies. |
| Reference display | `inUse` is returned by API and displayed by Web. In P0-02 it is always `false`. |
| Delete protection | Delete uses a backend reference-check boundary and returns `FILE_IN_USE` when references exist. In P0-02 references do not exist yet. |
| Storage | API streams file bytes to MinIO and stores metadata in PostgreSQL. Web never accesses MinIO directly. |

This slice establishes the data and API shape needed by later slices. The later slice that first creates real Dependency File references must update the reference check and the relevant Slice SDD.

---

## 3. Document Responsibility

This Slice SDD owns the concrete P0-02 contract for:

1. Dependency File data model.
2. Dependency File upload, list, detail, download, delete endpoints.
3. Dependency File frontend route behavior under `/assets/dependency-files`.
4. Dependency File validation rules, including safe filename, sensitive filename blocklist, optional extension allowlist behavior, size limit, and duplicate name behavior.
5. Dependency File storage behavior under the MinIO prefix defined by `07-storage-artifacts-minio.md`.
6. Dependency File audit events.
7. Dependency File tests and Done When.

This document must not redefine global rules owned by Foundation SDDs:

| Concern | Source of truth |
| --- | --- |
| P0/P1/P2 scope gate | `00-product-scope-and-priority.md` |
| Architecture, component boundaries, MinIO only | `01-architecture-overview.md` |
| Repository layout, migrations, contracts, commands | `02-repo-structure-and-dev-workflow.md` |
| REST, headers, pagination, OpenAPI, error shape | `04-api-contract-guidelines.md` |
| Auth, CSRF, role, Workspace, sensitive value handling | `06-security-permission-workspace.md` |
| MinIO prefixes, streaming, path safety, storage errors, audit baseline | `07-storage-artifacts-minio.md` |
| Frontend routing, UI stack, query ownership | `08-frontend-routing-and-ui-rules.md` |
| Verification gates and test layer ownership | `09-testing-and-acceptance-strategy.md` |

---

## 4. In Scope

### 4.1 Backend

Implement these public API endpoints:

| Endpoint | Method | Auth | CSRF | Purpose |
| --- | --- | --- | --- | --- |
| `/api/v1/dependency-files` | `GET` | session | no | List Dependency Files in the current Workspace. |
| `/api/v1/dependency-files` | `POST` | session | yes | Upload a Dependency File. |
| `/api/v1/dependency-files/{dependencyFileId}` | `GET` | session | no | Get one Dependency File metadata record. |
| `/api/v1/dependency-files/{dependencyFileId}/download` | `GET` | session | no | Download one Dependency File through API streaming. |
| `/api/v1/dependency-files/{dependencyFileId}` | `DELETE` | session | yes | Metadata-delete a Dependency File when not in use. |

Backend support includes:

1. Workspace-aware queries and writes.
2. Multipart upload through API.
3. Streaming upload to MinIO while computing SHA-256 and actual size.
4. Streaming download from MinIO through API.
5. Safe filename validation using the global storage validator floor.
6. Sensitive filename blocklist.
7. Optional extension allowlist mechanism with an empty default allowlist.
8. Default `100MB` Dependency File size limit, configurable by `apps/api`.
9. Case-insensitive active filename uniqueness within a Workspace.
10. `inUse` response field with P0-02 value `false`.
11. Future-ready delete protection boundary returning `FILE_IN_USE` when references exist.
12. Storage audit events for upload, download, and metadata delete.
13. OpenAPI export and generated Web client updates.

### 4.2 Data

Create one Alembic migration after P0-01:

```text
apps/api/migrations/versions/0003_p0_02_dependency_files.py
```

The migration creates:

1. `dependency_files` table.
2. Workspace/active-filename uniqueness index.
3. Workspace list query indexes.
4. Status and size constraints.

### 4.3 Frontend

Implement the P0 route:

| Route | Layout | Purpose |
| --- | --- | --- |
| `/assets/dependency-files` | `AppLayout` | List, upload, download, and delete Dependency Files. |

Frontend support includes:

1. List view.
2. Upload action.
3. Download action.
4. Delete confirmation.
5. `FILE_IN_USE` error handling branch.
6. Loading, empty, error, validation, and disabled submitting states.
7. AppLayout global navigation entry and active state for `Assets -> Dependency Files`.

### 4.4 Tests

Implement:

1. API unit tests for validators, storage key construction, size/hash behavior, service rules, and reference-check boundary.
2. API integration tests for all Dependency File endpoints.
3. MinIO-backed storage integration tests for upload and download.
4. Contract tests for OpenAPI operation IDs, schemas, headers, binary download response, and error responses.
5. Web component/page tests for list, upload, download, delete, and error states.
6. One lightweight Playwright smoke test covering upload, list, download, and delete.

---

## 5. Out of Scope

This slice must not implement:

1. Attaching Dependency Files to Scenario, Test Plan, Run, Runner, Taurus, or execution bundle behavior.
2. Real reference counting from Scenario, Test Plan, Run Snapshot, or Run.
3. Scenario or Test Plan Dependency File selector UI.
4. Run Snapshot capture of Dependency Files.
5. Generated Taurus YAML or execution manifest integration.
6. Dependency File preview.
7. Dependency CSV parsing, schema detection, column preview, summary generation, or row pagination.
8. Dependency File inline editing.
9. Dependency File rename, description, patch, replace, or versioning.
10. Physical MinIO object deletion for user delete.
11. Tags, archive, restore, history, diff, or soft-delete API behavior.
12. ZIP / TAR / TGZ extraction.
13. Direct browser-to-MinIO upload.
14. Browser-visible MinIO presigned URL.
15. Browser-visible MinIO bucket, object key, endpoint, access key, or secret key.
16. Local filesystem storage, S3, OSS, GCS, or generic storage plugin framework.
17. Per-Workspace storage quota.
18. Automatic retention cleanup, object lifecycle cleanup, or orphan scanner.
19. Malware scanning, content disarm, or generic sensitive-content detection.
20. HTTP Range download.
21. Inline rendering or `Content-Disposition: inline`.
22. Owner-only or resource-level permission model.
23. Admin-only Dependency File management.
24. Audit log UI or audit list API.
25. P1/P2 user-visible navigation or placeholder pages.
26. New user-facing P1/P2 asset features hidden behind a flag.

P0-02 may create extension-safe fields and service boundaries only when required by this slice contract. It must not expose usable P1/P2 behavior.

---

## 6. Key Decisions

| Area | Decision |
| --- | --- |
| Resource name | `dependency-files` |
| Frontend route | `/assets/dependency-files` |
| Workspace | Required business resource; route path does not contain Workspace ID. |
| Permissions | Any authenticated `admin` or `user` with current Workspace access may upload, list, get, download, and delete Dependency Files. |
| Storage backend | MinIO only. |
| Object prefix | `dependency-files/{workspaceId}/{fileId}/{safeFilename}`. |
| Web storage access | Web never accesses MinIO directly. |
| Upload transport | Browser multipart upload to API. |
| Upload request fields | P0-02 accepts one file part named `file`; callers do not supply bucket, object key, or SHA-256. |
| Upload memory behavior | API streams upload; it must not read the full file into memory. |
| Download behavior | API streams download as attachment; no Range support. |
| File size limit | Default `100MB`, using the storage configuration from `07-storage-artifacts-minio.md`. |
| Filename floor | Must satisfy `safeFilename` from `07-storage-artifacts-minio.md`: ASCII `[A-Za-z0-9._-]`, length `1..255`, no slash, no backslash, no whitespace, no Unicode, not `.` or `..`. |
| Sensitive filename blocklist | Enabled in P0-02 and enforced after `safeFilename`. |
| Extension allowlist | Mechanism exists, but default allowlist is empty. Empty means no extension restriction. |
| Content type | Stored as metadata only; never trusted for security or preview decisions. |
| Hash | API computes SHA-256 while streaming and stores it. |
| Filename uniqueness | Active Dependency File filenames are case-insensitively unique within one Workspace. |
| Same filename after delete | Allowed because uniqueness applies only to active rows. |
| Same filename while active | Rejected with `DEPENDENCY_FILE_NAME_CONFLICT`. |
| Replacement | Not implemented. Upload always creates a new file ID. |
| Delete | Metadata-level status transition to `deleted`; P0 does not physically delete MinIO object. |
| Delete protection | Backend must check `inUse`; P0-02 always returns `false`. |
| In-use error | `FILE_IN_USE` is registered and handled by Web. |
| List pagination | Offset pagination. |
| List filter | `q` over filename only. |
| List sorting | P0-02 supports `filename`, `createdAt`, `-createdAt`, `sizeBytes`, and `-sizeBytes`. |
| Dependency CSV parsing | Not implemented. CSV summary belongs only to Run Artifacts in later Run Report slices. |
| Extension allowlist setting | API setting `DEPENDENCY_FILE_ALLOWED_EXTENSIONS`; default empty string/list. Empty disables extension restriction. No Web UI. |
| Audit | Upload, download, and metadata delete write storage audit events. |

---

## 7. Data Model

### 7.1 `dependency_files`

Purpose: Workspace-scoped Dependency File metadata for MinIO-backed file bytes.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `char(26)` | yes | ULID primary key. |
| `workspace_id` | `char(26)` | yes | FK to `workspaces.id`. |
| `filename` | `text` | yes | Safe display filename; case preserved. |
| `content_type` | `text` | no | Best-effort client-provided upload content type; not trusted for security. |
| `size_bytes` | `bigint` | yes | Actual uploaded size counted by API. |
| `sha256` | `char(64)` | yes | Hex SHA-256 computed by API while streaming. |
| `storage_bucket` | `text` | yes | Internal only. Must not be returned to Web. |
| `storage_object_key` | `text` | yes | Internal only. Must not be returned to Web. |
| `status` | `text` | yes | `available` or `deleted`. |
| `created_by` | `char(26)` | yes | FK to `users.id`. |
| `created_at` | `timestamptz` | yes | UTC. |
| `deleted_by` | `char(26)` | no | FK to `users.id`; set when metadata delete succeeds. |
| `deleted_at` | `timestamptz` | no | UTC; set when metadata delete succeeds. |

Constraints:

1. Primary key on `id`.
2. FK from `workspace_id` to `workspaces.id`.
3. FK from `created_by` to `users.id`.
4. FK from `deleted_by` to `users.id`.
5. `status in ('available', 'deleted')`.
6. `size_bytes >= 0`.
7. `sha256` must be a lower-case 64-character hex string. The migration must enforce this with a CHECK constraint equivalent to `sha256 ~ '^[0-9a-f]{64}$'`.
8. Unique index on `(workspace_id, lower(filename))` where `status = 'available'`.
9. Index on `(workspace_id, status, created_at desc, id desc)`.
10. Index on `(workspace_id, status, lower(filename))`.
11. Do not add a PostgreSQL trigram extension or trigram index for P0-02 search.

Rules:

1. `id`, `workspace_id`, `created_by`, and `deleted_by` are ULID strings.
2. API creates `id`; callers cannot supply it.
3. API writes `workspace_id` from the resolved Workspace context.
4. API writes `created_by` from the current user.
5. API writes `deleted_by` and `deleted_at` on successful metadata delete.
6. API must not expose DB `snake_case` field names.
7. API must not return `storage_bucket` or `storage_object_key`.
8. Normal list/detail/download endpoints only operate on `status = 'available'`.
9. P0-02 does not add `updated_at`, `updated_by`, `description`, `tags`, `version`, `archived_at`, or owner-only permission fields.
10. P0-02 does not expose include-deleted, restore, purge, or admin debug APIs.

### 7.2 Object Key Rule

Dependency File object key is:

```text
dependency-files/{workspaceId}/{fileId}/{safeFilename}
```

Rules:

1. `workspaceId` is the resolved Workspace ID.
2. `fileId` is the generated Dependency File ID.
3. `safeFilename` is the validated `filename`.
4. The object key is internal storage implementation detail.
5. The object key must not be returned in Web API response, OpenAPI examples, audit details, frontend state, or frontend logs.
6. Server logs may include object key only at debug level for operator diagnosis and must not include credentials, tokens, or file bytes.

### 7.3 Filename Rules

API reads the filename from the uploaded multipart file part named `file`.

Rules:

1. Filename is required.
2. Filename must pass `safeFilename`.
3. Filename must not be trimmed and accepted; leading or trailing whitespace causes rejection.
4. Filename case is preserved for display and download.
5. Uniqueness comparison uses `lower(filename)`.
6. API validation is authoritative.
7. Web validation must mirror API validation for user feedback only.
8. Filename conflict returns `DEPENDENCY_FILE_NAME_CONFLICT`.
9. Filename uniqueness is scoped to Workspace and active rows only.
10. The same filename may exist in another Workspace.
11. The same filename may be uploaded again in the same Workspace after the previous active metadata row is deleted.

### 7.4 Sensitive Filename Blocklist

P0-02 rejects sensitive filenames after `safeFilename` passes.

Matching rules:

1. Match is case-insensitive.
2. Match uses the full filename only, not path segments, because Dependency File filenames cannot contain path separators.
3. Rejection uses `INVALID_FILENAME`.

Blocked names and patterns:

| Pattern | Rule |
| --- | --- |
| `.env` | exact match |
| `.env.*` | prefix match |
| `.git` | exact match |
| `.git*` | prefix match |
| `id_rsa` | exact match |
| `id_rsa*` | prefix match |
| `id_dsa` | exact match |
| `id_dsa*` | prefix match |
| `id_ecdsa` | exact match |
| `id_ecdsa*` | prefix match |
| `id_ed25519` | exact match |
| `id_ed25519*` | prefix match |
| `known_hosts` | exact match |
| `authorized_keys` | exact match |
| `private.key` | exact match |
| `private.pem` | exact match |
| `*.private.key` | suffix match |
| `*.private.pem` | suffix match |

Rules:

1. `cert-prod.pem` is allowed if it passes `safeFilename`, because P0-02 does not reject all `.pem` files.
2. `client.key` is allowed if it passes `safeFilename`, because P0-02 does not reject all `.key` files.
3. `private.pem`, `private.key`, `team.private.pem`, and `team.private.key` are rejected.
4. Rejected filename errors must not disclose storage object key or server path.
5. OpenAPI examples must not use realistic private-key, token, password, or secret filenames.

### 7.5 Extension Allowlist Rule

P0-02 defines an extension allowlist mechanism for future deployment hardening.

API setting:

```text
DEPENDENCY_FILE_ALLOWED_EXTENSIONS=
```

Default P0-02 behavior:

```text
allowedExtensions = []
```

Rules:

1. `DEPENDENCY_FILE_ALLOWED_EXTENSIONS` defaults to an empty string.
2. Empty `allowedExtensions` means extension allowlist enforcement is disabled.
3. With the default empty list, P0-02 does not reject files because of extension.
4. If configured, the setting is parsed as a comma-separated list such as `.csv,.json,.txt`.
5. Each configured extension must be normalized to lower-case and include the leading dot.
6. Extension matching is case-insensitive.
7. The extension is the substring after the last dot in `filename`.
8. Filenames without an extension are accepted when `allowedExtensions` is empty.
9. Filenames without an extension are rejected when `allowedExtensions` is non-empty.
10. Extension allowlist does not replace `safeFilename` or the sensitive filename blocklist.
11. Extension allowlist failure returns `VALIDATION_ERROR` with field `file` and details code `UNSUPPORTED_FILE_EXTENSION`.
12. P0-02 does not add a Web UI for editing this allowlist.
13. Setup Status may show whether extension allowlist enforcement is enabled, but must not become a file policy editor.
14. `DEPENDENCY_FILE_ALLOWED_EXTENSIONS` is an `apps/api` configuration value whose registry owner is `02-repo-structure-and-dev-workflow.md`; 02 and P0-02 must remain aligned.

---

## 8. API Contract

All public business endpoints are under `/api/v1` at runtime and `/v1` in the exported OpenAPI paths.

All response JSON fields use `camelCase`.

All Workspace-scoped authenticated business responses must include:

1. `x-request-id`.
2. `x-workspace-id` for the resolved Workspace.
3. `Cache-Control: no-store` for JSON responses.
4. `Cache-Control: private, no-store` for download responses.

### 8.1 Shared Schemas

#### `DependencyFileSummary`

Used by list endpoint.

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "filename": "users.csv",
  "contentType": "text/csv",
  "sizeBytes": 12345,
  "sha256": "7f83b1657ff1fc53b92dc18148a1d65dfa135d0f2b018d8c828b4c5f7d2f2f12",
  "inUse": false,
  "createdBy": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
  "createdAt": "2030-05-18T03:14:15.123Z"
}
```

Rules:

1. `storageBucket` must not appear.
2. `storageObjectKey` must not appear.
3. `deletedAt`, `deletedBy`, and `status` must not appear in normal list responses.
4. `inUse` is always `false` in P0-02.
5. `contentType` may be `null`.

#### `DependencyFileDetail`

Used by get and upload responses.

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "filename": "users.csv",
  "contentType": "text/csv",
  "sizeBytes": 12345,
  "sha256": "7f83b1657ff1fc53b92dc18148a1d65dfa135d0f2b018d8c828b4c5f7d2f2f12",
  "inUse": false,
  "createdBy": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
  "createdAt": "2030-05-18T03:14:15.123Z"
}
```

Rules:

1. P0-02 does not expose file bytes or preview content in metadata responses.
2. P0-02 does not expose a separate user-editable description.
3. `DependencyFileDetail` uses the same public fields as `DependencyFileSummary` unless a later slice adds real references or preview behavior through SDD revision.

#### `DependencyFileListResponse`

```json
{
  "items": [],
  "page": 1,
  "pageSize": 20,
  "total": 0
}
```

Rules:

1. List response uses offset pagination.
2. `items` is always an array.
3. `total` is required in P0-02.
4. P0-02 data volume is expected to be small enough for offset pagination and `total`; if future data volume grows, the owning slice must reassess pagination under `04-api-contract-guidelines.md`.

### 8.2 `GET /api/v1/dependency-files`

Purpose: list active Dependency Files in the current Workspace.

Authentication: required session.

CSRF: not required.

Query parameters:

| Parameter | Required | Default | Rule |
| --- | --- | --- | --- |
| `page` | no | `1` | Integer, `>= 1`. |
| `pageSize` | no | `20` | Integer, `1..100`. |
| `q` | no | none | Optional search over filename only. Trimmed. Max 120 chars. |
| `sort` | no | `-createdAt` | Allowed: `filename`, `createdAt`, `-createdAt`, `sizeBytes`, `-sizeBytes`. |

Rules:

1. `sort=-filename` is not supported in P0-02.
2. Unknown query parameters return `INVALID_QUERY_PARAMETER`.
3. Unknown sort fields return `INVALID_QUERY_PARAMETER`.
4. Search is case-insensitive over `filename` only.
5. Response items must not include deleted rows.
6. Response items must not include storage bucket, object key, or server path.
7. Query must filter by resolved Workspace.

Response `200 OK`:

```json
{
  "items": [
    {
      "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
      "filename": "users.csv",
      "contentType": "text/csv",
      "sizeBytes": 12345,
      "sha256": "7f83b1657ff1fc53b92dc18148a1d65dfa135d0f2b018d8c828b4c5f7d2f2f12",
      "inUse": false,
      "createdBy": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
      "createdAt": "2030-05-18T03:14:15.123Z"
    }
  ],
  "page": 1,
  "pageSize": 20,
  "total": 1
}
```

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Missing or invalid session. |
| `WORKSPACE_REQUIRED` | 400 | Workspace cannot be resolved. |
| `WORKSPACE_ACCESS_DENIED` | 403 | User cannot access requested Workspace. |
| `INVALID_QUERY_PARAMETER` | 400 | Invalid `page`, `pageSize`, `q`, `sort`, or unknown query parameter. |

### 8.3 `POST /api/v1/dependency-files`

Purpose: upload a Dependency File into the current Workspace.

Authentication: required session.

CSRF: required.

Content-Type: `multipart/form-data`.

Multipart fields:

| Field | Required | Rule |
| --- | --- | --- |
| `file` | yes | Single file part. Filename comes from this part. |

Rules:

1. API rejects missing file.
2. API rejects more than one `file` part.
3. API rejects filename that fails `safeFilename`.
4. API rejects filename that matches the sensitive filename blocklist.
5. API applies extension allowlist only when the allowlist is non-empty.
6. API rejects an active same-name file in the current Workspace ignoring case.
7. API enforces the configured Dependency File max size while streaming.
8. API streams bytes to MinIO and computes SHA-256 and actual size.
9. API creates metadata only after upload, size validation, and hash computation succeed.
10. API must not require or accept caller-provided bucket, object key, or SHA-256.
11. API must not read the entire upload into memory.
12. API must not expose MinIO internal errors to the client.
13. If metadata creation fails after MinIO upload succeeds, including a race-created name conflict, API best-effort deletes the just-uploaded object before re-raising the safe application error.
14. Upload success writes `dependency_file.uploaded` audit event.

Response `201 Created`: `DependencyFileDetail`.

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Missing or invalid session. |
| `CSRF_TOKEN_REQUIRED` | 403 | Missing CSRF token. |
| `CSRF_TOKEN_INVALID` | 403 | Invalid CSRF token. |
| `WORKSPACE_REQUIRED` | 400 | Workspace cannot be resolved. |
| `WORKSPACE_ACCESS_DENIED` | 403 | User cannot access requested Workspace. |
| `INVALID_REQUEST` | 400 | Multipart request is malformed or required file part is missing. |
| `INVALID_FILENAME` | 400 | Filename fails path-safety floor or sensitive-name blocklist. |
| `VALIDATION_ERROR` | 422 | Extension allowlist rejects the file or semantic upload validation fails. |
| `DEPENDENCY_FILE_NAME_CONFLICT` | 409 | Active filename already exists in the current Workspace ignoring case. |
| `PAYLOAD_TOO_LARGE` | 413 | Uploaded file exceeds configured Dependency File limit. |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Request is not `multipart/form-data`. |
| `STORAGE_UNAVAILABLE` | 503 | MinIO endpoint, credential, bucket, or object operation is unavailable. |

### 8.4 `GET /api/v1/dependency-files/{dependencyFileId}`

Purpose: get one active Dependency File metadata record.

Authentication: required session.

CSRF: not required.

Path parameters:

| Parameter | Rule |
| --- | --- |
| `dependencyFileId` | ULID string. |

Rules:

1. Query filters by `id`, resolved Workspace, and `status = 'available'`.
2. Cross-Workspace access returns `RESOURCE_NOT_FOUND`.
3. Deleted metadata returns `RESOURCE_NOT_FOUND`.
4. Response must not include storage bucket, object key, server path, deleted fields, or file bytes.

Response `200 OK`: `DependencyFileDetail`.

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Missing or invalid session. |
| `WORKSPACE_REQUIRED` | 400 | Workspace cannot be resolved. |
| `WORKSPACE_ACCESS_DENIED` | 403 | User cannot access requested Workspace. |
| `RESOURCE_NOT_FOUND` | 404 | Dependency File does not exist, is deleted, or is outside the current Workspace. |
| `VALIDATION_ERROR` | 422 | Invalid `dependencyFileId` format. |

### 8.5 `GET /api/v1/dependency-files/{dependencyFileId}/download`

Purpose: download one active Dependency File through API streaming.

Authentication: required session.

CSRF: not required.

Path parameters:

| Parameter | Rule |
| --- | --- |
| `dependencyFileId` | ULID string. |

Rules:

1. Query filters by `id`, resolved Workspace, and `status = 'available'`.
2. Cross-Workspace access returns `RESOURCE_NOT_FOUND`.
3. Deleted metadata returns `RESOURCE_NOT_FOUND`.
4. API validates metadata access before reading MinIO.
5. API streams MinIO object to HTTP response.
6. API must not read the full object into memory.
7. Download response uses attachment disposition.
8. Download response uses `Cache-Control: private, no-store`.
9. HTTP Range is not supported.
10. API response headers must not expose storage bucket or object key.
11. If metadata exists but MinIO read fails due to storage outage, return `STORAGE_UNAVAILABLE` before starting response body when possible.
12. Download success writes `dependency_file.downloaded` audit event.
13. Audit failure must not block the download response once the user operation succeeds.

Success response:

```http
HTTP/1.1 200 OK
Content-Type: application/octet-stream
Content-Disposition: attachment; filename="users.csv"
Cache-Control: private, no-store
x-request-id: req_01HZX3Y9M0E9W7Z6M5QK9S8P7A
x-workspace-id: 01HZW000000000000000000000
```

OpenAPI:

1. `200` response must be documented as binary stream.
2. Error responses must use the shared error response schema.
3. Generated Web client must expose a stable download operation or binary fetch path.

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Missing or invalid session. |
| `WORKSPACE_REQUIRED` | 400 | Workspace cannot be resolved. |
| `WORKSPACE_ACCESS_DENIED` | 403 | User cannot access requested Workspace. |
| `RESOURCE_NOT_FOUND` | 404 | Dependency File does not exist, is deleted, or is outside the current Workspace. |
| `VALIDATION_ERROR` | 422 | Invalid `dependencyFileId` format. |
| `STORAGE_UNAVAILABLE` | 503 | MinIO object cannot be read safely. |

### 8.6 `DELETE /api/v1/dependency-files/{dependencyFileId}`

Purpose: metadata-delete a Dependency File when it is not in use.

Authentication: required session.

CSRF: required.

Path parameters:

| Parameter | Rule |
| --- | --- |
| `dependencyFileId` | ULID string. |

Response `204 No Content` on success.

Rules:

1. Delete checks Workspace before checking references.
2. Cross-Workspace access returns `RESOURCE_NOT_FOUND`.
3. Deleted metadata returns `RESOURCE_NOT_FOUND`.
4. Delete uses a reference-check service boundary even though P0-02 always reports not in use.
5. When reference-check reports in use, return `FILE_IN_USE`.
6. Successful delete sets `status = 'deleted'`, `deleted_by`, and `deleted_at`.
7. Successful delete does not physically delete the MinIO object in P0-02.
8. Successful delete writes `dependency_file.deleted` audit event.
9. Audit failure must not fail the delete response after metadata deletion succeeds.
10. Delete is not a restoreable public API behavior.

Errors:

| Code | HTTP | Trigger |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Missing or invalid session. |
| `CSRF_TOKEN_REQUIRED` | 403 | Missing CSRF token. |
| `CSRF_TOKEN_INVALID` | 403 | Invalid CSRF token. |
| `WORKSPACE_REQUIRED` | 400 | Workspace cannot be resolved. |
| `WORKSPACE_ACCESS_DENIED` | 403 | User cannot access requested Workspace. |
| `RESOURCE_NOT_FOUND` | 404 | Dependency File does not exist, is deleted, or is outside the current Workspace. |
| `FILE_IN_USE` | 409 | Dependency File is referenced and cannot be deleted. |
| `VALIDATION_ERROR` | 422 | Invalid `dependencyFileId` format. |

### 8.7 Error Code Registry Additions

This slice registers one slice-specific error code:

| Code | HTTP | Message example | Trigger | UX branch |
| --- | --- | --- | --- | --- |
| `DEPENDENCY_FILE_NAME_CONFLICT` | 409 | `Dependency File filename already exists.` | Active filename already exists in current Workspace ignoring case. | Highlight upload filename conflict and keep upload dialog open. |

This slice reuses these existing error codes:

| Code | Use |
| --- | --- |
| `UNAUTHENTICATED` | Missing or invalid session. |
| `FORBIDDEN` | Reserved for generic forbidden actions if needed. |
| `WORKSPACE_REQUIRED` | Workspace context cannot be resolved. |
| `WORKSPACE_ACCESS_DENIED` | User cannot access requested Workspace. |
| `RESOURCE_NOT_FOUND` | Resource missing, deleted, or hidden by Workspace boundary. |
| `VALIDATION_ERROR` | Field-level or semantic validation failure. |
| `INVALID_QUERY_PARAMETER` | Invalid list query parameter. |
| `INVALID_REQUEST` | Malformed request or missing file part. |
| `INVALID_FILENAME` | Filename path-safety or sensitive-name failure. |
| `FILE_IN_USE` | Delete protection boundary reports references. |
| `PAYLOAD_TOO_LARGE` | Upload exceeds configured Dependency File limit. |
| `UNSUPPORTED_MEDIA_TYPE` | Request content type is unsupported. |
| `STORAGE_UNAVAILABLE` | MinIO or storage dependency unavailable. |
| `CSRF_TOKEN_REQUIRED` | Missing CSRF token for write request. |
| `CSRF_TOKEN_INVALID` | Invalid CSRF token for write request. |

Do not add separate public codes for:

1. Sensitive filename failure.
2. Extension allowlist failure.
3. Empty extension.
4. MIME type mismatch.
5. Dependency File hash mismatch.

Use `INVALID_FILENAME` or `VALIDATION_ERROR` with field-level details for those cases.

Field-level details code used by P0-02:

| details[].code | Top-level code | Field | Trigger |
| --- | --- | --- | --- |
| `UNSUPPORTED_FILE_EXTENSION` | `VALIDATION_ERROR` | `file` | Extension allowlist is non-empty and the uploaded filename extension is not allowed. |

`UNSUPPORTED_FILE_EXTENSION` is a `details[].code`, not a top-level API error code.

---

## 9. Frontend Contract

### 9.1 Route and Navigation

Route:

```text
/assets/dependency-files
```

Rules:

1. Route is protected by authenticated AppLayout.
2. AppLayout global navigation shows and highlights `Assets -> Dependency Files` for this route.
3. `Assets -> Env Groups` remains available from P0-01.
4. Other P1/P2 navigation entries remain hidden.
5. No detail route is introduced in P0-02.
6. No `/assets/dependency-files/:dependencyFileId` route is introduced.
7. Unknown or future actions remain inaccessible.
8. Business data is fetched with TanStack Query, not React Router loader data.

### 9.2 Page Behavior

The page contains:

1. Header with title `Dependency Files`.
2. Upload button.
3. Search input for `q`.
4. Table with filename, content type, size, reference state, created time, and actions.
5. Delete confirmation dialog.
6. Optional upload dialog or panel.
7. Optional metadata details panel or copy action for SHA-256.

Table actions:

| Action | Rule |
| --- | --- |
| Download | Calls the generated download operation or stable API download path. |
| Delete | Opens confirmation; calls delete endpoint only after confirmation. |

Rules:

1. List page uses summary endpoint and must not depend on file bytes or preview content.
2. The table must not display the full 64-character `sha256` by default. SHA-256 may be shown in a details panel, tooltip, truncated copy control, or explicit metadata view.
3. Upload form accepts a single file per submit in P0-02.
4. Upload form does not collect custom filename, description, tags, or extension metadata.
5. Delete confirmation must include the Dependency File filename.
6. Submit buttons are disabled while mutation is pending.
7. Repeated clicks must not submit duplicate mutations.
8. Download action must not expose or store object keys.
9. UI copy is English only.

### 9.3 Upload Form

Fields:

1. File picker.

Rules:

1. Form validation mirrors API rules where possible.
2. Web may show a client-side error for unsafe filenames.
3. Web must not be the only validation boundary.
4. Web must not compute or submit SHA-256 in P0-02.
5. Web must not let users edit MinIO bucket, object key, storage prefix, or content type.
6. Web shows active filename conflict using the `DEPENDENCY_FILE_NAME_CONFLICT` branch.
7. Web shows oversized file failure using the `PAYLOAD_TOO_LARGE` branch.
8. Web shows unsafe filename failure using the `INVALID_FILENAME` branch.
9. Web shows extension allowlist failure from `VALIDATION_ERROR` details if the allowlist is populated later.
10. Upload success refreshes list.

### 9.4 UI States

Required states:

1. Loading list.
2. Empty list.
3. List API error with retry.
4. Upload pending.
5. Upload validation error.
6. Filename conflict.
7. Unsafe filename.
8. Payload too large.
9. Storage unavailable.
10. Download pending or disabled state.
11. Download error.
12. Delete confirmation.
13. Delete pending.
14. Dependency File in use.
15. Access denied.
16. Not found after concurrent delete.

Required error branches:

| Code | Frontend behavior |
| --- | --- |
| `DEPENDENCY_FILE_NAME_CONFLICT` | Keep upload UI open and show filename conflict message. |
| `INVALID_FILENAME` | Show unsafe filename message. |
| `PAYLOAD_TOO_LARGE` | Show size limit message. |
| `FILE_IN_USE` | Keep row, close or keep delete dialog with clear explanation that referenced files cannot be deleted. |
| `VALIDATION_ERROR` | Show field-level messages when details exist. |
| `STORAGE_UNAVAILABLE` | Show safe storage unavailable message and allow retry. |
| `UNAUTHENTICATED` | Follow global auth recovery. |
| `WORKSPACE_ACCESS_DENIED` | Show access denied state. |
| `RESOURCE_NOT_FOUND` | Show not found and refresh list when relevant. |

### 9.5 No Preview Rule

P0-02 Web must not:

1. Render Dependency File bytes inline.
2. Parse CSV content.
3. Show CSV columns.
4. Preview JSON/YAML/text files.
5. Tail or search file content.
6. Show thumbnails.
7. Use `Content-Disposition: inline`.
8. Open a browser-visible MinIO URL.

---

## 10. Security, Permission, and Workspace Rules

### 10.1 Authentication and CSRF

1. All endpoints require an active session.
2. `GET` endpoints do not require CSRF.
3. `POST` and `DELETE` endpoints require `x-csrf-token`.
4. CSRF failures use `CSRF_TOKEN_REQUIRED` or `CSRF_TOKEN_INVALID`.
5. No endpoint returns session token, CSRF token, cookie value, password hash, MinIO credential, object key, or server path.

### 10.2 Authorization

| Action | User | Admin | Rule |
| --- | --- | --- | --- |
| List Dependency Files | Yes | Yes | Current Workspace only. |
| Upload Dependency File | Yes | Yes | Current Workspace only. |
| Get Dependency File | Yes | Yes | Current Workspace only. |
| Download Dependency File | Yes | Yes | Current Workspace only. |
| Delete Dependency File | Yes | Yes | Current Workspace only and not in use. |

Rules:

1. Backend authorization is mandatory.
2. Frontend route visibility is not a permission boundary.
3. No owner-only permission is implemented in P0-02.
4. No Admin-only Dependency File action is implemented in P0-02.
5. Cross-Workspace resource lookup returns `RESOURCE_NOT_FOUND`.

### 10.3 Workspace Handling

1. All Dependency File rows carry `workspace_id`.
2. API route paths do not include Workspace ID.
3. Web sends `x-workspace-id` after it has current Workspace state.
4. Missing `x-workspace-id` falls back to the user's default Workspace in P0.
5. API response includes the resolved `x-workspace-id` header.
6. Queries must filter by resolved Workspace.
7. Upload must write resolved Workspace.
8. Get, download, and delete must check resolved Workspace.
9. Cross-Workspace access must not leak resource existence.

### 10.4 Sensitive Data Handling

Rules:

1. MinIO endpoint credentials are server-side secrets.
2. MinIO object key is server-side storage logic and must not be returned to Web.
3. Server absolute path must not appear in API responses.
4. MinIO internal error details must not appear in API responses.
5. Upload content may contain user data; audit details must not include file content.
6. Logs may include business IDs, request ID, Workspace ID, Dependency File ID, safe filename, size, hash, and safe error code.
7. Logs must not include file bytes, credentials, token values, secret headers, raw MinIO internal errors, or server paths.
8. Test fixtures must not include realistic private keys, tokens, passwords, or credentials.
9. OpenAPI examples must use fake and non-sensitive filenames.
10. `contentType` must not be trusted for security decisions.
11. Download is always attachment to avoid inline rendering.

### 10.5 Audit Events

P0-02 must write audit events for:

| Event type | Actor | Required safe details |
| --- | --- | --- |
| `dependency_file.uploaded` | user | `dependencyFileId`, `workspaceId`, `filename`, `sizeBytes`, `sha256`, `requestId` |
| `dependency_file.downloaded` | user | `dependencyFileId`, `workspaceId`, `filename`, `sizeBytes`, `requestId` |
| `dependency_file.deleted` | user | `dependencyFileId`, `workspaceId`, `filename`, `requestId` |

Rules:

1. Audit details must not include MinIO object key.
2. Audit details must not include MinIO credentials.
3. Audit details must not include file content.
4. Audit details must not include raw MinIO internal error.
5. If upload, download, or metadata delete succeeds but audit write fails, the user operation still returns its normal success response.
6. Audit write failure must be logged at `ERROR` level with request ID, actor ID when available, Workspace ID when available, event type, and resource ID.
7. P0-02 does not implement audit log UI, export, or cleanup.

---

## 11. Runner, Storage, and External Dependency

### 11.1 Storage Dependency

This slice depends on MinIO.

Rules:

1. API is the only application component that reads and writes MinIO for Dependency Files.
2. Web uploads and downloads through API only.
3. Web never receives MinIO credentials.
4. Web never receives browser-visible presigned URLs.
5. Web never receives object keys.
6. API checks bucket availability through the storage health behavior defined by `07-storage-artifacts-minio.md`.
7. If storage is unavailable, upload and download return `STORAGE_UNAVAILABLE`.
8. P0-02 does not auto-create bucket, mutate bucket policy, enforce server-side encryption, configure lifecycle, or change storage backend.

### 11.2 Storage Adapter Boundary

Use the storage adapter boundary defined by `07-storage-artifacts-minio.md`.

P0-02 requires these adapter capabilities:

```text
put_stream(bucket, object_key, stream, size_limit) -> PutResult(size_bytes, sha256)
get_stream(bucket, object_key) -> stream metadata + iterator
delete_object_best_effort(bucket, object_key) -> result
health_check() -> status
```

Rules:

1. P0 implementation may be MinIO-specific behind this adapter.
2. Do not implement a user-selectable storage backend interface.
3. Adapter must not log credentials.
4. Adapter must support streaming upload and download.
5. Adapter must surface safe domain errors to API layer.

### 11.3 Transaction Boundary

Rules:

1. Do not hold long DB transactions while streaming large files.
2. Do not make metadata downloadable before MinIO upload and hash computation succeed.
3. Check active filename conflict before streaming where practical.
4. Use the DB unique index as the final guard against concurrent same-name uploads.
5. If metadata insert fails after object upload, the metadata must not become visible.
6. If metadata insert fails after object upload, best-effort object deletion is allowed.
7. Best-effort object deletion failure must be logged safely and must not expose the object to users without metadata.
8. Do not create a durable orphan scanner in P0-02.

### 11.4 Runner and Taurus

This slice has no Runner, Load Node, SSH, Taurus, Run state machine, or artifact summary dependency.

Rules:

1. Runner must not import or consume Dependency File code in P0-02.
2. P0-02 does not generate Taurus YAML.
3. P0-02 does not create execution bundle manifests.
4. P0-02 does not create Run Artifact metadata.
5. P0-02 does not parse Run Artifact CSVs.
6. P0-02 does not alter Run state machine, node lease, callback, heartbeat, Stop, or artifact behavior.

Future integration ownership:

| Future concern | Owning slice |
| --- | --- |
| Dependency File selected by Scenario | `P0-05-visual-scenario-debug-run.md` |
| Dependency File selected by Test Plan | `P0-06-test-plan-run-now.md` |
| Dependency File captured in Run Snapshot | `P0-06-test-plan-run-now.md` |
| Dependency File copied or referenced by Runner execution bundle | `P0-04` / `P0-06` contract boundary, as defined by those slices |
| Dependency File shown as referenced or in use | First slice that creates real references |
| Run Artifact CSV summary | `P0-07-run-report-artifacts-validity.md` or equivalent Run Report slice |

---

## 12. Tests

### 12.1 API Unit Tests

Required coverage:

1. Valid safe filename examples.
2. Invalid filename examples: Unicode, whitespace, slash, backslash, `.`, and `..`.
3. Sensitive filename blocklist examples.
4. `.pem` certificate-style filename allowed when not sensitive, such as `cert-prod.pem`.
5. `.key` certificate-style filename allowed when not sensitive, such as `client.key`.
6. Extension allowlist default empty means no extension rejection.
7. Extension allowlist non-empty rejects unsupported extension.
8. Object key construction for Dependency File.
9. Object key construction never normalizes unsafe path into safe path.
10. SHA-256 streaming calculation.
11. Size counting.
12. Size limit rejection.
13. Case-insensitive active filename uniqueness behavior.
14. Same filename allowed after metadata delete.
15. Reference-check boundary returns not in use in P0-02.
16. Delete status transition sets `deleted_by` and `deleted_at`.
17. Content-Disposition filename generation.
18. Safe error mapping for MinIO failures.
19. Audit detail construction excludes credentials, object key, and file content.
20. Audit failure behavior does not fail successful user operations.

### 12.2 API Integration Tests

Required endpoint coverage:

1. Upload success stores object in MinIO under the required prefix.
2. Upload success creates metadata with actual `sizeBytes` and `sha256`.
3. Upload success returns metadata without `storageBucket` or `storageObjectKey`.
4. Upload rejects invalid filename with `INVALID_FILENAME`.
5. Upload rejects sensitive filename with `INVALID_FILENAME`.
6. Upload rejects oversized file with `PAYLOAD_TOO_LARGE`.
7. Upload rejects duplicate active filename in same Workspace with `DEPENDENCY_FILE_NAME_CONFLICT`.
8. Upload allows same filename in a different Workspace if the test fixture contains multiple Workspaces.
9. Upload allows same filename after previous metadata delete.
10. Upload requires auth and CSRF.
11. Upload rejects non-multipart request with `UNSUPPORTED_MEDIA_TYPE` or `INVALID_REQUEST` according to request shape.
12. List returns only current Workspace active rows.
13. List does not return deleted rows.
14. List supports `page`, `pageSize`, `q`, and supported `sort` values.
15. List rejects `sort=-filename`.
16. List response does not expose object key.
17. Get returns metadata for an active file.
18. Get hides cross-Workspace resource with `RESOURCE_NOT_FOUND`.
19. Get hides deleted metadata with `RESOURCE_NOT_FOUND`.
20. Download streams attachment and no-store.
21. Download does not expose object key.
22. Download requires user access to current Workspace.
23. Download of deleted metadata returns `RESOURCE_NOT_FOUND`.
24. Delete succeeds when not in use.
25. Delete returns `FILE_IN_USE` when the reference-check boundary reports in use.
26. Delete writes metadata status as `deleted`.
27. Delete does not physically delete MinIO object in P0-02.
28. All endpoints require session.
29. All write endpoints require CSRF.
30. All endpoints enforce Workspace access.
31. Storage outage maps to `STORAGE_UNAVAILABLE` safely.
32. Upload, download, and delete write audit events with safe details.
33. Audit write failure does not fail a successful upload, download, or delete.

### 12.3 MinIO Integration Tests

Required coverage:

1. API streams upload to real MinIO in the test profile.
2. API streams download from real MinIO in the test profile.
3. Uploaded bytes equal downloaded bytes.
4. Stored object key follows the required prefix.
5. Object key is not returned to Web API responses.
6. MinIO unavailable upload returns `STORAGE_UNAVAILABLE`.
7. MinIO unavailable download returns `STORAGE_UNAVAILABLE`.
8. Test files are large enough to prove streaming code paths without committing huge fixtures.

### 12.4 Contract Tests

Required coverage:

1. OpenAPI paths exist under `/v1/dependency-files`.
2. Operation IDs are exactly:
   - `listDependencyFiles`
   - `uploadDependencyFile`
   - `getDependencyFile`
   - `downloadDependencyFile`
   - `deleteDependencyFile`
3. List response is an offset envelope.
4. Metadata schemas exclude `storageBucket` and `storageObjectKey`.
5. Upload endpoint documents `multipart/form-data`.
6. Upload endpoint documents size, filename, duplicate, storage, auth, Workspace, and CSRF errors.
7. Download endpoint documents a binary `200` response.
8. Download endpoint documents shared JSON error responses.
9. Write endpoints document CSRF header requirement.
10. Workspace-aware endpoints document `x-workspace-id` behavior.
11. Error responses use the shared error shape.
12. Slice-specific error code is documented.
13. Generated Web client/types are fresh.
14. Internal storage details do not appear in public OpenAPI examples.

### 12.5 Web Tests

Required coverage:

1. Empty list state.
2. Loading state.
3. API error state with retry.
4. Search input updates `q` query.
5. Upload form client-side validation for unsafe filename.
6. Upload success refreshes list.
7. `DEPENDENCY_FILE_NAME_CONFLICT` UI branch.
8. `INVALID_FILENAME` UI branch.
9. `PAYLOAD_TOO_LARGE` UI branch.
10. `STORAGE_UNAVAILABLE` UI branch.
11. Download action calls generated client operation or stable download path.
12. Delete confirmation behavior.
13. `FILE_IN_USE` UI branch.
14. Submit buttons disabled while pending.
15. AppLayout highlights `Assets -> Dependency Files`.
16. P1/P2 navigation entries remain hidden.
17. Web uses generated client/types from `@surgepilot/contracts`.
18. Web does not render Dependency File preview.

### 12.6 E2E Smoke

Add one lightweight Playwright smoke under `tests/e2e/`:

```text
authenticated user
  -> opens /assets/dependency-files
  -> uploads Dependency File
  -> sees file in list
  -> downloads file
  -> deletes file
  -> sees file removed from normal list
```

Rules:

1. The smoke may use the existing P0 auth setup path from P0-00.
2. The smoke must use product routes and public APIs.
3. The smoke must not require real Runner, SSH, Taurus, external network, P1/P2 services, or non-MinIO storage.
4. The smoke may require the P0 MinIO test profile.
5. The smoke is wired to `make verify-e2e`; it does not enter the default `make verify` gate unless the repository later makes storage smoke part of the default gate.
6. If `make verify-e2e` already has a storage smoke slot, P0-02 must reuse that slot instead of creating a parallel E2E category.

Implementation backfill:

1. The P0 API implementation uses FastAPI / Starlette multipart parsing into `UploadFile`, then streams the spooled file object to the MinIO adapter while computing SHA-256 and actual size. It does not keep the whole file in application memory.
2. The API rejects requests whose `Content-Length` is larger than the configured Dependency File max size plus multipart overhead before parsing the multipart body. The storage adapter still enforces the exact file-byte limit while reading.
3. Metadata creation failures after a successful object write trigger best-effort cleanup of only the current upload's MinIO object. This does not change user-initiated metadata delete, which remains metadata-only in P0-02.
4. A real MinIO storage adapter round-trip is wired into `make verify-e2e` after the dev MinIO profile starts.
5. Storage warning logs use safe error codes at warning level; raw MinIO exception details are limited to debug logs.
6. Review follow-up adds resolved `x-workspace-id` on Workspace-scoped error responses, keeps download OpenAPI `200` binary-only, surfaces extension allowlist field-level upload errors in Web, and strengthens MinIO readiness from bucket-exists to a write/read/delete probe.
7. Dependency File upload, download, and metadata delete audit writes use an independent DB session and transaction. Upload and metadata delete commit the user-visible metadata change before best-effort audit persistence, so audit DB failure is logged but cannot roll back a successful P0-02 user operation.

---

## 13. Done When

P0-02 is complete only when:

1. `apps/api/migrations/versions/0003_p0_02_dependency_files.py` creates `dependency_files` with required constraints and indexes.
2. Dependency File upload stores bytes only in MinIO under `dependency-files/{workspaceId}/{fileId}/{safeFilename}`.
3. Dependency File metadata stores `workspace_id`, `filename`, `content_type`, `size_bytes`, `sha256`, internal bucket/key, status, creator, and timestamps.
4. API never returns MinIO credentials, presigned URL, storage bucket, object key, server path, or file bytes in metadata responses.
5. Web never accesses MinIO directly.
6. API upload and download paths are streaming and memory-bounded.
7. Safe filename validator rejects unsafe filename examples.
8. Sensitive filename blocklist rejects `.env`, `.git*`, SSH private key names, and private key pattern examples.
9. Extension allowlist mechanism exists and default empty allowlist does not reject files by extension.
10. Active filenames are case-insensitively unique within one Workspace.
11. Same filename can be uploaded after metadata delete.
12. List, get, upload, download, and delete are Workspace-aware.
13. Cross-Workspace access does not leak resource existence.
14. Delete uses a reference-check boundary and returns `FILE_IN_USE` when the boundary reports references.
15. P0-02 reference-check boundary returns not in use until later slices add real references.
16. Delete performs metadata-level deletion and does not physically delete MinIO object in P0-02.
17. Upload, download, and delete write safe audit events.
18. Audit write failure behavior follows this document.
19. Dependency File preview is not implemented.
20. Dependency CSV parsing or summary is not implemented.
21. Direct browser-to-MinIO upload and presigned URL behavior are not implemented.
22. Non-MinIO storage is not implemented.
23. HTTP Range download is not implemented.
24. P1/P2 navigation and placeholder pages are not implemented.
25. OpenAPI exports the required operation IDs and schemas.
26. Generated Web client/types are fresh.
27. Unit, API, MinIO integration, contract, Web, and smoke tests cover the minimum matrix in Section 12.
28. `make generate-contracts` and the applicable verification commands pass according to repository workflow.

---

## 14. Review Checklist

Reviewers should check:

1. Does the change stay within P0 and avoid non-MinIO storage?
2. Does Web upload/download only through API?
3. Are MinIO credentials, object keys, server paths, and raw storage errors absent from Web responses and OpenAPI examples?
4. Does every query and mutation filter by resolved Workspace?
5. Does cross-Workspace access return `RESOURCE_NOT_FOUND` where required?
6. Does upload enforce CSRF?
7. Does upload stream bytes and compute hash without loading the full file into memory?
8. Does download stream bytes as attachment with `private, no-store`?
9. Does filename validation reuse the storage validator floor?
10. Does sensitive filename blocklist reject private key and `.env` examples while allowing non-sensitive certificate filenames?
11. Is extension allowlist empty by default and non-blocking in P0-02?
12. Is filename uniqueness scoped to active files in one Workspace?
13. Does delete use the reference-check boundary before metadata delete?
14. Does delete avoid physical MinIO deletion in P0-02?
15. Do audit details exclude object key, credentials, and file content?
16. Do API errors use registered codes only?
17. Does OpenAPI use exact operation IDs from this document?
18. Does Web use generated client/types rather than hand-written API shapes?
19. Are Dependency File preview, CSV parsing, tags, archive, replace, and P1/P2 routes absent?
20. Are tests added in the same change as functional code?
