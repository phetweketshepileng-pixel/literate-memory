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


# text as it really comes out of the DPSA PDFs (circular 35 of 2026, annexures A and Q)
REAL_A = """4
ANNEXURE A
DEPARTMENT OF AGRICULTURE (DOA)
CLOSING DATE  :  16 October 2026 at 16:00
NOTE  :  To apply, submit a completed Z83 form and detailed Curriculum Vitae (PDF
document to a maximum of 10 megabytes) via e-mail or hand delivery. Applications: Please submit
your application before the closing date.
5
OTHER POSTS
POST 35/01  :  ICT SYSTEM ADMINISTRATOR (UNIX/LINUX AND WINDOWS) REF NO:
3/3/1/87/2026
Directorate: ICT Service Delivery and Operations
SALARY  :  R487 197 per annum (Level 09)
CENTRE  :  Gauteng (Pretoria)
REQUIREMENTS  :  Applicants must be in possession of a Grade 12 Certificate and a National
Diploma  in  Information  Technology/Computer  Science  (NQF  Level  6).
DUTIES  :  Maintain Hardware and Software Infrastructure.
ENQUIRIES  :  Ms M Nemutendani Tel No: (012) 319 6154 / 6195
APPLICATIONS  :  Applications can be submitted by hand delivery during office hours to 20 Steve
Biko  Street,  Agriculture  Place,  Arcadia,  Pretoria,  0002  or  by  email
ICTSArecruit87@nda.gov.za
NOTE  :  EE Target: African Females and persons with disability.
POST 35/02  :  SENIOR AGRICULTURAL  SCIENTIST  (SENIOR  LECTURER)  REF  NO:
3/3/1/88/2026
Directorate: Grootfontein Agricultural Development Institute
SALARY  :  R487 197 per annum (Level 09)
CENTRE  :  Eastern Cape (Middelburg)
REQUIREMENTS  :  Grade 12 Certificate and a Bachelor of Science Degree (BSc) in Agriculture.
DUTIES  :  Develop and implement the academic curriculum.
ENQUIRIES  :  Mr T Cebani Tel No: (049) 802 6605
APPLICATIONS  :  email SASrecruit88@nda.gov.za
NOTE  :  EE Target: African Males.
6
ANNEXURE B
"""

REAL_Q = """ANNEXURE Q
PROVINCIAL ADMINISTRATION: FREE STATE
DEPARTMENT OF HEALTH
APPLICATIONS  :  Applications should be sent to recruitment@fshealth.gov.za
CLOSING DATE  :  17 October 2026
OTHER POSTS
POST 35/170  :  MEDICAL SPECIALIST GRADE 1-3: PAEDIATRICS REF NO: H/M/34/2026
(X2 POSTS)
SALARY  :  Grade 1: R1 341 855 – R1 422 810 per annum
Grade 2: R1 531 032 – R1 623 609 per annum
Grade 3: R1 773 222 – R2 212 680 per annum
116
all -inclusive package consists of 70% basic salary and 30% flexible portion
CENTRE  :  Pelonomi Tertiary Hospital
REQUIREMENTS  :  Senior Certificate/ Grade 12. Registration with the HPCSA as a Medical Specialist.
DUTES  :  Provide specialist paediatric care.
ENQUIRIES  :  Dr X Tel No: (051) 405 1911
"""


def test_real_national_layout():
    a, b = d.parse_posts(REAL_A, "Agriculture")
    assert a["title"] == "ICT System Administrator (UNIX/Linux and Windows)" and a["ref"] == "3/3/1/87/2026"
    assert b["title"] == "Senior Agricultural Scientist (Senior Lecturer)" and b["ref"] == "3/3/1/88/2026"
    assert a["department"] == "Department of Agriculture (DOA)"
    assert a["directorate"] == "Directorate: ICT Service Delivery and Operations"
    assert a["closing_date"].startswith("16 October 2026") and "ICTSArecruit87@nda.gov.za" in a["applications"]
    assert "ANNEXURE" not in b["note"] and not b["note"].endswith("6")


def test_real_provincial_layout():
    (p,) = d.parse_posts(REAL_Q, "Free State")
    assert p["title"] == "Medical Specialist Grade 1-3: Paediatrics" and p["posts"] == 2 and p["ref"] == "H/M/34/2026"
    assert p["department"] == "Department of Health (Free State)" and p["duties"].startswith("Provide")
    job = d.DpsaCircularAdapter("s", {}).normalize(d.RawListing("2026-35-170", {**p, "circular": 35, "year": 2026}))
    assert job.location == "Pelonomi Tertiary Hospital, Free State"
    assert (job.salary_min, job.salary_max) == (1341855, 2212680)
    assert job.raw_payload["closing_date_iso"] == "2026-10-17"


def test_single_quoted_circular_links():
    idx = "<a href='/newsroom/psvc/circular-35-of-2026/'>35</a><a href='/newsroom/psvc/circular-34-of-2026/'>34</a>"
    assert [n for _, n, _ in d.circular_links(idx)] == [35, 34]
