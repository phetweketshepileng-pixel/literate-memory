"""Polls every active job source once and tidies the results.

Run on a schedule by the Railway `job-poller` service:
    python scripts/poll_jobs.py
Seeds the default RSS sources below on first run (edit SOURCES to change them).
"""
import asyncio, json, os, sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import func, select, text
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

# ----------------------------------------------------------------- Adzuna
# South African job boards via the Adzuna API (needs ADZUNA_APP_ID/_KEY).
# Free tier: 250 requests/day, 1,000/week, 2,500/month (~80/day). Budget:
#   role searches      <= 18 pages, twice a day   -> 36/day
#   industry searches  <=  7 pages, once a day    ->  7/day
#   entry-level        <=  5 pages, once a day    ->  5/day
#   every category     <= 28 pages + 1 lookup, daily -> 29/day
#   total              <= ~77/day, ~2,300/month (searches stop early on a short page)
A = {"adapter_type": "adzuna", "country": "za", "max_days_old": 30}
# Role searches come from what people list under "Desired roles" on their
# profile (see app/modules/job_discovery/search_plan.py) — refreshed twice a day.
INDUSTRY_SEARCHES = [  # industries Adzuna has no category for — refreshed daily
    ("bank", "Gauteng", 1), ("bank", "Western Cape", 1), ("insurance", None, 1), ("telematics", None, 1),
    ("government", None, 1), ("municipality", None, 1), ("call centre", None, 1),
]
ROLE_REFRESH_HOURS, DAILY_REFRESH_HOURS = 11.5, 23.5
CATEGORY_PAGE_BUDGET = 28
# categories that get a 2nd page (the newest 100 jobs) when the budget allows
PRIORITY_CATEGORIES = ("accounting-finance-jobs", "it-jobs", "customer-services-jobs", "admin-jobs",
                       "sales-jobs", "consultancy-jobs", "hr-jobs", "logistics-warehouse-jobs", "engineering-jobs")
CATEGORY_PREFIX = "Adzuna SA category: "
ENTRY_LEVEL_SEARCHES = [  # jobs open to people without experience — refreshed daily
    ("learnership", None, 2), ("internship", None, 2), ("graduate programme", None, 1),
]
assert sum(p for *_, p in INDUSTRY_SEARCHES) <= 7 and sum(p for *_, p in ENTRY_LEVEL_SEARCHES) <= 5


def _adzuna_name(what, where):
    return f"Adzuna SA: {what}" + (f" ({where})" if where else " (all SA)")


def add_adzuna_searches(searches, hours):
    for what, where, pages in searches:
        SOURCES[_adzuna_name(what, where)] = {**A, "what": what, "pages": pages, "refresh_hours": hours,
                                               **({"where": where} if where else {})}


add_adzuna_searches(INDUSTRY_SEARCHES, DAILY_REFRESH_HOURS)
add_adzuna_searches(ENTRY_LEVEL_SEARCHES, DAILY_REFRESH_HOURS)


async def add_profile_role_searches(db):
    """One search per role people want (most wanted first, within budget)."""
    from app.modules.job_discovery.search_plan import PAGE_BUDGET, plan_role_searches
    roles = list((await db.execute(text(
        "SELECT unnest(desired_roles) FROM profiles WHERE desired_roles IS NOT NULL"))).scalars())
    plan = plan_role_searches(roles)
    assert sum(p for *_, p in plan) <= PAGE_BUDGET
    add_adzuna_searches(plan, ROLE_REFRESH_HOURS)
    print("ROLE_SEARCHES", ", ".join(f"{w} x{p}" for w, _, p in plan), flush=True)


def category_pages(tags):
    """1 page per category, then 2nd pages for priority ones, within the budget."""
    pages = {t: 1 for t in tags[:CATEGORY_PAGE_BUDGET]}
    spare = CATEGORY_PAGE_BUDGET - len(pages)
    for t in PRIORITY_CATEGORIES:
        if spare <= 0:
            break
        if t in pages:
            pages[t] += 1
            spare -= 1
    return pages


