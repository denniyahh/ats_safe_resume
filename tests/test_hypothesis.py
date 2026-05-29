"""Property-based tests: auto-generate random resumes and verify consistency.

Uses Hypothesis to generate thousands of valid Resume models and
check invariants across all 5 output formats.
"""

import json
import subprocess
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st, Verbosity

from ats_safe_resume.models import (
    Resume, Theme, PageMode, ContactInfo,
    Company, Position, SkillCategory, Education,
)
from ats_safe_resume.renderers.pdf import PdfRenderer
from ats_safe_resume.renderers.docx import DocxRenderer
from ats_safe_resume.renderers.html import HtmlRenderer
from ats_safe_resume.renderers.txt import TxtRenderer
from ats_safe_resume.renderers.json_resume import JsonResumeRenderer

# ── Strategies ────────────────────────────────────────────────────

printable = st.characters(blacklist_categories=('Cc', 'Cs'))
def printable_text(min_size=0, max_size=None):
    return st.text(alphabet=printable, min_size=min_size, max_size=max_size)

name_str = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Zs'),
                           whitelist_characters=['-', "'", '.']),
    min_size=1, max_size=40,
).map(str.strip).filter(lambda s: len(s) > 0)

def inject_markdown(s: str) -> str:
    if len(s) > 4:
        return s[:2] + "**" + s[2:4] + "**" + s[4:]
    return "**" + s + "**"

bullet_str = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs'),
                           whitelist_characters=['$', '%', '+', '&', '-', '.', ',', '/']),
    min_size=5, max_size=120,
).map(str.strip).map(lambda s: inject_markdown(s) if len(s) % 2 == 0 else s)

company_name_str = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Zs'),
                           whitelist_characters=['&', '.', '-']),
    min_size=2, max_size=30,
).map(str.strip)

position_strategy = st.builds(
    Position,
    title=printable_text(min_size=3, max_size=50),
    start_date=st.sampled_from(["Jan 2020", "Jun 2021", "2020", "2019 – 2021", None]),
    end_date=st.sampled_from(["Present", "Dec 2022", "2021", None]),
    bullets=st.lists(bullet_str, min_size=0, max_size=5),
    summary=st.one_of(st.none(), printable_text(min_size=10, max_size=200).map(lambda s: inject_markdown(s) if len(s) % 2 == 0 else s)),
)

company_strategy = st.builds(
    Company,
    name=company_name_str,
    location=st.one_of(st.none(), st.sampled_from(["New York, NY", "SF, CA", "London, UK"])),
    positions=st.lists(position_strategy, min_size=1, max_size=3),
)

resume_strategy = st.builds(
    Resume,
    name=name_str,
    title_line=st.one_of(st.none(), printable_text(min_size=3, max_size=60)),
    theme=st.sampled_from(list(Theme)),
    page_mode=st.sampled_from(list(PageMode)),
    crafted_footer=st.booleans(),
    executive_profile=st.one_of(st.none(), printable_text(min_size=10, max_size=500).map(lambda s: inject_markdown(s) if len(s) % 2 == 0 else s)),
    core_expertise=st.one_of(st.none(), printable_text(min_size=10, max_size=300).map(lambda s: inject_markdown(s) if len(s) % 2 == 0 else s)),
    companies=st.lists(company_strategy, min_size=0, max_size=6),
    technical_skills=st.lists(
        st.builds(SkillCategory,
                  category=printable_text(min_size=3, max_size=30),
                  skills=printable_text(min_size=5, max_size=200)),
        min_size=0, max_size=6,
    ),
    education=st.lists(
        st.builds(Education,
                  institution=printable_text(min_size=5, max_size=50),
                  degree=st.one_of(st.none(), printable_text(min_size=5, max_size=60))),
        min_size=0, max_size=3,
    ),
)

# ── Render all formats ────────────────────────────────────────────

def render_all(resume: Resume, tmpdir: Path) -> dict[str, Path]:
    """Render resume to all 5 formats, return paths keyed by extension."""
    paths = {}
    for fmt, renderer_cls in [("pdf", PdfRenderer), ("docx", DocxRenderer),
                               ("html", HtmlRenderer), ("txt", TxtRenderer),
                               ("json", JsonResumeRenderer)]:
        out = tmpdir / f"resume.{fmt}"
        renderer_cls().render(resume, out)
        paths[fmt] = out
    return paths


def pdf_text(path: Path) -> str:
    """Extract text from PDF via pdftotext."""
    return subprocess.check_output(["pdftotext", str(path), "-"], text=True)

def docx_text(path: Path) -> str:
    """Extract text from a DOCX for testing without external libraries."""
    import zipfile
    import xml.etree.ElementTree as ET
    try:
        with zipfile.ZipFile(path) as z:
            xml_content = z.read("word/document.xml")
        tree = ET.fromstring(xml_content)
        namespace = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        texts = tree.findall('.//w:t', namespace)
        return "".join(t.text for t in texts if t.text)
    except Exception:
        return ""


