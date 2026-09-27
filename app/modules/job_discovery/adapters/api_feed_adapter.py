"""Adapter for job boards reached via an official API/partner feed
(architecture doc section 2.1) — e.g. Indeed Publisher API, PNet/Careers24
partner XML feeds. Config per instance carries the endpoint + credentials;
this class contains no board-specific logic beyond response-shape mapping,
which is intentionally kept thin so most new API-based boards only need a
new job_sources row, not a new class.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime

import httpx

from app.modules.job_discovery.adapters.base import (
    JobSourceAdapter,
    NormalizedJob,
    RateLimitPolicy,
    RawListing,
)


class ApiFeedAdapter(JobSourceAdapter):
    """config keys: base_url, api_key, query_params (dict), field_map (dict
    mapping this source's response field names onto our normalized names),
    requests_per_minute."""

    async def fetch_listings(self, since: datetime | None) -> list[RawListing]:
        params = dict(self.config.get("query_params", {}))
        if since is not None:
            params["updated_since"] = since.isoformat()

        headers = {"Authorization": f"Bearer {self.config['api_key']}"}
        listings: list[RawListing] = []

        async with httpx.AsyncClient(timeout=30) as client:
            page = 1
            while True:
                params["page"] = page
                response = await client.get(self.config["base_url"], params=params, headers=headers)
                response.raise_for_status()
                body = response.json()
                results = body.get("results", [])
                if not results:
                    break

                for item in results:
                    external_id = str(item.get("id") or self._fallback_id(item))
                    listings.append(RawListing(external_id=external_id, payload=item))

                if not body.get("has_more"):
                    break
                page += 1

        return listings

    def normalize(self, raw: RawListing) -> NormalizedJob:
        fm = self.config.get("field_map", {})
        payload = raw.payload

        def get(field_key: str, default=None):
            source_key = fm.get(field_key, field_key)
            return payload.get(source_key, default)

        posted_raw = get("date_posted")
        date_posted = None
        if posted_raw:
            try:
                date_posted = datetime.fromisoformat(posted_raw).date()
            except ValueError:
                date_posted = None

        return NormalizedJob(
            external_id=raw.external_id,
            title=get("title", ""),
            company=get("company"),
            location=get("location"),
            is_remote=bool(get("is_remote", False)),
            salary_min=get("salary_min"),
            salary_max=get("salary_max"),
            description=get("description", ""),
            apply_url=get("apply_url", ""),
            date_posted=date_posted,
            is_syndicated=True,  # job-board listings are syndicated by definition
            raw_payload=payload,
        )

    def rate_limit_policy(self) -> RateLimitPolicy:
        return RateLimitPolicy(requests_per_minute=self.config.get("requests_per_minute", 20))

    @staticmethod
    def _fallback_id(item: dict) -> str:
        """Deterministic hash fallback when a source omits a stable ID,
        per architecture doc section 5.1."""
        basis = f"{item.get('title', '')}|{item.get('company', '')}|{item.get('apply_url', '')}"
        return hashlib.sha256(basis.encode()).hexdigest()[:32]
