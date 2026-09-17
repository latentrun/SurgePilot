# 09. Testing and Acceptance Strategy

- Document status: Draft v2
- Product: SurgePilot performance testing platform
- Document path: `docs/sdd/09-testing-and-acceptance-strategy.md`
- Product source: `docs/prd/PRD.md`
- Scope gate: `docs/sdd/00-product-scope-and-priority.md`
- Architecture source: `docs/sdd/01-architecture-overview.md`
- Workflow source: `docs/sdd/02-repo-structure-and-dev-workflow.md`
- API contract source: `docs/sdd/04-api-contract-guidelines.md`
- Runner source: `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- Security source: `docs/sdd/06-security-permission-workspace.md`
- Storage source: `docs/sdd/07-storage-artifacts-minio.md`
- Current delivery target: P2-02 Public API Substrate + P2-03 Env Group Secret + P2-04 Help AI Agents and System OpenAPI Bootstrap + ADR-0013 static Marketing Landing and Logo + P1-09 Scenario Global Configuration authorization
- Applies to: Foundation SDD, Slice SDD, CI, local verification, API, Web, Runner, contracts, fake-runner, real SSH smoke, AI Coding, code review, and release acceptance

---

## 1. Purpose

This document defines the P0 testing and acceptance contract for SurgePilot.

It defines:

1. Test layers and their ownership.
2. Required local and CI verification commands.
3. Coverage thresholds and exclusions.
4. API, Web, Runner, contract, security, storage, E2E, and smoke testing rules.
5. Slice and P0 acceptance rules.
6. Review gates for AI Coding and human review.

This document does not define implementation steps, test file names for every Slice, or author reasoning history. Concrete test cases, fixtures, endpoint schemas, and `Done When` items belong to the relevant Slice SDD.

---

## 2. Authority and Conflict Resolution

### 2.1 Canonical Inputs

This document depends on:

1. `docs/prd/PRD.md` for product scope and acceptance meaning.
2. `docs/sdd/00-product-scope-and-priority.md` for P0/P1/P2 boundaries.
3. `docs/sdd/01-architecture-overview.md` for component boundaries.
4. `docs/sdd/02-repo-structure-and-dev-workflow.md` for repository layout, root commands, contracts, and workflow.
5. `docs/sdd/04-api-contract-guidelines.md` for REST, OpenAPI, public API, internal runner API, error shape, and generated client rules.
6. `docs/sdd/05-runner-protocol-and-run-state-machine.md` for Runner protocol, Run state machine, callback idempotency, timeout, force-kill, and quarantine rules.
7. `docs/sdd/06-security-permission-workspace.md` for auth, session, CSRF, role, Workspace, credential, and security rules.
8. `docs/sdd/07-storage-artifacts-minio.md` for MinIO, Dependency File, Artifact, path safety, and storage boundary rules.

### 2.2 Conflict Resolution

Rules:

1. If this document conflicts with `docs/prd/PRD.md`, the PRD wins and this document must be updated.
2. If this document conflicts with `docs/sdd/00-product-scope-and-priority.md`, document 00 wins unless it conflicts with the PRD.
3. If this document conflicts with `docs/sdd/02-repo-structure-and-dev-workflow.md`, repository command semantics and toolchain ownership from document 02 win and both documents must be aligned.
4. If this document conflicts with document 04, API contract rules from document 04 win and the test gate must be adjusted without weakening coverage.
5. If this document conflicts with document 05, Run state machine and Runner protocol semantics from document 05 win.
6. If this document conflicts with document 06, security and Workspace rules from document 06 win.
7. If this document conflicts with document 07, storage and MinIO safety rules from document 07 win.
8. Slice SDD may add stricter test requirements but must not weaken this document.
9. Code and CI configuration must not override this document silently; any intentional change requires SDD or ADR update.

---

## 3. Confirmed Testing Decisions

| Area | Decision |
| --- | --- |
| Current testing scope | P0 baseline; accepted P1/P2 Slice-specific additions remain governed by their own Slice SDDs |
| Test pyramid | API 50%, Web 25%, Contract 15%, E2E 10% by testing effort and review focus |
| Default hard gate | `make verify` |
| Nightly / release E2E gate | `make verify-e2e` |
| API tests | `pytest`, `pytest-asyncio`, `httpx.AsyncClient`, `pytest-cov` |
| API coverage | line and branch coverage >= 90% |
| Runner tests | `pytest`, `pytest-cov`, JSON Schema validation for callback payloads |
| Runner coverage | line and branch coverage >= 90%, including fake-runner code inside the runner package |
| Web tests | `vitest`, `@testing-library/react`, V8 coverage |
| Web coverage | lines, branches, and functions >= 90% |
| Patch coverage | changed functional code >= 90% |
| Python patch coverage | must use `diff-cover` |
| Web patch gate | `vitest --related` or equivalent related-tests gate plus full Web coverage >= 90% |
| Contract tests | OpenAPI freshness, generated client freshness, OpenAPI breaking diff, Schemathesis, Runner JSON Schema |
| Schemathesis scope | `/api/v1/...` public business API only |
| Internal runner endpoint testing | JSON Schema contract tests plus API integration tests |
| E2E framework | Playwright |
| P0 E2E minimum | Happy path plus Stop path |
| Real SSH profile | `make verify-e2e`; required for release/main merge, not ordinary PR default gate |
| fake-runner | Lives in `apps/runner`, shares callback client/schema with real Runner |
| MinIO integration | Real MinIO required for storage integration tests |
| BDD/Gherkin | Not used in P0 |
| SAST/DAST | Not P0 merge gates |
| Formal platform performance testing | Deferred beyond P0 |
| Lightweight smoke | Local/dev p95 < 300ms for health/readiness/current-user/small list APIs only |
| Coverage rollout | M0 may use a documented bootstrap subset; P0 final requires >= 90% line and branch coverage for API, Web, and Runner |

---

## 4. Scope and Non-Goals

### 4.1 In Scope

P0 test strategy includes:

1. Unit tests for business rules, validators, services, reducers, hooks, utilities, and runner helpers.
2. API integration tests for auth, Workspace, permissions, CRUD, Run state, node lease, callback, storage, and security boundaries.
3. Web component and page tests for forms, state, generated client usage, empty states, error states, and key user flows.
4. Runner unit and integration-style tests for callback payloads, fake-runner, process behavior abstractions, artifact metadata, and stop semantics.
5. Contract tests for OpenAPI, generated Web client, Schemathesis, and Runner callback JSON Schema.
6. Storage integration tests against real MinIO.
7. Playwright smoke/E2E tests for P0 happy path and Stop path.
8. CI gates that reuse repository root commands.
9. Slice and P0 acceptance rules based on automated verification plus `Done When`.

### 4.2 Out of Scope

P0 test strategy does not include:

1. BDD/Gherkin as a separate source of truth.
2. Formal load testing of SurgePilot itself.
3. Capacity baseline, historical trend, or performance regression suite.
4. Browser matrix beyond the configured CI browser profile.
5. SAST/DAST or penetration testing as P0 merge gates.
6. Real cloud object storage testing outside MinIO.
7. Kubernetes, Redis, Celery, RabbitMQ, Kafka, monitoring, schedule, multi-node execution, OIDC, Secret, or non-MinIO tests as a reason to implement P1/P2 code.

---

## 5. Test Layer Ownership

| Layer | Primary location | Required focus |
| --- | --- | --- |
| API unit | `apps/api/tests` | services, validators, auth/session logic, Workspace filters, state transitions, storage adapter boundaries |
| API integration | `apps/api/tests` | FastAPI routes with DB, auth, CSRF, Workspace, permissions, MinIO where needed |
| Web unit/component | co-located or `apps/web/tests` | components, forms, hooks, generated client integration, state/error/loading behavior |
| Runner unit | `apps/runner/tests` | CLI, callback client, fake-runner, process control abstractions, artifact upload metadata |
| Contract | `tests/contract` | OpenAPI freshness, generated client freshness, Schemathesis, Runner callback schema |
| E2E | `tests/e2e` | Playwright P0 happy path and Stop path |
| Storage integration | `apps/api/tests` or `tests/contract` by boundary | real MinIO upload/download/hash/path/permission behavior |
| Real SSH smoke | `tests/e2e` or dedicated E2E profile | minimal real Runner start/stop/artifact flow |

Rules:

1. Application-specific unit tests stay with the application.
2. Cross-application contract and E2E tests stay under root `tests`.
3. E2E must not replace unit, integration, contract, or security tests.
4. fake-runner tests belong to `apps/runner`, not `apps/api` and not only `tests/e2e/helpers`.
5. Tests must be added or updated in the same PR as functional changes.

---

## 6. Required Commands

### 6.1 `make verify`

`make verify` is the default PR and local hard gate.

It must include at least:

```text
lint
+ typecheck
+ API unit/integration tests
+ Runner unit tests
+ Web unit/component tests
+ coverage gates
+ patch coverage gates
+ contract tests
+ OpenAPI freshness check
+ generated Web client freshness check
+ OpenAPI breaking diff in CI
```

Rules:

1. `make verify` must not require real SSH credentials.
2. `make verify` must not require public internet access.
3. `make verify` must not require P1/P2 services.
4. `make verify` must be runnable from a clean checkout after setup.
5. CI must call `make verify` instead of duplicating its logic in CI-only scripts.
6. M0 may expose a documented bootstrap subset, but the command name must remain stable and must converge to the full gate by P0 implementation.

### 6.2 `make verify-e2e`

`make verify-e2e` is the E2E, fake-runner, and real SSH profile gate.

It must include:

```text
Playwright P0 happy path
+ Playwright Stop path
+ fake-runner profile
+ real SSH smoke profile when configured
```

Rules:

1. `make verify-e2e` may be nightly/release-only.
2. `make verify-e2e` must use the same product paths as local development.
3. fake-runner E2E is allowed for stable UI smoke.
4. real SSH smoke is required for release/main merge.
5. ordinary PR `make verify` must not be blocked by missing real SSH credentials.

### 6.3 CI Command Parity

Rules:

1. Local and CI verification must use the same root commands.
2. CI may pass environment variables or profile flags, but must not create separate test semantics.
3. CI-only shell scripts that bypass root commands are forbidden.
4. Documentation-only changes may use a reduced CI path only when no code, contracts, generated clients, or workflow files changed.

---

## 7. Coverage Rules

### 7.1 Global Thresholds

The final P0 coverage thresholds are:

| Area | Required threshold |
| --- | --- |
| API | line >= 90%, branch >= 90% |
| Runner | line >= 90%, branch >= 90% |
| Web | lines >= 90%, branches >= 90%, functions >= 90% |
| Patch coverage | changed functional code >= 90% |

Rules:

1. API and Runner coverage must enable branch coverage explicitly with `--cov-branch` or equivalent configuration.
2. `pytest-cov` `fail_under=90` alone is insufficient because it may only enforce line coverage.
3. Web coverage must use V8 coverage or equivalent Vitest-supported coverage provider.
4. Patch coverage is separate from full coverage and must not be replaced by full coverage.
5. Coverage thresholds apply to P0 final state; M0 bootstrap may use a documented transitional gate.
6. New functional code in P0 implementation PRs should satisfy patch coverage from the start.

### 7.2 Python Coverage Command Contract

API and Runner coverage commands must enforce line and branch gates.

Required semantics:

```bash
pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90
pytest --cov=surgepilot_runner --cov-branch --cov-report=term-missing --cov-fail-under=90
```

Rules:

1. Equivalent package names are allowed if the actual package layout differs.
2. Branch coverage must be enabled.
3. Exclusions must be configured centrally.
4. Scattered `# pragma: no cover` is forbidden except for approved, documented cases.
5. Tests must not mock away the business logic being measured.

