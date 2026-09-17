# ADR-0016: P2 Help AI Agents and System OpenAPI Bootstrap

- Status: Accepted
- Scope: P2-04 authenticated Help AI Agents guidance, official Public API AI skill source download, and first-Admin system OpenAPI bootstrap import
- Active Slice: `docs/sdd/slices/P2-04-help-ai-agents-system-openapi-bootstrap.md`
- Related ADRs: `ADR-0010`, `ADR-0012`

## Context

SurgePilot already has an accepted API Catalog, a PAT-authenticated programmatic public API, and one governed repo-maintained Public API AI skill source package. Those capabilities are currently disconnected in the product:

1. `/help` is still only a planned P2 route and does not provide agent-native guidance.
2. The official skill source exists only in the repository and cannot be downloaded by a logged-in user.
3. A newly bootstrapped installation does not place SurgePilot's own curated Web/business OpenAPI document in the Default Workspace API Catalog.

The enhancement must remain small. It must not turn SurgePilot into an AI runtime, installer, marketplace, SDK platform, background ingestion service, or API-to-Scenario/Test Plan generation system.

The system OpenAPI import also needs a single runtime-safe export implementation. Reading a generated repository artifact from the container would create stale-file and image-layout coupling, while importing bare `app.openapi()` would expose public-programmatic, runner-internal, health, and raw `/api` routes that are not part of the curated Web/business contract.

## Options Considered

### Option A: One bounded P2-04 enhancement package using shared runtime OpenAPI export

Accepted.

This option activates the Help page, the session-authenticated skill source download, and the one-time system OpenAPI bootstrap together. It reuses the existing API Catalog and Public API skill source package, and moves OpenAPI filtering into an API-owned shared module used by both the export script and the runtime bootstrap helper.

### Option B: Keep Help presentation-only and publish the skill through a release or marketplace pipeline

Rejected.

This would require versioning, checksums, signing, installer behavior, release publication, or marketplace governance that is explicitly outside the requested scope. It would also delay the simple logged-in source download behind a much larger distribution system.

### Option C: Import a checked-in OpenAPI file or bare `app.openapi()` during registration

Rejected.

Reading `packages/contracts/openapi/api.openapi.json` or an image-local copy couples runtime behavior to generated-file placement and freshness. Importing bare `app.openapi()` includes routes that the Web/business export intentionally removes. Both alternatives create a second contract interpretation and weaken the existing export boundary.

### Option D: Use a worker, retry queue, or startup reconciliation job

Rejected.

The bootstrap import is best-effort and non-critical. A worker or queue would introduce lifecycle, retry, deduplication, and infrastructure complexity that is not justified for one small system-owned Catalog asset.

## Decision

