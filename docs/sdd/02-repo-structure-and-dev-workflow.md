# 02. Repository Structure and Development Workflow

- Current delivery target: P2-02 Public API Substrate, P2-03 Env Group Secret, P2-04 Help AI Agents and System OpenAPI Bootstrap, P2-05 Cross-platform Distribution, and P2-06 LAN-first Release Bootstrap under their accepted Slice ADRs

## Repository layout

```text
apps/
  api/                 FastAPI application, worker entrypoint, and migrations
  runner/              independent Runner application
  web/                 React application
packages/
  contracts/           OpenAPI output, generated Web client, Runner JSON Schemas
infra/
  docker/              Compose and container support
tests/
  contract/            cross-application contract checks
  e2e/                 end-to-end and real/fake Runner profiles
docs/
  prd/                 product requirements
  sdd/                 foundation, ADR, and Slice design documents
Makefile                stable repository commands
```

Applications must not import another application's private internals. Web consumes the generated client from `packages/contracts`; Runner and API communicate through versioned HTTP and JSON contracts.

## Root command contract

The repository exposes stable commands for bootstrap, development, contract generation, lint, type checking, tests, verification, and E2E verification. `make verify` is the default local and CI gate. `make verify-e2e` owns fake-Runner and configured real-SSH acceptance. Exact commands may begin as an M0 bootstrap subset but must retain their names as implementation grows.

## Contract-first workflow

1. Update the API schema or Runner JSON Schema source.
2. Generate committed OpenAPI, client, and schema artifacts.
3. Implement producers and consumers.
4. Add tests for behavior and contract freshness.
5. Run the root verification entrypoint.

Generated files are never edited by hand. Verification fails when generated artifacts are stale.

## Local development

Dependencies run in Docker Compose while Web, API, api-worker, and Runner may run from source. Environment examples contain placeholders only; real credentials and local overrides are ignored by version control. Database changes use append-only Alembic revisions rather than runtime schema creation.

## Release startup

P2-05 keeps source-checkout and tagged-release startup separate and does not add a second release mode:

- Source checkout uses `make start-full-stack`, which builds current source images and a local development Runtime and remains the default development and manual-acceptance entry.
- The source control-plane preview uses `make start-preview`. It performs the same secure root `.env` bootstrap, validates explicit external URL pairs and source Compose, and starts Web, API, api-worker, PostgreSQL, MinIO, Nginx, InfluxDB, and Grafana without Runtime preflight or the Demo profile. Preview overrides are process-local and never rewrite `.env`; Setup Status may report `not_configured`, and Load Node initialization and Run execution readiness are not promised. `make stop-preview` stops the preview without deleting volumes.
- Tagged releases publish a version-pinned `install.sh`, a checksummed bundle, and native-built Linux amd64/arm64 Runtime assets. The installer publishes below `${XDG_DATA_HOME:-$HOME/.local/share}/surgepilot` and creates a user-owned `surgepilot` launcher without `sudo` or shell-configuration changes; installation and the separate `surgepilot up` deployment decision stay two commands. A manually extracted bundle uses the `./surgepilot` spelling.
- Release Compose uses immutable multi-architecture image digests recorded in `release-manifest.json`, contains no application build context, and never falls back to a source build. Its lifecycle commands are `up`, `down`, `status`, and `logs`.
- Any external Load Node requires explicit final API and InfluxDB URLs; neither source nor release startup infers external connectivity from host interfaces or the Demo switch. The release bundle publishes application images and Linux Runtime assets only and never the Public API AI skill.
- P2-06 changes only this tagged-release path. A missing release `.env` requires an interactive host shell to confirm the host, HTTP port, and InfluxDB node-write port before services start; explicit canonical loopback (`localhost`, `127.0.0.1`, or `::1`) is allowed only as a warned local-evaluation choice for the persisted node-facing URLs and does not change the all-interface published-port bind. Non-TTY automation must pre-provision a complete owner-only `.env`. ADR-0017 decisions 7 and 8 are superseded only as ADR-0018 specifies.
- Release Demo defaults to disabled and new tagged-release deployments default to `SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64` without asking for Runtime architectures; `auto`, `amd64`, `arm64`, and `amd64,arm64` remain accepted advanced values. Release node-facing API/InfluxDB origins are required with no Compose-internal fallback, and release base Compose publishes the configured Nginx and authenticated InfluxDB ports on host interfaces. Source `make start-full-stack` and source Compose-internal Demo defaults remain unchanged, and root `.env.example` remains `auto`.
- Every valid release `up` prints the bounded non-secret effective configuration before Runtime fetch. Interactive startup uses default-Yes `[Y/n]`: accepting current state is read-only, while No repeats first-run entry or opens a standard-LAN loop that updates only the four allowlisted network fields after normalized review and Yes. Non-interactive startup prints the summary but never prompts or rewrites, advanced-HTTPS No requires manual `.env` editing, and source startup is excluded. Automatic or non-interactive rewriting, network discovery, a Web/API configuration surface, package-manager/system installers, and public workflow dispatch remain forbidden.

For the accepted P2-06 LAN-first release bootstrap, factual verification is kept in the active Slice SDD and its focused checks: `tests/test_release_wrapper.py`, `tests/test_release_preflight.py`, `tests/test_bootstrap_deployment_env.py`, `tests/test_node_facing_startup.py`, `tests/test_release_installer.py`, `tests/contract/test_p2_05_distribution.py`, `tests/contract/test_env_example_drift.py`, and `apps/api/tests/test_p0_00_services.py`. `make verify-p2-05-release-stack` and `make verify-p1-00-monitoring-remote-node-write` remain the environment-dependent LAN and node-write smokes and are not part of the default lightweight `make verify`.

## Scope discipline

