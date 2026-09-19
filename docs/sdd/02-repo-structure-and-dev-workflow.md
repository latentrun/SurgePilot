# 02 Repo Structure and Dev Workflow

- Document status: Draft
- Project: SurgePilot performance load testing platform
- Document location: `docs/sdd/02-repo-structure-and-dev-workflow.md`
- Product source: `docs/prd/PRD.md`
- Range constraint: `docs/sdd/00-product-scope-and-priority.md`
- Architecture source: `docs/sdd/01-architecture-overview.md`
- Current delivery target: P2-02 Public API Substrate and governed Public API AI skill source package implementation + P2-03 Env Group Secret implementation + P2-04 Help AI Agents and System OpenAPI Bootstrap + P2-05 Cross-platform Distribution, Full-stack Release Bootstrap, ADR-0019 Source Preview Startup, and ADR-0024 User-local Release Installer + P2-06 LAN-first Release Bootstrap Usability, ADR-0020 Release Dual-Architecture Runtime Default, ADR-0021 Release `up` Configuration Confirmation, and ADR-0024 User-local Release Installer + P2-07 Public Launch, GitHub Pages, and SEO + ADR-0013 static Marketing Landing and Logo + P1-09 Scenario Global Configuration SDD authorization + localized Public User Documentation MVP
- Scope of application: M0 repository skeleton, Foundation SDD, Slice SDD, AGENTS.md, AI Coding, code review, test acceptance

---

## 1. Purpose

This document defines the repository structure, development environment, root command, contract generation, test verification, AI Coding, and PR Review workflow of the SurgePilot P0 stage.

This article serves two goals:

1. Allow the M0 repository skeleton to be stably created by R&D or AI;
2. Allow subsequent P0 Slice development to iterate according to unified rules instead of reinventing directories, commands, contracts and verification methods for each slice.

This article is not a product requirements document, nor is it a module-level detailed design. It does not expand the full database table, full API fields, full Runner state machine, MinIO object key verification details, page interaction details, or full test matrix. These should be placed into subsequent Foundation SDD or Slice SDD respectively.

This article follows the following principles:

1. **Consistent with PRD**: The product wording is based on `docs/prd/PRD.md`.
2. **P0 baseline + scoped P1**: The repository skeleton and workflow should be stabilized first. P0 default Workspace, manual creation, Manual single node execution, Run Report closed loop; P1 can only be realized item by item through accepted ADR and real Slice SDD.
3. **Prioritize the use of mature open source frameworks and libraries**: Don't reinvent the wheel.
4. **No over-design**: No introduction of Kubernetes, Redis, Celery, microservice splitting, complex permission systems or additional platform engineering.
5. **AI is easy to understand and comply with**: Directories, commands, generated products, prohibitions and Done When must be clear.
6. **All completions must be verifiable**: Prefer using `make verify`, M0 allows temporary bootstrap subset early, but must converge to unified verification entry.
7. **Code and code examples must be in English**: The platform development language is unified to English, and Chinese is prohibited in the code; code examples in the document (including paths, variable names, function names, and comments) must also be in English.

---

## 2. Inputs and Authority

### 2.1 Canonical Inputs

This article relies on the following documents:

1. `docs/prd/PRD.md`: Single product source for product scope, terminology, P0/P1/P2 priorities and acceptance criteria.
2. `docs/sdd/00-product-scope-and-priority.md`: P0 Scope Gate, defines what P0 must do, what is prohibited, and how to judge crossing the boundary.
3. `docs/sdd/01-architecture-overview.md`: P0 technology stack, architectural boundaries, component responsibilities, deployment model, contracts and verification entry.
4. `docs/prd/SurgePilotSDDPlanningGuide.md` or equivalent planning guide: SDD Pack, M0, Slice SDD, AGENTS.md and AI Coding advancement methods.

### 2.2 Conflict Resolution

Conflict handling rules:

1. If this article conflicts with `docs/prd/PRD.md`, the PRD shall prevail.
2. If this article conflicts with `docs/sdd/00-product-scope-and-priority.md`, 00 shall prevail unless 00 conflicts with PRD.
3. If this article conflicts with `docs/sdd/01-architecture-overview.md`, the architectural boundary of 01 shall prevail, and this article shall be revised simultaneously.
4. If the subsequent code implementation is inconsistent with this article, the code cannot be used by default; it must be explicitly fed back in the corresponding Slice SDD, ADR, or this article.
5. Any SDD, Issue, PR, or AI output cannot implement P1/P2 in advance on the grounds of "hidden entrance", "configuration switch turned off", or "backend did it first".
6. `SurgePilotSDDPlanningGuide.md` is for guidance only and does not back-cover PRD, 00, 01 or this article. If planning guidance is inconsistent with the Foundation SDD, convergence should be achieved through ADR or corresponding SDD revisions rather than having implementations bypass locked Foundation rules.

### 2.3 Document Responsibility

This article only answers:

1. What should the repository look like;
2. What each directory is responsible for;
3. How to start local development;
4. How to name the root command;
5. How to generate and verify contracts;
6. How to organize migration, testing, Docker Compose, AGENTS, and PR Review;
7. What are the completion standards for the M0 repository skeleton.

This article does not answer:

1. Complete domain model;
2. Complete API routing and error codes;
3. Complete Runner Protocol;
4. Complete Run state machine;
5. Complete permission matrix;
6. Complete MinIO object key and artifacts metadata rules;
7. Complete front-end page specifications;
8. Complete testing strategy.

These contents are entered respectively:

- `03-domain-model-overview.md`: Domain model overview;
- `04-api-contract-guidelines.md`: API contract, error code, paging, Workspace context;
- `05-runner-protocol-and-run-state-machine.md`: Runner Protocol, Run state machine, Stop, heartbeat, self-healing, node lease;
- `06-security-permission-workspace.md`: permissions, accounts, Workspace, security;
- `07-storage-artifacts-minio.md`: MinIO, Dependency File, artifacts, path security;
- `08-frontend-routing-and-ui-rules.md`: Front-end routing, layout and UI rules;
- `09-testing-and-acceptance-strategy.md` : Test matrix, CI and acceptance strategy.

After 02 is completed, M0 will first complete `04-api-contract-guidelines.md` and `05-runner-protocol-and-run-state-machine.md` before starting, because contracts, Runner Protocol and Run state machine are the boundaries that are most likely to diverge in subsequent AI development.


---

## 3. Repository Layout

### 3.1 Top-level Layout

P0 uses a monorepo.

The standard repository structure is as follows:

```text
.
├── apps/
│   ├── web/
│   ├── api/
│   └── runner/
│
├── packages/
│   └── contracts/
│
├── tests/
│   ├── contract/
│   └── e2e/
│
├── infra/
│   └── docker/
│
├── docs/
│   ├── prd/
│   └── sdd/
│
├── scripts/
│   └── export_openapi.py
├── AGENTS.md
├── Makefile
├── README.md
├── package.json
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── pyproject.toml
├── uv.lock
├── .nvmrc
├── .python-version
├── .env.example
└── .gitignore
```

Rules:

1. P0 must use monorepo and not be split into multiple repositorys.
2. `apps/web`, `apps/api`, `apps/runner` are three independent application boundaries.
3. `packages/contracts` is the only shared directory for cross-end contracts.
4. `tests/contract` and `tests/e2e` are used for cross-application testing but not business implementation.
5. `infra/docker` puts P0 Docker Compose, Nginx, MinIO initialization script and other deployment related files.
6. `scripts` puts repository-level scripts, such as OpenAPI export, build check, bootstrap check.
7. The root directory only retains cross-project configurations and unified entries to avoid stacking internal application implementation files.

### 3.2 apps/web

`apps/web` is a React + Vite + TypeScript front-end application.

Recommended structure:

```text
apps/web/
├── src/
│   ├── app/
│   ├── routes/
│   ├── pages/
│   ├── features/
│   ├── components/
│   ├── api/
│   ├── hooks/
│   ├── utils/
│   └── main.tsx
├── public/
├── tests/ # Cross-component/integration testing; component unit tests are preferably in the same directory as the component
├── package.json
├── tsconfig.json
├── vite.config.ts
├── eslint.config.js
├── prettier.config.js
└── AGENTS.md
```

Responsibilities:

1. Page rendering, routing, form interaction and user feedback;
2. Only call the API through generated web client;
3. Display Run Report, list, empty status, error status, Loading and prevent duplicate submission;
4. Send necessary request headers such as `x-workspace-id` and `x-csrf-token`;
5. Use Tailwind CSS, source-owned UI primitives, TanStack Query, React Router and other convention stacks; see `08-frontend-routing-and-ui-rules.md` for UI stack rules.

