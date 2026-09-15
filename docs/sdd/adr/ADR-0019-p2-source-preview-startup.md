# ADR-0019: P2 Source Preview Startup

- Status: Accepted
- Scope: P2-05 source-checkout control-plane preview and source Runtime build observability
- Active Slice: `docs/sdd/slices/P2-05-cross-platform-distribution.md`
- Partial supersession: `ADR-0017` statements that excluded a source-only preview entry; its single
  complete tagged-release mode and `make start-full-stack` contracts remain unchanged
- Related ADRs: `ADR-0007-p0-runtime-bootstrap-packaging`, `ADR-0012-p2-public-api-substrate`,
  `ADR-0017-p2-cross-platform-distribution`, `ADR-0018-p2-lan-first-release-bootstrap`

## Context

The source-checkout `make start-full-stack` entry intentionally prepares a Linux Load Node Runtime
and starts the Compose-internal Demo Load Node. On a first run, both the Runtime builder and Demo
image may need network-dependent Java and operating-system packages. Slow registries or package
mirrors can therefore block access to the Web login page even when an evaluator only wants to
inspect the control plane.

The Runtime builder currently captures Docker output until the child process exits. A healthy but
slow build consequently appears stalled and gives the operator no phase or download progress.
`SURGEPILOT_SKIP_RUNTIME_PREFLIGHT=1` is an explicit manual/debug escape hatch, but it still follows
the full-stack target and Demo selection contract. It is not an appropriate public source-preview
interface.

The correction must remain source-only. It must not create a second tagged-release product mode,
change `./surgepilot`, weaken first-run secret persistence, change Runtime integrity, or alter any
P2-02 Public API, Workspace, permission, OpenAPI, AI skill, API, database, Web, Runner protocol, or
Run-state boundary.

## Options Considered

### Option A: Dedicated source `make start-preview` entry

Accepted.

This keeps the complete source and tagged-release contracts intact while giving explicit browser
review a bounded control-plane path. The preview reuses the source Compose topology with the Demo
profile inactive, does not prepare a Runtime, and reports that execution readiness is not promised.

### Option B: Rebrand the existing debug overrides as `start-full-stack-lite`

Rejected.

This would couple a user-facing command to a manual/debug flag, retain misleading full-stack output,
and use a name that implies both complete and incomplete readiness.

### Option C: Make `make start-full-stack` return before Runtime and Demo are ready

Rejected.

This would weaken its fail-fast readiness contract and introduce background failure and retry state.

## Decision

1. Add source-checkout `make start-preview` and `make stop-preview` entries.
2. `start-preview` runs the existing secure deployment bootstrap before applying process-local
   preview overrides. It never rewrites an existing `.env` or persists Demo-disabled state.
3. The preview clears native Compose profile activation, stops an existing Compose-internal Demo
   Load Node from a prior full-stack run, and then starts Web, API, api-worker, PostgreSQL, MinIO,
   Nginx, InfluxDB, and Grafana from the source Compose file without the Demo profile.
4. The preview does not invoke `make release-runtime` and explicitly clears Runtime version input.
   Setup Status may report `not_configured`; Load Node initialization and Run execution readiness
   are not part of the preview contract.
5. The preview mounts a dedicated empty Runtime directory created by the host user before Compose
   starts. The mount path must be absolute so the host preflight and Compose resolve the same
   directory, and it must be a real, empty, current-user-owned directory with mode `0700`; a
   relative path, symlink, file, non-empty directory, foreign owner, or unsafe mode fails closed. It
   must not let Docker create the normal Runtime output directory as root or contaminate a later
   `make start-full-stack` run.
6. `start-preview` validates explicit external API/InfluxDB URL pairs and validates the effective
   Compose configuration before startup. It retains source Compose-internal defaults and performs no
   host-interface discovery.
7. Startup output identifies Preview mode, prints the Web and Grafana URLs, states the missing
   Runtime/Demo readiness, and points to `make start-full-stack` for the complete execution demo.
8. `scripts/run_runtime_builder.py` streams Docker build and builder-container output while retaining
   captured output only for commands whose result must be parsed. Source full-stack startup prints
   bounded phase labels. No arbitrary build timeout is added.
9. Generic source startup remains `make start-full-stack`. Use `make start-preview` only when the
   user explicitly asks for login-page access, UI/page inspection, or control-plane preview without
   Runtime and Demo readiness.
10. The tagged release remains one complete `./surgepilot up` mode governed by ADR-0017/ADR-0018.

## Consequences

1. A source evaluator can reach the Web and Monitoring surfaces without first building Java-bearing
   Runtime or Demo images.
2. Preview startup still builds source API/Web images and may pull PostgreSQL, MinIO, InfluxDB,
   Grafana, and Nginx images; it is not an offline mode.
3. Preview and full source startup reuse the same deployment `.env`, Compose project, and data
   volumes so the evaluator can later switch to `make start-full-stack` without configuration
   migration.
4. The preview is an engineering/source-checkout entry, not a released product mode, release
   artifact, installer, or compatibility promise.
5. No API, OpenAPI artifact, generated contract, schema, migration, UI route, permission, Workspace,
   Runner, or Runtime packaging format changes.

## References

- `docs/sdd/slices/P2-05-cross-platform-distribution.md`
- `docs/sdd/00-product-scope-and-priority.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `docs/sdd/04-api-contract-guidelines.md`
- `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- `docs/sdd/06-security-permission-workspace.md`
- `docs/sdd/09-testing-and-acceptance-strategy.md`
- `Makefile`
- `scripts/run_runtime_builder.py`
