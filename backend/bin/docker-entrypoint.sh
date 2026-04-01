#!/usr/bin/env bash
set -euo pipefail

# Run Alembic migrations before starting the API server.
# Skipped for worker processes (they share the same DB but should not race on migrations).
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Running Alembic migrations ..."
  uv run alembic upgrade head
  echo "Migrations complete."
fi

exec "$@"