Prohibited:

1. No direct access to PostgreSQL;
2. No direct access to MinIO;
3. No SSH Load Node;
4. Do not write API response/request types by hand;
5. Do not bypass API permissions;
6. Do not create P1/P2 user-visible portals.

### 3.3 apps/api

`apps/api` is the FastAPI backend application and also contains the `api-worker` entry. `app/worker.py` must provide a module entry callable through `python -m app.worker` and provide `main()` in the implementation to avoid making the worker another FastAPI app or hidden within the API web process.

Recommended structure:

```text
apps/api/
├── app/
│   ├── main.py
│   ├── worker.py
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── routes/
│   ├── services/
│   ├── jobs/
│   ├── integrations/
│   └── utils/
├── migrations/
│   ├── env.py
│   └── versions/
├── tests/
├── pyproject.toml
└── AGENTS.md
```

Responsibilities:

1. Authentication, authorization, Workspace verification;
2. Business CRUD;
3. Run creation, Run Snapshot, node lease, Load Node Busy/Release;
4. Runner callback reception and idempotent processing;
5. Artifact metadata management and MinIO transfer;
6. Unified error response;
7. OpenAPI export;
8. Background self-healing and lightweight asynchronous compensation tasks required by `api-worker`.

Prohibited:

1. Does not rely on the Web;
2. Do not put business status on the Web, Runner or Load Node;
3. Does not implement P1/P2 user visibility capabilities;
4. Do not introduce Redis, Celery, RabbitMQ, Kafka or external queues;
5. Do not start long-term background workers in the API web process;
6. Do not bypass contracts;
7. Do not return sensitive credentials, session cookies, CSRF tokens, runner tokens, password hashes and other values.

### 3.4 apps/runner

`apps/runner` is a standalone Python application executing on the remote Load Node.

P0 CLI skeleton includes at least `start`, `stop`, `kill` subcommands, and supports `--fake` entry for local/CI smoke; fake runner must reuse the same set of callback client and contract.

Recommended structure:

```text
apps/runner/
├── runner.py
├── surgepilot_runner/
│   ├── __init__.py
│   ├── cli.py
│   ├── core/
│   ├── callback_client/
│   ├── artifact_upload/
│   └── safety/
├── tests/
├── pyproject.toml
└── AGENTS.md
```

M0 only requires a minimal CLI skeleton:

```bash
python runner.py --help
python runner.py start --run-id <runId>
python runner.py stop --run-id <runId>
```

M0's `start` / `stop` can be protocol placeholders or fake behaviors; the complete Runner Protocol, detached process, callback, artifact processing and stop idempotence are expanded in `P0-04-run-state-machine-runner-protocol.md`. The fake runner shares the `apps/runner/surgepilot_runner/` module with the real runner, which is enabled through `python runner.py start --fake` or equivalent CLI flag. It is not placed in `apps/api` or `tests/e2e/helpers` to separately implement another set of callback logic.

Responsibilities:

1. Receive execution bundle;
2. Start Taurus/JMeter;
3. Maintain remote run directory, pid file, logs and artifacts;
4. Send accepted, running, heartbeat, artifact, finished, failed, aborted callback to the API;
5. Execute stop and stop the detached process and its child process tree.

Prohibited:

1. No access to PostgreSQL;
2. Does not hold MinIO direct credentials;
3. Do not import `apps/api` internal code;
4. Does not determine the final status of the business;
5. Do not access the Web;
6. Do not write API internal tokens to logs.

### 3.5 packages/contracts

`packages/contracts` is the only cross-end contract directory and is also a pnpm workspace member. The package name is fixed to `@surgepilot/contracts`. `apps/web/package.json` must be referenced by `"@surgepilot/contracts": "workspace:*"` to generate the client. Direct import of `packages/contracts/generated/...` using relative paths is not allowed.

Recommended structure:

```text
packages/contracts/
├── openapi/
│   ├── api.openapi.json
│   └── public-api.openapi.json
├── runner/
│   └── runner-callback.schema.json
├── generated/
│   └── web-client/
├── package.json
└── AGENTS.md
```

Responsibilities:

1. Save the OpenAPI artifacts exported by FastAPI/Pydantic: Web/business `api.openapi.json` and P2-02 programmatic public API `public-api.openapi.json`;
2. Save Runner callback schema;
3. Save the Web client/types generated from the Web/business OpenAPI artifact;
4. Serve as the only contract source for Web, API, and Runner collaboration.

Rules:

1. `packages/contracts/openapi/api.openapi.json` and `packages/contracts/openapi/public-api.openapi.json` must be generated by FastAPI/Pydantic export script, handwriting is not allowed.
2. `packages/contracts/openapi/public-api.openapi.json` is the generated OpenAPI artifact for P2-02 `/api/public/v1/*` programmatic consumers and must not generate the Web client.
3. `packages/contracts/generated/web-client/` must be generated by Web/business `api.openapi.json`, handwriting is not allowed.
4. Runner callback schema must be versioned.
5. Generated files must be reproducible.
6. `make verify` must check both OpenAPI artifacts and generated Web client for stale contracts.
7. `name` of `package.json` is fixed to `@surgepilot/contracts`.
8. Web can only use generated client through workspace dependency, and cannot import generated files across directory relative paths.

### 3.5.1 packages/ai-skills

P2-02 authorizes one repo-maintained source package:

```text
packages/ai-skills/surgepilot-public-api/
├── SKILL.md
├── references/
│   └── public-api.openapi.json
├── scripts/
│   └── surgepilot_call.py
└── tests/
```

Rules:

1. This directory is source-owned package content, not a pnpm workspace member and not a Web `public/` or static distribution directory.
2. Its only API contract source is `packages/contracts/openapi/public-api.openapi.json`; the bundled reference is a copied snapshot and must fail stale verification when it drifts.
3. The caller accepts allowlisted public `operationId` values and typed parameter groups only. It must not accept arbitrary request URLs, session/internal operation IDs or caller-supplied authentication headers.
4. Package tests are part of `make verify`; release packaging, signing, checksums, marketplace publication and installers remain forbidden unless separately governed. ADR-0016/P2-04 separately allows one session-authenticated request-built source zip and does not create a release/version/update channel.
5. The P2-04 API image may copy this source directory to `/opt/surgepilot/ai-skills/surgepilot-public-api`; it must not copy generated OpenAPI artifacts or repository `scripts/` for the system bootstrap import.

### 3.6 tests

Cross-application tests are placed in the root directory `tests`.

```text
tests/
├── contract/
│   ├── test_openapi_contract.py
│   ├── test_web_client_freshness.py
│   └── test_runner_callback_schema.py
└── e2e/
    ├── p0_00_auth_workspace.spec.ts
    ├── p0_smoke_fake_runner.spec.ts
    └── helpers/
```

Rules:

1. The internal unit tests of the application are placed inside the corresponding app; the web component unit tests are preferably co-located in the same directory as the component, and `apps/web/tests` is only placed in cross-component or integration tests;
2. The contract test is placed in `tests/contract`;
3. Web/API/fake-runner smoke or E2E is placed in `tests/e2e`;
4. Fake runner can be used for P0 development and state machine testing, but it cannot replace the final real or near-real runner acceptance.

### 3.7 infra/docker

Recommended structure:

```text
infra/docker/
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.smoke.yml
├── nginx/
│   └── default.conf
├── minio/
│   └── init-bucket.sh
└── README.md
```

The P0 Compose service name is fixed as:

```text
web
api
api-migrate
api-worker
postgres
minio
nginx
```

Rules:

1. P0 is deployed on a single machine using Docker Compose.
2. Nginx is not forced to be enabled by default for local development.
3. Enable Nginx in local smoke/demo/full container mode and verify `/` to Web and `/api` to API.
4. P0 does not support Kubernetes.
5. P0 does not introduce Redis, Celery, RabbitMQ, Kafka or external message queues.

### 3.8 docs

Recommended structure:

