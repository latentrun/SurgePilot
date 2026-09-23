# P2-04 Help AI Agents and System OpenAPI Bootstrap

- Document status: Accepted for implementation by `docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md`
- Phase: P2
- Capability: `help_ai_agents_system_openapi_bootstrap`
- Scope Gate: `docs/sdd/00-product-scope-and-priority.md` §7, amended by ADR-0016 for this Slice only
- Related Slices: `docs/sdd/slices/P2-00-api-catalog-scalar.md`, `docs/sdd/slices/P2-02-public-api-substrate.md`
- API Contract Boundary: `docs/sdd/04-api-contract-guidelines.md`
- Security Boundary: `docs/sdd/06-security-permission-workspace.md`
- Frontend Boundary: `docs/sdd/08-frontend-routing-and-ui-rules.md`
- Testing Boundary: `docs/sdd/09-testing-and-acceptance-strategy.md`
- ADR: `docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md`
- Product Version Decision: `docs/sdd/adr/ADR-0027-product-version-and-artifact-identity.md`

## 1. Core Decision

P2-04 is a bounded enhancement package with three connected outcomes:

1. `/help` becomes a real authenticated agent-native guidance page.
2. A logged-in user can download the official repo-maintained Public API AI skill source as a request-built zip.
3. The first successfully registered Admin triggers best-effort creation of SurgePilot's own curated Web/business OpenAPI document in the Default Workspace API Catalog; later API startups reconcile the existing active system-owned document once.

The package connects existing capabilities without adding a new platform subsystem. It does not add an AI runtime, SDK, MCP server, marketplace, installer, release pipeline, background ingestion worker, or API Catalog generation chain.

## 2. Scope Trace

| Source | Contract in this Slice |
| --- | --- |
| PRD P2 Help route | Activates authenticated `/help` with real product guidance. |
| `ADR-0012` / `P2-02` | Reuses the governed Public API AI skill source package and public OpenAPI snapshot; adds only a session-authenticated source download. |
| `ADR-0010` / `P2-00` | Reuses existing API Catalog validation, metadata, MinIO storage, and detail rendering; adds one system-owned document lifecycle exception. |
| `04-api-contract-guidelines.md` | Keeps FastAPI/Pydantic as source of truth, session auth for `/api/v1/*`, and separate Web/business and public artifacts. |
| `06-security-permission-workspace.md` | Preserves first-Admin serialization, registration commit ownership, Default Workspace membership, and safe logging. |
| `08-frontend-routing-and-ui-rules.md` | Activates `/help` under `RequireAuth + AppLayout` and keeps the public Marketing Landing boundary unchanged. |

## 3. In Scope

### 3.1 Help AI Agents

1. Add a real authenticated `/help` route and AppLayout Help entry.
2. Use the exact tab order defined in §6.
3. Rename the planned `Automation` concept to `AI Agents` and place it second.
4. Explain API Keys, Workspace ID, Public API use, official skill source download, and local agent consumption.
5. Clearly distinguish activated system-owned OpenAPI creation/reconciliation from forbidden user/external automatic OpenAPI ingestion.

### 3.2 Official skill source download

1. Add `GET /api/v1/account/ai-skill/download`.
2. Require an authenticated current user; allow both `user` and `admin`.
3. Do not require or resolve Workspace context.
4. Create the zip on each request from the governed source directory.
5. Return a private, non-cacheable attachment named `surgepilot-public-api-skill.zip`.
6. Copy the source package into the API container image at the governed runtime path.

### 3.3 Shared OpenAPI export

1. Move reusable OpenAPI export behavior from `scripts/export_openapi.py` into `apps/api/app`.
2. Keep current `api.openapi.json` and `public-api.openapi.json` document semantics and public pruning behavior unchanged.
3. Use the shared Web/business export function to construct the bootstrap payload at runtime.

### 3.4 System OpenAPI lifecycle

1. Return an explicit `first_user` result from account registration service code.
2. Invoke a separate best-effort helper only after the registration service has committed successfully.
3. Create the current curated Web/business OpenAPI document in the first Admin's Default Workspace when no active marked system document exists there.
4. Reuse the existing API Catalog parser, storage path, metadata model, and service.
5. Compensate a new MinIO object when the helper's database commit fails.
6. Add a server-only nullable `system_key` and conservatively adopt one unambiguous canonical historical row in Alembic.
7. At API startup, synchronously make one best-effort attempt to reconcile an existing active marked system asset: same SHA-256 is a no-op; a changed contract replaces the complete stored document and retires the old metadata in one commit. Startup does not create a missing or deleted asset.

