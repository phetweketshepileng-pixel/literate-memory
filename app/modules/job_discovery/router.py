"""Job Discovery / Hidden Gems router (Modules 2 & 3)."""
from __future__ import annotations

import re
import time
from collections import Counter
from datetime import UTC, date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Application, Job, JobMatch, JobSource, Profile, Skill
from app.modules.job_discovery.insights import FitInput, quick_fit, region_bucket
from app.modules.job_discovery.search_helpers import (
    JobRow,
    collapse_duplicates,
    group_key,
    keyword_suggestions,
    location_suggestions,
    location_terms,
)
from app.modules.profile.cv_parsing import SKILL_VOCABULARY
from app.modules.job_discovery.ranking import RankableJob, rank_search_results

router = APIRouter(prefix="/jobs", tags=["jobs"])


_KEYWORD_WORD = re.compile(r"[\w+#.]{2,}")


def _search_filters(q, title, location, remote, salary_min, include_no_salary, posted_within_days):
    """WHERE clauses shared by search and its count. Every keyword must appear
    in the title, company or description; location expands provinces/cities."""
    conds = [Job.is_active.is_(True)]
    for word in _KEYWORD_WORD.findall(f"{q or ''} {title or ''}"):
        like = f"%{word}%"
        conds.append(or_(Job.title.ilike(like), Job.company.ilike(like), Job.description.ilike(like)))
    if location:
        terms, loc_remote = location_terms(location)
        ors = [Job.location.ilike(f"%{t}%") for t in terms]
        if loc_remote:
            ors.append(Job.is_remote.is_(True))
        conds.append(or_(*ors))
    if remote is not None:
        conds.append(Job.is_remote.is_(remote))
    if salary_min is not None:
        shows = or_(Job.salary_max >= salary_min, and_(Job.salary_max.is_(None), Job.salary_min >= salary_min))
        if include_no_salary:
            conds.append(or_(shows, and_(Job.salary_min.is_(None), Job.salary_max.is_(None))))
        else:
            conds.append(shows)
    if posted_within_days:
        since = datetime.now(_SAST).date() - timedelta(days=posted_within_days)
        conds.append(or_(Job.date_posted >= since, and_(Job.date_posted.is_(None), Job.created_at >= datetime.now(UTC) - timedelta(days=posted_within_days))))
    return conds


@router.get("/search")
async def search_jobs(
    q: str | None = None,
    title: str | None = None,
    industry: str | None = None,
    salary_min: int | None = None,
    include_no_salary: bool = True,
    location: str | None = None,
    remote: bool | None = None,
    posted_within_days: int | None = Query(default=None, ge=1, le=90),
    date_posted_after: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    conds = _search_filters(q, title, location, remote, salary_min, include_no_salary, posted_within_days)
    if date_posted_after is not None:
        conds.append(Job.date_posted >= date_posted_after)
    if industry:
        # no jobs.industry column yet: description match as a proxy
        conds.append(Job.description.ilike(f"%{industry}%"))

    # Light first pass over every match, so the same job posted in several
    # locations becomes ONE result (with "also in ...") before paginating.
    light = (
        await db.execute(
            select(Job.id, Job.title, Job.company, Job.location)
            .where(*conds)
            .order_by(Job.date_posted.desc().nulls_last(), Job.created_at.desc())
            .limit(5000)
        )
    ).all()
    groups = collapse_duplicates(light, key=lambda r: group_key(r.title, r.company), location=lambda r: r.location)
    total = len(groups)
    page_groups = groups[(page - 1) * page_size: page * page_size]
    also = {g.first.id: g.other_locations for g in page_groups}
    ids = [g.first.id for g in page_groups]
    jobs = (await db.execute(select(Job).where(Job.id.in_(ids)))).scalars().all() if ids else []

    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    match_rows = (
        await db.execute(
            select(JobMatch).where(
                JobMatch.profile_id == profile.id, JobMatch.job_id.in_([j.id for j in jobs])
            )
        )
    ).scalars().all() if jobs else []
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
        "data": [
            {**_job_summary(job, match_by_job.get(job.id, 0)), "also_in": also.get(job.id, [])}
            for job in ordered_jobs
        ],
        "meta": {"page": page, "page_size": page_size, "total": total, "postings": len(light)},
        "error": None,
    }


# Type-ahead reads every active job's title/company/location; cache that for
# a few minutes so typing stays instant (the feed only changes every 6 hours).
_SUGGEST_CACHE: dict[str, object] = {"at": 0.0, "rows": []}
_SUGGEST_TTL = 300


async def _suggest_rows(db: AsyncSession) -> list[JobRow]:
    if time.monotonic() - _SUGGEST_CACHE["at"] < _SUGGEST_TTL and _SUGGEST_CACHE["rows"]:
        return _SUGGEST_CACHE["rows"]
    result = await db.execute(
        select(Job.title, Job.company, Job.location, Job.is_remote, func.left(Job.description, 4000))
        .where(Job.is_active.is_(True))
    )
    rows = [
        JobRow(t or "", c, l, bool(r), f"{(t or '').lower()} {(d or '').lower()}")
        for t, c, l, r, d in result.all()
    ]
    _SUGGEST_CACHE.update(at=time.monotonic(), rows=rows)
    return rows


