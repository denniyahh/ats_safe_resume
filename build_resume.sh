#!/usr/bin/env bash
# ATS Safe Resume — Build Script
#
# Zero-dependency orchestrator: reads YAML frontmatter from resume.md,
# selects theme, adjusts page mode, applies ATS normalization, and
# drives pandoc via pandoc-defaults.yaml.
#
# Usage:
#   ./build_resume.sh                  # uses resume.md by default
#   ./build_resume.sh path/to/file.md  # custom input
#
# Env vars for power users:
#   OUT_DIR=dist                       # output directory
#   BASENAME=resume                    # base filename for outputs
#   PDF_ENGINE=lualatex                # override PDF engine
#   ATS_SAFE=1                         # enable/disable ATS normalization
#   KEEP_TMP=0                         # keep normalized temp file
#   THEME=dark                         # override theme from frontmatter
#   PAGE_MODE=two                      # override page mode from frontmatter
#   FORMATS=pdf,docx,html,txt,json     # comma-separated output formats
#
# Outputs (in OUT_DIR):
#   resume.pdf   resume.docx   resume.html   resume.txt   resume.json

set -euo pipefail

#########################
# Configuration
#########################

INPUT_MD="${1:-resume.md}"
OUT_DIR="${OUT_DIR:-dist}"
FORMATS="${FORMATS:-pdf,docx,html,txt,json}"

# Detect PDF engine (lualatex → xelatex → tectonic)
PDF_ENGINE="${PDF_ENGINE:-}"
ATS_SAFE="${ATS_SAFE:-1}"
KEEP_TMP="${KEEP_TMP:-0}"

# Script location (for relative paths to templates/themes)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

#########################
# Helpers
#########################

err() { echo "ERROR: $*" >&2; exit 1; }

check_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    return 1
  fi
  return 0
}

pick_pdf_engine() {
  if [[ -n "${PDF_ENGINE}" ]]; then
    echo "${PDF_ENGINE}"
    return 0
  fi
  if check_command "lualatex"; then
    echo "lualatex"
  elif check_command "xelatex"; then
    echo "xelatex"
  elif check_command "tectonic"; then
    echo "tectonic"
  else
    err "No LaTeX PDF engine found (lualatex/xelatex/tectonic). Install one or set PDF_ENGINE."
  fi
}

#########################
# YAML frontmatter parser
#########################

parse_frontmatter() {
  # Extract YAML frontmatter (between first two --- lines) and parse with Python.
  # Returns: theme, page_mode, title, and title_metadata (for pandoc --metadata)
  python3 - "$INPUT_MD" <<'PY'
import sys, re

text = open(sys.argv[1]).read()
m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
if not m:
    # No frontmatter — use defaults
    print('THEME="dark"')
    print('PAGE_MODE="two"')
    print('TITLE="Your Name — Resume"')
    print('FONTSIZE="10pt"')
    print('GEOMETRY="left=0.7in,right=0.7in,top=0.5in,bottom=0.5in"')
    sys.exit(0)

# Minimal YAML parser (avoids dependency on PyYAML)
front = m.group(1)
result = {}

for line in front.split('\n'):
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    # Strip inline comments (everything after unquoted #)
    if '#' in line:
        # Handle potential # inside quoted strings
        parsed = False
        in_quote = False
        quote_char = None
        for i, ch in enumerate(line):
            if ch in ('"', "'"):
                if not in_quote:
                    in_quote = True
                    quote_char = ch
                elif ch == quote_char:
                    in_quote = False
            elif ch == '#' and not in_quote:
                line = line[:i].rstrip()
                parsed = True
                break
    if ':' in line:
        key, _, val = line.partition(':')
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        result[key] = val

theme = result.get('theme', 'dark')
page_mode = result.get('page_mode', 'two')
title = result.get('title', 'Your Name — Resume')
fontsize = result.get('fontsize', '10pt')
geometry = result.get('geometry', 'left=0.7in,right=0.7in,top=0.5in,bottom=0.5in')

# Quote values for safe eval in the shell
print(f"THEME=\"{theme}\"")
print(f"PAGE_MODE=\"{page_mode}\"")
print(f"TITLE=\"{title}\"")
print(f"FONTSIZE=\"{fontsize}\"")
print(f"GEOMETRY=\"{geometry}\"")
PY
}

#########################
# ATS-safe normalization
#########################

