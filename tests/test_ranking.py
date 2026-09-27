from datetime import date, timedelta

from app.modules.job_discovery.ranking import (
    RECENCY_DECAY_DAYS,
    RankableJob,
    completeness_score,
    rank_dashboard_top_matches,
    rank_search_results,
    recency_score,
    search_rank_score,
)


def test_recency_score_today_is_max():
    assert recency_score(date.today()) == 100.0


def test_recency_score_decays_to_zero_at_window_edge():
    old_date = date.today() - timedelta(days=RECENCY_DECAY_DAYS)
    assert recency_score(old_date) == 0.0


def test_recency_score_none_date_is_neutral():
    assert recency_score(None) == 50.0


def test_completeness_score_rewards_salary_and_description():
    bare = completeness_score(has_salary=False, description_length=0)
    with_salary = completeness_score(has_salary=True, description_length=0)
    full = completeness_score(has_salary=True, description_length=1000)

    assert bare == 0.0
    assert with_salary == 50.0
    assert full == 100.0


def test_hidden_gem_boosts_rank_over_equal_match_non_gem():
    gem = RankableJob(
        job_id="a", match_score=70, date_posted=date.today(),
        is_hidden_gem=True, has_salary=True, description_length=500,
    )
    non_gem = RankableJob(
        job_id="b", match_score=70, date_posted=date.today(),
        is_hidden_gem=False, has_salary=True, description_length=500,
    )
    assert search_rank_score(gem) > search_rank_score(non_gem)


def test_strong_older_match_can_beat_weaker_fresh_match():
    strong_old = RankableJob(
        job_id="a", match_score=90, date_posted=date.today() - timedelta(days=10),
        is_hidden_gem=False, has_salary=True, description_length=500,
    )
    weak_fresh = RankableJob(
        job_id="b", match_score=40, date_posted=date.today(),
        is_hidden_gem=False, has_salary=True, description_length=500,
    )
    assert search_rank_score(strong_old) > search_rank_score(weak_fresh)


def test_rank_search_results_sorts_descending():
    jobs = [
        RankableJob("low", 20, date.today(), False, False, 0),
        RankableJob("high", 95, date.today(), True, True, 800),
        RankableJob("mid", 60, date.today(), False, True, 300),
    ]
    ranked = rank_search_results(jobs)
    assert [j.job_id for j in ranked] == ["high", "mid", "low"]


def test_dashboard_ranking_is_pure_match_score_no_hidden_gem_boost():
    jobs = [
        RankableJob("gem_lower_match", 50, date.today(), True, True, 500),
        RankableJob("plain_higher_match", 60, date.today(), False, True, 500),
    ]
    top = rank_dashboard_top_matches(jobs, limit=2)
    # unlike search ranking, dashboard must NOT let the hidden-gem flag
    # override a plain higher match score
    assert top[0].job_id == "plain_higher_match"


def test_dashboard_ranking_respects_limit():
    jobs = [RankableJob(str(i), i, date.today(), False, False, 0) for i in range(10)]
    top = rank_dashboard_top_matches(jobs, limit=3)
    assert len(top) == 3
    assert top[0].job_id == "9"
