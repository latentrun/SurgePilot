# P2-06 LAN-first Release Bootstrap Usability

- Document status: Active through `ADR-0018`, amended by `ADR-0020`, `ADR-0021`, and `ADR-0024`; implementation
  authorized within this Slice.
- Phase: P2
- Capability: `lan_first_release_bootstrap`
- Parent capability: `docs/sdd/slices/P2-05-cross-platform-distribution.md`
- Product scope: `docs/sdd/00-product-scope-and-priority.md` §7 deployment expansion
- Repository and deployment boundary: `docs/sdd/02-repo-structure-and-dev-workflow.md`
- Runner boundary: `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- Security boundary: `docs/sdd/06-security-permission-workspace.md`
- Monitoring boundary: `docs/sdd/slices/P1-00-monitoring.md`
- Load Node connectivity boundary: `docs/sdd/slices/P2-02-public-api-substrate.md`
- Testing boundary: `docs/sdd/09-testing-and-acceptance-strategy.md`
- Activation ADR: `docs/sdd/adr/ADR-0018-p2-lan-first-release-bootstrap.md`.
- Runtime default amendment ADR:
  `docs/sdd/adr/ADR-0020-p2-release-dual-runtime-default.md`.
- Release configuration confirmation amendment ADR:
  `docs/sdd/adr/ADR-0021-p2-release-up-configuration-confirmation.md`.
- User-local Release installer amendment ADR:
  `docs/sdd/adr/ADR-0024-p2-user-local-release-installer.md`.

## 1. Core Decision

P2-06 defines one bounded revision to the P2-05 release startup path:

```text
./surgepilot up on first run
  -> collect one explicit host and bounded port inputs in the host shell
  -> show the resulting node-facing URLs and ask Use this configuration? [Y/n]
  -> on No, repeat first-run entry; on default-Yes, continue
  -> persist the confirmed release configuration, amd64/arm64 Runtime default,
     and generated secrets in .env/state
  -> validate the persisted configuration before starting the release services
  -> fetch and validate both selected Runtime artifact sets
  -> start one complete release stack with Demo disabled by default
