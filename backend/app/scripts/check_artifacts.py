"""Artifact reconciliation for EvalLedger.

Queries the database for every artifact reference (benchmark version files and
reference corpus minhash indices) and checks whether the underlying object
actually exists in storage.  Produces a structured report with counts and a
list of missing or problematic entries.

Usage
-----
Against the local dev environment::

    python -m app.scripts.check_artifacts

Against a specific environment by pointing at its DATABASE_URL and storage::

    DATABASE_URL=postgresql+asyncpg://... STORAGE_BACKEND=s3 \\
        python -m app.scripts.check_artifacts

    python -m app.scripts.check_artifacts --json   # machine-readable output

Exit codes
----------
0   all referenced artifacts found
1   one or more artifacts missing or inaccessible
2   configuration / connectivity error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ArtifactEntry:
    kind: str          # "benchmark_version" | "corpus_index"
    ref_id: str        # version or corpus UUID string
    storage_key: str   # path on disk or S3 key
    exists: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "ref_id": self.ref_id,
            "storage_key": self.storage_key,
            "exists": self.exists,
            "error": self.error,
        }


@dataclass
class ReconciliationReport:
    total: int = 0
    found: int = 0
    missing: int = 0
    errors: int = 0
    missing_entries: list[ArtifactEntry] = field(default_factory=list)
    error_entries: list[ArtifactEntry] = field(default_factory=list)

    def add(self, entry: ArtifactEntry) -> None:
        self.total += 1
        if entry.error:
            self.errors += 1
            self.error_entries.append(entry)
        elif entry.exists:
            self.found += 1
        else:
            self.missing += 1
            self.missing_entries.append(entry)

    @property
    def ok(self) -> bool:
        return self.missing == 0 and self.errors == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "found": self.found,
            "missing": self.missing,
            "errors": self.errors,
            "missing_entries": [e.to_dict() for e in self.missing_entries],
            "error_entries": [e.to_dict() for e in self.error_entries],
        }


# ---------------------------------------------------------------------------
# Storage checkers
# ---------------------------------------------------------------------------


def _check_local_path(storage_key: str) -> tuple[bool, str]:
    """Return (exists, error_message) for a local filesystem path."""
    try:
        return Path(storage_key).exists(), ""
    except (OSError, ValueError) as exc:
        return False, str(exc)


def _check_s3_key(
    key: str,
    *,
    bucket: str,
    endpoint_url: str,
    access_key_id: str,
    secret_access_key: str,
    region: str = "us-east-1",
) -> tuple[bool, str]:
    """Return (exists, error_message) for an S3/R2 object key.

    Uses ``head_object`` which requires only object-level read access —
    compatible with Cloudflare R2 scoped API tokens.
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        return False, "boto3 is not installed"

    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name=region,
    )
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True, ""
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in {"404", "NoSuchKey"}:
            return False, ""
        return False, f"S3 error {code}: {exc.response['Error'].get('Message', '')}"
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# DSN / settings helpers
# ---------------------------------------------------------------------------


