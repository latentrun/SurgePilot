# ADR-0007: P0 Runtime Bootstrap Packaging

- Status: Accepted
- Scope: P0 Load Node initialization, Runtime packaging, Runner execution, Taurus/JMeter execution path

## Context

P0 has completed the initial Load Node and Runner implementation work. The existing P0-03 Load Node design and implementation backfill still describe a node model where Taurus and JMeter are preinstalled on each Load Node and initialization checks system-level `bzt` and a configured JMeter path.

That model leaves P0 execution sensitive to host drift, system `PATH`, per-node Python/Taurus/JMeter differences, and Taurus automatic download behavior. P0 needs a repeatable and verifiable execution closure without turning runtime management into a product feature.

The engineering baseline is preserved in `docs/sdd/p0-runtime-bootstrap-plan.md`.

## Decision

P0 will package a self-contained SurgePilot runtime artifact during release and push that artifact to each Load Node during initialization.

The runtime artifact contains:

1. A complete python-build-standalone CPython tree, not only a virtualenv.
2. Taurus `1.16.50` and its Python dependency closure.
3. Apache JMeter `5.6.3`.
4. The exact current JMeter plugin closure required by generated Taurus/JMX and Monitoring:
   `jpgc-casutg`, `jpgc-json`, `jpgc-tst`, `bzm-random-csv`, and
   `jmeter-plugin-influxdb2-listener`.
5. `bin/bzt`, which invokes the runtime-contained Python and Taurus.
6. `metadata.json`.
7. A whole-archive SHA256 sidecar.

The runtime artifact is produced per packaging-machine architecture. P0 does not cross-build runtime artifacts. Architecture mapping is:

```text
x86_64 -> linux-amd64
amd64 -> linux-amd64
aarch64 -> linux-arm64
arm64 -> linux-arm64
```

Release artifacts use this shape:

```text
surgepilot-runtime-linux-<arch>-<version>.tar.gz
surgepilot-runtime-linux-<arch>-<version>.tar.gz.sha256
```

The deployment pipeline places the artifacts needed by the target environment into the api-worker local read-only directory:

```text
/opt/surgepilot/runtime-artifacts/
```

When no CI/release artifact job is available, the release process must provide an equivalent local packaging path. The exact production-builder and compatibility-gate workflow is deferred to a later checkpoint; R10 records only the artifact contract and Load Node bootstrap boundary.

api-worker reads from that directory and uploads the selected runtime archive to the Load Node through SFTP `upload_stream`. Load Nodes do not receive runtime download URLs or credentials and do not download runtime artifacts themselves.

## Runtime bootstrap rules

Load Node initialization must:

1. Connect by SSH using the stored credential boundary defined by P0-03.
2. Prepare and validate `runnerHome`.
3. Probe target architecture using `uname -m`.
4. Select a matching local runtime artifact by configured runtime version and detected architecture.
5. Fail safely if no matching artifact exists.
6. Upload the archive to `runnerHome/tmp/` through SFTP `upload_stream`.
7. Verify the whole-archive SHA256.
8. Safely extract into a temporary directory under `runnerHome`.
9. Reject absolute paths, `..` traversal, symlink escape, and writes outside `runnerHome`.
10. Validate `metadata.json` version, architecture, and component versions.
11. Check required files exist.
12. Run `<tmp-runtime>/bin/bzt -h`.
13. Run `<tmp-runtime>/apache-jmeter-5.6.3/bin/jmeter --version`.
14. Verify all five required plugin jars are valid archives and contain their contract classes.
15. Move the verified runtime to `runnerHome/runtimes/<version>/`.
16. Atomically update `runnerHome/current -> runnerHome/runtimes/<version>`.
17. Upload or verify the Runner bundle.
18. Probe Runner version.
19. Mark initialization successful only after the runtime and runner are usable.

Any failure before the final atomic `current` switch must leave the previous `current` runtime unchanged.

## Init-stage hard boundaries

During Load Node initialization, P0 must not run:

```text
pip install
python -m pip install
apt install
curl
wget
online plugin install
native extension compile
```

The initialization phase is therefore zero network, zero pip, and zero compile. It may require base OS dependencies that are explicitly documented as Load Node prerequisites, such as Java, system Python for `runner.py`, POSIX shell basics, and `tar`.

## Runner and Taurus execution rules

Runner must execute Taurus from the activated runtime, not from system `PATH`:

```bash
${RUNNER_HOME}/current/bin/bzt -n surgepilot.yml
```

The generated Taurus YAML must dynamically set JMeter to the selected Load Node runtime path:

```yaml
modules:
  jmeter:
    path: <runnerHome>/current/apache-jmeter-5.6.3/bin/jmeter
    version: "5.6.3"
    detect-plugins: false
    fix-log4j: false
    fix-jars: false
    force-ctg: false
```

`TAURUS_DISABLE_DOWNLOADS` is not the primary no-download mechanism. The primary mechanism is explicit `modules.jmeter.path` pointing to the active runtime JMeter. `-n` and optional environment guards are defense-in-depth only.

`force-ctg` defaults to `false` and is set to `true` only when a scenario uses `steps` and actually needs Concurrent Thread Group.

The CASUTG jar must retain the upstream `jmeter-plugins-casutg-*` filename because Taurus
`1.16.50` uses that prefix to decide whether Concurrent Thread Group is available. Runtime
compatibility smoke must cover CTG selection, stepped ramp-up, Target RPS shaping, random CSV,
and JSONPath, then parse the final generated JMX and fail when any fully qualified external JMX
class cannot be resolved from the Runtime JMeter jars. Plugins for JMX elements that SurgePilot
does not generate remain out of scope.

## Alternatives considered

### Keep Taurus and JMeter preinstalled on each Load Node

Rejected for P0 execution closure. It makes behavior depend on per-node host drift and system `PATH`, and it leaves too much ambiguity in initialization success.

### Install Taurus/JMeter during Load Node initialization

Rejected. It violates the init-stage hard boundary of zero network, zero pip, and zero compile, and it makes failure modes depend on package registries, mirrors, and native build behavior.

### Store runtime artifacts in MinIO

Rejected for P0. Runtime artifacts are deployment assets, not Workspace Dependency Files and not Run artifacts. Keeping them in a local read-only api-worker directory avoids exposing runtime download URLs or credentials to Load Nodes.

### Build both architectures in every release

Rejected for P0. P0 builds runtime artifacts on the packaging-machine architecture only. Environments that need both `linux-amd64` and `linux-arm64` can run separate architecture-specific release jobs and place both artifacts in the api-worker local artifact directory.

### Add runtime catalog, UI, upload, or version negotiation

Rejected as out of scope. P0 Runtime Bootstrap is execution-loop support, not a product runtime-management feature.

## Consequences

Positive consequences:

1. Load Node initialization becomes reproducible and verifiable.
2. P0 Run execution no longer depends on system `bzt` or system JMeter.
3. Taurus cannot silently fall back to an auto-downloaded JMeter path when generated YAML is correct.
4. Runtime publication remains a deployment concern rather than a Workspace asset concern.
5. Failed runtime installation cannot corrupt an existing activated runtime when atomic switch rules are followed.

Costs and constraints:

1. Release and deployment must manage runtime artifacts and sidecar SHA256 files.
2. Runtime artifacts are architecture-bound and must match target Load Node architecture.
3. Load Nodes still need documented base OS prerequisites; P0 does not automatically install Java, system Python, `tar`, or OS packages.
4. If Taurus `1.16.50` cannot smoke successfully with Python `3.12.x`, the release may fall back to Python `3.11.x`, but the reason must be recorded in this ADR follow-up and in runtime metadata.
5. P0 does not implement per-file checksum manifests, glibc parsing, qemu cross-architecture smoke, runtime UI, runtime catalog, gray release, or automatic cleanup.

## Required documentation updates

1. `docs/sdd/p0-runtime-bootstrap-plan.md` remains the implementation baseline and includes deployment artifact publication, version switching, and rollback boundaries.
2. Existing `docs/sdd/slices/P0-03-load-nodes.md` carries the Runtime Bootstrap update to the P0-03 Load Node initialization contract.
3. Existing `docs/sdd/00-product-scope-and-priority.md` remains the scope source that classifies Runtime Bootstrap as P0 execution-loop support, not a runtime-management product capability.

## References

- `docs/sdd/p0-runtime-bootstrap-plan.md`
- `docs/sdd/slices/P0-03-load-nodes.md`
- `docs/sdd/00-product-scope-and-priority.md`
- `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- `docs/sdd/adr/ADR-0002-runner-independent-app.md`
- `docs/sdd/adr/ADR-0006-p0-separate-api-worker.md`
