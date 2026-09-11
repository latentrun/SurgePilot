# P1-06 Dependency File Preview

- Document status: Accepted for implementation
- Stage: P1
- Capability:`dependency_file_preview`
- Scope Gate:`docs/sdd/00-product-scope-and-priority.md` §6
- P1 Index:`docs/sdd/slices/P1-README.md`
- Storage Boundary:`docs/sdd/07-storage-artifacts-minio.md`
- API Contract Boundary:`docs/sdd/04-api-contract-guidelines.md`
- Security Boundary:`docs/sdd/06-security-permission-workspace.md`
- Frontend Route Boundary:`docs/sdd/08-frontend-routing-and-ui-rules.md`
- Testing Boundary:`docs/sdd/09-testing-and-acceptance-strategy.md`

## 1. Goal

P1-06 Added **Dependency File single file read-only preview** in `/assets/dependency-files`. Users can confirm the controlled text prefix content of a single uploaded Dependency File without downloading the file, thereby reducing the inefficiency of "confirm after downloading" operations.

Goal:

1. Maintain P0 Dependency File security boundary: Web is not directly connected to MinIO, and does not receive bucket, object key, presigned URL or server path.
2. Reuse existing Dependency File metadata, Workspace/session permissions, and API proxy storage access links.
3. Preview must be a convenience feature that is triggered on demand, read-only, has a byte upper limit, and has plain text rendering.
4. Generate `@surgepilot/contracts` through FastAPI / Pydantic OpenAPI, Web only consumes generated client/types.

P1-06 must not become a pre-dependency of the main link of P0 Scenario -> Test Plan -> Run -> Run Report.

## 2. PRD / Scope Trace

`docs/sdd/00-product-scope-and-priority.md` §6 Fixed P1 `Dependency Files` capabilities to "Single File Preview" and made it clear that P1 does not do Dependency Files tags, ZIP/TAR/TGZ secure decompression, or other out-of-scope asset capabilities.

This Slice locks in the following conclusions:

1. P1-06 only implements Dependency File single file read-only preview.
2. The preview prioritizes text content that can be safely decoded, including common source code, scripts, configurations, unsuffixed development files, and future new language files; text capabilities are not limited by maintaining a whitelist of source code extensions.
3. There are no historical compatibility issues in the current development stage; there is no need for old endpoints, old response schema, old clients or old data compatibility layers.
4. The implementation of P1-06 is authorized only after this document exists as the active P1 Slice SDD.
5. `P1-README.md` is only used as an index; the implementation must not be started directly from the placeholder copy.

If the implementation requires direct browser connection to MinIO, presigned URL, HTTP Range, compressed package unpacking, universal file parsing platform, background tasks, cache, queue, new object storage adaptation or new Dependency File tag/description/version model, you must first add ADR or update Scope Gate.

## 3. In Scope

1. API: Added `GET /api/v1/dependency-files/{dependencyFileId}/preview`.
2. API schema: Added preview response, preview kind enum, and unavailable reason enum.
3. API service: bounded prefix read based on existing Dependency File metadata and server-side MinIO client.
4. Preview eligibility: use the known binary extension denylist to skip obvious binary files, and the remaining files are determined by strict UTF-8 decoding, NUL/binary marker detection and byte upper limit whether they can be text previewed; `contentType` is only used for display/assistance.
5. Preview result: Return prefix text for safe decodable text; return clear status or error for known binary, binary content, undecodable, or storage unavailable.
6. Web: Add the `Preview` operation in the Dependency Files list line. Click to open the side drawer and lazily load the preview.
7. Web rendering: Only text node / `<pre>` is used to display the preview content, and the Download entry is retained.
8. Tests / verification gates: API unit/route/contract freshness, Web component, minimal Playwright smoke.

## 4. Out of Scope

1. Unpack ZIP, TAR, TGZ or other archive files.
2. CSV schema detection, paging, large file parsing, online search, syntax highlighting, and difference comparison.
3. Online editing, replacement, rename, version, archive, description, tag or Dependency File metadata extension.
4. Browser direct connection MinIO, presigned URL, HTTP Range, object key exposed.
5. New DB table, migration, index, cache, queue, background task or worker preprocessing.
6. Universal file parsing platform, plug-in mechanism, malware scanning, content disarm, and universal sensitive information desensitization framework.
7. Runner, api-worker, Run Snapshot, Run state machine, Taurus builder or Load Node behavior changes.
8. New open-source runtime dependency.
9. `dependency_file.previewed` audit event; P1-06 only relies on ordinary requestId log troubleshooting.

