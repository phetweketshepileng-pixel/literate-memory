"""Message generation prompt, v1 — shared by cover letters, recruiter
emails, LinkedIn messages, and follow-ups (Modules 6 and 7's drafting
path; see ai-architecture.md section 3.3/3.4). Tone few-shot examples are
data (TONE_EXAMPLES below), not hardcoded prose, so they can be tuned
without a code deploy — in production this would be loaded from a small
config table rather than this module-level dict."""
from __future__ import annotations

SYSTEM_PROMPT = """You are an expert career communications writer producing a
{message_type_label} on behalf of a job candidate.

Rules:
- Use ONLY the candidate and job facts given. Do not invent achievements,
  dates, or claims.
- Match the requested tone precisely — the example below shows the target
  register; mirror its formality and energy, not its literal content.
- Keep it concise and specific to this job, not generic.
- Respond with ONLY a JSON object matching the given schema.
"""

USER_PROMPT_TEMPLATE = """CANDIDATE
Name: {candidate_name}
Current role: {current_role}
Relevant strengths for this job: {strengths}

JOB
Title: {job_title}
Company: {company}
{recruiter_line}

TONE: {tone}
EXAMPLE IN THIS TONE (for register only — do not reuse its content):
\"\"\"{tone_example}\"\"\"

Write the {message_type_label} and return the JSON object.
"""

MESSAGE_TYPE_LABELS = {
    "cover_letter": "cover letter",
    "recruiter_email": "recruiter outreach email",
    "linkedin_message": "LinkedIn connection message",
    "follow_up": "application follow-up message",
}

TONE_EXAMPLES = {
    "professional": (
        "I'm writing to express my interest in the Business Analyst role at "
        "your organization. My background in stakeholder management and "
        "reporting aligns closely with what you've described, and I'd "
        "welcome the chance to discuss how I can contribute."
    ),
    "formal": (
        "I am writing to formally apply for the position advertised. My "
        "professional experience and qualifications, detailed in the "
        "enclosed curriculum vitae, correspond closely to the stated "
        "requirements."
    ),
    "executive": (
        "Across 15 years leading collections operations, I've driven "
        "measurable gains in efficiency and stakeholder outcomes — exactly "
        "the impact I'd bring to this role."
    ),
    "friendly": (
        "I came across this role and had to reach out — it lines up really "
        "well with what I've been doing, and I'd love to chat about it "
        "whenever suits you."
    ),
}


def build_prompt(
    *,
    message_type: str,
    candidate_name: str,
    current_role: str,
    strengths: list[str],
    job_title: str,
    company: str,
    tone: str,
    recruiter_name: str | None = None,
) -> tuple[str, str]:
    message_type_label = MESSAGE_TYPE_LABELS[message_type]
    recruiter_line = f"Recruiter/contact: {recruiter_name}" if recruiter_name else ""

    system_prompt = SYSTEM_PROMPT.format(message_type_label=message_type_label)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        candidate_name=candidate_name,
        current_role=current_role,
        strengths=", ".join(strengths),
        job_title=job_title,
        company=company,
        recruiter_line=recruiter_line,
        tone=tone,
        tone_example=TONE_EXAMPLES[tone],
        message_type_label=message_type_label,
    )
    return system_prompt, user_prompt
