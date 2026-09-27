from app.modules.match_scoring.service import (
    PRE_FILTER_MIN_SCORE,
    fallback_result,
    passes_pre_filter,
    pre_filter_score,
)


def test_no_skills_scores_zero():
    assert pre_filter_score(set(), "Business Analyst role requiring Jira and Agile") == 0


def test_no_overlap_scores_low():
    score = pre_filter_score({"Welding", "Forklift Operation"}, "Business Analyst role requiring Jira")
    assert not passes_pre_filter(score)


def test_full_overlap_scores_high():
    skills = {"Stakeholder Management", "Reporting"}
    description = "We need Stakeholder Management and Reporting skills for this role."
    score = pre_filter_score(skills, description)
    assert passes_pre_filter(score)
    assert score <= 100


def test_score_is_case_insensitive():
    score_lower = pre_filter_score({"jira"}, "Requires JIRA experience")
    score_matched_case = pre_filter_score({"JIRA"}, "Requires JIRA experience")
    assert score_lower == score_matched_case


def test_score_capped_at_100():
    skills = {"Python", "SQL", "Excel"}
    description = "Python SQL Excel Python SQL Excel " * 10
    score = pre_filter_score(skills, description)
    assert score <= 100


def test_pre_filter_threshold_boundary():
    assert passes_pre_filter(PRE_FILTER_MIN_SCORE) is True
    assert passes_pre_filter(PRE_FILTER_MIN_SCORE - 1) is False


def test_fallback_result_only_includes_confirmed_strengths():
    skills = {"Stakeholder Management", "Jira", "Excel"}
    description = "Looking for someone strong in Stakeholder Management and Excel."
    result = fallback_result(skills, description)

    assert set(result.strengths) == {"Stakeholder Management", "Excel"}
    assert "Jira" not in result.strengths


def test_fallback_result_never_fabricates_gaps_or_recommendations():
    result = fallback_result({"Excel"}, "Excel required.")
    assert result.missing_skills == []
    assert result.experience_gaps == []
    assert result.recommendations == []
