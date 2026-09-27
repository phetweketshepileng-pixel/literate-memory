from datetime import datetime, timedelta

from app.modules.analytics.service import (
    ApplicationOutcome,
    breakdown_by_key,
    compute_pipeline_metrics,
    compute_rates_from_history,
)


def test_pipeline_metrics_counts_each_stage():
    stages = ["saved", "saved", "applying", "interview", "offer"]
    metrics = compute_pipeline_metrics(stages)
    assert metrics["total"] == 5
    assert metrics["saved"] == 2
    assert metrics["applying"] == 1
    assert metrics["interview"] == 1
    assert metrics["offer"] == 1
    assert metrics["rejected"] == 0


def test_pipeline_metrics_empty_list():
    metrics = compute_pipeline_metrics([])
    assert metrics["total"] == 0
    assert metrics["saved"] == 0


def _outcome(submitted_days_ago=10, reached_interview=False, reached_offer=False,
             reached_rejected=False, responded_days_after_submit=None):
    submitted_at = datetime.now() - timedelta(days=submitted_days_ago) if submitted_days_ago is not None else None
    first_response_at = (
        submitted_at + timedelta(days=responded_days_after_submit)
        if submitted_at and responded_days_after_submit is not None
        else None
    )
    return ApplicationOutcome(
        submitted_at=submitted_at,
        reached_interview=reached_interview,
        reached_offer=reached_offer,
        reached_rejected=reached_rejected,
        first_response_at=first_response_at,
    )


def test_rates_with_no_submitted_applications_returns_none_rates():
    outcomes = [_outcome(submitted_days_ago=None)]
    result = compute_rates_from_history(outcomes)
    assert result["applications_submitted"] == 0
    assert result["response_rate"] is None
    assert result["interview_rate"] is None


def test_rates_computed_correctly_for_mixed_outcomes():
    outcomes = [
        _outcome(reached_interview=True, reached_offer=True, responded_days_after_submit=3),
        _outcome(reached_interview=True, responded_days_after_submit=5),
        _outcome(reached_rejected=True, responded_days_after_submit=2),
        _outcome(),  # submitted, no response yet
    ]
    result = compute_rates_from_history(outcomes)

    assert result["applications_submitted"] == 4
    assert result["interviews"] == 2
    assert result["offers"] == 1
    assert result["rejections"] == 1
    assert result["response_rate"] == 75.0  # 3 of 4 responded
    assert result["interview_rate"] == 50.0  # 2 of 4
    assert result["offer_rate"] == 25.0  # 1 of 4
    assert result["avg_time_to_response_days"] == round((3 + 5 + 2) / 3, 2)


def test_application_that_reached_interview_then_rejected_still_counts_toward_interview_rate():
    # this is the exact scenario compute_rates_from_history exists to get
    # right — a current-stage snapshot alone would miss this
    outcomes = [_outcome(reached_interview=True, reached_rejected=True, responded_days_after_submit=4)]
    result = compute_rates_from_history(outcomes)
    assert result["interviews"] == 1
    assert result["rejections"] == 1


def test_avg_response_time_none_when_nobody_responded():
    outcomes = [_outcome(responded_days_after_submit=None)]
    result = compute_rates_from_history(outcomes)
    assert result["avg_time_to_response_days"] is None
    assert result["response_rate"] == 0.0


def test_breakdown_by_key_counts_only_flagged_items():
    items = [("LinkedIn", True), ("LinkedIn", True), ("Company Site", True), ("Indeed", False)]
    result = breakdown_by_key(items)
    assert result == {"LinkedIn": 2, "Company Site": 1}
    assert "Indeed" not in result


def test_breakdown_by_key_empty_input():
    assert breakdown_by_key([]) == {}
