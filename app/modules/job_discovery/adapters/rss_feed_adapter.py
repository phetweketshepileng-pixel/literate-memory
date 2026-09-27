"""RSS/Atom feed adapter (architecture doc section 2.5) — the cheapest,
preferred ingestion method for any source that exposes one. Also used to
auto-discover a feed URL for a career-page source that was originally
onboarded for HTML scraping."""
from __future__ import annotations

import hashlib
from datetime import datetime

import feedparser
import httpx

from app.modules.job_discovery.adapters.base import (
    JobSourceAdapter,
    NormalizedJob,
    RateLimitPolicy,
    RawListing,
)


class RssFeedAdapter(JobSourceAdapter):
    """config keys: feed_url, company (fallback if not derivable per-entry),
    is_syndicated (bool, defaults True unless this feed belongs to a
    company career page / agency source, in which case the source config
    sets it False)."""

    async def fetch_listings(self, since: datetime | None) -> list[RawListing]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(self.config["feed_url"])
            response.raise_for_status()

        parsed = feedparser.parse(response.text)
        listings: list[RawListing] = []

        for entry in parsed.entries:
            published = getattr(entry, "published_parsed", None)
            if since is not None and published is not None:
                entry_dt = datetime(*published[:6])
                if entry_dt <= since:
                    continue

            external_id = getattr(entry, "id", None) or getattr(entry, "link", None)
            if not external_id:
                basis = f"{entry.get('title', '')}|{entry.get('link', '')}"
                external_id = hashlib.sha256(basis.encode()).hexdigest()[:32]

            listings.append(RawListing(external_id=str(external_id), payload=dict(entry)))

        return listings

    def normalize(self, raw: RawListing) -> NormalizedJob:
        payload = raw.payload
        published = payload.get("published_parsed")
        date_posted = datetime(*published[:6]).date() if published else None

        return NormalizedJob(
            external_id=raw.external_id,
            title=payload.get("title", ""),
            company=payload.get("author") or self.config.get("company"),
            location=payload.get("location") or self.config.get("default_location"),
            is_remote=self.config.get("default_is_remote", False),
            salary_min=None,
            salary_max=None,
            description=payload.get("summary", ""),
            apply_url=payload.get("link", ""),
            date_posted=date_posted,
            is_syndicated=self.config.get("is_syndicated", True),
            raw_payload=payload,
        )

    def rate_limit_policy(self) -> RateLimitPolicy:
        # Feeds are cheap; still throttled to be a good citizen of the source.
        return RateLimitPolicy(requests_per_minute=self.config.get("requests_per_minute", 30))
