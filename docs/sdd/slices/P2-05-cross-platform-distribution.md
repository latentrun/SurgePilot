# P2-05 Cross-platform Distribution and Full-stack Release Bootstrap

- Document status: Accepted and active through `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md`, with source-preview startup amended by `docs/sdd/adr/ADR-0019-p2-source-preview-startup.md`, the new-release Runtime default amended by `docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md`, the user-local platform Release installer amended by `docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md`, product/artifact version identity amended by `docs/sdd/adr/ADR-0027-product-version-and-artifact-identity.md`, and bounded installed-release transitions amended by `docs/sdd/adr/ADR-0029-user-local-release-upgrade.md`; implementation backfill is recorded in §17.1.
- Phase: P2
- Capability: `cross_platform_distribution`
- Scope Gate: `docs/sdd/00-product-scope-and-priority.md` §7 deployment expansion, plus the open-source deployment success criteria in `docs/prd/PRD.md` §3.3 and §4.2
- Runtime Boundary: `docs/sdd/adr/ADR-0007-p0-runtime-bootstrap-packaging.md` and `docs/sdd/p0-runtime-bootstrap-plan.md`
- Repository and Deployment Boundary: `docs/sdd/02-repo-structure-and-dev-workflow.md`
- Runner Boundary: `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- Security Boundary: `docs/sdd/06-security-permission-workspace.md`
- Testing Boundary: `docs/sdd/09-testing-and-acceptance-strategy.md`
- Governance activation: `docs/sdd/adr/ADR-0017-p2-cross-platform-distribution.md`
- Source preview amendment: `docs/sdd/adr/ADR-0019-p2-source-preview-startup.md`
- Release startup amendment: `docs/sdd/adr/ADR-0018-p2-lan-first-release-bootstrap.md` and
  `docs/sdd/slices/P2-06-lan-first-deployment-usability.md` supersede the Demo-first/internal-origin
  release defaults, conditional InfluxDB publication, and Demo-off Runtime `auto` behavior only.
- Release Runtime default amendment: `docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md`
  supersedes only the inherited new-release `auto` default and first-run Runtime architecture
  prompt. Existing release `.env` files remain authoritative, and `auto`, `amd64`, `arm64`, and
  `amd64,arm64` remain accepted advanced values.
- Release configuration confirmation amendment:
  `docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md` partially supersedes only
  conflicting existing-`.env` not-prompted/never-rewritten wording. Every valid `up` displays the
  bounded non-secret configuration; interactive No/re-entry/Yes may update only four standard-LAN
  network fields, while non-interactive and advanced HTTPS behavior remains read-only/manual.
- User-local Release installer amendment:
  `docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md` supersedes only blanket platform
  installer/downloader exclusions. It authorizes a version-pinned POSIX installer, bundle checksum,
  user-owned launcher, and installer smoke while leaving `up` as a separate interactive command.
- User-local Release transition amendment:
  `docs/sdd/adr/ADR-0029-user-local-release-upgrade.md` supersedes ADR-0024's fail-on-existing-root
  rule only for its exact-target, same-major, forward-only installed transition. It preserves the
  existing command surface and excludes background updates, downgrade, and automatic rollback.

## 1. Core Decision

P2-05 defines one complete public release mode for SurgePilot on Linux and macOS development machines without creating separate preview, demo, minimal, or full release product modes. Source development remains a separate engineering path and may expose the control-plane-only `make start-preview` entry authorized by ADR-0019; it is not a second released product mode and does not claim Runtime, Demo, Load Node initialization, or Run execution readiness.

The public release contract is:

```text
GitHub Release bundle
  + exact-version install.sh and bundle SHA-256 sidecar
  + GHCR multi-architecture application images
  + GitHub Release linux-amd64/linux-arm64 Runtime artifacts
  + one complete surgepilot up entry