## 4. Out of Scope

P2-04 must not implement:

1. User-supplied or externally fetched OpenAPI automatic ingestion.
2. Scheduled, periodic, or background OpenAPI reconciliation of arbitrary assets.
3. Retry workers, queues, Redis, Celery, RabbitMQ, Kafka, or a new service.
4. API Catalog operation import, version graph, version diff, coverage analysis, or schema registry.
5. OpenAPI/API Catalog to Scenario/Test Plan creation or generation.
6. AI-generated Scenarios, AI parameter tuning, or AI Run Report analysis.
7. SDK generation, MCP server, agent runtime, hosted agent, prompt platform, or arbitrary tool execution.
8. Marketplace publication, release artifact publication, signing, checksum manifest, `latest` endpoint, version selector, or automatic installation.
9. A SurgePilot-provided local agent installer or installation workflow UI.
10. Public unauthenticated skill download or PAT-authenticated skill download under `/api/public/v1/*`.
11. Skill zip persistence, MinIO storage, database metadata, CDN caching, or download history.
12. New API Catalog tables, new skill tables, or migrations beyond the server-only `system_key` identity/adoption migration.
13. Editable OpenAPI, editable Taurus YAML, or public/internal raw OpenAPI exposure outside existing governed artifacts.

## 5. Architecture and Component Boundaries

| Component | Responsibility | Must not do |
| --- | --- | --- |
| Help feature module | Render tabbed guidance and initiate the authenticated download. | Install the skill, run an agent, or claim unavailable capabilities. |
| Account AI skill route | Authenticate the current user and stream one request-built zip. | Resolve Workspace, use CSRF, persist a bundle, or expose server paths. |
| `SkillBundle` | Resolve the governed source directory and return safe source entries. | Download remote content, follow unsafe symlinks, or accept arbitrary directories from the request. |
| Shared OpenAPI export module | Normalize/filter/prune OpenAPI documents for script and runtime consumers. | Import FastAPI app state or read generated artifacts. |
| System OpenAPI helper | Build curated bytes, identify the active marked system asset, create or replace its Catalog spec as appropriate, and own commit/rollback/cleanup. | Reuse the registration session, run under the bootstrap lock, recreate a deleted asset at startup, or affect registration success. |
| Existing API Catalog service | Validate, parse, store, flush, and return metadata for the system document. | Add generation or execution semantics. |

Planned implementation anchors:

```text
apps/web/src/features/help/
apps/web/src/components/ui/tabs.tsx
apps/web/src/app/layouts/app-layout.tsx
apps/api/app/routes/account_ai_skill.py
apps/api/app/services/skill_bundle.py
apps/api/app/services/openapi_export.py
apps/api/app/services/system_openapi_bootstrap.py
scripts/export_openapi.py
apps/api/Dockerfile
```

Exact final filenames may follow existing source conventions, but implementation must backfill any differences in §16.

## 6. Help UI Contract

### 6.1 Route and access

| Route | Auth | Workspace | Layout |
| --- | --- | --- | --- |
| `/help` | Required cookie session | No Help-page data request requires Workspace context | `RequireAuth + AppLayout` |

The AppLayout Help entry becomes clickable only through this Slice. ADR-0013's public Marketing Landing remains unchanged and must not gain active Docs, API Guide, Community, GitHub, or Help links unless separately authorized.

### 6.2 Tabs

The order and labels are fixed:

1. `Getting Started`
2. `AI Agents`
3. `Scripting`
4. `API Catalog`
5. `Troubleshooting`
6. `Limits & Activation`

`Automation` must not remain as a tab label or alias.

### 6.3 AI Agents content

The `AI Agents` tab may describe only:

1. Creating and protecting an API Key through `/account/api-keys`.
2. Selecting and explicitly supplying the Workspace ID.
3. Calling the governed Public API with PAT Bearer authentication.
4. Downloading the official `surgepilot-public-api` skill source zip.
5. Extracting the source package and pointing a user-owned compatible local agent at `SKILL.md` according to that agent's own configuration model.
6. The skill's fixed safety boundary: bundled `public-api.openapi.json`, explicit Workspace ID, current public `operationId` allowlist, and confirmation before writes.

The content must not claim that SurgePilot provides an installer, marketplace, MCP server, SDK, built-in agent runtime, automatic Scenario generation, automatic tuning, or automatic report analysis.

### 6.4 Limits & Activation content

This tab must state both of these facts without ambiguity:

