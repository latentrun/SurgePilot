# P1-00 Monitoring

- Document status: Accepted for implementation
- Stage: P1
- Capability:`monitoring`
- Scope Gate:`docs/sdd/00-product-scope-and-priority.md` §6
- P1 Index:`docs/sdd/slices/P1-README.md`
- Runtime Boundary:`docs/sdd/p0-runtime-bootstrap-plan.md` §4/§7/§10
- API Contract Boundary:`docs/sdd/04-api-contract-guidelines.md`
- Runner Boundary:`docs/sdd/05-runner-protocol-and-run-state-machine.md`
- Frontend Route Boundary:`docs/sdd/08-frontend-routing-and-ui-rules.md`
- Optional local Taurus reference: ignored `docs/reference/taurus/JMeter.md`, if present; otherwise use the upstream Taurus/JMeter documentation.
- External Dashboard Source:Grafana Dashboard `13644` (`jmeter-load-test-org-md-jmeter-influxdb2-visualizer-influxdb-v2-0-flux`)
- External JMeter Plugin Source:`mderevyankoaqa/jmeter-influxdb2-listener-plugin`

## 1. Goal

P1-00 adds **JMeter Backend Listener / InfluxDB write config bridge + same-origin Grafana iframe** to SurgePilot.

The scope of the first version of Monitoring converges to:

1. deployment-level monitoring config;
2. Standard Run writes JMeter BackendListener indicators into InfluxDB2;
3. Run Report and `/observability/monitoring` provide read-only Grafana entry;
4. Debug Run never writes to InfluxDB and only returns safe disabled / muted hint;
5. The official compose profile provides InfluxDB2, Grafana, datasource provisioning, Dashboard 13644 provisioning and `/grafana/*` same-origin proxy;
6. The remote Load Node uses node-facing InfluxDB write URL and does not use compose-internal service DNS;
7. The runtime is still a self-contained bundle, and the new InfluxDB2 listener plugin must not destroy the P0 runtime/init/Runner boundary;
8. Tokens and per-run secrets do not enter API responses, Web, JMX plaintext, YAML, artifacts, or logs.

P1-00 does not introduce the Grafana/InfluxDB management plane, workspace-level Monitoring settings, Admin settings UI, listener tuning UI, or historical compatibility/backfill design.

## 2. PRD / Scope Trace

`docs/sdd/00-product-scope-and-priority.md` §6 Limit P1 Monitoring to read-only entry + JMeter Backend Listener / InfluxDB write config Write link configuration and explicitly exclude Grafana datasource management, Dashboard editing or InfluxDB management.

This Slice locks the following range interpretation:

1. The source of the first version of write config is deployment env/secret mount, not workspace override.
2. The first version only retains `getMonitoringEmbed`, `getRunMonitoringLink` and Nginx session-check; it does not provide Monitoring settings read/write API, and does not add `GET /monitoring/status`.
3. The Run Report page uses `getRunMonitoringLink` to combine the monitoring status; P1-00 does not require the `RunReportDetail` embedded monitoring field.
4. Debug Run monitoring is a hard constraint and takes precedence over any deployment default, feature flag or debug artifact requirements.
5. P1-00 does not change the P0 Run state machine, P0 artifact ingest, P0 runtime init, or Stop/Abort semantics.
6. The Web only consumes the generated OpenAPI client, does not read the token, does not display the node/internal URL, and does not directly access the Grafana external login page.
7. Runner is still an independent application, does not import API internals, does not access DB/MinIO, and does not decrypt DB token.

## 3. In Scope

1. Deployment-level monitoring config:
   - `SURGEPILOT_MONITORING_ENABLED`;
   - `SURGEPILOT_MONITORING_INFLUXDB_INTERNAL_URL`;
   - `SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL`;
   - `SURGEPILOT_MONITORING_INFLUXDB_ORG`;
   - `SURGEPILOT_MONITORING_INFLUXDB_BUCKET`;
   - `SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED`;
   - token from env or secret mount;
   - fixed listener defaults.
2. Monitoring resolver:
   - Debug Run returns dynamic disabled state; no DB snapshot required.
   - Standard Run reads deployment config only.
   - Enabled/config_error Standard Run must persist a minimal non-secret `run_monitoring_configs` snapshot.
3. API:
   - `GET /api/v1/monitoring/embed`.
   - `GET /api/v1/runs/{runId}/monitoring`.
   - Run Report page obtains monitoring state by calling `getRunMonitoringLink`.
   - one internal session-check endpoint for Nginx `auth_request`.
   - API owns time-window building and Grafana URL building.
4. api-worker:
   - enabled Standard Run uploads `secrets/monitoring.properties` before Runner starts.
   - upload failure is fail fast.
   - Debug, disabled, and config_error Runs do not upload monitoring secret.
5. Runner / Runtime:
   - all runs keep Taurus execution through runtime `bzt -n surgepilot.yml`.
   - all Taurus bundles use `surgepilot-jmeter-wrapper` as `modules.jmeter.path`.
   - wrapper pass-throughs for Debug/disabled/config_error and injects only enabled Standard Run.
   - runtime bundle includes the InfluxDB2 listener plugin.
6. Web:
   - `/observability/monitoring` same-origin Grafana iframe.
   - Run Report `Open Monitoring` for usable Standard Run monitoring only.
   - Debug muted hint and not configured/config_error empty states.
   - no Admin settings link, no diagnostics panel, no token/internal/node URL display.
7. Compose/Nginx:
   - official monitoring profile provisions InfluxDB2/Grafana/Dashboard 13644.
   - `/grafana/*` goes through SurgePilot session gate.
   - no `/influxdb/*` Nginx write proxy.

## 4. Out of Scope

1. Workspace Monitoring settings, workspace override, workspace token storage, Admin settings UI.
2. `GET /api/v1/monitoring/settings` and `PATCH /api/v1/monitoring/settings`.
3. `GET /api/v1/monitoring/status` or equivalent extra status endpoint.
4. `monitoring_settings` table.
5. Token DB crypto, key rotation, token fingerprint, tokenConfigured API diagnostics.
6. Listener parameter API/DB/UI tuning.
7. Grafana datasource management UI.
8. Grafana Dashboard import/edit/template UI.
9. InfluxDB bucket/org/token lifecycle management UI.
10. Grafana management/provisioning API calls from product API.
11. Grafana users, OAuth/OIDC/SAML/LDAP or login proxy.
12. Unified Nginx InfluxDB write route such as `/influxdb/*`.
13. SSH tunnel as default InfluxDB write path.
14. Debug Run monitoring data.
15. Run List Monitoring quick action.
16. Multi-node monitoring aggregation semantics.
17. Historical compatibility, backfill, downgrade, or migration compatibility for pre-P1 monitoring rows.
18. Complete Dashboard 13644 JSON pasted into this SDD.