def _sync_dsn_from_env() -> str:
    """Derive a sync psycopg DSN from environment variables.

    Reads DATABASE_URL or SYNC_DATABASE_URL (in that order) and normalises
    the scheme to ``postgresql+psycopg://`` for use with SQLAlchemy sync.
    """
    raw = os.environ.get("SYNC_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    if not raw:
        # Fall back to the dev default.
        raw = "postgresql+asyncpg://evalledger:evalledger@localhost:5432/evalledger"
    # Normalise scheme.
    for prefix, replacement in [
        ("postgresql+asyncpg://", "postgresql+psycopg://"),
        ("postgres://", "postgresql+psycopg://"),
        ("postgresql://", "postgresql+psycopg://"),
    ]:
        if raw.startswith(prefix):
            return raw.replace(prefix, replacement, 1)
    return raw


# ---------------------------------------------------------------------------
# DB query
# ---------------------------------------------------------------------------


def _fetch_artifact_refs(dsn: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Connect synchronously and fetch (id, artifact_url) and (id, minhash_index_path).

    Returns:
        version_refs   — list of (version_id_str, artifact_url)
        corpus_refs    — list of (corpus_id_str, minhash_index_path)

    Only rows where the column is non-NULL are included.
    """
    try:
        from sqlalchemy import create_engine, text
    except ImportError as exc:
        raise RuntimeError("SQLAlchemy is required to query the database") from exc

    engine = create_engine(dsn, pool_pre_ping=True)
    with engine.connect() as conn:
        version_rows = conn.execute(
            text("SELECT id::text, artifact_url FROM benchmark_versions WHERE artifact_url IS NOT NULL")
        ).fetchall()
        corpus_rows = conn.execute(
            text(
                "SELECT id::text, minhash_index_path FROM reference_corpora"
                " WHERE minhash_index_path IS NOT NULL AND is_active = true"
            )
        ).fetchall()
    engine.dispose()
    return (
        [(str(r[0]), str(r[1])) for r in version_rows],
        [(str(r[0]), str(r[1])) for r in corpus_rows],
    )


# ---------------------------------------------------------------------------
# Storage config from environment
# ---------------------------------------------------------------------------


def _s3_config_from_env() -> dict[str, str] | None:
    """Return S3 config dict if STORAGE_BACKEND=s3, else None."""
    backend = os.environ.get("STORAGE_BACKEND", "local")
    if backend != "s3":
        return None
    return {
        "bucket": os.environ.get("STORAGE_BUCKET", "evalledger-artifacts"),
        "endpoint_url": os.environ.get("STORAGE_S3_ENDPOINT_URL", ""),
        "access_key_id": os.environ.get("STORAGE_S3_ACCESS_KEY_ID", ""),
        "secret_access_key": os.environ.get("STORAGE_S3_SECRET_ACCESS_KEY", ""),
        "region": os.environ.get("STORAGE_S3_REGION", "us-east-1"),
    }


# ---------------------------------------------------------------------------
# Reconciliation logic
# ---------------------------------------------------------------------------


def reconcile(
    version_refs: list[tuple[str, str]],
    corpus_refs: list[tuple[str, str]],
    s3_config: dict[str, str] | None,
) -> ReconciliationReport:
    """Check every artifact reference and return a ReconciliationReport."""
    report = ReconciliationReport()

    all_refs: list[tuple[str, str, str]] = [
        ("benchmark_version", ref_id, key) for ref_id, key in version_refs
    ] + [
        ("corpus_index", ref_id, key) for ref_id, key in corpus_refs
    ]

    for kind, ref_id, storage_key in all_refs:
        if s3_config:
            exists, error = _check_s3_key(
                storage_key,
                bucket=s3_config["bucket"],
                endpoint_url=s3_config["endpoint_url"],
                access_key_id=s3_config["access_key_id"],
                secret_access_key=s3_config["secret_access_key"],
                region=s3_config.get("region", "us-east-1"),
            )
        else:
            exists, error = _check_local_path(storage_key)

        entry = ArtifactEntry(
            kind=kind,
            ref_id=ref_id,
            storage_key=storage_key,
            exists=exists,
            error=error,
        )
        report.add(entry)

    return report


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def print_report(report: ReconciliationReport) -> None:
    sep = "=" * 60
    print(f"\n{sep}")
    print("  Artifact reconciliation report")
    print(f"  Total referenced: {report.total}")
    print(f"  Found:            {report.found}")
    print(f"  Missing:          {report.missing}")
    print(f"  Errors:           {report.errors}")
    print(sep)

    if report.missing_entries:
        print(f"\n  Missing artifacts ({report.missing}):")
        for e in report.missing_entries:
            print(f"    [\u2717] [{e.kind}] {e.ref_id[:8]}... {e.storage_key}")

    if report.error_entries:
        print(f"\n  Storage errors ({report.errors}):")
        for e in report.error_entries:
            print(f"    [!] [{e.kind}] {e.ref_id[:8]}... {e.storage_key}")
            print(f"        {e.error}")

    if report.ok:
        print(f"\n  All {report.total} artifacts accounted for.\n")
    else:
        print(f"\n  RECONCILIATION FAILED — {report.missing} missing, {report.errors} error(s).\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Artifact reconciliation for EvalLedger",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON instead of human-readable text",
    )
    args = parser.parse_args()

    backend = os.environ.get("STORAGE_BACKEND", "local")
    s3_config = _s3_config_from_env()

    if not args.json:
        print("\nEvalLedger artifact reconciliation")
        print(f"Storage backend: {backend}")

    try:
        dsn = _sync_dsn_from_env()
        version_refs, corpus_refs = _fetch_artifact_refs(dsn)
    except Exception as exc:
        print(f"\nFailed to query database: {exc}", file=sys.stderr)
        return 2

    if not args.json:
        print(f"Version artifact refs: {len(version_refs)}")
        print(f"Corpus index refs:     {len(corpus_refs)}")

    try:
        report = reconcile(version_refs, corpus_refs, s3_config)
    except Exception as exc:
        print(f"\nReconciliation failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print_report(report)

    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
