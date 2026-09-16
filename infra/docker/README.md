# Docker Compose

Docker Compose provides a lightweight base for smoke/E2E, a source full stack with Monitoring
and the internal Demo Load Node, and the separate digest-pinned tagged-release stack under
`infra/release/`.

```bash
make infra-up
make infra-down
make start-full-stack
make start-full-ssh-e2e
make start-full-ssh-e2e-build
make dev-compose
make verify-p1-00-monitoring-compose
```

`make dev-compose` is a compatibility alias for `make start-full-stack`.

`make start-full-stack` builds source application images and builds or reuses a Linux Runtime
through `infra/docker/runtime-builder/Dockerfile`. It uses internal Demo API/InfluxDB origins by
default. External nodes require both final node-facing URL overrides.

`make start-full-ssh-e2e` remains the two-node manual-review path. It disables the internal Demo
profile and reuses the same containerized Runtime builder. Use `make verify-runtime-compat` for
the Ubuntu 24.04 + Debian 12 Runtime compatibility matrix.

The MinIO init sidecar creates the default `surgepilot` bucket.

- `infra/docker/docker-compose.base.yml` is the lightweight base used by smoke, SSH, and P0 API E2E profiles. It intentionally excludes Grafana and InfluxDB.
- `infra/docker/docker-compose.yml` is the source full stack with Monitoring and the optional
  `demo` profile enabled by official startup.
- `infra/release/docker-compose.release.yml` is the no-build release template rendered with
  immutable image index digests by `scripts/build_release_bundle.py`.

InfluxDB is not exposed through Nginx. Use the published InfluxDB port or a deployment-specific node-facing URL for Load Node writes.
