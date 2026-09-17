# ADR-0018: P2 LAN-first Interactive Release Bootstrap

- Status: Accepted
- Scope: P2-06 first-run host/origin configuration for the tagged release bundle operated through
  `./surgepilot up`
- Active Slice: `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`
- Partial supersession: `ADR-0017` Decisions 7 and 8 for the release startup path only
- Partially superseded by: `ADR-0020-p2-release-dual-runtime-default` for the new-release Runtime
  default and interactive Runtime architecture prompt only
- Existing configuration confirmation amendment:
  `docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md` partially supersedes only
  conflicting existing-`.env` not-prompted/never-rewritten wording
- Related ADRs: `ADR-0007-p0-runtime-bootstrap-packaging`, `ADR-0012-p2-public-api-substrate`,
  `ADR-0017-p2-cross-platform-distribution`

## Context

ADR-0017 established a complete tagged release path with immutable GHCR image digests, Linux
Runtime release assets, release Compose, and one `./surgepilot up` lifecycle entry. Its default
topology was intentionally Demo-first: the bundled Demo Load Node used Compose-internal API and
InfluxDB origins, Demo was enabled by default, and `SURGEPILOT_RUNTIME_ARCHITECTURES=auto` acquired
the Docker daemon architecture only when Demo was enabled.

That topology proves the packaged stack, but it does not prove the primary private-network usage
expected from SurgePilot. A Compose-internal Demo can succeed while browsers or real Load Nodes on
the LAN cannot reach the API callback origin or InfluxDB node-write origin. Configuring the API
origin after startup also cannot retroactively change Compose port publication. The release can
therefore appear healthy without being usable for a real external Load Node.

The release path needs one explicit host address before services start, but automatic interface
selection is unsafe on hosts with Ethernet, Wi-Fi, VPN, virtual interfaces, policy routing, or a
remote Docker context. Requiring users to edit `.env` before their first command creates avoidable
evaluation friction. A Web first-run wizard would start too late to own host port publication and
would add API/UI/configuration scope unrelated to the deployment defect.

The operator may also be evaluating the product only on the deployment machine and may not need a
Load Node yet. Rejecting an explicitly selected canonical loopback address prevents that low-friction
first look without improving security. The release path therefore distinguishes a deliberate
loopback-origin choice from the normal LAN-ready choice instead of guessing an address or silently
claiming external-node readiness. This choice scopes only the persisted node-facing URLs: release
Compose still publishes Nginx and InfluxDB on host interfaces.

The revision must remain bounded. It must not reopen P2-05 artifact publication, add a downloader
or package manager, change source-checkout startup, or weaken P0/P1 security and execution
boundaries.

The existing `release-validation.yml` and tagged `release.yml` smoke jobs invoke `./surgepilot up`
non-interactively after extracting a fresh bundle. They are part of the impacted release path and
must pre-provision the new complete `.env` contract before startup. This requires fixture changes,
not a new workflow, trigger, permission, or publication action.

## Options Considered

### Option A: Interactive host-shell bootstrap with persisted LAN configuration

Accepted.

On a missing release `.env`, `./surgepilot up` asks the operator for one LAN host, HTTP port,
InfluxDB node-write port, and Runtime architecture set. A non-interactive helper validates and
persists the confirmed result before release services start. Demo is disabled by default, the
release requires explicit node-facing origins, and `auto` acquires the Docker daemon architecture
even without Demo.

This option makes the first successful release startup correspond to the intended LAN topology,
keeps one ordinary command, and avoids network discovery or a Web configuration subsystem.
Canonical loopback input is also accepted as an explicit local-only evaluation choice. It receives
an actionable warning that distinguishes URL usability from Docker port exposure, and never weakens
the non-loopback smoke or external-node acceptance path.

### Option B: Keep Demo-first startup and configure external connectivity later

Rejected.

