"""Weekly recruiter/company intelligence materialization — uses the SAME
compute_recruiter_aggregate / compute_company_aggregate functions verified
in tests/test_recruiter_intelligence_service.py. This is deliberately a
thin wrapper: all the privacy-critical logic lives in the tested service
module, never duplicated here."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models import (
    Application,
    ApplicationStageHistory,
    CompanyIntelligenceSnapshot,
    Email,
    Job,
    Message,
    Profile,
    Recruiter,
    RecruiterIntelligenceSnapshot,
)
from app.modules.job_discovery.canonicalization import canonicalize_company
from app.modules.recruiter_intelligence.service import (
    ApplicationRecord,
    EmailRecord,
    compute_company_aggregate,
    compute_recruiter_aggregate,
)

logger = logging.getLogger(__name__)

SNAPSHOT_WINDOW_DAYS = 90  # longer window than daily analytics — recruiter/
                            # company behavior is a slower-moving signal


@celery_app.task(name="recruiter_intelligence.materialize_all", queue="default")
def materialize_all() -> dict:
    import asyncio

    return asyncio.run(_materialize_all_async())


async def _materialize_all_async() -> dict:
    async with AsyncSessionLocal() as db:
        recruiter_count = await _materialize_recruiters(db)
        company_count = await _materialize_companies(db)
        return {"recruiters_processed": recruiter_count, "companies_processed": company_count}


async def _consenting_profile_ids(db) -> set:
    rows = (
        await db.execute(select(Profile.id).where(Profile.contributes_to_pooled_analytics.is_(True)))
    ).scalars().all()
    return set(rows)


async def _materialize_recruiters(db) -> int:
    """Groups emails by recruiter, filtered to consenting profiles only,
    per ai-job-hunter-recruiter-intelligence.md section 2 — consent is
    enforced HERE, at the data-loading boundary, before anything reaches
    the aggregation service (which has no knowledge of consent by design)."""
    period_end = date.today()
    period_start = period_end - timedelta(days=SNAPSHOT_WINDOW_DAYS)
    consenting = await _consenting_profile_ids(db)
    if not consenting:
        return 0

    recruiters = (await db.execute(select(Recruiter))).scalars().all()
    processed = 0

    for recruiter in recruiters:
        rows = (
            await db.execute(
                select(Email, Message)
                .join(Message, Message.id == Email.message_id)
                .where(
                    Message.recruiter_id == recruiter.id,
                    Message.profile_id.in_(consenting),
                    Email.sent_at >= period_start,
                )
            )
        ).all()
        if not rows:
            continue

        email_records = [
            EmailRecord(
                profile_id=str(message.profile_id),
                recruiter_id=str(recruiter.id),
                sent_at=email.sent_at,
                first_response_at=email.replied_at,
            )
            for email, message in rows
            if email.sent_at is not None
        ]
        aggregate = compute_recruiter_aggregate(email_records)

        existing = (
            await db.execute(
                select(RecruiterIntelligenceSnapshot).where(
                    RecruiterIntelligenceSnapshot.recruiter_id == recruiter.id,
                    RecruiterIntelligenceSnapshot.period_start == period_start,
                    RecruiterIntelligenceSnapshot.period_end == period_end,
                )
            )
        ).scalar_one_or_none()

        if existing is None:
            existing = RecruiterIntelligenceSnapshot(
                recruiter_id=recruiter.id, period_start=period_start, period_end=period_end
            )
            db.add(existing)

        existing.contributing_user_count = aggregate.contributing_user_count
        existing.response_rate = aggregate.response_rate
        existing.avg_hours_to_first_response = aggregate.avg_hours_to_first_response
        processed += 1

    await db.commit()
    return processed


async def _materialize_companies(db) -> int:
    period_end = date.today()
    period_start = period_end - timedelta(days=SNAPSHOT_WINDOW_DAYS)
    consenting = await _consenting_profile_ids(db)
    if not consenting:
        return 0

    applications = (
        await db.execute(
            select(Application).where(
                Application.profile_id.in_(consenting), Application.applied_at >= period_start
            )
        )
    ).scalars().all()

    by_company: dict[str, list[ApplicationRecord]] = {}
    for app in applications:
        job = (await db.execute(select(Job).where(Job.id == app.job_id))).scalar_one_or_none()
        if job is None or not job.company:
            continue
        canonical_company = canonicalize_company(job.company)

        profile = (await db.execute(select(Profile).where(Profile.id == app.profile_id))).scalar_one()
        source_domain = profile.primary_source_domain

        history = (
            await db.execute(
                select(ApplicationStageHistory)
                .where(ApplicationStageHistory.application_id == app.id)
                .order_by(ApplicationStageHistory.changed_at)
            )
        ).scalars().all()
        reached_interview = any(h.to_stage in ("interview", "assessment", "offer") for h in history)
        resolved_at = next(
            (h.changed_at for h in history if h.to_stage in ("offer", "rejected")), None
        )

        by_company.setdefault(canonical_company, []).append(
            ApplicationRecord(
                profile_id=str(app.profile_id),
                company_name=canonical_company,
                source_domain=source_domain,
                submitted_at=app.applied_at,
                resolved_at=resolved_at,
                reached_interview=reached_interview,
            )
        )

    processed = 0
    for company_name, records in by_company.items():
        aggregate = compute_company_aggregate(records)

        existing = (
            await db.execute(
                select(CompanyIntelligenceSnapshot).where(
                    CompanyIntelligenceSnapshot.company_name == company_name,
                    CompanyIntelligenceSnapshot.period_start == period_start,
                    CompanyIntelligenceSnapshot.period_end == period_end,
                )
            )
        ).scalar_one_or_none()

        if existing is None:
            existing = CompanyIntelligenceSnapshot(
                company_name=company_name, period_start=period_start, period_end=period_end
            )
            db.add(existing)

        existing.contributing_user_count = aggregate.contributing_user_count
        existing.avg_turnaround_days = aggregate.avg_turnaround_days
        existing.interview_rate_overall = aggregate.interview_rate_overall
        existing.interview_rate_by_source_domain = aggregate.interview_rate_by_source_domain
        processed += 1

    await db.commit()
    return processed