```text
docs/
├── site/
│   ├── .vitepress/
│   │   └── config.mts
│   ├── package.json
│   ├── index.md
│   ├── quickstart.md
│   ├── startup-modes.md
│   ├── configuration.md
│   ├── first-run.md
│   ├── faq.md
│   ├── zh-CN/
│   │   └── six-page localized mirror
│   └── ja/
│       └── six-page localized mirror
├── prd/
│   ├── PRD.md
│   └── SurgePilotSDDPlanningGuide.md
└── sdd/
    ├── README.md
    ├── 00-product-scope-and-priority.md
    ├── 01-architecture-overview.md
    ├── 02-repo-structure-and-dev-workflow.md
    ├── 03-domain-model-overview.md
    ├── 04-api-contract-guidelines.md
    ├── 05-runner-protocol-and-run-state-machine.md
    ├── 06-security-permission-workspace.md
    ├── 07-storage-artifacts-minio.md
    ├── 08-frontend-routing-and-ui-rules.md
    ├── 09-testing-and-acceptance-strategy.md
    ├── adr/
    │   ├── ADR-0001-monorepo.md
    │   ├── ADR-0002-runner-independent-app.md
    │   ├── ADR-0003-p0-minio-only.md
    │   ├── ADR-0004-p0-manual-single-node-only.md
    │   ├── ADR-0005-p0-no-api-catalog-no-monitoring-no-schedule.md
    │   └── ADR-0006-p0-separate-api-worker.md
    └── slices/
```

Rules:

1. PRD is placed in `docs/prd`.
2. SDD is placed in `docs/sdd`.
3. ADR is placed in `docs/sdd/adr`.
4. Slice SDD is placed in `docs/sdd/slices`.
5. SDD is a living document, but updates must serve engineering facts and cannot be taken as an opportunity to expand product scope.
6. M0 must create ADR placeholder or v1 for fixed monorepo, Runner standalone, MinIO only, Manual single-node, P0 disable API Catalog/Monitoring/Schedule, and standalone api-worker decisions.
7. The Public User Documentation MVP and P2-07 Pages site use one VitePress package under
   `docs/site`, included in `pnpm-workspace.yaml` with the exact `docs/site` entry rather than a
   broad `docs/*` glob.
8. User-documentation navigation remains limited to Home, Quickstart, Startup Modes,
   Configuration, First Run, and FAQ. English is authoritative; ADR-0025 preserves exact
   Simplified Chinese (`zh-CN`) and Japanese (`ja`) mirrors, native locale navigation, no automatic
   redirect, locale-relative link checks, and complete Configuration template-key coverage.
   ADR-0026/P2-07 moves those same page sets below `/docs/`, `/docs/zh-CN/`, and `/docs/ja/` in the
   unified public site. `docs/sdd` and `docs/prd` remain outside user-documentation navigation.
9. ADR-0026/P2-07 authorizes private preparation of the static marketing/docs artifact, the exact
   `https://latentrun.github.io/SurgePilot/` origin and `/SurgePilot/` project base, publication
   metadata, online links, public-readiness checks, and a separately gated Pages workflow. Private
   CI remains build-only until public-launch acceptance passes; deployment permissions and public
   activation must not run early. A custom domain, automatic translation/language redirect,
   multi-version docs, blog/CMS, and unrelated external-link tooling remain inactive.

---

## 4. Toolchain Decisions

### 4.1 JavaScript / TypeScript

| Item | Decision |
| --- | --- |
| Package manager | pnpm |
| Node version | Node.js 22 LTS, `.nvmrc` content is fixed to `22` |
| Frontend framework | React + Vite + TypeScript |
| UI stack | Tailwind CSS + CSS variables + source-owned minimal primitives; see `08-frontend-routing-and-ui-rules.md` |
| Data fetching | TanStack Query |
| Routing | React Router |
| API client | OpenAPI generated client, recommended `openapi-typescript` + `openapi-fetch` |
| Lint / format | ESLint + Prettier |
| Typecheck | `tsc --noEmit` |

Rules:

1. The root directory must have `pnpm-workspace.yaml` and at least contain `apps/*` and `packages/*`.
2. The root directory `package.json` only contains workspace scripts and cross-package dev tools.
3. `apps/web/package.json` puts web application dependencies.
4. `packages/contracts/package.json` puts contract generation related dependencies.
5. Do not use npm/yarn to mix dependencies.
6. Do not commit `node_modules`.

`pnpm-workspace.yaml` contains at least:

```yaml
packages:
  - apps/*
  - packages/*
```

### 4.2 Python

| Item | Decision |
| --- | --- |
| Python version | Python 3.12 |
| Dependency manager | uv |
| API framework | FastAPI |
| Schemas | Pydantic |
| Migrations | Alembic |
| Database driver / ORM | To be confirmed by subsequent SDD or Slice, mature and stable solutions can be used first |
| Lint / format | Ruff |
| Type check | Mypy can be gradually enabled according to Slice risks; code involving Run state machine, node lease, and callback idempotence must have explicit type checking or alternative verification strategies in the corresponding Slice |
| Tests | pytest |

Rules:

1. The root directory must have `.python-version` and the content is `3.12` or specifically `3.12.x`.
2. Use `uv.lock` to lock Python dependencies.
3. Python workspace convention must be unique: root `pyproject.toml` declares `[tool.uv.workspace] members = ["apps/api", "apps/runner"]`; `apps/api/pyproject.toml` and `apps/runner/pyproject.toml` as workspace members; the repository has only one root `uv.lock`.
4. It is not allowed to create a second set of Python dependency lock files in addition to `apps/api` and `apps/runner`.
5. Do not submit the virtual environment directory.
6. Do not import API internal modules in Runner; if you need to share schema, pass `packages/contracts` or explicitly generate the product.

Root `pyproject.toml` contains at least:

```toml
[tool.uv.workspace]
members = ["apps/api", "apps/runner"]
```

### 4.3 Docker and Compose

| Item | Decision |
| --- | --- |
| Local infra | Docker Compose |
| P0 deployment | Docker Compose |
| Gateway | Nginx |
| Database | PostgreSQL |
| Object storage | MinIO |

Rules:

1. P0 Compose does not include Grafana / InfluxDB.
2. P0 Compose does not include Redis / Celery / external queue.
3. P0 Compose does not contain Kubernetes related configuration.
4. The default name of MinIO bucket is `surgepilot`.
5. Local development and smoke operation must reuse the same set of environment variable names.
6. Docker image build package sources are opt-in build args only: API images accept `PIP_INDEX_URL` / `UV_INDEX_URL` from `SURGEPILOT_PIP_INDEX_URL`, Web images accept `NPM_REGISTRY` from `SURGEPILOT_NPM_REGISTRY`, and SSH Load Node images accept apt `APT_MIRROR` / `APT_SECURITY_MIRROR` from `SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_*` and `SURGEPILOT_DOCKER_BUILD_DEBIAN_APT_*`. Defaults must remain upstream PyPI/npm/apt. These variables are build-time mirror controls, not runtime System Settings.

---

## 5. Local Development Modes

P0 supports two local development modes.

### 5.1 Mode A: Dependencies in Docker, Apps on Host

This is the default development mode.

How to run:

```bash
make setup
make infra-up
make migrate
make dev-api
make dev-worker
make dev-web
```

Features:

1. PostgreSQL and MinIO use Docker Compose;
2. API, api-worker, and Web run on the local machine;
3. Nginx is not forced to be enabled locally;
4. Web access API through Vite proxy or configured API base URL;
5. Suitable for daily development, debugging and AI Coding.

Requirements:

1. Configure native API, DB, MinIO, runner token, and other process-level values in `.env`;
2. `make infra-up` must be executed repeatedly;
3. `make infra-down` should not delete data volumes by default;
4. If you need to clean the data, you must use an explicit command, such as `make infra-clean`.

### 5.2 Mode B: Source Checkout Full Container Startup

This is the source-checkout default for development demos, manual acceptance, and AI startup services.

How to run:

```bash
make start-full-stack
```

Compatible aliases:

```bash
make dev-compose
```

Raw `docker compose` is an expert/manual troubleshooting path, not a compatible alias. It bypasses the official first-run bootstrap and Runtime release/preflight orchestration and therefore does not carry the `make start-full-stack` readiness or secret-persistence promise.

Features:

1. Web, api, api-worker, postgres, minio, nginx, and the Demo Load Node are containerized;
2. P1 Monitoring is enabled by default, including InfluxDB, Grafana and `/grafana/*` same-origin Nginx routes;
3. Enable Nginx and verify `/`, `/api` and `/grafana` routes;
4. Suitable for source-checkout demos, manual acceptance, contributor startup and verification close to deployment environment.

Requirements:

