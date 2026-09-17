# 00 Product Scope and Priority

- Document status: Draft
- Project: SurgePilot performance load testing platform
- Document location: `docs/sdd/00-product-scope-and-priority.md`
- Product source: `docs/prd/PRD.md`
- Current delivery target: P2-02 Public API Substrate and governed Public API AI skill source package implementation + P2-03 Env Group Secret implementation + P2-04 Help AI Agents and System OpenAPI Bootstrap + P2-05 Cross-platform Distribution, Full-stack Release Bootstrap, and ADR-0019 Source Preview Startup + P2-06 LAN-first Release Bootstrap Usability, ADR-0020 Release Dual-Architecture Runtime Default, and ADR-0021 Release `up` Configuration Confirmation + P2-07 Public Launch, GitHub Pages, and SEO + ADR-0013 static Marketing Landing and Logo + P1-09 Scenario Global Configuration SDD authorization + localized Public User Documentation MVP
- Scope of application: Foundation SDD, Slice SDD, AGENTS.md, AI Coding, code review, test acceptance

---

## 1. Document purpose

This article is the **Scope Gate / scope gate document** developed by SurgePilot.

It only answers four questions:

1. What must be done at the current stage;
2. To what extent must the current stage be stable;
3. What clearly must not be done at the current stage;
4. When there are fuzzy boundaries in requirements or implementation, how to judge whether the boundaries have been crossed.

This article is not a second PRD, nor is it a module-level detailed design. Module details should be put into the corresponding Foundation SDD or Slice SDD.

---

## 2. Authoritative sources and conflict handling

The only sources of product wording are:

- `docs/prd/PRD.md`

Subsequent SDDs, ADRs, Issues, code implementations, and AI outputs may not overwrite the PRD.

Conflict handling rules:

1. If this document or other SDD conflicts with the PRD, the PRD shall control.
2. If you really need to change the product scope, you must first explicitly update the PRD or add a confirmed ADR.
3. Slice SDD shall not independently expand its product range.
4. Code implementation must not implement P1/P2 in advance on the grounds of "it was done easily", "the entrance is hidden" or "the configuration switch is turned off".
5. P1/P2 capabilities are considered to be implemented in advance even if they only have backend interfaces, hidden routes or no UI displayed.

---

## 3. Current delivery target

Current delivery targets are:

> **P2-02 Public API Substrate and governed Public API AI skill source package implementation + P2-03 Env Group Secret implementation + P2-04 Help AI Agents and System OpenAPI Bootstrap + P2-05 Cross-platform Distribution, Full-stack Release Bootstrap, ADR-0019 Source Preview Startup, and ADR-0024 User-local Release Installer + P2-06 LAN-first Release Bootstrap Usability, ADR-0020 Release Dual-Architecture Runtime Default, ADR-0021 Release `up` Configuration Confirmation, and ADR-0024 User-local Release Installer + P2-07 Public Launch, GitHub Pages, and SEO + ADR-0013 static Marketing Landing and Logo + P1-09 Scenario Global Configuration SDD authorization + localized Public User Documentation MVP**

P0 is the completed baseline; P1 can only be started via the Revision Protocol of `docs/sdd/slices/P1-README.md`, accepted ADRs, and the real P1 Slice SDD. `ADR-0008` / `P1-08-debug-http-trace` and `ADR-0015` / `P1-09-scenario-global-configuration` are the currently allowed P1 append slices.


P2-00 API Catalog Scalar remains the accepted API documentation asset management Slice through `docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md` and `docs/sdd/slices/P2-00-api-catalog-scalar.md`. It is limited to API documentation asset management (`upload / list / detail / delete`) plus an authorized content proxy and Scalar read-only rendering.

P2-01 OpenAPI Step Generation remains an active P2 Slice through `docs/sdd/adr/ADR-0011-p2-openapi-step-generation.md` and `docs/sdd/slices/P2-01-openapi-step-generation.md`. It is limited to Scenario editor Step draft generation from authorized API Catalog spec assets. It does not activate API Catalog operation management, API Catalog detail-page generation actions, Scenario creation, Test Plan generation, Schedule Run, Help, SSO, Secret, non-MinIO storage, or any other P2 capability.

P2-02 Public API Substrate is an active P2 Slice through `docs/sdd/adr/ADR-0012-p2-public-api-substrate.md` and `docs/sdd/slices/P2-02-public-api-substrate.md`. It activates only Account self-service API keys, PAT Bearer public business API, public OpenAPI artifact, structured config writes, Run lifecycle access, a bounded Dependency File public extension (`read` list plus `dependency:write` upload/delete), and one repo-maintained Public API AI skill source package whose allowlist and bundled snapshot are governed by that public artifact. The Dependency File extension reuses the existing filename/extension/size/SHA/MinIO/Workspace/reference-protection contracts and does not add public preview or download. P2-02 does not authorize public token-management routes, admin-managed keys, token-on-token rotation, new RBAC, Schedule Run, Help/download UI outside P2-04, SDK, MCP server, skills runtime, release publication, SSO, Env Group Secret, non-MinIO storage, or any API Catalog → Scenario/Test Plan generation chain.