1. Create `P2-04 Help AI Agents and System OpenAPI Bootstrap` as one active P2 Slice.
2. Implement authenticated `/help` content with tabs ordered exactly as `Getting Started`, `AI Agents`, `Scripting`, `API Catalog`, `Troubleshooting`, and `Limits & Activation`.
3. Replace the planned `Automation` Help concept with `AI Agents` and place it second. The tab may explain API Keys, explicit Workspace ID, the Public API, official skill download, and how a user-owned local agent consumes the downloaded source package.
4. Add `GET /api/v1/account/ai-skill/download` as a cookie-session, current-user read API. It is not Workspace-scoped, does not require `x-workspace-id`, and does not use CSRF.
5. Build `surgepilot-public-api-skill.zip` on each request from the repo-maintained `packages/ai-skills/surgepilot-public-api/` source. Do not cache it, persist it, upload it to MinIO, publish it as a release artifact, or expose it through `/api/public/v1/*`.
6. Add an API-owned `SkillBundle` source resolver with exactly two default layouts: `/opt/surgepilot/ai-skills/surgepilot-public-api` first and the repository source directory second. The API image copies only that skill source directory to the container layout.
7. Document source-unavailable failures only on this route with `AI_SKILL_SOURCE_NOT_AVAILABLE`; do not add the code to `info.x-surgepilot-error-codes` or any shared error-code enum.
8. Move OpenAPI normalization, path filtering, public schema pruning, public error-code pruning, and `_export_document` into a shared module under `apps/api/app`, such as `app/services/openapi_export.py`. `scripts/export_openapi.py` and runtime code must import that module; export semantics for both committed OpenAPI artifacts remain unchanged.
9. Build the bootstrap payload from `_export_document(app.openapi(), public=False)`, then serialize it with `json.dumps(document, sort_keys=True).encode("utf-8")`. Do not read a generated OpenAPI file and do not import bare `app.openapi()`.
10. Change `register_user` to return an explicit `first_user` boolean in addition to its existing result values. The auth route must use this boolean and must not infer bootstrap status from `role == "admin"`.
11. Preserve the existing registration transaction and `db.commit()` inside `register_user`. Only after that function returns successfully with `first_user is True` may the route invoke the bootstrap import helper.
12. The bootstrap helper uses its own `SessionLocal` session and transaction. OpenAPI generation, MinIO writes, and `create_api_catalog_spec` must never run inside `begin_nested()` or the `lock_users_for_bootstrap()` lock window.
13. Import into the registered first Admin's Default Workspace with `created_by` set to that Admin. Before creation, skip when a non-deleted Catalog spec in the same Workspace already has the same SHA-256; `name` is not part of the idempotency key.
14. Reuse `UploadedApiSpec`, `validate_spec_filename`, `parse_api_spec`, and `create_api_catalog_spec` with a `.json` filename and `application/json` content type. No new Catalog storage path or model is introduced.
15. Registration success is authoritative. Any OpenAPI generation, query, MinIO, flush, or commit failure in the independent bootstrap helper is logged safely and must not change the successful registration response.
16. If `create_api_catalog_spec` has written a MinIO object and the helper's later commit fails, the helper must roll back and best-effort delete that new object's bucket/key. Existing objects skipped by idempotency must never be deleted.
17. `Limits & Activation` must state both sides of the boundary: the one-time system curated OpenAPI bootstrap is active, while user/external automatic OpenAPI ingestion remains inactive.

## Consequences

1. `ADR-0010` and `P2-00` gain one narrow system bootstrap exception without changing API Catalog's documentation-only product model.
2. `ADR-0012` and `P2-02` gain one authenticated source-download surface without turning the skill into a release, SDK, MCP server, installer, marketplace item, or server-side runtime.
3. The Web/business OpenAPI artifact includes the session download endpoint. The public OpenAPI artifact excludes it through the existing normalized public-path selection.
4. The system-imported Catalog document is generated from current runtime routes with the same curated `/v1/*` rules as `api.openapi.json`, avoiding generated-file staleness and container-file dependencies.
5. The first registration may perform a bounded synchronous best-effort Catalog import after registration commit. Import failure may leave the Default Workspace without the system spec; P2-04 adds no worker, retry loop, startup reconciliation, or admin repair UI.
6. No database migration is required because the bootstrap reuses the existing API Catalog model and storage service.

## Related ADRs

- `docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md`
- `docs/sdd/adr/ADR-0012-p2-public-api-substrate.md`
- `docs/sdd/adr/ADR-0013-p2-static-marketing-landing-logo.md`

## References

- `docs/sdd/slices/P2-04-help-ai-agents-system-openapi-bootstrap.md`
- `docs/sdd/slices/P2-00-api-catalog-scalar.md`
- `docs/sdd/slices/P2-02-public-api-substrate.md`
- `docs/sdd/00-product-scope-and-priority.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `docs/sdd/04-api-contract-guidelines.md`
- `docs/sdd/06-security-permission-workspace.md`
- `docs/sdd/08-frontend-routing-and-ui-rules.md`
- `docs/sdd/09-testing-and-acceptance-strategy.md`
- `AGENTS.md`
