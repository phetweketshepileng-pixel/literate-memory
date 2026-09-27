"""Nightly analytics snapshot materialization (Celery beat, once/day per
profile). Uses the SAME compute_rates_from_history function the tests in
tests/test_analytics_service.py verify — the live dashboard and this batch
job can never silently disagree on the math, only on staleness (at most a
day old, per the db-schema doc's design rationale)."""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models import Application, ApplicationStageHistory, AnalyticsSnapshot, Job, Profile
from app.modules.analytics.service import ApplicationOutcome, breakdown_by_key, compute_rates_from_history

logger = logging.getLogger(__name__)

SNAPSHOT_WINDOW_DAYS = 30


@celery_app.task(name="analytics.materialize_all_snapshots", queue="default")
def materialize_all_snapshots() -> dict:
    import asyncio

    return asyncio.run(_materialize_all_async())


async def _materialize_all_async() -> dict:
    async with AsyncSessionLocal() as db:
        profile_ids = (await db.execute(select(Profile.id))).scalars().all()
        processed = 0
        for profile_id in profile_ids:
            await _materialize_for_profile(db, str(profile_id))
            processed += 1
        return {"profiles_processed": processed}


async def _materialize_for_profile(db, profile_id: str) -> None:
    period_end = date.today()
    period_start = period_end - timedelta(days=SNAPSHOT_WINDOW_DAYS)

    applications = (
        await db.execute(select(Application).where(Application.profile_id == profile_id))
    ).scalars().all()

    outcomes: list[ApplicationOutcome] = []
    source_items: list[tuple[str, bool]] = []
    role_items: list[tuple[str, bool]] = []

    for app in applications:
        if app.applied_at is None or app.applied_at.date() < period_start:
            continue

        history = (
            await db.execute(
                select(ApplicationStageHistory)
                .where(ApplicationStageHistory.application_id == app.id)
                .order_by(ApplicationStageHistory.changed_at)
            )
        ).scalars().all()

        first_response_at = next(
            (h.changed_at for h in history if h.to_stage != "saved" and h.to_stage != "applying"), None
        )
        reached_interview = any(h.to_stage in ("interview", "assessment", "offer") for h in history)
        reached_offer = any(h.to_stage == "offer" for h in history)
        reached_rejected = any(h.to_stage == "rejected" for h in history)

        outcomes.append(
            ApplicationOutcome(
                submitted_at=app.applied_at,
                reached_interview=reached_interview,
                reached_offer=reached_offer,
                reached_rejected=reached_rejected,
                first_response_at=first_response_at,
            )
        )

        job = (await db.execute(select(Job).where(Job.id == app.job_id))).scalar_one_or_none()
        if job is not None:
            source_name = str(job.source_id) if job.source_id else "direct"
            source_items.append((source_name, True))

    metrics = compute_rates_from_history(outcomes)
    breakdown_by_source = breakdown_by_key(source_items)

    existing = (
        await db.execute(
            select(AnalyticsSnapshot).where(
                AnalyticsSnapshot.profile_id == profile_id,
                AnalyticsSnapshot.period_start == period_start,
                AnalyticsSnapshot.period_end == period_end,
            )
        )
    ).scalar_one_or_none()

    if existing:
        _apply_metrics(existing, metrics, breakdown_by_source)
    else:
        snapshot = AnalyticsSnapshot(
            profile_id=profile_id, period_start=period_start, period_end=period_end
        )
        _apply_metrics(snapshot, metrics, breakdown_by_source)
        db.add(snapshot)

    await db.commit()


def _apply_metrics(snapshot: AnalyticsSnapshot, metrics: dict, breakdown_by_source: dict) -> None:
    snapshot.applications_submitted = metrics["applications_submitted"]
    snapshot.interviews = metrics["interviews"]
    snapshot.offers = metrics["offers"]
    snapshot.rejections = metrics["rejections"]
    snapshot.response_rate = metrics["response_rate"]
    snapshot.interview_rate = metrics["interview_rate"]
    snapshot.offer_rate = metrics["offer_rate"]
    snapshot.avg_time_to_response_days = metrics["avg_time_to_response_days"]
    snapshot.breakdown_by_source = breakdown_by_source