```

The default released stack includes Web, API, api-worker, PostgreSQL, MinIO, Nginx, InfluxDB,
Grafana, and the matching Linux Load Node Runtime. The Demo Load Node remains an optional explicit
development profile and is disabled by default under P2-06. A user who downloads a tagged release
bundle needs Docker Engine or Docker Desktop with Docker Compose, but does not need a host
installation of Python, Node.js, pnpm, uv, Java, Taurus, or JMeter.

Load Nodes and the Runtime remain Linux-only. macOS support means:

1. Apple Silicon and Intel Macs may run the Linux containerized control plane through Docker Desktop.
2. macOS may run Web, API, and api-worker host development workflows.
3. macOS is not a supported Load Node operating system.
4. Runtime artifacts built from macOS must be produced inside a Linux builder container and must never contain macOS executables labeled as Linux.

P2-05 does not create a runtime-management product, general installer platform, package manager,
orchestration platform, or automatic upgrade system. ADR-0024 and ADR-0029 authorize only one
bounded user-local installer and its explicit exact-target transition for this release bundle.

The complete product experience has two intentionally separate delivery paths:

1. A source checkout uses the source Compose configuration and `make start-full-stack`; it builds current source application images and builds or reuses a local development Runtime.
2. A tagged release may be installed through the version-pinned user-local installer and then uses
   the release Compose configuration through `surgepilot up`; a manually extracted bundle retains
   `./surgepilot up`. Both pull digest-pinned images and download matching semantic-version Runtime
   assets.

For explicit source login-page, UI, or control-plane review, `make start-preview` reuses the source
Compose file without the Demo profile or Runtime preflight. It retains the secure root `.env` and
data volumes but is not a complete delivery path or execution-readiness claim.

The paths may share bounded bootstrap and validation helpers, but they must not share one ambiguous effective Compose contract. Release Compose must not contain application build contexts or fall back to source builds, and source Compose is not governed by release-manifest digest pins.

## 2. Scope Trace

| Source                                  | Contract in this Slice                                                                                                                                                                                                                                                               |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `PRD.md` §3.3                           | Reduces open-source deployment friction and preserves the goal that a new user can complete a Visual Scenario Debug Run within 15 minutes after the platform is ready.                                                                                                               |
| `PRD.md` §4.2                           | Gives an open-source deployment user a low-threshold path to start SurgePilot, register the first Admin, inspect Setup Status, register a Load Node, and execute the normal product flow.                                                                                             |
| `00-product-scope-and-priority.md` §7   | Uses the P2 deployment-expansion boundary without activating unrelated enterprise login, storage, scheduling, or AI capabilities.                                                                                                                                                    |
| `02-repo-structure-and-dev-workflow.md` | Preserves Docker Compose, one root deployment `.env`, official Make development entries, first-run secret stability, and the standard full Monitoring stack.                                                                                                                         |
| `ADR-0007`                              | Keeps Runtime artifacts as architecture-specific deployment assets pushed from api-worker to Linux Load Nodes through the existing zero-network initialization boundary.                                                                                                             |
| `P2-02`                                 | Preserves `loadNodeApiBaseUrl` and official node-facing URL semantics. Its host-specific installer and release-publication exclusions continue to govern the Public API/AI skill capability; the portable platform release bundle proposed here is a separate deployment capability. |
| `P2-04`                                 | Keeps the authenticated request-built AI skill source zip as the only skill download. Platform images and Runtime artifacts introduced here are not an AI skill release channel and do not amend the skill source contract.                                                          |

## 3. Goals

1. Provide one complete tagged-release startup flow with a single normal user entry: `./surgepilot up`.
2. Publish SurgePilot-owned application images for `linux/amd64` and `linux/arm64` to GitHub Container Registry.
3. Publish release-grade Linux Runtime archives for `linux-amd64` and `linux-arm64` as GitHub Release assets with whole-archive SHA256 sidecars.
4. Allow Apple Silicon users to run the complete stack natively through Linux arm64 containers without forced amd64 emulation.
5. Allow Linux amd64 and Linux arm64 hosts to use the same release bundle and command surface.
6. Keep source development supported on Linux and macOS while preserving Linux-only Runner/Load Node behavior.
7. Reuse current bootstrap, Runtime validation, Compose, Monitoring, and SSH initialization behavior instead of introducing parallel implementations.
8. Keep release and startup failure behavior fail-closed, actionable, and non-destructive to existing deployment state.

## 4. In Scope

### 4.1 Public release artifacts

1. Multi-architecture GHCR image publication for API/api-worker/migration, Web, and the Demo Load Node.
2. A tagged GitHub Release bundle containing the supported Compose files, deployment template, bounded helper scripts, and the `surgepilot` command wrapper.
3. Separate GitHub Release Runtime archives and SHA256 sidecars for `linux-amd64` and `linux-arm64`.
4. Semantic-version alignment across the published release bundle, SurgePilot-owned release images, published Runtime metadata, and GitHub Release tag without changing local development Runtime version semantics.
5. Immutable multi-architecture image digest references in the released Compose configuration and release manifest.
6. One version-pinned POSIX `install.sh` plus a SHA-256 sidecar for the versioned platform bundle.

### 4.2 One complete startup path

1. `surgepilot up` performs preflight, secure first-run configuration, Runtime selection/download/verification, image pull, Compose validation, startup, health waiting, and final next-step output. A manually extracted bundle uses `./surgepilot up`.
2. `surgepilot down`, `surgepilot status`, and `surgepilot logs` provide the minimum installed lifecycle surface; manually extracted bundles retain the `./surgepilot` spelling.
3. The default stack includes P1 Monitoring and explicit LAN-reachable node-facing origins produced
   by the P2-06 first-run bootstrap.
4. The optional Demo Load Node remains available through the existing profile and registration
   contracts but is not part of ordinary first-use readiness.
5. An operator may explicitly enable Demo through the persisted deployment environment while
   continuing to use the same `./surgepilot up` entry.

### 4.3 Runtime build and fetch corrections

1. Move release-grade Runtime construction behind a Linux builder container.
2. Make local `make release-runtime` produce a Linux artifact matching the Docker builder architecture on Linux and macOS while preserving its development/fixed-version behavior.
3. Build both release architectures in separate native Linux release jobs.
4. Add a bounded release-asset fetch helper that downloads atomically, validates the whole-archive SHA256, validates archive metadata, and writes the existing Runtime environment file shape.
5. Let the release bootstrap acquire the architecture set declared by deployment configuration without adding a Runtime UI, catalog, or separate user mode.

### 4.4 Cross-platform development corrections

1. Keep Mode A host development available on Linux and macOS for Web, API, and api-worker.
2. Make `make start-full-stack` use the Linux Runtime builder path rather than host-native Runtime executables.
3. Replace Linux-only host verification commands in the default `make verify` path with portable Python or Docker-backed checks where practical.
4. Keep source startup semantics unchanged while the release path uses the P2-06 interactive
   first-run LAN inputs rather than automatic interface discovery or Compose-internal node-facing
   defaults.
5. Add automated and manual platform acceptance coverage defined in §15.
6. Provide `make start-preview` as a source-only control-plane entry that leaves
   `make start-full-stack` and `./surgepilot up` readiness unchanged, and stream Runtime builder
   output so complete source startup remains observable during network-dependent work.

## 5. Out of Scope

P2-05 must not implement:

1. Kubernetes, Helm, Docker Swarm, Nomad, Terraform, cloud-specific deployment modules, or another orchestrator.
2. A native macOS application, DMG, PKG, launch daemon, menu bar application, or native Load Node.
3. Homebrew, apt, yum, winget, Chocolatey, or another package-manager distribution.
4. Windows control-plane or Windows Load Node support.
5. A single all-in-one image that combines Web, API, databases, object storage, Monitoring, and Runner processes.
6. Background or channel-driven application updates, downgrade, automatic rollback, or migration
   orchestration outside ADR-0029's explicit bounded installed-release transition.
7. Runtime UI, Runtime Catalog, Runtime upload API, version negotiation, gray release, automatic cleanup, or automatic rollback.
8. Runtime storage in MinIO, Dependency Files, Run artifacts, the database, or another product-managed storage surface.
9. Load Node direct download of Runtime assets or GitHub credentials; api-worker remains the component that pushes Runtime through SFTP.
10. Cross-compiling or QEMU-validating a release-grade Runtime as a substitute for native architecture release jobs.
11. Publishing the Public API AI skill source as a GitHub Release, GHCR artifact, marketplace package, SDK, MCP server, or installer.
12. Docker Hub mirroring, multiple public registries, image signing, SBOM publication, provenance attestation, or vulnerability-management UI in this Slice.
13. API routes, new product-schema migrations outside ADR-0029 transition execution, new product
    tables, new RBAC, new Web product pages, or automatic Demo Load Node database seeding.
14. Changing the Runner protocol, Run state machine, Workspace semantics, storage backend, or existing Load Node credential boundary.
15. Resumable same-version release publication, draft reconciliation, or byte-for-byte continuation of a partially published release.
16. Package-manager/system installers, Docker installation, `sudo`, shell-startup-file mutation,
    background update/automatic rollback/uninstall, or a one-pipeline install-and-start command.
    The bounded ADR-0024 installer and ADR-0029 exact-target transition are the only exceptions.

## 6. Platform Support Contract

### 6.1 Supported matrix

| Surface                              | linux/amd64              | linux/arm64              | macOS arm64                                 | macOS amd64                                  |
| ------------------------------------ | ------------------------ | ------------------------ | ------------------------------------------- | -------------------------------------------- |
| Released containerized control plane | Required                 | Required                 | Required through Docker Desktop linux/arm64 | Supported through Docker Desktop linux/amd64 |
| Host Web/API/api-worker development  | Required                 | Required                 | Required                                    | Supported                                    |
| Host Runner execution                | Linux only               | Linux only               | Not supported                               | Not supported                                |
| Load Node                            | Ubuntu 24.04 / Debian 12 | Ubuntu 24.04 / Debian 12 | Not supported                               | Not supported                                |
| Runtime artifact target              | `linux-amd64`            | `linux-arm64`            | Uses `linux-arm64` inside Linux Load Nodes  | Uses `linux-amd64` inside Linux Load Nodes   |

### 6.2 Architecture selection

New missing-`.env` tagged-release deployments persist `amd64,arm64` and therefore select both
official Runtime architectures without an operator architecture decision. The accepted advanced
value `auto` maps from the actual Docker daemon architecture, whether Demo is enabled or disabled,
as follows:

```text
x86_64 | amd64  -> linux-amd64
aarch64 | arm64 -> linux-arm64
```

The Docker daemon platform, not host `uname`, is authoritative because Docker may use a remote
context. Unknown architectures fail before Runtime download or Compose startup. When Demo is
explicitly enabled, the bootstrap also rejects a conflicting forced platform rather than silently
using emulation.

### 6.3 Compatibility meaning

Container image availability alone is not acceptance evidence. A supported architecture requires:

1. successful application image build;
2. successful Compose configuration and health startup;
3. successful first Admin registration;
4. successful external Linux Load Node registration and initialization over the configured LAN
   origins;
5. successful Runtime installation;
6. successful real Debug Run through Taurus/JMeter;
7. accessible Run Report and Monitoring entry.

Official release compatibility is limited to Ubuntu 24.04 and Debian 12 until the maintained native compatibility matrix explicitly adds another distribution release. Newer distribution versions are best-effort rather than implied by a `+` suffix.

### 6.4 Host tool baseline

The release wrapper supports POSIX `sh` and the base utilities normally present on supported Linux and macOS hosts. It must not require GNU-only flags or macOS-incompatible shell extensions.

The minimum public baseline is Docker Engine 26 or newer with Docker Compose v2.27 or newer, or Docker Desktop providing the same Engine/Compose capability baseline. `./surgepilot up` validates the actual Docker daemon and Compose versions before pulling Runtime assets or mutating Compose state.

## 7. Public Release Contract

### 7.1 SurgePilot-owned images

The release publishes these conceptual package names under the GHCR namespace selected by the activation ADR:

```text
surgepilot-api
surgepilot-web
surgepilot-demo-node
```

Rules:

1. `surgepilot-api` is reused by `api`, `api-worker`, and `api-migrate`; do not publish three duplicate application images.
2. Every public release image index has `linux/amd64` and `linux/arm64` manifests.
3. SurgePilot-owned images include OCI source, revision, and version labels.
4. PostgreSQL, MinIO, Nginx, InfluxDB, and Grafana continue to use their upstream images; SurgePilot does not rebuild or republish them. If an upstream registry stops anonymous pulls, an externally maintained mirror may be used only when it serves the identical
   immutable upstream OCI digest.
5. Release Compose pins each SurgePilot-owned image by the immutable multi-architecture OCI index digest recorded in the release manifest. Semantic-version and `latest` tags may exist for discovery but are not the deployment integrity boundary.
6. Release publication must fail if the semantic-version tag already exists, regardless of whether its digest matches; release tags are never resumed, moved, or overwritten by the P2-05 workflow.
7. Public release packages allow anonymous pulls after the open-source release. Private prerelease testing may keep package visibility private without changing artifact contents.
8. Pull requests build without pushing. Publication occurs only from an explicitly authorized release workflow.

### 7.2 Published release and local Runtime version contracts

All artifacts published as one public release share one `vX.Y.Z` semantic version such as `v0.3.0`:

| Artifact                 | Version rule              |
| ------------------------ | ------------------------- |
| GitHub Release           | `v0.3.0`                  |
| Release bundle           | `surgepilot-v0.3.0.tar.gz` |
| API image                | `v0.3.0`                  |
| Web image                | `v0.3.0`                  |
| Demo Load Node image     | `v0.3.0`                  |
| Runtime metadata version | `v0.3.0`                  |
| Runtime filename version | `v0.3.0`                  |
| Release manifest version | `v0.3.0`                  |

A release bundle must not mix images or Runtime assets from another published version. `release-manifest.json` records the release version, source commit, multi-architecture image index digests, and Runtime asset SHA256 values. Commit-SHA tags may also be published for traceability but do not replace the semantic release tag or digest pins.

ADR-0027 separates this release-artifact identity from product metadata. The root `VERSION`, API
OpenAPI, Runner, system Catalog, public OpenAPI, and AI skill snapshot use canonical `X.Y.Z` without
`v`. Formal release images receive `SURGEPILOT_VERSION=vX.Y.Z` for the OCI version label and
`SURGEPILOT_PRODUCT_VERSION=X.Y.Z` for API runtime metadata. Release preflight requires the tag to
equal `v` plus root `VERSION`.

This semantic-version contract applies to published release artifacts only. Source and local verification paths preserve the existing Runtime builder semantics:

1. `make release-runtime` defaults to `dev-<manifestHash>` and may retain the existing `<RUNTIME_RELEASE_PREFIX>-<manifestHash>` development form.
2. `scripts/release_runtime_artifact.py --fixed-version <version>` remains valid for bounded E2E, compatibility, and release jobs; a public release job supplies the exact `vX.Y.Z` value.
3. Runtime `manifestHash` is only an internal deterministic build-input integrity/reuse validation value, not a public product version and not a requirement that every environment use semantic versions.
4. Whole-archive SHA256 and the digests recorded in `release-manifest.json` remain the published artifact integrity boundary.

### 7.3 Release bundle contents

The bundle contains only the bounded files needed to start and operate the released stack:

```text
surgepilot/
├── surgepilot
├── .env.example
├── release-manifest.json
├── compose files and required Nginx/MinIO/Grafana configuration
├── scripts/bootstrap_deployment_env.py
├── scripts/fetch_runtime_release.py
└── README.md
```

Exact final paths may follow repository conventions. The implementation backfill must record them.

The archive filename is versioned, but its top-level deployment directory is stable. `.env`, `.surgepilot/`, and named Compose volumes are deployment state and are never members of the release archive, so replacing release-owned files in the same deployment root does not replace state.

The Release also contains `install.sh` and `surgepilot-vX.Y.Z.tar.gz.sha256` beside the versioned
archive. The installer embeds `vX.Y.Z`, validates that sidecar, publishes the archive below
`${XDG_DATA_HOME:-$HOME/.local/share}/surgepilot`, and creates
`$HOME/.local/bin/surgepilot`. It never calls `up`.

The bundle must not contain source application trees, `.git`, a pre-generated `.env`, credentials, database data, MinIO data, Monitoring tokens, Runtime archives, node private keys, or user data.

## 8. Release Full-stack Startup Contract

### 8.1 User command surface

The normal release command surface is intentionally small:

```bash
surgepilot up
surgepilot down
surgepilot status
surgepilot logs
```

For a manually extracted archive, prepend `./` to the same four commands.

The normal new-release default is `SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64`. Existing or
pre-provisioned `.env` files may retain any accepted advanced architecture value; this configuration
does not add another public command surface or Runtime product capability.

### 8.2 `up` ordering

`./surgepilot up` performs these steps in order:

```text
validate Docker and Compose
  -> require a TTY for a missing .env and collect explicit LAN/port inputs
  -> pull the pinned API image needed for bootstrap helpers
  -> first run: normalize, display, and default-Yes confirm in a repeatable input loop
  -> existing .env: validate and display the bounded non-secret effective configuration
       -> non-TTY or interactive Yes/default: continue read-only
       -> interactive No plus standard LAN: normalize, display, and confirm a four-field proposal
       -> interactive No plus advanced HTTPS: fail with manual-edit guidance
  -> validate both required host ports
  -> create first-run state or explicitly update four existing network fields; new .env files
     persist amd64,arm64
  -> validate the complete persisted release environment
  -> fetch or reuse every Runtime release asset selected by the persisted configuration
  -> verify Runtime SHA256, metadata version, platform, and architecture
  -> validate full release Compose configuration
  -> pull all pinned images
  -> start the full stack
  -> wait for bounded health readiness
  -> print the persisted LAN Web/Grafana/API/InfluxDB URLs and lifecycle commands
