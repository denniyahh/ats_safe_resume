# Phase 1 Implementation Plan: v2 Parallel Pipeline

> **Goal:** Build the v2 Python pipeline alongside the existing v1 bash pipeline. Both produce output in parallel. CI validates parity between them.
> **Review requested by:** Gemini (via Dennis)
> **Timeline:** 3-5 days
> **Principle:** Zero regression risk — v1 stays untouched, v2 is proven alongside it.

---

## Architecture Flow (Phase 1)

```
resume.md ──┬──► v1 (build_resume.sh) ──► dist/   [existing, untouched]
             │
             └──► v2 (python3 -m ats_safe_resume) ──► dist-v2/  [new]
                                                         │
                                                         ▼
                                                validate_outputs_v2.py
                                                compares v1 vs v2 output
```

---

## Task Breakdown

### Task 1: Create Python Package Structure

**Objective:** Set up `src/` package layout with `pyproject.toml`, `__init__.py`, and `__main__.py`.

**Files:**
- Create: `src/ats_safe_resume/__init__.py`
- Create: `src/ats_safe_resume/__main__.py`
- Create: `src/ats_safe_resume/models.py`
- Create: `src/ats_safe_resume/ats_normalize.py`
- Create: `src/ats_safe_resume/inline_md.py`
- Create: `src/ats_safe_resume/renderers/__init__.py`
- Create: `src/ats_safe_resume/renderers/base.py`
- Create: `src/ats_safe_resume/renderers/pdf.py`
- Create: `src/ats_safe_resume/renderers/docx.py`
- Create: `src/ats_safe_resume/renderers/html.py`
- Create: `src/ats_safe_resume/renderers/txt.py`
- Create: `src/ats_safe_resume/renderers/json_resume.py`
- Create: `src/ats_safe_resume/templates/resume.html`
- Create: `src/ats_safe_resume/templates/resume.txt`
- Create: `pyproject.toml`

**Stubs:** Each file gets a module docstring, empty class/function stubs, and a `pass` or `TODO` marker. No logic yet.

**pyproject.toml:**
```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "ats_safe_resume"
version = "2.0.0-alpha"
description = "ATS-safe, multi-format resume generator"
requires-python = ">=3.10"
dependencies = [
    "pyyaml>=6.0",
    "pydantic>=2.0",
    "python-docx>=1.2.0",
    "jinja2>=3.1",
    "typst>=0.11",
]

[project.scripts]
ats-safe-resume = "ats_safe_resume.cli:build"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
ats_safe_resume = ["templates/*"]
```

---

### Task 2: Implement Pydantic Models

**Objective:** Define all data models in `models.py` as specified in §2 of ARCHITECTURE_V2.md. Write unit tests first.

**Files:**
- Create: `tests/test_models.py`
- Modify: `src/ats_safe_resume/models.py`

**Step 1 — Write tests:**

```python
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
```

**Step 2 — Verify tests fail** (no implementation yet)

Run: `python3 -m pytest tests/test_models.py -v`
Expected: ALL FAIL — "ModuleNotFoundError" or "ImportError"

**Step 3 — Implement models.py:**

Complete `models.py` with all model classes, `to_json_resume()`, `to_ats_string()`, `_normalize_date()`, and `_parse_profiles()`.

**Step 4 — Verify tests pass:**

Run: `python3 -m pytest tests/test_models.py -v`
Expected: ALL PASS

**Step 5 — Commit:**

```bash
git add src/ats_safe_resume/models.py tests/test_models.py pyproject.toml
git commit -m "feat(models): add Pydantic resume data model with JSON Resume export"
```

---

### Task 3: Implement Markdown Parser

**Objective:** Parse the example resume markdown into a valid `Resume` model.

**Files:**
- Create: `tests/test_parser.py`
- Create: `tests/fixtures/jane_doe.md` (copy of `example/resume.md` as test fixture)
- Modify: `src/ats_safe_resume/parser.py`

**Step 1 — Write tests:**

