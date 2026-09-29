from types import SimpleNamespace as NS

from app.modules.job_discovery.search_helpers import (
    JobRow,
    clean_title,
    collapse_duplicates,
    group_key,
    keyword_suggestions,
    location_matches,
    location_suggestions,
    location_terms,
)

ROWS = [
    JobRow("Business Analyst", "Absa", "Sandton, Johannesburg", False, "business analyst sql stakeholder"),
    JobRow("Business Analyst (Contract)", "FNB", "Johannesburg, Gauteng", False, "business analyst"),
    JobRow("Senior Business Analyst", "DLK Group", "Milnerton, Cape Town City Centre", False, "senior business analyst"),
    JobRow("Senior Business Analyst", "DLK Group", "Kloof Street, Cape Town City Centre", False, "senior business analyst"),
    JobRow("Business Intelligence Developer", "Takealot", "Cape Town, Western Cape", False, "power bi sql"),
    JobRow("Data Analyst", "Remote Co", "Anywhere in the World", True, "data analyst sql"),
    JobRow("Systems Analyst", "Nedbank", "Centurion", False, "systems analyst"),
]


def test_province_expands_to_its_cities_and_suburbs():
    terms, remote = location_terms("gauteng")
    assert not remote
    for place in ("Gauteng", "Johannesburg", "Sandton", "Pretoria", "Centurion"):
        assert place in terms
    assert location_matches("Sandton, Johannesburg", False, terms, remote)
    assert not location_matches("Cape Town", False, terms, remote)


def test_city_includes_suburbs_and_country_includes_everything():
    terms, _ = location_terms("Cape Town")
    assert location_matches("Milnerton, Cape Town City Centre", False, terms, False)
    assert location_matches("Bellville", False, terms, False)
    terms, _ = location_terms("South Africa")
    assert location_matches("Durban, KwaZulu-Natal", False, terms, False)
    assert not location_matches("Anywhere in the World", True, terms, False)


def test_remote_location_uses_the_remote_flag():
    terms, remote = location_terms("Remote")
    assert remote and location_matches("Anywhere in the World", True, terms, remote)


def test_unknown_place_is_searched_as_typed():
    assert location_terms("Kloof Street") == (["Kloof Street"], False)


def test_keyword_suggestions_from_a_few_letters():
    out = keyword_suggestions("bus ana", ROWS, ["SQL"])
    values = [s.value for s in out]
    assert values[0] == "Business Analyst"
    assert out[0].count == 2  # "(Contract)" is cleaned into the same title
    assert "Senior Business Analyst" in values
    assert "Business Intelligence Developer" not in values


def test_keyword_suggestions_include_companies_and_skills():
    out = keyword_suggestions("sq", ROWS, ["SQL", "Power BI"])
    assert ("SQL", "Skill", 3) in [(s.value, s.kind, s.count) for s in out]
    out = keyword_suggestions("dlk", ROWS, [])
    assert out[0].kind == "Company" and out[0].count == 2


def test_location_suggestions_show_province_city_and_counts():
    out = location_suggestions("gau", ROWS)
    assert out[0].value == "Gauteng" and out[0].kind == "Province" and out[0].count == 3
    out = location_suggestions("cape", ROWS)
    kinds = {s.value: (s.kind, s.count) for s in out}
    assert kinds["Cape Town"] == ("City", 3)
    assert kinds["Western Cape"] == ("Province", 3)
    assert "Eastern Cape" not in kinds  # no jobs there, so not offered
    assert location_suggestions("sou", ROWS)[0].value == "South Africa"
    assert location_suggestions("kzn", [JobRow("x", "y", "Durban", False)])[0].value == "KwaZulu-Natal"


def test_clean_title():
    assert clean_title("Business Analyst (Contract) - Sandton") == "Business Analyst"
    assert clean_title("Analyst") == "Analyst"


def test_collapse_duplicates_keeps_first_and_lists_other_locations():
    items = [NS(title=r.title, company=r.company, location=r.location) for r in ROWS]
    groups = collapse_duplicates(items, key=lambda r: group_key(r.title, r.company), location=lambda r: r.location)
    assert len(groups) == len(ROWS) - 1
    dlk = next(g for g in groups if g.first.company == "DLK Group")
    assert dlk.first.location.startswith("Milnerton")
    assert dlk.other_locations == ["Kloof Street, Cape Town City Centre"]


def test_collapse_keeps_jobs_without_company_separate():
    items = [NS(title="Analyst", company=None, location="A"), NS(title="Analyst", company=None, location="B")]
    assert len(collapse_duplicates(items, key=lambda r: group_key(r.title, r.company), location=lambda r: r.location)) == 2


def test_different_roles_at_one_company_are_not_merged():
    items = [NS(title="Business Analyst - Credit", company="Absa", location="Sandton"),
             NS(title="Business Analyst - Payments", company="Absa", location="Rosebank")]
    assert len(collapse_duplicates(items, key=lambda r: group_key(r.title, r.company), location=lambda r: r.location)) == 2


def test_areas_from_ads_come_after_known_places():
    out = location_suggestions("cape", ROWS)
    kinds = [s.kind for s in out]
    assert kinds.index("Area") > kinds.index("Province")
