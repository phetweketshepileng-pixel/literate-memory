from datetime import datetime, timedelta

from app.modules.analytics.advanced_service import (
    ApplicationOutcomeDetail,
    EmailEvent,
    JobFunnelProgress,
    MonthlyMatchSummary,
    SourceApplicationOutcome,
    breakdown_by_tone,
    breakdown_interview_rate_by_cv_variant,
    breakdown_interview_rate_by_match_score_band,
    compute_engagement_score,
    compute_funnel_conversion_rates,
    compute_funnel_counts,
    compute_match_score_trend,
    compute_recruiter_engagement,
    compute_skill_gap_closure,
    compute_source_performance,
    identify_weakest_funnel_step,
    rank_sources_by_interview_rate,
    top_closing_skill_gaps,
)


# ===================== Funnel =====================

def test_funnel_counts_jobs_reaching_at_least_each_stage():
    progresses = [
        JobFunnelProgress({"discovered", "viewed", "saved", "applying", "submitted"}),
        JobFunnelProgress({"discovered", "viewed"}),
        JobFunnelProgress({"discovered"}),
    ]
    counts = compute_funnel_counts(progresses)
    assert counts["discovered"] == 3
    assert counts["viewed"] == 2
    assert counts["saved"] == 1
    assert counts["interview"] == 0


def test_funnel_job_that_reached_interview_then_rejected_still_counts():
    # mirrors the same "ever reached" rule as compute_rates_from_history
    progress = JobFunnelProgress({"discovered", "viewed", "saved", "applying", "submitted", "screening", "interview"})
    counts = compute_funnel_counts([progress])
    assert counts["interview"] == 1


def test_conversion_rates_between_adjacent_stages():
    counts = {"discovered": 100, "viewed": 80, "saved": 40, "applying": 20, "submitted": 20,
              "screening": 10, "interview": 5, "offer": 1}
    rates = compute_funnel_conversion_rates(counts)
    assert rates["discovered_to_viewed"] == 80.0
    assert rates["viewed_to_saved"] == 50.0
    assert rates["screening_to_interview"] == 50.0


def test_conversion_rate_none_when_prior_stage_is_zero():
    counts = {stage: 0 for stage in compute_funnel_counts([])}
    rates = compute_funnel_conversion_rates(counts)
    assert all(v is None for v in rates.values())


def test_weakest_funnel_step_identifies_lowest_rate():
    rates = {"discovered_to_viewed": 90.0, "viewed_to_saved": 20.0, "saved_to_applying": 80.0}
    assert identify_weakest_funnel_step(rates) == "viewed_to_saved"


def test_weakest_funnel_step_ignores_undefined_rates():
    rates = {"a_to_b": None, "b_to_c": 50.0, "c_to_d": None}
    assert identify_weakest_funnel_step(rates) == "b_to_c"


def test_weakest_funnel_step_none_when_all_undefined():
    assert identify_weakest_funnel_step({"a_to_b": None}) is None


# ===================== Recruiter Engagement =====================

def _email(sent_days_ago=5, opened=False, clicked=False, replied_hours_after_open=None, interview=False, tone=None):
    sent_at = datetime.now() - timedelta(days=sent_days_ago)
    opened_at = sent_at + timedelta(hours=1) if opened else None
    clicked_at = sent_at + timedelta(hours=2) if clicked else None
    replied_at = (opened_at + timedelta(hours=replied_hours_after_open)) if (opened_at and replied_hours_after_open is not None) else None
    return EmailEvent(sent_at=sent_at, opened_at=opened_at, clicked_at=clicked_at, replied_at=replied_at,
                       interview_requested=interview, tone=tone)


def test_recruiter_engagement_empty_list():
    result = compute_recruiter_engagement([])
    assert result["emails_sent"] == 0
    assert result["send_to_open_rate"] is None


def test_recruiter_engagement_rates_computed_correctly():
    emails = [
        _email(opened=True, replied_hours_after_open=5, interview=True),
        _email(opened=True, replied_hours_after_open=None),
        _email(opened=False),
        _email(opened=False),
    ]
    result = compute_recruiter_engagement(emails)
    assert result["emails_sent"] == 4
    assert result["emails_opened"] == 2
    assert result["send_to_open_rate"] == 50.0
    assert result["open_to_reply_rate"] == 50.0  # 1 of 2 opened replied
    assert result["interview_request_rate"] == 25.0


def test_recruiter_engagement_open_to_reply_none_when_never_opened():
    emails = [_email(opened=False)]
    result = compute_recruiter_engagement(emails)
    assert result["open_to_reply_rate"] is None


def test_engagement_score_weights_interview_highest():
    replied_only = EmailEvent(sent_at=datetime.now(), replied_at=datetime.now())
    interview = EmailEvent(sent_at=datetime.now(), interview_requested=True)
    assert compute_engagement_score(interview) > compute_engagement_score(replied_only)


def test_engagement_score_zero_for_no_engagement():
    email = EmailEvent(sent_at=datetime.now())
    assert compute_engagement_score(email) == 0


