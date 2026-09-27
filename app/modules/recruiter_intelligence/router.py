"""Recruiter Intelligence Dashboard router. Reads exclusively from
recruiter_intelligence_snapshots / company_intelligence_snapshots — like
every other analytics-shaped endpoint in this platform, never a live
cross-user aggregate on request (and especially not here, where the
k-anonymity gate has to run in a controlled batch job, not on demand)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import CompanyIntelligenceSnapshot, Profile, Recruiter, RecruiterIntelligenceSnapshot

router = APIRouter(prefix="/recruiter-intelligence", tags=["recruiter-intelligence"])


class PooledAnalyticsConsent(BaseModel):
    contributes_to_pooled_analytics: bool


@router.put("/settings/pooled-analytics-consent")
async def set_pooled_analytics_consent(
    payload: PooledAnalyticsConsent,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    profile.contributes_to_pooled_analytics = payload.contributes_to_pooled_analytics
    await db.commit()
    return {"data": {"contributes_to_pooled_analytics": profile.contributes_to_pooled_analytics}, "meta": {}, "error": None}


@router.get("/recruiters")
async def list_recruiter_intelligence(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(RecruiterIntelligenceSnapshot, Recruiter)
            .join(Recruiter, Recruiter.id == RecruiterIntelligenceSnapshot.recruiter_id)
            .order_by(RecruiterIntelligenceSnapshot.period_start.desc())
        )
    ).all()

    return {
        "data": [_recruiter_summary(snapshot, recruiter) for snapshot, recruiter in rows],
        "meta": {},
        "error": None,
    }


@router.get("/companies")
async def list_company_intelligence(
    source_domain: str | None = None, db: AsyncSession = Depends(get_db)
):
    rows = (
        await db.execute(
            select(CompanyIntelligenceSnapshot).order_by(CompanyIntelligenceSnapshot.period_start.desc())
        )
    ).scalars().all()

    results = []
    for snapshot in rows:
        entry = _company_summary(snapshot)
        if source_domain:
            breakdown = snapshot.interview_rate_by_source_domain or {}
            if source_domain not in breakdown:
                continue  # segment didn't clear the k-anonymity threshold — omit, don't show as zero
            entry["interview_rate_for_your_background"] = breakdown[source_domain]
        results.append(entry)

    if source_domain:
        results.sort(key=lambda e: e.get("interview_rate_for_your_background", 0), reverse=True)

    return {"data": results, "meta": {"source_domain": source_domain}, "error": None}


@router.get("/companies/{company_name}")
async def get_company_intelligence(company_name: str, db: AsyncSession = Depends(get_db)):
    snapshot = (
        await db.execute(
            select(CompanyIntelligenceSnapshot)
            .where(CompanyIntelligenceSnapshot.company_name == company_name)
            .order_by(CompanyIntelligenceSnapshot.period_start.desc())
        )
    ).scalars().first()

    if snapshot is None:
        return {"data": None, "meta": {"note": "No intelligence data yet for this company."}, "error": None}

    return {"data": _company_summary(snapshot), "meta": {}, "error": None}


def _recruiter_summary(snapshot: RecruiterIntelligenceSnapshot, recruiter: Recruiter) -> dict:
    return {
        "recruiter_id": str(recruiter.id),
        "recruiter_name": recruiter.name,
        "company": recruiter.company,
        "postings_count": snapshot.postings_count,
        "contributing_user_count": snapshot.contributing_user_count,
        "response_rate": float(snapshot.response_rate) if snapshot.response_rate is not None else None,
        "avg_hours_to_first_response": float(snapshot.avg_hours_to_first_response)
        if snapshot.avg_hours_to_first_response is not None else None,
        "insufficient_data": snapshot.response_rate is None,
    }


def _company_summary(snapshot: CompanyIntelligenceSnapshot) -> dict:
    return {
        "company_name": snapshot.company_name,
        "contributing_user_count": snapshot.contributing_user_count,
        "avg_turnaround_days": float(snapshot.avg_turnaround_days) if snapshot.avg_turnaround_days is not None else None,
        "interview_rate_overall": float(snapshot.interview_rate_overall)
        if snapshot.interview_rate_overall is not None else None,
        "insufficient_data": snapshot.interview_rate_overall is None,
    }
