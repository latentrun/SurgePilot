.PHONY: help setup dev dev-web dev-api dev-runner generate-contracts contracts-stale-check lint test verify

help:
	@printf "SurgePilot commands:\n"
	@printf "  make setup                  Install workspace dependencies\n"
	@printf "  make dev-web                Start the Vite web dev server\n"
	@printf "  make dev-api                Start the FastAPI dev server\n"
	@printf "  make dev-runner             Show Runner CLI help\n"
	@printf "  make generate-contracts     Export OpenAPI and generate Web client/types\n"
	@printf "  make contracts-stale-check  Check committed contracts are fresh\n"
	@printf "  make lint                   Run bootstrap lint and type checks\n"
	@printf "  make test                   Run bootstrap tests\n"
	@printf "  make verify                 Run the bootstrap verification gate\n"

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

contracts-stale-check:
	@set -eu; \
		tmp_dir=$$(mktemp -d); \
		trap 'rm -rf "$$tmp_dir"' EXIT; \
		uv run --directory apps/api python ../../scripts/export_openapi.py --output "$$tmp_dir/api.openapi.json"; \
		pnpm --filter @surgepilot/contracts exec openapi-typescript \
			"$$tmp_dir/api.openapi.json" -o "$$tmp_dir/web-client.ts"; \
		diff -u packages/contracts/openapi/api.openapi.json "$$tmp_dir/api.openapi.json"; \
		diff -u packages/contracts/generated/web-client/index.ts "$$tmp_dir/web-client.ts"

lint:
	uv run --all-packages ruff check apps tests scripts
	pnpm -r typecheck

test:
	uv run --all-packages pytest tests/contract -q

verify: lint test contracts-stale-check