P2-03 Env Group Secret is an active P2 Slice through `docs/sdd/adr/ADR-0014-p2-env-group-secret.md` and `docs/sdd/slices/P2-03-env-group-secret.md`. It activates only Env Group `plain | secret` typed variables, session masked secret read models, session-only secret writes, plain-only public DTOs, required one-time string-map-to-plain migration, public API secret exclusion, and existing runtime env materialization. It does not authorize Snapshot encryption, key rotation, reveal API, external Secret Manager integration, generic redaction, new RBAC, or any broader public secret management.

P2-04 Help AI Agents and System OpenAPI Bootstrap is an active P2 Slice through `docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md` and `docs/sdd/slices/P2-04-help-ai-agents-system-openapi-bootstrap.md`. It activates only authenticated `/help` agent-native guidance, a session-authenticated request-built download of the repo-maintained Public API AI skill source, shared runtime/script OpenAPI export logic, and a best-effort first-Admin import of SurgePilot's own curated Web/business OpenAPI into the Default Workspace API Catalog. It does not authorize user/external automatic OpenAPI ingestion, retries/workers, SDK, MCP, marketplace, installer, release publication, built-in agent runtime, AI generation/tuning/analysis, or API Catalog to Scenario/Test Plan generation.

P2-05 Cross-platform Distribution and Full-stack Release Bootstrap is an active P2 Slice through `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md`, amended for source preview by `docs/sdd/adr/ADR-0019-p2-source-preview-startup.md`, amended for the user-local platform Release installer by `docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md`, and `docs/sdd/slices/P2-05-cross-platform-distribution.md`. It activates only one complete tagged-release mode using GHCR multi-architecture SurgePilot application images, a bounded GitHub Release bundle, a version-pinned user-local installer and bundle checksum, native-built `linux-amd64` / `linux-arm64` Runtime assets, release Compose plus `surgepilot up`, complete source Compose plus `make start-full-stack`, source-only control-plane preview through `make start-preview`, P1 Monitoring, and one optional Compose-internal real Demo Load Node. Preview does not claim Runtime, Load Node initialization, or Run execution readiness. It does not authorize Kubernetes, package-manager/system installers, Docker Hub mirroring, all-in-one images, native macOS Load Nodes/Runtime, automatic upgrades, Runtime UI/catalog, signing/SBOM publication, standalone Public API AI skill release, or any P2-02 Phase A expansion.

P2-06 LAN-first Release Bootstrap Usability is an active P2 Slice through `docs/sdd/adr/ADR-0018-p2-lan-first-release-bootstrap.md`, amended by `docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md`, `docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md`, and `docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md`, and `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`. ADR-0020 changes only new tagged-release deployments to default to `amd64,arm64` without an architecture prompt; all four advanced Runtime values remain valid and source startup remains native-only. ADR-0021 requires every valid release `up` to display its bounded non-secret configuration before Runtime fetch: interactive default-Yes is read-only, explicit No/re-entry/Yes may update only four allowlisted standard-LAN network fields, non-interactive startup never rewrites, and advanced HTTPS remains manual-edit-only. ADR-0024 adds only the separate, version-pinned user-local installation command and does not run `up` inside the download pipeline. Automatic repair, secrets and non-network state, all other ADR-0018 host/origin, Demo-off, cookie transport, authenticated InfluxDB publication, non-interactive smoke, warned loopback-origin, and all-interface published-port contracts remain unchanged. P2-06 does not add network discovery, Web/API configuration, a package-manager/system installer, or public workflow dispatch capability.

P2-07 Public Launch, GitHub Pages, and SEO is an active P2 Slice through `docs/sdd/adr/ADR-0026-p2-public-launch-github-pages-seo.md` and `docs/sdd/slices/P2-07-public-launch-github-pages-seo.md`. It activates only the coordinated `latentrun/SurgePilot` public repository launch, one statically generated VitePress Pages marketing/docs site under `https://latentrun.github.io/SurgePilot/`, exact English/`zh-CN`/`ja` user-documentation mirrors below `/docs/`, original AI-authored baseline evidence, publication SEO and social metadata, self-hosted Web `noindex`, demo/social assets, repository metadata preparation, history/public-readiness review, and a gated Pages deployment. It consumes the existing P2-05/P2-06 tagged Release without changing Runtime, installer, Compose, application publication, or startup semantics. The two Landing variants may preserve their original animated synthetic dashboard, Recent Test Runs, and Distributed load mesh only as adjacent, explicit UI demonstration/example data that is not a live service, live topology, benchmark, adoption claim, or evidence source. P2-07 does not authorize hosted SurgePilot, pricing/billing/leads, blog/CMS, programmatic SEO, a custom-domain launch, automatic translation, product localization, fabricated benchmark/adoption/status/Star claims, or mandatory AI provenance for later community contributions.

ADR-0013 static Marketing Landing and Logo authorizes only the static public `/` Marketing Landing route and Logo visual migration. It does not authorize API, DB, migration, runner, contracts, SDK, MCP, Help, Docs, Community, API Guide, GitHub, or external runtime design assets.

