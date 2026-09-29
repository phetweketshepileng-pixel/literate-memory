"""Deterministic helpers behind the dashboard widgets (Module 3 / Module 9).

`quick_fit` is a transparent, rule-based relevance score used for the
"Top matches for you" widget. It is deliberately NOT the AI Match Score
(Module 4): it needs no model call, costs nothing, and every point it gives
is explained in `reasons`, so users can see why a job was suggested.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

# Ordered: first match wins. Keys are matched as whole words in the location.
_REGIONS: list[tuple[str, tuple[str, ...]]] = [
    ("Remote", ("remote", "work from home", "anywhere")),
    ("Johannesburg", ("johannesburg", "sandton", "midrand", "randburg", "rosebank", "fourways",
                      "bryanston", "parktown", "roodepoort", "soweto", "germiston", "boksburg",
                      "kempton park", "bedfordview", "edenvale", "illovo", "woodmead", "sunninghill")),
    ("Pretoria", ("pretoria", "centurion", "tshwane", "menlyn", "hatfield")),
    ("Cape Town / W. Cape", ("cape town", "bellville", "stellenbosch", "century city", "claremont", "western cape")),
    ("Durban / KZN", ("durban", "umhlanga", "pinetown", "kwazulu-natal", "kwazulu natal")),
    ("Other Gauteng", ("gauteng",)),
    ("Other South Africa", ("south africa", "eastern cape", "free state", "limpopo", "mpumalanga",
                            "north west", "northern cape", "port elizabeth", "gqeberha", "bloemfontein",
                            "polokwane", "nelspruit", "mbombela", "east london")),
]
_REGION_PATTERNS = [
    (name, re.compile(r"\b(?:" + "|".join(re.escape(k) for k in keys) + r")\b", re.IGNORECASE))
    for name, keys in _REGIONS
]

_STOPWORDS = {"and", "or", "the", "of", "a", "an", "to", "in", "for", "with", "junior", "senior", "snr", "jnr"}


def region_bucket(location: str | None, is_remote: bool = False) -> str:
    text = location or ""
    for name, pattern in _REGION_PATTERNS:
        if pattern.search(text):
            return name
    if is_remote:
        return "Remote"
    return "Other / international" if text else "Unspecified"


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if w not in _STOPWORDS and len(w) > 1}


@dataclass
class FitInput:
    desired_roles: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    location_preferences: list[str] = field(default_factory=list)
    work_mode_preference: str | None = None
    today: date | None = None


@dataclass
class FitResult:
    score: int
    reasons: list[str]


def quick_fit(title: str, description: str | None, location: str | None, is_remote: bool,
              date_posted: date | None, prefs: FitInput) -> FitResult:
    """0-100. Role match dominates (up to 55), then skills (up to 25),
    location / work mode (up to 12) and freshness (up to 8)."""
    title_l = (title or "").lower()
    title_words = _words(title)
    desc_l = f"{title_l} {(description or '').lower()}"
    score = 0
    reasons: list[str] = []

    # --- role (max 55): exact phrase in title beats partial word overlap
    best_role, best_role_pts = None, 0
    for role in prefs.desired_roles:
        role_l = role.strip().lower()
        if not role_l:
            continue
        if role_l in title_l:
            pts = 55
        else:
            rw = _words(role_l)
            overlap = len(rw & title_words) / len(rw) if rw else 0
            pts = int(round(40 * overlap)) if overlap >= 0.5 else 0
        if pts > best_role_pts:
            best_role, best_role_pts = role.strip(), pts
    if best_role:
        score += best_role_pts
        reasons.append(f"Matches your target role “{best_role}”")

    # --- skills (max 25): 5 points per profile skill mentioned in the ad
    matched_skills = []
    for skill in prefs.skills:
        s = skill.strip().lower()
        if s and re.search(r"\b" + re.escape(s) + r"\b", desc_l):
            matched_skills.append(skill.strip())
    if matched_skills:
        score += min(25, 5 * len(matched_skills))
        shown = ", ".join(matched_skills[:3]) + ("…" if len(matched_skills) > 3 else "")
        reasons.append(f"Mentions your skills: {shown}")

    # --- location / work mode (max 12)
    loc_l = (location or "").lower()
    for pref in prefs.location_preferences:
        p = pref.strip().lower()
        if not p:
            continue
        if p == "remote" and is_remote:
            score += 12; reasons.append("Remote, as you prefer"); break
        if p in loc_l or region_bucket(location, is_remote).lower() == p:
            score += 12; reasons.append(f"In {pref.strip()}"); break
    else:
        if prefs.work_mode_preference == "remote" and is_remote:
            score += 8; reasons.append("Remote, as you prefer")

    # --- freshness (max 8)
    if date_posted and prefs.today:
        age = (prefs.today - date_posted).days
        if age <= 2:
            score += 8; reasons.append("Posted in the last 2 days")
        elif age <= 7:
            score += 4

    return FitResult(score=min(100, score), reasons=reasons)
