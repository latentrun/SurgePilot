# P2-03 Env Group Secret

- Document status: Accepted for implementation by `docs/sdd/adr/ADR-0014-p2-env-group-secret.md`.
- Phase: P2
- Capability: `env_group_secret`
- Scope Gate: `docs/sdd/00-product-scope-and-priority.md` §7, rows `Secret` , `Snapshot Security` , `Key Governance` , `Redaction`
- Related Slice: `docs/sdd/slices/P0-01-env-groups.md`, `docs/sdd/slices/P2-02-public-api-substrate.md`
- API Contract Boundary: `docs/sdd/04-api-contract-guidelines.md`
- Run State Boundary: `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- Security Boundary: `docs/sdd/06-security-permission-workspace.md`
- Storage Boundary: `docs/sdd/07-storage-artifacts-minio.md`
- ADR: `docs/sdd/adr/ADR-0014-p2-env-group-secret.md`

## 1. Core Decision

P2-03 adds first-class Env Group variable types with exactly two values: `plain` and `secret`.

The storage shape remains inside the existing `env_groups.variables` JSONB object, but the value of each variable changes from a string to a per-variable typed entry. The canonical stored entry is conceptually:

```json
{
  "BASE_URL": { "type": "plain", "value": "https://example.test" },
  "API_TOKEN": { "type": "secret", "value": "runtime-token" }
}
```

This Slice does not preserve the old `dict[str,string]` write contract. SurgePilot is still in active development, so maintaining dual schemas would increase implementation and test complexity without product value.

Read models are context-specific. Browser session read models return `secret` entries as masked metadata only and must not return the plaintext `value`. Public PAT read models use a separate plain-only DTO and must not expose secret `value`, `hasValue`, `displayValue`, masked secret entries, secret examples, or any field that can reconstruct secret semantics. Previews, reports, logs, audit-like diagnostic data, and OpenAPI examples must never return secret plaintext.

## 2. Scope Trace

| Source | Contract in this Slice |
| --- | --- |
| `00-product-scope-and-priority.md` §7 `Secret` | Adds Env Group `plain | secret` variable types and sensitive value display/copy restrictions. |
| `00-product-scope-and-priority.md` §7 `Snapshot Security` | Explicitly out of scope for this Slice; Run Snapshot may internally persist execution-needed plaintext values until a later Snapshot Security Slice. |
| `00-product-scope-and-priority.md` §7 `Key Governance` | Explicitly out of scope; no key rotation or historical Run decryption boundary. |
| `00-product-scope-and-priority.md` §7 `Redaction` | This Slice only applies targeted Env Group secret response/preview/report redaction; it does not build a generic sanitization framework. |
| `P0-01 Env Groups` | Replaces non-secret string variable contract with typed variables while preserving Workspace, CRUD, validation, duplicate, delete protection, and generated contract rules. |
| `P2-02 Public API Substrate` | Public Env Group structured writes remain available for plain variables only; public secret create/patch/copy is forbidden in this Slice. |

## 3. In Scope

### 3.1 Backend / contracts

1. Replace Env Group variable write contract with typed entries for session route schemas and a plain-only typed contract for public route schemas.
2. Replace Env Group session detail read contract with a masked read model.
3. Add a separate public Env Group DTO that includes only plain entries and never exposes secret `value`, `hasValue`, `displayValue`, or masked secret metadata.
4. Preserve existing Env Group list behavior for session routes: list responses do not include variable values.
5. Keep the existing `env_groups.variables` JSONB storage location and switch entry shape in place.
6. Add service helpers for normalize, validate, masked read view, public plain-only view, secret-bearing detection, and internal runtime full view.
7. Update Run Snapshot creation and Execution Bundle materialization to use internal runtime values.
8. Ensure preview/report/public/session responses never return secret plaintext.
9. Regenerate internal and public OpenAPI artifacts from FastAPI/Pydantic schemas.

### 3.2 Session API / Web

1. Session `create`, `get`, `patch`, and `duplicate` return masked Env Group detail.
2. Session users may create and replace `secret` values.
3. Session patch preserves an existing secret value when the variable entry is present without `value` and the variable already exists as `secret`.
4. Session patch replaces a secret value only when a new `value` is submitted.
5. Session duplicate may copy secret plaintext server-side into the new Env Group, but all responses remain masked.
6. Web Env Group forms support choosing `plain` or `secret`, entering secret values, displaying masked secret entries, and editing secret entries without reveal or client-side copy.

### 3.3 Public API

1. Public Env Group create/patch uses a plain-only typed schema and allows only `type: "plain"`.
2. Public create/patch with `type: "secret"` returns `VALIDATION_ERROR`.
3. Public responses use a plain-only DTO and must not expose secret `value`, `hasValue`, `displayValue`, masked secret read entries, or secret-bearing examples.
4. Public copy of a secret-bearing Env Group is rejected and does not create a target Env Group.
5. Public OpenAPI must not include any secret plaintext example, reveal field, secret write/copy example, masked secret read model, or reconstructable secret field.

## 4. Out of Scope

This Slice must not implement:

1. External Secret Manager, Vault, KMS, or cloud secret backend.
2. Secret encryption at rest beyond the existing database deployment boundary.
3. Run Snapshot encryption.
4. Key rotation or historical Run re-encryption / decryption policy.
5. Reveal API or UI reveal button.
6. Client-side copy of secret plaintext.
7. Public API secret creation, secret patching, secret reveal, or secret-bearing copy.
8. Generic sensitive-data detection framework for all logs/errors.
9. New RBAC model, owner-only Env Group permissions, or Admin-only secret management.
10. New middleware, queue, Redis, Celery, RabbitMQ, Kafka, API Gateway policy layer, or microservice split.
11. Import/export of `.env`, JSON, YAML, CSV, or shell files.
12. Env Group tags, version history, diff, archive/restore, or soft delete.
13. Runner protocol changes.

## 5. Key Decisions

| Area | Decision |
| --- | --- |
| Capability name | `env_group_secret` |
| Variable types | Exactly `plain` and `secret`; enum values are lower snake case strings. |
| Storage location | Reuse `env_groups.variables` JSONB; no side table in this Slice. |
| Stored entry shape | Per-variable typed entry containing at minimum `type` and internal `value`. |
| Legacy write compatibility | Not supported at runtime; implementation must perform a one-time data migration that converts existing string-map variables to typed `plain` entries. |
| Read model | Session/Web reads use a masked secret model; public reads use a separate plain-only DTO and do not expose masked secret entries. |
| Public API | Plain variables only; public secret create/patch/reveal/copy is forbidden. |
| Session duplicate | Allowed to server-side copy secret values; response remains masked. |
| Snapshot | Internal snapshot may keep execution-needed values; external snapshot/report views expose only keys/masked metadata. |
| Execution bundle | Uses internal full view to produce process environment variables; no runner protocol change. |
| OpenAPI source | FastAPI/Pydantic remains the only source of truth; generated front-end types must not be handwritten. |
| New dependencies | None. |

## 6. Data Contract

### 6.1 Conceptual Env Group variable entry

The API and storage concept is a map from environment variable key to a typed entry.

| Field | Required | Contract |
| --- | --- | --- |
| variable key | yes | Existing key rule remains `^[A-Za-z_][A-Za-z0-9_]{0,63}$`. |
| `type` | yes | Must be `plain` or `secret`. |
| `value` | write-dependent | Plain entries require a string `value`. Secret create requires plaintext `value`. Secret patch may omit `value` only to preserve an existing secret value. |
| `hasValue` | session/Web read-only | Returned only for session/Web masked secret read entries; `true` means server has a stored secret value. |
| `displayValue` | session/Web read-only | Returned only for session/Web masked secret read entries as the fixed masked token `********`. |

Rules:

1. Max variables per group remains `200`.
2. Plain and secret values are strings; empty string remains allowed.
3. UTF-8 encoded value length remains `<= 4096` bytes.
4. The API must reject unknown variable entry fields instead of silently preserving them.
5. The implementation must include a one-time data migration that converts every existing old string-map variable entry into `{ "type": "plain", "value": "<existing string>" }` before runtime code relies on the typed shape.
6. The stored object must not contain old string-map entries after the migration or after successful create/patch in this Slice.
7. The SDD intentionally does not define exact table names, column types, indexes, ORM models, or migration filenames beyond preserving the existing Env Group storage location. Implementation must backfill exact migration/type details after reading current code.

### 6.2 Write model examples

Create with mixed plain and secret variables:

```http
POST /api/v1/env-groups
Content-Type: application/json
x-csrf-token: <csrf>
```

```json
{
  "name": "staging",
  "description": "Staging environment",
  "variables": {
    "BASE_URL": { "type": "plain", "value": "https://staging.example.test" },
    "API_TOKEN": { "type": "secret", "value": "token-value" }
  }
}
```

Patch to replace a secret value:

```json
{
  "variables": {
    "BASE_URL": { "type": "plain", "value": "https://staging.example.test" },
    "API_TOKEN": { "type": "secret", "value": "new-token-value" }
  }
}
```

Patch to preserve an existing secret value:

```json
{
  "variables": {
    "BASE_URL": { "type": "plain", "value": "https://staging.example.test" },
    "API_TOKEN": { "type": "secret" }
  }
}
```

Preserve semantics apply only when the target Env Group already has `API_TOKEN` as a `secret` entry with a stored value. The same payload on create, or against a missing/plain existing variable, returns `VALIDATION_ERROR`.

### 6.3 Masked read model example

```json
{
  "id": "01J0Y6T6H2Y0S9V4W8M7N6P5Q8",
  "name": "staging",
  "description": "Staging environment",
  "variableCount": 2,
  "inUse": false,
  "variables": {
    "BASE_URL": { "type": "plain", "value": "https://staging.example.test" },
    "API_TOKEN": { "type": "secret", "hasValue": true, "displayValue": "********" }
  },
  "createdBy": "01J0Y6T6H2Y0S9V4W8M7N6P5Q8",
  "updatedBy": "01J0Y6T6H2Y0S9V4W8M7N6P5Q8",
  "createdAt": "2030-07-01T00:00:00Z",
  "updatedAt": "2030-07-01T00:00:00Z"
}
```

Rules:

1. `displayValue` is a session/Web UI display hint only and must not be accepted as a submitted secret value.
2. `hasValue` must not expose length, entropy, prefix, suffix, hash, or creation time of the secret value.
3. The masked read model is session/Web only.
4. Public reads must use a separate plain-only public DTO. Public responses must not include secret `value`, `hasValue`, `displayValue`, masked secret entries, secret field paths, or any secret-bearing example.
5. Public OpenAPI must not include the masked read model.

## 7. API Contract

### 7.1 Session Env Group routes

| Method | Path | Contract change |
| --- | --- | --- |
| `GET` | `/api/v1/env-groups` | Summary remains value-free. `variableCount` counts both plain and secret entries. |
| `POST` | `/api/v1/env-groups` | Accepts typed entries including `secret`; returns masked detail. |
| `GET` | `/api/v1/env-groups/{envGroupId}` | Returns masked detail. |
| `PATCH` | `/api/v1/env-groups/{envGroupId}` | Replaces the full variables object when `variables` is present; supports secret preserve/replace semantics. |
| `DELETE` | `/api/v1/env-groups/{envGroupId}` | Unchanged reference protection behavior. |
| `POST` | `/api/v1/env-groups/{envGroupId}/duplicate` | Server-side copies plain and secret entries; returns masked detail. |

Session rules:

1. Existing Workspace, auth, CSRF, name uniqueness, delete protection, list pagination, and duplicate name rules remain unchanged.
2. `variables: null` remains invalid when the field is present.
3. `PATCH` retains full replacement semantics for `variables`; clients must submit all variables they want to keep.
4. For secret preservation, the service must read the existing stored entry in the same Workspace before writing the replacement object.
5. Any response path that currently returns `EnvGroupDetail` must use the masked read model after this Slice.

### 7.2 Public Env Group routes

| Method | Path | Contract change |
| --- | --- | --- |
| `POST` | `/api/public/v1/env-groups` | Accepts typed entries only when every entry is `type: "plain"`; returns the plain-only public DTO. |
| `PATCH` | `/api/public/v1/env-groups/{envGroupId}` | Allows plain-only typed replacement only for non-secret-bearing target groups. `type: "secret"` or a secret-bearing target with `variables` present returns `VALIDATION_ERROR`. |
| `DELETE` | `/api/public/v1/env-groups/{envGroupId}` | Unchanged reference protection behavior; response must not expose secret metadata. |
| `POST` | `/api/public/v1/env-groups/{envGroupId}/copy` | If source has any secret entry, return `ENV_GROUP_SECRET_PUBLIC_COPY_DENIED` and do not create a copy. |

Public rules:

1. Public routes continue to require PAT Bearer auth and `config:write` for writes.
2. Public routes must not accept browser session auth or CSRF.
3. Public routes must not call a service mode that preserves, copies, reveals, writes, or masks secret values.
4. Public read/detail responses must use the plain-only public DTO; they must not reuse the session masked detail schema.
5. Public `variableCount` means the number of public-visible plain variables, not the internal total variable count, so it does not reveal secret-variable presence.
5. Public copy must detect secret-bearing source groups before calling duplicate/create logic.
6. Public patch with `variables` present must detect a secret-bearing target before mutation and reject the request rather than silently dropping or preserving hidden secret entries.
7. Public OpenAPI must not show secret write/copy examples, masked secret read fields, or secret-bearing response examples.

## 8. Error Contract

| Code | HTTP status | Surface | Contract |
| --- | --- | --- | --- |
| `VALIDATION_ERROR` | `422` | session/public | Invalid typed entry shape, unsupported `type`, missing required `value`, old string-map payload, null variables, value too long, too many variables, invalid key, forbidden public secret type, or public variable patch against a secret-bearing target. |
| `ENV_GROUP_NAME_CONFLICT` | `409` | session/public | Existing Env Group name uniqueness behavior remains unchanged. |
| `ENV_GROUP_IN_USE` | `409` | session/public | Existing delete protection behavior remains unchanged. |
| `ENV_GROUP_SECRET_PUBLIC_COPY_DENIED` | `409` | public | Public copy source contains one or more secret entries. No target Env Group is created. |
| `RESOURCE_NOT_FOUND` | `404` | session/public | Existing Workspace-hidden missing resource behavior remains unchanged. |

Representative public copy failure:

```json
{
  "code": "ENV_GROUP_SECRET_PUBLIC_COPY_DENIED",
  "message": "Public API cannot copy Env Groups that contain secret variables.",
  "requestId": "req_01J0Y6T6H2Y0S9V4W8M7N6P5Q8",
  "details": null
}
```

Rules:

1. Error `details` must not include secret variable values.
2. Validation details may include variable keys and field paths, but must not include rejected plaintext values.
3. Public forbidden secret writes use `VALIDATION_ERROR` rather than a public secret-management code because public secret writing is not a supported capability.

## 9. Runtime, Snapshot, Preview, and Report Contracts

### 9.1 Internal full view

API service code may materialize an internal full view for execution-only paths:

```json
{
  "BASE_URL": "https://staging.example.test",
  "API_TOKEN": "token-value"
}
```

Rules:

1. Internal full view is allowed only inside service/runtime functions that create Run Snapshots or Execution Bundles.
2. Internal full view must not be returned by route handlers, public schemas, Web schemas, preview responses, report responses, logs, audit details, or generated OpenAPI examples.
3. Runner protocol remains unchanged: execution receives a process environment map.

### 9.2 Run Snapshot

This Slice keeps Run Snapshot behavior operational by storing execution-needed values in the internal snapshot payload. This is an explicit temporary security boundary, not a Snapshot encryption solution.

Rules:

1. Snapshot write may include the internal full env values needed to reproduce the Run.
2. Snapshot read/report/public views expose only Env Group name and variable keys or masked metadata.
3. Snapshot payload returned through any API must not expose secret plaintext.
4. A later Snapshot Security Slice must own encryption, key rotation, and historical decryption boundaries.

### 9.3 Execution Bundle

Execution Bundle generation must consume the internal full view and produce the same runtime environment behavior as before for Taurus/JMeter execution.

Rules:

1. Execution Bundle must support both plain and secret variables at runtime.
2. Execution Bundle must not write secret plaintext into manifest fields, preview YAML, response payloads, or diagnostic metadata unless the existing execution engine strictly requires process environment injection.
3. Runner callback contracts do not change.

### 9.4 Preview and report

Rules:

1. Test Plan Preview must reuse or extend existing environment-value redaction behavior. Scenario Preview is not exposed under `ADR-0023`.
2. Run Report continues to expose Env Group variable keys, not values.
3. Public Run Report follows the same value-free contract.
4. Debug HTTP Trace redaction remains a separate feature; this Slice does not generalize it.

## 10. Web UI Contract

| UI area | Contract |
| --- | --- |
| Env Group list | No value display. `variableCount` includes plain and secret entries. |
| Create/edit form | Each row has key, type, and value input behavior. |
| Plain value | Editable as ordinary text under existing validation. |
| Secret value | Input is write-only. Existing secret displays `********` and `hasValue: true`. |
| Secret preserve | Leaving an existing secret value blank preserves it only when the row remains `type: "secret"`. |
| Secret replace | Entering a new value replaces the stored secret. |
| Secret reveal | Not implemented. |
| Secret copy | Not implemented. |
| Duplicate | Session duplicate may duplicate secret-bearing groups; duplicate result page/details stay masked. |

Rules:

1. Web must use generated types from `@surgepilot/contracts`.
2. Web must not invent local API shapes or import generated files by relative paths.
3. Web must not store secret plaintext in persisted local storage, route query strings, URLs, analytics payloads, or test snapshots.
4. Web may hold newly typed secret values in transient form state only until submit/reset/navigation.
5. Web validation mirrors API validation for feedback only; API validation remains authoritative.

## 11. OpenAPI and Generated Contracts

Required artifacts remain:

```text
packages/contracts/openapi/api.openapi.json
packages/contracts/openapi/public-api.openapi.json
packages/contracts/generated/*
```

Rules:

1. `make generate-contracts` must run after schema changes.
2. Internal/Web OpenAPI must show typed Env Group variables and masked secret read model.
3. Public OpenAPI must show typed plain Env Group variables for public write routes and plain-only public response DTOs.
4. Public OpenAPI must exclude hidden-value fields, masked-read fields, write/copy examples for non-public variable types, plaintext examples, and any field that can reconstruct protected variable semantics.
5. Generated Web client/types are consumers of the API contract and must not be manually patched.
6. Existing public OpenAPI exclusion checks must be extended to include Env Group secret exclusions.

## 12. Test and Acceptance Criteria

### 12.1 API and service

1. `test_env_group_create_secret_returns_masked_detail` verifies session create stores a secret and returns no plaintext.
2. `test_env_group_get_secret_returns_masked_detail` verifies session get returns `hasValue` and `displayValue` only.
3. `test_env_group_patch_secret_without_value_preserves_existing_value` verifies session preserve semantics.
4. `test_env_group_patch_secret_with_value_replaces_existing_value` verifies explicit replacement.
5. `test_env_group_patch_old_string_map_rejected` verifies no legacy dual-schema compatibility.
6. `test_env_group_duplicate_secret_copies_runtime_value_but_masks_response` verifies session duplicate behavior.
7. `test_public_env_group_create_secret_rejected` verifies `VALIDATION_ERROR` for public secret write.
8. `test_public_env_group_patch_secret_rejected` verifies public patch cannot introduce secret.
9. `test_public_env_group_patch_secret_bearing_target_rejected` verifies public variable replacement cannot silently drop or preserve hidden secret entries.
10. `test_public_env_group_copy_secret_source_rejected` verifies `ENV_GROUP_SECRET_PUBLIC_COPY_DENIED` and no target row.
11. `test_env_group_validation_errors_do_not_echo_secret_values` verifies error details are safe.

### 12.2 Runtime / reports

1. `test_run_snapshot_uses_internal_full_env_view` verifies execution-needed variables are present internally.
2. `test_execution_bundle_materializes_secret_env_variable` verifies runtime receives secret values through the existing env map.
3. `test_run_report_exposes_env_group_keys_only_for_secret_group` verifies Run Report does not expose values.
4. `test_public_run_report_exposes_env_group_keys_only_for_secret_group` verifies public report does not expose values.
5. `test_execution_preview_redacts_secret_env_values` verifies Test Plan Preview redaction.

### 12.3 OpenAPI / Web

1. `test_internal_openapi_env_group_typed_variable_contract` verifies internal artifact schema changed from string-map to typed variables.
2. `test_public_openapi_env_group_plain_only_write_contract` verifies public artifact has plain-only write examples/contracts and plain-only public response DTOs.
3. `test_public_openapi_excludes_env_group_secret_plaintext` verifies no protected variable plaintext fields, masked read fields, examples, or reveal contracts.
4. `env-groups secret create/edit component test` verifies masked display and preserve/replace UI semantics.
5. `env-groups secret no reveal or copy test` verifies UI has no reveal/copy path for secret plaintext.

## 13. Done When

This Slice is done only when:

1. Env Group variable contract is typed across API schemas, service validation, session routes, public routes, Web generated types, and tests.
2. No session/public Env Group read returns secret plaintext.
3. Public create/patch rejects `type: "secret"` with `VALIDATION_ERROR`.
4. Public copy rejects secret-bearing source groups with `ENV_GROUP_SECRET_PUBLIC_COPY_DENIED`.
5. Session duplicate preserves runtime usability of copied secret variables while returning masked responses.
6. Run Snapshot creation and Execution Bundle generation preserve runtime env behavior for plain and secret variables.
7. Preview, Run Report, public Run Report, OpenAPI examples, test snapshots, and Web persisted state contain no secret plaintext.
8. `make generate-contracts` updates internal/public OpenAPI and generated contracts.
9. `make verify` passes, including public OpenAPI secret exclusion checks.
10. Implementation Backfill is completed with exact file paths, schema names, migration names, generated operation IDs, and test names.

## 14. Implementation Backfill

Implementation PR backfill:

1. API schema class names:
   - `EnvGroupPlainVariableWrite`
   - `EnvGroupSecretVariableWrite`
   - `EnvGroupPlainVariableRead`
   - `EnvGroupSecretVariableRead`
   - `EnvGroupCreateRequest`
   - `EnvGroupPatchRequest`
   - `EnvGroupDetail`
   - `PublicEnvGroupCreateRequest`
   - `PublicEnvGroupPatchRequest`
   - `PublicEnvGroupDetail`
2. Service helper names:
   - `normalize_variables`
   - `validate_variables`
   - `validate_public_variables`
   - `mask_variables`
   - `public_plain_variables`
   - `internal_env_values`
   - `env_group_runtime_values`
   - `env_group_has_secret_variables`
   - `reject_public_secret_bearing_group`
   - `raise_public_secret_copy_denied`
3. Migration filename:
   - `apps/api/migrations/versions/0017_p2_03_env_group_secret.py`
4. Route updates:
   - `apps/api/app/routes/env_groups.py`: `detail_response` now returns masked variables for session Env Group detail responses.
   - `apps/api/app/routes/public_api.py`: `public_create_env_group`, `public_patch_env_group`, and `public_copy_env_group` now use plain-only public DTOs and public secret exclusion checks.
5. Runtime materialization updates:
   - `apps/api/app/services/scenarios.py`
   - `apps/api/app/services/test_plans.py`
   - `apps/api/app/services/execution_bundles.py`
6. Web files:
   - `apps/web/src/app/api-client.ts`
   - `apps/web/src/features/env-groups/pages/env-groups-page.tsx`
   - `apps/web/src/features/env-groups/env-groups.test.tsx`
7. OpenAPI export and stale-check behavior:
   - `make generate-contracts` regenerates `packages/contracts/openapi/api.openapi.json`, `packages/contracts/openapi/public-api.openapi.json`, and `packages/contracts/generated/web-client/index.ts`.
   - Public OpenAPI secret exclusion coverage is implemented in `tests/contract/test_p2_02_public_api_openapi.py`.
8. Test files:
   - `apps/api/tests/test_p2_03_env_group_secret.py`
   - `apps/api/tests/test_p0_01_env_groups_api.py`
   - `apps/api/tests/test_p0_01_env_groups_service.py`
   - `apps/api/tests/test_p0_05_scenarios_api.py`
   - `apps/api/tests/test_p0_06_test_plans_api.py`
   - `apps/api/tests/test_p1_04_scenario_testplan_polish_api.py`
   - `apps/api/tests/test_p2_02_public_api.py`
   - `apps/web/src/App.test.tsx`
   - `apps/web/src/features/env-groups/env-groups.test.tsx`
   - `tests/contract/test_p0_01_env_groups_openapi.py`
   - `tests/contract/test_p2_02_public_api_openapi.py`
   - `tests/test_p0_06_ssh_taurus_smoke_verifier.py`

## 15. Remaining Risks


1. Run Snapshot stores execution-needed secret plaintext until a later Snapshot Security Slice; this is an accepted temporary boundary for P2-03 only and must not be represented as encryption or key governance.
2. Existing old string-map Env Group variables must be converted by the required one-time migration before typed runtime code is enabled; this SDD forbids ongoing dual-schema runtime compatibility.