The Public User Documentation MVP remains localized through `docs/sdd/adr/ADR-0025-public-user-documentation-localization.md` and is published only through the bounded P2-07 amendment in ADR-0026. It retains one same-repository VitePress package under `docs/site`, the exact `docs/site` pnpm workspace entry, six authoritative English user pages (Home, Quickstart, Startup Modes, Configuration, First Run, and FAQ), exact Simplified Chinese (`zh-CN`) and Japanese (`ja`) mirrors, native locale navigation, exact locale page-set and relative-link checks, and Configuration reference coverage aligned with source and tagged-release `.env.example` templates. P2-07 moves the same exact page sets below `/docs/`, `/docs/zh-CN/`, and `/docs/ja/` inside the unified Pages site and authorizes the gated publication metadata/workflow only after private acceptance passes. A seventh user page, automatic translation or language redirection, product UI localization, a custom domain, API or AI Skill reference sections, contributor architecture navigation, and multi-version documentation remain inactive. `docs/sdd` and `docs/prd` remain engineering sources outside the user-documentation main navigation.

P1-09 Scenario Global Configuration Phase A is an active P1 Slice through `docs/sdd/adr/ADR-0015-p1-scenario-global-configuration.md` and `docs/sdd/slices/P1-09-scenario-global-configuration.md`. It activates only Scenario-level structured Global Configuration Phase A Tabs for `Settings`, `Headers`, `Variables`, and `Data Sources`; Settings/Data Sources reuse existing Scenario capability, while `globalHeaders` and Scenario-local non-secret `variables` are new. It preserves P1-04 Clone / Archive / tags and the Test Plan Preview semantics amended by `docs/sdd/adr/ADR-0023-remove-scenario-execution-preview.md`; Scenario Preview is not exposed. It does not change Test Plan schema except through existing Scenario references naturally used by execution. It does not authorize editable Taurus YAML, JMX upload, API Catalog generation, Schedule, multi-node, Secret Scenario variables, JMeter expert panels, new runtime dependencies, k6/Locust abstractions, or Phase B `globalScripts`.

The goal of P0 is to run through the internal network MVP closed loop, rather than deliver a complete enterprise-level platform.

P0 must also contain:

1. **P0-Core**: Users can complete the core load test closed loop;
2. **P0-Stability**: Execution, status, permissions, resource and file security will not be out of control.

P0-Core and P0-Stability must be delivered together. You cannot first make a "runnable but unstable" version and then postpone capabilities such as state machine, Stop idempotence, Runner heartbeat, permission verification, and path security to P1.

---

## 4. P0 product main link

P0 is only delivered around the following primary links:

```text
Default Workspace
  ↓
Local account registration/login
  ↓
Create Env Group / Dependency File / Load Node
  ↓
Create Visual Scenario
  ↓
Create Test Plan
  ↓
Manually select a single Idle Load Node
  ↓
Debug Run / Run Now
  ↓
View Run Report/artifacts
  ↓
Mark Valid / Invalid
  ↓
Reuse and Iterate Scenario/Test Plan
```

Core product mentality:

- **Scenario**: Define "what to suppress";
- **Test Plan**: Define "how to test, what resources to use, and what counts as passing";
- **Run**: an actual execution;
- **Run Report**: judge results, locate problems, and download products;
- **Env Group / Dependency File / Load Node**: Reusable assets that support execution.

Taurus is the underlying execution compatibility layer, not the primary user mind. P0 should not be implemented as a Taurus YAML web editor, a JMeter launcher, or an artifacts file management system.

---

## 5. P0 must deliver scope

### 5.1 P0-Core

P0-Core must contain:

| module | P0 range |
| --- | --- |
| Account | Local email password for registration, login, and logout; the first user automatically becomes Admin; subsequent users default User |
| Workspace | Default Workspace; all business data from day one Workspace-aware |
| Overview | Basic overview, recent executions, resource status summary, quick entry |
| Env Groups | Environment variable group CRUD, copy, reference display, deletion protection |
| Dependency Files | MinIO ordinary file upload, list, download, deletion protection |
| Load Nodes | Public / Private Load Node registration, initialization, status, logs, basic management |
| Scenarios | Visual Scenario creation, editing, saving, Step management, Debug Run |
| Test Plans | Test Plan Creation, Editing, Scenario Orchestration, Load Settings, SLA Minimum Subset |
| Resources | Manual Single node selection; only allows selection of one Idle node |
| Runs | Run Now, Debug, Run List, Stop, Validity tags |
| Run Report | Verdict, KPI, Failure Diagnostics, Final Stats, Snapshot, collapsible Artifacts, Nodes |
| Artifacts | MinIO artifacts metadata, download, basic preview |
| Admin | Setup Status read-only page; platform-level read-only view, not bound to a specific Workspace; other Admin operations are still subject to Workspace context, permissions and data isolation constraints |
| UX | Basic empty status, error status, Loading, and prevention of duplicate submissions |

### 5.2 Workspace boundary of Admin Setup Status

Most business data in P0 must have Workspace ownership and be isolated through `x-workspace-id` or equivalent authentication context.

The only explicit exceptions are:

> **Admin Setup Status is a platform-level read-only configuration and health status view, and is not bound to a Workspace as a business record. **

This exception only applies to the Setup Status page itself and may not be extended to global reasons for other business resources.

The constraints are as follows:

1. Setup Status can show whether the default Workspace exists, whether MinIO/artifacts are available, whether Public Load Node is available, whether local registration is enabled, whether the concurrency limit is configured, whether background self-healing tasks are enabled, and other platform-level statuses.
2. Setup Status can display current context-oriented check items such as "whether the current Workspace has available Private Load Node".
3. Setup Status does not display sensitive configuration values and does not display Private Load Node credentials.
4. In addition to Setup Status, Scenario, Test Plan, Run, Env Group, Dependency File, Private Load Node, Run Snapshot, artifacts metadata, etc. must still be Workspace-aware.
5. Other Admin operations, including viewing default Workspace data, managing Public Load Nodes, viewing basic node status, etc., must still go through backend permission verification.

### 5.3 P0-Stability

P0-Stability must contain:

| Domain | P0 Stability Requirements |
| --- | --- |
| Run Snapshot | Save Test Plan, Scenario, Env Group, Dependency File, Load Settings, SLA, Resource Request, etc. execution snapshot when Run is created |
| Run state machine | Supports Initializing, Running, Stopping, Finished, Failed, Aborted |
| Terminal status | Finished / Failed / Aborted must not be overwritten by subsequent callbacks |
| Stop | Stop Initializing / Running must be idempotent and converge to Aborted or Failed |
| Runner callback | accepted, running, heartbeat, artifact, finished, failed, aborted must be idempotent |
| Heartbeat timeout | Runner heartbeat timeout must be converged to the final state by the background self-healing task |
| Node lease full life cycle | Run atomically obtains and marks a single Load Node as Busy when it is created; it is released by callback or api-worker in the final state; the node must not be permanently Busy |
| Workspace | All business queries and writes must carry the Workspace context |
| Permission | Admin/User permissions must be verified by the backend, and the entrance cannot be hidden by the frontend alone |
| Credential safety | Private Load Node SSH passwords, private keys and other sensitive credentials will not be echoed back in text after being saved, nor may they be displayed in plain text to the Admin |
| Path safety | Dependency File, artifact callback, artifact download and preview must prevent path crossing |
| Account safety | Password security hashing, login state expiration, basic explosion protection |
| Input guard | Basic values such as concurrency, duration, and throughput must have back-end hard verification; single-node concurrency exceeding the soft upper limit must be strongly prompted and confirmed twice |

Input guard supplementary rules:

1. The soft upper limit is used to remind users of risks and is not equivalent to a hard rejection.
2. Hard verification is used to protect the stability of the platform and pressure-generating nodes. Extreme inputs such as negative numbers, non-digits, obviously abnormal large values, and long durations must be rejected.
3. By default, PRD triggers a strong warning when the single-node concurrency exceeds 1,000; the final configuration name, coverage method, and front-end and back-end verification boundaries are specified in the Test Plan / Load Settings slice by `P0-06-test-plan-run-now.md`.
4. Soft caps should not be hard-coded in multiple locations; they should be managed through deployment-level configuration or a shared contract/config schema.

P0-Stability is not an optimization and must not be postponed.

Supplementary borders:

1. For the force-kill cleanup and node quarantine rules, see `docs/sdd/05-runner-protocol-and-run-state-machine.md` for details. 00 does not expand the implementation details repeatedly.
2. 00 only locks the scope gate; the state machine, cleanup path and callback idempotent details are subject to 05.

---

## 6. P1 range

P1 is the stage of experience improvement and efficiency enhancement, and does not block P0.

P1 final reservation list:

| Domain | P1 Competencies |
| --- | --- |
| Monitoring | Read-only entry + JMeter Backend Listener / InfluxDB write config Write link configuration, including Terminal status history playback entry; does not include Grafana datasource management, Dashboard editing or InfluxDB management |
| Resource | Auto allocation, multi-node execution, Node Count, Selected Nodes |
| Workspace | Workspace switching, creation, editing, archiving, etc. UI |
| User Management | User list, disable/enable, role modification, create user, reset password |
| System Settings | Some non-sensitive configuration UI |
| Scenario/Test Plan polish | Clone, Archive, Test Plan-only read-only Generated YAML / Execute configuration preview, existing lightweight tag; Scenario Preview is removed by `ADR-0023`; P1-09 Scenario Global Configuration Phase A by `ADR-0015` additionally authorizes only Scenario-level structured `Settings` / `Headers` / `Variables` / `Data Sources` Tabs, of which `globalHeaders` and Scenario-local non-secret `variables` are new capabilities; do not change the semantics of P1-04 Clone / Archive / tags or Test Plan Preview; the Test Plan schema must not be changed, and the execution effect can only be naturally reflected through the existing Scenario reference and execution bundle/Taurus builder |
| Scenario / Test Plan tags | Existing lightweight metadata is retained, not a new P1 deliverable; P1 does not add a new front-end list filtering UI by tag, nor does it extend tags to other assets |
| Dependency Files | Single file preview |
| Run Report | failed_requests plug-in preview, failed_requests/finalstats large file paging and enhanced preview; Debug Run `debug_http_trace` (only `ADR-0008` and `P1-08-debug-http-trace` are displayed to display the request/response details) |
| Run tags | Run tag display/filter If it exists, the Scenario/Test Plan tags in the snapshot must be used; Run does not have an independent variable tag model; Run List currently only displays tags and does not add a new filtering UI |
| Import | cURL import; P1 Import only refers to cURL import |

