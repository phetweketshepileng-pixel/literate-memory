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

# Growing within the same line of work.
TECHNICAL_QUESTION_BANK.update({
    "current_field": {
        "junior": [
            "What does a strong week look like in your current team, and how do you measure it?",
            "Which part of your current job would you most like to take more responsibility for, and why?",
        ],
        "mid": [
            "How would you take over an under-performing team and turn it around in 90 days?",
            "Which three measures would you report to your manager every week, and why those?",
        ],
        "senior": [
            "How would you set targets for several team leaders whose teams handle different kinds of work?",
            "Describe how you'd build a business case for more staff or a new system in your area.",
        ],
    },
    "collections_management": {
        "junior": [
            "What is a promise-to-pay, and how would you improve a team's kept-promise rate?",
            "How do you decide which accounts to call first on a given day?",
        ],
        "mid": [
            "How would you design a collection strategy for early arrears versus accounts 90+ days down?",
            "What do roll rates tell you, and what would you do if your 30-to-60 roll rate jumped?",
            "How does the National Credit Act shape what a collections team may and may not do?",
        ],
        "senior": [
            "How would you decide between collecting in-house, using an agency, or selling a debt book?",
            "How would you set up champion/challenger testing for a collections strategy?",
            "Walk me through how you'd forecast monthly recoveries and resource the team to hit them.",
        ],
    },
    "credit_risk": {
        "junior": [
            "What is the difference between a probability of default and a loss given default?",
            "Which information would you look at before approving a personal loan?",
        ],
        "mid": [
            "How would you monitor whether a credit portfolio is getting riskier?",
            "What is a vintage analysis, and what can it show that a monthly arrears report can't?",
        ],
        "senior": [
            "How would you change credit policy if early-arrears rates on new business doubled?",
            "How do collections results feed back into credit scoring and approval rules?",
        ],
    },
    "operations_management": {
        "junior": [
            "What is a service level, and how would you know if your team is meeting it?",
            "How would you handle a day when half the team is absent?",
        ],
        "mid": [
            "How do you find the biggest bottleneck in a process you've just inherited?",
            "How would you balance productivity targets with quality and staff wellbeing?",
        ],
        "senior": [
            "How would you plan staffing for next year's demand with a fixed budget?",
            "Describe how you'd run a process-improvement programme across several teams.",
        ],
    },
    "customer_experience": {
        "junior": [
            "What is the difference between CSAT, NPS and first-contact resolution?",
            "How would you handle a customer who is angry about something your team didn't cause?",
        ],
        "mid": [
            "How would you use complaint data to decide what to fix first?",
            "How would you map a customer journey to find the points that cause most complaints?",
        ],
        "senior": [
            "How would you build a business case for a customer-experience improvement?",
            "How do you balance cost-cutting targets with keeping customers satisfied?",
        ],
    },
})

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

BEHAVIORAL_QUESTION_BANK.update({
    "people leadership": [
        "Tell me about a time you turned around a team member's poor performance.",
        "Describe how you kept a team motivated through a difficult month.",
    ],
    "performance management": [
        "Tell me about a time your team was off target mid-month. What did you change?",
        "Describe a measure you introduced that changed how your team worked.",
    ],
    "portfolio strategy": [
        "Tell me about a time you changed how accounts were prioritised, and what happened.",
        "Describe how you used data to decide where your team should focus.",
    ],
    "regulatory compliance": [
        "Tell me about a time you stopped something that would have broken a rule or regulation.",
        "Describe how you made sure your team followed a new policy or law.",
    ],
    "credit risk analysis": [
        "Tell me about a time you spotted a worrying trend in a portfolio early.",
        "Describe a decision you made where the numbers and your instinct disagreed.",
    ],
    "process improvement": [
        "Tell me about a process you improved and how you measured the result.",
        "Describe a change you made that people resisted at first.",
    ],
    "customer experience improvement": [
        "Tell me about a recurring customer complaint you got to the root of.",
        "Describe a time you changed a process because of customer feedback.",
    ],
})

GENERIC_BEHAVIORAL_QUESTIONS: list[str] = [
    "Tell me about a time you had to learn something completely new quickly.",
    "Describe a mistake you made and what you learned from it.",
    "Tell me about a time you disagreed with a decision and how you handled it.",
]
