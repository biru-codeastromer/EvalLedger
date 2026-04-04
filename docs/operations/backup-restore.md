# Backup and Restore Runbook

This runbook describes how to back up and restore EvalLedger, verify that a restore succeeded, and reconcile artifact storage after recovery. All scripts referenced here live in the repo and are executable without additional tooling beyond Python and a working database connection.

---

## What must be backed up

| Component | Storage location | Why it matters |
|---|---|---|
| PostgreSQL database | Managed DB or self-hosted | All benchmark metadata, versions, citations, audit trail, user accounts |
| Artifact storage | S3/R2 bucket or `STORAGE_ROOT` on disk | Benchmark dataset files referenced by `benchmark_versions.artifact_url` |
| MinHash corpus indices | Same storage as artifacts | Required to re-run contamination checks without re-indexing |
| Environment configuration | Secrets manager or `.env` | Database URL, S3 credentials, JWT secret, OAuth credentials |
| Migration history | Git repository (`backend/alembic/`) | Must match the schema of the restored database |

---

## Backup cadence

- **Database**: daily full backup via `pg_dump`; enable PITR (point-in-time recovery) if your provider supports it (Render, Neon, Supabase all do).
- **Artifact storage**: enable bucket versioning (R2 / S3) or take daily snapshots. Object storage is typically more durable than the database — prioritise the DB.
- **Corpus indices**: snapshot after every rebuild. These are large but rarely change.
- **Configuration**: store secrets in a secrets manager (Render secret files, Doppler, AWS Secrets Manager). The `.env.example` file in the repo documents the required variables.
- **Migration history**: Alembic migration files are in Git on `main` — no separate backup needed.

---

## Creating a database backup

Use the built-in pg_dump wrapper:

```bash
# Dry-run: print the pg_dump command without running it
make db-backup-print

# Write a plain SQL dump to a timestamped file
make db-backup OUTPUT=backup-$(date +%Y%m%d-%H%M%S).sql

# Compressed custom-format dump (smaller, supports parallel restore)
make db-backup OUTPUT=backup.dump FORMAT=custom
```

Or directly via the script:

```bash
DATABASE_URL=postgresql://user:pass@host:5432/evalledger \
    python -m app.scripts.db_backup --output backup.sql --format plain
```

The script extracts `PGPASSWORD` from the DSN and passes it via environment variable — it is never written to the command line.

### Automated backups on Render

Render's managed PostgreSQL includes daily backups with 7-day retention on paid plans. For production:

1. Enable the "Daily Backups" option on your Postgres instance.
2. Enable PITR if on the Standard plan or above.
3. Schedule `make db-backup` via a Render Cron Job for an additional off-platform copy.

---

## Restore order

Restore components in this sequence to avoid broken foreign key references or schema mismatches:

1. **Restore the database** — `pg_restore` or `psql` from the dump file.
2. **Run migrations** — `make migrate` to apply any pending Alembic revisions against the restored schema.
3. **Restore artifact storage** — copy files to `STORAGE_ROOT` or restore the S3/R2 bucket from a snapshot.
4. **Deploy the matching application revision** — ensure the deployed code matches the schema version (`alembic current`).
5. **Run post-restore verification** — `make check-restore` (see below).
6. **Run artifact reconciliation** — `make check-artifacts` to confirm every DB artifact reference resolves in storage.

---

## Post-restore verification

Run the verification script against the restored instance to confirm all key subsystems are functional:

```bash
# Against local dev server (no API key needed)
make check-restore

# Against a deployed instance
make check-restore API_URL=https://evalledger-api.onrender.com

# With admin checks (verifies the review queue endpoint)
make check-restore API_URL=https://evalledger-api.onrender.com API_KEY=<admin-key>
```

The script runs 9 checks (10 with API key) and exits 0 if all pass:

| Check | Endpoint | Passes when |
|---|---|---|
| Liveness probe | `GET /health/live` | `{"status":"ok"}` |
| Readiness probe | `GET /health` | All component checks true |
| Stats overview | `GET /stats/overview` | 200 with `total_benchmarks` |
| Recent submissions | `GET /stats/recent` | 200 list |
| Search | `GET /search?q=mmlu` | 200 with items |
| Seeded benchmark | `GET /benchmarks/mmlu` | 200 with name field |
| Benchmark versions | `GET /benchmarks/mmlu/versions` | Non-empty list |
| Citation block | `GET /benchmarks/mmlu/0.0.0` | Citation string present |
| Audit activity | `GET /benchmarks/mmlu/activity` | 200 list |
| Admin review queue | `GET /admin/review-queue` | 200 list (admin only) |

