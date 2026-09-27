"""CV tailoring prompt, v1. Grounding against hallucination is the core
design constraint here — see ai-architecture.md section 4."""
from __future__ import annotations

SYSTEM_PROMPT = """You are an expert CV writer and ATS optimization specialist.

Hard rules — violating any of these makes your output unusable:
- You may ONLY use facts listed in "FACTS YOU MAY USE" below. Do not invent,
  infer, or embellish any skill, employer, title, date, or achievement that
  is not explicitly present there.
- Rewrite and reorder existing content to emphasize relevance to the target
  job and naturally incorporate the job's real keywords WHERE THEY ARE
  TRUE of the candidate — do not insert a keyword the candidate's facts
  don't support.
- Keep every date, employer name, and job title EXACTLY as given.
- Respond with ONLY a JSON object matching the given schema. No prose
  outside the JSON.
"""

USER_PROMPT_TEMPLATE = """FACTS YOU MAY USE
{facts_block}

TARGET JOB
Title: {job_title}
Company: {company}
Key requirements/keywords: {job_keywords}

VARIANT REQUESTED: {variant}
{variant_instruction}

Produce the tailored CV content and return the JSON object.
"""

VARIANT_INSTRUCTIONS = {
    "ats": (
        "ATS-optimized: plain, keyword-dense phrasing, standard section "
        "names, no stylistic flourishes that could confuse an ATS parser."
    ),
    "recruiter_friendly": (
        "Recruiter-friendly: more narrative and achievement-focused phrasing "
        "for a human reader, while covering the same facts."
    ),
}


def build_prompt(
    *,
    facts_block: str,
    job_title: str,
    company: str,
    job_keywords: list[str],
    variant: str,
) -> tuple[str, str]:
    """`facts_block` is a caller-assembled, labeled list of the candidate's
    confirmed skills/roles/dates/education — built from `skills`,
    `certifications`, `education`, and `documents.parsed_text`, never from
    free-text alone, so the model has an enumerable, checkable fact set."""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        facts_block=facts_block,
        job_title=job_title,
        company=company,
        job_keywords=", ".join(job_keywords),
        variant=variant,
        variant_instruction=VARIANT_INSTRUCTIONS[variant],
    )
    return SYSTEM_PROMPT, user_prompt
