.DEFAULT_GOAL := help

ORIGINAL_XDG_DATA_HOME := $(XDG_DATA_HOME)
ORIGINAL_XDG_CACHE_HOME := $(XDG_CACHE_HOME)
ORIGINAL_XDG_STATE_HOME := $(XDG_STATE_HOME)
ORIGINAL_XDG_CONFIG_HOME := $(XDG_CONFIG_HOME)

SURGEPILOT_TOOLCHAIN_DATA_ROOT ?= $(if $(strip $(ORIGINAL_XDG_DATA_HOME)),$(ORIGINAL_XDG_DATA_HOME),$(HOME)/.local/share)/surgepilot-contributor-toolchain
SURGEPILOT_TOOLCHAIN_CACHE_ROOT ?= $(if $(strip $(ORIGINAL_XDG_CACHE_HOME)),$(ORIGINAL_XDG_CACHE_HOME),$(HOME)/.cache)/surgepilot-contributor-toolchain
SURGEPILOT_TOOLCHAIN_STATE_ROOT ?= $(if $(strip $(ORIGINAL_XDG_STATE_HOME)),$(ORIGINAL_XDG_STATE_HOME),$(HOME)/.local/state)/surgepilot-contributor-toolchain
SURGEPILOT_TOOLCHAIN_CONFIG_ROOT ?= $(if $(strip $(ORIGINAL_XDG_CONFIG_HOME)),$(ORIGINAL_XDG_CONFIG_HOME),$(HOME)/.config)/surgepilot-contributor-toolchain
export SURGEPILOT_TOOLCHAIN_DATA_ROOT SURGEPILOT_TOOLCHAIN_CACHE_ROOT
export SURGEPILOT_TOOLCHAIN_STATE_ROOT SURGEPILOT_TOOLCHAIN_CONFIG_ROOT

TOOLCHAIN_FREE_GOALS := help dev infra-up infra-down e2e-clean stop-preview stop-full-stack stop-full-ssh-e2e
TOOLCHAIN_MANAGEMENT_GOALS := toolchain-install toolchain-check
TOOLCHAIN_MANAGEMENT_REQUESTS := $(filter $(TOOLCHAIN_MANAGEMENT_GOALS),$(MAKECMDGOALS))
TOOLCHAIN_REQUIRED_GOALS := $(filter-out $(TOOLCHAIN_FREE_GOALS) $(TOOLCHAIN_MANAGEMENT_GOALS),$(MAKECMDGOALS))
TOOLCHAIN_DISPATCH_REQUIRED := $(if $(filter 1,$(SURGEPILOT_TOOLCHAIN_ACTIVE)),,$(if $(TOOLCHAIN_REQUIRED_GOALS),1,))

ifneq ($(TOOLCHAIN_MANAGEMENT_REQUESTS),)
ifneq ($(words $(MAKECMDGOALS)),1)
$(error toolchain-install and toolchain-check must be requested alone)
endif
endif

.PHONY: help toolchain-install toolchain-check toolchain-tests setup setup-docs-browser dev dev-web dev-api dev-worker dev-runner dev-compose release-runtime _release-runtime start-preview _start-preview-with-env _start-preview stop-preview start-full-stack _start-full-stack-with-env _start-full-stack restart-full-stack _restart-full-stack-with-env _restart-full-stack stop-full-stack seed-full-ssh-e2e-runtime _seed-full-ssh-e2e-runtime start-full-ssh-e2e _start-full-ssh-e2e start-full-ssh-e2e-build _start-full-ssh-e2e-build restart-full-ssh-e2e _restart-full-ssh-e2e restart-full-ssh-e2e-build _restart-full-ssh-e2e-build stop-full-ssh-e2e infra-up infra-down e2e-clean migrate migration generate-contracts lint test api-coverage ai-skill-tests verifier-tests python-patch-coverage verify-db verify-smoke-compose verify verify-e2e verify-runtime-compat verify-p2-05-release-stack verify-p1-00-monitoring-compose verify-p1-00-monitoring-ssh verify-p1-00-monitoring-remote-node-write verify-p1-08-debug-http-trace-e2e verify-p2-01-openapi-two-node-e2e verify-p2-02-public-api-lifecycle verify-runner-ssh verify-runner-ssh-fast _verify-runner-ssh verify-p0-api-main-flow-e2e verify-p0-api-main-flow-e2e-fast verify-p0-06-runner-ssh verify-p0-06-runner-ssh-fast contracts-stale-check