Future workspace-level Monitoring configuration, token DB storage, listener tuning UI, Grafana provisioning API, real-VM smoke automation, and multi-node monitoring semantics require a separate Slice or ADR.

## 5. Preconditions

1. P0 Runtime Bootstrap is landed; Runner does not depend on system Taurus/JMeter.
2. P0 Run state machine, callback idempotency, Stop/Abort, node lease, and artifact ingest remain stable.
3. P1 governance has authorized P1-00 as the active Monitoring Slice.
4. Dashboard 13644 UID, slug, Flux datasource, `runId` variable, and `from/to` URL behavior are smoke-verifiable in the compose profile.
5. InfluxDB2 listener plugin jar/classname/argument names are pinned by runtime smoke.
6. Remote Load Node deployment requires both SSH connectivity and `Load Node -> SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL` HTTP(S) connectivity. SSH connectivity alone is not sufficient.

## 6. Locked Core Decisions

| ID | Decision |
| --- | --- |
| KTD-01 | Resolver first branch is always `if runType == "debug": disabled(debug_run_not_monitored)`. |
| KTD-02 | API, api-worker, and Runner all guard Debug Run no-write behavior. |
| KTD-03 | `run_monitoring_configs` is written only for enabled/config_error Standard Runs; Debug Run disabled state is computed dynamically and must not require persistence. |
| KTD-04 | API owns `platformMonitoringUrl`, `iframeUrl`, `grafanaFrom`, and `grafanaTo` generation. |
| KTD-05 | Terminal window is `startedAt - 60s` to `endedAt + 60s`, in epoch ms. |
| KTD-06 | Active run window is `startedAt - 60s` epoch ms to literal `now`; P1-00 never emits `now-*`. |
| KTD-06a | Sidebar Monitoring entry without `runId` defaults to a server-generated last 5 minutes window, `from=<epoch ms>` and `to=now`, without `var-runId`. |
| KTD-06b | `/observability/monitoring` is a full-bleed embedded dashboard viewport inside the existing right-side `AppLayout` content region, not a boxed card/max-width document page. |
| KTD-07 | Missing `startedAt` falls back to `createdAt - 60s` with warning `monitoring_started_at_missing`. |
| KTD-08 | Runtime bundle adds the InfluxDB2 listener plugin while preserving self-contained init and zero-network Load Node activation. |
| KTD-09 | API builds non-secret Taurus bundles and must not put token into YAML/JMX/artifacts/API/logs. |
| KTD-10 | api-worker uploads per-run `monitoring.properties` only for enabled Standard Runs. |
| KTD-11 | All runs use `surgepilot-jmeter-wrapper` as Taurus `modules.jmeter.path`; wrapper pass-throughs unless the run is an enabled Standard Run. |
| KTD-12 | Injected JMX contains only `${__P(...)}` placeholders for monitoring values. |
| KTD-13 | Monitoring token comes only from deployment env/secret mount in P1-00; no workspace token DB crypto is implemented. API reads only `SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED`; api-worker is the only component that reads token plaintext/env file. |
| KTD-14 | Grafana browser entry uses same-origin `/grafana/*` behind SurgePilot session gate. |
| KTD-15 | Remote Load Node InfluxDB writes use node-facing write URL, not `http://influxdb:8086`. |
| KTD-16 | `http://influxdb:8086` is compose/internal only, usable by Grafana datasource and optional internal smoke. |
| KTD-17 | P1-00 does not expose InfluxDB write API through SurgePilot Nginx. |
| KTD-18 | Grafana anonymous Viewer is allowed only behind same-origin session-gated `/grafana/*`. |
| KTD-19 | `SURGEPILOT_MONITORING_ENABLED` is deployment-level and disabled by default outside explicit monitoring profiles. |
| KTD-20 | Web shows only read-only Monitoring entry, Run Report link, Debug muted hint, and empty/error states. |
| KTD-21 | Run List has no Monitoring action. |
| KTD-22 | Taurus `modifications` is not used for BackendListener insertion. |
| KTD-23 | Provisioned Dashboard 13644 keeps `runId` as an InfluxDB query variable over the `requestsRaw` `runId` tag; the default/All value expands to regex `.*` so generic Monitoring without `var-runId` does not produce an empty Flux regex. |

## 7. Component Responsibility Matrix

| Component | Responsibilities | Must not |
| --- | --- | --- |
| Runtime bundle | Ship JMeter 5.6.3, Taurus, P0 plugin `jpgc-casutg`, InfluxDB2 listener plugin, metadata, and smoke checks. | Use online plugin install or system JMeter/Taurus. |
| API | Resolve deployment monitoring state, build URLs/time windows, expose embed/run-link/session-check, persist minimal Standard Run snapshots. | Provide settings API/UI, store tokens, call Grafana management APIs, expose internal/node URLs to ordinary UI. |
| api-worker | Upload normal bundle and, for enabled Standard Run only, upload `monitoring.properties` with `0600` mode before starting Runner; compensate failed pre-start secret uploads. | Upload monitoring secret for Debug/disabled/config_error, include token in bundle/artifacts/logs, silently disable on properties upload failure, release a node when compensating cleanup is uncertain. |
| Runner | Execute runtime `bzt -n surgepilot.yml`, provide wrapper execution boundary, upload P0 artifacts, clean up secret file best-effort. | Import API internals, access DB/MinIO, decrypt tokens, fallback to system JMeter. |
| Wrapper | Act as Taurus JMeter path, pass-through non-enabled runs, inject BackendListener for enabled Standard Run, then delegate to runtime real JMeter. | Be per-run generated, contain token, mutate original JMX in place, bypass runtime real JMeter. |
| Web | Render `/observability/monitoring`, Run Report link from `getRunMonitoringLink`, Debug hint, and empty states from generated client. | Handwrite API shapes, display token/node/internal URL diagnostics, manage Grafana/InfluxDB. |
| Compose/Nginx | Provision InfluxDB2/Grafana/Dashboard and session-gated `/grafana/*`. | Add `/influxdb/*` write proxy or expose unauthenticated public Grafana as default path. |

## 8. Configuration Model

### 8.1 Deployment config

P1-00 uses deployment env/secret mount as the only configuration source.