```

The normal release path no longer treats Compose-internal API or InfluxDB node-facing origins, or a
successful Demo Load Node flow, as the ordinary first-use contract. The user chooses the address
before service containers start. A non-loopback address is the normal LAN-ready path. An explicitly
entered canonical loopback address is a local-only evaluation path that starts the same complete
stack but does not claim that other computers or external Load Nodes can use the persisted
node-facing URLs. “Local-only” describes those URLs, not Docker port binding: release Compose still
publishes Nginx and InfluxDB on host interfaces.

The design remains intentionally small:

1. no network scan or automatic interface choice;
2. no first-run Web wizard;
3. no new API, database table, Monitoring setting, or Runner protocol;
4. ADR-0024 adds only one version-pinned, user-local platform Release installer and checksum with
   separate `surgepilot up`; package managers, system installers, Docker installation, automatic
   upgrades, and new public workflow dispatch capability remain excluded;
5. no change to source-checkout `make start-full-stack` behavior.

P2-06 is the active release-path amendment to P2-05. ADR-0017 remains authoritative outside the
explicit partial supersession recorded by ADR-0018. ADR-0020 partially supersedes only ADR-0018's
new-release `auto` default and interactive Runtime architecture prompt. ADR-0021 partially
supersedes only conflicting existing-`.env` not-prompted/never-rewritten wording and authorizes
default-Yes review plus an explicit interactive four-field standard-LAN update.
ADR-0024 partially supersedes only blanket platform-installer/downloader exclusions and does not
change any `up` configuration or startup behavior.

## 2. Scope and Supersession Boundary

### 2.1 Release path only

This Slice changes only the tagged release bundle operated through:

```sh
./surgepilot up
./surgepilot down
./surgepilot status
./surgepilot logs
```

It does not reopen the P2-05 image, Runtime archive, digest pinning, release-manifest, GHCR, or
tagged publication design. It consumes those existing artifacts without adding a GitHub action or
new distribution format.

### 2.2 ADR-0017 decisions that require supersession

ADR-0018 supersedes only these release-path parts of ADR-0017 and P2-05:

1. the default release topology being Demo-first with Compose-internal node-facing origins;
2. `SURGEPILOT_DEMO_LOAD_NODE_ENABLED=true` as the release default;
3. `SURGEPILOT_RUNTIME_ARCHITECTURES=auto` returning no Runtime architecture when Demo is disabled;
4. InfluxDB host publication being conditional on an external-node overlay;
5. external node-facing URLs being optional for the default release startup.

ADR-0018 must not supersede source-checkout startup, immutable image/runtime integrity,
secret handling, Workspace isolation, permission, or release-publication boundaries.

### 2.3 ADR-0020 new-release-only amendment

ADR-0020 changes only a missing-`.env` tagged-release bootstrap: it persists
`SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64` without asking an architecture question, and both
selected prebuilt Runtime sets must validate before release Compose startup. Existing release
`.env` Runtime and all other non-network values remain authoritative and are never rewritten.
ADR-0021 permits only an explicit interactive update of the four allowlisted network fields.
`auto`, `amd64`, `arm64`, and `amd64,arm64` remain accepted advanced values.

Source `make start-full-stack` remains native-only, and root `.env.example` remains `auto`. The
amendment does not change ADR-0018's LAN host, Demo, cookie, InfluxDB, published-port, or
non-interactive complete-`.env` contracts.

### 2.4 No historical compatibility burden

The project is still in development. P2-06 does not add automatic migration or compatibility
branches for an earlier P2-05 release `.env` shape. After activation, an existing release `.env`
that lacks the newly required values fails with actionable guidance and must be corrected by the
operator. It is never automatically repaired, rewritten, or supplemented; the ADR-0021 quick path
requires already-valid standard-LAN state and is not historical compatibility logic.

### 2.5 ADR-0024 separate installation amendment

ADR-0024 adds a separate step before this Slice's `up` flow:

```sh
curl -fsSL https://github.com/latentrun/SurgePilot/releases/latest/download/install.sh | sh
surgepilot up
```

The first command installs one exact semantic bundle below the user's home directory, validates
its SHA-256 sidecar, and creates a user-owned launcher. It never reads the LAN host/ports, creates
`.env`, downloads Runtime sets, pulls images, or calls Compose. The second command enters the
existing P2-06 terminal, confirmation, state, Runtime, and startup contract unchanged. Manually
extracted archives retain `./surgepilot up`.

## 3. User Problem

### 3.1 Demo success does not prove the intended deployment

The current release default can prove a complete flow through a Compose-internal Demo Load Node
while a browser or real Load Node on the LAN still cannot reach the configured callback or
Monitoring write origin. That creates a misleading success state: the bundled demonstration works,
but the system's primary private-network deployment path is incomplete.

### 3.2 Post-start configuration is too late for published ports

The current external-node Compose overlay is selected from `.env` before containers start. A value
saved later through System Settings cannot change the active Compose file set or publish InfluxDB
port `8086`. Runtime configuration and host publication can therefore disagree.

### 3.3 Automatic host selection is ambiguous

Linux and macOS hosts may have Ethernet, Wi-Fi, VPN, virtual, container, and remote-Docker
interfaces. Choosing one automatically risks persisting an address that browsers or Load Nodes
cannot use. The wrapper should ask the operator instead of claiming that one discovered address is
correct.

### 3.4 Manual pre-editing harms first use

A new evaluator should not need to read `.env.example` before the first startup. The release
wrapper already owns first-run bootstrap, so it should collect the small set of required LAN inputs
before creating `.env`.

## 4. Goals and Non-goals

### 4.1 Goals

1. A new user can run `./surgepilot up` without first editing `.env`.
2. The first successful release startup has explicit API and InfluxDB node-facing origins, using
   either the normal LAN-ready path or a clearly warned explicit loopback-origin evaluation path;
   the latter does not change Docker's host-interface port bindings.
3. The four network values are produced from one confirmed host/port input set and cannot silently
   diverge.
4. A new tagged-release deployment fetches and validates both amd64 and arm64 Runtime sets without
   asking the operator to choose architectures.
5. Non-interactive first startup fails closed instead of accepting EOF or an empty host.
6. Release Compose publishes the browser/API entry and InfluxDB node-write port by default.
7. Existing P0/P1 safety, credential, Workspace, Run-state, and artifact boundaries remain intact.

### 4.2 Non-goals

1. Network scanning, NIC/default-route selection, mDNS, UPnP, or firewall modification.
2. A Web setup wizard, startup modal, or new System Settings page.
3. A Monitoring UI/API, Runtime Catalog, package-manager/system installer, or general downloader.
4. Changes to Runner protocol, Run state machine, Workspace, RBAC, CSRF, or credential storage.
5. Public GitHub Release/GHCR publication, package visibility, tag creation, or workflow dispatch.
6. Source-checkout startup redesign.
7. Automatic migration of an earlier release `.env`.

## 5. First-run User Experience

### 5.1 Interactive startup

When `.env` does not exist and both standard input and standard output are terminals, the user runs:

```sh
./surgepilot up
```

The host shell asks, in this order:

```text
LAN host or IP [required]:
HTTP port [8080]:
InfluxDB node-write port [8086]:
```

Interactive first-run setup does not ask for Runtime architectures. A new release `.env` persists
`amd64,arm64`. Existing or pre-provisioned release `.env` files may use any accepted advanced
Runtime value:

```text
auto
amd64
arm64
amd64,arm64
```

The host may be a valid LAN-reachable IPv4 address, IPv6 address, or DNS hostname. The explicit
canonical loopback forms `localhost`, `127.0.0.1`, and `::1` are also accepted for local-only
evaluation; the prompt remains required and never defaults to loopback. The wrapper does not
suggest, discover, or rank host interfaces. IPv6 literals are normalized with brackets when the
URLs are constructed. The normalization contract accepts either `2001:db8::20` or
`[2001:db8::20]`, removes at most one valid outer bracket pair, parses the remaining value as one
IPv6 address, and renders exactly one bracket pair. Mismatched, nested, empty, or zone-qualified
bracket forms fail rather than producing a double-bracketed URL. Legacy IPv4 spellings such as
`127.1`, integer, octal-like, hexadecimal-like, or leading-zero forms are rejected as
non-canonical before they can be accepted as DNS hostnames. After IDNA normalization, the same IP,
legacy-notation, Compose-only, and loopback checks run again; Unicode lookalikes that normalize to
a prohibited host cannot bypass the contract, while ordinary internationalized DNS names remain
valid in their normalized ASCII form.

After syntax normalization, the wrapper displays the exact intended configuration:

```text
Web and API: http://192.168.1.20:8080
InfluxDB node write: http://192.168.1.20:8086
Runtime architectures: amd64,arm64
Demo Load Node: disabled
```

For canonical loopback input the same summary additionally prints:

```text
Configured node-facing URLs: this computer only.
Warning: other computers and external Load Nodes cannot reach these configured URLs.
Docker still publishes these ports on host interfaces; use the host firewall if local-only network exposure is required.
```

This is one warning in the existing confirmation flow, not a second prompt or a new persisted
deployment-mode variable. The wrapper asks:

```text
Use this configuration? [Y/n]:
```

Empty input, `y`, or `yes` accepts the normalized proposal. `n` or `no` repeats first-run host/port
entry; any other value repeats only the confirmation question. EOF aborts. No state, Runtime, or
Compose service changes occur before default-Yes confirmation.

### 5.2 Successful startup output

After health readiness, the wrapper prints the confirmed host rather than `localhost`:

```text
SurgePilot vX.Y.Z is ready.
Web: http://192.168.1.20:8080
Grafana: http://192.168.1.20:8080/grafana/
External Load Nodes must reach:
  API: http://192.168.1.20:8080
  InfluxDB: http://192.168.1.20:8086
