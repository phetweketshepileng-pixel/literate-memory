"""JobSourceAdapter interface — every ingestion source implements this.
See docs/job-discovery-architecture.md section 3. Adding a new source is a
new job_sources config row (and, only if the response shape genuinely
differs, a new adapter class) — never a change to the ingestion pipeline
itself.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class RawListing:
    """Whatever a source hands back before normalization — kept opaque to
    the pipeline so each adapter owns its own source-specific shape."""
    external_id: str
    payload: dict[str, Any]


@dataclass
class NormalizedJob:
    """Common shape every adapter must produce. See architecture doc
    section 8 — this is the contract dedup/ranking/matching depend on."""
    external_id: str
    title: str
    company: str | None
    location: str | None
    is_remote: bool
    salary_min: int | None
    salary_max: int | None
    description: str
    apply_url: str
    date_posted: date | None
    is_syndicated: bool
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RateLimitPolicy:
    requests_per_minute: int
    backoff_seconds_on_429: int = 60


class JobSourceAdapter(abc.ABC):
    """One subclass per source *type* (API feed, RSS, ATS career page,
    scraped career page, search-engine discovery) — never one subclass
    per company/agency. Per-instance differences (URLs, credentials,
    selectors) live in job_sources.config, injected via __init__."""

    def __init__(self, source_id: str, config: dict[str, Any]) -> None:
        self.source_id = source_id
        self.config = config

    @abc.abstractmethod
    async def fetch_listings(self, since: datetime | None) -> list[RawListing]:
        """Return raw postings newer than `since` (or everything available,
        on first run when `since` is None). Must not raise on an individual
        malformed listing — skip and log it, don't fail the whole batch."""

    @abc.abstractmethod
    def normalize(self, raw: RawListing) -> NormalizedJob:
        """Map this source's raw fields onto NormalizedJob. Must set
        `external_id` deterministically — see architecture doc section 5.1:
        this is what UNIQUE(source_id, external_id) relies on."""

    def rate_limit_policy(self) -> RateLimitPolicy:
        """Override per source; conservative default for anything unknown."""
        return RateLimitPolicy(requests_per_minute=10)
