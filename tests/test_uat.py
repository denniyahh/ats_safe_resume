"""UAT & Regression Test Suite

Tests are marked @pytest.mark.uat — run with:
  pytest -m uat tests/test_uat.py

Not run in CI by default. Designed for pre-release validation,
weekly cron, and regression hunting.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st
from hypothesis import HealthCheck

from ats_safe_resume.parser import parse
from ats_safe_resume.models import (
    Resume, Theme, PageMode, ContactInfo,
    Company, Position, SkillCategory, Education,
)
from ats_safe_resume.renderers import PdfRenderer
from ats_safe_resume.renderers.docx import DocxRenderer
from ats_safe_resume.renderers.html import HtmlRenderer
from ats_safe_resume.renderers.txt import TxtRenderer
from ats_safe_resume.renderers.json_resume import JsonResumeRenderer


pytestmark = pytest.mark.uat

# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def example_resume():
    """Parse the Jane Doe example resume once per test module."""
    md = (Path(__file__).resolve().parent / "fixtures" / "jane_doe.md").read_text()
    return parse(md)


@pytest.fixture(scope="module")
def example_outputs(example_resume, tmp_path_factory):
    """Render all 5 formats from the example resume."""
    tmp = tmp_path_factory.mktemp("example_outputs")
    outputs = {}
    for fmt, renderer_cls in [("pdf", PdfRenderer), ("docx", DocxRenderer),
                               ("html", HtmlRenderer), ("txt", TxtRenderer),
                               ("json", JsonResumeRenderer)]:
        out = tmp / f"resume.{fmt}"
        renderer_cls().render(example_resume, out)
        outputs[fmt] = out
    return outputs


# ═══════════════════════════════════════════════════════════════════
# PDF tests
# ═══════════════════════════════════════════════════════════════════

def test_pdf_fonts_embedded(example_outputs):
    """Source Sans 3 fonts must be embedded and subset in PDF."""
    pdf = example_outputs["pdf"]
    font_output = subprocess.check_output(["pdffonts", str(pdf)], text=True)
    source_sans_lines = [l for l in font_output.split('\n') if 'SourceSans' in l]
    assert len(source_sans_lines) >= 3, \
        f"Expected at least 3 Source Sans 3 faces, got {len(source_sans_lines)}"

    for line in source_sans_lines:
        parts = line.rsplit(None, 4)
        if len(parts) >= 4:
            assert 'yes' in parts[-3].lower(), \
                f"Font not subset: {line.strip()}"
            # emb column is one more left
            if len(parts) >= 5:
                assert 'yes' in parts[-4].lower(), \
                    f"Font not embedded: {line.strip()}"


def test_pdf_is_valid(example_outputs):
    """PDF must start with %PDF magic bytes."""
    pdf = example_outputs["pdf"]
    assert pdf.read_bytes()[:4] == b"%PDF"


def test_pdf_contains_sections(example_outputs):
    """PDF text must contain standard ATS section headers."""
    pdf = example_outputs["pdf"]
    text = subprocess.check_output(["pdftotext", str(pdf), "-"], text=True)
    assert "Executive Profile" in text
    assert "Professional Experience" in text
    assert "Education" in text


# ═══════════════════════════════════════════════════════════════════
# DOCX tests
# ═══════════════════════════════════════════════════════════════════

def test_docx_opens_without_corruption(example_outputs):
    """DOCX must be openable by python-docx without errors."""
    from docx import Document
    doc = Document(str(example_outputs["docx"]))
    assert len(doc.paragraphs) > 0


def test_docx_heading_styles(example_outputs):
    """Section headings should use Heading 1 style."""
    from docx import Document
    doc = Document(str(example_outputs["docx"]))
    heading_texts = {p.text for p in doc.paragraphs
                     if p.style.name.startswith("Heading")}
    assert "Executive Profile" in heading_texts, \
        "Executive Profile missing from heading styles"
    assert "Professional Experience" in heading_texts, \
        "Professional Experience missing from heading styles"


def test_docx_accent_bars(example_outputs):
    """Section headings should have bottom borders (accent bars)."""
    from docx import Document
    from docx.oxml.ns import qn
    doc = Document(str(example_outputs["docx"]))
    heading_paras = [p for p in doc.paragraphs
                     if p.style.name.startswith("Heading 1")]
    assert len(heading_paras) > 0, "No Heading 1 paragraphs found"

    # At least one heading should have a bottom border
    borders_found = 0
    for p in heading_paras:
        pPr = p._element.find(qn('w:pPr'))
        if pPr is not None:
            pBdr = pPr.find(qn('w:pBdr'))
            if pBdr is not None:
                bottom = pBdr.find(qn('w:bottom'))
                if bottom is not None:
                    borders_found += 1
    assert borders_found > 0, "No heading paragraphs have accent bars (bottom borders)"


def test_docx_list_bullet_style(example_outputs):
    """Bullet points should use List Bullet style."""
    from docx import Document
    doc = Document(str(example_outputs["docx"]))
    bullet_paras = [p for p in doc.paragraphs
                    if p.style.name == "List Bullet"]
    assert len(bullet_paras) > 0, "No paragraphs use List Bullet style"


# ═══════════════════════════════════════════════════════════════════
# HTML tests
# ═══════════════════════════════════════════════════════════════════

def test_html_valid_structure(example_outputs):
    """HTML must have doctype, head, and body."""
    html = example_outputs["html"].read_text()
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "</html>" in html
    assert "<head>" in html
    assert "<body>" in html


def test_html_print_stylesheet(example_outputs):
    """HTML should have @media print rules."""
    html = example_outputs["html"].read_text()
    assert "@media print" in html


def test_html_no_double_escaped(example_outputs):
    """HTML must not have double-escaped entities (e.g. &amp;amp; not &amp;).
    
    Note: Jinja2 auto-escapes & to &amp; which is correct HTML.
    We check for double-escaping: &amp;amp; or &lt; appearing in output.
    """
    html = example_outputs["html"].read_text()
    # Double-escaping would be &amp;amp; or &amp;lt;
    assert "&amp;amp;" not in html, "Double-escaped &amp;amp; in HTML"
    assert "&amp;lt;" not in html, "Double-escaped &amp;lt; in HTML"


# ═══════════════════════════════════════════════════════════════════
# TXT tests
# ═══════════════════════════════════════════════════════════════════

def test_txt_ats_normalized(example_outputs):
    """TXT must have ASCII-only typography (no em dashes, smart quotes)."""
    text = example_outputs["txt"].read_text()
    assert "—" not in text, "Em dash found in TXT"
    assert "–" not in text, "En dash found in TXT"
    assert "\u201c" not in text, "Left smart quote found in TXT"
    assert "\u201d" not in text, "Right smart quote found in TXT"


def test_txt_no_formatting(example_outputs):
    """TXT must not contain ** or * formatting markers."""
    text = example_outputs["txt"].read_text()
    assert "**" not in text, "Bold markers in TXT output"
    assert "—" not in text, "Em dash in TXT output"


# ═══════════════════════════════════════════════════════════════════
# JSON tests
# ═══════════════════════════════════════════════════════════════════

def test_json_valid_json(example_outputs):
    """Output must be parseable JSON."""
    text = example_outputs["json"].read_text()
    data = json.loads(text)
    assert isinstance(data, dict)


def test_json_required_fields(example_outputs):
    """JSON Resume must have all required top-level keys."""
    data = json.loads(example_outputs["json"].read_text())
    for key in ["basics", "work", "education", "skills"]:
        assert key in data, f"Missing required JSON Resume key: {key}"
    assert "name" in data["basics"]


def test_json_section_order(example_outputs):
    """Section order: basics → work → skills → education."""
    data = json.loads(example_outputs["json"].read_text())
    keys = list(data.keys())
    # All must be present in this order
    for key in ["basics", "work", "skills", "education"]:
        assert key in keys, f"Missing key: {key}"
    basics_idx = keys.index("basics")
    work_idx = keys.index("work")
    skills_idx = keys.index("skills") if "skills" in keys else -1
    education_idx = keys.index("education") if "education" in keys else -1
    # Basics must come before work; education must come last
    assert basics_idx < work_idx, f"basics ({basics_idx}) not before work ({work_idx})"
    if skills_idx >= 0:
        assert work_idx < skills_idx, f"work ({work_idx}) not before skills ({skills_idx})"
    if education_idx >= 0:
        if skills_idx >= 0:
            assert skills_idx < education_idx, f"skills ({skills_idx}) not before education ({education_idx})"
        else:
            assert work_idx < education_idx, f"work ({work_idx}) not before education ({education_idx})"


def test_json_per_position_dates(example_outputs):
    """Each work entry must have its own startDate/endDate (was v1 bug)."""
    data = json.loads(example_outputs["json"].read_text())
    work = data["work"]
    assert len(work) >= 3, f"Expected at least 3 work entries, got {len(work)}"
    dates = [(w.get("position"), w.get("startDate"), w.get("endDate"))
             for w in work]
    # All dates should be present (no None for startDate across positions)
    start_dates = [d[1] for d in dates if d[1]]
    assert len(start_dates) == len(work), \
        f"Not all positions have startDate: {dates}"


def test_json_no_markdown_leak(example_outputs):
    """JSON must not contain ** markdown formatting."""
    text = example_outputs["json"].read_text()
    assert "**" not in text


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _read_text(path: Path, fmt: str) -> str:
    """Read text content from any output format."""
    if fmt == "pdf":
        return subprocess.check_output(["pdftotext", str(path), "-"], text=True)
    elif fmt == "docx":
        from docx import Document
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    elif fmt == "json":
        return json.dumps(json.loads(path.read_text()))
    else:
        return path.read_text()


# ═══════════════════════════════════════════════════════════════════
# Cross-format consistency
# ═══════════════════════════════════════════════════════════════════

def test_all_formats_same_name(example_outputs):
    """Candidate name must appear in all 5 formats."""
    name = "Jane Doe"
    for fmt in ["pdf", "docx", "html", "txt", "json"]:
        text = _read_text(example_outputs[fmt], fmt)
        assert name in text, f"Name '{name}' not found in {fmt}"


def test_all_formats_same_companies(example_outputs):
    """Same company names across all text-based formats."""
    expected = {"Acme Corp", "TechCorp Solutions", "DataFirst Inc."}
    for fmt in ["pdf", "docx", "html", "txt"]:
        text = _read_text(example_outputs[fmt], fmt)
        found = {c for c in expected if c in text}
        missing = expected - found
        assert len(missing) == 0, f"Missing companies in {fmt}: {missing}"


def test_all_formats_same_sections(example_outputs):
    """Key section headers must appear in all text-based formats."""
    expected = ["Executive Profile", "Professional Experience",
                "Technical Skills", "Education"]
    for fmt in ["pdf", "docx", "html", "txt"]:
        text = _read_text(example_outputs[fmt], fmt)
        for header in expected:
            # TXT uses UPPERCASE headers — check case-insensitively
            assert header.lower() in text.lower(), \
                f"Section '{header}' missing in {fmt}"


def test_all_formats_crafted_footer(example_outputs):
    """Crafted footer must appear in all text-based formats."""
    for fmt in ["pdf", "docx", "html", "txt"]:
        text = _read_text(example_outputs[fmt], fmt)
        assert "ats_safe_resume" in text.lower(), \
            f"Crafted footer missing in {fmt}"


# ═══════════════════════════════════════════════════════════════════
# Hypothesis regression suite (exhaustive, slow — UAT only)
# ═══════════════════════════════════════════════════════════════════

# Strategies (imported from test_hypothesis.py pattern)
name_str = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Zs'),
                           whitelist_characters=['-', "'", '.']),
    min_size=1, max_size=40,
).map(str.strip).filter(lambda s: len(s) > 0)

bullet_str = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs'),
                           whitelist_characters=['$', '%', '+', '&', '-', '.', ',', '/', '*']),
    min_size=5, max_size=120,
).map(str.strip)

position_strategy = st.builds(
    Position,
    title=st.text(min_size=3, max_size=50),
    start_date=st.sampled_from(["Jan 2020", "Jun 2021", "2020", "2019 – 2021", None]),
    end_date=st.sampled_from(["Present", "Dec 2022", "2021", None]),
    bullets=st.lists(bullet_str, min_size=0, max_size=5),
)

company_strategy = st.builds(
    Company,
    name=st.text(min_size=2, max_size=30),
    positions=st.lists(position_strategy, min_size=1, max_size=3),
)

resume_strategy = st.builds(
    Resume,
    name=name_str,
    companies=st.lists(company_strategy, min_size=0, max_size=6),
    education=st.lists(st.builds(Education, institution=st.text(min_size=5, max_size=50)), min_size=0, max_size=3),
    crafted_footer=st.booleans(),
)


@given(resume_strategy)
@settings(max_examples=200, deadline=None,
          suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
def test_regression_all_formats_consistent(resume):
    """Regression: all formats must contain the candidate name."""
    if not resume.name:
        return
    tmp = Path(tempfile.mkdtemp())
    try:
        for fmt, renderer_cls in [("pdf", PdfRenderer), ("docx", DocxRenderer),
                                   ("html", HtmlRenderer), ("txt", TxtRenderer),
                                   ("json", JsonResumeRenderer)]:
            out = tmp / f"resume.{fmt}"
            renderer_cls().render(resume, out)
            if fmt == "pdf":
                text = subprocess.check_output(["pdftotext", str(out), "-"], text=True)
            elif fmt == "json":
                text = json.dumps(json.loads(out.read_text()))
            else:
                text = out.read_text()
            assert resume.name in text, \
                f"Name '{resume.name}' missing from {fmt}"
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


@given(resume_strategy)
@settings(max_examples=200, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
def test_regression_no_crash(resume):
    """Regression: no renderer should crash on any valid resume."""
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
