# ADR-0022 P1 Governance Start

- Status: Accepted
- Scope: P1 governance, Slice SDD kickoff, and agent execution contract
- Supersedes: P0-only delivery-target wording where it conflicts with this ADR
- Does not supersede: PRD P1/P2 scope boundaries, P1 fixed exclusions, or contract-first verification rules

## Context

P0 development has been completed and the project needs to begin P1 work. The PRD and `docs/sdd/00-product-scope-and-priority.md` already define the retained P1 scope and fixed P1 exclusions, including that P1 Import means cURL only and P1 does not include API Catalog / OpenAPI generated Scenario or Test Plan flows.

However, operational governance files still contain P0-only target wording. Without an accepted governance marker, downstream contributors may either continue treating all P1 work as forbidden, or incorrectly use P1 startup as permission to implement P2 or unscoped capabilities.

## Decision

The current delivery target is updated from **P0 only** to **P1 governance start / P1 Slice kickoff**.

P1 implementation may begin only through a named P1 Slice SDD that references the authoritative PRD / SDD scope and includes verifiable Done When criteria. P1 work must stay inside the active Slice and must not create P2 behavior or revive previously excluded P1 candidates.

P0 remains the completed baseline. P1 work must not regress the P0 execution loop, P0-Stability requirements, contract-first workflow, Workspace isolation, permission enforcement, Runner/API/Web boundaries, or verification gates.

## P1 Scope Source

P1 scope is not redefined by this ADR. Use the existing authoritative sources:

- `docs/prd/PRD.md` P1 / P2 priority sections.
- `docs/sdd/00-product-scope-and-priority.md` P1 scope, fixed boundaries, and Slice split guidance.
- `docs/sdd/slices/P1-README.md` as the thin index only.

## Required Follow-up Sync

This ADR authorizes syncing the operational target wording in:

1. `docs/sdd/00-product-scope-and-priority.md`;
2. `docs/sdd/02-repo-structure-and-dev-workflow.md` §12;
3. root `AGENTS.md`.

If any of those files still mention P0-only after this ADR is merged, interpret the P0-only wording as stale and update it before using that file as execution input for a P1 task.

## Consequences

- P1 Slice drafting may start immediately after this ADR is accepted.
- P1 implementation may start only after the corresponding real P1 Slice SDD exists.
- P2 remains out of scope unless a separate accepted ADR or PRD update explicitly changes it.
- API Catalog / OpenAPI generated Scenario or Test Plan flows remain excluded from P1.
- Schedule Run, Scheduled Job, product Help page, Dependency archive extraction, and enterprise auth/security extensions remain P2 unless separately changed.

## P1-03 Verification Backfill

The P1-03 reconstruction remains within the governance boundary established here. Its final verification atomic is represented by focused API, Web, contract, E2E, and base-compose drift checks; those checks verify session/workspace authority, Admin protections, settings secrecy, and generated-contract boundaries without authorizing another P1 Slice or any P2 surface.

## P1-01 Verification Backfill

The P1-01 reconstruction remains within the governance boundary established here. Its verification atomic is represented by focused API, generated-contract, Web, and E2E checks for atomic multi-node allocation, allocation-backed terminal and SLA aggregation, node-bound callback validation, idempotent Stop, per-allocation timeout/quarantine cleanup, and public redaction. The API verification now executes the shared fake Runner once per allocation, feeds its callback and artifact events through allocation-aware handling, covers success and one-node failure, checks token-node mismatch rejection, and asserts report redaction. Real SSH two-node acceptance remains an environment-dependent gap. This backfill authorizes no P2 surface, Debug multi-node behavior, Monitoring semantics, or resource-matching capability.

## P1-00 Verification Backfill

The P1-00 reconstruction remains within the governance boundary established here and does not add workspace monitoring settings, a `monitoring_settings` table, token persistence, listener tuning, or any Grafana/InfluxDB management plane. Its verification atomic is represented by focused API, Runner, contract, compose, and E2E checks for Debug dynamic disabled behavior, enabled/config_error Standard Run snapshots, non-secret monitoring link and embed responses, runner wrapper injection/pass-through, runner monitoring-secret cleanup, session-gated `/grafana/*` provisioning, and the absence of a `/influxdb/*` Nginx write proxy. The official compose profile provisions InfluxDB2, Grafana, the `InfluxDB-SurgePilot` datasource, and Dashboard 13644; the compose smoke script checks the authenticated same-origin embed, the Grafana session gate, and Grafana provisioning. Supplemental compose and remote-node gates require Docker or an explicit node-facing InfluxDB write URL and are not mandatory lightweight `make verify` checks. This backfill authorizes no P2 surface and does not change the P0 execution loop, Run state machine, or artifact ingest.

## P1-04 Verification Backfill

The P1-04 reconstruction remains within the governance boundary established here and does not add Scenario Generated YAML Preview, editable YAML apply/save/import, a tag filter UI, or any P2 surface. Its verification atomic is represented by focused API, generated-contract, Web, and E2E checks for Scenario/Test Plan clone, Archive-through-DELETE visibility, the removed Scenario Preview endpoint, and the read-only Test Plan execution preview with invalid-mode rejection, static warnings, redacted values, and non-mutating behavior. Clone rejects missing, archived, or cross-Workspace sources as `RESOURCE_NOT_FOUND`, and the Scenario/Test Plan list and detail Clone and Archive affordances use only the generated `@surgepilot/contracts` client. This backfill authorizes no P2 surface and does not change the P0 execution loop, Run state machine, or artifact ingest.

## P1-05 Verification Backfill

The P1-05 reconstruction remains within the governance boundary established here and does not add API Catalog, OpenAPI Step generation, Postman/JMX/Locust/HAR import, batch import, local file reading, Runner or worker changes, raw cURL persistence, or any P2 surface. Its verification atomic is represented by focused API parser fixtures, route auth/Workspace/CSRF checks, generated-contract freshness checks, Web modal/merge tests, and an E2E smoke for paste, preview, append or replace, and save through the existing Scenario `PATCH`. The parse endpoint persists nothing, returns an ID-free preview Step draft, and never echoes raw cURL, parsed sensitive values, parser internals, or unsupported option values in responses. This backfill authorizes no P2 surface and does not change the P0 execution loop, Run state machine, or artifact ingest.
