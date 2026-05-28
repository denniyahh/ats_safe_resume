# ATS Safe Resume — Project Spec

## Overview

Build and publish an open-source, programmatic resume template that produces a modern, ATS-safe PDF from a single Markdown source file. The template targets **all professionals**, not just developers — from technical PMs to marketing directors to finance analysts. The goal is to produce the most accessible, lowest-friction resume builder on GitHub.

### Repo
- **Name**: `ats_safe_resume`
- **Owner**: `denniyahh` (GitHub)
- **Visibility**: Public
- **Description**: "A modern, programmatic resume template built with Markdown + Pandoc — produces clean PDFs that pass applicant tracking systems without sacrificing design."

### Guiding Principles
1. **No personal data** in the template repo — example text only
2. **One-file simplicity** — edit `resume.md`, run one command, get PDF/DOCX/HTML/TXT/JSON
3. **Zero-install path** — users can fork the repo, edit in the GitHub web editor, and get a PDF from CI without installing anything
4. **Docker path** — users who want local iteration can `docker run` instead of installing LaTeX (1GB+)
5. **ATS safety by default** — typographic normalization is built into the pipeline, not an afterthought
6. **Frontmatter-driven customization** — colors, themes, page count all controlled via YAML frontmatter; users never open a `.tex` file
7. **AI-assisted** — ships with instructions that prime AI coding assistants to help users write and improve their resume content
8. **Modern aesthetic** — Source Sans 3, 10pt, multiple color themes, accent bars under headings, clean pages
9. **Reproducible** — CI builds and publishes artifacts on every push, proving it works

---

## 1. Project Structure

```
ats_safe_resume/
├── .github/
│   └── workflows/
│       └── build.yml               # CI: builds PDF + DOCX, publishes Docker image
├── example/
│   └── resume.md                   # Template with example data + inline instructions
├── templates/
│   └── eisvogel.latex              # Self-contained single-file Eisvogel template
├── themes/
│   ├── dark.tex                    # Dark gray (default)
│   ├── navy.tex                    # Navy blue
│   ├── teal.tex                    # Teal accent
│   ├── burgundy.tex                # Burgundy accent
│   └── minimal.tex                 # Black/minimal
├── reference.docx                  # Reference DOCX for styled Word output
├── resume-preamble.tex             # Base LaTeX header: accent bars, compact spacing
├── pandoc-defaults.yaml            # Pandoc defaults file (thin build wrapper)
├── build_resume.sh                 # Build script: reads frontmatter, drives pandoc
├── build_docker.sh                 # Docker convenience wrapper
├── Dockerfile                      # Pinned Pandoc + TeX Live + fonts
├── AI_INSTRUCTIONS.md              # Instructions for AI coding assistants
├── .gitignore
├── LICENSE
└── README.md
```

### What NOT to include
- Dennis Kim's personal resume data (phone, email, work history)
- `dist/` directory (build output, gitignored — except `example/resume.pdf`)
- `dist/.gitkeep` — not needed; we commit `example/resume.pdf` instead
- `archive/` directory (irrelevant to template users)
- `.git/` from personal repo
- Multi-file Eisvogel directory — we ship a compiled single-file template

---

## 2. Template Resume (`example/resume.md`)

The template resume serves triple purpose: (a) example output to show users what they'll get, (b) the file they edit to customize, and (c) a living demo that CI builds on every push.

### Frontmatter

```yaml
---
title: "Your Name — Your Title"
author: "Your Name"
geometry: "left=0.7in,right=0.7in,top=0.5in,bottom=0.5in"
fontsize: 10pt
mainfont: Source Sans 3
monofont: Source Code Pro
theme: dark                    # dark | navy | teal | burgundy | minimal
page_mode: two                 # one | two
disable-header-and-footer: true
---
```

### Theme System

All visual customization is controlled via the `theme` frontmatter field. Each theme file in `themes/` defines:

- **Accent color** — section headings, accent bars, link color
- **Secondary color** — accent bar opacity, subtle highlights
- **Link color** — coordinated with accent

Users change one word and the entire color scheme updates. No LaTeX knowledge required.

| Theme | Accent | Vibe |
|-------|--------|------|
| `dark` | #555555 | Professional, understated (default) |
| `navy` | #2B547E | Corporate, traditional |
| `teal` | #0B7261 | Modern, fresh |
| `burgundy` | #7B2040 | Bold, distinctive |
| `minimal` | #222222 | Black and white, maximum contrast |