Commands: ./surgepilot status | ./surgepilot logs | ./surgepilot down
```

The wrapper must not claim that the address is reachable merely because it was confirmed and is
syntactically valid. Host firewall, routing, DNS, and remote-node reachability remain operator and
acceptance-test responsibilities.

For local-only configuration the ready output prints the local Web/Grafana URLs and states that
external Load Nodes require both node-facing origins in `.env` to be changed to a reachable
non-loopback host before `./surgepilot up` is run again. It must not print the ordinary “External
Load Nodes must reach” claim for loopback URLs. It also states that Docker still publishes the
configured ports on host interfaces; the host firewall, rather than this URL choice, owns any
local-only exposure requirement.

### 5.3 Non-interactive first startup

When `.env` is absent and either standard input or standard output is not a terminal,
`./surgepilot up` fails before prompting or creating deployment state:

```text
SurgePilot: first-run release setup requires an interactive terminal. Create and validate .env before running non-interactively.
```

EOF, redirected empty input, and pipeline input must never create an empty host value. CI and other
automation must pre-provision a complete owner-only `.env` based on the release `.env.example`.
This applies to the existing `.github/workflows/release-validation.yml` and
`.github/workflows/release.yml` smoke jobs because GitHub Actions steps are non-interactive.

Those jobs must materialize a complete test `.env` before `./surgepilot up` and choose an explicit
non-loopback API/InfluxDB host that is reachable from the smoke Load Node. They must not use
`localhost` as the node-facing origin: inside a Load Node container, `localhost` identifies that
container rather than the release host, and the release preflight rejects loopback origins. A smoke
job may explicitly enable Demo as a packaging fixture only when the chosen host address is routable
from the Demo container; this does not restore Demo as the ordinary release default or primary
acceptance proof.

When `.env` already exists, non-interactive `up` performs normal validation, prints the same bounded
non-secret configuration summary, and either continues or fails. It never opens a prompt, reads
stdin, or rewrites `.env`.

### 5.4 Existing `.env`

An existing `.env` is operator-owned state. Every valid `up` prints its effective Web/API and
InfluxDB endpoints, Runtime architecture value, and Demo state before Runtime fetch. In a TTY it
then asks `Use this configuration? [Y/n]:`:

1. empty input, `y`, or `yes` accepts the current state without rewriting it;
2. invalid confirmation input repeats only the confirmation question;
3. `n` or `no` opens standard-LAN re-entry only when the current configuration is valid direct
   HTTP; current host and ports are the prompt defaults;
4. the normalized proposal is displayed and requires default-Yes confirmation; No repeats entry;
5. only the four allowlisted network fields may change after No, valid entry, normalized review,
   and Yes; an identical proposal does not replace the file;
6. valid advanced HTTPS is display-and-accept only; No exits before Runtime and Compose with
   explicit manual `.env` edit guidance;
7. all required release values must already be present, and invalid or inconsistent state fails
   without repair before Runtime fetch or Compose service changes;
8. normal repeated `up`, `down`/`up`, and version transitions preserve all non-target state;
9. canonical loopback remains valid only for Demo-off local evaluation and continues to display
   the local-only-URLs/all-interface-ports warning rather than being silently upgraded to LAN-ready
   status.

## 6. Release Configuration Model

### 6.1 Persisted first-run values

The confirmed input set is rendered into the release `.env` together with existing generated
secrets and bootstrap values:

```text
SURGEPILOT_HTTP_PORT=<http_port>
SURGEPILOT_NODE_API_BASE_URL=http://<normalized_lan_host>:<http_port>
SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT=<influx_port>
SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://<normalized_lan_host>:<influx_port>
SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false
SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64
SESSION_COOKIE_SECURE=false
```

`amd64,arm64` is the new tagged-release default. Demo is disabled and the session cookie matches
the bundled trusted-LAN HTTP transport without requiring additional questions. Existing Runtime,
Demo, cookie, credential, secret, and other non-network values, including `auto` and either explicit
single architecture, remain authoritative and are never rewritten by the quick path.

`SESSION_COOKIE_SECURE` uses a dedicated strict parser. When present, only case-insensitive
`true` or `false` after surrounding-whitespace removal are valid. Empty values, `ture`, `1`, `0`,
`yes`, `no`, `on`, and `off` fail API startup. When the variable is absent outside the release
bundle, the current secure-by-default production behavior remains: `APP_ENV=production` implies a
Secure cookie. Release preflight rejects the same invalid values before Compose startup, and the API
strict parser remains the final guard for expert/raw Compose paths. The implementation must not
reuse the permissive generic `_bool_from_env` behavior for this transport-security control.

### 6.2 Direct-LAN consistency rules

For the standard generated HTTP deployment:

1. `SURGEPILOT_HTTP_PORT` equals the explicit port in
   `SURGEPILOT_NODE_API_BASE_URL`;
2. `SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT` equals the explicit port in
   `SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL`;
3. both URLs use the same normalized host;
4. both URLs use `http` and contain no credentials, path other than optional `/`, query, or
   fragment;
5. ports are decimal integers from `1` through `65535` and must be distinct;
6. the host is either a normal non-loopback host or one of the explicit local-only forms
   `localhost`, `127.0.0.1`, or `::1`; wildcard, other loopback forms, unspecified, link-local,
   multicast, legacy/non-canonical IPv4 notation, known Compose-only service names, and
   `host.docker.internal` remain invalid; these checks repeat after IDNA normalization;
7. `SESSION_COOKIE_SECURE` is exactly `false`.

The wrapper and helper validate the same normalized contract. Neither treats syntactic validation
as proof of remote reachability.

### 6.3 Process environment boundary

The release `.env` is the only ordinary deployment input after first-run confirmation. The wrapper
rejects inherited process-level values for every `up`, `down`, `status`, and `logs` invocation:

```text
SURGEPILOT_HTTP_PORT
SURGEPILOT_NODE_API_BASE_URL
SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT
SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL
SURGEPILOT_RUNTIME_ARCHITECTURES
SURGEPILOT_DEMO_LOAD_NODE_ENABLED
SESSION_COOKIE_SECURE
```

This prevents shell state from changing Compose bindings, callback URLs, Runtime acquisition, Demo
selection, or cookie policy without changing the persisted deployment contract. Existing bounded
bootstrap identity and credential inheritance may remain where P2-05 already requires values to be
persisted and later matched.

Prompt results are held as wrapper-local, non-secret values and passed to the helper through an
explicit internal helper interface. They are not exposed as supported process overrides.

### 6.4 Existing DB System Setting

P2-06 removes the earlier proposed `Use current address` UI helper and server-side InfluxDB URL
derivation. It does not add or remove a business API field.

The existing P2-02 DB-backed `loadNodeApiBaseUrl` setting remains an intentional advanced product
override with its existing DB-over-environment precedence. A clean release does not populate that
DB setting, so the confirmed `.env` origin is effective by default. If an Admin later changes the
DB setting, that is an explicit post-bootstrap policy change and must remain a valid external
origin; it does not rewrite `.env`, republish ports, or derive a new InfluxDB URL.

This distinction keeps P2-06 out of the API/database/UI scope while making `.env` the only ordinary
first-run deployment input.

### 6.5 HTTPS boundary

The interactive P2-06 quickstart configures direct trusted-LAN HTTP only. Plain HTTP provides no
transport confidentiality and is not an internet-facing deployment contract.

An operator-managed HTTPS/reverse-proxy deployment must explicitly set
`SESSION_COOKIE_SECURE=true` and provide final externally reachable origins. Because a proxy may
use different public and local ports, that topology is not produced by the first-run prompt and is
outside the direct-LAN same-port contract above. For this advanced mode, the wrapper still validates
both local published ports and both absolute final origins, but it does not require the public proxy
ports to equal the local Compose bindings or require the API and InfluxDB origins to share a host.
The final API origin must use `https` when `SESSION_COOKIE_SECURE=true`; otherwise the browser would
not return the Secure session cookie and authentication would be unusable. The operator edits
`.env` deliberately; process overrides remain rejected. Every valid advanced HTTPS configuration
is still displayed before Runtime fetch. Interactive Yes/default accepts it read-only, while No
exits with manual-edit guidance; advanced HTTPS never enters the quick rewrite path.
P2-06 does not automate
TLS, proxy configuration, certificates, HSTS, or public ingress.

## 7. Startup and State Flow

### 7.1 `./surgepilot up` ordering

The release wrapper performs these steps in order:

```text
validate command, Docker Engine, Docker Compose, and release manifest
  -> inspect whether .env exists and enforce interactive/non-interactive rules
  -> pull the immutable API image required by the existing helper boundary
  -> first run: collect and normalize host/port inputs, show the exact URLs and amd64/arm64 Runtime
     default, then use the default-Yes confirmation loop
  -> existing .env: validate and describe the bounded non-secret effective configuration
       -> non-TTY: show and continue read-only
       -> TTY Yes/default: continue read-only
       -> TTY No plus standard LAN: collect, normalize, show, and confirm in a loop
       -> TTY No plus advanced HTTPS: fail with manual-edit guidance
  -> validate required host-port availability
  -> atomically create first-run state or use standard os.replace for four existing network fields
  -> validate the persisted release configuration and secret state
  -> resolve Runtime architectures and fetch/reuse matching release assets
  -> validate release Compose configuration
  -> pull digest-pinned images
  -> start release services and wait for bounded health readiness
  -> print confirmed URLs and bounded next steps