This preserves the current packaging proof but allows an ordinary “successful” startup that has
not established a real callback or Monitoring write path. A later DB setting cannot publish a host
port or update the Compose process environment.

### Option C: Automatically detect and persist the primary host address

Rejected.

There is no portable, unambiguous primary address across multi-NIC, VPN, Docker Desktop, virtual
interface, policy-routing, and remote-context environments. Persisting a guessed address would
create hidden deployment state and misleading readiness claims.

### Option D: Require users and automation to create `.env` manually before first startup

Rejected as the ordinary user path.

It is deterministic but increases time-to-first-use and requires new evaluators to understand
deployment variables before seeing the product. A complete pre-provisioned `.env` remains the
required non-interactive/automation path.

### Option E: Add a Web first-run network wizard

Rejected.

The services and published ports must already exist before Web can load. A wizard would duplicate
deployment ownership in application APIs and UI without solving the pre-Compose ordering problem.

## Decision

1. Activate `P2-06 LAN-first Release Bootstrap Usability` exactly within
   `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`.
2. Limit the change to the tagged release path operated by `./surgepilot`; source-checkout
   `make start-full-stack` and source Compose internal defaults remain unchanged.
3. When release `.env` is missing, require an interactive host shell to collect one explicit
   host/IP, HTTP port, InfluxDB node-write port, and Runtime architecture value. The helper
   container remains non-interactive. Accept explicit `localhost`, `127.0.0.1`, or `::1` input as a
   local-only evaluation choice; keep the host field required and do not auto-select loopback.
4. When `.env` is missing and standard input or output is not a TTY, fail closed before deployment
   state or release services are created. Automation, including the existing release-validation and
   tagged-release smoke jobs, must pre-provision a complete valid `.env` before `./surgepilot up`.
   Node-facing smoke origins must be non-loopback and reachable from the smoke Load Node; using
   `localhost` is invalid even when a job explicitly enables Demo.
5. Persist the confirmed direct-LAN HTTP configuration atomically in `.env`, including matching
   published ports and node-facing origins, `SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false`,
   `SURGEPILOT_RUNTIME_ARCHITECTURES`, and `SESSION_COOKIE_SECURE=false`.
6. Treat `.env` as the only ordinary release deployment input after first run. Reject inherited
   process overrides for the persisted release quickstart values so Compose bindings, node-facing
   URLs, Demo selection, Runtime acquisition, and cookie policy cannot silently diverge.
7. Validate and normalize the inputs and prove required host-port availability before publishing a
   new `.env`. Existing `.env` and private state remain operator-owned and are never automatically
   repaired, migrated, overwritten, or rotated. Accept bare or singly bracketed IPv6 input and
   render exactly one bracket pair; reject mismatched, nested, empty, or zone-qualified forms.
   Reject legacy/non-canonical IPv4 spellings before treating an input as DNS. After IDNA
   normalization, repeat IP, legacy-notation, Compose-only, and loopback safety checks so Unicode
   lookalikes cannot bypass the canonical-host contract.
   A confirmed local-only origin remains valid on later `up` runs while Demo is disabled, but the
   wrapper must warn that other computers and external Load Nodes cannot use the configured URLs,
   while Docker still publishes the configured ports on host interfaces. Host firewall policy owns
   any requirement for local-only network exposure.
8. Require explicit release `SURGEPILOT_NODE_API_BASE_URL` and
   `SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL` values. Remove only their Compose-internal node-facing
   fallbacks; retain private service-to-service InfluxDB traffic required by API, Grafana, and
   health checks.
9. Publish the release Nginx host port and authenticated InfluxDB node-write host port in base
   release Compose by default. Raw API, Web, PostgreSQL, MinIO, and Demo SSH ports remain private.
10. Change release `SURGEPILOT_RUNTIME_ARCHITECTURES=auto` to resolve to the normalized Docker daemon
    architecture whether Demo is enabled or disabled. Cross-architecture external nodes require an
    explicit supported architecture set.
