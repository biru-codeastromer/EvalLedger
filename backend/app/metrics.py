"""Prometheus metrics for EvalLedger (the RED metrics: Rate, Errors, Duration).

A dedicated CollectorRegistry (rather than the global default) keeps metrics
isolated and avoids duplicate-registration errors under test re-imports and the
dev autoreloader. The request label uses the matched *route template*
(e.g. ``/benchmarks/{slug}``) rather than the raw path, so per-endpoint metrics
stay low-cardinality instead of exploding on every distinct slug/version.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest

REGISTRY = CollectorRegistry()

REQUESTS_TOTAL = Counter(
    "evalledger_http_requests_total",
    "Total HTTP requests handled, labelled by method, route template and status.",
    ["method", "path", "status"],
    registry=REGISTRY,
)

REQUEST_DURATION_SECONDS = Histogram(
    "evalledger_http_request_duration_seconds",
    "HTTP request latency in seconds, labelled by method and route template.",
    ["method", "path"],
    registry=REGISTRY,
)


def observe_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    """Record one completed request against the RED metrics."""
    REQUESTS_TOTAL.labels(method=method, path=path, status=str(status_code)).inc()
    REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration_seconds)


def render_latest() -> tuple[bytes, str]:
    """Return the Prometheus exposition payload and its content type."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