### 7.3 Web Coverage Command Contract

Web coverage command must enforce lines, branches, and functions.

Required semantics:

```bash
vitest --coverage
```

Rules:

1. Coverage provider should be V8.
2. `lines`, `branches`, and `functions` must each be >= 90%.
3. UI tests must cover validation, error state, loading state, and disabled/double-submit behavior for critical forms.
4. Generated client code must be excluded from Web coverage.
5. Web tests must not assert internal implementation details when user-visible behavior is the contract.

### 7.4 Patch Coverage

Rules:

1. Python patch coverage must use `diff-cover` or an equivalent diff-aware coverage gate approved by this document.
2. Python changed functional lines must be >= 90% covered.
3. Web changed functional code must run related tests through `vitest --related` or an equivalent changed-files test gate.
4. Web still must satisfy full Web coverage thresholds.
5. Patch coverage applies to functional source code, not generated code, migrations, or configuration-only files.
6. Lowering patch coverage for convenience is forbidden.

### 7.5 Exclusions

Allowed coverage exclusions:

1. `migrations/`.
2. `__init__.py`.
3. `*.config.ts`.
4. `contracts/generated/`.
5. `main.py` application bootstrap where only framework wiring is present.
6. Generated OpenAPI and generated Web client files.

Rules:

1. Exclusions must be explicit in tool configuration.
2. Core business logic, validators, state machine transitions, permission checks, security checks, storage path safety, callback handling, and node lease logic must not be excluded.
3. Any additional exclusion requires review and SDD or Slice-level justification.

