# ADR-0008 P1 Debug HTTP Trace

- Status: Accepted
- Scope: P1 Debug Run Run Report diagnostics, Runner artifact boundary, Storage preview boundary
- Active Slice: `docs/sdd/slices/P1-08-debug-http-trace.md`
- Supersedes: none
- Does not supersede: P0-Stability, contract-first rules, MinIO-only storage, runtime bootstrap packaging, or Runner/API/Web boundaries

## Context

Run Report currently has `Failure Diagnostics`, which shows only safe failure summaries. Debug Run users need a different diagnostic surface: for a Scenario debug run and a Test Plan debug-mode run, each HTTP request is executed once and users need the full request/response details to diagnose URL, method, header, body, environment variable, authentication and response failures.

This capability was not part of the original P1 reservation list in `docs/sdd/00-product-scope-and-priority.md` §6. This accepted ADR adds it as a bounded P1 capability; `docs/sdd/slices/P1-README.md` requires the capability to remain governed by the Revision Protocol and its named Slice SDD.

Runtime bootstrap is already fixed: the Runner executes `${RUNNER_HOME}/current/bin/bzt -n surgepilot.yml`, the P0 runtime tar contents are frozen, and Taurus supports inline JSR223 `script-text` in YAML. Therefore the debug trace script must be injected into the per-run Taurus YAML by the API/worker bundle generation path, not distributed as a runtime file and not installed globally.

## Decision

Add a P1 capability named `debug_http_trace`, implemented only by the active Slice SDD `P1-08-debug-http-trace`.

The accepted architecture is:

1. Debug-only Taurus YAML injection: API/worker bundle generation adds inline JSR223 `script-text` only for `runType=debug` and `sourceType in (debug_scenario, test_plan)`.
2. The Runner stays unchanged: it executes the run bundle and uploads artifacts through the existing API-mediated artifact endpoint. The Runner does not own Groovy distribution and does not receive MinIO credentials.
3. The inline script writes a bounded JSONL artifact with one sanitized line per HTTP sampler execution.
4. Add the P1-only Run artifact type `debug_http_trace`.
5. The debug trace artifact must be uploaded before the Run terminal callback whenever it exists. It must not rely on terminal-late diagnostics-only upload.
6. The API parses only this artifact type into the Run Report response as nullable `debugHttpTrace`. This parser performs debug-trace-specific validation, truncation and a second sanitization pass.
7. The Web displays an `HTTP Trace` sub-block near `Failure Diagnostics` only for Debug Run when `debugHttpTrace` is present or unavailable; Standard Run does not show request/response details.

## Boundaries

In scope:

- Scenario Debug Run (`sourceType=debug_scenario`).
- Test Plan debug-mode Run (`sourceType=test_plan`, `runType=debug`).
- Single node, single concurrency, each configured HTTP request sent at most once.
- Request/response details: URL, method, request headers, request body, response status, response headers, response body, duration, error, truncation flags.
- Bounds: default maximum 100 trace entries, 64KB per body, 10MB trace artifact.
- Configuration names: `SURGEPILOT_DEBUG_TRACE_MAX_REQUESTS`, `SURGEPILOT_DEBUG_TRACE_BODY_MAX_BYTES`, `SURGEPILOT_DEBUG_TRACE_ARTIFACT_MAX_BYTES`.

Out of scope:

- Standard Run full request/response tracing.
- JMeter plugin installation, Backend Listener, Monitoring, InfluxDB, Grafana.
- General logging, log search, or generic sanitization framework.
- Full unredacted JTL upload or preview.
- Runtime tar changes, runtime metadata changes, `~/.bzt-rc`, global plugin/script directories, or standalone SFTP `.groovy` distribution.
- Large file pagination, trend analysis, ZIP/TAR/TGZ extraction, editable Taurus YAML.

## Security and Limits

The trace must be sanitized before artifact upload and sanitized again when the API reads it. This is a debug-trace-specific sanitizer, not a general P2 log sanitization framework.

Sensitive names include, at minimum:

- Headers: `Authorization`, `Cookie`, `Set-Cookie`, `X-Api-Key`, and case-insensitive names containing `token`, `password`, `secret`, or `key`.
- Body fields: case-insensitive JSON/form keys containing `token`, `password`, `secret`, or `key`.

Body preview is allowed only for text, JSON, XML and form content. Binary-like content is represented by content type, size and SHA-256 prefix. Oversized bodies set `bodyTruncated=true`; total overflow sets `traceTruncated=true`.

## Consequences

- `docs/sdd/00-product-scope-and-priority.md`, `docs/sdd/02-repo-structure-and-dev-workflow.md`, root `AGENTS.md`, `docs/sdd/slices/P1-README.md`, `docs/sdd/05-runner-protocol-and-run-state-machine.md`, and `docs/sdd/07-storage-artifacts-minio.md` must be synchronized before code implementation.
- The active Slice SDD must contain verifiable Done When criteria before implementation begins.
- API contract changes follow FastAPI schema → OpenAPI export → generated client → Web consumption.
- P0 Stability remains mandatory: terminal protection, idempotent Stop, node lease cleanup, path safety, Workspace enforcement, permission checks and credential safety cannot regress.
