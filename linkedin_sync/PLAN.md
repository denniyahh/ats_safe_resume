# LinkedIn Sync — Plan

## Overview

Sync an `ats_safe_resume` markdown resume to a LinkedIn profile using Playwright
browser automation with stealth plugin.

## Data Flow

```
resume.md
  → ats_safe_resume parser (Python subprocess)
    → JSON Resume (structured data)
      → mapper.js (field mapping)
        → LinkedIn Playwright automation
          ├─ headline (basics.label)
          ├─ about/summary (basics.summary)
          ├─ positions (work[]) — idempotent upsert by company+title
          ├─ skills (skills[]) — add-only (no delete)
          └─ education (education[])
```

## Architecture

```
linkedin_sync/
├── package.json           # playwright-extra + stealth
├── index.js               # CLI: node index.js [--resume path] [--dry-run]
├── lib/
│   ├── parser.js          # spawn Python parser → JSON Resume
│   ├── mapper.js          # JSON Resume → LinkedIn field map
│   └── linkedin.js        # Playwright: login, navigate, edit sections
├── cookies/               # gitignored — persistent browser context
│   └── .gitkeep
└── README.md
```

## State Persistence

- Browser context saved to `cookies/state.json` after first login
- Subsequent runs reuse the session unless it expires
- If session is invalid, prompts for re-login

## LinkedIn Edit Approach

LinkedIn uses modal-based editing. For each section:

1. **Headline**: Click edit pencil near headline → type in text input → save
2. **About**: Click edit pencil → paste into rich text editor → save
3. **Positions**: For each position:
   - Match existing by company+title → update description + dates
   - No match → click "Add position" → fill modal → save
   - Positions in LinkedIn but not in resume → skip (no delete)
4. **Skills**: Add-only — paste skills, LinkedIn deduplicates
5. **Education**: Match by institution → update; no match → add

## Anti-Detection

- playwright-extra with puppeteer-extra-plugin-stealth
- Headful mode (visible browser)
- Human-like delays between actions (500ms–2s random)
- Persistent browser context (no repeated logins)
- Realistic viewport and user agent

## MVP Deliverables

- [x] Parse resume into structured data
- [ ] Login flow with cookie persistence
- [ ] Headline update
- [ ] About/Summary update
- [ ] Position update (match + upsert)
- [ ] Skills update (add-only)
- [ ] Education update (match + upsert)
- [ ] Dry-run mode (print what would change)
- [ ] README with usage instructions