P1 fixed boundary:

- P1 no longer contains any generation links for OpenAPI / API Catalog → Scenario / Test Plan; P1 Import only refers to cURL import.
- P1 does not support API Catalog, automatic generation of OpenAPI Step, Schedule Run, Scheduled Job, in-product Help page, Dependency Files label, and secure decompression of ZIP/TAR/TGZ.
- Env Group / Dependency File tags are permanently removed and do not enter any stage.
- P1 does not have Load Node tags; if resource matching tags are needed later, they will be classified into P2 Resource matching and designed separately.
- P1 Monitoring does not include Grafana datasource management, Dashboard editing, and InfluxDB management; it only provides write link configuration and read-only entry for JMeter Backend Listener + InfluxDB write config.
- P1 Debug HTTP Trace only applies to Debug Run, not Standard Run; does not introduce JMeter plugins, Backend Listener, Monitoring, common logging/masking framework, or runtime tar changes.
- P1-09 Scenario Global Configuration Phase A does not activate `globalScripts`, editable Taurus YAML, Secret Scenario variables, Test Plan schema redesign, API Catalog generation, Schedule, multi-node, JMeter expert panels, or script library capabilities.

Recommended P1 Slice split:

- `P1 Monitoring`
- `P1 Resource Multi-node`
- `P1 Workspace/Admin`
- `P1 Scenario/TestPlan Polish`
- `P1 cURL Import`
- `P1 Dependency Preview`
- `P1 Run Report Preview`
- `P1 Debug HTTP Trace`

The capability of P1 must not become a pre-dependency of the closed loop execution of P0.

## 7. P2 range

P2 is the enterprise-level security governance, deployment expansion and delayed enhancement phase.

P2 includes but is not limited to:

| Domain | P2 Competencies |
| --- | --- |
| API Catalog | API document asset management, only upload / list / details / delete; P2-04 additionally allows one system-owned first-Admin bootstrap import of SurgePilot's own curated Web/business OpenAPI into Default Workspace |
| API Catalog fixed boundary | `P2 API Catalog is documentation asset management only; it does not create, update, or generate Scenario/Test Plan.` P2 API Catalog also does not contain version diff, operation import, coverage analysis, API → Scenario/Test Plan generation, or user/external automatic ingestion; the P2-04 system bootstrap exception does not change this boundary |
| OpenAPI Step generation | P2-01 Only allows Scenario editor Step draft generation from authorized API Catalog spec assets; may not be implemented in advance as API Catalog → Scenario/Test Plan generation link |
| Public API Substrate | P2-02 only allows Account self-service API keys, PAT Bearer public business API, public OpenAPI artifact, structured config writes, Run lifecycle access, bounded Dependency File list/upload/delete, and one repo-maintained Public API AI skill source package verified against that artifact; P2-04 adds only a logged-in request-built source zip download, not a release distribution or runtime |
| Public Dependency File boundary | `read` may list Workspace-visible Dependency Files; `dependency:write` may upload/delete through existing storage, validation, audit, Workspace and reference-protection services. Public preview/download and generic binary APIs remain out of scope. |
| Schedule | One-time Schedule Run, Scheduled Job status closed loop; together with Overview "upcoming execution" statistics, Test Plan details are not triggered Scheduled Jobs list |
| Help | P2-04 activates authenticated in-product Help with `AI Agents` guidance and official skill source download; engineering documents such as README/deployment/operation and maintenance remain unrestricted |
| Cross-platform distribution | P2-05 activates one complete tagged-release mode with GHCR `linux/amd64` / `linux/arm64` application images, a version-pinned user-local installer and checksummed bundle through ADR-0024, GitHub Release Linux Runtime assets, release Compose plus `surgepilot up`, complete source Compose plus `make start-full-stack`, ADR-0019 source-only control-plane preview plus `make start-preview`, Monitoring, and an optional Compose-internal Demo Load Node; preview does not claim execution readiness and external Load Nodes require explicit final API/InfluxDB URLs |
| Public launch and Pages | P2-07 activates the coordinated `latentrun/SurgePilot` public launch, one unified static VitePress marketing/docs Pages site, exact localized user-doc mirrors below `/docs/`, original AI-authored baseline evidence, publication SEO, self-hosted Web `noindex`, public-readiness review, and legitimate Star-growth assets without changing product/release execution contracts |
| Dependency Files | ZIP / TAR / TGZ safe decompression |
| Resource matching | If Load Node tags or resource matching tags are needed later, they will be classified into P2 and designed separately |
| Enterprise Login | OAuth 2.0 / OIDC |
| SSO | SSO user automatic creation, SSO group/claim to Admin/User mapping |
| Secret | P2-03 activates Env Group `plain | secret` typed variables, session masked secret reads, session-only secret writes, plain-only public DTOs, and public API secret exclusion through `docs/sdd/adr/ADR-0014-p2-env-group-secret.md`; reveal/copy remains forbidden. |
| Snapshot security | Secret type Env Var is saved encrypted in Run Snapshot; P2-03 only allows temporary internal execution-needed plaintext and does not activate Snapshot encryption. |
| Key management | Key rotation, history Run decryption boundary |
| Desensitization | Desensitization of general sensitive information in logs and error messages |
| Storage expansion | Local file system, AWS S3, Alibaba Cloud OSS or other object storage backend |

