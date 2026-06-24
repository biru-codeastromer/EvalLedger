"""Trust-and-safety: abuse/takedown reports and the admin moderation queue."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from app.dependencies import AdminUser, CurrentUser, SessionDep
from app.errors import AppError
from app.models.report import AbuseReport
from app.ratelimit import RateLimit
from app.schemas.report import ReportCreateRequest, ReportResolveRequest, ReportResponse
from app.services.audit import record_audit_event

router = APIRouter()

_report_logger = logging.getLogger("evalledger.reports")
_report_create_rl = Depends(RateLimit("report_create", anon_limit=10, auth_limit=10))


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: ReportCreateRequest,
    session: SessionDep,
    current_user: CurrentUser,
    _rl: Annotated[None, _report_create_rl] = None,
) -> ReportResponse:
    """File a report against a public benchmark or version (authenticated)."""
    report = AbuseReport(
        reporter_user_id=current_user.id,
        resource_type=payload.resource_type,
        resource_slug=payload.resource_slug,
        reason=payload.reason,
        detail=payload.detail,
        status="open",
    )
    session.add(report)
    await session.flush()
    await record_audit_event(
        session,
        action="report.created",
        actor=current_user,
        resource_type=payload.resource_type,
        resource_id=str(report.id),
        resource_slug=payload.resource_slug,
        summary=f"Reported {payload.resource_type} {payload.resource_slug} ({payload.reason})",
    )
    await session.commit()
    await session.refresh(report)
    _report_logger.info(
        "report.created",
        extra={"report_id": str(report.id), "reason": payload.reason, "resource": payload.resource_slug},
    )
    return ReportResponse.model_validate(report)


@router.get("", response_model=list[ReportResponse])
async def list_reports(
    session: SessionDep,
    _admin: AdminUser,
    status_filter: Annotated[str, Query(alias="status")] = "open",
) -> list[ReportResponse]:
    """List moderation reports, newest first (admin only)."""
    statement = select(AbuseReport).order_by(AbuseReport.created_at.desc())
    if status_filter != "all":
        statement = statement.where(AbuseReport.status == status_filter)
    reports = list((await session.scalars(statement)).all())
    return [ReportResponse.model_validate(item) for item in reports]


@router.patch("/{report_id}", response_model=ReportResponse)
async def resolve_report(
    report_id: str,
    payload: ReportResolveRequest,
    session: SessionDep,
    admin: AdminUser,
) -> ReportResponse:
    """Action or dismiss a report (admin only)."""
    report = await session.scalar(select(AbuseReport).where(AbuseReport.id == report_id))
    if report is None:
        raise AppError("report_not_found", "Report does not exist", status_code=404)
    report.status = payload.status
    report.resolution_note = payload.resolution_note
    report.resolver_user_id = admin.id
    report.resolved_at = datetime.now(UTC) if payload.status in ("actioned", "dismissed") else None
    await record_audit_event(
        session,
        action="report.updated",
        actor=admin,
        resource_type=report.resource_type,
        resource_id=str(report.id),
        resource_slug=report.resource_slug,
        summary=f"Report {report.id} marked {payload.status}",
    )
    await session.commit()
    await session.refresh(report)
    return ReportResponse.model_validate(report)
