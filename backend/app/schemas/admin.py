from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.audit import AuditEventResponse
from app.schemas.benchmark import BenchmarkDetail
from app.schemas.common import ORMModel, UserSummary


class BenchmarkVerificationRequest(BaseModel):
    verified: bool
    note: str | None = Field(default=None, max_length=2000)


class ReviewNoteRequest(BaseModel):
    """Add a reviewer note to a benchmark without changing its verification status."""

    note: str = Field(min_length=1, max_length=2000)


class VersionReviewSummary(ORMModel):
    """Compact version info shown in the reviewer context view."""

    id: UUID
    version: str
    contamination_status: str
    artifact_sha256: str | None = None
    artifact_size_bytes: int | None = None
    num_examples: int | None = None
    license: str | None = None
    paper_url: str | None = None
    github_url: str | None = None
    created_at: datetime
    released_at: datetime | None = None
    submitter: UserSummary | None = None


class ReviewQueueItem(BenchmarkDetail):
    """BenchmarkDetail enriched with reviewer-facing context fields."""

    # Persisted review tracking (from the benchmarks table)
    review_note: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by: UserSummary | None = None
    # OAuth providers the submitter has linked (e.g. ["github", "google"])
    submitter_providers: list[str] = Field(default_factory=list)
    # Integrity fingerprint from the latest version
    latest_artifact_sha256: str | None = None
    latest_artifact_size_bytes: int | None = None


class BenchmarkVerificationResponse(BaseModel):
    benchmark: ReviewQueueItem


class BenchmarkReviewContext(ReviewQueueItem):
    """Full reviewer context for a single benchmark — versions + full audit trail."""

    versions: list[VersionReviewSummary] = Field(default_factory=list)
    audit_history: list[AuditEventResponse] = Field(default_factory=list)


class AdminStats(BaseModel):
    """Summary counts for the admin dashboard header."""

    total_benchmarks: int
    unverified_count: int
    verified_count: int
    contamination_pending_count: int
    contamination_flagged_count: int