P2 shall not be realized early during the P0 phase.

## 8. The first version will not be made yet.

Unless the project is subsequently re-established, the following capabilities will not enter the scope of the first version:

1. AI generated scenes;
2. AI parameter adjustment;
3. AI report analysis;
4. Independent Load Profile template library;
5. Multi-tenant complex permission model;
6. Resource queuing system;
7. Automatic expansion and contraction;
8. Automatic procurement of cloud resources;
9. Auto quarantine recovery;
10. Real-time link tracking/APM deep integration;
11. Trend comparison;
12. Capacity baseline;
13. Historical regression analysis;
14. Notification subscription;
15. Alarm push;
16. Self-developed load testing execution engine replaces Taurus;
17. Independent script scene mode;
18. Postman Collection;
19. Raw JMeter JMX upload;
20. Independent API coverage analysis platform;
21. Cross-product data import;
22. Batch asset import;
23. Compatible with external scripts.

---

## 9. P0 Explicit Prohibitions

The following capabilities are prohibited from being implemented in the P0 stage.

### 9.1 Importing and API Assets

P0 prohibited:

- API Catalog;
- OpenAPI / Swagger Spec upload;
- API Spec details display;
- Create Test Plan from API operation;
- OpenAPI Step is automatically generated, including Path / Query / Header / JSON Body generation;
- API document import or any API Catalog / OpenAPI → Scenario/Test Plan generation link;
- cURL import;
- Postman Collection import;
- JMeter JMX upload;
- Locust import or compatible run.

Allowed:

- Reserve route planning or navigation space for future API Catalog, but must not provide available entrances;
- P1 no longer contains any generation links for OpenAPI / API Catalog → Scenario / Test Plan; P1 Import only refers to cURL import.

### 9.2 Execution resources

P0 prohibited:

- Resource Auto allocation;
- Multi-node execution;
- Node Count;
- Manually select multiple nodes;
- Cross-node concurrent summary;
- Resource queuing;
- Automatic expansion and contraction;
- Automatic procurement of cloud resources.

Allowed:

- The data structure reserves expansion space for future multiple nodes;
- Manual single node must be strictly implemented when running P0.

### 9.3 Scheduling

P0 prohibited:

- Schedule Run;
- Scheduled Job;
- Periodic tasks;
- Scheduling retries;
- Scheduling and queuing;
- Upcoming Scheduled Jobs statistics.

### 9.4 Monitoring

P0 prohibited:

- Monitoring page;
- Grafana iframe;
- Open in Grafana;
- InfluxDB write link;
- InfluxDB datasource management;
- Grafana Dashboard editor;
- InfluxDB management;
- JMeter Backend Listener configuration management;
- Run ID timing indicator filtering;
- Real-time TPS / response time / error rate graphs.

Allowed:

- Run Report completes P0 result judgment through offline artifacts, final stats summary, security failure reasons and log download; failed_requests plug-in preview belongs to P1;
- P1 Monitoring only provides write link configuration and read-only entry for JMeter Backend Listener + InfluxDB write config, and does not include Grafana datasource management, Dashboard editing or InfluxDB management.

### 9.5 Enterprise security and account management

P0 prohibited:

- OAuth 2.0;
- OIDC;
- SAML;
- LDAP;
- SSO group mapping;
- User Management UI;
- Workspace member management;
- Complex RBAC;
- Secret Env Var;
- General log and error message desensitization framework;
- Secret Snapshot encryption and key rotation.

Allowed:

- Local email password account;
- Admin/User two-level roles;
- Backend permission verification;
- Password secure hashing;
- Login status expired;
- Basic explosion-proof.

### 9.6 Storage

P0 prohibited:

- Local file system as Dependency File/artifacts storage backend;
- AWS S3;
- Alibaba Cloud OSS;
- Other object storage adaptation;
- ZIP / TAR / TGZ automatic decompression;
- Dependency File tag;
- Env Group tag;
- Online document editing;
- Dependency File preview.

Allowed:

- MinIO only;
- Ordinary file upload, download, reference, and deletion protection;
- artifacts metadata, downloads and basic previews;
- Path security verification;
- P1 only adds Dependency File single file preview; ZIP / TAR / TGZ can be safely decompressed into P2.

### 9.7 Taurus / YAML

P0 prohibited:

- Editable Taurus YAML editor;
- View Generated YAML;
- Preview Generated YAML;
- Read-only Generated YAML / execute configuration preview;
- Users directly edit and execute YAML.

Allowed:

- Backend internally generates Taurus/JMeter execution configuration;
- Keep low-level logs and execution files in artifacts for troubleshooting.

Description:

- **Test Plan-only Read-only Generated YAML/Execution Configuration Preview is a P1 diagnostic capability and is not part of P0. Scenario does not expose this surface.**
- The first version does not provide any editable YAML entry.

---

## 10. Range judgment rules

If you encounter uncertain requirements during the development process, judge according to the following rules.

### 10.1 Necessary conditions for entering P0

An ability can enter P0 only if it meets the following conditions at the same time:

