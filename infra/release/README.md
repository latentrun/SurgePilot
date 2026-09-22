# SurgePilot @@RELEASE_VERSION@@

## Quickstart

```sh
surgepilot up
```

This command form applies to deployments created by `install.sh`. If you manually downloaded and
extracted the advanced release archive instead, run `./surgepilot up` from that archive directory
and use `./surgepilot` for the lifecycle commands below.

The installer uses no `sudo`, does not edit shell startup files, and places its launcher at
`$HOME/.local/bin/surgepilot`. If that directory is not in `PATH`, use the absolute launcher path
printed by the installer or run `export PATH="$HOME/.local/bin:$PATH"` for the current shell. Docker
Engine/Desktop 26+ and Docker Compose 2.27+ are required by `surgepilot up`, not by installation.

On the first run, the wrapper asks for the host or IP and the HTTP and InfluxDB ports. Use a
reachable LAN address for other computers and Load Nodes. For a local first look, you may explicitly
enter `localhost`, `127.0.0.1`, or `::1`; the complete stack still starts, but the wrapper labels the
configured node-facing URLs as local-only. Docker still publishes the configured ports on host
interfaces, so use the host firewall if local-only network exposure is required. Review and confirm
the normalized URLs before the wrapper writes an owner-only `.env` and starts containers. Legacy
IPv4 spellings such as `127.1` or integer/octal/hexadecimal forms are rejected; use canonical
address notation. Unicode hostnames are revalidated after IDNA normalization so lookalikes of
loopback or Compose-only names are also rejected.

Before Runtime acquisition or container changes, every valid `surgepilot up` displays the
effective Web/API and InfluxDB node-write endpoints, Runtime architectures, and Demo state. In an
interactive terminal it then asks `Use this configuration? [Y/n]`. Press Enter to use the displayed configuration.
Empty input, `y`, and `yes` are Yes, case-insensitively; other input repeats the confirmation
question. For the initial confirmation of an existing `.env`, Yes accepts the current configuration
without rewriting it. On first run, Yes creates an owner-only `.env` from the displayed
configuration.

On first run, choosing No repeats the LAN host and port questions. With an existing standard
direct-LAN HTTP configuration, choosing No opens the same entry loop and uses the current LAN host,
HTTP port, and InfluxDB node-write port as defaults. Choosing No lets you change only the LAN host,
HTTP port, and InfluxDB node-write port. After a changed direct-LAN proposal is reviewed, Yes
atomically replaces only these four assignments:

- `SURGEPILOT_HTTP_PORT`;
- `SURGEPILOT_NODE_API_BASE_URL`;
- `SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT`;
- `SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL`.

The wrapper derives the URLs from the normalized host and matching ports. All credentials and
secrets, Runtime selection, Demo state, cookie policy, comments, unknown fields, and other
non-network values are preserved. Advanced HTTPS configuration must be edited explicitly in .env.
Choosing No for an advanced HTTPS configuration stops before Runtime or Compose work and prints
that guidance.

The update helper revalidates the complete owner-only configuration in a private temporary file,
then checks the exact reviewed `.env` SHA-256 immediately before calling standard `os.replace`.
This flow provides no strict compare-and-swap (CAS), locks, backups, or automatic rollback. The
final check-to-replacement syscall window therefore remains open, and simultaneous manual
same-user editing in that window is unsupported. A post-replacement directory durability failure
stops startup and requires inspection of `.env`.

On a new deployment, `surgepilot up` acquires and validates both official Linux Runtime sets
(`amd64` and `arm64`) so later external Load Nodes work without an architecture choice. Runtime
assets are cached under `.surgepilot/runtime-artifacts` and reused only after full validation.
For tagged releases, these Runtime sets are version-matched, prebuilt GitHub Release assets.
`surgepilot up` downloads them or reuses fully validated cached copies; it never compiles Runtime
assets on the deployment host.

Open the `Web` URL printed after startup. The default direct HTTP setup is intended for a trusted
LAN and does not provide transport encryption. Internet-facing deployments require an
operator-managed HTTPS reverse proxy, final node-facing origins, and
`SESSION_COOKIE_SECURE=true`.

Use `surgepilot status`, `surgepilot logs`, and `surgepilot down` for the minimal lifecycle. `down` preserves volumes and all deployment state.

To run more than one installation on the same Docker host, set a distinct `COMPOSE_PROJECT_NAME` in each deployment directory before its first `surgepilot up`. Keep that value stable for later lifecycle commands and installed transitions.

The release `.env` is the ordinary deployment input after first run. Process-level overrides for
the published ports, node-facing URLs, Runtime architectures, Demo selection, or cookie policy are
rejected so validation and Compose use one persisted source. Existing `.env` files are validated
but never repaired or rewritten automatically. The explicit interactive No/re-entry/Yes sequence
above is the only quick rewrite path, and it preserves every field outside the four network
assignments. Advanced persisted Runtime choices are `auto`, `amd64`, `arm64`, and `amd64,arm64`.

The optional Demo Load Node is disabled by default. To use it as a development aid, deliberately
set `SURGEPILOT_DEMO_LOAD_NODE_ENABLED=true` in `.env` before `surgepilot up`. It uses the same LAN
API and InfluxDB URLs as an external node, so those URLs must also be routable from Docker
containers; loopback URLs are therefore invalid when Demo is enabled. Demo credentials and host
identity are generated only when Demo is enabled.

The wrapper never repairs existing private deployment state automatically. If you manually create
the Runtime staging directories, create them with owner-only permissions:

```sh
install -d -m 700 .surgepilot .surgepilot/runtime-artifacts
```

If ordinary `mkdir -p` already created them, run `chmod 700 .surgepilot
.surgepilot/runtime-artifacts` before `surgepilot up`. Keep `.env` and secret files at mode `600`.

With a complete valid existing `.env`, non-interactive startup displays the same non-secret
configuration summary and does not prompt or read standard input.
Non-interactive startup never rewrites an existing .env.
Non-interactive first startup fails closed. CI or automation must create a complete owner-only
`.env` before running `surgepilot up`. Do not copy `.env.example` directly because it intentionally
contains secret placeholders. In automation that already provides Python 3.12, use the bundled
bootstrap helper so secrets, the Monitoring token, permissions, and final origins are created by
the same implementation as interactive startup:

```sh
python scripts/bootstrap_deployment_env.py \
  --root . \
  --release-http-port 8080 \
  --release-node-api-base-url "http://192.168.1.20:8080" \
  --release-influxdb-host-port 8086 \
  --release-influxdb-node-write-url "http://192.168.1.20:8086" \
  --release-demo-enabled false \
  --release-runtime-architectures amd64,arm64 \
  --session-cookie-secure false
```

Replace the example host with an explicit non-loopback address reachable from browsers and Load
Nodes. An automation system that does not use the helper must provide an equivalent complete
owner-only `.env` and private token state; unexpanded template placeholders are rejected.

For an installer-managed upgrade, back up persistent volumes, finish active work, rerun the exact
release installer, and then run `surgepilot up`. The wrapper prepares target assets before downtime,
refuses active work, and uses forward-only same-target retry after migration starts. It does not
provide automatic rollback. Reinitialize required Load Nodes after the control plane reaches the
new version. Manually extracted bundles remain expert-managed and outside this transition protocol.
