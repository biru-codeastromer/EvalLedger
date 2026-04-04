from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import load_only, selectinload

from app.dependencies import AdminUser, SessionDep
from app.errors import AppError
from app.models.audit import AuditEvent
from app.models.benchmark import Benchmark
from app.models.user import User
from app.models.version import BenchmarkVersion
from app.schemas.admin import (
    AdminStats,
    BenchmarkReviewContext,
    BenchmarkVerificationRequest,
    BenchmarkVerificationResponse,
    ReviewNoteRequest,
    ReviewQueueItem,
    VersionReviewSummary,
)
from app.schemas.audit import AuditEventResponse
from app.schemas.benchmark import BenchmarkListItem
from app.services.audit import record_audit_event
from app.services.query_projections import latest_version_projection

router = APIRouter()
AdminLimit = Annotated[int, Query(ge=1, le=100)]
_admin_logger = logging.getLogger("evalledger.admin")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _review_queue_item(
    benchmark: Benchmark,
    *,
    latest_version: str | None = None,
    latest_contamination_status: str | None = None,
    latest_num_examples: int | None = None,
    latest_artifact_sha256: str | None = None,
    latest_artifact_size_bytes: int | None = None,
) -> ReviewQueueItem:
    """Build a ReviewQueueItem from a fully-loaded Benchmark ORM object."""
    latest = benchmark.versions[0] if benchmark.versions else None

    # Collect OAuth providers the submitter has authenticated with.
    submitter_providers: list[str] = []
    if benchmark.submitter and hasattr(benchmark.submitter, "identities"):
        submitter_providers = [ident.provider for ident in benchmark.submitter.identities]

    base = BenchmarkListItem(
        id=benchmark.id,
        slug=benchmark.slug,
        name=benchmark.name,
        description=benchmark.description,
        domain=benchmark.domain,
        task_type=benchmark.task_type,
        is_verified=benchmark.is_verified,
        total_versions=benchmark.total_versions,
        total_citations=benchmark.total_citations,
        created_at=benchmark.created_at,
        updated_at=benchmark.updated_at,
        latest_version=latest_version if latest_version is not None else (latest.version if latest else None),
        latest_contamination_status=latest_contamination_status
        if latest_contamination_status is not None
        else (latest.contamination_status if latest else None),
        latest_num_examples=latest_num_examples
        if latest_num_examples is not None
        else (latest.num_examples if latest else None),
    )
    return ReviewQueueItem(
        **base.model_dump(),
        submitter=benchmark.submitter,
        review_note=benchmark.review_note,
        reviewed_at=benchmark.reviewed_at,
        reviewed_by=benchmark.reviewed_by,
        submitter_providers=submitter_providers,
        latest_artifact_sha256=latest_artifact_sha256
        if latest_artifact_sha256 is not None
        else (latest.artifact_sha256 if latest else None),
        latest_artifact_size_bytes=latest_artifact_size_bytes
        if latest_artifact_size_bytes is not None
        else (latest.artifact_size_bytes if latest else None),
    )


def _version_review_summary(version: BenchmarkVersion) -> VersionReviewSummary:
    return VersionReviewSummary(
        id=version.id,
        version=version.version,
        contamination_status=version.contamination_status,
        artifact_sha256=version.artifact_sha256,
        artifact_size_bytes=version.artifact_size_bytes,
        num_examples=version.num_examples,
        license=version.license,
        paper_url=version.paper_url,
        github_url=version.github_url,
        created_at=version.created_at,
        released_at=version.released_at,
        submitter=version.submitter,
    )


