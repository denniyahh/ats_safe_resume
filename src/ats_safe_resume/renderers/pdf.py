"""PDF renderer using Typst — v1 Eisvogel-compatible layout."""

from pathlib import Path
import tempfile
import re

import typst

from ats_safe_resume.models import Resume
from ats_safe_resume.renderers.base import BaseRenderer
from ats_safe_resume import inline_md


# ── Escape helpers ────────────────────────────────────────────────

def _escape(text: str) -> str:
    """Escape Typst parser-special characters: @ # $ < > \\"""
    text = text.replace("\\", "\\\\")
    for ch in "@#$":
        text = text.replace(ch, "\\" + ch)
    text = text.replace("<", "\\<")
    text = text.replace(">", "\\>")
    return text


def _escape_all(text: str) -> str:
    """Escape all Typst-special chars including * _ ` (plain text)."""
    text = _escape(text)
    for ch in "*_`":
        text = text.replace(ch, "\\" + ch)
    return text


def _md(text: str) -> str:
    """Convert **bold**→*bold* and *italic*→_italic_ for Typst."""
    text = _escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'_\1_', text)
    return text


def _strip_links(text: str) -> str:
    """Remove [text](url) markdown links."""
    return re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)


def _s(text: str | None) -> str:
    """Safe plain text, returns '' for None."""
    return _escape_all(text) if text else ''


ACCENT = "#555555"


class PdfRenderer(BaseRenderer):
    """Render resume to PDF using Typst, v1-compatible Eisvogel layout."""

    def render(self, resume: Resume, output_path: Path) -> None:
        src = self._render_typst(resume)
        with tempfile.NamedTemporaryFile(suffix=".typ", mode="w", delete=False) as f:
            f.write(src)
            tp = Path(f.name)
        try:
            pdf = typst.compile(str(tp), format="pdf")
            output_path.write_bytes(pdf)
        finally:
            tp.unlink(missing_ok=True)

    def _render_typst(self, resume: Resume) -> str:
        """Build Typst markup matching v1 Eisvogel layout."""
        L = []

        # ── Page & style setup ──────────────────────────────────
        L.append('#set page("a4", margin: (left: 0.7in, right: 0.7in, top: 0.5in, bottom: 0.5in))')
        L.append('#set text(font: "Source Sans 3", size: 10pt)')
        L.append('#set par(leading: 0.6em)')
        L.append('#set heading(numbering: none)')
        L.append('#show heading.where(level: 1): it => {')
        L.append('  set text(fill: black, weight: "bold", size: 10pt)')
        L.append('  v(0.5em)')
        L.append('  it')
        L.append('  line(length: 100%, stroke: 0.5pt + gray)')
        L.append('  v(0.15em)')
        L.append('}')
        L.append('#show heading.where(level: 2): it => {')
        L.append('  v(0.1em)')
        L.append('  it')
        L.append('}')
        L.append('#show list: set text(size: 10pt)')

        L.append('')

        # ── Name block ─────────────────────────────────────────
        if resume.name:
            L.append(f'#text(size: 18pt, weight: "bold")[{_escape_all(resume.name)}]')
        L.append('#v(1.4em)')

        if resume.title_line:
            L.append(f'#text(size: 10pt, weight: "bold")[{_escape_all(resume.title_line)}]')
        L.append('#v(0.12em)')

        if resume.contact:
            c = _escape(resume.contact.to_ats_string())
            c = _strip_links(c)
            L.append(f'#text(size: 9pt)[{c}]')
        L.append('#v(0.6em)')

        # ── Sections ───────────────────────────────────────────
        if resume.executive_profile:
            L.append('= Executive Profile')
            L.append(f'{_md(resume.executive_profile)}')

        if resume.core_expertise:
            L.append('= Core Expertise')
            L.append(f'{_md(resume.core_expertise)}')

        if resume.companies:
            L.append('= Professional Experience')
            for company in resume.companies:
                for pos in company.positions:
                    L.append(f'== {_s(company.name)}  --  {_s(company.location)}'
                             if company.location else f'== {_s(company.name)}')
                    # Position line: title [+ subtitle] [+ dates inline, no parens]
                    parts = [f'*{_s(pos.title)}*']
                    if pos.subtitle:
                        parts.append(_s(pos.subtitle))
                    if pos.start_date:
                        ed = _s(pos.end_date) if pos.end_date else 'Present'
                        parts.append(f'_{_s(pos.start_date)}  --  {ed}_')
                    L.append('#text(size: 10pt)[' + '  --  '.join(parts) + ']')
                    if pos.summary:
                        L.append(_md(_strip_links(pos.summary)))
                    for bullet in pos.bullets:
                        L.append(f'-  {_md(_strip_links(bullet))}')
                    L.append('')

        if resume.technical_skills:
            L.append('= Technical Skills')
            for skill in resume.technical_skills:
                L.append(f'{_s(skill.category)}: {skill.skills}')
                L.append('')

        if resume.education:
            L.append('= Education')
            for edu in resume.education:
                ed = f'*{_s(edu.institution)}*'
                if edu.degree:
                    ed += f'  --  {_s(edu.degree)}'
                if edu.details:
                    ed += f', {_s(edu.details)}'
                L.append(f'#text(size: 10pt)[{ed}]')

        if resume.crafted_footer:
            L.append('#v(1em)')
            L.append('#align(center, text(size: 8pt, fill: gray)['
                     'crafted with #link("https://github.com/denniyahh/ats_safe_resume")[ats_safe_resume]])')

        return '\n'.join(L)