Each change follows design -> schema/contracts -> backend -> Runner/Web -> generated artifacts -> tests -> factual documentation. Repository scaffolding must not introduce routes, services, dependencies, tables, or configuration for excluded future capability.

For the accepted P1-09 Scenario Global Configuration Phase A, factual verification is kept in the active Slice SDD and its focused tests: `apps/api/tests/test_p1_09_scenario_global_configuration.py`, `tests/contract/test_p1_09_scenario_global_configuration_openapi.py`, and `tests/e2e/p1_09_scenario_global_configuration.spec.ts`. The focused API/contract command and Playwright command recorded there are the verification paths for Scenario global headers, non-secret local variables, effective-variable validation, public artifact boundaries, and the draft `Done` versus page `Save` workflow.

P0 is the completed baseline. P1 work may start only when the task names a real P1 Slice SDD and its accepted scope source; each Slice must include verifiable Done When criteria. P1 must not regress the P0 execution loop, P0-Stability, contract-first workflow, Workspace isolation, permission enforcement, Runner/API/Web boundaries, or verification gates. P2 remains out of scope unless separately authorized by an accepted ADR or PRD update; the active P2 Slice surfaces are listed in `docs/sdd/00-product-scope-and-priority.md` §7 and `docs/sdd/slices/P2-README.md`.

## 12. AI Coding / AGENTS.md Workflow

`AGENTS.md` is a synced operational copy of this document and must be updated whenever the active Slice or ADR authorization surface changes.

### 12.1 Required AGENTS.md files

The repository keeps a root `AGENTS.md` plus the application/package-level `AGENTS.md` files created during M0.

### 12.2 Root AGENTS.md minimum content

During P1/P2, `AGENTS.md` must list the current real P1/P2 Slice SDD. Accepted capabilities can only be implemented through the respective real Slice SDD and must not be directly authorized by placeholder or index content. Monitoring can only be implemented through `docs/sdd/slices/P1-00-monitoring.md`; Resource Multi-node only through `docs/sdd/slices/P1-01-resource-multi-node.md` and `docs/sdd/adr/ADR-0009-p1-resource-multi-node.md`; Scenario/Test Plan Polish only through `docs/sdd/slices/P1-04-scenario-testplan-polish.md` as amended by `docs/sdd/adr/ADR-0023-remove-scenario-execution-preview.md`; cURL Import only through `docs/sdd/slices/P1-05-curl-import.md`; Dependency File Preview only through `docs/sdd/slices/P1-06-dependency-preview.md`; Debug HTTP Trace only through `docs/sdd/slices/P1-08-debug-http-trace.md`; P1-09 Scenario Global Configuration only through `docs/sdd/adr/ADR-0015-p1-scenario-global-configuration.md` and `docs/sdd/slices/P1-09-scenario-global-configuration.md`, limited to Phase A structured Scenario Global Configuration Tabs for Settings, Headers, Variables, and Data Sources.

P2-00 API Catalog Scalar can only be implemented through `docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md` and `docs/sdd/slices/P2-00-api-catalog-scalar.md`. P2-01 OpenAPI Step Generation can only be implemented through `docs/sdd/adr/ADR-0011-p2-openapi-step-generation.md` and `docs/sdd/slices/P2-01-openapi-step-generation.md`. P2-02 Public API Substrate can only be implemented through `docs/sdd/adr/ADR-0012-p2-public-api-substrate.md` and `docs/sdd/slices/P2-02-public-api-substrate.md`. P2-03 Env Group Secret can only be implemented through `docs/sdd/adr/ADR-0014-p2-env-group-secret.md` and `docs/sdd/slices/P2-03-env-group-secret.md`; it authorizes only Env Group typed variables, session masked reads, session-only secret writes, plain-only public DTOs, the required one-time migration, and public API secret exclusion, and does not authorize Snapshot encryption, key rotation, a reveal API, external Secret Manager integration, or a generic redaction framework. P2-04 Help AI Agents and System OpenAPI Bootstrap can only be implemented through `docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md` and `docs/sdd/slices/P2-04-help-ai-agents-system-openapi-bootstrap.md`; it authorizes only authenticated Help, the session request-built skill source download, shared runtime/script OpenAPI export, and first-Admin best-effort system curated OpenAPI import. P2-05 Cross-platform Distribution can only be implemented through `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md`, its source-preview amendment `docs/sdd/adr/ADR-0019-p2-source-preview-startup.md`, its user-local platform Release installer amendment `docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md`, and `docs/sdd/slices/P2-05-cross-platform-distribution.md`; ADR-0017 authorizes the complete GHCR/GitHub Release distribution, Linux Runtime assets, distinct source/release Compose paths, Monitoring, and one optional Compose-internal Demo Load Node, ADR-0019 adds only the source control-plane preview and Runtime build observability, and ADR-0024 adds only the version-pinned user-local installer, bundle checksum, launcher, and installer smoke. P2-06 LAN-first Release Bootstrap can only be implemented through `docs/sdd/adr/ADR-0018-p2-lan-first-release-bootstrap.md`, its new-release Runtime default amendment `docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md`, its release `up` configuration confirmation amendment `docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md`, its separate user-local installation amendment `docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md`, and `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`; ADR-0020 changes only a missing-`.env` tagged-release default to `amd64,arm64` without an architecture prompt, ADR-0021 adds bounded pre-Runtime configuration display, read-only default-Yes confirmation, and explicit interactive four-field standard-LAN updates, and ADR-0024 keeps installation separate from the unchanged interactive `up` contract. Non-interactive rewriting, advanced-HTTPS quick editing, non-network changes, source-startup changes, network discovery, a Web/API configuration surface, package-manager/system installers, and public workflow dispatch remain forbidden. No other P2 capability is activated.
