# Production Deployment

EvalLedger's production backend runs on **Fly.io** with Fly Managed Postgres, Upstash Redis, and Tigris S3-compatible object storage. The frontend is deployed separately on **Vercel**.

## Architecture

```
Vercel (Next.js frontend)
  |
  v  HTTPS
Fly.io – evalledger (web process)   FastAPI / Uvicorn
  |             |
  v             v
Fly Postgres   Upstash Redis ──────> Fly.io – evalledger (worker process)   Celery
                                         |
                                         v
                                   Tigris (S3-compatible object storage)
```

The `web` and `worker` processes run from the **same Docker image** inside a single Fly app (`evalledger`), differentiated by Fly process groups. Each process group can be scaled independently.

---

## Prerequisites

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Log in
fly auth login
```

---

## First-time provisioning

All commands are run from the **repository root** unless otherwise noted.

### 1. Create the Fly app

```bash
fly apps create evalledger --org personal
```

### 2. Provision Fly Managed Postgres

```bash
fly postgres create \
  --name evalledger-db \
  --region iad \
  --vm-size shared-cpu-1x \
  --volume-size 10 \
  --initial-cluster-size 1

# Attach injects DATABASE_URL into the evalledger app as a secret.
fly postgres attach --app evalledger evalledger-db
```

`fly postgres attach` sets `DATABASE_URL` to a `postgres://` connection string.
`Settings._normalise_database_urls` rewrites it automatically to:
- `DATABASE_URL` → `postgresql+asyncpg://…` (async engine)
- `SYNC_DATABASE_URL` → derived automatically if not set (psycopg, used by Alembic)

If you need to override `SYNC_DATABASE_URL` explicitly:

```bash
# Grab the raw postgres:// URL that was just injected:
RAW_DB_URL=$(fly secrets list --app evalledger -j | jq -r '.[] | select(.Name=="DATABASE_URL") | .Digest')
# Then set it (paste the actual value, not the digest):
fly secrets set SYNC_DATABASE_URL="postgres://…" --app evalledger
```

### 3. Provision Upstash Redis

```bash
fly ext upstash redis create \
  --name evalledger-redis \
  --region iad \
  --plan free

# Wire up the Redis URL (Upstash prints the redis:// URL after creation):
fly secrets set \
  REDIS_URL="redis://…" \
  CELERY_BROKER_URL="redis://…" \
  CELERY_RESULT_BACKEND="redis://…" \
  --app evalledger
```

> Upstash Redis URLs start with `rediss://` (TLS). Use the same URL for all three variables.

### 4. Provision Tigris object storage

```bash
fly storage create --name evalledger-storage --app evalledger
```

Tigris injects `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3`, and `BUCKET_NAME` automatically. Map them to the names EvalLedger expects:

```bash
# After `fly storage create` prints the credentials, set them:
fly secrets set \
  STORAGE_BUCKET="<BUCKET_NAME from Tigris>" \
  STORAGE_S3_ENDPOINT_URL="<AWS_ENDPOINT_URL_S3 from Tigris>" \
  STORAGE_S3_ACCESS_KEY_ID="<AWS_ACCESS_KEY_ID from Tigris>" \
  STORAGE_S3_SECRET_ACCESS_KEY="<AWS_SECRET_ACCESS_KEY from Tigris>" \
  --app evalledger
```

### 5. Set remaining secrets

```bash
fly secrets set \
  APP_URL="https://evalledger.fly.dev" \
  FRONTEND_URL="https://eval-ledger.vercel.app" \
  CORS_ORIGINS='["https://eval-ledger.vercel.app"]' \
  JWT_SECRET_KEY="$(openssl rand -hex 32)" \
  --app evalledger
```

### 6. Deploy

```bash
# From the backend/ directory (where fly.toml lives):
cd backend
fly deploy --app evalledger
```

Fly will:
1. Build the Docker image.
2. Run `uv run alembic upgrade head` in a release VM (migrations).
3. Roll out new `web` and `worker` machines.
4. Wait for `/health/live` to return 200 before shifting traffic.

### 7. Verify

```bash
curl https://evalledger.fly.dev/health
fly logs --app evalledger
fly status --app evalledger
```

### 8. Seed initial data (optional)

```bash
fly ssh console --app evalledger --command "uv run python -m app.scripts.seed"
```

---

## Required environment variables

### Secrets (`fly secrets set`)

