"""Gives every job a plain-language industry for the Job Search filter.

Order of evidence, strongest first:
  1. the source says so (an employer's own careers board is configured
     with its industry, e.g. Standard Bank -> Banking)
  2. the employer is a well-known South African company in that industry
  3. the job title names it ("Relationship Banker", "Telematics Technician")
  4. the job board's own category (Adzuna's "Accounting & Finance Jobs")
Anything left is "Other".
"""
from __future__ import annotations

import re

BANKING = "Banking & financial services"
INSURANCE = "Insurance"
TELEMATICS = "Telematics & fleet"
GOVERNMENT = "Government & public sector"
CONTACT_CENTRE = "Contact centre & collections"
IT = "IT & technology"
FINANCE = "Accounting & finance"

_COMPANIES: list[tuple[str, str]] = [
    (GOVERNMENT, r"^department of|\bdepartment of\b|municipality|metropolitan municipality|city of (johannesburg|cape town|tshwane|ekurhuleni)"
                 r"|provincial government|national treasury|\bsars\b|revenue service|\bsaps\b|police service|\bsandf\b"
                 r"|\bsassa\b|public service|\bdpsa\b|statistics south africa|stats ?sa|\bcsir\b|\bnhls\b|eskom|transnet"
                 r"|prasa|sanral|\bsaa\b|denel|\bsabc\b|\bnsfas\b|\bseta\b|auditor.general|\bagsa\b|public protector"),
    (BANKING, r"absa|standard bank|stanbic|first ?rand|\bfnb\b|first national bank|\brmb\b|rand merchant|nedbank|capitec"
              r"|investec|african bank|tyme ?bank|discovery bank|bidvest bank|sasfin|mercantile bank|grindrod bank"
              r"|access bank|bank ?zero|ubank|postbank|land bank|\bdbsa\b|development bank|reserve bank|\bsarb\b"
              r"|experian|transunion|\bxds\b|compuscan|bankserv|payinc|ikhokha|ozow|yoco|peach payments|mama ?money"
              r"|lulalend|retail capital|merchant capital|luno|valr|entersekt|adumo|lesaka|net1|mukuru|dlocal|payu"),
    (INSURANCE, r"old mutual|sanlam|momentum|metropolitan|liberty|discovery|hollard|outsurance|santam|king ?price"
                r"|pineapple|naked insurance|miway|auto ?general|budget insurance|dial ?direct|telesure|1life|clientele"
                r"|assupol|bryte|mutual ?& ?federal|guardrisk|avbob|\bpps\b|bestmed|medshield|bonitas|fedhealth"),
    (TELEMATICS, r"cartrack|karooooo|mix telematics|\bmix\b.*telematics|netstar|tracker connect|\btracker\b|ctrack"
                 r"|inseego|webfleet|geotab|samsara|matrix vehicle|fleetwatch|trackmatic|bidtrack|beame"),
    (CONTACT_CENTRE, r"\bwns\b|sutherland|teleperformance|concentrix|webhelp|majorel|merchants|\bison\b|\bcci\b"
                     r"|taskus|startek|ttec|conduent|\bibex\b|nexus outsourcing"),
]
_COMPANY_PATTERNS = [(ind, re.compile(p, re.IGNORECASE)) for ind, p in _COMPANIES]

_TITLES: list[tuple[str, str]] = [
    (TELEMATICS, r"telematics|fleet (tracking|management|controller)|vehicle tracking|tracking (technician|controller)"),
    (GOVERNMENT, r"municipal|government|public (service|sector)|\bdepartment of\b"),
    (CONTACT_CENTRE, r"call cent|contact cent|collections? (agent|consultant|officer|specialist|team leader|manager|supervisor)"
                     r"|debt (collect|recover)|customer service (agent|consultant|representative)|(inbound|outbound) (sales|agent|consultant)"),
    (INSURANCE, r"insurance|underwrit|claims (assessor|handler|consultant)|actuar|broker consultant"),
    (BANKING, r"\bbank(er|ing)?\b|credit (analyst|risk|controller)|relationship manager|wealth|lending|\bloans?\b|fraud"),
]
_TITLE_PATTERNS = [(ind, re.compile(p, re.IGNORECASE)) for ind, p in _TITLES]

# Adzuna category labels -> the names used in the app
_CATEGORY_NAMES = {
    "accounting & finance": FINANCE,
    "it": IT,
    "customer services": "Customer service",
    "admin": "Admin & office support",
    "hr & recruitment": "HR & recruitment",
    "legal": "Legal",
    "sales": "Sales",
    "pr, advertising & marketing": "Marketing & PR",
    "engineering": "Engineering",
    "healthcare & nursing": "Healthcare",
    "teaching": "Education",
    "logistics & warehouse": "Logistics & supply chain",
    "retail": "Retail",
    "hospitality & catering": "Hospitality",
    "trade & construction": "Construction & trades",
    "manufacturing": "Manufacturing",
    "consultancy": "Consulting",
    "scientific & qa": "Science & QA",
    "energy, oil & gas": "Energy & mining",
    "property": "Property",
    "social work": "Social work & NGO",
    "charity & voluntary": "Social work & NGO",
    "creative & design": "Creative & design",
    "travel": "Travel & tourism",
    "graduate": "Graduate & entry level",
    "maintenance": "Maintenance",
    "domestic help & cleaning": "Domestic & cleaning",
    "security & safety": "Security & safety",
    "part time": "Other",
    "other/general": "Other",
}


def category_name(label: str | None) -> str | None:
    """'Accounting & Finance Jobs' -> 'Accounting & finance'."""
    if not label:
        return None
    key = re.sub(r"\s+jobs?$", "", label.strip(), flags=re.IGNORECASE).lower()
    if key == "unknown":
        return None
    return _CATEGORY_NAMES.get(key) or key[:1].upper() + key[1:]


def classify_industry(
    title: str | None,
    company: str | None,
    board_category: str | None = None,
    source_industry: str | None = None,
) -> str:
    if source_industry:
        return source_industry
    for industry, pattern in _COMPANY_PATTERNS:
        if company and pattern.search(company):
            return industry
    for industry, pattern in _TITLE_PATTERNS:
        if title and pattern.search(title):
            return industry
    return category_name(board_category) or "Other"


def industry_from_payload(payload: dict | None) -> str | None:
    """Adzuna stores {'category': {'label': 'IT Jobs', 'tag': 'it-jobs'}}."""
    cat = (payload or {}).get("category")
    if isinstance(cat, dict):
        return cat.get("label")
    return None
