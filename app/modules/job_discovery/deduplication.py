"""Deduplication — architecture doc section 5. Two layers:
  (a) same-source exact de-dupe, enforced by the DB's UNIQUE(source_id,
      external_id) constraint via upsert (handled at the upsert call site,
      not here)
  (b) cross-source near-duplicate detection (this module), which decides
      whether a newly normalized listing is the same real-world vacancy as
      one already in `jobs`, and if so records it as an additional
      reference instead of inserting a duplicate job row.
"""
from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, JobSourceReference
from app.modules.job_discovery.adapters.base import NormalizedJob
from app.modules.job_discovery.canonicalization import (
    canonicalize_company,
    canonicalize_title,
    location_bucket,
)

# Trigram similarity threshold for confirming a candidate as a genuine
# duplicate rather than a coincidentally similar title/company pairing.
DESCRIPTION_SIMILARITY_THRESHOLD = 0.6
CANDIDATE_WINDOW_DAYS = 30


async def find_duplicate(db: AsyncSession, candidate: NormalizedJob) -> Job | None:
    """Returns the existing Job this candidate duplicates, or None if it's
    genuinely new. Does NOT insert or modify anything — callers decide what
    to do with the result (architecture doc section 5.2, steps 2-4)."""
    canon_company = canonicalize_company(candidate.company)
    canon_title = canonicalize_title(candidate.title)
    bucket = location_bucket(candidate.location)

    if not canon_company or not canon_title:
        return None  # not enough signal to safely dedupe; let it insert as new

    # Step 2: candidate lookup within the rolling window, same canonical key.
    # Narrow in SQL first (company and title must share their first word)
    # so this stays fast when the feed holds tens of thousands of jobs;
    # the exact canonical comparison below still decides.
    company_word = canon_company.split()[0]
    title_word = canon_title.split()[0]
    result = await db.execute(
        select(Job).where(
            Job.date_posted >= text(f"CURRENT_DATE - INTERVAL '{CANDIDATE_WINDOW_DAYS} days'"),
            Job.company.ilike(f"%{company_word}%"),
            Job.title.ilike(f"%{title_word}%"),
        )
    )
    candidates = [
        job
        for job in result.scalars().all()
        if canonicalize_company(job.company) == canon_company
        and canonicalize_title(job.title) == canon_title
        and location_bucket(job.location) == bucket
    ]
    if not candidates:
        return None

    # Step 3: confirm via description trigram similarity, not just the key match
    for job in candidates:
        similarity_row = await db.execute(
            select(text("similarity(:a, :b)")).params(
                a=(job.description or "")[:2000], b=candidate.description[:2000]
            )
        )
        similarity = similarity_row.scalar() or 0.0
        if similarity >= DESCRIPTION_SIMILARITY_THRESHOLD:
            return job

    return None


async def record_additional_source(
    db: AsyncSession, job: Job, source_id: str, candidate: NormalizedJob
) -> None:
    """Step 4: a confirmed duplicate is recorded as another reference, not
    a second jobs row — this is also what drives competition_score
    (architecture doc section 5.2, step 5)."""
    existing = await db.execute(
        select(JobSourceReference).where(
            JobSourceReference.job_id == job.id, JobSourceReference.source_id == source_id
        )
    )
    if existing.scalar_one_or_none():
        return  # already recorded this exact source for this job

    db.add(
        JobSourceReference(
            job_id=job.id,
            source_id=source_id,
            external_id=candidate.external_id,
            apply_url=candidate.apply_url,
        )
    )

    ref_count_result = await db.execute(
        select(JobSourceReference).where(JobSourceReference.job_id == job.id)
    )
    ref_count = len(ref_count_result.scalars().all()) + 1  # +1 for the one just added

    job.is_syndicated = True
    if ref_count >= 3:
        job.competition_score = "high"
    elif ref_count == 2:
        job.competition_score = "medium"
    else:
        job.competition_score = "low"
    job.is_hidden_gem = False  # confirmed duplicate elsewhere; no longer a hidden gem

    await db.commit()
