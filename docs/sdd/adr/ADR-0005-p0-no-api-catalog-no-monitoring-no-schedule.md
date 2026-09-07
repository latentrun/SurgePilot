# ADR-0005: P0 No API Catalog, Monitoring, or Schedule

- Status: Accepted
- Scope: P0 product and implementation boundary
- Product source: `docs/prd/PRD.md`
- Scope gate: `docs/sdd/00-product-scope-and-priority.md`

## Context

SurgePilot P0 must deliver the internal MVP performance test loop:

```text
Scenario -> Test Plan -> Run Now / Debug -> Run Report -> Validity
```

The PRD defines API Catalog, Monitoring and Schedule Run as P1 capabilities. They improve productivity and observability, but they are not required for the P0 execution loop.

These three areas are easy to implement accidentally because the PRD includes future routes and page hierarchy planning:

1. API Catalog route planning appears as `/api-catalog`.
2. Monitoring route planning appears as `/observability/monitoring`.
3. Schedule Run is described near Test Plan and Run behavior.

Without a hard P0 decision, Slice work could create hidden routes, placeholder pages, backend tables, API endpoints, Compose services or UI navigation that make P1 behavior partially usable during P0.

## Options Considered

1. **Exclude API Catalog, Monitoring and Schedule from P0**
   - Pros: keeps P0 focused on manual creation, execution and report validity; prevents hidden P1 dependencies; reduces infrastructure and UI surface.
   - Cons: users cannot import APIs, view live Grafana metrics or schedule runs in P0.
2. **Implement placeholder routes without usable behavior**
   - Pros: makes future navigation visible earlier.
   - Cons: creates confusing UI and risks accidentally exposing partial P1 workflows.
3. **Implement these capabilities in P0**
   - Pros: broader first release.
   - Cons: expands scope into API asset management, monitoring infrastructure and scheduling before the core Run loop is stable.

## Decision

P0 does not implement:

1. API Catalog.
2. OpenAPI / Swagger Spec upload.
3. API Spec detail pages.
4. Creating Test Plans from API operations.
5. OpenAPI Step auto-generation.
6. cURL import.
7. Monitoring pages.
8. Grafana iframe.
9. Open in Grafana.
10. InfluxDB write path.
11. InfluxDB datasource management.
12. JMeter Backend Listener configuration management.
13. Run ID time-series metric filtering.
14. Schedule Run.
15. Scheduled Job.
16. Upcoming Scheduled Jobs statistics.

P0 may mention these capabilities only as roadmap or non-clickable planning in documentation.

## Allowed P0 References

Allowed:

1. PRD and SDD documentation may describe P1 routes and future page hierarchy.
2. Route inventory documents may list P1 paths as not implemented in P0.
3. Data models may reserve non-user-visible future enum values only when they do not activate P1 behavior.
4. Run Report may use offline summary, failed request preview, final stats, logs and artifacts for result evaluation.

Not allowed:

1. Clickable navigation entries for `/api-catalog`, `/observability/monitoring` or Schedule Run.
2. Placeholder pages that look usable.
3. Hidden routable pages exposing P1 workflows.
4. Backend endpoints for API Spec upload, import, Monitoring or Scheduled Jobs.
5. Database tables or migrations for API Specs, monitoring config or Scheduled Jobs during P0.
6. Docker Compose services for Grafana or InfluxDB during P0.
7. Runner behavior that depends on InfluxDB, Grafana or Backend Listener configuration.
8. Overview statistics for Upcoming Scheduled Jobs during P0.

## Consequences

1. P0 implementation remains focused on manual Scenario and Test Plan creation, single-node Run execution, and Run Report artifacts.
2. P0 verification must fail review if it introduces user-visible API Catalog, Monitoring or Schedule behavior.
3. `docs/sdd/08-frontend-routing-and-ui-rules.md` must keep P1 routes non-clickable and document-only during P0.
4. `docs/sdd/01-architecture-overview.md`, `docs/sdd/02-repo-structure-and-dev-workflow.md`, root `AGENTS.md`, and Slice SDDs must preserve the same P0 boundary.
5. P1 can introduce these capabilities later through explicit Slice SDD updates and implementation work; this ADR only blocks their activation in P0.

## Review Checklist

Before accepting a P0 change, verify:

1. No API Catalog, Spec upload, Spec detail, cURL import or API-operation-to-Test-Plan flow is implemented.
2. No Monitoring page, Grafana iframe, Open in Grafana, InfluxDB write path or datasource management is implemented.
3. No Schedule Run, Scheduled Job, scheduling queue, retry or Upcoming Scheduled Jobs statistic is implemented.
4. Future routes are documentation-only and not clickable in P0 UI.
5. P0 Run execution and Run Report do not depend on Monitoring configuration.

## Related ADRs

- `ADR-0003-p0-minio-only.md`
- `ADR-0004-p0-manual-single-node-only.md`
- `ADR-0006-p0-separate-api-worker.md`

## References

- `docs/prd/PRD.md`
- `docs/sdd/00-product-scope-and-priority.md`
- `docs/sdd/01-architecture-overview.md`
- `docs/sdd/08-frontend-routing-and-ui-rules.md`
- `AGENTS.md`
