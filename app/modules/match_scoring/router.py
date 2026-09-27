"""Match Scoring router (Module 4)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Job, JobMatch, Profile
from app.workers.match_scoring_tasks import score_job_for_profile

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("/score", status_code=202)
async def request_score(
    job_id: UUID, user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Job not found"})

    task = score_job_for_profile.delay(str(profile.id), str(job_id))
    return {"data": {"task_id": task.id}, "meta": {}, "error": None}


@router.get("")
async def list_matches(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    matches = (
        await db.execute(
            select(JobMatch).where(JobMatch.profile_id == profile.id).order_by(JobMatch.match_score.desc())
        )
    ).scalars().all()
    return {
        "data": [_match_summary(m) for m in matches],
        "meta": {"total": len(matches)},
        "error": None,
    }


@router.get("/{job_id}")
async def get_match_detail(
    job_id: UUID, user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    match = (
        await db.execute(
            select(JobMatch).where(JobMatch.profile_id == profile.id, JobMatch.job_id == job_id)
        )
    ).scalar_one_or_none()
    if match is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "No match computed for this job yet"},
        )
    return {"data": _match_detail(match), "meta": {}, "error": None}


def _match_summary(match: JobMatch) -> dict:
    return {"job_id": str(match.job_id), "match_score": match.match_score, "scored_at": match.scored_at.isoformat()}


def _match_detail(match: JobMatch) -> dict:
    return {
        **_match_summary(match),
        "strengths": match.strengths or [],
        "missing_skills": match.missing_skills or [],
        "experience_gaps": match.experience_gaps or [],
        "recommendations": match.recommendations or [],
    }