11. Disable Demo by default. If explicitly enabled, Demo uses the persisted LAN node-facing origins
    and does not restore internal node-facing fallbacks. Demo credential and SSH identity state are
    generated or validated only when Demo is enabled. Loopback node-facing origins remain invalid
    when Demo is enabled because loopback inside the Demo container does not identify the host.
12. Keep the existing P2-02 DB-backed `loadNodeApiBaseUrl` as an advanced post-bootstrap override
    with its current precedence. P2-06 adds no Web helper, route, schema, migration, or InfluxDB
    System Setting.
13. Define the interactive quickstart as trusted-LAN direct HTTP. Operator-managed HTTPS requires
    explicit final origins and `SESSION_COOKIE_SECURE=true`; P2-06 does not automate TLS, proxy,
    certificate, HSTS, or public-ingress configuration. Parse an explicit
    `SESSION_COOKIE_SECURE` with a dedicated strict `true`/`false` parser; invalid or empty values
    fail release preflight and API startup rather than silently disabling Secure cookies. When
    absent outside release Compose, retain the existing production-secure default.
14. Do not add historical release `.env` compatibility logic. An earlier or incomplete `.env`
    fails with actionable guidance and requires deliberate operator correction.
15. ADR-0024 supersedes the blanket platform-installer, downloader, `curl | sh`, installer-asset,
    and installer-validation-job exclusions in this decision. It authorizes only one
    version-pinned, user-local platform Release installer plus the existing separate interactive
    `surgepilot up`. Package managers, system installers, public workflow dispatch, new
    publication permissions, Docker installation, automatic upgrades, and standalone Public API
    AI skill distribution remain forbidden.
16. Preserve Runner protocol, Run state machine, Workspace isolation, RBAC, CSRF, server-side
    sessions, credential encryption, Monitoring token secrecy, Runtime integrity verification, and
    immutable Run snapshots.
17. Under ADR-0021 every valid release `up` displays the bounded non-secret effective
    configuration before Runtime fetch. Interactive startup uses default-Yes `[Y/n]`; No repeats
    first-run entry or, for existing standard-LAN state, opens a normalized confirmation loop that
    may change only the four allowlisted network fields. Non-interactive startup remains read-only,
    advanced HTTPS requires explicit manual editing, and source startup is excluded.

## ADR-0021 Supersession Boundary

`ADR-0021-p2-release-up-configuration-confirmation` supersedes only statements that a valid
existing release `.env` is not prompted over or can never be rewritten after any operator action.
Existing `.env` remains authoritative by default. It may change only after an interactive operator
selects No, enters valid standard-LAN host/port values, reviews their normalized form, and confirms
Yes; only the four allowlisted network fields may change through that path.

Automatic repair or migration, automatic and non-interactive rewriting, secret rotation,
non-target changes, and process overrides remain forbidden. Non-TTY startup prints the summary and
continues read-only. Advanced HTTPS is display-and-accept only and requires manual editing after No.
Source-checkout startup remains unchanged.

## ADR-0024 Supersession Boundary

`ADR-0024-p2-user-local-release-installer` supersedes only statements that forbid every platform
Release installer, downloader, `curl | sh` entry, checksum sidecar, or installer validation job.
It authorizes the exact-version POSIX installer, user-owned deployment root and launcher, bundle
sidecar, Linux/macOS install-only smoke, and installer-driven existing release smoke defined there.

This amendment does not change first-run host/port collection, TTY requirements, default-Yes
configuration review, Demo-off default, dual Runtime default, published ports, secret handling,
or any source-checkout startup behavior. The installer never calls `up` inside the pipeline.

## ADR-0020 Supersession Boundary

`ADR-0020-p2-release-dual-runtime-default` supersedes only the ADR-0018 statements that select
`auto` as the new tagged-release Runtime default or require interactive first-run setup to ask for
Runtime architectures. New tagged-release deployments instead persist `amd64,arm64` without that
prompt. Existing `.env` values, including `auto`, remain authoritative and accepted.

