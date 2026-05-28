#!/usr/bin/env python3
"""Generate reference.docx for styled DOCX output.

Creates a Word document with styles matching the PDF aesthetic:
- Source Sans 3 body, 10pt
- Source Code Pro for code/monospace
- Dark gray (#555555) heading colors
- Accent bars (bottom border) under headings
- Compact spacing matching the resume layout

Run: python3 scripts/generate_reference_docx.py
"""

from docx import Document
from docx.shared import Pt, Inches, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
import os

doc = Document()

# ── Page setup ─────────────────────────────────────────────
section = doc.sections[0]
section.top_margin = Inches(0.5)
section.bottom_margin = Inches(0.5)
section.left_margin = Inches(0.7)
section.right_margin = Inches(0.7)
section.page_height = Inches(11.69)  # A4
section.page_width = Inches(8.27)

# ── Helper: set font for a run ─────────────────────────────
def set_run_font(run, name="Source Sans 3", size=Pt(10), color=RGBColor(0x33, 0x33, 0x33), bold=False, italic=False):
    run.font.name = name
    run.font.size = size
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.italic = italic
    # Set East Asian font fallback
    r = run._element
    rPr = r.find(qn('w:rPr'))
    if rPr is None:
        rPr = parse_xml(f'<w:rPr {nsdecls("w")}></w:rPr>')
        r.insert(0, rPr)
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = parse_xml(f'<w:rFonts {nsdecls("w")}></w:rFonts>')
        rPr.insert(0, rFonts)
    rFonts.set(qn('w:ascii'), name)
    rFonts.set(qn('w:hAnsi'), name)
    rFonts.set(qn('w:eastAsia'), name)
    rFonts.set(qn('w:cs'), name)

# ── Helper: set paragraph spacing ──────────────────────────
def set_para_spacing(para, before=0, after=0, line=None):
    pf = para.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if line:
        pf.line_spacing = Pt(line)

# ── Helper: add bottom border (accent bar) ────────────────
def add_accent_bar(para, color_hex="555555", width=12):
    pPr = para._element.find(qn('w:pPr'))
    if pPr is None:
        pPr = parse_xml(f'<w:pPr {nsdecls("w")}></w:pPr>')
        para._element.insert(0, pPr)
    pBdr = parse_xml(
        f'<w:pBdr {nsdecls("w")}>'
        f'  <w:bottom w:val="single" w:sz="{width}" w:space="1" w:color="{color_hex}"/>'
        f'</w:pBdr>'
    )
    pPr.append(pBdr)

# ── Style: Normal ──────────────────────────────────────────
style = doc.styles['Normal']
style.font.name = 'Source Sans 3'
style.font.size = Pt(10)
style.paragraph_format.space_before = Pt(2)
style.paragraph_format.space_after = Pt(2)
style.paragraph_format.line_spacing = Pt(13)

# ── Style: Title ───────────────────────────────────────────
# Name at top: 18pt, bold, dark gray, no spacing
p = doc.add_paragraph()
set_para_spacing(p, before=0, after=0, line=22)
run = p.add_run("Jane Doe")
set_run_font(run, size=Pt(18), color=RGBColor(0x33, 0x33, 0x33), bold=True)

# Subtitle: 11pt, medium gray
p = doc.add_paragraph()
set_para_spacing(p, before=0, after=6, line=16)
run = p.add_run("Senior Product Manager")
set_run_font(run, size=Pt(11), color=RGBColor(0x55, 0x55, 0x55), bold=False)

# Contact line: 9pt
p = doc.add_paragraph()
set_para_spacing(p, before=0, after=10, line=14)
run = p.add_run("San Francisco, CA | jane.doe@email.com | (555) 123-4567 | LinkedIn | GitHub")
set_run_font(run, size=Pt(9), color=RGBColor(0x55, 0x55, 0x55))

# ── Style: Heading 1 (Executive Profile / section headers) ─
p = doc.add_paragraph()
set_para_spacing(p, before=8, after=2, line=16)
run = p.add_run("Executive Profile")
set_run_font(run, size=Pt(11), color=RGBColor(0x55, 0x55, 0x55), bold=True)
add_accent_bar(p)

# Body text
p = doc.add_paragraph()
set_para_spacing(p, before=2, after=4, line=14)
run = p.add_run(
    "Product leader with 10+ years shipping data platforms, SaaS products, "
    "and AI-powered features into production. Combines deep domain expertise "
    "in financial technology with modern product management practices."
)
set_run_font(run, size=Pt(10), color=RGBColor(0x33, 0x33, 0x33))

# ── Style: Heading 2 (Company name) ────────────────────────
p = doc.add_paragraph()
set_para_spacing(p, before=8, after=1, line=16)
run = p.add_run("Acme Corp — San Francisco, CA")
set_run_font(run, size=Pt(10), color=RGBColor(0x22, 0x22, 0x22), bold=True)

# Role title + date
p = doc.add_paragraph()
set_para_spacing(p, before=0, after=2, line=15)
run = p.add_run("Senior Product Manager — Platform & Data Products")
set_run_font(run, size=Pt(10), color=RGBColor(0x55, 0x55, 0x55), italic=True)

# Bullet points
for text in [
    "Grew platform revenue from $5MM to $25MM+ through new product launches.",
    "Launched AI-powered analytics product, reaching $8MM ARR in 18 months.",
    "Reduced average feature delivery time by 40% through improved prioritization.",
]:
    p = doc.add_paragraph(style='List Bullet')
    set_para_spacing(p, before=0, after=1, line=14)
    p.clear()
    run = p.add_run(text)
    set_run_font(run, size=Pt(10), color=RGBColor(0x33, 0x33, 0x33))

# ── Style: Heading for Skills ──────────────────────────────
p = doc.add_paragraph()
set_para_spacing(p, before=8, after=2, line=16)
run = p.add_run("Technical Skills")
set_run_font(run, size=Pt(11), color=RGBColor(0x55, 0x55, 0x55), bold=True)
add_accent_bar(p)

# Skill categories
for cat_name, skills in [
    ("Product & strategy", "Roadmap planning, OKR frameworks, user research"),
    ("Data & analytics", "SQL, Python, A/B testing, cohort analysis"),
]:
    p = doc.add_paragraph()
    set_para_spacing(p, before=1, after=1, line=14)
    run = p.add_run(f"{cat_name}: ")
    set_run_font(run, size=Pt(10), color=RGBColor(0x33, 0x33, 0x33), bold=True)
    run = p.add_run(skills)
    set_run_font(run, size=Pt(10), color=RGBColor(0x33, 0x33, 0x33))

# ── Style: Heading for Education ───────────────────────────
p = doc.add_paragraph()
set_para_spacing(p, before=8, after=2, line=16)
run = p.add_run("Education")
set_run_font(run, size=Pt(11), color=RGBColor(0x55, 0x55, 0x55), bold=True)
add_accent_bar(p)

p = doc.add_paragraph()
set_para_spacing(p, before=1, after=1, line=14)
run = p.add_run("University of California, Berkeley")
set_run_font(run, size=Pt(10), color=RGBColor(0x33, 0x33, 0x33), bold=True)
run = p.add_run(" — B.S. Business Administration, Minor in Computer Science")
set_run_font(run, size=Pt(10), color=RGBColor(0x33, 0x33, 0x33))

# ── Save ───────────────────────────────────────────────────
output_path = os.path.join(os.path.dirname(__file__), '..', 'reference.docx')
doc.save(output_path)
print(f"Generated: {output_path}")
