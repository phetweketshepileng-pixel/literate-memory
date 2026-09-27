"""Job matching prompt, v1. Versioned per ai-architecture.md section 4 —
edits go in a new file (job_matching_v2.py), never in-place here."""
from __future__ import annotations

SYSTEM_PROMPT = """You are an expert technical recruiter assessing candidate-to-job fit.

Rules you must follow:
- Base every judgment ONLY on the profile and job details given below. Never
  invent skills, certifications, or experience the candidate did not state.
- "strengths" must be things the candidate's profile plausibly demonstrates
  for THIS job, not a generic list of their skills.
- "missing_skills" must come from the job's stated requirements, not general
  assumptions about the role.
- Respond with ONLY a JSON object matching the given schema. No prose,
  no markdown, no explanation outside the JSON.
"""

USER_PROMPT_TEMPLATE = """CANDIDATE PROFILE
Current role: {current_role}
Years of experience: {years_experience}
Industry: {industry}
Confirmed skills: {skills_list}
Career transition target: {career_transition_target}

JOB POSTING
Title: {job_title}
Company: {company}
Requirements / description (relevant excerpt): {job_requirements_excerpt}

Score this candidate's fit for this specific job and return the JSON object.
"""


def build_prompt(
    *,
    current_role: str,
    years_experience: int,
    industry: str,
    skills_list: list[str],
    career_transition_target: str | None,
    job_title: str,
    company: str,
    job_requirements_excerpt: str,
) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt). Caller is responsible for
    truncating job_requirements_excerpt to the relevant section before
    calling this (see ai-architecture.md section 5, token optimization)."""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        current_role=current_role,
        years_experience=years_experience,
        industry=industry,
        skills_list=", ".join(skills_list),
        career_transition_target=career_transition_target or "not specified",
        job_title=job_title,
        company=company,
        job_requirements_excerpt=job_requirements_excerpt,
    )
    return SYSTEM_PROMPT, user_prompt