```

Rules:

1. Bootstrap or Runtime failure occurs before Compose startup side effects.
2. A restart or repeated `up` is read-only by default. Only interactive No, valid standard-LAN
   re-entry, normalized review, and Yes may replace the four allowlisted network assignments;
   Monitoring token state, Demo Load Node credential/host-key state, Runtime selection, secrets,
   and every other `.env` value remain unchanged.
3. `COMPOSE_PROJECT_NAME` is generated or persisted in the root `.env`, defaults to `surgepilot`, and remains stable while volumes are reused. Operators running multiple deployments must choose distinct persisted project names.
4. `down` stops/removes containers and networks but does not delete named volumes, `.env`, `.surgepilot/`, Runtime files, or Demo SSH identity.
5. A manually extracted bundle uses the expert-managed replacement of release-owned files in the
   same stable deployment root. An installer-managed deployment uses only ADR-0029's bounded
   prepare-then-`up` transition, including preflight, quiescence, forward migration, and stable
   publication. Neither path adds a background update command or rollback engine.
6. Generated secret plaintext must not be printed by normal startup.
7. Health timeout returns non-zero and prints the failing service plus safe diagnostic commands.
8. Raw `docker compose` remains an expert/manual path, not the public quickstart promise.

### 8.3 Full service topology

The default effective release stack contains:

```text
web
api
api-worker
api-migrate
postgres
minio
minio-init
nginx
influxdb
grafana
```

The release Compose file also contains `demo-load-node` behind the explicit `demo` profile. Nginx
and authenticated InfluxDB node-write ports are published from the base release stack using the
persisted P2-06 values. Raw API, Web, PostgreSQL, MinIO, MinIO Console, and Demo SSH ports remain
private. Source development and automated E2E profiles may retain their explicit
test/development ports.

## 9. Demo Load Node Contract

1. The Demo Load Node is a real Linux SSH node image containing only documented Load Node prerequisites such as sshd, Java, system Python, tar, and POSIX tools.
2. It must not contain a separately built Taurus/JMeter Runtime. Initialization must exercise the same released Runtime upload, checksum, safe extraction, validation, Runner bundle, and atomic activation path used by real nodes.
3. It lives on the Compose network and does not publish SSH to the host by default.
4. The user registers and trusts it through the existing Load Node UI; P2-05 does not seed a Load Node record or bypass SSH host-key trust.
5. The published image contains no usable default password, SSH host private key, or installation-specific credential.
6. Its password and SSH host keypair are generated once per deployment, stored in private ignored deployment state, and mounted read-only or through an equivalent least-privilege mechanism.
7. Demo SSH host keys remain stable across container recreation while the deployment state is retained, so an existing trusted fingerprint is not invalidated by normal `down`/`up`.
8. Two independent deployments generate different passwords and SSH host fingerprints.
9. When Demo is explicitly enabled, startup prints its host, port, username, and private
   credential/host-key state paths, but not generated secret or private-key plaintext.
10. The Compose service hostname must be accepted by the existing registration/SSH path and remain stable within the release bundle.
11. Demo uses the same persisted LAN API and InfluxDB origins as external Load Nodes; it does not
    restore Compose-internal node-facing fallbacks. The selected LAN address must therefore be
    routable from the Demo container when Demo is enabled.
12. `SURGEPILOT_DEMO_LOAD_NODE_ENABLED` defaults to `false` in the public release bundle and does
    not enter DB-backed System Settings or Web UI.
13. Demo password and SSH identity state are generated or validated only when Demo is explicitly
    enabled.

## 10. Deployment Bootstrap and Secret Handling

### 10.1 No host Python requirement

The public release must not require host Python. The wrapper first pulls the pinned API image and runs the repository-owned bootstrap helper inside that container with the release directory bind-mounted and the host user's UID/GID where supported.

The existing bootstrap invariants remain mandatory:

1. one root `.env` is the normal deployment source;
2. first-run creation is concurrency-safe and fail-closed;
3. existing `.env` and secret files are never overwritten or repaired automatically; ADR-0021's
   explicit interactive path may update only four allowlisted network assignments after a final
   reviewed-content SHA-256 check using a private same-directory candidate and standard
   `os.replace`; simultaneous manual same-user editing in the final syscall window is unsupported,
   with no strict CAS, backup, or automatic rollback;
4. MinIO identity/password pairs remain consistent;
5. `SSH_CREDENTIAL_ENCRYPTION_KEY` remains stable while data volumes are reused;
6. secret files are non-symlink regular files with owner-only permissions;
7. generated secrets are not printed or committed.

### 10.2 New Demo SSH state

The Demo Load Node credential and SSH identity follow the same ignored private-state model as the Monitoring token:

```text
.surgepilot/secrets/demo-load-node-password.secret
.surgepilot/demo-load-node/ssh_host_ed25519_key
.surgepilot/demo-load-node/ssh_host_ed25519_key.pub
```

Exact filenames may follow the existing SSH image conventions, but private keys and password state must remain private deployment files rather than active `.env.example` plaintext values, DB settings, API responses, Web bundles, image layers, or GitHub Release members. Public host keys may be inspected for registration trust, but the private host key must never be returned by API or printed.

## 11. Runtime Build and Distribution Contract

### 11.1 Runtime remains a Linux deployment asset

P2-05 does not change the Runtime contents or Load Node installation model from ADR-0007. The archive still contains self-contained CPython, Taurus, JMeter, required plugins, wrappers, metadata, and the whole-archive SHA256 sidecar.

Load Nodes still receive Runtime through api-worker SFTP. They never receive a GitHub URL, release token, registry token, or Runtime download credential.

### 11.2 Linux builder container

Release-grade construction runs inside a dedicated Linux builder image or equivalent Docker build stage containing the build prerequisites and Java smoke environment.

Rules:

1. macOS host binaries must never enter a Runtime archive.
2. The builder's actual Linux architecture determines `linux-amd64` or `linux-arm64` metadata.
3. `bzt -h`, JMeter version, required plugin classes, manifest hash, metadata, and archive checksum are validated inside Linux before publication.
4. Local development builds only the current Docker architecture.
5. Release publication builds amd64 and arm64 in separate native Linux jobs.
6. The existing stable manifest/reuse validation remains authoritative for development builds.

### 11.3 GitHub Release assets

Each release publishes:

```text
surgepilot-runtime-linux-amd64-v0.3.0.tar.gz
surgepilot-runtime-linux-amd64-v0.3.0.tar.gz.sha256
surgepilot-runtime-linux-amd64-v0.3.0.manifest.json