1. **Active:** after the first Admin registration, SurgePilot best-effort creates its curated Web/business OpenAPI in the Default Workspace API Catalog and keeps an existing active system-owned document aligned with the running contract on later API startups.
2. **Inactive:** SurgePilot does not automatically ingest user-provided URLs, external OpenAPI documents, repository specs, or arbitrary remote API definitions.

## 7. Skill Download API Contract

### 7.1 Endpoint

```http
GET /api/v1/account/ai-skill/download
```

| Field | Contract |
| --- | --- |
| Operation ID | `downloadPublicApiAiSkill` |
| Auth | `CurrentUserDep` cookie session |
| Allowed roles | `user`, `admin` |
| CSRF | Not required; safe read |
| Workspace header | Not required and not resolved |
| Success status | `200 OK` |
| Success content type | `application/zip` |
| Attachment filename | `surgepilot-public-api-skill.zip` |
| Cache header | `Cache-Control: private, no-store` |

The FastAPI route returns `StreamingResponse` with the fixed attachment and cache headers. The route appears in `packages/contracts/openapi/api.openapi.json` after path normalization as `/v1/account/ai-skill/download`. It must not appear in `packages/contracts/openapi/public-api.openapi.json`.

### 7.2 Success body

The archive contains one safe top-level directory:

```text
surgepilot-public-api/
├── SKILL.md
├── references/
├── scripts/
└── tests/
```

Rules:

1. Preserve source-relative paths below the top-level directory.
2. Include regular source files under `SKILL.md`, `references/`, `scripts/`, and `tests/`.
3. Exclude `__pycache__/`, `.pytest_cache/`, `*.pyc`, `*.pyo`, editor backup files ending in `~`, and temporary files ending in `.tmp` or `.temp`.
4. Reject or skip symlinks and any entry whose resolved path escapes the source root.
5. Do not add generated server configuration, PAT values, Workspace IDs, environment files, or runtime secrets to the archive.
6. The request path does not create a persistent zip file. An in-memory or streaming archive builder may be used because the governed source package is bounded and repository-owned.

### 7.3 Error contract

| Code | HTTP | Trigger |
| --- | --- | --- |
| `UNAUTHENTICATED` | `401` | No valid current session. |
| `AI_SKILL_SOURCE_NOT_AVAILABLE` | `503` | The governed source directory or required `SKILL.md` is unavailable, unreadable, or contains no safe bundle. |

`AI_SKILL_SOURCE_NOT_AVAILABLE` rules:

1. Document the code only through this route's `responses` OpenAPI metadata.
2. Do not add it to `info.x-surgepilot-error-codes`, a shared Pydantic enum, or the public OpenAPI artifact.
3. Return the standard safe error envelope.
4. Log a safe server-side reason without returning absolute paths, container paths, usernames, stack traces, or source directory candidates to the client.

## 8. SkillBundle and Image Contract

`SkillBundle` resolves source layout in this order:

1. `/opt/surgepilot/ai-skills/surgepilot-public-api`
2. Repository fallback `packages/ai-skills/surgepilot-public-api`, discovered relative to API source parents in local development and tests

P2-04 does not add a UI-editable path, System Setting, request parameter, remote URL, or release version selector.

`apps/api/Dockerfile` must copy only:

```text
packages/ai-skills/surgepilot-public-api/
  -> /opt/surgepilot/ai-skills/surgepilot-public-api/
```

The OpenAPI bootstrap must not depend on copying `scripts/`, `packages/contracts/openapi/api.openapi.json`, or another generated contract file into the image.

## 9. Shared OpenAPI Export Contract

### 9.1 Module ownership

Move reusable export behavior into an API-owned module such as:

```text
apps/api/app/services/openapi_export.py
```

The shared module owns at least:

1. `_normalize_path`
2. `_filter_paths`
3. schema-reference collection and public schema pruning
4. public-only error-code pruning
5. `_export_document`
6. the public-pruned error-code constant

`scripts/export_openapi.py` remains the repository CLI wrapper that imports the FastAPI app, calls the shared module, and writes the two committed artifacts with their existing formatting and trailing newline.

### 9.2 Curated Web/business document

The runtime bootstrap payload is constructed exactly from the shared Web/business branch:

```python
document = _export_document(request.app.openapi(), public=False)
payload = json.dumps(document, sort_keys=True).encode("utf-8")
```

Required semantics:

1. `_export_document` deep-copies the source and does not mutate `app.openapi_schema`.
2. Runtime `/api/v1/*` paths normalize to `/v1/*`.
3. `/api/public/v1/*` paths are excluded from the Web/business document.
4. `/api/internal/*`, health/readiness, raw `/api/*` paths outside the normalized business rule, and schema-only unreachable components are excluded according to current export behavior.
5. `servers` is exactly `[{"url": "/api"}]`.
6. The runtime helper must not read `packages/contracts/openapi/api.openapi.json`, `/app/api.openapi.json`, or another generated file.
7. The runtime helper must not pass bare `request.app.openapi()` bytes to API Catalog.
8. Existing script output semantics for both committed artifacts and existing public pruning tests must remain unchanged.

