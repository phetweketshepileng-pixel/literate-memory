import io

from pypdf import PdfReader

from app.modules.profile.cv_builder import CvData, file_name, has_content, render_pdf, to_text
from app.modules.profile.cv_parsing import extract_text

SAMPLE = {
    "personal": {"full_name": "  Thandi   Mokoena ", "phone": "071 234 5678", "email": "thandi@example.com",
                 "location": "Soweto, Johannesburg", "drivers_licence": "Code 8"},
    "summary": "Matriculant with retail experience, eager to start a learnership in customer service.",
    "experience": [{"role": "Cashier", "organisation": "Family spaza shop", "kind": "informal", "start": "2024",
                    "current": True, "bullets": "Handled cash and card payments daily\n- Kept stock records <neat>"},
                   {"role": "Tutor", "organisation": "Church youth group", "kind": "volunteer", "start": "2023", "end": "2024"}],
    "education": [{"qualification": "National Senior Certificate (Matric)", "institution": "Morris Isaacson High",
                   "year": "2023", "details": "Maths 65%, English 72%"}],
    "skills": "Customer service, Cash handling, MS Excel",
    "languages": [{"name": "isiZulu", "level": "Fluent"}, {"name": "English", "level": "Fluent"}],
    "achievements": ["Class representative (2023)"],
    "references_on_request": True,
}


def test_validation_cleans_and_splits():
    d = CvData.model_validate(SAMPLE)
    assert d.personal.full_name == "Thandi Mokoena"
    assert d.skills == ["Customer service", "Cash handling", "MS Excel"]
    assert d.experience[0].bullets == ["Handled cash and card payments daily", "Kept stock records <neat>"]
    assert has_content(d) and not has_content(CvData())


def test_text_version_has_all_sections():
    t = to_text(CvData.model_validate(SAMPLE))
    for part in ("Thandi Mokoena", "EXPERIENCE", "Cashier (Self-employed / informal)", "Present", "EDUCATION",
                 "SKILLS", "isiZulu (Fluent)", "ACHIEVEMENTS"):
        assert part in t


def test_pdf_is_readable_and_escapes_text():
    pdf = render_pdf(CvData.model_validate(SAMPLE))
    assert pdf[:4] == b"%PDF"
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
    assert "Thandi Mokoena" in text and "<neat>" in text and "Available on request" in text
    # the app's own CV reader can read it (so skills get extracted)
    assert "Customer service" in extract_text(pdf, "cv.pdf", "application/pdf")


def test_empty_cv_still_renders_and_file_name():
    assert render_pdf(CvData())[:4] == b"%PDF"
    assert file_name(CvData.model_validate(SAMPLE)).startswith("Thandi_Mokoena_CV_")
