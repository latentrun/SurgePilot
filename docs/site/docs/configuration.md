# Deployment Configuration

SurgePilot stores deployment settings in a root `.env` file. Normal users do
not need to create this file by hand: the official startup command creates it
on the first run, generates private values, validates the result, and keeps it
for later starts.

## Choose the correct template

SurgePilot intentionally has two templates because the release and source
lifecycles have different networking, Runtime, and build requirements.

| Deployment      | Template in this repository                                                                | Ordinary command                                |
| --------------- | ------------------------------------------------------------------------------------------ | ----------------------------------------------- |
| Tagged release  | `infra/release/.env.example`, shipped as `.env.example` in the installed release directory | `surgepilot up` or `./surgepilot up`            |
| Source checkout | Root `.env.example`                                                                        | `make start-full-stack` or `make start-preview` |

Do not copy one template over the other. The release template requires final
node-facing LAN origins and secure-cookie intent. The source template contains
development ports, source-build mirrors, and locally generated Runtime inputs
that do not belong in a release deployment.

## How `.env` is managed

1. If `.env` is missing, official startup copies the correct template,
   generates the private bootstrap values, and writes owner-only deployment
   state.
2. If `.env` already exists, startup treats it as authoritative. It does not
   overwrite, rotate, or repair existing values.
3. Bootstrap values explicitly supplied through the process environment are
   persisted only during first-run creation. Supplying a conflicting value on
   a later run fails closed.
4. Release first-run asks for the host and two published ports, then persists
   the final API and InfluxDB node-write origins. On later interactive starts,
   answering **No** at the configuration confirmation can update only those
   four network fields.
5. Source startup does not use the release reconfiguration flow. Edit the
   source `.env` deliberately when an override is needed.

After a manual change, run `surgepilot up` for a release or
`make restart-full-stack` for a running source stack. Both paths validate the
effective configuration before starting services.

::: danger Keep generated secrets stable
Do not rotate deployment secrets by editing `.env`. In particular, losing or
changing the SSH credential encryption key makes existing stored Load Node
credentials unreadable. Existing database and object-storage volumes also
retain the identities used when they were initialized.
:::

## Reading the reference

- **No** means the generated or template value is suitable for ordinary use.
- **First run** means the release prompt supplies the deployment-specific
  value.
- **Conditional** means change it only for the described deployment mode.
- **Advanced** means leave it unchanged without an operational reason and a
  restart plan.
- **Managed** means an official startup or Runtime command supplies the value;
  do not persist it manually in normal use.
- **Not present** means that template does not expose the setting.

## Startup and network settings

| Variable                                        | Release                                   | Source                  | Configure? Meaning                                                                                                                                                                                                                                               |
| ----------------------------------------------- | ----------------------------------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `COMPOSE_PROJECT_NAME`                          | `surgepilot`                              | `surgepilot`            | **No.** Docker Compose resource namespace. Changing it selects a different stack and different named volumes.                                                                                                                                                    |
| `SURGEPILOT_HTTP_PORT`                          | `8080`                                    | `8080`                  | **First run for release; conditional for source.** Host port published by Nginx for the Web UI, API, and Grafana path. Use a free port.                                                                                                                          |
| `POSTGRES_HOST_PORT`                            | Not present                               | `5432`                  | **Source only, conditional.** Host port published by the source PostgreSQL service. Release PostgreSQL is not published.                                                                                                                                         |
| `SURGEPILOT_API_HOST_PORT`                      | Not present                               | `8000`                  | **Source only, conditional.** Direct host port for the source API container; this is separate from the normal Nginx entry.                                                                                                                                       |
| `DEFAULT_WORKSPACE_NAME`                        | `Default Workspace`                       | `Default Workspace`     | **Conditional.** Name used when the first Admin creates the initial Workspace. It does not rename an existing Workspace.                                                                                                                                         |
| `SURGEPILOT_NODE_API_BASE_URL`                  | Active LAN example, replaced at first run | Commented example       | **First run for release; conditional for source external nodes.** Final API origin reachable by Load Nodes. Source Demo uses a Compose-internal origin when this is absent. A DB-backed System Setting can override the application fallback.                    |
| `SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT`      | `8086`                                    | `8086`                  | **First run for release; conditional for source.** Host port published for authenticated Load Node writes to InfluxDB. It must differ from the HTTP port.                                                                                                        |
| `SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL` | Active LAN example, replaced at first run | Commented example       | **First run for release; conditional for source external nodes.** Final InfluxDB origin reachable by Load Nodes. Set it together with the node API origin.                                                                                                       |
| `SESSION_COOKIE_SECURE`                         | `false`                                   | Not present             | **Conditional.** Release HTTP mode requires `false`; an operator-managed HTTPS deployment sets `true` and uses an HTTPS node API origin.                                                                                                                         |
| `SURGEPILOT_DEMO_LOAD_NODE_ENABLED`             | `false`                                   | `true`                  | **Conditional.** Enables the optional Compose-internal Demo Load Node. Release defaults it off; the source full stack defaults it on; preview forces it off without rewriting `.env`.                                                                            |
| `SURGEPILOT_RUNTIME_ARCHITECTURES`              | `amd64,arm64`                             | `auto`                  | **No for normal startup.** Architectures prepared for Load Node Runtime assets. Release first-run keeps both supported architectures; source `auto` selects the native Docker daemon architecture. Valid values are `auto`, `amd64`, `arm64`, and `amd64,arm64`. |
| `APP_ENV`                                       | Not present                               | `development`           | **Source direct-host development only.** Selects application environment defaults. Official Compose supplies its own fixed value.                                                                                                                                |
| `DATABASE_URL`                                  | Not present                               | Local PostgreSQL URL    | **Source direct-host development only.** Database connection used by `make dev-api`, `make dev-worker`, and migrations outside Compose. Official Compose supplies an internal URL.                                                                               |
| `MINIO_ENDPOINT`                                | Not present                               | `http://localhost:9000` | **Source direct-host development only.** MinIO endpoint for API processes outside Compose. Official Compose supplies its internal endpoint.                                                                                                                      |

