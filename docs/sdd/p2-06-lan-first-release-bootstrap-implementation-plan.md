# P2-06 LAN-first Release Bootstrap Implementation Plan

Every behavior change follows red-green-refactor; do not add a production behavior without first
observing its focused test fail.

**Goal:** Activate ADR-0018 and make the tagged release `./surgepilot up` establish one explicit,
persistent, LAN-usable node-facing topology before starting services.

**Architecture:** Keep the POSIX wrapper as the only ordinary release entry and reuse the pinned API
image for Python validation/bootstrap. The host shell owns TTY prompts only; `release_preflight.py`
owns normalization and validation; `bootstrap_deployment_env.py` owns atomic `.env`/secret state;
release Compose consumes required persisted values without node-facing internal fallbacks.

**Tech Stack:** POSIX `sh`, Python 3.12, pytest, Docker Compose, GitHub Actions YAML, FastAPI runtime
configuration.

**Execution status:** Tasks 1-5 are implemented. Task 6 local verification,
independent review, and review-finding fixes are complete. Focused release tests and repository
`make verify` pass locally, including 97% patch coverage. Branch completion requires the final
commit/push, successful GitHub PR CI, and the final PR description update.

## Global Constraints

- Release-only behavior; source `make start-full-stack` and source Compose defaults do not change.
- No new API route, database migration, Web UI, service, dependency, workflow, permission, trigger,
  publication action, downloader, installer, or Runtime catalog.
- User-visible messages and examples are English.
- Existing `.env`, secrets, Runtime files, and volumes are never silently repaired or overwritten.
- Direct quickstart is trusted-LAN HTTP; invalid security configuration fails closed.

---

### Task 1: Activate governance

**Files:**
- Modify: `docs/sdd/adr/ADR-0018-p2-lan-first-release-bootstrap.md`
- Modify: `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md`
- Modify: `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`
- Modify: `docs/sdd/slices/P2-05-cross-platform-distribution.md`
- Modify: `docs/sdd/slices/P2-README.md`
- Modify: `docs/sdd/02-repo-structure-and-dev-workflow.md`
- Modify: `AGENTS.md`

- [ ] Mark ADR-0018 Accepted and make P2-06 active.
- [ ] Record only the approved partial ADR-0017/P2-05 release-path supersession.
- [ ] Add P2-06 to the active-scope/context router without expanding unrelated P2 capability.
- [ ] Run `git diff --check`.

### Task 2: Release configuration primitives and API cookie policy

**Files:**
- Modify: `tests/test_release_preflight.py`
- Modify: `apps/api/tests/test_p0_00_services.py`
- Modify: `apps/api/tests/test_p0_00_auth_api.py`
- Modify: `scripts/release_preflight.py`
- Modify: `apps/api/app/core/config.py`
- Modify: `apps/api/app/services/sessions.py`

**Interfaces:**
- Produce: normalized bootstrap output with fixed keys for host, ports, URLs, Demo, Runtime set, and
  cookie mode.
- Produce: strict release environment validation and daemon-architecture `auto` resolution.
- Produce: `Settings.session_cookie_secure: bool`.

- [ ] Write failing tests for bare/bracketed IPv6, malformed brackets, ports, required environment,
  direct-LAN consistency, HTTPS advanced mode, strict cookie values, and Demo-off `auto`.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement the minimal normalization/validation and cookie-setting changes.
- [ ] Run focused tests to green and refactor without widening scope.

### Task 3: Atomic release `.env` bootstrap and optional Demo state

**Files:**
- Modify: `tests/test_bootstrap_deployment_env.py`
- Modify: `scripts/bootstrap_deployment_env.py`
- Modify: `infra/release/.env.example`

**Interfaces:**
- Consume: normalized explicit release values passed as CLI arguments.
- Produce: owner-only `.env` with the seven quickstart values and existing generated secrets.

- [ ] Write failing tests for CLI-provided release values, Demo-off state omission, Demo-on state,
  concurrent conflicting winners, and existing-state validation.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement CLI value persistence and conditional Demo state generation/validation.
- [ ] Run focused tests to green.

### Task 4: Release wrapper and Compose topology

**Files:**
- Modify: `tests/test_release_wrapper.py`
- Modify: `tests/contract/test_p2_05_distribution.py`
- Modify: `infra/release/surgepilot`
- Modify: `infra/release/docker-compose.release.yml`
- Delete: `infra/release/docker-compose.external-node.yml`
- Modify: `scripts/build_release_bundle.py`
- Modify: `infra/release/README.md`

**Interfaces:**
- Consume: preflight normalized output and persisted `.env`.
- Produce: interactive first-run prompt, non-TTY failure, base `8086` publication, Demo-off default,
  node-facing required values, bounded ready output.

- [ ] Write failing wrapper/contract tests for TTY/non-TTY behavior, confirmation, prompt ownership,
  process override rejection, ordering, port checks, output URLs, Compose fallbacks, and Demo profile.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement the minimal wrapper/Compose/bundle changes.
- [ ] Run shell syntax, wrapper tests, preflight/bootstrap tests, and Compose contract tests to green.

### Task 5: Existing CI smoke fixtures and release documentation

**Files:**
- Modify: `.github/workflows/release-validation.yml`
- Modify: `.github/workflows/release.yml`
- Modify: `tests/contract/test_p2_05_distribution.py`
- Modify: P2-05/P2-06 release documentation where implementation facts require synchronization.

- [ ] Write failing contract assertions that every non-interactive smoke creates a complete
  owner-only `.env` with non-loopback node-facing origins before `./surgepilot up`.
- [ ] Run the focused contract test and confirm failure.
- [ ] Update the two existing smoke fixtures without adding triggers, permissions, jobs, or
  publication behavior.
- [ ] Validate YAML and every shell `run` block; run the focused contract test to green.

### Task 6: Verification, independent review, and PR completion

**Files:** all touched files.

- [ ] Run focused Python, wrapper, bootstrap, Compose, and workflow tests.
- [ ] Run `make generate-contracts` if contract freshness requires it.
- [ ] Run `make verify`.
- [ ] Push and require GitHub PR CI to pass.
- [ ] Run an independent review covering design alignment, security, Workspace isolation,
  source/release separation, workflow permissions, P0/P1 regression, and over-design.
- [ ] Fix findings with regression tests, rerun verification, commit, push, and update the PR body.
