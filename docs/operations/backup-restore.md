# Backup and Restore Runbook

This is the draft recovery plan for EvalLedger state. It covers the minimum sequence needed to restore benchmark metadata and associated artifacts without breaking provenance guarantees.

## What must be backed up

- PostgreSQL database
- Object storage bucket or filesystem artifact root
- MinHash index artifacts used by contamination checks
- Deployment environment configuration and secrets inventory

## Backup cadence

- Database: daily full backup plus point-in-time recovery if available.
- Artifact storage: daily snapshot or bucket versioning.
- Reference corpus indices: snapshot whenever rebuilt.
- Runbooks and migration history: keep in Git on `main`.

## Restore order

1. Restore the database first.
2. Restore artifact storage next.
3. Restore contamination index assets.
4. Deploy the application revision that matches the restored schema.
5. Run health checks and targeted verification.

## Post-restore verification

After a restore, verify:

- `/health` returns healthy checks
- seeded benchmark pages load
- a known benchmark version still exposes its citation block
- artifact download links resolve
- a no-op contamination job can be queued and observed

## Minimum recovery drill

At least once per quarter:

1. Restore into a staging environment.
2. Verify a known benchmark and version pair end to end.
3. Confirm audit activity still renders for that record.
4. Record the restore duration and any missing steps.

## Failure modes to watch

- database restored without matching artifact objects
- artifacts restored without corresponding metadata rows
- restored schema behind the deployed application revision
- stale contamination indices pointing at missing storage paths
