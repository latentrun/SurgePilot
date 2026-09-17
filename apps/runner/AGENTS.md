# Runner Agent Notes

- Follow root `AGENTS.md` and `docs/sdd/05-runner-protocol-and-run-state-machine.md`.
- This file is subordinate to `/AGENTS.md`; when conflicts occur, follow root AGENTS and the referenced SDD.
- Follow root verification gates and `docs/sdd/09-testing-and-acceptance-strategy.md` for test expectations.
- Runner is an independent app and must not import `apps/api` internals.
- Communicate with API only through runner protocol HTTP callbacks and `packages/contracts`.
- Runner internal API requests use `x-runner-token`.
- Callback payloads follow `packages/contracts/runner/runner-callback.schema.json`; `eventId` is the idempotency key.
- Heartbeat, stop, and terminal overwrite behavior follows `docs/sdd/05-runner-protocol-and-run-state-machine.md`.
- Do not access PostgreSQL or MinIO directly; artifacts go through API in P0.
- Keep fake-runner behavior inside this app so tests and E2E share runner code paths.
