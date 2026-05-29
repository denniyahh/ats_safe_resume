#!/usr/bin/env python3
"""
Output validation for ATS Safe Resume.

Builds all 5 formats from a markdown resume and validates each one
against a comprehensive checklist. Exits non-zero on any failure.

Usage:
    ./validate_outputs.py                    # uses example/resume.md
    ./validate_outputs.py path/to/resume.md  # custom input
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PASS = "✅"
FAIL = "✗"
WARN = "⚠"

SCRIPT_DIR = Path(__file__).resolve().parent
DIST_DIR = SCRIPT_DIR / "dist"
EXIT_FAILURES = []


def log(status, label, detail=""):
    icon = {"pass": PASS, "fail": FAIL, "warn": WARN}[status]
    msg = f"  {icon} {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    if status == "fail":
        EXIT_FAILURES.append(label)


def build_resume(md_path):
    """Build all output formats from the given markdown file."""
    build_script = SCRIPT_DIR / "build_resume.sh"
    if not build_script.exists():
        print(f"ERROR: build script not found at {build_script}")
        sys.exit(1)

    # Clean dist
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(exist_ok=True)

    result = subprocess.run(
        [str(build_script), str(md_path)],
        capture_output=True, text=True, cwd=SCRIPT_DIR, timeout=120
    )
    if result.returncode != 0:
        print(f"BUILD FAILED:\n{result.stdout}\n{result.stderr}")
        sys.exit(1)

    # Gather outputs
    outputs = {}
    for fmt, ext in [("PDF", "pdf"), ("DOCX", "docx"), ("HTML", "html"),
                      ("TXT", "txt"), ("JSON", "json")]:
        f = DIST_DIR / f"resume.{ext}"
        outputs[fmt] = f if f.exists() else None
    return outputs


def check_pdf(path):
    """Validate PDF output."""
    print("\n── PDF ──")
    if not path:
        return log("fail", "PDF file missing")

    log("pass", f"File exists ({path.stat().st_size} bytes)")

    # Page count
    r = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True)
    if r.returncode != 0:
        return log("fail", f"pdfinfo failed: {r.stderr}")
    pages = None
    for line in r.stdout.splitlines():
        if line.startswith("Pages:"):
            pages = int(line.split(":")[1].strip())
            break
    if pages is None:
        log("fail", "Could not read page count")
    elif 1 <= pages <= 2:
        log("pass", f"Page count: {pages}")
    else:
        log("warn", f"Unusual page count: {pages}")

    # Font embedding
    r = subprocess.run(["pdffonts", str(path)], capture_output=True, text=True)
    lines = r.stdout.strip().splitlines()
    if len(lines) < 2:
        return log("fail", "No font info")
    fonts = []
    header = lines[1]  # column headers
    for line in lines[2:]:
        if not line.strip():
            continue
        # pdffonts columns: name, type, encoding, emb, sub, uni, object ID
        # Name can contain spaces? No. Type can be "CID Type 0C" (3 tokens).
        # Parse from the right: last 4 fields are fixed-width (yes/no + ID)
        parts = line.rsplit(None, 4)
        if len(parts) >= 5:
            fonts.append({
                "name": parts[0],
                "emb": parts[-4],
                "sub": parts[-3],
            })
    all_embedded = all(f["emb"] == "yes" for f in fonts)
    all_subset = all(f["sub"] == "yes" for f in fonts)
    font_names = [f["name"] for f in fonts]
    has_sourcesans = any("SourceSans" in n for n in font_names)

    if has_sourcesans:
        log("pass", f"Source Sans 3 fonts: {len(fonts)} faces")
    else:
        log("warn", "No Source Sans 3 fonts found")
    if all_embedded:
        log("pass", "All fonts embedded")
    else:
        log("fail", f"Some fonts not embedded: {fonts}")
    if all_subset:
        log("pass", "All fonts subsetted")

    # Text extraction (ATS check)
    r = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True)
    text = r.stdout
    if not text.strip():
        return log("fail", "PDF text extraction empty")

    # Check for garbled text
    garbled = len(re.findall(r'[^\x20-\x7E\u00A0-\u00FF\u2013\u2014\u2018\u2019\u201C\u201D\n•|]', text))
    if garbled > 10:
        log("warn", f"{garbled} potentially garbled characters detected")

    return text


def check_docx(path):
    """Validate DOCX output."""
    print("\n── DOCX ──")
    if not path:
        return log("fail", "DOCX file missing")

    log("pass", f"File exists ({path.stat().st_size} bytes)")

    try:
        from docx import Document
        doc = Document(str(path))
    except ImportError as e:
        return log("warn", f"Cannot analyze: {e}")

    paras = [p for p in doc.paragraphs if p.text.strip()]
    if len(paras) < 20:
        return log("fail", f"Only {len(paras)} paragraphs with text (expected 20+)")

    log("pass", f"{len(paras)} paragraphs with text")

    # Check for heading styles
    h1 = sum(1 for p in doc.paragraphs if p.style.name == "Heading 1")
    h2 = sum(1 for p in doc.paragraphs if p.style.name == "Heading 2")
    h3 = sum(1 for p in doc.paragraphs if p.style.name == "Heading 3")
    if h1 + h2 + h3 > 0:
        log("pass", f"Styled headings: H1={h1}, H2={h2}, H3={h3}")
    else:
        log("warn", "No heading styles used")

    # Check for font usage
    all_text = "\n".join(p.text for p in doc.paragraphs)
    return all_text


def check_html(path, pdf_text):
    """Validate HTML output."""
    print("\n── HTML ──")
    if not path:
        return log("fail", "HTML file missing")

    log("pass", f"File exists ({path.stat().st_size} bytes)")

    html = path.read_text(encoding="utf-8", errors="replace")

    # Check title tag
    title_match = re.search(r'<title>(.*?)</title>', html)
    if title_match:
        log("pass", f"Title tag: {title_match.group(1)[:60]}")
    else:
        log("warn", "No <title> tag found")

    # Check body content
    body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
    if not body_match:
        return log("fail", "No <body> tag")

    body = body_match.group(1)
    # Strip tags for content comparison
    text = re.sub(r'<[^>]+>', '\n', body)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Check for double-escaped HTML entities (e.g., &amp;amp;)
    if "&amp;amp;" in html:
        log("fail", "Double-escaped HTML entities (&amp;amp;) found")
    if "&amp;" in html:
        log("pass", "HTML entities properly single-escaped (&amp; = &)")

    return text


def check_txt(path, pdf_text):
    """Validate TXT output."""
    print("\n── TXT ──")
    if not path:
        return log("fail", "TXT file missing")

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [l for l in text.split("\n") if l.strip()]

    log("pass", f"File exists ({path.stat().st_size} bytes, {len(lines)} lines)")

    # Check no title duplication (>2 occurrences of name at top)
    first_lines = text.strip().split("\n")[:5]
    name_count = sum(1 for l in first_lines if "Dennis Kim" in l or "Jane Doe" in l)
    if name_count > 2:
        log("warn", f"Title appears {name_count} times in first 5 lines (expected 1-2)")

    return text


def check_json(path):
    """Validate JSON Resume output."""
    print("\n── JSON ──")
    if not path:
        return log("fail", "JSON file missing")

    log("pass", f"File exists ({path.stat().st_size} bytes)")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return log("fail", f"Invalid JSON: {e}")

    # Validate required fields
    checks = [
        ("basics.name", "basics" in data and "name" in data["basics"]),
        ("basics.email or phone", "basics" in data and ("email" in data["basics"] or "phone" in data["basics"])),
        ("work array", isinstance(data.get("work"), list)),
        ("education array", isinstance(data.get("education"), list)),
        ("skills array", isinstance(data.get("skills"), list)),
    ]
    for label, ok in checks:
        log("pass" if ok else "fail", label)

    # Validate work dates per-position
    for w in data.get("work", []):
        for p in w.get("positions", []):
            if "startDate" not in p:
                log("fail", f"Missing date for: {w.get('company','?')} / {p.get('position','?')}")

    # Check dict key order (should be: basics, work, skills, education)
    keys = list(data.keys())
    if keys == ["basics", "work", "skills", "education"]:
        log("pass", "Section order: basics → work → skills → education")
    else:
        log("warn", f"Section order: {keys}")

    return data


def cross_check(pdf_text, docx_text, html_text, txt_text, json_data):
    """Verify key content appears in ALL formats."""
    print("\n── Cross-Format Consistency ──")

    checks = {
        "Name (Dennis Kim or Jane Doe)": r"Dennis Kim|Jane Doe",
        "Executive Profile heading": r"Executive Profile",
        "Professional Experience heading": r"Professional Experience",
        "Education heading": r"Education",
        "Technical Skills heading": r"Technical Skills",
        "Email domain": r"[@]",
    }

    sources = {
        "PDF": pdf_text or "",
        "DOCX": docx_text or "",
        "HTML": html_text or "",
        "TXT": txt_text or "",
    }

    for label, pattern in checks.items():
        results = []
        for fmt, text in sources.items():
            found = bool(re.search(pattern, text, re.IGNORECASE))
            results.append(found)
        if all(results):
            log("pass", label)
        else:
            failing = [fmt for fmt, found in zip(sources.keys(), results) if not found]
            log("fail", label, f"Missing in: {', '.join(failing)}")

    # Cross-verify JSON company count vs PDF
    if json_data and pdf_text:
        pdf_companies = re.findall(r'^(MarketAxess|Tradeweb|Interactive Data|Thomson Reuters|Acme Corp|TechCorp|DataFirst)', pdf_text, re.MULTILINE)
        json_companies = [w.get("company", "") for w in json_data.get("work", [])]
        # Check at least some overlap
        overlap = set(pdf_companies) & set(json_companies)
        if overlap:
            log("pass", f"Companies match across formats: {len(overlap)} shared")
        else:
            log("warn", "No company name overlap between PDF and JSON")


def check_crafted_footer(pdf_text, docx_text, html_text, txt_text):
    """Verify the crafted footer appears in all formats when enabled."""
    print("\n── Crafted Footer ──")

    label = " craft/github/denniyahh/ats_safe_resume"
    sources = {
        "PDF": pdf_text or "",
        "DOCX": docx_text or "",
        "HTML": html_text or "",
        "TXT": txt_text or "",
    }

    for fmt, text in sources.items():
        if "ats_safe_resume" in text or "crafted with" in text:
            log("pass", f"Footer present in {fmt}")
        else:
            log("warn", f"Footer missing in {fmt}")


def main():
    md_path = sys.argv[1] if len(sys.argv) > 1 else SCRIPT_DIR / "example" / "resume.md"
    md_path = Path(md_path).resolve()

    if not md_path.exists():
        print(f"ERROR: Input not found: {md_path}")
        sys.exit(1)

    print(f"Building from: {md_path}")

    # Ensure executables exist
    for cmd in ["pandoc", "lualatex", "pdftotext", "pdfinfo", "pdffonts"]:
        if not shutil.which(cmd):
            print(f"WARNING: {cmd} not found — some checks will be skipped")

    # Build
    outputs = build_resume(md_path)

    # Validate each format
    pdf_text = check_pdf(outputs.get("PDF"))
    docx_text = check_docx(outputs.get("DOCX"))
    html_text = check_html(outputs.get("HTML"), pdf_text)
    txt_text = check_txt(outputs.get("TXT"), pdf_text)
    json_data = check_json(outputs.get("JSON"))

    # Cross-format checks
    cross_check(pdf_text, docx_text, html_text, txt_text, json_data)
    check_crafted_footer(pdf_text, docx_text, html_text, txt_text)

    # Summary
    print(f"\n{'='*50}")
    total = len(EXIT_FAILURES)
    if total == 0:
        print(f" {PASS} ALL CHECKS PASSED")
    else:
        print(f" {FAIL} {total} FAILURE(S):")
        for f in EXIT_FAILURES:
            print(f"     • {f}")

    sys.exit(total)


if __name__ == "__main__":
    main()