surgepilot-runtime-linux-arm64-v0.3.0.tar.gz
surgepilot-runtime-linux-arm64-v0.3.0.tar.gz.sha256
surgepilot-runtime-linux-arm64-v0.3.0.manifest.json
```

The fetch helper must:

1. select the expected exact asset names from the pinned release version;
2. download to a private temporary file in the target directory;
3. follow redirects only when every redirect target and the final origin belong to the fixed allowlist of official GitHub and GitHub release-asset origins;
4. verify the SHA256 sidecar against the archive;
5. verify that the sidecar digest and actual archive digest both equal the Runtime digest recorded in the bundle's `release-manifest.json`;
6. verify metadata name, version, `platform=linux`, architecture, Taurus, JMeter, required plugins, and manifest hash contract;
7. atomically publish the validated archive, sidecar, and manifest;
8. write the existing generated Runtime environment file only after validation succeeds;
9. reuse an existing artifact only after the same release-manifest, sidecar, archive, and metadata validation passes.

### 11.4 Deployment architecture set

A new tagged-release deployment created from a missing `.env` has one default value:

```text
SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64
```

Existing release Runtime architecture values remain authoritative and are never rewritten by the
configuration confirmation path. Operators and pre-provisioned automation may deliberately use
any accepted advanced value:

```text
auto
amd64
arm64
amd64,arm64
```

Rules:

1. Interactive first-run `./surgepilot up` does not ask for Runtime architectures; after the
   host/port confirmation it persists `amd64,arm64`.
2. The default selects, fetches or reuses, and validates both official Runtime asset sets before
   release Compose startup.
3. `auto` remains an accepted advanced value. It resolves from the actual Docker daemon
   architecture and fetches the matching Runtime whether Demo is enabled or disabled.
4. Explicit `amd64` and `arm64` values remain accepted advanced single-architecture selections.
5. A forced Docker platform that disagrees with the daemon architecture is rejected for the default Demo flow rather than using emulation silently.
6. The declared set controls which release assets `up` fetches into the existing local Runtime directory.
7. Advanced architecture values are deployment inputs, not a Runtime catalog, product capability, or normal user prompt.
8. This does not create multiple active Runtime versions. `LOAD_NODE_RUNTIME_VERSION` remains one release version, and initialization selects the matching architecture from the target Load Node `uname -m` result.

## 12. Networking and Published Ports

1. Released Web traffic remains same-origin through Nginx.
2. Raw API and Web container ports are not public release entry points.
3. The normal release networking contract requires explicit persisted API and InfluxDB origins
   reachable from browsers and external Load Nodes on the intended LAN. P2-06 also permits an
   explicitly warned canonical loopback choice for local evaluation only.
4. First-run `./surgepilot up` asks the operator for one host plus the two published ports and derives
   the consistent node-facing origins before containers start.
5. The release bootstrap must not scan, rank, or infer host interfaces, Docker host aliases, or
   the Demo enable switch.
6. Existing DB `loadNodeApiBaseUrl` authority and environment fallback ordering remain unchanged.
7. Source `make start-full-stack` retains its existing derivation contract; P2-06 changes only the
   release `./surgepilot up` path.
8. No new public host-only intermediate variable is allowed.
9. Both published-port conflicts are detected before first-run `.env` publication, Runtime fetch,
   or Compose mutation.
10. Every valid `up` displays the effective non-secret endpoints, Runtime selection, and Demo state
    before Runtime fetch. Interactive startup uses `Use this configuration? [Y/n]`; Yes/default is
    read-only, while No may enter the standard-LAN four-field reconfiguration loop. Non-interactive
    startup never prompts or rewrites. Advanced HTTPS No requires manual `.env` editing.

## 13. Source Development Contract

### 13.1 Linux and macOS Mode A

The existing host-development flow remains:

```bash
make setup
make infra-up
make migrate
make dev-api
make dev-worker
make dev-web
```

On macOS this supports control-plane development only. Developers use a Linux Demo/remote Load Node for real Runner execution.

### 13.2 Source full-stack flow

`make start-full-stack` remains the source-checkout full-stack entry. Its effective Compose configuration builds current source application images and consumes a local Runtime produced or reused through the Linux builder path. It is not a digest-pinned release deployment and does not consume `release-manifest.json` as its image-selection contract.

`make start-preview` is the narrower source-checkout control-plane entry. It performs the same
secure first-run deployment bootstrap, validates explicit external URL pairs and source Compose,
then starts Web, API, api-worker, PostgreSQL, MinIO, Nginx, InfluxDB, and Grafana without the Demo
profile or Runtime preflight. Preview-only values are process-local: `.env` is not rewritten, the
Runtime version is cleared, and a dedicated host-created empty Runtime mount prevents Docker from
creating or changing ownership of the normal Runtime output directory. Startup output must state
that Setup Status may report `not_configured` and that Load Node initialization and Run execution
readiness are not promised. `make stop-preview` stops this topology without deleting volumes.

Runtime builder Docker build and container execution output must stream to the operator. Commands
whose stdout is parsed, such as Docker daemon architecture detection, remain captured. Source
full-stack startup prints bounded phase labels and does not impose an arbitrary build timeout.

`./surgepilot up` remains the release-bundle entry. Its effective Compose configuration contains no application build contexts, never invokes a source build, pulls the immutable image digests recorded in `release-manifest.json`, and fetches the selected published semantic-version Runtime assets.

The two paths may reuse the same Linux Runtime construction, bootstrap, and validation code where their inputs match, but implementation must keep their configuration and failure messages explicit rather than making one path silently behave like the other.

`make start-full-ssh-e2e` remains an automated/manual acceptance path and must not become the public release entry.

### 13.3 Default verification portability

The default `make verify` gate must pass on supported Linux development hosts and Apple Silicon macOS with Docker Desktop, subject only to explicit Linux-only tests that already declare safe skips. Shell-only Linux utilities such as GNU `timeout`, Linux container-IP reachability assumptions, or `/proc` requirements must not cause unexplained macOS failures in the default gate.

Release-grade Runtime compatibility and SSH E2E remain Linux/Docker gates and are not required to execute natively on macOS.

## 14. Release Workflow and Failure Boundaries

### 14.1 Release trigger

An operator starts the formal workflow with `workflow_dispatch` on the current `main` commit.
The workflow derives the exact `vX.Y.Z` target from root `VERSION`, validates that version and its
reviewed notes, and creates the Git tag only after every required candidate smoke passes. It then
publishes the public release for that exact tag. A normal push to `main`, a pull request, and a
manual Git tag push do not trigger publication.

`v0.0.0` is reserved for non-published development validation artifacts and must be rejected by the
formal release preflight even though it is syntactically valid SemVer.

The release workflow performs at least:

```text
verify source and generated contracts
  -> build/test linux-amd64 Runtime
  -> build/test linux-arm64 Runtime
  -> build multi-arch API/Web/Demo images
  -> verify image index architectures and record immutable digests
  -> assemble and test the digest-pinned release bundle/manifest
  -> run installer, fresh-install, and every required upgrade smoke
  -> recheck the current main commit and create the exact Git tag
  -> stage the GitHub Release and Runtime assets/bundle
  -> publish non-overwritable semantic GHCR tags
  -> publish the completed GitHub Release