COMPOSE_BASE=docker compose -f infra/docker/docker-compose.base.yml
COMPOSE_FULL=docker compose -f infra/docker/docker-compose.yml $(if $(filter false,$(SURGEPILOT_DEMO_LOAD_NODE_ENABLED)),,--profile demo)
COMPOSE_PREVIEW=docker compose -f infra/docker/docker-compose.yml
COMPOSE_FULL_SSH_E2E=$(COMPOSE_FULL) -f infra/docker/docker-compose.ssh-e2e.yml --profile ssh-e2e
COMPOSE_DEV=$(COMPOSE_BASE) -f infra/docker/docker-compose.dev.yml --profile dev
COMPOSE_SMOKE=$(COMPOSE_BASE) -f infra/docker/docker-compose.smoke.yml --profile smoke
COMPOSE_SSH_E2E=$(COMPOSE_BASE) -f infra/docker/docker-compose.ssh-e2e.yml --profile ssh-e2e
DEPLOYMENT_ENV_RUN=$(if $(wildcard $(CURDIR)/.env),uv run --all-packages dotenv -f "$(CURDIR)/.env" run --no-override --,)
BOOTSTRAP_DEPLOYMENT_ENV=python3 scripts/bootstrap_deployment_env.py --root "$(CURDIR)"
NODE_FACING_STARTUP=uv run --all-packages python scripts/node_facing_startup.py --
VERIFY_RUNNER_INTERNAL_TOKEN ?= surgepilot-verification-token
VERIFY_SSH_CREDENTIAL_ENCRYPTION_KEY ?= MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=
VERIFY_MINIO_ENV=MINIO_BUCKET=surgepilot MINIO_ACCESS_KEY=minioadmin MINIO_SECRET_KEY=surgepilot-verification-minio-secret MINIO_ROOT_USER=minioadmin MINIO_ROOT_PASSWORD=surgepilot-verification-minio-secret
VERIFY_COMPOSE_ENV=RUNNER_INTERNAL_TOKEN=$(VERIFY_RUNNER_INTERNAL_TOKEN) SSH_CREDENTIAL_ENCRYPTION_KEY=$(VERIFY_SSH_CREDENTIAL_ENCRYPTION_KEY) $(VERIFY_MINIO_ENV)
VERIFY_DB_COMPOSE=COMPOSE_PROJECT_NAME=surgepilot-verify-db POSTGRES_HOST_PORT=0 $(VERIFY_COMPOSE_ENV) $(COMPOSE_DEV)
FULL_SSH_E2E_PROJECT ?= surgepilot-full-ssh-e2e
FULL_SSH_E2E_RUNTIME_VERSION ?= p0-e2e
FULL_SSH_E2E_RUNTIME_ARTIFACT_HOST_DIR ?= /tmp/surgepilot-runtime-artifacts-$(FULL_SSH_E2E_PROJECT)
FULL_SSH_E2E_RUNTIME_BUILD_DIR ?= /tmp/surgepilot-runtime-build-$(FULL_SSH_E2E_PROJECT)
FULL_SSH_E2E_RUNTIME_CACHE_DIR ?= /tmp/surgepilot-runtime-cache-$(FULL_SSH_E2E_PROJECT)
FULL_SSH_E2E_RUNTIME_ENV_FILE ?= $(FULL_SSH_E2E_RUNTIME_ARTIFACT_HOST_DIR)/runtime.env
FULL_SSH_E2E_SSH_CREDENTIAL_ENCRYPTION_KEY ?= MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=
FULL_SSH_E2E_ENV=$(VERIFY_COMPOSE_ENV) COMPOSE_PROJECT_NAME=$(FULL_SSH_E2E_PROJECT) SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false LOAD_NODE_RUNTIME_VERSION=$(FULL_SSH_E2E_RUNTIME_VERSION) LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR=$(FULL_SSH_E2E_RUNTIME_ARTIFACT_HOST_DIR) SSH_CREDENTIAL_ENCRYPTION_KEY=$(FULL_SSH_E2E_SSH_CREDENTIAL_ENCRYPTION_KEY)
FULL_SSH_E2E_APP_BUILD_SERVICES=api-migrate api api-worker web
RUNTIME_ARTIFACT_HOST_DIR ?= $(CURDIR)/.surgepilot/runtime-artifacts/default
RUNTIME_BUILD_DIR ?= $(CURDIR)/.surgepilot/runtime-build
RUNTIME_CACHE_DIR ?= $(CURDIR)/.surgepilot/runtime-cache
RUNTIME_ENV_FILE ?= $(RUNTIME_ARTIFACT_HOST_DIR)/runtime.env
PREVIEW_RUNTIME_ARTIFACT_HOST_DIR ?= $(CURDIR)/.surgepilot/runtime-artifacts/preview-empty
RUNTIME_RELEASE_COMMAND ?= uv run --all-packages python scripts/run_runtime_builder.py --output-dir "$(RUNTIME_ARTIFACT_HOST_DIR)" --build-dir "$(RUNTIME_BUILD_DIR)" --cache-dir "$(RUNTIME_CACHE_DIR)" --env-file "$(RUNTIME_ENV_FILE)" $${RUNTIME_RELEASE_PREFIX:+--release-prefix "$${RUNTIME_RELEASE_PREFIX}"}
RUNNER_SSH_RUNTIME_VERSION ?= p0-e2e
RUNNER_SSH_RUNTIME_ARTIFACT_DIR ?= $(CURDIR)/.surgepilot/runtime-artifacts/runner-ssh
RUNNER_SSH_RUNTIME_BUILD_DIR ?= $(CURDIR)/.surgepilot/runtime-build/runner-ssh
RUNNER_SSH_RUNTIME_CACHE_DIR ?= $(CURDIR)/.surgepilot/runtime-cache/runner-ssh
RUNNER_SSH_RUNTIME_ENV_FILE ?= $(RUNNER_SSH_RUNTIME_ARTIFACT_DIR)/runtime.env
RUNTIME_COMPAT_PROJECT ?= surgepilot-runtime-compat
RUNTIME_COMPAT_RUNTIME_VERSION ?= p0-e2e
RUNTIME_COMPAT_RUNTIME_ARTIFACT_DIR ?= $(CURDIR)/.surgepilot/runtime-artifacts/compat
RUNTIME_COMPAT_RUNTIME_BUILD_DIR ?= $(CURDIR)/.surgepilot/runtime-build/compat
RUNTIME_COMPAT_RUNTIME_CACHE_DIR ?= $(CURDIR)/.surgepilot/runtime-cache/compat
RUNTIME_COMPAT_RUNTIME_ENV_FILE ?= $(RUNTIME_COMPAT_RUNTIME_ARTIFACT_DIR)/runtime.env
RUNTIME_COMPAT_COMPOSE=COMPOSE_PROJECT_NAME=$(RUNTIME_COMPAT_PROJECT) SURGEPILOT_SSH_E2E_PORT=0 SURGEPILOT_SSH_E2E_DEBIAN12_PORT=0 $(VERIFY_COMPOSE_ENV) $(COMPOSE_BASE) -f infra/docker/docker-compose.ssh-e2e.yml --profile ssh-e2e --profile runtime-compat


export XDG_DATA_HOME ?= /tmp/surgepilot-xdg-data
export PNPM_HOME ?= /tmp/surgepilot-pnpm
export PNPM_STORE_PATH ?= /tmp/surgepilot-pnpm-store

ifneq ($(TOOLCHAIN_MANAGEMENT_REQUESTS),)

toolchain-install:
	@scripts/toolchain install

toolchain-check:
	@scripts/toolchain check

else ifeq ($(TOOLCHAIN_DISPATCH_REQUIRED),1)

.PHONY: __toolchain-dispatch $(MAKECMDGOALS)

