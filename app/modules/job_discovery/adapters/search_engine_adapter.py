"""Search-engine discovery adapter (architecture doc section 2.6). Unlike
every other adapter, this one does NOT return jobs to ingest directly — it
discovers new company career-page URLs (fed into job_sources as new
AtsCareerPageAdapter instances) and, separately, JobPosting schema.org data
surfaced directly in search results. Run as a weekly low-volume batch, not
on the regular polling cadence.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

import httpx

from app.modules.job_discovery.adapters.base import (
    JobSourceAdapter,
    NormalizedJob,
    RateLimitPolicy,
    RawListing,
)


class SearchEngineDiscoveryAdapter(JobSourceAdapter):
    """config keys: search_api_key, search_engine_id (for Google Custom
    Search JSON API), discovery_queries (list of query strings, e.g.
    '"business analyst" jobs Johannesburg', 'site:*.co.za careers vacancies').
    Uses only an official search API — never scrapes search-results HTML
    directly, per architecture doc section 2.6.
    """

    SEARCH_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

    async def fetch_listings(self, since: datetime | None) -> list[RawListing]:
        listings: list[RawListing] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for query in self.config.get("discovery_queries", []):
                params = {
                    "key": self.config["search_api_key"],
                    "cx": self.config["search_engine_id"],
                    "q": query,
                    "num": 10,
                }
                response = await client.get(self.SEARCH_ENDPOINT, params=params)
                response.raise_for_status()
                for item in response.json().get("items", []):
                    external_id = hashlib.sha256(item["link"].encode()).hexdigest()[:32]
                    listings.append(RawListing(external_id=external_id, payload=item))
        return listings

    def normalize(self, raw: RawListing) -> NormalizedJob:
        """Discovery results normalize into a *candidate career-page URL*
        record, not a fully-formed job posting — downstream, a separate
        onboarding step reviews these and, once confirmed, creates a real
        job_sources row using AtsCareerPageAdapter. Returned here as a
        NormalizedJob with is_syndicated left None-equivalent (False by
        convention) purely so it satisfies the interface; callers of this
        adapter must route its output to the source-onboarding queue, not
        the jobs upsert path, which the ingestion pipeline enforces by
        source type rather than by inspecting output shape."""
        payload = raw.payload
        return NormalizedJob(
            external_id=raw.external_id,
            title=payload.get("title", ""),
            company=None,
            location=None,
            is_remote=False,
            salary_min=None,
            salary_max=None,
            description=payload.get("snippet", ""),
            apply_url=payload.get("link", ""),
            date_posted=None,
            is_syndicated=False,
            raw_payload=payload,
        )

    def rate_limit_policy(self) -> RateLimitPolicy:
        # Search APIs are typically metered per day, not per minute; kept
        # conservative and run as a weekly batch per the architecture doc.
        return RateLimitPolicy(requests_per_minute=self.config.get("requests_per_minute", 5))
