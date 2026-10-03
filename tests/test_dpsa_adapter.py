"""Government posts from the DPSA vacancy circular."""
import io
from datetime import date

from app.modules.job_discovery.adapters import dpsa_adapter as d

SAMPLE = """ANNEXURE A
DEPARTMENT OF AGRICULTURE
APPLICATIONS : Hand delivery to 20 Steve Biko Street, Arcadia, Pretoria or email recruit@nda.gov.za
CLOSING DATE : 16 October 2026 at 16:00
NOTE : Applications must be submitted on the new Z83 form.
OTHER POSTS
POST 35/01 : ICT SYSTEM ADMINISTRATOR (UNIX/LINUX AND WINDOWS) REF NO: 3/3/1/87/2026
Directorate: ICT Service Delivery and Operations
SALARY : R487 197 per annum (Level 09)
CENTRE : Gauteng (Pretoria)
REQUIREMENTS : Grade 12 and National Diploma in Information Technology (NQF Level 6).
Minimum three years IT experience.
DUTIES : Maintain Unix/Linux and Windows infrastructure.
ENQUIRIES : Ms M Nemutendani Tel No: (012) 319 6154
NOTE : EE Target: African Females and persons with disability.
POST 35/02 : GRADUATE INTERNS: AGRICULTURAL SCIENCE (X10 POSTS) REF NO: 3/3/1/90/2026
SALARY : R8 500 per month (stipend)
CENTRE : Eastern Cape (Middelburg)
REQUIREMENTS : A degree in Agriculture. No work experience required.
DUTIES : Assist with research projects.
ENQUIRIES : Mr T Cebani Tel No: (049) 802 6605
APPLICATIONS : email interns@nda.gov.za
CLOSING DATE : 23 October 2026
"""


def test_parses_each_post_with_its_fields():
    posts = d.parse_posts(SAMPLE, "Agriculture")
    assert [p["post"] for p in posts] == ["35/01", "35/02"]
    a, b = posts
    assert a["title"] == "ICT System Administrator (UNIX/Linux and Windows)"
    assert a["ref"] == "3/3/1/87/2026" and a["department"] == "Department of Agriculture"
    assert a["salary"].startswith("R487 197") and a["centre"] == "Gauteng (Pretoria)"
    assert "three years" in a["requirements"] and "Unix/Linux" in a["duties"]
    # section-level details carry forward; a post's own override them
    assert "recruit@nda.gov.za" in a["applications"] and a["closing_date"].startswith("16 October")
    assert b["applications"] == "email interns@nda.gov.za" and b["closing_date"] == "23 October 2026"
    assert b["title"] == "Graduate Interns: Agricultural Science" and b["posts"] == 10


def test_normalize_gives_salary_dates_and_industry():
    posts = d.parse_posts(SAMPLE, "Agriculture")
    a = d.DpsaCircularAdapter("s", {}).normalize(d.RawListing("2026-35-01", {**posts[0], "circular": 35, "year": 2026,
                                                                                 "pdf_url": "https://x/a.pdf"}))
    assert (a.salary_min, a.salary_max) == (487197, None)
    assert a.industry == d.INDUSTRY and a.company == "Department of Agriculture"
    assert a.raw_payload["closing_date_iso"] == "2026-10-16" and a.apply_url == "https://x/a.pdf"
    assert "Z83" in a.description and "Circular 35 of 2026" in a.description
    b = d.DpsaCircularAdapter("s", {}).normalize(d.RawListing("2026-35-02", {**posts[1], "circular": 35, "year": 2026}))
    assert b.salary_min == 8500 * 12        # monthly stipend shown as a yearly figure like other jobs


def test_money_ranges_and_dates():
    assert d._money("R1 216 824 - R1 433 355 per annum") == (1216824, 1433355)
    assert d._money("Market related") == (None, None)
    assert d.parse_date("Closing date: 6 November 2026 at 16:00") == date(2026, 11, 6)


def test_links_on_index_and_circular_pages():
    idx = ('<a href="/newsroom/psvc/circular-34-of-2026/">34</a><a href="https://www.dpsa.gov.za/newsroom/psvc/'
           'circular-35-of-2026/">35</a><a href="/newsroom/psvc/circular-43-of-2025/">old</a>')
    assert [(y, n) for y, n, _ in d.circular_links(idx, limit=2)] == [(2026, 35), (2026, 34)]
    page = ('<a href="/dpsa2g/documents/vacancies/2026/35/Circular 35 of 2026.pdf">Circular 35 (click here to view the full document)</a>'
            '<a href="/dpsa2g/documents/vacancies/2026/35/a.pdf"><strong>Agriculture</strong></a>'
            '<a href="/dpsa2g/documents/vacancies/2026/35/q.pdf">Eastern Cape</a>')
    links = d.pdf_links(page, "https://www.dpsa.gov.za/newsroom/psvc/circular-35-of-2026/")
    assert links == [("https://www.dpsa.gov.za/dpsa2g/documents/vacancies/2026/35/a.pdf", "Agriculture"),
                     ("https://www.dpsa.gov.za/dpsa2g/documents/vacancies/2026/35/q.pdf", "Eastern Cape")]


def test_reads_a_real_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in SAMPLE.splitlines():
        c.drawString(40, y, line[:110]); y -= 14
        if y < 60:
            c.showPage(); y = 800
    c.save()
    posts = d.parse_posts(d.pdf_text(buf.getvalue()), "Agriculture")
    assert [p["post"] for p in posts] == ["35/01", "35/02"]
    assert posts[0]["centre"] == "Gauteng (Pretoria)"


def test_title_case_keeps_acronyms():
    assert d.title_case("DEPUTY DIRECTOR: HRM AND SCM") == "Deputy Director: HRM and SCM"
    assert d.title_case("Already Mixed Case") == "Already Mixed Case"