$(MAKECMDGOALS): __toolchain-dispatch

__toolchain-dispatch:
	+@scripts/toolchain exec -- $(MAKE) $(MAKECMDGOALS)

else

help:
	@printf "SurgePilot commands:\n"
	@printf "  make toolchain-install  Install or repair the isolated contributor toolchain\n"
	@printf "  make toolchain-check    Validate the contributor toolchain offline without mutation\n"
	@printf "  make toolchain-tests    Run focused contributor-toolchain tests\n"
	@printf "  make setup              Install pnpm and uv workspace dependencies\n"
	@printf "  make setup-docs-browser Install the Playwright-managed Chromium used by docs verification\n"
	@printf "  make infra-up           Start PostgreSQL and MinIO for local development\n"
	@printf "  make infra-down         Stop local dependency services without deleting volumes\n"
	@printf "  make e2e-clean          Stop E2E compose stacks and delete volumes\n"
	@printf "  make dev-web            Start the Vite web dev server\n"
	@printf "  make dev-api            Start the FastAPI dev server\n"
	@printf "  make dev-worker         Start the api-worker entrypoint\n"
	@printf "  make dev-runner         Show runner CLI help\n"
	@printf "  make release-runtime    Build or reuse the Linux Load Node runtime in the Docker builder\n"
	@printf "  make start-preview     Start the source control plane without Runtime or Demo readiness\n"
	@printf "  make stop-preview      Stop the source control-plane preview without deleting volumes\n"
	@printf "  make start-full-stack   Initialize config, prepare Runtime, and start Monitoring plus the Demo Load Node\n"
	@printf "  make restart-full-stack Preserve config and restart; preflights the Load Node runtime before stopping\n"
	@printf "  make stop-full-stack    Stop full local stack without deleting volumes\n"
	@printf "  make start-full-ssh-e2e Start full local stack plus two SSH E2E load nodes using existing local SSH image\n"
	@printf "  make start-full-ssh-e2e-build  Build SSH image, prepare runtime, then start full SSH E2E stack\n"
	@printf "  make restart-full-ssh-e2e  Restart full SSH E2E stack using existing local SSH image\n"
	@printf "  make restart-full-ssh-e2e-build  Rebuild SSH image, prepare runtime, then restart full SSH E2E stack\n"
	@printf "  make stop-full-ssh-e2e  Stop full local stack plus SSH E2E load nodes\n"
	@printf "  make dev-compose        Alias for start-full-stack\n"
	@printf "  make generate-contracts Export OpenAPI and generate web client/types\n"
	@printf "  make lint               Run bootstrap lint checks\n"
	@printf "  make test               Run bootstrap tests\n"
	@printf "  make api-coverage       Run API tests with line and branch coverage gate\n"
	@printf "  make ai-skill-tests     Run governed Public API AI skill tests\n"
	@printf "  make verifier-tests     Run script verifier unit tests\n"
	@printf "  make python-patch-coverage  Run Python patch coverage gate\n"
	@printf "  make verify-db          Run PostgreSQL migration and first-admin concurrency tests\n"
	@printf "  make verify-smoke-compose  Start full smoke stack and check api-worker startup logs\n"
	@printf "  make verify             Run verification excluding SSH/Docker E2E\n"
	@printf "  make verify-e2e         Run full P0 E2E gate when later slices provide it\n"
	@printf "  make verify-runtime-compat  Build one production runtime and verify it on Ubuntu 24.04 and Debian 12 SSH nodes\n"
	@printf "  make verify-p2-05-release-stack  Verify an already-started release through the Demo Debug Run path\n"
	@printf "  make verify-p1-00-monitoring-compose  Validate P1 Monitoring compose/nginx configuration\n"
	@printf "  make verify-p1-00-monitoring-ssh  Run P1 Monitoring SSH supplemental smoke when environment is ready\n"
	@printf "  make verify-p1-00-monitoring-remote-node-write  Run P1 Monitoring remote node write supplemental smoke when environment is ready\n"
	@printf "  make verify-p2-01-openapi-two-node-e2e  Run OpenAPI Step Generation plus two-node SSH E2E\n"
	@printf "  make verify-p2-02-public-api-lifecycle  Run P2-02 Public API lifecycle E2E\n"
	@printf "  make verify-p1-08-debug-http-trace-e2e  Run P1-08 Debug HTTP Trace browser acceptance\n"
	@printf "  make verify-runner-ssh  Run near-real SSH/SFTP runner control smoke\n"
	@printf "  make verify-runner-ssh-fast  Run SSH smoke with existing local image, without rebuilding\n"
	@printf "  make verify-p0-api-main-flow-e2e  Run P0-00..P0-07 real-system API E2E\n"
	@printf "  make verify-p0-api-main-flow-e2e-fast  Reuse local images for P0 API main-flow E2E\n"
	@printf "  make verify-p0-06-runner-ssh  Run P0-06 Test Plan over SSH/Taurus smoke\n"
	@printf "  make verify-p0-06-runner-ssh-fast  Reuse local images for P0-06 SSH/Taurus smoke\n"
	@printf "  make contracts-stale-check  Check generated contracts are fresh\n"

setup:
	pnpm install
	uv sync --all-packages --all-groups

setup-docs-browser:
	pnpm --filter @surgepilot/docs exec playwright install chromium

toolchain-tests:
	uv run --all-packages pytest -q tests/contract/test_toolchain_governance.py tests/test_toolchain_bootstrap.py

dev:
	@printf "Run make infra-up, then use separate terminals for make dev-api, make dev-worker, and make dev-web.\n"

dev-web:
	$(DEPLOYMENT_ENV_RUN) pnpm --filter @surgepilot/web dev

dev-api:
	$(DEPLOYMENT_ENV_RUN) uv run --directory apps/api fastapi dev app/main.py

dev-worker:
	$(DEPLOYMENT_ENV_RUN) uv run --directory apps/api python -m app.worker

dev-runner:
	cd apps/runner && uv run python runner.py --help

dev-compose: start-full-stack

release-runtime:
	$(DEPLOYMENT_ENV_RUN) $(MAKE) _release-runtime