### Page Mode

`page_mode: one` automatically adjusts fontsize (9.5pt), margins (tighter), and list spacing to fit content onto a single page. `page_mode: two` uses the standard 10pt layout optimized for two pages. The build script translates this into the right Pandoc variables and LaTeX preamble includes.

### Body

Replace personal content with **recognizable placeholder data** (e.g., "Jane Doe," "Acme Corp") so the rendered PDF looks realistic enough to judge the design. Each section should have brief inline comments explaining what to put there:

```markdown
# Your Name
**Your Title**

City, State · [email@example.com](mailto:email@example.com) · (555) 000-0000 · [LinkedIn](https://linkedin.com/in/yourname) · [Github](https://github.com/yourname)

## Executive Profile

[2-3 sentence professional summary. Include your years of experience, key domains, and measurable outcomes.]
```

Sections to include in the example:
1. **Executive Profile** — placeholder text showing quantified results
2. **Core Expertise** — 4–6 bullet-style items with separators
3. **Professional Experience** — 2–3 example jobs, each with 2–4 bullet points showing metric-driven STAR format
4. **Education** — example school, degree
5. **Technical Skills** — comma-separated categories

---

## 3. Build Pipeline

### Architecture

The build system separates concerns cleanly:

```
resume.md (source of truth)
    │
    ▼
build_resume.sh (thin orchestrator)
    │
    ├─ Reads YAML frontmatter (theme, page_mode, etc.)
    ├─ Selects theme preamble
    ├─ Applies ATS normalization
    │
    ▼
pandoc-defaults.yaml + theme preamble.tex + resume-preamble.tex
    │
    ▼
pandoc (one call per output format)
    │
    ▼
dist/ (resume.pdf, resume.docx, resume.html, resume.txt, resume.json)
```

### `pandoc-defaults.yaml`

Rather than passing 10+ CLI flags per format, the build is driven by a Pandoc defaults file:

```yaml
from: markdown+smart
standalone: true
pdf-engine: lualatex
template: templates/eisvogel.latex
include-in-header:
  - resume-preamble.tex
variables:
  mainfont: Source Sans 3
  mainfontoptions: Ligatures=NoCommon
  monofont: Source Code Pro
  fontsize: 10pt
  colorlinks: true
```

The build script merges theme-specific variables into the defaults file before each run. Users can also provide a `pandoc-defaults.user.yaml` to override settings without modifying the repo files.

### `build_resume.sh`

A thin orchestrator that:

1. Parses YAML frontmatter from the input markdown
2. Selects the theme preamble based on `theme` field
3. Adjusts `fontsize`, `geometry`, and list spacing for `page_mode: one`
4. Runs ATS-safe normalization (en/em dashes → hyphens, middle dots → pipes, etc.)
5. Calls `pandoc -d pandoc-defaults.yaml` for each output format
6. Cleans up temp files

**Environment variables** (power-user overrides):

| Variable | Default | Purpose |
|----------|---------|---------|
| `INPUT_MD` | `resume.md` | Input markdown file |
| `OUT_DIR` | `dist` | Output directory |
| `BASENAME` | `resume` | Base filename for outputs |
| `PDF_ENGINE` | `lualatex` | PDF engine override |
| `ATS_SAFE` | `1` | Enable/disable ATS normalization |
| `KEEP_TMP` | `0` | Keep normalized temp file for inspection |
| `THEME` | from frontmatter | Override color theme |

### Bugs Fixed from `my_resume`

| Issue | Fix |
|-------|-----|
| Template detection broken (searches `./templates/`, template at `./Eisvogel-3.3.0/`) | Ship compiled single-file `templates/eisvogel.latex`, reference it directly |
| `mktemp -t` non-portable | Use `mktemp /tmp/resume_ats_XXXXXX.md` |
| Python ATS normalization fragile (`.encode().decode('unicode_escape')` roundtrip) | Use direct Unicode escapes or literal characters |
| `&amp;` in YAML frontmatter (double-escaping) | Use plain `&` |
| DOCX/HTML bypass ATS normalization | Apply normalization to DOCX and TXT builds too |
| Hardcoded `--metadata=title:"Dennis Kim — Resume"` | Read from YAML frontmatter; don't override Pandoc's built-in metadata parsing |
| `paralist` package deprecated | Switch to `enumitem` with `nosep` option |