## Deployment identity, secrets, and MinIO

| Variable                        | Template value                                | Configure? Meaning                                                                                                                                                        |
| ------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `RUNNER_INTERNAL_TOKEN`         | Placeholder replaced with a random token      | **Managed.** Shared internal authentication material used between the API and Runner. Keep it private and stable.                                                         |
| `SSH_CREDENTIAL_ENCRYPTION_KEY` | Placeholder replaced with a random base64 key | **Managed.** AES-256-GCM key for stored Load Node credentials. It must decode to exactly 32 bytes and must remain stable while the database is reused.                    |
| `MINIO_BUCKET`                  | `surgepilot`                                  | **No.** Object-storage bucket used for dependency files and Run artifacts.                                                                                                |
| `MINIO_ACCESS_KEY`              | `minioadmin`                                  | **No for the bundled service.** API-side MinIO access identity. It must equal the MinIO root user in the bundled deployment.                                              |
| `MINIO_SECRET_KEY`              | Placeholder replaced with a random password   | **Managed.** API-side MinIO secret. It must equal the MinIO root password in the bundled deployment.                                                                      |
| `MINIO_ROOT_USER`               | `minioadmin`                                  | **No for the bundled service.** MinIO initialization user; must match the access key.                                                                                     |
| `MINIO_ROOT_PASSWORD`           | Same generated value as the MinIO secret      | **Managed.** MinIO initialization password; must match the API-side secret. Changing it does not reinitialize an existing MinIO volume.                                   |
| `MINIO_REGION`                  | Commented                                     | **Advanced, direct-host only.** Optional region passed to the MinIO client when the endpoint does not already determine it. Official Compose does not pass this override. |
| `MINIO_SECURE`                  | Commented, default `false`                    | **Advanced, direct-host only.** Enables TLS when a scheme-less direct-host MinIO endpoint is used. An explicit `https` endpoint already selects TLS.                      |

## Monitoring bootstrap and links