## 10. First-Admin Trigger and Transaction Contract

### 10.1 Registration result

The account service result becomes explicitly equivalent to:

```python
user, workspace, created_session, first_user = register_user(...)
```

Rules:

1. `first_user` is computed under the existing serialized bootstrap lock.
2. `register_user` keeps ownership of its existing nested transaction, membership/session/audit work, and `db.commit()`.
3. The auth route must not move registration commit responsibility upward.
4. The auth route must not infer first-user status from `user.role` because an Admin role is not a durable bootstrap event marker.

### 10.2 Trigger ordering

The required order is:

```text
register_user enters existing serialized bootstrap transaction
  -> first_user is decided
  -> user, Default Workspace membership, session, and registration audit are flushed
  -> register_user commits
  -> register_user returns first_user
  -> route invokes best-effort bootstrap helper only when first_user is true
  -> route sets cookie/header and returns the successful registration response
```

OpenAPI generation, SHA-256 lookup, MinIO write, API Catalog creation, and helper commit must not execute inside `begin_nested()` or while `lock_users_for_bootstrap()` is held.

### 10.3 Failure isolation

The helper is synchronous and bounded, but non-critical:

1. It creates and closes its own `SessionLocal` session.
2. It catches generation, validation, database, storage, flush, and commit failures.
3. It logs the failure with safe identifiers such as first Admin ID, Default Workspace ID, and request ID when available.
4. It never raises a failure back through the registration route.
5. Registration remains `201 Created` with its committed user, membership, session, cookie, and Workspace header.
6. P2-04 adds no retry loop, worker, admin repair button, or Catalog-specific health gate. Startup reconciliation is one synchronous best-effort attempt; existing DB/MinIO client timeouts may delay lifespan.

## 11. Bootstrap Import and Idempotency Contract

### 11.1 UploadedApiSpec input

The helper synthesizes an existing service input with these fixed properties:

| Field | Contract |
| --- | --- |
| `filename` | `surgepilot-api.openapi.json` |
| `content_type` | `application/json` |
| `payload` | Curated bytes from §9.2 |
| `name` | `SurgePilot API` |
| `workspace_id` | Default Workspace ID returned by first registration |
| `actor_user_id` / `created_by` | First Admin user ID |
| `storage` / `bucket` | Existing `get_storage_client()` and configured MinIO bucket |
| `max_bytes` | Existing `api_catalog_spec_max_bytes` setting |

The filename and content type must satisfy `validate_spec_filename`, `validate_content_type`, and `parse_api_spec`. The document's `info.title`, `info.version`, and OpenAPI version remain derived from the current FastAPI schema. Under ADR-0027, `info.version` is the canonical product version, so the imported `documentVersion` is `X.Y.Z` for source, validation, and formal-release deployments.

### 11.2 System identity and content idempotency

For first-Admin creation, query:

```text
workspace_id == Default Workspace ID
AND system_key == "surgepilot_api"
AND status != "deleted"
```

Rules:

1. When an active marked row exists, skip first-Admin creation and commit no new Catalog row or object.
2. A user-uploaded row with identical SHA-256 cannot suppress system creation or become system identity.
3. Startup queries only active marked rows. Zero rows is a no-op, and more than one is a warning with no mutation.
4. For exactly one active marked row, compare only its SHA-256 with the current curated payload. Equal SHA-256 produces no DB or MinIO mutation.
5. A deleted row does not block a later explicit first-Admin helper invocation, but startup never recreates it.

### 11.3 Create and compensation

`create_api_catalog_spec` writes MinIO before `db.flush()`. The helper owns the outer commit:

1. If validation, storage write, or flush fails inside `create_api_catalog_spec`, existing service cleanup behavior remains authoritative.
2. After creation returns, retain the new spec's server-only bucket and object key until commit succeeds.
3. If the helper's `db.commit()` fails, call `db.rollback()` and then `storage.delete_object_best_effort()` for only that newly created object.
4. Cleanup failure is logged safely and does not affect registration.
5. Never delete an object belonging to an existing marked row that was skipped.

### 11.4 Startup replacement

