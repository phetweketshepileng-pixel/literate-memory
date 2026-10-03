"""Government jobs from the DPSA Public Service Vacancy Circular.

Every week (except December) the Department of Public Service and
Administration publishes one circular listing posts across national and
provincial departments: https://www.dpsa.gov.za/newsroom/psvc/
Each circular has its own page linking one PDF per department
(.../vacancies/2026/35/a.pdf, b.pdf ...), and every post in a PDF uses the
same labels:

    POST 35/01 : ICT SYSTEM ADMINISTRATOR REF NO: 3/3/1/87/2026
    SALARY : R487 197 per annum (Level 09)
    CENTRE : Gauteng (Pretoria)
    REQUIREMENTS : ...   DUTIES : ...   ENQUIRIES : ...
    APPLICATIONS : ...   CLOSING DATE : 16 October 2026   NOTE : ...

APPLICATIONS / CLOSING DATE often appear once at the top of a department's
section and apply to all its posts, so the parser carries them forward.

config keys:
    index_url   the circulars page (default below)
    circulars   how many of the latest circulars to read (default 3: posts
                usually stay open about two weeks)
"""
from __future__ import annotations

import html as htmllib
import io
import re
from datetime import UTC, date, datetime
from urllib.parse import urljoin

import httpx

from app.modules.job_discovery.adapters.base import JobSourceAdapter, NormalizedJob, RateLimitPolicy, RawListing

INDEX_URL = "https://www.dpsa.gov.za/newsroom/psvc/"
INDUSTRY = "Government & public sector"
HOW_TO_APPLY = ("Government posts are free to apply for. You need a completed Z83 application form "
                "(on the DPSA vacancy circular page) and a short CV. Follow the application details "
                "above exactly — late or incomplete applications are not considered.")
HEADERS = {"User-Agent": "Ascend job alerts (free career tool for South African job seekers)"}

_CIRCULAR_LINK = re.compile(r'href="([^"]*?/psvc/circular-(\d+)-of-(\d{4})/?)"', re.I)
_PDF_LINK = re.compile(r'<a[^>]+href="([^"]+?/vacancies/\d{4}/\d+/[^"/]+\.pdf)"[^>]*>(.*?)</a>', re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")

LABELS = ("SALARY", "CENTRE", "REQUIREMENTS", "DUTIES", "ENQUIRIES", "APPLICATIONS", "FOR ATTENTION",
          "CLOSING DATE", "NOTE", "NOTES")
_LABEL = re.compile(r"(?:^|\n)[ \t]*(" + "|".join(re.escape(l) for l in LABELS) + r")[ \t]*:[ \t]*", re.I)
_POST = re.compile(r"(?:^|\n)[ \t]*POST[ \t]+(\d{1,3})[ \t]*/[ \t]*(\d{1,4})[ \t]*:?[ \t]*", re.I)
_REF = re.compile(r"\bREF(?:ERENCE)?\.?\s*(?:NO|NUMBER)?\.?\s*:?\s*([\w/.\- ]{2,60}?)(?=\s*(?:\(|$|\n))", re.I)
_DEPT_LINE = re.compile(r"^\s*((?:NATIONAL |PROVINCIAL )?DEPARTMENT OF [A-Z ,&'\-]+|OFFICE OF THE [A-Z ,&'\-]+"
                        r"|PROVINCIAL ADMINISTRATION:?\s*[A-Z ,&'\-]+|[A-Z][A-Z ,&'\-]+ (?:COMMISSION|AGENCY|SECRETARIAT|"
                        r"SCHOOL OF GOVERNMENT|ACADEMY|PRESIDENCY))\s*$")
_MONEY = re.compile(r"R\s?(\d{1,3}(?:[  ,]\d{3})+|\d{4,7})(?:\.\d{2})?")
_DATE = re.compile(r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)"
                   r"\s+(\d{4})", re.I)
_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                         "september", "october", "november", "december"], 1)}
# words that stay in capitals when titles are converted from ALL CAPS
_ACRONYMS = {"ICT", "IT", "HR", "HRM", "HRD", "SMS", "MMS", "OSD", "CFO", "CEO", "CIO", "SCM", "EPWP", "GIS", "PA",
             "EAP", "OHS", "SHE", "ECD", "TVET", "NQF", "SAPS", "SANDF", "SARS", "DPSA", "MEC", "DG", "DDG", "CD",
             "HOD", "PMDS", "M&E", "ERP", "SAP", "PERSAL", "BAS", "LOGIS", "AI", "UNIX", "II", "III", "IV", "CAD",
             "SITA", "PHC", "ICU", "OT", "ENT", "HIV", "TB", "STI", "EMS", "WIL", "VIP", "NHI", "PFMA", "MFMA"}
