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
INPUT_DIR="$(cd "$(dirname "$INPUT_MD")" && pwd)"
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
    print('CRAFTED_FOOTER="true"')
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

mainfont = result.get('mainfont', 'Source Sans 3')
monofont = result.get('monofont', 'Source Code Pro')
crafted_footer = result.get('crafted_footer', 'true')

# Quote values for safe eval in the shell
print(f"THEME=\"{theme}\"")
print(f"PAGE_MODE=\"{page_mode}\"")
print(f"TITLE=\"{title}\"")
print(f"FONTSIZE=\"{fontsize}\"")
print(f"GEOMETRY=\"{geometry}\"")
print(f"MAINFONT=\"{mainfont}\"")
print(f"MONOFONT=\"{monofont}\"")
print(f"CRAFTED_FOOTER=\"{crafted_footer}\"")
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

# Helper: strip HTML comments from text
def strip_html_comments(t):
    return re.sub(r'<!--.*?-->', '', t, flags=re.DOTALL)

# Helper: smart split by markdown H3 headings (company name)
def split_by_h3(block):
    """Split text into chunks at each ### Company heading."""
    parts = re.split(r'\n(?=### )', block)
    return [p.strip() for p in parts if p.strip()]

# Strip YAML frontmatter
text = re.sub(r'^---\s*\n.*?\n---\s*\n', '', text, flags=re.DOTALL)

# Strip HTML comments from the raw text first
text = strip_html_comments(text)

# Extract sections using markdown headings
sections = {}
current_section = None
current_content = []

for line in text.split('\n'):
    h2 = re.match(r'^## (.+)', line)
    h1 = re.match(r'^# (.+)', line)
    if h1 and current_section is None:
        current_section = 'header'
        continue
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
resume = {"basics": {}, "work": [], "skills": [], "education": []}

# ── Basics ──────────────────────────────────────────────────────
lines = text.strip().split('\n')
if lines:
    name_line = lines[0].lstrip('#').strip()
    resume["basics"]["name"] = name_line

    # Find contact line (contains email, phone, linkedin, github)
    for i, l in enumerate(lines[1:15]):
        l = l.strip()
        if not l or ('@' not in l and 'linkedin.com' not in l.lower() and 'github.com' not in l.lower()):
            continue
        # Extract URL <-> text mappings from markdown links first
        url_map = {}
        for text_part, url in re.findall(r'\[([^\]]+)\]\(([^)]+)\)', l):
            url_map[text_part.strip()] = url
        # Strip markdown link syntax, keep visible text
        clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', l)
        clean = re.sub(r'\*\*', '', clean)
        # Normalize separators to middle-dot for splitting
        parts = [p.strip() for p in clean.replace(' | ', ' · ').split('·')]
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if '@' in p:
                resume["basics"]["email"] = p
            elif p.lower() in [k.lower() for k in url_map]:
                url = url_map[p]
                if 'linkedin.com' in url.lower():
                    resume["basics"].setdefault("profiles", []).append({
                        "network": "LinkedIn",
                        "username": url.rstrip('/').split('/')[-1],
                        "url": url
                    })
                elif 'github.com' in url.lower():
                    resume["basics"].setdefault("profiles", []).append({
                        "network": "GitHub",
                        "username": url.rstrip('/').split('/')[-1],
                        "url": url
                    })
            elif re.match(r'^[\d\-\(\)\s\+]+$', p):
                resume["basics"]["phone"] = p
            elif p.lower().startswith('http'):
                # Bare URL, not wrapped in markdown link syntax
                if 'linkedin.com' in p.lower():
                    resume["basics"].setdefault("profiles", []).append({
                        "network": "LinkedIn",
                        "username": p.rstrip('/').split('/')[-1],
                        "url": p
                    })
                elif 'github.com' in p.lower():
                    resume["basics"].setdefault("profiles", []).append({
                        "network": "GitHub",
                        "username": p.rstrip('/').split('/')[-1],
                        "url": p
                    })
        break

