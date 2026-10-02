"""Employer careers boards hosted on Greenhouse, Lever, SmartRecruiters or
Workable — the source of Module 3's hidden gems.

These platforms publish each employer's open roles through a public,
documented job-board API meant for exactly this kind of reuse (embedding a
company's openings elsewhere), so no scraping is involved. A job that
exists only here — posted directly by the employer and not on the job
boards Adzuna aggregates — is a hidden gem (is_syndicated=False); the
dedupe step clears the flag if the same vacancy later turns up on a board.

config keys (one job_sources row per employer):
    platform   "greenhouse" | "lever" | "smartrecruiters" | "workable"
    board      the employer's board id on that platform, e.g. "ozow"
    company    display name, used when the API doesn't give one
    industry   plain-language industry for the Job Search filter
    sa_only    keep only South African roles (default true)
    region     Lever only: "eu" for boards on api.eu.lever.co
"""
from __future__ import annotations

import html
import re
from datetime import UTC, date, datetime

import httpx

from app.modules.job_discovery.adapters.base import (
    JobSourceAdapter,
    NormalizedJob,
    RateLimitPolicy,
    RawListing,
)

_SA = re.compile(
    r"south africa|\bza\b|johannesburg|cape town|durban|pretoria|sandton|centurion|midrand|stellenbosch|gauteng"
    r"|western cape|kwazulu|gqeberha|port elizabeth|bloemfontein|umhlanga|rosebank|randburg|bryanston|\bjhb\b|\bcpt\b",
    re.IGNORECASE,
)
_REMOTE = re.compile(r"\b(remote|work from home|anywhere)\b", re.IGNORECASE)
_TAGS = re.compile(r"<[^>]+>")
SMARTRECRUITERS_MAX_PAGES = 3  # 100 postings a page


class UnknownPlatformError(ValueError):
    pass


def _plain(text: str | None) -> str:
    """HTML (sometimes escaped twice, as Greenhouse does) -> plain text."""
    t = html.unescape(html.unescape(text or ""))
    t = re.sub(r"</(p|li|div|h\d)>|<br\s*/?>", "\n", t, flags=re.IGNORECASE)
    t = html.unescape(_TAGS.sub(" ", t))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    return re.sub(r"\n{2,}", "\n\n", t).strip()


def _date(value) -> date | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):  # Lever: epoch milliseconds
            return datetime.fromtimestamp(value / 1000, tz=UTC).date()
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")[:25]).date()
    except (ValueError, OSError):
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


