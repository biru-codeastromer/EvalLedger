"""Tests for Prometheus /metrics and HTTP caching (ETag / Cache-Control)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import StreamingResponse

from app.main import _apply_http_caching, app


def _make_request(method: str = "GET", path: str = "/search", headers: dict[str, str] | None = None) -> Request:
    raw = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    return Request({"type": "http", "method": method, "path": path, "headers": raw, "query_string": b""})


def test_metrics_endpoint_exposes_prometheus_exposition() -> None:
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    # The request we just made should be counted under its route template.
    assert "evalledger_http_requests_total" in response.text


def test_caching_sets_etag_for_anonymous_get() -> None:
    response = _apply_http_caching(_make_request(), JSONResponse({"hello": "world"}))
    assert response.headers["ETag"].startswith('W/"')
    assert response.headers["Cache-Control"].startswith("public")


def test_caching_returns_304_on_matching_if_none_match() -> None:
    first = _apply_http_caching(_make_request(), JSONResponse({"hello": "world"}))
    etag = first.headers["ETag"]
    second = _apply_http_caching(_make_request(headers={"if-none-match": etag}), JSONResponse({"hello": "world"}))
    assert second.status_code == 304
    assert second.headers["ETag"] == etag


def test_caching_is_private_for_authenticated_requests() -> None:
    response = _apply_http_caching(
        _make_request(headers={"authorization": "Bearer x"}), JSONResponse({"me": 1})
    )
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "ETag" not in response.headers


def test_caching_skips_exempt_paths() -> None:
    response = _apply_http_caching(_make_request(path="/health"), JSONResponse({"status": "ok"}))
    assert "ETag" not in response.headers


def test_caching_ignores_non_get_and_non_200() -> None:
    assert "ETag" not in _apply_http_caching(_make_request(method="POST"), JSONResponse({"x": 1})).headers
    err = JSONResponse({"x": 1}, status_code=404)
    assert "ETag" not in _apply_http_caching(_make_request(), err).headers


def test_caching_ignores_streaming_responses() -> None:
    # A streaming/file response (e.g. artifact download) has no .body and must
    # pass through untouched rather than being buffered to compute an ETag.
    async def _stream() -> AsyncIterator[bytes]:
        yield b"chunk"

    response = _apply_http_caching(_make_request(), StreamingResponse(_stream(), status_code=200))
    assert "ETag" not in response.headers
