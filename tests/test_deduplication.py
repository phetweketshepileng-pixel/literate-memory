from app.modules.job_discovery.canonicalization import (
    canonicalize_company,
    canonicalize_title,
    location_bucket,
)


def test_canonicalize_company_strips_legal_suffixes():
    assert canonicalize_company("FirstRand Bank Pty Ltd") == "firstrand bank"
    assert canonicalize_company("Discovery Limited Inc.") == "discovery"


def test_canonicalize_company_strips_punctuation_and_case():
    assert canonicalize_company("O'Reilly & Co.") == canonicalize_company("OReilly Co")


def test_canonicalize_company_handles_none():
    assert canonicalize_company(None) == ""


def test_canonicalize_title_normalizes_case_and_punctuation():
    assert canonicalize_title("Business Analyst - Mid Level!") == canonicalize_title(
        "business analyst mid level"
    )


def test_location_bucket_groups_by_city_token():
    assert location_bucket("Sandton, Johannesburg") == "sandton"
    assert location_bucket("Johannesburg, Gauteng") == "johannesburg"


def test_location_bucket_handles_none():
    assert location_bucket(None) == ""


def test_same_company_different_legal_suffix_dedupes_to_same_key():
    # This is the actual scenario the canonicalization exists to solve:
    # a job board lists "FNB Pty Ltd", the company's own career page says
    # just "FNB" — both must canonicalize identically.
    assert canonicalize_company("FNB Pty Ltd") == canonicalize_company("FNB")