---

## 4. LaTeX Preamble (`resume-preamble.tex`)

Base styling applied to all themes:

```latex
\definecolor{accent}{HTML}{555555}
\addtokomafont{section}{\color{accent}\large}
\addtokomafont{subsection}{\color{accent}\normalsize}
\let\oldsection\section
\renewcommand{\section}[1]{\oldsection{#1}\vspace{-0.5em}\par\noindent\textcolor{accent!40}{\rule{\textwidth}{0.3pt}}\vspace{0.3em}}
% Compact list spacing via enumitem (replaces deprecated paralist)
\usepackage{enumitem}
\setlist{nosep,leftmargin=*}
\setlength{\parskip}{0.4\baselineskip}
```

Each theme file in `themes/` overrides `\definecolor{accent}{HTML}{...}` and link colors. The build script includes the selected theme BEFORE the base preamble so the color definition is picked up.

---

## 5. Self-Contained Eisvogel Template

The multi-file Eisvogel template (`Eisvogel-3.3.0/template-multi-file/`) is compiled into a single `templates/eisvogel.latex` by inlining all the partial files. This eliminates the multi-file path resolution problems and makes the template trivially portable.

The compiled file retains the Eisvogel license header and a comment indicating it was compiled from the multi-file source.

---

## 6. Output Formats

| Format | Command flag | Use case |
|--------|-------------|----------|
| **PDF** | (default) | Primary output — applications, email attachments, print |
| **DOCX** | `--docx` | Job portals that require Word format; styled via `reference.docx` |
| **HTML** | `--html` | Web preview, personal site embedding |
| **Plain Text** | `--txt` | Simple ATS portals, plain-text application forms |
| **JSON Resume** | `--json` | Programmatic consumption, JSON Resume schema (jsonresume.org) |

### DOCX with Reference Styling

Pandoc's default DOCX output is unstyled and unprofessional. A `reference.docx` file in the repo provides:

- Source Sans 3 font mapping
- Matching heading styles (colors, sizes, spacing)
- Accent bars as bottom borders on headings
- Appropriate margins and line spacing

The build script uses `--reference-doc=reference.docx` to produce a Word document that matches the PDF aesthetic.

### JSON Resume Output

The JSON Resume format (jsonresume.org) is an open standard for resume data. Outputting to this schema enables:

- Integration with JSON Resume themes and hosting platforms
- Import into other resume tools (Reactive Resume, etc.)
- Programmatic consumption by recruiters' internal systems
- Acts as the bridge format for LinkedIn profile migration (see §12)

The conversion from Markdown to JSON Resume schema is done via a Python script that parses the structured markdown sections and maps them to the JSON Resume fields:

```
resume.md  →  parse_sections.py  →  resume.json (JSON Resume schema)
```

---

## 7. CI/CD (`build.yml`)

GitHub Actions workflow that:

1. **Triggers**: on push to `main`, on PRs
2. **Environment**: `ubuntu-latest`
3. **Dependencies**:
   - Install `pandoc`, `texlive-latex-extra`, `texlive-luatex`, `fonts-source-sans-pro`, `fonts-source-code-pro`
   - Install `shellcheck` for build script validation
4. **Steps**:
   - Check out repo
   - Run `shellcheck build_resume.sh`
   - Install dependencies
   - Run `./build_resume.sh` (all formats)
   - Copy `dist/resume.pdf` → `example/resume.pdf` (committed demo)
   - Upload all `dist/*` as build artifacts
   - Build and push Docker image to `ghcr.io/denniyahh/ats_safe_resume`
5. **Artifact retention**: 90 days (GitHub default)
6. **Docker image**: tagged as `latest` and git SHA

### Why Commit `example/resume.pdf`