_release-runtime:
	$(RUNTIME_RELEASE_COMMAND)

start-preview:
	$(BOOTSTRAP_DEPLOYMENT_ENV)
	$(MAKE) _start-preview-with-env

_start-preview-with-env:
	$(DEPLOYMENT_ENV_RUN) $(MAKE) _start-preview

_start-preview:
	@set -eu; \
		export SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false; \
		export COMPOSE_PROFILES=; \
		export LOAD_NODE_RUNTIME_VERSION=; \
		export LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR="$(PREVIEW_RUNTIME_ARTIFACT_HOST_DIR)"; \
		printf "[1/2] Validating source preview configuration...\n"; \
		uv run --all-packages python scripts/release_preflight.py validate-external; \
		$(COMPOSE_PREVIEW) config >/dev/null; \
		uv run --all-packages python scripts/release_preflight.py prepare-preview-runtime --path "$(PREVIEW_RUNTIME_ARTIFACT_HOST_DIR)"; \
		$(COMPOSE_PREVIEW) --profile demo stop demo-load-node; \
		printf "[2/2] Building and starting source control-plane services...\n"; \
		$(COMPOSE_PREVIEW) up -d --build
	@printf "SurgePilot Preview started.\nWeb: http://localhost:%s\nGrafana: http://localhost:%s/grafana/\n\n" "$${SURGEPILOT_HTTP_PORT:-8080}" "$${SURGEPILOT_HTTP_PORT:-8080}"
	@printf "Load Node Runtime: not prepared (Setup Status may report not_configured).\nDemo Load Node: disabled.\nLoad Node initialization and Run execution readiness are not promised.\n"
	@printf "For the complete execution demo, run: make start-full-stack\n"

stop-preview:
	$(COMPOSE_PREVIEW) down

start-full-stack:
	$(BOOTSTRAP_DEPLOYMENT_ENV)
	$(MAKE) _start-full-stack-with-env

_start-full-stack-with-env:
	$(DEPLOYMENT_ENV_RUN) $(MAKE) _start-full-stack

_start-full-stack:
	@printf "[1/3] Validating source full-stack configuration...\n"
	uv run --all-packages python scripts/release_preflight.py validate-external
	@printf "[2/3] Preparing the Load Node Runtime...\n"
	@if [ "$${SURGEPILOT_SKIP_RUNTIME_PREFLIGHT:-}" = "1" ]; then \
		printf "Skipping Load Node runtime preflight for manual/debug startup; setup status may report not_configured or artifact_missing.\n"; \
		printf "[3/3] Building and starting the complete source stack...\n"; \
		$(COMPOSE_FULL) up -d --build; \
	else \
		set -e; \
		$(MAKE) release-runtime; \
		. "$(RUNTIME_ENV_FILE)"; \
		LOAD_NODE_RUNTIME_VERSION="$$LOAD_NODE_RUNTIME_VERSION" LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR="$$LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR" $(COMPOSE_FULL) config >/dev/null; \
		printf "[3/3] Building and starting the complete source stack...\n"; \
		LOAD_NODE_RUNTIME_VERSION="$$LOAD_NODE_RUNTIME_VERSION" LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR="$$LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR" $(COMPOSE_FULL) up -d --build; \
	fi
	@printf "SurgePilot started successfully.\nWeb: http://localhost:%s\nGrafana: http://localhost:%s/grafana/\n" "$${SURGEPILOT_HTTP_PORT:-8080}" "$${SURGEPILOT_HTTP_PORT:-8080}"
	@if [ "$${SURGEPILOT_DEMO_LOAD_NODE_ENABLED:-true}" != "false" ]; then \
		printf "Demo Load Node: host=demo-load-node port=22 username=surgepilot\nPassword file: %s/.surgepilot/secrets/demo-load-node-password.secret\nSSH public key: %s/.surgepilot/demo-load-node/ssh_host_ed25519_key.pub\n" "$(CURDIR)" "$(CURDIR)"; \
	fi
	@printf "Next: register the first Admin account, then register and initialize the Demo Load Node.\n"

restart-full-stack:
	$(BOOTSTRAP_DEPLOYMENT_ENV)
	$(MAKE) _restart-full-stack-with-env

_restart-full-stack-with-env:
	$(DEPLOYMENT_ENV_RUN) $(MAKE) _restart-full-stack

_restart-full-stack:
	uv run --all-packages python scripts/release_preflight.py validate-external
	@if [ "$${SURGEPILOT_SKIP_RUNTIME_PREFLIGHT:-}" = "1" ]; then \
		set -e; \
		printf "Skipping Load Node runtime preflight for manual/debug restart; setup status may report not_configured or artifact_missing.\n"; \
		$(COMPOSE_FULL) down; \
		$(COMPOSE_FULL) up -d --build; \
	else \
		set -e; \
		$(MAKE) release-runtime; \
		. "$(RUNTIME_ENV_FILE)"; \
		LOAD_NODE_RUNTIME_VERSION="$$LOAD_NODE_RUNTIME_VERSION" LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR="$$LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR" $(COMPOSE_FULL) config >/dev/null; \
		$(COMPOSE_FULL) down; \
		LOAD_NODE_RUNTIME_VERSION="$$LOAD_NODE_RUNTIME_VERSION" LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR="$$LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR" $(COMPOSE_FULL) up -d --build; \
	fi
	@printf "SurgePilot restarted successfully.\nWeb: http://localhost:%s\nGrafana: http://localhost:%s/grafana/\n" "$${SURGEPILOT_HTTP_PORT:-8080}" "$${SURGEPILOT_HTTP_PORT:-8080}"
	@if [ "$${SURGEPILOT_DEMO_LOAD_NODE_ENABLED:-true}" != "false" ]; then \
		printf "Demo Load Node: host=demo-load-node port=22 username=surgepilot\nPassword file: %s/.surgepilot/secrets/demo-load-node-password.secret\nSSH public key: %s/.surgepilot/demo-load-node/ssh_host_ed25519_key.pub\n" "$(CURDIR)" "$(CURDIR)"; \
	fi
	@printf "Next: register the first Admin account, then register and initialize the Demo Load Node.\n"

