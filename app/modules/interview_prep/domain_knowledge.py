"""Curated question banks for Interview Preparation. Reuses Career
Transition's target-domain competency vocabulary (domain_knowledge.py in
that module) so behavioral questions can be selected by competency and
paired with the user's own reframed experience where a transferable
mapping exists — the same "curated data, not per-user AI call" pattern
used throughout the platform."""
from __future__ import annotations

DIFFICULTIES = ("junior", "mid", "senior")

# Technical/domain-knowledge questions per target domain, by difficulty.
TECHNICAL_QUESTION_BANK: dict[str, dict[str, list[str]]] = {
    "business_analysis": {
        "junior": [
            "What's the difference between a business requirement and a functional requirement?",
            "How would you document a simple 'as-is' process?",
        ],
        "mid": [
            "Walk me through how you'd run a gap analysis between current and desired state.",
            "How do you prioritize conflicting requirements from different stakeholders?",
        ],
        "senior": [
            "How would you structure a BRD for a multi-system integration project?",
            "Describe how you'd lead requirements gathering across a resistant business unit.",
        ],
    },
    "systems_analysis": {
        "junior": [
            "What's the difference between a use case and a user story?",
            "How would you document a simple system workflow?",
        ],
        "mid": [
            "How do you approach specifying integration requirements between two systems?",
            "Walk me through the SDLC stages and your role at each.",
        ],
        "senior": [
            "How would you evaluate whether a proposed system change introduces integration risk?",
            "Describe leading technical requirements gathering for a legacy system replacement.",
        ],
    },
    "data_analysis": {
        "junior": [
            "Write a SQL query to find duplicate records in a table.",
            "How would you handle missing values in a dataset before analysis?",
        ],
        "mid": [
            "How would you design a dashboard to track a KPI you've never worked with before?",
            "Explain the difference between a JOIN and a UNION and when you'd use each.",
        ],
        "senior": [
            "How would you validate that a dashboard's numbers match the underlying source system?",
            "Describe how you'd design a reporting layer that scales as data volume grows.",
        ],
    },
    "it_management": {
        "junior": [
            "What's the difference between an incident and a problem in ITIL terms?",
            "How would you track a vendor's SLA compliance?",
        ],
        "mid": [
            "How do you balance a fixed budget against a growing backlog of team requests?",
            "Describe how you'd manage a vendor that's consistently missing SLA targets.",
        ],
        "senior": [
            "How would you build a technology roadmap that balances short-term fixes and long-term investment?",
            "Describe leading a team through a major incident with executive visibility.",
        ],
    },
    "project_management": {
        "junior": [
            "What's the difference between a risk and an issue?",
            "How would you track progress against a project plan?",
        ],
        "mid": [
            "How do you handle scope creep on a fixed-budget project?",
            "Walk me through how you'd run a project kickoff with a new stakeholder group.",
        ],
        "senior": [
            "How would you recover a project that's significantly behind schedule and over budget?",
            "Describe managing a portfolio of projects with competing resource demands.",
        ],
    },
}

# Behavioral questions keyed by TARGET COMPETENCY (same vocabulary as
# Career Transition's transferable_skill_mappings target_competency field)
# — this is the join point that lets a question be paired with the user's
# own reframed experience for that competency.
BEHAVIORAL_QUESTION_BANK: dict[str, list[str]] = {
    "stakeholder management": [
        "Tell me about a time you managed conflicting priorities between two stakeholders.",
        "Describe a situation where you had to deliver difficult news to a stakeholder.",
    ],
    "requirements gathering": [
        "Tell me about a time you had to clarify a vague or ambiguous request.",
        "Describe a time your understanding of a requirement changed significantly partway through.",
    ],
    "brd/frs documentation": [
        "Tell me about a time your documentation prevented a misunderstanding down the line.",
        "Describe how you've adapted your documentation style for different audiences.",
    ],
    "process mapping (bpmn)": [
        "Tell me about a time you identified and fixed an inefficient process.",
        "Describe mapping a process that no one had documented before.",
    ],
    "vendor leadership": [
        "Tell me about a time you managed an underperforming vendor.",
        "Describe negotiating a difficult vendor contract or SLA.",
    ],
    "risk management": [
        "Tell me about a time you identified a risk before it became a problem.",
        "Describe a time you had to escalate a compliance or risk concern.",
    ],
    "resource management": [
        "Tell me about a time you had to do more with fewer resources than you needed.",
        "Describe reallocating resources midway through a plan.",
    ],
    "reporting automation": [
        "Tell me about a time you automated a manual reporting process.",
        "Describe a time a report you built changed a business decision.",
    ],
    "system/process mapping": [
        "Tell me about a time working with a system helped you understand a business process better.",
        "Describe troubleshooting an issue that spanned multiple systems.",
    ],
}

GENERIC_BEHAVIORAL_QUESTIONS: list[str] = [
    "Tell me about a time you had to learn something completely new quickly.",
    "Describe a mistake you made and what you learned from it.",
    "Tell me about a time you disagreed with a decision and how you handled it.",
]