```python
# tests/test_parser.py
import pytest
from pathlib import Path
from ats_safe_resume.parser import parse, parse_frontmatter, parse_body
from ats_safe_resume.models import Resume, Theme, PageMode

FIXTURES = Path(__file__).parent / "fixtures"

def test_parse_frontmatter():
    md = FIXTURES.joinpath("jane_doe.md").read_text()
    front = parse_frontmatter(md)
    assert front["title"] == "Jane Doe — Senior Product Manager"
    assert front["theme"] == "dark"
    assert front["page_mode"] == "two"
    assert front.get("crafted_footer", True) is True

def test_parse_full_resume():
    md = FIXTURES.joinpath("jane_doe.md").read_text()
    resume = parse(md)
    assert resume.name == "Jane Doe"
    assert resume.title_line == "Senior Product Manager"
    assert resume.executive_profile is not None
    assert "Product leader" in resume.executive_profile
    assert resume.core_expertise is not None

def test_parse_work_history():
    md = FIXTURES.joinpath("jane_doe.md").read_text()
    resume = parse(md)
    assert len(resume.companies) == 3  # Acme Corp, TechCorp, DataFirst
    acme = resume.companies[0]
    assert acme.name == "Acme Corp"
    assert acme.location == "San Francisco, CA"
    assert len(acme.positions) == 2  # Senior PM, PM
    assert acme.positions[0].title == "Senior Product Manager"

def test_parse_dates():
    md = FIXTURES.joinpath("jane_doe.md").read_text()
    resume = parse(md)
    first = resume.companies[0].positions[0]
    assert first.start_date == "Jun 2021"
    assert first.end_date == "Present"

def test_parse_bullets():
    md = FIXTURES.joinpath("jane_doe.md").read_text()
    resume = parse(md)
    first = resume.companies[0].positions[0]
    assert len(first.bullets) >= 3
    assert "**$25MM+**" in first.bullets[0]  # bold preserved

def test_parse_skills():
    md = FIXTURES.joinpath("jane_doe.md").read_text()
    resume = parse(md)
    assert len(resume.technical_skills) >= 4
    assert resume.technical_skills[0].category == "Product & strategy"

def test_parse_education():
    md = FIXTURES.joinpath("jane_doe.md").read_text()
    resume = parse(md)
    assert len(resume.education) >= 1
    assert "UC Berkeley" in resume.education[0].institution

def test_parse_contact():
    md = FIXTURES.joinpath("jane_doe.md").read_text()
    resume = parse(md)
    assert resume.contact is not None
    assert "jane.doe@email.com" in resume.contact.email

def test_parse_no_frontmatter():
    """Should handle markdown without frontmatter gracefully."""
    md = "# Test\n**Test Title**\n\n## Section\n\nContent"
    resume = parse(md)
    assert resume.name == "Test"
    assert resume.theme == Theme.dark  # default

def test_parse_html_comments():
    """HTML comments should be stripped, not included in content."""
    md = "# Name\n**Title**\n\n## Section\n<!-- secret -->\nText"
    resume = parse(md)
    assert "secret" not in (resume.executive_profile or "")
```

**Step 2 — Verify tests fail.**

**Step 3 — Implement parser.py:**

Implement `parse_frontmatter()` using `yaml.safe_load()`, `parse_body()` with regex-based section detection, and `parse()` as the top-level orchestrator. Follow the parsing algorithm in §3.2 of ARCHITECTURE_V2.md.

**Step 4 — Verify tests pass:**

Run: `pytest tests/test_parser.py -v`
Expected: ALL PASS

**Step 5 — Test with actual example:**

```python
python3 -c "
from ats_safe_resume.parser import parse
r = parse(open('example/resume.md').read())
print(f'Name: {r.name}')
print(f'Title: {r.title_line}')
print(f'Companies: {len(r.companies)}')
print(f'Skills: {len(r.technical_skills)}')
print(f'Education: {len(r.education)}')
print(f'JSON Resume valid: {r.to_json_resume()[\"basics\"][\"name\"] == r.name}')
"
```

Expected: All fields populated correctly.

**Step 6 — Commit:**

```bash
git add src/ats_safe_resume/parser.py tests/test_parser.py tests/fixtures/
git commit -m "feat(parser): add markdown resume parser with section detection"
```

---

### Task 4: Implement ATS Normalization Utility

**Objective:** Centralize typographic character normalization so all renderers share the same rules.

**Files:**
- Create: `tests/test_ats_normalize.py`
- Modify: `src/ats_safe_resume/ats_normalize.py`

**Step 1 — Write tests:**