| Env / Secret | Requirement / default | Contract |
| --- | --- | --- |
| `SURGEPILOT_MONITORING_ENABLED` | default `false` outside explicit monitoring profiles | Enables monitoring resolution for Standard Run only when complete config exists. |
| `SURGEPILOT_MONITORING_INFLUXDB_INTERNAL_URL` | required for official compose monitoring profile | Internal URL for Grafana datasource and optional compose smoke, for example `http://influxdb:8086`. |
| `SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL` | required effective value when monitoring is enabled | URL reachable from Load Node network namespace, for example `https://influxdb-write.example.com` or `http://<server-ip>:18086`. Official Make startup may derive it from one unambiguous host publish address and `SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT`; raw Compose and remote-write verification require final URL semantics. |
| `SURGEPILOT_MONITORING_INFLUXDB_ORG` | required when monitoring is enabled | InfluxDB org. |
| `SURGEPILOT_MONITORING_INFLUXDB_BUCKET` | required when monitoring is enabled | InfluxDB bucket. |
| `SURGEPILOT_MONITORING_INFLUXDB_TOKEN_CONFIGURED` | optional API-side readiness boolean for deployments where the API must not mount/read the token secret | Allows API to snapshot `config_error` when token presence is not declared, while api-worker remains the only component reading token plaintext. |
| InfluxDB write token env/secret mount | required when monitoring is enabled | Read by api-worker only to write per-run `monitoring.properties`. It is not stored in DB. |
| `SURGEPILOT_MONITORING_GRAFANA_BASE_PATH` | default `/grafana` | Browser-facing path. |
| `SURGEPILOT_MONITORING_DASHBOARD_UID` | default `surgepilot-jmeter-13644` | Provisioned dashboard UID. |
| `SURGEPILOT_MONITORING_DASHBOARD_SLUG` | default `jmeter-load-test` | Provisioned dashboard slug. |
| `SURGEPILOT_MONITORING_TIME_PADDING_SECONDS` | default `60` | Run-specific Grafana time-window padding. |

Rules:

1. There is no workspace override branch in P1-00.
2. There is no settings PATCH path in P1-00.
3. Listener parameters are fixed defaults, not API/DB/UI configuration.
4. Missing required deployment config yields `not_configured` when monitoring is not enabled and `config_error` when monitoring is enabled but incomplete; neither affects Debug no-write semantics.
5. `SURGEPILOT_MONITORING_INFLUXDB_INTERNAL_URL` must not be copied into `monitoring.properties` for remote-node runs.
6. `SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL` must be explicitly supplied for remote-node write verification; scripts must not default it to `http://influxdb:8086` or infer it from a separate host-only variable.
7. `config_error` snapshots keep `disabled_reason = null`; warning codes carry the safe explanation.
8. Official Make startup discovery must fail fast on zero or multiple host candidates and ask for the final node-write URL. It must not introduce a public host intermediate variable or copy `SURGEPILOT_MONITORING_INFLUXDB_INTERNAL_URL` into the node path.

### 8.2 Listener defaults

| Parameter | Default |
| --- | --- |
| `SURGEPILOT_MONITORING_SAMPLERS_LIST` | `.*` |
| `SURGEPILOT_MONITORING_USE_REGEX` | `true` |
| `SURGEPILOT_MONITORING_SUMMARY_ONLY` | `false` |
| `SURGEPILOT_MONITORING_SAVE_RESPONSE_BODY_OF_FAILURES` | `false` |
| `SURGEPILOT_MONITORING_RESPONSE_BODY_LENGTH` | `0` |
| `SURGEPILOT_MONITORING_FLUSH_INTERVAL_MS` | `4000` |
| `SURGEPILOT_MONITORING_MAX_BATCH_SIZE` | `2000` |
| `SURGEPILOT_MONITORING_THRESHOLD_ERROR_COUNT` | `5` |

These values are implementation constants or deployment-level env overrides only if the implementation chooses; they must not enter public API, DB schema, or UI in P1-00.

### 8.3 URL model

| URL | Consumer | Example | Contract |
| --- | --- | --- | --- |
| Internal InfluxDB URL | Grafana datasource, optional API/compose smoke | `http://influxdb:8086` | Compose/internal network only. |
| Node write URL | JMeter BackendListener on Load Node | `https://influxdb-write.example.com` or `http://<server-ip>:18086` | Must be reachable from Load Node. |
| Grafana base path | Browser iframe | `/grafana` | Same-origin Nginx path only. |

Recommended chain:

```text
Grafana container -> internal InfluxDB URL -> InfluxDB2
Browser -> /grafana/* -> Nginx -> Grafana
Remote Load Node JMeter BackendListener -> node write URL -> InfluxDB2 /api/v2/write
```

Rejected chains:

```text
Remote Load Node -> http://influxdb:8086
Remote Load Node -> /grafana/*
Remote Load Node -> /influxdb/* through SurgePilot Nginx
```

### 8.4 Local e2e URL model

| JMeter / Load Node location | Node write URL example | Contract |
| --- | --- | --- |
| Host process | `http://127.0.0.1:${INFLUXDB_HOST_PORT:-18086}` | Host process sees host-published InfluxDB port as loopback. |
| Dedicated e2e node container | `http://host.docker.internal:${INFLUXDB_HOST_PORT:-18086}` or host LAN IP | `127.0.0.1` inside node container is the node container itself. |
| Real remote VM | `https://influxdb-write.example.com` or `http://<server-private-ip>:18086` | Must match actual Load Node routing. |
| Co-located compose-only smoke | `http://influxdb:8086` | Allowed only for explicit co-located smoke; not a remote-node simulation. |

Official `make start-full-stack`, `make restart-full-stack`, and `make start-full-ssh-e2e` derive the node-write URL only when the final override is absent. Their preflight applies the Compose empty-value default for the published InfluxDB port, rejects non-canonical host-port syntax before runtime/build side effects, and passes the effective decimal port to the child Make process. Raw `docker compose` keeps static/env semantics and does not promise remote-node reachability.

## 9. API Contracts

### 9.1 Endpoints

| Method | Path | OperationId | Auth | Contract |
| --- | --- | --- | --- | --- |
| `GET` | `/api/v1/monitoring/embed` | `getMonitoringEmbed` | User/Admin cookie + `x-workspace-id` | Returns same-origin iframe URL/status. Optional `runId/from/to`. Debug run returns disabled. |
| `GET` | `/api/v1/runs/{runId}/monitoring` | `getRunMonitoringLink` | User/Admin cookie + `x-workspace-id` | Returns run-specific monitoring link/status/time window. Debug returns disabled. Run Report page must use this endpoint for Monitoring state. |
| `GET` | session-check endpoint | `checkSessionForProxy` or equivalent | cookie | Internal Nginx `auth_request`, `204/401/403`, not generated into public Web client. |