---

## 8. API Test Strategy

### 8.1 Required API Test Areas

API tests must cover:

1. Auth registration, login, logout, current user, session expiry, and CSRF.
2. First Admin bootstrap and later User registration.
3. Workspace resolution, default Workspace fallback, and cross-Workspace denial.
4. Role authorization for Admin-only and User-allowed operations.
5. CRUD validation for current Slice resources.
6. Uniform error shape and request ID behavior.
7. OpenAPI response model shape for public APIs.
8. Run creation atomicity: Run, Run Snapshot, and node lease.
9. Run state transition conditions.
10. Runner callback authentication, schema validation, idempotency, and late callback behavior.
11. Stop idempotency and convergence.
12. Heartbeat timeout, accepted wait timeout, stop grace timeout, force-kill result, and quarantine behavior.
13. MinIO-backed Dependency File and Artifact boundaries.
14. Security minimum set defined in this document.

### 8.2 API Test Rules

1. Use `pytest`, `pytest-asyncio`, and `httpx.AsyncClient` or equivalent FastAPI-compatible test client.
2. API integration tests must exercise middleware for session, CSRF, Workspace, and request ID where applicable.
3. Route tests must verify status codes and error codes, not only response messages.
4. Negative tests are required for permission, Workspace, CSRF, invalid input, duplicate callback, unsafe path, and stale state conditions.
5. API tests must not depend on Web behavior.
6. API tests must not use real SSH in `make verify`.
7. API tests that need storage integration must use real MinIO, not only mocks.

