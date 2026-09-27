"""CV Tailoring router (Module 5)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Profile, TailoredCV

router = APIRouter(prefix="/cv", tags=["cv"])


@router.post("/tailor", status_code=202)
async def request_tailoring(
    job_id: UUID,
    variant: str,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if variant not in ("ats", "recruiter_friendly"):
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Invalid variant"})

    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()

    from app.workers.cv_tailoring_tasks import tailor_cv_for_job

    task = tailor_cv_for_job.delay(str(profile.id), str(job_id), variant)
    return {"data": {"task_id": task.id}, "meta": {}, "error": None}


@router.get("/tailor/{task_id}/status")
async def get_tailoring_status(task_id: str):
    from app.workers.cv_tailoring_tasks import tailor_cv_for_job

    result = tailor_cv_for_job.AsyncResult(task_id)
    return {
        "data": {"task_id": task_id, "status": result.status, "result": result.result if result.ready() else None},
        "meta": {},
        "error": None,
    }


@router.get("/tailored")
async def list_tailored_cvs(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    cvs = (
        await db.execute(select(TailoredCV).where(TailoredCV.profile_id == profile.id))
    ).scalars().all()
    return {"data": [_cv_summary(cv) for cv in cvs], "meta": {"total": len(cvs)}, "error": None}


@router.get("/tailored/{cv_id}")
async def get_tailored_cv(
    cv_id: UUID, user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    cv = (
        await db.execute(
            select(TailoredCV).where(TailoredCV.id == cv_id, TailoredCV.profile_id == profile.id)
        )
    ).scalar_one_or_none()
    if cv is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "CV not found"})
    return {
        "data": {**_cv_summary(cv), "content_json": cv.content_json, "added_keywords": cv.added_keywords},
        "meta": {},
        "error": None,
    }


@router.get("/tailored/{cv_id}/download")
async def download_tailored_cv(
    cv_id: UUID,
    format: str = "pdf",
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if format not in ("pdf", "docx"):
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "format must be pdf or docx"})
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    cv = (
        await db.execute(
            select(TailoredCV).where(TailoredCV.id == cv_id, TailoredCV.profile_id == profile.id)
        )
    ).scalar_one_or_none()
    if cv is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "CV not found"})

    document_id = cv.pdf_document_id if format == "pdf" else cv.docx_document_id
    if document_id is None:
        raise HTTPException(
            status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": f"{format} export not yet generated"}
        )

    from app.core.storage import generate_signed_download_url
    from app.models import Document

    document = (await db.execute(select(Document).where(Document.id == document_id))).scalar_one()
    url = await generate_signed_download_url(document.storage_path)
    return {"data": {"download_url": url}, "meta": {}, "error": None}


def _cv_summary(cv: TailoredCV) -> dict:
    return {
        "id": str(cv.id),
        "job_id": str(cv.job_id) if cv.job_id else None,
        "variant": cv.variant,
        "optimization_score": cv.optimization_score,
        "ats_score": cv.ats_score,
        "created_at": cv.created_at.isoformat(),
    }
