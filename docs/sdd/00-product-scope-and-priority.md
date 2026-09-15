# 00. Product Scope and Priority

## Purpose

This document is the initial milestone scope gate. It prevents future-product ideas from becoming partially implemented before the core execution loop and its safety properties are complete.

## Current delivery target

P0 is the completed baseline. P1 work is governed by `docs/sdd/adr/ADR-0022-p1-governance-start.md` and may begin only through a named P1 Slice SDD with verifiable Done When criteria. P1 must preserve the P0 execution loop, P0-Stability requirements, contract-first workflow, Workspace isolation, permission enforcement, Runner/API/Web boundaries, and verification gates.

The current delivery target is **P2-02 Public API Substrate and governed Public API AI skill source package implementation plus P2-03 Env Group Secret implementation plus P2-04 Help AI Agents and System OpenAPI Bootstrap plus P2-05 Cross-platform Distribution and Full-stack Release Bootstrap, ADR-0019 Source Preview Startup, and ADR-0024 User-local Release Installer**. P2-00 API Catalog Scalar, P2-01 OpenAPI Step Generation, P2-02 Public API Substrate, P2-03 Env Group Secret, P2-04 Help AI Agents and System OpenAPI Bootstrap, and P2-05 Cross-platform Distribution are the currently active P2 Slice surfaces; each is implemented only through its accepted ADR and Slice SDD, and no other P2 capability is activated. Section 7 records the P2 range and the activation state of each domain.

```text
Default Workspace
  -> local registration and login
  -> reusable Env Group, Dependency File, and Load Node
  -> visual Scenario
  -> Test Plan
  -> manual selection of one Idle Load Node
  -> Debug or Run Now
  -> Run Report and artifacts
  -> validity judgment
```

Core behavior and stability ship together. A runnable flow is incomplete without immutable snapshots, callback idempotency, safe Stop, heartbeat timeout convergence, node lease cleanup, authorization, and file-path safety.

## Included capability

- Local accounts, first-admin initialization, and a Default Workspace.
- Workspace-aware assets and Private Load Nodes; platform-owned Public Load Nodes.
- Visual Scenario and Test Plan authoring.
- Manual single-node Debug and standard Runs.
- Run state, Stop, immutable execution snapshot, node lease, and self-healing worker.
- Verdict-first Run Report, validity, logs, final statistics, and downloadable artifacts.
- MinIO-backed Dependency Files and Run Artifacts through the API.
- Read-only platform Setup Status.

## Explicit exclusions

The initial milestone does not implement API Catalog, import/generation flows, Monitoring, Grafana or InfluxDB, Schedule Run, automatic allocation, multi-node execution, resource queues, Kubernetes, Redis or an external task queue, enterprise SSO, secret Env Groups, non-MinIO storage, or AI generation and analysis.

An excluded capability is still implemented if it exists only as a hidden API, route, migration, disabled service, or feature-flagged usable path. Roadmap wording in documents is allowed; executable surface is not.

## Scope-change rule

Feature work may refine initial behavior but may not expand this boundary. A scope change requires an explicit product update or accepted ADR and a focused Slice SDD before implementation.

## 6. P1 scope and fixed boundaries

P1 is the post-P0 stage for experience improvement and efficiency enhancement. P1 does not become a prerequisite for the completed P0 execution loop. The authoritative P1 scope is the PRD, as refined by accepted ADRs and the named Slice SDD for the capability being implemented.

The retained P1 range includes:

- Scenario and Test Plan polish, including Clone, Archive, lightweight tags, and Test Plan-only read-only execution configuration preview. Scenario Preview remains excluded.
- Resource Multi-node, Workspace/Admin, cURL Import, Dependency File Preview, Run Report Preview, Monitoring, and Debug HTTP Trace when each is activated by its own accepted Slice source.
- Debug HTTP Trace only for Debug Run, governed by `docs/sdd/adr/ADR-0008-p1-debug-http-trace.md` and `docs/sdd/slices/P1-08-debug-http-trace.md`.
- Scenario Global Configuration Phase A, governed by `docs/sdd/adr/ADR-0015-p1-scenario-global-configuration.md` and `docs/sdd/slices/P1-09-scenario-global-configuration.md`, adds only Scenario-level structured `Settings`, `Headers`, `Variables`, and `Data Sources` Tabs; `globalHeaders` and non-secret Scenario-local `variables` are new.

P1 fixed boundaries are:

- P1 Import means cURL import only. P1 does not activate API Catalog or any OpenAPI/API Catalog-to-Scenario or Test Plan generation flow.
- P1 does not include Schedule Run, Scheduled Job, an in-product Help page, Dependency File archive extraction, or enterprise authentication/security extensions.
- Debug HTTP Trace applies only to Debug Run. It does not add Standard Run tracing, JMeter plugins, Backend Listener, Monitoring, a generic logging or sanitization framework, or runtime tar changes.
- P1-09 does not activate `globalScripts`, Secret Scenario variables, editable Taurus YAML, JMeter expert panels, or new runtime dependencies.
- A P1 capability must not become a prerequisite for the P0 closed loop.

