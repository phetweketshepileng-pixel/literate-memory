from app.modules.cv_tailoring.service import (
    CVContent,
    compute_ats_score,
    compute_optimization_score,
    extract_keywords,
    find_unauthorized_claims,
    keyword_coverage,
)


def test_extract_keywords_ignores_short_words():
    kws = extract_keywords("I am a BA with SQL and Jira skills")
    assert "sql" in kws
    assert "jira" in kws
    assert "am" not in kws  # too short


def test_keyword_coverage_full_match():
    job_keywords = {"jira", "agile", "reporting"}
    cv_text = "Experienced in Jira, Agile methodology, and Reporting."
    matched, coverage = keyword_coverage(job_keywords, cv_text)
    assert coverage == 1.0
    assert matched == job_keywords


def test_keyword_coverage_partial_match():
    job_keywords = {"jira", "agile", "reporting", "python"}
    cv_text = "Experienced in Jira and Reporting."
    matched, coverage = keyword_coverage(job_keywords, cv_text)
    assert coverage == 0.5
    assert matched == {"jira", "reporting"}


def test_keyword_coverage_no_job_keywords_returns_zero():
    matched, coverage = keyword_coverage(set(), "anything")
    assert coverage == 0.0
    assert matched == set()


def test_ats_score_rewards_full_coverage_and_complete_sections():
    content = CVContent(
        summary="Experienced business analyst with strong stakeholder management skills.",
        experience_bullets=["Led Jira-based Agile sprints.", "Delivered reporting dashboards."],
        skills_section=["Jira", "Agile", "Reporting"],
    )
    score = compute_ats_score(content, {"jira", "agile", "reporting"})
    assert score >= 90


def test_ats_score_low_for_empty_cv():
    content = CVContent(summary="", experience_bullets=[], skills_section=[])
    score = compute_ats_score(content, {"jira", "agile"})
    assert score == 0


def test_ats_score_bounded_0_to_100():
    content = CVContent(
        summary="x" * 500,
        experience_bullets=["jira " * 50] * 10,
        skills_section=["jira"] * 20,
    )
    score = compute_ats_score(content, {"jira"})
    assert 0 <= score <= 100


def test_optimization_score_reflects_gap_closure():
    assert compute_optimization_score(added_keywords_count=3, job_keywords_count=3) == 100
    assert compute_optimization_score(added_keywords_count=1, job_keywords_count=4) == 25
    assert compute_optimization_score(added_keywords_count=0, job_keywords_count=0) == 100


def test_unauthorized_claims_flags_unfounded_skill():
    allowed = {"Stakeholder Management", "Reporting", "Excel"}
    tailored = "Expert in Stakeholder Management, Reporting, and advanced Kubernetes deployment."
    suspicious = find_unauthorized_claims(tailored, allowed)
    assert "kubernetes" in suspicious
    assert "reporting" not in suspicious


def test_unauthorized_claims_empty_when_fully_grounded():
    allowed = {"Stakeholder Management", "Reporting", "Excel"}
    tailored = "Skilled in Stakeholder Management, Reporting and Excel."
    suspicious = find_unauthorized_claims(tailored, allowed)
    assert suspicious == set()


def test_unauthorized_claims_ignores_common_words():
    allowed = {"Excel"}
    tailored = "Strong experience with Excel across many years, responsible for team results."
    suspicious = find_unauthorized_claims(tailored, allowed)
    assert suspicious == set()
