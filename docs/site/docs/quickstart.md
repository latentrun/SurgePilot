# Quickstart

Use a tagged release when you want to run SurgePilot without a source checkout.
Use the source path when you are developing SurgePilot itself.

## Install a tagged release

### Prerequisites

- A Linux host with Docker Engine 26 or newer, or a macOS host with Docker
  Desktop 26 or newer.
- Docker Compose 2.27 or newer (`docker compose`, not the legacy
  `docker-compose` command).
- Standard host tools, including `curl` and `tar`.
- An interactive terminal for the first `up`.

The installer does not install or configure Docker.

### 1. Install and start

```sh
curl -fsSL https://github.com/latentrun/SurgePilot/releases/latest/download/install.sh | sh
surgepilot up
```

The installer uses no `sudo`, does not edit shell startup files, and installs
the selected release under `${XDG_DATA_HOME:-$HOME/.local/share}/surgepilot`.
It creates the launcher at `$HOME/.local/bin/surgepilot`.

If that directory is not in `PATH`, use the absolute command printed by the
installer or enable it for the current shell:

```sh
export PATH="$HOME/.local/bin:$PATH"
surgepilot up
```

### 2. Confirm the first-run configuration

On a new deployment, `surgepilot up` asks for:

1. A host name or IP address for browsers and external Load Nodes.
2. The HTTP port for SurgePilot Web and API traffic.
3. The InfluxDB port used by Load Nodes for monitoring data.

Use an address that other machines and Load Nodes can reach. You may enter
`localhost` or `127.0.0.1` for a local evaluation, but the persisted
node-facing URLs will not work from another machine. Docker still publishes
the selected ports on host interfaces; use the host firewall if you require
loopback-only exposure.

The command displays the normalized, non-secret configuration and asks
`Use this configuration? [Y/n]`. Press Enter to accept it. A new release
deployment selects both Linux Runtime architectures, `amd64,arm64`, and keeps
the Demo Load Node disabled by default.

The command then validates and downloads the matching Runtime assets, pulls
the immutable application images, starts the stack, and prints the Web URL.
See [Deployment Configuration](./configuration.md) for the generated `.env`,
the release network fields, and optional settings.

### 3. Check the deployment

```sh
surgepilot status
surgepilot logs
```

Open the Web URL printed by `surgepilot up`, then continue with
[Your First Run](./first-run.md).

To stop the stack without deleting its volumes or `.env`:

```sh
surgepilot down
```

## Start from source

The source path requires Git, GNU or compatible Make, a POSIX shell, `curl`,
`tar`/gzip, a SHA-256 utility, the host file-lock utility (`lockf` on macOS or
`flock` on Linux), Docker, and Docker Compose. From the repository root:

```sh
make setup
make start-full-stack
```

Make downloads and verifies the pinned mise bootstrap, then installs the
repository-selected Python 3.12, Node.js 22, pnpm, and uv versions in an
isolated contributor namespace. It does not change your global runtime
versions or shell startup files. Use `make toolchain-check` for an offline,
non-mutating diagnostic, or `make toolchain-install` to repair the managed
state explicitly.

`make start-full-stack` creates secure local deployment state when the root
`.env` does not exist, builds or reuses the native Linux Load Node Runtime, and
starts the control plane, Monitoring, and the Compose-internal Demo Load Node.
Open `http://localhost:8080`.

The source and release templates are intentionally different. See
[Deployment Configuration](./configuration.md) before changing the source
`.env`.

The Demo node is running, but it is not registered in the product database yet.
Follow the source Demo instructions in [Prepare a Load Node](./first-run.md#prepare-a-load-node)
before starting a Run.

Use these commands for later lifecycle operations:

```sh
make restart-full-stack
make stop-full-stack
```

For UI review without execution readiness, use
[source preview](./startup-modes.md#source-preview) instead.
