from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from statistics import mean
from time import perf_counter

import httpx


@dataclass(slots=True)
class RequestSample:
    status_code: int | None
    duration_ms: float
    error: str | None = None


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


async def run_once(client: httpx.AsyncClient, url: str) -> RequestSample:
    started_at = perf_counter()
    try:
        response = await client.get(url)
    except httpx.HTTPError as exc:
        return RequestSample(status_code=None, duration_ms=(perf_counter() - started_at) * 1000, error=str(exc))
    return RequestSample(status_code=response.status_code, duration_ms=(perf_counter() - started_at) * 1000)


async def run_load_test(url: str, requests: int, concurrency: int, request_timeout: float) -> list[RequestSample]:
    samples: list[RequestSample] = []
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=request_timeout) as client:
        async def wrapped_request() -> None:
            async with semaphore:
                samples.append(await run_once(client, url))

        await asyncio.gather(*(wrapped_request() for _ in range(requests)))

    return samples


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a lightweight HTTP load test against an EvalLedger endpoint.")
    parser.add_argument("--url", required=True, help="Absolute URL to request.")
    parser.add_argument("--requests", type=int, default=100, help="Total number of requests to send.")
    parser.add_argument("--concurrency", type=int, default=10, help="Maximum concurrent in-flight requests.")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-request timeout in seconds.")
    return parser


def print_summary(samples: list[RequestSample], total_elapsed_ms: float) -> None:
    latencies = [sample.duration_ms for sample in samples]
    successes = [
        sample
        for sample in samples
        if sample.error is None and sample.status_code is not None and sample.status_code < 500
    ]
    failures = [sample for sample in samples if sample not in successes]

    throughput = (len(samples) / total_elapsed_ms) * 1000 if total_elapsed_ms > 0 else 0.0

    print("EvalLedger load test summary")
    print(f"  Requests:        {len(samples)}")
    print(f"  Successes:       {len(successes)}")
    print(f"  Failures:        {len(failures)}")
    print(f"  Throughput:      {throughput:.2f} req/s")
    print(f"  Mean latency:    {mean(latencies):.2f} ms" if latencies else "  Mean latency:    0.00 ms")
    print(f"  P50 latency:     {percentile(latencies, 0.50):.2f} ms")
    print(f"  P95 latency:     {percentile(latencies, 0.95):.2f} ms")
    print(f"  P99 latency:     {percentile(latencies, 0.99):.2f} ms")

    status_breakdown: dict[str, int] = {}
    for sample in samples:
        key = sample.error if sample.error is not None else str(sample.status_code)
        status_breakdown[key] = status_breakdown.get(key, 0) + 1

    print("  Status summary:")
    for key, count in sorted(status_breakdown.items()):
        print(f"    {key}: {count}")


async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    started_at = perf_counter()
    samples = await run_load_test(
        url=args.url,
        requests=args.requests,
        concurrency=args.concurrency,
        request_timeout=args.timeout,
    )
    total_elapsed_ms = (perf_counter() - started_at) * 1000
    print_summary(samples, total_elapsed_ms)


if __name__ == "__main__":
    asyncio.run(main())