After the identity migration and configuration validation, FastAPI lifespan makes one best-effort attempt using an independent `SessionLocal`. If the active system row's SHA-256 differs, the helper validates and writes the current curated payload, creates a replacement marked row with the previous `created_by`, and tombstones the previous row (`deleted_by = NULL`) in the same transaction. It deletes the old object only after commit, best-effort. Failure before commit rolls back and cleans up only the new object; failure after commit leaves the replacement authoritative. No request actor, worker, retry loop, or Catalog-specific release stable gate is added.

## 12. Security and Privacy Requirements

1. The skill download route requires a valid current user and does not accept anonymous access or PAT Bearer as a substitute.
2. Both normal users and Admins download the same repository-owned source; no user-specific or Workspace-specific content is injected.
3. The route does not require `x-workspace-id`, does not use browser preferred/default Workspace fallback, and does not expose cross-Workspace data.
4. The zip contains no token, session, CSRF, Workspace ID, secret, database value, MinIO credential, object key, or server path.
5. Error responses and logs must not expose bundle candidate paths or filesystem details.
6. The system OpenAPI helper uses only the first Admin and Default Workspace IDs already committed by registration.
7. Imported API Catalog metadata follows existing Workspace ownership, content proxy, and storage secrecy rules.
8. The imported document may contain session business route contracts because it is the curated Web/business artifact, but it must not contain PAT-public routes, runner-internal routes, secret examples, server paths, or generated-file locations beyond existing artifact rules.
9. Help copy must tell users to protect PAT values and use an explicit Workspace ID; it must not embed example real tokens.

## 13. OpenAPI, Contracts, and Error-Code Boundaries

1. FastAPI route and response metadata remain the source of truth.
2. Run `make generate-contracts` after adding the download endpoint.
3. The Web/business artifact includes the binary download operation and its route-local `503` error example.
4. The public artifact excludes the download path, route-local error code, browser session schemas, and all existing forbidden fields.
5. `AI_SKILL_SOURCE_NOT_AVAILABLE` must not appear in `info.x-surgepilot-error-codes` in either artifact.
6. The shared export refactor must be behavior-preserving for all existing operations and public pruning.
7. Web code must use the generated operation through `@surgepilot/contracts` and the existing API-client wrapper pattern when fetching the zip blob; it must not invent a response DTO.

## 14. Observability and Error Handling

Required safe log events or equivalent structured messages:

1. Skill bundle source unavailable.
2. Skill archive construction failed.
3. System OpenAPI bootstrap skipped because an active marked asset already exists.
4. System OpenAPI bootstrap completed.
5. System OpenAPI bootstrap failed.
6. Bootstrap commit compensation attempted and whether object cleanup succeeded.
7. System OpenAPI startup reconciliation completed, failed, skipped because of duplicate active assets, or left an old object after cleanup failure.

Logs may include request ID, first Admin ID, Default Workspace ID, Catalog spec ID after creation, and a bounded SHA-256 prefix. Logs must not include archive bytes, OpenAPI payload, PATs, cookies, CSRF values, absolute paths, MinIO credentials, or full storage object keys.

## 15. Tests and Acceptance Criteria

### 15.1 Shared OpenAPI export

1. The export script imports the API-owned shared module and no longer owns a duplicate `_filter_paths` or `_export_document` implementation.
2. Web/business and public committed artifacts are semantically unchanged before the new route is added, except for expected generated timestamps if any are already governed out.
3. `_export_document(source, public=False)` keeps normalized `/v1/*` paths and excludes `/public/v1/*`, `/internal/*`, health, and raw `/api` paths.
4. `_export_document(source, public=True)` preserves existing public schema and error-code pruning.
5. Export does not mutate the cached source schema.

### 15.2 Skill bundle and route

1. Container path wins over repository fallback when both are available.
2. Repository fallback works in local tests.
3. Required source absence returns `AI_SKILL_SOURCE_NOT_AVAILABLE` without an absolute path.
4. Archive entries contain the required source tree and exclude caches, bytecode, temp files, unsafe paths, and symlinks.
5. Anonymous download returns `401 UNAUTHENTICATED`.
6. Authenticated `user` and `admin` receive `200`, `application/zip`, the fixed attachment filename, and `Cache-Control: private, no-store` when the request omits `x-workspace-id`.
7. Repeated requests build valid independent archives and create no MinIO object or persistent zip.
8. Internal OpenAPI contains `downloadPublicApiAiSkill`; public OpenAPI does not contain the path or route-local error code.
9. API Docker image contract checks confirm the governed source directory is copied and no generated OpenAPI file or `scripts/` copy is required for bootstrap.

### 15.3 First-Admin bootstrap

