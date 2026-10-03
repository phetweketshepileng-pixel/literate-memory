"""Spots jobs open to people with little or no work experience — the
learnerships, internships, graduate programmes, apprenticeships and YES
posts young South Africans can actually get — so Job Search can filter
for them.

classify_opportunity(title, description) -> (opportunity_type, entry_level)
    opportunity_type: one of OPPORTUNITY_TYPES or None
    entry_level:      True when the job is realistically open to someone
                      without (much) experience
"""
from __future__ import annotations

import re

OPPORTUNITY_TYPES = {
    "learnership": "Learnership",
    "internship": "Internship",
    "graduate": "Graduate programme",
    "apprenticeship": "Apprenticeship",
    "yes": "YES programme",
    "entry": "Entry level",
}

# programme types, strongest signal first; matched in the title, then in
# the first part of the description
_TYPES: list[tuple[str, re.Pattern]] = [
    ("yes", re.compile(r"\bYES\s*(?:4|for)\s*Youth|\bYES\s+(?:programme|program|initiative)\b|youth employment service", re.I)),
    ("learnership", re.compile(r"\blearner\s*ships?\b|\bNQF\s*[1-5]\b.*\blearner", re.I)),
    ("apprenticeship", re.compile(r"\bapprentice(?:ship)?s?\b", re.I)),
    ("internship", re.compile(r"\bintern(?:ship)?s?\b|\bin-service\s+train|\bWIL\b|work[- ]integrated learning|\bexperiential\s+(?:training|learning)", re.I)),
    ("graduate", re.compile(r"\bgraduate\s+(?:programme|program|trainee|development|intake|scheme|recruitment)|\bgrad\s+programme|\bcandidate\s+(?:attorney|engineer|chartered accountant|CA)\b|\btrainee\s+accountant", re.I)),
]

# phrases meaning "no or little experience needed"
_NO_EXPERIENCE = re.compile(
    r"no (?:prior |previous |work )?experience (?:is )?(?:required|needed|necessary)"
    r"|experience (?:is )?not (?:required|necessary|needed)"
    r"|\b0\s*(?:-|to|–)\s*[12]\s*years?"
    r"|\bentry[- ]level\b"
    r"|\bfirst[- ]time job seekers?\b"
    r"|\bunemployed (?:youth|graduates?|matriculants?)\b"
    r"|\bmatric(?:ulants?)? (?:with no experience|school leavers?)\b"
    r"|\bschool leavers?\b", re.I)

# titles that are entry level by nature
_ENTRY_TITLES = re.compile(
    r"\b(?:junior|trainee|assistant|learner|cadet|entry[- ]level|general worker|packer|cashier|picker|"
    r"call cent(?:re|er) agent|customer service agent|sales assistant|shop assistant|waitron|barista|"
    r"data capturer|receptionist|admin(?:istration)? clerk|filing clerk|general assistant|runner)\b", re.I)

# anything plainly senior is never entry level, whatever the advert says
_SENIOR = re.compile(r"\b(?:senior|snr|sr\.?|lead|principal|head|chief|director|manager|supervisor|"
                     r"specialist|expert|architect|consultant|executive|partner)\b", re.I)
_YEARS_REQUIRED = re.compile(r"\b([3-9]|1[0-9])\s*\+?\s*(?:-|to|–)?\s*\d*\s*years?(?:'|’)?\s*(?:of\s+)?(?:relevant\s+|working\s+|work\s+)?experience", re.I)

DESCRIPTION_CHARS = 1500


def classify_opportunity(title: str | None, description: str | None) -> tuple[str | None, bool]:
    t = title or ""
    d = (description or "")[:DESCRIPTION_CHARS]

    kind = None
    for name, pattern in _TYPES:
        if pattern.search(t):
            kind = name
            break
    if kind is None:
        for name, pattern in _TYPES:
            # in the description only the programme words count, and only
            # when the title isn't clearly a senior role (adverts often say
            # "you will mentor our interns")
            if pattern.search(d) and not _SENIOR.search(t):
                kind = name
                break

    senior = bool(_SENIOR.search(t)) and kind is None
    if senior:
        return None, False
    if kind is not None:
        return kind, True

    years_needed = _YEARS_REQUIRED.search(d)
    if _NO_EXPERIENCE.search(t) or _NO_EXPERIENCE.search(d):
        return "entry", True
    if _ENTRY_TITLES.search(t) and not years_needed:
        return "entry", True
    return None, False
