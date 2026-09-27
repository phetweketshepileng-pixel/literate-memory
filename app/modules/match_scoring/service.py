"""Match Scoring module business logic (Module 4). Pure functions here
(no DB, no AI provider) — the pre-filter is Stage 1 of the two-stage
pipeline in ai-job-hunter-ai-architecture.md section 3.1, and doubles as
the AI-unavailable fallback path (architecture doc section 7.4)."""
from __future__ import annotations

from app.ai.schemas import JobMatchResult

# Jobs below this pre-filter score never reach the LLM at all — see
# ai-architecture.md section 3.1, "the biggest single cost lever."
PRE_FILTER_MIN_SCORE = 35


def pre_filter_score(profile_skill_names: set[str], job_description: str) -> int:
    """Cheap, no-LLM keyword-overlap heuristic. A real implementation would
    use a local embedding model; this keyword version is the V1 baseline
    and also the degraded-mode fallback when AI is unavailable."""
    if not profile_skill_names:
        return 0
    description_lower = job_description.lower()
    hits = sum(1 for skill in profile_skill_names if skill.lower() in description_lower)
    return min(100, int((hits / max(len(profile_skill_names), 1)) * 100) + 20)


def passes_pre_filter(score: int) -> bool:
    return score >= PRE_FILTER_MIN_SCORE


def fallback_result(profile_skill_names: set[str], job_description: str) -> JobMatchResult:
    """Degraded output per ai-architecture.md section 7.4: keyword score
    only; gaps/recommendations left empty rather than fabricated."""
    description_lower = job_description.lower()
    strengths = [s for s in profile_skill_names if s.lower() in description_lower]
    return JobMatchResult(
        match_score=pre_filter_score(profile_skill_names, job_description),
        strengths=strengths,
        missing_skills=[],
        experience_gaps=[],
        recommendations=[],
    )
