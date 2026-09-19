# ADR-0010 P2 API Catalog Scalar

- Status: Accepted
- Scope: P2 API Catalog documentation asset management, read-only Scalar API Reference rendering, and the ADR-0016 system bootstrap exception
- Active Slice: `docs/sdd/slices/P2-00-api-catalog-scalar.md`
- Slice Status: Accepted for implementation; design frozen as the P2-00 Slice SDD
- Supersedes: none
- Does not supersede: P0/P1 execution flow, contract-first rules, MinIO-only storage boundary, Runner/API/Web boundaries, Workspace isolation, or P2 exclusions outside API Catalog documentation asset management

## Context

The PRD and Scope Gate define API Catalog as a P2 documentation asset management capability only. It stores and displays OpenAPI / Swagger specs but must not create, update, import, or generate Scenario, Step, Test Plan, Run, Artifact, Taurus YAML, or operation coverage behavior.

`docs/sdd/slices/P2-00-api-catalog-scalar.md` selects Scalar API Reference for the detail-page renderer and defines a minimal asset lifecycle: upload, list, detail, authorized content proxy, and delete. The Slice explicitly requires a P2 governance decision or accepted implementation decision before any callable API or clickable UI is added.

## Decision

Activate `P2-00-api-catalog-scalar` as the current P2 implementation Slice.

The accepted architecture is:

1. Add API Catalog spec asset management under `/api/v1/api-catalog/specs` for upload, list, detail, authorized content proxy, and delete.
2. Store raw specs as controlled server-side assets through the existing MinIO/storage boundary, with PostgreSQL metadata as the Workspace ownership source of truth.
3. Return only safe metadata and a same-origin API `contentUrl` to Web; never return bucket names, object keys, presigned URLs, MinIO endpoints, server paths, or storage credentials.
4. Render detail pages with Scalar API Reference from the authorized `contentUrl` only.
5. Disable request sending and external Scalar integrations, including Test Request / Try it affordances, API client buttons, auth persistence, hosted proxy, Agent, MCP, developer tools, and telemetry when supported by the integration.
6. Reuse the existing AppLayout, route/module style, Tailwind tokens, CSS variables, source-owned primitives, generated contracts, session auth, Workspace header, and CSRF rules.
7. Keep API Catalog isolated from Scenario, Step, Test Plan, Run, Runner, Artifact, Taurus builder, scheduling, SSO, Secret, non-MinIO storage, and OpenAPI Step generation behavior. ADR-0016 adds only a Help explanation and one system-owned first-Admin bootstrap import of SurgePilot's own curated Web/business OpenAPI; it does not add a Catalog generation action.
8. Allow ADR-0016/P2-04 to invoke the existing API Catalog service after first-Admin registration commit, using an independent session, for one best-effort Default Workspace import deduplicated by `workspace_id + sha256 + status != deleted`.

## Boundaries

In scope:

- API Catalog spec upload / list / detail / content / delete.
- Basic safe JSON/YAML parsing and OpenAPI 3.x / Swagger 2.0 root validation.
- Metadata persistence, SHA-256 digest, size, source format, document title/version, and safe status.
- API-mediated content proxy with private/no-store cache headers.
- Web list/detail/upload/delete UI and read-only Scalar rendering.
- One ADR-0016/P2-04 system-owned bootstrap import of SurgePilot's own current curated Web/business OpenAPI into Default Workspace, reusing the same validation, MinIO, metadata, content proxy, and rendering boundaries.
- API, contract, Web, Scalar hardening, and E2E/smoke tests required by the Slice.

Out of scope:

- API operation import, operation resources, version diff, coverage analysis, SDK generation, mock server, AI Agent chat, or schema registry.
- User-provided, externally fetched, scheduled, startup-reconciled, or background automatic OpenAPI ingestion. The ADR-0016 first-Admin system document is the only automatic import exception.
- API Catalog → Scenario/Test Plan generation, OpenAPI Step auto-generation, Scenario/Test Plan mutation, Run creation, Artifact generation, or Taurus YAML changes.
- Independent docs service, queue/worker platform, external API Gateway, external object storage backend, self-built OpenAPI renderer, or second UI component/theme system.
- Any P2 capability other than API Catalog documentation asset management.

## Consequences

- The scope gate, P2 index, owning Slice, and this ADR must remain synchronized before code
  implementation proceeds. Root instructions route P2 discovery through the index and change only
  for a stable repository-wide invariant or routing branch.
- API contracts follow FastAPI/Pydantic schemas → OpenAPI export → generated `@surgepilot/contracts` client/types → Web consumption.
- The implementation must backfill final API files, migration/model/storage facts, Scalar package/version/import mode, Web module paths, tests, verification commands, and risks in the Slice SDD.
- Any future change that adds operation import, generation, remote request sending, a different renderer architecture, a new storage backend, or a new UI system requires a new or updated ADR/Scope Gate before implementation.
- ADR-0016 does not alter the documentation-only model: the imported system asset has no Scenario/Test Plan generation, execution, operation resource, version management, or update/retry behavior.

## Implementation Backfill

- The current detail route fetches authorized API Catalog metadata to obtain the same-origin `contentUrl`, then renders the source-owned Scalar wrapper as the primary API Reference surface rather than duplicating a separate metadata/card view outside Scalar.
- `AppLayout` treats `/api-catalog/:specId` as an embedded-content page: the global sidebar and top bar remain, while standard page padding is removed so Scalar can use the available viewport.
- The Scalar wrapper remains documentation-only: it uses a Shadow DOM/style boundary, restores host `body` class/style mutations, handles explicit Scalar sidebar operation navigation through Scalar's supported callback without replacing global History API methods, delegates tag-only sidebar clicks to Scalar's own expand/collapse behavior, defaults the isolated reference canvas to Scalar dark mode, mirrors later theme behavior only inside the isolated renderer/teleport nodes, and keeps request sending, proxying, auth persistence, Agent/MCP, Try it/Test Request, and API Catalog generation actions disabled. Initial URL fragments and Scalar's passive section-to-hash synchronization do not trigger SurgePilot-owned scrolling.
- Web and E2E coverage includes list/detail/upload/delete flows, current Workspace header usage, Scalar hardening/style containment/navigation behavior, and no API Catalog Scenario/Test Plan/OpenAPI generation entry points.
