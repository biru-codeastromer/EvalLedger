"""Helpers for opt-in ``Idempotency-Key`` support on POST writes.

A client that retries a POST (network blip, double-click) can send the same
``Idempotency-Key`` header; the first response is cached in Redis and replayed
on subsequent identical requests, so the write happens at most once. The cache
key is scoped by the caller's credential and the request path so one client's
key can never collide with another's or be replayed across endpoints.
"""

from __future__ import annotations

import base64
import hashlib
import json

IDEMPOTENCY_HEADER = "idempotency-key"


def build_idempotency_key(credential: str, path: str, idempotency_key: str) -> str:
    """Return the Redis key for a (caller, path, client-key) triple."""
    scope = hashlib.sha256(f"{credential}|{path}".encode()).hexdigest()[:32]
    return f"idem:{scope}:{idempotency_key}"


def encode_cached_response(status_code: int, content_type: str, body: bytes) -> bytes:
    """Serialise a response for storage (body base64-encoded so it is JSON-safe)."""
    payload = {
        "status_code": status_code,
        "content_type": content_type,
        "body_b64": base64.b64encode(body).decode("ascii"),
    }
    return json.dumps(payload).encode("utf-8")


def decode_cached_response(raw: bytes) -> tuple[int, str, bytes]:
    """Inverse of :func:`encode_cached_response`. Raises ValueError if malformed."""
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or "status_code" not in payload or "body_b64" not in payload:
        raise ValueError("malformed cached idempotent response")
    status_code = int(payload["status_code"])
    content_type = str(payload.get("content_type") or "application/json")
    body = base64.b64decode(payload["body_b64"])
    return status_code, content_type, body