stop-full-stack:
	$(COMPOSE_FULL) down

seed-full-ssh-e2e-runtime:
	$(DEPLOYMENT_ENV_RUN) $(MAKE) _seed-full-ssh-e2e-runtime

_seed-full-ssh-e2e-runtime:
	uv run --all-packages python scripts/run_runtime_builder.py --output-dir "$(FULL_SSH_E2E_RUNTIME_ARTIFACT_HOST_DIR)" --build-dir "$(FULL_SSH_E2E_RUNTIME_BUILD_DIR)" --cache-dir "$(FULL_SSH_E2E_RUNTIME_CACHE_DIR)" --env-file "$(FULL_SSH_E2E_RUNTIME_ENV_FILE)" --fixed-version "$(FULL_SSH_E2E_RUNTIME_VERSION)"

start-full-ssh-e2e:
	$(FULL_SSH_E2E_ENV) $(DEPLOYMENT_ENV_RUN) $(NODE_FACING_STARTUP) $(MAKE) _start-full-ssh-e2e

_start-full-ssh-e2e: seed-full-ssh-e2e-runtime
	$(FULL_SSH_E2E_ENV) $(COMPOSE_FULL_SSH_E2E) build $(FULL_SSH_E2E_APP_BUILD_SERVICES)
	$(FULL_SSH_E2E_ENV) $(COMPOSE_FULL_SSH_E2E) up -d --no-build
	@$(FULL_SSH_E2E_ENV) uv run --all-packages python scripts/verify_full_ssh_e2e_node_connectivity.py || { \
		$(FULL_SSH_E2E_ENV) $(COMPOSE_FULL_SSH_E2E) down; \
		exit 1; \
	}

start-full-ssh-e2e-build:
	$(FULL_SSH_E2E_ENV) $(DEPLOYMENT_ENV_RUN) $(NODE_FACING_STARTUP) $(MAKE) _start-full-ssh-e2e-build

_start-full-ssh-e2e-build:
	$(FULL_SSH_E2E_ENV) $(COMPOSE_FULL_SSH_E2E) build ssh-load-node
	$(MAKE) _start-full-ssh-e2e

restart-full-ssh-e2e:
	$(FULL_SSH_E2E_ENV) $(DEPLOYMENT_ENV_RUN) $(NODE_FACING_STARTUP) $(MAKE) _restart-full-ssh-e2e

_restart-full-ssh-e2e:
	$(FULL_SSH_E2E_ENV) $(COMPOSE_FULL_SSH_E2E) down
	$(MAKE) _start-full-ssh-e2e

restart-full-ssh-e2e-build:
	$(FULL_SSH_E2E_ENV) $(DEPLOYMENT_ENV_RUN) $(NODE_FACING_STARTUP) $(MAKE) _restart-full-ssh-e2e-build

_restart-full-ssh-e2e-build:
	$(FULL_SSH_E2E_ENV) $(COMPOSE_FULL_SSH_E2E) down
	$(MAKE) _start-full-ssh-e2e-build

stop-full-ssh-e2e:
	$(FULL_SSH_E2E_ENV) $(COMPOSE_FULL_SSH_E2E) down

infra-up:
	$(COMPOSE_DEV) up -d postgres minio minio-init

infra-down:
	$(COMPOSE_DEV) down

e2e-clean:
	$(VERIFY_COMPOSE_ENV) $(COMPOSE_SSH_E2E) down -v
	$(VERIFY_COMPOSE_ENV) $(COMPOSE_SMOKE) down -v
	$(FULL_SSH_E2E_ENV) $(COMPOSE_FULL_SSH_E2E) down -v
	$(VERIFY_COMPOSE_ENV) $(COMPOSE_FULL) down -v

migrate:
	$(DEPLOYMENT_ENV_RUN) uv run --directory apps/api alembic upgrade head

migration:
	$(DEPLOYMENT_ENV_RUN) uv run --directory apps/api alembic revision --autogenerate -m "$${name:?pass name=...}"

generate-contracts:
	cd apps/api && uv run python ../../scripts/export_openapi.py
	pnpm --filter @surgepilot/contracts generate
	cp packages/contracts/openapi/public-api.openapi.json packages/ai-skills/surgepilot-public-api/references/public-api.openapi.json

lint:
	uv run --all-packages ruff check apps/api apps/runner scripts tests packages/ai-skills/surgepilot-public-api/scripts packages/ai-skills/surgepilot-public-api/tests
	uv run --all-packages ruff format --check apps/api apps/runner scripts tests packages/ai-skills/surgepilot-public-api/scripts packages/ai-skills/surgepilot-public-api/tests
	pnpm -r lint
	pnpm -r typecheck

test:
	$(MAKE) api-coverage
	$(MAKE) ai-skill-tests
	$(MAKE) verifier-tests
	uv run --all-packages pytest apps/runner/tests
	pnpm -r test

api-coverage:
	uv run --all-packages pytest apps/api/tests tests/contract --cov=app --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=90

ai-skill-tests:
	uv run --all-packages pytest packages/ai-skills/surgepilot-public-api/tests -q --cov=packages/ai-skills/surgepilot-public-api/scripts --cov-branch --cov-append --cov-report=term-missing --cov-report=xml --cov-fail-under=90

