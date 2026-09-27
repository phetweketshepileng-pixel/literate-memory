from app.modules.profile.service import ProfileCompletionInput, compute_completion_score


def _blank_input(**overrides) -> ProfileCompletionInput:
    base = dict(
        full_name=None,
        current_role=None,
        years_experience=None,
        industry=None,
        desired_roles=None,
        salary_expectation_min=None,
        location_preferences=None,
        work_mode_preference=None,
        skill_count=0,
        has_master_cv=False,
        education_count=0,
    )
    base.update(overrides)
    return ProfileCompletionInput(**base)


def test_empty_profile_scores_zero():
    score, missing = compute_completion_score(_blank_input())
    assert score == 0
    assert "Full name" in missing
    assert "Skills" in missing


def test_fully_complete_profile_scores_100():
    data = _blank_input(
        full_name="Thabo Nkosi",
        current_role="Collections Manager",
        years_experience=15,
        industry="Banking",
        desired_roles=["Business Analyst"],
        salary_expectation_min=500000,
        location_preferences=["Johannesburg"],
        work_mode_preference="hybrid",
        skill_count=8,
        has_master_cv=True,
        education_count=1,
    )
    score, missing = compute_completion_score(data)
    assert score == 100
    assert missing == []


def test_partial_skills_get_partial_credit_not_zero():
    zero_skills = _blank_input(skill_count=0)
    two_skills = _blank_input(skill_count=2)
    five_skills = _blank_input(skill_count=5)

    score_zero, _ = compute_completion_score(zero_skills)
    score_two, missing_two = compute_completion_score(two_skills)
    score_five, _ = compute_completion_score(five_skills)

    assert score_zero == 0
    assert 0 < score_two < score_five
    assert any("more skills" in m.lower() for m in missing_two)


def test_score_never_exceeds_100():
    # even with every optional bonus maxed, score is capped
    data = _blank_input(
        full_name="X", current_role="Y", years_experience=1, industry="Z",
        desired_roles=["A"], salary_expectation_min=1, location_preferences=["B"],
        work_mode_preference="remote", skill_count=999, has_master_cv=True, education_count=5,
    )
    score, _ = compute_completion_score(data)
    assert score <= 100


def test_missing_fields_labels_are_human_readable():
    _, missing = compute_completion_score(_blank_input(full_name="Set"))
    assert "Full name" not in missing
    assert "Current role" in missing
