# Architecture v2: Hybrid Markdown → JSON → Render Pipeline

> **Status:** Design Review (pre-implementation)
> **Review requested by:** Gemini (via Dennis)
> **Last updated:** 2026-05-28

---

## 1. Overview

### 1.1 Problem Statement

The current v1 pipeline drives 5 independent output formats through Pandoc + bash regex. Each format-path interprets the source markdown independently, producing inconsistent results for the same input. Bug history: title duplication (TXT/DOCX), double-escaped HTML entities (HTML), overwritten per-position dates (JSON), invisible footer links (PDF). Each new user resume permutation risks introducing another format-specific bug.

### 1.2 Solution

**Hybrid architecture:** Users edit markdown (no UX change). The build pipeline parses markdown once into a validated Pydantic model, exports it to JSON Resume format as the canonical intermediate, and renders all 5 output formats from that single JSON source.

```
resume.md ──► Pydantic Parser ──► resume.json ──┬──► PDF (Typst)
              (parse once)        (canonical)    ├──► DOCX (python-docx)
                                                  ├──► HTML (Jinja2)
                                                  ├──► TXT (Jinja2)
                                                  └──► JSON (identity)
```

### 1.3 Key Principles

1. **Parse once.** Every format reads from the same validated data model. A bug fix in the parser fixes all formats.
2. **Primacy of content.** Not a single word of content is ever dropped. Any unclassifiable markdown is safely captured in "escape hatch" fields to guarantee nothing goes missing.
3. **Graceful degradation.** We do not overengineer formats to look identical. Rich formatting (accent bars, inline bold) degrades gracefully to simpler formatting in less expressive formats (TXT, HTML, DOCX) without sacrificing content.
4. **Deterministic rendering.** Every renderer is a pure function of the data model. Same input = same output.
5. **Human-friendly input.** Users write markdown. They never touch JSON unless they choose to.
6. **Machine-friendly intermediate.** JSON Resume schema (jsonresume.org) is an open standard for resume data.
7. **Property-based testing.** Auto-generate thousands of random resumes and verify consistency across all formats.

---

## 2. Data Model

### 2.1 Pydantic Models (`src/ats_safe_resume/models.py`)

```python
from pydantic import BaseModel, Field, EmailStr, HttpUrl
from typing import Optional
from enum import Enum


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
    other: list[str] = Field(default_factory=list) # Unclassified segments

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
```

### 2.2 Date Storage Design Decision

Dates are stored as **strings**, not `date` objects. Rationale:

| Issue | date object | string |
|-------|-------------|--------|
| "Jun 2021" | Must parse, can fail | ✅ Store as-is |
| "Q1 2020" | Parse fails | ✅ Store as-is |
| "Expected 2025" | Parse fails | ✅ Store as-is |
| "2019 - 2020" | Parse fails | ✅ Store as-is |
| "Present" | Invalid date | ✅ Store as-is |
| ATS sorting requirement | Before:1900-01-01 | ✅ Parser normalizes "Present" to end-of-list |

**ATS sorting convention:** If a consumer needs to sort by date, the parser normalizes:
- `start_date` → ISO string for known formats (e.g. "Jun 2021" → "2021-06-01")
- `end_date` → ISO string, or "9999-12-31" for "Present"
- Original display string preserved alongside for rendering

### 2.3 JSON Resume Export (`Resume.to_json_resume()`)

