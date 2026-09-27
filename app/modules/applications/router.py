"""Application Tracker router (Module 8)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Application, ApplicationStageHistory, Profile
from app.modules.applications.service import InvalidStageTransitionError, validate_transition

router = APIRouter(prefix="/applications", tags=["applications"])


class ApplicationCreate(BaseModel):
    job_id: UUID
    tailored_cv_id: UUID | None = None


class StageUpdate(BaseModel):
    stage: str


@router.post("", status_code=201)
async def create_application(
    payload: ApplicationCreate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()

    existing = (
        await db.execute(
            select(Application).where(
                Application.profile_id == profile.id, Application.job_id == payload.job_id
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409, detail={"code": "VALIDATION_ERROR", "message": "Job already tracked"}
        )

    application = Application(
        profile_id=profile.id, job_id=payload.job_id, tailored_cv_id=payload.tailored_cv_id, stage="saved"
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return {"data": _summary(application), "meta": {}, "error": None}


@router.get("")
async def list_applications(
    stage: str | None = None,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    query = select(Application).where(Application.profile_id == profile.id)
    if stage:
        query = query.where(Application.stage == stage)
    applications = (await db.execute(query)).scalars().all()
    return {"data": [_summary(a) for a in applications], "meta": {"total": len(applications)}, "error": None}


@router.get("/dashboard")
async def dashboard_metrics(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    applications = (
        await db.execute(select(Application).where(Application.profile_id == profile.id))
    ).scalars().all()

    from app.modules.analytics.service import compute_pipeline_metrics

    metrics = compute_pipeline_metrics([a.stage for a in applications])
    return {"data": metrics, "meta": {}, "error": None}


@router.get("/{application_id}")
async def get_application(
    application_id: UUID, user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    application = await _get_owned_application(db, user_id, application_id)
    history = (
        await db.execute(
            select(ApplicationStageHistory)
            .where(ApplicationStageHistory.application_id == application.id)
            .order_by(ApplicationStageHistory.changed_at)
        )
    ).scalars().all()
    return {
        "data": {
            **_summary(application),
            "notes": application.notes,
            "history": [
                {"from_stage": h.from_stage, "to_stage": h.to_stage, "changed_at": h.changed_at.isoformat()}
                for h in history
            ],
        },
        "meta": {},
        "error": None,
    }


@router.put("/{application_id}/stage")
async def update_stage(
    application_id: UUID,
    payload: StageUpdate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    application = await _get_owned_application(db, user_id, application_id)

    try:
        validate_transition(application.stage, payload.stage)
    except InvalidStageTransitionError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VALIDATION_ERROR",
                "message": str(exc),
                "field_errors": {"stage": f"cannot move from {exc.from_stage} to {exc.to_stage}"},
            },
        ) from exc

    db.add(
        ApplicationStageHistory(
            application_id=application.id, from_stage=application.stage, to_stage=payload.stage
        )
    )
    application.stage = payload.stage
    if payload.stage == "submitted" and application.applied_at is None:
        from datetime import UTC, datetime

        application.applied_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(application)
    return {"data": _summary(application), "meta": {}, "error": None}


async def _get_owned_application(db: AsyncSession, user_id: UUID, application_id: UUID) -> Application:
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    application = (
        await db.execute(
            select(Application).where(
                Application.id == application_id, Application.profile_id == profile.id
            )
        )
    ).scalar_one_or_none()
    if application is None:
        raise HTTPException(
            status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Application not found"}
        )
    return application


def _summary(application: Application) -> dict:
    return {
        "id": str(application.id),
        "job_id": str(application.job_id),
        "tailored_cv_id": str(application.tailored_cv_id) if application.tailored_cv_id else None,
        "stage": application.stage,
        "applied_at": application.applied_at.isoformat() if application.applied_at else None,
    }