---

## 9. Web Test Strategy

### 9.1 Required Web Test Areas

Web tests must cover:

1. Auth pages and session-dependent routing.
2. Forms for current Slice resources.
3. Generated API client usage through `@surgepilot/contracts`.
4. Loading, empty, success, and error states.
5. Validation errors and field-level error display.
6. Disabled submit and double-submit prevention for critical actions.
7. Workspace header propagation through the client layer.
8. Run status and Run Report user-visible state.
9. Stop action user flow and disabled/retry behavior.
10. Artifact list and download action through business API URLs only.

### 9.2 Web Test Rules

1. Use `vitest` and `@testing-library/react`.
2. Tests should assert user-visible behavior before internal component details.
3. API calls should be mocked at the generated client or request boundary in component tests.
4. Web tests must not invent API shapes outside OpenAPI/generated types.
5. Web must never receive MinIO URL, object key, bucket credential, SSH credential, session token, or runner token.
6. Playwright should cover only P0 critical paths and must not replace component tests.

---

## 10. Runner and fake-runner Test Strategy

### 10.1 Runner Unit Tests

Runner tests must cover:

1. CLI argument parsing for `start`, `stop`, `kill`, and fake-runner mode.
2. Callback client payload construction and retry behavior.
3. JSON Schema validation for emitted callback payloads.
4. Required callback fields including `schemaVersion`, `eventId`, `runId`, `nodeId`, `eventType`, `seq`, and `eventTime`.
5. Terminal callback requirement for `details.processGroupExited`.
6. Safe artifact metadata preparation.
7. Secret-safe logging behavior.
8. Stop and kill command behavior through testable process-control abstractions.

### 10.2 fake-runner Rules

1. fake-runner must live under `apps/runner`.
2. fake-runner must share callback client and schema validation with the real Runner.
3. fake-runner must not be implemented as an API-only mock.
4. fake-runner must be covered by Runner package coverage.
5. fake-runner must support deterministic branches for accepted, running, heartbeat, artifact, finished, failed, aborted, heartbeat timeout simulation, stop grace timeout simulation, quarantine path, and duplicate `eventId` behavior.
6. fake-runner may drive API integration tests and Playwright smoke tests.
7. fake-runner cannot replace real SSH acceptance.

### 10.3 Real SSH Smoke

Real SSH smoke belongs to `make verify-e2e`.

Rules:

1. Real SSH smoke must be small and deterministic.
2. Real SSH smoke is not a general performance test.
3. Real SSH smoke must not require public internet access from the Load Node unless explicitly configured by the test environment.
4. Real SSH failure blocks release/main merge but not ordinary PR default `make verify`.
5. Real SSH smoke must verify start, heartbeat or running signal, Stop or terminal convergence, and artifact upload through API when the environment supports it.

---

## 11. Contract Test Strategy

### 11.1 OpenAPI Source and Freshness

Rules:

1. `packages/contracts/openapi/api.openapi.json` is generated from FastAPI/Pydantic and is not hand-written.
2. `make generate-contracts` must regenerate OpenAPI and Web client/types.
3. `make verify` must fail when exported OpenAPI differs from the committed artifact.
4. `make verify` must fail when generated Web client/types are stale.
5. Generated files must be deterministic.
6. Web must import API types through `@surgepilot/contracts`, not relative paths into generated files.

