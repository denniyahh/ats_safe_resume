# tests/test_models.py
import pytest
from ats_safe_resume.models import (
    Resume, Theme, PageMode, ContactInfo,
    Company, Position, SkillCategory, Education
)


def test_default_theme():
    r = Resume()
    assert r.theme == Theme.dark


def test_default_page_mode():
    r = Resume()
    assert r.page_mode == PageMode.two


def test_default_crafted_footer():
    r = Resume()
    assert r.crafted_footer is True


def test_company_with_positions():
    pos = Position(
        title="Senior PM",
        start_date="Jun 2021",
        end_date="Present",
        bullets=["Grew revenue **$5MM** to **$25MM+**"]
    )
    company = Company(name="Acme Corp", positions=[pos])
    assert len(company.positions) == 1
    assert company.positions[0].title == "Senior PM"


def test_to_json_resume_basic():
    r = Resume(name="Jane Doe", title_line="Senior PM")
    j = r.to_json_resume()
    assert j["basics"]["name"] == "Jane Doe"
    assert j["basics"]["label"] == "Senior PM"


def test_to_json_resume_work():
    r = Resume(
        name="Jane Doe",
        companies=[Company(
            name="Acme Corp",
            positions=[Position(
                title="Senior PM",
                start_date="Jun 2021",
                end_date="Present",
                summary="Led the data products team.",
                bullets=["Grew revenue"]
            )]
        )]
    )
    j = r.to_json_resume()
    assert len(j["work"]) == 1
    assert j["work"][0]["name"] == "Acme Corp"
    assert j["work"][0]["summary"] == "Led the data products team."


def test_contact_to_ats_string():
    c = ContactInfo(city_state="SF, CA", email="j@e.com", phone="555-0000")
    s = c.to_ats_string()
    assert " · " in s
    assert "SF, CA" in s


def test_education_defaults():
    e = Education(institution="UC Berkeley")
    assert e.degree is None
