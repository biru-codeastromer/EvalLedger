from __future__ import annotations

from pydantic import BaseModel

from app.schemas.benchmark import BenchmarkDetail


class BenchmarkVerificationRequest(BaseModel):
    verified: bool
    note: str | None = None


class BenchmarkVerificationResponse(BaseModel):
    benchmark: BenchmarkDetail
