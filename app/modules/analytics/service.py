"""Analytics business logic (Module 9). `compute_pipeline_metrics` and
`compute_time_to_response` are pure functions — the nightly
analytics_snapshots materialization job and the live
/applications/dashboard endpoint both call the same logic, so the two
numbers can never silently drift apart."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

TERMINAL_POSITIVE = {"offer"}
TERMINAL_NEGATIVE = {"rejected", "closed"}
INTERVIEW_OR_BEYOND = {"interview", "assessment", "offer"}
RESPONSE_STAGES = {"screening", "interview", "assessment", "offer", "rejected"}


def compute_pipeline_metrics(stages: list[str]) -> dict:
    """Given the current stage of every tracked application, compute the
    dashboard's headline metrics. This is a snapshot of CURRENT stages
    (used by the live /applications/dashboard endpoint); rate metrics that
    need the full history (e.g. how many ever reached interview, not just
    those currently there) use compute_rates_from_history instead."""
    total = len(stages)
    counts = {stage: stages.count(stage) for stage in set(stages)}
    return {
        "total": total,
        "saved": counts.get("saved", 0),
        "applying": counts.get("applying", 0),
        "submitted": counts.get("submitted", 0),
        "screening": counts.get("screening", 0),
        "interview": counts.get("interview", 0),
        "assessment": counts.get("assessment", 0),
        "offer": counts.get("offer", 0),
        "rejected": counts.get("rejected", 0),
        "closed": counts.get("closed", 0),
    }


@dataclass
class ApplicationOutcome:
    """One application's relevant history for rate calculations — built by
    the caller from `applications` + `application_stage_history`."""
    submitted_at: datetime | None
    reached_interview: bool
    reached_offer: bool
    reached_rejected: bool
    first_response_at: datetime | None  # first stage change after 'submitted'


def compute_rates_from_history(outcomes: list[ApplicationOutcome]) -> dict:
    """The metrics that belong in analytics_snapshots — computed from full
    per-application outcomes, not just a current-stage snapshot, so an
    application that reached Interview and was later Rejected still counts
    toward interview_rate."""
    submitted = [o for o in outcomes if o.submitted_at is not None]
    submitted_count = len(submitted)

    if submitted_count == 0:
        return {
            "applications_submitted": 0,
            "interviews": 0,
            "offers": 0,
            "rejections": 0,
            "response_rate": None,
            "interview_rate": None,
            "offer_rate": None,
            "avg_time_to_response_days": None,
        }

    interviews = sum(1 for o in submitted if o.reached_interview)
    offers = sum(1 for o in submitted if o.reached_offer)
    rejections = sum(1 for o in submitted if o.reached_rejected)
    responded = [o for o in submitted if o.first_response_at is not None]

    response_times = [
        (o.first_response_at - o.submitted_at).days for o in responded if o.submitted_at is not None
    ]
    avg_response_days = round(sum(response_times) / len(response_times), 2) if response_times else None

    return {
        "applications_submitted": submitted_count,
        "interviews": interviews,
        "offers": offers,
        "rejections": rejections,
        "response_rate": round(100 * len(responded) / submitted_count, 2),
        "interview_rate": round(100 * interviews / submitted_count, 2),
        "offer_rate": round(100 * offers / submitted_count, 2),
        "avg_time_to_response_days": avg_response_days,
    }


def breakdown_by_key(items: list[tuple[str, bool]]) -> dict[str, int]:
    """Generic counter for 'applications by source' / 'applications by
    role' breakdowns: items is [(key, counts_as_submitted), ...]."""
    result: dict[str, int] = {}
    for key, counted in items:
        if counted:
            result[key] = result.get(key, 0) + 1
    return result