### 11.2 OpenAPI Breaking Diff

CI must compare current OpenAPI against the base branch.

Rules:

1. Breaking changes fail unless the corresponding SDD/ADR and Slice explicitly approve the migration.
2. Adding a new P0 endpoint may pass if it follows document 04 and is in the current Slice scope.
3. Adding a P1/P2 endpoint during P0 must fail review even if OpenAPI diff is technically non-breaking.
4. Removing or changing public API fields requires SDD update and migration plan.
5. Internal runner endpoints are not part of the Web public OpenAPI client.

### 11.3 Schemathesis Scope

Schemathesis tests apply to public business API only.

Rules:

1. Schemathesis covers `/api/v1/...` public business APIs.
2. Schemathesis does not cover `/api/internal/v1/runner/...`.
3. Runner internal endpoints are covered by JSON Schema contract tests and API integration tests.
4. Schemathesis tests must use authenticated fixtures where the endpoint requires session and Workspace context.
5. Schemathesis must assert API returns valid error shapes for invalid inputs and does not leak stack traces or secrets.

### 11.4 Runner Callback Schema Contract

Rules:

1. `packages/contracts/runner/runner-callback.schema.json` is the source of truth for callback payloads.
2. API tests must reject schema-invalid callback payloads.
3. Runner tests must validate emitted payloads against the schema.
4. `schemaVersion` is required and P0 accepts only `"1"`.
5. `eventId` is required and is the idempotency key.
6. `seq` is required for diagnostics and must not be used to decide state transitions.
7. Terminal callbacks must include `details.processGroupExited`.

---

## 12. Run State Machine Acceptance Matrix

Run state machine tests must explicitly cover the following branches.

### 12.1 State Transition Branches

| Scenario | Required assertion |
| --- | --- |
| Run creation | Run, Run Snapshot, and node lease are created atomically |
| `accepted` callback | Run remains `initializing` |
| `running` callback | `initializing` -> `running` |
| `heartbeat` callback | Only `lastHeartbeatAt` changes |
| `artifact` callback | Metadata/event registration only; no state change |
| `finished` callback from running | Run becomes `finished` and lease releases when cleanup is safe |
| `failed` callback from active state | Run becomes `failed` and lease releases or node quarantines according to cleanup result |
| `aborted` callback after Stop | Run becomes `aborted` and lease releases when cleanup is safe |
| terminal late callback | Terminal state remains unchanged |
| duplicate callback | No duplicate state transition, audit event, artifact, or lease release |
| illegal transition | State unchanged and event logged/ignored according to contract |

### 12.2 Timeout and Cleanup Branches

| Scenario | Required assertion |
| --- | --- |
| accepted wait timeout | Run becomes `failed`; cleanup path runs |
| heartbeat timeout | Run becomes `failed`; force-kill path runs |
| Stop requested in initializing | Run enters `stopping`; repeated Stop is idempotent |
| Stop requested in running | Run enters `stopping`; repeated Stop is idempotent |
| Stop grace timeout | Run becomes `aborted` with forced convergence |
| force-kill succeeds | Node becomes unavailable during cooldown, then eligible according to Load Node rules |
| force-kill fails | Node becomes `quarantined` and unavailable |
| terminal callback with `details.processGroupExited=false` | Node remains unavailable until cleanup succeeds or quarantine is applied |
| api-worker crash mid-cleanup | Recovery resumes cleanup or keeps node unavailable |
| stale lease recovery | Lease does not leave node permanently Busy |

### 12.3 Node Lease Branches

Tests must assert:

1. Only one active Run can lease a single Idle Load Node.
2. Terminal transition releases lease only when cleanup is safe.
3. Failed cleanup does not return node to Idle.
4. Quarantined node cannot be selected for a new Run.
5. Workspace and permission rules are applied before node lease acquisition.
6. Manual single-node rule is enforced in P0.

---

## 13. Storage and MinIO Test Strategy

### 13.1 Storage Test Layers

| Layer | Required approach |
| --- | --- |
| Unit | Validators, metadata services, error mapping, and adapter boundaries may mock MinIO |
| Integration | Upload/download/hash/stream/path/permission tests use real MinIO |
| Contract | API response must not expose object key, bucket, or presigned URL |
| E2E | Artifacts appear in Run Report through API business endpoint; Web never receives MinIO URL or object key |

