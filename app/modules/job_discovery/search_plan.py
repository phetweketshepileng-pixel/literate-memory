"""Turns what users list under "Desired roles" into the job-board searches
the poller runs, so the feed follows people's profiles instead of a fixed
list. Pure functions; scripts/poll_jobs.py feeds in the roles from the DB.
"""
from __future__ import annotations

import re
from collections import Counter

# used only while no profile lists any desired roles yet
FALLBACK_ROLES = ("operations manager", "business analyst", "collections manager", "credit risk analyst",
                  "customer service manager", "project coordinator")
MAX_ROLES = 12          # distinct roles searched per refresh
PAGE_BUDGET = 18        # pages of 50 per refresh (refreshed twice a day)
MAX_PAGES_PER_ROLE = 4  # 200 newest jobs per role when only a few roles are wanted

_FILLER = re.compile(r"\b(role|roles|position|positions|job|jobs|vacancy|vacancies)\b")


def normalize_role(raw: str | None) -> str | None:
    """'  Collections Team Manager (JHB) ' -> 'collections team manager'."""
    if not raw:
        return None
    r = re.sub(r"\([^)]*\)", " ", raw.lower())
    r = _FILLER.sub(" ", r)
    r = re.sub(r"[^a-z0-9&+#/ -]", " ", r)
    r = re.sub(r"\s+", " ", r).strip(" -/&")
    if len(r) < 3 or len(r) > 60 or not re.search(r"[a-z]{3}", r):
        return None
    return r


def plan_role_searches(desired_roles: list[str]) -> list[tuple[str, None, int]]:
    """Most-wanted roles first: [(keywords, where=None for all of SA, pages)].
    Every role gets a page; spare budget deepens the searches, most wanted
    roles first, up to MAX_PAGES_PER_ROLE each."""
    counts = Counter(r for r in (normalize_role(x) for x in desired_roles) if r)
    roles = [r for r, _ in counts.most_common(MAX_ROLES)] or list(FALLBACK_ROLES)
    pages = {r: 1 for r in roles}
    spare = PAGE_BUDGET - len(roles)
    # hand out the spare pages round-robin, most wanted roles first
    while spare > 0 and any(p < MAX_PAGES_PER_ROLE for p in pages.values()):
        for r in roles:
            if spare > 0 and pages[r] < MAX_PAGES_PER_ROLE:
                pages[r] += 1
                spare -= 1
    return [(r, None, pages[r]) for r in roles]