## 5. Preconditions

1. Dependency File list/upload/detail/download/delete already exists in `apps/api/app/routes/dependency_files.py`.
2. Dependency File public schema currently only returns business fields, not `storage_bucket` or `storage_object_key`.
3. The API storage client currently reads and writes objects through the server-side MinIO credential; the Web does not touch MinIO.
4. The Workspace context continues to use the `x-workspace-id` header; the route path does not contain the workspace ID.
5. Auth continues to use cookie session; GET preview does not require CSRF.
6. The current Dependency Files management page on the Web is `apps/web/src/features/dependency-files/pages/dependency-files-page.tsx`.
7. Web API calls continue to use `@surgepilot/contracts` via generated client/types; handwritten request/response types are not allowed.
8. There are no historical compatibility issues at the current development stage; there is no need to be compatible with old Dependency File preview endpoints or old clients.

## 6. Locked Core Decisions

| ID | Decision |
| --- | --- |
| DFP-01 | P1-06 is a single-file read-only preview feature for Dependency Files only. |
| DFP-02 | Preview is implemented as a public business API under `/api/v1/dependency-files/{dependencyFileId}/preview`. |
| DFP-03 | The API must reuse existing session auth, Workspace resolution and `get_dependency_file` Workspace filtering before reading storage. |
| DFP-04 | Web must never access MinIO directly and must never receive bucket, object key, presigned URL, server path or storage credential data. |
| DFP-05 | Preview eligibility is content-first: a known-binary extension denylist skips obvious binary files, while strict UTF-8 decoding plus NUL/binary marker checks decide whether all other files can be returned as text. `contentType` is not a security decision input. |
| DFP-06 | The default visible preview size is `DEPENDENCY_FILE_PREVIEW_MAX_BYTES=65536`; oversize text returns `truncated=true` and a bounded prefix, not an error. |
| DFP-07 | Known binary, binary marker and decode failures are user-visible unavailable states, not platform errors. |
| DFP-08 | Storage client failure remains `503 STORAGE_UNAVAILABLE` and must not be hidden as successful text preview. |
| DFP-09 | Frontend rendering must use plain text / `<pre>` only; `dangerouslySetInnerHTML` is forbidden for preview content. |
| DFP-10 | P1-06 does not add DB migration, new middleware, cache, queue, worker task, audit event or new dependency. |
| DFP-11 | Existing upload/download/delete contracts remain unchanged. |
| DFP-12 | No historical compatibility layer is required in the current development stage. |

## 7. Architecture

```text
Dependency Files page
  -> user clicks Preview on one row
  -> Web opens side drawer and lazily calls generated previewDependencyFile client
  -> API validates session and Workspace via existing deps
  -> API validates dependencyFileId and resolves metadata with get_dependency_file(workspace_id, dependency_file_id)
  -> API checks known-binary extension denylist
  -> API reads at most a bounded prefix from MinIO using server-side storage client
  -> API strict-decodes safe UTF-8 text or returns an unavailable state/error
  -> Web renders plain text preview or unavailable/error state
  -> Download remains available through existing downloadDependencyFile API proxy
```

Component boundaries:

| Component | Responsibility | Forbidden |
| --- | --- | --- |
| `apps/api/app/routes/dependency_files.py` | Expose the preview route, enforce auth/Workspace, attach `x-workspace-id`, return OpenAPI-backed response. | Returning storage internals, presigned URLs, raw stack traces, server paths, or preview content in logs. |
| `apps/api/app/schemas/dependency_files.py` | Define `DependencyFilePreviewResponse` and fixed preview enums using existing `ApiSchema` camelCase behavior. | Hand-written OpenAPI as source of truth or schema fields exposing bucket/object key. |
| `apps/api/app/services/dependency_files.py` or `apps/api/app/services/dependency_file_preview.py` | Implement denylist classification, bounded stream read, text classification and unavailable-state mapping. | Full-object reads, archive extraction, CSV parsing, schema inference, background jobs or storage backend abstraction. |
| `apps/api/app/services/storage.py` | Continue owning server-side MinIO access. The implementation may add a small bounded-read helper only if it keeps existing upload/download contracts unchanged. | Browser-visible storage access, HTTP Range contract, object-key exposure, credential exposure. |
| `@surgepilot/contracts` | Generated client/types from FastAPI OpenAPI. | Manual generated-file edits as source of truth. |
| `apps/web/src/features/dependency-files/pages/dependency-files-page.tsx` | Add Preview action, drawer, loading/error/unavailable/truncated states and text rendering. | Hand-written response types, `dangerouslySetInnerHTML`, object key display, hidden download bypass. |
| Runner / api-worker / DB | No change. | Any dependency on preview availability or preview precomputation. |

