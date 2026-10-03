import pytest

from app.modules.job_discovery.opportunity import classify_opportunity as c


@pytest.mark.parametrize("title,desc,expected", [
    ("Banking Learnership 2027", "", ("learnership", True)),
    ("Unemployed Youth - NQF 4 Business Admin", "Learnership opportunity for matriculants", ("learnership", True)),
    ("IT Internship Programme", "", ("internship", True)),
    ("Graduate Intern: Finance", "", ("internship", True)),
    ("Finance Graduate Programme 2027", "", ("graduate", True)),
    ("Trainee Accountant (SAICA)", "", ("graduate", True)),
    ("Electrical Apprentice", "", ("apprenticeship", True)),
    ("YES4Youth Opportunity - Admin", "", ("yes", True)),
    ("Call Centre Agent", "Matric required. No experience required, full training provided.", ("entry", True)),
    ("Junior Data Capturer", "Grade 12", ("entry", True)),
    ("General Worker", "", ("entry", True)),
    ("Cashier", "Minimum 3 years experience in retail", (None, False)),
    ("Senior Business Analyst", "Mentor our interns and graduates", (None, False)),
    ("Collections Manager", "8+ years experience", (None, False)),
    ("Business Analyst", "5 years of experience in banking", (None, False)),
    ("Software Developer", "Entry-level position, 0-1 years", ("entry", True)),
    ("Operations Supervisor", "", (None, False)),
])
def test_classify(title, desc, expected):
    assert c(title, desc) == expected
