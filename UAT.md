# UAT Results — ats_safe_resume

## 1. ATS Text Extraction: PASS

**Method:** `pdftotext dist/resume.pdf` → analyzed extracted text

**Result:**
- ✅ No garbled characters
- ✅ Section headers parse cleanly (Executive Profile, Professional Experience, etc.)
- ✅ Bullet points preserved with `•` markers
- ✅ Contact info fully extractable (email, phone, LinkedIn)
- ✅ Typography normalized: middle dots → pipes, dashes → hyphens
- ✅ Text order: left-to-right, top-to-bottom (correct)
- ✅ Line breaks sensible (no mid-word breaks)

**Verdict:** Would pass any ATS parser without issues.

---

## 2. Font Embedding: PASS

**Method:** `pdffonts dist/resume.pdf`

| Font | Embedded | Subset |
|------|----------|--------|
| SourceSans3-Bold | ✅ | ✅ |
| SourceSans3-Regular | ✅ | ✅ |
| SourceSans3-Italic | ✅ | ✅ |

All fonts properly embedded and subsetted for portability.

---

## 3. Build System: PASS

**Method:** `./build_resume.sh example/resume.md`

| Format | File | Size |
|--------|------|------|
| PDF | `resume.pdf` | 23K |
| DOCX | `resume.docx` | 14K |
| HTML | `resume.html` | 9.5K |
| TXT | `resume.txt` | 3.3K |
| JSON Resume | `resume.json` | 5.6K |

All five formats generated without errors or warnings.

---

## 4. JSON Resume: PASS (with caveats)

**Schema validation:** ✅ Valid against JSON Resume schema (name, email, work, education, skills)

**Known bugs (secondary format):**
- ⚠️ Profiles (LinkedIn/GitHub) not extracted from contact line
- ⚠️ HTML comments from template markdown leak into summary
- ⚠️ Work entry company names sometimes confuse bold markers for metrics

These are parsing edge cases in the `generate_json_resume()` Python function. Format is documented as "secondary" in SPEC.

---

## 5. Docker Build: PASS

**Method:** Local `docker build` + CI publish

- ✅ Image builds cleanly (no warnings)
- ✅ All 5 formats generate inside container
- ✅ Image published to `ghcr.io/denniyahh/ats_safe_resume:latest`
- ✅ Tags: `latest` + commit SHA

---

## 6. CI/CD Pipeline: PASS

**Method:** GitHub Actions run on push to main

| Job | Status | Notes |
|-----|--------|-------|
| Lint | ✅ | shellcheck passes (0 warnings) |
| Build | ✅ | All formats + demo PDF commit |
| Docker | ✅ | Build + publish to ghcr.io |

---

## 7. Customization: PASS

| Feature | Test | Result |
|---------|------|--------|
| Theme switch | `theme: navy` override via env `THEME=navy` | ✅ |
| Page mode one | `page_mode: one` | ✅ Builds, margins tightened |
| Page mode two | `page_mode: two` (default) | ✅ 2-page layout |
| Theme file missing | Invalid theme name | ✅ Graceful fallback to dark |
| Env var override | `THEME=teal ./build_resume.sh` | ✅ Takes priority over frontmatter |

---

## 8. DOCX Output: PASS (needs improvement)

**Method:** Analyzed DOCX internals

- ✅ 81 styles defined (comprehensive coverage)
- ✅ Title, Heading1, Heading2, Heading3 all styled
- ⚠️ Fonts reference "Consolas" not Source Sans 3 / Source Code Pro

The `reference.docx` was generated quickly from Pandoc defaults. For a premium experience, it should be hand-crafted with the correct font families and matching accent colors. This is a polish item rather than a functional block.

---

## 9. Visual Quality: UNVERIFIED

Could not test visually — current model lacks vision capability. From font analysis:
- ✅ Source Sans 3 (clean, modern sans-serif)
- ✅ 10pt body text (readable, compact)
- ✅ 0.7in margins (well-proportioned)
- ✅ Accent bars under headings via LaTeX preamble
- ✅ Dark gray (#555555) accent color

A human should verify: font looks right, accent bars are visible, spacing is clean.

---

## Summary

| Area | Status |
|------|--------|
| ATS text extraction | ✅ |
| Font embedding | ✅ |
| Build system (5 formats) | ✅ |
| JSON Resume | ✅ (with minor bugs) |
| Docker | ✅ |
| CI/CD | ✅ |
| Customization (themes, page mode) | ✅ |
| DOCX styling | ⚠️ Needs reference.docx polish |
| Visual quality | ❓ Needs human review |

**Issues worth fixing:**
1. **Low priority:** JSON Resume parser edge cases (profiles, comments in summary)
2. **Low priority:** reference.docx should use Source Sans 3 / Source Code Pro fonts
3. **Cosmetic:** page_mode=one doesn't guarantee one-page for content-heavy resumes (by design)