1. The Compose service name must be stable;
2. Nginx is only responsible for routing and does not carry business logic;
3. API/api-worker uses the same code base and image;
4. `docker-compose.yml` is a standard full stack and must explicitly include the Grafana/InfluxDB services and environment variables required by P1 Monitoring;
5. Lightweight smoke, CI-style verifier and SSH E2E profile can continue to use base compose, but they must not be used as the default entry for users to generalize "start services".
6. The complete default topology uses Compose-internal API and InfluxDB origins for the Demo Load Node. Any external Load Node requires explicit final `SURGEPILOT_NODE_API_BASE_URL` and `SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL` values, independent of the Demo enable switch. Official source startup does not perform host-interface discovery.

### 5.2.1 Source Checkout Control-plane Preview

For an explicit login-page, UI, or control-plane review that does not require Load Node execution
readiness, use:

```bash
make start-preview
```

This entry performs the same secure root `.env` bootstrap, validates explicit external URL pairs,
and starts the source Web, API, api-worker, PostgreSQL, MinIO, Nginx, InfluxDB, and Grafana topology.
It does not activate the Demo profile or build/reuse a Load Node Runtime. Preview overrides are
process-local and never rewrite `.env`; Setup Status may report `not_configured`. A dedicated empty
host-created Runtime mount prevents Docker from creating or changing ownership of the normal
Runtime output directory. Use `make stop-preview` to stop the preview topology without deleting
volumes, and use `make start-full-stack` when complete Runtime and Demo readiness are required.

This is a source engineering entry authorized by ADR-0019, not a second tagged-release product
mode. It does not change P2-06 release bootstrap, API, OpenAPI, Workspace, permission, database,
Web, Runner, or Run-state contracts.

### 5.3 P2-05 Tagged Release Startup

P2-05 adds one complete user-facing release mode without replacing the source-checkout development entry:

```bash
curl -fsSL https://github.com/latentrun/SurgePilot/releases/latest/download/install.sh | sh
surgepilot up
surgepilot down
surgepilot status
surgepilot logs
```

Manually extracted bundles retain the same lifecycle commands with the `./surgepilot` spelling.

Rules:

1. The tagged release bundle uses release Compose and immutable multi-architecture image digests recorded in `release-manifest.json`.
2. Release Compose contains no application build contexts and never falls back to a source build.
3. `./surgepilot up` requires Docker/Compose only, includes P1 Monitoring and one real Compose-internal Demo Load Node by default, and fetches the matching GitHub Release Runtime asset.
4. Source `make start-full-stack` continues to build current source images and a local development Runtime; it does not consume release-manifest image pins.
5. Default `SURGEPILOT_RUNTIME_ARCHITECTURES=auto` follows the Docker daemon architecture for the Demo node. Explicit architecture sets are advanced deployment inputs for external Load Nodes.
6. Any external Load Node requires explicit final API and InfluxDB URLs. Neither source nor release startup infers external connectivity from host interfaces or the Demo switch after P2-05 implementation.
7. Repository source-checkout startup requests use `make start-full-stack`; installed tagged
   bundles use the user-local `surgepilot` launcher, while manually extracted bundles use the
   bundled `./surgepilot` wrapper.
8. ADR-0024 adds one version-pinned POSIX installer and bundle SHA-256 sidecar. It publishes below
   `${XDG_DATA_HOME:-$HOME/.local/share}/surgepilot`, creates `$HOME/.local/bin/surgepilot`, never
   invokes `sudo` or changes shell configuration, and never calls `up` inside the pipeline.

### 5.4 P2-06 LAN-first Tagged Release Amendments

ADR-0018/P2-06 changes only the tagged release startup contract, ADR-0020 partially supersedes only
its new-release Runtime default and architecture prompt, ADR-0021 partially supersedes only
conflicting existing-`.env` not-prompted/never-rewritten wording, and ADR-0024 adds only a separate
version-pinned installation entry before the unchanged `up` contract:

1. a missing release `.env` requires an interactive host shell to confirm the host, HTTP port, and
   InfluxDB node-write port before services start; explicit canonical loopback is allowed only as a
   warned local-evaluation choice for persisted node-facing URLs and does not change the
   all-interface published-port bind;
2. non-TTY automation must pre-provision a complete owner-only `.env`;
3. release Demo defaults to disabled, and new tagged-release deployments default to `amd64,arm64`
   without asking for Runtime architectures;
4. release node-facing API/InfluxDB values are required and have no Compose-internal fallback;
5. release base Compose publishes the configured Nginx and authenticated InfluxDB ports on host
   interfaces; operators who require local-only exposure must enforce it with the host firewall;
6. source `make start-full-stack` and source Compose-internal Demo defaults remain unchanged;
7. existing release workflows update their smoke `.env` fixtures and may expose the same validation
   bundle tar separately, but gain no public publication capability, permissions, triggers, or jobs.
8. every valid release `up` prints the bounded non-secret effective configuration before Runtime
   fetch; interactive startup asks `Use this configuration? [Y/n]`, with Yes/default read-only and
   No opening first-run re-entry or a standard-LAN four-field proposal loop;
9. existing `.env` changes require interactive No, valid host/port entry, normalized review, and
   Yes; only the four allowlisted network fields change through candidate validation, a final
   pre-replacement SHA-256 check, and standard `os.replace`; simultaneous manual same-user editing
   in the final syscall window is unsupported, with no backup or automatic rollback;
10. non-interactive startup prints the summary but never prompts or rewrites, advanced HTTPS No
    requires manual `.env` editing, and source startup is excluded.

Automatic and non-interactive rewriting remains forbidden. Runtime, Demo, cookie, credential,
secret, and all other non-network values remain authoritative; `auto`, `amd64`, `arm64`, and
`amd64,arm64` remain accepted advanced Runtime values. Explicitly persisted `auto` selects the
Docker daemon architecture even without Demo. Both selected prebuilt Runtime sets validate before
release Compose startup. Source `make start-full-stack` remains native-only and root `.env.example`
remains `auto`. ADR-0020 and ADR-0021 change none of ADR-0018's other LAN host, Demo, cookie,
InfluxDB, published-port, non-interactive smoke, or capability boundaries.

### 5.5 P2-07 Public Launch and GitHub Pages

ADR-0026/P2-07 adds one public repository and Pages delivery surface without changing product or
release execution:

```text
https://latentrun.github.io/SurgePilot/             marketing homepage
https://latentrun.github.io/SurgePilot/docs/        English user guide
https://latentrun.github.io/SurgePilot/docs/zh-CN/  Simplified Chinese mirror
https://latentrun.github.io/SurgePilot/docs/ja/     Japanese mirror
```

Rules:

1. `docs/site` is the only Pages package and emits meaningful static HTML through one VitePress
   build; it must not mount the React product application.
2. The Pages homepage is a separate Star-oriented marketing implementation based on the approved
   product Landing visual direction. It contains no product Log in, Sign up, hosted SaaS, or
   pricing action.
3. The existing product Marketing Landing keeps its self-hosted authentication role, while every
   self-hosted Web route defaults to crawler-observable `noindex` before client routing.
4. English remains authoritative; the exact six-page `zh-CN` and `ja` mirrors, explicit locale
   selection, relative-link checks, and Configuration drift checks remain mandatory below
   `/docs/`.
5. Every indexable route has unique metadata, self-canonical URL, social metadata, reciprocal
   locale alternates plus `x-default`, and supportable structured data. One canonical-only sitemap
   and Pages-compatible robots file belong to the build.
6. The original AI-authored baseline claim must state the human/AI role boundary and bind the
   strong claim to one audited semantic tag. Future community work may be human- or AI-authored.
7. Private CI may build and inspect the exact future artifact but cannot deploy Pages. Public
   activation waits for history/privacy/license review, organization migration, full verification,
   anonymous tagged Release readiness, and exact Pages smoke.
8. The coordinated public launch consumes existing P2-05/P2-06 Release artifacts without changing
   Runtime, installer, Compose, startup, or publication integrity contracts.
9. The original animated dashboard/VU counters, Recent Test Runs, and Distributed load mesh remain
   only as adjacent, explicitly labelled UI demonstration/example data that is not a live service,
   live topology, benchmark, or evidence source. The desktop-first Landing keeps full signature motion without a
   Landing-scoped reduced-motion override.
10. Purchased/fake Stars, fabricated benchmark/adoption/status/Star claims, hosted-service claims, blog/CMS,
   programmatic SEO, custom-domain launch, and automatic translation remain forbidden.

---

## 6. Environment and Secrets

### 6.1 Files

The repository must provide:

```text
.env.example
.env.e2e.example
```

Repositorys may not submit:

```text
.env
.env.local
*.secret
```

Configuration has four sources of truth:

| Source | File / entry | Ownership |
| --- | --- | --- |
| Deployment environment | Root `.env`, created from `.env.example` by official first-run startup or copied explicitly by an operator | Bootstrap secrets, deployment topology, Compose overrides, commented build mirrors, and commented advanced guardrails. Root `.env` is the only ordinary deployment env file. |
| Generated runtime environment | `.surgepilot/runtime-artifacts/.../runtime.env` | The containerized Runtime builder or release fetch helper writes runtime version and host artifact directory values. Official startup injects the version into Compose. |
| DB-backed System Settings | Database plus Admin UI | Non-sensitive business policy settings. Process env is fallback/default only when no DB value exists. |
| Test / E2E overrides | `.env.e2e.example` | Real-IP, SSH fixture, Monitoring node-write, retention, and SSH-image build-only overrides. It is not loaded by ordinary startup. |

Rules:

1. Ordinary deployment must use one root `.env`; do not split bootstrap, build, runtime, or advanced settings across multiple `.env.*.example` files.
2. `.env.example` groups values by edit frequency: quickstart requirements first, then deployment services, Monitoring, optional build controls, and advanced guardrails.
3. `.env.example` must not contain real secrets. Bootstrap secret examples must include generation and stability guidance where losing or rotating a value would invalidate stored data.
4. DB-backed System Settings must not be active quickstart assignments. They may appear only as commented fallback/default reference because DB values override them.
5. Generated runtime variables must not be normal hand-edited assignments. Manual Compose users may set them explicitly, but source checkouts use `make start-full-stack` / `make restart-full-stack` and tagged P2-05 bundles use `./surgepilot up`.
6. `.env.e2e.example` contains only test facts and overrides. It must not become a second deployment source.
7. `.env` is local/deployment state and is not committed. Deployment platforms may inject bootstrap secrets through their native secret facilities instead of a plaintext file.
8. Docker Compose reads root `.env` through standard interpolation. Official Make startup/release and host development targets load the same file through `python-dotenv` with existing process environment values taking precedence; users do not need to export each value manually.
9. Automated verification paths inject explicit test-only Runner and MinIO values so a developer's deployment `.env` cannot change verifier credentials or break Compose/Python agreement.
10. Compose secret ownership follows least privilege: API and api-worker receive the Runner token and MinIO client credentials they use, while migration containers receive only migration-required configuration. Verification must exercise non-default MinIO credentials across API, worker, browser, and SSH flows.
11. When root `.env` is absent, official source and release startup create it from `.env.example`, persist explicitly inherited bootstrap identity/credential values, replace placeholders with cryptographically random values, and create private Monitoring token, Demo password, and Demo Ed25519 host-key state under `.surgepilot/`. Conflicting MinIO pairs fail before `.env` publication.
12. First-run bootstrap is concurrency-safe, idempotent, and fail-closed. Existing `.env`, secret files, and complete Demo SSH identities are never overwritten or rotated automatically; partial or unsafe state fails rather than being repaired. Two deployment roots receive distinct Demo credentials and fingerprints, while one retained root preserves them across container recreation.
13. Generated bootstrap secret values must not be printed to stdout/stderr, logs, tests, or command summaries.

### 6.2 Required Environment Variables

The exact deployment inventory and examples live in `.env.example`; this SDD defines ownership rather than duplicating a second value list.

1. Direct host development may use `APP_ENV`, `DATABASE_URL`, and `MINIO_ENDPOINT`. Compose may hardcode equivalent container-internal topology when it is not a user-managed deployment choice.
2. Compose host ports, MinIO bootstrap credentials/bucket, `DEFAULT_WORKSPACE_NAME`, and P1 Monitoring bootstrap values remain deployment environment concerns.
3. `RUNNER_INTERNAL_TOKEN`, `SSH_CREDENTIAL_ENCRYPTION_KEY`, MinIO secrets, and Monitoring secret-file sources are deployment secrets. Compose services that share `RUNNER_INTERNAL_TOKEN` must consume the same required root env value; a hardcoded second token source is forbidden.
4. `LOAD_NODE_RUNTIME_VERSION` and `LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR` are generated by the runtime release path for official startup. Container paths such as `LOAD_NODE_RUNTIME_ARTIFACT_DIR` and `SURGEPILOT_RUNNER_BUNDLE_DIR` are fixed topology and remain hardcoded by design.
5. `SURGEPILOT_NODE_API_BASE_URL` is only the bootstrap fallback for DB-backed `loadNodeApiBaseUrl`. `APP_BASE_URL` is not a Runner callback or remote-node origin fallback.
6. `SURGEPILOT_SINGLE_NODE_CONCURRENCY_HARD_LIMIT`, artifact/trace size ceilings, run-control timings, and Load Node operational timeouts are deployment safety or operational guardrails and do not enter System Settings.
7. P1 Monitoring remains deployment-level. The host token-file source and container secret mount path do not enter DB/UI and token plaintext must not be returned or logged.
8. `RUNNER_HOME`, `SURGEPILOT_RUNNER_ARCHIVE_MAX_BYTES`, and `SURGEPILOT_RUNNER_HEARTBEAT_INTERVAL_SECONDS` are node-local Runner settings rather than ordinary platform deployment settings.
9. Secret values must not be written to logs, API responses, front-end bundles, generated contracts, or test snapshots.
10. Source and release full-stack startup use Compose-internal Demo origins by default and require explicit final API/InfluxDB URLs for every external Load Node. Do not add `SURGEPILOT_HOST_IP`, `SURGEPILOT_HOST_IP`, or another public host-only intermediate variable.

### 6.3 Runtime Configuration

1. `VITE_API_BASE_URL` is build-time only. Runtime Web containers use same-origin `/api` and must not receive `VITE_API_BASE_URL` as a runtime environment variable.
2. DB-backed System Settings are limited to the accepted settings registry and active Slice contracts. Current examples include Access, remote Load Node connectivity, load/JMeter policy, and Dependency File policy; deployment secrets, build controls, topology, Monitoring, and hard safety ceilings do not enter the registry.
3. Full/base Compose forwards documented DB fallback variables into the API process while DB rows remain authoritative at runtime. Active deployment values such as `DEFAULT_WORKSPACE_NAME` must likewise be interpolated instead of duplicated as hardcoded second sources.
4. Build mirrors, `VITE_API_BASE_URL`, and SSH E2E image build proxies are build-time controls with upstream or same-origin defaults. They remain commented optional examples, are wired only as image build arguments where applicable, and are not runtime System Settings.
5. Runtime artifact release pins and preflight opt-outs are deployment/release controls. They remain commented advanced options and do not create runtime catalog, rollback, or management UI capabilities.
6. If a future browser runtime configuration is required, it must be introduced through an accepted Slice contract; do not infer a generic configuration platform from this ownership model.

---

## 7. Root Make Commands

The root directory `Makefile` is the unified development entrance.

### 7.1 Required Commands

The repository root `Makefile` must define the following commands; both the early bootstrap subset and subsequent P1/P2 entries are exposed through the same help surface to avoid humans and AI choosing unofficial entries.

```bash
make help
make setup
make dev
make dev-web
make dev-api
make dev-worker
make dev-runner
make release-runtime
make start-preview
make stop-preview
make start-full-stack
make restart-full-stack
make stop-full-stack
make start-full-ssh-e2e
make start-full-ssh-e2e-build
make restart-full-ssh-e2e
make restart-full-ssh-e2e-build
make stop-full-ssh-e2e
make dev-compose
make infra-up
make infra-down
make migrate
make migration
make generate-contracts
make contracts-stale-check
make lint
make test
make verify
make verify-e2e
```

### 7.2 Command Semantics