A non-zero exit code means one or more checks failed — review the output for the specific failure and consult the **failure modes** section below.

---

## Artifact reconciliation

After restoring, verify that every artifact file referenced in the database actually exists in storage:

```bash
# Local storage (STORAGE_BACKEND=local)
make check-artifacts

# S3/R2 storage
STORAGE_BACKEND=s3 \
STORAGE_BUCKET=evalledger-artifacts \
STORAGE_S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com \
STORAGE_S3_ACCESS_KEY_ID=<key> \
STORAGE_S3_SECRET_ACCESS_KEY=<secret> \
    make check-artifacts

# Machine-readable JSON output
python -m app.scripts.check_artifacts --json
```

The script queries `benchmark_versions.artifact_url` and `reference_corpora.minhash_index_path` and verifies each against storage. It reports:

- **Found** — artifact exists in storage
- **Missing** — DB references an artifact that does not exist in storage
- **Errors** — storage check failed (permissions, connectivity)

Exit codes: 0 = all found, 1 = missing or error, 2 = DB connectivity failure.

---

## Failure modes

| Symptom | Likely cause | Resolution |
|---|---|---|
| `GET /health` shows `db: false` | DB connection string wrong or DB not ready | Check `DATABASE_URL`; wait for DB to accept connections |
| `GET /benchmarks/mmlu` → 404 | Seed data missing from restored DB | Run `make seed` to re-seed reference data |
| Artifact reconciliation shows missing | Artifact storage not restored | Restore bucket from snapshot or copy files to `STORAGE_ROOT` |
| `alembic current` shows stale revision | Migrations not run after restore | Run `make migrate` |
| Search returns 0 results | Search index stale | Trigger a re-index if a separate search service is in use |
| Contamination status stuck at `pending` | Worker not running after restore | Start Celery worker; check `WORKER_ENABLED=true` |
| Admin queue returns 403 | API key invalid or user not admin | Verify admin flag in DB: `SELECT is_admin FROM users WHERE email = 'admin@example.com'` |

---

## Recovery drill (quarterly)

Run a full recovery drill at least once per quarter:

1. Restore the latest backup into a **staging** environment (separate from production).
2. Run `make check-restore API_URL=<staging-url>` — all 9 checks must pass.
3. Run `make check-artifacts` — zero missing artifacts.
4. Verify a known benchmark (`/benchmarks/mmlu`) loads with citation and audit history.
5. Attempt to log in as an admin user and access the review queue.
6. Record: restore duration, number of missing artifacts (if any), manual steps required.
7. Update this runbook with findings.

---

## Makefile reference

```
make check-restore                       # verify local server (port 8000)
make check-restore API_URL=<url>         # verify deployed instance
make check-restore API_URL=<url> API_KEY=<key>  # include admin checks

make check-artifacts                     # reconcile artifacts (local storage)

make db-backup OUTPUT=<file>             # run pg_dump → file
make db-backup OUTPUT=<file> FORMAT=custom  # compressed format
make db-backup-print                     # dry-run: print command only
```

---

## Environment variables required for scripts

| Variable | Used by | Description |
|---|---|---|
| `DATABASE_URL` | `db_backup.py`, `check_artifacts.py` | SQLAlchemy async DSN (normalised automatically) |
| `STORAGE_BACKEND` | `check_artifacts.py` | `local` (default) or `s3` |
| `STORAGE_BUCKET` | `check_artifacts.py` | Bucket name (S3/R2 mode) |
| `STORAGE_S3_ENDPOINT_URL` | `check_artifacts.py` | S3-compatible endpoint URL |
| `STORAGE_S3_ACCESS_KEY_ID` | `check_artifacts.py` | S3 access key |
| `STORAGE_S3_SECRET_ACCESS_KEY` | `check_artifacts.py` | S3 secret key |
