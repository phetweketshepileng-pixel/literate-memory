"""Recruiter Intelligence Dashboard — pure aggregation logic. The
k-anonymity gate in this module is the single most important piece of
code in this feature: every aggregate function refuses to return a real
number below the contributor threshold, full stop. See
ai-job-hunter-recruiter-intelligence.md sections 2 and 4.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

K_ANONYMITY_THRESHOLD = 5


@dataclass
class ApplicationRecord:
    """One application's relevant fields for pooled aggregation. The
    caller filters to profiles with contributes_to_pooled_analytics=True
    BEFORE building this list — this module has no knowledge of consent
    and must never be trusted to enforce it; that's the caller's job, and
    this module only ever receives data that already cleared consent."""
    profile_id: str
    company_name: str
    source_domain: str | None
    submitted_at: datetime | None
    resolved_at: datetime | None  # offer or rejection timestamp
    reached_interview: bool


@dataclass
class EmailRecord:
    profile_id: str
    recruiter_id: str
    sent_at: datetime
    first_response_at: datetime | None


def _distinct_contributor_count(profile_ids: list[str]) -> int:
    return len(set(profile_ids))


def clears_threshold(contributor_count: int, threshold: int = K_ANONYMITY_THRESHOLD) -> bool:
    return contributor_count >= threshold


@dataclass
class RecruiterAggregate:
    contributing_user_count: int
    response_rate: float | None
    avg_hours_to_first_response: float | None


def compute_recruiter_aggregate(
    emails: list[EmailRecord], threshold: int = K_ANONYMITY_THRESHOLD
) -> RecruiterAggregate:
    """Aggregates ALL emails passed in as belonging to one recruiter — the
    caller groups by recruiter_id before calling this. Returns None
    metrics (not a computed-but-hidden number) below threshold, so a bug
    upstream can never accidentally leak a below-threshold value."""
    contributor_count = _distinct_contributor_count([e.profile_id for e in emails])

    if not clears_threshold(contributor_count, threshold):
        return RecruiterAggregate(
            contributing_user_count=contributor_count, response_rate=None, avg_hours_to_first_response=None
        )

    sent = len(emails)
    responded = [e for e in emails if e.first_response_at is not None]
    response_hours = [
        (e.first_response_at - e.sent_at).total_seconds() / 3600 for e in responded
    ]

    return RecruiterAggregate(
        contributing_user_count=contributor_count,
        response_rate=round(100 * len(responded) / sent, 2) if sent > 0 else None,
        avg_hours_to_first_response=round(sum(response_hours) / len(response_hours), 2)
        if response_hours else None,
    )


@dataclass
class CompanyAggregate:
    contributing_user_count: int
    avg_turnaround_days: float | None
    interview_rate_overall: float | None
    interview_rate_by_source_domain: dict[str, float]  # only segments that independently clear threshold


def compute_company_aggregate(
    applications: list[ApplicationRecord], threshold: int = K_ANONYMITY_THRESHOLD
) -> CompanyAggregate:
    """Aggregates ALL applications passed in as belonging to one company —
    caller groups by company_name (canonicalized, per the job-discovery
    dedup logic) before calling this."""
    submitted = [a for a in applications if a.submitted_at is not None]
    contributor_count = _distinct_contributor_count([a.profile_id for a in submitted])

    if not clears_threshold(contributor_count, threshold):
        return CompanyAggregate(
            contributing_user_count=contributor_count,
            avg_turnaround_days=None,
            interview_rate_overall=None,
            interview_rate_by_source_domain={},
        )

    resolved = [a for a in submitted if a.resolved_at is not None]
    turnaround_days = [
        (a.resolved_at - a.submitted_at).days for a in resolved
    ]
    avg_turnaround = round(sum(turnaround_days) / len(turnaround_days), 2) if turnaround_days else None

    interview_rate_overall = round(
        100 * sum(1 for a in submitted if a.reached_interview) / len(submitted), 2
    )

    by_domain = _compute_segment_interview_rates(submitted, threshold)

    return CompanyAggregate(
        contributing_user_count=contributor_count,
        avg_turnaround_days=avg_turnaround,
        interview_rate_overall=interview_rate_overall,
        interview_rate_by_source_domain=by_domain,
    )


def _compute_segment_interview_rates(
    submitted: list[ApplicationRecord], threshold: int
) -> dict[str, float]:
    """Section 4's per-segment independent gating: a domain segment is only
    included if IT ALONE has enough distinct contributors — a company can
    clear the overall threshold while one of its segments doesn't, and
    that segment must be silently omitted, not shown anyway."""
    by_domain: dict[str, list[ApplicationRecord]] = {}
    for app in submitted:
        if app.source_domain is None:
            continue
        by_domain.setdefault(app.source_domain, []).append(app)

    result: dict[str, float] = {}
    for domain, group in by_domain.items():
        domain_contributor_count = _distinct_contributor_count([a.profile_id for a in group])
        if not clears_threshold(domain_contributor_count, threshold):
            continue  # omitted entirely, never shown with an inadequate sample
        result[domain] = round(100 * sum(1 for a in group if a.reached_interview) / len(group), 2)

    return result


def rank_companies_for_source_domain(
    company_aggregates: dict[str, CompanyAggregate], source_domain: str
) -> list[tuple[str, float]]:
    """Ranks companies by their (independently-gated) interview rate for
    ONE specific source domain — the direct answer to 'companies most
    likely to interview candidates with my background'. Companies where
    that segment didn't clear the threshold are excluded, not ranked with
    a missing value."""
    scored = [
        (company, agg.interview_rate_by_source_domain[source_domain])
        for company, agg in company_aggregates.items()
        if source_domain in agg.interview_rate_by_source_domain
    ]
    return sorted(scored, key=lambda pair: pair[1], reverse=True)