```

Authoritative origin/architecture validation remains in the existing Python helper boundary rather
than being reimplemented in POSIX shell. Input and port validation occurs before `.env` publication
so a simple typo or occupied port does not leave a newly generated deployment that immediately
requires manual repair. No application service is started before bootstrap, Runtime, and Compose
validation succeed. The helper container is non-interactive and never reads from the user's
terminal; only the host wrapper prints prompts and reads confirmation. No Runtime acquisition,
Compose config/pull/up, or application-service change occurs before the interactive decision and
any required safe persistence completes.

### 7.2 Persistence and concurrency boundary

The existing P2-05 bootstrap invariants remain:

1. `.env` and secret files use owner-only permissions;
2. files are non-symlink regular files;
3. one concurrent first-run process may publish the winner atomically;
4. a losing process validates the published state and succeeds only if it matches its confirmed
   non-secret bootstrap values;
5. existing state is never overwritten, rotated, or repaired automatically; the sole update path
   requires interactive No, valid standard-LAN entry, normalized review, and Yes, and changes only
   four allowlisted network fields;
6. generated secret plaintext is not printed;
7. failure before publication cleans private temporary files.

When Demo is disabled, the helper does not generate or validate Demo password/SSH identity state.
Those files are created or validated only when Demo is explicitly enabled. The ordinary release
bootstrap therefore cannot fail because optional Demo credentials are absent.

For an existing-state update, the helper validates an owner-owned mode-private non-symlink regular
file, requires the SHA-256 of the exact content shown to the operator, rejects missing or duplicate
allowlisted assignments, preserves all non-target content, and accepts only LF or CRLF line endings.
It writes and fsyncs a same-directory mode-`0600` candidate, validates its bytes/mode/owner,
revalidates the existing direct-LAN state, performs a final pre-replacement SHA-256 check, uses
standard `os.replace`, and fsyncs the parent directory. A no-op proposal performs no replacement.
Failures before `os.replace` leave the original intact. This is not strict CAS: simultaneous manual
same-user editing in the final syscall window is unsupported, with no backup or automatic rollback.
If parent fsync fails after replacement, startup reports that the file was updated but durability
could not be confirmed and halts before Runtime or Compose work.

### 7.3 Port availability

Before publishing first-run state or an explicitly confirmed existing-state proposal, the wrapper
proves that the selected HTTP and InfluxDB host ports are available or already owned by the same
persisted Compose project. Unrelated listeners fail with the exact conflicting port and return to
the appropriate input loop without changing `.env`.

The probe remains cross-platform for supported Linux and Docker Desktop hosts and must not require
host Python, GNU-only shell tools, or direct container-IP access.

### 7.4 Existing CI and release-smoke contract

P2-06 changes the inputs of existing non-interactive smoke jobs but does not add a new workflow,
publication action, permission, or dispatch surface.

Before each workflow invocation of `./surgepilot up`:

1. create the complete smoke `.env` inside the extracted release directory;
2. use one job-selected non-loopback host/origin reachable from the smoke node;
3. keep API and InfluxDB URL ports equal to their published-port variables;
4. set `SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64` for the default release smoke contract, or
   explicitly exercise another accepted advanced value in a focused test;
5. set Demo deliberately for the specific smoke rather than relying on the release default;
6. validate the generated Compose configuration before invoking `up`.

Product code must not copy the CI host-selection mechanism. Controlled test infrastructure may
select and verify its runner address explicitly; the release wrapper still performs no NIC
discovery for users.

## 8. Runtime Architecture Contract

### 8.1 New-release default and resolution

New tagged-release deployments default to:

```text
SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64
```

The wrapper does not ask first-run operators to select architectures. Both prebuilt Runtime sets
must pass the existing checksum, release-manifest, version, platform, architecture, component,
plugin, and manifest-hash validation before release Compose startup.

`auto` remains an accepted advanced value and keeps the ADR-0018 release-path behavior:

```text
resolve_runtime_architectures(auto, false, amd64) -> ("amd64",)
resolve_runtime_architectures(auto, false, arm64) -> ("arm64",)
resolve_runtime_architectures(auto, true, amd64)  -> ("amd64",)
resolve_runtime_architectures(auto, true, arm64)  -> ("arm64",)
```

`auto` always means the normalized Docker daemon architecture for the release path. It no longer
means “fetch nothing when Demo is disabled.”

Other explicit values remain:

```text
amd64
arm64
amd64,arm64
```

Duplicate, reversed mixed-order, unknown, empty, or unsupported values fail. The accepted mixed
order is exactly `amd64,arm64`. Existing `.env` selections are never rewritten.

### 8.2 External-node selection

The declared architecture set controls only which artifacts are downloaded or reused locally.
During Load Node initialization, api-worker continues to inspect the target node through
`uname -m`, normalize the result, and select the matching release artifact.

If the target architecture is not present, initialization fails with actionable English guidance:

```text
Runtime for arm64 is not available in this deployment. Set SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64 in .env and run ./surgepilot up again.
```

P2-06 does not add runtime auto-download during node initialization, a Runtime Catalog, multiple
active versions, or architecture guessing from SSH hostnames.

### 8.3 Forced platform

The existing supported Docker-daemon normalization and forced-platform safety remain. A forced
application platform must not silently make Runtime artifacts claim a different native
architecture. Exact validation behavior is synchronized with the P2-05 release preflight during
activation.

## 9. Release Compose and Network Contract

### 9.1 Default published ports

Release base Compose publishes both node-facing entries by default:

```text
${SURGEPILOT_HTTP_PORT}:80
${SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT}:8086
```

The bindings must not be loopback-only, including when the persisted node-facing URLs use a
canonical loopback host for local evaluation. Host firewall and routing policy may still limit
which LAN clients can reach them. Therefore, the wrapper describes loopback URLs as local-only but
must not describe Docker port exposure or the whole deployment as reachable only from this computer.

The conditional external-node overlay is removed or reduced so it is no longer responsible for
publishing InfluxDB. Raw API, Web, PostgreSQL, MinIO, MinIO Console, and Demo SSH ports remain
unpublished.

### 9.2 Required node-facing values

Release Compose requires non-empty explicit values for:

```text
SURGEPILOT_NODE_API_BASE_URL
SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL
```

The release definitions no longer use these node-facing fallbacks:

```text
http://api.surgepilot.test:8000
http://influxdb:8086
```

This removal applies to the API/api-worker values used to construct external Runner callbacks and
JMeter Backend Listener configuration. It does **not** remove the private service-to-service
InfluxDB URL required by API queries, Grafana provisioning, or InfluxDB health checks. Internal
control-plane traffic remains on the Compose network.

### 9.3 Same-origin browser behavior

Web continues to use same-origin `/api` through Nginx. P2-06 does not add CORS or publish the raw API
container port. The confirmed host affects user guidance and node-facing origins, not Web
client routing.

## 10. Demo Load Node Contract

### 10.1 Default state

The release default becomes:

```text
SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false
```

The normal acceptance claim is therefore based on a real LAN-reachable external Load Node rather
than Demo success. The release may still contain the existing Demo image and Compose profile; this
Slice does not remove the development aid or reopen its image design.

### 10.2 Explicit enablement

When an operator deliberately changes `.env` to enable Demo and reruns `./surgepilot up`:

1. Demo uses the persisted LAN API and InfluxDB node-facing URLs;
2. Demo does not restore Compose-internal node-facing fallback values;
3. the chosen LAN host must be routable from the Demo container to the host-published ports;
4. registration, initialization, Debug Run, and Standard Run use the ordinary node contracts;
5. an unreachable address fails with the same actionable connectivity or Monitoring errors used
   for external nodes.

Canonical loopback origins are rejected when Demo is enabled because loopback inside the Demo
container identifies the container itself rather than the release host.

The wrapper does not probe multiple host aliases or rewrite the persisted host to make Demo work.

## 11. Failure and Security Behavior

1. Missing TTY on first run fails before state creation.
2. Empty, malformed, wildcard, legacy/non-canonical IPv4, unsafe non-canonical loopback, or
   Compose-only host input fails before confirmation; canonical loopback is accepted only as an
   explicit Demo-off local-only URL choice and produces a warning that ports remain published on
   host interfaces.
3. Invalid Runtime architecture syntax in an existing or pre-provisioned `.env` fails before
   Runtime fetch or Compose startup and never triggers a rewrite.
4. Occupied host ports fail before `.env` creation on a clean first run.
5. Missing or inconsistent values in an existing `.env` fail without repair.
6. An invalid explicit `SESSION_COOKIE_SECURE` value fails release preflight before Runtime fetch or
   Compose service changes; the API strict parser also rejects it as the final guard for expert/raw
   Compose paths instead of silently treating it as `false`.
7. Runtime download, checksum, metadata, or architecture failure blocks service startup.
8. Compose validation failure blocks service startup.
9. Load Node initialization fails when the target architecture artifact is absent.
10. Run start and callbacks continue to fail closed when the effective API origin is invalid or
   unreachable.
11. Standard Run Monitoring continues to use the immutable per-Run node-write snapshot and fails
    with existing `config_error` behavior when configuration is invalid.
12. Monitoring token plaintext remains excluded from `.env`, API responses, logs, artifacts, and
    Runner-visible values other than the bounded generated execution configuration.
13. Session cookies remain HttpOnly and SameSite=Lax; CSRF, server-side session storage, logout,
    RBAC, and Workspace isolation do not change.
14. Invalid confirmation input repeats without mutation. No alone changes nothing. Invalid
    proposals or occupied proposed ports return to the standard-LAN input loop without mutation.
15. EOF, unsafe `.env` state, unsupported line separators, duplicate target assignments, candidate
    validation failure, expected SHA-256 mismatch detected before replacement, or `os.replace`
    failure exits before Runtime and Compose side effects and leaves the original file intact. A
    post-replacement parent-fsync failure does not roll back; it reports the uncertain durability
    and halts before Runtime and Compose work.
16. Automatic and non-interactive rewriting remains forbidden. Advanced HTTPS never enters the
    four-field quick path.

When bundled HTTP mode uses `SESSION_COOKIE_SECURE=false`, `./surgepilot up` prints one non-blocking
warning:

```text
Warning: this trusted-LAN HTTP deployment does not provide transport confidentiality. Use an operator-managed HTTPS deployment and SESSION_COOKIE_SECURE=true on untrusted networks.
```

No recurring browser modal, response warning header, or browser-console warning is added.

## 12. Source-checkout Boundary

`make start-full-stack` remains governed by the source Compose and the current source startup
contract. P2-06 does not require source users to answer the release prompt and does not delete the
source Compose-internal Demo/API/InfluxDB defaults. ADR-0021 display, confirmation, and existing
release `.env` update behavior does not apply to source startup or preview.

Source and release may reuse pure validation or normalization functions when their contracts match,
but release-specific TTY prompting, `.env` LAN persistence, Demo-off default, required node-facing
URLs, and default `8086` publication must not silently change source startup semantics.

Contract tests must prove that the release fallback removal does not delete source-only internal
defaults.

## 13. Contract and Data Impact

### 13.1 API and database

1. No new route, response field, database table, or migration.
2. Existing `loadNodeApiBaseUrl` schema and permission remain unchanged.
3. Existing `run_monitoring_configs.influxdb_node_write_url` remains the immutable Run snapshot.
4. No Monitoring token or effective node-write URL is exposed through business APIs.

### 13.2 Web

No Web implementation is authorized. The prior draft's `Use current address` helper is removed from
scope. User-visible first-run interaction is terminal-only and occurs before services start.

### 13.3 Release deployment

Expected implementation areas after activation are limited to:

1. release wrapper host/port prompt and TTY handling without a Runtime architecture prompt;
2. bounded non-secret configuration description, default-Yes confirmation, and interactive
   standard-LAN re-entry;
3. release bootstrap/preflight validation, expected-content SHA-256 checks, atomic first-run `.env`
   creation, and explicit standard-`os.replace` updates of only four allowlisted network fields;
4. release dual-architecture default and existing advanced Runtime selection;
5. release `.env.example` and Compose defaults;
6. existing release/release-validation smoke fixtures required by the non-interactive contract;
7. bounded release/source contract tests and LAN external-node acceptance;
8. synchronized P2-05, ADR-0017/0018/0020/0021, README, and AGENTS wording.

## 14. Acceptance Criteria

### 14.1 Interactive first run

On a clean supported Linux or macOS Docker host:

1. `./surgepilot up` prompts only in the host shell;
2. pressing Enter accepts the two stated port defaults after a valid host is entered;
3. the exact normalized URLs and Runtime selection are shown before confirmation;
4. No repeats host/port entry and leaves no `.env`, generated secret, Runtime, or Compose-service
   side effect until a proposal receives default-Yes confirmation;
5. confirmation creates one private `.env` whose network values are same-host and port-consistent;
6. Demo is disabled and `SESSION_COOKIE_SECURE=false` is persisted by default;
7. the wrapper fetches and validates both amd64 and arm64 Runtime sets for a new deployment;
8. the release stack becomes healthy and prints the confirmed URLs.
9. explicit `localhost`, `127.0.0.1`, or `::1` starts the same complete stack, prints local Web and
   Grafana URLs, and warns that other computers and external Load Nodes cannot use those origins.

### 14.2 Non-interactive behavior

1. no `.env` plus non-TTY input or output fails with the documented message;
2. EOF and empty redirected input cannot create `.env`;
3. a complete valid pre-provisioned `.env` continues non-interactively;
4. an incomplete or inconsistent existing `.env` fails without modification;
5. existing release-validation and tagged-release smoke jobs create a complete `.env` before
   invoking `./surgepilot up` and do not use loopback node-facing origins.
6. existing startup prints the bounded non-secret summary but no prompt, never reads stdin, and
   never rewrites `.env`.

### 14.3 Existing interactive configuration

1. every valid existing release `.env` is described before Runtime fetch;
2. empty input, `y`, or `yes` accepts current state without replacement;
3. No on standard LAN opens host/port re-entry with current defaults, and repeated No is safe;
4. confirmed persistence changes exactly the four allowlisted network fields and preserves all
   other content; an identical proposal performs no replacement;
5. No on advanced HTTPS exits with manual-edit guidance and preserves `.env`;
6. EOF, invalid input, port conflict, unsafe state, unsupported line separators, duplicate key,
   candidate failure, final digest mismatch, and pre-replacement write/replace failure preserve
   `.env` and precede Runtime/Compose side effects; post-replacement fsync failure keeps the update,
   prints the durability diagnostic, and also precedes Runtime/Compose side effects.

### 14.4 Configuration and Compose

1. all seven persisted quickstart values are present and validated;
2. process-level overrides for those values are rejected;
3. HTTP and InfluxDB host ports are distinct and available before clean first-run publication;
4. release base Compose publishes `8080` and `8086` by default when defaults are selected;
5. release API/api-worker have no Compose-internal node-facing callback/write fallback;
6. source Compose retains its existing internal development defaults;
7. raw API/Web/internal storage ports remain unpublished;
8. `SESSION_COOKIE_SECURE=false` and `true` are accepted case-insensitively, while empty or any
   other explicit value fails startup.

### 14.5 Runtime

1. a new release `.env` persists `amd64,arm64` without an architecture prompt;
2. `auto,false,amd64` resolves to `("amd64",)` and `auto,false,arm64` resolves to
   `("arm64",)` when deliberately configured as an advanced value;
3. `amd64,arm64` fetches and validates both release artifacts before Compose startup;
4. duplicate, reversed, unknown, empty, and unsupported architecture values fail;
5. target-node architecture selection uses `uname -m` and fails clearly when its artifact is absent.

### 14.6 LAN external-node flow

Native Linux amd64 and arm64 validation must each prove:

1. browser registration/authentication through `http://<lan-host>:<http-port>`;
2. external SSH Load Node registration and initialization;
3. Runner health/OpenAPI access and authenticated callbacks through the configured LAN API origin;
4. a completed Debug Run and Run Report;
5. a completed Standard Run whose JMeter Backend Listener writes through the published LAN
   InfluxDB origin;
