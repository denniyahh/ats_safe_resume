"""PDF renderer using Typst."""

from pathlib import Path
import re

import typst

from ats_safe_resume.models import Resume
from ats_safe_resume.renderers.base import BaseRenderer
from ats_safe_resume import inline_md


def _escape_typst(text: str) -> str:
    """Escape Typst-special characters in plain text.

    Only escapes characters that cause *parser* errors (not formatting sigils
    like * and _ which are intentionally used by inline_md.to_typst()).
    """
    text = text.replace("\\", "\\\\")
    for ch in "@#$":
        text = text.replace(ch, "\\" + ch)
    text = text.replace("<", "\\<")
    text = text.replace(">", "\\>")
    return text


def _escape_typst_all(text: str) -> str:
    """Escape all Typst-special characters including * and _.
    Used for plain-text fields that don't go through to_typst().
    """
    text = _escape_typst(text)
    for ch in "*_`":
        text = text.replace(ch, "\\" + ch)
    return text


def _e(text: str) -> str:
    """Shortcut: escape then convert inline markdown."""
    return inline_md.to_typst(_escape_typst(text))


def _esafe(text: str | None) -> str:
    """Escape text or return empty string for None."""
    if text is None:
        return ""
    return _escape_typst_all(text)


class PdfRenderer(BaseRenderer):
    """Render resume to PDF using Typst."""

    def render(self, resume: Resume, output_path: Path) -> None:
        typst_source = self._render_typst(resume)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".typ", mode="w", delete=False) as f:
            f.write(typst_source)
            temp_path = Path(f.name)
        try:
            pdf_data = typst.compile(str(temp_path), format="pdf")
            output_path.write_bytes(pdf_data)
        finally:
            temp_path.unlink(missing_ok=True)

    def _render_typst(self, resume: Resume) -> str:
        """Generate Typst markup from Resume model."""
        lines = []

        # Page setup
        lines.append('#set page("a4", margin: (left: 0.7in, right: 0.7in, top: 0.5in, bottom: 0.5in))')
        lines.append('#set text(font: "Source Sans 3", size: 10pt)')
        lines.append("")

        # Name
        if resume.name:
            lines.append(f'#align(center, text(size: 18pt, weight: "bold")[{_esafe(resume.name)}])')

        # Title line
        if resume.title_line:
            lines.append(f'#align(center, text(size: 11pt, weight: "semibold")[{_esafe(resume.title_line)}])')

        # Contact
        if resume.contact:
            contact_text = _esafe(resume.contact.to_ats_string())
            lines.append(f"#align(center, text(size: 9pt)[{contact_text}])")

        lines.append("")

        # Sections
        if resume.executive_profile:
            lines.append("= Executive Profile")
            lines.append(f"#text(size: 10pt)[{_e(resume.executive_profile)}]")
            lines.append("")

        if resume.core_expertise:
            lines.append("= Core Expertise")
            lines.append(f"#text(size: 10pt)[{_e(resume.core_expertise)}]")
            lines.append("")

        if resume.companies:
            lines.append("= Professional Experience")
            lines.append("")
            for company in resume.companies:
                for position in company.positions:
                    loc = f" — {_esafe(company.location)}" if company.location else ""
                    lines.append(f"== {_esafe(company.name)}{loc}")

                    title_line = f"*{_esafe(position.title)}*"
                    if position.subtitle:
                        title_line += f" — {_esafe(position.subtitle)}"
                    if position.start_date:
                        dates = f"({_esafe(position.start_date)} – {_esafe(position.end_date) or 'Present'})"
                        title_line += f" _{dates}_"
                    lines.append(f"#text(size: 10pt)[{title_line}]")

                    if position.summary:
                        lines.append(f"#text(size: 10pt)[{_e(position.summary)}]")

                    for bullet in position.bullets:
                        lines.append(f"- {_e(bullet)}")

                    lines.append("")

        if resume.technical_skills:
            lines.append("= Technical Skills")
            for skill in resume.technical_skills:
                cat = _esafe(skill.category)
                skills_text = _esafe(skill.skills)
                lines.append(f"#text(size: 10pt)[*{cat}:* {skills_text}]")
            lines.append("")

        if resume.education:
            lines.append("= Education")
            for edu in resume.education:
                edu_text = f"*{_esafe(edu.institution)}*"
                if edu.degree:
                    edu_text += f" — {_esafe(edu.degree)}"
                if edu.details:
                    edu_text += f", {_esafe(edu.details)}"
                lines.append(f"#text(size: 10pt)[{edu_text}]")
            lines.append("")

        if resume.crafted_footer:
            lines.append('#align(center, text(size: 8pt, fill: gray)[crafted with #link("https://github.com/denniyahh/ats_safe_resume")[ats_safe_resume]])')

        return "\n".join(lines)
