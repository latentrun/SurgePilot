# ADR-0003: P0 MinIO Only

- Status: Accepted
- Scope: P0 Dependency Files, Run Artifacts, API storage boundary, and deployment

## Context

P0 needs object storage for Dependency Files and Run Artifacts while keeping the deployment reproducible in Docker Compose. Storage must support streaming upload/download through the API, Workspace-aware metadata, path safety, artifact hash checks, and deterministic tests. The PRD places non-MinIO storage backends and generic storage extensibility in later scope.

## Options Considered

1. **MinIO only for P0**
   - Pros: S3-compatible behavior in local Compose, simple operational model, deterministic tests, single storage adapter, aligns Dependency Files and artifacts.
   - Cons: deployments that prefer another backend must wait for a later storage ADR and Slice.
2. **Local filesystem storage**
   - Pros: simple for a single developer machine.
   - Cons: weak container portability, harder multi-process access, unsafe path handling pressure, and poor parity with future object storage.
3. **Multiple object storage backends in P0**
   - Pros: more deployment options.
   - Cons: expands configuration, test matrix, error handling, and security surface before P0 needs it.
4. **Direct browser-to-object-storage upload**
   - Pros: reduces API bandwidth.
   - Cons: exposes storage-specific credentials or presigned flows to Web and complicates Workspace authorization in P0.

## Decision

P0 uses MinIO as the only application-supported object storage backend.

The API owns all MinIO access. Web and Runner do not receive MinIO credentials and do not access MinIO directly. Web uploads and downloads through API endpoints. Runner uses API-mediated streaming upload through API internal artifact endpoints. API validates authentication, Workspace, permissions, object key construction, size, hash, and path safety before writing metadata or streaming bytes.

P0 does not implement local filesystem storage, AWS S3, Aliyun OSS, GCS, generic storage plugins, direct browser-to-MinIO upload, browser-visible presigned URLs, or application-managed bucket policy/lifecycle setup.

## Consequences

Positive consequences:

1. Dependency Files and Run Artifacts share one storage boundary.
2. P0 tests can run against a predictable MinIO service.
3. Web does not learn bucket names, object keys, endpoints, access keys, or secret keys.
4. Path safety and Workspace checks stay centralized in the API.

Costs and constraints:

1. Deployments must provide a MinIO-compatible service for P0.
2. Object storage portability is intentionally deferred.
3. Non-MinIO backends require a future ADR and implementation Slice.
4. Deployment-level MinIO versioning, encryption, backup, and lifecycle policy may exist, but P0 application code must not depend on them.

## Related ADRs

- `ADR-0001-monorepo.md`
- `ADR-0002-runner-independent-app.md`
- `ADR-0006-p0-separate-api-worker.md`

## References

- `docs/sdd/00-product-scope-and-priority.md`
- `docs/sdd/01-architecture-overview.md`
- `docs/sdd/07-storage-artifacts-minio.md`
- `docs/sdd/slices/P0-02-dependency-files-minio.md`
- `docs/sdd/slices/P0-07-run-report-artifacts-validity.md`