### 13.2 Required Storage Tests

Storage tests must cover at least:

1. Safe filename allowlist and rejection cases.
2. Safe artifact relative path allowlist and rejection cases.
3. Rejection of `..`, absolute paths, backslashes, duplicate slashes, Unicode, and whitespace paths.
4. Dependency File upload streams to MinIO and computes actual size/hash.
5. Dependency File download streams through API and uses attachment disposition.
6. Dependency File delete protection when referenced by Scenario, Test Plan, or Run Snapshot.
7. Artifact upload through API internal endpoint, not direct MinIO.
8. Artifact size limit and SHA-256 mismatch rejection.
9. Artifact idempotency by `(runId, eventId)`.
10. Artifact path conflict by `(runId, relativePath)`.
11. Terminal-late artifact acceptance/rejection rules.
12. Artifact listing and download filter by Workspace and Run.
13. Web API responses do not include MinIO object key, bucket, credential, or presigned URL.
14. Storage outage maps to `503 STORAGE_UNAVAILABLE` without leaking internal error details.

### 13.3 MinIO Isolation

Rules:

1. Each test run uses a unique object prefix such as `test-{ulid}/` when storage adapter supports test prefixing.
2. Each test case must clean up objects it writes, or rely on a per-run test bucket/prefix cleanup step.
3. Tests must not share mutable MinIO objects across cases.
4. Real MinIO integration tests must not use production credentials.
5. Local and CI storage test configuration must be equivalent.

---

## 14. Security Test Strategy

### 14.1 P0 Security Minimum Set

The following P0 security tests are mandatory and must be included in automated tests and coverage accounting:

| Area | Required tests |
| --- | --- |
| Password hashing | Argon2id hash is used; plaintext and reversible encryption are not stored |
| Password policy | Minimum length and letter/digit requirements are enforced by backend |
| Session expiry | Absolute 7-day expiry and idle 24-hour sliding expiry are enforced |
| Logout | Current session is invalidated server-side |
| CSRF | Browser write requests require valid session-bound `x-csrf-token` |
| Brute-force guard | 5-failure and 10-failure lock thresholds behave as specified |
| Login failure response | Unknown email, wrong password, and lockout use generic public response |
| Role authorization | Admin-only and User-allowed operations are enforced by backend |
| Workspace isolation | Cross-Workspace reads/writes/downloads are denied or hidden |
| Private Load Node credentials | Credentials are encrypted at rest and never returned in API response |
| Runner token | Internal runner endpoints reject missing/invalid token and do not use browser session |
| MinIO path traversal | Dependency File and Artifact paths reject traversal and unsafe characters |
| Secret leakage | API responses, errors, and normal logs do not expose password hash, session token, CSRF token, runner token, SSH credential, or MinIO credential |

### 14.2 Security Testing Rules

1. Security tests should be unit or API integration tests whenever possible.
2. Security tests must not rely on Playwright E2E as the only validation.
3. Negative tests are required for auth, CSRF, Workspace, permission, credential, and path safety boundaries.
4. Test snapshots must not contain real tokens, passwords, private keys, or credentials.
5. P0 does not require SAST, DAST, or penetration testing as merge gates.
6. P1 may add SAST/DAST if it does not replace P0 automated security tests.

---

## 15. Test Data and Isolation

### 15.1 Fixture Rules

1. Each test case creates its own user, workspace, and required resources unless it tests bootstrap seed behavior.
2. Tests that require Admin must create a dedicated admin fixture.
3. Tests that require User must create a dedicated user fixture.
4. Shared mutable global seed data is forbidden.
5. Default Workspace seed may exist, but ordinary tests should not mutate it.
6. Fixtures must be explicit about role, Workspace, and resource ownership.

### 15.2 Database Isolation

1. API tests should use transaction rollback per case where supported.
2. Tests requiring commit/worker behavior may use isolated data and explicit cleanup.
3. Concurrent state transition tests must not run against shared fixtures that can affect unrelated tests.
4. Migration tests must run against PostgreSQL-compatible behavior.
5. Tests must not depend on execution order.

### 15.3 External Boundary Isolation

| Boundary | Rule |
| --- | --- |
| MinIO | Real integration tests use isolated prefix/bucket and cleanup |
| SSH | Real SSH only in `make verify-e2e` profile |
| Time | Time-sensitive tests use controllable clock or bounded tolerance |
| Network | Unit tests do not require public internet |
| Secrets | Test secrets are synthetic and never production values |

---

## 16. E2E and Smoke Acceptance

