import pytest

from app.modules.applications.service import (
    InvalidStageTransitionError,
    is_valid_transition,
    next_suggested_stage,
    validate_transition,
)


def test_forward_progression_is_valid():
    assert is_valid_transition("saved", "applying")
    assert is_valid_transition("applying", "submitted")
    assert is_valid_transition("submitted", "screening")
    assert is_valid_transition("screening", "interview")


def test_backward_move_within_active_pipeline_is_allowed():
    # user correcting a mis-click
    assert is_valid_transition("interview", "screening")


def test_same_stage_is_not_a_valid_transition():
    assert not is_valid_transition("saved", "saved")


def test_cannot_leave_terminal_stage():
    assert not is_valid_transition("rejected", "interview")
    assert not is_valid_transition("offer", "applying")
    assert not is_valid_transition("closed", "saved")


def test_any_active_stage_can_move_to_rejected():
    assert is_valid_transition("saved", "rejected")
    assert is_valid_transition("interview", "rejected")
    assert is_valid_transition("assessment", "rejected")


def test_offer_requires_having_passed_through_interview():
    assert not is_valid_transition("saved", "offer")
    assert not is_valid_transition("applying", "offer")
    assert not is_valid_transition("screening", "offer")


def test_offer_valid_from_interview_or_assessment():
    assert is_valid_transition("interview", "offer")
    assert is_valid_transition("assessment", "offer")


def test_unknown_stage_is_invalid():
    assert not is_valid_transition("saved", "not_a_real_stage")
    assert not is_valid_transition("not_a_real_stage", "saved")


def test_validate_transition_raises_with_details():
    with pytest.raises(InvalidStageTransitionError) as exc_info:
        validate_transition("rejected", "interview")
    assert exc_info.value.from_stage == "rejected"
    assert exc_info.value.to_stage == "interview"


def test_validate_transition_passes_silently_when_valid():
    validate_transition("saved", "applying")  # should not raise


def test_next_suggested_stage_follows_forward_order():
    assert next_suggested_stage("saved") == "applying"
    assert next_suggested_stage("screening") == "interview"
    assert next_suggested_stage("interview") == "assessment"


def test_next_suggested_stage_none_at_end_of_pipeline():
    assert next_suggested_stage("offer") is None
    assert next_suggested_stage("rejected") is None
