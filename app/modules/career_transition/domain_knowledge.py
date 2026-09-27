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
TARGET_DOMAINS = ("business_analysis", "systems_analysis", "data_analysis", "it_management", "project_management")

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
}
