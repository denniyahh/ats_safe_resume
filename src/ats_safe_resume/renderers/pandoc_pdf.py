"""PDF renderer using Pandoc + LuaLaTeX + Eisvogel template.

Converts the Resume model back to markdown and drives pandoc
to produce the exact v1-quality PDF the user expects.
"""

import re
import subprocess
import tempfile
from pathlib import Path

from ats_safe_resume.models import Resume
from ats_safe_resume.renderers.base import BaseRenderer

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent.parent
TEMPLATES_DIR = SCRIPT_DIR / "templates"
THEMES_DIR = SCRIPT_DIR / "themes"
PREAMBLE = SCRIPT_DIR / "resume-preamble.tex"


class PandocPdfRenderer(BaseRenderer):
    """Render resume to PDF using Pandoc + LuaLaTeX + Eisvogel template.

    This recovers the v1 build path: model → markdown → pandoc → PDF.
    """

    def render(self, resume: Resume, output_path: Path) -> None:
        # 1. Generate markdown with frontmatter from the Resume model
        md_content = self._resume_to_markdown(resume)

        # 2. Write to a temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(md_content)
            md_path = Path(f.name)

        try:
            # 3. Build the pandoc command
            theme_name = resume.theme.value if resume.theme else "dark"
            theme_file = THEMES_DIR / f"{theme_name}.tex"

            cmd = [
                "pandoc",
                str(md_path),
                "--pdf-engine=lualatex",
                f"--template={TEMPLATES_DIR / 'eisvogel.latex'}",
                "-f", "markdown+smart",
                "-o", str(output_path),
                "--metadata=title:" + (resume.title or "Resume"),
                "--metadata=author:" + (resume.author or ""),
                f"--include-in-header={PREAMBLE}",
            ]

            if theme_file.exists():
                cmd.append(f"--include-in-header={theme_file}")

            # Page mode (one → tighter, two → standard)
            if resume.page_mode and resume.page_mode.value == "one":
                cmd += ["-V", "fontsize=9.5pt", "-V", "geometry:left=0.7in,right=0.7in,top=0.4in,bottom=0.4in"]
            else:
                cmd += ["-V", "fontsize=10pt", "-V", "geometry:left=0.7in,right=0.7in,top=0.5in,bottom=0.5in"]

            cmd += ["-V", "linkcolor=blue"]

            # Crafted footer
            if resume.crafted_footer:
                cmd += ["--include-after-body", str(SCRIPT_DIR / "crafted-footer.tex")]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise RuntimeError(f"Pandoc failed:\n{result.stderr}")

        finally:
            md_path.unlink(missing_ok=True)

    def _resume_to_markdown(self, resume: Resume) -> str:
        """Convert a Resume model back into markdown suitable for pandoc."""
        lines = []

        # ── Frontmatter ──────────────────────────────────────────
        lines.append("---")
        lines.append(f"title: \"{_yml_escape(resume.title or '')}\"")
        lines.append(f"author: \"{_yml_escape(resume.author or '')}\"")
        lines.append(f"theme: {resume.theme.value if resume.theme else 'dark'}")
        lines.append(f"page_mode: {resume.page_mode.value if resume.page_mode else 'two'}")
        lines.append(f"crafted_footer: {str(resume.crafted_footer).lower()}")
        lines.append("disable-header-and-footer: true")
        lines.append("---")
        lines.append("")

        # ── Name ─────────────────────────────────────────────────
        if resume.name:
            lines.append(f"# {_md_escape(resume.name)}")
            lines.append("")

        # ── Title line ───────────────────────────────────────────
        if resume.title_line:
            lines.append(f"**{_md_escape(resume.title_line)}**")
            lines.append("")

        # ── Contact ──────────────────────────────────────────────
        if resume.contact:
            contact_parts = []
            if resume.contact.city_state:
                contact_parts.append(_escape_latex_special(resume.contact.city_state))
            if resume.contact.email:
                contact_parts.append(f"[{resume.contact.email}](mailto:{resume.contact.email})")
            if resume.contact.phone:
                contact_parts.append(_escape_latex_special(resume.contact.phone))
            if resume.contact.linkedin:
                contact_parts.append(f"[LinkedIn]({resume.contact.linkedin})")
            if resume.contact.github:
                contact_parts.append(f"[Github]({resume.contact.github})")
            if resume.contact.website:
                contact_parts.append(f"[Website]({resume.contact.website})")
            for other in resume.contact.other:
                # Try to extract URL from markdown link
                m = re.match(r'\[(.+)\]\((.+)\)', other)
                if m:
                    contact_parts.append(f"[{m.group(1)}]({m.group(2)})")
                else:
                    contact_parts.append(_escape_latex_special(other))
            lines.append(" · ".join(contact_parts))
            lines.append("")

        # ── Executive Profile ────────────────────────────────────
        if resume.executive_profile:
            lines.append("## Executive Profile")
            lines.append("")
            lines.append(_escape_latex_special(resume.executive_profile))
            lines.append("")

        # ── Core Expertise ───────────────────────────────────────
        if resume.core_expertise:
            lines.append("## Core Expertise")
            lines.append("")
            lines.append(_escape_latex_special(resume.core_expertise))
            lines.append("")

        # ── Professional Experience ──────────────────────────────
        if resume.companies:
            lines.append("## Professional Experience")
            lines.append("")
            for company in resume.companies:
                if company.url:
                    lines.append(f"### [{_escape_latex_special(company.name)}]({company.url})"
                                 f"{' — ' + _escape_latex_special(company.location) if company.location else ''}")
                else:
                    # No primary URL — render name as-is (may contain inline markdown links)
                    lines.append(f"### {_escape_latex_special(company.name)}"
                                 f"{' — ' + _escape_latex_special(company.location) if company.location else ''}")
                lines.append("")

                for position in company.positions:
                    title_line = f"**{_escape_latex_special(position.title)}**"
                    if position.subtitle:
                        # Split subtitle into bold and non-bold parts
                        # e.g. "Trillium Trading, LLC (2005–2007)" → bold company, plain dates
                        m = re.match(r'^(.*?)\s*(\(\d{4}.*)', position.subtitle)
                        if m:
                            title_line += f" — **{_escape_latex_special(m.group(1))}** {_escape_latex_special(m.group(2))}"
                        else:
                            title_line += f" — **{_escape_latex_special(position.subtitle)}**"
                    if position.start_date:
                        end = position.end_date or "Present"
                        title_line += f" \\hfill \\textit{{{position.start_date} – {end}}}"
                    lines.append(title_line)
                    # blank line before bullets (markdown requires this)
                    lines.append("")

                    # For Earlier Experience-style entries (no bullets, has summary):
                    # merge summary into same paragraph as title
                    if position.summary and not position.bullets:
                        lines[-2] = lines[-2] + " " + _escape_latex_special(position.summary)
                    elif position.summary:
                        lines.append(_escape_latex_special(position.summary))

                    if position.bullets:
                        for bullet in position.bullets:
                            stripped = re.sub(r'\*\*(.+?)\*\*', r'**\1**', bullet)
                            lines.append(f"- {_escape_latex_special(stripped)}")
                    lines.append("")  # blank after each position

                lines.append("")  # blank line between companies

        # ── Technical Skills ─────────────────────────────────────
        if resume.technical_skills:
            lines.append("## Technical Skills")
            lines.append("")
            for skill in resume.technical_skills:
                lines.append(f"**{_escape_latex_special(skill.category)}:** {_escape_latex_special(skill.skills)}")
                lines.append("")

        # ── Education ────────────────────────────────────────────
        if resume.education:
            lines.append("## Education")
            lines.append("")
            for edu in resume.education:
                edu_line = f"**{_escape_latex_special(edu.institution)}**"
                if edu.degree:
                    edu_line += f" — {_escape_latex_special(edu.degree)}"
                if edu.details:
                    edu_line += f", {_escape_latex_special(edu.details)}"
                lines.append(edu_line)
                lines.append("")

        return "\n".join(lines).strip() + "\n"


def _escape_latex_special(s: str) -> str:
    """Escape backslashes so pandoc doesn't pass them through as TeX control sequences.

    Pandoc's markdown parser passes literal backslashes through to LaTeX,
    which then interprets them as undefined control sequences.
    Doubling them (\\) makes pandoc output \\textbackslash{} instead.
    """
    return s.replace("\\", "\\\\")


def _yml_escape(s: str) -> str:
    """Escape YAML special characters in frontmatter values."""
    return s.replace('"', '\\"')


def _md_escape(s: str) -> str:
    """Escape markdown/LaTeX special characters in plain text fields."""
    s = _escape_latex_special(s)  # backslash → pandoc TeX control sequence
    s = s.replace("[", r"\[").replace("]", r"\]")
    return s
