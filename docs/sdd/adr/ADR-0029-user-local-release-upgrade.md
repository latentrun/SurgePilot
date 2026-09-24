# ADR-0029: User-local Release Upgrade Transition

- Status: Accepted
- Scope: Official `install.sh` user-local tagged-release transitions within one product major
- Baseline: `origin/main` at `e41d02c9e6ac99dde5d3bf88d7c39e00ff929a56`
- Proposed amendments: P2-05 Cross-platform Distribution and P2-06 LAN-first Deployment Usability
- Related ADRs: ADR-0017, ADR-0018, ADR-0020, ADR-0021, ADR-0024, and ADR-0027

This ADR is accepted. P2-05 and P2-06 synchronize its bounded installed-release transition and
authorize implementation within the constraints below.

## Context

ADR-0024 intentionally made an existing installation fail closed. After v1.1.0 was published, the
ordinary two-command installation flow could install a fresh release but could not transition an
existing v1.0.0 deployment to v1.1.0. Re-running `install.sh` therefore left the previous release
in place, and `surgepilot up` continued to report the previous product version.

The first supported upgrade must preserve the existing deployment root, Compose project, volumes,
`.env`, `.surgepilot/`, credentials, Admin and Workspace data, MinIO objects, Monitoring state, and
Demo identity. It must also respect active Run, Load Node initialization, lease, Run-control, and
report work. Database migration is forward-only: after target migration may have started, the
previous release must not be started automatically.

The design must remain smaller than a general updater. SurgePilot does not need a daemon, release
channel, compatibility registry, cleanup subsystem, rollback engine, package manager, or new
product interface.

## Options Considered

### Option A: Immutable release directories, one dispatcher, and one transition record

Accepted. Each release payload is published once under `.releases/vX.Y.Z`. A small dispatcher
selects the target wrapper from one atomic state file. The current deployed payload is never
rewritten in place.

### Option B: Replace release-owned files in place and commit by writing `VERSION` last

Rejected. Several `rename` operations do not form one transaction. A process crash or power loss
can leave a runnable mixture of wrappers, Compose files, scripts, and configuration from different
releases. It can also replace files that running containers bind-mount.

### Option C: Hold PostgreSQL table locks while stopping the previous control plane

Rejected as unnecessary complexity. The supported release topology exposes the API only through
Nginx. After Nginx, api-worker, and API are confirmed stopped and every source `api-migrate`
container is confirmed non-running, no supported PostgreSQL writer remains. A final read-only
probe after writer shutdown closes the race without a long-lived database transaction, FIFO
protocol, keepalive, or lock-timeout state machine.

### Option D: Automatically reclaim a process lock owned by a dead PID

Rejected. A portable POSIX-shell `read -> rename -> revalidate` reclaim has an ABA race: another
process can acquire a new lock between rename and revalidation, and a stale contender can then move
the new live lock. The design chooses fail-closed manual recovery instead of adding a host daemon,
platform-specific locking dependency, or custom native helper.

### Option E: Add an `upgrade`, `repair`, `unlock`, or `rollback` command

Rejected. The existing `install.sh` plus `surgepilot up|down|status|logs` interface is sufficient.
Recovery guidance may describe an explicit operator action without expanding the command surface.

## Decision

### 1. External interface

Fresh installation and upgrade retain the same two commands:

```sh
curl -fsSL https://github.com/latentrun/SurgePilot/releases/latest/download/install.sh | sh
surgepilot up
```

Their interface is:

- `install.sh` installs a fresh exact release or prepares one exact target release;
- `surgepilot up` starts a fresh release or applies the prepared target;
- `surgepilot up` never resolves `latest` or downloads another installer;
- the installer embeds `vX.Y.Z` and downloads only assets below `/releases/download/vX.Y.Z/`;
- `surgepilot down` remains non-destructive in every valid state, operates only on the
  state-selected source or target, and never deletes volumes;
