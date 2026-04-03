# Production Deployment

EvalLedger's production backend runs as an **API-only deployment** on **Render free tier** with managed PostgreSQL and Redis. The frontend is deployed separately on **Vercel**.

> **Alternative:** A Fly.io deployment configuration is available in `backend/fly.toml` for deployments that need a Celery worker (contamination checks) and persistent object storage. See [Fly.io alternative](#flyio-alternative) at the bottom.

## Architecture

```
Vercel (Next.js frontend)
  |
  v  HTTPS
Render Web Service (evalledger-api)  ── FastAPI / Uvicorn
  |
  v
PostgreSQL (Render, free)     Redis (Render, free)
```

### What is deployed

| Component | Status | Notes |
|---|---|---|
| FastAPI API | ✅ Live | `https://evalledger-api.onrender.com` |
| PostgreSQL 16 | ✅ Live | Render managed, free tier (256 MB, expires after 90 days) |
| Redis | ✅ Live | Render managed, free tier (25 MB, expires after 90 days) |
| Celery worker | ❌ Not deployed | Render free tier does not support background workers |
| S3 object storage | ❌ Not configured | Local filesystem storage (ephemeral across redeploys) |

### What this means in practice

- **Registry browsing, search, benchmark creation, version submission** — all work normally.
- **Contamination checks** — disabled. The API returns `status: "unavailable"` instead of queueing jobs that would never process. New benchmark versions are created with `contamination_status: "unchecked"`.
- **Artifact storage** — uses the local filesystem. Uploaded artifacts are **lost on every redeploy**. Download URLs for previously uploaded versions will 404 after a redeploy.
- **Cold starts** — free instances spin down after 15 minutes of inactivity. The first request after spin-down takes 30–60 seconds.
- **90-day expiry** — free PostgreSQL and Redis instances expire after 90 days and must be recreated.

---

## Quick start: deploy via Render Blueprint

### 1. Create a Render account

Go to [https://render.com](https://render.com) and sign up.

### 2. Deploy via Blueprint

1. Go to [https://render.com/deploy](https://render.com/deploy)
2. Paste the repo URL: `https://github.com/biru-codeastromer/EvalLedger`
3. Click **New Blueprint Instance**
4. Render will detect `render.yaml` and show the services to create:
   - `evalledger-api` (Web Service, free)
   - `evalledger-db` (PostgreSQL 16, free)
   - `evalledger-redis` (Redis, free)
5. Click **Apply**

### 3. Set `APP_URL`

After deployment, go to `evalledger-api` → **Environment** → set `APP_URL` to the assigned URL (e.g. `https://evalledger-api.onrender.com`).

### 4. Configure OAuth providers

Authentication uses **GitHub OAuth** and **Google OAuth** exclusively. Set up both providers and add their credentials to the Render environment.

#### GitHub OAuth App

1. Go to **https://github.com/settings/developers** → OAuth Apps → **New OAuth App**
2. Fill in:
   - **Homepage URL**: `https://evalledger-frontend.vercel.app`
   - **Authorization callback URL**: `https://evalledger-api.onrender.com/auth/oauth/github/callback`
3. Click **Register application** → copy **Client ID** → generate and copy **Client Secret**
4. In Render → `evalledger-api` → **Environment**, set:
   - `GITHUB_CLIENT_ID` = the client ID
   - `GITHUB_CLIENT_SECRET` = the client secret

#### Google OAuth App

1. Go to **https://console.cloud.google.com/apis/credentials** (create a new project, e.g. `evalledger`)
2. Configure the **OAuth consent screen** (Google Auth Platform → Branding, Audience)
3. Go to **Clients** → **Create client** → **Web application**
   - **Authorized redirect URI**: `https://evalledger-api.onrender.com/auth/oauth/google/callback`
4. Copy **Client ID** and **Client Secret**
5. In Render → `evalledger-api` → **Environment**, set:
   - `GOOGLE_CLIENT_ID` = the client ID
   - `GOOGLE_CLIENT_SECRET` = the client secret

> **Note:** The Google app starts in "Testing" status. Only test users added in the Audience page can sign in. This is fine for a small team. To open it to all Google users, submit for verification.

### 5. Verify

```bash
curl https://evalledger-api.onrender.com/health/live
curl https://evalledger-api.onrender.com/health
```

### 6. Seed initial data

In the Render dashboard → `evalledger-api` → **Shell**:

```bash
uv run python -m app.scripts.seed
```

### 7. Wire the Vercel frontend

In the Vercel project → **Settings → Environment Variables**:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://evalledger-api.onrender.com` |
| `API_INTERNAL_URL` | `https://evalledger-api.onrender.com` |

Then redeploy the frontend from the Vercel Deployments tab.

---

## Required environment variables

### Render (configured in render.yaml)

| Variable | Source | Notes |
|---|---|---|
| `APP_ENV` | static | `production` |
| `DATABASE_URL` | Render DB | `postgres://…` (auto-rewritten by the app) |
| `REDIS_URL` | Render Redis | `redis://…` |
| `CELERY_BROKER_URL` | Render Redis | Same as `REDIS_URL` (kept for code compatibility) |
| `CELERY_RESULT_BACKEND` | Render Redis | Same as `REDIS_URL` |
| `JWT_SECRET_KEY` | auto-generated | |
| `CORS_ORIGINS` | static | `["https://evalledger-frontend.vercel.app"]` |
| `STORAGE_BACKEND` | static | `local` |
| `WORKER_ENABLED` | static | `false` — no Celery worker is deployed |
| `APP_URL` | manual | Set after deploy (e.g. `https://evalledger-api.onrender.com`) |
| `FRONTEND_URL` | static | `https://evalledger-frontend.vercel.app` |
| `GITHUB_CLIENT_ID` | manual | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | manual | GitHub OAuth App client secret |
| `GOOGLE_CLIENT_ID` | manual | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | manual | Google OAuth client secret |

### Vercel

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://evalledger-api.onrender.com` |
| `API_INTERNAL_URL` | `https://evalledger-api.onrender.com` |

---

## Contamination processing (disabled)

The `WORKER_ENABLED` setting (default: `false`) controls whether contamination jobs are dispatched.

When `WORKER_ENABLED=false`:
- `POST /contamination/check` returns `{ "status": "unavailable", "message": "..." }` immediately, without uploading or queueing.
- `GET /contamination/jobs/{id}` returns `{ "status": "unavailable" }`.
- Version creation sets `contamination_status: "unchecked"` and returns an empty `contamination_job_ids` list.
- The frontend contamination page shows a clear message explaining the limitation.

To enable contamination processing, deploy a Celery worker and set `WORKER_ENABLED=true`. This requires a paid Render plan or an alternative platform (see Fly.io alternative below).

---

## Storage (ephemeral)

On Render free tier with `STORAGE_BACKEND=local`:
- Artifacts are stored in `/app/storage/` inside the container.
- **This storage is ephemeral.** Files are lost on every redeploy or container restart.
- Download endpoints will return 404 for artifacts that existed before the last deploy.
- To enable durable storage, configure S3-compatible object storage (e.g. Cloudflare R2) and set `STORAGE_BACKEND=s3` with the appropriate credentials.

---

## Database URL normalisation

`Settings._normalise_database_urls` rewrites bare connection strings automatically:

- `DATABASE_URL`: `postgres://` → `postgresql+asyncpg://`
- `SYNC_DATABASE_URL`: auto-derived from `DATABASE_URL` if empty

---

## Migrations

Migrations run automatically on every deploy via `bin/docker-entrypoint.sh`.

To run manually via Render Shell:
```bash
uv run alembic upgrade head
```

---

## Deploying changes

1. Push to `main`.
2. Render auto-deploys the API service.
3. The entrypoint runs migrations before starting Uvicorn.
4. Verify: `curl https://evalledger-api.onrender.com/health`

---

## Fly.io alternative

A complete Fly.io configuration is in `backend/fly.toml`. It supports:
- Process groups (`web` + `worker`) for running the Celery worker
- Fly Managed Postgres
- Upstash Redis via Fly extension
- Tigris S3-compatible storage via Fly extension
- Alembic migrations via Fly release command

Fly.io requires a credit card (even for free-tier usage).

To use: install `flyctl`, create the app, provision services, set secrets, deploy. See `backend/fly.toml` comments for details.
