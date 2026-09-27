"""Ranking logic — architecture doc section 6. Two contexts, two functions:
search results get the full blended score, the dashboard gets a simple
match-score sort. Weights are module-level constants, deliberately not
buried in a query, so they're easy to find and tune without touching the
query logic itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# Tunable without touching query logic — see architecture doc section 6.1.
WEIGHT_MATCH_SCORE = 0.40
WEIGHT_RECENCY = 0.25
WEIGHT_HIDDEN_GEM = 0.20
WEIGHT_COMPLETENESS = 0.15

RECENCY_DECAY_DAYS = 14
HIDDEN_GEM_BOOST_POINTS = 100  # full weight applied when true, 0 otherwise


@dataclass
class RankableJob:
    job_id: str
    match_score: int  # 0-100; 0 if not yet scored for this profile
    date_posted: date | None
    is_hidden_gem: bool
    has_salary: bool
    description_length: int


def recency_score(date_posted: date | None) -> float:
    """Linear decay to 0 over RECENCY_DECAY_DAYS; jobs with no date get a
    neutral mid-score rather than being penalized for missing data."""
    if date_posted is None:
        return 50.0
    age_days = (date.today() - date_posted).days
    if age_days <= 0:
        return 100.0
    if age_days >= RECENCY_DECAY_DAYS:
        return 0.0
    return 100.0 * (1 - age_days / RECENCY_DECAY_DAYS)


def completeness_score(has_salary: bool, description_length: int) -> float:
    score = 0.0
    if has_salary:
        score += 50.0
    # description length contributes up to the other 50 points, saturating
    # at 500 characters — a one-line posting shouldn't score near-zero, but
    # shouldn't compete with a thorough one either.
    score += min(50.0, (description_length / 500.0) * 50.0)
    return score


def search_rank_score(job: RankableJob) -> float:
    """The blended default sort for Job Search results — architecture doc
    section 6.1. Callers needing 'sort by date' or 'sort by match only'
    bypass this entirely and sort on the raw column instead; this function
    is only for the default/blended view."""
    hidden_gem_points = HIDDEN_GEM_BOOST_POINTS if job.is_hidden_gem else 0.0

    return (
        WEIGHT_MATCH_SCORE * job.match_score
        + WEIGHT_RECENCY * recency_score(job.date_posted)
        + WEIGHT_HIDDEN_GEM * hidden_gem_points
        + WEIGHT_COMPLETENESS * completeness_score(job.has_salary, job.description_length)
    )


def rank_search_results(jobs: list[RankableJob]) -> list[RankableJob]:
    return sorted(jobs, key=search_rank_score, reverse=True)


def rank_dashboard_top_matches(jobs: list[RankableJob], limit: int = 5) -> list[RankableJob]:
    """Simpler than search ranking, per architecture doc section 6.2 — pure
    match_score, no recency/hidden-gem/completeness blending. The dashboard
    is a fast honest snapshot, not a discovery surface."""
    return sorted(jobs, key=lambda j: j.match_score, reverse=True)[:limit]
