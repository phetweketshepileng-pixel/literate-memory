"""Analytics router (Module 9). Reads exclusively from analytics_snapshots
— per ai-job-hunter-db-schema-v1.1.md section 8, the dashboard never runs
a live aggregate against applications/application_stage_history. Snapshot
materialization (nightly Celery beat job, calling compute_rates_from_history
from app.modules.analytics.service) lives in app/workers/analytics_tasks.py,
not here."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import AnalyticsSnapshot, Profile

router = APIRouter(prefix="/analytics", tags=["analytics"])

PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90}


@router.get("/summary")
async def analytics_summary(
    period: str = Query(default="30d"),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    days = PERIOD_DAYS.get(period, 30)
    since = date.today() - timedelta(days=days)

    snapshots = (
        await db.execute(
            select(AnalyticsSnapshot).where(
                AnalyticsSnapshot.profile_id == profile.id, AnalyticsSnapshot.period_start >= since
            )
        )
    ).scalars().all()

    if not snapshots:
        return {
            "data": {
                "applications_submitted": 0, "interviews": 0, "offers": 0,
                "response_rate": None, "interview_rate": None, "offer_rate": None,
                "avg_time_to_response_days": None,
            },
            "meta": {"period": period, "note": "No analytics computed yet — snapshots refresh nightly."},
            "error": None,
        }

    latest = max(snapshots, key=lambda s: s.period_end)
    return {
        "data": {
            "applications_submitted": latest.applications_submitted,
            "interviews": latest.interviews,
            "offers": latest.offers,
            "response_rate": float(latest.response_rate) if latest.response_rate is not None else None,
            "interview_rate": float(latest.interview_rate) if latest.interview_rate is not None else None,
            "offer_rate": float(latest.offer_rate) if latest.offer_rate is not None else None,
            "avg_time_to_response_days": float(latest.avg_time_to_response_days)
            if latest.avg_time_to_response_days is not None else None,
        },
        "meta": {"period": period},
        "error": None,
    }


@router.get("/by-source")
async def analytics_by_source(
    period: str = Query(default="30d"),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    latest = await _latest_snapshot(db, user_id, period)
    return {"data": latest.breakdown_by_source if latest else {}, "meta": {"period": period}, "error": None}


@router.get("/by-role")
async def analytics_by_role(
    period: str = Query(default="30d"),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    latest = await _latest_snapshot(db, user_id, period)
    return {"data": latest.breakdown_by_role if latest else {}, "meta": {"period": period}, "error": None}


@router.get("/trends")
async def analytics_trends(
    period: str = Query(default="90d"),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    days = PERIOD_DAYS.get(period, 90)
    since = date.today() - timedelta(days=days)

    snapshots = (
        await db.execute(
            select(AnalyticsSnapshot)
            .where(AnalyticsSnapshot.profile_id == profile.id, AnalyticsSnapshot.period_start >= since)
            .order_by(AnalyticsSnapshot.period_start)
        )
    ).scalars().all()

    return {
        "data": [
            {
                "period_start": s.period_start.isoformat(),
                "applications_submitted": s.applications_submitted,
                "interviews": s.interviews,
                "response_rate": float(s.response_rate) if s.response_rate is not None else None,
            }
            for s in snapshots
        ],
        "meta": {"period": period},
        "error": None,
    }


async def _latest_snapshot(db: AsyncSession, user_id: UUID, period: str) -> AnalyticsSnapshot | None:
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    days = PERIOD_DAYS.get(period, 30)
    since = date.today() - timedelta(days=days)
    snapshots = (
        await db.execute(
            select(AnalyticsSnapshot).where(
                AnalyticsSnapshot.profile_id == profile.id, AnalyticsSnapshot.period_start >= since
            )
        )
    ).scalars().all()
    return max(snapshots, key=lambda s: s.period_end) if snapshots else None