```python
def test_em_dash_to_hyphen():
    assert normalize("Revenue — grew 40%") == "Revenue - grew 40%"

def test_en_dash_to_hyphen():
    assert normalize("2019–2021") == "2019-2021"

def test_smart_quotes_straight():
    assert normalize('"Smart" and \'single\'') == '"Smart" and \'single\''

def test_bullet_to_asterisk():
    assert normalize("• Item") == "* Item"

def test_middle_dot_to_pipe():
    assert normalize("a · b") == "a | b"

def test_no_change_for_normal_text():
    assert normalize("Hello, world!") == "Hello, world!"

def test_preserves_markdown_formatting():
    """Bold markers should be preserved."""
    assert normalize("**$25MM**") == "**$25MM**"
```

**Step 2 — Implement normalize() using str.translate():**

```python
NORMALIZE_TABLE = str.maketrans({
    '\u2014': '-',   # em dash
    '\u2013': '-',   # en dash
    '\u2018': "'",   # left single quote
    '\u2019': "'",   # right single quote
    '\u201c': '"',   # left double quote
    '\u201d': '"',   # right double quote
    '\u2022': '*',   # bullet
    '\u00b7': '|',   # middle dot
    '\u2026': '...', # ellipsis
})

def normalize(text: str) -> str:
    return text.translate(NORMALIZE_TABLE)
```

**Step 3 — Verify tests pass.**

---

### Task 5: Implement PDF Renderer (Typst)

**Objective:** Render a `Resume` model to PDF via Typst.

**Prerequisites:** Install Typst Python package:
```bash
pip install typst
```

**Files:**
- Create: `tests/test_renderers/test_pdf.py`
- Modify: `src/ats_safe_resume/renderers/pdf.py`

**Step 1 — Write tests:**

```python
def test_pdf_generates_valid_pdf(tmp_path):
    resume = Resume(name="Jane Doe", title_line="Senior PM")
    renderer = PdfRenderer()
    out = tmp_path / "resume.pdf"
    renderer.render(resume, out)
    assert out.exists()
    assert out.stat().st_size > 1000
    # Verify it's a valid PDF
    assert out.read_bytes()[:4] == b'%PDF'

def test_pdf_contains_name(tmp_path):
    resume = Resume(name="Alice Smith", title_line="Engineer")
    renderer = PdfRenderer()
    out = tmp_path / "resume.pdf"
    renderer.render(resume, out)
    # pdftotext check
    text = subprocess.check_output(["pdftotext", str(out), "-"]).decode()
    assert "Alice Smith" in text

def test_pdf_crafted_footer(tmp_path):
    resume = Resume(name="Test", title_line="Test", crafted_footer=True)
    renderer = PdfRenderer()
    out = tmp_path / "resume.pdf"
    renderer.render(resume, out)
    text = subprocess.check_output(["pdftotext", str(out), "-"]).decode()
    assert "ats_safe_resume" in text
```

**Step 2 — Implement PdfRenderer:**

The renderer generates Typst markup programmatically (no static .typ file). It composes the document as a Python string using the Resume model fields.

Key: Typst markup looks like this:
```typst
#set page("a4", margin: (left: 0.7in, right: 0.7in, top: 0.5in, bottom: 0.5in))
#set text(font: "Source Sans 3", size: 10pt)

#align(center, text(size: 18pt, weight: "bold")[Jane Doe])
#align(center, text(size: 11pt, weight: "semibold")[Senior PM])
#align(center, text(size: 9pt)[San Francisco, CA · j@e.com · 555-0000])

= Executive Profile
#text(size: 10pt)[Product leader with 10+ years...]

= Professional Experience
== Acme Corp — San Francisco, CA
*Senior PM* _Jun 2021 - Present_
- Grew revenue...
```

The renderer builds this string from the Resume model fields, writes it to a temp `.typ` file, runs `typst compile`, and deletes the temp file.

**Step 3 — Verify tests pass:**

```bash
pytest tests/test_renderers/test_pdf.py -v
```

---

### Task 6: Implement DOCX Renderer (python-docx)

**Objective:** Render a `Resume` model to DOCX using python-docx.

**Files:**
- Create: `tests/test_renderers/test_docx.py`
- Modify: `src/ats_safe_resume/renderers/docx.py`

**Step 1 — Write tests:**

