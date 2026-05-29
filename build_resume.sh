#!/usr/bin/env bash
# ATS Safe Resume — Build Script
#
# Thin wrapper around the v2 Python pipeline.
#
# Usage:
#   ./build_resume.sh                  # uses resume.md by default
#   ./build_resume.sh path/to/file.md  # custom input
#
# Env vars:
#   OUT_DIR=dist                       # output directory
#   FORMATS=pdf,docx,html,txt,json     # comma-separated output formats
#
# Outputs (in OUT_DIR):
#   resume.pdf   resume.docx   resume.html   resume.txt   resume.json

set -euo pipefail

INPUT_MD="${1:-resume.md}"
OUT_DIR="${OUT_DIR:-dist}"
FORMATS="${FORMATS:-pdf,docx,html,txt,json}"

if command -v ats-safe-resume >/dev/null 2>&1; then
  exec ats-safe-resume "$INPUT_MD" --formats "$FORMATS" --out-dir "$OUT_DIR"
elif python3 -c "import ats_safe_resume" 2>/dev/null; then
  exec python3 -m ats_safe_resume "$INPUT_MD" --formats "$FORMATS" --out-dir "$OUT_DIR"
else
  echo "ERROR: Python deps not found." >&2
  echo "Run: pip install -e . (from the repo root)" >&2
  exit 1
fi