Every `Resume` model exports to the [JSON Resume](https://jsonresume.org/schema/) schema via a method:

```python
class Resume(BaseModel):
    # ... fields above ...

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
                    "summary": position.summary,
                    "highlights": position.bullets,
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
            "education": [{
                "institution": e.institution,
                "area": e.details,
                "studyType": e.degree,
                "startDate": None,
                "endDate": None,
            } for e in self.education],
            "skills": skills,
        }
```

---

## 3. Markdown Parser (`src/ats_safe_resume/parser.py`)

### 3.1 Input Format

Users write the same markdown format as v1 (no UX change):

```markdown
---
title: "Jane Doe — Senior Product Manager"
author: "Jane Doe"
theme: dark
page_mode: two
crafted_footer: true
---

# Jane Doe
**Senior Product Manager**

San Francisco, CA · [jane@email.com](mailto:jane@email.com) · (555) 123-4567

## Executive Profile
Product leader with 10+ years...

## Core Expertise
Product strategy · AI/ML productization · Data platform design

## Professional Experience

### [Acme Corp](https://acme.com) — San Francisco, CA
<!-- Optional comment -->

**Senior Product Manager** — Platform & Data Products
*Jun 2021 – Present*

- Grew platform revenue from **$5MM** to **$25MM+**.
- Launched AI-powered analytics product.

**Product Manager** — Core Platform
*Aug 2019 – May 2021*

- Delivered first REST API product.

## Technical Skills

**Product & strategy:** Roadmap planning, OKR frameworks

**Data & analytics:** SQL, Python, A/B testing

## Education

**UC Berkeley** — B.S. Business Administration, Minor in CS
```

### 3.2 Parsing Algorithm

```python
def parse(markdown_text: str) -> Resume:
    """Parse markdown resume into validated Resume model."""

def parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter between --- blocks."""

def parse_body(text: str, resume: Resume) -> Resume:
    """Parse body sections into Resume model."""
```

**Step-by-step:**

1. **Frontmatter:** Split on first `---` block. Parse YAML with `yaml.safe_load()`.
2. **Strip comments:** Remove all `<!-- ... -->` from body.
3. **Name + title:** H1 line → `resume.name`. First bold line after H1 → `resume.title_line`.
4. **Contact line:** Line with `·` separators. Detect email (contains `@`), phone (contains digits + parens/dashes), URLs (`http` or `.com` pattern), city/state (comma pattern).
5. **Sections by H2 heading text:**
   - `"Executive Profile"` → paragraph text → `resume.executive_profile`
   - `"Core Expertise"` → inline text → `resume.core_expertise`
   - `"Professional Experience"` → parse work history
   - `"Technical Skills"` → parse skill categories
   - `"Education"` → parse education entries

6. **Work history parsing (most complex):**
   ```
   For each H3 heading (company):
     - Extract name: text before first link, or heading text
     - Extract URL: from markdown link in heading
     - Extract location: text after ` — ` or ` — ` separator
     For each position block under that H3:
       - Bold line → title (text before ` — ` → subtitle)
       - Italic line → start_date / end_date (split on ` – ` or ` - `)
       - Bullets (- ...) → position.bullets
   ```

7. **Skill categories:**
   ```
   For each line with bold (**...**):
     - Text before `:` → category name
     - Text after `:` → skills string
   ```

8. **Education:**
   ```
   For each bold line:
     - Text before ` — ` → institution
     - Text after ` — ` → degree + details
   ```

### 3.3 Edge Case Handling

| Edge case | Behavior |
|-----------|----------|
| No frontmatter | Defaults: dark, two-page, crafted_footer=true |
| Missing section | That field stays `None`/empty list |
| Company without positions | Empty positions list |
| Position without dates | Both dates are `None` |
| No contact info | `contact` is `None` |
| `&amp;` in source | Replaced with `&` during parsing (not in renderers) |
| Em dashes, en dashes | Preserved for rich formats (PDF/HTML), normalized to ASCII for TXT |
| Non-standard H2 section names | Skipped (ignored, not dropped — user may want custom sections) |
| Empty bullets between content | Filtered out (strip whitespace, drop empty) |

---

## 4. Renderers

### 4.0 Inline Markdown Utility (`src/ats_safe_resume/inline_md.py`)

All renderers need to convert inline markdown (`**bold**`, `*italic*`) to their native formatting. This is done **once** in a shared utility — no per-renderer duplication.

```python
def strip_markdown(text: str) -> str:
    """Remove ** and * markers, return plain text."""
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    return text

def to_typst(text: str) -> str:
    """Convert **bold** → *bold*, *italic* → _italic_ for Typst."""
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'_\1_', text)
    return text

def to_html(text: str) -> str:
    """Convert **bold** → <strong>bold</strong>, *italic* → <em>italic</em>."""
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    return text

def to_docx_runs(paragraph, text: str):
    """Tokenize text with ** and * into python-docx runs (bold/italic)."""
    # Implemented in the DOCX renderer as it needs run-level access
    pass
```

### 4.1 Common Interface

```python
from abc import ABC, abstractmethod
from pathlib import Path
from ats_safe_resume.models import Resume


class BaseRenderer(ABC):
    """All renderers implement this interface."""

    @abstractmethod
    def render(self, resume: Resume, output_path: Path) -> None:
        """Render resume to output_path."""
```

### 4.2 PDF Renderer — Typst (`src/ats_safe_resume/renderers/pdf.py`)

**External dependency:** `typst` Python package (`pip install typst`), which safely bundles the compiler.

**Inline Markdown:** `inline_md.to_typst()` converts `**bold**` → `*bold*` and `*italic*` → `_italic_` before inserting into the Typst markup.

**Implementation:**
```python
class PdfRenderer(BaseRenderer):
    def _render_typst(self, resume: Resume) -> str:
        """Generate Typst markup from Resume model."""
    def render(self, resume: Resume, output_path: Path) -> None:
        typst_source = self._render_typst(resume)
        temp_path = output_path.with_suffix(".typ")
        temp_path.write_text(typst_source)
        subprocess.run(
            ["typst", "compile", str(temp_path), str(output_path)],
            check=True, capture_output=True
        )
        temp_path.unlink()
```

**Typst template structure:**
```
Resume.typ (generated programmatically, no static template file)
├── Page setup (A4, margins, font)
├── Name block (centered, large)
├── Title line (centered, medium)
├── Contact line (centered, small, with · separators)
├── Section loop (H2 → accent bar)
│   ├── Executive Profile (paragraph)
│   ├── Core Expertise (inline)
│   ├── Professional Experience
│   │   ├── Company H3 (bold, location inline)
│   │   │   ├── Position (bold title, italic dates)
│   │   │   └── Bullets (compact enumitem)
│   ├── Technical Skills (bold category: inline list)
│   └── Education (bold institution, details inline)
└── Crafted footer (last page)
```

**Typography normalization for ATS:**
- Em dash (—), en dash (–) → ASCII hyphen (-) in text content
- Bullet (•) → ASCII asterisk (*)
- Middle dot (·) → pipe (|)  
- Smart quotes ("", '') → straight quotes ("", '')
- Applied at render time, not at parse time (so rich formats preserve typography)

### 4.3 DOCX Renderer — python-docx (`src/ats_safe_resume/renderers/docx.py`)

**External dependency:** `python-docx` (already in CI, already used by `validate_outputs.py`).

**Inline Markdown Handling:**
- **Accent Bars:** Heading paragraphs get a `w:pBdr` bottom border matching the theme accent color. This is the same visual treatment as v1's reference.docx.
- **Inline Bold/Italic:** A shared utility in `ats_safe_resume/inline_md.py` handles `**→bold`, `*→italic` conversion once. Every renderer imports from one place — no per-renderer duplication.

**Implementation approach:**
- Build document programmatically (no pandoc, no reference.docx)
- Every paragraph, run, and style is explicit
- Source Sans 3 embedded via font name (user must have font installed, or it falls back gracefully)

**Style mapping:**

| Element | Word Style | Font | Size |
|---------|-----------|------|------|
| Name | Title (centered) | Source Sans 3 Bold | 18pt |
| Title line | Subtitle (centered) | Source Sans 3 Semibold | 11pt |
| Contact | BodyText (centered) | Source Sans 3 | 9pt |
| Section H2 | Heading 1 | Source Sans 3 Bold | 11pt |
| Company H3 | Heading 2 | Source Sans 3 Bold | 10.5pt |
| Position title | Heading 3 | Source Sans 3 Bold | 10pt |
| Dates | Heading 3 (italic) | Source Sans 3 Italic | 10pt |
| Bullets | List Bullet | Source Sans 3 | 10pt |
| Skill category | BodyText Bold | Source Sans 3 Bold | 10pt |
| Crafted footer | Footer | Source Sans 3 | 8pt |

**No reference.docx needed** — all styling is programmatic. The `reference.docx` file can be removed in Phase 2.

### 4.4 HTML Renderer — Jinja2 (`src/ats_safe_resume/renderers/html.py`)

**External dependency:** `jinja2`.

**Template:** `src/ats_safe_resume/templates/resume.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ resume.title }}</title>
  <style>
    body { font-family: 'Source Sans 3', sans-serif; font-size: 10pt;
           margin: 0.5in 0.7in; line-height: 1.3; color: #333; }
    h1 { font-size: 18pt; text-align: center; margin-bottom: 0; }
    .contact { text-align: center; font-size: 9pt; margin-top: 2px; }
    h2 { font-size: 11pt; color: #555; border-bottom: 1px solid #555;
         padding-bottom: 2px; text-transform: uppercase; }
    .company { font-weight: bold; font-size: 10.5pt; }
    .dates { font-style: italic; color: #666; }
    ul { margin: 0; padding-left: 20px; }
    li { margin-bottom: 2px; }
    footer { text-align: center; font-size: 8pt; color: #999;
             margin-top: 20pt; }
  </style>
</head>
<body>
  <!-- rendered programmatically from Resume model -->
</body>
</html>
```

**Key features:**
- One template, deterministic output
- **Print-styled layout:** Mirrors the PDF dimensions (A4, max-width, print margins). `@media print` rules ensure faithful paper output. Responsive as a secondary consideration.
- **Inline Markdown:** Jinja2 custom filters replace `**` with `<strong>` tags.
- No Pandoc HTML markup to interpret
- Inline CSS (no external dependencies)
- Self-contained HTML file

### 4.5 TXT Renderer — Jinja2 (`src/ats_safe_resume/renderers/txt.py`)

```jinja2
{{ resume.name }}
{{ "=" * (resume.name|length) }}

{{ resume.title_line }}

{{ resume.contact.render_ats() }}

Executive Profile
{{ resume.executive_profile }}

Core Expertise
{{ resume.core_expertise }}

Professional Experience
{% for company in resume.companies %}
{% for position in company.positions %}
{{ company.name }} — {{ company.location }}
  {{ position.title }}{% if position.subtitle %} — {{ position.subtitle }}{% endif %}
  ({{ position.start_date }} - {{ position.end_date }})
{% for bullet in position.bullets %}
  * {{ self._ats_normalize(bullet) }}
{% endfor %}
{% endfor %}
{% endfor %}
...
```

**ATS-safe & Plaintext Downgrade:** 
- Typographic characters normalized to ASCII (em dash → hyphen, smart quotes → straight, bullets → asterisk).
- **Graceful Downgrade:** Jinja2 filters strip out any `**` and `*` inline markdown formatting since TXT doesn't support it, keeping content pure.

### 4.6 JSON Renderer (`src/ats_safe_resume/renderers/json_resume.py`)

Takes `Resume.to_json_resume()`, writes to file.

```python
class JsonResumeRenderer(BaseRenderer):
    def render(self, resume: Resume, output_path: Path) -> None:
        data = resume.to_json_resume()
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
```

The JSON output IS the canonical intermediate. It serves double duty: (a) the artifact all other renderers consume, and (b) the deliverable for programmatic consumers.

---

## 5. CLI Entry Point (`src/ats_safe_resume/cli.py`)

Accepts both markdown and JSON input:

```bash
# Normal: markdown input
ats-safe-resume resume.md

# Power user: skip markdown, provide JSON directly
ats-safe-resume resume.json

# Specify formats
ats-safe-resume resume.md --formats pdf,docx

# Validation after build
ats-safe-resume resume.md --validate
```

```python
import click
from pathlib import Path


@click.command()
@click.argument("input", type=click.Path(exists=True))
@click.option("--formats", default="pdf,docx,html,txt,json",
              help="Comma-separated output formats")
@click.option("--out-dir", default="dist",
              help="Output directory")
@click.option("--validate", is_flag=True,
              help="Run validation after build")
def build(input, formats, out_dir, validate):
    """Build a resume from markdown (or JSON) into multiple formats."""
    input_path = Path(input)
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse input
    text = input_path.read_text()
    if input_path.suffix == ".json":
        resume = Resume.model_validate_json(text)
    else:
        resume = parse(text)

    # Save canonical JSON
    json_path = output_dir / "resume.json"
    JsonResumeRenderer().render(resume, json_path)

    # Render requested formats
    format_map = {
        "pdf": PdfRenderer,
        "docx": DocxRenderer,
        "html": HtmlRenderer,
        "txt": TxtRenderer,
        "json": JsonResumeRenderer,
    }

    for fmt in formats.split(","):
        fmt = fmt.strip()
        if fmt == "json":
            continue  # already rendered as canonical
        ext = fmt
        output_path = output_dir / f"resume.{ext}"
        renderer = format_map[fmt]()
        renderer.render(resume, output_path)

    # Optional validation
    if validate:
        validate_all(output_dir)
```

---

## 6. Package Structure

```
ats_safe_resume/
├── src/
│   └── ats_safe_resume/
│       ├── __init__.py
│       ├── __main__.py            # python3 -m ats_safe_resume
│       ├── cli.py                 # Click/argparse entry point
│       ├── models.py              # Pydantic Resume model
│       ├── parser.py              # Markdown → Resume parser
│       ├── ats_normalize.py       # ATS typography normalization
│       ├── renderers/
│       │   ├── __init__.py
│       │   ├── base.py            # BaseRenderer ABC
│       │   ├── pdf.py             # Typst PDF
│       │   ├── docx.py            # python-docx
│       │   ├── html.py            # Jinja2 HTML
│       │   ├── txt.py             # Jinja2 TXT
│       │   └── json_resume.py     # JSON Resume export
│       └── templates/
│           ├── resume.html        # Jinja2 HTML template
│           └── resume.txt         # Jinja2 TXT template
├── tests/
│   ├── test_parser.py
│   ├── test_models.py
│   ├── test_renderers/
│   │   ├── test_pdf.py
│   │   ├── test_docx.py
│   │   ├── test_html.py
│   │   ├── test_txt.py
│   │   └── test_json.py
│   ├── test_integration.py        # Cross-format consistency
│   └── fixtures/
│       ├── jane_doe.md            # Current example resume
│       └── jane_doe.json          # Expected JSON output
├── example/
│   ├── resume.md                  # User-facing template (unchanged)
│   └── resume.pdf                 # Committed demo (unchanged)
├── validate_outputs.py            # Kept for backward compat
├── build_resume.sh                # Replaced in Phase 2, kept in Phase 1
├── pyproject.toml                 # Package config
├── Dockerfile                     # Simplified in Phase 2
├── .github/workflows/build.yml    # Updated in Phase 2
└── ARCHITECTURE_V2.md             # This document
```

---

## 7. Testing Strategy

### 7.1 Unit Tests (pytest, no external deps)

| Test file | Covers |
|-----------|--------|
| `test_models.py` | Pydantic validation, default values, `to_json_resume()` export |
| `test_parser.py` | Frontmatter parsing, body parsing, edge cases, all sections |
| `test_renderers/*.py` | Each renderer produces valid output for known input |

### 7.2 Integration Tests

| Test | What it verifies |
|------|-----------------|
| `test_v1_v2_parity()` | v2 output matches v1 output for `example/resume.md` (PDF as benchmark) |
| `test_all_formats_contain_name()` | Name, sections, companies present in all 5 formats |
| `test_json_schema_valid()` | JSON output validates against jsonresume.org schema |
| `test_no_double_escaped_entities()` | No `&amp;amp;` or `&lt;` in any output |
| `test_multi_page_pdf()` | Resume with 10+ positions renders across pages without crash |
| `test_pdf_fonts_embedded()` | Source Sans 3 fonts are embedded and subset (pdffonts check) |
| `test_json_no_markdown_in_summary()` | `basics.summary` has no `**markdown**` — it's stripped |

### 7.3 Property-Based Tests (Hypothesis)

```python
from hypothesis import given, strategies as st
from ats_safe_resume.models import Resume, Company, Position

resume_strategy = st.builds(Resume, ...)

@given(resume_strategy)
def test_all_formats_consistent(resume):
    """For any valid Resume, all 5 formats contain the same name."""
    outputs = {}
    for fmt, renderer in ALL_RENDERERS.items():
        path = tmp_path / f"resume.{fmt}"
        renderer.render(resume, path)
        outputs[fmt] = path.read_text() if fmt != "pdf" else extract_text(path)
    for fmt, text in outputs.items():
        assert resume.name in text, f"Name missing in {fmt}"
```

---

## 8. Migration Plan

### Phase 1: Parallel Implementation (this sprint)

**Goal:** Build v2 pipeline alongside v1. Both produce output. Validate parity.

**Timeline:** 3-5 days

**Tasks:**
1. Create Python package structure (`src/`, `pyproject.toml`)
2. Implement Pydantic models
3. Implement markdown parser
4. Implement Typst-based PDF renderer
5. Implement python-docx DOCX renderer
6. Implement Jinja2 HTML renderer
7. Implement Jinja2 TXT renderer
8. Implement JSON Resume renderer
9. Implement CLI entry point
10. Add unit tests for all components
11. Add integration tests comparing v1 vs v2 output
12. Run in CI for 1 week (both pipelines in build job; v2 results uploaded as additional artifacts)

### Phase 2: Cutover (after Phase 1 validation)

**Goal:** v2 becomes the default pipeline. v1 removed.

**Tasks:**
1. Update `build_resume.sh` to call `python3 -m ats_safe_resume` 
2. Simplify `Dockerfile` (remove Pandoc/TeX Live, add Typst + Python)
3. Simplify CI (remove apt texlive-* packages)
4. Add Hypothesis property-based tests
5. Update `README.md` (new dependency requirements)
6. Archive/remove v1 artifacts

### Phase 3: Enhancement (future)

- Accept JSON input directly (power users)
- LinkedIn profile migration feature
- Web UI for non-technical users

---

## 9. Dependency Graph

```
                           ┌──────────────────────────┐
                           │     resume.md (source)    │
                           └──────────┬───────────────┘
                                      │
                                      ▼
                           ┌──────────────────────────┐
                           │   parser.py               │
                           │   (yaml, re)              │
                           └──────────┬───────────────┘
                                      │
                                      ▼
                           ┌──────────────────────────┐
                           │  Resume (Pydantic model)  │
                           └──────────┬───────────────┘
                                      │
                        ┌─────────────┼─────────────┐
                        │             │             │
                        ▼             ▼             ▼
            ┌───────────────┐ ┌───────────┐ ┌───────────┐
            │ to_json_resume│ │ PDF (typst)│ │ DOCX      │
            │   (no deps)   │ │           │ │(python-docx)│
            └───────┬───────┘ └───────────┘ └───────────┘
                    │
                    ▼
           ┌────────────────┐
           │ resume.json    │
           │ (canonical)    │
           └────────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
   ┌────────┐ ┌────────┐ ┌──────────┐
   │ HTML   │ │ TXT    │ │ JSON     │
   │(jinja2)│ │(jinja2)│ │(identity)│
   └────────┘ └────────┘ └──────────┘
```

**External dependencies by component:**

| Component | Dependency | Size | Install |
|-----------|-----------|------|---------|
| Parser | PyYAML | ~150KB | `pip install pyyaml` |
| Models | Pydantic | ~5MB | `pip install pydantic` |
| PDF | Typst Python | ~40MB | `pip install typst` |
| DOCX | python-docx | ~2MB | `pip install python-docx` |
| HTML | Jinja2 | ~500KB | `pip install jinja2` |
| TXT | Jinja2 (same) | — | — |
| JSON | stdlib | — | — |
| Tests | Hypothesis | ~2MB | `pip install hypothesis` |
| CLI | Click or argparse | ~200KB | `pip install click` (or stdlib) |

**Total new install size:** ~50MB.

**Old install size removed:** ~1.5GB (texlive-* packages, Pandoc).

---

## 10. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Typst markup doesn't match LaTeX layout exactly | High | Medium | Phase 1 parallel comparison; iterate on Typst markup until pixel-match with PDF benchmark |
| python-docx produces different DOCX than pandoc reference.docx | Medium | Low | Programmatic control is more reliable; visual differences are acceptable as long as content matches |
| Markdown parser misses edge case resume structure | Medium | Medium | Property-based testing catches edge cases; parser tests with many fixture resumes |
| Typst binary download fails in CI | Low | High | Pin version, cache binary in CI, fall back to `no-cache: true` for Docker |
| Existing users depend on Pandoc/DOCX behavior | Low | Low | v1 still ships unchanged in Phase 1; no user has custom DOCX template (reference.docx is our file) |
| parser.py maintains HTML comments but drops content inside | Low | Low | Comments are stripped before body parsing — no content inside comments |