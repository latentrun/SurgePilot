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

## Initial behavior

Dependency Files support upload, list, download, and deletion protection. Run Artifacts support Runner upload, metadata listing, download, and structured summary extraction for recognized final statistics. The application checks bucket readiness but does not mutate bucket policy or require versioning, lifecycle, or server-side encryption settings.

Local filesystem storage, additional object stores, direct-to-MinIO browser flows, archive extraction, inline file editing, Range downloads, retention automation, quotas, and storage plugins are outside the initial milestone.
