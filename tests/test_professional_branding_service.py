from app.modules.professional_branding.service import (
    check_headline_role_consistency,
    check_skills_consistency,
    compute_brand_consistency,
    flag_generic_summary_language,
    suggest_linkedin_headline,
    suggest_summary_bullets,
)


# ===================== Headline consistency =====================

def test_headline_consistent_when_role_mentioned():
    check = check_headline_role_consistency("Collections Team Leader", "Collections Team Leader | Banking")
    assert check.is_consistent


def test_headline_inconsistent_when_role_completely_different():
    check = check_headline_role_consistency("Collections Team Leader", "Freelance Photographer")
    assert not check.is_consistent
    assert check.note is not None


def test_headline_check_handles_missing_data_gracefully():
    check = check_headline_role_consistency(None, None)
    assert check.is_consistent  # nothing to flag as inconsistent


def test_headline_check_one_side_missing():
    check = check_headline_role_consistency("Business Analyst", None)
    assert check.is_consistent  # can't compare, not a false flag


# ===================== Skills consistency =====================

def test_skills_consistent_when_all_present():
    check = check_skills_consistency({"Jira", "Agile"}, "Skilled in Jira and Agile methodologies.")
    assert check.is_consistent


def test_skills_flags_missing_from_linkedin():
    check = check_skills_consistency({"Jira", "Agile", "Excel"}, "Skilled in Jira only.")
    assert not check.is_consistent
    assert "agile" in check.note.lower() or "excel" in check.note.lower()


def test_skills_check_empty_cv_skills_is_consistent():
    check = check_skills_consistency(set(), "anything here")
    assert check.is_consistent


# ===================== Overall consistency score =====================

def test_consistency_score_all_passing():
    checks = [
        check_headline_role_consistency("BA", "BA | Transitioning"),
        check_skills_consistency({"Jira"}, "Jira expert"),
    ]
    report = compute_brand_consistency(checks)
    assert report.consistency_score == 100


def test_consistency_score_partial():
    checks = [
        check_headline_role_consistency("BA", "Photographer"),  # fails
        check_skills_consistency({"Jira"}, "Jira expert"),        # passes
    ]
    report = compute_brand_consistency(checks)
    assert report.consistency_score == 50


def test_consistency_score_empty_checks():
    report = compute_brand_consistency([])
    assert report.consistency_score == 100


# ===================== LinkedIn suggestions =====================

def test_suggest_headline_includes_role_and_target():
    headline = suggest_linkedin_headline("Collections Manager", "Business Analysis", "Stakeholder Management")
    assert "Collections Manager" in headline
    assert "Business Analysis" in headline


def test_suggest_headline_respects_character_limit():
    headline = suggest_linkedin_headline("X" * 300, "Y" * 300, "Z" * 300)
    assert len(headline) <= 220


def test_suggest_headline_works_without_top_strength():
    headline = suggest_linkedin_headline("Ops Manager", "IT Management", None)
    assert "Ops Manager" in headline


def test_suggest_summary_bullets_respects_limit():
    facts = ["fact one", "fact two", "fact three", "fact four"]
    bullets = suggest_summary_bullets(facts, limit=2)
    assert bullets == ["fact one", "fact two"]


def test_suggest_summary_bullets_empty_input():
    assert suggest_summary_bullets([]) == []


# ===================== Generic language flagging =====================

def test_flags_weak_opener():
    flagged = flag_generic_summary_language("I am a results-driven professional.")
    assert "results-driven" in flagged


def test_no_flags_for_specific_summary():
    flagged = flag_generic_summary_language("Led a 12-person collections team recovering R4.2M annually.")
    assert flagged == []