Rules:

1. P1-00 does not define `GET/PATCH /api/v1/monitoring/settings`.
2. P1-00 does not define `GET /api/v1/monitoring/status`.
3. P1-00 does not require `RunReportDetail.monitoring`; Web composes Run Report with `getRunMonitoringLink`.
4. API does not call Grafana management or provisioning APIs; compose smoke validates provisioning.
5. API responses must not expose token, internal InfluxDB URL, node write URL, secret file path, or listener tuning diagnostics.

### 9.2 `MonitoringEmbedResponse`

```json
{
  "enabled": true,
  "status": "ready",
  "iframeUrl": "/grafana/d/surgepilot-jmeter-13644/jmeter-load-test?orgId=1&kiosk=tv&theme=dark&var-runId=01J...&from=1907625540000&to=1907626260000",
  "runId": "01J...",
  "from": "1907625540000",
  "to": "1907626260000",
  "dashboardUid": "surgepilot-jmeter-13644",
  "warnings": []
}
```

`status` values:

1. `ready`
2. `not_configured`
3. `disabled`
4. `config_error`

Rules:

1. Debug `runId` returns `enabled=false`, `status=disabled`, `iframeUrl=null`.
2. Generic `/observability/monitoring` without `runId` omits `var-runId` and defaults to the last 5 minutes using server-generated epoch-ms `from` plus `to=now`.
3. `iframeUrl` is always same-origin `/grafana/...`.
4. API readiness is based only on local deployment config and run monitoring state.
5. Grafana iframe load failure is handled by Web iframe empty/error state; Grafana provisioning correctness is covered by compose smoke.
6. API must not probe or mutate Grafana as product behavior.

### 9.3 `RunMonitoringLinkResponse`

```json
{
  "runId": "01J...",
  "enabledForRun": true,
  "status": "enabled",
  "disabledReason": null,
  "platformMonitoringUrl": "/observability/monitoring?runId=01J...&from=1907625540000&to=1907626260000",
  "iframeUrl": "/grafana/d/surgepilot-jmeter-13644/jmeter-load-test?orgId=1&kiosk=tv&theme=dark&var-runId=01J...&from=1907625540000&to=1907626260000",
  "dashboardUid": "surgepilot-jmeter-13644",
  "runStartedAt": "2030-06-14T00:00:00.000Z",
  "runEndedAt": "2030-06-14T00:10:00.000Z",
  "grafanaFrom": "1907625540000",
  "grafanaTo": "1907626260000",
  "warnings": []
}
```

`status` values: `not_configured | disabled | enabled | config_error`.

`disabledReason` values: `debug_run_not_monitored | monitoring_disabled | not_configured | null`.

Debug fixed response:

```json
{
  "enabledForRun": false,
  "status": "disabled",
  "disabledReason": "debug_run_not_monitored",
  "platformMonitoringUrl": null,
  "iframeUrl": null,
  "grafanaFrom": null,
  "grafanaTo": null
}
```

### 9.4 Run Report composition

P1-00 does not change `RunReportDetail` to embed monitoring state.

Rules:

1. Web renders Run Report base content from the existing Run Report endpoint.
2. Web calls `getRunMonitoringLink` for the same `runId` to render `Open Monitoring`, Debug muted hint, or empty/error state.
3. Web may load the monitoring link lazily, but it must not infer monitoring status from `runType` alone.
4. Debug Run returns disabled state and no usable URL from `getRunMonitoringLink`.
5. `not_configured` and `config_error` render empty/error states, not Admin remediation links.
6. Run Report UI does not expose internal URL, node write URL, token, token fingerprint, or listener diagnostics.

### 9.5 Data contract: `run_monitoring_configs`

P1-00 has no `monitoring_settings` table.

`run_monitoring_configs` is required for Standard Runs whose monitoring resolver returns `enabled` or `config_error`.

| Field | Contract |
| --- | --- |
| `run_id` | One-to-one Run FK. |
| `workspace_id` | Workspace for run ownership and query scoping. |
| `status` | `enabled | config_error`. |
| `disabled_reason` | nullable; normally null for enabled/config_error rows. |
| `influxdb_node_write_url` | Non-secret snapshot used by api-worker for `SURGEPILOT_INFLUXDB_URL`; nullable for `config_error`. |
| `dashboard_uid` | Default `surgepilot-jmeter-13644`. |
| `grafana_base_path` | Default `/grafana`. |
| `created_at` | UTC timestamp. |

Rules:

1. Debug Runs do not create rows.
2. Disabled/not-configured Standard Runs do not create rows.
3. Enabled/config_error Standard Runs must create rows.
4. The table must not contain token, token ciphertext, token fingerprint, internal URL by default, listener params, warning/diagnostic product fields, Grafana datasource config, or Dashboard JSON.
5. No backfill or historical compatibility path is required in the current development phase.

## 10. Runtime / JMeter Design

### 10.1 Runtime bundle

The consolidated runtime bundle carries the exact generated-JMX compatibility closure plus the
InfluxDB2 listener plugin.

Rules:

1. Keep JMeter `5.6.3` and existing P0 runtime constraints.
2. Keep Taurus and the generated-JMX plugins `jpgc-casutg`, `jpgc-json`, `jpgc-tst`, and
   `bzm-random-csv`.
3. Keep the pinned `jmeter-plugin-influxdb2-listener` jar.
4. Runtime metadata records plugin name, version, sha256, and smoke result.
5. Load Node init remains zero network: no `pip install`, `curl`, `wget`, online plugin install, native compile, or OS package install.
6. Missing plugin or contract-class smoke failure fails runtime init or release smoke before production use.

### 10.2 Wrapper contract

All runs set Taurus `modules.jmeter.path` to a shipped wrapper:

```yaml
modules:
  jmeter:
    path: <runnerHome>/current/apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper
    version: "5.6.3"
    detect-plugins: false
    fix-log4j: false
    fix-jars: false
    force-ctg: false
```

Rules:

1. `surgepilot-jmeter-wrapper` is a shipped executable entrypoint, not a per-run generated file.
2. It may be implemented as a Python script, shell script, or compiled binary, but it must live beside real JMeter under the activated Runtime's `apache-jmeter-5.6.3/bin` directory so Taurus derives the correct JMeter home and plugin directory.
3. The wrapper delegates to runtime real JMeter, for example `<runnerHome>/current/apache-jmeter-5.6.3/bin/jmeter`.
4. Debug, disabled, and config_error runs use the same wrapper in pass-through mode.
5. Enabled Standard Run uses the same wrapper to inject BackendListener and append `-q secrets/monitoring.properties`.
6. No acceptance matrix may require direct real-JMeter path mode for non-enabled runs.
7. Do not use Taurus `modules.jmeter.properties` or scenario-level `properties` for token.
8. Do not use Taurus `modifications` for BackendListener insertion.