```

The exact safe publish ordering must prevent a release page or semantic tag from appearing complete when required artifacts failed. A draft GitHub Release or equivalent staged publication is used until all required artifacts and digest checks are ready.

Every formal release has one reviewed user-facing notes source at
`docs/releases/vX.Y.Z.md`, matching the exact tag. The workflow validates that the file exists and
has the exact tag-matched filename, omits the redundant top-level Release title, and contains the
required ordered sections with substantive content before publication work; it revalidates the
file before draft creation and passes it to
`gh release create --notes-file`. The format and author/review procedure are defined in
`docs/releases/README.md`; installation, upgrade, compatibility, and breaking-change guidance are
explicit rather than inferred from commits.

Release publication is create-only for a semantic version:

1. the dispatched commit must be the current `main` commit at preflight and immediately before
   tag creation; the created tag must resolve to that commit;
2. before staging begins, any existing Git tag, GitHub Release, semantic GHCR tag, or same-named
   release asset for the version causes publication to fail;
3. existing tags, assets, and release identity are never replaced or reconciled in place; an
   exceptional metadata-only body correction may publish the matching checked-in notes file after
   recording and then rechecking the unchanged tag target and complete asset inventory;
4. candidate verification failures before tag creation may be rerun with the same version using a
   new run-specific staging image tag; after tag creation, partial or failed publication requires an
   explicit manual recovery process and a new semantic version;
5. resumable draft publication may be considered later but is not required by P2-05.

### 14.2 Permissions

1. Pull-request workflows use read-only permissions and do not receive release secrets.
2. Release jobs use only the repository/package permissions needed to write GHCR packages and GitHub Release assets.
3. No long-lived registry password is stored when `GITHUB_TOKEN` can publish to GHCR.
4. Runtime component checksum pins and optional build mirrors remain release/deployment controls and are not exposed in Web UI.

### 14.3 Failure safety

1. Runtime build or compatibility failure blocks release publication.
2. Missing image architecture blocks release publication.
3. Release bundle Compose validation failure blocks publication.
4. Runtime download or checksum failure blocks `up` before starting an unready new stack.
5. Repeated `up`, `down`/`up`, an expert-managed extracted-bundle transition, and an ADR-0029
   installer-managed transition must preserve the persisted Compose project, volumes, Admin data,
   MinIO data, Monitoring data, deployment secrets, Demo password, and Demo SSH fingerprint.
6. Neither transition path may stop an existing stack until new-version bootstrap, Runtime,
   digest-pinned image references, and Compose preflight succeed; the installer-managed path also
   satisfies ADR-0029's quiescence and state-publication rules.
7. P2-05 does not promise automatic rollback after a successful stop or partial external infrastructure failure.

## 15. Tests and Acceptance Criteria

### 15.1 Unit and contract coverage

Implementation must cover:

1. Docker-daemon architecture normalization, remote-context behavior, unsupported-architecture failure, forced-platform mismatch rejection, the new dual-architecture default without an architecture prompt, and explicit advanced architecture-set handling including `auto`;
2. Docker/Compose minimum-version preflight, POSIX-shell portability, published semantic versions, local `dev-<manifestHash>`/fixed versions, and exact asset-name construction;
3. successful Runtime download, reuse, checksum verification, metadata validation, and atomic publication;
4. checksum, release-manifest digest mismatch, metadata version, platform, architecture, component, manifest, truncated-download, and redirect-origin failures;
5. interactive/non-interactive first-run behavior, normalized LAN configuration, deployment state
   reuse, stable Compose project identity, optional Demo credential safety, and restart-stable Demo
   SSH fingerprint when enabled;
6. release wrapper command parsing, rejection of the seven quickstart process overrides, complete
   persisted node-facing URL requirements independent of the Demo switch, and non-destructive
   failure ordering;
7. repeated `up`, `down` without volume deletion, `down`/`up`, expert-managed extracted-bundle
   transition, and ADR-0029 installer-managed transition without loss of PostgreSQL, MinIO,
   Monitoring, Admin, secret, or Demo identity state;
8. source/release effective Compose separation, absence of application build contexts from release Compose, release digest pinning, service topology, secret mounts, port exposure, health dependencies, and Demo-node enable/disable behavior;
9. GHCR multi-architecture index requirements for amd64 and arm64, equality with the digest recorded in `release-manifest.json`, Runtime archive/sidecar equality with the release-manifest digest, and create-only rejection when the semantic version already exists;
10. exact-tag release-note source existence, non-empty workflow gating, and publication through the
    reviewed notes file;
11. absence of application source, credentials, `.env`, Runtime files, SSH host private keys, and local state from the release bundle and image layers;
12. two independent installations producing different Demo passwords/fingerprints while one installation preserves its fingerprint across container recreation;
13. preservation of P2-02/P2-04 AI skill release prohibitions.

### 15.2 Platform acceptance matrix

At minimum, release acceptance records:

| Host                | Required evidence                                                                       |
| ------------------- | --------------------------------------------------------------------------------------- |
| Linux amd64         | `./surgepilot up`, first Admin, real LAN node initialize, Debug Run, Run Report, Monitoring. |
| Linux arm64         | Same full flow using arm64 images and Runtime.                                              |
| Apple Silicon macOS | Same full flow through Docker Desktop without amd64 image emulation.                        |

Intel macOS may use the Linux amd64 artifacts but is not required to receive a dedicated hosted CI runner if a documented manual acceptance run is available.

### 15.3 Runtime compatibility

Both release Runtime architectures must pass the existing Ubuntu 24.04 and Debian 12 compatibility contract on their native architecture, including:

1. upload and whole-archive SHA256;
2. safe extraction;
3. metadata and critical-file validation;
4. `current/bin/bzt -h`;
5. JMeter `5.6.3 --version`;
6. required plugin classes;
7. minimal Taurus/JMeter execution.

### 15.4 Repository gates

Implementation must run at least:

```bash
make generate-contracts
make verify
make verify-runtime-compat
make verify-e2e
```

Where architecture-specific release jobs are required, the implementation backfill must record the exact CI jobs and results rather than implying that one amd64 run proves arm64 compatibility.

## 16. Done When

P2-05 is complete only when:

1. `ADR-0017` activates the Slice and synchronizes the Scope Gate, workflow, AGENTS, and P2 index.
2. A tagged release produces one bounded release bundle, three SurgePilot-owned multi-architecture images, and both Runtime architecture assets.
3. The versioned release manifest pins immutable multi-architecture image digests and Runtime asset SHA256 values, the released Compose configuration uses those image digests, and all published SurgePilot-owned release artifacts carry the same semantic version without changing local Runtime version semantics.
4. `./surgepilot up` requires only Docker/Compose, persists one confirmed LAN-usable topology, and
   starts the complete product stack with Monitoring while Demo remains disabled by default.
5. First-run deployment state and Compose project identity are stable, private, and idempotent;
   optional Demo password/SSH state has the same properties when explicitly enabled.
6. Runtime construction on macOS occurs only inside Linux and produces a real Linux artifact.
7. Linux amd64, Linux arm64, and Apple Silicon macOS acceptance evidence satisfies §15.2.
8. Both Runtime architectures satisfy the Ubuntu/Debian native compatibility matrix.
9. A new user can register the first Admin, register/initialize a real LAN Load Node, run a real
   Debug Run, and inspect the report/Monitoring path.
10. New tagged-release deployments persist `SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64`
    without an architecture prompt; existing `.env` authority and advanced `auto`, `amd64`,
    `arm64`, or `amd64,arm64` values safely acquire the declared Runtime set without a Runtime UI,
    database record, separate command mode, or Load Node direct download.
11. Every valid release `up` prints the bounded non-secret effective configuration before Runtime
    fetch; interactive default-Yes is read-only, explicit No/re-entry/Yes may change only four
    standard-LAN network fields, non-interactive startup never rewrites, and advanced HTTPS is
    manual-edit-only.
12. Source development remains available through the existing Make entries on Linux and macOS.
13. Public release work does not publish the Public API AI skill as a standalone artifact or activate another out-of-scope P2 capability.
14. The semantic Release publishes the exact-version installer and bundle sidecar; Linux/macOS
    installer-only smoke and native installer-driven release-stack smoke pass without `sudo`, shell
    configuration mutation, host Python, Node.js, `jq`, or GitHub CLI requirements.
14. Required repository, release, platform, and compatibility verification passes.
15. The implementation backfill records final files, workflow names, image names, commands, acceptance evidence, differences, and remaining risks.

## 17. Governance Decision and Implementation Backfill

`ADR-0017` activates this Slice by reference without repeating its detailed contracts. It records the concrete public GHCR namespace, exact semantic release trigger and permissions, native Linux arm64 runner source, external-node URL supersession, accepted consequences, and required governance-document synchronization.

Activation authorizes implementation only within this Slice. It does not mean that the release wrapper, release Compose, public images, Runtime assets, or release workflow already exist.

The implementation PR must backfill:

1. final stable release bundle/deployment-root layout, wrapper implementation, and manual version-transition instructions;
2. final Compose files/profiles and Demo-node environment control;
3. final GHCR image names, OCI labels, index digests, and release manifest shape;
4. final GitHub workflow files, jobs, runner architectures, and publish ordering;
5. final Runtime builder image/stage and fetch helper names;
6. final Demo password/SSH host-key paths and registration instructions;
7. final networking defaults for Demo and external Load Nodes;
8. final Docker/Compose minimum versions and portability behavior;
9. exact tests and platform acceptance evidence;
10. implementation differences from this SDD;
11. remaining operational and supply-chain risks.

### 17.1 Implementation backfill

The P2-05 implementation uses these final repository and release boundaries:

1. Release source lives under `infra/release/`. `scripts/build_release_bundle.py` produces
   `surgepilot-vX.Y.Z.tar.gz` with the stable top-level `surgepilot/` directory containing
   `surgepilot`, `.env.example`, `release-manifest.json`, rendered Compose/configuration files,
   bounded bootstrap/fetch source scripts, and `README.md`. It excludes `.env`, `.surgepilot/`,
   Runtime archives, application source trees, credentials, and the Public API AI skill.
2. Source startup uses `infra/docker/docker-compose.yml` plus the `demo` profile. Release startup
   uses the separately rendered `compose/docker-compose.yml`; the obsolete external-node overlay
   is removed and release application services contain no `build` keys. The base release file
   publishes Nginx and InfluxDB, while `SURGEPILOT_DEMO_LOAD_NODE_ENABLED=true` explicitly adds the
   Demo profile without creating another product mode.
3. The public image repositories are exactly the ADR-0017 GHCR names. API/api-worker/migration
   share the API image. API, Web, and Demo Dockerfiles accept OCI version/revision/source labels.
   `release-manifest.json` schema version 1 records `version`, full `revision`, each image
   repository plus immutable multi-architecture index digest, and each amd64/arm64 Runtime asset
   name plus whole-archive SHA-256.
4. `.github/workflows/release-package-bootstrap.yml` is the explicitly authorized, manual one-time
   package bootstrap. It publishes bounded non-release `package-bootstrap` images only to create
   the three GHCR package namespaces; the maintainer then changes each package to Public in GitHub
   Package settings. When the workflow exists on the default branch it may use `workflow_dispatch`.
   A maintainer may instead push `package-bootstrap-<12-to-40 source identifier>` for a candidate already
   contained in `main`; the workflow performs the same source-identifier prefix and `main` containment
   checks as release validation. It
   does not create a semantic image tag or GitHub Release.
   `.github/workflows/release.yml` is the manually dispatched formal release workflow. Its jobs are
   `preflight`, `verify`, native `runtime`, native `images`, `image-indexes`, `bundle`, native
   `release-smoke`, conditional `upgrade-smoke`, and `publish`. Preflight enumerates every published
   canonical, non-draft, non-prerelease same-major release in the target manifest's supported
   interval. Later `v1.x`
   targets retain minimum `v1.0.0`; legacy `v1.0.0` and `v1.1.0` root-layout installations remain
   eligible whenever the target manifest includes them. Every eligible source receives a running
   upgrade smoke, and the newest also receives a clean-down upgrade smoke. Missing required source
   evidence fails publication. The first release of a major may have an empty upgrade matrix only
   when its minimum equals its target; fresh-install release smoke remains mandatory.
   `ubuntu-24.04` and `ubuntu-24.04-arm` build/test their own Runtime and application
   architecture. Semantic GHCR tags and the completed GitHub Release are published only after the
   draft assets and all required release-stack smoke jobs pass. The formal Git tag is created only
   after those smoke jobs pass. Existing Git tags and semantic artifacts fail create-only preflight;
   run-specific staging tags let a failed pre-tag candidate run be repeated. GitHub/GHCR existence
   probes distinguish confirmed absence from authentication, rate-limit, and network failures;
   publication repeats the semantic checks and creates tags only from the recorded digest artifact
   that matches the bundled manifest. Release
   smoke and the final publish gate use a clean Docker authentication configuration to prove every
   recorded digest is anonymously pullable before the GitHub Release becomes public. Preflight
   also checks the stable bootstrap tag anonymously before it creates any release staging tag. The
   three GHCR packages therefore must be bootstrapped and configured with public visibility before
   a semantic release tag is created; private prerelease packages cannot pass the public release gate.
   Each native `release-smoke` job uses the formal dual-default tagged-release smoke contract: it
   configures `amd64,arm64` and pre-positions both Runtime architecture file sets before `up`.
5. `infra/docker/runtime-builder/Dockerfile` is the single Linux Runtime builder environment.
   It pins Debian 12 for Java 17 availability and keeps uv's writable environment under `/tmp`
   while the recipe source/lock remain read-only for the host UID/GID. `scripts/run_runtime_builder.py`
   selects the Docker daemon architecture, rejects a conflicting forced platform, and invokes the
   existing `scripts/release_runtime_artifact.py` recipe inside Linux. Local hash versions and
   fixed versions retain ADR-0007 semantics. The builder Dockerfile is copied into that image and
   included in Runtime `recipeFiles`, so builder base/package changes invalidate local artifact
   reuse instead of retaining an older `manifestHash` result.
6. `scripts/fetch_runtime_release.py` constructs exact GitHub Release asset names, permits only
   HTTPS GitHub/release-asset origins across redirects, uses private temporary files, validates
   release-manifest/sidecar/archive digest equality, validates Runtime metadata and component /
   manifest-hash contracts, atomically publishes the files, and writes `runtime.env` last.
7. Bootstrap always owns `.surgepilot/secrets/influxdb-token.secret`. It creates or validates
   `.surgepilot/secrets/demo-load-node-password.secret`,
   `.surgepilot/demo-load-node/ssh_host_ed25519_key`, and
   `.surgepilot/demo-load-node/ssh_host_ed25519_key.pub` only when Demo is explicitly enabled.
   `infra/docker/demo-load-node/Dockerfile` contains no usable default password or host key; its
   entrypoint copies the mounted identity and applies the private password at container start.
   Existing `.env`, private directories, secret files, passwords, and SSH keys must be owned by
   the deployment user with no group/world permission bits; unsafe state fails without repair.
8. First-run release bootstrap prompts for one LAN host, HTTP port, and InfluxDB port, shows the
   dual Runtime default in the confirmation summary, then persists consistent final API/InfluxDB
   origins, Demo-off, `amd64,arm64`, and the trusted-LAN HTTP cookie policy. It does not ask for
   Runtime architectures. Known Compose-only names and local/unsafe addresses are rejected, while
   a valid single-label private DNS hostname remains supported. Bare or singly bracketed IPv6 input
   is normalized to exactly one bracket pair in URLs. Existing `.env` state must already contain
   the complete contract and is never repaired. When Demo is enabled, its registration facts remain
   host `demo-load-node`, port `22`, username `surgepilot`, and runner home
   `/opt/surgepilot/runner`, but it uses the same persisted LAN origins as external nodes.
   Every valid existing configuration is also described before Runtime fetch. Default-Yes is
   read-only; explicit No plus a standard-LAN proposal and Yes may update only the four network
   assignments after candidate validation and a final expected SHA-256 check through standard
   `os.replace`. Simultaneous manual same-user editing in the final syscall window is unsupported;
   there is no backup or automatic rollback. Non-TTY startup never prompts or rewrites, and
   advanced HTTPS No exits with manual-edit guidance.
9. The release wrapper is POSIX `sh`, requires Docker Engine 26+ and Compose 2.27+, does not
   require host Python or `jq`, and executes the Python bootstrap/preflight/fetch helpers from the
   pinned API image. It supports only `up`, `down`, `status`, and `logs`; `down` never deletes
   volumes or deployment state. Only the host shell reads first-run prompts; helper containers use
   closed stdin and private host temporary files outside deployment state. The wrapper validates
   both required HTTP/InfluxDB bind ports before first-run publication or Runtime fetch and prints
   bounded `ps` plus `status`/`logs` guidance on health failure. The pinned API image is used as the
   cross-platform bind probe; no application service starts before bootstrap, Runtime, and Compose
   validation succeed.
   A port already published by the persisted Compose project is accepted for repeated `up` and
   same-root version transitions, while unrelated listeners fail. All seven P2-06 quickstart
   values must be persisted in `.env`; process-level overrides, including empty values, are
   rejected so validation, Runtime selection, Compose bindings, Demo selection, and cookie policy
   cannot diverge. Missing `.env` in a non-TTY fails before image pull or deployment-state creation.
10. Automated coverage includes architecture/version/forced-platform rules, Runtime download /
    reuse / redirect / digest / metadata failures, interactive/non-interactive wrapper behavior,
    LAN/IPv6 normalization, strict cookie parsing, atomic and optional Demo state, wrapper ordering,
    bounded bundle contents, source/release Compose separation, OCI/release workflow contracts,
    and the container-backed SSH fixture used by existing tagged smoke jobs. Those jobs
    pre-provision a complete non-loopback `.env`, authenticate through the published LAN API,
    initialize the SSH node, execute Debug and Standard Runs against the published LAN target,
    and require the Standard Run measurements through the published InfluxDB port. Manual physical
    external-node and Apple Silicon records remain required where hosted infrastructure is absent.
11. There is no new product API, product table, Web route, Runtime catalog, background update,
    signing, SBOM, SDK, MCP, marketplace, or standalone Public API AI skill publication in this
    change. A manually extracted bundle retains the expert-managed replacement path. An
    installer-managed deployment uses ADR-0029's bounded transition, including its explicit
    forward Alembic migration and fail-closed recovery contract.

Implementation evidence that inherently requires external runners or publication is recorded by
the tagged workflow rather than inferred from a local amd64 run. Apple Silicon Docker Desktop full
flow remains a required manual release record when no hosted Docker-capable macOS runner is
available.

## 18. Remaining Design Risks

1. GitHub-hosted native Linux arm64 capacity, cost, or queue time may block release publication or development validation. `ADR-0017` does not allow QEMU fallback; moving to a self-hosted runner requires a governance amendment.
2. The complete default stack has a larger first pull and higher Docker Desktop memory requirement than a partial preview stack; startup must warn clearly when local Docker resources are likely insufficient.
3. GitHub Release availability is an external dependency for first-time Runtime acquisition. Reuse must keep subsequent startup independent of GitHub while the validated local artifact remains present.
4. A syntactically valid confirmed LAN host can still be unreachable because of routing, DNS, VPN,
   or firewall policy. Real external-node acceptance is required; the wrapper does not claim to
   discover or prove the correct interface.
5. Public image and release publication increases supply-chain exposure. Signing, SBOM, provenance, and vulnerability policy remain deliberately deferred rather than silently implied.
6. macOS Docker networking differs from native Linux. Apple Silicon acceptance must verify the
   browser path plus a real external Linux node's Runner callback and Monitoring write instead of
   relying only on image builds or optional Demo success.
7. Public `validation-*` versions in the production GHCR package namespaces add package-list noise,
   consume storage, and may be mistaken for supported releases. They remain explicitly unsupported
   development artifacts, are never referenced by user documentation, and use manual cleanup rather
   than an automated retention subsystem.

## 19. Development Release Validation Design

P2-05 uses one additional `.github/workflows/release-validation.yml` workflow to validate the
release path before the first real semantic release without adding another release system.

The implemented jobs are `verify`, `pr-native`, `tag-preflight`, `tag-native`, `tag-indexes`,
`tag-bundle`, and `tag-smoke`. The production `.github/workflows/release.yml` preflight rejects
`v0.0.0` before any release existence or staging checks.

### 19.1 Pull-request path

For `pull_request` events targeting `main`, the workflow remains read-only and performs:

1. the existing repository verification gate;
2. native Runtime construction and compatibility verification on `ubuntu-24.04` and
   `ubuntu-24.04-arm`;
3. native API, Web, and Demo image builds without registry publication;
4. existing P2-05 workflow and release-contract tests.

The pull-request path uses only `contents: read` and `packages: read`. It creates no package tags,
GitHub Releases, semantic versions, or public artifacts.

`make verify` runs once on `ubuntu-24.04`. The native Runtime/image matrix uses `fail-fast: false` so
both architecture results remain available when one architecture fails; any failed job still blocks
the PR. The minimal implementation does not add path filters because application, lockfile, builder,
Compose, and workflow changes can all affect release output. If a general repository CI workflow is
introduced later, duplicate `make verify` execution may be removed in that separate scope.

### 19.2 Explicit public GHCR validation path

A maintainer may push an explicit `validation-<source-identifier-prefix>` tag only after the candidate
is contained in `origin/main`:

```bash
tag="validation-<source-identifier-prefix>"
git push origin "$tag"
```

The validation tag uses a 12-to-40-character source-identifier prefix, while every GHCR tag below
uses the fixed full source identifier. The workflow rejects tags whose suffix is not a prefix of
the candidate identifier or whose candidate is not contained in `origin/main`. The tag preflight
loads the complete candidate context and explicitly fetches `main` into
`refs/remotes/origin/main` before checking containment. Only validation publication jobs receive
`packages: write`.

Before the first validation tag, the three package namespaces must be created by the bounded
Release Package Bootstrap workflow and made Public in GitHub Package settings. A private repository
whose workflow is not yet present on default `main` uses the explicit trusted
`package-bootstrap-<source-identifier-prefix>` tag path rather than relying on unavailable `workflow_dispatch`.

Validation uses the existing ADR-0017 GHCR repositories and publishes only candidate-specific,
non-semantic tags:

```text
validation-<full-source-identifier>-amd64
validation-<full-source-identifier>-arm64
validation-<full-source-identifier>
```

The multi-architecture tag is assembled from the two native manifests. Its immutable digest is
recorded and used by the existing bundle builder. Validation artifacts use reserved internal
version `v0.0.0`; validation images use that value for their OCI version label while retaining
`validation-<full-source-identifier>` registry tags and the full source identifier in the OCI
revision label. The workflow passes root `VERSION` separately as the API product version, so
`v0.0.0` never enters OpenAPI, Runner, Catalog, or skill metadata. The workflow does not create a
`v0.0.0` image tag or GitHub Release, and the formal release workflow rejects that reserved
version.

Validation image tags are deliberately re-runnable rather than create-only. A rerun for the same
source identifier may replace only its derived `validation-<full-source-identifier>[-arch]` tags. The workflow never
writes a `v*` tag, `package-bootstrap`, or any operator-supplied package tag. Production semantic
tags remain create-only under §14.1.

Native Runtime jobs build `v0.0.0` amd64 and arm64 Runtime files and upload them as workflow
artifacts; validation does not publish Runtime files to GitHub Release. The bundle job downloads
both Runtime artifacts and records their SHA-256 values in `release-manifest.json`. Before each
native `auto` development-validation smoke job runs `./surgepilot up`, it configures the accepted
advanced `auto` value and copies only that runner's matching archive, sidecar, and Runtime manifest
into `surgepilot/.surgepilot/runtime-artifacts/`. This intentionally differs from formal
dual-default tagged-release smoke, which configures `amd64,arm64` and stages both Runtime file sets
on each native runner. `fetch_runtime_release.py` validates and reuses every locally selected
artifact, writes `runtime.env`, and performs no GitHub Release download. A missing or mismatched
selected artifact fails instead of falling back to a fake or temporary Release.

The existing tag-bundle job exposes two download shapes without adding a workflow, job,
permission, public release, or artifact format:

1. `validation-release-assets` retains the bundle plus both Runtime architectures for automated
   native smoke and complete evidence retention;
2. `validation-release-bundle` contains only `surgepilot-v0.0.0.tar.gz`, allowing a maintainer to
   pair the small bundle with only `validation-runtime-amd64` or `validation-runtime-arm64` instead
   of downloading both Runtime archives.

Manual validation staging must preserve the same private-state permissions as smoke:

```sh
tar -xzf surgepilot-v0.0.0.tar.gz
install -d -m 700 surgepilot/.surgepilot surgepilot/.surgepilot/runtime-artifacts
cp surgepilot-runtime-linux-<arch>-v0.0.0.* surgepilot/.surgepilot/runtime-artifacts/
cd surgepilot
./surgepilot up
```

The architecture-specific Runtime artifact intentionally contains only its archive, checksum, and
Runtime manifest; the `surgepilot` wrapper is part of the release bundle. Ordinary `mkdir -p` is not
the documented staging command because a permissive umask can create `.surgepilot` with group/other
access that the bootstrap correctly rejects rather than repairing.

Before smoke testing, an empty Docker authentication configuration must inspect every recorded
image digest successfully, proving that the public GHCR packages support anonymous pulls. The
existing release-stack verifier then exercises the digest-pinned bundle, locally pre-positioned
Runtime reuse, Demo Load Node initialization, Debug Run, Run Report, and Monitoring path on native
amd64 and arm64.

Validation publishes non-semantic development image tags only; it never publishes a public release.

### 19.3 Simplicity and boundaries

1. Reuse the existing Dockerfiles, Runtime builder, bundle builder, release wrapper, Compose files,
   and `verify-p2-05-release-stack` target.
2. Do not refactor the production release workflow into a reusable workflow.
3. Do not add a sandbox repository, separate package namespace, cleanup service, release database,
   or publication API.
4. Do not create draft or public GitHub Releases from validation.
5. Validation package versions are removed manually only when maintenance requires it; automated
   retention remains outside this Slice.
6. Pull requests never receive package-write permission. A validation tag can write packages only
   after its candidate passes the `main` containment check.
7. Validation never creates or moves semantic image tags and does not change any P2-02 Phase A,
   Workspace, OpenAPI, AI skill, credential, API, database, Runner protocol, or Web boundary.

### 19.4 Acceptance and remaining evidence

The development workflow is accepted when a PR proves read-only native Runtime/image construction,
and an explicit validation tag publishes both architectures, records the multi-architecture index
digests, proves anonymous access, pre-positions the matching Runtime artifacts, and passes the native
release-stack smoke without creating a semantic GHCR tag or GitHub Release.

| Evidence | Development validation |
| --- | --- |
| Native amd64/arm64 Runtime build and compatibility | Covered by PR and validation tag |
| Native amd64/arm64 application image build | Covered by PR and validation tag |
| Multi-architecture indexes and recorded digest pins | Covered by validation tag |
| Anonymous GHCR digest access | Covered by validation tag |
| Digest-pinned release-stack smoke | Covered by validation tag with local Runtime reuse |
| Runtime download from GitHub Release assets | Not covered; first real `vX.Y.Z` release |
| Semantic tag create-only conflict behavior | Not covered; first real `vX.Y.Z` release |
| Draft Release to final publication ordering | Not covered; first real `vX.Y.Z` release |
| Apple Silicon Docker Desktop full flow | Not covered; manual acceptance |

Apple Silicon Docker Desktop remains a manual acceptance item because standard GitHub-hosted macOS
runners do not provide an equivalent Docker Desktop environment. The GitHub Release create-only API
path, public Runtime download, and semantic conflict handling remain proven by the first real
semantic release. That release follows the existing §14.1 maintainer recovery contract: keep the
Release draft until all gates pass and use a new semantic version after partial publication rather
than reconciling artifacts in place. Development validation deliberately covers the preceding build,
digest, bundle, public-pull, and local Runtime-reuse behavior only.

Focused implementation verification includes the P2-05 distribution contract tests, PyYAML loading
plus `bash -n` for every workflow `run` block, `sh -n infra/release/surgepilot`, and
`git diff --check`. Final repository acceptance continues to use the §15.4 commands.
