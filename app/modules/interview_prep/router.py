"""Interview Preparation router."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import InterviewPrepAnswer, InterviewPrepSession, Profile
from app.modules.career_transition.domain_knowledge import SOURCE_DOMAINS, TARGET_DOMAINS
from app.modules.interview_prep.service import (
    QuestionResult,
    compute_session_readiness,
    identify_missing_star_components,
    score_star_structure,
    select_behavioral_questions,
    select_technical_questions,
    years_to_difficulty,
)

router = APIRouter(prefix="/interview-prep", tags=["interview-prep"])


class StartSessionRequest(BaseModel):
    source_domain: str
    target_domain: str
    behavioral_count: int = 3
    technical_count: int = 3


class SubmitAnswerRequest(BaseModel):
    answer_id: UUID
    answer_text: str | None = None       # for behavioral questions
    technical_correct: bool | None = None  # self-assessed for technical questions


@router.post("/sessions", status_code=201)
async def start_session(
    payload: StartSessionRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if payload.source_domain not in SOURCE_DOMAINS or payload.target_domain not in TARGET_DOMAINS:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Unknown domain"})

    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    difficulty = years_to_difficulty(profile.years_experience or 0)

    session = InterviewPrepSession(
        profile_id=profile.id, source_domain=payload.source_domain, target_domain=payload.target_domain
    )
    db.add(session)
    await db.flush()  # get session.id without committing yet

    behavioral = select_behavioral_questions(
        payload.source_domain, payload.target_domain, count=payload.behavioral_count
    )
    for q in behavioral:
        db.add(
            InterviewPrepAnswer(
                session_id=session.id, question=q.question, question_type="behavioral",
                target_competency=q.target_competency,
            )
        )

    technical = select_technical_questions(payload.target_domain, difficulty, count=payload.technical_count)
    for q in technical:
        db.add(InterviewPrepAnswer(session_id=session.id, question=q, question_type="technical"))

    await db.commit()
    await db.refresh(session)

    answers = (
        await db.execute(select(InterviewPrepAnswer).where(InterviewPrepAnswer.session_id == session.id))
    ).scalars().all()

    return {
        "data": {
            "session_id": str(session.id),
            "questions": [
                {
                    "answer_id": str(a.id), "question": a.question, "question_type": a.question_type,
                    "target_competency": a.target_competency,
                }
                for a in answers
            ],
        },
        "meta": {}, "error": None,
    }


@router.post("/sessions/{session_id}/answers")
async def submit_answer(
    session_id: UUID,
    payload: SubmitAnswerRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, user_id, session_id)
    answer = (
        await db.execute(
            select(InterviewPrepAnswer).where(
                InterviewPrepAnswer.id == payload.answer_id, InterviewPrepAnswer.session_id == session.id
            )
        )
    ).scalar_one_or_none()
    if answer is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Answer slot not found"})

    result_payload: dict = {}
    if answer.question_type == "behavioral" and payload.answer_text is not None:
        star = score_star_structure(payload.answer_text)
        answer.answer_text = payload.answer_text
        answer.star_score = star.score
        result_payload = {
            "star_score": star.score,
            "missing_components": identify_missing_star_components(star),
        }
    elif answer.question_type == "technical" and payload.technical_correct is not None:
        answer.technical_correct = payload.technical_correct
        result_payload = {"technical_correct": payload.technical_correct}

    await db.commit()
    return {"data": result_payload, "meta": {}, "error": None}


@router.post("/sessions/{session_id}/complete")
async def complete_session(
    session_id: UUID, user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    session = await _get_owned_session(db, user_id, session_id)
    answers = (
        await db.execute(select(InterviewPrepAnswer).where(InterviewPrepAnswer.session_id == session.id))
    ).scalars().all()

    results = [
        QuestionResult(
            question=a.question, target_competency=a.target_competency,
            star_score=a.star_score, technical_correct=a.technical_correct,
        )
        for a in answers
        if a.star_score is not None or a.technical_correct is not None
    ]
    readiness = compute_session_readiness(results)

    session.readiness_score = readiness["readiness_score"]
    session.weak_competencies = readiness["weak_competencies"]
    await db.commit()

    return {"data": readiness, "meta": {}, "error": None}


@router.get("/sessions")
async def list_sessions(user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    sessions = (
        await db.execute(
            select(InterviewPrepSession)
            .where(InterviewPrepSession.profile_id == profile.id)
            .order_by(InterviewPrepSession.created_at.desc())
        )
    ).scalars().all()
    return {
        "data": [
            {
                "id": str(s.id), "source_domain": s.source_domain, "target_domain": s.target_domain,
                "readiness_score": s.readiness_score, "created_at": s.created_at.isoformat(),
            }
            for s in sessions
        ],
        "meta": {}, "error": None,
    }


async def _get_owned_session(db: AsyncSession, user_id: UUID, session_id: UUID) -> InterviewPrepSession:
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one()
    session = (
        await db.execute(
            select(InterviewPrepSession).where(
                InterviewPrepSession.id == session_id, InterviewPrepSession.profile_id == profile.id
            )
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Session not found"})
    return session