### 10.3 Injection flow

```text
API builds normal non-secret Taurus bundle
  -> bundle always points modules.jmeter.path at surgepilot-jmeter-wrapper
  -> api-worker uploads bundle
  -> if Standard enabled: api-worker uploads secrets/monitoring.properties
  -> Runner executes runtime bzt -n surgepilot.yml
  -> Taurus calls surgepilot-jmeter-wrapper with -t <generated.jmx>
  -> wrapper pass-throughs when not enabled
  -> wrapper injects BackendListener into a copy when enabled Standard Run
  -> wrapper calls runtime real JMeter
```

Injection rules:

1. Do not mutate the original generated JMX in place.
2. De-duplicate any existing SurgePilot-injected listener by stable marker before adding.
3. Inject one BackendListener + `hashTree` pair.
4. Injected JMX contains placeholders only.
5. Wrapper appends `-q <secrets/monitoring.properties>` only for enabled Standard Run.
6. Wrapper is transparent for Debug, disabled, and config_error runs.
7. Wrapper forces the InfluxDB2 listener logger category to `ERROR` before delegation so listener connection properties cannot enter downloadable INFO logs.

### 10.4 JMX placeholders

Injected JMX may contain only placeholders such as:

```text
${__P(SURGEPILOT_RUN_ID)}
${__P(SURGEPILOT_NODE_ID)}
${__P(SURGEPILOT_INFLUXDB_URL)}
${__P(SURGEPILOT_INFLUXDB_ORG)}
${__P(SURGEPILOT_INFLUXDB_BUCKET)}
${__P(SURGEPILOT_INFLUXDB_TOKEN)}
${__P(SURGEPILOT_MONITORING_SAMPLERS_LIST)}
${__P(SURGEPILOT_MONITORING_FLUSH_INTERVAL_MS)}
${__P(SURGEPILOT_MONITORING_MAX_BATCH_SIZE)}
```

Rules:

1. Token plaintext must never appear in JMX.
2. `SURGEPILOT_NODE_ID` resolves to the actual selected Load Node id for the Run, preserving the dashboard node dimension.
3. `SURGEPILOT_INFLUXDB_URL` resolves to node write URL for remote-node runs.
4. Tests must grep injected JMX, Taurus logs, JMeter logs, callbacks, Taurus-generated properties, and artifacts for secret absence.

## 11. Secret Safety

### 11.1 Deployment token source

1. Token is provided by deployment env or secret mount.
2. API does not store token in DB.
3. API does not return token, tokenConfigured, token fingerprint, ciphertext, or key metadata in P1-00.
4. api-worker is the only component that needs token plaintext to write the per-run properties file.
5. Runner/JMeter only receive token through the per-run properties file on the Load Node.

### 11.2 Per-run `monitoring.properties`

Path:

```text
<runnerHome>/runs/<runId>/secrets/monitoring.properties
```

Rules:

1. api-worker creates secrets directory with `0700`.
2. api-worker uploads the file with `0600`.
3. File is uploaded only for enabled Standard Run.
4. Upload failure is fail fast before Runner starts.
5. Debug, disabled, and config_error runs must not receive the file.
6. Before remote Runner `start` invocation, api-worker owns compensating deletion after a failed or partially completed upload; uncertain deletion quarantines the node. After invocation, Runner owns lifecycle cleanup and deletes the file in terminal `finally` after all sequential JMeter processes finish. An uncertain `start` result queues the existing same-allocation `force_kill` while retaining the lease. When a secret exists but the in-flight start has not published a pidfile yet, idempotent `kill` waits within the existing start-readiness window; it then terminates a live same-Run supervisor first, rereads and terminates any workload created during that boundary, and deletes the file only after both identities are confirmed absent. The JMeter wrapper must not delete the run-shared file.
7. Cleanup failure logs only safe metadata and must not change terminal Run state.
8. The file is not part of the Taurus bundle and is never registered as an artifact.

Example:

```properties
SURGEPILOT_RUN_ID=01J...
SURGEPILOT_INFLUXDB_URL=https://influxdb-write.example.com
SURGEPILOT_INFLUXDB_ORG=surgepilot
SURGEPILOT_INFLUXDB_BUCKET=jmeter
SURGEPILOT_INFLUXDB_TOKEN=<secret>
SURGEPILOT_MONITORING_SAMPLERS_LIST=.*
SURGEPILOT_MONITORING_FLUSH_INTERVAL_MS=4000
SURGEPILOT_MONITORING_MAX_BATCH_SIZE=2000
```

### 11.3 Exclusion rules

The following must never contain token plaintext or `monitoring.properties` contents:

1. API responses.
2. OpenAPI examples.
3. Web state.
4. Run artifacts.
5. `artifacts.zip`.
6. Runner callback `details`.
7. Taurus/JMeter/Runner logs.
8. `.surgepilot.env`.
9. generated `surgepilot.yml`.
10. generated or injected JMX.
11. MinIO object metadata.
12. GitHub Actions logs.
13. Taurus-generated `.properties` files in artifacts.

## 12. Compose, Grafana, and Nginx

### 12.1 Official compose stack

Monitoring profile adds:

1. InfluxDB2.
2. Grafana.
3. InfluxDB org/bucket/token bootstrap through deployment env/secret.
4. Grafana datasource provisioning using internal InfluxDB URL.
5. Dashboard 13644 provisioning with UID `surgepilot-jmeter-13644`.
6. `/grafana/*` same-origin reverse proxy.
7. SurgePilot session gate for `/grafana/*`.
8. Optional InfluxDB host port exposure for local/e2e node write URL, for example `${INFLUXDB_HOST_PORT:-18086}:8086`; this is not a SurgePilot Nginx route.

Rules:

1. Monitoring profile disabled means P0 profile startup is unaffected.
2. Dashboard provisioning smoke validates `runId/from/to` behavior.
3. Compose smoke validates Grafana datasource uses internal URL and BackendListener uses node write URL.
4. API must not call Grafana provisioning or management APIs as product behavior.
5. Do not add `/influxdb/*` to SurgePilot Nginx for P1-00.

### 12.2 Grafana settings

Required official compose settings:

```text
GF_AUTH_ANONYMOUS_ENABLED=true
GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
GF_SECURITY_ALLOW_EMBEDDING=true
GF_SERVER_ROOT_URL=${SURGEPILOT_PUBLIC_BASE_URL}/grafana/
GF_SERVER_SERVE_FROM_SUB_PATH=true
```

Rules:

1. Grafana anonymous Viewer is acceptable only behind same-origin `/grafana/*` and SurgePilot session gate.
2. Grafana is not exposed as unauthenticated public default path.
3. P1-00 does not introduce Grafana users, OAuth/OIDC/SAML/LDAP, login proxy, service-account UI, or custom gateway policy layer.

### 12.3 Nginx session gate

Nginx `/grafana/*` uses `auth_request` to a SurgePilot session-check endpoint.

Rules:

1. Session-check is `GET`, cookie-based, and excluded from public Web client generation.
2. It returns `204`, `401`, or `403`.
3. It does not require CSRF.
4. Web does not call session-check directly; browser iframe requests trigger Nginx auth gate.
5. Session gate is not used for JMeter -> InfluxDB writes.

## 13. API / Worker / Runner Workflow

### 13.1 Run creation

```text
POST run
  -> validate source and runType
  -> resolve deployment monitoring state
  -> Debug: no monitoring row, dynamic disabled later
  -> Standard enabled/config_error: persist minimal non-secret run_monitoring_configs
  -> build non-secret Taurus bundle with wrapper path
  -> enqueue/dispatch as P0
```

Rules:

1. Monitoring config_error must not reject Run creation by default; it disables monitoring for that Run and surfaces `config_error` state.
2. Debug Run does not inspect token and does not create monitoring snapshot.
3. API must not write token to YAML, JMX, artifacts, API response, or logs.
4. API must not replace node write URL with internal URL for remote-node runs.

### 13.2 Worker dispatch

```text
api-worker
  -> upload normal bundle
  -> upload .surgepilot.env
  -> if run_monitoring_configs.status == enabled and runType == standard:
       write secrets/monitoring.properties with SURGEPILOT_INFLUXDB_URL=<node write URL>
       upload with 0600
       fail fast on upload/write error before Runner starts
     else:
       no monitoring secret
  -> start Runner as P0
```

Rules:

1. `monitoring.properties` is not part of the bundle.
2. `monitoring.properties` is not registered as artifact.
3. upload/write failure for enabled Standard Run is always fail fast.
4. Debug Run never enters the upload branch.
5. config_error Standard Run never uploads monitoring secret.

### 13.3 Runner execution

```text
Runner
  -> accepts run
  -> bzt -n surgepilot.yml
  -> wrapper pass-through or inject
  -> runtime real JMeter exits
  -> upload P0 artifacts
  -> cleanup secrets
  -> terminal callback
```

Rules:

1. InfluxDB write endpoint unreachable during JMeter execution does not change SurgePilot Run state by default; JMeter/Taurus exit and SLA remain authoritative.
2. JMX injection failure before load starts fails the Run with safe reason `monitoring_jmx_injection_failed`.
3. Plugin missing must be caught by runtime init/release smoke; if detected at runtime, fail before load with safe reason.
4. Stop/Abort semantics remain P0.

## 14. Web UX

### 14.1 Monitoring page

Route:

```text
/observability/monitoring
```

Behavior:

1. Protected route using existing auth flow.
2. Renders same-origin iframe URL from API.
3. Generic page may show dashboard without `runId`.
4. Run-specific query uses `runId/from/to` from API.
5. `not_configured`, `config_error`, and `disabled` render empty states from API status.
6. iframe loading/auth/provisioning failures render Web-owned iframe error states.
7. No Admin settings link, diagnostics panel, node/internal URL display, or token status.
8. The ready iframe state is full-bleed within the right-side content viewport: no page max-width, no enclosing card chrome, and the iframe grows to fill remaining height below the lightweight page header.

### 14.2 Run Report

1. Place `Open Monitoring` near Verdict/KPI.
2. Run Report page calls `getRunMonitoringLink` for the current Run.
3. Show primary action only when Standard Run monitoring is enabled and `platformMonitoringUrl` is non-null.
4. Debug Run shows muted hint, for example `Debug Runs do not emit monitoring data.`
5. `not_configured` and `config_error` show safe empty states only.
6. Run Report never exposes internal URL, node write URL, token, token fingerprint, or listener diagnostics.

### 14.3 Navigation

1. Monitoring navigation entry is allowed only when P1-00 is active.
2. Run List has no Monitoring quick action.
3. Web does not expose Grafana login/user management.

## 15. Failure and Degradation Semantics

| Scenario | Behavior |
| --- | --- |
| Debug Run | Executes normally; dynamic disabled monitoring response; no DB row; no properties; no BackendListener injection; no InfluxDB write; no usable link. |
| Monitoring disabled | P0 Run normal; no monitoring row; Run Report shows no usable link. |
| Deployment config missing | Standard Run normal; no usable link or config_error according to resolver; no secret upload. |
| Enabled Standard Run with config_error | Minimal config_error snapshot; no properties upload; Run Report empty/error state. |
| Enabled Standard Run properties upload/write fails | Fail fast before Runner starts with safe reason; no fallback to disabled. |
| JMX injection fails | Fail before load with `monitoring_jmx_injection_failed`. |
| Plugin missing | Runtime init/release smoke fails; runtime detection fails before load if missed. |
| InfluxDB unreachable during run | SurgePilot Run state follows JMeter/Taurus exit and SLA; Monitoring page may show no data. |
| Grafana iframe load/auth/provisioning issue | Run normal; Web renders iframe empty/error state; compose smoke covers official provisioning. |
| Stop/Abort | P0 state machine unchanged. |

## 16. Verification Gates

### 16.1 Default `make verify` scope

P1-00 adds only deterministic lightweight checks to `make verify`:

1. API unit tests for Debug dynamic disabled response.
2. API unit tests for Standard enabled/config_error resolver from deployment config.
3. API URL/time-window builder tests.
4. Contract freshness tests for embed/run-link fields.
5. DB/model tests confirming no `monitoring_settings` table and no Debug monitoring row requirement.
6. DB/model tests confirming enabled/config_error Standard Run writes minimal `run_monitoring_configs` rows without token, source-scope, warning/diagnostic product fields, internal URL by default, or listener params.
7. Worker unit tests for `monitoring.properties` branch and fail-fast upload/write behavior.
8. Runner/wrapper unit tests for all-runs wrapper path, pass-through mode, enabled injection mode, and runtime real JMeter delegation.
9. Secret grep tests for YAML, JMX, Taurus-generated property files, logs, callbacks, and artifacts fixtures.
10. Web unit/component tests for iframe, Run Report `getRunMonitoringLink` composition, Debug muted hint, and empty/error states.
11. Static Nginx/config checks for `/grafana/*` route and absence of `/influxdb/*` write proxy.