_SMALL = {"and", "of", "the", "for", "in", "on", "to", "a", "an", "at", "with", "or", "by"}


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(_TAGS.sub(" ", fragment))).strip()


def circular_links(index_html: str, base: str = INDEX_URL, limit: int = 3) -> list[tuple[int, int, str]]:
    """Latest circulars first: [(year, number, url)]."""
    seen = {}
    for href, num, year in _CIRCULAR_LINK.findall(index_html):
        seen[(int(year), int(num))] = urljoin(base, href)
    return [(y, n, u) for (y, n), u in sorted(seen.items(), reverse=True)][:limit]


def pdf_links(circular_html: str, base: str) -> list[tuple[str, str]]:
    """Per-department PDFs on a circular page: [(url, label)]. The single
    'full document' PDF repeats them all, so it is skipped."""
    out, seen = [], set()
    for href, label in _PDF_LINK.findall(circular_html):
        url, text = urljoin(base, href), _text(label)
        if url in seen or re.search(r"full|complete|entire|whole", text, re.I):
            continue
        seen.add(url)
        out.append((url, text))
    return out


def title_case(s: str) -> str:
    """'ICT SYSTEM ADMINISTRATOR (UNIX/LINUX AND WINDOWS)' -> 'ICT System Administrator (Unix/Linux and Windows)'."""
    s = re.sub(r"\s+", " ", s).strip(" :-–")
    if not s or (any(c.islower() for c in s) and not s.isupper()):
        return s

    def word(w: str, first: bool) -> str:
        core = re.sub(r"[^\w&]", "", w).upper()
        if core in _ACRONYMS:
            return w.upper()
        low = w.lower()
        if not first and low in _SMALL:
            return low
        return re.sub(r"[a-z]", lambda m: m.group(0).upper(), low, count=1) if low else low

    parts = re.split(r"(\s+|/|-|\()", s)
    out, first = [], True
    for p in parts:
        if not p or re.fullmatch(r"\s+|/|-|\(", p):
            out.append(p or "")
            continue
        out.append(word(p, first))
        first = False
    return "".join(out)


def _money(value: str) -> tuple[int | None, int | None]:
    nums = [int(re.sub(r"[  ,]", "", m)) for m in _MONEY.findall(value or "")]
    if not nums:
        return None, None
    monthly = bool(re.search(r"per month|p\.?m\.?\b|monthly|stipend", value, re.I)) and not re.search(r"per annum|p\.?a\.?\b", value, re.I)
    nums = [n * 12 if monthly else n for n in nums[:2]]
    lo, hi = min(nums), max(nums)
    return lo, (hi if hi != lo else None)


