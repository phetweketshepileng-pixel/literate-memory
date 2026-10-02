"""Curated domain knowledge for the Career Transition Intelligence Engine.
See ai-job-hunter-career-transition-engine.md sections 2-2.4. This is
DATA, not logic — reviewable/correctable by a subject-matter admin,
seeded once into transition_pathways / transferable_skill_mappings and
editable there without a code deploy. The module-level constants here are
the seed values and the fallback if the DB tables are empty.
"""
from __future__ import annotations

from dataclasses import dataclass

SOURCE_DOMAINS = ("collections", "operations", "banking", "call_centre")
# Keys are stored in String(30) columns, so keep them <= 30 characters.
TARGET_DOMAINS = (
    # growing within the same line of work
    "current_field", "collections_management", "credit_risk", "operations_management", "customer_experience",
    # moving into analysis / IT / projects
    "business_analysis", "systems_analysis", "data_analysis", "it_management", "project_management",
)

# How domains are shown in the app.
DOMAIN_LABELS: dict[str, str] = {
    "collections": "Collections", "operations": "Operations", "banking": "Banking", "call_centre": "Call Centre",
    "current_field": "Grow in my current field",
    "collections_management": "Collections & Recovery Management",
    "credit_risk": "Credit Risk",
    "operations_management": "Operations Management",
    "customer_experience": "Customer Experience Management",
    "business_analysis": "Business Analysis", "systems_analysis": "Systems Analysis",
    "data_analysis": "Data Analysis", "it_management": "IT Management", "project_management": "Project Management",
}

# Section 2.4 — base transfer-affinity matrix (0-100), curated starting
# estimates reflecting genuine domain overlap before any individual's
# actual skills are factored in.
BASE_AFFINITY_MATRIX: dict[tuple[str, str], int] = {
    ("collections", "business_analysis"): 65,
    ("collections", "systems_analysis"): 40,
    ("collections", "data_analysis"): 35,
    ("collections", "it_management"): 45,
    ("collections", "project_management"): 50,
    ("operations", "business_analysis"): 60,
    ("operations", "systems_analysis"): 45,
    ("operations", "data_analysis"): 30,
    ("operations", "it_management"): 70,
    ("operations", "project_management"): 65,
    ("banking", "business_analysis"): 55,
    ("banking", "systems_analysis"): 40,
    ("banking", "data_analysis"): 45,
    ("banking", "it_management"): 50,
    ("banking", "project_management"): 45,
    ("call_centre", "business_analysis"): 55,
    ("call_centre", "systems_analysis"): 30,
    ("call_centre", "data_analysis"): 25,
    ("call_centre", "it_management"): 40,
    ("call_centre", "project_management"): 45,
    # staying in (and moving up within) the same kind of work
    ("collections", "current_field"): 85, ("operations", "current_field"): 85,
    ("banking", "current_field"): 85, ("call_centre", "current_field"): 85,
    ("collections", "collections_management"): 85,
    ("collections", "credit_risk"): 70,
    ("collections", "operations_management"): 65,
    ("collections", "customer_experience"): 60,
    ("operations", "collections_management"): 50,
    ("operations", "credit_risk"): 40,
    ("operations", "operations_management"): 85,
    ("operations", "customer_experience"): 60,
    ("banking", "collections_management"): 65,
    ("banking", "credit_risk"): 75,
    ("banking", "operations_management"): 60,
    ("banking", "customer_experience"): 55,
    ("call_centre", "collections_management"): 65,
    ("call_centre", "credit_risk"): 35,
    ("call_centre", "operations_management"): 60,
    ("call_centre", "customer_experience"): 80,
}


@dataclass(frozen=True)
class TransferableSkillMapping:
    source_domain: str
    source_competency: str
    target_domain: str
    target_competency: str
    transfer_strength: str  # 'direct' | 'strong' | 'partial'
    reframing_template: str


TRANSFER_STRENGTH_WEIGHTS = {"direct": 1.0, "strong": 0.8, "partial": 0.4}

