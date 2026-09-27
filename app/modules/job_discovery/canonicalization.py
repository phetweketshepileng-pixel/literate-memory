"""Pure canonicalization functions used by the deduplication service.
Deliberately dependency-free (no SQLAlchemy import) so they're testable in
isolation and reusable anywhere a canonical key is needed without pulling
in the DB layer."""
from __future__ import annotations

import re

_LEGAL_SUFFIXES = re.compile(
    r"\b(pty ltd|proprietary limited|limited|inc\.?|incorporated|llc|ltd\.?|"
    r"corp\.?|corporation|co\.?)\b",
    re.IGNORECASE,
)
_PUNCTUATION = re.compile(r"[^\w\s]")


def canonicalize_company(company: str | None) -> str:
    if not company:
        return ""
    value = _LEGAL_SUFFIXES.sub("", company.lower())
    value = _PUNCTUATION.sub("", value)
    return " ".join(value.split())


def canonicalize_title(title: str) -> str:
    value = _PUNCTUATION.sub("", title.lower())
    return " ".join(value.split())


def location_bucket(location: str | None) -> str:
    """City-level grouping rather than exact address — deliberately coarse
    so 'Sandton, Johannesburg' and 'Johannesburg, Gauteng' still match."""
    if not location:
        return ""
    return location.lower().split(",")[0].strip()