### 16.1 P0 Happy Path

Playwright P0 happy path must cover:

```text
Register first Admin / login
  -> Default Workspace available
  -> Create required P0 assets for a minimal run
  -> Create or select a Load Node test fixture
  -> Create Visual Scenario or minimal scenario fixture
  -> Create Test Plan
  -> Run Now
  -> Run reaches terminal state through fake-runner or real Runner profile
  -> Run Report shows verdict, KPI/report summary area, artifacts list, and download action
```

Rules:

1. E2E covers user-observable flow, not every validation branch.
2. E2E must not become the main source of coverage for business logic.
3. P0 happy path must not use P1/P2 capabilities such as API Catalog, Schedule Run, Monitoring, multi-node execution, or generated YAML preview.
4. E2E must use stable selectors and avoid depending on cosmetic layout details.

### 16.2 Stop Path

Playwright Stop path must cover:

```text
Start Run
  -> Run becomes initializing or running
  -> User clicks Stop
  -> User clicks Stop again or repeats action through the UI path if exposed
  -> Run enters stopping and converges to aborted or failed according to controlled runner behavior
  -> Load Node is released or quarantined according to cleanup result
  -> Run Report shows a clear terminal reason and any available artifacts/logs
```

Rules:

1. Stop path is part of P0 acceptance.
2. fake-runner Stop path may run in nightly and can be used for stable UI smoke.
3. Real SSH Stop path must run in the release/main merge profile.
4. E2E assertions must verify final state and node availability outcome.

### 16.3 E2E Boundary

1. P0 E2E does not cover every CRUD branch.
2. P0 E2E does not cover browser matrices beyond the supported CI browser profile.
3. P0 E2E does not use BDD/Gherkin.
4. P0 E2E does not run formal performance tests.
5. E2E failures block nightly/release according to the configured gate.

---

## 17. Performance and Smoke Checks

### 17.1 P0 Performance Boundary

P0 does not establish a formal SurgePilot performance baseline.

Rules:

1. SurgePilot must not use itself as a required performance test dependency in P0.
2. P0 does not run load tests against the platform as a merge gate.
3. P0 does not benchmark Run creation, artifact upload, file download, or SSH execution as hard performance gates.
4. Formal capacity, baseline, regression, and trend testing are deferred to P2 or later scope.

### 17.2 Lightweight API Smoke

P0 may keep a local smoke expectation:

```text
p95 < 300ms for lightweight API checks on local/dev CI environment
```

Allowed endpoints:

1. `/api/healthz`;
2. `/api/readyz`;
3. current-user identity endpoint;
4. core list endpoints with empty or small test data.

Rules:

1. `/api/healthz` and `/api/readyz` are unversioned health/readiness endpoints and are not violations of the `/api/v1/...` business API rule.
2. This smoke check is not a load test.
3. It must not require large datasets.
4. It must not include Run creation, SSH, artifact upload, or file download as hard p95 targets.
5. Failure should indicate obvious local regression, not capacity readiness.

---

## 18. CI Rules

### 18.1 PR Gate

Every functional PR must pass:

```text
make verify
```

Rules:

1. PR gate must run lint, typecheck, tests, coverage, and contract checks.
2. PR gate must fail on stale OpenAPI or generated client.
3. PR gate must fail on unapproved breaking OpenAPI diff.
4. PR gate must fail on coverage or patch coverage below threshold once the relevant code area is active.
5. PR gate must not require real SSH credentials.
6. Documentation-only PRs may skip runtime tests only through an explicit CI path that still validates Markdown and does not touch code/contracts.

### 18.2 Nightly Gate

Nightly must run:

```text
make verify
make verify-e2e
```

Rules:

1. Nightly should include fake-runner Playwright flows.
2. Nightly should include real SSH profile when a test Load Node is available.
3. Nightly failures must be visible to maintainers and treated as release blockers until resolved or explicitly waived.
4. Nightly must not use a separate test implementation path from local commands.

### 18.3 Release / Main Merge Gate

Before P0 release or main merge, the gate must include:

```text
make verify
make verify-e2e
```

Rules:

1. Release/main merge gate must include real SSH smoke.
2. Release/main merge gate must include P0 happy path and Stop path.
3. Release/main merge gate must not rely only on fake-runner.
4. Waiving real SSH requires an explicit risk note in the release record or PR summary.

---

## 19. Acceptance Rules

### 19.1 Slice Acceptance

Each Slice is accepted only when:

```text
automated tests pass
+ required contract checks pass
+ required coverage gates pass
+ Slice Done When items are all satisfied
```