normalize_md_for_ats() {
  local in="$1"
  local out="$2"
  python3 - "$in" "$out" <<'PY'
import sys
from pathlib import Path

inp = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")

# Typography → ATS-safe ASCII equivalents
replacements = {
    "\u00B7": " | ",    # middle dot → pipe separator
    "\u2022": "*",      # bullet
    "\u2013": "-",      # en dash → hyphen
    "\u2014": "--",     # em dash → double hyphen
    "\u2212": "-",      # minus sign → hyphen
    "\u00A0": " ",      # non-breaking space → regular space
    "\u2018": "'",      # left single quote
    "\u2019": "'",      # right single quote
    "\u201C": '"',      # left double quote
    "\u201D": '"',      # right double quote
}

for uni_char, ascii_repl in replacements.items():
    inp = inp.replace(uni_char, ascii_repl)

# Strip soft hyphen, BOM, zero-width characters
for zw in ["\u00AD", "\uFEFF", "\u200B", "\u200C", "\u200D", "\u2060"]:
    inp = inp.replace(zw, "")

# Collapse repeated spaces
while "  " in inp:
    inp = inp.replace("  ", " ")

Path(sys.argv[2]).write_text(inp, encoding="utf-8")
PY
}

#########################
# JSON Resume output
#########################

generate_json_resume() {
  local in="$1"
  local out="$2"
  python3 - "$in" "$out" <<'PY'
import sys, json, re
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")

# Strip YAML frontmatter
text = re.sub(r'^---\s*\n.*?\n---\s*\n', '', text, flags=re.DOTALL)

# Extract sections using markdown headings
sections = {}
current_section = None
current_content = []

for line in text.split('\n'):
    h2 = re.match(r'^## (.+)', line)
    h1 = re.match(r'^# (.+)', line)
    if h1 and current_section is None:
        current_section = 'header'
        continue  # skip the name heading — we extract it below
    if h2:
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()
        current_section = h2.group(1).strip()
        current_content = []
    else:
        current_content.append(line)

if current_section:
    sections[current_section] = '\n'.join(current_content).strip()

# Build JSON Resume schema
resume = {"basics": {}, "work": [], "education": [], "skills": []}

# Basics from first line and contact info
lines = text.strip().split('\n')
if lines:
    name_line = lines[0].lstrip('#').strip()
    resume["basics"]["name"] = name_line

    # Find contact line (contains email, phone, etc.)
    for i, l in enumerate(lines[1:15]):
        l = l.strip()
        if l and ('@' in l or 'linkedin.com' in l or 'github.com' in l):
            clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', l)
            clean = re.sub(r'\*\*', '', clean)
            parts = [p.strip() for p in clean.replace(' | ', ' · ').split('·')]
            for p in parts:
                p = p.strip()
                if '@' in p:
                    resume["basics"]["email"] = p
                elif 'linkedin.com' in p.lower():
                    resume["basics"]["profiles"] = resume["basics"].get("profiles", [])
                    resume["basics"]["profiles"].append({"network": "LinkedIn", "username": p.split('/')[-1], "url": p})
                elif 'github.com' in p.lower():
                    resume["basics"]["profiles"] = resume["basics"].get("profiles", [])
                    resume["basics"]["profiles"].append({"network": "GitHub", "username": p.split('/')[-1], "url": p})
                elif re.match(r'^[\d\-\(\)\s\+]+$', p):
                    resume["basics"]["phone"] = p
            break

# Summary (Executive Profile)
for sec_name in ['Executive Profile', 'Professional Summary', 'Summary']:
    if sec_name in sections:
        resume["basics"]["summary"] = sections[sec_name]
        break

# Work experience
if 'Professional Experience' in sections:
    exp_text = sections['Professional Experience']
    # Split by ### or **Company** patterns
    jobs = re.split(r'\n(?=### |\*\*\[)', exp_text)
    for job in jobs:
        job = job.strip()
        if not job:
            continue
        entry = {}
        # Company and title
        company_match = re.search(r'\*\*\[?([^\]]*)\]?\*\*.*?\*\*(.*?)\*\*', job, re.DOTALL)
        if company_match:
            entry["company"] = company_match.group(1).strip()
            date_match = re.search(r'\*(.{3,40})\*', job.split('\n')[0] if '\n' in job else job)
            if not date_match:
                date_match = re.search(r'\*(.{3,40})\*', job)
            if date_match:
                entry["startDate"] = date_match.group(1).strip()
        # Position
        pos_match = re.search(r'\*\*(.+?)\*\*', job)
        if pos_match and 'company' not in entry:
            entry["position"] = pos_match.group(1).strip()
        # Bullet points as highlights
        bullets = re.findall(r'^- (.+)$', job, re.MULTILINE)
        if bullets:
            entry["highlights"] = bullets
        elif 'summary' not in entry:
            entry["summary"] = job[:500]

        if entry.get("company") or entry.get("position"):
            resume["work"].append(entry)

# Education
if 'Education' in sections:
    edu_text = sections['Education']
    schools = re.split(r'\n(?=\*\*)', edu_text)
    for school in schools:
        school = school.strip()
        if not school:
            continue
        entry = {}
        name_match = re.search(r'\*\*(.+?)\*\*', school)
        if name_match:
            entry["institution"] = name_match.group(1).strip()
        degree_match = re.search(r'— (.+)', school)
        if degree_match:
            entry["studyType"] = degree_match.group(1).strip()
        if entry:
            resume["education"].append(entry)

# Skills
if 'Technical Skills' in sections:
    skills_text = sections['Technical Skills']
    for line in skills_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Parse "Category: skill1, skill2, skill3" or "**Category:** skill1, skill2"
        cat_match = re.match(r'\*\*(.+?):?\*\*\s*(.+)', line)
        if cat_match:
            resume["skills"].append({
                "name": cat_match.group(1).strip(),
                "keywords": [k.strip() for k in cat_match.group(2).split(',')]
            })

Path(sys.argv[2]).write_text(json.dumps(resume, indent=2), encoding="utf-8")
print(f"  JSON Resume written: {sys.argv[2]}")
PY
}

