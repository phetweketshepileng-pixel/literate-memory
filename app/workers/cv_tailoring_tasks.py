"""CV Tailoring Celery task — same pipeline shape as match_scoring_tasks.py
(quota → AI call with circuit breaker → validate/ground → fallback →
idempotent persist). See ai-architecture.md section 3.2 and 7.4."""
from __future__ import annotations

import json
import logging

from pydantic import ValidationError
from sqlalchemy import select

from app.ai.base import AIProviderError
from app.ai.prompts.cv_tailoring_v1 import build_prompt
from app.ai.quota import AIQuota, QuotaExceededError
from app.ai.schemas import CV_TAILORING_JSON_SCHEMA, CVTailoringResult
from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models import Certification, Document, Job, Profile, Skill, TailoredCV
from app.modules.cv_tailoring.service import (
    CVContent,
    compute_ats_score,
    compute_optimization_score,
    extract_keywords,
    find_unauthorized_claims,
    keyword_coverage,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="cv_tailoring.tailor_cv_for_job", bind=True, max_retries=0, queue="ai_heavy")
def tailor_cv_for_job(self, profile_id: str, job_id: str, variant: str) -> dict:
    import asyncio

    return asyncio.run(_tailor_cv_async(profile_id, job_id, variant))


def _build_facts_block(skills: list[Skill], certifications: list[Certification], master_cv_text: str | None) -> tuple[str, set[str]]:
    """Assembles the enumerable, checkable fact set the prompt is grounded
    against (ai-architecture.md section 4) and returns it alongside the
    flat set of allowed terms used by the post-generation validator."""
    lines = ["Confirmed skills:"]
    allowed_facts: set[str] = set()
    for skill in skills:
        lines.append(f"- {skill.name} ({skill.proficiency or 'unspecified level'})")
        allowed_facts.add(skill.name)
    lines.append("Certifications:")
    for cert in certifications:
        lines.append(f"- {cert.name} ({cert.issuer or 'unspecified issuer'})")
        allowed_facts.add(cert.name)
    if master_cv_text:
        lines.append("Master CV text (source of truth for roles/dates/employers):")
        lines.append(master_cv_text[:3000])
        allowed_facts |= extract_keywords(master_cv_text)
    return "\n".join(lines), allowed_facts


def _fallback_cv_result(master_cv_text: str | None) -> CVTailoringResult:
    """Degraded path (ai-architecture.md section 3.2): unmodified master CV
    content returned as the 'tailored' result, clearly flagged by
    optimization_score=0 rather than a fabricated confident number."""
    return CVTailoringResult(
        content_json={
            "summary": (master_cv_text or "")[:500],
            "experience": [],
            "skills_section": [],
        },
        added_keywords=[],
        optimization_score=0,
    )