# ── Summary ─────────────────────────────────────────────────────
for sec_name in ['Executive Profile', 'Professional Summary', 'Summary']:
    if sec_name in sections:
        summary = sections[sec_name]
        # Remove any remaining HTML comments
        summary = strip_html_comments(summary)
        # Remove bold markers for clean text
        summary = re.sub(r'\*\*', '', summary)
        resume["basics"]["summary"] = summary.strip()
        break

# ── Work Experience ─────────────────────────────────────────────
if 'Professional Experience' in sections:
    exp_text = sections['Professional Experience']
    # Split into company blocks by ### header
    company_blocks = split_by_h3(exp_text)

    for block in company_blocks:
        lines = block.split('\n')
        entry = {}

        # Line 0: ### [Company Name](url) — City, State
        first = lines[0].strip()
        company_match = re.match(r'^###\s+\[([^\]]+)\]\(([^)]+)\)\s*[—–-]?\s*(.*)$', first)
        if company_match:
            entry["company"] = company_match.group(1).strip()
            entry["url"] = company_match.group(2).strip()
        else:
            # Plain ### Company Name — City (no link)
            company_match = re.match(r'^###\s+([^—–]+)\s*[—–]\s*(.*)$', first)
            if company_match:
                name = company_match.group(1).strip()
                # Strip trailing parentheticals like "(now [ICE Data...])"
                name = re.sub(r'\s*\(.*\)\s*$', '', name).strip()
                entry["company"] = name
            else:
                # ### Company Name (no dash)
                company_match = re.match(r'^###\s+(.+)$', first)
                if company_match:
                    entry["company"] = company_match.group(1).strip()

        # Lines 1+: roles and bullets
        current_position = None
        current_highlights = []
        current_date = ""
        role_lines = lines[1:]

        for rl in role_lines:
            rl = rl.strip()
            if not rl:
                continue
            # Role title line: **Title** — Subtitle
            role_match = re.match(r'^\*\*(.+?)\*\*\s*[—–-]?\s*(.*)$', rl)
            if role_match:
                # Save previous role if exists
                if current_position:
                    pos = {"position": current_position, "highlights": current_highlights}
                    if current_date:
                        pos["startDate"] = current_date
                    entry.setdefault("positions", []).append(pos)
                current_position = role_match.group(1).strip()
                sub = role_match.group(2).strip()
                current_highlights = []
                # Check if date is inline in subtitle (e.g., "(2005–2007)")
                inline_date = re.search(r'\((\d{4}\s*[–-]\s*\d{4})\)', sub)
                if not inline_date:
                    inline_date = re.search(r'\((\w+\s+\d{4}\s*[–-]\s*(?:\w+\s+\d{4}|Present))\)', sub)
                if inline_date:
                    current_date = inline_date.group(1).strip()
                    # Remove date from subtitle
                    sub = sub[:inline_date.start()] + sub[inline_date.end():]
                # Use subtitle as department/team
                if sub.strip():
                    current_department = sub.strip().strip('(').strip(')').strip()
                continue
            # Date line: *Jun 2021 – Present*
            date_match = re.match(r'^\*(.+?)\*$', rl)
            if date_match:
                current_date = date_match.group(1).strip()
                continue
            # Bullet point: - something
            bullet_match = re.match(r'^- (.+)$', rl)
            if bullet_match:
                bullet_text = re.sub(r'\*\*', '', bullet_match.group(1)).strip()
                current_highlights.append(bullet_text)

        # Save last role
        if current_position:
            pos = {"position": current_position, "highlights": current_highlights}
            if current_date:
                pos["startDate"] = current_date
            entry.setdefault("positions", []).append(pos)
        # Add all highlights to top-level for broad compatibility
        all_highlights = []
        for pos in entry.get("positions", []):
            all_highlights.extend(pos.get("highlights", []))
        if all_highlights:
            entry["highlights"] = all_highlights

        if entry.get("company") or entry.get("positions"):
            resume["work"].append(entry)

