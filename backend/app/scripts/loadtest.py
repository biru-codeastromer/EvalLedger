from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from itertools import cycle, islice
from statistics import mean
from time import perf_counter
from typing import TypedDict

import httpx


@dataclass(slots=True, frozen=True)
class RequestTarget:
    name: str
    url: str
    headers: dict[str, str] | None = None


@dataclass(slots=True)
class RequestSample:
    target: str
    status_code: int | None
    duration_ms: float
    error: str | None = None


class TargetSummary(TypedDict):
    requests: int
    mean_latency_ms: float
    p95_latency_ms: float
    failures: int


class LoadTestSummary(TypedDict):
    requests: int
    successes: int
    failures: int
    throughput_rps: float
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    status_summary: dict[str, int]
    targets: dict[str, TargetSummary]


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def _normalize_base_url(api_url: str) -> str:
    return api_url.rstrip("/")


def build_targets(
    *,
    api_url: str,
    scenario: str | None = None,
    url: str | None = None,
    api_key: str | None = None,
) -> list[RequestTarget]:
    if bool(url) == bool(scenario):
        raise ValueError("Provide exactly one of --url or --scenario.")

    if url:
        return [RequestTarget(name="custom", url=url)]

    assert scenario is not None
    base_url = _normalize_base_url(api_url)
    authed_headers = {"X-API-Key": api_key} if api_key else None

    public_targets = [
        RequestTarget("health_live", f"{base_url}/health/live"),
        RequestTarget("stats_overview", f"{base_url}/stats/overview"),
        RequestTarget("stats_recent", f"{base_url}/stats/recent?limit=12"),
        RequestTarget("search_mmlu", f"{base_url}/search?q=mmlu"),
        RequestTarget("benchmark_detail", f"{base_url}/benchmarks/mmlu"),
        RequestTarget("version_list", f"{base_url}/benchmarks/mmlu/versions"),
        RequestTarget("version_detail", f"{base_url}/benchmarks/mmlu/0.0.0"),
    ]
    account_targets = [
        RequestTarget("auth_me", f"{base_url}/auth/me", headers=authed_headers),
    ]
    review_targets = [
        RequestTarget("admin_stats", f"{base_url}/admin/stats", headers=authed_headers),
        RequestTarget(
            "admin_review_queue",
            f"{base_url}/admin/review-queue?status=pending&limit=20",
            headers=authed_headers,
        ),
        RequestTarget(
            "admin_review_context",
            f"{base_url}/admin/benchmarks/mmlu/context",
            headers=authed_headers,
        ),
    ]

    if scenario == "browse":
        return public_targets
    if scenario == "account":
        if not api_key:
            raise ValueError("--api-key is required for the account scenario.")
        return account_targets
    if scenario == "review":
        if not api_key:
            raise ValueError("--api-key is required for the review scenario.")
        return review_targets
    if scenario == "mixed":
        return public_targets + (account_targets + review_targets if api_key else [])

    raise ValueError(f"Unknown scenario: {scenario}")


def build_schedule(targets: list[RequestTarget], requests: int) -> list[RequestTarget]:
    if requests <= 0:
        raise ValueError("--requests must be greater than 0.")
    return list(islice(cycle(targets), requests))


async def run_once(client: httpx.AsyncClient, target: RequestTarget) -> RequestSample:
    started_at = perf_counter()
    try:
        response = await client.get(target.url, headers=target.headers)
    except httpx.HTTPError as exc:
        return RequestSample(
            target=target.name,
            status_code=None,
            duration_ms=(perf_counter() - started_at) * 1000,
            error=str(exc),
        )
    return RequestSample(
        target=target.name,
        status_code=response.status_code,
        duration_ms=(perf_counter() - started_at) * 1000,
    )


async def run_load_test(
    *,
    targets: list[RequestTarget],
    requests: int,
    concurrency: int,
    request_timeout: float,
) -> list[RequestSample]:
    samples: list[RequestSample] = []
    schedule = build_schedule(targets, requests)
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=request_timeout) as client:
        async def wrapped_request(target: RequestTarget) -> None:
            async with semaphore:
                samples.append(await run_once(client, target))

        await asyncio.gather(*(wrapped_request(target) for target in schedule))

    return samples


