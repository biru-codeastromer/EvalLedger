SHELL := /bin/zsh

# Configurable via environment or make arguments
API_URL ?= http://localhost:8000
API_KEY  ?=
OUTPUT   ?= backup-$(shell date +%Y%m%d-%H%M%S).sql
FORMAT   ?= plain

.PHONY: dev migrate seed test lint loadtest verify \
        check-restore check-artifacts db-backup db-backup-print

dev:
	docker compose up --build

migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run python -m app.scripts.seed

test:
	cd backend && uv run pytest
	cd cli && uv run pytest
	cd frontend && pnpm test && pnpm test:e2e

lint:
	cd backend && uv run ruff check . && uv run mypy app
	cd cli && uv run ruff check . && uv run mypy evalledger
	cd frontend && pnpm lint && pnpm typecheck

loadtest:
	cd backend && uv run python -m app.scripts.loadtest --url http://localhost:8000/health/live --requests 200 --concurrency 20

verify: lint test
	cd frontend && pnpm build

# ---------------------------------------------------------------------------
# Recovery and verification targets
# ---------------------------------------------------------------------------

## Post-restore verification — runs HTTP checks against a live API instance.
## Usage:
##   make check-restore                            # local server
##   make check-restore API_URL=https://...        # remote instance
##   make check-restore API_URL=https://... API_KEY=<key>  # with admin checks
check-restore:
	cd backend && uv run python -m app.scripts.check_restore \
		--api-url $(API_URL) \
		$(if $(API_KEY),--api-key $(API_KEY),)

## Artifact reconciliation — verifies every DB artifact reference exists in storage.
## Uses STORAGE_BACKEND, DATABASE_URL, and S3 env vars from the environment.
check-artifacts:
	cd backend && uv run python -m app.scripts.check_artifacts

## Database backup via pg_dump wrapper.
## Usage:
##   make db-backup                                # dump to timestamped .sql file
##   make db-backup OUTPUT=backup.dump FORMAT=custom
db-backup:
	cd backend && uv run python -m app.scripts.db_backup \
		--output $(OUTPUT) \
		--format $(FORMAT)

## Print the pg_dump command without running it (dry-run).
db-backup-print:
	cd backend && uv run python -m app.scripts.db_backup --print