Rules:

1. `Done When` is the Slice acceptance checklist.
2. Each `Done When` item must be linked to an automated test, a verification command, or an explicit manual check.
3. Manual-only Done When items must be rare and justified by external dependency constraints.
4. A Slice cannot be accepted if it implements P1/P2 functionality outside the approved scope.
5. A Slice cannot be accepted if it weakens Foundation SDD rules.
6. A Slice cannot be accepted if generated contracts are stale.
7. A Slice cannot be accepted if it passes E2E but fails unit/integration/contract gates.

### 19.2 P0 Acceptance

P0 is accepted only when all of the following are true:

1. All P0 Slice `Done When` checklists are complete.
2. `make verify` passes from a clean checkout.
3. `make verify-e2e` passes in fake-runner profile.
4. `make verify-e2e` passes in real SSH profile for release/main merge.
5. P0 happy path passes.
6. P0 Stop path passes.
7. P0-Stability matrix passes, including Run Snapshot, callback idempotency, Stop idempotency, heartbeat timeout, node lease release, quarantine, and path safety.
8. No P1/P2 visible or callable product capability is implemented outside approved placeholders.
9. Security minimum set passes.
10. MinIO integration tests pass against real MinIO.

### 19.3 No BDD/Gherkin Rule

1. P0 does not introduce BDD/Gherkin.
2. Acceptance remains `Done When` plus automated verification commands.
3. User-facing scenarios may be described in Slice SDD prose, but not as a separate Gherkin source of truth.

---

## 20. Review Checklist

Reviewers must reject SDD, Issue, PR, or AI output when any of the following is true.

### 20.1 Scope Review

- Implements or tests API Catalog, cURL import, Monitoring, Schedule Run, multi-node execution, OIDC, Secret, non-MinIO storage, or other P1/P2 capability in P0.
- Uses hidden endpoint, hidden route, or config flag to justify premature P1/P2 implementation.
- Makes E2E the only validation for business logic, security, or state machine behavior.
- Adds CI-only scripts that duplicate repository `make` commands.

### 20.2 Coverage Review

- Coverage drops below the required threshold without approved transitional M0 reason.
- Patch coverage is below 90% for changed functional code.
- Core business logic is excluded from coverage.
- Tests mock away the code path being validated.
- Tests cover only the happy path for permission, validation, callback, storage, or security logic.

### 20.3 Contract Review

- OpenAPI artifact is hand-written or stale.
- Generated Web client/types are stale.
- Web imports generated files through relative paths instead of `@surgepilot/contracts`.
- Schemathesis scope includes internal runner endpoints or excludes public P0 business API without reason.
- Runner callback payload is not validated against JSON Schema.
- API returns object keys, credentials, session token, CSRF token, runner token, or private SSH credentials.

### 20.4 Runner and State Review

- `accepted` moves Run to `running`.
- Terminal state can be overwritten by late callback.
- Duplicate `eventId` creates duplicate state transition, audit event, artifact, or lease release.
- Stop is not idempotent.
- Heartbeat timeout does not converge Run and node lease.
- Force-kill failure returns node to Idle instead of quarantine/unavailable state.
- fake-runner lives outside `apps/runner` or does not reuse runner callback client/schema.
- Real SSH smoke is skipped for release/main merge without explicit waiver.

### 20.5 Storage and Security Review

- MinIO is mocked in all tests and never exercised as a real integration boundary.
- Path safety relies on frontend validation or path normalization as the primary defense.
- Unsafe filename/path cases are not tested.
- Private Load Node credentials are returned, logged, or snapshot-tested.
- Password hashing, session expiry, brute-force guard, CSRF, role authorization, or Workspace isolation lacks automated tests.
- Dependency File or Artifact download bypasses API and exposes MinIO URL or object key to Web.

---

## 21. AI Coding Rules

AI Coding tasks must follow these rules:

1. Read this document before implementing tests for any P0 Slice.
2. Read only the relevant Foundation SDD and Slice SDD for the current task; do not load unrelated full-document context by default.
3. Update contracts before implementing API/Web consumers when a contract changes.
4. Add or update tests in the same PR as implementation.
5. Run the relevant local command before final response; prefer `make verify` when feasible.
6. Report exact commands and outcomes.
7. Do not claim a Slice is complete unless its `Done When` is satisfied.
8. Do not add P1/P2 tests as a reason to implement P1/P2 code.
9. Do not replace missing tests with prose assurances.
10. Do not weaken coverage, contract, or security gates for convenience.