6. Monitoring entry and completed-Run dashboard access without token or node-write URL exposure.

Apple Silicon Docker Desktop receives a manual LAN-origin record when no Docker-capable hosted
macOS runner is available. Intel macOS remains documented best effort.

### 14.7 Optional Demo

1. Demo is absent from the default effective service set;
2. explicit enablement uses the persisted LAN API and InfluxDB URLs;
3. no internal node-facing fallback reappears;
4. a container-unreachable LAN address produces an actionable failure rather than silent fallback.

## 15. Test Plan

Automated coverage must include:

1. POSIX wrapper tests for host/port prompt order, absence of a Runtime architecture prompt,
   defaults, confirmation, negative confirmation, EOF, stdin/stdout TTY combinations, and absence
   of prompt reads inside the helper container;
2. host/IP normalization tests proving bare and singly bracketed IPv6 inputs render one identical
   bracketed origin; canonical loopback forms produce local-only origins; and mismatched/double
   brackets, zone identifiers, legacy/non-canonical IPv4 spellings, IDNA lookalikes of prohibited
   hosts, other loopback, wildcard, unspecified, link-local, credentials, paths, queries, and
   fragments are rejected while ordinary internationalized DNS names remain accepted;
3. `.env` rendering tests proving same-host and port consistency, owner-only atomic publication,
   concurrent winner behavior, and no repair of existing state;