def _base_benchmark_query(status: str, contamination: str | None) -> Select[tuple[Benchmark]]:
    """Return a SQLAlchemy select() for Benchmark with appropriate filters applied.

    status:
      "pending"  — unverified benchmarks (default)
      "verified" — already-verified benchmarks
      "all"      — no status filter

    contamination: optional filter on any version's contamination_status,
      e.g. "flagged", "contaminated", "pending".
    """
    latest = latest_version_projection()
    query = (
        select(
            Benchmark,
            latest.version,
            latest.contamination_status,
            latest.num_examples,
            latest.artifact_sha256,
            latest.artifact_size_bytes,
        )
        .options(
            load_only(
                Benchmark.id,
                Benchmark.slug,
                Benchmark.name,
                Benchmark.description,
                Benchmark.domain,
                Benchmark.task_type,
                Benchmark.is_verified,
                Benchmark.total_versions,
                Benchmark.total_citations,
                Benchmark.created_at,
                Benchmark.updated_at,
                Benchmark.review_note,
                Benchmark.reviewed_at,
                Benchmark.reviewed_by_id,
                Benchmark.submitter_id,
            ),
            selectinload(Benchmark.submitter)
            .load_only(User.id, User.username, User.display_name, User.affiliation, User.is_verified)
            .selectinload(User.identities),
            selectinload(Benchmark.reviewed_by).load_only(
                User.id, User.username, User.display_name, User.affiliation, User.is_verified
            ),
        )
        .order_by(Benchmark.created_at.asc())  # oldest first — fair review queue
    )

    if status == "pending":
        query = query.where(Benchmark.is_verified.is_(False))
    elif status == "verified":
        query = query.where(Benchmark.is_verified.is_(True))
    # "all" — no filter

    if contamination:
        # Filter to benchmarks that have at least one version with this status.
        query = query.where(
            Benchmark.id.in_(
                select(BenchmarkVersion.benchmark_id)
                .where(BenchmarkVersion.contamination_status == contamination)
                .distinct()
            )
        )

    return query


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=AdminStats)
async def admin_stats(session: SessionDep, _: AdminUser) -> AdminStats:
    """Summary counts for the admin dashboard."""
    total = (await session.scalar(select(func.count()).select_from(Benchmark))) or 0
    unverified = (
        await session.scalar(
            select(func.count()).select_from(Benchmark).where(Benchmark.is_verified.is_(False))
        )
    ) or 0
    verified = (
        await session.scalar(
            select(func.count()).select_from(Benchmark).where(Benchmark.is_verified.is_(True))
        )
    ) or 0
    pending_contamination = (
        await session.scalar(
            select(func.count())
            .select_from(BenchmarkVersion)
            .where(BenchmarkVersion.contamination_status == "pending")
        )
    ) or 0
    flagged_contamination = (
        await session.scalar(
            select(func.count())
            .select_from(BenchmarkVersion)
            .where(BenchmarkVersion.contamination_status.in_(["flagged", "contaminated"]))
        )
    ) or 0
    return AdminStats(
        total_benchmarks=total,
        unverified_count=unverified,
        verified_count=verified,
        contamination_pending_count=pending_contamination,
        contamination_flagged_count=flagged_contamination,
    )


@router.get("/review-queue", response_model=list[ReviewQueueItem])
async def review_queue(
    session: SessionDep,
    _: AdminUser,
    limit: AdminLimit = 50,
    status: Literal["pending", "verified", "all"] = "pending",
    contamination: str | None = Query(default=None),
) -> list[ReviewQueueItem]:
    """Return benchmarks awaiting or having received review.

    By default returns unverified (pending) benchmarks oldest-first so the
    longest-waiting submissions surface at the top of the queue.

    Query parameters
    ----------------
    status        pending | verified | all  (default: pending)
    contamination optional filter on any version's contamination_status
                  e.g. ?contamination=flagged shows only benchmarks that have
                  at least one version flagged for contamination
    limit         1-100 (default: 50)
    """
    query = _base_benchmark_query(status=status, contamination=contamination).limit(limit)
    rows = (await session.execute(query)).all()
    return [
        _review_queue_item(
            row[0],
            latest_version=row.latest_version,
            latest_contamination_status=row.latest_contamination_status,
            latest_num_examples=row.latest_num_examples,
            latest_artifact_sha256=row.latest_artifact_sha256,
            latest_artifact_size_bytes=row.latest_artifact_size_bytes,
        )
        for row in rows
    ]