## 8. API Contract

### 8.1 Endpoint

| Method | Path | Operation ID | Response | Contract |
| --- | --- | --- | --- | --- |
| `GET` | `/api/v1/dependency-files/{dependencyFileId}/preview` | `previewDependencyFile` | `200 DependencyFilePreviewResponse` | Return a bounded read-only preview result for one Dependency File in the current Workspace. |

Rules:

1. The route belongs to the existing Dependency Files router.
2. The route requires cookie session auth and Workspace resolution through `x-workspace-id` / default Workspace behavior already used by Dependency File APIs.
3. The route does not require CSRF because it is a GET with no persistence side effects.
4. The route path must not include `workspaceId`.
5. The route must validate `dependencyFileId` with the existing ULID validation path and return `422 VALIDATION_ERROR` for invalid IDs.
6. The route must call `get_dependency_file(db, workspace_id=workspace.id, dependency_file_id=dependencyFileId)` before storage access.
7. The route must attach `x-workspace-id` on successful responses.
8. The route should be registered near the existing detail/download routes; readability matters, but the existing single-segment `/{dependencyFileId}` route does not match `/{dependencyFileId}/preview`.
9. API error responses use the existing `{code, message, requestId, details?}` envelope.
10. Response examples and OpenAPI schema must not include object keys, bucket names, MinIO URLs, local paths or credentials.

### 8.2 Response schema

`DependencyFilePreviewResponse` uses Python snake_case fields and OpenAPI / JSON camelCase aliases through the existing `ApiSchema` base.

| Field | Type | Required | Contract |
| --- | --- | --- | --- |
| `id` | string | yes | Dependency File business ID. |
| `filename` | string | yes | Existing safe filename. |
| `contentType` | string or null | yes | Existing metadata content type for display only. |
| `sizeBytes` | integer | yes | Existing metadata size. |
| `sha256` | string | yes | Existing metadata hash. |
| `previewKind` | `text | unsupported` | yes | `text` only when `text` contains renderable preview content. |
| `canPreview` | boolean | yes | `true` only for renderable text preview. |
| `truncated` | boolean | yes | `true` when the stored object has more readable bytes than `maxBytes`. Unsupported states must return `false`. |
| `maxBytes` | integer | yes | Effective byte limit used for this response. Default `65536`. |
| `text` | string or null | yes | UTF-8 decoded preview text when `canPreview=true`; otherwise `null`. |
| `reason` | `binary_content | decode_failed | storage_unavailable` or null | yes | Reason for unavailable preview. `null` when `canPreview=true`. |

