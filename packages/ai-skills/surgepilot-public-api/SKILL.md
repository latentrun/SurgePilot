---
name: surgepilot-public-api
description: Use when operating SurgePilot Scenarios, Test Plans, plain-only Env Groups, Dependency Files, Runs, Run reports, or Load Node summaries through the governed PAT Bearer public API.
---

# SurgePilot Public API

Use the bundled `references/public-api.openapi.json` as the only API contract and `scripts/surgepilot_call.py` as the only request path.

## Configure

Require all three local client variables:

```bash
export SURGEPILOT_PUBLIC_API_BASE="https://surgepilot.example.com"
export SURGEPILOT_PAT="<PAT>"
export SURGEPILOT_WORKSPACE_ID="<workspace-id>"
```

`SURGEPILOT_PUBLIC_API_BASE` is the deployment origin only; do not append `/api`. Never print, persist, summarize, or place the PAT in command arguments.

## Call operations

Pass an allowlisted public `operationId` plus JSON objects for path, query, and body parameters:

```bash
python scripts/surgepilot_call.py publicListScenarios \
  --query-json '{"page":1,"pageSize":20}'
```

The caller derives the method and path from the bundled contract. Do not construct URLs, headers, cookies, or CSRF requests yourself.

Dependency File upload is the only file-body exception. Use the dedicated `--file` option with `publicUploadDependencyFile`:

```bash
python scripts/surgepilot_call.py publicUploadDependencyFile --file ./setup.groovy
```

The dry run reports only filename, size, and SHA256. It must never print file contents. After confirmation, execute the exact planned upload with `--confirm --expected-file-sha256 <confirmed-sha256>`. If the file changed after the preview, stop and present a new plan for confirmation. Use the returned Dependency File `id` as `dependencyFileId` in Scenario script configuration.

## Confirm writes

For related multi-step writes, prepare the complete execution plan first and ask for one confirmation before executing that plan. The confirmation applies only to the listed operations, resources, and parameters. Any new or changed write operation requires a new confirmation.

After that confirmation, execute each exact planned write operation with the caller's `--confirm` flag. Do not add a batch API or hidden execution state; the caller still uses the public contract operation-by-operation.

## Scenario assertions and scripts

- For JSON response bodies, default to `jsonpath_exists` or `jsonpath_equals`. Use `body_contains` only for literal/non-JSON matching.
- Treat a JSON `body_contains` value containing suspicious escaped quotes such as `\"` as a warning sign. Convert the assertion to JSONPath before presenting the execution plan unless the user explicitly requires literal escaped text matching.
- Enabled executable scripts must reference an uploaded `.groovy` Dependency File by `dependencyFileId`.
- If no executable Dependency File is available, omit script entries. Do not create disabled script placeholders and do not treat disabled scripts as execution evidence.

## Generated temporary names

When the agent generates temporary, smoke-test, or E2E resource names, append a short unique suffix before presenting the confirmed plan. Preserve names explicitly supplied by the user exactly. If an explicit name receives `409`, stop and report the conflict instead of silently renaming it.

## Fail closed

- Stop on `400 WORKSPACE_REQUIRED`, `401`, `403`, `409`, `422`, network errors, contract drift, or forbidden response fields.
- Never follow HTTP redirects. Reject response statuses and JSON shapes that are not declared for the selected public operation.
- Never guess or probe another Workspace and never use browser default/preferred Workspace state.
- Never fall back to cookie/session/CSRF APIs, `/api/v1/account/api-tokens`, `/api/internal/*`, Runner callbacks, MinIO, PostgreSQL, Load Node SSH, or arbitrary URLs.
- Env Group operations are plain-only. Do not send `type: secret`, hidden-value fields, masked-read fields, or secret copy/write payloads. If copy/patch fails because protected variables exist, stop.
- Do not provide token management, artifact binary download, API Catalog generation, SDK, MCP, marketplace, installer, or runtime behavior.
- Dependency File operations are allowed only through the governed public Dependency File contract when enabled by the bundled OpenAPI contract.
