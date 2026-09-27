"""CV Tailoring module business logic (Module 5). ATS scoring is
deliberately a deterministic heuristic, not an LLM call — see
ai-architecture.md section 3.2 ("saving a full round-trip"). The
grounding validator is the enforcement backstop for the prompt's
anti-hallucination instructions (ai-architecture.md section 4)."""
from __future__ import annotations

import re
from dataclasses import dataclass

REQUIRED_SECTIONS = ("summary", "experience", "skills_section")

# Common English filler/structural words that should never be treated as a
# "skill-like" keyword, whether in job descriptions or generated CV text.
# This list is intentionally generous — false negatives here (a real skill
# that happens to be a common word) are far cheaper than false positives
# (flagging ordinary prose as a fabricated claim).
_STOPWORDS = {
    "with", "have", "this", "that", "role", "team", "work", "years", "strong",
    "skills", "experience", "responsible", "including", "using", "across",
    "many", "for", "and", "the", "from", "over", "who", "were", "are", "was",
    "been", "being", "also", "into", "such", "only", "more", "most", "some",
    "each", "then", "than", "when", "where", "what", "which", "while",
    "within", "without", "will", "your", "our", "their", "they", "you",
    "expert", "skilled", "proficient", "experienced", "advanced", "deployment",
    "deploying", "focused", "driven", "excellent", "solid", "extensive",
    "results", "achievements", "responsibilities", "duties", "background",
}


def extract_keywords(text: str) -> set[str]:
    """Sentence-position-aware keyword extraction: skips each sentence's
    first word (its capitalization reflects sentence position, not
    significance) and filters common filler words, so what remains is a
    reasonable proxy for skill/tool/domain terms rather than ordinary
    prose."""
    keywords: set[str] = set()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        words = sentence.split()
        for index, word in enumerate(words):
            if index == 0:
                continue  # sentence-initial capitalization is positional, not semantic
            cleaned = re.sub(r"[^\w+#.]", "", word).lower().strip(".")
            if len(cleaned) < 3 or cleaned in _STOPWORDS:
                continue
            keywords.add(cleaned)
    return keywords


def keyword_coverage(job_keywords: set[str], cv_text: str) -> tuple[set[str], float]:
    """Returns (matched keywords, coverage fraction 0.0-1.0). Uses plain
    substring containment (not extract_keywords) since job_keywords here
    are already a curated list, not raw text to re-tokenize."""
    if not job_keywords:
        return set(), 0.0
    cv_lower = cv_text.lower()
    matched = {kw for kw in job_keywords if kw.lower() in cv_lower}
    return matched, len(matched) / len(job_keywords)


@dataclass
class CVContent:
    summary: str
    experience_bullets: list[str]
    skills_section: list[str]


def compute_ats_score(content: CVContent, job_keywords: set[str]) -> int:
    """Deterministic ATS score: keyword coverage (60%) + section
    completeness (40%). No LLM call — see module docstring."""
    full_text = content.summary + " " + " ".join(content.experience_bullets) + " " + " ".join(
        content.skills_section
    )
    _, coverage = keyword_coverage(job_keywords, full_text)
    keyword_component = coverage * 60

    completeness_component = 0.0
    if content.summary and len(content.summary) > 30:
        completeness_component += 15
    if len(content.experience_bullets) >= 2:
        completeness_component += 15
    if len(content.skills_section) >= 3:
        completeness_component += 10

    return min(100, round(keyword_component + completeness_component))


def compute_optimization_score(added_keywords_count: int, job_keywords_count: int) -> int:
    """Distinct from ATS score: measures how much of the *gap* between the
    original CV and this job's keywords was closed by tailoring."""
    if job_keywords_count == 0:
        return 100
    return min(100, round((added_keywords_count / job_keywords_count) * 100))


def find_unauthorized_claims(tailored_text: str, allowed_facts: set[str]) -> set[str]:
    """Hallucination guard (ai-architecture.md section 4, 'enforcement
    backstop'): flags any skill-like term in the tailored output that
    doesn't appear in the candidate's confirmed facts. This is a coarse
    safety net, not a substitute for the prompt's grounding instructions —
    it catches egregious fabrication, not subtle rephrasing."""
    tailored_keywords = extract_keywords(tailored_text)

    allowed_tokens: set[str] = set()
    for fact in allowed_facts:
        allowed_tokens.add(fact.lower())
        allowed_tokens |= {w.lower() for w in re.findall(r"[\w+#.]+", fact) if len(w) >= 3}

    return {kw for kw in tailored_keywords if kw not in allowed_tokens}
