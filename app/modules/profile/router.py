"""Profile module router (Module 1). Endpoints per the V1 API spec:
GET/PUT /profile, GET /profile/completion-score, skills/certifications/
education/documents CRUD."""
from __future__ import annotations

from uuid import UUID

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
            select(Document.id).where(
                Document.profile_id == profile.id,
                Document.document_type == "master_cv",
                Document.deleted_at.is_(None),
            ).limit(1)
        )
    ).first() is not None

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
    exists = (
        await db.execute(select(Skill.id).where(Skill.profile_id == profile.id, Skill.name.ilike(payload.name.strip())))
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail={"code": "VALIDATION_ERROR", "message": "You already have this skill"})
    skill = Skill(profile_id=profile.id, **{**payload.model_dump(), "name": payload.name.strip()})
    db.add(skill)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail={"code": "VALIDATION_ERROR", "message": "You already have this skill"})
    await db.refresh(skill)
    return skill


@router.get("/skills", response_model=list[SkillOut])
async def list_skills(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> list[Skill]:
    profile = await _get_owned_profile(db, user_id)
    return list(
        (await db.execute(select(Skill).where(Skill.profile_id == profile.id).order_by(Skill.created_at))).scalars()
    )


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
    return {"id": str(edu.id), "qualification": edu.qualification, "institution": edu.institution, "status": edu.status}


@router.post("/documents", status_code=201)
async def upload_document(
    file: UploadFile,
    document_type: str,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.core.storage import MAX_DOCUMENT_BYTES, build_storage_path, save_document_bytes
    from app.modules.profile.cv_parsing import UnreadableDocumentError, detect_skills, extract_text

    profile = await _get_owned_profile(db, user_id)
    if document_type not in ("master_cv", "certificate", "cover_letter", "generated_cv"):
        raise HTTPException(
            status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Invalid document_type"}
        )
    content = await file.read(MAX_DOCUMENT_BYTES + 1)
    if len(content) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail={"code": "VALIDATION_ERROR", "message": "File is larger than 10MB"})
    if not content:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "The file is empty"})

    parsed_text, parse_error = None, None
    try:
        parsed_text = extract_text(content, file.filename, file.content_type) or None
        if parsed_text is None:
            parse_error = "No text found — if this is a scanned PDF, upload a Word or text version instead."
    except UnreadableDocumentError as exc:
        parse_error = str(exc)

    if document_type == "master_cv" and parse_error:
        # the master CV feeds skill extraction and CV Tailoring, so an
        # unreadable one must not replace a good existing one
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": parse_error})

    storage_path = build_storage_path(str(profile.id), file.filename)
    await save_document_bytes(db, storage_path, content)

    if document_type == "master_cv":
        # one current master CV per profile — older versions are soft-deleted
        previous = (
            await db.execute(
                select(Document).where(
                    Document.profile_id == profile.id,
                    Document.document_type == "master_cv",
                    Document.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        for doc in previous:
            doc.deleted_at = datetime.now(UTC)

    document = Document(
        profile_id=profile.id,
        document_type=document_type,
        file_name=file.filename,
        storage_path=storage_path,
        mime_type=file.content_type,
        parsed_text=parsed_text,
    )
    db.add(document)

    added_skills: list[str] = []
    if document_type == "master_cv" and parsed_text:
        existing = {
            n.lower() for n in (await db.execute(select(Skill.name).where(Skill.profile_id == profile.id))).scalars()
        }
        for name in detect_skills(parsed_text):
            if name.lower() not in existing:
                db.add(Skill(profile_id=profile.id, name=name, source="cv_extracted"))
                added_skills.append(name)

    await db.commit()
    await db.refresh(document)
    return {
        "id": str(document.id),
        "document_type": document.document_type,
        "file_name": document.file_name,
        "text_extracted": parsed_text is not None,
        "parse_error": parse_error,
        "skills_added": added_skills,
    }


@router.get("/documents")
async def list_documents(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> list[dict]:
    profile = await _get_owned_profile(db, user_id)
    docs = (
        await db.execute(
            select(Document)
            .where(Document.profile_id == profile.id, Document.deleted_at.is_(None))
            .order_by(Document.created_at.desc())
        )
    ).scalars().all()
    return [
        {
            "id": str(d.id),
            "document_type": d.document_type,
            "file_name": d.file_name,
            "text_extracted": bool(d.parsed_text),
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: UUID, user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> Response:
    from app.core.storage import load_document_bytes

    profile = await _get_owned_profile(db, user_id)
    doc = (
        await db.execute(
            select(Document).where(
                Document.id == document_id, Document.profile_id == profile.id, Document.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    content = await load_document_bytes(db, doc.storage_path) if doc else None
    if doc is None or content is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Document not found"})
    safe_name = (doc.file_name or "document").replace('"', "")
    return Response(
        content=content,
        media_type=doc.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.get("/education")
async def list_education(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> list[dict]:
    profile = await _get_owned_profile(db, user_id)
    rows = (await db.execute(select(Education).where(Education.profile_id == profile.id))).scalars().all()
    return [
        {"id": str(e.id), "qualification": e.qualification, "institution": e.institution, "status": e.status}
        for e in rows
    ]


@router.delete("/education/{education_id}", status_code=204)
async def delete_education(
    education_id: UUID, user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> None:
    profile = await _get_owned_profile(db, user_id)
    row = (
        await db.execute(select(Education).where(Education.id == education_id, Education.profile_id == profile.id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Education not found"})
    await db.delete(row)
    await db.commit()


@router.get("/certifications")
async def list_certifications(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> list[dict]:
    profile = await _get_owned_profile(db, user_id)
    rows = (await db.execute(select(Certification).where(Certification.profile_id == profile.id))).scalars().all()
    return [{"id": str(c.id), "name": c.name, "issuer": c.issuer} for c in rows]


@router.delete("/certifications/{certification_id}", status_code=204)
async def delete_certification(
    certification_id: UUID, user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> None:
    profile = await _get_owned_profile(db, user_id)
    row = (
        await db.execute(
            select(Certification).where(Certification.id == certification_id, Certification.profile_id == profile.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Certification not found"})
    await db.delete(row)
    await db.commit()
