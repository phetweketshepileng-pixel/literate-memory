import asyncio

from app.modules.job_discovery.adapters.ats_board_adapter import AtsBoardAdapter, _plain
from app.modules.job_discovery.adapters.base import RawListing

GH = {"id": 7800988003, "title": "Enterprise Solutions Lead ", "company_name": "Ozow",
      "absolute_url": "https://job-boards.greenhouse.io/ozow/jobs/7800988003", "location": {"name": "Cape Town"},
      "first_published": "2026-07-10T11:01:00-04:00", "updated_at": "2026-08-17T05:55:35-04:00",
      "content": "&lt;p&gt;&lt;strong&gt;Meet Ozow&lt;/strong&gt;&lt;/p&gt;&lt;p&gt;Payments &amp;amp; more&lt;/p&gt;",
      "offices": [{"name": "Cape Town, Foreshore"}]}
GH_ABROAD = {**GH, "id": 1, "location": {"name": "London"}, "offices": [{"name": "London"}]}
LV = {"id": "a1f8", "text": "Customer Success Consultant (CPT)", "country": "ZA", "workplaceType": "onsite",
      "categories": {"location": "Cape Town, ZA", "allLocations": ["Cape Town, ZA"]}, "createdAt": 1748511424400,
      "descriptionPlain": "Who we are", "lists": [{"text": "You will:", "content": "<li>Help customers</li>"}],
      "hostedUrl": "https://jobs.lever.co/mamamoney/a1f8"}
SR = {"id": "744000152387879", "name": "Specialist: Ethics & Conduct Risk", "releasedDate": "2026-09-29T11:09:03.468Z",
      "company": {"name": "Standard Bank Group"}, "location": {"city": "Johannesburg", "region": "GP", "country": "za",
      "remote": False, "fullLocation": "Johannesburg, GP, South Africa"},
      "function": {"label": "Other"}, "experienceLevel": {"label": "Mid-Senior Level"}, "typeOfEmployment": {"label": "Full-time"}}
WK = {"shortcode": "659548114E", "title": "R&D Software Engineer", "city": "Cape Town", "state": "Western Cape",
      "country": "South Africa", "url": "https://apply.workable.com/j/659548114E", "published_on": "2026-06-02",
      "telecommuting": False, "description": "<p><strong>We Are Innovators</strong></p>"}


def adapter(platform, board="b", **cfg):
    return AtsBoardAdapter("src", {"platform": platform, "board": board, "company": "Cfg Co", **cfg})


def fetched(a, items):
    async def fake(client):
        return items
    a._fetch = fake
    return asyncio.run(a.fetch_listings(None))


def test_greenhouse_keeps_sa_roles_and_normalizes():
    a = adapter("greenhouse", "ozow", industry="Banking & financial services")
    raws = fetched(a, [GH, GH_ABROAD])
    assert [r.external_id for r in raws] == ["7800988003"]
    j = a.normalize(raws[0])
    assert j.title == "Enterprise Solutions Lead" and j.company == "Ozow" and j.location == "Cape Town"
    assert "Meet Ozow" in j.description and "<" not in j.description and "&amp;" not in j.description
    assert str(j.date_posted) == "2026-07-10"
    assert j.is_syndicated is False and j.industry == "Banking & financial services"


def test_sa_only_can_be_switched_off():
    assert len(fetched(adapter("greenhouse", sa_only=False), [GH, GH_ABROAD])) == 2


def test_lever():
    a = adapter("lever", "mamamoney")
    j = a.normalize(fetched(a, [LV])[0])
    assert j.title.startswith("Customer Success") and j.location == "Cape Town, ZA" and j.company == "Cfg Co"
    assert "Help customers" in j.description and j.apply_url.endswith("/a1f8") and str(j.date_posted) == "2025-05-29"


def test_smartrecruiters():
    a = adapter("smartrecruiters", "StandardBankGroup")
    j = a.normalize(fetched(a, [SR])[0])
    assert j.company == "Standard Bank Group" and j.location == "Johannesburg, Gauteng"
    assert j.apply_url == "https://jobs.smartrecruiters.com/StandardBankGroup/744000152387879"
    assert "Mid-Senior Level" in j.description and "Other" not in j.description


def test_workable():
    a = adapter("workable", "clickatell")
    j = a.normalize(fetched(a, [WK])[0])
    assert j.external_id == "659548114E" and j.location == "Cape Town, Western Cape"
    assert j.description == "We Are Innovators" and str(j.date_posted) == "2026-06-02"


def test_plain_text():
    assert _plain("&lt;p&gt;a&lt;/p&gt;&lt;p&gt;b&lt;/p&gt;") == "a\nb"