def test_breakdown_by_tone_tracks_sent_and_replied():
    emails = [
        _email(tone="formal", opened=True, replied_hours_after_open=1),
        _email(tone="formal", opened=False),
        _email(tone="friendly", opened=True, replied_hours_after_open=1),
    ]
    breakdown = breakdown_by_tone(emails)
    assert breakdown["formal"] == {"sent": 2, "replied": 1}
    assert breakdown["friendly"] == {"sent": 1, "replied": 1}


# ===================== Interview Conversion Breakdown =====================

def test_interview_rate_by_cv_variant():
    outcomes = [
        ApplicationOutcomeDetail(reached_interview=True, reached_offer=False, cv_variant="ats", match_score=80),
        ApplicationOutcomeDetail(reached_interview=False, reached_offer=False, cv_variant="ats", match_score=70),
        ApplicationOutcomeDetail(reached_interview=True, reached_offer=True, cv_variant="recruiter_friendly", match_score=90),
    ]
    result = breakdown_interview_rate_by_cv_variant(outcomes)
    assert result["ats"] == 50.0
    assert result["recruiter_friendly"] == 100.0


def test_interview_rate_by_cv_variant_ignores_none():
    outcomes = [ApplicationOutcomeDetail(reached_interview=True, reached_offer=False, cv_variant=None, match_score=80)]
    assert breakdown_interview_rate_by_cv_variant(outcomes) == {}


def test_interview_rate_by_match_score_band():
    outcomes = [
        ApplicationOutcomeDetail(reached_interview=True, reached_offer=False, cv_variant="ats", match_score=85),
        ApplicationOutcomeDetail(reached_interview=False, reached_offer=False, cv_variant="ats", match_score=45),
        ApplicationOutcomeDetail(reached_interview=True, reached_offer=False, cv_variant="ats", match_score=65),
    ]
    result = breakdown_interview_rate_by_match_score_band(outcomes)
    assert result["80-100"] == 100.0
    assert result["40-59"] == 0.0
    assert result["60-79"] == 100.0


# ===================== Source Performance =====================

def test_source_performance_grouped_correctly():
    outcomes = [
        SourceApplicationOutcome(source_id="board_a", reached_interview=True, match_score=80, is_hidden_gem=False),
        SourceApplicationOutcome(source_id="board_a", reached_interview=False, match_score=60, is_hidden_gem=False),
        SourceApplicationOutcome(source_id="career_page_b", reached_interview=True, match_score=90, is_hidden_gem=True),
    ]
    result = compute_source_performance(outcomes)
    assert result["board_a"]["applications_submitted"] == 2
    assert result["board_a"]["interview_rate"] == 50.0
    assert result["career_page_b"]["hidden_gem_ratio"] == 100.0


def test_rank_sources_by_interview_rate_descending():
    performance = {
        "low": {"interview_rate": 10.0},
        "high": {"interview_rate": 80.0},
        "mid": {"interview_rate": 40.0},
    }
    assert rank_sources_by_interview_rate(performance) == ["high", "mid", "low"]


# ===================== Career Progression =====================

def test_skill_gap_closure_negative_when_gap_shrinking():
    closure = compute_skill_gap_closure({"jira": 10}, {"jira": 5})
    jira = next(d for d in closure if d["skill"] == "jira")
    assert jira["gap_frequency_change_pct"] == -50.0


def test_skill_gap_closure_new_gap_appearing():
    closure = compute_skill_gap_closure({}, {"kubernetes": 3})
    kube = next(d for d in closure if d["skill"] == "kubernetes")
    assert kube["gap_frequency_change_pct"] == 100.0


def test_top_closing_skill_gaps_excludes_growing_gaps():
    closure = [
        {"skill": "jira", "gap_frequency_change_pct": -50.0, "current_count": 5},
        {"skill": "python", "gap_frequency_change_pct": 30.0, "current_count": 13},
        {"skill": "agile", "gap_frequency_change_pct": None, "current_count": 0},
    ]
    top = top_closing_skill_gaps(closure)
    assert [d["skill"] for d in top] == ["jira"]


def test_match_score_trend_improving():
    summaries = [
        MonthlyMatchSummary("2026-07", 60.0),
        MonthlyMatchSummary("2026-08", 68.0),
        MonthlyMatchSummary("2026-09", 75.0),
    ]
    result = compute_match_score_trend(summaries)
    assert result["trend"] == "improving"
    assert result["change_pct"] > 0


def test_match_score_trend_insufficient_data_with_one_point():
    result = compute_match_score_trend([MonthlyMatchSummary("2026-09", 70.0)])
    assert result["trend"] == "insufficient_data"


def test_match_score_trend_flat_within_threshold():
    summaries = [MonthlyMatchSummary("2026-08", 70.0), MonthlyMatchSummary("2026-09", 71.0)]
    result = compute_match_score_trend(summaries)
    assert result["trend"] == "flat"
