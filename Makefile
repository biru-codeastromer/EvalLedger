SHELL := /bin/zsh

.PHONY: dev migrate seed test lint loadtest verify

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