```python
def test_docx_generates_valid_file(tmp_path):
    resume = Resume(name="Jane Doe", title_line="Senior PM")
    renderer = DocxRenderer()
    out = tmp_path / "resume.docx"
    renderer.render(resume, out)
    assert out.exists()
    doc = Document(str(out))
    assert doc.paragraphs[0].text == "Jane Doe"

def test_docx_contains_sections(tmp_path):
    resume = Resume(name="Jane", title_line="PM",
                    executive_profile="A great leader.",
                    companies=[Company(name="Acme", positions=[
                        Position(title="PM", bullets=["Did stuff"])
                    ])])
    renderer = DocxRenderer()
    out = tmp_path / "resume.docx"
    renderer.render(resume, out)
    doc = Document(str(out))
    texts = [p.text for p in doc.paragraphs]
    assert "Executive Profile" in texts
    assert "Professional Experience" in texts
    assert "Acme" in texts

def test_docx_crafted_footer(tmp_path):
    resume = Resume(name="Test", title_line="Test", crafted_footer=True)
    renderer = DocxRenderer()
    out = tmp_path / "resume.docx"
    renderer.render(resume, out)
    doc = Document(str(out))
    texts = [p.text for p in doc.paragraphs]
    assert any("ats_safe_resume" in t for t in texts)
```

**Step 2 — Implement DocxRenderer:**

Build the document programmatically:
1. Set default font to Source Sans 3, 10pt
2. Add name (centered, 18pt, bold)
3. Add title line (centered, 11pt, semibold)
4. Add contact (centered, 9pt)
5. For each section: add heading with accent bar (bottom border matching theme accent color), add content
6. For each company: company name with location
7. For each position: bold title + italic dates on same line, summary (if present), bullets with List Bullet style
8. Inline markdown: `inline_md.to_docx_runs()` tokenizes `**bold**` and `*italic*` into python-docx runs
9. Crafted footer
10. Save

**Step 3 — Verify tests pass.**

---

### Task 7: Implement HTML Renderer (Jinja2)

**Objective:** Render a `Resume` model to HTML via Jinja2 template.

**Files:**
- Create: `tests/test_renderers/test_html.py`
- Modify: `src/ats_safe_resume/renderers/html.py`
- Modify: `src/ats_safe_resume/templates/resume.html`