class AtsBoardAdapter(JobSourceAdapter):
    # the board lists every open role, so a job missing from it has closed
    closes_missing_listings = True

    @property
    def platform(self) -> str:
        return self.config["platform"]

    @property
    def board(self) -> str:
        return self.config["board"]

    async def fetch_listings(self, since: datetime | None) -> list[RawListing]:
        async with httpx.AsyncClient(timeout=30, headers={"Accept": "application/json"}) as client:
            items = await self._fetch(client)
        listings = []
        for item in items:
            ext = str(item.get("id") or item.get("shortcode") or "")
            if not ext:
                continue
            if self.config.get("sa_only", True) and not _SA.search(self._location_text(item)):
                continue
            listings.append(RawListing(external_id=ext, payload=item))
        return listings

    async def _fetch(self, client: httpx.AsyncClient) -> list[dict]:
        b = self.board
        if self.platform == "greenhouse":
            r = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{b}/jobs", params={"content": "true"})
            r.raise_for_status()
            return r.json().get("jobs") or []
        if self.platform == "lever":
            host = "api.eu.lever.co" if self.config.get("region") == "eu" else "api.lever.co"
            r = await client.get(f"https://{host}/v0/postings/{b}", params={"mode": "json"})
            r.raise_for_status()
            return r.json() or []
        if self.platform == "smartrecruiters":
            out: list[dict] = []
            for page in range(SMARTRECRUITERS_MAX_PAGES):
                params = {"limit": 100, "offset": page * 100}
                if self.config.get("sa_only", True):
                    params["country"] = "za"
                r = await client.get(f"https://api.smartrecruiters.com/v1/companies/{b}/postings", params=params)
                r.raise_for_status()
                body = r.json()
                content = body.get("content") or []
                out += content
                if len(out) >= (body.get("totalFound") or 0) or len(content) < 100:
                    break
            return out
        if self.platform == "workable":
            r = await client.get(f"https://apply.workable.com/api/v1/widget/accounts/{b}", params={"details": "true"})
            r.raise_for_status()
            return r.json().get("jobs") or []
        raise UnknownPlatformError(f"Unknown careers platform '{self.platform}'")

    def _location_text(self, p: dict) -> str:
        if self.platform == "greenhouse":
            offices = " ".join(o.get("name") or "" for o in p.get("offices") or [])
            return f"{(p.get('location') or {}).get('name') or ''} {offices}"
        if self.platform == "lever":
            c = p.get("categories") or {}
            return " ".join([c.get("location") or "", *(c.get("allLocations") or []), p.get("country") or ""])
        if self.platform == "smartrecruiters":
            loc = p.get("location") or {}
            return f"{loc.get('fullLocation') or ''} {loc.get('country') or ''}"
        if self.platform == "workable":
            return " ".join(str(p.get(k) or "") for k in ("city", "state", "country"))
        return ""

    def normalize(self, raw: RawListing) -> NormalizedJob:
        p, company = raw.payload, self.config.get("company")
        if self.platform == "greenhouse":
            title, location = p.get("title"), (p.get("location") or {}).get("name")
            description, url = _plain(p.get("content")), p.get("absolute_url")
            posted = _date(p.get("first_published") or p.get("updated_at"))
            company = p.get("company_name") or company
            remote = bool(_REMOTE.search(location or ""))
        elif self.platform == "lever":
            c = p.get("categories") or {}
            title, location = p.get("text"), c.get("location")
            description = "\n\n".join(x for x in (p.get("descriptionPlain"), *(
                f"{l.get('text')}\n{_plain(l.get('content'))}" for l in p.get("lists") or []
            ), p.get("additionalPlain")) if x)
            url, posted = p.get("hostedUrl"), _date(p.get("createdAt"))
            remote = p.get("workplaceType") == "remote" or bool(_REMOTE.search(location or ""))
        elif self.platform == "smartrecruiters":
            loc = p.get("location") or {}
            title = p.get("name")
            location = ", ".join(x for x in (loc.get("city"), _sa_region(loc.get("region"))) if x) or loc.get("fullLocation")
            bits = [(p.get(k) or {}).get("label") for k in ("function", "experienceLevel", "typeOfEmployment")]
            description = " · ".join(b for b in bits if b and b != "Other")
            url = f"https://jobs.smartrecruiters.com/{self.board}/{p.get('id')}"
            posted = _date(p.get("releasedDate"))
            company = (p.get("company") or {}).get("name") or company
            remote = bool(loc.get("remote"))
        else:  # workable
            title = p.get("title")
            location = ", ".join(x for x in (p.get("city"), p.get("state")) if x) or p.get("country")
            description, url = _plain(p.get("description")), p.get("url")
            posted = _date(p.get("published_on") or p.get("created_at"))
            remote = bool(p.get("telecommuting"))

        return NormalizedJob(
            external_id=raw.external_id,
            title=(title or "").strip(),
            company=company,
            location=location,
            is_remote=remote,
            salary_min=None,
            salary_max=None,
            description=description or "",
            apply_url=url or "",
            date_posted=posted,
            is_syndicated=False,  # posted by the employer itself: hidden-gem candidate
            raw_payload={"platform": self.platform, "board": self.board, "id": raw.external_id},
            industry=self.config.get("industry"),
        )

    def rate_limit_policy(self) -> RateLimitPolicy:
        return RateLimitPolicy(requests_per_minute=self.config.get("requests_per_minute", 10))


_SA_REGIONS = {"GP": "Gauteng", "WC": "Western Cape", "KZN": "KwaZulu-Natal", "EC": "Eastern Cape", "FS": "Free State",
               "LP": "Limpopo", "MP": "Mpumalanga", "NW": "North West", "NC": "Northern Cape"}


def _sa_region(code: str | None) -> str | None:
    return _SA_REGIONS.get((code or "").upper(), code)
