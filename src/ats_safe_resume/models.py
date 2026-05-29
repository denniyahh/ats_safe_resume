"""Pydantic data models for resume representation."""

import re
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field


class Theme(str, Enum):
    dark = "dark"
    navy = "navy"
    teal = "teal"
    burgundy = "burgundy"
    minimal = "minimal"


class PageMode(str, Enum):
    one = "one"
    two = "two"


class ContactInfo(BaseModel):
    """Parsed from the contact line under the title."""
    city_state: Optional[str] = None       # "San Francisco, CA"
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    website: Optional[str] = None
    other: list[str] = Field(default_factory=list)  # Unclassified segments

    def to_ats_string(self) -> str:
        """ATS-safe pipe-separated string: City, State | email | phone | ..."""
        parts = [self.city_state] if self.city_state else []
        if self.email: parts.append(self.email)
        if self.phone: parts.append(self.phone)
        if self.linkedin: parts.append(self.linkedin)
        if self.github: parts.append(self.github)
        if self.website: parts.append(self.website)
        parts.extend(self.other)
        return " · ".join(p for p in parts if p)


class Position(BaseModel):
    """A single role within a company."""
    title: str                                    # "Senior Product Manager"
    subtitle: Optional[str] = None                # "Platform & Data Products"
    start_date: Optional[str] = None              # "Jun 2021"
    end_date: Optional[str] = None                # "Present" or "May 2021"
    summary: Optional[str] = None                 # Un-bulleted paragraph
    bullets: list[str] = Field(default_factory=list)


class Company(BaseModel):
    """An employer with one or more positions."""
    name: str                                     # "Acme Corp"
    location: Optional[str] = None                # "San Francisco, CA"
    url: Optional[str] = None                     # https://www.acmecorp.com
    positions: list[Position] = Field(default_factory=list)


class SkillCategory(BaseModel):
    """A skill group with category name and inline skills."""
    category: str                                 # "Product & strategy"
    skills: str                                   # "Roadmap planning, OKR frameworks, ..."


class Education(BaseModel):
    """An education entry."""
    institution: str                              # "University of California, Berkeley"
    degree: Optional[str] = None                  # "B.S. Business Administration"
    details: Optional[str] = None                 # "Minor in Computer Science"
    years: Optional[str] = None                   # "2010 - 2014"


class Resume(BaseModel):
    """Single canonical representation of a resume.

    This is the ONLY data model in the system. Every renderer reads
    from this model. The parser produces it. The CLI passes it.
    """
    # Frontmatter
    title: str = ""
    author: str = ""
    theme: Theme = Theme.dark
    page_mode: PageMode = PageMode.two
    crafted_footer: bool = True

    # Body
    name: Optional[str] = None
    title_line: Optional[str] = None               # "Senior Product Manager"
    contact: Optional[ContactInfo] = None
    executive_profile: Optional[str] = None
    core_expertise: Optional[str] = None
    companies: list[Company] = Field(default_factory=list)
    technical_skills: list[SkillCategory] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)

    # ---------- helpers ----------

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Remove ** and * markers from text."""
        from ats_safe_resume.inline_md import strip_markdown
        return strip_markdown(text)

    @staticmethod
    def _normalize_date(date_str: Optional[str]) -> Optional[str]:
        """Convert display date to ISO-ish for JSON Resume.

        "Jun 2021" -> "2021-06-01"
        "Present"  -> None (JSON Resume uses None for current)
        """
        if not date_str:
            return None
        if date_str.lower() == "present":
            return None
        return date_str  # Keep as-is for now; renderers use the display string

    @staticmethod
    def _parse_city(city_state: Optional[str]) -> Optional[str]:
        """Extract city from 'City, State' string."""
        if not city_state:
            return None
        return city_state.split(",")[0].strip()

    def _parse_profiles(self) -> list[dict]:
        """Extract network profiles from ContactInfo."""
        profiles = []
        c = self.contact
        if not c:
            return profiles
        if c.linkedin:
            profiles.append({
                "network": "LinkedIn",
                "username": c.linkedin.split("/")[-1] if "/" in c.linkedin else c.linkedin,
                "url": c.linkedin,
            })
        if c.github:
            profiles.append({
                "network": "GitHub",
                "username": c.github.split("/")[-1] if "/" in c.github else c.github,
                "url": c.github,
            })
        return profiles

    # ---------- JSON Resume export ----------

    def to_json_resume(self) -> dict:
        """Export to JSON Resume v1.0.0 schema."""
        work = []
        for company in self.companies:
            for position in company.positions:
                work.append({
                    "name": company.name,
                    "location": company.location,
                    "position": position.title,
                    "url": company.url,
                    "startDate": self._normalize_date(position.start_date),
                    "endDate": self._normalize_date(position.end_date),
                    "summary": self._strip_markdown(position.summary) if position.summary else None,
                    "highlights": [self._strip_markdown(b) for b in position.bullets],
                })

        skills = [{"name": s.category, "keywords": [k.strip() for k in s.skills.split(",")]} for s in self.technical_skills]
        if self.core_expertise:
            skills.insert(0, {"name": "Core Expertise", "keywords": [k.strip() for k in self.core_expertise.split("·")]})

        return {
            "$schema": "https://jsonresume.org/schema/",
            "basics": {
                "name": self.name,
                "label": self.title_line,
                "summary": self._strip_markdown(self.executive_profile) if self.executive_profile else None,
                "email": self.contact.email if self.contact else None,
                "phone": self.contact.phone if self.contact else None,
                "url": self.contact.website if self.contact else None,
                "location": {
                    "city": self._parse_city(self.contact.city_state) if self.contact else None,
                    "countryCode": None,
                },
                "profiles": self._parse_profiles(),
            },
            "work": work,
            "skills": skills,
            "education": [{
                "institution": e.institution,
                "area": e.details,
                "studyType": e.degree,
                "startDate": None,
                "endDate": None,
            } for e in self.education],
        }