# ------------------------------------------------- employer careers boards
# Public job-board APIs (Greenhouse, Lever, SmartRecruiters, Workable).
# Jobs found only here are hidden gems. Only South African roles are kept.
BANKING, INSURANCE, FINTECH = "Banking & financial services", "Insurance", "Banking & financial services"
EMPLOYER_BOARDS = [  # (display name, platform, board id, industry)
    ("Standard Bank", "smartrecruiters", "StandardBankGroup", BANKING),
    ("Experian", "smartrecruiters", "Experian", BANKING),
    ("OUTsurance", "smartrecruiters", "OUTsurance", INSURANCE),
    ("1Life", "smartrecruiters", "1Life", INSURANCE),
    ("iKhokha", "smartrecruiters", "IKhokha", FINTECH),
    ("WNS", "smartrecruiters", "WNSGlobalServices144", "Contact centre & collections"),
    ("Sutherland", "smartrecruiters", "Sutherland", "Contact centre & collections"),
    ("Deloitte", "smartrecruiters", "Deloitte6", "Consulting"),
    ("BCX", "smartrecruiters", "BCX", "IT & technology"),
    ("Continental", "smartrecruiters", "Continental", "Manufacturing"),
    ("Takealot", "greenhouse", "takealotgroup", "Retail"),
    ("Ozow", "greenhouse", "ozow", FINTECH),
    ("Entersekt", "greenhouse", "entersekt", FINTECH),
    ("Luno", "greenhouse", "luno", FINTECH),
    ("OfferZen", "greenhouse", "offerzen", "IT & technology"),
    ("Mama Money", "lever", "mamamoney", FINTECH),
    ("dLocal", "lever", "dlocal", FINTECH),
    ("Clickatell", "workable", "clickatell", "IT & technology"),
    ("Cartrack", "workable", "cartrack", "Telematics & fleet"),
]
# Government posts: the weekly DPSA Public Service Vacancy Circular (one PDF
# per department). Read once a day; posts close on their own closing date.
DPSA_SOURCE = "Government: DPSA vacancy circular"
SOURCES[DPSA_SOURCE] = {"adapter_type": "dpsa_circular", "circulars": 3, "refresh_hours": 23.5}

for name, platform, board, industry in EMPLOYER_BOARDS:
    SOURCES[f"Careers: {name}"] = {"adapter_type": "ats_board", "platform": platform, "board": board,
                                   "company": name, "industry": industry, "sa_only": True}

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
                         AND e.key NOT ILIKE '%link%' AND length(e.value) BETWEEN 1 AND 200
                         AND left(e.value, 1) NOT IN ('{', '[') LIMIT 1) AS v
         FROM jobs j WHERE j.company IS NULL) sub
       WHERE jobs.id = sub.id AND sub.v IS NOT NULL""",
    """UPDATE jobs SET location = sub.v FROM (
         SELECT j.id, (SELECT e.value FROM jsonb_each_text(j.raw_payload) e
                       WHERE (e.key ILIKE '%location%' OR e.key ILIKE '%region%') AND length(e.value) BETWEEN 1 AND 200
                         AND left(e.value, 1) NOT IN ('{', '[') LIMIT 1) AS v
         FROM jobs j WHERE j.location = 'Remote') sub
       WHERE jobs.id = sub.id AND sub.v IS NOT NULL""",
    # undo earlier runs that copied a raw data object (e.g. an Adzuna ad with
    # no employer name) into company/location
    "UPDATE jobs SET company = NULL WHERE left(company, 1) IN ('{', '[')",
    "UPDATE jobs SET location = NULL WHERE left(location, 1) IN ('{', '[')",
    # feed summaries are HTML — keep plain text for the UI
    "UPDATE jobs SET description = trim(regexp_replace(regexp_replace(description, '<[^>]+>', ' ', 'g'), '&nbsp;|&amp;|&#39;|&quot;', ' ', 'g')) WHERE description LIKE '%<%'",
    # WWR titles look like 'Company: Role' with no author field
    "UPDATE jobs SET company = split_part(title, ': ', 1), title = substr(title, length(split_part(title, ': ', 1)) + 3) WHERE company IS NULL AND position(': ' in title) > 1",
    # government posts close on the closing date printed in the circular
    f"""UPDATE jobs SET is_active = false, closed_at = now() WHERE is_active
         AND raw_payload->>'closing_date_iso' < to_char(current_date, 'YYYY-MM-DD')
         AND source_id IN (SELECT id FROM job_sources WHERE name = '{DPSA_SOURCE}')""",
    # board jobs older than 40 days drop out of search (keeps the wider feed
    # lean); employer careers-page jobs stay while the employer still lists them
    """UPDATE jobs SET is_active = false, closed_at = now() WHERE is_active AND date_posted < current_date - 40
         AND source_id NOT IN (SELECT id FROM job_sources WHERE name LIKE 'Careers:%')""",
]

def _due(src, now):
    hours = (src.config or {}).get("refresh_hours")
    return not (hours and src.last_polled_at and now - src.last_polled_at < timedelta(hours=hours))


async def sync_categories(db, now):
    """Once a day: read Adzuna's category list and keep one source per category."""
    from app.modules.job_discovery.adapters.adzuna_adapter import fetch_categories
    existing = {s.name: s for s in (await db.execute(select(JobSource).where(JobSource.name.like(CATEGORY_PREFIX + "%")))).scalars()}
    active = [s for s in existing.values() if s.is_active]
    if active and not any(_due(s, now) for s in active):
        return
    try:
        cats = await fetch_categories("za")
    except Exception as e:  # keep yesterday's list if the lookup fails
        print("NOTE Adzuna category lookup failed:", str(e)[:200], flush=True)
        return
    tags = [c["tag"] for c in cats if c.get("tag") and c["tag"] not in ("unknown",)]
    pages = category_pages(tags)
    labels = {c["tag"]: c.get("label") or c["tag"] for c in cats}
    keep = set()
    for tag, n in pages.items():
        name = CATEGORY_PREFIX + labels[tag]
        keep.add(name)
        cfg = {**A, "category": tag, "pages": n, "refresh_hours": DAILY_REFRESH_HOURS}
        if name in existing:
            existing[name].config, existing[name].is_active = cfg, True
        else:
            db.add(JobSource(name=name, config=cfg, poll_frequency_minutes=1440))
    for name, src in existing.items():
        if name not in keep:
            src.is_active = False
    print("CATEGORIES", len(pages), "categories,", sum(pages.values()), "pages", flush=True)


