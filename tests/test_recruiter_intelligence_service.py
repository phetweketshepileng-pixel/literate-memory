from datetime import datetime, timedelta

from app.modules.recruiter_intelligence.service import (
    K_ANONYMITY_THRESHOLD,
    ApplicationRecord,
    EmailRecord,
    clears_threshold,
    compute_company_aggregate,
    compute_recruiter_aggregate,
    rank_companies_for_source_domain,
)


# ===================== The core privacy gate =====================

def test_clears_threshold_boundary():
    assert clears_threshold(K_ANONYMITY_THRESHOLD) is True
    assert clears_threshold(K_ANONYMITY_THRESHOLD - 1) is False


def test_clears_threshold_zero_contributors():
    assert clears_threshold(0) is False


# ===================== Recruiter aggregate =====================

def _email(profile_id, sent_days_ago=10, responded_hours_after=None):
    sent_at = datetime.now() - timedelta(days=sent_days_ago)
    first_response_at = sent_at + timedelta(hours=responded_hours_after) if responded_hours_after is not None else None
    return EmailRecord(profile_id=profile_id, recruiter_id="r1", sent_at=sent_at, first_response_at=first_response_at)


def test_recruiter_aggregate_below_threshold_returns_none_metrics():
    # only 3 distinct contributors — below the default threshold of 5
    emails = [_email("p1"), _email("p2"), _email("p3", responded_hours_after=5)]
    result = compute_recruiter_aggregate(emails)
    assert result.contributing_user_count == 3
    assert result.response_rate is None
    assert result.avg_hours_to_first_response is None


def test_recruiter_aggregate_at_threshold_returns_real_metrics():
    emails = [_email(f"p{i}", responded_hours_after=(4 if i < 3 else None)) for i in range(5)]
    result = compute_recruiter_aggregate(emails)
    assert result.contributing_user_count == 5
    assert result.response_rate == 60.0  # 3 of 5 responded
    assert result.avg_hours_to_first_response == 4.0


def test_recruiter_aggregate_counts_distinct_profiles_not_email_count():
    # same profile sending 10 emails should NOT count as 10 contributors
    emails = [_email("p1", responded_hours_after=i) for i in range(10)]
    result = compute_recruiter_aggregate(emails)
    assert result.contributing_user_count == 1
    assert result.response_rate is None  # still below threshold


def test_recruiter_aggregate_never_leaks_a_number_below_threshold_even_with_extreme_data():
    # a stress test of the gate itself: even with wildly high response
    # rates, below-threshold data must never surface a real number
    emails = [_email("p1", responded_hours_after=1), _email("p2", responded_hours_after=1)]
    result = compute_recruiter_aggregate(emails)
    assert result.response_rate is None
    assert result.avg_hours_to_first_response is None


# ===================== Company aggregate =====================

def _application(profile_id, company="Acme", domain="operations", submitted_days_ago=30,
                  resolved_days_after_submit=None, interview=False):
    submitted_at = datetime.now() - timedelta(days=submitted_days_ago)
    resolved_at = submitted_at + timedelta(days=resolved_days_after_submit) if resolved_days_after_submit is not None else None
    return ApplicationRecord(
        profile_id=profile_id, company_name=company, source_domain=domain,
        submitted_at=submitted_at, resolved_at=resolved_at, reached_interview=interview,
    )


def test_company_aggregate_below_threshold_returns_none():
    apps = [_application(f"p{i}") for i in range(3)]
    result = compute_company_aggregate(apps)
    assert result.contributing_user_count == 3
    assert result.avg_turnaround_days is None
    assert result.interview_rate_overall is None
    assert result.interview_rate_by_source_domain == {}


def test_company_aggregate_at_threshold_computes_real_metrics():
    apps = [
        _application(f"p{i}", resolved_days_after_submit=10, interview=(i < 2))
        for i in range(5)
    ]
    result = compute_company_aggregate(apps)
    assert result.contributing_user_count == 5
    assert result.interview_rate_overall == 40.0  # 2 of 5
    assert result.avg_turnaround_days == 10.0


def test_company_aggregate_excludes_unsubmitted_applications():
    apps = [_application(f"p{i}") for i in range(10)]
    for a in apps:
        a.submitted_at = None  # simulate 'saved' applications never submitted
    result = compute_company_aggregate(apps)
    assert result.contributing_user_count == 0


def test_source_domain_segment_independently_gated():
    # 6 total contributors (clears overall threshold) but only 2 are from
    # 'collections' specifically (does NOT clear threshold for that segment)
    apps = (
        [_application(f"op{i}", domain="operations", interview=True) for i in range(4)]
        + [_application(f"col{i}", domain="collections", interview=True) for i in range(2)]
    )
    result = compute_company_aggregate(apps)
    assert result.contributing_user_count == 6
    assert result.interview_rate_overall is not None  # overall clears threshold
    assert "operations" not in result.interview_rate_by_source_domain  # only 4 < 5, still excluded
    assert "collections" not in result.interview_rate_by_source_domain  # only 2 < 5


def test_source_domain_segment_included_when_it_clears_threshold_alone():
    apps = [_application(f"op{i}", domain="operations", interview=(i < 3)) for i in range(6)]
    result = compute_company_aggregate(apps)
    assert "operations" in result.interview_rate_by_source_domain
    assert result.interview_rate_by_source_domain["operations"] == 50.0  # 3 of 6


def test_company_aggregate_none_source_domain_excluded_from_breakdown():
    apps = [_application(f"p{i}", domain=None) for i in range(10)]
    result = compute_company_aggregate(apps)
    assert result.interview_rate_by_source_domain == {}


# ===================== Ranking =====================

def test_rank_companies_only_includes_cleared_segments():
    apps_a = [_application(f"a{i}", company="A", domain="operations", interview=True) for i in range(6)]
    apps_b = [_application(f"b{i}", company="B", domain="operations", interview=False) for i in range(2)]  # below threshold

    aggregates = {
        "A": compute_company_aggregate(apps_a),
        "B": compute_company_aggregate(apps_b),
    }
    ranked = rank_companies_for_source_domain(aggregates, "operations")
    assert ranked == [("A", 100.0)]  # B excluded entirely, not ranked with a low/zero score


def test_rank_companies_sorted_descending():
    apps_high = [_application(f"h{i}", company="High", domain="operations", interview=True) for i in range(5)]
    apps_low = [_application(f"l{i}", company="Low", domain="operations", interview=(i < 1)) for i in range(5)]

    aggregates = {
        "High": compute_company_aggregate(apps_high),
        "Low": compute_company_aggregate(apps_low),
    }
    ranked = rank_companies_for_source_domain(aggregates, "operations")
    assert [c for c, _ in ranked] == ["High", "Low"]