#########################
# Pre-flight checks
#########################

[[ -f "$INPUT_MD" ]] || err "Input markdown file not found: $INPUT_MD"
check_command "pandoc" || err "Required command 'pandoc' not found in PATH."

PDF_ENGINE="$(pick_pdf_engine)"
check_command "$PDF_ENGINE" || err "Required PDF engine '$PDF_ENGINE' not found in PATH."

mkdir -p "$OUT_DIR"

#########################
# Parse frontmatter
#########################

echo "Parsing frontmatter from $INPUT_MD..."

# Save explicit env vars before eval so they take priority over frontmatter
ENV_THEME="${THEME:-}"
ENV_PAGE_MODE="${PAGE_MODE:-}"
ENV_FONTSIZE="${FONTSIZE:-}"
ENV_GEOMETRY="${GEOMETRY:-}"

eval "$(parse_frontmatter)"

# Priority: explicit env var > frontmatter > hardcoded default
THEME="${ENV_THEME:-${THEME:-dark}}"
PAGE_MODE="${ENV_PAGE_MODE:-${PAGE_MODE:-two}}"
FONTSIZE="${ENV_FONTSIZE:-${FONTSIZE:-10pt}}"
GEOMETRY="${ENV_GEOMETRY:-${GEOMETRY:-left=0.7in,right=0.7in,top=0.5in,bottom=0.5in}}"

echo "  Theme:      $THEME"
echo "  Page mode:  $PAGE_MODE"
echo "  Font size:  $FONTSIZE"

# Validate theme
THEME_FILE="$SCRIPT_DIR/themes/${THEME}.tex"
if [[ ! -f "$THEME_FILE" ]]; then
  echo "WARNING: Theme '$THEME' not found at $THEME_FILE. Using dark."
  THEME_FILE="$SCRIPT_DIR/themes/dark.tex"
fi

# Validate template
TEMPLATE_FILE="$SCRIPT_DIR/templates/eisvogel.latex"
if [[ ! -f "$TEMPLATE_FILE" ]]; then
  err "Template not found: $TEMPLATE_FILE"
fi

# Page mode adjustments
if [[ "$PAGE_MODE" == "one" ]]; then
  FONTSIZE="10pt"
  GEOMETRY="left=0.6in,right=0.6in,top=0.4in,bottom=0.4in"
  echo "  Page mode one: tightened margins for single-page fit"
fi

# Build a temporary defaults YAML with theme preamble injected,
# so the theme is included BEFORE resume-preamble.tex
DEFAULTS_FILE="$(mktemp /tmp/pandoc_defaults_XXXXXX.yaml)"