4. process-override rejection tests for the seven release quickstart values;
5. port-probe tests for available ports, unrelated conflicts, and ports already owned by the same
   persisted Compose project;
6. Runtime preflight tests for the new exact dual default, both Runtime sets validating before
   Compose startup, `auto` with Demo on/off on amd64/arm64, both explicit single values, exact dual
   order, existing `.env` preservation, and invalid values;
7. release Compose contract tests for default `8080`/`8086` publication, Demo-off default, required
   node-facing variables, no node-facing internal fallback, and no new raw service ports;
8. source Compose contract tests proving internal source defaults remain available;
9. session-cookie tests for the persisted HTTP default, advanced secure-cookie setting, absent
   production default, and strict rejection of empty/misspelled/numeric/permissive boolean values;
10. clean-install and repeated-start tests proving no data, identity, credential, Runtime, or volume
    loss;
11. native Linux amd64/arm64 LAN external-node acceptance covering initialization, callbacks, Debug
    Run, Standard Run Monitoring write, report, and Monitoring;
12. explicit Demo tests proving LAN URL use and clear failure when the host address is not routable
    from the container;
13. static workflow contract tests proving every non-interactive `./surgepilot up` in
    `release-validation.yml` and `release.yml` first creates a complete owner-only `.env` with
    non-loopback origins and does not add new publication permissions or dispatch triggers; the
    executed smoke/verifier, not YAML inspection, proves that the injected origins are reachable
    from the smoke Load Node.
