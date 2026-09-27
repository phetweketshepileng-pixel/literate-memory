"""Profile module router (Module 1). Endpoints per the V1 API spec:
GET/PUT /profile, GET /profile/completion-score, skills/certifications/
education/documents CRUD."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Certification, Document, Education, Profile, Skill
from app.modules.profile.schemas import (
    CertificationIn,
    EducationIn,
    ProfileCompletionOut,
    ProfileOut,
    ProfileUpdate,
    SkillIn,
    SkillOut,
)
from app.modules.profile.service import ProfileCompletionInput, compute_completion_score

router = APIRouter(prefix="/profile", tags=["profile"])


async def _get_owned_profile(db: AsyncSession, user_id: UUID) -> Profile:
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Profile not found"})
    return profile


@router.get("", response_model=ProfileOut)
async def get_profile(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> Profile:
    return await _get_owned_profile(db, user_id)


@router.put("", response_model=ProfileOut)
async def update_profile(
    payload: ProfileUpdate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Profile:
    profile = await _get_owned_profile(db, user_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/completion-score", response_model=ProfileCompletionOut)
async def get_completion_score(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> ProfileCompletionOut:
    profile = await _get_owned_profile(db, user_id)
    skill_count = len((await db.execute(select(Skill).where(Skill.profile_id == profile.id))).scalars().all())
    education_count = len(
        (await db.execute(select(Education).where(Education.profile_id == profile.id))).scalars().all()
    )
    has_master_cv = (
        await db.execute(
            select(Document).where(Document.profile_id == profile.id, Document.document_type == "master_cv")
        )
    ).scalar_one_or_none() is not None

    score, missing = compute_completion_score(
        ProfileCompletionInput(
            full_name=profile.full_name,
            current_role=profile.current_role,
            years_experience=profile.years_experience,
            industry=profile.industry,
            desired_roles=profile.desired_roles,
            salary_expectation_min=profile.salary_expectation_min,
            location_preferences=profile.location_preferences,
            work_mode_preference=profile.work_mode_preference,
            skill_count=skill_count,
            has_master_cv=has_master_cv,
            education_count=education_count,
        )
    )
    if score != profile.profile_completion_score:
        profile.profile_completion_score = score
        await db.commit()

    return ProfileCompletionOut(score=score, missing_fields=missing)


@router.post("/skills", response_model=SkillOut, status_code=201)
async def add_skill(
    payload: SkillIn, user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> Skill:
    profile = await _get_owned_profile(db, user_id)
    skill = Skill(profile_id=profile.id, **payload.model_dump())
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill


@router.delete("/skills/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: UUID, user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> None:
    profile = await _get_owned_profile(db, user_id)
    skill = (
        await db.execute(select(Skill).where(Skill.id == skill_id, Skill.profile_id == profile.id))
    ).scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Skill not found"})
    await db.delete(skill)
    await db.commit()


@router.post("/certifications", status_code=201)
async def add_certification(
    payload: CertificationIn, user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> dict:
    profile = await _get_owned_profile(db, user_id)
    cert = Certification(profile_id=profile.id, **payload.model_dump())
    db.add(cert)
    await db.commit()
    await db.refresh(cert)
    return {"id": str(cert.id), "name": cert.name, "issuer": cert.issuer}


@router.post("/education", status_code=201)
async def add_education(
    payload: EducationIn, user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> dict:
    profile = await _get_owned_profile(db, user_id)
    edu = Education(profile_id=profile.id, **payload.model_dump())
    db.add(edu)
    await db.commit()
    await db.refresh(edu)
    return {"id": str(edu.id), "qualification": edu.qualification, "status": edu.status}


@router.post("/documents", status_code=201)
async def upload_document(
    file: UploadFile,
    document_type: str,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    profile = await _get_owned_profile(db, user_id)
    if document_type not in ("master_cv", "certificate", "cover_letter", "generated_cv"):
        raise HTTPException(
            status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Invalid document_type"}
        )
    # storage_path is written by the object-storage upload step (not shown
    # here — see ai-job-hunter-db-schema-v1.1.md section 3 on encrypted
    # storage); this handler owns only the DB record.
    from app.core.storage import upload_to_encrypted_storage  # local import, keeps router import-light

    storage_path = await upload_to_encrypted_storage(file, profile_id=str(profile.id))
    document = Document(
        profile_id=profile.id,
        document_type=document_type,
        file_name=file.filename,
        storage_path=storage_path,
        mime_type=file.content_type,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return {"id": str(document.id), "document_type": document.document_type, "file_name": document.file_name}