- manually extracted bundles retain expert-managed `./surgepilot` transitions and do not use this
  installed-release state protocol.

The design adds no background check, automatic downgrade, database downgrade, or automatic
rollback.

### 2. Installed layout and ownership

The user-local deployment root becomes:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/surgepilot/
├── surgepilot                    # schema-1 dispatcher
├── .release-state                # atomic transition record
├── .releases/
│   ├── v1.1.0/                   # immutable legacy release payload
│   │   └── .surgepilot -> ../../.surgepilot
│   └── v1.2.3/                   # first published schema-1 release payload
│       ├── surgepilot-dispatcher
│       ├── surgepilot            # version wrapper
│       └── .surgepilot -> ../../.surgepilot
├── .env                          # deployment-owned
└── .surgepilot/                  # deployment-owned private state and Runtime cache
```

The deployment lock is the directory `${INSTALL_ROOT}.lock/` in the deployment root's parent.

Every `.releases/<version>` directory contains the complete release-owned bundle payload plus one
installer-created, exact relative `.surgepilot -> ../../.surgepilot` symlink. Existing Compose
files already resolve deployment-owned Runtime, secret, and Demo paths through that location. The
symlink is validated as part of the immutable directory; the deployment root and private-state
directory, when present, must themselves be owner-owned non-symlink directories. No other
compatibility overlay is introduced.

An existing version directory is never repaired or overwritten; a same-version installer verifies
every required member and fails on any difference. Old version directories are retained.
Automatic cleanup is outside this ADR.

The dispatcher artifact seam is fixed:

```text
repository infra/release/dispatcher -> bundle surgepilot-dispatcher
repository infra/release/surgepilot -> bundle surgepilot (version wrapper)
bundle surgepilot-dispatcher         -> deployment-root surgepilot
bundle surgepilot                    -> .releases/<version>/surgepilot
```

The schema-1 exact archive-member contract adds `surgepilot/surgepilot-dispatcher`; both bundle
executables must be non-symlink regular executable files. The bundle builder performs release
substitutions only in the version wrapper. The dispatcher has no release substitution and is
byte-identical in every schema-1 bundle.

The root dispatcher is deliberately small. It acquires the deployment lock, strictly parses
schema 1 state, overwrites the internal `SURGEPILOT_DEPLOYMENT_ROOT`,
`SURGEPILOT_RELEASE_ROOT`, and `SURGEPILOT_LOCK_NONCE` values, then `exec`s the target version
wrapper. The wrapper always receives the deployment root separately from its immutable release
root and passes the deployment `.env` explicitly to Compose. Containerized helpers mount the
deployment and release roots separately and do not use the Compose-only `.surgepilot` path bridge.
The dispatcher does not run Docker, download Runtime assets, or access PostgreSQL.

The schema-1 dispatcher is immutable. A fresh installer copies the checksum-verified bundled
dispatcher to the private deployment root before publication. Every later installer first requires
the installed dispatcher to be an owner-owned, non-symlink regular executable, then compares it
byte-for-byte with the checksum-verified target bundle copy and fails on any difference; it does
not replace the dispatcher. A future state schema or dispatcher change requires a separate
accepted design. This avoids a second transition protocol whose only purpose would be upgrading
the transition protocol.

Archive integrity and runtime identity are deliberately distinct. At install/prepare time, the
sidecar SHA256, exact archive-member list, required path/type checks, and payload validation anchor
the published release. A same-target installer compares existing archive-owned members with its
newly checksum-verified payload and fails on any difference. After installer publication, runtime
checks validate required path/type, version/revision consistency, image/OCI identity, API product
version, and health; they do not continuously cryptographically attest every release file.

Same-user manual mutation of release-owned files after publication is unsupported. Here,
`immutable` means SurgePilot never edits or repairs a published release directory; it is not a
claim that owner-writable local files have continuous cryptographic attestation. This narrower
interface avoids a second release-file hash registry that is not required by the current threat
model.

### 3. Module seams

The design has four modules with small interfaces:

1. installer: exact target assets in, atomically published target/state or a non-zero failure out;
2. dispatcher: lifecycle command plus state in, one selected version wrapper out;
3. version wrapper: `up|down|status|logs` in, one lifecycle result out;
4. transition probe: read-only database classification or active-work counts out.

The transition probe is an internal seam used only by the wrapper. It is not a product API, a
daemon, or a generic database administration framework.

### 4. Transition-state interface

`.release-state` is an owner-owned mode-`0600` non-symlink regular file. It contains exactly these
keys, once each, in this order:

```text
schema=1
phase=<installed|stable|unclassified|prepared|migration_started>
target=<vX.Y.Z>
base=<none|vX.Y.Z>
```

Unknown, missing, duplicate, reordered, or malformed fields fail closed. Values are parsed without
`eval`. A version has exactly one leading `v` and otherwise follows the canonical ADR-0027 product
version grammar.

The only valid cross-field states are:

| Phase | Required values | Meaning |
| --- | --- | --- |
| `installed` | `base=none` | Target is installed but no SurgePilot application schema has been established. |
| `stable` | `base` equals the exact `target` version | Target passed identity and health checks and is the database compatibility baseline. |
| `unclassified` | `base` is the exact lower same-major legacy source | Target and legacy payloads are immutable, but the legacy database has not been classified. |
| `prepared` | `base` is the exact lower same-major source | Target is immutable and the source database lineage is accepted. |
| `migration_started` | `base=none` or the exact lower same-major source | Target migration may have changed the database. Only the same target may run. |

No `applying`, `failed`, `deployed`, or sub-stage fields are persisted. Before migration, retry is
safe and actual Compose state is inspected on every invocation. After the durable
`migration_started` marker, every failure has the same conservative recovery rule. Volatile health
or error status belongs in command output and container logs, not in the transition record.

These are the complete state transitions; all others fail closed:

```text
absent                     -> installed(target, none)             # fresh install
legacy without state       -> unclassified(target, legacy source) # one-time bootstrap
stable(source, source)     -> prepared(target, source)            # later target installer
unclassified(target, source) -> installed(target, none)           # empty legacy database
unclassified(target, source) -> prepared(target, source)          # exact legacy heads
installed(target, none)    -> migration_started(target, none)
prepared(target, source)   -> migration_started(target, source)
migration_started(...)     -> stable(target, target)
```

An exact same-target installer may verify and leave any valid state unchanged. A different target
is accepted only from `stable`; it is rejected from `installed`, `unclassified`, `prepared`, or
`migration_started`. Missing/corrupt state has no recovery transition except the exact legacy
bootstrap recovery described below.

State publication writes and closes a private same-directory candidate, invokes the host `sync`
utility, atomically renames the candidate, and invokes `sync` again. A failed write, sync, or
rename returns non-zero and does not continue to the next transition step. This uses the existing
macOS/Linux base utility instead of adding a state-writing binary.

### 5. Deployment mutex

Installer commit and every installed lifecycle command use the same lock.

Acquisition is:

1. create a private owner candidate containing the complete record
   `schema=1`, `pid=<decimal>`, `nonce=<unique value>`;
2. atomically claim ownership with `mkdir -m 0700 "${INSTALL_ROOT}.lock"`;
3. atomically move the owner candidate to `${INSTALL_ROOT}.lock/owner`.

A crash before `mkdir` leaves no stable lock. A crash after `mkdir` may leave an incomplete stale
lock, which fails closed and uses the same manual recovery rule as every other stale lock. The
dispatcher exports the nonce and uses `exec`, so the version wrapper keeps the same PID. Before
release, either holder verifies the owner record still contains its PID and nonce, removes that
record, and removes the empty lock directory.

If the lock directory already exists:

- a valid record whose PID is live is busy;
- permission-denied liveness is conservatively busy;
- a dead PID is reported as a stale lock;
- a missing/malformed owner record, a non-directory/symlink lock path, wrong ownership, or wrong
  mode is reported as unsafe state.

The program never automatically renames or removes an existing lock directory. Stale-lock guidance
requires the operator to stop all SurgePilot installer/lifecycle commands, inspect the exact owner
record, and remove only the exact lock directory before retrying. PID reuse may conservatively
report busy; this is an availability trade-off, not a mutual-exclusion failure.

### 6. Fresh installation

Fresh installation retains ADR-0024's strongest publication property:

```text
download exact target
-> verify sidecar, exact archive members, manifest, wrapper, and dispatcher
-> place the complete bundle under .releases/<target> in a private deployment root
-> create the exact .surgepilot path bridge
-> copy the bundled dispatcher byte-for-byte to deployment-root surgepilot
-> write phase=installed, base=none
-> atomically publish the complete root
-> atomically publish the launcher
```

The first `surgepilot up` may create `.env`, private state, Runtime cache, and Compose resources.
Failures before target migration leave `phase=installed`; retry repeats the same target. Immediately
before a command can start target `api-migrate`, it publishes `phase=migration_started`.

After target identity and health pass, it publishes `phase=stable` with `base` equal to the exact
target version.

### 7. Stateful prepare

Network download and archive validation may occur outside the deployment lock. After acquiring the
lock, the installer rereads and validates the actual state and immutable payloads.

For `stable source -> target` it performs:

```text
validate stable state and byte-compare the installed dispatcher with the target bundle copy
-> require source < target, same major, and source within target range
-> publish immutable .releases/<target>
-> publish phase=prepared with base=source
```

Prepare does not modify `.env`, existing `.surgepilot/`, volumes, source payload, or running
containers. Re-run behavior follows the complete state rules above.

### 8. One-time v1.0.0/v1.1.0 bootstrap

The only supported legacy sources are the two actually published root-layout releases:
`v1.0.0` and `v1.1.0`. Their one-time bootstrap is available to any later same-major target whose
manifest still includes them in its supported upgrade range; it is not limited to `v1.2.3`.

`v1.0.0` predates ADR-0027 and reports API/Runner product metadata `0.1.0`, while `v1.1.0`
reports `1.1.0`. Source recovery and release validation use only this explicit historical mapping;
release identity remains `v1.0.0` or `v1.1.0` and is never inferred from package metadata.

The operator must not run another legacy `surgepilot` command concurrently with the target
installer or first target `up`. Those historical wrappers cannot be made to honor a future lock.
This one-time limitation is explicit; full installer/lifecycle serialization starts after the
schema-1 dispatcher is installed.

The target installer:

1. downloads the official source bundle and target bundle;
2. verifies the legacy release-owned files against the official source bundle;
3. publishes immutable source and target directories;
4. atomically replaces only the root wrapper with the exact target-bundled schema-1 dispatcher;
5. writes `phase=unclassified`, `base=source`.

The copied legacy wrapper is never executed; it is retained only as validated source payload. The
target wrapper owns classification, source Compose operations, restoration, and the transition.
Exact legacy release-owned files that already remain in the deployment root become inert after
dispatcher publication and are not deleted by this transition.

If the process stops before dispatcher publication, the legacy installation remains executable.
If dispatcher publication succeeds but state publication does not, lifecycle commands fail closed.
Only the same target installer may recover, and only when the launcher, root dispatcher, legacy
root version, official source directory, and exact target directory all match. Dispatcher recovery
requires byte equality with the newly checksum-verified target bundle copy. It writes the same
`unclassified/source` state; it never guesses from the highest directory version. Other installers
fail closed. Orphan release directories are inert and are not deleted automatically.

### 9. Legacy database classification

`unclassified` must become `installed` or `prepared` before target migration can start.

- If the official Compose project has no PostgreSQL container and no PostgreSQL named volume,
  publish `phase=installed`, `base=none`.
- If the volume exists, start only the source PostgreSQL container and wait for its health check.
- If the `public` schema contains neither `alembic_version` nor any ordinary/partitioned
  application table, publish `phase=installed`, `base=none`.
- If `alembic_version` exists, require its exact head set to equal the heads shipped by the official
  source API image. On equality, publish `phase=prepared`, `base=source`.
- Any other schema shape, head count, head value, or probe failure fails closed.

Matching Alembic heads proves only the supported migration lineage; it does not claim to detect
manual schema edits. An operator-modified schema remains unsupported and may require restoration
from backup.

The one-shot probe runs from the source API image and target-mounted helper with the exact shape:

```text
docker compose ... run --rm -T --no-deps \
  --volume <target-probe>:/tmp/release-transition-probe.py:ro \
  api /app/.venv/bin/python /tmp/release-transition-probe.py <mode>
