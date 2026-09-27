"""Career page adapter (architecture doc section 2.2), also used for
recruitment agency and government vacancy sources (section 2.3-2.4), which
share the same tiered parsing logic against a different seed URL list.

Tries, in order:
  1. Known ATS platform (Workday/Greenhouse/Lever/etc.) structured endpoint
  2. schema.org JobPosting JSON-LD embedded in the page HTML
  3. Bespoke CSS-selector scraping (config per source)
  4. Headless-browser render, only if 1-3 all return nothing (JS-only pages)
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup

from app.modules.job_discovery.adapters.base import (
    JobSourceAdapter,
    NormalizedJob,
    RateLimitPolicy,
    RawListing,
)

# Known ATS platforms with a predictable JSON endpoint pattern. Extending
# this dict covers many company career pages at once, per the architecture
# doc's "tier 1" cost-saving rationale.
ATS_JSON_ENDPOINTS = {
    "greenhouse.io": "{base_url}/embed/job_board/jobs",
    "lever.co": "{base_url}/api/v0/postings",
}


class AtsCareerPageAdapter(JobSourceAdapter):
    """config keys: career_page_url, company, css_selectors (dict, tier-3
    fallback: listing, title, location, description, apply_link),
    use_headless_fallback (bool)."""

    async def fetch_listings(self, since: datetime | None) -> list[RawListing]:
        url = self.config["career_page_url"]

        ats_result = await self._try_ats_endpoint(url)
        if ats_result:
            return ats_result

        html = await self._fetch_html(url)
        jsonld_result = self._try_jsonld(html)
        if jsonld_result:
            return jsonld_result

        css_result = self._try_css_scrape(html)
        if css_result:
            return css_result

        if self.config.get("use_headless_fallback"):
            html = await self._fetch_html_headless(url)
            return self._try_css_scrape(html) or []

        return []

    async def _try_ats_endpoint(self, url: str) -> list[RawListing] | None:
        for domain_fragment, endpoint_template in ATS_JSON_ENDPOINTS.items():
            if domain_fragment not in url:
                continue
            endpoint = endpoint_template.format(base_url=url.rstrip("/"))
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(endpoint)
                if response.status_code != 200:
                    return None
                body = response.json()
            jobs = body.get("jobs") or body.get("postings") or []
            return [
                RawListing(external_id=str(item.get("id", "")), payload=item) for item in jobs
            ]
        return None

    async def _fetch_html(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    async def _fetch_html_headless(self, url: str) -> str:
        """Only reached when tiers 1-3 found nothing on a plain fetch — per
        architecture doc, this is deliberately the most expensive path and
        used sparingly."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            content = await page.content()
            await browser.close()
            return content

    def _try_jsonld(self, html: str) -> list[RawListing] | None:
        soup = BeautifulSoup(html, "html.parser")
        listings: list[RawListing] = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
            except json.JSONDecodeError:
                continue
            entries = data if isinstance(data, list) else [data]
            for entry in entries:
                if entry.get("@type") == "JobPosting":
                    ext_id = entry.get("identifier", {}).get("value") if isinstance(
                        entry.get("identifier"), dict
                    ) else str(entry.get("url", ""))
                    listings.append(RawListing(external_id=ext_id or self._hash(entry), payload=entry))
        return listings or None

    def _try_css_scrape(self, html: str) -> list[RawListing] | None:
        selectors = self.config.get("css_selectors")
        if not selectors:
            return None
        soup = BeautifulSoup(html, "html.parser")
        listings: list[RawListing] = []
        for node in soup.select(selectors["listing"]):
            title_el = node.select_one(selectors.get("title", ""))
            link_el = node.select_one(selectors.get("apply_link", ""))
            if not title_el:
                continue
            payload = {
                "title": title_el.get_text(strip=True),
                "location": (node.select_one(selectors.get("location", "")) or {}).get_text(strip=True)
                if node.select_one(selectors.get("location", "")) else None,
                "description": (node.select_one(selectors.get("description", "")) or {}).get_text(strip=True)
                if node.select_one(selectors.get("description", "")) else "",
                "apply_url": link_el.get("href") if link_el else self.config["career_page_url"],
            }
            listings.append(RawListing(external_id=self._hash(payload), payload=payload))
        return listings or None

    def normalize(self, raw: RawListing) -> NormalizedJob:
        payload = raw.payload
        date_posted_raw = payload.get("datePosted") or payload.get("date_posted")
        date_posted = None
        if date_posted_raw:
            try:
                date_posted = datetime.fromisoformat(str(date_posted_raw)[:10]).date()
            except ValueError:
                pass

        return NormalizedJob(
            external_id=raw.external_id,
            title=payload.get("title", ""),
            company=payload.get("hiringOrganization", {}).get("name")
            if isinstance(payload.get("hiringOrganization"), dict)
            else self.config.get("company"),
            location=payload.get("location") or self._extract_jsonld_location(payload),
            is_remote="remote" in str(payload.get("location", "")).lower(),
            salary_min=None,
            salary_max=None,
            description=payload.get("description", ""),
            apply_url=payload.get("apply_url") or payload.get("url", self.config["career_page_url"]),
            date_posted=date_posted,
            # direct company/agency career pages are the canonical "not
            # syndicated" case central to Module 3 hidden-gems detection
            is_syndicated=False,
            raw_payload=payload,
        )

    def rate_limit_policy(self) -> RateLimitPolicy:
        return RateLimitPolicy(requests_per_minute=self.config.get("requests_per_minute", 6))

    @staticmethod
    def _extract_jsonld_location(payload: dict) -> str | None:
        loc = payload.get("jobLocation")
        if isinstance(loc, dict):
            address = loc.get("address", {})
            if isinstance(address, dict):
                return address.get("addressLocality")
        return None

    @staticmethod
    def _hash(payload: dict) -> str:
        basis = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(basis.encode()).hexdigest()[:32]
