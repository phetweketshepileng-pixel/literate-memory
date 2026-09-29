"""Application Tracker router (Module 8)."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
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


_SAST = timezone(timedelta(hours=2))


@router.get("/activity")
async def weekly_activity(
    weeks: int = Query(default=8, ge=1, le=26),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Per-week counts for the dashboard: jobs saved, applications submitted,
    interviews reached, offers — computed live from the stage history, so it
    works before the nightly analytics snapshots exist."""
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    today = datetime.now(_SAST).date()
    this_monday = today - timedelta(days=today.weekday())
    starts = [this_monday - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]
    since = datetime.combine(starts[0], datetime.min.time(), tzinfo=_SAST)

    def week_of(ts):
        d = ts.astimezone(_SAST).date()
        return d - timedelta(days=d.weekday())

    saved = Counter(
        week_of(ts)
        for ts in (
            await db.execute(
                select(Application.created_at).where(
                    Application.profile_id == profile.id, Application.created_at >= since
                )
            )
        ).scalars()
    )
    moves = (
        await db.execute(
            select(ApplicationStageHistory.to_stage, ApplicationStageHistory.changed_at)
            .join(Application, Application.id == ApplicationStageHistory.application_id)
            .where(Application.profile_id == profile.id, ApplicationStageHistory.changed_at >= since)
        )
    ).all()
    counts = {k: Counter() for k in ("submitted", "interview", "offer")}
    for stage, ts in moves:
        if stage in counts:
            counts[stage][week_of(ts)] += 1
    return {
        "data": [
            {
                "week_start": w.isoformat(),
                "saved": saved.get(w, 0),
                "submitted": counts["submitted"].get(w, 0),
                "interviews": counts["interview"].get(w, 0),
                "offers": counts["offer"].get(w, 0),
            }
            for w in starts
        ],
        "meta": {"timezone": "Africa/Johannesburg"},
        "error": None,
    }


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
