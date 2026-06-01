# ATS Safe Resume

[![Built with Python](https://img.shields.io/badge/built%20with-python-blue)](https://python.org/)
[![Pandoc+LaTeX](https://img.shields.io/badge/engine-Pandoc%2BLaTeX-4B8BBE)](https://pandoc.org/)
[![Typst fallback](https://img.shields.io/badge/fallback-Typst-239DAD)](https://typst.app/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

A modern, programmatic resume template that produces clean PDFs that pass applicant tracking systems — without sacrificing design.

**Edit one Markdown file. Get PDF, DOCX, HTML, plain text, and JSON Resume output. Zero-install path available via GitHub Actions. Automated LinkedIn profile sync.**

![Example Resume](example/resume.pdf)

---

## Architecture

**Single-parse, multi-render pipeline.** Parse once into a typed data model, then render to all output formats from the same canonical source.

```
resume.md → Pydantic Parser → canonical JSON → Pandoc/LaTeX PDF (Eisvogel)
                                               ├─ Typst PDF (fallback, if no Pandoc)
                                               ├─ DOCX / HTML / TXT / JSON Resume
                                               └─ LinkedIn profile (Playwright automation)
```

| Decision | Rationale |
|---|---|
| Pandoc + LuaLaTeX + Eisvogel (primary PDF) | Pixel-perfect v1 layout match, link color=blue, footer styling |
| Typst (fallback PDF) | ~30MB install, deterministic output — for CI / Docker / quick builds |
| Single markdown source | One fix in the data model fixes all outputs |
| Property-based testing | Automated validation across all renderers |

Full architecture: [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) · Implementation plan: [PLAN_PHASE1.md](PLAN_PHASE1.md)

---

## Quick Start — Zero Install

**No Pandoc. No LaTeX. No terminal needed.**

1. [Click "Use this template"](https://github.com/new?template_name=ats_safe_resume&template_owner=denniyahh) to create your own copy
2. Edit `example/resume.md` in the GitHub web editor
3. Commit your changes
4. Go to **Actions** → click the latest workflow → download `resume.pdf` from the artifacts

That's it. GitHub Actions builds everything automatically (using the Typst fallback — no LaTeX needed in CI).

---

## Quick Start — Docker (Local Build)

Build locally without installing Pandoc or LaTeX:

```bash
docker run --rm -v "$(pwd):/data" ghcr.io/denniyahh/ats_safe_resume:latest /data/resume.md
```

---

## Quick Start — Native (Local Build)

For pixel-perfect PDF output matching the example:

```bash
# Prerequisites: Pandoc + TeX Live (LuaLaTeX + Eisvogel template)
# Install: sudo dnf install pandoc texlive-scheme-full

# Install Python dependencies
pip install -e .

# Build all formats
./build_resume.sh

# Or directly:
ats-safe-resume resume.md

# Outputs in dist/
ls dist/   # resume.pdf  resume.docx  resume.html  resume.txt  resume.json
```

If Pandoc/LaTeX isn't available, the Typst fallback kicks in automatically for PDF generation.

---

## LinkedIn Profile Sync

Keep your LinkedIn profile in sync with your resume — no copy-paste, no manual edits.

```
resume.md → parse → map → LinkedIn profile
                           ├─ Headline
                           ├─ About
                           ├─ Positions (exact mirror)
                           ├─ Skills (add-only)
                           └─ Education (exact mirror)
```

### Setup

```bash
cd linkedin_sync
npm install
npx playwright install chromium
```

### Usage

```bash
# Dry run — prints what would change without touching LinkedIn
node index.js --dry-run

# Live sync
node index.js

# Custom resume path
node index.js --resume /path/to/your/resume.md
```

### How it works

- **Headful browser** — you see everything happening. On first run, log in manually; session is saved to `cookies/` and reused.
- **Selector validation** — before any edits, validates all selectors against LinkedIn's live DOM. Sections with broken selectors are skipped with screenshots for debugging.
- **Exact mirror** — positions and education are matched by company+title and school+degree. Missing entries are added, existing ones are updated, and LinkedIn-only entries (not in resume source) are deleted.
- **Anti-detection** — `playwright-extra` + stealth plugin, realistic delays, persistent browser context.
- **Delete handling** — confirmation dialogs are bypassed via DOM manipulation (LinkedIn overlays intercept pointer events on dialog buttons).

### Limitations

- LinkedIn's DOM changes frequently — the validation layer detects breakage, but selectors need manual updates when they change
- Skills are add-only (LinkedIn has a 50-skill cap)
- Dates are best-effort — LinkedIn's date pickers vary by locale

See [linkedin_sync/README.md](linkedin_sync/README.md) for full details.

---

## Customization

All customization happens in the YAML frontmatter at the top of your `resume.md`:

### Themes

Change your entire color scheme by changing one word:

```yaml
theme: dark       # professional, understated gray
# theme: navy     # corporate, traditional blue
# theme: teal     # modern, fresh green-blue
# theme: burgundy # bold, distinctive
# theme: minimal  # black and white, maximum contrast
```

### Page Mode

```yaml
page_mode: two    # standard 2-page layout (default)
# page_mode: one  # tighter spacing to fit 1 page
```

### Font Size & Margins

```yaml
fontsize: 10pt
geometry: "left=0.7in,right=0.7in,top=0.5in,bottom=0.5in"
```

---

## Output Formats

| Format | File | Use Case |
|--------|------|----------|
| **PDF** (Pandoc) | `resume.pdf` | Applications, email, print — pixel-perfect Eisvogel template |
| **PDF** (Typst) | `resume.pdf` | Fallback when Pandoc unavailable — near-identical output |
| **DOCX** | `resume.docx` | Job portals requiring Word format (styled via `reference.docx`) |
| **HTML** | `resume.html` | Web preview, personal site |
| **Plain Text** | `resume.txt` | Simple ATS portals, plain-text forms |
| **JSON Resume** | `resume.json` | JSON Resume standard (jsonresume.org) — import into other tools |

Build a subset with the `FORMATS` env var:

```bash
FORMATS=pdf,docx ./build_resume.sh
```

---

## AI-Assisted Writing

This repo includes [AI_INSTRUCTIONS.md](AI_INSTRUCTIONS.md) — a file that primes AI coding assistants (Claude, Cursor, GitHub Copilot) to help you write and improve your resume.

**How to use it:**

1. Open the repo in an AI-enabled editor (VS Code + Cursor, Claude Desktop, etc.)
2. Ask the AI to help with a section: "Improve my executive profile" or "Tighten my experience bullets"
3. The AI already knows the resume format, STAR bullet structure, and ATS optimization rules

The AI can help with:
- Rewriting vague bullets into metric-driven STAR format
- Tightening content to fit one or two pages
- Adding relevant keywords for ATS scanning
- Suggesting a color theme based on your industry

---

## ATS Safety

ATS (Applicant Tracking Systems) parse resumes by extracting text from PDFs. Many beautiful templates produce PDFs that extract as garbled text — special characters become unrecognizable, section headers get merged, and bullet points disappear.

This template ensures ATS safety through typography normalization: typographic characters (en/em dashes, middle dots, non-breaking spaces, curly quotes) are replaced with plain ASCII equivalents. The visual-copy PDF and ATS-safe PDF are the same file — clean text extraction with professional typography.

Section headers use standard names (Executive Profile, Professional Experience, Education) that ATS parsers recognize.

---

## Dependencies

### Native (Pandoc/LaTeX — pixel-perfect output)

| Tool | Required | Notes |
|------|----------|-------|
| Python 3.10+ | ✅ | Parser, renderers, CLI |
| Pandoc 3+ | ✅ | Markdown → LaTeX conversion |
| TeX Live (LuaLaTeX) | ✅ | PDF engine |
| Eisvogel template | ✅ | LaTeX template for layout |
| Source Sans 3 | ✅ | Primary font |
| Source Code Pro | ✅ | Monospace font |

Native fallback (Typst — if Pandoc unavailable):

| Tool | Required | Notes |
|------|----------|-------|
| `typst` (Python pkg) | ⬜ | PDF generation (~30MB) |

Python packages:

| Package | Notes |
|---------|-------|
| `pydantic` | Data model |
| `python-docx` | DOCX generation |
| `jinja2` | HTML/TXT templates |
| `pyyaml` | Frontmatter parsing |

Install: `pip install -e .` (from the repo root).

### Docker (no local install needed)

See **Quick Start — Docker** above.

---

## Project Structure

```
ats_safe_resume/
├── example/
│   ├── resume.md            # Template — edit this
│   └── resume.pdf           # Committed demo (auto-updated by CI)
├── src/ats_safe_resume/
│   ├── models.py            # Pydantic data model
│   ├── parser.py            # Markdown parser
│   ├── renderers/           # PDF (Pandoc + Typst fallback), DOCX, HTML, TXT, JSON
│   ├── cli.py               # CLI entry point
│   └── templates/           # Jinja2 templates
├── linkedin_sync/           # LinkedIn profile automation
│   ├── index.js             # CLI entry point
│   ├── lib/
│   │   ├── linkedin.js      # Playwright automation + LinkedIn DOM
│   │   ├── mapper.js        # Resume → LinkedIn field mapping
│   │   └── parser.js        # Python parser integration
│   └── README.md
├── tests/
│   └── ...                  # Unit + integration + property-based tests
├── build_resume.sh          # Build script
├── Dockerfile               # Docker image
├── AI_INSTRUCTIONS.md       # AI assistant instructions
├── .github/workflows/
│   └── build.yml            # CI: builds PDF + publishes Docker image
├── pyproject.toml           # Python package config
├── LICENSE                  # MIT
└── README.md
```

---

## Advanced Usage

### Environment Variables

```bash
# Custom input file
./build_resume.sh path/to/custom.md

# Override output directory
OUT_DIR=output ./build_resume.sh

# Select output formats
FORMATS=pdf,json ./build_resume.sh
```

---

## FAQ / Troubleshooting

**Q: The PDF looks different from the example.**
A: Most likely a missing font or Pandoc/LaTeX not installed. Install Source Sans 3 and Source Code Pro, or use the Docker build.

**Q: Font "Source Sans 3" not found error.**
A: Install the fonts (see Dependencies). Use the Docker build to avoid font issues entirely.

**Q: Build fails with import errors.**
A: Run `pip install -e .` from the repo root to install all Python dependencies.

**Q: Build fails with Pandoc/LaTeX errors.**
A: The Typst fallback activates automatically. Or install Pandoc + TeX Live for the pixel-perfect Eisvogel output.

**Q: Can I use a different font?**
A: Yes — set `mainfont` and `monofont` in the YAML frontmatter. The font must be installed on your system (or in the Docker image).

**Q: Can I add more pages?**
A: The template is optimized for 1–2 pages. For longer resumes, increase margins or reduce fontsize. Resumes over 2 pages are rarely read all the way through.

**Q: How do I add a photo?**
A: This template does not support photos. Photos can hurt ATS parsing and are not standard for US-based professional resumes.

**Q: The DOCX output looks plain.**
A: The DOCX output is designed for ATS uploads, not visual presentation. For a styled Word document, edit `reference.docx` with your own styles.

---

## License

MIT — free to use, modify, and distribute. See [LICENSE](LICENSE).

---

Built by [Dennis Kim](https://github.com/denniyahh). Contributions welcome!
