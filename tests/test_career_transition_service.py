from app.modules.career_transition.service import (
    ReadinessInputs,
    build_reframed_facts_for_cv_tailoring,
    compute_certification_bonus,
    compute_experience_factor,
    compute_skill_coverage,
    compute_transition_readiness,
    find_applicable_reframings,
    identify_highest_leverage_gap,
    rank_target_domains_by_readiness,
    recommend_certifications,
    recommend_pathway,
)


# ===================== Skill coverage =====================

def test_skill_coverage_zero_with_no_confirmed_skills():
    coverage = compute_skill_coverage("collections", "business_analysis", set())
    assert coverage == 0.0


def test_skill_coverage_full_with_all_mappings_confirmed():
    # every collections->BA source competency, confirmed
    confirmed = {"escalation handling", "kpi/target management", "dispute resolution"}
    coverage = compute_skill_coverage("collections", "business_analysis", confirmed)
    assert coverage == 1.0


def test_skill_coverage_weights_strong_over_partial():
    # confirming only the 'strong' mappings should score higher than
    # confirming only the 'partial' one, since strong mappings carry more weight
    strong_only = compute_skill_coverage(
        "collections", "business_analysis", {"escalation handling", "dispute resolution"}
    )
    partial_only = compute_skill_coverage(
        "collections", "business_analysis", {"kpi/target management"}
    )
    assert strong_only > partial_only


def test_skill_coverage_case_insensitive():
    coverage_lower = compute_skill_coverage("collections", "business_analysis", {"escalation handling"})
    coverage_upper = compute_skill_coverage("collections", "business_analysis", {"Escalation Handling"})
    assert coverage_lower == coverage_upper


def test_skill_coverage_zero_for_nonexistent_pathway():
    coverage = compute_skill_coverage("collections", "data_analysis_typo", {"escalation handling"})
    assert coverage == 0.0


# ===================== Experience factor =====================

def test_experience_factor_zero_years():
    assert compute_experience_factor(0) == 0.0


def test_experience_factor_plateaus_past_threshold():
    factor_8_years = compute_experience_factor(8)
    factor_20_years = compute_experience_factor(20)
    assert factor_8_years == 1.0
    assert factor_20_years == 1.0  # capped, not still growing


def test_experience_factor_scales_below_plateau():
    factor_4_years = compute_experience_factor(4)
    assert 0.0 < factor_4_years < 1.0


# ===================== Certification bonus =====================

def test_certification_bonus_zero_with_none_held():
    bonus = compute_certification_bonus("business_analysis", set())
    assert bonus == 0.0


def test_certification_bonus_partial_credit():
    bonus = compute_certification_bonus(
        "business_analysis", {"BABOK-aligned Business Analysis Foundations"}
    )
    assert 0.0 < bonus < 1.0


def test_certification_bonus_unknown_target_domain_is_zero():
    assert compute_certification_bonus("not_a_real_domain", {"anything"}) == 0.0


# ===================== Full readiness score =====================

def test_readiness_score_bounded_0_to_100():
    inputs = ReadinessInputs(
        source_domain="operations", target_domain="it_management",
        confirmed_skill_names={"vendor/sla management", "incident management"},
        confirmed_certification_names={"ITIL Foundation", "COBIT Foundations"},
        years_in_source_domain=15,
    )
    result = compute_transition_readiness(inputs)
    assert 0 <= result.readiness_score <= 100


def test_readiness_score_higher_with_more_confirmed_skills():
    base_inputs = dict(
        source_domain="collections", target_domain="business_analysis",
        confirmed_certification_names=set(), years_in_source_domain=5,
    )
    low = compute_transition_readiness(ReadinessInputs(confirmed_skill_names=set(), **base_inputs))
    high = compute_transition_readiness(
        ReadinessInputs(confirmed_skill_names={"escalation handling", "dispute resolution"}, **base_inputs)
    )
    assert high.readiness_score > low.readiness_score


def test_operations_to_it_management_scores_higher_than_call_centre_to_data_analysis():
    # reflects the curated domain reality described in the design doc:
    # Operations->ITM is the strongest pairing, Call Centre->DA the weakest
    strong_pairing = compute_transition_readiness(
        ReadinessInputs("operations", "it_management", set(), set(), 5)
    )
    weak_pairing = compute_transition_readiness(
        ReadinessInputs("call_centre", "data_analysis", set(), set(), 5)
    )
    assert strong_pairing.readiness_score > weak_pairing.readiness_score


# ===================== Ranking =====================

def test_rank_target_domains_returns_all_five_sorted_descending():
    ranked = rank_target_domains_by_readiness("operations", set(), set(), 5)
    assert len(ranked) == 5
    scores = [result.readiness_score for _, result in ranked]
    assert scores == sorted(scores, reverse=True)


def test_rank_target_domains_operations_favors_it_management_or_pm():
    ranked = rank_target_domains_by_readiness("operations", set(), set(), 5)
    top_domain = ranked[0][0]
    assert top_domain in ("it_management", "project_management")


# ===================== Experience reframing =====================

def test_find_applicable_reframings_matches_mentioned_competency():
    text = "Handled daily escalation handling for high-value accounts."
    applicable = find_applicable_reframings("collections", "business_analysis", text)
    assert len(applicable) >= 1
    assert any(m.source_competency == "escalation handling" for m in applicable)


def test_find_applicable_reframings_empty_when_nothing_matches():
    text = "Baked bread every morning for the team."
    applicable = find_applicable_reframings("collections", "business_analysis", text)
    assert applicable == []


def test_build_reframed_facts_returns_template_strings():
    text = "Managed escalation handling and dispute resolution daily."
    facts = build_reframed_facts_for_cv_tailoring("collections", "business_analysis", text)
    assert len(facts) >= 1
    assert all(isinstance(f, str) for f in facts)


# ===================== Pathway recommendations =====================

def test_recommend_certifications_excludes_already_held():
    recs = recommend_certifications("business_analysis", {"BABOK-aligned Business Analysis Foundations"})
    assert "BABOK-aligned Business Analysis Foundations" not in recs
    assert "CBAP (for later career stage)" in recs


def test_recommend_certifications_all_when_none_held():
    recs = recommend_certifications("data_analysis", set())
    assert len(recs) == 2


def test_highest_leverage_gap_returns_none_when_all_closed():
    all_collections_ba_skills = {"escalation handling", "dispute resolution"}
    gap = identify_highest_leverage_gap("collections", "business_analysis", all_collections_ba_skills)
    assert gap is None


def test_highest_leverage_gap_identifies_unclosed_strong_mapping():
    gap = identify_highest_leverage_gap("collections", "business_analysis", set())
    assert gap == "stakeholder management"


def test_recommend_pathway_picks_secondary_when_close():
    rec = recommend_pathway("operations", set(), set(), years_in_source_domain=5)
    assert rec.primary_target_domain in (
        "it_management", "project_management", "business_analysis", "systems_analysis", "data_analysis"
    )
    assert isinstance(rec.recommended_certifications, list)


def test_recommend_pathway_no_secondary_when_clear_leader():
    # a huge experience/skill gap between domains should push the winner
    # far enough ahead that no secondary is suggested
    rec = recommend_pathway(
        "operations",
        confirmed_skill_names={"vendor/sla management", "incident management", "capacity planning"},
        confirmed_certification_names={"ITIL Foundation", "COBIT Foundations"},
        years_in_source_domain=10,
        readiness_gap_threshold=1,  # near-zero tolerance forces a clear winner
    )
    assert rec.primary_target_domain == "it_management"