Build artifacts expire after 90 days. A committed PDF in the repo:
- Renders immediately in the README
- Is always accessible (clone and it's there)
- Proves the template works from the first visit
- CI auto-updates it on every push

---

## 8. Docker Build

For users who want local iteration but refuse to install LaTeX (1GB+ download, complex dependencies), a Docker image provides a one-command build:

```bash
# From the repo root:
docker run --rm -w /data -v "$(pwd):/data" ghcr.io/denniyahh/ats_safe_resume:latest /data/resume.md
```

Or via the convenience wrapper:

```bash
./build_docker.sh
```

The `Dockerfile` pins specific versions of:
- `pandoc` (via Ubuntu package or official binary)
- `texlive-latex-extra` + `texlive-luatex`
- Source Sans 3 and Source Code Pro fonts
- `python3` (for ATS normalization)

The GitHub Actions workflow publishes the image to GitHub Container Registry on every push to main.

---

## 9. AI-Assisted Resume Writing (`AI_INSTRUCTIONS.md`)

A file in the repo root that primes AI coding assistants (Claude, Cursor, Copilot, etc.) to help users write and improve their resume. When a user opens the repo in an AI-enabled editor and asks for help, the AI already knows:

- The resume format, sections, and style conventions
- How to write STAR-format (Situation, Task, Action, Result) bullet points with measurable metrics
- How to tighten content to fit page counts
- How to tailor bullets for ATS keyword optimization
- Section-by-section coaching (what goes in Executive Profile vs Core Expertise)
- Common pitfalls (vague verbs, missing metrics, passive voice)

```markdown
# AI Instructions for Resume Assistance

When the user asks for help with their resume, follow these guidelines:

## Bullet Point Quality
- Every bullet must have a measurable outcome (%, $, count, rank)
- Lead with strong action verbs (Led, Built, Shipped, Grew, Designed)
- Use STAR format implicitly: [Action] → [Scope/Context] → [Measurable Result]
- Minimum 2, maximum 4 bullets per role
- ...
```

This is a core differentiator — no other resume template on GitHub ships with AI instructions.

---

## 10. README (`README.md`)

Target audience: **all professionals**, not just developers. Assume the user has never used a terminal, Pandoc, or LaTeX.

### Sections

1. **Title & Badges** — "ATS Safe Resume" with Pandoc + LaTeX + Docker badges
2. **Screenshot** — embedded `example/resume.pdf` preview (renders natively on GitHub)
3. **Quick Start (Zero Install)** — fork → edit `resume.md` → commit → download PDF from Actions. 3 steps, no terminal.
4. **Quick Start (Docker)** — `docker run` one-liner for local builds
5. **Quick Start (Native)** — install Pandoc + LaTeX, run `./build_resume.sh`
6. **Customization** — theme picker, page mode, font overrides (all via frontmatter)
7. **Output Formats** — PDF, DOCX, HTML, TXT, JSON Resume
8. **AI-Assisted Writing** — link to `AI_INSTRUCTIONS.md`, how to use with VS Code / Cursor / Claude
9. **ATS Safety** — explain what ATS-safe means and how normalization works
10. **Dependencies** — table with install commands for Fedora, Ubuntu, macOS, Windows (WSL)
11. **Project Structure** — directory tree
12. **FAQ / Troubleshooting** — font not found, LaTeX errors, Docker issues
13. **License** — MIT

### Important: Zero-Install Path Must Be First

The README must lead with the zero-install path. The majority of users should never need to install anything. Technical users who want local builds can scroll down for the Docker or native paths.

---

## 11. License, `.gitignore`, etc.

### LICENSE
**MIT License** — simple, permissive, standard for open-source templates.

### `.gitignore`

```
dist/
*.bak
*.tmp
*.swp
*~
.DS_Store
Thumbs.db
.idea/
.vscode/
!example/resume.pdf
```

Note: `example/resume.pdf` is explicitly NOT gitignored — it's the committed demo file.

---

## 12. Future Enhancement: LinkedIn Profile Migration (post-v1)

### Goal

Automate the migration of a resume to a LinkedIn profile. The resume becomes the source of truth, and LinkedIn content is generated from it rather than manually duplicated.

### Approach

1. **Parse resume.md** (or `resume.json` JSON Resume output) into structured data
2. **Map sections** to LinkedIn profile fields:
   - Executive Profile → About section (2,600 char max)
   - Professional Experience → Experience entries (title, company, dates, description)
   - Education → Education entries (school, degree, field, dates)
   - Technical Skills → Skills section (up to 50 skills, including AI-suggested endorsable skills)
   - Core Expertise → Featured section or additional About context
3. **Content adaptation** for LinkedIn's tone and format:
   - Shorten bullet points for mobile readability
   - Add relevant keywords for LinkedIn's search algorithm
   - Generate a LinkedIn-optimized headline (220 char max)
   - Suggest a profile photo guideline based on industry
4. **Output format**: Copy-paste-ready text organized by LinkedIn section, plus a structured YAML/JSON that could eventually drive LinkedIn's API

### Integration Points

- **JSON Resume output** from the build pipeline is the natural input for this feature
- Could output a `linkedin-profile.md` or `linkedin-profile.yaml` that maps 1:1 to LinkedIn's edit screens
- Could generate a checklist of LinkedIn sections with copy-paste content blocks
- Future: if LinkedIn opens write APIs or headless browser automation is acceptable, automate the actual profile update

### User Flow (Target)

```
resume.md  →  ./build_resume.sh --linkedin  →  linkedin-profile.md
                                                  │
                                                  ▼
                                     Copy-paste into LinkedIn,
                                     section by section
```

---

## 13. Connecting to Personal Repo (post-launch)

After the template repo is created, wire it into `~/Github/my_resume` as an upstream remote:

```bash
cd ~/Github/my_resume
git remote add template https://github.com/denniyahh/ats_safe_resume.git
```

To pull template improvements:

```bash
git pull template main --allow-unrelated-histories
# Resolve any conflicts manually
```

Files that flow template → personal:
- `build_resume.sh` (improvements)
- `build_docker.sh` (new)
- `pandoc-defaults.yaml` (new)
- `resume-preamble.tex` (styling tweaks)
- `templates/eisvogel.latex` (updates)
- `themes/` (new themes)
- `reference.docx` (styling updates)
- `.gitignore` (updates)

Personal data never flows to template.

---

## 14. Execution Steps

### Phase 1: Foundation
1. Create `ats_safe_resume` directory if not exists
2. Initialize git repo
3. Compile self-contained `templates/eisvogel.latex` from multi-file source
4. Create `themes/` directory with 5 theme `.tex` files
5. Write `resume-preamble.tex` (using `enumitem`, theme-color aware)
6. Write `pandoc-defaults.yaml`

### Phase 2: Build System
7. Write `build_resume.sh` (frontmatter-aware, theme selector, page_mode)
8. Write `build_docker.sh` convenience wrapper
9. Write `Dockerfile` (pinned versions)
10. Fix ATS normalization Python (clean Unicode handling, apply to DOCX/TXT)

### Phase 3: Template Content
11. Write `example/resume.md` with placeholder content + inline comments
12. Write `AI_INSTRUCTIONS.md`
13. Create `reference.docx` with matching styles

### Phase 4: CI & Polish
14. Write `.github/workflows/build.yml` (shellcheck, build, Docker publish)
15. Write `README.md` (zero-install path first)
16. Write `LICENSE` (MIT)
17. Write `.gitignore`

### Phase 5: Launch
18. Create GitHub repo `denniyahh/ats_safe_resume`
19. Push
20. Verify CI runs, produces all formats, publishes Docker image
21. Verify `example/resume.pdf` renders in README
22. Wire up template remote in `my_resume`
23. Share on relevant communities (r/resumes, r/cscareerquestions, Hacker News, LinkedIn)

---

## 15. Future Enhancements (post-v1)

### High Priority
- **LinkedIn profile migration** — §12 above. Parse resume → generate LinkedIn-ready content blocks
- **Multiple font packs** — offer Serif (Lora/Merriweather) and Humanist alternatives to Source Sans 3
- **One-page smart fit** — algorithmically adjust fontsize/spacing based on content length rather than a binary toggle

### Medium Priority
- **GitHub template repository** — enable "Use this template" button for one-click fork
- **Codespaces / devcontainer** — one-click browser IDE with live PDF preview
- **JSON Resume import** — ingest from JSON Resume schema as an alternative to Markdown editing
- **Grammar/style linting** — CI step that checks for passive voice, weak verbs, missing metrics
- **NPM / Homebrew distribution** — `npx ats-safe-resume` or `brew install ats-safe-resume`

### Low Priority
- **Section reordering** — change section order via frontmatter without editing markdown
- **Photo support** — optional profile photo in PDF (where culturally appropriate)
- **Cover letter template** — matching cover letter from same markdown metadata
- **i18n** — support for right-to-left languages, localized date formats, region-specific resume conventions
- **ATS score simulator** — CI step that evaluates the resume against common ATS keyword heuristics