| Command | Meaning |
| --- | --- |
| `make help` | Output all root commands and one sentence description for newcomers and AI to quickly find the entrance |
| `make setup` | Install pnpm/uv dependencies and prepare local development environment |
| `make dev` | Start the default local development combination, which can prompt you to run web/api/worker separately |
| `make dev-web` | Start the Vite dev server, which is equivalent to running the pnpm dev command under `apps/web` |
| `make dev-api` | Start FastAPI dev server, the recommended underlying command is `cd apps/api && uv run fastapi dev app/main.py` or equivalent uv command |
| `make dev-worker` | Start api-worker, the underlying command is fixed to `cd apps/api && uv run python -m app.worker` |
| `make dev-runner` | Run runner CLI help or local fake runner entry, use `cd apps/runner && uv run python runner.py --help` or `uv run python runner.py start --fake` for the underlying command |
| `make release-runtime` | Build or reuse the repo-local Linux Load Node Runtime inside `infra/docker/runtime-builder/Dockerfile`; use the Docker daemon architecture and stable input manifest hash, then write the runtime env file for official startup |
| `make start-preview` | Source-checkout control-plane preview; securely bootstraps the normal root `.env`, validates explicit external URL pairs and source Compose, then starts Web/API/api-worker/PostgreSQL/MinIO/Nginx/InfluxDB/Grafana without Runtime preflight or the Demo profile; preview overrides are process-local and execution readiness is not promised |
| `make stop-preview` | Stop the source control-plane preview without deleting named volumes or deployment state |
| `make start-full-stack` | Source-checkout default startup entry; first creates secure local deployment configuration only when root `.env` is absent, then executes `make release-runtime`, uses the same `LOAD_NODE_RUNTIME_VERSION` and runtime artifact host dir to verify compose config, and starts the standard full stack, including web/api/api-worker/postgres/minio/nginx, P1 Monitoring, InfluxDB and Grafana; bootstrap and runtime preflight failures fail fast |
| `make restart-full-stack` | Runs the same no-overwrite deployment bootstrap, then performs runtime release/preflight before stopping the existing stack; after preflight success it restarts without deleting volumes, while any bootstrap or preflight failure retains the existing stack and fails fast |
| `make stop-full-stack` | Stop standard full stack without deleting volumes |
| `make start-full-ssh-e2e` | Multi-node manual acceptance/demo default fast path; reuse local `docker-ssh-load-node:latest`, first build or reuse the `p0-e2e` runtime artifact through production `scripts/release_runtime_artifact.py --fixed-version` with persistent output/build/cache directories, set `LOAD_NODE_RUNTIME_VERSION`, `LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR` and stable `SSH_CREDENTIAL_ENCRYPTION_KEY`, only build app/web images, and then use compose `--no-build` to start the full + SSH E2E stack |
| `make start-full-ssh-e2e-build` | Used when you need to rebuild the SSH Load Node image; this path allows network-dependent SSH image build, and then reuses `make start-full-ssh-e2e` to complete production runtime artifact reuse/build and startup |
| `make restart-full-ssh-e2e` | Stop and re-execute fast path without deleting volumes |
| `make restart-full-ssh-e2e-build` | Stop and execute build path without deleting volumes |
| `make stop-full-ssh-e2e` | Stop full + SSH E2E stack without deleting volumes |
| `make dev-compose` | Compatible alias for `make start-full-stack` |
| `make infra-up` | Start dependent services such as PostgreSQL and MinIO |
| `make infra-down` | Stop dependent services and do not delete volumes by default |
| `make migrate` | Execute Alembic upgrade head |
| `make migration` | Create migration, specific parameters are specified by the implementation |
| `make generate-contracts` | Export OpenAPI and generate Web client/types |
| `make contracts-stale-check` | Check that the OpenAPI artifact and generated Web client are consistent with the source schema |
| `make lint` | Run API/Runner/Web lint and format check |
| `make test` | Run API/Runner/Web/contract test subset |
| `make verify` | Unified final verification entrance |
| `make verify-e2e` | E2E/smoke validation entry before nightly, release or trunk merge |

### 7.3 Bootstrap Rule

M0 stage `make verify` can start with a smaller set, but must contain the following; `make help` must always be available:

1. Python dependencies can be installed;
2. pnpm dependencies can be installed;
3. API app can be imported;
4. Web can be typechecked or at least buildable;
5. Runner CLI executable `--help`;
6. Docker Compose configuration can be parsed;
7. OpenAPI export command exists;
8. The generated contracts check command exists.

Starting from P0-00, `make verify` must gradually converge to a complete verification entry. Slice SDD If a narrower command is used temporarily, it must be stated when it will converge.

### 7.4 Final P0 verify Scope

P0 eventually `make verify` covers at least:

1. Alembic migration check;
2. API lint / format check;
3. API unit tests;
4. Web lint / typecheck;
5. Web unit tests where applicable;
6. Runner unit tests;
7. OpenAPI export check;
8. Web client/types generation freshness check;
9. Runner callback contract tests;
10. API contract tests;
11. smoke or E2E tests using fake runner.

More detailed test matrices are placed in `docs/sdd/09-testing-and-acceptance-strategy.md` .

---

## 8. Contracts Workflow

### 8.1 Contract First Rule

Functions involving API, Web, and Runner must comply with:

```text
Update or define contract
  ↓
Implement API
  ↓
Generate Web client/types
  ↓
Implement Web consumer
  ↓
Implement Runner or callback consumer
  ↓
Supplementary test
  ↓
make verify
```

Rules:

1. The frontend must not guess the API shape.
2. Runner must not import API internal code.
3. API and Runner can only communicate through contracts and Runner Protocol.
4. The new error code must first be registered in `docs/sdd/04-api-contract-guidelines.md` or the corresponding error code registry.
5. The new callback field must first update the runner callback schema.

### 8.2 OpenAPI Generation

OpenAPI flow:

```text
FastAPI routes + Pydantic schemas
        ↓
export OpenAPI
        ↓
packages/contracts/openapi/api.openapi.json
packages/contracts/openapi/public-api.openapi.json
        ↓
openapi-typescript / openapi-fetch reads api.openapi.json only
        ↓
packages/contracts/generated/web-client/

public-api.openapi.json is committed for P2-02 /api/public/v1/* programmatic consumers and does not generate Web client/types.
```

The OpenAPI export script path is fixed to:

```text
scripts/export_openapi.py
```

`make generate-contracts` must be completed in the following order:

1. Call `scripts/export_openapi.py` and import the FastAPI app in `apps/api/app/main.py`;
2. Output `packages/contracts/openapi/api.openapi.json` and `packages/contracts/openapi/public-api.openapi.json`;
3. Call `pnpm --filter @surgepilot/contracts generate` or equivalent contracts package script;
4. Generate `packages/contracts/generated/web-client/` from Web/business `api.openapi.json`;
5. Ensure that the output of both OpenAPI artifacts and generated Web client is stable and repeatable.

OpenAPI export logic must not be written as inline Python in the Makefile, nor must it be dispersed into application internal directories such as `apps/api/scripts` and `apps/web/scripts`.

### 8.3 Stale Contract Check

`make verify` must check whether generated contracts are stale.

Recommended method:

```bash
make generate-contracts
git diff --exit-code packages/contracts
```

If a diff is generated after the build, it means that the developer modified the API or schema but did not submit the updated contracts, and verify must fail. This includes stale diffs in either OpenAPI artifact or in the generated Web client.

### 8.4 Generated Files Do Not Edit

The following files or directories cannot be edited by hand:

```text
packages/contracts/openapi/api.openapi.json
packages/contracts/openapi/public-api.openapi.json
packages/contracts/generated/web-client/
```

If you need to change these files, you should modify the source:

1. FastAPI route;
2. Pydantic schema;
3. contract generation script;
4. OpenAPI generation config.

### 8.5 Runner Callback Schema

Runner callback schema is located at:

```text
packages/contracts/runner/runner-callback.schema.json
```

Rules:

1. M0 can create the smallest schema footprint;
2. P0-04 must be perfected accepted, running, heartbeat, artifact, finished, failed, aborted;
3. The callback schema must have contract tests;
4. Both API and Runner must comply with the schema;
5. Runner token uses HTTP header and does not put payload.

---

## 9. Database Migration Workflow

P0 uses PostgreSQL + Alembic.

### 9.1 Migration Location

```text
apps/api/migrations/
├── env.py
└── versions/
```

### 9.2 Rules

1. Any database schema change must have Alembic migration.
2. Migration must be upgradeable from the empty library to head.
3. Migration must not rely on local temporary data.
4. When the model is modified but the migration is not committed, `make verify` should fail or at least be checked in the corresponding Slice Done When.
5. Data structures required for P1/P2 user-visible capabilities must not be created in Migration, unless explicitly allowed by 00/01 or the corresponding ADR as a non-user-visible extension point.
6. Workspace-aware business objects must contain `workspace_id` from day one, and Setup Status exceptions must not be extended to other business objects.

### 9.3 Commands

```bash
make migrate
make migration name="create users table"
```

The specific underlying commands can be determined by the implementation, but the root command semantics must be stable.

---

## 10. Testing and Verification Workflow

### 10.1 Test Levels

The P0 test layering is as follows:

| Level | Location | Purpose |
| --- | --- | --- |
| API unit/service tests | `apps/api/tests` | Backend business logic, permissions, workspace, error handling |
| Runner unit tests | `apps/runner/tests` | CLI, process, callback payload, artifact safety |
| Web tests | `*.test.ts(x)` next to components; `apps/web/tests` only across components/integration tests | Key components, forms, states, API client usage |
| Contract tests | `tests/contract` | OpenAPI, generated client, runner callback schema |
| E2E / smoke | `tests/e2e` | Web/API/fake-runner main link smoke |

### 10.2 Naming

Suggested naming:

```text
Python: test_*.py
Web: *.test.ts / *.test.tsx
E2E: p0_XX_feature.spec.ts
```

### 10.3 Slice Testing Rule

Each Slice SDD must state:

1. API testing;
2. Web testing;
3. Runner test, if involved;
4. Storage / MinIO testing, if involved;
5. Contract testing, if involved;
6. E2E or smoke, if involved;
7. Done When verification command.

You cannot just write "function completed", "page available" and "interface implemented".

### 10.4 Fake Runner Rule

The fake runner's physical location is fixed at `apps/runner` and shares the `apps/runner/surgepilot_runner/` module and Runner callback contract with the real runner. fake mode is enabled via `python runner.py start --fake` or equivalent CLI flag.

fake runner is allowed for:

1. Run List/Run Report UI local development;
2. accepted → running → heartbeat → finished process;
3. failed / aborted process;
4. heartbeat timeout;
5. artifact callback;
6. E2E smoke.

fake runner does not allow substitution:

1. Real or near-real Runner Protocol acceptance;
2. Taurus/JMeter performs acceptance;
3. SSH/SFTP remote start acceptance.

---

## 11. Docker Compose and Infra Workflow

### 11.1 Compose Services

P0 Compose services:

```text
web
api
api-worker
postgres
minio
nginx
```

Does not include:

```text
redis
celery
rabbitmq
kafka
grafana
influxdb
kubernetes
```

### 11.2 Nginx

Nginx responsibilities:

1. `/` route to Web;
2. `/api` route to API;
3. HTTPS or upstream gateway access can be extended by the deployer.

Rules:

1. The local default development mode does not force Nginx to be enabled.
2. Nginx must be enabled in full container smoke / demo mode.
3. Nginx does not carry business logic.

### 11.3 MinIO Initialization

P0 default bucket:

```text
surgepilot
```

M0 adopts double insurance by default:

1. Compose provides MinIO init-bucket sidecar or equivalent initialization script to create `surgepilot` bucket;
2. API startup / Setup Status checks whether the bucket is accessible and gives a clear error if it is not available.

Smoke Compose must also provide a one-time `api-migrate` sidecar that executes `alembic upgrade head` before the API is started with `api-worker` .

An explicit init command can be additionally provided as a troubleshooting fallback, but it cannot be used as the only initialization path.

Non-MinIO storage implementations must not be introduced in P0.

---

## 12. AI Instruction Architecture

### 12.1 Authority and files

`/AGENTS.md` is the repository authority for AI contribution behavior. PRD, Foundation/Slice SDDs,
and accepted ADRs remain authoritative for product behavior and technical design. This document
owns repository and development workflow design; it references and does not reproduce `/AGENTS.md`.

The instruction chain contains:

```text
AGENTS.md
apps/api/AGENTS.md
apps/web/AGENTS.md
apps/runner/AGENTS.md
packages/contracts/AGENTS.md
```

Root instructions contain stable repository-wide policy and invariants. A nested file declares its
filesystem scope and adds only stable domain constraints and review rules. A nested rule may
specialize or tighten root behavior for its subtree, but it cannot weaken repository-wide
invariants. Resolve an apparent conflict in the governing documents before implementation.

The accepted instruction model and lifecycle are defined by
`docs/sdd/ai-development-governance-optimization-design.md`.

### 12.2 Size and maintenance

- Root instructions remain below 20 KiB.
- Each nested instruction file normally remains below 4 KiB.
- Every root-plus-child chain remains below the Codex default 32 KiB project-instruction budget.
- Dynamic Slice/ADR activation belongs in the P1/P2 indexes and owning design sources.
- Detailed startup, release, installer, launch, and E2E procedures remain in focused SDDs, ADRs,
  and runbooks reached through task-triggered pointers.
- New scope or ADRs should update their owning index and design sources; root changes only when a
  stable repository-wide invariant or routing branch changes.

### 12.3 Task context

For every task, read root instructions and the instruction file in every affected subtree. Then use
the root task routes to load the named Slice or discover it from the SDD entry, scope gate, and P1/P2
index. Load only direct ADR, Foundation, contract, code, and test dependencies. Reading additional
documents never expands implementation scope.

Feature work requires an accepted Slice/ADR. A bug fix restores documented established behavior.
Cross-subtree contract work changes contract sources before consumers. Generic source startup,
preview-only startup, tagged-release operations, and governance work follow their distinct root
routing branches.

### 12.4 Implementation and evidence

For multi-application features, provide an implementation plan, update contracts before consumers,
stay within the active Slice, run applicable verification, and synchronize design documents only
when implementation facts or approved behavior changed. Simple bug fixes may proceed directly with
the same scope, contract, safety, and verification gates.

Completion requires a complete diff review, current generated artifacts, applicable focused and
repository verification, and explicit `NOT VERIFIED` reporting for required checks that could not
run.

## 13. Branch, PR and Review Workflow

### 13.1 Branch Model

New implementation tasks use a short-lived task branch created from the current `origin/main`
after `git fetch origin`; they do not start directly on `main` or reuse an unrelated or stale
branch/worktree. Follow-up fixes for an existing open PR stay on that PR's branch/worktree unless
explicitly requested otherwise. `/AGENTS.md` defines the required AI workspace procedure.

The branch model is:

```text
main
  └── feature/p0-00-auth-workspace-admin-setup
  └── feature/p0-01-env-groups
  └── fix/runner-callback-idempotency
```

Rules:

1. A PR should try to correspond to a Slice or a small task within a Slice.
2. A PR is not allowed to implement multiple unrelated P0 Slices at the same time.
3. Mixing of P1/P2 capabilities in P0 PR is not allowed.

### 13.2 Commit Message

Use lightweight Conventional Commits:

```text
feat(api): add auth session skeleton
feat(web): add login route shell
test(runner): add callback schema validation tests
docs(sdd): update p0-00 done when
chore(contracts): regenerate openapi client
```

No complicated release process is forced.

### 13.3 PR Template

Suggested PR template:

```markdown
## Goal

## Related SDD / Issue
- docs/sdd/slices/P0-xx-xxx.md

## Documents Read
- docs/sdd/README.md
- docs/sdd/00-product-scope-and-priority.md
- docs/sdd/01-architecture-overview.md
- docs/sdd/02-repo-structure-and-dev-workflow.md
- docs/sdd/slices/P0-xx-xxx.md
- relevant AGENTS.md
- relevant contracts

## Changes

## P0 Scope Check
- [ ] Does not implement API Catalog / import
- [ ] Does not implement Monitoring / Grafana / InfluxDB
- [ ] Does not implement Schedule Run
- [ ] Does not implement multi-node / auto allocation
- [ ] Does not implement OIDC / Secret / non-MinIO storage
- [ ] Does not expose Generated YAML preview/editor

## Contract Check
- [ ] Contracts updated before consumers
- [ ] Generated client refreshed
- [ ] No hand-authored API response types in Web

## Verification
- [ ] make verify
- [ ] If not available, documented bootstrap command:

## Risks / Follow-ups
```

### 13.4 Review Checklist

Review checks at least:

1. Whether the P0 baseline is still maintained without regression, and P1 work is limited to the accepted real Slice SDD;
2. Whether to comply with PRD, 00, 01, current Slice;
3. Whether to realize P1/P2 in advance;
4. Whether to generate Web client/types from contracts;
5. Whether there is a Workspace context;
6. Whether permissions should be verified by the backend instead of just hidden by the frontend;
7. Whether to avoid direct Web connection to DB/MinIO/Load Node;
8. Whether to prevent Runner from accessing DB/MinIO/API internal code;
9. Whether there is migration;
10. Is there any testing?
11. Whether passed `make verify` or a temporary command declared by the current Slice;
12. Whether it is necessary to recharge SDD or add ADR.

---

## 14. Generated Files and Do-Not-Edit Rules

### 14.1 Do Not Edit

Handwritten editing is not allowed:

```text
packages/contracts/openapi/api.openapi.json
packages/contracts/openapi/public-api.openapi.json
packages/contracts/generated/web-client/
```

Do not submit:

```text
node_modules/
.venv/
.env
.env.local
coverage/
dist/
build/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
```

### 14.2 Generated but Committed

The following spawn should be submitted in order for AI, Review, and CI to use the stable contract. The purpose of submitting generated contracts is to allow AI Review and manual Review to directly see the contract diff, so that IDE jumps and completions do not rely on executing `make generate-contracts` first. This is not equivalent to submitting a normal build; the stale check must ensure that the submitted content is always generated from the source.

```text
packages/contracts/openapi/api.openapi.json
packages/contracts/openapi/public-api.openapi.json
packages/contracts/generated/web-client/
```

Must be run before submitting:

```bash
make generate-contracts
make verify
```

### 14.3 Source of Truth

| Output | Source of Truth |
| --- | --- |
| OpenAPI JSON | FastAPI routes + Pydantic schemas |
| Web client/types | OpenAPI JSON |
| Runner callback validation | runner-callback schema |
| DB schema | Alembic migrations |
| P0 scope | PRD + 00 Scope Gate |

---

## 15. P0 Forbidden Work in Repo Scaffold

The following user-visible capabilities, available backend interfaces, or runnable services are prohibited from being included in M0 and subsequent P0 scaffolds.

### 15.1 Product Capabilities Forbidden in P0

Prohibited:

1. API Catalog (P2 document asset management only; does not belong to P1);
2. OpenAPI / Swagger Spec upload;
3. API Spec details display;
4. Create Test Plan from API operation;
5. Any OpenAPI/API Catalog → Scenario/Test Plan generate link;
6. OpenAPI Step is automatically generated;
7. cURL import (P1 Import only refers to cURL; P1 still must not contain API Catalog/OpenAPI generation);
8. Monitoring page;
9. Grafana iframe / Open in Grafana;
10. InfluxDB write link;
11. Grafana datasource management, Dashboard editing or InfluxDB management;
12. Schedule Run / Scheduled Job(P2);
13. In-product Help page (P2);
14. Resource Auto allocation;
15. Multi-node execution;
16. Node Count;
17. Workspace switching or Workspace management UI;
18. User Management UI;
19. System Settings UI;
20. OAuth 2.0 / OIDC / SAML / LDAP;
21. Env Group Secret type;
22. Env Group tag and Dependency File tag (permanently removed);
23. Non-MinIO storage;
24. ZIP / TAR / TGZ automatic decompression (P2);
25. Editable Taurus YAML;
26. P0 Generated YAML preview; P1-04 as amended by ADR-0023 only allows Test Plan read-only Preview generated by the API, and does not allow Scenario Preview or editable YAML.

### 15.2 Infrastructure Forbidden in P0

Prohibited:

1. Kubernetes;
2. Redis;
3. Celery;
4. RabbitMQ;
5. Kafka;
6. External queue service;
7. Split microservices;
8. API Gateway complex strategy;
9. Self-developed authority platform;
10. Self-developed UI basic component library.

### 15.3 Allowed Extension Points

Allowed to remain:

1. P1/P2 README or roadmap in docs;
2. Future extension enumeration in type field, but cannot be activated by P0 UI or API;
3. The data structure does not expose compatible fields of user behavior, but cannot form usable P1/P2 capabilities;
4. Design instructions for navigation occupancy, but clickable entrances must not be provided in P0 products;
5. P1-09 Structured Scenario Global Configuration Tabs authorization exception for Phase A, only `Settings` / `Headers` / `Variables` / `Data Sources` , Phase B `globalScripts` , editable YAML, Secret Scenario variables, Test Plan are not allowed schema redesign, API Catalog generation, Schedule, multi-node, JMeter expert panels or new runtime dependencies.

If it is not sure whether it crosses the boundary, the default is to not enter P0.

---

## 16. M0 Done When

When the M0 repository skeleton is completed, the following conditions must be met.

### 16.1 Repository

- [ ] Monorepo structure created.
- [ ] `apps/web`, `apps/api`, `apps/runner` were created.
- [ ] `packages/contracts` created.
- [ ] `tests/contract`, `tests/e2e` created.
- [ ] `infra/docker` created.
- [ ] `docs/prd`, `docs/sdd` created.
- [ ] Root `AGENTS.md` created.
- [ ] Key subdirectory `AGENTS.md` created.
- [ ] The following ADR placeholders or v1s have been created: `ADR-0001-monorepo.md` , `ADR-0002-runner-independent-app.md` , `ADR-0003-p0-minio-only.md` , `ADR-0004-p0-manual-single-node-only.md` , `ADR-0005-p0-no-api-catalog-no-monitoring-no-schedule.md` , `ADR-0006-p0-separate-api-worker.md` .

### 16.2 Tooling

- [ ] pnpm can install Web / contracts dependencies.
- [ ] uv can install API/Runner dependencies according to workspace, and there is only one `uv.lock` in the root directory.
- [ ] Python version fixed to 3.12.
- [ ] Node is fixed to 22 LTS, and the content of `.nvmrc` is `22`.
- [ ] `.env.example` provided.
- [ ] `.gitignore` Override node_modules, venv, env, cache, build output.

### 16.3 Apps

- [ ] Web has a minimal Vite app that can be launched or built.
- [ ] API has minimal FastAPI app, providing `/api/health` or equivalent health endpoint.
- [ ] api-worker has an independent entrance and can exit safely or execute an empty loop after startup.
- [ ] Runner has minimal CLI, supports `--help`.
- [ ] M0 does not implement business functions and does not create P1/P2 entries.

### 16.4 Contracts

- [ ] `packages/contracts/openapi/api.openapi.json` can be exported by the API.
- [ ] The package name of `packages/contracts` is fixed to `@surgepilot/contracts`.
- [ ] `packages/contracts/generated/web-client/` can be generated by OpenAPI.
- [ ] `packages/contracts/runner/runner-callback.schema.json` has a minimum footprint.
- [ ] `make generate-contracts` is runnable.
- [ ] generated files have stale check.

### 16.5 Infra

- [ ] Docker Compose enables PostgreSQL and MinIO.
- [ ] Full container smoke can start web, api, api-worker, postgres, minio, nginx.
- [ ] Nginx smoke mode can route `/` and `/api`.
- [ ] MinIO bucket `surgepilot` can be initialized by Compose init-bucket sidecar and explicitly checked by API startup / Setup Status.
- [ ] Compose does not include P1/P2 services.

### 16.6 Verification

- [ ] `make setup` is runnable.
- [ ] `make infra-up` is runnable.
- [ ] `make generate-contracts` is runnable.
- [ ] `make lint` At least overwrite existing code.
- [ ] `make test` at least covers bootstrap tests.
- [ ] `make verify` is runnable, even if only the M0 bootstrap subset.
- [ ] `make help` is runnable.
- [ ] `make verify` can be called with one click in the CI environment and does not rely on the native IDE or GUI; the specific CI platform and matrix are defined by `09-testing-and-acceptance-strategy.md`.
- [ ] README must at least state the prerequisites (Node 22, Python 3.12, Docker, pnpm, uv), Mode A and Mode B startup commands, `make verify` usage, `docs/sdd/README.md` entry; README does not repeat the PRD or complete product introduction.

### 16.7 Scope

- [ ] There are no P1/P2 available capabilities such as API Catalog, Monitoring, Schedule, multi-node, OIDC, Secret, non-MinIO storage, etc.
- [ ] No direct web access to DB/MinIO/Load Node.
- [ ] No Runner access to DB/MinIO or import API internal code.
- [ ] No handwritten Web API types to bypass contracts.

---

## 17. Open Questions Deferred to Later SDDs

The following issues are not discussed in this article:

1. Complete domain model and table fields;
2. API route naming, paging, filtering, error code registry;
3. Runner callback payload complete schema;
4. Run state machine and timeout value;
5. Node lease table structure and index;
6. MinIO object key verification rules;
7. Artifact metadata field;
8. Frontend routing, layout and page component specifications;
9. Complete test matrix and CI platform configuration; `make verify` can be called in CI is a fixed requirement 02;
10. Specific implementation plan for each P0 Slice.

These contents must be supplemented in the corresponding Foundation SDD or Slice SDD and should not be rolled out in advance in 02.

---

## 18. One-line Rule

> **02 is only responsible for fixing the repository skeleton, development commands, contracts, verification entrances and AI Coding workflow; business details are handed over to the subsequent Foundation SDD and Slice SDD; all implementations maintain the P0 baseline without regression, P1 is only activated through the accepted real Slice SDD, contracts are prioritized, verifiable, and not over-designed. **
