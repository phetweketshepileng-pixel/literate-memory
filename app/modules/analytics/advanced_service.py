"""Advanced analytics business logic — see
ai-job-hunter-advanced-analytics.md sections 1-5. Pure functions only, no
DB access, following the same discipline as
app/modules/analytics/service.py: business rules get a unit test before
they're wired into a nightly snapshot job or a router.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# ===================== Section 2: Application Conversion Funnel =====================

FUNNEL_STAGES = ("discovered", "viewed", "saved", "applying", "submitted", "screening", "interview", "offer")


@dataclass
class JobFunnelProgress:
    """One job's furthest-reached funnel stage for a profile, built by the
    caller from job_engagement_events + applications + stage history."""
    reached_stages: set[str]  # e.g. {"discovered", "viewed", "saved", "applying"}


def compute_funnel_counts(progresses: list[JobFunnelProgress]) -> dict[str, int]:
    """Standard funnel counting: a job counts toward a stage if it reached
    AT LEAST that stage, per advanced-analytics.md section 2 — mirrors
    compute_rates_from_history's existing 'ever reached' design rather than
    a current-stage snapshot."""
    return {
        stage: sum(1 for p in progresses if stage in p.reached_stages)
        for stage in FUNNEL_STAGES
    }


def compute_funnel_conversion_rates(counts: dict[str, int]) -> dict[str, float | None]:
    """Conversion rate between each adjacent stage pair. None (not 0) when
    the prior stage had zero jobs — an undefined rate, not a zero rate."""
    rates: dict[str, float | None] = {}
    for i in range(1, len(FUNNEL_STAGES)):
        prev_stage, stage = FUNNEL_STAGES[i - 1], FUNNEL_STAGES[i]
        prev_count = counts.get(prev_stage, 0)
        key = f"{prev_stage}_to_{stage}"
        if prev_count == 0:
            rates[key] = None
        else:
            rates[key] = round(100 * counts.get(stage, 0) / prev_count, 2)
    return rates


def identify_weakest_funnel_step(rates: dict[str, float | None]) -> str | None:
    """Points the UI/user at the single biggest drop-off — directly serves
    the platform's stated goal of showing users what's blocking interviews,
    per advanced-analytics.md section 2."""
    defined = {k: v for k, v in rates.items() if v is not None}
    if not defined:
        return None
    return min(defined, key=defined.get)


# ===================== Section 1: Recruiter Engagement =====================

@dataclass
class EmailEvent:
    sent_at: datetime
    opened_at: datetime | None = None
    clicked_at: datetime | None = None
    replied_at: datetime | None = None
    interview_requested: bool = False
    tone: str | None = None


def compute_recruiter_engagement(emails: list[EmailEvent]) -> dict:
    sent = len(emails)
    if sent == 0:
        return {
            "emails_sent": 0, "emails_opened": 0, "emails_clicked": 0, "emails_replied": 0,
            "interview_requests": 0, "send_to_open_rate": None, "open_to_reply_rate": None,
            "interview_request_rate": None, "avg_hours_to_first_response": None,
        }

    opened = sum(1 for e in emails if e.opened_at is not None)
    clicked = sum(1 for e in emails if e.clicked_at is not None)
    replied = sum(1 for e in emails if e.replied_at is not None)
    interview_requests = sum(1 for e in emails if e.interview_requested)

    response_hours = [
        (e.replied_at - e.sent_at).total_seconds() / 3600 for e in emails if e.replied_at is not None
    ]

    return {
        "emails_sent": sent,
        "emails_opened": opened,
        "emails_clicked": clicked,
        "emails_replied": replied,
        "interview_requests": interview_requests,
        "send_to_open_rate": round(100 * opened / sent, 2),
        "open_to_reply_rate": round(100 * replied / opened, 2) if opened > 0 else None,
        "interview_request_rate": round(100 * interview_requests / sent, 2),
        "avg_hours_to_first_response": round(sum(response_hours) / len(response_hours), 2)
        if response_hours else None,
    }


def compute_engagement_score(email: EmailEvent) -> int:
    """Weighted composite per advanced-analytics.md section 1 — used to
    rank 'top engaged companies/recruiters'."""
    score = 0
    if email.opened_at is not None:
        score += 1
    if email.clicked_at is not None:
        score += 2
    if email.replied_at is not None:
        score += 5
    if email.interview_requested:
        score += 10
    return score


def breakdown_by_tone(emails: list[EmailEvent]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for email in emails:
        if email.tone is None:
            continue
        bucket = result.setdefault(email.tone, {"sent": 0, "replied": 0})
        bucket["sent"] += 1
        if email.replied_at is not None:
            bucket["replied"] += 1
    return result


# ===================== Section 3: Interview Conversion Tracking =====================

@dataclass
class ApplicationOutcomeDetail:
    reached_interview: bool
    reached_offer: bool
    cv_variant: str | None  # 'ats' | 'recruiter_friendly' | None
    match_score: int | None


def _match_score_band(score: int) -> str:
    if score >= 80:
        return "80-100"
    if score >= 60:
        return "60-79"
    if score >= 40:
        return "40-59"
    return "0-39"


def breakdown_interview_rate_by_cv_variant(outcomes: list[ApplicationOutcomeDetail]) -> dict[str, float | None]:
    by_variant: dict[str, list[ApplicationOutcomeDetail]] = {}
    for o in outcomes:
        if o.cv_variant is None:
            continue
        by_variant.setdefault(o.cv_variant, []).append(o)

    return {
        variant: round(100 * sum(1 for o in group if o.reached_interview) / len(group), 2)
        for variant, group in by_variant.items()
    }


def breakdown_interview_rate_by_match_score_band(outcomes: list[ApplicationOutcomeDetail]) -> dict[str, float | None]:
    by_band: dict[str, list[ApplicationOutcomeDetail]] = {}
    for o in outcomes:
        if o.match_score is None:
            continue
        by_band.setdefault(_match_score_band(o.match_score), []).append(o)

    return {
        band: round(100 * sum(1 for o in group if o.reached_interview) / len(group), 2)
        for band, group in by_band.items()
    }


# ===================== Section 4: Source Performance Tracking =====================

@dataclass
class SourceApplicationOutcome:
    source_id: str
    reached_interview: bool
    match_score: int
    is_hidden_gem: bool


def compute_source_performance(outcomes: list[SourceApplicationOutcome]) -> dict[str, dict]:
    by_source: dict[str, list[SourceApplicationOutcome]] = {}
    for o in outcomes:
        by_source.setdefault(o.source_id, []).append(o)

    result: dict[str, dict] = {}
    for source_id, group in by_source.items():
        n = len(group)
        result[source_id] = {
            "applications_submitted": n,
            "interview_rate": round(100 * sum(1 for o in group if o.reached_interview) / n, 2),
            "avg_match_score": round(sum(o.match_score for o in group) / n, 2),
            "hidden_gem_ratio": round(100 * sum(1 for o in group if o.is_hidden_gem) / n, 2),
        }
    return result


def rank_sources_by_interview_rate(source_performance: dict[str, dict]) -> list[str]:
    """Best-performing sources first — feeds both the user-facing 'which
    sources work for me' view and, platform-wide, Job Discovery Engine
    prioritization per advanced-analytics.md section 4."""
    return sorted(
        source_performance.keys(),
        key=lambda sid: source_performance[sid]["interview_rate"],
        reverse=True,
    )


# ===================== Section 5: Career Progression =====================

def compute_skill_gap_closure(previous_month_gaps: dict[str, int], current_month_gaps: dict[str, int]) -> list[dict]:
    """For each skill that appeared as a missing_skill in either month,
    the % change in how often it appears — negative means the gap is
    closing (appearing less often in new matches)."""
    all_skills = set(previous_month_gaps) | set(current_month_gaps)
    results = []
    for skill in all_skills:
        prev = previous_month_gaps.get(skill, 0)
        curr = current_month_gaps.get(skill, 0)
        if prev == 0:
            change_pct = None if curr == 0 else 100.0  # newly appearing gap
        else:
            change_pct = round(100 * (curr - prev) / prev, 2)
        results.append({"skill": skill, "gap_frequency_change_pct": change_pct, "current_count": curr})
    return results


def top_closing_skill_gaps(closure_data: list[dict], limit: int = 5) -> list[dict]:
    """Skills whose gap frequency is dropping fastest (most negative
    change), excluding newly-appearing or unchanged/undefined ones."""
    closing = [d for d in closure_data if d["gap_frequency_change_pct"] is not None and d["gap_frequency_change_pct"] < 0]
    return sorted(closing, key=lambda d: d["gap_frequency_change_pct"])[:limit]


@dataclass
class MonthlyMatchSummary:
    month: str  # "YYYY-MM"
    avg_match_score: float


def compute_match_score_trend(summaries: list[MonthlyMatchSummary]) -> dict:
    """Simple trend classification over the available months — 'improving'
    requires at least 2 points and a positive slope end-to-end; anything
    else is reported as insufficient data or flat/declining rather than
    guessed at."""
    if len(summaries) < 2:
        return {"trend": "insufficient_data", "change_pct": None}

    ordered = sorted(summaries, key=lambda s: s.month)
    first, last = ordered[0], ordered[-1]
    if first.avg_match_score == 0:
        return {"trend": "insufficient_data", "change_pct": None}

    change_pct = round(100 * (last.avg_match_score - first.avg_match_score) / first.avg_match_score, 2)
    if change_pct > 2:
        trend = "improving"
    elif change_pct < -2:
        trend = "declining"
    else:
        trend = "flat"
    return {"trend": trend, "change_pct": change_pct}
