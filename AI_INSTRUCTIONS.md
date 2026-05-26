# AI Instructions for Resume Assistance

This file primes AI coding assistants (Claude, Cursor, Copilot, etc.) when users ask for help writing, editing, or improving their resume. It defines the resume format, quality standards, and ATS optimization strategies.

---

## Resume Structure

The resume is a single Markdown file (`resume.md`) with YAML frontmatter and the following section order:

1. **Name & Title** (H1 + bold subtitle)
2. **Contact line** (city, email, phone, LinkedIn, GitHub — separated by middle dots)
3. **Executive Profile** (2-3 sentence summary with quantified results)
4. **Core Expertise** (4-6 comma-separated keyword areas)
5. **Professional Experience** (reverse chronological, 2-4 bullets per role)
6. **Technical Skills** (categorized: **Category:** skill, skill, skill)
7. **Education** (school, degree)

## Bullet Point Quality Standards

Every bullet point must pass this checklist:

- [ ] **Action verb**: Starts with a strong verb (Led, Built, Shipped, Grew, Designed, Drove, Launched, Delivered, Established, Founded, Reduced, Increased)
- [ ] **Scope/Context**: Describes what was done and why it mattered
- [ ] **Measurable outcome**: Contains a bold metric (**_$25MM_**, **_40%_**, **_200+_**)
- [ ] **No vague verbs**: Never use "Helped with," "Responsible for," "Worked on," "Involved in," "Participated in"
- [ ] **No passive voice**: Active voice only — "Shipped feature X" not "Feature X was shipped"
- [ ] **AT LEAST 1 bold metric per bullet** — bold markers in markdown: `**$25MM**`

### Bad → Good Examples

| Bad | Good |
|-----|------|
| "Responsible for data platform strategy" | "Led data platform strategy, growing revenue from **$5MM** to **$25MM**" |
| "Helped with AI product launch" | "Launched AI-powered analytics product, reaching **$8MM** ARR in 18 months" |
| "Worked with engineering teams" | "Established product practice across 4 engineering teams, reducing delivery time by **40%**" |
| "Involved in Jira migration" | "Drove enterprise-wide Jira migration, shortening PI Planning from hours to **seconds**" |

## ATS Optimization

The build pipeline normalizes typography for ATS safety (en/em dashes → hyphens, middle dots → pipes, etc.). But you should also:

1. **Use standard section headers** — ATS parsers look for "Professional Experience," "Education," "Technical Skills," "Executive Profile"
2. **Avoid tables and multi-column layouts** — ATS parsers read left-to-right, top-to-bottom
3. **Use bold for metrics only** — LaTeX renders bold well; avoid over-bolding random words
4. **Include keywords from job descriptions** — the skills section and bullet points should mirror language from target roles
5. **No acronyms without expansion** — first mention: "Applicant Tracking System (ATS)"
6. **Standard date format** — "Jun 2021 – Present" or "Jun 2021 – Sep 2023"

## Section-Specific Guidance

### Executive Profile
- 2-3 sentences maximum
- Must include: years of experience, key domains, one standout achievement with a bold metric
- Think "elevator pitch" — readable in 10 seconds
- Third person is fine ("Product leader with...")

### Professional Experience
- Order: most recent first
- Each role: 2-4 bullets
- Current role can have up to 3 sub-roles (showing progression) with 2-4 bullets each
- First bullet of each role should be the "headline" — biggest impact metric
- Use `### [Company Name](url) — City, State` for company header
- Use `**Title**` for the role title, `*Date span*` for the date range

### Technical Skills
- Group into 3-5 categories (e.g., Product, Data, Platforms, Methods)
- Each category: **Category:** skill1, skill2, skill3
- Order by relevance to the target role
- Skills should be real, not aspirational — you'll be tested on them

### Education
- Most recent first
- Format: **Institution** — Degree, Field
- GPA optional (include if 3.5+)
- Dean's list, honors, relevant coursework optional

## Page Count & Layout

- Default layout: **2 pages** (Source Sans 3, 10pt, 0.7in margins)
- To force 1 page, set `page_mode: one` in YAML frontmatter
- To fit 1 page: cut weaker bullets, merge metrics, reduce fontsize in frontmatter to 9.5pt
- Never exceed 2 pages

## Content Improvement Workflow

When the user says "improve [section]":

1. Read the current content
2. For each bullet, ask: what's the metric? What was the action? What was the scope?
3. Rewrite with the STAR pattern + bold metric
4. Show the diff, explain the changes
5. Only apply changes when the user approves

## Theme & Style

- Colors are controlled by `theme:` in YAML frontmatter — never edit `themes/*.tex` directly
- Available themes: `dark` (default), `navy`, `teal`, `burgundy`, `minimal`
- Fonts are always Source Sans 3 (body) and Source Code Pro (mono)
- The build system adds accent bars under section headings automatically

## Troubleshooting Common Issues

| Symptom | Likely cause |
|---------|-------------|
| PDF won't build | Check pandoc + LaTeX installed, or use Docker |
| Font looks wrong | Source Sans 3 not installed — install it or use Docker |
| Section headers lack accent bar | YAML frontmatter has a malformed `theme:` field |
| Page count is wrong | Adjust `page_mode` or `fontsize` in frontmatter |
| Contact line has odd characters | Those are typographic characters — ATS normalization handles them for PDF |
