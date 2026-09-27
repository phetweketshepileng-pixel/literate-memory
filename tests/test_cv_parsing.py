import io

import pytest

from app.modules.profile.cv_parsing import UnreadableDocumentError, detect_skills, extract_text


def test_extract_text_plain():
    assert extract_text(b"Hello  world", "cv.txt", "text/plain") == "Hello world"


def test_extract_text_docx_roundtrip():
    from docx import Document

    doc = Document()
    doc.add_paragraph("Collections Team Leader handling escalations and SQL reporting")
    buf = io.BytesIO(); doc.save(buf)
    text = extract_text(buf.getvalue(), "cv.docx", None)
    assert "escalations" in text


def test_extract_text_rejects_unknown_type():
    with pytest.raises(UnreadableDocumentError):
        extract_text(b"\x89PNG", "photo.png", "image/png")


def test_extract_text_corrupt_pdf_is_unreadable():
    with pytest.raises(UnreadableDocumentError):
        extract_text(b"not really a pdf", "cv.pdf", "application/pdf")


def test_detect_skills_uses_word_boundaries():
    skills = detect_skills("Led escalations, dispute resolution and KPI reporting in SQL. Used Jira.")
    assert {"Escalation handling", "Dispute resolution", "KPI management", "Reporting", "SQL", "Jira"} <= set(skills)
    # 'sap' must not match inside 'disappear'; 'sql' not inside 'sqlite'-free text
    assert "SAP" not in detect_skills("targets would disappear")


def test_detect_skills_empty():
    assert detect_skills("") == []
