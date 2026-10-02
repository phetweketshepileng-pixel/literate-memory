"""Adzuna job-search API adapter — the South African job-board source.

Adzuna aggregates listings from SA job boards and exposes them through an
official, free API (developer.adzuna.com), so this is the ToS-safe way to
cover the boards (PNet, Careers24, etc.) that don't offer feeds of their own.

config keys (one job_sources row per search):
    what          keywords, e.g. "business analyst"
    category      Adzuna category tag, e.g. "it-jobs" (what and/or category required)
    where         location, e.g. "Gauteng"; omit for all of SA
    country       Adzuna country code, default "za"
    max_days_old  only listings newer than this, default 21
    pages         pages of 50 results to fetch per run, default 2

Credentials come from the ADZUNA_APP_ID / ADZUNA_APP_KEY settings, never
from the job_sources row.
"""
from __future__ import annotations

import asyncio
import html
import re
import time
from datetime import datetime

import httpx

from app.core.config import settings
from app.modules.job_discovery.adapters.base import (
    JobSourceAdapter,
    NormalizedJob,
    RateLimitPolicy,
    RawListing,
)

API_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
RESULTS_PER_PAGE = 50
_REMOTE = re.compile(r"\b(remote|work from home|wfh|anywhere)\b", re.IGNORECASE)
CATEGORIES_URL = "https://api.adzuna.com/v1/api/jobs/{country}/categories"

# Adzuna allows 25 requests a minute across ALL our searches, and the poller
# runs them back to back, so space every request out (process-wide).
MIN_SECONDS_BETWEEN_REQUESTS = 2.6
_last_request = 0.0


async def _throttle() -> None:
    global _last_request
    wait = _last_request + MIN_SECONDS_BETWEEN_REQUESTS - time.monotonic()
    if wait > 0:
        await asyncio.sleep(wait)
    _last_request = time.monotonic()


async def fetch_categories(country: str = "za") -> list[dict]:
    """[{'tag': 'it-jobs', 'label': 'IT Jobs'}, ...] — costs one request."""
    await _throttle()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(CATEGORIES_URL.format(country=country), params={
            "app_id": settings.ADZUNA_APP_ID, "app_key": settings.ADZUNA_APP_KEY, "content-type": "application/json"})
        r.raise_for_status()
        return r.json().get("results") or []


class AdzunaNotConfiguredError(Exception):
    """ADZUNA_APP_ID / ADZUNA_APP_KEY aren't set on this service."""


class AdzunaAdapter(JobSourceAdapter):
    async def fetch_listings(self, since: datetime | None) -> list[RawListing]:
        if not settings.ADZUNA_APP_ID or not settings.ADZUNA_APP_KEY:
            raise AdzunaNotConfiguredError(
                "Set ADZUNA_APP_ID and ADZUNA_APP_KEY (free at developer.adzuna.com) to enable this source"
            )
        country = self.config.get("country", "za")
        params = {
            "app_id": settings.ADZUNA_APP_ID,
            "app_key": settings.ADZUNA_APP_KEY,
            "results_per_page": RESULTS_PER_PAGE,
            "max_days_old": self.config.get("max_days_old", 21),
            "sort_by": "date",
            "content-type": "application/json",
        }
        if self.config.get("what"):
            params["what"] = self.config["what"]
        if self.config.get("category"):
            params["category"] = self.config["category"]
        if self.config.get("where"):
            params["where"] = self.config["where"]

        listings: list[RawListing] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=30) as client:
            for page in range(1, int(self.config.get("pages", 2)) + 1):
                await _throttle()
                response = await client.get(API_URL.format(country=country, page=page), params=params)
                response.raise_for_status()
                results = response.json().get("results") or []
                for item in results:
                    ext_id = str(item.get("id") or "")
                    if ext_id and ext_id not in seen:
                        seen.add(ext_id)
                        listings.append(RawListing(external_id=ext_id, payload=item))
                if len(results) < RESULTS_PER_PAGE:
                    break
        return listings

    def normalize(self, raw: RawListing) -> NormalizedJob:
        p = raw.payload
        company = (p.get("company") or {}).get("display_name")
        location = (p.get("location") or {}).get("display_name")
        description = html.unescape(re.sub(r"<[^>]+>", " ", p.get("description") or "")).strip()
        title = html.unescape(re.sub(r"<[^>]+>", "", p.get("title") or "")).strip()

        # Adzuna fills in *estimated* salaries when the ad has none; only
        # keep salaries the employer actually published.
        predicted = str(p.get("salary_is_predicted", "0")) == "1"
        salary_min = None if predicted else _as_int(p.get("salary_min"))
        salary_max = None if predicted else _as_int(p.get("salary_max"))
        if salary_min is not None and salary_max is not None and salary_max < salary_min:
            salary_min, salary_max = salary_max, salary_min

        created = p.get("created")
        date_posted = None
        if created:
            try:
                date_posted = datetime.fromisoformat(created.replace("Z", "+00:00")).date()
            except ValueError:
                date_posted = None

        return NormalizedJob(
            external_id=raw.external_id,
            title=title,
            company=company,
            location=location,
            is_remote=bool(_REMOTE.search(f"{title} {location or ''} {description[:500]}")),
            salary_min=salary_min,
            salary_max=salary_max,
            description=description,
            apply_url=p.get("redirect_url") or "",
            date_posted=date_posted,
            is_syndicated=True,  # aggregated from job boards, so never a hidden gem on its own
            raw_payload=p,
        )

    def rate_limit_policy(self) -> RateLimitPolicy:
        return RateLimitPolicy(requests_per_minute=self.config.get("requests_per_minute", 20))


def _as_int(value) -> int | None:
    try:
        return int(round(float(value))) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