### 16.2 Supplemental gates

External service, SSH, browser, and remote-node checks are supplemental, not mandatory lightweight `make verify` gates:

```bash
make verify-p1-00-monitoring-compose
make verify-p1-00-monitoring-ssh
make verify-p1-00-monitoring-remote-node-write
make verify-e2e
```

Rules:

1. Supplemental commands may require Docker, host port exposure, SSH fixtures, or remote network setup.
2. They must be documented for release/nightly/profile validation.
3. Failing to run supplemental gates locally must not be represented as default `make verify` failure.
4. `verify-p1-00-monitoring-remote-node-write` requires an explicit remote-write environment and an explicit node-facing `SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL`; a skipped run is recorded as an environment gap and must not count as release/nightly green evidence.

### 16.3 Hard assertions

1. Runtime metadata contains the pinned InfluxDB2 listener plugin and sha256.
2. Load Node init fails on missing plugin jar/class smoke.
3. Runner uses runtime `bzt` and P0 `-n` path.
4. All Taurus bundles set `modules.jmeter.path` to SurgePilot wrapper.
5. Wrapper delegates to runtime real JMeter.
6. Debug/disabled/config_error wrapper path is pass-through and does not inject BackendListener.
7. Enabled Standard Run injects one BackendListener into a JMX copy.
8. Enabled Standard Run appends `-q secrets/monitoring.properties`.
9. Taurus YAML does not contain token in `modules.jmeter.properties` or scenario `properties`.
10. Debug Run does not create a monitoring DB row.
11. Debug Run does not upload `monitoring.properties`.
12. Debug Run has no InfluxDB point for `runId`.
13. Debug Run returns `debug_run_not_monitored` dynamically.
14. Enabled/config_error Standard Run creates a minimal non-secret `run_monitoring_configs` row.
15. Disabled/not_configured Standard Run does not require a monitoring DB row.
16. `run_monitoring_configs` does not include `source_scope`, `warning_code`, token fields, listener params, or internal URL by default.
17. `monitoring.properties` for remote-node profile contains node write URL, actual `SURGEPILOT_NODE_ID`, and no internal URL such as `http://influxdb:8086`.
18. Host-process local e2e may use `http://127.0.0.1:<publishedPort>` as node write URL.
19. Containerized node e2e must not use `127.0.0.1` unless InfluxDB runs inside that same node container.
20. Grafana datasource uses internal URL in official compose.
21. SurgePilot Nginx has `/grafana/*` route but no `/influxdb/*` write proxy.
22. Run Report page uses `getRunMonitoringLink`; it does not depend on `RunReportDetail.monitoring`.
23. Run Report URL contains `runId/from/to` when monitoring is enabled.
24. iframe URL contains `var-runId/from/to` when run-specific monitoring is enabled.
24a. Generic `/observability/monitoring` iframe URL omits `var-runId`; Dashboard 13644 `runId` variable remains a visible/selectable query variable and uses All=`.*` to avoid empty Flux regex parse errors.
25. Terminal Run uses epoch ms -> epoch ms.
26. Active Run uses epoch ms -> `now`.
27. API never outputs `now-*`.
28. Debug Run has no primary Monitoring button.
29. Run List has no Monitoring action.
30. `/grafana/*` requires SurgePilot session.
31. Grafana anonymous role is Viewer.
32. API does not call Grafana management/provisioning APIs or probe Grafana availability as product behavior.
33. Monitoring page full-bleed layout is covered by Web tests and preserves existing `AppLayout`/Tailwind token conventions.
34. SDD and tests do not paste full dashboard JSON.

## 17. Implementation Milestones

| M | Content | Acceptance |
| --- | --- | --- |
| M0 | Scope/doc sync. | 00/P1 index/P1-00 agree on deployment-level config, no settings API/UI/DB, Debug dynamic disabled, Run Report link composition, and supplemental external gates. |
| M1 | Compose/provisioning. | Monitoring profile provisions InfluxDB2/Grafana/Dashboard 13644; `/grafana/*` works through session gate; compose smoke also checks authenticated `/api/v1/monitoring/embed`; no `/influxdb/*` proxy. |
| M2 | Runtime. | InfluxDB2 listener plugin is bundled and smoke-verified. |
| M3 | API contracts. | Embed/run-link/session-check contracts exist; no RunReportDetail monitoring field requirement, no settings/status endpoints. |
| M4 | Minimal DB. | `run_monitoring_configs` supports only enabled/config_error Standard Run non-secret snapshots; no `monitoring_settings`, no `source_scope`, no `warning_code`. |
| M5 | api-worker. | Enabled Standard Run writes/upload properties and fails fast on upload/write failure. |
| M6 | Runner/wrapper. | All runs use wrapper; pass-through and enabled injection are tested. |
| M7 | Web. | Monitoring iframe and Run Report link/hints/empty states use generated client only; `/observability/monitoring` uses full-bleed iframe layout; Run Report uses `getRunMonitoringLink`. |
| M8 | Verification. | Lightweight `make verify` checks pass; supplemental gates documented and runnable in appropriate environments. |

## 18. Migration and Compatibility

1. Current development phase has no historical Monitoring compatibility requirement.
2. P1-00 does not create `monitoring_settings`.
3. P1-00 does not require Debug monitoring rows.
4. No backfill is required for pre-P1 Runs.
5. Existing Runs without `run_monitoring_configs` resolve monitoring dynamically as disabled/not_configured unless they are Standard Runs with an enabled/config_error snapshot created after P1-00 implementation.
6. If a future Slice adds workspace settings, token DB crypto, listener tuning, or migration compatibility, it must introduce a new Slice/ADR and migration plan.

## 18.1 Implementation Backfill

Implemented P1-00 uses:

1. `run_monitoring_configs` as the only Monitoring persistence table, storing only non-secret Standard Run snapshots.
2. API settings from deployment env, with the InfluxDB token read only by the api-worker runtime path in official compose.
3. Public API contracts:
   - `GET /api/v1/monitoring/embed`
   - `GET /api/v1/runs/{runId}/monitoring`
   - internal `GET /api/internal/v1/session-check` excluded from OpenAPI.
