# tests/test_parser.py
import pytest
from pathlib import Path
from ats_safe_resume.parser import parse
from ats_safe_resume.models import Resume, Theme

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_frontmatter():
    md = (FIXTURES / "jane_doe.md").read_text()
    resume = parse(md)
    assert resume.title == "Jane Doe — Senior Product Manager"
    assert resume.theme == Theme.dark
    assert resume.page_mode.value == "two"
    assert resume.crafted_footer is True


def test_parse_full_resume():
    md = (FIXTURES / "jane_doe.md").read_text()
    resume = parse(md)
    assert resume.name == "Jane Doe"
    assert resume.title_line == "Senior Product Manager"
    assert resume.executive_profile is not None
    assert "Product leader" in resume.executive_profile
    assert resume.core_expertise is not None


def test_parse_work_history():
    md = (FIXTURES / "jane_doe.md").read_text()
    resume = parse(md)
    assert len(resume.companies) == 3  # Acme Corp, TechCorp, DataFirst
    acme = resume.companies[0]
    assert acme.name == "Acme Corp"
    assert acme.location == "San Francisco, CA"
    assert len(acme.positions) == 2  # Senior PM, PM
    assert acme.positions[0].title == "Senior Product Manager"


def test_parse_dates():
    md = (FIXTURES / "jane_doe.md").read_text()
    resume = parse(md)
    first = resume.companies[0].positions[0]
    assert first.start_date == "Jun 2021"
    assert first.end_date == "Present"


def test_parse_bullets():
    md = (FIXTURES / "jane_doe.md").read_text()
    resume = parse(md)
    first = resume.companies[0].positions[0]
    assert len(first.bullets) >= 3
    assert "**$25MM+**" in first.bullets[0]  # bold preserved


def test_parse_skills():
    md = (FIXTURES / "jane_doe.md").read_text()
    resume = parse(md)
    assert len(resume.technical_skills) >= 4
    assert resume.technical_skills[0].category == "Product & strategy"


def test_parse_education():
    md = (FIXTURES / "jane_doe.md").read_text()
    resume = parse(md)
    assert len(resume.education) >= 1
    assert "Berkeley" in resume.education[0].institution


def test_parse_no_frontmatter():
    """Should handle markdown without frontmatter gracefully."""
    md = "# Test\n**Test Title**\n\n## Section\n\nContent"
    resume = parse(md)
    assert resume.name == "Test"
    assert resume.theme == Theme.dark  # default


def test_parse_html_comments():
    """HTML comments should be stripped, not included in content."""
    md = "# Name\n**Title**\n\n## Executive Profile\n<!-- secret -->\nText"
    resume = parse(md)
    assert resume.executive_profile is not None
    assert "secret" not in resume.executive_profile
