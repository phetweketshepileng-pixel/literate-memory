"""Ingestion pipeline orchestration — architecture doc section 4. One
Celery beat schedule per source_id; each run is isolated so one source's
failure never blocks another's, and all polling lives in the `scraping`
queue, separate from the ai_heavy queue (V1.1 review's queue-isolation
fix).
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.modules.job_discovery.adapters.adzuna_adapter import AdzunaAdapter
from app.modules.job_discovery.adapters.api_feed_adapter import ApiFeedAdapter
from app.modules.job_discovery.adapters.career_page_adapter import AtsCareerPageAdapter
from app.modules.job_discovery.adapters.rss_feed_adapter import RssFeedAdapter
from app.modules.job_discovery.adapters.ats_board_adapter import AtsBoardAdapter
from app.modules.job_discovery.deduplication import find_duplicate, record_additional_source
from app.modules.job_discovery.industry import classify_industry, industry_from_payload
from app.core.rate_limit import TokenBucketLimiter
from app.models import Job, JobSource

logger = logging.getLogger(__name__)

ADAPTER_REGISTRY = {
    "api_feed": ApiFeedAdapter,
    "rss_feed": RssFeedAdapter,
    "career_page": AtsCareerPageAdapter,
    "adzuna": AdzunaAdapter,
    "ats_board": AtsBoardAdapter,  # employer careers boards (Greenhouse, Lever, SmartRecruiters, Workable)
    # "search_discovery" intentionally omitted — its results route to a
    # separate onboarding queue, not this ingestion path (see
    # SearchEngineDiscoveryAdapter docstring).
}


@celery_app.task(name="job_discovery.poll_source", bind=True, max_retries=0, queue="scraping")
def poll_source(self, source_id: str) -> dict:
    import asyncio

    return asyncio.run(_poll_source_async(source_id))


async def _poll_source_async(source_id: str) -> dict:
    from app.core.redis_client import get_redis

    async with AsyncSessionLocal() as db:
        source = (await db.execute(select(JobSource).where(JobSource.id == source_id))).scalar_one()
        adapter_type = source.config.get("adapter_type") if hasattr(source, "config") else None
        adapter_cls = ADAPTER_REGISTRY.get(adapter_type)
        if adapter_cls is None:
            logger.error("Unknown adapter type '%s' for source %s", adapter_type, source.name)
            return {"source": source.name, "status": "skipped_unknown_adapter"}

        adapter = adapter_cls(source_id=str(source.id), config=source.config)

        redis = await get_redis()
        policy = adapter.rate_limit_policy()
        limiter = TokenBucketLimiter(
            redis, key=f"ratelimit:source:{source_id}", rate_per_minute=policy.requests_per_minute
        )

        try:
            await limiter.acquire()
            raw_listings = await adapter.fetch_listings(source.last_polled_at)
        except Exception as exc:  # noqa: BLE001 — isolate this source's failure
            logger.exception("Ingestion failed for source %s: %s", source.name, exc)
            return {"source": source.name, "status": "error", "detail": str(exc)}

        new_count = 0
        updated_count = 0
        duplicate_count = 0

        for raw in raw_listings:
            try:
                normalized = adapter.normalize(raw)
            except Exception as exc:  # noqa: BLE001 — one bad listing shouldn't kill the batch
                logger.warning("Failed to normalize listing from %s: %s", source.name, exc)
                continue

            if not normalized.title:
                continue  # unusable listing, skip rather than insert garbage

            industry = classify_industry(
                normalized.title, normalized.company,
                industry_from_payload(normalized.raw_payload), normalized.industry,
            )

            # A listing this source already gave us is an update, not a
            # cross-source duplicate — check that first, otherwise every
            # re-poll would count the job as "seen elsewhere" and wrongly
            # clear its hidden-gem flag / inflate competition_score.
            existing = (
                await db.execute(
                    select(Job).where(
                        Job.source_id == source.id, Job.external_id == normalized.external_id
                    )
                )
            ).scalar_one_or_none()

            if existing is None:
                duplicate = await find_duplicate(db, normalized)
                if duplicate is not None and duplicate.source_id != source.id:
                    await record_additional_source(db, duplicate, str(source.id), normalized)
                    duplicate_count += 1
                    continue

            if existing:
                existing.title = normalized.title
                existing.company = normalized.company
                existing.location = normalized.location
                existing.is_remote = normalized.is_remote
                existing.salary_min = normalized.salary_min
                existing.salary_max = normalized.salary_max
                existing.description = normalized.description
                existing.apply_url = normalized.apply_url
                existing.raw_payload = normalized.raw_payload
                existing.industry = industry
                updated_count += 1
            else:
                db.add(
                    Job(
                        source_id=source.id,
                        external_id=normalized.external_id,
                        title=normalized.title,
                        company=normalized.company,
                        location=normalized.location,
                        is_remote=normalized.is_remote,
                        salary_min=normalized.salary_min,
                        salary_max=normalized.salary_max,
                        description=normalized.description,
                        apply_url=normalized.apply_url,
                        date_posted=normalized.date_posted,
                        is_syndicated=normalized.is_syndicated,
                        is_hidden_gem=not normalized.is_syndicated,  # initial guess;
                        # confirmed/revised by record_additional_source if a
                        # duplicate later turns up on another source
                        raw_payload=normalized.raw_payload,
                        industry=industry,
                    )
                )
                new_count += 1

        from datetime import datetime, UTC

        closed_count = 0
        if getattr(adapter, "closes_missing_listings", False):
            # employer boards list every open role: anything of theirs we
            # hold that's no longer listed has been filled or withdrawn
            seen = {r.external_id for r in raw_listings}
            for job in (
                await db.execute(select(Job).where(Job.source_id == source.id, Job.is_active.is_(True)))
            ).scalars():
                if job.external_id not in seen:
                    job.is_active, job.closed_at = False, datetime.now(UTC)
                    closed_count += 1

        source.last_polled_at = datetime.now(UTC)
        await db.commit()

        result = {
            "source": source.name,
            "status": "ok",
            "new": new_count,
            "updated": updated_count,
            "duplicates_merged": duplicate_count,
            "closed": closed_count,
        }
        logger.info("Ingestion complete for %s: %s", source.name, result)
        return result