# Section 2.3 — curated transferable skill mappings. Grows over time as
# data, never as a code change.
TRANSFERABLE_SKILL_MAPPINGS: list[TransferableSkillMapping] = [
    TransferableSkillMapping(
        "collections", "escalation handling", "business_analysis", "stakeholder management",
        "strong", "Managed escalated stakeholder concerns, negotiating resolutions — directly applicable to BA stakeholder engagement",
    ),
    TransferableSkillMapping(
        "collections", "kpi/target management", "business_analysis", "requirements gathering",
        "partial", "Consistently translated business targets into actionable team objectives",
    ),
    TransferableSkillMapping(
        "collections", "dispute resolution", "business_analysis", "stakeholder management",
        "strong", "Resolved disputes through structured negotiation and clear communication",
    ),
    TransferableSkillMapping(
        "collections", "crm & dialer systems", "systems_analysis", "system/process mapping",
        "partial", "Operated and reported from CRM/dialer platforms, developing working knowledge of system-driven workflows",
    ),
    TransferableSkillMapping(
        "collections", "portfolio & risk reporting", "data_analysis", "reporting automation",
        "partial", "Produced regular portfolio and risk reports from structured data sources",
    ),
    TransferableSkillMapping(
        "operations", "process documentation (sops)", "business_analysis", "brd/frs documentation",
        "strong", "Authored and maintained process documentation used across cross-functional teams",
    ),
    TransferableSkillMapping(
        "operations", "vendor/sla management", "it_management", "vendor leadership",
        "direct", "Managed vendor relationships against SLA commitments",
    ),
    TransferableSkillMapping(
        "operations", "workflow optimization", "business_analysis", "process mapping (bpmn)",
        "strong", "Redesigned operational workflows to remove bottlenecks and improve throughput",
    ),
    TransferableSkillMapping(
        "operations", "capacity planning", "project_management", "resource management",
        "strong", "Planned resource capacity against forecasted operational demand",
    ),
    TransferableSkillMapping(
        "operations", "incident management", "it_management", "risk management",
        "strong", "Led incident response and resolution processes to minimize business impact",
    ),
    TransferableSkillMapping(
        "banking", "regulatory/compliance adherence", "project_management", "risk management",
        "strong", "Ensured adherence to regulatory frameworks, identifying and escalating compliance risk",
    ),
    TransferableSkillMapping(
        "banking", "risk assessment", "it_management", "risk management",
        "strong", "Assessed and documented operational risk exposure across processes",
    ),
    TransferableSkillMapping(
        "banking", "financial/audit reporting", "data_analysis", "reporting automation",
        "partial", "Prepared structured financial and audit reports from source data",
    ),
    TransferableSkillMapping(
        "call_centre", "workforce scheduling", "project_management", "resource management",
        "partial", "Planned and adjusted staffing resources against demand forecasts",
    ),
    TransferableSkillMapping(
        "call_centre", "crm/ticketing systems", "systems_analysis", "system/process mapping",
        "partial", "Operated ticketing/CRM systems, developing familiarity with system-driven case workflows",
    ),
    TransferableSkillMapping(
        "call_centre", "metrics-driven performance", "data_analysis", "reporting automation",
        "partial", "Tracked and reported against operational performance metrics (AHT/CSAT/FCR)",
    ),
    TransferableSkillMapping(
        "call_centre", "escalation management", "business_analysis", "stakeholder management",
        "strong", "Managed escalated customer concerns through structured resolution processes",
    ),
]

