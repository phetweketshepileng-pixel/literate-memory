"""Application Tracker business logic (Module 8). The stage transition
graph is a pure state machine — validated independently of the DB so an
invalid drag-and-drop move (e.g. Rejected -> Interview) is caught before
ever touching application_stage_history."""
from __future__ import annotations

STAGES = (
    "saved", "applying", "submitted", "screening", "interview",
    "assessment", "offer", "rejected", "closed",
)

TERMINAL_STAGES = {"offer", "rejected", "closed"}

# Forward progression is the common path; backward moves are allowed within
# the active pipeline (a user correcting a mis-click), but nothing may move
# OUT of a terminal stage — that requires creating a fresh application, not
# reopening a closed one, which keeps analytics' stage-history honest.
_FORWARD_ORDER = {
    "saved": 0, "applying": 1, "submitted": 2, "screening": 3,
    "interview": 4, "assessment": 5, "offer": 6,
}


class InvalidStageTransitionError(Exception):
    def __init__(self, from_stage: str, to_stage: str) -> None:
        self.from_stage = from_stage
        self.to_stage = to_stage
        super().__init__(f"Cannot move application from '{from_stage}' to '{to_stage}'")


def is_valid_transition(from_stage: str, to_stage: str) -> bool:
    if from_stage not in STAGES or to_stage not in STAGES:
        return False
    if from_stage == to_stage:
        return False  # no-op move isn't a transition
    if from_stage in TERMINAL_STAGES:
        return False  # nothing leaves a terminal stage

    if to_stage == "rejected" or to_stage == "closed":
        return True  # any active stage can be marked rejected/closed at any point

    # both sides are non-terminal pipeline stages (saved..offer): any move
    # is allowed, forward or backward, EXCEPT jumping straight to 'offer'
    # from before 'interview' — an offer without an interview stage on
    # record would silently corrupt the interview-rate analytics.
    if to_stage == "offer" and _FORWARD_ORDER.get(from_stage, -1) < _FORWARD_ORDER["interview"]:
        return False

    return True


def validate_transition(from_stage: str, to_stage: str) -> None:
    if not is_valid_transition(from_stage, to_stage):
        raise InvalidStageTransitionError(from_stage, to_stage)


def next_suggested_stage(current_stage: str) -> str | None:
    """Powers the 'Move to next stage' button in the Application Detail
    screen — the single most likely forward move, not an enforced path."""
    order = _FORWARD_ORDER.get(current_stage)
    if order is None:
        return None
    forward_stages = sorted(_FORWARD_ORDER.items(), key=lambda kv: kv[1])
    for stage, stage_order in forward_stages:
        if stage_order == order + 1:
            return stage
    return None
