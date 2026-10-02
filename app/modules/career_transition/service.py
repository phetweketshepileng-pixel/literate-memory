"""Career Transition Intelligence Engine — pure business logic. See
ai-job-hunter-career-transition-engine.md sections 3-5. Every function
here is DB-free and deterministic, consuming the curated domain knowledge
in domain_knowledge.py plus data the caller loads from the profile."""
from __future__ import annotations

from dataclasses import dataclass

from app.modules.career_transition.domain_knowledge import (
    BASE_AFFINITY_MATRIX,
    TARGET_DOMAIN_CERTIFICATIONS,
    TRANSFER_STRENGTH_WEIGHTS,
    TRANSFERABLE_SKILL_MAPPINGS,
    TransferableSkillMapping,
)

# Section 3 — readiness score component weights
WEIGHT_BASE_AFFINITY = 0.30
WEIGHT_SKILL_COVERAGE = 0.35
WEIGHT_EXPERIENCE = 0.20
WEIGHT_CERTIFICATION = 0.15

EXPERIENCE_PLATEAU_YEARS = 8  # diminishing returns past this many years
CERTIFICATION_BONUS_CAP = 100  # capped contribution when fully certified


def get_mappings_for_pathway(source_domain: str, target_domain: str) -> list[TransferableSkillMapping]:
    return [
        m for m in TRANSFERABLE_SKILL_MAPPINGS
        if m.source_domain == source_domain and m.target_domain == target_domain
    ]


def compute_skill_coverage(
    source_domain: str, target_domain: str, confirmed_skill_names: set[str]
) -> float:
    """Fraction (0.0-1.0) of this pathway's transferable mappings that the
    user has actually confirmed, weighted by transfer strength — a user
    who confirmed only 'direct' mappings scores higher per-skill than one
    who confirmed only 'partial' ones."""
    mappings = get_mappings_for_pathway(source_domain, target_domain)
    if not mappings:
        return 0.0

    confirmed_lower = {s.lower() for s in confirmed_skill_names}
    total_weight = sum(TRANSFER_STRENGTH_WEIGHTS[m.transfer_strength] for m in mappings)
    if total_weight == 0:
        return 0.0

    matched_weight = sum(
        TRANSFER_STRENGTH_WEIGHTS[m.transfer_strength]
        for m in mappings
        if m.source_competency.lower() in confirmed_lower
    )
    return matched_weight / total_weight


def compute_experience_factor(years_in_source_domain: int) -> float:
    """0.0-1.0, diminishing returns past EXPERIENCE_PLATEAU_YEARS — depth
    of transferable competency matters more than raw tenure once a solid
    grounding is established."""
    if years_in_source_domain <= 0:
        return 0.0
    return min(1.0, years_in_source_domain / EXPERIENCE_PLATEAU_YEARS)


def compute_certification_bonus(target_domain: str, confirmed_certification_names: set[str]) -> float:
    """0.0-1.0: fraction of this target domain's recommended certifications
    the user already holds."""
    recommended = TARGET_DOMAIN_CERTIFICATIONS.get(target_domain, ())
    if not recommended:
        return 0.0
    confirmed_lower = {c.lower() for c in confirmed_certification_names}
    held = sum(1 for cert in recommended if cert.lower() in confirmed_lower)
    return held / len(recommended)


@dataclass
class ReadinessInputs:
    source_domain: str
    target_domain: str
    confirmed_skill_names: set[str]
    confirmed_certification_names: set[str]
    years_in_source_domain: int


@dataclass
class ReadinessResult:
    readiness_score: int
    base_affinity: int
    skill_coverage_pct: float
    experience_factor: float
    certification_bonus_pct: float


def compute_transition_readiness(inputs: ReadinessInputs) -> ReadinessResult:
    base_affinity = BASE_AFFINITY_MATRIX.get((inputs.source_domain, inputs.target_domain), 0)
    skill_coverage = compute_skill_coverage(
        inputs.source_domain, inputs.target_domain, inputs.confirmed_skill_names
    )
    experience_factor = compute_experience_factor(inputs.years_in_source_domain)
    certification_bonus = compute_certification_bonus(
        inputs.target_domain, inputs.confirmed_certification_names
    )

    score = (
        WEIGHT_BASE_AFFINITY * base_affinity
        + WEIGHT_SKILL_COVERAGE * (skill_coverage * 100)
        + WEIGHT_EXPERIENCE * (experience_factor * 100)
        + WEIGHT_CERTIFICATION * (certification_bonus * 100)
    )

    return ReadinessResult(
        readiness_score=round(min(100, score)),
        base_affinity=base_affinity,
        skill_coverage_pct=round(skill_coverage * 100, 2),
        experience_factor=round(experience_factor, 2),
        certification_bonus_pct=round(certification_bonus * 100, 2),
    )