cat > "$DEFAULTS_FILE" <<DEFAULTS
from: markdown+smart
standalone: true
pdf-engine: $PDF_ENGINE
template: $TEMPLATE_FILE
variables:
  mainfont: Source Sans 3
  mainfontoptions: Ligatures=NoCommon
  monofont: Source Code Pro
  fontsize: $FONTSIZE
  colorlinks: true
  linkcolor: darkgray
metadata:
  title: "$TITLE"
include-in-header:
  - $THEME_FILE
  - $SCRIPT_DIR/resume-preamble.tex
DEFAULTS

#########################
# Build
#########################

BASENAME="${BASENAME:-$(basename "${INPUT_MD%.*}")}"

for format in $(echo "$FORMATS" | tr ',' ' '); do
  case "$format" in
    pdf)
      echo "Building PDF (engine: $PDF_ENGINE)..."
      PDF_INPUT="$INPUT_MD"
      TMP_MD=""
      if [[ "$ATS_SAFE" == "1" ]]; then
        TMP_MD="$(mktemp /tmp/resume_ats_XXXXXX.md)"
        normalize_md_for_ats "$INPUT_MD" "$TMP_MD"
        PDF_INPUT="$TMP_MD"
        echo "  ATS_SAFE=1: using normalized markdown"
      fi
      pandoc "$PDF_INPUT" \
        -d "$DEFAULTS_FILE" \
        -o "${OUT_DIR}/${BASENAME}.pdf" \
        --variable "geometry=$GEOMETRY"

      [[ -n "${TMP_MD}" && "$KEEP_TMP" != "1" ]] && rm -f "$TMP_MD"
      ;;

    docx)
      echo "Building DOCX..."
      DOCX_INPUT="$INPUT_MD"
      TMP_DOCX=""
      if [[ "$ATS_SAFE" == "1" ]]; then
        TMP_DOCX="$(mktemp /tmp/resume_ats_XXXXXX.md)"
        normalize_md_for_ats "$INPUT_MD" "$TMP_DOCX"
        DOCX_INPUT="$TMP_DOCX"
      fi
      pandoc "$DOCX_INPUT" \
        -o "${OUT_DIR}/${BASENAME}.docx" \
        --metadata=title:"$TITLE" \
        --standalone \
        --reference-doc="$SCRIPT_DIR/reference.docx"

      [[ -n "${TMP_DOCX}" && "$KEEP_TMP" != "1" ]] && rm -f "$TMP_DOCX"
      ;;

    html)
      echo "Building HTML..."
      pandoc "$INPUT_MD" \
        -o "${OUT_DIR}/${BASENAME}.html" \
        --metadata=title:"$TITLE" \
        --standalone
      ;;

    txt)
      echo "Building plain text..."
      TXT_INPUT="$INPUT_MD"
      TMP_TXT=""
      if [[ "$ATS_SAFE" == "1" ]]; then
        TMP_TXT="$(mktemp /tmp/resume_ats_XXXXXX.md)"
        normalize_md_for_ats "$INPUT_MD" "$TMP_TXT"
        TXT_INPUT="$TMP_TXT"
      fi
      pandoc "$TXT_INPUT" \
        -o "${OUT_DIR}/${BASENAME}.txt" \
        --metadata=title:"$TITLE" \
        --standalone \
        -t plain

      [[ -n "${TMP_TXT}" && "$KEEP_TMP" != "1" ]] && rm -f "$TMP_TXT"
      ;;

    json)
      echo "Building JSON Resume..."
      generate_json_resume "$INPUT_MD" "${OUT_DIR}/${BASENAME}.json"
      ;;

    *)
      echo "WARNING: Unknown format '$format'. Skipping."
      ;;
  esac
done

# Copy PDF to example/ for committed demo
if [[ -f "${OUT_DIR}/${BASENAME}.pdf" ]]; then
  mkdir -p "$SCRIPT_DIR/example"
  cp "${OUT_DIR}/${BASENAME}.pdf" "$SCRIPT_DIR/example/${BASENAME}.pdf"
  echo "  Demo PDF copied to example/resume.pdf"
fi

# Cleanup
rm -f "$DEFAULTS_FILE"

#########################
# Summary
#########################

echo ""
echo "Build complete. Outputs:"
for f in "${OUT_DIR}/${BASENAME}".*; do
  if [[ -f "$f" ]]; then
    echo "  - $f"
  fi
done
