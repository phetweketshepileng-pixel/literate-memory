"""Professional Branding module — closes the last gap named in
ai-job-hunter-platform-vision.md section 3. Checks consistency between a
user's CV/profile and their LinkedIn text, and reuses Career Transition's
reframing templates for headline/summary suggestions — no new AI calls or
domain data needed, this module composes what already exists.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.cv_tailoring.service import extract_keywords


@dataclass
class ConsistencyCheck:
    field: str
    cv_value: str | None
    linkedin_value: str | None
    is_consistent: bool
    note: str | None = None


def check_headline_role_consistency(cv_current_role: str | None, linkedin_headline: str | None) -> ConsistencyCheck:
    """A recruiter cross-checking CV and LinkedIn who sees different
    current roles is the single most damaging inconsistency this module
    can catch — everything else is refinement, this one is a red flag."""
    if not cv_current_role or not linkedin_headline:
        return ConsistencyCheck(
            "current_role", cv_current_role, linkedin_headline, is_consistent=True,
            note="Nothing to compare yet" if not (cv_current_role or linkedin_headline) else None,
        )

    cv_keywords = extract_keywords(cv_current_role)
    headline_keywords = extract_keywords(linkedin_headline)
    overlap = cv_keywords & headline_keywords

    is_consistent = len(overlap) > 0 or cv_current_role.lower() in linkedin_headline.lower()
    note = None if is_consistent else "Your LinkedIn headline doesn't mention your current role from your CV"
    return ConsistencyCheck("current_role", cv_current_role, linkedin_headline, is_consistent, note)


def check_skills_consistency(cv_skills: set[str], linkedin_skills_text: str) -> ConsistencyCheck:
    """Flags confirmed CV skills that are entirely absent from the
    LinkedIn skills section/summary — the most common branding gap for
    someone who filled out their platform profile more thoroughly than
    their LinkedIn."""
    if not cv_skills:
        return ConsistencyCheck("skills", None, linkedin_skills_text, is_consistent=True)

    linkedin_lower = linkedin_skills_text.lower()
    missing = {s for s in cv_skills if s.lower() not in linkedin_lower}
    is_consistent = len(missing) == 0
    note = (
        f"{len(missing)} confirmed skill(s) not mentioned on LinkedIn: {', '.join(sorted(missing)[:5])}"
        if missing else None
    )
    return ConsistencyCheck("skills", ", ".join(sorted(cv_skills)), linkedin_skills_text, is_consistent, note)


@dataclass
class BrandConsistencyReport:
    checks: list[ConsistencyCheck]
    consistency_score: int  # 0-100


def compute_brand_consistency(checks: list[ConsistencyCheck]) -> BrandConsistencyReport:
    if not checks:
        return BrandConsistencyReport(checks=[], consistency_score=100)
    consistent_count = sum(1 for c in checks if c.is_consistent)
    score = round(100 * consistent_count / len(checks))
    return BrandConsistencyReport(checks=checks, consistency_score=score)


# ===================== LinkedIn optimization suggestions =====================

def suggest_linkedin_headline(current_role: str, target_domain_label: str, top_strength: str | None) -> str:
    """A single, concrete headline suggestion built from data already on
    the profile — not a generic template. Kept short (LinkedIn headlines
    have a hard character limit recruiters actually see in search results)."""
    base = f"{current_role} → {target_domain_label}"
    if top_strength:
        suggestion = f"{base} | {top_strength}"
    else:
        suggestion = base
    return suggestion[:220]  # LinkedIn's headline character limit


def suggest_summary_bullets(reframed_facts: list[str], limit: int = 3) -> list[str]:
    """Reuses Career Transition's already-generated reframed experience
    facts (build_reframed_facts_for_cv_tailoring) as ready-to-use LinkedIn
    summary bullet suggestions — same grounded content, different surface,
    which is exactly the point of a branding consistency module: one
    source of truth, multiple presentations."""
    return reframed_facts[:limit]


_WEAK_OPENERS = ("i am a", "i'm a", "results-driven", "passionate about", "hard-working")


def flag_generic_summary_language(summary_text: str) -> list[str]:
    """Points out filler openers that make a summary indistinguishable
    from thousands of others — a lightweight, deterministic check, not an
    AI rewrite (consistent with this module's no-new-AI-call design)."""
    text_lower = summary_text.lower().strip()
    return [phrase for phrase in _WEAK_OPENERS if phrase in text_lower]