@router.get("/suggest")
async def suggest(
    kind: str = Query(pattern="^(keyword|location)$"),
    q: str = Query(default="", max_length=80),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Type-ahead options for the Job Search boxes, each with how many jobs it finds."""
    rows = await _suggest_rows(db)
    if kind == "keyword":
        items = keyword_suggestions(q, rows, list(SKILL_VOCABULARY))
    else:
        items = location_suggestions(q, rows)
    return {"data": [i.as_dict() for i in items], "meta": {}, "error": None}


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


# South Africa Standard Time — "today" on the dashboard means the user's day
_SAST = timezone(timedelta(hours=2))


def _source_group(source_name: str | None) -> str:
    name = source_name or ""
    if name.startswith("Adzuna"):
        return "SA job boards (via Adzuna)"
    if name:
        return "International remote boards"
    return "Other"


@router.get("/stats")
async def job_stats(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    """Feed overview for the dashboard: how many jobs, how fresh, where from."""
    rows = (
        await db.execute(
            select(Job.created_at, Job.location, Job.is_remote, Job.is_hidden_gem, JobSource.name)
            .join(JobSource, JobSource.id == Job.source_id, isouter=True)
            .where(Job.is_active.is_(True))
        )
    ).all()
    today = datetime.now(_SAST).date()
    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    per_day = Counter()
    regions, sources = Counter(), Counter()
    new_today = new_week = gems = 0
    for created_at, location, is_remote, is_gem, source_name in rows:
        d = created_at.astimezone(_SAST).date() if created_at else None
        if d:
            per_day[d] += 1
            new_today += d == today
            new_week += (today - d).days < 7
        regions[region_bucket(location, bool(is_remote))] += 1
        sources[_source_group(source_name)] += 1
        gems += bool(is_gem)
    return {
        "data": {
            "total_active": len(rows),
            "new_today": new_today,
            "new_this_week": new_week,
            "hidden_gems": gems,
            "added_per_day": [{"date": d.isoformat(), "count": per_day.get(d, 0)} for d in days],
            "by_region": [{"label": k, "count": v} for k, v in regions.most_common()],
            "by_source": [{"label": k, "count": v} for k, v in sources.most_common()],
        },
        "meta": {"timezone": "Africa/Johannesburg"},
        "error": None,
    }


@router.get("/recommended")
async def recommended_jobs(
    limit: int = Query(default=6, ge=1, le=30),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Top matches for the dashboard, ranked by the rule-based quick-fit score
    (see insights.quick_fit). Jobs already in the user's pipeline are left out."""
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    skills = list((await db.execute(select(Skill.name).where(Skill.profile_id == profile.id))).scalars())
    desired = list(profile.desired_roles or [])
    if profile.current_role and not desired:
        desired = [profile.current_role]
    prefs = FitInput(
        desired_roles=desired,
        skills=skills,
        location_preferences=list(profile.location_preferences or []),
        work_mode_preference=profile.work_mode_preference,
        today=datetime.now(_SAST).date(),
    )
    if not prefs.desired_roles and not prefs.skills:
        return {"data": [], "meta": {"reason": "no_preferences"}, "error": None}

    in_pipeline = set(
        (await db.execute(select(Application.job_id).where(Application.profile_id == profile.id))).scalars()
    )
    cutoff = prefs.today - timedelta(days=45)
    jobs = (
        await db.execute(
            select(Job)
            .where(Job.is_active.is_(True), or_(Job.date_posted.is_(None), Job.date_posted >= cutoff))
            .order_by(Job.date_posted.desc().nulls_last())
            .limit(5000)
        )
    ).scalars().all()

    scored = []
    for job in jobs:
        if job.id in in_pipeline:
            continue
        fit = quick_fit(job.title, job.description, job.location, job.is_remote, job.date_posted, prefs)
        if fit.score >= 30:
            scored.append((fit.score, job.date_posted or date.min, job, fit))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    # one card per job: the same ad posted for several suburbs collapses into
    # its best-scoring copy, with the other locations listed underneath
    groups = collapse_duplicates(scored, key=lambda t: group_key(t[2].title, t[2].company), location=lambda t: t[2].location)
    return {
        "data": [
            {**_job_summary(g.first[2], 0), "fit_score": g.first[3].score, "fit_reasons": g.first[3].reasons,
             "also_in": g.other_locations}
            for g in groups[:limit]
        ],
        "meta": {"candidates": len(groups)},
        "error": None,
    }


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
        "via": "adzuna" if "adzuna." in (job.apply_url or "") else None,
    }


def _job_detail(job: Job) -> dict:
    return {**_job_summary(job, 0), "description": job.description}
