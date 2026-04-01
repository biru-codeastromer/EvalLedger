# Production Deployment

EvalLedger's production backend runs on **Render** with managed PostgreSQL, Redis, and Cloudflare R2 for object storage. The frontend is deployed separately on **Vercel**.

## Architecture

```
Vercel (Next.js frontend)
  |
  v  HTTPS
Render Web Service  (evalledger-api)  -- FastAPI / Uvicorn
  |           |
  v           v
PostgreSQL   Redis -------> Render Worker (evalledger-worker) -- Celery
  (Render)    (Render)
                              |
                              v
                        Cloudflare R2  (S3-compatible object storage)
```

## Render services

| Service | Type | Dockerfile | Notes |
|---------|------|------------|-------|
| `evalledger-api` | Web Service | `backend/Dockerfile` | Runs Alembic migrations on every deploy via the entrypoint script |
| `evalledger-worker` | Background Worker | `backend/Dockerfile` | Celery worker; skips migrations (`RUN_MIGRATIONS=false`) |
| `evalledger-db` | PostgreSQL 16 | managed | Starter plan |
| `evalledger-redis` | Redis 7 | managed | Starter plan |

## Required environment variables

### API and Worker (shared)

| Variable | Source | Example |
|----------|--------|---------|
| `APP_ENV` | static | `production` |
| `DATABASE_URL` | Render DB internal connection string | `postgres://...` (auto-rewritten by the app) |
| `SYNC_DATABASE_URL` | same as `DATABASE_URL` | `postgres://...` (auto-rewritten by the app) |
| `REDIS_URL` | Render Redis connection string | `redis://...` |
| `CELERY_BROKER_URL` | same as `REDIS_URL` | `redis://...` |
| `CELERY_RESULT_BACKEND` | same as `REDIS_URL` | `redis://...` |
| `JWT_SECRET_KEY` | generated once, shared | 64-char random string |
| `STORAGE_BACKEND` | static | `s3` |
| `STORAGE_BUCKET` | R2 bucket name | `evalledger-prod` |
| `STORAGE_S3_ENDPOINT_URL` | R2 S3 API endpoint | `https://<account>.r2.cloudflarestorage.com` |
| `STORAGE_S3_ACCESS_KEY_ID` | R2 API token | |
| `STORAGE_S3_SECRET_ACCESS_KEY` | R2 API token | |
| `STORAGE_S3_REGION` | R2 region | `auto` |

### API only

| Variable | Source | Example |
|----------|--------|---------|
| `APP_URL` | Render service URL | `https://evalledger-api.onrender.com` |
| `FRONTEND_URL` | Vercel deployment URL | `https://eval-ledger.vercel.app` |
| `CORS_ORIGINS` | JSON list | `["https://eval-ledger.vercel.app"]` |
| `STORAGE_S3_PRESIGN_ENDPOINT` | R2 public/presign endpoint | same as `STORAGE_S3_ENDPOINT_URL` |

### Worker only

| Variable | Source | Notes |
|----------|--------|-------|
| `RUN_MIGRATIONS` | static | Set to `false` so only the API service runs migrations |

### Vercel frontend

| Variable | Notes |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | Production API URL (e.g. `https://evalledger-api.onrender.com`) |
| `API_INTERNAL_URL` | Same as `NEXT_PUBLIC_API_URL` (Vercel has no internal network to Render) |

## Database URL rewriting

Render provides connection strings with the `postgres://` scheme. The app's `Settings._normalise_database_urls` validator automatically rewrites them:

- `DATABASE_URL`: `postgres://` -> `postgresql+asyncpg://`
- `SYNC_DATABASE_URL`: `postgres://` -> `postgresql+psycopg://`

You can set both `DATABASE_URL` and `SYNC_DATABASE_URL` to the same Render-provided connection string.

## Migrations

Migrations run automatically on every deploy of the API service via `bin/docker-entrypoint.sh`. To run manually:

```bash
# On Render Shell (evalledger-api service)
uv run alembic upgrade head
```

## Seeding

To load initial benchmark and corpus data in production:

```bash
# On Render Shell (evalledger-api service)
uv run python -m app.scripts.seed
```

## Deploying changes

1. Push to `main` (or merge a PR).
2. Render auto-deploys the API and worker services.
3. The API entrypoint runs migrations before starting Uvicorn.
4. Verify: `curl https://evalledger-api.onrender.com/health`

## Restart behaviour

Both the API and worker are configured with `restart: always` on Render. The API re-runs migrations on every restart (idempotent via Alembic's version tracking). The worker reconnects to Redis and PostgreSQL automatically via Celery's built-in retry logic.
