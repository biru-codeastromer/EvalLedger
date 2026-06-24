# Disaster Recovery Runbook

This runbook defines EvalLedger's disaster-recovery (DR) posture: explicit
recovery objectives per data store, the blast radius of the current
single-region deployment, a step-by-step restore-from-backup procedure, and a
quarterly restore-drill checklist.

It is the authoritative reference for "the database/region/storage is gone — how
do we get back". For routine backup mechanics and the verification scripts, see
the companion [Backup and Restore Runbook](./backup-restore.md). For handling a
live production incident, see the [Incident Response Runbook](./incident-response.md).

---

## Recovery objectives (RPO / RTO)

**RPO** (Recovery Point Objective) — the maximum acceptable data loss, measured
as the age of the most recent recoverable backup.

**RTO** (Recovery Time Objective) — the maximum acceptable time to restore
service after a declared disaster.

These targets are scoped to the current deployment (Render free tier, single
region — see [Blast radius](#blast-radius-single-region-single-replica) below).
They are deliberately modest; tightening them requires the infrastructure
upgrades listed under [Improving these objectives](#improving-these-objectives).

| Data store | RPO (max data loss) | RTO (max downtime) | Backup mechanism | Notes |
|---|---|---|---|---|
| **PostgreSQL** | 24h (daily `pg_dump`); ≤5 min if PITR enabled | 1h | Daily `pg_dump` via scheduled backup workflow + provider daily snapshot; PITR on Standard plan or above | Authoritative store. All benchmark metadata, versions, citations, audit trail, user accounts. Loss here is the worst case. |
| **Redis** | N/A (no durable RPO target) | 15 min | None — treated as disposable | Broker/result backend for Celery and rate-limit/cache state only. No source-of-truth data. Recovery = re-provision empty; the app re-populates. `WORKER_ENABLED=false` in production today, so the queue is normally empty. |
| **Object storage (artifacts)** | 24h with bucket versioning (R2/S3); **no recovery** with local ephemeral storage | 1h (R2/S3) | Bucket versioning or daily snapshot (R2/S3) | Production currently runs `STORAGE_BACKEND=local` — artifacts are **ephemeral and not recoverable** across redeploys. Durable recovery requires migrating to R2/S3 (see deployment.md → "Durable artifact storage"). |

**Read these targets together with the data-store priority:** PostgreSQL is the
only store whose loss is unrecoverable from elsewhere, so it gets the strictest
RPO and the first restore step. Object storage is recoverable only if durable
storage (R2/S3) is configured; under the default local-storage configuration,
artifact loss is permanent and a redeploy is the "recovery". Redis carries no
durable data and is rebuilt empty.

---

## Blast radius (single region, single replica)

The current production topology (see `render.yaml` and
[deployment.md](./deployment.md)) is intentionally minimal and has a wide blast
radius. Operators must understand these limits before relying on the RPO/RTO
targets above.

- **Single region.** All three managed resources (`evalledger-db`,
  `evalledger-redis`, `evalledger-api`) live in one Render region. A regional
  outage takes down the entire service. There is **no cross-region replica and
  no automatic failover.**
- **Single Postgres instance, no read replica.** `evalledger-db` is a single
  free-tier instance. There is no hot standby; recovery from instance loss is a
  restore-from-backup operation, not a failover. This is the dominant
  contributor to the 1h Postgres RTO.
- **Single API instance, no horizontal redundancy.** `evalledger-api` runs as a
  single free-tier web service. A crash, a bad deploy, or a free-tier cold start
  is a full availability gap for that window. Liveness is probed at
  `/health/live`; readiness (dependency health) at `/health`.
- **Single Redis instance.** `evalledger-redis` is a single free-tier instance
  with `allkeys-lru` eviction. Its loss degrades rate limiting and (when the
  worker is enabled) drops in-flight Celery tasks, but loses no source-of-truth
  data.
- **Ephemeral artifact storage by default.** With `STORAGE_BACKEND=local`,
  uploaded artifact files live on the API container's local filesystem and are
  **lost on every redeploy**, not just on disaster. Treat any
  local-storage deployment as having **no artifact durability**.
- **No background worker in production.** `WORKER_ENABLED=false` on Render, so
  contamination jobs do not run. After a restore, contamination status may
  remain `pending` until a worker is run; this is expected, not a restore
  failure.

**Implication:** a single regional incident can cause total downtime, and under
default settings any artifact data created since the last redeploy is
unrecoverable. The RTO/RPO targets above assume the disaster is scoped to a
single data store (e.g. Postgres corruption), not a full regional loss. A full
regional loss requires re-provisioning the stack in a new region and is
out-of-band of the stated RTO.

---

## Restore-from-backup procedure

This is the end-to-end recovery sequence. It follows the same component order as
the [Backup and Restore Runbook](./backup-restore.md#restore-order) but is
framed for a disaster (data store lost or corrupted) rather than a routine
restore. All commands are run from the repository root unless noted; the backup
and verification scripts live at `backend/app/scripts/db_backup.py` and
`backend/app/scripts/check_restore.py`.

### 0. Declare and scope (target: first 15 minutes)

1. Declare the incident and assign one owner (see
   [incident-response.md](./incident-response.md) → "First 15 minutes").
2. Determine the blast radius: which data store(s) are affected — Postgres,
   Redis, object storage, or a full regional loss.
3. Freeze deploys and disable new submissions to prevent writing into a
   half-restored state.
4. Identify the recovery point: locate the most recent good backup. Daily
   `pg_dump` artifacts come from the scheduled backup workflow (see
   [Backup cadence](./backup-restore.md#backup-cadence)); provider snapshots and
   PITR are managed in the Render dashboard.

### 1. Restore PostgreSQL (the authoritative store)

1. Provision a healthy target database (a new Render Postgres instance, or PITR
   recovery on the existing one).
2. Restore the most recent good dump produced by `db_backup.py` / `make db-backup`:

   ```bash
   # Plain SQL dump (produced by --format plain / make db-backup)
   DATABASE_URL=postgresql://user:pass@host:5432/evalledger \
       psql "$DATABASE_URL" < backup-YYYYMMDD-HHMMSS.sql

   # Custom-format dump (produced by --format custom)
   DATABASE_URL=postgresql://user:pass@host:5432/evalledger \
       pg_restore --dbname "$DATABASE_URL" --no-owner backup.dump
   ```

   The dump is produced by `backend/app/scripts/db_backup.py`, which normalises
   the SQLAlchemy DSN and passes the password via `PGPASSWORD` (never on the
   command line). See
   [Creating a database backup](./backup-restore.md#creating-a-database-backup).
3. Apply any pending migrations so the schema matches the deployed application
   revision:

   ```bash
   make migrate          # uv run alembic upgrade head
   ```

   Confirm with `alembic current` that the head revision matches the application
   you are about to deploy.

### 2. Re-provision Redis (disposable)

1. Provision a fresh, empty `evalledger-redis` instance (or accept the existing
   one if it survived). No data restore is required.
2. Ensure `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` point at
   the new instance. The application repopulates cache and rate-limit state on
   its own.

### 3. Restore object storage (artifacts)

- **R2/S3 (durable):** restore the bucket from a snapshot or rely on bucket
  versioning to roll back deleted/overwritten objects. Re-point the
  `STORAGE_S3_*` variables if the bucket changed.
- **Local ephemeral storage:** there is **nothing to restore** — artifact bytes
  created since the last redeploy are gone. Expect artifact reconciliation
  (step 6) to report missing files. This is a known limitation of the default
  configuration, not a recoverable failure.

### 4. Deploy the matching application revision

Deploy the application commit whose schema matches the restored database
(`alembic current`). On Render this is the container that runs
`bin/docker-entrypoint.sh` (which itself runs `uv run alembic upgrade head`)
before serving via uvicorn. Do **not** deploy a newer commit with unapplied
migrations against an older restored schema.

### 5. Verify the restore (target: before reopening writes)

Run the post-restore verification script against the restored instance. It
exercises liveness, readiness, and the key read paths:

```bash
# Against a deployed instance (public checks only)
make check-restore API_URL=https://evalledger-api.onrender.com

# Include the admin-only review-queue check
make check-restore API_URL=https://evalledger-api.onrender.com API_KEY=<admin-key>
```

`make check-restore` runs `backend/app/scripts/check_restore.py`, which performs
9 checks (10 with an API key) and exits non-zero if any fail. The full check
table and its pass criteria are documented in
[Post-restore verification](./backup-restore.md#post-restore-verification).
All checks must pass before reopening writes.

### 6. Reconcile artifacts

Confirm every artifact reference in the restored database resolves in storage:

```bash
make check-artifacts
```

See [Artifact reconciliation](./backup-restore.md#artifact-reconciliation).
Under local ephemeral storage, missing artifacts are expected after a disaster;
under R2/S3, zero missing artifacts is the success criterion.

### 7. Reopen and confirm recovery

1. Re-enable submissions and unfreeze deploys.
2. Confirm `/health` (readiness) returns 200 with all dependency checks true.
3. Watch monitoring for sustained recovery, not a single successful retry (see
   [incident-response.md](./incident-response.md) → "Exit criteria").
4. Record the actual recovery point and recovery time achieved, and compare them
   against the RPO/RTO targets above.

### Common restore failure modes

Symptom-to-resolution mappings (seed data missing, stale Alembic revision,
missing artifacts, `db: false` on `/health`, etc.) are catalogued in
[Failure modes](./backup-restore.md#failure-modes). Consult that table for any
failed `check-restore` step.

---

## Quarterly restore drill

Run a full DR drill at least once per quarter to validate that the procedure
above actually meets the RPO/RTO targets. The drill **must use a staging target,
never production.** This extends the
[Recovery drill](./backup-restore.md#recovery-drill-quarterly) checklist with
explicit objective measurement.

Checklist:

- [ ] **Pick the recovery point.** Identify the latest daily `pg_dump` artifact
      from the scheduled backup workflow. Record its timestamp; confirm its age
      is within the 24h Postgres RPO.
- [ ] **Provision a clean staging target** (Postgres + Redis), separate from
      production.
- [ ] **Start a stopwatch.** Record the drill start time — this is the RTO clock.
- [ ] **Restore Postgres** from the chosen dump (step 1 above) and run
      `make migrate`.
- [ ] **Provision empty Redis** and point the staging app at it (step 2).
- [ ] **Restore/seed artifact storage** as appropriate for the staging backend
      (step 3).
- [ ] **Deploy the matching application revision** to staging (step 4).
- [ ] **Run `make check-restore API_URL=<staging-url>`** — all 9 checks must
      pass (10 with an admin key).
- [ ] **Run `make check-artifacts`** — record the number of missing artifacts
      (expected to be > 0 under local ephemeral storage; should be 0 under
      R2/S3).
- [ ] **Manually verify** a known benchmark (`/benchmarks/mmlu`) loads with
      citation and audit history, and that an admin can reach the review queue.
- [ ] **Stop the stopwatch.** Record total restore duration and compare against
      the 1h Postgres RTO. Flag a follow-up if it was exceeded.
- [ ] **Record results:** recovery point age (vs RPO), restore duration (vs RTO),
      missing-artifact count, and any manual steps or surprises.
- [ ] **Update this runbook and `backup-restore.md`** with findings, and file
      follow-up work for any objective that was missed.

---

## Improving these objectives

The targets above reflect the current free-tier, single-region topology. To
tighten RPO/RTO, in rough priority order:

1. **Migrate artifacts to durable R2/S3 storage** (`STORAGE_BACKEND=s3`). This is
   the single biggest gap: it changes object-storage RPO from "no recovery" to
   24h (or better, with versioning). See deployment.md → "Durable artifact
   storage (Cloudflare R2)".
2. **Enable Postgres PITR** (Render Standard plan or above) to cut the Postgres
   RPO from 24h to roughly 5 minutes.
3. **Add a Postgres read replica / standby** to convert instance loss from a
   restore into a failover, cutting the Postgres RTO well below 1h.
4. **Run more than one API instance** to remove the single-API availability gap
   and absorb cold starts.
5. **Add a second region** with cross-region backup copies to shrink the blast
   radius of a regional outage. Until then, a full regional loss is explicitly
   out-of-band of the stated RTO.
