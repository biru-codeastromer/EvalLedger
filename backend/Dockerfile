# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: builder -- build the synced virtualenv at /app/.venv
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Build toolchain + Postgres dev headers needed to compile any wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      libpq-dev \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# Only dependency metadata is needed to resolve and build the venv.
# README.md is referenced by pyproject.toml (readme = "README.md").
COPY pyproject.toml uv.lock README.md /app/

# Build /app/.venv from the locked, dev-free dependency set. The project
# package itself ("app") is installed from source in the final stage via the
# bind-mounted / copied source tree, so we skip installing it here.
RUN uv sync --no-dev --frozen --no-install-project

# ---------------------------------------------------------------------------
# Stage 2: final -- slim runtime image with the baked venv + app source
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_SYNC=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Runtime-only system libs: libpq5 for Postgres client, curl for HEALTHCHECK.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpq5 \
      curl \
  && rm -rf /var/lib/apt/lists/*

# uv must stay installed: docker-compose and the entrypoint invoke `uv run`.
RUN pip install --no-cache-dir uv

# Non-root runtime user.
RUN groupadd --gid 10001 appuser \
  && useradd --uid 10001 --gid 10001 --create-home appuser

WORKDIR /app

# Bring in the prebuilt virtualenv from the builder stage.
COPY --from=builder /app/.venv /app/.venv

# Application source.
COPY . /app

# Ensure the entrypoint is executable and the runtime user owns the tree.
RUN chmod +x bin/docker-entrypoint.sh \
  && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Liveness probe: /health/live always returns 200 when the app is up.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:8000/health/live || exit 1

ENTRYPOINT ["bin/docker-entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
