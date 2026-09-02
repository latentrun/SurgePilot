# 09. Testing and Acceptance Strategy

## Verification entrypoints

`make verify` is the default local and CI gate. It grows from an M0 bootstrap check into lint, type checking, API tests, Runner tests, Web tests, coverage, contract freshness, and generated-client freshness. `make verify-e2e` owns browser acceptance plus fake-Runner and configured real-SSH profiles. CI invokes the same root commands used locally.

## Test ownership

| Layer | Location | Focus |
| --- | --- | --- |
| API | `apps/api/tests` | services, routes, DB behavior, security, state transitions, storage |
| Runner | `apps/runner/tests` | process control, callback client/schema, Stop, fake Runner |
| Web | `apps/web` tests | components, routes, forms, generated client, view states |
| Contract | `tests/contract` | OpenAPI and client freshness, Runner JSON Schema, boundaries |
| E2E | `tests/e2e` | manual closed loop, Stop path, real/fake Runner profiles |

PostgreSQL and real MinIO are used for integration behavior that depends on their semantics. Unit tests isolate external boundaries, but mocks must not replace the business rule being asserted.

## Required foundation coverage

- API JSON/OpenAPI exposes camelCase while Python and DB models remain snake_case.
- Workspace filtering covers reads, writes, cross-Workspace references, Public Load Node visibility, and the Setup Status exception.
- Run tests cover every legal transition and terminal immutability.
- `accepted` remains `initializing`; Stop covers both `initializing -> stopping` and `running -> stopping`.
- Duplicate and out-of-order callbacks, concurrent delivery, Stop-before-accepted, and the Stop/start race are deterministic and idempotent.
- Acceptance, heartbeat, and Stop grace timeouts converge and never release an uncertain node to Idle.
- MinIO tests cover safe paths, size/hash enforcement, authorization, deduplication, conflicts, and streaming failure cleanup.
- Web tests cover auth/role gates, mutation duplicate prevention, loading/empty/error states, polling termination, and separate Run/SLA/validity presentation.

## Initial E2E acceptance

The happy path registers or logs in, creates required assets, builds a visual Scenario and Test Plan, manually selects one Idle node, starts a Run, observes completion, and views report conclusions and artifacts. The Stop path stops an initializing or running Run, tolerates duplicate Stop/callback delivery, reaches `aborted`, and makes the node reusable only after process cleanup is known safe.

Fake Runner provides deterministic ordinary CI coverage and must share the real callback client and schema. It does not replace a configured real SSH smoke that proves transfer, start, heartbeat, Stop, terminal callback, cleanup, and artifact boundaries.

## Acceptance rule

A Slice is complete only when its design, contract, implementation, generated artifacts, tests, and user-visible behavior agree and root verification passes. Tests or scaffolding must not introduce excluded capabilities. Coverage thresholds may be introduced progressively during M0, but new functional behavior requires meaningful branch coverage from its first Slice.
