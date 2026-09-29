from datetime import date

from app.modules.job_discovery.insights import FitInput, quick_fit, region_bucket

TODAY = date(2026, 9, 29)
PREFS = FitInput(desired_roles=["Business Analyst", "Systems Analyst"], skills=["SQL", "Stakeholder management", "Jira"],
                 location_preferences=["Johannesburg"], work_mode_preference="hybrid", today=TODAY)


def test_region_bucket():
    assert region_bucket("Sandton, Johannesburg") == "Johannesburg"
    assert region_bucket("Johannesburg, Gauteng") == "Johannesburg"
    assert region_bucket("Centurion, Gauteng") == "Pretoria"
    assert region_bucket("Midrand") == "Johannesburg"
    assert region_bucket("Vereeniging, Gauteng") == "Other Gauteng"
    assert region_bucket("Bellville, Western Cape") == "Cape Town / W. Cape"
    assert region_bucket("Remote") == "Remote"
    assert region_bucket("Berlin, Germany") == "Other / international"
    assert region_bucket(None, is_remote=True) == "Remote"
    assert region_bucket(None) == "Unspecified"


def test_exact_role_in_johannesburg_scores_high_with_reasons():
    fit = quick_fit("Senior Business Analyst - Payments", "Work with stakeholder management and SQL.",
                    "Sandton, Johannesburg", False, TODAY, PREFS)
    assert fit.score >= 80
    assert any("Business Analyst" in r for r in fit.reasons)
    assert any("SQL" in r for r in fit.reasons)
    assert any("Johannesburg" in r for r in fit.reasons)


def test_unrelated_job_scores_low():
    fit = quick_fit("Cyber Security Engineer", "Firewalls and SIEM.", "Remote", True, date(2026, 8, 1), PREFS)
    assert fit.score < 30


def test_partial_role_overlap():
    fit = quick_fit("Business Process Analyst", "", "Cape Town", False, None, PREFS)
    assert 20 <= fit.score <= 45  # 'business' + 'analyst' overlap, no exact phrase


def test_skill_matching_uses_word_boundaries():
    fit = quick_fit("Analyst", "We use PostgreSQL and nosql stores", None, False, None,
                    FitInput(skills=["SQL"], today=TODAY))
    assert fit.score == 0


def test_score_capped_at_100():
    many = FitInput(desired_roles=["analyst"], skills=[f"s{i}" for i in range(20)], location_preferences=["Remote"], today=TODAY)
    desc = " ".join(f"s{i}" for i in range(20))
    assert quick_fit("Analyst", desc, "Remote", True, TODAY, many).score <= 100