def parse_date(value: str | None) -> date | None:
    m = _DATE.search(value or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
    except ValueError:
        return None


def _fields(chunk: str) -> tuple[str, dict[str, str]]:
    """Split one post's text into (heading, {LABEL: value})."""
    parts = _LABEL.split(chunk)
    head, fields = parts[0], {}
    for i in range(1, len(parts) - 1, 2):
        key = parts[i].upper().replace("NOTES", "NOTE")
        val = re.sub(r"[ \t]+", " ", parts[i + 1]).strip()
        fields[key] = (fields[key] + "\n" + val) if key in fields else val
    return head, fields


def _department(text: str) -> str | None:
    found = None
    for line in text.splitlines():
        m = _DEPT_LINE.match(line)
        if m and len(m.group(1)) < 120:
            found = m.group(1)
    return title_case(found) if found else None


def parse_posts(text: str, default_department: str | None = None) -> list[dict]:
    """All posts in one department PDF's text."""
    text = text.replace("\r", "\n").replace(" ", " ")
    matches = list(_POST.finditer(text))
    posts = []
    # section-level details (apply-to address, closing date) carried forward
    _, top = _fields(text[: matches[0].start()] if matches else text)
    carry = {k: top[k] for k in ("APPLICATIONS", "CLOSING DATE", "FOR ATTENTION") if k in top}
    department = _department(text[: matches[0].start()] if matches else "") or default_department
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[m.end(): end]
        head, fields = _fields(chunk)
        # a department heading inside this chunk (after the post's own heading) starts the next posts' department
        tail_dept = _department(chunk.split("\n", 1)[1] if "\n" in chunk else "")
        first_line, _, rest = head.partition("\n")
        heading = first_line
        # titles sometimes wrap onto a second line before REF NO / the first label
        if rest and not _REF.search(first_line) and _REF.search(first_line + " " + rest.split("\n", 1)[0]):
            heading = first_line + " " + rest.split("\n", 1)[0]
        ref = _REF.search(heading)
        title = heading[: ref.start()] if ref else heading
        title = re.sub(r"\(\s*X?\s*\d+\s+POSTS?\s*\)|\bX\s*\d+\s+POSTS?\b", "", title, flags=re.I)
        title = re.sub(r"\(\s*\)", "", title)
        title = title_case(title)
        if not title or len(title) < 3:
            continue
        for k in ("APPLICATIONS", "CLOSING DATE", "FOR ATTENTION"):
            fields.setdefault(k, carry.get(k, ""))
        n_posts = re.search(r"\(\s*X?\s*(\d+)\s+POSTS?\s*\)", heading, re.I)
        posts.append({
            "post": f"{m.group(1)}/{m.group(2)}",
            "title": title[:300],
            "ref": ref.group(1).strip() if ref else None,
            "posts": int(n_posts.group(1)) if n_posts else 1,
            "department": department,
            "salary": fields.get("SALARY", ""),
            "centre": fields.get("CENTRE", ""),
            "requirements": fields.get("REQUIREMENTS", ""),
            "duties": fields.get("DUTIES", ""),
            "enquiries": fields.get("ENQUIRIES", ""),
            "applications": fields.get("APPLICATIONS", ""),
            "for_attention": fields.get("FOR ATTENTION", ""),
            "closing_date": fields.get("CLOSING DATE", ""),
            "note": fields.get("NOTE", ""),
        })
        # a department header or section-level details after this post apply to the next ones
        if tail_dept:
            department = tail_dept
    return posts


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def _first_line(s: str, n: int = 200) -> str:
    return re.sub(r"\s+", " ", (s or "").split("\n")[0]).strip()[:n]


class DpsaCircularAdapter(JobSourceAdapter):
    def rate_limit_policy(self) -> RateLimitPolicy:
        return RateLimitPolicy(requests_per_minute=30)

    async def fetch_listings(self, since: datetime | None) -> list[RawListing]:
        index_url = self.config.get("index_url", INDEX_URL)
        out: list[RawListing] = []
        async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers=HEADERS) as client:
            r = await client.get(index_url)
            r.raise_for_status()
            circulars = circular_links(r.text, index_url, int(self.config.get("circulars", 3)))
            for year, number, url in circulars:
                try:
                    page = await client.get(url)
                    page.raise_for_status()
                except httpx.HTTPError as e:
                    print("DPSA circular failed", number, year, str(e)[:120], flush=True)
                    continue
                for pdf_url, label in pdf_links(page.text, url):
                    try:
                        resp = await client.get(pdf_url)
                        resp.raise_for_status()
                        posts = parse_posts(pdf_text(resp.content), label or None)
                    except Exception as e:  # noqa: BLE001 — one bad PDF must not stop the rest
                        print("DPSA pdf failed", pdf_url, str(e)[:160], flush=True)
                        continue
                    print("DPSA", f"{number}/{year}", pdf_url.rsplit("/", 1)[-1], label[:40], len(posts),
                          (posts[0]["title"][:50] if posts else "-"), flush=True)
                    for p in posts:
                        p.update(circular=number, year=year, pdf_url=pdf_url, circular_url=url)
                        out.append(RawListing(external_id=f"{year}-{number}-{p['post'].split('/')[-1]}", payload=p))
        return out

    def normalize(self, raw: RawListing) -> NormalizedJob:
        p = raw.payload
        lo, hi = _money(p.get("salary", ""))
        closing = parse_date(p.get("closing_date"))
        sections = [
            ("Department", p.get("department")),
            ("Salary", p.get("salary")),
            ("Centre", p.get("centre")),
            ("Requirements", p.get("requirements")),
            ("Duties", p.get("duties")),
            ("Enquiries", p.get("enquiries")),
            ("How to apply", "\n".join(x for x in (p.get("applications"), p.get("for_attention") and "For attention: " + p["for_attention"]) if x)),
            ("Closing date", p.get("closing_date")),
            ("Note", p.get("note")),
        ]
        desc = "\n\n".join(f"{k}: {v.strip()}" for k, v in sections if v and v.strip())
        desc += f"\n\n{HOW_TO_APPLY}\n\nSource: Public Service Vacancy Circular {p.get('circular')} of {p.get('year')} (post {p.get('post')}" + (f", ref {p['ref']}" if p.get("ref") else "") + ")."
        centre = _first_line(p.get("centre", ""), 250) or "South Africa"
        return NormalizedJob(
            external_id=raw.external_id,
            title=p["title"],
            company=(p.get("department") or "South African government")[:255],
            location=centre,
            is_remote=False,
            salary_min=lo,
            salary_max=hi,
            description=desc,
            apply_url=p.get("pdf_url") or INDEX_URL,
            date_posted=datetime.now(UTC).date(),
            is_syndicated=True,
            raw_payload={**p, "closing_date_iso": closing.isoformat() if closing else None, "via": "dpsa"},
            industry=INDUSTRY,
        )