1. `register_user` returns `first_user=True` for the serialized first registration and `False` for later users.
2. The route calls the helper only for the explicit `True` result, not for any later Admin role.
3. Registration commits before OpenAPI generation or storage work begins.
4. The helper uses a different database session from the registration dependency session.
5. Successful first registration creates one available Catalog row in Default Workspace with first Admin as creator and valid JSON/OpenAPI metadata.
6. An active marked system row causes a no-op even when its name differs.
7. An ordinary same-SHA row does not suppress Default Workspace system creation.
8. A deleted marked row does not count as an existing active import.
9. OpenAPI generation, validation, MinIO, flush, and commit failures do not change successful registration status, cookie, session, or Workspace membership.
10. Commit failure after object creation triggers rollback and best-effort deletion of only the new object.
11. The imported content contains curated `/v1/*` paths and excludes `/public/v1/*`, `/internal/*`, health, and raw runtime `/api` prefixes.

### 15.3.1 Historical adoption and startup reconciliation

1. Migration adopts exactly one canonical unaudited historical row created by the earliest registered user; zero, duplicate, deleted, non-first-user, and successfully upload-audited candidates remain unmarked. Audit absence alone is not proof of system ownership.
2. Fresh first-Admin creation sets server-only `system_key`, current metadata version, and current stored `info.version`.
3. Same-SHA startup performs no DB or MinIO mutation; changed SHA replaces the full stored document and leaves exactly one active marked row.
4. Replacement inherits `created_by`, retires the previous row with `deleted_by = NULL`, and deletes its object only after commit.
5. Commit failure preserves the old row/object and attempts cleanup of the new object; old-object cleanup failure leaves the committed replacement authoritative.
6. Duplicate active system rows, explicit deletion, and unmarked user assets cause no startup mutation. A reconciliation exception itself does not fail lifespan.
7. Release verification requires exactly one canonical name/filename match and checks both target-version metadata and stored content title/version.

### 15.4 Help Web

1. `/help` is protected by the existing auth route guard and renders inside AppLayout.
2. The Help entry is visible to both `user` and `admin`.
3. Tab labels and order match §6.2 exactly; `Automation` is absent.
4. The AI Agents tab covers API Keys, Workspace ID, Public API, download, local-agent consumption, operation allowlist, and write confirmation.
5. The download action uses the generated contract/API-client wrapper, saves the fixed filename, and shows a safe error state.
6. Limits & Activation states that system creation and later startup alignment are active while user/external auto-ingestion is inactive.
7. Copy tests reject claims for SDK, MCP, marketplace, installer, built-in runtime, automatic Scenario generation, automatic tuning, or automatic report analysis.

### 15.5 Verification commands

Implementation must run at least:

```bash
make generate-contracts
make verify
```

Targeted tests should be added for API services/routes, auth bootstrap, API Catalog integration, Web Help, contract export, Docker build-source rules, and the governed skill package.

## 16. Done When

P2-04 is complete only when:

1. The ADR, Slice, Scope Gate, workflow, AGENTS, P2 index, API Catalog governance, and Public API skill governance are synchronized.
2. `/help` is an authenticated real page with the exact tab order and bounded AI Agents copy.
3. A logged-in user can download a fresh valid source zip with fixed headers and no Workspace requirement.
4. The API image contains the governed skill source and the route fails closed when source is unavailable.
5. The export script and runtime helper use one shared API-owned OpenAPI export implementation.
6. The first Admin's successful registration triggers only the independent best-effort bootstrap path.
7. The Default Workspace receives an active marked system asset independent of ordinary same-SHA user uploads.
8. Registration remains successful on every bootstrap import failure path.
9. Commit-after-MinIO failure compensation is covered by tests.
10. Internal/public OpenAPI inclusion and exclusion rules pass automated checks.
11. `make generate-contracts` and `make verify` pass.
12. Implementation Backfill records exact files, test names, commands, differences, and risks.

## 17. Implementation Backfill

The implementation PR must record:

1. Final Help route, page, copy, tabs primitive, navigation, and test files.
2. Final account AI skill router, operation ID, API-client wrapper, and generated contract paths.
3. Final `SkillBundle` class/function names and source resolution behavior.
4. Final zip builder, exclusion set, archive root, and streaming implementation.
5. Final shared OpenAPI export module and script import changes.
6. Final `register_user` return shape and bootstrap helper call site.
7. Final bootstrap helper/session function names, system-key query, and cleanup implementation.
8. Exact API Catalog name/filename/content type used if they differ from §11.1.
9. Tests added or changed and verification commands/results.
10. Implementation differences from this SDD. Any scope expansion requires governance revision before merge.

### 17.1 Implemented files and interfaces

