# LinkedIn Sync

Sync your `ats_safe_resume` markdown resume to your LinkedIn profile via Playwright browser automation.

## How it works

```
resume.md  →  Python parser  →  JSON Resume  →  mapper  →  LinkedIn profile
                                                              ├─ Headline
                                                              ├─ About
                                                              ├─ Positions (exact mirror)
                                                              ├─ Skills (add-only)
                                                              └─ Education (exact mirror)
```

On first run, a browser window opens for manual LinkedIn login. Your session is saved to `cookies/` and reused on subsequent runs.

## Setup

```bash
cd linkedin_sync
npm install
npx playwright install chromium
```

## Usage

```bash
# Dry run — prints what would change without touching LinkedIn
node index.js --dry-run

# Live sync (uses default resume path: ../../my_resume/resume.md)
node index.js

# Custom resume path
node index.js --resume /path/to/your/resume.md
```

## What gets synced

| Section    | Behavior |
|------------|----------|
| Headline   | Replaced with resume title line |
| About      | Replaced with Executive Profile |
| Positions  | Exact mirror — matched by company+title. Updates matching entries, adds new ones, deletes LinkedIn-only entries that aren't in the resume. |
| Skills     | Add-only — pasted into skills editor (LinkedIn deduplicates, 50-skill cap) |
| Education  | Exact mirror — matched by school+degree. Updates matching entries, adds new ones, deletes LinkedIn-only entries that aren't in the resume. |

## Safety

- **Headful browser** — you see everything happening in a visible window
- **Dry-run mode** — `--dry-run` prints the plan without touching LinkedIn
- **Persistent session** — login once, reuses cookies on subsequent runs
- **DOM validation** — before any edits, validates all selectors against the live DOM. Sections with broken selectors are skipped and reported with screenshots.

## Selector validation

Every run (including dry runs) validates selectors before touching anything:

```
🔍 Validating LinkedIn DOM selectors...

  ✓ Headline: OK
  ✗ Positions / Experience: 2 selectors broken
      ─ modalTitle: none of [input[name="title"], ...] matched
      ─ modalCompany: none of [input[name="companyName"], ...] matched
      📸 linkedin_sync/screenshots/positions-2026-05-31T....png

  Result: 1 section(s) need selector updates, 4 ready.
```

When LinkedIn changes their DOM:
1. Validation detects the breakage before any edits
2. Screenshots are saved to `screenshots/` for debugging
3. Only validated sections are synced — broken ones are skipped
4. Update the selectors in `lib/linkedin.js` (the `SELECTORS` object at the top)

## Anti-detection

- `playwright-extra` with `puppeteer-extra-plugin-stealth`
- Realistic viewport, user agent, and human-like delays
- Persistent browser context (no repeated logins that trigger flags)

## Known LinkedIn quirks

- **Deletion dialogs** — LinkedIn's confirmation dialogs use transparent overlays that intercept pointer events on dialog buttons. The code removes the overlay from the DOM before clicking Delete/Confirm.
- **Save button coverage** — when filling degree/company typeahead inputs, LinkedIn's autocomplete dropdown can cover the Save button. Pressing Escape before Save dismisses it.
- **Date selectors** — the form layout differs between adding new positions and editing existing ones (Employment Type dropdown shifts indices). The code detects form type dynamically.

## Limitations

- LinkedIn's DOM changes frequently — the validation layer detects this, but selectors still need manual updates when they change
- Skills are add-only (LinkedIn has a 50-skill cap)
- "Earlier Experience" entries in the resume aren't synced (they're unstructured in markdown)
- Dates are mapped as best-effort — LinkedIn's date pickers vary by locale
