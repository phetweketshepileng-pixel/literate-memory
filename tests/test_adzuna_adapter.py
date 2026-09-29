from datetime import date

from app.modules.job_discovery.adapters.adzuna_adapter import AdzunaAdapter
from app.modules.job_discovery.adapters.base import RawListing

SAMPLE = {
    "id": "4812345678",
    "title": "<strong>Business Analyst</strong> - Banking",
    "company": {"display_name": "Nedbank"},
    "location": {"display_name": "Sandton, Johannesburg", "area": ["South Africa", "Gauteng", "Johannesburg"]},
    "description": "Gather requirements &amp; manage <b>stakeholders</b>. Hybrid, remote Fridays.",
    "redirect_url": "https://www.adzuna.co.za/details/4812345678",
    "created": "2026-09-25T08:15:00Z",
    "salary_min": 550000.0,
    "salary_max": 650000.0,
    "salary_is_predicted": "0",
}


def _norm(payload):
    return AdzunaAdapter("src", {"what": "business analyst"}).normalize(RawListing(payload["id"], payload))


def test_normalize_maps_fields():
    job = _norm(SAMPLE)
    assert job.title == "Business Analyst - Banking"
    assert job.company == "Nedbank"
    assert job.location == "Sandton, Johannesburg"
    assert job.salary_min == 550000 and job.salary_max == 650000
    assert job.date_posted == date(2026, 9, 25)
    assert "&amp;" not in job.description and "<b>" not in job.description
    assert job.apply_url.startswith("https://www.adzuna.co.za/")
    assert job.is_syndicated is True
    assert job.is_remote is True  # "remote Fridays" mentioned


def test_predicted_salary_is_dropped():
    job = _norm({**SAMPLE, "salary_is_predicted": "1"})
    assert job.salary_min is None and job.salary_max is None


def test_missing_fields_are_tolerated():
    job = _norm({"id": "1", "title": "Systems Analyst"})
    assert job.company is None and job.location is None and job.date_posted is None and job.salary_min is None
    assert job.is_remote is False
