"""First-timer CV builder: the answers people fill in (stored on
profiles.cv_builder) and the one-page-style, ATS-friendly PDF made from them.

Deliberately no AI: free to run, instant, and nothing is invented — the CV
only ever contains what the person typed.
"""
from __future__ import annotations

import io
import re
from datetime import date

from pydantic import BaseModel, Field, field_validator

S = 120     # short field
L = 1200    # long field


def _clean(v):
    return re.sub(r"[ \t]+", " ", v).strip() if isinstance(v, str) else v


class _Model(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def _strip(cls, v):
        return _clean(v)


class Personal(_Model):
    full_name: str = Field("", max_length=S)
    phone: str = Field("", max_length=40)
    email: str = Field("", max_length=S)
    location: str = Field("", max_length=S)
    linkedin: str = Field("", max_length=300)
    drivers_licence: str = Field("", max_length=40)


class Experience(_Model):
    role: str = Field("", max_length=S)
    organisation: str = Field("", max_length=S)
    kind: str = Field("job", pattern="^(job|part-time|volunteer|informal|project|learnership|internship)$")
    location: str = Field("", max_length=S)
    start: str = Field("", max_length=20)
    end: str = Field("", max_length=20)
    current: bool = False
    bullets: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("bullets", mode="before")
    @classmethod
    def _bullets(cls, v):
        if isinstance(v, str):
            v = v.split("\n")
        return [b.strip(" -•*\t")[:300] for b in (v or []) if b and b.strip(" -•*\t")][:8]


class Education(_Model):
    qualification: str = Field("", max_length=S)
    institution: str = Field("", max_length=S)
    year: str = Field("", max_length=20)
    status: str = Field("completed", pattern="^(completed|in_progress)$")
    details: str = Field("", max_length=400)


class Language(_Model):
    name: str = Field("", max_length=40)
    level: str = Field("", max_length=40)


class Certificate(_Model):
    name: str = Field("", max_length=S)
    issuer: str = Field("", max_length=S)
    year: str = Field("", max_length=20)


class Referee(_Model):
    name: str = Field("", max_length=S)
    relationship: str = Field("", max_length=S)
    phone: str = Field("", max_length=40)
    email: str = Field("", max_length=S)


class CvData(_Model):
    personal: Personal = Field(default_factory=Personal)
    summary: str = Field("", max_length=L)
    experience: list[Experience] = Field(default_factory=list, max_length=12)
    education: list[Education] = Field(default_factory=list, max_length=8)
    skills: list[str] = Field(default_factory=list, max_length=30)
    languages: list[Language] = Field(default_factory=list, max_length=11)
    certificates: list[Certificate] = Field(default_factory=list, max_length=12)
    achievements: list[str] = Field(default_factory=list, max_length=10)
    references_on_request: bool = True
    references: list[Referee] = Field(default_factory=list, max_length=4)

    @field_validator("skills", "achievements", mode="before")
    @classmethod
    def _list_of_text(cls, v):
        if isinstance(v, str):
            v = re.split(r"[\n,]", v)
        return [x.strip()[:200] for x in (v or []) if x and x.strip()]


KIND_LABELS = {"part-time": "Part-time", "volunteer": "Volunteer", "informal": "Self-employed / informal",
               "project": "Project", "learnership": "Learnership", "internship": "Internship"}


def _period(e: Experience) -> str:
    end = "Present" if e.current else e.end
    return " – ".join(x for x in (e.start, end) if x)


def has_content(d: CvData) -> bool:
    return bool(d.personal.full_name and (d.summary or d.experience or d.education or d.skills))


def to_text(d: CvData) -> str:
    """Plain-text version: what skill extraction and CV tailoring read."""
    p = d.personal
    out = [p.full_name, " | ".join(x for x in (p.phone, p.email, p.location, p.linkedin) if x)]
    if d.summary:
        out += ["", "PROFILE", d.summary]
    if d.experience:
        out += ["", "EXPERIENCE"]
        for e in d.experience:
            kind = f" ({KIND_LABELS[e.kind]})" if e.kind in KIND_LABELS else ""
            out.append(" — ".join(x for x in (e.role + kind, e.organisation, _period(e)) if x))
            out += [f"- {b}" for b in e.bullets]
    if d.education:
        out += ["", "EDUCATION"]
        for ed in d.education:
            out.append(" — ".join(x for x in (ed.qualification + (" (in progress)" if ed.status == "in_progress" else ""),
                                              ed.institution, ed.year) if x))
            if ed.details:
                out.append(ed.details)
    if d.skills:
        out += ["", "SKILLS", ", ".join(d.skills)]
    if d.languages:
        out += ["", "LANGUAGES", ", ".join(f"{l.name} ({l.level})" if l.level else l.name for l in d.languages if l.name)]
    if d.certificates:
        out += ["", "CERTIFICATES"] + [" — ".join(x for x in (c.name, c.issuer, c.year) if x) for c in d.certificates]
    if d.achievements:
        out += ["", "ACHIEVEMENTS"] + [f"- {a}" for a in d.achievements]
    return "\n".join(out).strip()


def render_pdf(d: CvData) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import HRFlowable, KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer
    from xml.sax.saxutils import escape

    ink, mid, accent = colors.HexColor("#10251A"), colors.HexColor("#4A5A50"), colors.HexColor("#226B45")
    st = {
        "name": ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=ink),
        "contact": ParagraphStyle("contact", fontName="Helvetica", fontSize=9.5, leading=13, textColor=mid),
        "h": ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=accent, spaceBefore=10, spaceAfter=3),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=13.5, textColor=ink, alignment=TA_LEFT),
        "item": ParagraphStyle("item", fontName="Helvetica-Bold", fontSize=10, leading=13.5, textColor=ink),
        "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=9.5, leading=12.5, textColor=mid),
    }
    e = lambda s: escape(s or "")  # noqa: E731
    story = []
    p = d.personal
    story.append(Paragraph(e(p.full_name or "Your name"), st["name"]))
    contact = [p.phone, p.email, p.location, p.linkedin, (f"Driver's licence: {p.drivers_licence}" if p.drivers_licence else "")]
    story.append(Paragraph("  ·  ".join(e(x) for x in contact if x), st["contact"]))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=0.8, color=accent, spaceBefore=2, spaceAfter=2))

    def section(title):
        story.append(Paragraph(e(title.upper()), st["h"]))

    def bullets(items):
        return ListFlowable([ListItem(Paragraph(e(b), st["body"]), leftIndent=10, value="•") for b in items],
                            bulletType="bullet", start="•", leftIndent=10, bulletFontSize=8, spaceBefore=1)

    if d.summary:
        section("Profile")
        story.append(Paragraph(e(d.summary), st["body"]))
    if d.experience:
        section("Experience")
        for x in d.experience:
            kind = f" ({KIND_LABELS[x.kind]})" if x.kind in KIND_LABELS else ""
            head = Paragraph(e(x.role or "Role") + e(kind), st["item"])
            meta = Paragraph("  ·  ".join(e(v) for v in (x.organisation, x.location, _period(x)) if v), st["meta"])
            block = [head, meta] + ([bullets(x.bullets)] if x.bullets else []) + [Spacer(1, 5)]
            story.append(KeepTogether(block))
    if d.education:
        section("Education")
        for ed in d.education:
            q = e(ed.qualification or "Qualification") + (" <font color='#4A5A50'>(in progress)</font>" if ed.status == "in_progress" else "")
            block = [Paragraph(q, st["item"]),
                     Paragraph("  ·  ".join(e(v) for v in (ed.institution, ed.year) if v), st["meta"])]
            if ed.details:
                block.append(Paragraph(e(ed.details), st["body"]))
            story.append(KeepTogether(block + [Spacer(1, 5)]))
    if d.skills:
        section("Skills")
        story.append(Paragraph(e("  ·  ".join(d.skills)), st["body"]))
    if d.languages:
        section("Languages")
        story.append(Paragraph(e("  ·  ".join(f"{l.name} ({l.level})" if l.level else l.name for l in d.languages if l.name)), st["body"]))
    if d.certificates:
        section("Certificates")
        story.append(bullets([" — ".join(v for v in (c.name, c.issuer, c.year) if v) for c in d.certificates]))
    if d.achievements:
        section("Achievements & activities")
        story.append(bullets(d.achievements))
    section("References")
    refs = [r for r in d.references if r.name]
    if d.references_on_request or not refs:
        story.append(Paragraph("Available on request.", st["body"]))
    else:
        for r in refs:
            story.append(Paragraph(e(r.name) + (f" — {e(r.relationship)}" if r.relationship else ""), st["item"]))
            story.append(Paragraph("  ·  ".join(e(v) for v in (r.phone, r.email) if v), st["meta"]))
            story.append(Spacer(1, 4))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=f"CV - {p.full_name}".strip(" -"), author=p.full_name or "Ascend")
    doc.build(story)
    return buf.getvalue()


def file_name(d: CvData) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "_", d.personal.full_name or "My").strip("_") or "My"
    return f"{base}_CV_{date.today():%Y%m%d}.pdf"
