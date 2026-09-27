"""CV text extraction and rule-based skill detection for Module 1.

Deterministic on purpose: extracted skills are saved with source='cv_extracted'
and become grounded facts for CV Tailoring, so they must come from words
actually present in the user's CV — never from a model's guess."""
from __future__ import annotations

import io
import re

# canonical skill name -> phrases that indicate it (matched on word boundaries)
SKILL_VOCABULARY: dict[str, tuple[str, ...]] = {
    "Stakeholder management": ("stakeholder",),
    "Escalation handling": ("escalation", "escalations", "escalated"),
    "Dispute resolution": ("dispute", "disputes"),
    "Negotiation": ("negotiation", "negotiated", "negotiating"),
    "KPI management": ("kpi", "kpis", "key performance indicator"),
    "Reporting": ("reporting", "reports"),
    "Process improvement": ("process improvement", "process optimisation", "process optimization", "streamlined"),
    "Process documentation": ("process documentation", "process mapping", "sop", "sops", "standard operating procedure"),
    "Requirements gathering": ("requirements gathering", "requirements elicitation", "business requirements", "brd", "user stories"),
    "Business analysis": ("business analysis", "business analyst"),
    "Data analysis": ("data analysis", "analysed data", "analyzed data", "data analytics"),
    "Risk management": ("risk management", "risk assessment", "credit risk"),
    "Compliance": ("compliance", "regulatory"),
    "Collections": ("collections", "debt recovery", "arrears"),
    "Team leadership": ("team leader", "team lead", "supervised", "managed a team", "people management"),
    "Coaching": ("coaching", "coached", "mentoring", "mentored"),
    "Workforce management": ("workforce management", "workforce planning", "scheduling"),
    "Vendor management": ("vendor management", "vendors", "service providers"),
    "Budgeting": ("budget", "budgeting", "budgets"),
    "Customer service": ("customer service", "client service", "customer experience"),
    "SLA management": ("sla", "slas", "service level"),
    "Project management": ("project management", "managed projects", "project manager"),
    "Change management": ("change management",),
    "Agile": ("agile",),
    "Scrum": ("scrum",),
    "Jira": ("jira",),
    "Confluence": ("confluence",),
    "SQL": ("sql",),
    "Excel": ("excel", "spreadsheets"),
    "Power BI": ("power bi", "powerbi"),
    "Tableau": ("tableau",),
    "Python": ("python",),
    "CRM systems": ("crm", "salesforce", "dynamics 365"),
    "SAP": ("sap",),
    "BPMN": ("bpmn",),
    "Visio": ("visio",),
    "Dialer systems": ("dialer", "dialler"),
    "Microsoft Office": ("microsoft office", "ms office", "ms word", "microsoft word", "powerpoint"),
}

_PATTERNS = {
    skill: re.compile(r"\b(?:" + "|".join(re.escape(p) for p in phrases) + r")\b", re.IGNORECASE)
    for skill, phrases in SKILL_VOCABULARY.items()
}


class UnreadableDocumentError(Exception):
    """The file's text couldn't be extracted (scanned image PDF, corrupt file...)."""


def extract_text(content: bytes, file_name: str | None, mime_type: str | None) -> str:
    name = (file_name or "").lower()
    mime = (mime_type or "").lower()
    try:
        if name.endswith(".pdf") or "pdf" in mime:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        elif name.endswith(".docx") or "wordprocessingml" in mime:
            from docx import Document as DocxDocument

            doc = DocxDocument(io.BytesIO(content))
            parts = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                for row in table.rows:
                    parts.extend(cell.text for cell in row.cells)
            text = "\n".join(parts)
        elif name.endswith(".txt") or mime.startswith("text/"):
            text = content.decode("utf-8", errors="replace")
        else:
            raise UnreadableDocumentError("Unsupported file type — upload a PDF, Word (.docx) or .txt file.")
    except UnreadableDocumentError:
        raise
    except Exception as exc:  # noqa: BLE001 — any parser failure means "couldn't read it"
        raise UnreadableDocumentError(f"Couldn't read this file: {exc.__class__.__name__}") from exc

    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


def detect_skills(text: str) -> list[str]:
    if not text:
        return []
    return [skill for skill, pattern in _PATTERNS.items() if pattern.search(text)]
