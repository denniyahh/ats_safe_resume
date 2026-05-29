# tests/test_v1_v2_parity.py
"""Validate that v2 pipeline produces the same content as v1."""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent


def test_v2_pipeline_runs_without_error():
    """v2 pipeline must complete without crashing."""
    result = subprocess.run(
        ["python3", "-m", "ats_safe_resume", str(SCRIPT_DIR / "example/resume.md"),
         "--out-dir", "dist-v2"],
        capture_output=True, text=True, cwd=SCRIPT_DIR,
    )
    assert result.returncode == 0, f"v2 failed:\n{result.stderr}"


def test_v1_v2_json_match():
    """v2 JSON output must contain the same core data as v1 JSON output."""
    v1_path = SCRIPT_DIR / "dist/resume.json"
    v2_path = SCRIPT_DIR / "dist-v2/resume.json"

    if not v1_path.exists():
        pytest.skip("v1 dist/ not available (run build_resume.sh first)")
    if not v2_path.exists():
        pytest.skip("v2 dist-v2/ not available (run v2 pipeline first)")

    v1_data = json.loads(v1_path.read_text())
    v2_data = json.loads(v2_path.read_text())

    assert v1_data["basics"]["name"] == v2_data["basics"]["name"], \
        f"Name mismatch: v1={v1_data['basics']['name']} v2={v2_data['basics']['name']}"
    # v2 may have additional fields (label, location, url) that v1 doesn't
    assert len(v1_data.get("work", [])) == len(v2_data.get("work", [])), \
        f"Work count mismatch: v1={len(v1_data.get('work',[]))} v2={len(v2_data.get('work',[]))}"


def test_v1_v2_pdf_contains_same_name():
    """Both pipelines' PDFs must contain the candidate name."""
    if not (SCRIPT_DIR / "dist/resume.pdf").exists():
        pytest.skip("v1 PDF not available")
    if not (SCRIPT_DIR / "dist-v2/resume.pdf").exists():
        pytest.skip("v2 PDF not available")

    v1_text = subprocess.check_output(
        ["pdftotext", str(SCRIPT_DIR / "dist/resume.pdf"), "-"]
    ).decode()
    v2_text = subprocess.check_output(
        ["pdftotext", str(SCRIPT_DIR / "dist-v2/resume.pdf"), "-"]
    ).decode()
    assert "Jane Doe" in v1_text
    assert "Jane Doe" in v2_text


def test_v2_pdf_fonts_embedded():
    """v2 PDF must have Source Sans 3 fonts embedded and subset."""
    pdf_path = SCRIPT_DIR / "dist-v2/resume.pdf"
    if not pdf_path.exists():
        pytest.skip("v2 PDF not available")

    font_output = subprocess.check_output(["pdffonts", str(pdf_path)]).decode()
    source_sans_lines = [l for l in font_output.split('\n') if 'SourceSans' in l]
    assert len(source_sans_lines) >= 3, "Expected at least 3 Source Sans 3 font faces"
    for line in source_sans_lines:
        parts = line.rsplit(None, 4)
        if len(parts) >= 4:
            assert 'yes' in parts[-3].lower(), f"Font not subset: {line.strip()}"


def test_v2_multi_page_no_crash():
    """PDF with many positions should render without crash."""
    from ats_safe_resume.models import Resume, Company, Position
    from ats_safe_resume.renderers.pdf import PdfRenderer

    resume = Resume(
        name="Overachiever",
        title_line="Professional",
        companies=[
            Company(name=f"Company {i}", positions=[
                Position(title=f"Role {j}", start_date="2020", end_date="2022",
                         bullets=[f"Accomplishment {j}"])
                for j in range(3)
            ])
            for i in range(5)
        ]
    )
    out = Path(tempfile.mkdtemp()) / "multi.pdf"
    PdfRenderer().render(resume, out)
    assert out.exists()
    page_count = int(subprocess.check_output(
        ["pdfinfo", str(out)]
    ).decode().split("Pages:")[1].strip().split()[0])
    assert page_count > 0


def test_v2_json_no_markdown_in_summary():
    """JSON basics.summary must not contain **markdown**."""
    from ats_safe_resume.models import Resume
    from ats_safe_resume.renderers.json_resume import JsonResumeRenderer

    resume = Resume(
        name="Test",
        title_line="Test",
        executive_profile="Grew revenue from **$5MM** to **$25MM+**."
    )
    out = Path(tempfile.mkdtemp()) / "resume.json"
    JsonResumeRenderer().render(resume, out)
    data = json.loads(out.read_text())
    assert "**" not in data["basics"]["summary"], \
        f"Markdown found in summary: {data['basics']['summary']}"