@router.get("/benchmarks/{slug}/context", response_model=BenchmarkReviewContext)
async def benchmark_review_context(slug: str, session: SessionDep, _: AdminUser) -> BenchmarkReviewContext:
    """Full reviewer context for a single benchmark.

    Returns all versions (with integrity details and contamination status),
    submitter provenance (OAuth providers), and the complete audit trail for
    this benchmark.  Intended for the detail view a reviewer opens before
    making a verification decision.
    """
    benchmark = await session.scalar(
        select(Benchmark)
        .options(
            load_only(
                Benchmark.id,
                Benchmark.slug,
                Benchmark.name,
                Benchmark.description,
                Benchmark.domain,
                Benchmark.task_type,
                Benchmark.is_verified,
                Benchmark.total_versions,
                Benchmark.total_citations,
                Benchmark.created_at,
                Benchmark.updated_at,
                Benchmark.review_note,
                Benchmark.reviewed_at,
                Benchmark.reviewed_by_id,
                Benchmark.submitter_id,
            ),
            selectinload(Benchmark.submitter)
            .load_only(User.id, User.username, User.display_name, User.affiliation, User.is_verified)
            .selectinload(User.identities),
            selectinload(Benchmark.reviewed_by).load_only(
                User.id, User.username, User.display_name, User.affiliation, User.is_verified
            ),
            selectinload(Benchmark.versions)
            .load_only(
                BenchmarkVersion.id,
                BenchmarkVersion.version,
                BenchmarkVersion.contamination_status,
                BenchmarkVersion.artifact_sha256,
                BenchmarkVersion.artifact_size_bytes,
                BenchmarkVersion.num_examples,
                BenchmarkVersion.license,
                BenchmarkVersion.paper_url,
                BenchmarkVersion.github_url,
                BenchmarkVersion.created_at,
                BenchmarkVersion.released_at,
                BenchmarkVersion.submitter_id,
            )
            .selectinload(BenchmarkVersion.submitter)
            .load_only(User.id, User.username, User.display_name, User.affiliation, User.is_verified),
            selectinload(Benchmark.audit_events)
            .load_only(
                AuditEvent.id,
                AuditEvent.action,
                AuditEvent.resource_type,
                AuditEvent.resource_id,
                AuditEvent.resource_slug,
                AuditEvent.summary,
                AuditEvent.metadata_json,
                AuditEvent.created_at,
                AuditEvent.actor_user_id,
            )
            .selectinload(AuditEvent.actor)
            .load_only(User.id, User.username, User.display_name, User.affiliation, User.is_verified),
        )
        .where(Benchmark.slug == slug)
    )
    if benchmark is None:
        raise AppError("benchmark_not_found", "Benchmark not found", status_code=404)

    item = _review_queue_item(benchmark)
    # Versions are already ordered created_at DESC by the relationship.
    versions = [_version_review_summary(v) for v in benchmark.versions]
    audit_history = [
        AuditEventResponse.model_validate(e)
        for e in sorted(benchmark.audit_events, key=lambda e: e.created_at, reverse=True)
    ]
    return BenchmarkReviewContext(
        **item.model_dump(),
        versions=versions,
        audit_history=audit_history,
    )


