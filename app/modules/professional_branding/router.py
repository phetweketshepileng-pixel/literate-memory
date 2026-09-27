"""Professional Branding router."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import BrandProfile, Profile, Skill
from app.modules.professional_branding.service import (
    check_headline_role_consistency,
    check_skills_consistency,
    compute_brand_consistency,
    flag_generic_summary_language,
    suggest_linkedin_headline,
)

router = APIRouter(prefix="/branding", tags=["branding"])


class BrandProfileUpdate(BaseModel):
    linkedin_headline: str | None = None
    linkedin_summary: str | None = None


@router.put("")
async def update_brand_profile(
    payload: BrandProfileUpdate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    brand = (
        await db.execute(select(BrandProfile).where(BrandProfile.profile_id == profile.id))
    ).scalar_one_or_none()

    if brand is None:
        brand = BrandProfile(profile_id=profile.id)
        db.add(brand)

    if payload.linkedin_headline is not None:
        brand.linkedin_headline = payload.linkedin_headline
    if payload.linkedin_summary is not None:
        brand.linkedin_summary = payload.linkedin_summary

    await db.commit()
    return {"data": {"linkedin_headline": brand.linkedin_headline}, "meta": {}, "error": None}


@router.get("/consistency-check")
async def get_consistency_check(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    brand = (
        await db.execute(select(BrandProfile).where(BrandProfile.profile_id == profile.id))
    ).scalar_one_or_none()
    skills = (await db.execute(select(Skill).where(Skill.profile_id == profile.id))).scalars().all()

    linkedin_headline = brand.linkedin_headline if brand else None
    linkedin_summary = brand.linkedin_summary if brand else None

    checks = [
        check_headline_role_consistency(profile.current_role, linkedin_headline),
        check_skills_consistency({s.name for s in skills}, linkedin_summary or ""),
    ]
    report = compute_brand_consistency(checks)
    generic_flags = flag_generic_summary_language(linkedin_summary) if linkedin_summary else []

    if brand:
        from datetime import UTC, datetime
        brand.last_consistency_score = report.consistency_score
        brand.last_checked_at = datetime.now(UTC)
        await db.commit()

    return {
        "data": {
            "consistency_score": report.consistency_score,
            "checks": [
                {"field": c.field, "is_consistent": c.is_consistent, "note": c.note} for c in report.checks
            ],
            "generic_language_flags": generic_flags,
        },
        "meta": {}, "error": None,
    }


@router.get("/headline-suggestion")
async def get_headline_suggestion(
    target_domain_label: str,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    skills = (await db.execute(select(Skill).where(Skill.profile_id == profile.id))).scalars().all()
    top_strength = skills[0].name if skills else None

    suggestion = suggest_linkedin_headline(profile.current_role or "", target_domain_label, top_strength)
    return {"data": {"suggested_headline": suggestion}, "meta": {}, "error": None}
