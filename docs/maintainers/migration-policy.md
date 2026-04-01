# Migration Policy

EvalLedger stores provenance records. Schema changes must preserve operator clarity and historical trust.

## Rules

- Every schema change must ship with an Alembic migration.
- Every migration must have a downgrade path, even if rollback is operationally discouraged.
- Prefer additive changes first, then cleanup in a later migration.
- Avoid migrations that require application downtime unless explicitly documented.

## Operational expectations

- Name indices and constraints predictably.
- Document any backfill requirement in the migration header or release notes.
- Never hide destructive data transformations inside unrelated migrations.
- If a migration changes auth, submission, or artifact semantics, update docs in the same branch.

## Review questions

Before merging a migration, answer:

1. Can old code tolerate the new schema during rollout?
2. Can new code tolerate the old schema during rollout?
3. Is there a clear restore path if the migration succeeds but the deploy fails?
4. Are the affected queries indexed for the new access pattern?
