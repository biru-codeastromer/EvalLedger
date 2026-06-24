"""Unit tests for the idempotency helpers (key scoping + response (de)serialisation)."""

from __future__ import annotations

import pytest

from app.idempotency import build_idempotency_key, decode_cached_response, encode_cached_response


def test_key_is_stable_for_same_inputs() -> None:
    a = build_idempotency_key("Bearer tok", "/benchmarks", "k1")
    b = build_idempotency_key("Bearer tok", "/benchmarks", "k1")
    assert a == b and a.startswith("idem:")


def test_key_differs_by_credential_path_and_client_key() -> None:
    base = build_idempotency_key("Bearer tok", "/benchmarks", "k1")
    assert build_idempotency_key("Bearer other", "/benchmarks", "k1") != base  # per-caller
    assert build_idempotency_key("Bearer tok", "/reports", "k1") != base  # per-endpoint
    assert build_idempotency_key("Bearer tok", "/benchmarks", "k2") != base  # per client key


def test_encode_decode_round_trip() -> None:
    raw = encode_cached_response(201, "application/json", b'{"id":"abc"}')
    status_code, content_type, body = decode_cached_response(raw)
    assert status_code == 201
    assert content_type == "application/json"
    assert body == b'{"id":"abc"}'


def test_decode_rejects_malformed_payload() -> None:
    with pytest.raises(ValueError):
        decode_cached_response(b"not json")
    with pytest.raises(ValueError):
        decode_cached_response(b'{"missing":"fields"}')
