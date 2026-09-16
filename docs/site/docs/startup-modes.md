# Startup Modes

SurgePilot has one tagged-release mode and two source-checkout entries. Choose
the mode by what you need to verify, not by which command starts fastest.

| Mode              | Use it for                                      | Runtime                                                            | Demo Load Node                                       | Application source builds      |
| ----------------- | ----------------------------------------------- | ------------------------------------------------------------------ | ---------------------------------------------------- | ------------------------------ |
| Tagged release    | A self-hosted deployment                        | Downloads validated `amd64` and `arm64` assets on a new deployment | Disabled by default                                  | No; pulls digest-pinned images |
| Source full stack | Development and a complete local execution path | Builds or reuses the native Linux Runtime                          | Started, then registered and initialized by the user | Yes                            |
| Source preview    | Login, UI, control-plane, and Monitoring review | Not prepared                                                       | Disabled                                             | Yes                            |

All modes use persistent deployment state, but release and source checkouts
have different `.env` templates. See
[Deployment Configuration](./configuration.md) for their fields and
first-run behavior.

## Tagged release

Install a release, then use the user-local launcher:

```sh
surgepilot up
surgepilot status
surgepilot logs
surgepilot down
```

If you manually downloaded and verified a versioned release archive instead,
run the same lifecycle commands as `./surgepilot up`, `./surgepilot status`,
`./surgepilot logs`, and `./surgepilot down` from the extracted directory.

The release starts Web, API, api-worker, PostgreSQL, MinIO, Nginx, InfluxDB,
and Grafana. It does not build application source or compile a Runtime on the
deployment host. Load Nodes and their Runtime remain Linux-only; macOS support
means the containerized control plane can run through Docker Desktop.

Every valid `up` displays the effective Web/API endpoint, InfluxDB node-write
endpoint, Runtime architectures, and Demo state before Runtime acquisition.
An existing valid `.env` is accepted without rewriting when you answer Yes or
press Enter. In a non-interactive environment, a missing `.env` fails closed;
automation must provide a complete owner-only `.env` first.

The generated direct-LAN configuration uses HTTP and is intended for a trusted
network. An internet-facing deployment requires an operator-managed HTTPS
reverse proxy, final externally reachable node-facing origins, and
`SESSION_COOKIE_SECURE=true`. This advanced configuration is edited explicitly
in `.env`; the first-run prompt does not configure TLS.

## Source full stack

Use the official complete source entry:

```sh
make start-full-stack
```

On first use, the command creates the root `.env` and private local state. It
then prepares the native-architecture Runtime, validates the full Compose
configuration, builds the application images, and starts Monitoring plus the
Compose-internal Demo Load Node. The default Web URL is
`http://localhost:8080`.

The Demo node must still be registered and initialized in SurgePilot before a
Run can select it. See [Prepare a Load Node](./first-run.md#prepare-a-load-node).

```sh
make restart-full-stack
make stop-full-stack
```

Both lifecycle commands preserve the root `.env`, private state, and Compose
volumes. Restart preflight completes before the running stack is stopped.

## Source preview

Use preview only when you want to inspect the login page, product UI,
control-plane behavior, or Monitoring without preparing execution resources:

```sh
make start-preview
```

Preview starts Web, API, api-worker, PostgreSQL, MinIO, Nginx, InfluxDB, and
Grafana. It deliberately skips Runtime preparation and disables the Demo Load
Node. Setup Status may report `not_configured`; Load Node initialization and
Run execution readiness are not promised.

Open `http://localhost:8080`. Stop preview without deleting its volumes:

```sh
make stop-preview
```

Preview and the source full stack use the same secure root deployment state.
Switch to `make start-full-stack` when you need a complete execution path.
