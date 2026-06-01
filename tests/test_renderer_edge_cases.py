# tests/test_v1_v2_parity.py
"""Edge-case renderer tests that aren't covered by UAT or hypothesis."""

import json
import subprocess
import tempfile
from pathlib import Path

from ats_safe_resume.models import Resume, Company, Position
from ats_safe_resume.renderers import PdfRenderer
from ats_safe_resume.renderers.json_resume import JsonResumeRenderer


def test_multi_page_no_crash():
    """PDF with many positions should render without crash."""
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


def test_json_no_markdown_in_summary():
    """JSON basics.summary must not contain **markdown**."""
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