verifier-tests:
	uv run --all-packages pytest tests/test_bootstrap_deployment_env.py -q --cov=scripts.bootstrap_deployment_env --cov-branch --cov-append --cov-report=term-missing --cov-report=xml --cov-fail-under=90
	uv run --all-packages pytest tests/test_release_preflight.py tests/test_fetch_runtime_release.py tests/test_run_runtime_builder.py tests/test_build_release_bundle.py tests/test_release_installer.py tests/test_release_wrapper.py -q --cov=scripts.release_preflight --cov=scripts.fetch_runtime_release --cov=scripts.run_runtime_builder --cov=scripts.build_release_bundle --cov-branch --cov-append --cov-report=term-missing --cov-report=xml --cov-fail-under=90
	uv run --all-packages pytest tests/test_p2_05_release_stack_verifier.py -q --cov=scripts.verify_p2_05_release_stack --cov-branch --cov-append --cov-report=term-missing --cov-report=xml --cov-fail-under=90
	uv run --all-packages pytest tests/test_api_image_product_version_verifier.py tests/test_node_facing_startup.py tests/test_verify_full_ssh_e2e_node_connectivity.py tests/test_p0_api_main_flow_e2e_verifier.py tests/test_p0_06_ssh_taurus_smoke_verifier.py tests/test_p1_00_monitoring_remote_node_write_verifier.py tests/test_p1_01_ssh_two_node_smoke_verifier.py tests/test_p2_01_openapi_two_node_verifier.py tests/test_p2_02_public_api_lifecycle_verifier.py tests/test_surgepilot_e2e_helpers.py tests/test_verify_runtime_compat_node.py tests/test_release_runtime_artifact.py -q

python-patch-coverage:
	uv run --all-packages diff-cover coverage.xml --fail-under=90 --compare-branch=$${DIFF_COVER_COMPARE_BRANCH:-HEAD}

verify-db:
	@set -e; \
	$(VERIFY_DB_COMPOSE) up -d postgres; \
	trap '$(VERIFY_DB_COMPOSE) down -v >/dev/null 2>&1 || true' EXIT; \
	for i in $$(seq 1 30); do \
		if $(VERIFY_DB_COMPOSE) exec -T postgres pg_isready -U surgepilot -d surgepilot >/dev/null 2>&1; then \
			break; \
		fi; \
		if [ "$$i" = "30" ]; then \
			printf "PostgreSQL did not become ready.\n"; \
			exit 1; \
		fi; \
		sleep 1; \
	done; \
	postgres_host=127.0.0.1; \
	postgres_port=$$($(VERIFY_DB_COMPOSE) port postgres 5432 | awk -F: 'NR == 1 {print $$NF}'); \
	if [ -z "$$postgres_port" ] || ! timeout 3 bash -c "cat < /dev/null > /dev/tcp/127.0.0.1/$$postgres_port" >/dev/null 2>&1; then \
		container_id=$$($(VERIFY_DB_COMPOSE) ps -q postgres); \
		postgres_host=$$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$$container_id"); \
		postgres_port=5432; \
		if [ -z "$$postgres_host" ]; then \
			printf "Unable to discover PostgreSQL host port or container IP for verify-db.\n"; \
			exit 1; \
		fi; \
		printf "Docker did not expose a reachable host PostgreSQL port; using container address %s.\n" "$$postgres_host"; \
	fi; \
	SURGEPILOT_TEST_DATABASE_URL=postgresql://surgepilot:surgepilot@$$postgres_host:$$postgres_port/surgepilot uv run --all-packages pytest apps/api/tests/test_p0_00_postgres_integration.py

verify-smoke-compose:
	uv run --all-packages python scripts/verify_smoke_stack.py

contracts-stale-check:
	@set -e; \
	tmp_dir=$$(mktemp -d); \
	trap 'rm -rf "$$tmp_dir"' EXIT; \
	cp -R packages/contracts/openapi "$$tmp_dir/openapi"; \
	cp -R packages/contracts/generated "$$tmp_dir/generated"; \
	cp packages/ai-skills/surgepilot-public-api/references/public-api.openapi.json "$$tmp_dir/public-api-skill.openapi.json"; \
	$(MAKE) generate-contracts; \
	diff -ru "$$tmp_dir/openapi" packages/contracts/openapi; \
	diff -ru "$$tmp_dir/generated" packages/contracts/generated; \
	diff -u "$$tmp_dir/public-api-skill.openapi.json" packages/ai-skills/surgepilot-public-api/references/public-api.openapi.json

verify: lint test verify-db python-patch-coverage contracts-stale-check
	$(VERIFY_COMPOSE_ENV) $(COMPOSE_SMOKE) config >/dev/null
	$(VERIFY_COMPOSE_ENV) $(COMPOSE_FULL) config >/dev/null

verify-e2e:
	$(VERIFY_COMPOSE_ENV) $(COMPOSE_DEV) up -d minio minio-init
	$(VERIFY_MINIO_ENV) MINIO_ENDPOINT=http://localhost:9000 SURGEPILOT_REAL_MINIO_TEST=1 uv run --all-packages pytest apps/api/tests/test_p0_02_dependency_files_service.py -q -k real_minio_storage_adapter_round_trip
	$(VERIFY_MINIO_ENV) MINIO_ENDPOINT=http://localhost:9000 pnpm e2e -- \
		tests/e2e/p0_00_auth_workspace.spec.ts \
		tests/e2e/p0_01_env_groups.spec.ts \
		tests/e2e/p0_02_dependency_files.spec.ts \
		tests/e2e/p0_03_load_nodes.spec.ts \
		tests/e2e/p0_03_load_node_registration_error.spec.ts \
		tests/e2e/p0_05_scenarios.spec.ts
	$(VERIFY_COMPOSE_ENV) $(COMPOSE_DEV) stop minio minio-init
	$(VERIFY_COMPOSE_ENV) $(COMPOSE_DEV) rm -f -v minio minio-init
	$(VERIFY_MINIO_ENV) $(MAKE) verify-p0-api-main-flow-e2e
	$(VERIFY_MINIO_ENV) $(MAKE) verify-p0-06-runner-ssh

