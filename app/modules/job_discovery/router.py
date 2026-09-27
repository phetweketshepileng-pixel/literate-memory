"""Job Discovery / Hidden Gems router (Modules 2 & 3)."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Job, JobMatch, Profile
from app.modules.job_discovery.ranking import RankableJob, rank_search_results

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/search")
async def search_jobs(
    title: str | None = None,
    industry: str | None = None,
    salary_min: int | None = None,
    location: str | None = None,
    remote: bool | None = None,
    date_posted_after: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    query = select(Job).where(Job.is_active.is_(True))
    if title:
        query = query.where(or_(Job.title.ilike(f"%{title}%"), Job.company.ilike(f"%{title}%")))
    if location:
        query = query.where(Job.location.ilike(f"%{location}%"))
    if remote is not None:
        query = query.where(Job.is_remote.is_(remote))
    if salary_min is not None:
        query = query.where(Job.salary_max >= salary_min)
    if date_posted_after is not None:
        query = query.where(Job.date_posted >= date_posted_after)
    if industry:
        # industry lives on the profile/company side, not a jobs column in
        # V1.1 — filtered here via company/description match as a proxy
        # until a normalized `jobs.industry` column lands (see roadmap).
        query = query.where(Job.description.ilike(f"%{industry}%"))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = (
        query.order_by(Job.date_posted.desc().nulls_last(), Job.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    jobs = (await db.execute(query)).scalars().all()

    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    match_rows = (
        await db.execute(
            select(JobMatch).where(
                JobMatch.profile_id == profile.id, JobMatch.job_id.in_([j.id for j in jobs])
            )
        )
    ).scalars().all()
    match_by_job = {m.job_id: m.match_score for m in match_rows}

    rankable = [
        RankableJob(
            job_id=str(job.id),
            match_score=match_by_job.get(job.id, 0),
            date_posted=job.date_posted,
            is_hidden_gem=job.is_hidden_gem,
            has_salary=job.salary_min is not None or job.salary_max is not None,
            description_length=len(job.description or ""),
        )
        for job in jobs
    ]
    ranked_ids = [r.job_id for r in rank_search_results(rankable)]
    jobs_by_id = {str(j.id): j for j in jobs}
    ordered_jobs = [jobs_by_id[jid] for jid in ranked_ids]

    return {
        "data": [_job_summary(job, match_by_job.get(job.id, 0)) for job in ordered_jobs],
        "meta": {"page": page, "page_size": page_size, "total": total},
        "error": None,
    }


@router.get("/hidden-gems")
async def hidden_gems(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    jobs = (
        await db.execute(
            select(Job).where(Job.is_hidden_gem.is_(True), Job.is_active.is_(True)).limit(50)
        )
    ).scalars().all()
    return {"data": [_job_summary(job, 0) for job in jobs], "meta": {}, "error": None}


@router.get("/{job_id}")
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Job not found"})
    return {"data": _job_detail(job), "meta": {}, "error": None}


def _job_summary(job: Job, match_score: int) -> dict:
    return {
        "id": str(job.id),
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "is_remote": job.is_remote,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "apply_url": job.apply_url,
        "date_posted": job.date_posted.isoformat() if job.date_posted else None,
        "is_hidden_gem": job.is_hidden_gem,
        "competition_score": job.competition_score,
        "match_score": match_score,
    }


def _job_detail(job: Job) -> dict:
    return {**_job_summary(job, 0), "description": job.description}