4. Runner/runtime wrapper path `current/apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper` for all generated Taurus bundles.
5. Runtime validation that checks the InfluxDB2 listener jar contains `InfluxDatabaseBackendListenerClient.class`.
6. Official Monitoring compose profile with InfluxDB2, Grafana Dashboard 13644 JSON, session-gated `/grafana/*`, no `/influxdb/*` Nginx route, and Grafana Viewer embedding.
7. Web Monitoring route `/observability/monitoring` as a full-bleed right-content dashboard viewport and Run Report Monitoring card using generated contracts.
8. Dashboard 13644 `runId` variable visible as an InfluxDB query variable with All=`.*`, allowing generic Monitoring to omit `var-runId` without Flux empty-regex parse failures.

Verification run after implementation:

- `make verify`
- `make verify-p1-00-monitoring-compose`
- `make verify-p1-00-monitoring-remote-node-write` skipped locally without explicit remote environment and node-facing URL; skipped is not release/nightly green evidence.
- `pnpm e2e -- tests/e2e/p1_00_monitoring.spec.ts --project=chrome`

## 19. Documentation and Regeneration Rules

1. H1 remains `# P1-00 Monitoring`.
2. Regenerated summaries must preserve:
   - deployment-level config only,
   - no Monitoring settings API/Admin UI/`monitoring_settings` table,
   - Debug dynamic disabled/no DB row,
   - enabled/config_error Standard Run minimal non-secret snapshot only,
   - no complete omission of `run_monitoring_configs` for enabled/config_error Standard Runs,
   - no `source_scope` or `warning_code` fields in `run_monitoring_configs`,
   - Run Report uses `getRunMonitoringLink`, not `RunReportDetail.monitoring`,
   - API local-config readiness only; iframe/provisioning failures are Web/compose-smoke concerns,
   - all-runs wrapper path with pass-through for non-enabled runs,
   - enabled Standard Run fail-fast on `monitoring.properties` upload/write failure,
   - internal InfluxDB URL vs node-facing write URL separation,
   - no unified Nginx `/influxdb/*` write proxy,
   - secret exclusion,
   - session-gated `/grafana/*`,
   - no Grafana/InfluxDB management UI,
   - lightweight default verification plus supplemental external gates.
3. Do not paste full Dashboard 13644 JSON into SDD or prompts.

## 20. Done When

P1-00 is complete only when:

1. Scope Gate and P1 index agree with this Slice.
2. API exposes embed/run-link/session-check without settings/status endpoints.
3. Runtime bundle includes the pinned InfluxDB2 listener plugin and passes release/init smoke.
4. Debug Run returns disabled state dynamically and never writes InfluxDB.
5. Enabled Standard Run persists minimal non-secret monitoring snapshot.
6. Config_error Standard Run persists minimal non-secret config_error snapshot and uploads no secret.
7. Disabled/not-configured Standard Run does not need a monitoring row.
8. `run_monitoring_configs` contains no `source_scope`, `warning_code`, token fields, listener params, or internal URL by default.
9. Run Report page uses `getRunMonitoringLink` for Monitoring state.
10. All runs use wrapper path; wrapper pass-throughs non-enabled runs.
11. Enabled Standard Run injects BackendListener and uses `monitoring.properties` with node write URL.
12. `monitoring.properties` upload/write failure is fail fast.
13. Run Report displays `Open Monitoring` only for usable Standard Run monitoring.
14. `/observability/monitoring` embeds same-origin `/grafana/...` through session gate.
15. Web shows Debug muted hint and safe empty/iframe-error states without Admin remediation/diagnostics.
16. API does not call Grafana management/provisioning APIs or probe Grafana availability as product behavior.
17. Secrets are absent from API responses, YAML, JMX, Taurus-generated properties, artifacts, logs and callbacks.
18. official compose Grafana datasource uses internal URL.
19. remote-node supplemental gate proves Load Node can write through node write URL when that environment is available.
20. SurgePilot Nginx does not expose unified `/influxdb/*` write proxy.
21. `make generate-contracts` passes after implementation changes.
22. `make verify` passes with lightweight deterministic P1-00 checks after implementation changes.

## Implementation backfill

The compose layout was tightened after initial P1-00 implementation:

1. `infra/docker/docker-compose.base.yml` is now the lightweight base stack for smoke, SSH, and P0 API E2E profiles; it intentionally excludes Grafana and InfluxDB.
2. `infra/docker/docker-compose.yml` is the standard full-stack entry point. It explicitly defines the final base application services plus InfluxDB2 and Grafana in one file; full-stack operation no longer depends on a monitoring override file.
3. `infra/docker/docker-compose.monitoring.yml` was removed to avoid duplicate service-key merge ambiguity for `api`, `api-worker`, and `nginx` monitoring env/secrets/depends_on.
4. Real-IP E2E scripts separate SurgePilot API orchestration URL, target URL under test, SSH Load Node host/port, and node-facing InfluxDB write URL through `SURGEPILOT_E2E_*` and `SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL` variables. `.env.e2e.example` documents the expected values.
5. `SURGEPILOT_JMETER_MEMORY_XMX` is an internal Taurus YAML generation setting. It defaults to `4G`, validates with `^[1-9][0-9]*[KMG]$`, and is written to `modules.jmeter.memory-xmx`; it does not change public API schemas or generated contracts.
6. Official Make startup now derives a missing `SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL` from one unambiguous IPv4/IPv6 default-route source address across all routing tables and `SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT`. Full Compose no longer falls back to `host.docker.internal` or the internal service URL. `scripts/verify_full_ssh_e2e_node_connectivity.py` checks the final API and InfluxDB health URLs from both SSH E2E nodes, validates SurgePilot OpenAPI identity in addition to health, and validates the InfluxDB-specific health payload, while `scripts/verify_p1_00_monitoring_remote_node_write.py` requires both final node-facing URLs, gives the explicit API origin precedence over any E2E host fallback, and still proves `requestsRaw`, `virtualUsers`, and `testStartEnd` for the Run.

Verification added/updated:

- `tests/contract/test_p1_00_monitoring_compose.py` asserts full/base compose separation and merged monitoring env/secrets/depends_on.
- `tests/test_p0_06_ssh_taurus_smoke_verifier.py` and `tests/test_p0_api_main_flow_e2e_verifier.py` cover real-IP URL/node parameterization and `--keep-data` cleanup semantics.
- `tests/test_node_facing_startup.py`, `tests/test_verify_full_ssh_e2e_node_connectivity.py`, and `tests/test_p1_00_monitoring_remote_node_write_verifier.py` cover derivation ambiguity, publish-port conflicts, node-side final URL health checks, and explicit remote-write evidence requirements.
- API tests assert Taurus YAML contains `memory-xmx: 4G` and invalid memory values are rejected.
