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

# the circulars page quotes its links with ' and each circular page with " — accept both
_CIRCULAR_LINK = re.compile(r"""href=["']([^"']*?circular-(\d+)-of-(\d{4})/?)["']""", re.I)
_PDF_LINK = re.compile(r"""<a[^>]+href=["']([^"']+?/vacancies/\d{4}/\d+/[^"'/]+\.pdf)["'][^>]*>(.*?)</a>""", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")

LABELS = ("SALARY", "CENTRE", "REQUIREMENTS", "DUTIES", "DUTES", "ENQUIRIES", "APPLICATIONS", "FOR ATTENTION",
          "CLOSING DATE", "NOTE", "NOTES")
_LABEL = re.compile(r"(?:^|\n)[ \t]*(" + "|".join(re.escape(l) for l in LABELS) + r")[ \t]*:[ \t]*", re.I)
_POST = re.compile(r"(?:^|\n)[ \t]*POST[ \t]+(\d{1,3})[ \t]*/[ \t]*(\d{1,4})[ \t]*:?[ \t]*", re.I)
# "REF NO: 3/3/1/87/2026" — the number often wraps onto the next line
_REF = re.compile(r"\bREF(?:ERENCE)?\.?\s*(?:NO|NUMBER)\.?\s*:?\s*([A-Z0-9][\w.\-]*(?:\s*/\s*[\w.\-]+)*)", re.I)
_REF_START = re.compile(r"\bREF(?:ERENCE)?\.?\s*(?:NO|NUMBER)\b", re.I)
_DEPT_LINE = re.compile(r"^\s*((?:NATIONAL )?DEPARTMENT OF [A-Z ,&'\-]+(?:\s*\([A-Z&]+\))?|OFFICE OF THE [A-Z ,&'\-]+"
                        r"(?:\s*\([A-Z&]+\))?|[A-Z][A-Z ,&'\-]+ (?:COMMISSION|AGENCY|SECRETARIAT|SCHOOL OF GOVERNMENT|"
                        r"ACADEMY|PRESIDENCY)(?:\s*\([A-Z&]+\))?)\s*$")
_PROVINCE_LINE = re.compile(r"^\s*PROVINCIAL ADMINISTRATION\s*:?\s*([A-Z \-]+?)\s*$")
_N_POSTS = re.compile(r"\(\s*X?\s*(\d+)\s+POSTS?\s*\)", re.I)
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
    nums = [n * 12 if monthly else n for n in nums[:12]]  # several grades -> lowest to highest
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


# page numbers and section headings that land between posts
_NOISE_LINES = re.compile(r"(?:\n[ \t]*(?:\d{1,4}|ANNEXURE [A-Z]{1,2}|OTHER POSTS|MANAGEMENT ECHELON|"
                          r"PROVINCIAL ADMINISTRATION\s*:?[A-Z \-]*|(?:NATIONAL )?DEPARTMENT OF [A-Z ,&'\-]+(?:\s*\([A-Z&]+\))?)"
                          r"[ \t]*(?=\n))+")


def _fields(chunk: str) -> tuple[str, dict[str, str]]:
    """Split one post's text into (heading, {LABEL: value})."""
    parts = _LABEL.split(chunk)
    head, fields = parts[0], {}
    for i in range(1, len(parts) - 1, 2):
        key = parts[i].upper().replace("NOTES", "NOTE")
        val = _NOISE_LINES.sub("\n", "\n" + parts[i + 1] + "\n")
        val = re.sub(r"[ \t]+", " ", val).strip()
        fields[key] = (fields[key] + "\n" + val) if key in fields else val
    return head, fields


def _headers(text: str) -> tuple[str | None, str | None]:
    """Last department and province headings in `text`."""
    dept = prov = None
    for line in text.splitlines():
        m = _PROVINCE_LINE.match(line)
        if m:
            prov, dept = title_case(m.group(1)), None
            continue
        m = _DEPT_LINE.match(line)
        if m and len(m.group(1)) < 120:
            name, abbr = re.match(r"(.*?)\s*(\([A-Z&]+\))?$", m.group(1)).groups()
            dept = title_case(name) + (f" {abbr}" if abbr else "")  # keep "(DOA)" in capitals
    return dept, prov


def _company(dept: str | None, prov: str | None, default: str | None) -> str | None:
    if dept and prov:
        return f"{dept} ({prov})"
    return dept or (f"{prov} provincial government" if prov else default)


def parse_posts(text: str, default_department: str | None = None) -> list[dict]:
    """All posts in one department PDF's text."""
    text = text.replace("\r", "\n").replace("\u00a0", " ")
    matches = list(_POST.finditer(text))
    posts = []
    preamble = text[: matches[0].start()] if matches else text
    # section-level details (apply-to address, closing date) carried forward
    _, top = _fields(preamble)
    carry = {k: top[k] for k in ("APPLICATIONS", "CLOSING DATE", "FOR ATTENTION") if k in top}
    dept, prov = _headers(preamble)
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[m.end(): end]
        head, fields = _fields(chunk)
        heading = re.sub(r"\s+", " ", head).strip()
        directorate = None
        dm = re.search(r"\b(?:Directorate|Chief Directorate|Branch|Component|Unit|Sub-?directorate)\s*:\s*(.+)$", heading, re.I)
        if dm:
            directorate, heading = dm.group(0).strip(), heading[: dm.start()].strip()
        ref = _REF.search(heading)
        cut = _REF_START.search(heading)
        title = heading[: cut.start()] if cut else heading
        n_posts = _N_POSTS.search(heading)
        title = _N_POSTS.sub("", title)
        title = re.sub(r"\bX\s*\d+\s+POSTS?\b|\(\s*\)", "", title, flags=re.I)
        title = title_case(title)
        if not title or len(title) < 3:
            continue
        for k in ("APPLICATIONS", "CLOSING DATE", "FOR ATTENTION"):
            fields.setdefault(k, carry.get(k, ""))
        salary = re.sub(r"\n\d{1,4}\n", "\n", "\n" + fields.get("SALARY", "") + "\n").strip()  # drop page numbers
        posts.append({
            "post": f"{m.group(1)}/{m.group(2)}",
            "title": title[:300],
            "ref": ref.group(1).replace(" ", "") if ref else None,
            "posts": int(n_posts.group(1)) if n_posts else 1,
            "department": _company(dept, prov, default_department),
            "province": prov,
            "directorate": directorate,
            "salary": salary,
            "centre": fields.get("CENTRE", ""),
            "requirements": fields.get("REQUIREMENTS", ""),
            "duties": fields.get("DUTIES") or fields.get("DUTES", ""),
            "enquiries": fields.get("ENQUIRIES", ""),
            "applications": fields.get("APPLICATIONS", ""),
            "for_attention": fields.get("FOR ATTENTION", ""),
            "closing_date": fields.get("CLOSING DATE", ""),
            "note": fields.get("NOTE", ""),
        })
        # a new department / province heading inside this chunk applies to the posts after it
        d2, p2 = _headers(chunk)
        if p2:
            prov, dept = p2, d2
        elif d2:
            dept = d2
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
            ("Unit", p.get("directorate")),
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
        centre = _first_line(p.get("centre", ""), 200) or "South Africa"
        prov = p.get("province")
        if prov and prov.lower() not in centre.lower():
            centre = f"{centre}, {prov}"
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