@router.get("/audit-events", response_model=list[AuditEventResponse])
async def recent_audit_events(
    session: SessionDep,
    _: AdminUser,
    limit: AdminLimit = 100,
    action: str | None = Query(default=None, description="Filter by action, e.g. benchmark.verified"),
    resource_type: str | None = Query(default=None, description="Filter by resource_type, e.g. benchmark"),
    benchmark_slug: str | None = Query(default=None, description="Filter events to a specific benchmark slug"),
) -> list[AuditEventResponse]:
    """Recent admin audit events, optionally filtered by action or resource type."""
    query = (
        select(AuditEvent)
        .options(
            load_only(
                AuditEvent.id,
                AuditEvent.action,
                AuditEvent.resource_type,
                AuditEvent.resource_id,
                AuditEvent.resource_slug,
                AuditEvent.summary,
                AuditEvent.metadata_json,
                AuditEvent.created_at,
                AuditEvent.actor_user_id,
            ),
            selectinload(AuditEvent.actor).load_only(
                User.id, User.username, User.display_name, User.affiliation, User.is_verified
            ),
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )
    if action:
        query = query.where(AuditEvent.action == action)
    if resource_type:
        query = query.where(AuditEvent.resource_type == resource_type)
    if benchmark_slug:
        query = query.where(AuditEvent.resource_slug == benchmark_slug)

    events = list((await session.scalars(query)).all())
    return [AuditEventResponse.model_validate(e) for e in events]


@router.patch("/benchmarks/{slug}/verification", response_model=BenchmarkVerificationResponse)
async def set_benchmark_verification(
    slug: str,
    payload: BenchmarkVerificationRequest,
    session: SessionDep,
    current_user: AdminUser,
) -> BenchmarkVerificationResponse:
    """Verify or unverify a benchmark.

    If a note is supplied it is persisted on the benchmark record itself
    (review_note / reviewed_at / reviewed_by_id) for quick UI display, and
    also recorded in the audit trail metadata.
    """
    benchmark = await session.scalar(
        select(Benchmark)
        .options(
            selectinload(Benchmark.submitter).selectinload(User.identities),
            selectinload(Benchmark.reviewed_by),
            selectinload(Benchmark.versions),
        )
        .where(Benchmark.slug == slug)
    )
    if benchmark is None:
        raise AppError("benchmark_not_found", "Benchmark not found", status_code=404)

    benchmark.is_verified = payload.verified
    if payload.note:
        benchmark.review_note = payload.note
    benchmark.reviewed_at = datetime.now(UTC)
    benchmark.reviewed_by_id = current_user.id
    await session.flush()

    action = "benchmark.verified" if payload.verified else "benchmark.unverified"
    summary = payload.note or (
        "Marked benchmark as verified" if payload.verified else "Removed benchmark verification"
    )
    await record_audit_event(
        session,
        action=action,
        actor=current_user,
        benchmark=benchmark,
        resource_type="benchmark",
        resource_id=str(benchmark.id),
        resource_slug=benchmark.slug,
        summary=summary,
        metadata={"verified": payload.verified, "note": payload.note},
    )
    await session.commit()
    await session.refresh(benchmark)

    _admin_logger.info(
        action,
        extra={
            "benchmark_slug": slug,
            "verified": payload.verified,
            "reviewer_id": str(current_user.id),
            "has_note": payload.note is not None,
        },
    )
    return BenchmarkVerificationResponse(benchmark=_review_queue_item(benchmark))


@router.post("/benchmarks/{slug}/notes", response_model=BenchmarkVerificationResponse)
async def add_review_note(
    slug: str,
    payload: ReviewNoteRequest,
    session: SessionDep,
    current_user: AdminUser,
) -> BenchmarkVerificationResponse:
    """Add a reviewer note to a benchmark without changing its verification status.

    Useful for recording observations mid-review — e.g. "waiting for submitter
    to clarify dataset license" — without committing to a final decision.
    The note is stored on the benchmark record and in the audit trail.
    """
    benchmark = await session.scalar(
        select(Benchmark)
        .options(
            selectinload(Benchmark.submitter).selectinload(User.identities),
            selectinload(Benchmark.reviewed_by),
            selectinload(Benchmark.versions),
        )
        .where(Benchmark.slug == slug)
    )
    if benchmark is None:
        raise AppError("benchmark_not_found", "Benchmark not found", status_code=404)

    benchmark.review_note = payload.note
    benchmark.reviewed_at = datetime.now(UTC)
    benchmark.reviewed_by_id = current_user.id
    await session.flush()

    await record_audit_event(
        session,
        action="benchmark.review_note",
        actor=current_user,
        benchmark=benchmark,
        resource_type="benchmark",
        resource_id=str(benchmark.id),
        resource_slug=benchmark.slug,
        summary=payload.note,
        metadata={"note": payload.note},
    )
    await session.commit()
    await session.refresh(benchmark)

    _admin_logger.info(
        "benchmark.review_note",
        extra={"benchmark_slug": slug, "reviewer_id": str(current_user.id)},
    )
    return BenchmarkVerificationResponse(benchmark=_review_queue_item(benchmark))