14. wrapper/CLI regression tests proving helper validation failures remain visible on standard
    error even when successful normalization output is redirected to a private temporary file.
15. wrapper regression tests proving loopback warnings describe only persisted node-facing URLs,
    disclose all-interface Docker port publication, and never label legacy IPv4 notation as either
    local-only or LAN-ready.
16. PTY tests proving every valid existing configuration is shown before Runtime/Compose work;
    default/`y`/`yes` is read-only; `n`/`no`, repeated No, invalid confirmation, and first-run No
    loop safely; and advanced HTTPS No exits with manual-edit guidance.
17. helper tests proving description excludes secrets and classifies standard LAN versus advanced
    HTTPS; explicit update changes exactly four assignments, preserves LF/CRLF non-target bytes,
    rejects exotic separators, validates the reviewed SHA-256 plus candidate bytes/mode/owner,
    uses standard `os.replace`, leaves the original on pre-replacement failures, and reports a
    post-replacement fsync failure without backup or rollback. Simultaneous manual same-user editing
    in the final syscall window is unsupported.
18. installer tests proving exact-version download, SHA-256 validation, owner-only temporary state,
    stable user-local publication, launcher behavior from any directory, PATH guidance, and refusal
    to overwrite either destination;
19. failure tests proving invalid downloads, checksum mismatch, malformed payloads, version
    mismatch, missing tools, and launcher-publication failure leave no partial new installation and
    never invoke `sudo`, Docker, or shell configuration writes;
20. Ubuntu/macOS installer-only workflow smoke plus native amd64/arm64 release-stack smoke that
    installs through the generated asset before pre-provisioning the existing non-interactive
    `.env` fixture and executing the existing `up`/Debug Run/Monitoring acceptance.

Repository gates remain:

```sh
make generate-contracts
make verify
```

Release-grade LAN/SSH evidence remains outside default `make verify` where the environment requires
native runners, Docker networking, or real SSH nodes.

## 16. Out of Scope

P2-06 does not authorize:

1. automatic IP/default-route discovery or interface ranking;
2. automatic or non-interactive `.env` rewrite, repair, migration, or restart; ADR-0021 authorizes
   only explicit interactive four-field standard-LAN replacement after No, normalized review, and
   Yes;
3. a startup Web wizard, modal, or new configuration page;
4. an InfluxDB node-write System Setting or Monitoring management API;
5. TLS automation, certificate issuance, HSTS, CORS mode, or public ingress;
6. firewall changes, port forwarding, UPnP, mDNS, or service discovery;
7. per-Load-Node API or InfluxDB origins;
8. Runtime Catalog, initialization-time Runtime download, or additional architectures;
9. changes to Runner protocol, Run state machine, Workspace, storage, or credential boundaries;
10. Kubernetes, another registry, an all-in-one image, or desktop application;
11. installer/downloader scripts other than the exact ADR-0024 user-local platform Release
    installer; one-pipeline install-and-start, Homebrew, apt, yum, winget, Chocolatey, DMG, or PKG;
12. public GitHub Release/GHCR publication changes, package bootstrap, semantic tag creation, or
    workflow dispatch; the existing validation tag-bundle job may expose the already-built bundle
    tar as a second bundle-only Actions artifact without changing the public release format;
