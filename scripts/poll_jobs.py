"""Polls every active job source once and tidies the results.

Run on a schedule by the Railway `job-poller` service:
    python scripts/poll_jobs.py
Seeds the default RSS sources below on first run (edit SOURCES to change them).
"""
import asyncio, json, os, sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import select, text
from app.core.database import AsyncSessionLocal
from app.models import JobSource
from app.workers.job_scraper_tasks import _poll_source_async

R = {"adapter_type": "rss_feed", "default_is_remote": True, "default_location": "Remote", "is_syndicated": True}
SOURCES = {
    "WWR Management & Finance": {**R, "feed_url": "https://weworkremotely.com/categories/remote-management-and-finance-jobs.rss"},
    "Remotive Project Management": {**R, "feed_url": "https://remotive.com/remote-jobs/feed/project-management"},
    "Jobicy Business": {**R, "feed_url": "https://jobicy.com/?feed=job_feed&job_categories=business"},
    "Himalayas": {**R, "feed_url": "https://himalayas.app/jobs/rss"},
}

# South African roles via the Adzuna API (needs ADZUNA_APP_ID / ADZUNA_APP_KEY).
# Targets the platform's core transition paths: collections/banking into
# business/systems/process/operations analysis, data, and IT/ops management.
#
# Adzuna's free tier allows 250 requests/day, 1,000/week and 2,500/month.
# These searches cost at most ADZUNA_PAGE_BUDGET requests per refresh (a
# search stops early when a page comes back short), and Adzuna sources are
# refreshed at most every ADZUNA_REFRESH_HOURS, i.e. ~2 refreshes/day
# -> <= ~50 requests/day, ~1,500/month.
ADZUNA_REFRESH_HOURS = 11.5
A = {"adapter_type": "adzuna", "country": "za", "max_days_old": 30}
ADZUNA_SEARCHES = [  # (keywords, location or None for all of SA, max pages of 50)
    ("business analyst", "Gauteng", 4),
    ("business analyst", "Western Cape", 2),
    ("business analyst", "KwaZulu-Natal", 1),
    ("business analyst remote", None, 1),
    ("junior business analyst", None, 1),
    ("systems analyst", "Gauteng", 2),
    ("process improvement", "Gauteng", 2),
    ("process analyst", "Gauteng", 1),
    ("operations analyst", "Gauteng", 1),
    ("data analyst", "Gauteng", 2),
    ("business intelligence analyst", "Gauteng", 1),
    ("credit risk analyst", "Gauteng", 1),
    ("IT manager", "Gauteng", 2),
    ("operations manager", "Gauteng", 2),
    ("project coordinator", "Gauteng", 1),
    ("collections manager", "Gauteng", 1),
]
ADZUNA_PAGE_BUDGET = sum(p for _, _, p in ADZUNA_SEARCHES)
assert ADZUNA_PAGE_BUDGET <= 30, "keep each refresh well inside Adzuna's free quota"
for what, where, pages in ADZUNA_SEARCHES:
    SOURCES[f"Adzuna SA: {what}" + (f" ({where})" if where else " (all SA)")] = {
        **A, "what": what, "pages": pages, **({"where": where} if where else {})
    }

# Sources dropped after the first live run: Remotive's business and
# finance feeds return 404, and the ACCA feed ignores its country filter
# (listings were European, not South African). Their jobs are hidden.
RETIRED = ("Remotive Business", "Remotive Finance & Legal", "ACCA Careers South Africa",
           # global feeds that were mostly unrelated roles (engineering,
           # support, data science) — noise for SA analyst job seekers
           "WWR Product", "WWR Customer Support", "Jobicy Data Science")

CLEANUP = [
    # many feeds (Jobicy, Himalayas) carry company/location in namespaced
    # fields like job_listing:company rather than <author>
    """UPDATE jobs SET company = sub.v FROM (
         SELECT j.id, (SELECT e.value FROM jsonb_each_text(j.raw_payload) e
                       WHERE e.key ILIKE '%company%' AND e.key NOT ILIKE '%logo%' AND e.key NOT ILIKE '%url%'
                         AND e.key NOT ILIKE '%link%' AND length(e.value) BETWEEN 1 AND 200 LIMIT 1) AS v
         FROM jobs j WHERE j.company IS NULL) sub
       WHERE jobs.id = sub.id AND sub.v IS NOT NULL""",
    """UPDATE jobs SET location = sub.v FROM (
         SELECT j.id, (SELECT e.value FROM jsonb_each_text(j.raw_payload) e
                       WHERE (e.key ILIKE '%location%' OR e.key ILIKE '%region%') AND length(e.value) BETWEEN 1 AND 200 LIMIT 1) AS v
         FROM jobs j WHERE j.location = 'Remote') sub
       WHERE jobs.id = sub.id AND sub.v IS NOT NULL""",
    # feed summaries are HTML — keep plain text for the UI
    "UPDATE jobs SET description = trim(regexp_replace(regexp_replace(description, '<[^>]+>', ' ', 'g'), '&nbsp;|&amp;|&#39;|&quot;', ' ', 'g')) WHERE description LIKE '%<%'",
    # WWR titles look like 'Company: Role' with no author field
    "UPDATE jobs SET company = split_part(title, ': ', 1), title = substr(title, length(split_part(title, ': ', 1)) + 3) WHERE company IS NULL AND position(': ' in title) > 1",
    # jobs older than 45 days drop out of search
    "UPDATE jobs SET is_active = false, closed_at = now() WHERE is_active AND date_posted < current_date - 45",
]

async def main():
    async with AsyncSessionLocal() as db:
        existing = {s.name: s for s in (await db.execute(select(JobSource))).scalars()}
        for name, cfg in SOURCES.items():
            if name in existing:
                existing[name].config = cfg
            else:
                db.add(JobSource(name=name, config=cfg, poll_frequency_minutes=360))
        for src in existing.values():
            if src.name.startswith("Adzuna") and src.name not in SOURCES and src.is_active:
                src.is_active = False  # search replaced; its jobs stay until they age out
        for src in (await db.execute(select(JobSource).where(JobSource.name.in_(RETIRED)))).scalars():
            src.is_active = False
            await db.execute(text("UPDATE jobs SET is_active = false, closed_at = now() WHERE source_id = :s AND is_active"), {"s": src.id})
        await db.commit()
        now = datetime.now(UTC)
        ids = [
            (s.name, str(s.id))
            for s in (await db.execute(select(JobSource).where(JobSource.is_active))).scalars()
            # Adzuna searches refresh ~twice a day to stay inside the free quota
            if not (s.name.startswith("Adzuna") and s.last_polled_at
                    and now - s.last_polled_at < timedelta(hours=ADZUNA_REFRESH_HOURS))
        ]
    from app.core.config import settings
    if not (settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY):
        print("NOTE Adzuna keys not set - skipping South African job searches (set ADZUNA_APP_ID and ADZUNA_APP_KEY)", flush=True)
        ids = [(n, i) for n, i in ids if not n.startswith("Adzuna")]
    for name, sid in ids:
        try:
            print("POLL", json.dumps(await _poll_source_async(sid)), flush=True)
        except Exception as e:  # one bad source must not stop the rest
            print("POLL", json.dumps({"source": name, "status": "crash", "detail": str(e)[:200]}), flush=True)
    async with AsyncSessionLocal() as db:
        for q in CLEANUP:
            await db.execute(text(q))
        await db.commit()
        n = (await db.execute(text("select count(*) from jobs where is_active"))).scalar()
    print("ACTIVE_JOBS", n, flush=True)

asyncio.run(main())