1. PRD is clearly listed as P0-Core or P0-Stability;
2. Support the closed loop of manual Scenario → Test Plan → Manual Single Node Run → Run Report;
3. Does not rely on API Catalog, Monitoring, Schedule Run, multi-node, OIDC, Secret, non-MinIO storage; P1 does not contain any OpenAPI/API Catalog → Scenario/Test Plan generation link, and P1 Import only refers to cURL import;
4. Can be completed in the default Workspace;
5. Can pass automated verification under `make verify` or the temporary bootstrap verification command explicitly declared by this slice;
6. Do not introduce P1/P2 user-visible entrance.

### 10.2 Signals that do not belong to P0 by default

If a capability meets any of the following conditions, it does not belong to P0 by default:

1. Mainly improves efficiency, rather than supporting P0 closed loop;
2. Mainly improve the management experience, rather than ensuring that P0 can run;
3. Involves import, monitoring, scheduling, and multiple nodes;
4. Involving SSO, Secret, desensitization, and non-MinIO storage;
5. Without it, users can still complete the P0 main link manually;
6. Just for future expansion convenience.

### 10.3 Not allowed bypasses

The following practices are not allowed:

1. "Build the back-end interface first, and the front-end will not be displayed."
2. "Use the configuration switch to hide it first."
3. "Do half of it first, without accessing the mouth."
4. "The database fields already exist, so it can be easily implemented."
5. "AI is easy to write and we can do it together."
6. "P1 will have to be done sooner or later, why not do it now?"
7. "It was used in the test, so it was made into a product capability."

---

## 11. Engineering constraints

### 11.1 Contract priority

Functions involving API, front-end, and Runner must comply with:

1. Define or update contracts / OpenAPI first;
2. Then implement the API;
3. Then implement the Web consumer;
4. Then implement Runner or callback;
5. Final test and acceptance.

Frontends must not guess the API shape.

Runners must not import API internal code.

The API and Runner can only communicate through contracts and Runner Protocol.

### 11.2 Workspace from day 1

Although P0 only exposes the default Workspace, all business data must have Workspace ownership from the first day.

Include at least:

- Scenario;
- Test Plan;
- Run;
- Env Group;
- Dependency File;
- Private Load Node;
- Run Snapshot;
- artifacts metadata.

Setup Status is a platform-level read-only view and is an explicit Workspace exception listed in this article; it may not be extended as a global resource for other business objects.

### 11.3 Run Snapshot mandatory

A snapshot of the execution must be saved when the Run is created.

Historical Run Report must be displayed based on snapshots and must not be contaminated by subsequent asset modifications.

### 11.4 MinIO only in P0

P0 Dependency Files and artifacts can only use MinIO.

If a storage abstraction exists in the code, P0 can only have a MinIO implementation.

### 11.5 Manual single node only in P0

P0 Each Run can only be bound to one manually selected Idle Load Node.

It must be verified when performing creation:

1. Node exists;
2. The node is Idle;
3. Pool Type matching;
4. Workspace matching;
5. The user has permission to use the node;
6. The node is not occupied by other Runs.

Creating Run, locking nodes, and creating node leases must be completed in the atomic persistence process.

---

## 12. AI/development task reading rules

Each development task reads by default:

1. `docs/sdd/README.md`;
2. `docs/sdd/00-product-scope-and-priority.md`;
3. Current Slice SDD;
4. Related `AGENTS.md`;
5. Related contracts / OpenAPI.

Read on demand:

- Relevant chapters of `docs/prd/PRD.md`;
- Related Foundation SDD;
- Relevant ADR;
- Related code and tests.

Do not read the full PRD, full SDD Pack, and all Slice SDDs indiscriminately in each task.

---

## 13. Slice SDD scope rules

Each Slice SDD must specify:

1. The Goal of this slice;
2. Corresponds to PRD Trace;
3. In Scope;
4. Out of Scope;
5. Whether it involves Runner / Storage / External Dependency;
6. P0-Stability requirements such as permissions, Workspace, path security, state machine, etc.;
7. Tests;
8. Done When.

Done When must be verifiable, not just "function completed".

Preferred use:

```bash
make verify
```

If the current slice is in the repository bootstrap phase and `make verify` is not yet fully available, the Slice SDD must declare a temporary verification command and converge to `make verify` or equivalent unified entry in subsequent M0/P0-00.

Each Slice SDD must specify which P1/P2 capabilities this slice does not provide.

Slice SDD may not add capabilities prohibited by this article to In Scope.

---

## 14. P0 Acceptance Summary

When P0 is completed, at least the following main closed loop should be verified:

```text
First Admin registration/login
  ↓
Default Workspace initialization
  ↓
Create Env Group
  ↓
Upload Dependency File
  ↓
Register and initialize Load Node
  ↓
Create Visual Scenario
  ↓
Scenario Debug Run
  ↓
View Run Report/artifacts
  ↓
Create Test Plan
  ↓
Add Scenario, Load Settings, SLA
  ↓
Manually select a single Idle Load Node
  ↓
Run Now
  ↓
View Run Report/artifacts
  ↓
Mark Valid / Invalid
```

P0 must also verify the Stop stability closed loop:

```text
Run Now
  ↓
Run enters Initializing or Running
  ↓
User actively Stop
  ↓
Run into Stopping
  ↓
Repeating Stop will not cause status confusion
  ↓
Run converges to Aborted or Failed
  ↓
Load Node is released
  ↓
Run Report shows understandable reasons and existing artifacts/logs
```