13. source `make start-full-stack` semantic changes;
14. internet-facing plain HTTP support.

## 17. Alternatives Considered

### 17.1 Keep Demo-first Compose-internal defaults

Rejected because Demo success can hide an unusable real LAN callback or Monitoring path. It proves
the internal test topology rather than the ordinary deployment topology.

### 17.2 Auto-detect and persist a host address

Rejected because multi-NIC, VPN, virtual-interface, policy-routing, and remote-Docker environments
make one automatic choice unreliable. Explicit operator confirmation is simpler and safer.

### 17.3 Ask users to edit `.env` before first startup

Rejected because it increases time-to-first-use and abandonment risk. The host wrapper can collect
the bounded values without adding a Web wizard or configuration framework.

### 17.4 Configure the address after startup in Web

Rejected as the normal release bootstrap because Web configuration cannot retroactively change
host port publication or the Compose process environment. The existing DB field remains only as an
intentional advanced policy override.

### 17.5 Keep `auto` empty when Demo is disabled

Rejected because the ordinary release now targets real external Load Nodes. Fetching the daemon
architecture gives the common same-architecture deployment one ready Runtime while keeping mixed
architecture explicit.

### 17.6 Add a downloader or new publication/dispatch workflow

Rejected because acquisition/publication is unrelated to the LAN bootstrap defect and is already
governed by P2-05. Adding it would widen scope without improving the confirmed host configuration.

### 17.7 Require a separate local-only flag or deployment-mode variable

Rejected because the explicit host input already carries the required intent. Recognizing the
three canonical loopback forms and adding a warning preserves one command and one persisted
configuration model without introducing another mode switch.

### 17.8 Rewrite the wrapper, edit with shell, regenerate `.env`, or add `configure`

Rejected because a host Python CLI changes prerequisites, shell editing cannot enforce the file and
validation contract, full-env regeneration risks non-target state, and a general configure command
unnecessarily broadens the lifecycle surface. The POSIX wrapper plus immutable helper boundary and
explicit four-field loop is sufficient.

## 18. Rollout and Governance

1. ADR-0018 is accepted and activates implementation within this document; ADR-0020 amends the
   new-release Runtime default and ADR-0021 authorizes default-Yes release configuration review and
   explicit interactive four-field standard-LAN updates.
2. Implementation must preserve the exact partial supersession of the identified ADR-0017/P2-05
   release defaults.
3. The activation changes synchronize P2-05 and ADR-0017/0018/0020/0021; they do not rewrite the
   publication or artifact design.
4. The owning workflow sections, this Slice, and the P2 index are synchronized; root instructions
   change only for a stable repository-wide invariant or routing branch.
5. `infra/release/README.md`, release `.env.example`, release Compose, wrapper, bootstrap helper,
   Runtime preflight, and tests change together during implementation.
6. Source Compose retains internal defaults and receives only regression tests required to prove
   isolation.
7. No new public GitHub Release/GHCR publication, package tag, workflow, job, permission, or
   dispatch is introduced. The existing validation tag-bundle job may additionally upload the same
   bundle tar as `validation-release-bundle` so maintainers do not download both Runtime
   architectures for a local manual check. Existing release smoke remains non-loopback evidence.

## 19. Risks and Trade-offs

1. **Interactive first run:** automation must pre-provision `.env`. This is intentional and safer
   than accepting empty input.
2. **Operator-selected host:** syntax can be validated, but reachability cannot be guaranteed before
   a real browser/node test.
3. **Dual Runtime default:** cold startup downloads and validates both official architecture sets,
   and either unavailable set blocks startup. An explicitly persisted advanced `auto` value still
   covers only the Docker daemon architecture.
4. **Default `8086` publication:** it increases LAN exposure. Random InfluxDB token authentication,
   trusted-LAN scope, firewall guidance, and no internet-facing claim bound the risk; they do not
   provide transport confidentiality.
5. **Trusted-LAN HTTP:** `SESSION_COOKIE_SECURE=false` enables ordinary LAN authentication but is not
   suitable for untrusted networks.
6. **Demo routing:** explicitly enabled Demo depends on container-to-host-LAN routing and may fail on
   some host/network configurations. P2-06 fails closed instead of adding host discovery.
7. **Raw Compose:** direct `docker compose` use becomes easier to misconfigure because release
   node-facing values are required. `./surgepilot up` is intentionally the only ordinary entry.
8. **Existing DB override:** an Admin may intentionally change `loadNodeApiBaseUrl` after bootstrap.
   That advanced override can diverge from `.env`; it is not silently mirrored to InfluxDB or host
   publication.
9. **Local-only evaluation:** the complete stack starts, but external Load Node initialization and
   Monitoring writes are not promised until both persisted node-facing origins use a reachable
   non-loopback host. The wrapper labels this URL limitation instead of blocking first use. Docker
   still publishes the configured ports on host interfaces; operators requiring local-only network
   exposure must use host firewall policy.

## 20. Review Questions

Reviewers should explicitly confirm:

1. Is an interactive terminal required only for a missing `.env`, with non-TTY automation required
   to pre-provision complete state?
2. Is explicit operator host selection preferable to automatic NIC discovery?
3. Is Demo-off plus real external-node LAN acceptance the correct ordinary release contract?
4. Is `amd64,arm64` the correct new-release default while `auto` remains an advanced
   daemon-architecture selection?
5. Is default authenticated InfluxDB port publication acceptable for the trusted-LAN contract?
6. Is direct trusted-LAN HTTP sufficiently bounded by the warning and advanced HTTPS guidance?
7. Is keeping the existing DB `loadNodeApiBaseUrl` only as an advanced post-bootstrap override
   preferable to expanding P2-06 into API/UI removal?
8. Is the source/release separation clear enough to prevent release changes from altering
   `make start-full-stack` behavior?
9. Is requiring existing non-interactive release smoke jobs to pre-provision a non-loopback,
   node-reachable `.env` sufficient without adding a new workflow or publication action?
10. Are single-bracket IPv6 normalization and strict `SESSION_COOKIE_SECURE=true|false` parsing the
    correct fail-closed boundaries?
11. Does allowing only explicit canonical loopback forms, with no default or new mode variable,
    provide local evaluation without weakening non-loopback release-smoke evidence?
