# Incident Response Runbook

This document is the draft operating procedure for production incidents. It is implementation-ready, but it should still be aligned with the final company communication policy before launch.

## Severity levels

- `SEV-1`: Public outage, corrupted provenance data, or inaccessible benchmark artifacts.
- `SEV-2`: Major feature degradation, failed submissions, stalled contamination jobs, or widespread auth failures.
- `SEV-3`: Localized defects, partial admin-tool issues, or degraded non-critical workflows.

## First 15 minutes

1. Assign one incident owner.
2. Record the start time, observed symptoms, and user impact.
3. Confirm whether the issue is frontend-only, API-only, worker-only, or storage-related.
4. Freeze non-essential deploys until the incident is contained.
5. Capture request IDs, logs, and failing benchmark or version identifiers before retrying actions.

## System triage order

1. Check `/health/live` and `/health`.
2. Verify database reachability and migration state.
3. Verify Redis and Celery queue movement.
4. Verify artifact storage reads and writes.
5. Reproduce the failure through the web UI or CLI with a known request ID.

### Reading logs on Render

Open the Render dashboard → `evalledger-api` → **Logs**.  All lines are JSON. Useful search patterns:

| What to find | Search term |
|---|---|
| All errors | `"levelname": "ERROR"` |
| Unhandled exceptions with stack traces | `request.unhandled_exception` |
| Auth failures (invalid key / bad token) | `auth.api_key_invalid` or `auth.invalid_token` |
| OAuth login failures | `oauth.callback_provider_error` or `oauth.account_creation_failed` |
| Rate-limit hits | `ratelimit.throttled` |
| A specific request | the `request_id` value from the `X-Request-ID` response header |
| Benchmark or version creation | `benchmark.created` or `version.created` |
| Upload rejections | `upload.artifact_too_large` or `upload.unsupported_extension` |
| Infrastructure degradation at startup | `app.startup_storage_failed` |
| Health probe failures | `health.database_failed`, `health.redis_failed`, `health.storage_failed` |

To find all events for a single request, search for its `request_id` — every log line for that request carries it.

### Correlating a user-reported failure

1. Ask the user for the `X-Request-ID` value from their browser or CLI response.
2. Search Render logs for that value.
3. The sequence of log lines for that ID shows the full path: rate-limit check → auth → handler → response.

### Key structured fields

| Field | What it contains |
|---|---|
| `request_id` | Unique per-request ID; echoed in `X-Request-ID` response header |
| `user_id` | UUID of the authenticated user |
| `benchmark_slug` | Slug of the affected benchmark |
| `error_code` | Machine-readable error code (e.g. `invalid_api_key`) |
| `status_code` | HTTP status returned to the client |
| `duration_ms` | Server-side request duration |
| `git_commit` | Git commit SHA at deploy time (from `RENDER_GIT_COMMIT`) |

## Communication cadence

- `SEV-1`: update every 15 minutes.
- `SEV-2`: update every 30 minutes.
- `SEV-3`: update at milestone changes.

Each update should include:

- current impact
- suspected blast radius
- mitigation in progress
- next checkpoint time

## Containment tactics

- Disable new submissions if ingestion is corrupting records.
- Pause worker processing if contamination tasks are writing invalid status updates.
- Revert the most recent deploy if the failure is clearly release-linked.
- Switch to read-only messaging if writes cannot be trusted.

## Exit criteria

An incident is not closed until:

1. The user-facing path is healthy again.
2. Data correctness is verified for affected records.
3. Monitoring shows recovery, not just a single successful retry.
4. A short postmortem note exists with root cause, fix, and follow-up work.

## SLOs and on-call

These are the draft service-level objectives and on-call policy. Like the rest of this runbook, they are implementation-ready but should be confirmed against the final company policy before launch. They define what "healthy" means in measurable terms, so the severity levels and exit criteria above can be judged against numbers rather than intuition.

SLOs are scoped to the current single-region, single-replica deployment (see [disaster-recovery.md](./disaster-recovery.md) → "Blast radius"). They deliberately exclude Render free-tier cold starts, which are a platform wake-up cost, not an application regression — see [performance.md](./performance.md) → "Important limitation: Render free-tier cold starts". Latency targets are for the **hot path** (post-warmup); measure them with the load-test harness in performance.md.

