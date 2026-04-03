from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import httpx

from evalledger.config import CLIConfig


class EvalLedgerClientError(Exception):
    pass


class EvalLedgerClient:
    def __init__(self, config: CLIConfig) -> None:
        self.config = config
        self.base_url = config.endpoint.rstrip("/")
        self._client = httpx.Client(timeout=30.0)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.config.api_key:
            headers["X-API-Key"] = self.config.api_key
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.request(
                method,
                f"{self.base_url}{path}",
                headers={**self._headers(), **kwargs.pop("headers", {})},
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise EvalLedgerClientError(f"Network error: {exc}") from exc
        if response.is_error:
            try:
                payload = response.json()
                message = payload.get("error", {}).get("message", response.text)
            except ValueError:
                message = response.text
            raise EvalLedgerClientError(message)
        return response

    def _json_dict(self, response: httpx.Response) -> dict[str, Any]:
        payload = response.json()
        if not isinstance(payload, dict):
            raise EvalLedgerClientError("Unexpected response payload")
        return cast(dict[str, Any], payload)

    def whoami(self) -> dict[str, Any]:
        """Return the current user's profile. Used to validate an API key."""
        return self._json_dict(self._request("GET", "/auth/me"))

    def search(self, query: str) -> dict[str, Any]:
        return self._json_dict(self._request("GET", "/search", params={"q": query}))

    def get_benchmark(self, slug: str) -> dict[str, Any]:
        return self._json_dict(self._request("GET", f"/benchmarks/{slug}"))

    def get_version(self, slug: str, version: str) -> dict[str, Any]:
        return self._json_dict(self._request("GET", f"/benchmarks/{slug}/{version}"))

    def get_citation(self, slug: str, version: str, citation_format: str) -> str:
        response = self._request(
            "GET",
            f"/benchmarks/{slug}/{version}/citation",
            params={"format": citation_format},
        )
        return response.text

    def create_benchmark(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._json_dict(self._request("POST", "/benchmarks", json=payload))

    def submit_version(self, slug: str, data: dict[str, Any], file_path: Path) -> dict[str, Any]:
        with file_path.open("rb") as handle:
            files = {"artifact": (file_path.name, handle, "application/octet-stream")}
            response = self._request(
                "POST",
                f"/benchmarks/{slug}/versions",
                data=data,
                files=files,
                timeout=120.0,
            )
            return self._json_dict(response)

    def run_check(self, file_path: Path, corpus_ids: list[str] | None = None) -> dict[str, Any]:
        with file_path.open("rb") as handle:
            files = {"artifact": (file_path.name, handle, "application/octet-stream")}
            data = {"corpus_ids": ",".join(corpus_ids or [])}
            response = self._request("POST", "/contamination/check", files=files, data=data, timeout=120.0)
            return self._json_dict(response)

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._json_dict(self._request("GET", f"/contamination/jobs/{job_id}"))

    def close(self) -> None:
        self._client.close()
