# 02. Repository Structure and Development Workflow

## Repository layout

```text
apps/
  api/                 FastAPI application, worker entrypoint, and migrations
  runner/              independent Runner application
  web/                 React application
packages/
  contracts/           OpenAPI output, generated Web client, Runner JSON Schemas
infra/
  docker/              Compose and container support
tests/
  contract/            cross-application contract checks
  e2e/                 end-to-end and real/fake Runner profiles
docs/
  prd/                 product requirements
  sdd/                 foundation, ADR, and Slice design documents
Makefile                stable repository commands
```

Applications must not import another application's private internals. Web consumes the generated client from `packages/contracts`; Runner and API communicate through versioned HTTP and JSON contracts.

## Root command contract

The repository exposes stable commands for bootstrap, development, contract generation, lint, type checking, tests, verification, and E2E verification. `make verify` is the default local and CI gate. `make verify-e2e` owns fake-Runner and configured real-SSH acceptance. Exact commands may begin as an M0 bootstrap subset but must retain their names as implementation grows.

## Contract-first workflow

1. Update the API schema or Runner JSON Schema source.
2. Generate committed OpenAPI, client, and schema artifacts.
3. Implement producers and consumers.
4. Add tests for behavior and contract freshness.
5. Run the root verification entrypoint.

Generated files are never edited by hand. Verification fails when generated artifacts are stale.

## Local development

Dependencies run in Docker Compose while Web, API, api-worker, and Runner may run from source. Environment examples contain placeholders only; real credentials and local overrides are ignored by version control. Database changes use append-only Alembic revisions rather than runtime schema creation.

## Scope discipline

Each change follows design -> schema/contracts -> backend -> Runner/Web -> generated artifacts -> tests -> factual documentation. Repository scaffolding must not introduce routes, services, dependencies, tables, or configuration for excluded future capability.