### Service-level objectives

Two user-facing paths carry an explicit SLO:

- **Public read path** — anonymous browsing and provenance inspection: `/search`, `/benchmarks`, `/benchmarks/{slug}`, `/benchmarks/{slug}/versions`, `/benchmarks/{slug}/{version}`, `/stats/overview`, `/stats/recent`.
- **Submission path** — authenticated writes that create or update records: benchmark and version creation, and artifact upload.

| Path | Availability (30-day) | p95 latency (hot) | p99 latency (hot) | Error budget (30-day) |
|---|---|---|---|---|
| Public read path | 99.5% | 400 ms | 800 ms | ~3h 39m of downtime |
| Submission path | 99.0% | 1200 ms | 2500 ms | ~7h 18m of downtime |

Notes:

- **Availability** is the share of non-`5xx`, non-timeout responses on the path. A successful `4xx` (e.g. validation rejection, `401`) counts as available — it is correct behaviour, not an outage.
- **Latency** is the server-side `duration_ms` field (see "Key structured fields" above), excluding cold-start requests. The submission path is allowed a looser budget because it performs writes, validation, and storage I/O.
- **Error budget** is the inverse of the availability target. When the budget for a 30-day window is exhausted, freeze non-essential deploys (consistent with "First 15 minutes") and prioritise reliability work until the budget recovers.

### Alerting plan

Alerts map to the severity levels at the top of this runbook. Tune thresholds against the baselines captured in performance.md.

| Signal | Condition | Severity | Notify |
|---|---|---|---|
| Health-endpoint failure (liveness) | `GET /health/live` non-200 or unreachable for 2 consecutive minutes | `SEV-1` | Page on-call immediately |
| Health-endpoint failure (readiness) | `GET /health` returns 503 (a dependency check is false) for 5 consecutive minutes | `SEV-2` | Page on-call |
| Dependency-down log signal | `health.database_failed`, `health.redis_failed`, or `health.storage_failed` recurring | `SEV-2` | Page on-call |
| Error rate | `5xx` rate on any SLO path exceeds 2% over a 5-minute window | `SEV-2` | Page on-call |
| Error-budget burn | 30-day error budget for a path projected to exhaust early (fast burn) | `SEV-2`/`SEV-3` | Notify on-call channel |
| Latency (public read) | p95 `duration_ms` > 400 ms (or p99 > 800 ms) over 10 minutes, excluding cold starts | `SEV-3` | Notify on-call channel |
| Latency (submission) | p95 `duration_ms` > 1200 ms (or p99 > 2500 ms) over 10 minutes | `SEV-3` | Notify on-call channel |
| Auth/abuse anomaly | Sustained spike in `auth.api_key_invalid` / `auth.invalid_token` / `ratelimit.throttled` | `SEV-3` | Notify on-call channel |

The readiness endpoint is the primary dependency signal: `/health` returns 503 when Postgres, Redis, or storage is unhealthy, so alerting on it covers most dependency outages without a separate probe per data store.

### On-call and escalation policy (stub)

This is a stub to be finalised with the on-call rotation before launch.

- **Rotation:** one primary on-call engineer at a time, with a named secondary as backup. Define the rotation length (e.g. weekly) and handoff time when the rotation is staffed.
- **Acknowledgement targets:** `SEV-1` acknowledged within 15 minutes, `SEV-2` within 30 minutes, `SEV-3` next business day. These mirror the communication cadence above.
- **Escalation path:** primary on-call → secondary on-call → engineering lead. Escalate to the next tier if a `SEV-1` is unacknowledged after 15 minutes or unmitigated after 30 minutes.
- **First action on page:** follow "First 15 minutes" and "System triage order" above — assign an owner, record impact, and check `/health/live` and `/health`.
- **Disaster escalation:** if triage points to lost or corrupted data, or a regional/data-store outage, escalate to the DR procedure in [disaster-recovery.md](./disaster-recovery.md).
- **Postmortem ownership:** the incident owner produces the postmortem note required by the exit criteria above; SLO and error-budget impact should be recorded in it.
