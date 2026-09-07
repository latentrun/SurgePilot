# ADR-0006: P0 Separate API Worker

- Status: Accepted
- Scope: P0 background jobs, self-healing, cleanup, and asynchronous compensation

## Context

P0-Stability requires work that must continue independently of browser requests: heartbeat timeout scans, stop grace convergence, stale node lease recovery, force-kill cleanup, artifact summary parsing, and Load Node initialization attempts. These jobs mutate shared PostgreSQL state and must remain idempotent if the process restarts or more than one worker is accidentally started. P0 must keep the architecture simple and must not introduce Redis, Celery, RabbitMQ, Kafka, or an external queue service.

## Options Considered

1. **Separate `api-worker` process using PostgreSQL coordination**
   - Pros: keeps HTTP serving separate from background loops, works with the existing API codebase and image, avoids external infrastructure, supports advisory locks and row-level claiming.
   - Cons: requires a second process in development and Docker Compose.
2. **Run background loops inside each FastAPI web process**
   - Pros: fewer process entrypoints.
   - Cons: duplicated scans under multiple API workers, harder shutdown behavior, hidden long-running work in HTTP processes, and greater risk of conflicting state transitions.
3. **Use Celery/RQ with Redis or another broker**
   - Pros: mature job semantics.
   - Cons: violates P0 scope, adds infrastructure, and creates a queue system before P0 needs one.
4. **Do everything synchronously in HTTP requests**
   - Pros: direct request/response flow.
   - Cons: long SSH and parsing operations would block users and fail if the request disconnects.

## Decision

P0 uses a separate `api-worker` process from the same codebase and container image as `apps/api`.

The worker uses PostgreSQL for coordination with two distinct mechanisms:

1. global periodic scans use PostgreSQL advisory locks, for example heartbeat timeout scans, stop grace scans, stale lease recovery, and orphaned initialization-attempt recovery;
2. object-level work items use row-level claiming with `FOR UPDATE SKIP LOCKED`, for example Load Node initialization attempts and artifact summary parsing jobs;
3. each worker task must be idempotent and safe after restart;
4. no external broker, cache, or queue service is introduced in P0.

FastAPI web processes must not start long-running background loops. P0 Docker Compose starts one `api-worker` by default. If more than one worker process is started accidentally, advisory locks and row-level claiming must prevent duplicate scans or duplicate work-item execution.

## Consequences

Positive consequences:

1. HTTP request handling remains simple and stateless with respect to long-running jobs.
2. P0 self-healing work can run even when no user is polling a page.
3. Docker Compose can start API and worker independently while using one image.
4. Future multi-replica API deployments do not duplicate background scans inside web workers, and duplicate worker processes must be de-duplicated by PostgreSQL locks or row claiming.

Costs and constraints:

1. Local development and CI must account for a worker entrypoint.
2. Worker jobs must use PostgreSQL locks or row claiming, not in-memory flags.
3. P0 worker behavior is not a general resource queue or scheduling system.
4. Introducing Redis, Celery, RabbitMQ, Kafka, or external queues requires a future ADR that supersedes this decision.

## Related ADRs

- `ADR-0001-monorepo.md`
- `ADR-0002-runner-independent-app.md`
- `ADR-0003-p0-minio-only.md`
- `ADR-0004-p0-manual-single-node-only.md`

## References

- `docs/sdd/01-architecture-overview.md`
- `docs/sdd/02-repo-structure-and-dev-workflow.md`
- `docs/sdd/05-runner-protocol-and-run-state-machine.md`
- `docs/sdd/slices/P0-03-load-nodes.md`
- `docs/sdd/slices/P0-04-run-state-machine-runner-protocol.md`
