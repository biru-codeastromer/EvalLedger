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
