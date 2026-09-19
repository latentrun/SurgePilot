# Runner Agent Instructions

Scope: `apps/runner/**`.

Inherits `/AGENTS.md`. This file adds Runner-specific constraints and review rules. Consult
`docs/sdd/05-runner-protocol-and-run-state-machine.md` for protocol or state changes.

- Runner is an independent application and does not import API internals.
- Communicate with API only through documented HTTP protocol and `packages/contracts`.
- Internal requests use `x-runner-token`; callback `eventId` is the idempotency key.
- Runner never owns direct PostgreSQL or MinIO access. Artifacts cross the API boundary defined by
  the active design.
- Keep Fake Runner behavior in this application so tests exercise intended shared code paths.
- State-machine safety, late-callback protection, Stop idempotency, heartbeat behavior, and lease
  release cannot be weakened for convenience or minimum diff.

## Code Review Rules

- Flag callbacks that can overwrite terminal state or apply the same event twice.
- Flag failure/cancellation paths that can leave a Load Node permanently Busy.
- Flag direct database/storage access or imports from API internals.
- Flag Fake Runner behavior that diverges from the real Runner path without explicit test intent.
