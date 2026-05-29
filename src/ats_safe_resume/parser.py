"""Markdown resume parser.

Parses the existing markdown format (frontmatter + body) into a Resume model.
Users keep writing markdown — no UX change.
"""

import re
import yaml

from ats_safe_resume.models import (
    Resume, Theme, PageMode, ContactInfo,
    Company, Position, SkillCategory, Education,
)


def parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter between --- blocks."""
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        return {}
    return yaml.safe_load(m.group(1)) or {}


def parse(markdown_text: str) -> Resume:
    """Parse markdown resume into validated Resume model."""
    # --- Frontmatter ---
    front = parse_frontmatter(markdown_text)

    resume = Resume(
        title=front.get("title", ""),
        author=front.get("author", ""),
        theme=Theme(front.get("theme", "dark")),
        page_mode=PageMode(front.get("page_mode", "two")),
        crafted_footer=front.get("crafted_footer", True),
    )

    # Strip frontmatter block from body
    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', markdown_text, count=1, flags=re.DOTALL)

    # Strip HTML comments
    body = re.sub(r'<!--.*?-->', '', body, flags=re.DOTALL)

    # Split into lines
    lines = body.strip().split('\n')
    i = 0
    n = len(lines)

    # Step 1: Name (H1)
    while i < n:
        line = lines[i].strip()
        if line.startswith('# ') and not line.startswith('## '):
            resume.name = line[2:].strip()
            i += 1
            break
        i += 1

    # Step 2: Title line (first bold line after name)
    while i < n:
        line = lines[i].strip()
        m = re.match(r'^\*\*(.+?)\*\*$', line)
        if m:
            resume.title_line = m.group(1).strip()
            i += 1
            break
        if line and not line.startswith('#'):
            # Not a bold title, skip
            break
        i += 1

    # Step 3: Contact line
    while i < n:
        line = lines[i].strip()
        if line and not line.startswith('#') and not line.startswith('-'):
            # This is the contact line
            resume.contact = _parse_contact(line)
            i += 1
            break
        if line.startswith('##'):
            break
        i += 1

    # Step 4: Parse sections by H2
    sections_text = _split_sections(lines[i:])
    for heading, content in sections_text.items():
        h_lower = heading.lower().strip()
        if "executive profile" in h_lower:
            resume.executive_profile = _join_paragraphs(content)
        elif "core expertise" in h_lower:
            resume.core_expertise = " ".join(content).strip()
        elif "professional experience" in h_lower:
            resume.companies = _parse_companies(content)
        elif "technical skills" in h_lower:
            resume.technical_skills = _parse_skills(content)
        elif "education" in h_lower:
            resume.education = _parse_education(content)

    return resume


# ---------- section helpers ----------

def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    """Split body lines into sections by H2 headings."""
    sections: dict[str, list[str]] = {}
    current_heading: str | None = None
    current_content: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('## ') and not stripped.startswith('### '):
            if current_heading:
                sections[current_heading] = current_content
            current_heading = stripped[3:].strip()
            current_content = []
        elif current_heading is not None:
            current_content.append(line)

    if current_heading:
        sections[current_heading] = current_content

    return sections


def _join_paragraphs(lines: list[str]) -> str:
    """Join section content into a single paragraph string."""
    text = " ".join(l.strip() for l in lines if l.strip())
    return text


def _strip_markdown_links(text: str) -> str:
    """Convert [text](url) and [text][ref] to just text."""
    return re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)


# ---------- contact parsing ----------

def _parse_contact(line: str) -> ContactInfo:
    """Parse contact line separated by · characters."""
    segments = [s.strip() for s in line.split('·')]
    contact = ContactInfo()

    for seg in segments:
        if not seg:
            continue
        # Detect email
        if '@' in seg:
            # Strip markdown link if present
            m = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', seg)
            if m:
                contact.email = m.group(0)
        # Detect phone
        elif re.search(r'\d{3}.*\d{3}.*\d{4}', seg):
            contact.phone = seg
        # Detect LinkedIn
        elif 'linkedin.com' in seg.lower():
            m = re.search(r'https?://[^\s)]+', seg)
            contact.linkedin = m.group(0) if m else seg
        # Detect GitHub
        elif 'github.com' in seg.lower():
            m = re.search(r'https?://[^\s)]+', seg)
            contact.github = m.group(0) if m else seg
        # Detect website
        elif seg.startswith('http') or '.com' in seg:
            m = re.search(r'https?://[^\s)]+', seg)
            contact.website = m.group(0) if m else seg
        # City, State (contains comma)
        elif ',' in seg:
            contact.city_state = seg
        else:
            contact.other.append(seg)

    return contact


# ---------- work history parsing ----------

def _parse_companies(lines: list[str]) -> list[Company]:
    """Parse Professional Experience section into companies."""
    companies: list[Company] = []
    current_company: Company | None = None
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].strip()

        # H3 heading = new company
        if line.startswith('### '):
            heading = line[4:].strip()
            company = Company(name="")  # name set below
            # Extract URL from markdown link at start of heading: [Name](URL) — Location
            m = re.match(r'\[(.+?)\]\((.+?)\)\s*[—–-]\s*(.+)', heading)
            if m:
                company.name = m.group(1)
                company.url = m.group(2)
                company.location = m.group(3).strip()
            else:
                # Name — Location (may contain markdown links inline)
                # Only split on em/en dash or spaced hyphen (not word-internal hyphens)
                parts = re.split(r'\s*[—–]\s*|\s+-\s+', heading, maxsplit=1)
                company.name = parts[0].strip()
                if len(parts) > 1:
                    company.location = parts[1].strip()
                # Extract URL from embedded markdown link: [text](url)
                url_m = re.search(r'\[([^\]]+)\]\(([^)]+)\)', heading)
                if url_m:
                    company.url = url_m.group(2)
            # Clean any remaining markdown link syntax: [text](url) → text
            company.name = _strip_markdown_links(company.name)
            if company.location:
                company.location = _strip_markdown_links(company.location)
            current_company = company
            companies.append(company)
            i += 1
            continue

        # Bold line = new position title
        if line.startswith('**') and '**' in line[2:]:
            if current_company is not None:
                pos = _parse_position_line(line, lines, i)
                current_company.positions.append(pos)
                # Skip past the bullets we consumed
                skip_to = _find_next_position_or_end(lines, i)
                # Parse bullets and summary between i+1 and skip_to
                _parse_bullets_and_summary(lines, i+1, skip_to, current_company.positions[-1])
                i = skip_to
                continue
        # Non-bold, non-bullet line = inline position (e.g. Earlier Experience format)
        elif line.strip() and not line.strip().startswith('-') and not line.strip().startswith('*') and current_company is not None and current_company.name and line[0].isupper():
            pos = _parse_position_line(line, lines, i)
            current_company.positions.append(pos)
            skip_to = _find_next_position_or_end(lines, i)
            _parse_bullets_and_summary(lines, i+1, skip_to, current_company.positions[-1])
            i = skip_to
            continue
        i += 1

    return companies


def _parse_position_line(line: str, lines: list[str], i: int) -> Position:
    """Parse a bold position title line."""
    pos = Position(title="")

    # Extract bold title: **text**
    m = re.match(r'\*\*(.+?)\*\*\s*(.*)', line)
    if m:
        title_text = m.group(1)
        rest = m.group(2).strip()

        # Title — Subtitle
        if '—' in title_text or '–' in title_text:
            parts = re.split(r'\s*[—–-]\s*', title_text, maxsplit=1)
            pos.title = parts[0].strip()
            pos.subtitle = parts[1].strip()
        else:
            pos.title = title_text

        # Remaining text might be subtitle
        if rest:
            if rest.startswith('—') or rest.startswith('–') or rest.startswith('-'):
                subtitle_add = rest[1:].strip()
            else:
                subtitle_add = rest
            if pos.subtitle:
                # Append to existing subtitle (don't overwrite)
                pos.subtitle = pos.subtitle + " " + subtitle_add
            else:
                pos.subtitle = subtitle_add

    else:
        # No bold at start — treat whole line as inline position text
        # Format: Title — Company/Subtitle (dates) description
        stripped = line.strip()
        # Split on first bold group if present in the middle: Title — **Company** (dates) desc
        bold_m = re.search(r'\*\*(.+?)\*\*', stripped)
        if bold_m:
            before = stripped[:bold_m.start()].strip().rstrip('—–-').strip()
            after = stripped[bold_m.end():].strip()
            pos.title = before
            pos.subtitle = f"{bold_m.group(1)} {after}".strip()
        else:
            # No bold at all — split on first em/en dash for title
            parts = re.split(r'\s*[—–]\s*', stripped, maxsplit=1)
            pos.title = parts[0].strip()
            if len(parts) > 1:
                pos.subtitle = parts[1].strip()

    return pos


def _find_next_position_or_end(lines: list[str], start: int) -> int:
    """Find index of next position line or end of section."""
    i = start + 1
    n = len(lines)
    while i < n:
        line = lines[i].strip()
        if line.startswith('### '):
            return i
        if line.startswith('**') and '**' in line[2:]:
            return i
        i += 1
    return n


def _parse_bullets_and_summary(lines: list[str], start: int, end: int, position: Position) -> None:
    """Parse bullet points and date line between position header and next position."""
    i = start
    while i < end:
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Italic date line: *Jun 2021 – Present* or _Jun 2021 – Present_
        m = re.match(r'^[*_](.+?)[*_]$', line)
        if m:
            date_text = m.group(1)
            parts = re.split(r'\s*[–-]\s*', date_text, maxsplit=1)
            if len(parts) == 2:
                position.start_date = parts[0].strip()
                position.end_date = parts[1].strip()
            else:
                position.start_date = parts[0].strip()
            i += 1
            continue

        # Bullet points
        if line.startswith('- '):
            position.bullets.append(line[2:].strip())
        elif line.startswith('* ') and not line.startswith('**'):
            position.bullets.append(line[2:].strip())
        elif line.startswith('-'):
            # Bullet without space: just consume the dash
            position.bullets.append(line[1:].strip())
        else:
            # Non-bullet line before bullets = summary paragraph
            if not position.bullets:
                position.summary = (position.summary or "") + " " + line
                position.summary = position.summary.strip()

        i += 1


# ---------- skills parsing ----------

def _parse_skills(lines: list[str]) -> list[SkillCategory]:
    """Parse Technical Skills section."""
    skills: list[SkillCategory] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Bold category: **Category:** skills, skills
        # The colon may have a space before it: **foo:** bar or **foo **: bar
        m = re.match(r'\*\*(.+?)\*\*\s*(.*)', stripped)
        if m:
            cat = m.group(1).strip()
            rest = m.group(2).strip()
            if cat.endswith(':'):
                cat = cat.rstrip(':').strip()
            elif rest.startswith(':'):
                rest = rest[1:].strip()
            if cat and rest:
                skills.append(SkillCategory(category=cat, skills=rest))
    return skills


# ---------- education parsing ----------

def _parse_education(lines: list[str]) -> list[Education]:
    """Parse Education section."""
    educations: list[Education] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Bold institution: **Institution** — Degree, Details
        m = re.match(r'\*\*(.+?)\*\*\s*(.*)', stripped)
        if m:
            institution_text = m.group(1).strip()
            rest = m.group(2).strip()

            edu = Education(institution=institution_text)

            if rest:
                # Remove leading dash/em-dash
                rest = re.sub(r'^[—–-]\s*', '', rest).strip()
                # Split degree and details
                parts = rest.split(',', maxsplit=1)
                edu.degree = parts[0].strip()
                if len(parts) > 1:
                    edu.details = parts[1].strip()

            educations.append(edu)

    return educations
