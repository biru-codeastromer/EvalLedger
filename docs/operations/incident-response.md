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