Examples:

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "filename": "users.csv",
  "contentType": "text/csv",
  "sizeBytes": 24,
  "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
  "previewKind": "text",
  "canPreview": true,
  "truncated": false,
  "maxBytes": 65536,
  "text": "id,name\n1,Ada\n",
  "reason": null
}
```

```json
{
  "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "filename": "image.png",
  "contentType": "image/png",
  "sizeBytes": 1024,
  "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
  "previewKind": "unsupported",
  "canPreview": false,
  "truncated": false,
  "maxBytes": 65536,
  "text": null,
  "reason": "binary_content"
}
```

Enum rules:

1. `previewKind` has exactly two P1-06 values: `text`, `unsupported`.
2. `reason` values are stable lower snake case strings for Web localization.
3. `binary_content` covers both known-binary extension denylist matches and binary markers found in the bounded prefix.
4. `storage_unavailable` is reserved for UI state normalization, but storage read failures should normally return `503 STORAGE_UNAVAILABLE` rather than `200`.
5. No response field may contain storage bucket, object key, presigned URL, server path or MinIO endpoint.

### 8.3 Error contract

| Condition | HTTP | Code | Contract |
| --- | ---: | --- | --- |
| Invalid `dependencyFileId` | 422 | `VALIDATION_ERROR` | Same field-level validation style as existing Dependency File APIs. |
| Missing/invalid auth | 401 | existing auth code | Existing auth middleware behavior. |
| Workspace access denied | 403 | existing workspace/permission code | Existing Workspace enforcement behavior. |
| File not found in current Workspace or deleted | 404 | `RESOURCE_NOT_FOUND` | Must not reveal whether the ID exists in another Workspace. |
| Storage client unavailable | 503 | `STORAGE_UNAVAILABLE` | Safe message only; no bucket/object key/path. |
| Invalid explicit preview kind if a future query is added | 400 or 422 | `UNSUPPORTED_PREVIEW_TYPE` | P1-06 does not add such a query; normal unavailable files return `200` with `previewKind=unsupported`. |

Oversized text is not an error. It returns `200`, `canPreview=true`, `truncated=true`, and a bounded text prefix.

## 9. Preview Classification and Bounded Read Rules

Configuration:

| Config | Default | Contract |
| --- | ---: | --- |
| `DEPENDENCY_FILE_PREVIEW_MAX_BYTES` | `65536` | Maximum visible preview bytes. Must be positive and small enough for API/Web memory safety. |
| `DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS` | `.png,.jpg,.jpeg,.gif,.webp,.bmp,.ico,.svg,.pdf,.zip,.tar,.gz,.tgz,.bz2,.xz,.7z,.rar,.jar,.war,.class,.so,.dll,.dylib,.exe,.bin,.dat,.woff,.woff2,.ttf,.otf,.eot,.mp3,.mp4,.mov,.avi,.mkv,.webm` | Known-binary extension denylist. Denylist matches skip object body read and return `binary_content`. |

Rules:

1. Denylist extension matching is case-insensitive and based on the stored `filename` suffix.
2. Files with no suffix or uncommon/source-code suffixes are not rejected by name. Examples such as `Makefile`, `Dockerfile`, `.env.example`, `.gitignore`, `script.py`, `build.gradle`, `main.go`, `handler.ts`, `surgepilot.groovy`, `schema.sql`, and future source languages may be previewed when content checks pass.
3. Known-binary denylist matches must return `previewKind=unsupported`, `canPreview=false`, `reason=binary_content` without reading the object body.
4. `contentType` must not make a known-binary extension previewable and must not make a non-denied file unpreviewable.
5. Non-denied files must pass content checks before returning text.
6. The service must read from storage in chunks and stop after enough bytes to determine truncation. It must not read the whole object into memory.
7. The implementation may read at most `maxBytes + 1` stored bytes to determine `truncated`; only the first `maxBytes` bytes are eligible for `text`.
8. The storage stream must be closed after preview read; if the underlying response exposes `release_conn`, it should be called.
9. If the prefix contains NUL bytes or other binary-only markers, return `reason=binary_content`.
10. UTF-8 decoding must be strict. Invalid UTF-8 before the truncation boundary returns `reason=decode_failed`.
11. If truncation cuts through a multibyte UTF-8 sequence at the `maxBytes` boundary, the decoder must not return `decode_failed` solely for that incomplete trailing character. It should omit only the incomplete trailing character while still returning `truncated=true` and must not switch to lossy replacement characters.
12. API and Web logs must not include preview text.
13. Preview output is not a validation result, parser result, schema detection result, security scan result or execution input.

## 10. Web UX Contract

The existing `/assets/dependency-files` page adds a row-level Preview action.

Behavior:

1. Clicking Preview opens a right-side drawer or drawer-like modal for one file.
2. The preview request is lazy: it starts only after the user chooses a file to preview.
3. Opening a different file must cancel, ignore, or supersede the previous visible result so stale content is not shown under the wrong filename.
4. Loading state shows filename and a safe progress message.
5. Available text preview renders in a bounded scroll area using `<pre>` or equivalent text nodes.
6. `truncated=true` shows a visible "Preview truncated" notice with the effective byte limit.
7. Unsupported states show a friendly reason and keep the existing Download action available.
8. `STORAGE_UNAVAILABLE` shows a retry affordance and keeps Download visible only if the existing download path remains available to the user.
9. Copy action may copy only the currently returned preview `text`; it must not fetch full file contents.
10. HTML, XML, JSON, YAML and logs are displayed as text. `dangerouslySetInnerHTML` is forbidden.
11. The drawer must not display bucket, object key, MinIO URL, server path, credentials or raw error stack.
12. List, upload, delete and download behavior must remain unchanged.

Suggested user-facing unavailable copy:

| Reason / error | Copy intent |
| --- | --- |
| `binary_content` | "This file looks binary, so inline preview is disabled." |
| `decode_failed` | "This file is not valid UTF-8 text, so inline preview is disabled." |
| `STORAGE_UNAVAILABLE` / `storage_unavailable` | "File storage is temporarily unavailable. Try again later." |

## 11. Security and Privacy Requirements

1. API must enforce auth, Workspace and permission checks before any storage read.
2. PostgreSQL metadata remains authoritative for Workspace ownership and UI listing; MinIO object existence alone never grants access.
3. API must not return bucket, object key, MinIO URL, presigned URL, server path or credentials.
4. Web must not call MinIO directly and must not construct storage URLs.
5. Preview content must not be written to normal logs, audit details, analytics events or error details.
6. Preview is authorized at the same user/workspace boundary as existing Dependency File detail/download.
7. P1-06 does not perform generic sensitive-data redaction. Authorized users who can download the file may see its preview text.
8. Preview rendering must be text-only to prevent XSS from HTML/XML/SVG-like content.
9. Cache headers should remain private/no-store for any response path that could expose file content.
10. Request/response examples must use harmless sample content.
11. The content-first preview rule is not a parser or trust boundary. It only decides whether to display a bounded plain-text prefix to an already authorized user.

## 12. Observability and Audit

1. P1-06 does not add a `dependency_file.previewed` audit event.
2. Normal API request logging and `x-request-id` are sufficient for troubleshooting.
3. Logs may include `dependencyFileId`, `workspaceId`, safe status code and request ID.
4. Logs must not include preview `text`, storage object key, bucket, MinIO endpoint, credentials or raw storage exception details outside existing safe debug-level behavior.
5. Storage failures continue to use `STORAGE_UNAVAILABLE` handling.

## 13. Data, Migration and Compatibility

1. No DB table, column, enum, index or migration is required.
2. Existing Dependency File metadata remains unchanged.
3. Existing upload/download/delete/detail contracts remain unchanged.
4. Existing `DEPENDENCY_FILE_ALLOWED_EXTENSIONS` upload behavior remains independent of preview binary denylist.
5. Current development stage has no historical compatibility requirement; do not add legacy route aliases or schema compatibility fields.
6. Future archive extraction, versioning, tags, object-storage expansion or HTTP Range work must be designed in a separate Slice/ADR.

## 14. Implementation Plan

1. Add `DependencyFilePreviewResponse` and enum types to `apps/api/app/schemas/dependency_files.py`.
2. Add `DEPENDENCY_FILE_PREVIEW_MAX_BYTES` and `DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS` settings to `apps/api/app/core/config.py`.
3. Add preview helper/service for known-binary extension classification and bounded UTF-8 prefix reading.
4. Add `GET /api/v1/dependency-files/{dependencyFileId}/preview` to `apps/api/app/routes/dependency_files.py`.
5. Add API tests for text, no-extension text, common source files, known-binary extension, binary marker, invalid UTF-8, truncation at an ASCII boundary, truncation at a multibyte UTF-8 boundary, invalid ID, cross-Workspace access, not found, storage unavailable and no object key leakage.
6. Run `make generate-contracts` and commit generated OpenAPI/client changes.
7. Update Web Dependency Files page to use generated `previewDependencyFile` client and generated `DependencyFilePreviewResponse` type.
8. Add Web component tests for drawer states, truncated notice, binary-content state, decode-failed state, HTML-as-text rendering, copy behavior and no stale preview under wrong filename.
9. Add a minimal Playwright smoke test that opens Dependency Files, previews a seeded text/source/no-extension file and verifies object key/HTML injection is not shown.
10. Run `make verify`; if local infra is incomplete, run the closest available subset and record gaps.

## 15. Tests

Minimum tests:

1. API service tests:
   - common text files return decoded `text`;
   - no-extension files such as `Makefile` / `Dockerfile` may preview when UTF-8 content checks pass;
   - common source extensions such as `.sh`, `.go`, `.java`, `.js`, `.ts`, `.py`, `.groovy`, `.sql`, `.toml` may preview when UTF-8 content checks pass;
   - known-binary denylist extensions avoid storage body read and return `binary_content`;
   - binary/NUL content returns `binary_content`;
   - invalid UTF-8 before the truncation boundary returns `decode_failed`;
   - object larger than max returns `truncated=true` and bounded text;
   - a multibyte UTF-8 character split exactly at `maxBytes` returns `truncated=true` without misclassifying as `decode_failed`;
   - stream is closed/released after bounded read.
2. API route tests:
   - `GET /api/v1/dependency-files/{dependencyFileId}/preview` returns OpenAPI-shaped response;
   - no CSRF is required for GET;
   - invalid ULID returns `422 VALIDATION_ERROR`;
   - missing/unauthorized Workspace cannot preview;
   - cross-Workspace file returns `404 RESOURCE_NOT_FOUND` or existing access-safe behavior without existence leak;
   - storage failure returns `503 STORAGE_UNAVAILABLE`;
   - response never contains `storageBucket`, `storageObjectKey`, bucket name, object key or MinIO URL.
3. Contract tests:
   - OpenAPI contains operation ID `previewDependencyFile`;
   - generated client/types are fresh after `make generate-contracts`.
4. Web component tests:
   - Preview action opens drawer and lazy-loads once selected;
   - loading, available, truncated, binary-content, decode-failed and storage-error states render correctly;
   - HTML/XML sample is displayed as escaped text;
   - copy copies only returned preview text;
   - switching files does not show stale preview under the new filename.
5. E2E smoke:
   - seeded or uploaded text/source/no-extension Dependency File can be previewed from `/assets/dependency-files`;
   - known-binary file shows unavailable state and Download remains available;
   - object key and MinIO URL are not visible.

## 16. Done When

This Slice is complete only when:

1. `docs/sdd/slices/P1-06-dependency-preview.md` is the active Slice SDD and `P1-README.md` marks it active.
2. Preview API exists with operation ID `previewDependencyFile` and generated contracts are fresh.
3. API reads only a bounded prefix and never returns storage internals.
4. Known-binary, binary marker, decode-failed, multibyte-boundary truncation and storage-unavailable states are covered by tests.
5. Common source-code and no-extension text files can preview when UTF-8 content checks pass.
6. Web Preview drawer uses generated client/types and renders content as plain text only.
7. Existing Dependency File upload/detail/download/delete behavior remains unchanged.
8. No DB migration, background job, cache, queue, new dependency, presigned URL, HTTP Range or MinIO direct Web access is introduced.
9. `make generate-contracts` passes.
10. `make verify` passes, or any environment gap is explicitly recorded with the closest successful subset.
11. Independent review finds no remaining Slice-blocking issues.

## 17. Open Questions

None.

## 18. Implementation Backfill

Implemented in `feature/p1-06-dependency-preview`.

Engineering facts:

1. API preview logic lives in the existing Dependency File service/router boundary:
   - `apps/api/app/services/dependency_files.py`
   - `apps/api/app/routes/dependency_files.py`
   - `apps/api/app/schemas/dependency_files.py`
2. Preview configuration is environment-driven through:
   - `DEPENDENCY_FILE_PREVIEW_MAX_BYTES`
   - `DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS`
3. Web uses the generated `previewDependencyFile` contract through
   `apps/web/src/app/api-client.ts` and renders preview content as plain text
   in the existing Dependency Files page drawer.
4. The Playwright P0-02 Dependency Files smoke now starts or reuses a local
   MinIO-compatible bucket before upload/preview/download checks.

Added verification coverage:

1. API service tests cover text, no-extension/source text, known-binary
   denylist, binary markers, invalid UTF-8, ASCII truncation, multibyte-boundary
   truncation and stream cleanup.
2. API route tests cover preview success, GET without CSRF, invalid ULID,
   Workspace isolation, storage unavailable, unavailable states and storage
   internal non-leakage.
3. Contract tests cover operation ID `previewDependencyFile`, response schema,
   preview enums, header rules and generated contract freshness.
4. Web component tests cover lazy loading, available/truncated text preview,
   unsupported state, storage-error retry, copy behavior, HTML-as-text rendering
   and stale preview suppression.
5. Playwright smoke covers text preview, binary unavailable state, Download
   availability and absence of object-key / MinIO URL display.

Verification commands run:

```bash
make generate-contracts
make verify
pnpm exec playwright test tests/e2e/p0_02_dependency_files.spec.ts
```

Remaining risks: None.