| Variable                                          | Template value                                      | Configure? Meaning                                                                                                                                                |
| ------------------------------------------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SURGEPILOT_MONITORING_INFLUXDB_USERNAME`         | `surgepilot`                                        | **No for ordinary first run.** InfluxDB initialization username. Do not expect edits to reinitialize an existing volume.                                          |
| `SURGEPILOT_MONITORING_INFLUXDB_PASSWORD`         | Placeholder replaced with a random password         | **Managed.** InfluxDB initialization password. It must not begin with `-`, because the setup CLI parses such a value as a flag.                                   |
| `SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE_HOST`  | Example path replaced with a private generated file | **Managed.** Host path mounted as the InfluxDB token secret. Official startup creates the private token file and writes the correct path for the selected layout. |
| `SURGEPILOT_MONITORING_INFLUXDB_ORG`              | `surgepilot`                                        | **No.** InfluxDB organization used by setup, the Backend Listener, and monitoring links.                                                                          |
| `SURGEPILOT_MONITORING_INFLUXDB_BUCKET`           | `jmeter`                                            | **No.** InfluxDB bucket receiving Standard Run metrics.                                                                                                           |
| `SURGEPILOT_GRAFANA_ADMIN_USER`                   | `admin`                                             | **Conditional.** Grafana bootstrap Admin username. Set it before the Grafana volume is initialized if a different name is required.                               |
| `SURGEPILOT_GRAFANA_ROOT_URL`                     | Commented, Grafana subpath expression               | **Advanced.** Grafana server root URL used when it is served below `/grafana/`. The template value matches the bundled proxy layout.                              |
| `SURGEPILOT_MONITORING_DASHBOARD_UID`             | Commented, `surgepilot-jmeter-13644`                | **Advanced.** UID used to build links to the provisioned read-only JMeter dashboard. Change only with matching Grafana provisioning.                              |
| `SURGEPILOT_MONITORING_DASHBOARD_SLUG`            | Commented, `jmeter-load-test`                       | **Advanced.** Slug used to build links to the provisioned dashboard. Change only with matching Grafana provisioning.                                              |
| `SURGEPILOT_MONITORING_ENABLED`                   | Commented, default `false` for a direct-host API    | **Direct-host only.** Official full-stack Compose enables monitoring explicitly, so this `.env` override does not disable bundled monitoring.                     |
| `SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED` | Commented, default `false` for a direct-host API    | **Direct-host only.** Tells a directly started API whether monitoring token state was configured externally. Official Compose supplies the correct value.         |
| `SURGEPILOT_MONITORING_GRAFANA_BASE_PATH`         | Commented, `/grafana`                               | **Direct-host only.** Base path used for generated Grafana links. Official Compose fixes the bundled path to `/grafana`.                                          |
| `SURGEPILOT_MONITORING_TIME_PADDING_SECONDS`      | Commented, `60`                                     | **Advanced.** Seconds added around a Run time range when generating monitoring links.                                                                             |

The InfluxDB initialization username, password, organization, and bucket must
not start with `-`; the InfluxDB setup CLI would parse such a value as a flag.

## Source Runtime and image-build settings

These settings exist only in the source template. Tagged releases pull pinned
application images and validated Runtime assets instead of building them from
source.

| Variable                                             | Template value                  | Configure? Meaning                                                                                                                                                              |
| ---------------------------------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `LOAD_NODE_RUNTIME_VERSION`                          | Commented                       | **Managed.** Runtime version written to generated `runtime.env` state by the official Runtime builder.                                                                          |
| `LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR`                | Commented absolute-path example | **Managed.** Host directory written to generated Runtime state and mounted read-only into API services.                                                                         |
| `SURGEPILOT_SKIP_RUNTIME_PREFLIGHT`                  | Commented, `1`                  | **Advanced manual/debug only.** Skips Runtime preparation for source full-stack startup. It does not skip deployment bootstrap and does not promise Load Node or Run readiness. |
| `RUNTIME_JMETER_SHA256`                              | Commented                       | **Advanced.** Optional expected checksum supplied to the source Runtime builder for its JMeter download.                                                                        |
| `RUNTIME_CASUTG_SHA256`                              | Commented                       | **Advanced.** Optional expected checksum supplied to the source Runtime builder for the Concurrency Thread Group plugin.                                                        |
| `RUNTIME_JSON_SHA256`                                | Commented                       | **Advanced.** Optional expected checksum supplied to the source Runtime builder for the JSONPath plugin.                                                                         |
| `RUNTIME_TST_SHA256`                                 | Commented                       | **Advanced.** Optional expected checksum supplied to the source Runtime builder for the Throughput Shaping Timer plugin.                                                         |
| `RUNTIME_RANDOM_CSV_SHA256`                          | Commented                       | **Advanced.** Optional expected checksum supplied to the source Runtime builder for the Random CSV Data Set plugin.                                                              |
| `RUNTIME_INFLUXDB2_LISTENER_SHA256`                  | Commented                       | **Advanced.** Optional expected checksum supplied to the source Runtime builder for the InfluxDB2 listener plugin.                                                              |
| `SURGEPILOT_PIP_INDEX_URL`                           | Commented mirror example        | **Conditional.** Python package index used by source Docker builds and the Runtime builder. Leave unset for the upstream default.                                               |
| `SURGEPILOT_NPM_REGISTRY`                            | Commented mirror example        | **Conditional.** npm registry used by the source Web image build. Leave unset for the upstream default.                                                                         |
| `SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_MIRROR`          | Commented invalid example       | **Conditional.** Ubuntu package mirror used only during source Docker builds. Replace the example with a real mirror before enabling it.                                        |
| `SURGEPILOT_DOCKER_BUILD_UBUNTU_APT_SECURITY_MIRROR` | Commented invalid example       | **Conditional.** Ubuntu security mirror used only during source Docker builds.                                                                                                  |
| `SURGEPILOT_DOCKER_BUILD_DEBIAN_APT_MIRROR`          | Commented invalid example       | **Conditional.** Debian package mirror used only during source Docker builds.                                                                                                   |
| `SURGEPILOT_DOCKER_BUILD_DEBIAN_APT_SECURITY_MIRROR` | Commented invalid example       | **Conditional.** Debian security mirror used only during source Docker builds.                                                                                                  |
| `VITE_API_BASE_URL`                                  | Commented direct-API example    | **Advanced source build only.** Build-time seed for the Web client. The bundled Web runtime uses same-origin `/api`, so ordinary deployments leave it unset.                    |

## DB-backed System Settings fallbacks

The following `.env` values are used only when the corresponding database
System Setting is absent. For normal policy changes, use **Admin → System
Settings** instead of editing `.env`. A deployment restart is required for an
environment fallback change to be loaded; an existing DB value still wins.

| Variable                                         | Fallback                | Meaning                                                                                                                         |
| ------------------------------------------------ | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `ALLOW_SIGNUP`                                   | `true`                  | Whether users after the first Admin may register. The first Admin bootstrap remains available when setup is incomplete.         |
| `DEPENDENCY_FILE_MAX_BYTES`                      | `104857600`             | Maximum dependency-file upload size in bytes.                                                                                   |
| `DEPENDENCY_FILE_ALLOWED_EXTENSIONS`             | Empty                   | Comma-separated allowlist. Empty means no extension allowlist is applied; filename safety checks still apply.                   |
| `DEPENDENCY_FILE_PREVIEW_MAX_BYTES`              | `65536`                 | Maximum bytes returned by the single-file text preview.                                                                         |
| `DEPENDENCY_FILE_PREVIEW_BINARY_DENY_EXTENSIONS` | Template extension list | Comma-separated extensions that are never rendered as text previews.                                                            |
| `SURGEPILOT_MAX_SCENARIO_ITEMS_PER_TEST_PLAN`    | `20`                    | Maximum enabled Scenario items in one Test Plan.                                                                                |
| `SURGEPILOT_SINGLE_NODE_CONCURRENCY_SOFT_LIMIT`  | `1000`                  | Per-node concurrency threshold that requires explicit high-concurrency confirmation.                                            |
| `SURGEPILOT_MAX_RUN_DURATION_SECONDS`            | `86400`                 | Maximum configured Run duration.                                                                                                |
| `SURGEPILOT_MAX_RAMP_UP_SECONDS`                 | `86400`                 | Maximum ramp-up duration; it cannot exceed the effective Run-duration limit.                                                    |
| `SURGEPILOT_MAX_DELAY_SECONDS`                   | `86400`                 | Maximum configured start delay.                                                                                                 |
| `SURGEPILOT_MAX_ITERATIONS`                      | `1000000`               | Maximum iteration count in an iteration-based load model.                                                                       |
| `SURGEPILOT_MAX_TARGET_RPS`                      | `100000`                | Maximum target requests per second accepted by load-model validation. This is a configuration ceiling, not a performance claim. |
| `SURGEPILOT_MAX_SLA_RULES_PER_TEST_PLAN`         | `5`                     | Maximum enabled SLA rules in a Standard Test Plan.                                                                              |
| `SURGEPILOT_JMETER_MEMORY_XMX`                   | `4G`                    | JMeter maximum heap written into execution configuration. Valid values are a positive integer followed by `K`, `M`, or `G`.     |

## Advanced operational guardrails

These values already have application and Compose defaults. Leave them
commented unless measured behavior justifies a change. A restart is required.

### Load Node initialization

| Variable                                    | Default                  | Meaning                                                                                             |
| ------------------------------------------- | ------------------------ | --------------------------------------------------------------------------------------------------- |
| `LOAD_NODE_INIT_COMMAND_TIMEOUT_SECONDS`    | `30`                     | Timeout for an individual command during Load Node initialization.                                  |
| `LOAD_NODE_RUNTIME_INSTALL_TIMEOUT_SECONDS` | `120`                    | Timeout for installing the Runtime on a Load Node.                                                  |
| `LOAD_NODE_DEFAULT_RUNNER_HOME`             | `/opt/surgepilot/runner` | Default remote Runner home used when a Load Node does not specify another path.                     |
| `LOAD_NODE_SSH_CONNECT_TIMEOUT_SECONDS`     | `15`                     | SSH connection timeout for Load Node operations.                                                    |
| `LOAD_NODE_INIT_TIMEOUT_SECONDS`            | `120`                    | Age threshold used to recover stale initialization attempts and nodes left in initialization state. |
| `LOAD_NODE_INIT_LOG_TAIL_BYTES`             | `65536`                  | Maximum initialization-log tail retained for status and failure reporting.                          |
| `LOAD_NODE_GENERATED_KEY_TYPE`              | `ed25519`                | SSH key type used when SurgePilot generates a Load Node keypair.                                    |

### Run control and artifacts

| Variable                                          | Default     | Meaning                                                                                                              |
| ------------------------------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------- |
| `SURGEPILOT_RUN_HEARTBEAT_TIMEOUT_SECONDS`        | `60`        | Maximum wait after Runner acceptance for execution to start, and maximum gap between heartbeats after it is running. |
| `SURGEPILOT_RUN_ACCEPTED_TIMEOUT_SECONDS`         | `120`       | Maximum wait for the Runner to accept a remotely requested allocation.                                               |
| `SURGEPILOT_RUN_STOP_GRACE_SECONDS`               | `60`        | Grace period allowed for a normal stop before force-kill handling.                                                   |
| `SURGEPILOT_RUN_FORCE_KILL_SSH_TIMEOUT_SECONDS`   | `30`        | SSH timeout used by force-kill control.                                                                              |
| `SURGEPILOT_RUNNER_CALLBACK_RETENTION_DAYS`       | `30`        | Retention period for persisted Runner callback records.                                                              |
| `SURGEPILOT_RUN_CONTROL_STALE_SECONDS`            | `120`       | Age after which claimed Run-control work is considered stale for recovery.                                           |
| `SURGEPILOT_NODE_COOLDOWN_SECONDS`                | `300`       | Cooldown period after a force-kill before that Load Node may be allocated again.                                     |
| `SURGEPILOT_RUN_ARTIFACT_MAX_BYTES`               | `209715200` | Maximum accepted ordinary Run artifact size.                                                                         |
| `SURGEPILOT_RUN_TERMINAL_LATE_ARTIFACT_MAX_BYTES` | `1048576`   | Maximum accepted artifact size after the Run has already reached a terminal state.                                   |
| `SURGEPILOT_RUN_TERMINAL_LATE_ARTIFACT_SECONDS`   | `300`       | Time window in which a bounded late artifact may be accepted after terminal state.                                   |
| `SURGEPILOT_SINGLE_NODE_CONCURRENCY_HARD_LIMIT`   | `10000`     | Hard per-node concurrency ceiling. It cannot be bypassed by confirmation and is not DB-editable.                     |

### API Catalog and Debug HTTP Trace

| Variable                                           | Default    | Meaning                                                                  |
| -------------------------------------------------- | ---------- | ------------------------------------------------------------------------ |
| `SURGEPILOT_API_CATALOG_SPEC_MAX_BYTES`            | `10485760` | Maximum uploaded API Catalog specification size.                         |
| `SURGEPILOT_DEBUG_TRACE_MAX_REQUESTS`              | `100`      | Maximum request records retained from one Debug HTTP Trace.              |
| `SURGEPILOT_DEBUG_TRACE_BODY_MAX_BYTES`            | `65536`    | Maximum inline request or response body bytes retained per trace record. |
| `SURGEPILOT_DEBUG_TRACE_ARTIFACT_MAX_BYTES`        | `10485760` | Maximum Debug HTTP Trace artifact size accepted for parsing.             |
| `SURGEPILOT_DEBUG_TRACE_RECORD_MAX_BYTES`          | `131072`   | Maximum encoded size of one trace record.                                |
| `SURGEPILOT_DEBUG_TRACE_BODY_BLOB_MAX_BYTES`       | `5242880`  | Maximum size of one separately stored trace body blob.                   |
| `SURGEPILOT_DEBUG_TRACE_BODY_BLOB_TOTAL_MAX_BYTES` | `20971520` | Maximum total separately stored trace body bytes for one trace artifact. |

## Before editing manually

1. Confirm whether the value belongs in the release or source template.
2. Stop if the setting is marked **Managed**.
3. Preserve `.env` ownership and owner-only permissions.
4. Never commit `.env` or generated secret files.
5. For a release network change, prefer the `surgepilot up` confirmation flow
   over direct editing.
6. Run the official startup command after the change and read its effective
   configuration summary before services start.

For startup behavior and supported modes, continue with
[Startup Modes](./startup-modes.md). For product terms, see
[Terms and FAQ](./faq.md).
