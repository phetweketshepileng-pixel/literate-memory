"""Profile module business logic. `compute_completion_score` is a pure
function (no DB access) so it's independently unit-testable — the router
calls it after loading a profile + its related rows."""
from __future__ import annotations

from dataclasses import dataclass

# Each field/section contributes points toward 100. Weighted toward the
# fields that actually drive matching/CV tailoring quality (skills, role,
# desired roles) rather than treating every field as equally important.
WEIGHTS = {
    "full_name": 5,
    "current_role": 10,
    "years_experience": 5,
    "industry": 5,
    "desired_roles": 15,
    "salary_expectations": 5,
    "location_preferences": 5,
    "work_mode_preference": 5,
    "skills": 25,        # most important for match quality — capped below
    "master_cv": 15,      # having ANY document of type master_cv
    "education": 5,
}
MIN_SKILLS_FOR_FULL_CREDIT = 5


@dataclass
class ProfileCompletionInput:
    full_name: str | None
    current_role: str | None
    years_experience: int | None
    industry: str | None
    desired_roles: list[str] | None
    salary_expectation_min: int | None
    location_preferences: list[str] | None
    work_mode_preference: str | None
    skill_count: int
    has_master_cv: bool
    education_count: int


def compute_completion_score(data: ProfileCompletionInput) -> tuple[int, list[str]]:
    """Returns (score 0-100, list of missing-field labels for the UI)."""
    score = 0
    missing: list[str] = []

    def award(condition: bool, field_key: str, label: str) -> None:
        nonlocal score
        if condition:
            score += WEIGHTS[field_key]
        else:
            missing.append(label)

    award(bool(data.full_name), "full_name", "Full name")
    award(bool(data.current_role), "current_role", "Current role")
    award(data.years_experience is not None, "years_experience", "Years of experience")
    award(bool(data.industry), "industry", "Industry")
    award(bool(data.desired_roles), "desired_roles", "Desired roles")
    award(data.salary_expectation_min is not None, "salary_expectations", "Salary expectations")
    award(bool(data.location_preferences), "location_preferences", "Location preferences")
    award(bool(data.work_mode_preference), "work_mode_preference", "Work mode preference")
    award(bool(data.has_master_cv), "master_cv", "Master CV upload")
    award(data.education_count > 0, "education", "Education")

    # Skills: partial credit scaled to MIN_SKILLS_FOR_FULL_CREDIT rather than
    # all-or-nothing, since 1 skill listed is meaningfully better than 0.
    skills_weight = WEIGHTS["skills"]
    if data.skill_count <= 0:
        missing.append("Skills")
    elif data.skill_count >= MIN_SKILLS_FOR_FULL_CREDIT:
        score += skills_weight
    else:
        score += int(skills_weight * (data.skill_count / MIN_SKILLS_FOR_FULL_CREDIT))
        missing.append(f"More skills (add {MIN_SKILLS_FOR_FULL_CREDIT - data.skill_count} more for full credit)")

    return min(100, score), missing
