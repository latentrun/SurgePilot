.PHONY: help setup dev dev-web dev-api dev-runner generate-contracts contracts-stale-check lint test ai-skill-tests verify verify-p1-00-monitoring-compose

help:
	@printf "SurgePilot commands:\n"
	@printf "  make setup                  Install workspace dependencies\n"
	@printf "  make dev-web                Start the Vite web dev server\n"
	@printf "  make dev-api                Start the FastAPI dev server\n"
	@printf "  make dev-runner             Show Runner CLI help\n"
	@printf "  make generate-contracts     Export OpenAPI and generate Web client/types\n"
	@printf "  make contracts-stale-check  Check committed contracts are fresh\n"
	@printf "  make ai-skill-tests         Run the Public API AI skill tests\n"
	@printf "  make lint                   Run bootstrap lint and type checks\n"
	@printf "  make test                   Run bootstrap tests\n"
	@printf "  make verify                 Run the bootstrap verification gate\n"
	@printf "  make verify-p1-00-monitoring-compose  Start the full stack with Monitoring and check provisioning\n"

setup:
	pnpm install --frozen-lockfile
	uv sync --all-packages --all-groups --locked

dev:
	@printf "Run make dev-api and make dev-web in separate terminals.\n"

dev-web:
	pnpm --filter @surgepilot/web dev

dev-api:
	uv run --directory apps/api fastapi dev app/main.py

dev-runner:
	cd apps/runner && uv run python runner.py --help

generate-contracts:
	uv run --directory apps/api python ../../scripts/export_openapi.py
	pnpm --filter @surgepilot/contracts generate
	cp packages/contracts/openapi/public-api.openapi.json packages/ai-skills/surgepilot-public-api/references/public-api.openapi.json

contracts-stale-check:
	@set -eu; \
		tmp_dir=$$(mktemp -d); \
		trap 'rm -rf "$$tmp_dir"' EXIT; \
		cp -R packages/contracts/openapi "$$tmp_dir/openapi"; \
		cp -R packages/contracts/generated "$$tmp_dir/generated"; \
		cp packages/ai-skills/surgepilot-public-api/references/public-api.openapi.json "$$tmp_dir/public-api-skill.openapi.json"; \
		$(MAKE) generate-contracts; \
		diff -ru "$$tmp_dir/openapi" packages/contracts/openapi; \
		diff -ru "$$tmp_dir/generated" packages/contracts/generated; \
		diff -u "$$tmp_dir/public-api-skill.openapi.json" packages/ai-skills/surgepilot-public-api/references/public-api.openapi.json

lint:
	uv run --all-packages ruff check apps tests scripts
	pnpm -r typecheck

test:
	uv run --all-packages pytest tests/contract -q

ai-skill-tests:
	uv run --all-packages pytest packages/ai-skills/surgepilot-public-api/tests -q --cov=packages/ai-skills/surgepilot-public-api/scripts --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=90

verify: lint test contracts-stale-check

verify-p1-00-monitoring-compose:
	uv run python scripts/verify_p1_00_monitoring_compose.py