async def _tailor_cv_async(profile_id: str, job_id: str, variant: str) -> dict:
    from app.core.redis_client import get_redis
    from app.ai.circuit_breaker import CircuitBreaker
    from app.ai.openai_provider import OpenAIProvider

    async with AsyncSessionLocal() as db:
        profile = (await db.execute(select(Profile).where(Profile.id == profile_id))).scalar_one()
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
        skills = (await db.execute(select(Skill).where(Skill.profile_id == profile_id))).scalars().all()
        certifications = (
            await db.execute(select(Certification).where(Certification.profile_id == profile_id))
        ).scalars().all()
        master_cv = (
            await db.execute(
                select(Document).where(
                    Document.profile_id == profile_id, Document.document_type == "master_cv"
                )
            )
        ).scalar_one_or_none()
        master_cv_text = master_cv.parsed_text if master_cv else None

        redis = await get_redis()
        quota = AIQuota(redis)

        job_keywords = extract_keywords(job.description or "")

        try:
            await quota.check_and_increment(str(profile.user_id), "cv_tailoring")
        except QuotaExceededError as exc:
            logger.info("CV tailoring quota exceeded for profile %s: %s", profile_id, exc)
            result = _fallback_cv_result(master_cv_text)
            await _persist_cv(db, profile_id, job_id, variant, result)
            return result.model_dump()

        facts_block, allowed_facts = _build_facts_block(skills, certifications, master_cv_text)

        try:
            circuit_breaker = CircuitBreaker(redis, provider_name="openai")
            provider = OpenAIProvider(circuit_breaker=circuit_breaker)

            system_prompt, user_prompt = build_prompt(
                facts_block=facts_block,
                job_title=job.title,
                company=job.company or "",
                job_keywords=sorted(job_keywords),
                variant=variant,
            )
            completion = await provider.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_schema=CV_TAILORING_JSON_SCHEMA,
                max_tokens=1200,
                model="generation",
            )
            validated = CVTailoringResult.model_validate(json.loads(completion.content))

            # Enforcement backstop (ai-architecture.md section 4): re-check
            # the model's own output against the allowed fact set.
            full_output_text = (
                validated.content_json.summary
                + " ".join(validated.content_json.experience)
                if isinstance(validated.content_json.experience, list)
                else str(validated.content_json.experience)
            )
            suspicious = find_unauthorized_claims(full_output_text, allowed_facts)
            if suspicious:
                logger.warning(
                    "CV tailoring for job %s produced unauthorized-looking claims %s; using fallback",
                    job_id, suspicious,
                )
                result = _fallback_cv_result(master_cv_text)
            else:
                # ATS score is computed deterministically, not by the LLM
                # (ai-architecture.md section 3.2) — recompute here rather
                # than trusting a model-reported score.
                cv_content = CVContent(
                    summary=validated.content_json.summary,
                    experience_bullets=[str(e) for e in validated.content_json.experience],
                    skills_section=validated.content_json.skills_section,
                )
                ats_score = compute_ats_score(cv_content, job_keywords)
                _, coverage_matched = keyword_coverage(job_keywords, full_output_text)
                optimization_score = compute_optimization_score(
                    len(validated.added_keywords), len(job_keywords)
                )
                result = CVTailoringResult(
                    content_json=validated.content_json,
                    added_keywords=validated.added_keywords,
                    optimization_score=optimization_score,
                )
                result_dict = result.model_dump()
                result_dict["ats_score"] = ats_score
                await _persist_cv(db, profile_id, job_id, variant, result, ats_score=ats_score)
                return result_dict

        except (AIProviderError, ValidationError, json.JSONDecodeError) as exc:
            logger.warning("CV tailoring AI call failed for job %s: %s", job_id, exc)
            result = _fallback_cv_result(master_cv_text)

        await _persist_cv(db, profile_id, job_id, variant, result, ats_score=None)
        return result.model_dump()


async def _persist_cv(
    db, profile_id: str, job_id: str, variant: str, result: CVTailoringResult, ats_score: int | None = None
) -> None:
    """Idempotent upsert on UNIQUE(profile_id, job_id, variant) — safe
    under Celery task retry, per ai-architecture.md section 7.5."""
    existing = (
        await db.execute(
            select(TailoredCV).where(
                TailoredCV.profile_id == profile_id,
                TailoredCV.job_id == job_id,
                TailoredCV.variant == variant,
            )
        )
    ).scalar_one_or_none()

    content_json = result.content_json.model_dump() if hasattr(result.content_json, "model_dump") else result.content_json

    if existing:
        existing.content_json = content_json
        existing.added_keywords = result.added_keywords
        existing.optimization_score = result.optimization_score
        existing.ats_score = ats_score
    else:
        db.add(
            TailoredCV(
                profile_id=profile_id,
                job_id=job_id,
                variant=variant,
                content_json=content_json,
                added_keywords=result.added_keywords,
                optimization_score=result.optimization_score,
                ats_score=ats_score,
            )
        )
    await db.commit()
