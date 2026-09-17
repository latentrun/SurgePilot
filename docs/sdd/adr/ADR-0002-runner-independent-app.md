# ADR-0002: Runner Independent App

- Status: Accepted
- Scope: P0 Runner, API, contracts, and Load Node execution boundary

## Context

SurgePilot P0 executes load tests on remote Load Nodes while the API remains the business state authority. The Runner runs outside the API process and must continue reporting progress through a documented protocol even when execution is detached from the user's browser session. P0 also requires callback idempotency, Stop convergence, heartbeat timeout handling, artifact upload, and credential safety. These requirements need a strict boundary between platform state management and remote process execution.

## Options Considered

1. **Runner as an independent application**
   - Pros: clear process boundary, no API database access from Load Nodes, protocol-first integration, easier real SSH acceptance, safer long-running execution.
   - Cons: requires explicit contracts, callback authentication, and integration tests across API and Runner.
2. **Runner embedded in `apps/api` internals**
   - Pros: fewer packages and direct access to existing Python functions.
   - Cons: couples remote execution to API internals, encourages database access from execution code, makes Load Node packaging unsafe, and weakens contract-first development.
3. **Single API process executes load tests directly**
   - Pros: simplest control flow for a local prototype.
   - Cons: blocks or overloads API workers, does not model remote Load Nodes, and cannot satisfy P0 node isolation and cleanup requirements.

## Decision

Runner is an independent application under `apps/runner`.

Runner must not import `apps/api` internal modules and must not access PostgreSQL, MinIO credentials, session state, or Workspace data directly. API and Runner communicate only through documented contracts and HTTP protocol boundaries:

1. shared contracts in `packages/contracts`;
2. runner callback schemas;
3. internal runner endpoints protected by `x-runner-token`;
4. API-mediated streaming artifact upload using the `Runner -> API -> MinIO` path.

API remains the authority for Run state, Workspace checks, node lease decisions, artifact metadata, and terminal convergence. Runner owns only remote process execution behavior and protocol callbacks. P0 does not give Runner MinIO credentials, bucket/object keys, or presigned upload URLs.

## Consequences

Positive consequences:

1. Remote execution can be tested and packaged independently from the API server.
2. Load Nodes do not need access to API internals or database credentials.
3. P0 callback idempotency, heartbeat, Stop, and artifact contracts stay explicit.
4. Web, API, and Runner cannot silently invent incompatible data shapes.

Costs and constraints:

1. Contract changes require OpenAPI/schema updates before consumer changes.
2. Runner protocol tests are required even when using a fake runner for development.
3. Shared business logic must live in contracts or duplicated protocol-safe utilities, not in API internals imported by Runner.
4. Runner acceptance cannot be replaced permanently by API-only tests.

## Related ADRs

- `ADR-0001-monorepo.md`
- `ADR-0003-p0-minio-only.md`
- `ADR-0004-p0-manual-single-node-only.md`
- `ADR-0006-p0-separate-api-worker.md`

## References

- `docs/sdd/01-architecture-overview.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- `docs/sdd/slices/P0-04-run-state-machine-runner-protocol.md`
- `packages/contracts/runner/runner-callback.schema.json`