# ── Skills ──────────────────────────────────────────────────────
if 'Technical Skills' in sections:
    skills_text = sections['Technical Skills']
    for line in skills_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        cat_match = re.match(r'^\*\*(.+?):?\*\*\s*(.+)$', line)
        if cat_match:
            name = cat_match.group(1).strip().rstrip(':').strip()
            kw = cat_match.group(2).strip()
            keywords = [k.strip() for k in re.split(r'[,;]', kw) if k.strip()]
            resume["skills"].append({"name": name, "keywords": keywords})

# ── Education ───────────────────────────────────────────────────
if 'Education' in sections:
    edu_text = sections['Education']
    for line in edu_text.split('\n'):
        line = line.strip()
        if not line:
            continue
        entry = {}
        name_match = re.match(r'^\*\*(.+?)\*\*\s*[—–-]?\s*(.+)$', line)
        if name_match:
            entry["institution"] = name_match.group(1).strip()
            entry["studyType"] = name_match.group(2).strip()
        if entry:
            resume["education"].append(entry)

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
ENV_MAINFONT="${MAINFONT:-}"
ENV_MONOFONT="${MONOFONT:-}"
ENV_CRAFTED_FOOTER="${CRAFTED_FOOTER:-}"

eval "$(parse_frontmatter)"

# Priority: explicit env var > frontmatter > hardcoded default
THEME="${ENV_THEME:-${THEME:-dark}}"
PAGE_MODE="${ENV_PAGE_MODE:-${PAGE_MODE:-two}}"
FONTSIZE="${ENV_FONTSIZE:-${FONTSIZE:-10pt}}"
MAINFONT="${ENV_MAINFONT:-${MAINFONT:-Source Sans 3}}"
MONOFONT="${ENV_MONOFONT:-${MONOFONT:-Source Code Pro}}"
CRAFTED_FOOTER="${ENV_CRAFTED_FOOTER:-${CRAFTED_FOOTER:-true}}"
GEOMETRY="${ENV_GEOMETRY:-${GEOMETRY:-left=0.7in,right=0.7in,top=0.5in,bottom=0.5in}}"

echo "  Theme:      $THEME"
echo "  Page mode:  $PAGE_MODE"
echo "  Font size:  $FONTSIZE"
echo "  Main font:  $MAINFONT"
echo "  Mono font:  $MONOFONT"
echo "  Footer:     ${CRAFTED_FOOTER}"

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
  FONTSIZE="9.5pt"
  GEOMETRY="left=0.6in,right=0.6in,top=0.4in,bottom=0.4in"
  echo "  Page mode one: tightened margins for single-page fit"
fi

# Crafted footer (enabled by default)
CRAFTED_FOOTER_INCLUDE=""
if [[ "${CRAFTED_FOOTER,,}" == "true" ]]; then
  CRAFTED_FOOTER_INCLUDE="  - $SCRIPT_DIR/crafted-footer.tex"
  echo "  Footer:     ats_safe_resume credit"
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
  mainfont: $MAINFONT
  mainfontoptions: Ligatures=NoCommon
  monofont: $MONOFONT
  fontsize: $FONTSIZE
  colorlinks: true
  linkcolor: darkgray
metadata:
  title: "$TITLE"
include-in-header:
  - $THEME_FILE
  - $SCRIPT_DIR/resume-preamble.tex
include-after-body:
$CRAFTED_FOOTER_INCLUDE
DEFAULTS

# Support for user overrides
USER_DEFAULTS_ARG=()
if [[ -f "$INPUT_DIR/pandoc-defaults.user.yaml" ]]; then
  USER_DEFAULTS_ARG=("-d" "$INPUT_DIR/pandoc-defaults.user.yaml")
elif [[ -f "pandoc-defaults.user.yaml" ]]; then
  USER_DEFAULTS_ARG=("-d" "pandoc-defaults.user.yaml")