verify-runtime-compat:
	uv run --all-packages python scripts/run_runtime_builder.py --output-dir "$(RUNTIME_COMPAT_RUNTIME_ARTIFACT_DIR)" --build-dir "$(RUNTIME_COMPAT_RUNTIME_BUILD_DIR)" --cache-dir "$(RUNTIME_COMPAT_RUNTIME_CACHE_DIR)" --env-file "$(RUNTIME_COMPAT_RUNTIME_ENV_FILE)" --fixed-version "$(RUNTIME_COMPAT_RUNTIME_VERSION)"
	@set -e; \
	cleanup() { \
		result=$$?; \
		$(RUNTIME_COMPAT_COMPOSE) down -v; \
		exit $$result; \
	}; \
	trap cleanup EXIT; \
	$(RUNTIME_COMPAT_COMPOSE) up -d --build --wait ssh-load-node ssh-load-node-debian12; \
	for service in ssh-load-node ssh-load-node-debian12; do \
		$(VERIFY_COMPOSE_ENV) uv run --all-packages python scripts/verify_runtime_compat_node.py \
			--service "$$service" \
			--artifact-dir "$(RUNTIME_COMPAT_RUNTIME_ARTIFACT_DIR)" \
			--version "$(RUNTIME_COMPAT_RUNTIME_VERSION)" \
			--compose-project "$(RUNTIME_COMPAT_PROJECT)" \
			--compose-file infra/docker/docker-compose.base.yml \
			--compose-file infra/docker/docker-compose.ssh-e2e.yml \
			--profile ssh-e2e \
			--profile runtime-compat; \
	done

verify-p2-05-release-stack:
	uv run --all-packages python scripts/verify_p2_05_release_stack.py

