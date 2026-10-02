from app.modules.job_discovery.industry import (
    BANKING, CONTACT_CENTRE, GOVERNMENT, INSURANCE, TELEMATICS, category_name, classify_industry, industry_from_payload,
)


def test_known_employers():
    assert classify_industry("Business Analyst", "Standard Bank Group") == BANKING
    assert classify_industry("Data Analyst", "Nedbank Ltd") == BANKING
    assert classify_industry("Developer", "Old Mutual") == INSURANCE
    assert classify_industry("Sales Consultant", "Cartrack") == TELEMATICS
    assert classify_industry("Call Center Agent - Inbound", "WNS Global Services") == CONTACT_CENTRE
    assert classify_industry("Clerk", "City of Johannesburg Metropolitan Municipality") == GOVERNMENT
    assert classify_industry("Analyst", "Department of Health") == GOVERNMENT


def test_title_keywords_when_employer_unknown():
    assert classify_industry("Telematics Technician", "Acme") == TELEMATICS
    assert classify_industry("Collections Team Leader", "Acme") == CONTACT_CENTRE
    assert classify_industry("Relationship Banker", "Acme") == BANKING
    assert classify_industry("Claims Assessor", "Acme") == INSURANCE


def test_board_category_then_other():
    assert classify_industry("Java Developer", "Acme", "IT Jobs") == "IT & technology"
    assert classify_industry("Bookkeeper", "Acme", "Accounting & Finance Jobs") == "Accounting & finance"
    assert classify_industry("Something", "Acme") == "Other"
    assert category_name("Unknown") is None
    assert category_name("Spaceflight Jobs") == "Spaceflight"


def test_source_industry_wins():
    assert classify_industry("Developer", "Standard Bank", "IT Jobs", source_industry="Banking & financial services") == BANKING


def test_payload_category():
    assert industry_from_payload({"category": {"label": "IT Jobs", "tag": "it-jobs"}}) == "IT Jobs"
    assert industry_from_payload({}) is None and industry_from_payload(None) is None
