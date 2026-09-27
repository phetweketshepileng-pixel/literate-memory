"""Example Celery task wiring the full AI pipeline together end-to-end for
Job Matching, matching ai-architecture.md section 2 step-by-step. The same
pattern (quota → cache → provider call → validate → fallback → persist)
is what every other AI-backed task (cv_tailoring_tasks.py,
message_generation_tasks.py) follows — this file is the reference
implementation to copy from, not a one-off.
"""
from __future__ import annotations

import json
import logging

from pydantic import ValidationError
from sqlalchemy import select

from app.ai.base import AIProviderError
from app.ai.cache import AIResultCache, content_hash
from app.ai.prompts.job_matching_v1 import build_prompt
from app.ai.quota import AIQuota, QuotaExceededError
from app.ai.schemas import JOB_MATCH_JSON_SCHEMA, JobMatchResult
from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models import Job, JobMatch, Profile, Skill
from app.modules.match_scoring.service import (
    fallback_result as _fallback_result,
    pre_filter_score as _pre_filter_score,
    passes_pre_filter,
)

logger = logging.getLogger(__name__)

JOB_DESCRIPTION_EXCERPT_CHARS = 2000  # token optimization: truncate long postings


@celery_app.task(name="match_scoring.score_job_for_profile", bind=True, max_retries=0)
def score_job_for_profile(self, profile_id: str, job_id: str) -> dict:
    """Celery entrypoint — synchronous wrapper is required because Celery
    tasks aren't natively async; the async body is run via asyncio.run
    inside `_score_job_for_profile_async`."""
    import asyncio

    return asyncio.run(_score_job_for_profile_async(profile_id, job_id))


async def _score_job_for_profile_async(profile_id: str, job_id: str) -> dict:
    from app.core.redis_client import get_redis  # local import avoids import cycles
    from app.ai.circuit_breaker import CircuitBreaker
    from app.ai.openai_provider import OpenAIProvider

    async with AsyncSessionLocal() as db:
        profile = (await db.execute(select(Profile).where(Profile.id == profile_id))).scalar_one()
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
        skills = (await db.execute(select(Skill).where(Skill.profile_id == profile_id))).scalars().all()
        profile_skill_names = {s.name for s in skills}

        redis = await get_redis()
        quota = AIQuota(redis)
        cache = AIResultCache(redis)

        # Step 1 — quota check, before anything else (section 8)
        try:
            await quota.check_and_increment(str(profile.user_id), "match_scoring")
        except QuotaExceededError as exc:
            logger.info("Quota exceeded for profile %s: %s", profile_id, exc)
            result = _fallback_result(profile_skill_names, job.description or "")
            await _persist_match(db, profile_id, job_id, result)
            return result.model_dump()

        # Stage 1 pre-filter — never call the LLM for a weak match (section 3.1)
        pre_score = _pre_filter_score(profile_skill_names, job.description or "")
        if not passes_pre_filter(pre_score):
            result = JobMatchResult(
                match_score=pre_score,
                strengths=[],
                missing_skills=[],
                experience_gaps=[],
                recommendations=[],
            )
            await _persist_match(db, profile_id, job_id, result)
            return result.model_dump()

        # Step 2 — cache lookup
        job_hash = content_hash(job.title, job.description or "", str(job.created_at))
        cache_key = AIResultCache.match_key(
            profile_id, job_id, str(profile.updated_at), job_hash
        )

        async def compute() -> dict:
            circuit_breaker = CircuitBreaker(redis, provider_name="openai")
            provider = OpenAIProvider(circuit_breaker=circuit_breaker)

            system_prompt, user_prompt = build_prompt(
                current_role=profile.current_role or "",
                years_experience=profile.years_experience or 0,
                industry=profile.industry or "",
                skills_list=sorted(profile_skill_names),
                career_transition_target=profile.career_transition_target,
                job_title=job.title,
                company=job.company or "",
                job_requirements_excerpt=(job.description or "")[:JOB_DESCRIPTION_EXCERPT_CHARS],
            )

            try:
                completion = await provider.complete(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    json_schema=JOB_MATCH_JSON_SCHEMA,
                    max_tokens=500,
                    model="classification",
                )
                validated = JobMatchResult.model_validate(json.loads(completion.content))
                return validated.model_dump()
            except (AIProviderError, ValidationError, json.JSONDecodeError) as exc:
                # Step 7 — fallback path (section 7.4): never propagate as a
                # 500, always return a usable degraded result.
                logger.warning("Match scoring AI call failed for job %s: %s", job_id, exc)
                return _fallback_result(profile_skill_names, job.description or "").model_dump()

        result_dict = await cache.get_or_compute(cache_key, compute, ttl_seconds=86400)
        result = JobMatchResult.model_validate(result_dict)
        await _persist_match(db, profile_id, job_id, result)
        return result.model_dump()


async def _persist_match(db, profile_id: str, job_id: str, result: JobMatchResult) -> None:
    """Idempotent upsert keyed on the existing UNIQUE(profile_id, job_id)
    constraint — safe under Celery task retry (section 7.5)."""
    existing = (
        await db.execute(
            select(JobMatch).where(JobMatch.profile_id == profile_id, JobMatch.job_id == job_id)
        )
    ).scalar_one_or_none()

    if existing:
        existing.match_score = result.match_score
        existing.strengths = result.strengths
        existing.missing_skills = result.missing_skills
        existing.experience_gaps = result.experience_gaps
        existing.recommendations = result.recommendations
    else:
        db.add(
            JobMatch(
                profile_id=profile_id,
                job_id=job_id,
                match_score=result.match_score,
                strengths=result.strengths,
                missing_skills=result.missing_skills,
                experience_gaps=result.experience_gaps,
                recommendations=result.recommendations,
            )
        )
    await db.commit()