**Step 1 — Write the Jinja2 template in `templates/resume.html`:**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ resume.title }}</title>
  <style>
    body { font-family: 'Source Sans 3', sans-serif; font-size: 10pt;
           margin: 0.5in 0.7in; max-width: 8in; color: #333; }
    h1 { font-size: 18pt; text-align: center; margin-bottom: 0.1em; }
    .title-line { text-align: center; font-size: 11pt; font-weight: 600;
                  margin-top: 0; }
    .contact { text-align: center; font-size: 9pt; color: #555; }
    h2 { font-size: 11pt; color: #555; text-transform: uppercase;
         border-bottom: 1px solid #555; padding-bottom: 2px;
         margin-top: 1em; }
    .company { font-weight: bold; font-size: 10.5pt; margin-bottom: 0; }
    .position { margin-bottom: 0.5em; }
    .position-title { font-weight: bold; }
    .dates { font-style: italic; color: #666; }
    ul { margin: 0.2em 0; padding-left: 1.5em; }
    li { margin-bottom: 0.15em; }
    .skill-cat { margin-bottom: 0.2em; }
    .skill-cat strong { font-weight: bold; }
    footer { text-align: center; font-size: 8pt; color: #999;
             margin-top: 2em; }
    a { color: #555; text-decoration: none; }
  </style>
</head>
<body>
  <h1>{{ resume.name }}</h1>
  {% if resume.title_line %}
    <p class="title-line">{{ resume.title_line }}</p>
  {% endif %}
  {% if resume.contact %}
    <p class="contact">{{ resume.contact.to_ats_string() }}</p>
  {% endif %}

  {% if resume.executive_profile %}
    <h2>Executive Profile</h2>
    <p>{{ resume.executive_profile }}</p>
  {% endif %}

  {% if resume.core_expertise %}
    <h2>Core Expertise</h2>
    <p>{{ resume.core_expertise }}</p>
  {% endif %}

  {% if resume.companies %}
    <h2>Professional Experience</h2>
    {% for company in resume.companies %}
      {% for position in company.positions %}
        <p class="company">{{ company.name }}{% if company.location %} — {{ company.location }}{% endif %}</p>
        <div class="position">
          <span class="position-title">{{ position.title }}</span>{% if position.subtitle %} — {{ position.subtitle }}{% endif %}
          {% if position.start_date %}
            <span class="dates"> ({{ position.start_date }} – {{ position.end_date or 'Present' }})</span>
          {% endif %}
        </div>
        {% if position.summary %}
          <p>{{ position.summary | inline_markdown }}</p>
        {% endif %}
        {% if position.bullets %}
          <ul>
          {% for bullet in position.bullets %}
            <li>{{ bullet | inline_markdown }}</li>
          {% endfor %}
          </ul>
        {% endif %}
      {% endfor %}
    {% endfor %}
  {% endif %}

  {% if resume.technical_skills %}
    <h2>Technical Skills</h2>
    {% for skill in resume.technical_skills %}
      <p class="skill-cat"><strong>{{ skill.category }}:</strong> {{ skill.skills }}</p>
    {% endfor %}
  {% endif %}

  {% if resume.education %}
    <h2>Education</h2>
    {% for edu in resume.education %}
      <p><strong>{{ edu.institution }}</strong>{% if edu.degree %} — {{ edu.degree }}{% endif %}{% if edu.details %}, {{ edu.details }}{% endif %}</p>
    {% endfor %}
  {% endif %}

  {% if resume.crafted_footer %}
    <footer>crafted with <a href="https://github.com/denniyahh/ats_safe_resume">ats_safe_resume</a></footer>
  {% endif %}
</body>
</html>
```

**Step 2 — Write tests:**

```python
def test_html_contains_name(tmp_path):
    resume = Resume(name="Jane Doe", title_line="Senior PM")
    renderer = HtmlRenderer()
    out = tmp_path / "resume.html"
    renderer.render(resume, out)
    html = out.read_text()
    assert "<h1>Jane Doe</h1>" in html

def test_html_no_double_escaped_entities(tmp_path):
    resume = Resume(name="Test & Co.", title_line="Engineer")
    renderer = HtmlRenderer()
    out = tmp_path / "resume.html"
    renderer.render(resume, out)
    html = out.read_text()
    assert "&amp;" not in html

def test_html_crafted_footer(tmp_path):
    resume = Resume(name="Test", title_line="Test", crafted_footer=True)
    renderer = HtmlRenderer()
    out = tmp_path / "resume.html"
    renderer.render(resume, out)
    html = out.read_text()
    assert "ats_safe_resume" in html
    assert "github.com/denniyahh" in html

def test_html_valid_structure(tmp_path):
    resume = Resume(name="Jane", title_line="PM",
                    executive_profile="Great leader.",
                    companies=[Company(name="Acme", positions=[
                        Position(title="PM", bullets=["Did stuff"])
                    ])])
    renderer = HtmlRenderer()
    out = tmp_path / "resume.html"
    renderer.render(resume, out)
    html = out.read_text()
    assert "<h2>Executive Profile</h2>" in html
    assert "<h2>Professional Experience</h2>" in html
```

**Step 3 — Verify tests pass.**

---

### Task 8: Implement TXT Renderer (Jinja2)

**Objective:** Render a `Resume` model to plain text with ATS-safe normalization via Jinja2 template.

**Files:**
- Create: `tests/test_renderers/test_txt.py`
- Modify: `src/ats_safe_resume/renderers/txt.py`
- Modify: `src/ats_safe_resume/templates/resume.txt`

**Step 1 — Write the Jinja2 template:**

```jinja2
{{ resume.name }}
{{ "=" * (resume.name|length) }}

{{ resume.title_line }}

{% if resume.contact %}{{ resume.contact.render_ats_text() }}{% endif %}

{% if resume.executive_profile %}
EXECUTIVE PROFILE

{{ resume.executive_profile }}
{% endif %}

{% if resume.core_expertise %}
CORE EXPERTISE

{{ resume.core_expertise }}
{% endif %}

{% if resume.companies %}
PROFESSIONAL EXPERIENCE

{% for company in resume.companies %}
{% for position in company.positions %}
{{ company.name }}{% if company.location %} -- {{ company.location }}{% endif %}
  {{ position.title }}{% if position.subtitle %} -- {{ position.subtitle }}{% endif %}
  ({{ position.start_date or '' }} - {{ position.end_date or '' }})
{% if position.summary %}
  {{ position.summary | strip_markdown }}
{% endif %}
{% for bullet in position.bullets %}
  * {{ bullet | strip_markdown }}
{% endfor %}

{% endfor %}
{% endfor %}
{% endif %}

{% if resume.technical_skills %}
TECHNICAL SKILLS

{% for skill in resume.technical_skills %}
  {{ skill.category }}: {{ skill.skills }}
{% endfor %}
{% endif %}

{% if resume.education %}
EDUCATION

{% for edu in resume.education %}
  {{ edu.institution }}{% if edu.degree %} -- {{ edu.degree }}{% endif %}{% if edu.details %}, {{ edu.details }}{% endif %}
{% endfor %}
{% endif %}

{% if resume.crafted_footer %}
--
crafted with ats_safe_resume (https://github.com/denniyahh/ats_safe_resume)
{% endif %}
```

**Step 2 — ATS normalization filter:** Apply `ats_normalize.normalize()` to all text content during rendering. The renderer calls `normalize()` on each field before inserting into the template.

**Step 3 — Write tests:**

```python
def test_txt_contains_name(tmp_path):
    resume = Resume(name="Jane Doe", title_line="Senior PM")
    renderer = TxtRenderer()
    out = tmp_path / "resume.txt"
    renderer.render(resume, out)
    text = out.read_text()
    assert "Jane Doe" in text

def test_txt_ats_normalized(tmp_path):
    """Smart quotes, em dashes should be ASCII in TXT."""
    resume = Resume(name="Test", title_line="Engineer",
                    executive_profile="Revenue — grew 40%")
    renderer = TxtRenderer()
    out = tmp_path / "resume.txt"
    renderer.render(resume, out)
    text = out.read_text()
    assert "—" not in text  # em dash must be normalized

def test_txt_no_bold_markers(tmp_path):
    """TXT should not contain ** markers."""
    resume = Resume(name="Test", title_line="Engineer",
                    companies=[Company(name="Acme", positions=[
                        Position(title="PM", bullets=["**$25MM** revenue"])
                    ])])
    renderer = TxtRenderer()
    out = tmp_path / "resume.txt"
    renderer.render(resume, out)
    text = out.read_text()
    assert "**" not in text
```

---

### Task 9: Implement JSON Resume Renderer

**Objective:** Write the existing JSON export as a standalone renderer that calls `Resume.to_json_resume()`.

**Files:**
- Create: `tests/test_renderers/test_json.py`
- Modify: `src/ats_safe_resume/renderers/json_resume.py`

**Step 1 — Write tests:**

```python
def test_json_generates_valid_json(tmp_path):
    resume = Resume(name="Jane Doe", title_line="Senior PM")
    renderer = JsonResumeRenderer()
    out = tmp_path / "resume.json"
    renderer.render(resume, out)
    data = json.loads(out.read_text())
    assert data["basics"]["name"] == "Jane Doe"

def test_json_section_order(tmp_path):
    """Section order should be: basics, work, skills, education."""
    resume = Resume(name="Test", title_line="Test")
    renderer = JsonResumeRenderer()
    out = tmp_path / "resume.json"
    renderer.render(resume, out)
    data = json.loads(out.read_text())
    keys = list(data.keys())
    basics_idx = keys.index("basics") if "basics" in keys else -1
    work_idx = keys.index("work") if "work" in keys else -1
    education_idx = keys.index("education") if "education" in keys else -1
    assert basics_idx < work_idx < education_idx

def test_json_no_html_in_names(tmp_path):
    resume = Resume(name="Test", title_line="Engineer",
                    companies=[Company(name="Interactive Data", positions=[
                        Position(title="Developer", bullets=[])
                    ])])
    renderer = JsonResumeRenderer()
    out = tmp_path / "resume.json"
    renderer.render(resume, out)
    data = json.loads(out.read_text())
    assert "<" not in json.dumps(data)
```

---

### Task 10: Implement CLI Entry Point

**Objective:** Wire everything together into a single `ats-safe-resume` CLI command.

**Files:**
- Create: `src/ats_safe_resume/cli.py`
- Create: `tests/test_cli.py`

**Step 1 — Implement cli.py using argparse (no external deps):**

```python
#!/usr/bin/env python3
"""CLI entry point for ats_safe_resume."""
import argparse
from pathlib import Path
from ats_safe_resume.parser import parse
from ats_safe_resume.models import Resume
from ats_safe_resume.renderers.pdf import PdfRenderer
from ats_safe_resume.renderers.docx import DocxRenderer
from ats_safe_resume.renderers.html import HtmlRenderer
from ats_safe_resume.renderers.txt import TxtRenderer
from ats_safe_resume.renderers.json_resume import JsonResumeRenderer


def build():
    parser = argparse.ArgumentParser(description="Build resume from markdown")
    parser.add_argument("input", help="Input resume.md or resume.json")
    parser.add_argument("--formats", default="pdf,docx,html,txt,json",
                        help="Comma-separated output formats")
    parser.add_argument("--out-dir", default="dist-v2",
                        help="Output directory (default: dist-v2)")
    parser.add_argument("--validate", action="store_true",
                        help="Run validation after build")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.out_dir)
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
    renderers = {
        "pdf": PdfRenderer,
        "docx": DocxRenderer,
        "html": HtmlRenderer,
        "txt": TxtRenderer,
        "json": JsonResumeRenderer,
    }

    for fmt in args.formats.split(","):
        fmt = fmt.strip()
        if fmt == "json":
            continue  # already rendered as canonical
        ext = fmt
        output_path = output_dir / f"resume.{ext}"
        renderer = renderers[fmt]()
        renderer.render(resume, output_path)
        print(f"  ✅ {output_path}")


if __name__ == "__main__":
    build()
```

**Step 2 — Install and test:**

```bash
pip install -e .
ats-safe-resume example/resume.md --formats pdf,docx,html,txt,json
ls dist-v2/
# Expected: resume.pdf, resume.docx, resume.html, resume.txt, resume.json
```

**Step 3 — Test JSON input directly:**

```bash
ats-safe-resume dist-v2/resume.json --formats pdf
ls dist-v2/
```

---

### Task 11: Add v1 vs v2 Parity Validation

**Objective:** CI runs both v1 and v2 pipelines, then validates that outputs match (content-wise).

**Files:**
- Create: `tests/test_v1_v2_parity.py`
- Modify: `.github/workflows/build.yml` (add v2 build + parity check)

**Step 1 — Write parity tests:**

```python
# tests/test_v1_v2_parity.py
"""Validate that v2 pipeline produces the same content as v1."""

import subprocess
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent


def test_v2_pipeline_runs_without_error():
    """v2 pipeline must complete without crashing."""
    result = subprocess.run(
        ["python3", "-m", "ats_safe_resume", str(SCRIPT_DIR / "example/resume.md"),
         "--out-dir", "dist-v2"],
        capture_output=True, text=True, cwd=SCRIPT_DIR
    )
    assert result.returncode == 0, f"v2 failed: {result.stderr}"
    assert Path(SCRIPT_DIR / "dist-v2/resume.json").exists()


def test_v1_v2_json_match():
    """v2 JSON output must contain the same data as v1 JSON output."""
    # v1 already ran and produced dist/resume.json
    v1_path = SCRIPT_DIR / "dist/resume.json"
    v2_path = SCRIPT_DIR / "dist-v2/resume.json"

    if not v1_path.exists():
        pytest.skip("v1 dist/ not available (run build_resume.sh first)")

    v1_data = json.loads(v1_path.read_text())
    v2_data = json.loads(v2_path.read_text())

    # Core data must match
    assert v1_data["basics"]["name"] == v2_data["basics"]["name"]
    assert v1_data["basics"]["label"] == v2_data["basics"]["label"]
    # Number of work entries
    assert len(v1_data.get("work", [])) == len(v2_data.get("work", []))


def test_v1_v2_pdf_contains_same_name():
    """Both pipelines' PDFs must contain the candidate name."""
    v1_text = subprocess.check_output(
        ["pdftotext", str(SCRIPT_DIR / "dist/resume.pdf"), "-"]
    ).decode()
    v2_text = subprocess.check_output(
        ["pdftotext", str(SCRIPT_DIR / "dist-v2/resume.pdf"), "-"]
    ).decode()
    # Both must contain "Jane Doe" (example resume name)
    assert "Jane Doe" in v1_text
    assert "Jane Doe" in v2_text


def test_v2_pdf_fonts_embedded():
    """v2 PDF must have Source Sans 3 fonts embedded and subset."""
    font_output = subprocess.check_output(
        ["pdffonts", str(SCRIPT_DIR / "dist-v2/resume.pdf")]
    ).decode()
    source_sans_lines = [l for l in font_output.split('\n') if 'SourceSans' in l]
    assert len(source_sans_lines) >= 3, "Expected at least 3 Source Sans 3 font faces"
    for line in source_sans_lines:
        parts = line.rsplit(None, 4)
        assert 'yes' in parts[-3].lower(), f"Font not subset: {line}"


def test_v2_multi_page_no_crash():
    """PDF with many positions should render without crash."""
    from ats_safe_resume.models import Resume, Company, Position
    import tempfile
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
    from ats_safe_resume.renderers.pdf import PdfRenderer
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
    import tempfile
    resume = Resume(
        name="Test",
        title_line="Test",
        executive_profile="Grew revenue from **$5MM** to **$25MM+**."
    )
    out = Path(tempfile.mkdtemp()) / "resume.json"
    JsonResumeRenderer().render(resume, out)
    data = json.loads(out.read_text())
    assert "**" not in data["basics"]["summary"]
```

**Step 2 — Update CI:**

Add a new CI job or extend the existing build job to:
1. Run v1 pipeline (existing)
2. Run v2 pipeline (`python3 -m ats_safe_resume example/resume.md --out-dir dist-v2`)
3. Run parity tests (`pytest tests/test_v1_v2_parity.py -v`)
4. Upload v2 artifacts alongside v1 artifacts

---

### Task 12: Run Validation Against Dennis's Real Resume

**Objective:** Verify the v2 pipeline produces correct output for a real-world resume (not just example placeholder).

**Step 1 — Run v2 against my_resume:**

```bash
cd ~/Github/ats_safe_resume
ats-safe-resume ~/Github/my_resume/resume.md --out-dir dist-v2-personal
```

**Step 2 — Compare with v1 output:**

```bash
cd ~/Github/my_resume
./build_resume.sh
cd ~/Github/ats_safe_resume
python3 -c "
import json
v1 = json.load(open('/home/denniyahh/Github/my_resume/dist/resume.json'))
v2 = json.load(open('dist-v2-personal/resume.json'))
# compare companies, positions, dates, skills
v1_names = {w['name'] for w in v1['work']}
v2_names = {w['name'] for w in v2['work']}
assert v1_names == v2_names, f'Companies mismatch: v1={v1_names}, v2={v2_names}'
print('✅ All companies match')
print(f'Companies: {len(v1_names)}')
print(f'Skills: {len(v1[\"skills\"])} categories')
"
```

**Step 3 — Commit Phase 1:**

```bash
cd ~/Github/ats_safe_resume
git add -A
git commit -m "feat: add v2 Python pipeline (markdown → JSON → renderers)

- Pydantic data model with JSON Resume export
- Markdown parser with section detection
- ATS normalization utility
- PDF renderer (Typst)
- DOCX renderer (python-docx)
- HTML renderer (Jinja2)
- TXT renderer (Jinja2)
- JSON Resume renderer
- CLI entry point (ats-safe-resume)
- v1 vs v2 parity tests
"
```

---

## CI Flow (Phase 1 — both pipelines)

```yaml
jobs:
  build:
    steps:
      - install-deps (pandoc + texlive + python deps + typst)
      - v1: ./build_resume.sh example/resume.md  → dist/
      - v2: python3 -m ats_safe_resume example/resume.md → dist-v2/
      - validate: pytest tests/test_v1_v2_parity.py -v
      - upload-artifacts: dist/ and dist-v2/
```

---

## Success Criteria

- [ ] All 12 tasks complete
- [ ] `ats-safe-resume example/resume.md` produces PDF, DOCX, HTML, TXT, JSON
- [ ] All v2 PDFs have the same content as v1 PDFs (verified via pdftotext)
- [ ] v2 JSON output has correct per-position dates (no v1 bugs)
- [ ] v2 HTML output has no `&amp;` double-escaped entities
- [ ] v2 TXT output has no title duplication
- [ ] v2 DOCX output has accent bar headings matching v1 reference.docx
- [ ] v2 HTML output is print-styled (A4 dimensions, @media print rules)
- [ ] v2 PDF fonts (Source Sans 3) are embedded and subset (pdffonts check)
- [ ] v2 PDF handles multi-page resumes (5 companies × 3 roles = 2+ pages) without crash
- [ ] v2 JSON `basics.summary` has no `**` markdown (stripped by `_strip_markdown()`)
- [ ] All unit tests pass
- [ ] Parity tests pass in CI
- [ ] Dennis's real resume also builds correctly with v2
- [ ] CI artifacts include both v1 and v2 output for comparison