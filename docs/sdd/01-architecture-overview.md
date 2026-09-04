# 01. Architecture Overview

## Principles

- Keep the initial deployment understandable and operable on an internal network.
- Separate business-state authority from remote process execution.
- Define contracts before consumers and generate browser types from OpenAPI.
- Use PostgreSQL for durable business and coordination state and MinIO for file bytes.
- Make unsafe states converge through idempotent callbacks and background compensation.
- Do not add infrastructure for excluded future capabilities.

## Components

```text
Browser -> Web -> API -> PostgreSQL
                  |  -> MinIO
                  |  -> SSH/SFTP -> Load Node -> Runner -> Taurus/JMeter
                  |
                  +<----------- authenticated Runner callbacks

             api-worker -> PostgreSQL coordination and bounded SSH cleanup
```

| Component | Responsibility |
| --- | --- |
| Web | Product UI; communicates only with API using generated contracts |
| API | Authentication, authorization, Workspace isolation, business rules, Run state, leases, and storage proxy |
| api-worker | Timeout scans, compensation, lease recovery, and lightweight asynchronous jobs |
| Runner | Independent remote process control, heartbeats, callbacks, and artifact upload to API |
| PostgreSQL | Authoritative metadata, sessions, state, leases, events, and audit records |
| MinIO | Dependency File and Run Artifact bytes |
| Load Node | Runner, Taurus/JMeter, and isolated Run directories |

The Runner has no database or MinIO access. The browser has no direct MinIO access. API and api-worker may share application packages and an image but run as separate processes.

## Initial technology baseline

- Web: React, Vite, TypeScript, React Router, TanStack Query, Tailwind CSS.
- API: Python, FastAPI, Pydantic, SQLAlchemy, Alembic.
- Runner: independent Python application using a versioned JSON callback schema.
- State: PostgreSQL.
- Object storage: MinIO only.
- Local orchestration: Docker Compose and root Make targets.

## Run flow

The API atomically creates a Run, immutable snapshot, and one node lease in `initializing`, then performs remote setup outside the transaction. Runner reports `accepted`, `running`, heartbeat, artifact, and terminal events. API state and conditional database transitions are authoritative. api-worker handles acceptance timeout, heartbeat timeout, Stop grace expiry, and stale lease recovery.

## Deployment boundary

The initial deployment consists of Web, API, api-worker, PostgreSQL, MinIO, and a MinIO bootstrap step. Runner is installed or transferred to a Load Node and invoked over SSH. Redis, Celery, RabbitMQ, Kafka, Kubernetes, Grafana, InfluxDB, and additional object-store providers are outside the initial architecture.