Recommended Slice boundaries are Monitoring, Resource Multi-node, Workspace/Admin, Scenario/Test Plan Polish, cURL Import, Dependency Preview, Run Report Preview, Debug HTTP Trace, and Scenario Global Configuration Phase A. Each implementation requires a named real Slice SDD with verifiable Done When criteria; this scope section does not authorize implementation by itself.

## 7. P2 range

P2 is the enterprise-level security governance, deployment expansion, and delayed enhancement phase. P2 range entries not activated by an accepted ADR and Slice SDD remain roadmap only and must not be implemented early.

| Domain | P2 Competencies |
| --- | --- |
| API Catalog | API document asset management only: upload / list / details / delete. P2-00 activates only that documentation-asset surface through `docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md` and `docs/sdd/slices/P2-00-api-catalog-scalar.md`. P2-04 adds only the best-effort first-Admin import of SurgePilot's own curated Web/business OpenAPI into the Default Workspace API Catalog. |
| API Catalog fixed boundary | `P2 API Catalog is documentation asset management only; it does not create, update, or generate Scenario/Test Plan.` Version diff, operation import, coverage analysis, and an API Catalog → Scenario/Test Plan generation chain remain out of scope. |
| OpenAPI Step generation | P2-01 activates only Scenario editor Step draft generation from authorized API Catalog spec assets through `docs/sdd/adr/ADR-0011-p2-openapi-step-generation.md` and `docs/sdd/slices/P2-01-openapi-step-generation.md`. |
| Public API Substrate | P2-02 activates only Account self-service API keys, PAT Bearer public business API, the public OpenAPI artifact, structured config writes, Run lifecycle access, bounded Dependency File list/upload/delete, and one repo-maintained Public API AI skill source package through `docs/sdd/adr/ADR-0012-p2-public-api-substrate.md` and `docs/sdd/slices/P2-02-public-api-substrate.md`. P2-04 adds only a session-authenticated request-built source download; it does not authorize a release, installer, marketplace, SDK, MCP, or public unauthenticated download. |
| Help / AI Agents / System OpenAPI Bootstrap | P2-04 activates only authenticated `/help` guidance, the session-authenticated request-built Public API AI skill source download, shared runtime/script OpenAPI export, and best-effort first-Admin system curated OpenAPI bootstrap through `docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md` and `docs/sdd/slices/P2-04-help-ai-agents-system-openapi-bootstrap.md`. User/external automatic ingestion, retries/workers, SDK, MCP, marketplace, installer, release publication, built-in agent runtime, AI generation/tuning/analysis, and API Catalog to Scenario/Test Plan generation remain out of scope. |
| Cross-platform distribution | P2-05 activates one complete tagged-release mode with GHCR `linux/amd64` / `linux/arm64` application images, a version-pinned user-local installer and checksummed bundle through `docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md`, GitHub Release Linux Runtime assets, release Compose plus `surgepilot up`, complete source Compose plus `make start-full-stack`, ADR-0019 source-only control-plane preview plus `make start-preview`, Monitoring, and one optional Compose-internal Demo Load Node through `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md`, `docs/sdd/adr/ADR-0019-p2-source-preview-startup.md`, and `docs/sdd/slices/P2-05-cross-platform-distribution.md`; preview does not claim execution readiness and external Load Nodes require explicit final API/InfluxDB URLs. Kubernetes, package-manager/system installers, Docker Hub mirroring, all-in-one images, native macOS Load Nodes/Runtime, automatic upgrades, Runtime UI/catalog, signing/SBOM publication, and standalone Public API AI skill release remain out of scope. |
| Public Dependency File boundary | `read` may list Workspace-visible Dependency Files; `dependency:write` may upload/delete through the existing storage, validation, audit, Workspace, and reference-protection services. Public preview/download and generic binary APIs remain out of scope. |
| Secret | P2-03 activates Env Group `plain | secret` typed variables, session masked secret reads, session-only secret writes, plain-only public DTOs, the required one-time string-map-to-plain migration, and public API secret exclusion through `docs/sdd/adr/ADR-0014-p2-env-group-secret.md` and `docs/sdd/slices/P2-03-env-group-secret.md`; a reveal API and public secret management remain forbidden. |
| Snapshot security | Secret-type Env variables must eventually be saved encrypted in Run Snapshot; P2-03 only allows temporary internal execution-needed plaintext and does not activate Snapshot encryption. |
| Key management | Key rotation and the historical Run decryption boundary remain inactive. |
| Desensitization | Desensitization of general sensitive information in logs and error messages remains inactive; P2-03 only adds targeted Env Group secret response, preview, and report redaction. |
| Dependency Files | ZIP / TAR / TGZ safe decompression. |
| Schedule | One-time Schedule Run and Scheduled Job status closed loop. |
| Enterprise Login | OAuth 2.0 / OIDC. |
| SSO | SSO user automatic creation, SSO group/claim to Admin/User mapping. |
| Storage expansion | Local file system, AWS S3, Alibaba Cloud OSS, or another object storage backend. |

P2 shall not be realized early during the P0 phase. An excluded capability is still implemented if it exists only as a hidden API, route, migration, disabled service, or feature-flagged usable path.
