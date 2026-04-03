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
| S3 object storage | ⚠️ Optional | Defaults to ephemeral local filesystem; configure Cloudflare R2 for durability |

### What this means in practice

- **Registry browsing, search, benchmark creation, version submission** — all work normally.
- **Contamination checks** — disabled. The API returns `status: "unavailable"` instead of queueing jobs that would never process. New benchmark versions are created with `contamination_status: "unchecked"`.
- **Artifact storage** — defaults to the local filesystem (`STORAGE_BACKEND=local`). Uploaded artifacts are **lost on every redeploy**. Configure Cloudflare R2 for durable storage — see [Durable artifact storage (Cloudflare R2)](#durable-artifact-storage-cloudflare-r2) below.
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
| `STORAGE_BACKEND` | static | `local` (default). Change to `s3` after configuring R2 |
| `STORAGE_BUCKET` | static | `evalledger-artifacts` (your R2 bucket name) |
| `STORAGE_S3_ENDPOINT_URL` | manual | R2 jurisdiction endpoint — only required when `STORAGE_BACKEND=s3` |
| `STORAGE_S3_ACCESS_KEY_ID` | manual | R2 API token access key — only required when `STORAGE_BACKEND=s3` |
| `STORAGE_S3_SECRET_ACCESS_KEY` | manual | R2 API token secret key — only required when `STORAGE_BACKEND=s3` |
| `STORAGE_S3_PRESIGN_ENDPOINT` | manual | R2 public domain for presigned URLs — only required when `STORAGE_BACKEND=s3` |
| `STORAGE_S3_REGION` | optional | `auto` for R2; region string for AWS S3 |
| `STORAGE_S3_PRESIGN_TTL` | optional | Presigned URL TTL in seconds (default `3600`) |
| `WORKER_ENABLED` | static | `false` — no Celery worker is deployed |
| `APP_URL` | manual | Set after deploy (e.g. `https://evalledger-api.onrender.com`) |
| `FRONTEND_URL` | static | `https://evalledger-frontend.vercel.app` |
| `GITHUB_CLIENT_ID` | manual | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | manual | GitHub OAuth App client secret |
| `GOOGLE_CLIENT_ID` | manual | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | manual | Google OAuth client secret |
| `RATE_LIMIT_ENABLED` | static | `true` — set to `false` only in test/staging environments |
| `LOG_LEVEL` | optional | `INFO` (default). Set to `DEBUG` for verbose local dev; never use `DEBUG` in production |
| `LOG_HEALTH_REQUESTS` | optional | `false` (default). Set to `true` only when debugging liveness probe failures |

### Vercel

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://evalledger-api.onrender.com` |
| `API_INTERNAL_URL` | `https://evalledger-api.onrender.com` |

---

## Observability

### Log format

All log lines are emitted as JSON to stdout. Render's log dashboard displays them inline; the raw stream can be tailed with `render logs --tail`.

Every record includes the standard JSON fields emitted by `pythonjsonlogger`:

| Field | Notes |
|---|---|
| `asctime` | ISO-8601 timestamp |
| `levelname` | `INFO` / `WARNING` / `ERROR` |
| `name` | Logger name (e.g. `evalledger.auth`) |
| `message` | Event name (e.g. `request.completed`) |

Structured fields are appended as additional top-level keys depending on the event. Key fields:

| Field | Present on |
|---|---|
| `request_id` | Every request, most error events |
| `method` + `path` | `request.completed`, error handlers |
| `status_code` | `request.completed`, error handlers |
| `duration_ms` | `request.completed` |
| `client_ip` | `request.completed` (X-Forwarded-For or direct) |
| `user_id` | Auth events, API key events, OAuth logins, version/benchmark creation |
| `benchmark_slug` | Benchmark and version creation |
| `version` + `artifact_sha256` | Version creation |
| `provider` | OAuth events |
| `error_code` | AppError events |
| `bucket` + `client_id` | Rate-limit throttle events |

### Event catalogue

| Event | Logger | Level | Meaning |
|---|---|---|---|
| `app.startup` | `evalledger` | INFO | Application started; includes `app_env`, `git_commit`, feature flags |
| `app.shutdown` | `evalledger` | INFO | Application stopping cleanly |
| `app.startup_storage_failed` | `evalledger` | ERROR | Storage backend not reachable at startup |
| `ratelimit.redis_connected` | `evalledger` | INFO | Redis connected for rate limiting |
| `ratelimit.redis_unavailable` | `evalledger` | WARNING | Redis unreachable; rate limiting in fail-open mode |
| `ratelimit.throttled` | `evalledger.ratelimit` | WARNING | A client exceeded a rate-limit bucket |
| `ratelimit.request_throttled` | `evalledger.errors` | WARNING | 429 AppError surfaced to the client |
| `request.completed` | `evalledger` | INFO | Every HTTP request (except `/health/live` when filtered) |
| `request.unhandled_exception` | `evalledger.errors` | ERROR | Uncaught exception (with stack trace) |
| `app_error.server_error` | `evalledger.errors` | ERROR | 5xx AppError |
| `app_error.auth_rejected` | `evalledger.errors` | WARNING | 401 / 403 AppError |
| `database.integrity_error` | `evalledger.errors` | WARNING | DB constraint violation |
| `http_error.server_error` | `evalledger.errors` | ERROR | 5xx HTTPException |
| `auth.api_key_invalid` | `evalledger.auth` | WARNING | API key not found or inactive |
| `auth.invalid_token` | `evalledger.auth` | WARNING | JWT decode failure |
| `auth.invalid_auth_header` | `evalledger.auth` | WARNING | Malformed Authorization header |
| `auth.user_not_found` | `evalledger.auth` | WARNING | JWT subject not in DB |
| `api_key.created` | `evalledger.auth` | INFO | User created an API key |
| `api_key.revoked` | `evalledger.auth` | INFO | User revoked an API key |
| `oauth.flow_start` | `evalledger.oauth` | INFO | User initiated OAuth login |
| `oauth.login_success` | `evalledger.oauth` | INFO | OAuth login completed; user created or linked |
| `oauth.callback_provider_error` | `evalledger.oauth` | WARNING | Provider returned an error param |
| `oauth.callback_missing_params` | `evalledger.oauth` | WARNING | Code or state absent from callback |
| `oauth.state_mismatch` | `evalledger.oauth` | WARNING | CSRF state token invalid or expired |
| `oauth.token_exchange_failed` | `evalledger.oauth` | WARNING | Provider token exchange returned no token |
| `oauth.profile_fetch_failed` | `evalledger.oauth` | WARNING | Provider profile API returned non-200 |
| `oauth.account_creation_failed` | `evalledger.oauth` | ERROR | DB error during find-or-create |
| `benchmark.created` | `evalledger.benchmarks` | INFO | New benchmark registered |
| `version.created` | `evalledger.versions` | INFO | New benchmark version submitted |
| `contamination.check_unavailable` | `evalledger.contamination` | INFO | Check requested but worker disabled |
| `upload.invalid_filename` | `evalledger.uploads` | WARNING | Bad or unsafe artifact filename |
| `upload.unsupported_extension` | `evalledger.uploads` | WARNING | File extension not allowed |
| `upload.empty_artifact` | `evalledger.uploads` | WARNING | Zero-byte upload rejected |
| `upload.artifact_too_large` | `evalledger.uploads` | WARNING | Upload exceeds size limit |
| `health.database_failed` | `evalledger` | ERROR | `GET /health` DB probe failed |
| `health.redis_failed` | `evalledger` | ERROR | `GET /health` Redis probe failed |
| `health.storage_failed` | `evalledger` | ERROR | `GET /health` storage probe failed |

### Health endpoints

| Endpoint | Purpose | Frequency |
|---|---|---|
| `GET /health/live` | Liveness — is the process running? Used by Render for autorestart. Logs suppressed by default (`LOG_HEALTH_REQUESTS=false`). | Every ~30 s |
| `GET /health` | Readiness — checks database, Redis, and storage. Returns `{"status":"ok"}` or `{"status":"degraded","checks":{...}}` with HTTP 200/503. Use this for manual triage, not for automated polling. | On-demand |

### Sensitive data policy

The following are **never** logged:
- Raw API keys or key prefixes (only the hashed client-id appears in rate-limit logs)
- OAuth access tokens or refresh tokens
- JWT token values
- Uploaded file contents
- `SECRET_KEY`, `CLIENT_SECRET`, or any credential env vars

### Log level configuration

| `LOG_LEVEL` | When to use |
|---|---|
| `INFO` | Production (default) |
| `WARNING` | Reduce noise if INFO volume is too high |
| `DEBUG` | Local development only — **never in production** |

---

## Rate limiting

EvalLedger enforces a **Redis-backed fixed-window rate limiter** on all public and write endpoints.

### How it works

- **Client identity** (most to least specific): hashed API key → hashed Bearer token → `X-Forwarded-For` first hop → direct IP.  Raw tokens are SHA-256 hashed before appearing in Redis keys.
- **Window**: 60 seconds (fixed, non-sliding).
- **Fail-open**: if Redis is unavailable, all requests are allowed and a `WARNING` is logged.  The API continues serving normally during Redis restarts.
- **Disabled globally** with `RATE_LIMIT_ENABLED=false` (useful in integration-test environments).

### Limits per bucket

| Bucket | Route(s) | Anon | Auth |
|---|---|---|---|
| `search` | `GET /search` | 60/min | 120/min |
| `stats` | `GET /stats/*` | 30/min | 60/min |
| `auth_me` | `GET /auth/me` | 30/min | 30/min |
| `auth_apikey_create` | `POST /auth/api-keys` | 10/min | 10/min |
| `auth_apikey_delete` | `DELETE /auth/api-keys/{id}` | 10/min | 10/min |
| `benchmark_create` | `POST /benchmarks` | 20/min | 20/min |
| `version_create` | `POST /benchmarks/{slug}/versions` | 10/min | 10/min |
| `contamination_check` | `POST /contamination/check` | 10/min | 20/min |
| `oauth_start_github` | `GET /auth/oauth/github` | 20/min | 20/min |
| `oauth_start_google` | `GET /auth/oauth/google` | 20/min | 20/min |
| `oauth_callback_github` | `GET /auth/oauth/github/callback` | 20/min | 20/min |
| `oauth_callback_google` | `GET /auth/oauth/google/callback` | 20/min | 20/min |

### Over-limit response

JSON endpoints respond with **HTTP 429** and a structured error body:

```json
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Too many requests — please slow down and retry shortly.",
    "details": { "retry_after": 42 }
  }
}
```

The response also includes a standard **`Retry-After: <seconds>`** header.

OAuth start **and** callback endpoints (browser redirect flow) respond with a **302 redirect** to `/login?error=Too+many+sign-in+attempts...` instead of JSON, so the browser flow is never broken mid-flight.

### Env vars

| Variable | Default | Notes |
|---|---|---|
| `RATE_LIMIT_ENABLED` | `true` | Set to `false` to disable globally |
| `REDIS_URL` | (Render managed) | Used for both Celery broker and rate limit counters |

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

## Storage

### Ephemeral local storage (default)

On Render free tier with `STORAGE_BACKEND=local` (the default):
- Artifacts are stored in `/app/storage/` inside the container.
- **This storage is ephemeral.** Files are lost on every redeploy or container restart.
- Download endpoints will return 404 for artifacts that existed before the last deploy.

To preserve artifacts across deploys, configure Cloudflare R2 as described below.

---

## Durable artifact storage (Cloudflare R2)

Cloudflare R2 is an S3-compatible object storage with a generous free tier (10 GB storage, 10 M class-A ops/month, 1 M class-B ops/month) and **no egress fees**. It is the recommended production storage backend for EvalLedger.

### 1. Create a Cloudflare account and enable R2

1. Go to [https://dash.cloudflare.com](https://dash.cloudflare.com) and sign up (or log in).
2. In the left sidebar, click **R2 Object Storage**.
3. If prompted, enable R2 (you may need to add a payment method for identity verification; you will not be charged within the free tier).

### 2. Create an R2 bucket

1. Click **Create bucket**.
2. Enter a bucket name, e.g. `evalledger-artifacts`.
3. Leave the default region (**Automatic**).
4. Click **Create bucket**.

### 3. Enable a public access domain

Presigned download URLs are rewritten to a public domain so browsers can fetch artifacts without the internal R2 endpoint leaking to clients.

**Option A — R2.dev subdomain (easiest):**
1. Open the bucket → **Settings** → **Public access**.
2. Under **R2.dev subdomain**, click **Allow access** → **Allow**.
3. Copy the generated subdomain, e.g. `https://pub-<hash>.r2.dev`.
4. Use this as `STORAGE_S3_PRESIGN_ENDPOINT`.

**Option B — Custom domain:**
1. Open the bucket → **Settings** → **Custom domains** → **Connect domain**.
2. Enter a domain you control (must be on the same Cloudflare account, e.g. `artifacts.yourdomain.com`).
3. Click **Connect** and follow the DNS instructions.
4. Use `https://artifacts.yourdomain.com` as `STORAGE_S3_PRESIGN_ENDPOINT`.

### 4. Configure CORS (required for browser uploads)

In the bucket → **Settings** → **CORS policy**, click **Add CORS rule** and paste:

```json
[
  {
    "AllowedOrigins": ["https://evalledger-frontend.vercel.app"],
    "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }
]
```

Replace `https://evalledger-frontend.vercel.app` with your actual frontend URL.

### 5. Create an R2 API token

1. Go to **R2** → **Manage R2 API tokens** (top right of the R2 overview page).
2. Click **Create API token**.
3. Give it a descriptive name, e.g. `evalledger-api`.
4. Under **Permissions**, select **Object Read & Write**.
5. Under **Specify bucket**, select your bucket (`evalledger-artifacts`).
6. Click **Create API token**.
7. Copy all three values shown — they are only displayed once:
   - **Access Key ID** → `STORAGE_S3_ACCESS_KEY_ID`
   - **Secret Access Key** → `STORAGE_S3_SECRET_ACCESS_KEY`
   - **Jurisdiction-specific endpoint** → `STORAGE_S3_ENDPOINT_URL`
     (looks like `https://<account-id>.r2.cloudflarestorage.com`)

### 6. Set the environment variables in Render

In the Render dashboard → `evalledger-api` → **Environment**, add or update:

| Variable | Value |
|---|---|
| `STORAGE_BACKEND` | `s3` |
| `STORAGE_BUCKET` | `evalledger-artifacts` (your bucket name) |
| `STORAGE_S3_ENDPOINT_URL` | `https://<account-id>.r2.cloudflarestorage.com` |
| `STORAGE_S3_ACCESS_KEY_ID` | from step 5 |
| `STORAGE_S3_SECRET_ACCESS_KEY` | from step 5 |
| `STORAGE_S3_PRESIGN_ENDPOINT` | `https://pub-<hash>.r2.dev` (from step 3) |
| `STORAGE_S3_REGION` | `auto` (R2-specific; omit for AWS S3) |
| `STORAGE_S3_PRESIGN_TTL` | `3600` (optional; default 1 hour) |

> **Security:** Never commit these values. Always set them via the Render dashboard or a secrets manager.

### 7. Trigger a redeploy

In Render → `evalledger-api` → **Manual deploy** → **Deploy latest commit**. The startup log will include:

```json
{"message": "app.startup", "storage_backend": "s3", ...}
```

If credentials are missing or incorrect, the startup will log `app.startup_storage_failed` and the `/health` endpoint will report `"storage": false`.

### Troubleshooting R2

| Symptom | Likely cause | Fix |
|---|---|---|
| `app.startup_storage_failed` at boot | Wrong endpoint URL or bucket name | Verify `STORAGE_S3_ENDPOINT_URL` and `STORAGE_BUCKET` |
| `403 Forbidden` from `head_bucket` | API token lacks permissions or wrong bucket scope | Re-create token with **Object Read & Write** scoped to the correct bucket |
| Presigned URLs return 403 | Wrong `STORAGE_S3_PRESIGN_ENDPOINT` or public access not enabled | Enable R2.dev subdomain or custom domain and update the env var |
| `STORAGE_BACKEND=s3 requires these env vars` at startup | One or more of the four required vars is blank | Check all four: endpoint URL, access key, secret key, presign endpoint |
| Download URLs expose internal R2 endpoint | `STORAGE_S3_PRESIGN_ENDPOINT` not set | Set this to your R2.dev subdomain or custom domain |

### Other S3-compatible providers

The storage layer works with any S3-compatible provider. Use the same environment variable pattern and substitute provider-specific values:

| Provider | `STORAGE_S3_ENDPOINT_URL` | `STORAGE_S3_REGION` | Notes |
|---|---|---|---|
| Cloudflare R2 | `https://<account-id>.r2.cloudflarestorage.com` | `auto` | No egress fees; recommended |
| AWS S3 | *(omit — boto3 uses the default)* | e.g. `us-east-1` | Standard AWS credentials |
| MinIO (local dev) | `http://localhost:9000` | `us-east-1` | Run via Docker; no cloud needed |
| Tigris (Fly.io) | Fly provides the URL | `auto` | See `backend/fly.toml` |

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
