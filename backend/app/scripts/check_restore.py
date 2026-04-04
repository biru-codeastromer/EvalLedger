"""Post-restore health and functionality verification for EvalLedger.

Runs a sequence of HTTP checks against a live API instance to verify that a
restore (or a fresh deployment) is functioning correctly.  Each check is
independent; the script reports pass/fail for each step and exits with a
summary exit code.

Usage
-----
Against the local dev server (no auth required for public endpoints)::

    python -m app.scripts.check_restore

Against a deployed instance with admin checks enabled::

    python -m app.scripts.check_restore \\
        --api-url https://evalledger-api.onrender.com \\
        --api-key <your-api-key>

Via Makefile::

    make check-restore API_URL=https://evalledger-api.onrender.com

Exit codes
----------
0   all checks passed
1   one or more checks failed
2   argument / connectivity error
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""

    def __str__(self) -> str:
        icon = "\u2713" if self.passed else "\u2717"
        suffix = f" — {self.detail}" if self.detail else ""
        return f"  [{icon}] {self.name}{suffix}"


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------


def _get(url: str, headers: dict[str, str] | None = None, timeout: int = 15) -> tuple[int, Any]:
    """GET *url*, return ``(status_code, parsed_json_or_str)``.

    Never raises — HTTP errors and JSON parse failures are captured and
    returned as ``(error_code, None)`` so callers can always inspect the
    status code.
    """
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            try:
                return resp.status, json.loads(body)
            except (json.JSONDecodeError, ValueError):
                return resp.status, body.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except Exception:
            return exc.code, None
    except OSError as exc:
        # Connection refused, timeout, etc.
        return 0, str(exc)


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


def check_liveness(base_url: str) -> CheckResult:
    """``GET /health/live`` → 200 ``{"status":"ok"}``."""
    status, body = _get(f"{base_url}/health/live")
    if status == 200 and isinstance(body, dict) and body.get("status") == "ok":
        return CheckResult("liveness probe", True)
    return CheckResult("liveness probe", False, f"status={status} body={body!r:.80}")


def check_readiness(base_url: str) -> CheckResult:
    """``GET /health`` → 200 with all component checks passing."""
    status, body = _get(f"{base_url}/health")
    if status == 200 and isinstance(body, dict):
        checks = body.get("checks", {})
        failed = [k for k, v in checks.items() if not v]
        if not failed:
            return CheckResult("readiness probe", True, f"checks={sorted(checks)}")
        return CheckResult("readiness probe", False, f"degraded: {failed}")
    return CheckResult("readiness probe", False, f"status={status}")


def check_stats(base_url: str) -> CheckResult:
    """``GET /stats/overview`` → benchmark counts are accessible."""
    status, body = _get(f"{base_url}/stats/overview")
    if status == 200 and isinstance(body, dict):
        total = body.get("total_benchmarks", 0)
        return CheckResult("stats overview", True, f"total_benchmarks={total}")
    return CheckResult("stats overview", False, f"status={status}")


def check_recent_submissions(base_url: str) -> CheckResult:
    """``GET /stats/recent`` → recent submissions list is accessible."""
    status, body = _get(f"{base_url}/stats/recent?limit=5")
    if status == 200 and isinstance(body, list):
        return CheckResult("recent submissions", True, f"{len(body)} item(s)")
    return CheckResult("recent submissions", False, f"status={status}")


def check_search(base_url: str) -> CheckResult:
    """``GET /search?q=mmlu`` → search returns results."""
    status, body = _get(f"{base_url}/search?q=mmlu")
    if status == 200 and isinstance(body, dict):
        items = body.get("items", [])
        return CheckResult("search", True, f"{len(items)} result(s) for 'mmlu'")
    return CheckResult("search", False, f"status={status}")


def check_seeded_benchmark(base_url: str, slug: str = "mmlu") -> CheckResult:
    """``GET /benchmarks/{slug}`` → a known seeded benchmark is present."""
    status, body = _get(f"{base_url}/benchmarks/{slug}")
    if status == 200 and isinstance(body, dict):
        name = body.get("name", "")
        verified = body.get("is_verified", False)
        return CheckResult(
            f"seeded benchmark ({slug})", True, f"name={name!r} verified={verified}"
        )
    return CheckResult(f"seeded benchmark ({slug})", False, f"status={status}")


def check_benchmark_versions(base_url: str, slug: str = "mmlu") -> CheckResult:
    """``GET /benchmarks/{slug}/versions`` → at least one version exists."""
    status, body = _get(f"{base_url}/benchmarks/{slug}/versions")
    if status == 200 and isinstance(body, list):
        count = len(body)
        if count > 0:
            return CheckResult(f"versions ({slug})", True, f"{count} version(s)")
        return CheckResult(f"versions ({slug})", False, "no versions found")
    return CheckResult(f"versions ({slug})", False, f"status={status}")


def check_citation(
    base_url: str, slug: str = "mmlu", version: str = "0.0.0"
) -> CheckResult:
    """``GET /benchmarks/{slug}/{version}`` → citation block is present."""
    status, body = _get(f"{base_url}/benchmarks/{slug}/{version}")
    if status == 200 and isinstance(body, dict):
        # Accept citation_string directly or nested under citations.bibtex
        citation = body.get("citation_string") or (
            (body.get("citations") or {}).get("bibtex")
        )
        if citation:
            snippet = citation[:60].replace("\n", " ")
            return CheckResult("citation block", True, f"{snippet!r}…")
        return CheckResult("citation block", False, "no citation_string found")
    return CheckResult("citation block", False, f"status={status}")


def check_audit_activity(base_url: str, slug: str = "mmlu") -> CheckResult:
    """``GET /benchmarks/{slug}/activity`` → audit trail is accessible."""
    status, body = _get(f"{base_url}/benchmarks/{slug}/activity")
    if status == 200 and isinstance(body, list):
        return CheckResult("audit activity", True, f"{len(body)} event(s)")
    return CheckResult("audit activity", False, f"status={status}")


def check_admin_queue(base_url: str, api_key: str) -> CheckResult:
    """``GET /admin/review-queue`` (admin-only) → review queue is accessible."""
    status, body = _get(
        f"{base_url}/admin/review-queue", headers={"X-API-Key": api_key}
    )
    if status == 200 and isinstance(body, list):
        return CheckResult("admin review queue", True, f"{len(body)} item(s)")
    if status in (401, 403):
        return CheckResult("admin review queue", False, f"auth error (status={status})")
    return CheckResult("admin review queue", False, f"status={status}")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_checks(
    base_url: str,
    api_key: str | None = None,
    seed_slug: str = "mmlu",
    seed_version: str = "0.0.0",
) -> list[CheckResult]:
    """Run the full check sequence and return all results."""
    results: list[CheckResult] = [
        check_liveness(base_url),
        check_readiness(base_url),
        check_stats(base_url),
        check_recent_submissions(base_url),
        check_search(base_url),
        check_seeded_benchmark(base_url, slug=seed_slug),
        check_benchmark_versions(base_url, slug=seed_slug),
        check_citation(base_url, slug=seed_slug, version=seed_version),
        check_audit_activity(base_url, slug=seed_slug),
    ]
    if api_key:
        results.append(check_admin_queue(base_url, api_key))
    return results


def print_summary(results: list[CheckResult]) -> None:
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    sep = "=" * 60
    print(f"\n{sep}")
    for r in results:
        print(r)
    print(sep)
    if passed == total:
        print(f"  All {total} checks passed.")
    else:
        print(f"  {passed}/{total} checks passed \u2014 {total - passed} FAILED.")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post-restore verification for EvalLedger",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base API URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Admin API key — enables admin-only checks",
    )
    parser.add_argument(
        "--slug",
        default="mmlu",
        help="Seeded benchmark slug to verify (default: mmlu)",
    )
    parser.add_argument(
        "--version",
        default="0.0.0",
        help="Seeded version string to verify (default: 0.0.0)",
    )
    args = parser.parse_args()

    base_url = args.api_url.rstrip("/")
    print("\nEvalLedger post-restore verification")
    print(f"Target: {base_url}")
    if args.api_key:
        print("Admin checks: enabled")

    try:
        results = run_checks(
            base_url=base_url,
            api_key=args.api_key,
            seed_slug=args.slug,
            seed_version=args.version,
        )
    except Exception as exc:
        print(f"\nFailed to run checks: {exc}", file=sys.stderr)
        return 2

    print_summary(results)
    return 1 if any(not r.passed for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
