from app.modules.job_discovery.search_plan import FALLBACK_ROLES, PAGE_BUDGET, normalize_role, plan_role_searches


def test_normalize_role():
    assert normalize_role("  Collections Team Manager (JHB) ") == "collections team manager"
    assert normalize_role("Credit Controller role") == "credit controller"
    assert normalize_role("x") is None and normalize_role("") is None and normalize_role(None) is None


def test_most_wanted_roles_first_and_within_budget():
    roles = ["Collections Manager", "collections manager", "Credit Controller", "Team Leader"] + [f"Role {c}aa" for c in "abcdefghijklmn"]
    plan = plan_role_searches(roles)
    assert plan[0] == ("collections manager", None, 2)
    assert len(plan) == 12
    assert sum(p for *_, p in plan) <= PAGE_BUDGET


def test_fallback_when_no_profile_roles():
    assert [w for w, *_ in plan_role_searches([])] == list(FALLBACK_ROLES)


def test_few_roles_get_deeper_searches():
    plan = plan_role_searches(["Collections Manager", "Credit Controller", "Team Leader"])
    assert [p for *_, p in plan] == [4, 4, 4]
    plan = plan_role_searches([f"Role {c}aa" for c in "abcdefg"])
    assert sum(p for *_, p in plan) == PAGE_BUDGET and max(p for *_, p in plan) == 3
