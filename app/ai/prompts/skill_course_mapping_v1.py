"""Skill → recommended course/certification mapping, v1. Generated ONCE
per distinct skill name platform-wide (not per user), refreshed on a
schedule — see ai-architecture.md section 3.5 and 5. This is the only
prompt in the platform that is never called per-request; it backs the
cached `skill_course_map:{skill}` entries in app/ai/cache.py."""
from __future__ import annotations

SYSTEM_PROMPT = """You recommend learning resources for professional skill gaps.

For each skill given, suggest ONE realistic course type or certification
path a working professional could pursue (category-level, e.g. "Jira
fundamentals course" or "Scrum Alliance CSM certification" — do not
recommend a specific paid vendor by brand name unless it is the
recognized industry-standard certification for that skill).

Respond with ONLY a JSON object: {"skill_name": "recommendation", ...}
for every skill in the input list.
"""

USER_PROMPT_TEMPLATE = """Skills needing a recommendation:
{skills_list}
"""


def build_prompt(*, skill_names: list[str]) -> tuple[str, str]:
    user_prompt = USER_PROMPT_TEMPLATE.format(
        skills_list="\n".join(f"- {s}" for s in skill_names)
    )
    return SYSTEM_PROMPT, user_prompt