async def backfill_industry(db):
    """Give jobs saved before industries existed (or before a rule changed) one."""
    from app.models import Job
    from app.modules.job_discovery.industry import classify_industry, industry_from_payload
    rows = (await db.execute(select(Job.id, Job.title, Job.company, Job.raw_payload)
                             .where(Job.is_active, Job.industry.is_(None)).limit(20000))).all()
    for jid, title, company, payload in rows:
        await db.execute(text("UPDATE jobs SET industry = :i WHERE id = :id"),
                         {"i": classify_industry(title, company, industry_from_payload(payload)), "id": jid})
    return len(rows)


async def backfill_opportunity(db):
    """Mark learnerships, internships and no-experience jobs saved before
    that classification existed."""
    from app.models import Job
    from app.modules.job_discovery.opportunity import classify_opportunity
    rows = (await db.execute(select(Job.id, Job.title, func.left(Job.description, 1500))
                             .where(Job.is_active, Job.entry_level.is_(None)).limit(20000))).all()
    for jid, title, desc in rows:
        kind, entry = classify_opportunity(title, desc)
        await db.execute(text("UPDATE jobs SET opportunity_type = :k, entry_level = :e WHERE id = :id"),
                         {"k": kind, "e": entry, "id": jid})
    return len(rows)


async def main():
    from app.core.config import settings
    have_adzuna = bool(settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY)
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        await add_profile_role_searches(db)
        existing = {s.name: s for s in (await db.execute(select(JobSource))).scalars()}
        for name, cfg in SOURCES.items():
            if name in existing:
                existing[name].config = cfg
                existing[name].is_active = True
            else:
                db.add(JobSource(name=name, config=cfg, poll_frequency_minutes=360))
        for src in existing.values():
            if (src.name.startswith("Adzuna") and not src.name.startswith(CATEGORY_PREFIX)
                    and src.name not in SOURCES and src.is_active):
                src.is_active = False  # search replaced; its jobs stay until they age out
        for src in (await db.execute(select(JobSource).where(JobSource.name.in_(RETIRED)))).scalars():
            src.is_active = False
            await db.execute(text("UPDATE jobs SET is_active = false, closed_at = now() WHERE source_id = :s AND is_active"), {"s": src.id})
        if have_adzuna:
            await sync_categories(db, now)
        await db.commit()
        ids = [(s.name, str(s.id)) for s in (await db.execute(select(JobSource).where(JobSource.is_active))).scalars()
               if _due(s, now)]
    if not have_adzuna:
        print("NOTE Adzuna keys not set - skipping South African job searches (set ADZUNA_APP_ID and ADZUNA_APP_KEY)", flush=True)
        ids = [(n, i) for n, i in ids if not n.startswith("Adzuna")]
    # employer boards first: a job seen there before Adzuna lists it stays a hidden gem until it shows up on a board
    ids.sort(key=lambda t: (not t[0].startswith("Careers:"), t[0]))
    print("POLLING", len(ids), "sources", flush=True)
    for name, sid in ids:
        try:
            print("POLL", json.dumps(await _poll_source_async(sid)), flush=True)
        except Exception as e:  # one bad source must not stop the rest
            print("POLL", json.dumps({"source": name, "status": "crash", "detail": str(e)[:200]}), flush=True)
    async with AsyncSessionLocal() as db:
        for q in CLEANUP:
            await db.execute(text(q))
        filled = await backfill_industry(db)
        classified = await backfill_opportunity(db)
        await db.commit()
        n = (await db.execute(text("select count(*) from jobs where is_active"))).scalar()
        gems = (await db.execute(text("select count(*) from jobs where is_active and is_hidden_gem"))).scalar()
    print("INDUSTRY_BACKFILLED", filled, "OPPORTUNITY_BACKFILLED", classified, flush=True)
    print("ACTIVE_JOBS", n, "HIDDEN_GEMS", gems, flush=True)

if __name__ == "__main__":
    asyncio.run(main())