The implementation uses these final anchors:

1. Help Web:
   - `apps/web/src/features/help/routes.tsx`
   - `apps/web/src/features/help/pages/help-page.tsx`
   - `apps/web/src/features/help/copy.ts`
   - `apps/web/src/features/help/help.test.tsx`
   - `apps/web/src/components/ui/tabs.tsx`
   - `apps/web/src/app/layouts/app-layout.tsx`
2. Skill download:
   - `apps/api/app/routes/account_ai_skill.py`
   - operation ID `downloadPublicApiAiSkill`
   - Web wrapper `downloadPublicApiAiSkill()` in `apps/web/src/app/api-client.ts`
   - generated paths in `packages/contracts/openapi/api.openapi.json` and `packages/contracts/generated/web-client/index.ts`
   - successful authenticated requests commit the existing sliding-session `last_seen_at` update without resolving Workspace context
3. Skill bundle:
   - `SkillBundle.build_zip()` returns an in-memory `BytesIO`
   - `default_skill_bundle_dir()` resolves container-first, then repository fallback
   - archive root is `surgepilot-public-api/`
   - allowed roots are `SKILL.md`, `references/`, `scripts/`, and `tests/`
   - cache directories, bytecode, temp files, editor backups, `.env*` files, symlinks, and resolved path escapes are excluded
4. Shared OpenAPI export:
   - `apps/api/app/services/openapi_export.py` owns normalization, filtering, schema pruning, public error pruning, and `_export_document`
   - `scripts/export_openapi.py` imports the shared module and retains the existing two-artifact output behavior
5. Registration and bootstrap:
   - `register_user()` returns `(user, workspace, created_session, first_user)` while retaining its existing commit
   - `apps/api/app/routes/auth.py` invokes `bootstrap_system_openapi_best_effort()` only after an explicit `first_user=True` return
   - `build_curated_openapi_payload()`, `import_system_openapi()`, and `bootstrap_system_openapi_best_effort()` live in `apps/api/app/services/system_openapi_bootstrap.py`
   - the helper uses its own `SessionLocal`, active Default Workspace `system_key` lookup, and `create_api_catalog_spec()`
   - the fixed Catalog input remains `SurgePilot API`, `surgepilot-api.openapi.json`, and `application/json`
   - commit failure rolls back and calls `delete_object_best_effort()` only for the newly written object
   - `StorageClient.delete_object_best_effort()` now returns a cleanup success boolean so compensation logs can record the outcome

### 17.2 Tests and verification

Added or adjusted tests:

1. `apps/api/tests/test_p2_04_openapi_export.py`: shared export filtering, pruning, and non-mutation.
2. `apps/api/tests/test_p2_04_ai_skill.py`: source resolution, per-request archives, environment/cache/temp/symlink/path-escape exclusions, session authorization, sliding-session persistence, normal-user access, ignored invalid Workspace header, response headers, and safe route-local failure.
3. `apps/api/tests/test_p2_04_system_openapi_bootstrap.py`: curated runtime payload, first-user trigger, independent session import, system identity, deleted-row behavior, the real route-to-wrapper failure-isolation path, commit compensation, and post-commit safety. Issue #53 extends this suite with startup reconciliation and replacement safety.
4. `tests/contract/test_p2_04_help_ai_agents_openapi.py`: internal/public OpenAPI separation, route-local error code, and Docker source-copy boundary.
5. `apps/web/src/features/help/help.test.tsx`: exact tabs, bounded copy, session download without Workspace header, fixed filename, route-local source-unavailable mapping, and expired-session mapping.
6. `tests/e2e/p2_04_help_ai_agents.spec.ts`: authenticated Help navigation, tab order, source zip download and ZIP signature, and activation limits.
7. `tests/e2e/p2_00_api_catalog.spec.ts`: deletion now asserts that the user-uploaded `Orders API` is removed without assuming the bootstrap system spec is absent.

Verification results:

```text
make generate-contracts
  PASS; internal Web/business artifact and generated Web client refreshed, public artifact unchanged for P2-04 route exposure.

make verify
  PASS; Ruff/lint/typecheck passed.
  API + contract: 769 passed, 7 skipped, 91.62% total coverage.
  Public API skill: 50 passed, cumulative coverage 91.67%.
  Verifier tests: 132 passed.
  Runner tests: 65 passed.
  Web tests: 152 passed.
  PostgreSQL integration: 3 passed.
  Diff coverage: 100% for the final uncommitted review fixes.

pnpm exec playwright test tests/e2e/p2_04_help_ai_agents.spec.ts tests/e2e/p2_00_api_catalog.spec.ts --project=chrome
  PASS; 2 passed.
```

