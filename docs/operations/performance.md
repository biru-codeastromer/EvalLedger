# Performance Verification

This runbook covers EvalLedger's query hardening and load-test workflow. It is designed for local development, staging, and small controlled checks against the live Render deployment.

---

## What was optimized

The current backend hot paths were hardened in three ways:

1. **Search and registry summaries now paginate in SQL**
   - `GET /search`
   - `GET /benchmarks`
   - contamination filters and total counts now happen in the database instead of loading every match into Python

2. **Latest-version summary fields no longer require loading full version collections**
   - registry cards
   - benchmark detail summaries
   - admin review queue cards

3. **Reviewer/account activity paths load less ORM state**
   - `GET /admin/review-queue`
   - `GET /admin/benchmarks/{slug}/context`
   - `GET /admin/audit-events`
   - `GET /auth/me`
   - benchmark/version activity feeds

Supporting indexes were added for:
- latest-version lookups by benchmark
- review queue ordering by verification state
- account benchmark ordering by submitter/update time
- audit-event filtering by benchmark slug
- API key listing by user

---

## Important limitation: Render free-tier cold starts

Render free tier can sleep after inactivity. When that happens:
- the first request can take **30–60 seconds**
- this is **not** a query regression
- a single cold request can make a remote load test look much worse than the hot path really is

When testing performance, separate:
- **cold-start latency**: platform/runtime wake-up
- **hot-path latency**: actual application/query performance after warmup

Always use warmup requests before judging the results.

---

## Recommended commands

### Local browse scenario

```bash
make loadtest API_URL=http://localhost:8000
```

Exercises:
- `/health/live`
- `/stats/overview`
- `/stats/recent`
- `/search?q=mmlu`
- `/benchmarks/mmlu`
- `/benchmarks/mmlu/versions`
- `/benchmarks/mmlu/0.0.0`

### Authenticated account scenario

```bash
make loadtest-account API_URL=http://localhost:8000 API_KEY=<user-api-key>
```

Exercises:
- `/auth/me`

### Admin review scenario

```bash
make loadtest-review API_URL=http://localhost:8000 API_KEY=<admin-api-key>
```

Exercises:
- `/admin/stats`
- `/admin/review-queue?status=pending`
- `/admin/benchmarks/mmlu/context`

### Direct script usage

```bash
cd backend
uv run python -m app.scripts.loadtest \
  --scenario mixed \
  --api-url http://localhost:8000 \
  --api-key <api-key> \
  --requests 150 \
  --concurrency 12 \
  --warmup 20
```

### Machine-readable JSON output

```bash
cd backend
uv run python -m app.scripts.loadtest \
  --scenario browse \
  --api-url http://localhost:8000 \
  --requests 100 \
  --concurrency 10 \
  --json
```

---

## How to interpret the output

The harness prints:
- total requests / successes / failures
- throughput
- mean / p50 / p95 / p99 latency
- status-code summary
- per-endpoint summary

### Healthy local/staging signal

Good signs:
- no `5xx` responses
- no timeouts
- per-endpoint failure count is zero
- search and review endpoints are not drastically worse than benchmark detail reads

Warning signs:
- `search_mmlu` is consistently much slower than benchmark detail endpoints
- `admin_review_context` spikes much harder than the rest of the review scenario
- timeouts or `429`s appear during modest test sizes
- p95 grows disproportionately when concurrency is raised slightly

---

## Suggested verification workflow

### Before changing query-heavy code

1. Run:
   - `make loadtest API_URL=http://localhost:8000`
   - `make loadtest-account API_URL=http://localhost:8000 API_KEY=<key>`
   - `make loadtest-review API_URL=http://localhost:8000 API_KEY=<admin-key>`
2. Save the output for comparison.

### After query/index changes

1. Run the same three scenarios again.
2. Confirm:
   - no correctness regressions
   - no new failures
   - equal or better p95 on the touched scenario

### Before release

1. Run a warm local check.
2. Run one small remote check against the deployed API:

```bash
cd backend
uv run python -m app.scripts.loadtest \
  --scenario browse \
  --api-url https://evalledger-api.onrender.com \
  --requests 30 \
  --concurrency 3 \
  --warmup 3
```

Keep remote checks small and infrequent to avoid mistaking cold starts or rate limits for application regressions.

---

## Current query/index focus areas

These endpoints matter most in EvalLedger's current architecture:

| Area | Endpoints | Why it matters |
|---|---|---|
| Registry/search | `/search`, `/benchmarks`, `/benchmarks/{slug}` | Main public browsing path |
| Version detail | `/benchmarks/{slug}/versions`, `/benchmarks/{slug}/{version}` | Provenance and citation inspection |
| Account | `/auth/me` | Session/account/API key surface |
| Review | `/admin/review-queue`, `/admin/benchmarks/{slug}/context` | Trust and verification workflow |
| Activity | benchmark/version/admin audit endpoints | Reviewability and provenance traceability |

If performance work is needed later, start with those paths first.

---

## What this runbook does not solve

- Render free-tier cold starts
- lack of a background worker for contamination jobs
- network latency between you and the deployment region
- slow artifact downloads caused by local ephemeral storage or external object storage setup

Those are infrastructure or hosting constraints, not purely query-level issues.