def rank_target_domains_by_readiness(
    source_domain: str,
    confirmed_skill_names: set[str],
    confirmed_certification_names: set[str],
    years_in_source_domain: int,
) -> list[tuple[str, ReadinessResult]]:
    """Powers Career Coach AI's 'which role should I focus on' — ranks all
    the target domains for this specific user, not just the curated base
    affinity, per ai-job-hunter-career-transition-engine.md section 3."""
    from app.modules.career_transition.domain_knowledge import TARGET_DOMAINS

    results = [
        (
            target,
            compute_transition_readiness(
                ReadinessInputs(
                    source_domain=source_domain,
                    target_domain=target,
                    confirmed_skill_names=confirmed_skill_names,
                    confirmed_certification_names=confirmed_certification_names,
                    years_in_source_domain=years_in_source_domain,
                ),
            ),
        )
        for target in TARGET_DOMAINS
    ]
    return sorted(results, key=lambda pair: pair[1].readiness_score, reverse=True)


# ===================== Section 4: Experience Reframing =====================

def find_applicable_reframings(
    source_domain: str, target_domain: str, experience_text: str
) -> list[TransferableSkillMapping]:
    """Rule-based first pass (no AI call): which transferable mappings'
    source competency appears in this piece of the user's own experience
    text. The matched mappings' reframing_template is what gets handed to
    CV Tailoring as additional grounded facts."""
    text_lower = experience_text.lower()
    mappings = get_mappings_for_pathway(source_domain, target_domain)
    return [m for m in mappings if m.source_competency.lower() in text_lower]


def build_reframed_facts_for_cv_tailoring(
    source_domain: str, target_domain: str, experience_text: str
) -> list[str]:
    """Returns ready-to-use grounded fact strings for the CV Tailoring
    prompt (ai-job-hunter-career-transition-engine.md section 4) — these
    are curated reframing templates, not model-generated claims, which is
    what keeps the hallucination guard meaningfully tighter."""
    applicable = find_applicable_reframings(source_domain, target_domain, experience_text)
    return [m.reframing_template for m in applicable]


# ===================== Section 5: Recommended Pathway Steps =====================

def recommend_certifications(target_domain: str, confirmed_certification_names: set[str]) -> list[str]:
    """Certifications the user doesn't already hold, for this target."""
    recommended = TARGET_DOMAIN_CERTIFICATIONS.get(target_domain, ())
    confirmed_lower = {c.lower() for c in confirmed_certification_names}
    return [cert for cert in recommended if cert.lower() not in confirmed_lower]


def identify_highest_leverage_gap(
    source_domain: str, target_domain: str, confirmed_skill_names: set[str]
) -> str | None:
    """The target competency with the lowest coverage among this pathway's
    STRONG/DIRECT mappings (the ones that matter most) — the single
    highest-leverage thing to close next."""
    mappings = [
        m for m in get_mappings_for_pathway(source_domain, target_domain)
        if m.transfer_strength in ("direct", "strong")
    ]
    confirmed_lower = {s.lower() for s in confirmed_skill_names}
    unclosed = [m for m in mappings if m.source_competency.lower() not in confirmed_lower]
    if not unclosed:
        return None
    return unclosed[0].target_competency


@dataclass
class PathwayRecommendation:
    primary_target_domain: str
    primary_readiness_score: int
    secondary_target_domain: str | None
    highest_leverage_gap: str | None
    recommended_certifications: list[str]


def recommend_pathway(
    source_domain: str,
    confirmed_skill_names: set[str],
    confirmed_certification_names: set[str],
    years_in_source_domain: int,
    readiness_gap_threshold: int = 10,
) -> PathwayRecommendation:
    """Section 5's target-role sequencing recommendation: if one target
    domain scores meaningfully higher than the rest, recommend it as
    primary and the next-best as secondary rather than suggesting the user
    spread effort evenly across all five."""
    ranked = rank_target_domains_by_readiness(
        source_domain, confirmed_skill_names, confirmed_certification_names, years_in_source_domain
    )
    primary_domain, primary_result = ranked[0]
    secondary_domain = None
    if len(ranked) > 1:
        second_domain, second_result = ranked[1]
        if primary_result.readiness_score - second_result.readiness_score < readiness_gap_threshold:
            secondary_domain = second_domain

    return PathwayRecommendation(
        primary_target_domain=primary_domain,
        primary_readiness_score=primary_result.readiness_score,
        secondary_target_domain=secondary_domain,
        highest_leverage_gap=identify_highest_leverage_gap(
            source_domain, primary_domain, confirmed_skill_names
        ),
        recommended_certifications=recommend_certifications(primary_domain, confirmed_certification_names),
    )
