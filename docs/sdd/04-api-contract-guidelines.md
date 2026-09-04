# 04. API Contract Guidelines

## Boundary

The API exposes browser-facing business routes under `/api/v1`, health endpoints outside the business namespace, and Runner-only routes under `/api/internal/v1`. Initial implementation has no general programmatic public API. Web uses only the generated client and types from `packages/contracts`.

## Naming and data types

- API request and response JSON fields use `camelCase`.
- Python, database, migration, and ORM fields use `snake_case`.
- Pydantic schemas define aliases and API serialization emits aliases; only camelCase properties appear in OpenAPI.
- Resource paths use plural kebab-case nouns and path parameters use camelCase.
- External business IDs are 26-character ULID strings.
- API timestamps are ISO 8601 UTC strings ending in `Z`; PostgreSQL uses `timestamptz`.
- Enum values use lower snake case. UI labels map them to user-facing text.

Example public JSON:

```json
{
  "workspaceId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
  "failureType": "node_unreachable"
}
```

## Authentication and context

Browser business routes use the server-side session cookie. Browser write requests made after a session exists include `x-csrf-token`. Workspace-aware routes accept `x-workspace-id`; the initial product may resolve the user's Default Workspace when the header is absent. Runner endpoints require `x-runner-token`, do not accept browser session authority, and bind the token identity to the referenced Run.

## Response shape

A successful single-resource response returns the resource directly. Lists use:

```json
{
  "items": [],
  "page": 1,
  "pageSize": 20,
  "total": 0
}
```

Delete may return `204` with no body. Errors use a stable machine-readable shape:

```json
{
  "error": {
    "code": "LOAD_NODE_UNAVAILABLE",
    "message": "The selected load node is unavailable.",
    "details": null,
    "requestId": "request-id"
  }
}
```

Messages are safe for users; logs hold diagnostic context and never secrets. Expected mappings include `400` invalid request, `401` unauthenticated, `403` forbidden or CSRF failure, `404` absent or not visible, `409` state/reference conflict, `413` upload too large, `422` field validation, and `503` unavailable dependency.

## Mutation and idempotency rules

- Run creation atomically persists Run, snapshot, and node lease before remote work begins.
- Stop is idempotent: an active Run converges toward cancellation and repeated Stop returns the current state.
- Runner callback events deduplicate by `(runId, eventId)`.
- Artifact events deduplicate by event ID and reject conflicting reuse of a relative path.
- State changes use legal-predecessor conditional updates, not unchecked read-then-write mutation.

## OpenAPI workflow

FastAPI/Pydantic is the source for the browser API contract. The repository commits a generated OpenAPI artifact and generated TypeScript client. Contract generation must be deterministic, contract freshness is part of `make verify`, and breaking changes require explicit review. Runner callbacks use a separately versioned JSON Schema because Runner is an independent application.

No API endpoint may activate an initial-scope exclusion merely because it has no UI.