```

`--no-deps` is mandatory: the probe must not start `api-migrate`, MinIO, Grafana, or another
dependency. The helper imports no target application models, uses only interfaces available in all
supported source API images, opens a read-only transaction, prints one bounded machine-readable
result line, and prints no secret or user payload.

The helper has a fixed 60-second total deadline from entrypoint, a 10-second PostgreSQL connection
timeout, a 10-second statement timeout, and a 5-second lock timeout. These are transition safety
bounds, not user settings. Timeout, a missing/extra result line, or any non-zero helper result is a
probe error and fails closed. If the source was already stopped, the wrapper follows the same
source-restoration rule as any other pre-migration failure.

### 10. Pre-migration active-work protocol

The source release remains available while target Runtime assets, target Compose validation, and
all target image pulls complete. Only then may `up` enter downtime.

For a known source that is running, the wrapper first runs a non-authoritative read-only probe. If
it finds active work, upgrade returns non-zero without stopping the source. A quiet result is only
an optimization; it does not authorize migration.

Before entering downtime, the wrapper also checks every container in the persisted Compose project
whose Compose service is `api-migrate`. If any source `api-migrate` container is running, upgrade
returns non-zero without stopping or killing it. The operator waits for the source migration to
finish or performs manual source recovery before retrying.

The authoritative sequence is:

```text
stop source nginx
-> stop source api-worker
-> stop source api
-> verify all three source writer/ingress containers are absent or stopped
-> require every source api-migrate container to be absent or stopped
-> run the final read-only active-work probe
```

The release API is not published directly, so stopping Nginx closes the supported ingress path.
API, api-worker, and `api-migrate` are the complete supported PostgreSQL writer set. After the first
two are stopped and every `api-migrate` container is confirmed non-running, no supported writer
remains. Existing API/worker transactions have committed or rolled back before container stop
completes, so the final probe has no TOCTOU with a supported writer and needs no table lock or
long-lived IPC.

If `api-migrate` is found running after downtime begins, the wrapper does not stop it, does not run
the final probe, keeps the pre-migration state, and returns non-zero with wait/recovery guidance.
This is fail-closed source-migration handling, not active-work restoration.

If the source was already down, the wrapper starts only source PostgreSQL and runs the final probe.
It does not start source Web/API merely to prove quiescence.

For `base=none`, the classified schema contains no work tables. The wrapper still confirms that
any legacy Nginx, api-worker, and API containers are absent or stopped and that no legacy
`api-migrate` container is running before publishing `migration_started`; it does not run the
active-work query against an absent schema.

The probe returns BLOCKED when any of these exists:

- `runs.state IN ('initializing', 'running', 'stopping')`;
- `run_node_allocations.state IN ('initializing', 'running', 'stopping')`;
- `node_leases.released_at IS NULL`;
- `run_control_requests.status IN ('pending', 'running')`;
- `load_node_initialization_attempts.status IN ('queued', 'running')`;
- `load_nodes.status IN ('initializing', 'busy')`;
- `load_nodes.current_run_id IS NOT NULL`;
- `run_report_summaries.parse_status = 'pending'`.

It prints only category counts. BLOCKED causes the wrapper to restore/converge the exact source
stack, validate source image identity and health, keep state `prepared`, and return non-zero. If
source recovery fails, target migration remains forbidden and the wrapper reports manual recovery
guidance. The upgrade path never force-kills active Runs or initialization work.

Any other failure after a known source was stopped but before `migration_started` uses the same
source-restoration rule. The exception is a still-running source `api-migrate`: the wrapper never
starts other source services around it and instead waits for operator retry after it exits. With
`base=none`, there is no valid source application stack to restore; state remains `installed` and
retry stays on the same target.

Immediately before the irreversible marker, the wrapper re-verifies that source ingress/writer
containers, including `api-migrate`, have not reappeared. A running `api-migrate` again fails closed
without being stopped. Raw Compose, direct database access, and a concurrently running legacy
wrapper are expert/operator actions outside this interface.

### 11. Migration and recovery

After classification is complete, the final probe is QUIESCENT, and source writers are confirmed
stopped, the wrapper durably publishes:

```text
phase=migration_started
```

Only then may target Compose start a command that can run `alembic upgrade head`.

From this marker onward:

- only the same target wrapper may run;
- the previous release is never started automatically;
- migration failure and target health failure both leave `migration_started` unchanged;
- retry reruns the same target's idempotent Alembic upgrade and startup;
- automatic database downgrade and rollback are forbidden;
- unrecoverable failure requires operator restoration from a pre-upgrade backup.

Target startup uses the persisted Compose project and volumes and converges them with the target
Compose configuration. It never uses `down -v`.

### 12. Stable commit and target identity

The wrapper publishes `stable` only after all of the following pass:

1. required containers belong to the persisted Compose project and expected Compose service;
2. target Compose was invoked from `.releases/<target>/compose/docker-compose.yml`;
3. required release paths have the expected regular-file, executable, directory, or exact bridge
   symlink type;
4. `VERSION`, manifest version/revision, and the version embedded in the wrapper agree with the
   target state;
5. every SurgePilot-owned running container uses the manifest's exact repository digest;
6. OCI version/revision labels equal the target release and manifest revision;
7. the API product-version probe returns target `X.Y.Z` under ADR-0027;
8. every required release health/readiness check passes.

This gate checks operational identity, not continuous file attestation. Exact release-file content
is anchored when the checksum-verified archive is published and whenever a same-target installer
revalidates it, as defined above.

A crash after health but before the stable commit leaves `migration_started`. On retry, passing the
same identity/health gate permits only the final stable state write.

### 13. Lifecycle matrix

| State | `up` | `status` | `logs` | `down` |
| --- | --- | --- | --- | --- |
| `installed` | first target deployment | installed, not stable | bounded target diagnostics | stop target containers without volumes |
| `stable` | normal target startup | normal | normal | normal, without volumes |
| `unclassified` | classify, then continue or fail closed | show target and base | base diagnostics | stop base containers without volumes; keep state |
| `prepared` | apply target | show target and base | base diagnostics | stop base containers without volumes; keep state |
| `migration_started` | same-target retry or finalize | show target transition | target diagnostics | stop target containers without volumes; keep state |
| missing/corrupt/unknown | reject | reject | reject | reject |

`status` and `logs` never mutate state. Installer and lifecycle commands reject process-level
overrides that could change persisted release identity, Compose project, Runtime selection, or
network behavior.

### 14. Upgrade range and release evidence

The target manifest adds one canonical field:

```json
{
  "minimumUpgradeVersion": "v1.0.0"
}
```

A transition source is supported only when it is lower than target, in the same major, and not
below the minimum. `base=none` is a first deployment. Downgrade and cross-major transition are
rejected.

The scalar minimum represents every canonical, non-draft, non-prerelease source release in the
same major and interval `[minimumUpgradeVersion, target)`. Formal publication enumerates and tests
every such source in running mode and additionally tests the newest supported source after a clean
`down`; it may not test only the endpoints. Later `v1.x` targets retain
`minimumUpgradeVersion=v1.0.0`. For the first implementation this means:

```text
v1.0.0 -> v1.2.3
v1.1.0 -> v1.2.3
```

The first release of a new major advertises its own target as the minimum. If no published
same-major source lies in that interval, its upgrade matrix is empty and formal publication still
requires the fresh-install release smoke. An empty matrix when the minimum is lower than the target
fails closed.

The publication workflow must complete those upgrade jobs before semantic image tags or the public
GitHub Release are finalized. Each job uses the published source assets, representative persisted
PostgreSQL/MinIO/credential/Workspace/Run data, the target candidate, a real Alembic transition,
and one post-upgrade Run.

Release notes at `docs/releases/vX.Y.Z.md` state the supported range, backup responsibility,
active-work refusal, same-target retry rule, absence of automatic rollback, and required Load Node
reinitialization.

### 15. Load Node Runtime and backups

After a successful control-plane transition, `LOAD_NODE_RUNTIME_VERSION` equals target. Existing
Load Nodes keep the previous recorded Runtime and remain ineligible until the operator explicitly
reinitializes them. The upgrade does not rotate or delete their credentials.

Control-plane ready and Run-execution ready are distinct. The wrapper and release notes must not
claim execution readiness while required Load Nodes still have the previous Runtime.

This ADR adds no backup engine. Before upgrade, the operator is responsible for PostgreSQL, MinIO,
and other persistent-volume backups that meet their recovery objective.

## Failure Safety and Acceptance

### Design-freeze conditions

Design freeze requires review agreement on this exact state grammar, immutable dispatcher rule,
dispatcher artifact seam, archive-versus-runtime integrity scope, manual stale-lock recovery, legacy
concurrency precondition, one-shot `--no-deps` probe, the complete writer set including
`api-migrate`, writer-stop/final-probe ordering, migration marker, target identity gate, and
supported range. Design freeze does not require implementation or release evidence.

### Implementation acceptance

Implementation must cover:

- strict state parsing and every allowed transition;
- fresh, stable, legacy, clean-down, and partial-source-stack paths;
- same-target retry and different-target rejection;
- lock contention, crash before/after lock-directory publication, holder-only release, and stale-lock
  fail-closed guidance;
- installer/lifecycle concurrency for schema-1 deployments;
- exact dispatcher source/bundle/install mapping, archive-member validation, and byte-identical
  later-release verification;
- legacy source/target payload validation and bootstrap crash points;
- exact legacy launcher ownership, mode, and content proof, including tampered-launcher refusal;
- classification for absent, empty, exact-head, partial, and unknown databases;
- proof that transition probes use `--no-deps` and never start `api-migrate`;
- connection, statement, lock, and total probe timeout failure paths;
- preliminary and final active-work checks, including non-terminal allocation state;
- source `api-migrate` running before downtime, appearing during downtime, and remaining untouched
  on refusal;
- source restoration on BLOCKED and failure before migration;
- crash before and after `migration_started` and before stable commit;
- archive publication integrity plus runtime path/type, version/revision, target digest, OCI
  identity, product version, and health checks;
- old Runtime rejection and explicit Load Node reinitialization;
- after target API startup and successful reconciliation, the active system Catalog metadata and
  stored OpenAPI expose the target product version alongside runtime OpenAPI, the AI skill snapshot,
  and the reinitialized Runner; Catalog reconciliation adds no release migration or stable gate;
- Linux and macOS installer, dispatcher, lock, and transition smoke;
- `make generate-contracts`, `make verify`, and applicable release validation.

Checks that cannot run must be recorded as `NOT VERIFIED`; physical power loss must not be claimed
from process-level fault injection.

### Release-publication acceptance

The first formal release additionally requires real v1.0.0 and v1.1.0 data upgrades, active-work
refusal, clean-down transition, Load Node reinitialization, existing native release smoke, reviewed
`docs/releases/v1.2.3.md`, the bounded historical product-metadata mapping above, and a publish job
that depends on all required upgrade jobs.

## Supersession Scope

If accepted, this ADR supersedes only:

- ADR-0024's rule that every existing installation must fail closed;
- P2-05/P2-06 wording that permits only manual replacement of release-owned files;
- the blanket exclusion of an official bounded user-local version transition.

It retains no sudo, no package manager, no Docker installation, exact-version downloads,
download/archive checksum integrity, immutable release lifecycle, image/Runtime identity, existing
`.env` and private state safety, no updater daemon, no background release checks, no automatic
downgrade, no database downgrade, no automatic rollback, no Runner protocol change, and no
Workspace/security weakening.

Manual bundle transitions, source-checkout startup, and raw Compose remain outside the installed
state protocol.

## Consequences

1. A normal user repeats the installation command and runs `surgepilot up`; no new command or
   setting is introduced.
2. Release payloads and state have one atomic commit point each; a crash cannot create a runnable
   mixed release.
3. Active work is checked authoritatively only after supported writers stop, so an attempted
   upgrade may cause a brief control-plane interruption before the previous release is restored.
4. A process killed while holding the host lock requires explicit stale-lock cleanup. This bounded
   recovery cost is preferred to an unsafe automatic reclaim algorithm or a new native dependency.
5. Forward database migration remains the only irreversible point and has one recovery rule.
6. Old release directories remain until an operator removes them; disk-retention automation is not
   part of the upgrade feature.

## Simplicity Review

The design deliberately removes the following from earlier drafts:

- `deployed`, `applying`, `failed`, and sub-stage state fields;
- a long-lived PostgreSQL table-lock transaction;
- FIFO/keepalive/release IPC and its timeout state machine;
- automatic stale-lock reclaim and PID-start fingerprinting;
- a second release-file hash registry and continuous local-file attestation;
- dispatcher self-upgrade and future-schema compatibility machinery;
- automatic payload cleanup, backup/restore, rollback, Load Node reinitialization, and repair.

The remaining modules pass the deletion test:

- deleting immutable release directories recreates multi-file transaction logic in the installer;
- deleting the exact `.surgepilot` path bridge misroutes deployment-owned paths in the existing
  Compose contract;
- deleting the dispatcher spreads state selection and locking across every version wrapper;
- deleting the transition record makes migration recovery guess from containers and files;
- deleting the one-shot probe spreads database knowledge into POSIX shell.

The wrapper remains a deep module: its existing four-command interface hides fresh installation,
legacy bootstrap, quiescence, migration, recovery, and normal lifecycle implementation. That depth
provides leverage to callers without adding commands, and locality keeps transition knowledge in
one wrapper instead of every installer and runbook. No remaining seam exists only to host a
hypothetical second adapter. The design reuses the existing API image, Compose project, wrapper
commands, Alembic migration, health checks, manifest, and release workflow.

## Related ADRs

- `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md`
- `docs/sdd/adr/ADR-0018-p2-lan-first-release-bootstrap.md`
- `docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md`
- `docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md`
- `docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md`
- `docs/sdd/adr/ADR-0027-product-version-and-artifact-identity.md`

## References

- `docs/sdd/slices/P2-05-cross-platform-distribution.md`
- `docs/sdd/slices/P2-06-lan-first-deployment-usability.md`
- `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- `docs/sdd/06-security-permission-workspace.md`
- `docs/sdd/09-testing-and-acceptance-strategy.md`
- `docs/releases/README.md`
- `infra/release/docker-compose.release.yml`
- `infra/release/install.sh`
- `infra/release/surgepilot`
- Docker Compose `run` reference: <https://docs.docker.com/reference/cli/docker/compose/run/>
