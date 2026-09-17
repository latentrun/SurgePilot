# ADR-0014: P2 Env Group Secret

- Status: Accepted
- Scope: P2 Env Group variable type contract, masking boundary, public API exclusion, Run Snapshot temporary security boundary

## Context

SurgePilot currently treats Env Group variables as `dict[str,string]`. The existing model, schemas, services, session routes, public routes, Run Snapshot creation, and Execution Bundle materialization all assume plaintext string values.

P0 Env Groups deliberately excluded secrets. P2 scope includes Env Group Secret types and sensitive value display/copy restrictions, while Snapshot encryption, key rotation, and broader redaction governance are separate later P2 capabilities.

P2-02 Public API Substrate exposes Env Group structured create/patch/delete/copy through PAT-authenticated public routes. That Slice does not authorize public secret management. Env Group Secret therefore needs its own Slice and decision boundary so it does not accidentally expand P2-02 public API scope.

SurgePilot is still in active development, so runtime support for old `dict[str,string]` write compatibility would add dual-schema parsing, contract, service, route, Web, public API, and test paths without product value. Existing old string-map data must instead be converted by a one-time migration into typed `plain` entries before typed runtime code is enabled.

## Options Considered

### Option A: Reuse existing `env_groups.variables` JSONB with typed per-variable entries

Accepted.

This keeps the current Env Group aggregate and service boundary while changing each variable value to a typed entry such as `{ "type": "plain", "value": "..." }` or `{ "type": "secret", "value": "..." }`. Session/Web read models mask secret values; public read models use a separate plain-only DTO and do not expose masked secret entries. Runtime paths use an internal full view.

### Option B: Add `env_group_secrets` side table

Rejected for this Slice.

A side table would clarify secret storage boundaries, but it adds join/assembly behavior, split CRUD semantics, public exclusion logic, migration complexity, and extra test surface. The current requirement does not include encryption, rotation, or separate secret lifecycle governance that would justify the additional model.

### Option C: Integrate Vault/KMS/external Secret Manager

Rejected for this Slice.

External secret infrastructure would exceed the requested scope and introduce deployment, credential, rotation, and local development complexity before SurgePilot has accepted Snapshot Security and key governance designs.

### Option D: Preserve old `dict[str,string]` as a compatibility input

Rejected.

Ongoing dual-format compatibility would increase implementation and test complexity. The project is still in active development, and the Slice should converge on a single typed contract.

## Decision

1. Create a standalone P2 Env Group Secret Slice SDD: `docs/sdd/slices/P2-03-env-group-secret.md`.
2. Reuse the existing `env_groups.variables` JSONB storage location and switch variable values to typed per-variable entries.
3. Do not support old `dict[str,string]` Env Group variable payloads after the Slice is implemented.
4. Perform a required one-time migration that converts existing old string-map variable entries into typed `plain` entries before typed runtime code is enabled.
5. Support exactly two variable types in this Slice: `plain` and `secret`.
6. Session Env Group create/patch may write secret plaintext; session read responses must return masked secret metadata only.
7. Session duplicate may copy secret values server-side, but every response remains masked.
8. Public Env Group create/patch must reject secret writes with `VALIDATION_ERROR`.
9. Public Env Group responses must use a plain-only DTO and must not expose masked secret read fields or secret-bearing examples.
10. Public Env Group copy must reject secret-bearing source groups with `ENV_GROUP_SECRET_PUBLIC_COPY_DENIED` and must not create a target Env Group.
11. No reveal API or UI reveal button is added.
12. No external Secret Manager, encryption at rest, Snapshot encryption, key rotation, or generic redaction platform is added.
13. Run Snapshot may internally persist execution-needed plaintext env values until a later Snapshot Security Slice; external snapshot/report/public views must not expose secret plaintext.
14. Execution Bundle generation uses an internal full view and does not change the Runner protocol.
15. Internal/public OpenAPI artifacts and generated Web contracts must be regenerated from FastAPI/Pydantic schemas; public artifacts must exclude hidden-value fields, masked-read fields, secret write/copy examples, plaintext examples, and reconstructable secret fields.

## Consequences

1. Env Group contract changes are explicit and isolated from P2-02 Public API Substrate.
2. Implementation remains medium-sized by preserving the existing Env Group aggregate and route/service boundaries.
3. Public API automation can continue managing plain Env Groups but cannot create, patch, reveal, read masked-secret metadata, or copy secret-bearing groups.
4. Web and API code must use the session masked read model only for browser session surfaces; public routes must use plain-only DTOs.
5. Existing development data with old string-map variables must be converted by the required one-time migration; runtime code must not keep dual-schema compatibility.
6. Snapshot plaintext remains a known temporary risk until a separate Snapshot Security design adds encryption and key governance.
7. After this ADR is accepted, governance docs must stay synchronized: `AGENTS.md`, `docs/sdd/00-product-scope-and-priority.md`, `docs/sdd/slices/P2-README.md`, and `docs/sdd/02-repo-structure-and-dev-workflow.md` §12 must reference this Slice and ADR as the Env Group Secret authorization source while preserving ADR-0013 exclusively for static Marketing Landing / Logo.

## Related ADRs

- `docs/sdd/adr/ADR-0012-p2-public-api-substrate.md` remains the accepted decision for P2-02 public API substrate and does not authorize public secret management.
- `docs/sdd/adr/ADR-0022-p1-governance-start.md` continues to require named accepted Slice SDDs before new staged capabilities are implemented.

## References

- `docs/sdd/slices/P2-03-env-group-secret.md`
- `docs/sdd/slices/P0-01-env-groups.md`
- `docs/sdd/slices/P2-02-public-api-substrate.md`
- `docs/sdd/00-product-scope-and-priority.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `docs/sdd/04-api-contract-guidelines.md`
- `docs/sdd/06-security-permission-workspace.md`
- `docs/sdd/09-testing-and-acceptance-strategy.md`
- `AGENTS.md`
