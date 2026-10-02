"""Pure helpers behind Job Search: place matching, type-ahead suggestions and
collapsing the same job posted in several locations.

No database access here, so everything is unit-testable; the router feeds in
rows and turns the results into SQL filters / JSON.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

# Province -> cities / suburbs / regions that listings use. A search for the
# province matches all of them, because SA ads often name only the suburb
# ("Sandton") or the city ("Cape Town") and not the province.
PROVINCES: dict[str, tuple[str, ...]] = {
    "Gauteng": (
        "Johannesburg", "Sandton", "Midrand", "Randburg", "Rosebank", "Fourways", "Bryanston",
        "Parktown", "Roodepoort", "Soweto", "Germiston", "Boksburg", "Kempton Park", "Bedfordview",
        "Edenvale", "Illovo", "Woodmead", "Sunninghill", "Benoni", "Alberton", "Krugersdorp",
        "Vereeniging", "Vanderbijlpark", "Pretoria", "Centurion", "Tshwane", "Menlyn", "Hatfield",
        "Ekurhuleni", "East Rand", "West Rand",
    ),
    "Western Cape": (
        "Cape Town", "Bellville", "Stellenbosch", "Century City", "Claremont", "Milnerton",
        "Durbanville", "Paarl", "Somerset West", "George", "Worcester", "Brackenfell", "Tygervalley",
    ),
    "KwaZulu-Natal": (
        "Durban", "Umhlanga", "Pinetown", "Pietermaritzburg", "Ballito", "Richards Bay", "Westville",
        "Newcastle", "KZN", "KwaZulu Natal",
    ),
    "Eastern Cape": ("Gqeberha", "Port Elizabeth", "East London", "Mthatha", "Makhanda"),
    "Free State": ("Bloemfontein", "Welkom", "Sasolburg"),
    "Limpopo": ("Polokwane", "Tzaneen", "Thohoyandou"),
    "Mpumalanga": ("Mbombela", "Nelspruit", "Witbank", "eMalahleni", "Secunda", "Middelburg"),
    "North West": ("Rustenburg", "Mahikeng", "Potchefstroom", "Klerksdorp", "Brits"),
    "Northern Cape": ("Kimberley", "Upington"),
}
# Cities big enough that searching them should also take in their suburbs.
CITY_AREAS: dict[str, tuple[str, ...]] = {
    "Johannesburg": ("Sandton", "Midrand", "Randburg", "Rosebank", "Fourways", "Bryanston", "Parktown",
                     "Roodepoort", "Soweto", "Illovo", "Woodmead", "Sunninghill"),
    "Pretoria": ("Centurion", "Tshwane", "Menlyn", "Hatfield"),
    "Cape Town": ("Bellville", "Century City", "Claremont", "Milnerton", "Durbanville", "Tygervalley",
                  "Brackenfell"),
    "Durban": ("Umhlanga", "Pinetown", "Westville"),
}
COUNTRY = "South Africa"
REMOTE_WORDS = ("remote", "work from home", "anywhere")

_CITY_TO_PROVINCE = {c.lower(): p for p, cities in PROVINCES.items() for c in cities}


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def location_terms(query: str) -> tuple[list[str], bool]:
    """Expand what the user typed into substrings to look for in job.location.

    Returns (terms, remote): `remote` means "also include jobs flagged remote".
    Province -> province + all its places; big city -> city + suburbs;
    "South Africa" -> every SA place; anything else -> itself.
    """
    q = _norm(query)
    if not q:
        return [], False
    if q in REMOTE_WORDS or q in ("remote only", "work from home"):
        return list(REMOTE_WORDS), True
    if q in ("south africa", "sa", "rsa", "za"):
        terms = [COUNTRY]
        for p, cities in PROVINCES.items():
            terms += [p, *cities]
        return _dedupe(terms), False
    for p, cities in PROVINCES.items():
        if q == p.lower() or (p == "KwaZulu-Natal" and q in ("kzn", "kwazulu natal", "natal")):
            return _dedupe([p, *cities]), False
    for city, areas in CITY_AREAS.items():
        if q == city.lower():
            return _dedupe([city, *areas]), False
    return [query.strip()], False


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for i in items:
        if i.lower() not in seen:
            seen.add(i.lower())
            out.append(i)
    return out


def location_matches(location: str | None, is_remote: bool, terms: list[str], remote: bool) -> bool:
    """Python mirror of the SQL location filter (used for suggestion counts)."""
    if remote and is_remote:
        return True
    loc = _norm(location)
    return any(t.lower() in loc for t in terms)


# ---------------------------------------------------------------- suggestions
@dataclass
class Suggestion:
    value: str          # what goes into the search box
    kind: str           # "Job title" | "Company" | "Skill" | "Province" | "City" | "Country" | "Work mode" | "Area"
    count: int          # active jobs it would find
    hint: str = ""      # e.g. the province a city is in

    def as_dict(self) -> dict:
        return {"value": self.value, "kind": self.kind, "count": self.count, "hint": self.hint}


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9+#.]+", _norm(s))


def _prefix_match(query_words: list[str], text: str) -> bool:
    """Every typed word is the start of some word in `text` ("bus ana" ~ "Business Analyst")."""
    words = _words(text)
    return all(any(w.startswith(q) for w in words) for q in query_words)


_TITLE_BRACKETS = re.compile(r"\s*[\(\[][^)\]]*[\)\]]")
_TITLE_SUFFIX = re.compile(r"\s+[-–|:]\s+.*$")


def clean_title(title: str) -> str:
    """'Business Analyst (Contract) - Sandton' -> 'Business Analyst'."""
    t = _TITLE_SUFFIX.sub("", _TITLE_BRACKETS.sub(" ", title or "")).strip()
    return re.sub(r"\s+", " ", t) or (title or "").strip()


@dataclass
class JobRow:
    title: str
    company: str | None
    location: str | None
    is_remote: bool
    text: str = ""       # title + description, lower-cased, for skill counts


def keyword_suggestions(query: str, rows: list[JobRow], skills: list[str], limit: int = 8) -> list[Suggestion]:
    qw = _words(query)
    if not qw:
        return []
    titles: Counter[str] = Counter()
    display: dict[str, str] = {}
    companies: Counter[str] = Counter()
    for r in rows:
        t = clean_title(r.title)
        if _prefix_match(qw, t):
            key = t.lower()
            titles[key] += 1
            display.setdefault(key, t)
        if r.company and _prefix_match(qw, r.company):
            companies[r.company.strip()] += 1
    out = [Suggestion(display[k], "Job title", n) for k, n in titles.most_common()]
    out += [Suggestion(c, "Company", n) for c, n in companies.most_common(3)]
    for s in skills:
        if _prefix_match(qw, s):
            n = sum(1 for r in rows if s.lower() in r.text)
            if n:
                out.append(Suggestion(s, "Skill", n))
    q = " ".join(qw)
    # exact / starts-with matches first, then the most jobs
    out.sort(key=lambda s: (not _norm(s.value).startswith(q), s.kind != "Job title", -s.count))
    return out[:limit]


def location_suggestions(query: str, rows: list[JobRow], limit: int = 8) -> list[Suggestion]:
    qw = _words(query)
    if not qw:
        return []
    candidates: list[tuple[str, str, str]] = [(COUNTRY, "Country", ""), ("Remote", "Work mode", "")]
    candidates += [(p, "Province", "") for p in PROVINCES]
    for p, cities in PROVINCES.items():
        candidates += [(c, "City", p) for c in cities if c not in ("KZN", "KwaZulu Natal", "East Rand", "West Rand")]
    known = {c[0].lower() for c in candidates}
    # places that only appear in listings (suburbs we don't know yet, other countries)
    for r in rows:
        for part in (r.location or "").split(","):
            part = part.strip()
            if part and part.lower() not in known and len(part) > 2:
                known.add(part.lower())
                candidates.append((part, "Area", ""))

    out = []
    for value, kind, hint in candidates:
        if not _prefix_match(qw, value) and not (kind == "Province" and value == "KwaZulu-Natal" and "kzn".startswith(qw[0])):
            continue
        terms, remote = location_terms(value)
        n = sum(1 for r in rows if location_matches(r.location, r.is_remote, terms, remote))
        if n:
            out.append(Suggestion(value, kind, n, hint))
    rank = {"Country": 0, "Province": 1, "City": 2, "Work mode": 3, "Area": 4}
    q = " ".join(qw)
    # the country, provinces and cities first, loose suburb names from ads last
    out.sort(key=lambda s: (s.kind == "Area", not _norm(s.value).startswith(q), rank.get(s.kind, 5), -s.count))
    return out[:limit]


# ------------------------------------------------------------ duplicate groups
DESCRIPTION_KEY_CHARS = 300


def group_key(title: str | None, company: str | None, description: str | None = None) -> tuple[str, str]:
    """Same job advertised in several places: same title + same company.
    When the ad doesn't name the employer (typical of recruiters), the same
    title + the same opening text of the description identifies a re-post."""
    # full title on purpose: "Analyst - Credit" and "Analyst - Payments" at one
    # company are different jobs; only exact re-posts are merged
    if _norm(company):
        return (_norm(title), _norm(company))
    desc = re.sub(r"[^a-z0-9]+", " ", (description or "")[:DESCRIPTION_KEY_CHARS].lower()).strip()
    return (_norm(title), "desc:" + desc) if len(desc) >= 40 else (_norm(title), "")


@dataclass
class Grouped:
    first: object
    other_locations: list[str] = field(default_factory=list)


def collapse_duplicates(items: list, key, location) -> list[Grouped]:
    """Keep the first item of each group (callers pass items best-first) and
    remember the other groups members' locations."""
    groups: dict[tuple, Grouped] = {}
    order: list[tuple] = []
    for it in items:
        k = key(it)
        if k[1] == "":           # no company: can't tell copies apart, keep all
            k = (k[0], id(it))
        if k not in groups:
            groups[k] = Grouped(it)
            order.append(k)
        else:
            loc = (location(it) or "").strip()
            g = groups[k]
            if loc and loc != (location(g.first) or "").strip() and loc not in g.other_locations:
                g.other_locations.append(loc)
    return [groups[k] for k in order]