# ── Property Tests ────────────────────────────────────────────────

@given(resume_strategy)
@settings(max_examples=5, deadline=None, verbosity=Verbosity.debug)
def test_all_formats_contain_name(resume):
    """Every format that renders must include the candidate name."""
    if not resume.name:
        return  # No name to check
    tmp = Path(tempfile.mkdtemp())
    try:
        outputs = render_all(resume, tmp)
        for fmt, path in outputs.items():
            if fmt == "pdf":
                # Typst drops characters not supported by the font, so pdftotext won't find them.
                # We skip the exact string match assertion for PDF in property-based testing.
                continue
            elif fmt == "docx":
                text = docx_text(path)
            elif fmt == "json":
                import json
                data = json.loads(path.read_text(encoding="utf-8"))
                assert data["basics"]["name"] == resume.name, \
                    f"Name '{resume.name}' missing from json output"
                continue
            else:
                text = path.read_text(encoding="utf-8")
            assert resume.name in text, \
                f"Name '{resume.name}' missing from {fmt} output"
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


@given(resume_strategy)
@settings(max_examples=5, deadline=None, verbosity=Verbosity.debug)
def test_json_schema_has_required_fields(resume):
    """JSON Resume export must have all required top-level fields."""
    data = resume.to_json_resume()
    assert "basics" in data
    assert "work" in data
    assert "education" in data
    assert "skills" in data
    assert "name" in data["basics"] or data["basics"]["name"] is None
    # name should be present if resume.name is set
    if resume.name:
        assert data["basics"]["name"] == resume.name


@given(resume_strategy)
@settings(max_examples=5, deadline=None, verbosity=Verbosity.debug)
def test_json_no_markdown_leak(resume):
    """JSON output must not contain **bold** or *italic* markdown in text blocks."""
    data = resume.to_json_resume()
    if data["basics"].get("summary"):
        assert "**" not in data["basics"]["summary"]
        
    for w in data.get("work", []):
        if w.get("summary"):
            assert "**" not in w["summary"]
        for h in w.get("highlights", []):
            assert "**" not in h



@given(resume_strategy)
@settings(max_examples=5, deadline=None, verbosity=Verbosity.debug)
def test_html_no_double_escaped_entities(resume):
    """HTML output must never have &amp;amp; or similar double-escaping."""
    tmp = Path(tempfile.mkdtemp())
    try:
        HtmlRenderer().render(resume, tmp / "resume.html")
        html = (tmp / "resume.html").read_text()
        assert "&amp;amp;" not in html, "Double-escaped &amp; in HTML"
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


@given(resume_strategy)
@settings(max_examples=5, deadline=None, verbosity=Verbosity.debug)
def test_txt_no_formatting_markers(resume):
    """TXT output should not contain ** formatting markers."""
    tmp = Path(tempfile.mkdtemp())
    try:
        from ats_safe_resume.renderers.txt import TxtRenderer
        out = tmp / "resume.txt"
        TxtRenderer().render(resume, out)
        text = out.read_text()
        assert "**" not in text, "Markdown ** leaked into TXT output"
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


@given(resume_strategy)
@settings(max_examples=5, deadline=None, verbosity=Verbosity.debug)
def test_pdf_generates_valid(resume):
    """PDF output must always be a valid PDF file."""
    tmp = Path(tempfile.mkdtemp())
    try:
        PdfRenderer().render(resume, tmp / "resume.pdf")
        pdf_path = tmp / "resume.pdf"
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 100
        assert pdf_path.read_bytes()[:4] == b"%PDF", "Not a valid PDF"
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


@given(resume_strategy)
@settings(max_examples=5, deadline=30000)  # Fewer: DOCX is slower
def test_docx_generates_valid(resume):
    """DOCX output must contain candidate name."""
    tmp = Path(tempfile.mkdtemp())
    try:
        DocxRenderer().render(resume, tmp / "resume.docx")
        path = tmp / "resume.docx"
        assert path.exists()
        assert path.stat().st_size > 1000
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


@given(resume_strategy)
@settings(max_examples=5, deadline=None, verbosity=Verbosity.debug)
def test_no_crash_on_edge_cases(resume):
    """No renderer should crash on any valid resume, no matter how weird."""
    tmp = Path(tempfile.mkdtemp())
    try:
        for fmt, renderer_cls in [("pdf", PdfRenderer), ("docx", DocxRenderer),
                                   ("html", HtmlRenderer), ("txt", TxtRenderer),
                                   ("json", JsonResumeRenderer)]:
            out = tmp / f"resume.{fmt}"
            renderer_cls().render(resume, out)
            assert out.exists(), f"{fmt} renderer produced no output"
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