P0 must also verify the following stability capabilities:

- Run Snapshot is not affected by subsequent modifications to assets;
- Runner accepted does not mean that the load testing has started, only running callback will enter Running;
- heartbeat can only update the last heartbeat and cannot overwrite the Terminal status;
- finished / failed / aborted callback remains idempotent when repeated arrivals occur;
- The artifact callback can only register the safe relative path of the current Run;
- heartbeat timeout can converge to the final state from the background self-healing task;
- Node lease can prevent repeated allocation and release in the final state;
- Workspace, permissions, Private Load Node credentials, and Dependency File/artifacts path security are all verified;
- Inputs such as concurrency, duration, throughput, etc. have basic hard verification; when the concurrency of a single node exceeds the soft upper limit, a strong prompt and a second confirmation are issued.

---

## 15. Review Checklist

When reviewing SDD, Issue, PR or AI code output, check for at least the following things.

### 15.1 Scope check

- Still only delivering P0?
- Is the API Catalog implemented in advance?
- Will OpenAPI Spec uploading/details display be implemented in advance?
- Is automatic generation of OpenAPI Step implemented in advance?
- Is cURL Import implemented in advance?
- Will Monitoring/Grafana/InfluxDB be implemented ahead of time?
- Is JMeter Backend Listener configuration management implemented in advance?
- Is Schedule Run / Scheduled Job implemented in advance?
- Will Auto Allocation/Multiple Nodes/Node Count be implemented in advance?
- Is Workspace switching or management UI implemented in advance?
- Is User Management UI / System Settings UI implemented in advance?
- Is OIDC / SSO / Secret / desensitization implemented in advance?
- Is non-MinIO storage implemented in advance?
- Make Taurus YAML a user-editable entry?
- Is read-only Generated YAML/execution configuration preview implemented in advance?

### 15.2 P0-Stability check

- Save Run Snapshot?
- Is there an explicit Run state machine?
- Is Stop idempotent?
- Is Runner callback idempotent?
- Will the Terminal state not be overwritten by subsequent callbacks?
- Can heartbeat timeout heal itself?
- Does Node lease cover acquisition, busy marking, release and compensation?
- Will Load Node not be permanently Busy?
- Are permissions verified by the backend?
- Does the Workspace context cover all business APIs?
- Does Setup Status remain a read-only, platform-level, non-sensitive display?
- Are the Private Load Node credentials not being echoed textually?
- Can Admins view or export Private Load Node sensitive credentials?
- Is the Dependency File/artifacts path safe?
- Are there basic hard checks on concurrency, duration, throughput, etc.?
- When the concurrency of a single node exceeds the soft upper limit, is there a strong prompt and a second confirmation?
- Are passwords securely hashed?
- Does the login status have an expiration date?

### 15.3 Product experience check

- Are standard terms from PRD used?
- Are Scenario, Test Plan, Run not mixed?
- Does the Run Report give conclusions first and details second?
- Are Status, SLA Result, and Validity displayed independently?
- Does Debug Run default to Invalid?
- Is Standard Run Valid by default?
- Is the empty state clear?
- Does the error copy explain the reason and next steps?
- Do the Loading status and anti-duplicate submission cover key actions?

### 15.4 Verifiability Check

- Can `make verify` be passed?
- If `make verify` is not yet available, was a temporary bootstrap verification command declared?
- Will the temporary verification command converge to the unified verify entry in the future?
- Does Done When contain specific commands, assertions, or a reproducible acceptance process?
- Do you avoid writing non-verifiable descriptions such as "function completed", "page available", "interface implemented", etc.?

---

## 16. Completion criteria

After this document is completed, it should satisfy:

1. R&D and AI can distinguish the completed P0 baseline from the current named active P1/P2 Slices and ADR-0013.
2. The boundaries of P0-Core, P0-Stability, P1, and P2 are explicit and do not treat an active Slice as authorization for unrelated capabilities.
3. Every active P1/P2 capability is traceable to an accepted Slice SDD and ADR where required; capabilities without an accepted activation source remain forbidden.
4. P0 prohibitions remain sufficiently visible as baseline and regression guardrails.
5. The document can be used as the scope basis of Slice SDDs.
6. The document can be used as a source of scope rules for `AGENTS.md`.
7. The document can be used as a scope checklist for code review.
8. The document remains consistent with `docs/prd/PRD.md` and accepted ADR amendments.
9. The document does not repeat module-level detailed specifications that belong in the PRD, Foundation SDDs, or Slice SDDs.
10. Done When and acceptance requirements can be verified through commands or reproducible processes.

---

## 17. P0 Boundary Principle

The `P0 only` wording below defines the P0 scope boundary and completed baseline. It is not a statement that the current delivery target excludes the named active P1/P2 Slices or ADR-0013.

> **P0 only performs a complete manual closed loop of the default Workspace, MinIO, Manual single node, Visual Scenario, Test Plan, Run, and Run Report; at the same time, stability capabilities such as Run state machine, Runner callback, Stop, heartbeat, self-healing, permissions, Workspace, path security, input verification, and resource release must be completed. **
