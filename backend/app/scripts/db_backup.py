"""Database backup helper for EvalLedger.

Builds and optionally executes a ``pg_dump`` command targeting the configured
EvalLedger PostgreSQL database.  Handles DSN normalisation (asyncpg → psycopg
schemes, ``postgres://`` shorthand) and injects ``PGPASSWORD`` into the
subprocess environment so the password is never exposed on the command line.

Usage
-----
Print the command that would be run (dry-run)::

    python -m app.scripts.db_backup --print

Dump to a timestamped file in the current directory::

    python -m app.scripts.db_backup --output backup.sql

Dump to a compressed file::

    python -m app.scripts.db_backup --output backup.dump --format custom

Via Makefile::

    make db-backup
    make db-backup OUTPUT=backup.dump FORMAT=custom

Exit codes
----------
0   success (or --print — command echoed but not run)
1   pg_dump exited with a non-zero status
2   configuration / invocation error
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# DSN helpers
# ---------------------------------------------------------------------------


@dataclass
class ParsedDSN:
    host: str
    port: str
    dbname: str
    user: str
    password: str


def _parse_dsn(raw_url: str) -> ParsedDSN:
    """Parse a SQLAlchemy-style or plain Postgres DSN into its components.

    Handles the following scheme variants produced by EvalLedger's
    ``_normalise_database_urls`` validator:
    - ``postgresql+asyncpg://``
    - ``postgresql+psycopg://``
    - ``postgres://``
    - ``postgresql://``

    Raises ``ValueError`` if the URL is empty or cannot be parsed.
    """
    if not raw_url:
        raise ValueError("DATABASE_URL is not set")

    # Strip driver suffixes so urlparse handles it as plain postgresql://.
    normalised = raw_url
    for prefix, replacement in [
        ("postgresql+asyncpg://", "postgresql://"),
        ("postgresql+psycopg://", "postgresql://"),
        ("postgres://", "postgresql://"),
    ]:
        if normalised.startswith(prefix):
            normalised = normalised.replace(prefix, replacement, 1)
            break

    parsed = urlparse(normalised)
    if not parsed.hostname:
        raise ValueError(f"Could not parse host from DATABASE_URL: {raw_url!r}")

    return ParsedDSN(
        host=parsed.hostname or "localhost",
        port=str(parsed.port or 5432),
        dbname=(parsed.path or "").lstrip("/") or "evalledger",
        user=parsed.username or "evalledger",
        password=parsed.password or "",
    )


def build_pg_dump_command(
    dsn: ParsedDSN,
    *,
    output_path: str | None = None,
    fmt: str = "plain",
) -> list[str]:
    """Build the ``pg_dump`` argument list for the given connection parameters.

    Args:
        dsn:         Parsed connection parameters.
        output_path: If set, include ``-f <path>`` in the command.
        fmt:         pg_dump format: ``plain`` (default), ``custom``, ``directory``.

    Returns:
        A list of strings suitable for ``subprocess.run()``.  Password is NOT
        included in the returned list — callers must pass it via ``PGPASSWORD``.
    """
    cmd = [
        "pg_dump",
        "--host", dsn.host,
        "--port", dsn.port,
        "--username", dsn.user,
        "--dbname", dsn.dbname,
        "--format", fmt,
        "--no-password",  # never prompt; password comes from PGPASSWORD
    ]
    if output_path:
        cmd += ["--file", output_path]
    return cmd


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EvalLedger pg_dump wrapper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--print",
        dest="dry_run",
        action="store_true",
        help="Print the pg_dump command without executing it",
    )
    mode.add_argument(
        "--output",
        metavar="PATH",
        help="File path to write the dump to (passed to pg_dump -f)",
    )
    parser.add_argument(
        "--format",
        default="plain",
        choices=["plain", "custom", "directory", "tar"],
        help="pg_dump output format (default: plain)",
    )
    args = parser.parse_args()

    raw_url = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("SYNC_DATABASE_URL")
        or "postgresql+asyncpg://evalledger:evalledger@localhost:5432/evalledger"
    )

    try:
        dsn = _parse_dsn(raw_url)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    cmd = build_pg_dump_command(dsn, output_path=args.output, fmt=args.format)

    if args.dry_run:
        # Show the command with a placeholder for the password.
        safe = ["PGPASSWORD=***", *cmd]
        print(" ".join(safe))
        return 0

    env = {**os.environ, "PGPASSWORD": dsn.password}
    try:
        result = subprocess.run(cmd, env=env, check=False)
    except FileNotFoundError:
        print(
            "Error: pg_dump not found. Install postgresql-client and ensure it is on PATH.",
            file=sys.stderr,
        )
        return 2

    if result.returncode != 0:
        print(f"pg_dump exited with status {result.returncode}", file=sys.stderr)
        return 1

    if args.output:
        print(f"Backup written to: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
