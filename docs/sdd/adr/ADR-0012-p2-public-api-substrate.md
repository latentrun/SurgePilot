# ADR-0012: P2 Public API Substrate

- Status: Accepted
- Scope: P2-02 programmatic public API substrate, PAT ownership surface, public OpenAPI artifact, governed AI skill package boundary, and the ADR-0016 authenticated source-download exception

## Context

SurgePilot needs a stable programmatic API surface for external automation, future MCP servers and skills. The API must support business operations without exposing browser session mechanics, internal runner endpoints, storage internals or token-management bootstrap operations.

The first PAT cannot be created through a PAT-only public API. Placing PAT create/list/revoke under `/api/public/v1/*` would create a bootstrap deadlock and would make token management look like a public programmatic capability. SurgePilot already has a browser session security model with CSRF for writes, so self-service PAT management belongs in the Account session surface.

`ADR-0010` remains scoped to P2-00 API Catalog Scalar and does not authorize P2-02.

## Options Considered

### Option A: Public token management

Rejected because the caller would need a PAT to create the first PAT. It also encourages token-on-token rotation and external token-management automation before SurgePilot has explicit governance for that capability.

### Option B: Admin token management

Rejected because API tokens are current-user credentials. Normal `user` accounts must be able to manage their own tokens, and `admin` should not automatically gain token-management powers over other users.

### Option C: Account self-service plus PAT-only public business API

Accepted.

## Decision

1. PAT create/list/revoke belongs to browser session APIs under `/api/v1/account/api-tokens`.
2. The UI route is `/account/api-keys` and is available to both `user` and `admin` roles.
3. Token management is self-only in P2-02 Phase A. Admin users manage only their own tokens through this surface.
4. `/api/public/v1/*` uses PAT Bearer authentication and does not expose token-management operations.
5. P2-02 public scopes are exactly `read`, `config:write`, `run` and `dependency:write`. `dependency:write` is limited to public Dependency File upload/delete; Dependency File list uses `read`.
6. `tokens:write` is not a P2-02 Phase A public scope.
7. `packages/contracts/openapi/api.openapi.json` may contain `/api/v1/account/api-tokens` and session schemas.
8. `packages/contracts/openapi/public-api.openapi.json` must exclude token-management routes, token-management schemas, PAT plaintext fields, `secretHash`, example token values and reconstructable secret fields.
9. `make verify` must include automated checks for public OpenAPI freshness, token-management exclusion and secret exclusion.
10. Public PAT Workspace resolution must use explicit `x-workspace-id`, or a single Workspace from the token allowlist when the header is absent. It must not use browser current session, browser local storage, preferred Workspace or default Workspace fallback.
11. P2-02 authorizes one repo-maintained, contract-aligned AI skill source package at `packages/ai-skills/surgepilot-public-api/`. The package may contain host-agent instructions, a snapshot copied from `packages/contracts/openapi/public-api.openapi.json`, a lightweight `operationId`-only caller, and verification tests. It is not a Web static asset, SDK, MCP server, skills runtime, installer, marketplace package, or published release artifact. ADR-0016/P2-04 may expose this source through one session-authenticated request-built zip download; that exception is not release publication.
12. P2-02 also authorizes one non-sensitive DB-backed runtime setting, `loadNodeApiBaseUrl`, for the origin that remote Load Nodes use when runners call SurgePilot API. The only bootstrap fallback is `SURGEPILOT_NODE_API_BASE_URL`; `APP_BASE_URL` is not a runner callback fallback. The runner wire variable remains `SURGEPILOT_API_BASE_URL` and is written only into the per-Run `.surgepilot.env`. Missing or invalid configuration blocks future remote Run start fail-closed, but registration and initialization remain allowed.
13. Official Make startup may best-effort derive the final `SURGEPILOT_NODE_API_BASE_URL` from one unambiguous publish address and `SURGEPILOT_API_HOST_PORT` when the final URL is absent. It must not introduce a public host intermediate variable, overwrite a DB setting, or turn raw Compose into an address-discovery contract.
14. The skill package may be verified by `make verify`. Its allowlist must match the current public OpenAPI `operationId` set exactly, its bundled snapshot must fail stale checks when it drifts, and it must fail closed for forbidden routes, secret-bearing contracts, missing explicit Workspace context, confirmation-required writes, and public API error responses. This verification authorization does not authorize release packaging, signing, checksums, version publishing, or any new public API capability. Help/download UI is authorized only through ADR-0016/P2-04's session route and remains outside `/api/public/v1/*`.
15. ADR-0016/P2-04 may add `GET /api/v1/account/ai-skill/download` for logged-in `user` and `admin` accounts. It is user-accessible but not Workspace-scoped, does not require `x-workspace-id`, does not use CSRF, builds the zip per request, and must appear only in the Web/business OpenAPI artifact.
16. P2-02 authorizes the bounded public Dependency File operations `GET /api/public/v1/dependency-files`, `POST /api/public/v1/dependency-files`, and `DELETE /api/public/v1/dependency-files/{dependencyFileId}`. They must reuse existing filename/extension/size/SHA-256, MinIO object-key, audit, Workspace-isolation, and reference-protection behavior. Public Dependency File preview/download and a generic multipart framework remain out of scope.

## Consequences

1. First PAT bootstrap uses existing browser login/session/CSRF protection.
2. Normal users can self-serve API keys without access to Admin UI.
3. Public API consumers cannot rotate or create tokens through the public API in Phase A.
4. Any future admin-managed token workflow or token-on-token rotation requires a separate governance item with explicit audit, permission and UX contracts.
5. Contract generation must support two artifacts: the Web/business artifact and a stricter public artifact.
6. Public OpenAPI verification must become a CI/`make verify` gate, not a manual review convention.
7. SurgePilot maintainers own the source skill package and its contract snapshot; third-party adapters may still consume the public API independently, but they are not the canonical package implementation.
8. ADR-0016's source download gives users a convenient copy of repository-owned source without creating a release/version/update channel or changing the skill's explicit Workspace, allowlist, confirmation, and fail-closed boundaries.
9. Verification backfill: session token coverage is in `apps/api/tests/test_p2_02_api_tokens_api.py`; public bearer/scope/Workspace/structured-write/Run/Dependency File coverage is in `apps/api/tests/test_p2_02_public_api.py`; node-facing origin, readiness, and start-blocking coverage is in `apps/api/tests/test_p2_02_load_node_connectivity.py`; public artifact exclusion and byte-identical skill-snapshot alignment are in `tests/contract/test_p2_02_public_api_openapi.py`; internal session-token and connectivity operations are covered in `tests/contract/test_openapi_contract.py`; and Web coverage is in `apps/web/src/features/account/api-keys.test.tsx` and `apps/web/src/features/load-nodes/load-node-connectivity-summary.test.tsx`. Deployment `.env`/bootstrap/Makefile startup governance and the SSH lifecycle verifier belong to the later startup checkpoint.

## Related ADRs

- `docs/sdd/adr/ADR-0010-p2-api-catalog-scalar.md` remains the accepted decision for P2-00 only.
- `docs/sdd/adr/ADR-0016-p2-help-ai-agents-system-openapi-bootstrap.md` governs the authenticated source download and Help surface.

## References

- `docs/sdd/slices/P2-02-public-api-substrate.md`
- `docs/sdd/slices/P2-README.md`
- `docs/sdd/04-api-contract-guidelines.md`
- `docs/sdd/06-security-permission-workspace.md`
- `AGENTS.md`