fi

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
        "${USER_DEFAULTS_ARG[@]}" \
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
      # Append crafted footer if enabled
      TMP_DOCX_FOOTER=""
      if [[ "${CRAFTED_FOOTER,,}" == "true" ]]; then
        TMP_DOCX_FOOTER="$(mktemp /tmp/resume_footer_XXXXXX.md)"
        cat "$DOCX_INPUT" "$SCRIPT_DIR/crafted-footer.md" > "$TMP_DOCX_FOOTER"
        DOCX_INPUT="$TMP_DOCX_FOOTER"
      fi
      # Strip metadata title to avoid duplicate (H1 already has the name)
      TMP_DOCX_CLEAN="$(mktemp /tmp/resume_clean_XXXXXX.md)"
      python3 -c "
import re, sys
t = open(sys.argv[1]).read()
t = re.sub(r'^---\s*\n.*?\n---\s*\n', '', t, count=1, flags=re.DOTALL)
open(sys.argv[2], 'w').write(t)
" "$DOCX_INPUT" "$TMP_DOCX_CLEAN"
      DOCX_INPUT="$TMP_DOCX_CLEAN"
      pandoc "$DOCX_INPUT" \
        -o "${OUT_DIR}/${BASENAME}.docx" \
        --standalone \
        --reference-doc="$SCRIPT_DIR/reference.docx"

      [[ -n "${TMP_DOCX}" && "$KEEP_TMP" != "1" ]] && rm -f "$TMP_DOCX" "$TMP_DOCX_CLEAN"
      [[ -n "${TMP_DOCX_FOOTER}" && "$KEEP_TMP" != "1" ]] && rm -f "$TMP_DOCX_FOOTER"
      ;;

    html)
      echo "Building HTML..."
      HTML_INPUT="$INPUT_MD"
      TMP_HTML_FOOTER=""
      if [[ "${CRAFTED_FOOTER,,}" == "true" ]]; then
        TMP_HTML_FOOTER="$(mktemp /tmp/resume_footer_XXXXXX.md)"
        cat "$INPUT_MD" "$SCRIPT_DIR/crafted-footer.md" > "$TMP_HTML_FOOTER"
        HTML_INPUT="$TMP_HTML_FOOTER"
      fi
      pandoc "$HTML_INPUT" \
        -o "${OUT_DIR}/${BASENAME}.html" \
        --metadata=title:"$TITLE" \
        --standalone

      [[ -n "${TMP_HTML_FOOTER}" && "$KEEP_TMP" != "1" ]] && rm -f "$TMP_HTML_FOOTER"
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
      TMP_TXT_FOOTER=""
      if [[ "${CRAFTED_FOOTER,,}" == "true" ]]; then
        TMP_TXT_FOOTER="$(mktemp /tmp/resume_footer_XXXXXX.md)"
        cat "$TXT_INPUT" "$SCRIPT_DIR/crafted-footer.md" > "$TMP_TXT_FOOTER"
        TXT_INPUT="$TMP_TXT_FOOTER"
      fi
      # Strip YAML frontmatter to avoid title repetition
      TMP_TXT_CLEAN="$(mktemp /tmp/resume_clean_XXXXXX.md)"
      python3 -c "
import re, sys
t = open(sys.argv[1]).read()
t = re.sub(r'^---\s*\n.*?\n---\s*\n', '', t, count=1, flags=re.DOTALL)
open(sys.argv[2], 'w').write(t)
" "$TXT_INPUT" "$TMP_TXT_CLEAN"
      TXT_INPUT="$TMP_TXT_CLEAN"
      pandoc "$TXT_INPUT" \
        -o "${OUT_DIR}/${BASENAME}.txt" \
        --standalone \
        -t plain

      [[ -n "${TMP_TXT}" && "$KEEP_TMP" != "1" ]] && rm -f "$TMP_TXT" "$TMP_TXT_CLEAN"
      [[ -n "${TMP_TXT_FOOTER}" && "$KEEP_TMP" != "1" ]] && rm -f "$TMP_TXT_FOOTER"
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
