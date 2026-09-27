"""Interview Preparation business logic. Question selection and STAR
scoring are deliberately deterministic (no AI call) for the same reason
CV Tailoring's ATS score is deterministic — this is instant, free
feedback; an optional AI-polish pass (following the same two-tier pattern
used in Career Transition's reframing) can layer richer qualitative
feedback on top without this module depending on it.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.modules.career_transition.service import get_mappings_for_pathway
from app.modules.interview_prep.domain_knowledge import (
    BEHAVIORAL_QUESTION_BANK,
    DIFFICULTIES,
    GENERIC_BEHAVIORAL_QUESTIONS,
    TECHNICAL_QUESTION_BANK,
)


def years_to_difficulty(years_experience: int) -> str:
    if years_experience < 3:
        return "junior"
    if years_experience < 8:
        return "mid"
    return "senior"


def select_technical_questions(target_domain: str, difficulty: str, count: int = 3) -> list[str]:
    if difficulty not in DIFFICULTIES:
        difficulty = "mid"
    bank = TECHNICAL_QUESTION_BANK.get(target_domain, {})
    questions = bank.get(difficulty, [])
    return questions[:count]


@dataclass
class BehavioralQuestion:
    question: str
    target_competency: str | None
    reframing_hint: str | None  # the user's own transferable-experience reframing, when one exists


def select_behavioral_questions(
    source_domain: str, target_domain: str, count: int = 3
) -> list[BehavioralQuestion]:
    """Pulls questions keyed by this pathway's transferable target
    competencies first (so the question can be paired with the user's own
    reframed experience via reframing_hint), falling back to generic
    behavioral questions if the pathway doesn't have enough coverage."""
    mappings = get_mappings_for_pathway(source_domain, target_domain)
    selected: list[BehavioralQuestion] = []

    for mapping in mappings:
        bank_questions = BEHAVIORAL_QUESTION_BANK.get(mapping.target_competency, [])
        for q in bank_questions:
            if len(selected) >= count:
                break
            selected.append(
                BehavioralQuestion(
                    question=q, target_competency=mapping.target_competency,
                    reframing_hint=mapping.reframing_template,
                )
            )
        if len(selected) >= count:
            break

    generic_index = 0
    while len(selected) < count and generic_index < len(GENERIC_BEHAVIORAL_QUESTIONS):
        selected.append(
            BehavioralQuestion(
                question=GENERIC_BEHAVIORAL_QUESTIONS[generic_index],
                target_competency=None, reframing_hint=None,
            )
        )
        generic_index += 1

    return selected


# ===================== STAR structure scoring (deterministic) =====================

_SITUATION_MARKERS = ("when", "at my previous", "in my role", "while working", "during", "at the time")
_TASK_MARKERS = ("needed to", "had to", "was responsible for", "my task", "the goal was", "i was asked")
_ACTION_MARKERS = ("i decided", "i implemented", "i led", "i created", "i built", "i reached out",
                   "i worked with", "i developed", "i organized", "i analyzed")
_RESULT_MARKERS = ("as a result", "this led to", "the outcome", "ultimately", "we achieved",
                    "resulted in", "improved", "reduced", "increased")

MIN_ANSWER_LENGTH_CHARS = 80


@dataclass
class StarScore:
    has_situation: bool
    has_task: bool
    has_action: bool
    has_result: bool
    length_adequate: bool
    score: int  # 0-100


def score_star_structure(answer_text: str) -> StarScore:
    """Deterministic heuristic: does the answer show signs of each STAR
    component, via marker phrases, plus a minimum length check (a
    one-sentence answer can't meaningfully cover all four components
    regardless of what phrases it contains)."""
    text_lower = answer_text.lower()

    has_situation = any(marker in text_lower for marker in _SITUATION_MARKERS)
    has_task = any(marker in text_lower for marker in _TASK_MARKERS)
    has_action = any(marker in text_lower for marker in _ACTION_MARKERS)
    has_result = any(marker in text_lower for marker in _RESULT_MARKERS)
    length_adequate = len(answer_text.strip()) >= MIN_ANSWER_LENGTH_CHARS

    components_present = sum([has_situation, has_task, has_action, has_result])
    component_score = (components_present / 4) * 80  # 80% of score from STAR coverage
    length_score = 20 if length_adequate else 0        # 20% from adequate depth

    return StarScore(
        has_situation=has_situation, has_task=has_task, has_action=has_action, has_result=has_result,
        length_adequate=length_adequate, score=round(component_score + length_score),
    )


def identify_missing_star_components(star_score: StarScore) -> list[str]:
    missing = []
    if not star_score.has_situation:
        missing.append("situation")
    if not star_score.has_task:
        missing.append("task")
    if not star_score.has_action:
        missing.append("action")
    if not star_score.has_result:
        missing.append("result")
    return missing


# ===================== Session readiness =====================

@dataclass
class QuestionResult:
    question: str
    target_competency: str | None
    star_score: int | None  # None for technical (non-behavioral) questions
    technical_correct: bool | None = None  # for technical questions, self- or AI-assessed


def compute_session_readiness(results: list[QuestionResult]) -> dict:
    if not results:
        return {"readiness_score": 0, "weak_competencies": [], "questions_answered": 0}

    behavioral = [r for r in results if r.star_score is not None]
    technical = [r for r in results if r.technical_correct is not None]

    behavioral_avg = sum(r.star_score for r in behavioral) / len(behavioral) if behavioral else None
    technical_rate = (
        100 * sum(1 for r in technical if r.technical_correct) / len(technical) if technical else None
    )

    components = [v for v in (behavioral_avg, technical_rate) if v is not None]
    readiness_score = round(sum(components) / len(components)) if components else 0

    weak_competencies = [
        r.target_competency for r in behavioral
        if r.target_competency is not None and r.star_score < 50
    ]

    return {
        "readiness_score": readiness_score,
        "weak_competencies": sorted(set(weak_competencies)),
        "questions_answered": len(results),
    }