verify-p2-02-public-api-lifecycle:
	env $${HOST_IP:+SURGEPILOT_E2E_HOST_IP=$${HOST_IP} SURGEPILOT_E2E_API_ORCHESTRATION_URL=$${SURGEPILOT_E2E_API_ORCHESTRATION_URL:-http://$${HOST_IP}:8000} SURGEPILOT_E2E_TARGET_URL=$${SURGEPILOT_E2E_TARGET_URL:-http://$${HOST_IP}:8000/api/healthz} SURGEPILOT_E2E_NODE_SSH_HOST=$${HOST_IP} SURGEPILOT_E2E_NODE_SSH_PORT=$${SURGEPILOT_SSH_E2E_PORT:-22322}} uv run --all-packages python scripts/verify_p2_02_public_api_lifecycle.py --build-app --build-ssh $${KEEP_STACK:+--keep-stack} $${RETAIN_DATA:+--retain-data}

verify-p2-01-openapi-two-node-e2e:
	env $${HOST_IP:+SURGEPILOT_E2E_HOST_IP=$${HOST_IP} SURGEPILOT_E2E_API_ORCHESTRATION_URL=$${SURGEPILOT_E2E_API_ORCHESTRATION_URL:-http://$${HOST_IP}:8000} SURGEPILOT_E2E_TARGET_URL=$${SURGEPILOT_E2E_TARGET_URL:-http://$${HOST_IP}:8000/api/healthz} SURGEPILOT_E2E_NODE_1_SSH_HOST=$${HOST_IP} SURGEPILOT_E2E_NODE_1_SSH_PORT=$${SURGEPILOT_SSH_E2E_PORT:-22322} SURGEPILOT_E2E_NODE_2_SSH_HOST=$${HOST_IP} SURGEPILOT_E2E_NODE_2_SSH_PORT=$${SURGEPILOT_SSH_E2E_2_PORT:-22323}} uv run --all-packages python scripts/verify_p2_01_openapi_two_node_e2e.py --build-app --build-ssh $${KEEP_STACK:+--keep-stack}

verify-p1-08-debug-http-trace-e2e:
	MINIO_ENDPOINT=$${MINIO_ENDPOINT:-http://127.0.0.1:19000} SURGEPILOT_E2E_API_PORT=$${SURGEPILOT_E2E_API_PORT:-18080} SURGEPILOT_E2E_WEB_PORT=$${SURGEPILOT_E2E_WEB_PORT:-15173} pnpm exec playwright test tests/e2e/p1_08_debug_http_trace.spec.ts --project=chrome

verify-runner-ssh:
	$(MAKE) _verify-runner-ssh SSH_E2E_BUILD=--build

verify-runner-ssh-fast:
	$(MAKE) _verify-runner-ssh

verify-p0-api-main-flow-e2e:
	env $${HOST_IP:+SURGEPILOT_E2E_HOST_IP=$${HOST_IP} SURGEPILOT_E2E_API_ORCHESTRATION_URL=$${SURGEPILOT_E2E_API_ORCHESTRATION_URL:-http://$${HOST_IP}:8000} SURGEPILOT_E2E_NODE_SSH_HOST=$${HOST_IP} SURGEPILOT_E2E_NODE_SSH_PORT=$${SURGEPILOT_SSH_E2E_PORT:-22322}} uv run --all-packages python scripts/verify_p0_api_main_flow_e2e.py --build-app --build-ssh $${KEEP_STACK:+--keep-stack} $${KEEP_DATA:+--keep-data}

verify-p0-api-main-flow-e2e-fast:
	env $${HOST_IP:+SURGEPILOT_E2E_HOST_IP=$${HOST_IP} SURGEPILOT_E2E_API_ORCHESTRATION_URL=$${SURGEPILOT_E2E_API_ORCHESTRATION_URL:-http://$${HOST_IP}:8000} SURGEPILOT_E2E_NODE_SSH_HOST=$${HOST_IP} SURGEPILOT_E2E_NODE_SSH_PORT=$${SURGEPILOT_SSH_E2E_PORT:-22322}} uv run --all-packages python scripts/verify_p0_api_main_flow_e2e.py --build-app $${KEEP_STACK:+--keep-stack} $${KEEP_DATA:+--keep-data}

verify-p0-06-runner-ssh:
	env $${HOST_IP:+SURGEPILOT_E2E_HOST_IP=$${HOST_IP} SURGEPILOT_E2E_API_ORCHESTRATION_URL=$${SURGEPILOT_E2E_API_ORCHESTRATION_URL:-http://$${HOST_IP}:8000} SURGEPILOT_E2E_NODE_SSH_HOST=$${HOST_IP} SURGEPILOT_E2E_NODE_SSH_PORT=$${SURGEPILOT_SSH_E2E_PORT:-22322}} uv run --all-packages python scripts/verify_p0_06_ssh_taurus_smoke.py --build-app --build-ssh $${KEEP_STACK:+--keep-stack} $${KEEP_DATA:+--keep-data}

verify-p0-06-runner-ssh-fast:
	env $${HOST_IP:+SURGEPILOT_E2E_HOST_IP=$${HOST_IP} SURGEPILOT_E2E_API_ORCHESTRATION_URL=$${SURGEPILOT_E2E_API_ORCHESTRATION_URL:-http://$${HOST_IP}:8000} SURGEPILOT_E2E_NODE_SSH_HOST=$${HOST_IP} SURGEPILOT_E2E_NODE_SSH_PORT=$${SURGEPILOT_SSH_E2E_PORT:-22322}} uv run --all-packages python scripts/verify_p0_06_ssh_taurus_smoke.py --build-app $${KEEP_STACK:+--keep-stack} $${KEEP_DATA:+--keep-data}

verify-p1-00-monitoring-compose:
	uv run --all-packages pytest tests/contract/test_p1_00_monitoring_compose.py -q
	uv run --all-packages python scripts/verify_p1_00_monitoring_compose.py

verify-p1-00-monitoring-ssh:
	@printf "P1-00 monitoring SSH smoke is supplemental; run with a monitoring-capable runtime artifact and Load Node profile.\n"
	$(MAKE) verify-p0-06-runner-ssh-fast

verify-p1-00-monitoring-remote-node-write:
	@if [ "$${SURGEPILOT_P1_MONITORING_REMOTE_WRITE:-}" != "1" ] || [ -z "$${SURGEPILOT_NODE_API_BASE_URL:-}" ] || [ -z "$${SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL:-}" ]; then \
		printf "P1-00 remote node write smoke skipped: set SURGEPILOT_P1_MONITORING_REMOTE_WRITE=1 with explicit final SURGEPILOT_NODE_API_BASE_URL and SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL values. Skipped is not release/nightly green evidence.\n"; \
		exit 77; \
	fi
	@printf "P1-00 remote node write smoke checks both final URLs from the Load Node and then verifies runId measurements in InfluxDB.\n"
	uv run --all-packages python scripts/verify_p1_00_monitoring_remote_node_write.py --build-app $${KEEP_STACK:+--keep-stack} $${KEEP_DATA:+--keep-data}

verify-p1-01-runner-ssh-two-node:
	env $${HOST_IP:+SURGEPILOT_E2E_HOST_IP=$${HOST_IP} SURGEPILOT_E2E_API_ORCHESTRATION_URL=$${SURGEPILOT_E2E_API_ORCHESTRATION_URL:-http://$${HOST_IP}:8000} SURGEPILOT_E2E_TARGET_URL=$${SURGEPILOT_E2E_TARGET_URL:-http://$${HOST_IP}:8000/api/healthz} SURGEPILOT_E2E_NODE_1_SSH_HOST=$${HOST_IP} SURGEPILOT_E2E_NODE_1_SSH_PORT=$${SURGEPILOT_SSH_E2E_PORT:-22322} SURGEPILOT_E2E_NODE_2_SSH_HOST=$${HOST_IP} SURGEPILOT_E2E_NODE_2_SSH_PORT=$${SURGEPILOT_SSH_E2E_2_PORT:-22323}} uv run --all-packages python scripts/verify_p1_01_ssh_two_node_smoke.py --build-app --build-ssh

verify-p1-01-runner-ssh-two-node-fast:
	env $${HOST_IP:+SURGEPILOT_E2E_HOST_IP=$${HOST_IP} SURGEPILOT_E2E_API_ORCHESTRATION_URL=$${SURGEPILOT_E2E_API_ORCHESTRATION_URL:-http://$${HOST_IP}:8000} SURGEPILOT_E2E_TARGET_URL=$${SURGEPILOT_E2E_TARGET_URL:-http://$${HOST_IP}:8000/api/healthz} SURGEPILOT_E2E_NODE_1_SSH_HOST=$${HOST_IP} SURGEPILOT_E2E_NODE_1_SSH_PORT=$${SURGEPILOT_SSH_E2E_PORT:-22322} SURGEPILOT_E2E_NODE_2_SSH_HOST=$${HOST_IP} SURGEPILOT_E2E_NODE_2_SSH_PORT=$${SURGEPILOT_SSH_E2E_2_PORT:-22323}} uv run --all-packages python scripts/verify_p1_01_ssh_two_node_smoke.py --build-app

_verify-runner-ssh:
	uv run --all-packages python scripts/run_runtime_builder.py --output-dir "$(RUNNER_SSH_RUNTIME_ARTIFACT_DIR)" --build-dir "$(RUNNER_SSH_RUNTIME_BUILD_DIR)" --cache-dir "$(RUNNER_SSH_RUNTIME_CACHE_DIR)" --env-file "$(RUNNER_SSH_RUNTIME_ENV_FILE)" --fixed-version "$(RUNNER_SSH_RUNTIME_VERSION)"
	$(VERIFY_COMPOSE_ENV) $(COMPOSE_SSH_E2E) up -d $(SSH_E2E_BUILD) --wait ssh-load-node ssh-load-node-2
	@status=0; \
	SURGEPILOT_SSH_E2E=1 \
	SURGEPILOT_SSH_E2E_HOST=127.0.0.1 \
	SURGEPILOT_SSH_E2E_PORT=$${SURGEPILOT_SSH_E2E_PORT:-22322} \
	SURGEPILOT_SSH_E2E_2_PORT=$${SURGEPILOT_SSH_E2E_2_PORT:-22323} \
	SURGEPILOT_SSH_E2E_USER=surgepilot \
	SURGEPILOT_SSH_E2E_PASSWORD=surgepilot \
	LOAD_NODE_RUNTIME_ARTIFACT_DIR="$(RUNNER_SSH_RUNTIME_ARTIFACT_DIR)" \
	LOAD_NODE_RUNTIME_VERSION="$(RUNNER_SSH_RUNTIME_VERSION)" \
	uv run --all-packages pytest \
		apps/api/tests/test_p0_03_initializer_ssh_e2e.py \
		apps/api/tests/test_p0_04_runner_ssh_e2e.py \
		apps/api/tests/test_p1_01_runner_ssh_two_node_e2e.py \
		-q || status=$$?; \
	$(VERIFY_COMPOSE_ENV) $(COMPOSE_SSH_E2E) down -v; \
	exit $$status

endif