| Variable | Description |
|---|---|
| `DATABASE_URL` | Injected by `fly postgres attach`; `postgres://…` is auto-rewritten |
| `SYNC_DATABASE_URL` | Auto-derived from `DATABASE_URL`; set explicitly only if needed |
| `REDIS_URL` | Upstash Redis URL (`rediss://…`) |
| `CELERY_BROKER_URL` | Same as `REDIS_URL` |
| `CELERY_RESULT_BACKEND` | Same as `REDIS_URL` |
| `JWT_SECRET_KEY` | 64-char random string; generate with `openssl rand -hex 32` |
| `APP_URL` | Public Fly.io API URL, e.g. `https://evalledger.fly.dev` |
| `FRONTEND_URL` | Vercel deployment URL, e.g. `https://eval-ledger.vercel.app` |
| `CORS_ORIGINS` | JSON array, e.g. `["https://eval-ledger.vercel.app"]` |
| `STORAGE_BUCKET` | Tigris bucket name |
| `STORAGE_S3_ENDPOINT_URL` | Tigris S3 endpoint URL |
| `STORAGE_S3_ACCESS_KEY_ID` | Tigris access key |
| `STORAGE_S3_SECRET_ACCESS_KEY` | Tigris secret key |

### Non-secret env vars (in `fly.toml [env]`)

| Variable | Value | Notes |
|---|---|---|
| `APP_ENV` | `production` | |
| `RUN_MIGRATIONS` | `false` | Migrations run via release command, not in-process |
| `STORAGE_BACKEND` | `s3` | |
| `STORAGE_S3_REGION` | `auto` | Tigris default; override if needed |

### Vercel frontend

Set these in the Vercel project dashboard under **Settings → Environment Variables**:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://evalledger.fly.dev` |
| `API_INTERNAL_URL` | `https://evalledger.fly.dev` |

---

## Database URL normalisation

`Settings._normalise_database_urls` (in `backend/app/config.py`) rewrites bare connection strings automatically:

- `DATABASE_URL`: `postgres://` → `postgresql+asyncpg://`
- `SYNC_DATABASE_URL`: `postgres://` → `postgresql+psycopg://`; if unset, auto-derived from `DATABASE_URL`

You can pass the raw Fly/Postgres `postgres://` URL for both variables and the app handles driver selection.

---

## Migrations

Alembic migrations run as a Fly **release command** before any new machine is started:

```toml
# backend/fly.toml
[deploy]
  release_command = "uv run alembic upgrade head"
```

If migrations fail the deploy is automatically rolled back. To run migrations manually:

```bash
fly ssh console --app evalledger --command "uv run alembic upgrade head"
```

The `web` process entrypoint (`bin/docker-entrypoint.sh`) also checks `RUN_MIGRATIONS`, which is set to `false` in `fly.toml` so migrations never run in-process.

---

## Scaling

```bash
# Scale web machines (adds horizontal replicas):
fly scale count web=2 --app evalledger

# Scale worker machines:
fly scale count worker=2 --app evalledger

# Resize VM memory:
fly scale memory 1024 --app evalledger --process-group web
```

---

## Deploying changes

1. Push to `main` (or merge a PR).
2. Run `fly deploy --app evalledger` from `backend/`.
3. Fly runs migrations → rolls out new machines → health-checks pass.
4. Verify: `curl https://evalledger.fly.dev/health`

CI can automate this with a GitHub Actions step that calls `flyctl deploy` using a `FLY_API_TOKEN` secret.

---

## Observability

```bash
fly logs --app evalledger                  # tail all logs
fly logs --app evalledger -i <machine-id>  # single machine
fly status --app evalledger                # machine health summary
fly ssh console --app evalledger           # interactive shell on web machine
```

---

## What was removed / replaced from the previous Render setup

| Item | Action | Notes |
|---|---|---|
| `render.yaml` | Removed | Replaced by `backend/fly.toml` |
| Render PostgreSQL | Replaced | Fly Managed Postgres (`evalledger-db`) |
| Render Redis | Replaced | Upstash Redis via Fly extension |
| Cloudflare R2 (Render-specific config) | Replaced | Tigris via Fly extension; same S3 API, different credentials |
| `APP_URL sync: false` workaround | Removed | Fly supplies `APP_URL` as a plain secret |
| Render auto-deploy on push | Replaced | `fly deploy` in CI or manual |
| `docker-entrypoint.sh` migration logic | Kept (unchanged) | `RUN_MIGRATIONS` env var still respected; release command takes precedence |
| `Settings._normalise_database_urls` | Extended | Now auto-derives `SYNC_DATABASE_URL` when not set |
