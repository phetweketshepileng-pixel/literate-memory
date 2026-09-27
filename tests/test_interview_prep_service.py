from app.modules.interview_prep.service import (
    QuestionResult,
    compute_session_readiness,
    identify_missing_star_components,
    score_star_structure,
    select_behavioral_questions,
    select_technical_questions,
    years_to_difficulty,
)


# ===================== Difficulty mapping =====================

def test_years_to_difficulty_boundaries():
    assert years_to_difficulty(0) == "junior"
    assert years_to_difficulty(2) == "junior"
    assert years_to_difficulty(3) == "mid"
    assert years_to_difficulty(7) == "mid"
    assert years_to_difficulty(8) == "senior"
    assert years_to_difficulty(20) == "senior"


# ===================== Technical question selection =====================

def test_select_technical_questions_respects_domain_and_difficulty():
    questions = select_technical_questions("business_analysis", "mid", count=2)
    assert len(questions) == 2
    assert all(isinstance(q, str) for q in questions)


def test_select_technical_questions_unknown_domain_returns_empty():
    questions = select_technical_questions("not_a_real_domain", "mid")
    assert questions == []


def test_select_technical_questions_invalid_difficulty_falls_back_to_mid():
    questions = select_technical_questions("data_analysis", "expert_level_nonsense", count=1)
    mid_questions = select_technical_questions("data_analysis", "mid", count=1)
    assert questions == mid_questions


def test_select_technical_questions_respects_count():
    questions = select_technical_questions("project_management", "senior", count=1)
    assert len(questions) == 1


# ===================== Behavioral question selection =====================

def test_select_behavioral_questions_pairs_with_reframing_hint():
    questions = select_behavioral_questions("collections", "business_analysis", count=3)
    assert len(questions) == 3
    assert any(q.reframing_hint is not None for q in questions)


def test_select_behavioral_questions_falls_back_to_generic_when_pathway_thin():
    questions = select_behavioral_questions("banking", "systems_analysis", count=5)
    assert len(questions) <= 5
    assert len(questions) > 0


def test_select_behavioral_questions_respects_count():
    questions = select_behavioral_questions("operations", "it_management", count=2)
    assert len(questions) == 2


# ===================== STAR scoring =====================

def test_star_score_full_structure_scores_high():
    answer = (
        "When I was working in collections, I had to resolve a dispute with a "
        "frustrated customer. I decided to review the account history myself "
        "and reached out directly to negotiate a payment plan. As a result, "
        "we recovered the full amount and the customer stayed with the bank."
    )
    result = score_star_structure(answer)
    assert result.has_situation
    assert result.has_task or result.has_action
    assert result.has_result
    assert result.score >= 60


def test_star_score_short_answer_scores_low():
    result = score_star_structure("I handled it well.")
    assert result.length_adequate is False
    assert result.score < 40


def test_star_score_empty_answer():
    result = score_star_structure("")
    assert result.score == 0
    assert result.has_situation is False


def test_star_score_bounded_0_to_100():
    long_answer = "when i had to i decided as a result " * 20
    result = score_star_structure(long_answer)
    assert 0 <= result.score <= 100


def test_missing_star_components_identifies_gaps():
    result = score_star_structure("I improved the process and reduced errors.")
    missing = identify_missing_star_components(result)
    assert "situation" in missing
    assert "task" in missing
    assert "result" not in missing


def test_missing_star_components_empty_when_all_present():
    answer = (
        "When faced with a backlog, I was responsible for clearing it. "
        "I decided to reprioritize the queue myself. As a result, turnaround improved."
    )
    result = score_star_structure(answer)
    missing = identify_missing_star_components(result)
    assert missing == []


# ===================== Session readiness =====================

def test_session_readiness_empty_results():
    readiness = compute_session_readiness([])
    assert readiness["readiness_score"] == 0
    assert readiness["questions_answered"] == 0


def test_session_readiness_averages_behavioral_scores():
    results = [
        QuestionResult("q1", "stakeholder management", star_score=80),
        QuestionResult("q2", "requirements gathering", star_score=60),
    ]
    readiness = compute_session_readiness(results)
    assert readiness["readiness_score"] == 70
    assert readiness["questions_answered"] == 2


def test_session_readiness_combines_behavioral_and_technical():
    results = [
        QuestionResult("q1", "stakeholder management", star_score=100),
        QuestionResult("q2", None, star_score=None, technical_correct=True),
        QuestionResult("q3", None, star_score=None, technical_correct=False),
    ]
    readiness = compute_session_readiness(results)
    assert readiness["readiness_score"] == 75


def test_session_readiness_flags_weak_competencies():
    results = [
        QuestionResult("q1", "stakeholder management", star_score=30),
        QuestionResult("q2", "requirements gathering", star_score=90),
    ]
    readiness = compute_session_readiness(results)
    assert "stakeholder management" in readiness["weak_competencies"]
    assert "requirements gathering" not in readiness["weak_competencies"]


def test_session_readiness_deduplicates_weak_competencies():
    results = [
        QuestionResult("q1", "stakeholder management", star_score=20),
        QuestionResult("q2", "stakeholder management", star_score=10),
    ]
    readiness = compute_session_readiness(results)
    assert readiness["weak_competencies"] == ["stakeholder management"]