# ---- growing within the same line of work -------------------------------
_M = TransferableSkillMapping
TRANSFERABLE_SKILL_MAPPINGS += [
    # collections -> collections & recovery management
    _M("collections", "team leadership", "collections_management", "people leadership", "direct",
       "Led a collections team day to day: coaching, call quality and motivation against monthly targets"),
    _M("collections", "kpi/target management", "collections_management", "performance management", "direct",
       "Set and tracked team targets (PTP, kept-promise rate, roll rates), acting early on under-performance"),
    _M("collections", "portfolio & risk reporting", "collections_management", "portfolio strategy", "strong",
       "Analysed portfolio and arrears reports to prioritise accounts and shape collection strategies"),
    _M("collections", "dispute resolution", "collections_management", "regulatory compliance", "strong",
       "Resolved customer disputes within NCA, POPIA and treating-customers-fairly requirements"),
    # collections -> credit risk
    _M("collections", "portfolio & risk reporting", "credit_risk", "credit risk analysis", "strong",
       "Tracked arrears, roll rates and recoveries — the same signals credit risk teams model"),
    _M("collections", "kpi/target management", "credit_risk", "performance management", "partial",
       "Monitored portfolio performance indicators against targets and escalated deteriorating trends"),
    _M("collections", "dispute resolution", "credit_risk", "regulatory compliance", "partial",
       "Applied credit legislation and internal policy when resolving account disputes"),
    # collections -> operations / customer experience
    _M("collections", "team leadership", "operations_management", "people leadership", "strong",
       "Ran a high-volume operational team, balancing staffing, quality and output"),
    _M("collections", "kpi/target management", "operations_management", "performance management", "strong",
       "Managed daily operational KPIs and adjusted team focus to hit them"),
    _M("collections", "escalation handling", "customer_experience", "customer experience improvement", "strong",
       "Turned recurring customer escalations into fixes that reduced repeat complaints"),
    # operations
    _M("operations", "workflow optimization", "operations_management", "process improvement", "direct",
       "Redesigned workflows to remove bottlenecks and raise throughput"),
    _M("operations", "capacity planning", "operations_management", "performance management", "strong",
       "Planned capacity against demand and tracked delivery against service levels"),
    _M("operations", "incident management", "customer_experience", "customer experience improvement", "partial",
       "Handled service incidents with a focus on limiting customer impact"),
    # banking
    _M("banking", "risk assessment", "credit_risk", "credit risk analysis", "strong",
       "Assessed risk exposure and documented findings for credit and operational decisions"),
    _M("banking", "regulatory/compliance adherence", "credit_risk", "regulatory compliance", "direct",
       "Applied banking regulation and internal credit policy in day-to-day decisions"),
    _M("banking", "regulatory/compliance adherence", "collections_management", "regulatory compliance", "strong",
       "Kept processes compliant with banking and consumer-credit regulation"),
    # call centre
    _M("call_centre", "metrics-driven performance", "customer_experience", "customer experience improvement", "strong",
       "Used CSAT, FCR and AHT data to find and fix the causes of poor customer experiences"),
    _M("call_centre", "workforce scheduling", "operations_management", "performance management", "strong",
       "Matched staffing to demand forecasts to protect service levels"),
    _M("call_centre", "escalation management", "collections_management", "people leadership", "partial",
       "Coached agents through difficult customer conversations and escalations"),
]

# "Grow in my current field": every source competency counts toward the
# leadership competencies needed to move up in the same line of work.
_CURRENT_FIELD_TARGETS = {"team leadership": "people leadership", "kpi/target management": "performance management",
                          "workflow optimization": "process improvement", "metrics-driven performance": "performance management",
                          "workforce scheduling": "performance management", "capacity planning": "performance management",
                          "regulatory/compliance adherence": "regulatory compliance", "risk assessment": "regulatory compliance",
                          "escalation handling": "people leadership", "escalation management": "people leadership"}
for _src in SOURCE_DOMAINS:
    _seen = set()
    for _m in [m for m in TRANSFERABLE_SKILL_MAPPINGS if m.source_domain == _src]:
        _target = _CURRENT_FIELD_TARGETS.get(_m.source_competency)
        if _target and _m.source_competency not in _seen:
            _seen.add(_m.source_competency)
            TRANSFERABLE_SKILL_MAPPINGS.append(_M(_src, _m.source_competency, "current_field", _target, "direct",
                                                  _m.reframing_template))


@dataclass(frozen=True)
class PathwayInfo:
    recommended_certifications: tuple[str, ...]
    typical_timeline_months: int


# Section 5 — curated certification recommendations per target domain
# (filtered per-user to what they don't already hold).
TARGET_DOMAIN_CERTIFICATIONS: dict[str, tuple[str, ...]] = {
    "business_analysis": ("BABOK-aligned Business Analysis Foundations", "CBAP (for later career stage)"),
    "systems_analysis": ("Systems Analysis & BPMN Fundamentals", "ITIL Foundation"),
    "data_analysis": ("SQL Fundamentals", "Power BI / Data Visualization Fundamentals"),
    "it_management": ("ITIL Foundation", "COBIT Foundations"),
    "project_management": ("PRINCE2 Foundation", "CAPM"),
    "current_field": ("Management Development Programme (MDP)", "Coaching / people leadership short course"),
    "collections_management": ("Credit management certificate (Institute of Credit Management SA)",
                               "Management Development Programme (MDP)"),
    "credit_risk": ("Credit risk management short course", "SQL Fundamentals", "FRM Part I (for later career stage)"),
    "operations_management": ("Lean Six Sigma Green Belt", "Management Development Programme (MDP)"),
    "customer_experience": ("CCXP (Certified Customer Experience Professional)", "COPC CX Standard training"),
}