### 17.3 Implementation differences and remaining risks

1. `SkillBundle` builds the bounded archive directly instead of introducing a separate bundle-file DTO; this keeps the implementation smaller without changing the archive contract.
2. The Tabs primitive is source-owned and delegates keyboard/ARIA behavior to the added `@radix-ui/react-tabs` package, consistent with the frontend interaction rules.
3. The storage cleanup method returns a boolean only for safe compensation observability; existing callers continue to ignore the result and no storage behavior or product scope changes.
4. The original P2-04 delivery added no database migration, worker, retry loop, installer, marketplace, SDK, MCP server, external ingestion, or generation chain. Issue #53 later adds only the bounded `system_key` identity/adoption migration.

5. Remaining product risks are unchanged from §18.

### 17.4 Second independent review

The additional independent review re-checked authentication/session behavior, Workspace isolation, archive contents, bootstrap failure isolation, stable frontend error mapping, OpenAPI/contracts, and P0/P1 regressions. It found and fixed:

1. The download route authenticated and flushed `last_seen_at` but did not commit it, so a successful skill download alone did not advance the 24-hour sliding session activity timestamp. The route now commits the shared request session before filesystem archive work.
2. `.env*` files placed below an allowed source directory could enter the archive. `SkillBundle` now excludes them at every allowed depth.
3. The Help download error state mapped `AI_SKILL_SOURCE_NOT_AVAILABLE` but treated `UNAUTHENTICATED` as a generic failure. It now maps the stable code to an explicit sign-in-focused message.
4. Registration failure isolation was previously split between a direct wrapper test and a route trigger spy. A new integration test now restores the real wrapper at the route boundary, forces the import implementation to fail, and verifies registration still returns `201`.
5. An authenticated request carrying an invalid `x-workspace-id` is covered and remains successful, confirming the account-scoped download route does not resolve Workspace context.

No new capability or architecture component was introduced by these fixes.

### 17.5 System OpenAPI lifecycle amendment (Issue #53)

The current implementation adds `ApiCatalogSpec.system_key` and the `0022_p2_04_system_openapi` Alembic migration. Runtime identity uses `system_key = surgepilot_api` in the Default Workspace. `import_system_openapi()` creates the marked asset after first-Admin commit, and `reconcile_system_openapi_best_effort()` runs once in FastAPI lifespan after configuration validation. `reconcile_system_openapi()` compares the marked row's SHA-256, replaces the complete stored curated document when changed, preserves `created_by`, retires the prior row with `deleted_by = NULL`, and cleans up the previous object only after commit. No public DTO or generated contract field changes.

Historical adoption requires canonical workspace, name, filename, title, JSON source format, earliest registered creator, no successful upload audit, and exactly one candidate. The absence of an upload audit is only a risk-reduction signal: upload audit is best-effort and cannot prove system ownership. This accepted one-time residual risk is confined to a crafted canonical lookalike with missing upload audit; ambiguous candidates are not adopted. After migration, runtime performs no legacy name/filename guessing.

The release verifier now requires one canonical Catalog list match and reads authorized stored content to assert both metadata and stored OpenAPI use the target product version. It no longer persists `sourceProductVersion` as an upgrade-state Catalog exception. The release transition and source release identity checks remain governed by ADR-0029. Help `Limits & Activation` describes startup alignment of the system-owned document.

Focused coverage lives in `test_p2_04_system_openapi_migration.py`, `test_p2_04_system_openapi_bootstrap.py`, `test_p2_05_release_stack_verifier.py`, and `help.test.tsx`. Required validation is `make generate-contracts`, `make verify-db`, and `make verify`; record any unavailable gate as `NOT VERIFIED` in the PR.

## 18. Remaining Risks

1. The bootstrap import is intentionally best-effort and has no automatic retry; a transient first-registration storage failure can leave the Default Workspace without the system spec.
2. Request-time zip creation adds bounded CPU and memory work to the API process; the source package must remain small and repository-owned.
3. Historical adoption cannot prove system ownership with certainty because the legacy schema has no marker and upload audit was best-effort. The unique canonical predicate narrows the accepted one-time risk; ambiguous candidates are not adopted.
4. Duplicate active `system_key` rows cause startup reconciliation to skip with a warning and release verification to fail until an operator identifies the legitimate row.
5. Synchronous startup reconciliation may wait for existing infrastructure client timeouts. Failure can leave the prior valid Catalog asset stale until a later API startup.
6. The downloaded skill source is a point-in-time request bundle with no version, signature, checksum, or automatic update channel.
