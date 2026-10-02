"""Career Transition Intelligence Engine router. Not in the original V1
module list — an additive module specific to the platform's core target
user (see ai-job-hunter-career-transition-engine.md)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Certification, Profile, Skill
from app.modules.career_transition.domain_knowledge import DOMAIN_LABELS, SOURCE_DOMAINS, TARGET_DOMAINS
from app.modules.career_transition.service import (
    ReadinessInputs,
    build_reframed_facts_for_cv_tailoring,
    compute_transition_readiness,
    rank_target_domains_by_readiness,
    recommend_pathway,
)

router = APIRouter(prefix="/career-transition", tags=["career-transition"])


class ReframeRequest(BaseModel):
    target_domain: str
    experience_text: str


async def _load_profile_signals(db: AsyncSession, user_id: UUID) -> tuple[Profile, set[str], set[str]]:
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    skills = (await db.execute(select(Skill).where(Skill.profile_id == profile.id))).scalars().all()
    certs = (
        await db.execute(select(Certification).where(Certification.profile_id == profile.id))
    ).scalars().all()
    return profile, {s.name for s in skills}, {c.name for c in certs}


@router.get("/domains")
async def list_domains():
    return {
        "data": {"source_domains": SOURCE_DOMAINS, "target_domains": TARGET_DOMAINS, "labels": DOMAIN_LABELS},
        "meta": {}, "error": None,
    }


@router.get("/readiness")
async def get_readiness(
    source_domain: str,
    target_domain: str,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if source_domain not in SOURCE_DOMAINS or target_domain not in TARGET_DOMAINS:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Unknown domain"})

    profile, skill_names, cert_names = await _load_profile_signals(db, user_id)
    result = compute_transition_readiness(
        ReadinessInputs(
            source_domain=source_domain,
            target_domain=target_domain,
            confirmed_skill_names=skill_names,
            confirmed_certification_names=cert_names,
            years_in_source_domain=profile.years_experience or 0,
        )
    )
    return {
        "data": {
            "readiness_score": result.readiness_score,
            "base_affinity": result.base_affinity,
            "skill_coverage_pct": result.skill_coverage_pct,
            "certification_bonus_pct": result.certification_bonus_pct,
        },
        "meta": {}, "error": None,
    }


@router.get("/readiness/ranked")
async def get_ranked_readiness(
    source_domain: str,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if source_domain not in SOURCE_DOMAINS:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Unknown source domain"})

    profile, skill_names, cert_names = await _load_profile_signals(db, user_id)
    ranked = rank_target_domains_by_readiness(
        source_domain, skill_names, cert_names, profile.years_experience or 0
    )
    return {
        "data": [
            {"target_domain": domain, "readiness_score": result.readiness_score}
            for domain, result in ranked
        ],
        "meta": {}, "error": None,
    }


@router.get("/pathway")
async def get_pathway_recommendation(
    source_domain: str,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if source_domain not in SOURCE_DOMAINS:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Unknown source domain"})

    profile, skill_names, cert_names = await _load_profile_signals(db, user_id)
    rec = recommend_pathway(source_domain, skill_names, cert_names, profile.years_experience or 0)
    return {
        "data": {
            "primary_target_domain": rec.primary_target_domain,
            "primary_readiness_score": rec.primary_readiness_score,
            "secondary_target_domain": rec.secondary_target_domain,
            "highest_leverage_gap": rec.highest_leverage_gap,
            "recommended_certifications": rec.recommended_certifications,
        },
        "meta": {}, "error": None,
    }


@router.post("/reframe")
async def reframe_experience(
    payload: ReframeRequest,
    source_domain: str,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Rule-based reframing suggestions for a piece of experience text —
    consumed by CV Tailoring as additional grounded facts (see
    ai-job-hunter-career-transition-engine.md section 4)."""
    if source_domain not in SOURCE_DOMAINS or payload.target_domain not in TARGET_DOMAINS:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Unknown domain"})

    facts = build_reframed_facts_for_cv_tailoring(source_domain, payload.target_domain, payload.experience_text)
    return {"data": {"reframed_facts": facts}, "meta": {}, "error": None}