def summarize_samples(samples: list[RequestSample], total_elapsed_ms: float) -> LoadTestSummary:
    latencies = [sample.duration_ms for sample in samples]
    successes = [
        sample
        for sample in samples
        if sample.error is None and sample.status_code is not None and sample.status_code < 500
    ]
    failures = [sample for sample in samples if sample not in successes]
    throughput = (len(samples) / total_elapsed_ms) * 1000 if total_elapsed_ms > 0 else 0.0

    status_breakdown: dict[str, int] = {}
    per_target: dict[str, list[RequestSample]] = {}
    for sample in samples:
        key = sample.error if sample.error is not None else str(sample.status_code)
        status_breakdown[key] = status_breakdown.get(key, 0) + 1
        per_target.setdefault(sample.target, []).append(sample)

    target_summaries: dict[str, TargetSummary] = {
        target: {
            "requests": len(target_samples),
            "mean_latency_ms": round(mean([sample.duration_ms for sample in target_samples]), 2),
            "p95_latency_ms": round(
                percentile([sample.duration_ms for sample in target_samples], 0.95), 2
            ),
            "failures": sum(
                1
                for sample in target_samples
                if sample.error is not None
                or sample.status_code is None
                or sample.status_code >= 500
            ),
        }
        for target, target_samples in per_target.items()
    }

    return {
        "requests": len(samples),
        "successes": len(successes),
        "failures": len(failures),
        "throughput_rps": round(throughput, 2),
        "mean_latency_ms": round(mean(latencies), 2) if latencies else 0.0,
        "p50_latency_ms": round(percentile(latencies, 0.50), 2),
        "p95_latency_ms": round(percentile(latencies, 0.95), 2),
        "p99_latency_ms": round(percentile(latencies, 0.99), 2),
        "status_summary": status_breakdown,
        "targets": target_summaries,
    }


def print_summary(summary: LoadTestSummary) -> None:
    print("EvalLedger load test summary")
    print(f"  Requests:        {summary['requests']}")
    print(f"  Successes:       {summary['successes']}")
    print(f"  Failures:        {summary['failures']}")
    print(f"  Throughput:      {summary['throughput_rps']:.2f} req/s")
    print(f"  Mean latency:    {summary['mean_latency_ms']:.2f} ms")
    print(f"  P50 latency:     {summary['p50_latency_ms']:.2f} ms")
    print(f"  P95 latency:     {summary['p95_latency_ms']:.2f} ms")
    print(f"  P99 latency:     {summary['p99_latency_ms']:.2f} ms")
    print("  Status summary:")
    for key, count in sorted(summary["status_summary"].items()):
        print(f"    {key}: {count}")
    print("  Endpoint summary:")
    for target, payload in sorted(summary["targets"].items()):
        print(
            "    "
            f"{target}: requests={payload['requests']} "
            f"mean={payload['mean_latency_ms']:.2f} ms "
            f"p95={payload['p95_latency_ms']:.2f} ms "
            f"failures={payload['failures']}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a lightweight load test against EvalLedger endpoints."
    )
    parser.add_argument("--url", help="Single absolute URL to request repeatedly.")
    parser.add_argument(
        "--scenario",
        choices=["browse", "account", "review", "mixed"],
        help="Named endpoint bundle to exercise against --api-url.",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base API URL used by scenario runs (default: http://localhost:8000).",
    )
    parser.add_argument("--api-key", help="API key for authenticated/admin scenarios.")
    parser.add_argument("--requests", type=int, default=100, help="Total number of requests to send.")
    parser.add_argument(
        "--concurrency", type=int, default=10, help="Maximum concurrent in-flight requests."
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-request timeout in seconds.")
    parser.add_argument(
        "--warmup",
        type=int,
        default=0,
        help="Optional warmup request count to run before recording results.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    return parser


async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        targets = build_targets(
            api_url=args.api_url,
            scenario=args.scenario,
            url=args.url,
            api_key=args.api_key,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if args.warmup:
        await run_load_test(
            targets=targets,
            requests=args.warmup,
            concurrency=min(args.concurrency, args.warmup),
            request_timeout=args.timeout,
        )

    started_at = perf_counter()
    samples = await run_load_test(
        targets=targets,
        requests=args.requests,
        concurrency=args.concurrency,
        request_timeout=args.timeout,
    )
    total_elapsed_ms = (perf_counter() - started_at) * 1000
    summary = summarize_samples(samples, total_elapsed_ms)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return
    print_summary(summary)


if __name__ == "__main__":
    asyncio.run(main())
