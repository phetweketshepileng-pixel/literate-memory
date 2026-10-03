import pytest

from app.modules.job_discovery.scam_check import check_job as c


@pytest.mark.parametrize("title,company,desc,level", [
    ("Learnership 2027", "Skills Academy", "Successful candidates must pay a once-off registration fee of R350.", "high"),
    ("Data Capturer", None, "Pay R250 for your training kit before you start.", "high"),
    ("Packer", None, "No experience required. Earn R30 000 per week!", "high"),
    ("Sales Agent", None, "Join our forex trading team and achieve financial freedom.", "high"),
    ("Admin Clerk", "Shoprite", "Send your CV to shopriterecruitment2027@gmail.com", "high"),
    ("Admin Clerk", "Small Bakery", "Send CV to bakerysmall@gmail.com", "caution"),
    ("Cleaner", None, "Apply via WhatsApp only: 071 000 0000", "caution"),
    ("General Worker", None, "Limited spots! Guaranteed job for all applicants.", "caution"),
])
def test_flags(title, company, desc, level):
    r = c(title, company, desc)
    assert r is not None and r.level == level and r.reasons


@pytest.mark.parametrize("title,company,desc", [
    ("Business Analyst", "Absa", "Apply online. Salary R45 000 per month. 5 years experience."),
    ("Banking Learnership", "Standard Bank", "Bring a certified copy of your ID and matric certificate. No fees are charged."),
    ("Call Centre Agent", "WNS", "No experience required, full training provided. Salary R6 500 per month."),
    ("Accountant", "Deloitte", "Responsible for processing fees and invoices for clients."),
])
def test_legit_ads_not_flagged(title, company, desc):
    assert c(title, company, desc) is None


def test_fee_words_need_the_applicant_to_pay():
    assert c("Learnership", None, "There is no registration fee. Training is free of charge.") is None
    assert c("Learnership", None, "A training fee is payable before you start.").level == "high"
