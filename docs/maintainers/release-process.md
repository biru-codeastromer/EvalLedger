# Release Process

This is the maintainer checklist for cutting a stable EvalLedger release.

## Before release

1. Confirm `main` is green in CI.
2. Run `make lint`, `make test`, and `cd frontend && pnpm build`.
3. Apply pending migrations in staging.
4. Seed or refresh any staging data required for verification.
5. Run `make loadtest API_URL=http://localhost:8000` or the staging equivalent and compare to the last known-good baseline.
6. Review open schema, auth, storage, or performance-sensitive changes for rollout order.

## Release checklist

1. Merge the release branch or approved change set into `main`.
2. Tag the release commit if the change is externally meaningful.
3. Deploy backend services first when migrations are additive.
4. Deploy the frontend after the API is reachable and healthy.
5. Re-run smoke checks on health, auth, submit, registry, and citation flows.

## Smoke checks

- `GET /health/live`
- `GET /health`
- login through the frontend
- open `/registry`
- open one benchmark detail page
- create an API key from `/account`
- submit flow reaches the review step without client errors
- run one small browse-scenario perf check if the release touched query-heavy paths

## After release

1. Capture the deployment revision and timestamp.
2. Record any manual migration steps performed.
3. Watch logs and error rates for at least one full contamination job cycle.
4. Write follow-up issues for anything manually patched during rollout.
