# ATS Safe Resume

[![Built with Pandoc](https://img.shields.io/badge/built%20with-pandoc-blueviolet)](https://pandoc.org/)
[![LaTeX](https://img.shields.io/badge/engine-lualatex%20|%20xelatex%20|%20tectonic-green)](https://www.latex-project.org/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

A modern, programmatic resume template that produces clean PDFs that pass applicant tracking systems — without sacrificing design.

**Edit one Markdown file. Get PDF, DOCX, HTML, plain text, and JSON Resume output. Zero-install path available via GitHub actions.**

![Example Resume](example/resume.pdf)

---

## 🚧 v2 Upgrade In Progress

**We're migrating from a Pandoc-based pipeline to a single-parse, multi-render architecture.** The v1 pipeline (Pandoc → PDF/DOCX/HTML/TXT + bash → JSON) runs 5 independent parses of the same markdown, which caused format-specific bugs: title duplication, double-escaped HTML entities, overwritten dates, and invisible footers.

**v2 fixes this for good:**

```
resume.md → Pydantic Parser → canonical JSON → Typst PDF / DOCX / HTML / TXT
                 (parse once)                           (dedicated renderers)
```

| Before (v1) | After (v2) |
|---|---|
| 5 independent parses (Pandoc + bash) | 1 parse into a typed data model |
| LaTeX engine (1.5GB install) | Typst (~30MB, deterministic output) |
| Format-specific bugs compound over time | One fix in the data model fixes all formats |
| Manual output validation | Automated property-based testing |

**Current status:** The v2 pipeline is built and running alongside v1 (output goes to `dist-v2/`). The `ats-safe-resume` CLI accepts the same markdown format with zero UX change.

**Remaining work:**
- CI integration (run both pipelines, validate parity)
- Parser edge cases (markdown URLs in some section headings)
- Property-based testing (Hypothesis) for Phase 2
- Cutover: switch default pipeline from v1 to v2, remove Pandoc/LaTeX dependencies
- Simplified Docker image (~100MB instead of ~1.2GB)

Full architecture: [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) · Implementation plan: [PLAN_PHASE1.md](PLAN_PHASE1.md)

---

## Quick Start — Zero Install

**No Pandoc. No LaTeX. No terminal needed.**

1. [Click "Use this template"](https://github.com/new?template_name=ats_safe_resume&template_owner=denniyahh) to create your own copy
2. Edit `example/resume.md` in the GitHub web editor
3. Commit your changes
4. Go to **Actions** → click the latest workflow → download `resume.pdf` from the artifacts

That's it. GitHub Actions builds everything automatically. No software to install.

---

## Quick Start — Docker (Local Build)

If you want to build locally without installing LaTeX:

```bash
# Build your resume with one command
docker run --rm -w /data -v "$(pwd):/data" ghcr.io/denniyahh/ats_safe_resume:latest /data/resume.md
```

Or use the convenience wrapper:

```bash
./build_docker.sh                  # default: resume.md
./build_docker.sh path/to/resume.md
```

---

## Quick Start — Native (Local Build)

If you have Pandoc and LaTeX installed:

```bash
# Install dependencies (Fedora)
sudo dnf install pandoc texlive-scheme-medium texlive-luatex \
  adobe-source-sans-pro-fonts adobe-source-code-pro-fonts

# Build all formats
./build_resume.sh

# Outputs in dist/
ls dist/   # resume.pdf  resume.docx  resume.html  resume.txt  resume.json
```

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
| **PDF** | `resume.pdf` | Applications, email, print |
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

This template ensures ATS safety in two ways:

1. **Typography normalization** — By default (`ATS_SAFE=1`), the PDF is built from a normalized copy where typographic characters (en/em dashes, middle dots, non-breaking spaces, curly quotes) are replaced with plain ASCII equivalents.
2. **Clean text extraction** — Section headers use standard names (Executive Profile, Professional Experience, Education) that ATS parsers recognize.

You can disable normalization for the visual-copy PDF:

```bash
ATS_SAFE=0 ./build_resume.sh
```

---

## Dependencies

### Native (installed on your machine)

| Tool | Required | Notes |
|------|----------|-------|
| `pandoc` | ✅ | Document conversion |
| `lualatex` / `xelatex` / `tectonic` | ✅ | PDF engine (auto-detected) |
| Source Sans 3 | ✅ | Primary font |
| Source Code Pro | ✅ | Monospace font |
| Python 3 | ✅ | ATS normalization, JSON generation |

### Install by OS

**Fedora / RHEL:**
```bash
sudo dnf install pandoc texlive-scheme-medium texlive-luatex \
  adobe-source-sans-pro-fonts adobe-source-code-pro-fonts python3
```

**Ubuntu / Debian:**
```bash
sudo apt-get install pandoc texlive-latex-base texlive-latex-extra \
  texlive-luatex texlive-fonts-recommended texlive-fonts-extra \
  fonts-source-sans-pro fonts-source-code-pro python3
```

**macOS (Homebrew):**
```bash
brew install pandoc tectonic
brew install --cask mactex-no-gui  # or basictex + extra packages
```

**Windows:** Use [WSL](https://learn.microsoft.com/en-us/windows/wsl/) with Ubuntu, then follow Ubuntu instructions.

### Docker (no local install needed)

See **Quick Start — Docker** above. The Docker image includes all dependencies.

---

## Project Structure

```
ats_safe_resume/
├── example/
│   ├── resume.md            # Template — edit this
│   └── resume.pdf           # Committed demo (auto-updated by CI)
├── templates/
│   └── eisvogel.latex       # Self-contained Pandoc LaTeX template
├── themes/
│   ├── dark.tex             # Dark gray (default)
│   ├── navy.tex             # Navy blue
│   ├── teal.tex             # Teal accent
│   ├── burgundy.tex         # Burgundy accent
│   └── minimal.tex          # Black/minimal
├── reference.docx           # Reference DOCX for styled Word output
├── resume-preamble.tex      # LaTeX preamble (accent bars, spacing)
├── pandoc-defaults.yaml     # Pandoc defaults file
├── build_resume.sh          # Build script
├── build_docker.sh          # Docker wrapper
├── Dockerfile               # Docker image (pinned versions)
├── AI_INSTRUCTIONS.md       # AI assistant instructions
├── .github/workflows/
│   └── build.yml            # CI: builds PDF + publishes Docker image
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

# Override base filename
BASENAME=jane-doe-resume ./build_resume.sh

# Force a specific PDF engine
PDF_ENGINE=xelatex ./build_resume.sh

# Disable ATS normalization
ATS_SAFE=0 ./build_resume.sh

# Keep the normalized temp file for inspection
KEEP_TMP=1 ./build_resume.sh

# Select output formats
FORMATS=pdf,json ./build_resume.sh
```

### Custom Pandoc Defaults

Create a `pandoc-defaults.user.yaml` in the repo root to override any Pandoc setting without modifying repo files. The build script does not touch this file.

---

## FAQ / Troubleshooting

**Q: The PDF looks different from the example.**
A: Most likely a missing font. Install Source Sans 3 and Source Code Pro, or use the Docker build.

**Q: LaTeX errors on build.**
A: Ensure all texlive packages are installed (see Dependencies). For Ubuntu, `texlive-latex-extra` is required for KOMA-script and Eisvogel template features.

**Q: Font "Source Sans 3" not found error.**
A: Install the fonts (see Dependencies by OS). On older Linux systems, the package is called `fonts-source-sans-pro`. Use the Docker build to avoid font issues entirely.

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

## ATS Safe Resume

Built by [Dennis Kim](https://github.com/denniyahh). Contributions welcome!
