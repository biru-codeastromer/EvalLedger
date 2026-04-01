# Contributing to EvalLedger

EvalLedger is meant to behave like infrastructure, not a demo. Changes should leave the registry easier to reason about, test, and operate.

## Local workflow

1. Run `make dev` to bring up Postgres, Redis, MinIO, the API, the worker, and the frontend.
2. Apply schema changes with `make migrate`.
3. Seed local benchmark records with `make seed`.
4. Run `make lint` and `make test` before pushing.

## Backend expectations

- Keep FastAPI handlers async all the way through.
- Prefer structured `AppError` responses over raw exceptions.
- When adding schema changes, include an Alembic migration in the same branch.
- Add or update tests whenever auth, validation, storage, or contamination behavior changes.

## Frontend expectations

- Preserve the editorial, research-institution visual tone.
- Keep internal routes wired with `next/link`.
- Use typed API helpers from `frontend/lib/api.ts` instead of inline `fetch` calls.
- Add or update Playwright and unit coverage when shipping new user flows.

## Migrations and schema changes

- Every migration should be forward-only and reversible.
- Name migrations after the operational change, not an internal ticket.
- Document cross-service rollout order whenever a migration changes runtime expectations.
- Update `docs/maintainers/migration-policy.md` if the migration introduces a new maintenance rule.

## Review checklist

- Lint, type, and test checks are green locally.
- README or docs are updated if the workflow changed.
- New routes return structured errors.
- New operational surfaces include at least one verification path.