All other ADR-0018 decisions remain authoritative, including explicit LAN host and port
confirmation, the Demo-off default, strict cookie transport, authenticated InfluxDB publication,
the warned loopback-origin exception, all-interface published-port binding, non-interactive
complete `.env` fixtures, and preservation of existing deployment state.

## ADR-0017 Supersession Boundary

ADR-0017 remains Accepted for GHCR packages, GitHub Release assets, semantic tag publication,
immutable image digests, Runtime construction/download integrity, source/release separation, and
the bounded `./surgepilot` command surface.

This ADR supersedes only:

1. ADR-0017 Decision 7's release default of a Compose-internal Demo node-facing topology;
2. the part of ADR-0017 Decision 8 and P2-05 §11.4 where release `auto` acquires no Runtime when
   Demo is disabled;
3. P2-05 statements that Demo is enabled by default, only Nginx is published by default, or
   node-facing URLs are optional for the ordinary release startup;
4. P2-05 acceptance claims that use Demo success as the normal release readiness proof.

It does not supersede ADR-0017 as a whole and does not change source Compose behavior.

## Consequences

1. A first successful release startup has one operator-confirmed address and explicit API and
   InfluxDB node-facing origins before service startup. A non-loopback address is LAN-ready; an
   explicit canonical loopback address makes the persisted node-facing URLs local-only and is
   labeled as such. It does not make Docker's published-port bindings local-only.
2. Ordinary users still run one command and do not need to pre-edit `.env`; they must answer one
   required host question and may accept three defaults.
3. Non-interactive deployment becomes stricter because it must provide complete persistent
   configuration in advance. Existing release smoke jobs must be updated in the same implementation
   so CI does not fail on a missing `.env`.
4. Real external-node LAN acceptance replaces Demo success as the primary release usability proof.
5. Demo remains available as an explicit development aid but is no longer a dependency of ordinary
   bootstrap, Runtime selection, or readiness.
6. `auto` supports the common same-architecture external-node case but cannot infer a different
   target architecture; mixed environments remain explicit.
7. Publishing InfluxDB by default increases trusted-LAN exposure. Random token authentication,
   firewall guidance, and the prohibition on internet-facing HTTP bound but do not eliminate this
   risk.
8. Direct trusted-LAN HTTP requires `SESSION_COOKIE_SECURE=false` and provides no transport
   confidentiality. HTTPS remains an operator-managed advanced topology.
9. Raw `docker compose` becomes a less forgiving expert path because required node-facing values
   are no longer supplied by release internal fallbacks.
10. No new GitHub workflow, permission, trigger, artifact format, application API, database, Web
    route, or infrastructure is required. Existing release workflow smoke steps require bounded
    `.env` fixtures, and the existing tag-bundle job may upload the same bundle tar separately so a
    maintainer need not download both Runtime architectures merely to obtain the wrapper bundle.

## Related ADRs

- `docs/sdd/adr/ADR-0007-p0-runtime-bootstrap-packaging.md`
- `docs/sdd/adr/ADR-0012-p2-public-api-substrate.md`
- `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md`
- `docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md`
- `docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md`

## References

- `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`
- `docs/sdd/slices/P2-05-cross-platform-distribution.md`
- `docs/sdd/slices/P2-02-public-api-substrate.md`
- `docs/sdd/slices/P1-00-monitoring.md`
- `docs/sdd/00-product-scope-and-priority.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- `docs/sdd/06-security-permission-workspace.md`
- `docs/sdd/09-testing-and-acceptance-strategy.md`
- `scripts/release_preflight.py`
- `scripts/bootstrap_deployment_env.py`
- `infra/release/surgepilot`
- `infra/release/docker-compose.release.yml`
- `.github/workflows/release-validation.yml`
- `.github/workflows/release.yml`
- `AGENTS.md`
