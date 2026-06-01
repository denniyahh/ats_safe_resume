/**
 * LinkedIn profile updater using Playwright + stealth.
 *
 * Uses launchPersistentContext for cookie/session persistence.
 * Navigates to profile page, clicks edit links, fills forms, saves.
 *
 * Before any edits, validates selectors against the live DOM.
 * Sections with broken selectors are skipped and reported with screenshots.
 */
import { chromium } from 'playwright-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import { resolve } from 'node:path';
import { randomInt } from 'node:crypto';
import { mkdirSync } from 'node:fs';

chromium.use(StealthPlugin());

const COOKIES_DIR = resolve(import.meta.dirname, '../cookies');
const SCREENSHOTS_DIR = resolve(import.meta.dirname, '../screenshots');
const LINKEDIN_BASE = 'https://www.linkedin.com';

mkdirSync(SCREENSHOTS_DIR, { recursive: true });

// ─── selector registry ─────────────────────────────────────────
// Each section defines the profile-page link and the form-page selectors.

const SELECTORS = {
  headline: {
    name: 'Headline (Intro)',
    profileLink: 'a[aria-label="Edit profile"]',
    elements: {
      headlineEditor: ['div[contenteditable="true"]'],
    },
  },
  about: {
    name: 'About',
    profileLink: 'a[aria-label="Edit about"]',
    elements: {
      editor: ['div[role="textbox"]'],
    },
  },
  position: {
    name: 'Position (edit)',
    detailsUrl: `${LINKEDIN_BASE}/in/me/details/experience/`,
    editUrlPattern: '/details/experience/edit/forms/',
    newUrl: `${LINKEDIN_BASE}/in/me/details/experience/edit/forms/new/`,
    elements: {
      titleInput: ['input[placeholder*="Retail"]', 'input[placeholder*="Sales Manager"]'],
      companyInput: ['input[placeholder*="Microsoft"]'],
      locationInput: ['input[placeholder*="London"]'],
      descriptionEditor: ['div[contenteditable="true"]', 'div[role="textbox"]'],
      startMonthSelect: ['select'],
      startYearSelect: ['select'],
      endMonthSelect: ['select'],
      endYearSelect: ['select'],
      currentCheckbox: ['input[type="checkbox"]'],
    },
  },
  education: {
    name: 'Education',
    detailsUrl: `${LINKEDIN_BASE}/in/me/details/education/`,
    editUrlPattern: '/details/education/edit/forms/',
    newUrl: `${LINKEDIN_BASE}/in/me/details/education/edit/forms/new/?profileFormEntryPoint=Detail`,
    elements: {
      schoolInput: ['input[placeholder*="Boston"]', 'input[placeholder*="University"]'],
      degreeInput: ['input[placeholder*="Bachelor"]', 'input[placeholder*="Science"]'],
      fieldInput: ['input[placeholder*="Business"]'],
    },
  },
  skills: {
    name: 'Skills',
    detailsUrl: `${LINKEDIN_BASE}/in/me/details/skills/`,
    addLink: 'a[aria-label="Add a skill"]',
    elements: {
      skillInput: ['input[placeholder*="Skill"]'],
      dropdownOption: ['[role="option"]'],
    },
  },
  shared: {
    name: 'Shared (Save button)',
    elements: {
      saveBtn: ['button:has-text("Save")'],
    },
  },
};

// ─── helpers ──────────────────────────────────────────────────

function delay(ms) {
  const jitter = randomInt(0, ms);
  return new Promise(r => setTimeout(r, ms + jitter));
}

async function findFirst(page, selectors) {
  for (const sel of selectors) {
    try {
      const count = await page.locator(sel).count();
      if (count > 0) return { locator: page.locator(sel).first(), matched: sel };
    } catch { /* invalid selector */ }
  }
  return null;
}

function ts() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

// ─── main class ───────────────────────────────────────────────

export class LinkedInUpdater {
  constructor(opts = {}) {
    this.dryRun = opts.dryRun ?? false;
    this.headless = opts.headless ?? false;
    this.context = null;
    this.page = null;
    this.validation = null;
  }

  // ─── lifecycle ──────────────────────────────────────────────

  async launch() {
    this.context = await chromium.launchPersistentContext(COOKIES_DIR, {
      headless: this.headless,
      viewport: { width: 1280, height: 900 },
      userAgent:
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
      args: ['--disable-blink-features=AutomationControlled', '--no-sandbox'],
    });
    this.page = await this.context.newPage();
  }

  async close() {
    if (this.context) await this.context.close();
  }

  // ─── login ──────────────────────────────────────────────────

  async ensureLoggedIn() {
    await this.page.goto(`${LINKEDIN_BASE}/feed/`, { waitUntil: 'domcontentloaded' });

    const loggedIn = await this.page
      .locator(
        '.feed-shared-update-v2, .share-box-feed-entry, ' +
        '[data-id="scrolling-header"] nav, .global-nav__me, ' +
        'button[aria-label*="Start a post"]'
      )
      .count()
      .then(c => c > 0);

    if (loggedIn) {
      console.log('✓ Already logged in (session reused)');
      return;
    }

    console.log('⚠ Not logged in. Opening LinkedIn login page...');
    console.log('  Please log in manually in the browser window.');
    console.log('  Your session will be saved for future runs.\n');

    await this.page.goto(`${LINKEDIN_BASE}/login`, { waitUntil: 'domcontentloaded' });

    this.page.on('framenavigated', frame => {
      if (frame === this.page.mainFrame()) console.log(`  [nav] ${frame.url()}`);
    });

    console.log('  Waiting for login...');
    try {
      await this.page.waitForURL(
        url => {
          const href = url.toString();
          return !href.includes('/login') && !href.includes('checkpoint') && !href.includes('/uas/login');
        },
        { timeout: 900_000 }
      );
      console.log('✓ Logged in successfully. Session saved.');
    } catch (err) {
      throw new Error(`Login failed: ${err.message}`);
    }
  }

  async goToProfile() {
    if (this.page.url().includes('/edit/') || this.page.url().includes('/details/') || !this.page.url().includes('/in/')) {
      await this.page.goto(`${LINKEDIN_BASE}/in/me/`, { waitUntil: 'domcontentloaded', timeout: 15000 });
      await delay(2000);
    }
    console.log('✓ On profile page');
  }

  // ─── selector validation ────────────────────────────────────

  async validateSelectors() {
    console.log('\n🔍 Validating LinkedIn DOM selectors...\n');
    const report = {};

    for (const [key, group] of Object.entries(SELECTORS)) {
      if (key === 'shared') continue;

      const result = { status: 'ok', broken: [], screenshot: null, group: group.name };

      if (group.profileLink) {
        // Sections accessed via profile page link click
        await this.goToProfile();
        await this._dismissDialogs();
        const link = this.page.locator(group.profileLink).first();
        if (await link.count() > 0) {
          await link.click();
          await delay(3000);
        } else {
          result.status = 'broken';
          result.broken.push({ element: 'profileLink', tried: [group.profileLink] });
        }

        if (result.status === 'ok') {
          const allElements = { ...group.elements, ...SELECTORS.shared.elements };
          for (const [elemKey, selectors] of Object.entries(allElements)) {
            const found = await findFirst(this.page, selectors);
            if (!found) {
              result.status = 'broken';
              result.broken.push({ element: elemKey, tried: selectors });
            }
          }
        }
      } else if (group.detailsUrl) {
        // Sections accessed via details page (e.g., positions, education, skills)
        await this.page.goto(group.detailsUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
        await delay(2000);

        if (group.editUrlPattern) {
          // Check that edit links exist
          const editLinks = await this.page.evaluate((pattern) => {
            return document.querySelectorAll('a[href*="' + pattern + '"]').length;
          }, group.editUrlPattern);

          if (editLinks === 0) {
            result.status = 'broken';
            result.broken.push({ element: 'editLinks', tried: [`links containing "${group.editUrlPattern}"`] });
          }
        } else if (group.addLink) {
          // Skills: check add link exists
          const addLink = this.page.locator(group.addLink).first();
          if (await addLink.count() === 0) {
            result.status = 'broken';
            result.broken.push({ element: 'addLink', tried: [group.addLink] });
          }
        }
      }

      if (result.status === 'broken') {
        const screenshotPath = resolve(SCREENSHOTS_DIR, `${key}-${ts()}.png`);
        await this.page.screenshot({ path: screenshotPath, fullPage: false });
        result.screenshot = screenshotPath;

        console.log(`  ✗ ${group.name}: ${result.broken.length} selectors broken`);
        for (const b of result.broken) {
          console.log(`      ─ ${b.element}: none of [${b.tried.join(', ')}] matched`);
        }
        console.log(`      📸 ${screenshotPath}`);
      } else {
        console.log(`  ✓ ${group.name}: OK`);
      }

      report[key] = result;
    }

    const broken = Object.values(report).filter(r => r.status === 'broken');
    console.log(`\n  Result: ${broken.length} section(s) need selector updates, ${Object.keys(report).length - broken.length} ready.\n`);
    return report;
  }

  // ─── save helper ────────────────────────────────────────────

  async _save(opts = {}) {
    const saveBtn = await findFirst(this.page, SELECTORS.shared.elements.saveBtn);
    if (!saveBtn) throw new Error('Save button not found');

    await saveBtn.locator.click();
    await delay(2000);

    if (opts.skipDismiss) {
      // For new-position adds: wait for LinkedIn to process, then confirm.
      await delay(3000);
      const confirmBtn = await findFirst(this.page, [
        'button:has-text("Done")',
        'button:has-text("Continue")',
        'button[aria-label="Done"]',
      ]);
      if (confirmBtn) {
        await confirmBtn.locator.click();
        await delay(2000);
      }
    } else {
      await this._dismissDialogs();
    }
  }

  async _dismissDialogs() {
    // LinkedIn often shows a dialog after saving profile changes
    const dismissSelectors = [
      'button[aria-label="Dismiss"]',
      'button[aria-label="Close"]',
      'dialog button:has-text("Done")',
      'dialog button:has-text("Got it")',
    ];
    for (const sel of dismissSelectors) {
      try {
        const btn = this.page.locator(sel).first();
        if (await btn.count() > 0) {
          await btn.click();
          await delay(500);
        }
      } catch { /* dialog may have already closed */ }
    }
    // Also try pressing Escape
    try {
      await this.page.keyboard.press('Escape');
      await delay(500);
    } catch { /* no dialog */ }
  }

  // ─── headline ───────────────────────────────────────────────

  async updateHeadline(headline) {
    if (!headline) return;
    console.log(`  ▶ Headline → "${headline}"`);
    if (this.dryRun) return;

    await this.goToProfile();
    await this.page.locator(SELECTORS.headline.profileLink).first().click();
    await delay(3000);

    const editor = await findFirst(this.page, SELECTORS.headline.elements.headlineEditor);
    if (!editor) throw new Error('Headline editor not found');

    // Clear and type (contenteditable divs need different handling)
    await editor.locator.click();
    await editor.locator.fill('');
    await editor.locator.fill(headline);
    await delay(500);

    await this._save();
    console.log('  ✓ Headline updated');
  }

  // ─── about ──────────────────────────────────────────────────

  async updateAbout(about) {
    if (!about) return;
    console.log(`  ▶ About → "${about.slice(0, 80)}..."`);
    if (this.dryRun) return;

    await this.goToProfile();
    await this.page.locator(SELECTORS.about.profileLink).first().click();
    await delay(3000);

    const editor = await findFirst(this.page, SELECTORS.about.elements.editor);
    if (!editor) throw new Error('About editor not found');

    await editor.locator.click();
    // Select all and delete
    await this.page.keyboard.press('Control+a');
    await this.page.keyboard.press('Backspace');
    await editor.locator.fill(about);
    await delay(500);

    await this._save();
    console.log('  ✓ About updated');
  }

  // ─── positions ──────────────────────────────────────────────

  /**
   * Discover existing LinkedIn positions and scrape their date ranges.
   * Returns array of { aria, href, dateText }.
   */
  async _discoverPositions() {
    await this.page.goto(SELECTORS.position.detailsUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await delay(3000);

    const linkedInPositions = await this.page.evaluate((pattern) => {
      const dateRx = /\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\s*[-–—]\s*(Present|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\b/;

      return [...document.querySelectorAll('a[href*="' + pattern + '"]')]
        .filter(a => a.getAttribute('aria-label')?.startsWith('Edit '))
        .map(a => {
          // Walk up to the list item / container, then find date text within it
          let el = a;
          for (let i = 0; i < 5 && el; i++) {
            const text = el.textContent || '';
            const m = text.match(dateRx);
            if (m) return { aria: a.getAttribute('aria-label') || '', href: a.getAttribute('href'), dateText: m[0] };
            el = el.parentElement;
          }
          return { aria: a.getAttribute('aria-label') || '', href: a.getAttribute('href'), dateText: null };
        });
    }, SELECTORS.position.editUrlPattern);

    console.log(`  Found ${linkedInPositions.length} existing positions on LinkedIn`);
    return linkedInPositions;
  }

  /**
   * Compare resume dates against LinkedIn's displayed date range.
   * LinkedIn format: "Jun 2021 - Present" or "Aug 2019 - May 2021"
   * Resume format: { month: 6, year: 2021 } or null for Present.
   */
  _datesMatch(resumePos, linkedInDateText) {
    if (!linkedInDateText) return false;
    const months = { jan:1,feb:2,mar:3,apr:4,may:5,jun:6,jul:7,aug:8,sep:9,oct:10,nov:11,dec:12 };

    const parts = linkedInDateText.split(/\s*[-–—]\s*/);
    if (parts.length !== 2) return false;

    const parseDate = (s) => {
      if (/present/i.test(s)) return null;
      const m = /([A-Za-z]{3})\s+(\d{4})/i.exec(s.trim());
      if (!m) return null;
      return { month: months[m[1].toLowerCase()], year: parseInt(m[2], 10) };
    };

    const liStart = parseDate(parts[0]);
    const liEnd = parseDate(parts[1]);

    const rStart = resumePos.startDate;
    const rEnd = resumePos.endDate;

    const startMatch = liStart && rStart
      && liStart.month === rStart.month && liStart.year === rStart.year;

    const endMatch = (liEnd === null && rEnd === null)
      || (liEnd && rEnd && liEnd.month === rEnd.month && liEnd.year === rEnd.year);

    return startMatch && endMatch;
  }

  /**
   * Match a resume position against a LinkedIn aria-label.
   * Aria format: "Edit {title} at {company}"
   * Matches on BOTH company AND title to distinguish multiple roles at same company.
   */
  _matchPosition(resumePos, linkedInAria) {
    const aria = linkedInAria.toLowerCase();
    const company = resumePos.company.toLowerCase();
    const title = resumePos.title.toLowerCase();

    // Must contain company
    if (!aria.includes(company)) {
      // Try without common prefixes
      const stripped = company.replace(/^(the|a|an)\s+/i, '');
      if (!(stripped !== company && aria.includes(stripped))) {
        // Try first word match
        const firstWord = company.split(' ')[0];
        if (!(firstWord.length > 3 && aria.includes(firstWord))) {
          return false;
        }
      }
    }

    // Must also contain the title (fuzzy — "Product Manager" matches "Product Manager / Scrum Master")
    const titleWords = title.split(/\s+/).filter(w => w.length > 3);
    if (titleWords.length === 0) return true; // generic title, match on company only
    const titleMatch = titleWords.some(w => aria.includes(w));
    return titleMatch;
  }

  async updatePositions(positions) {
    if (!positions.length) return;
    console.log(`  ▶ ${positions.length} positions`);

    // Discover existing LinkedIn positions
    const existing = this.dryRun ? [] : await this._discoverPositions();
    const matched = []; // track which LinkedIn entries were used

    for (let i = 0; i < positions.length; i++) {
      const pos = positions[i];
      const matchIdx = existing.findIndex(li => this._matchPosition(pos, li.aria));
      const match = matchIdx >= 0 ? existing[matchIdx] : null;

      if (match) {
        // Remove from array so subsequent entries can't match the same LinkedIn position
        existing.splice(matchIdx, 1);
        matched.push(match);

        // Check if dates already match — skip if so
        if (this._datesMatch(pos, match.dateText)) {
          console.log(`    ✓ ${pos.title} @ ${pos.company} (dates match — skipped)`);
          continue;
        }

        console.log(`    ✎ ${pos.title} @ ${pos.company} (dates differ: LI="${match.dateText}" → delete + re-add)`);
        if (this.dryRun) continue;
        try {
          await this._deletePosition(match.href, pos);
          await this._addPosition(pos);
        } catch (err) {
          console.error(`    ✗ Sync failed: ${err.message}`);
        }
      } else {
        console.log(`    + ${pos.title} @ ${pos.company} (new)`);
        if (this.dryRun) continue;
        try {
          await this._addPosition(pos);
        } catch (err) {
          console.error(`    ✗ Add failed: ${err.message}`);
        }
      }
    }

    // Post-sync duplicate removal: any remaining LinkedIn entries that match
    // a resume position's company+title are duplicates (not in source resume).
    // Delete them to make LinkedIn an exact mirror of the resume.
    for (const leftover of existing) {
      let matchFound = null;
      for (const pos of positions) {
        if (this._matchPosition(pos, leftover.aria)) {
          matchFound = pos;
          break;
        }
      }
      if (matchFound) {
        try {
          await this._deletePosition(leftover.href, matchFound);
        } catch (err) {
          console.error(`    ✗ Delete failed: ${err.message}`);
        }
      }
    }
  }

  async _addPosition(pos) {
    await this.page.goto(SELECTORS.position.newUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await delay(2000);

    const s = SELECTORS.position.elements;

    // Title
    const titleInput = await findFirst(this.page, s.titleInput);
    if (titleInput) await titleInput.locator.fill(pos.title);

    // Company
    const companyInput = await findFirst(this.page, s.companyInput);
    if (companyInput) await companyInput.locator.fill(pos.company);

    // Location
    if (pos.location) {
      const locInput = await findFirst(this.page, s.locationInput);
      if (locInput) await locInput.locator.fill(pos.location);
    }

    // ── Dates, Employment Type, Location Type ──────────────────
    // Use page.evaluate to directly manipulate DOM and dispatch React events.
    // Playwright's selectOption has unreliable value/label matching on React selects.

    if (pos.startDate || pos.endDate) {
      try {
        // Step 1: Uncheck "I currently work here" if we have an end date.
        // Find by label text — LinkedIn's checkbox may not be a plain <input>.
        if (pos.endDate) {
          const wasChecked = await this.page.evaluate(() => {
            // Strategy 1: Find label containing "currently work" or "current role"
            const labels = [...document.querySelectorAll('label')];
            for (const label of labels) {
              if (/currently work|current role/i.test(label.textContent || '')) {
                // Try to find the associated input
                const input = label.querySelector('input[type="checkbox"]')
                  || (label.htmlFor ? document.getElementById(label.htmlFor) : null)
                  || document.querySelector('input[type="checkbox"]');
                if (input && input.checked) {
                  input.checked = false;
                  input.dispatchEvent(new Event('change', { bubbles: true }));
                  return true;
                }
                // Fallback: click the label itself to toggle
                label.click();
                return true;
              }
            }
            // Strategy 2: Any checked checkbox on the page
            const cb = document.querySelector('input[type="checkbox"]:checked');
            if (cb) { cb.checked = false; cb.dispatchEvent(new Event('change', { bubbles: true })); return true; }
            return false;
          });
          if (wasChecked) await delay(3000);
        }

        // Step 2: Set all dates, Employment Type, Location Type
        const setResult = await this.page.evaluate(({ sMonth, sYear, eMonth, eYear }) => {
          const selects = [...document.querySelectorAll('select')];
          const log = [];

          let empType = null, locType = null;
          let startM = null, startY = null, endM = null, endY = null;
          for (const sel of selects) {
            const first = (sel.options[0]?.text || '').toLowerCase();
            if (first === 'month' && !startM) startM = sel;
            else if (first === 'year' && !startY) startY = sel;
            else if (first === 'month' && startM && !endM) endM = sel;
            else if (first === 'year' && startY && !endY) endY = sel;
            else if (!/month|year|arabic|language/i.test(first) && /please select/i.test(first)) {
              if (!empType) empType = sel; else if (!locType) locType = sel;
            }
          }
          log.push(`selects: total=${selects.length} startM=${!!startM} startY=${!!startY} endM=${!!endM} endY=${!!endY} empType=${!!empType} locType=${!!locType}`);

          if (empType) { empType.value = '12'; empType.dispatchEvent(new Event('change', { bubbles: true })); log.push(`empType=12`); }
          if (locType) { locType.value = ''; locType.dispatchEvent(new Event('change', { bubbles: true })); log.push(`locType=''`); }

          if (sMonth && sYear && startM && startY) {
            startM.value = String(sMonth); startM.dispatchEvent(new Event('change', { bubbles: true }));
            startY.value = String(sYear); startY.dispatchEvent(new Event('change', { bubbles: true }));
            log.push(`startDate=${sMonth}/${sYear}`);
          }

          if (eMonth && eYear && endM && endY) {
            endM.value = String(eMonth); endM.dispatchEvent(new Event('change', { bubbles: true }));
            endY.value = String(eYear); endY.dispatchEvent(new Event('change', { bubbles: true }));
            log.push(`endDate=${eMonth}/${eYear}`);
          } else if (eMonth && eYear) {
            log.push(`END DATE SKIPPED: endM=${!!endM} endY=${!!endY}`);
          }

          return log.join(' | ');
        }, {
          sMonth: pos.startDate?.month ?? null,
          sYear: pos.startDate?.year ?? null,
          eMonth: pos.endDate?.month ?? null,
          eYear: pos.endDate?.year ?? null,
        });
        console.log(`    [dates] ${setResult}`);
        await delay(1000);
      } catch (e) { console.error(`    ⚠ date fields: ${e.message}`); }
    }

    // Description
    if (pos.description) {
      const desc = await findFirst(this.page, s.descriptionEditor);
      if (desc) await desc.locator.fill(pos.description);
    }

    // Dismiss typeahead dropdowns before Save
    await this.page.keyboard.press('Escape');
    await delay(200);

    // Screenshot before save for diagnostics
    const ssPath = resolve(SCREENSHOTS_DIR, `pre-save-${pos.title.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 40)}.png`);
    await this.page.screenshot({ path: ssPath, fullPage: true });
    console.log(`    📸 pre-save screenshot: ${ssPath}`);

    // Dismiss overlay dialogs (not the form dialog which contains Save)
    try {
      await this.page.evaluate(() => {
        document.querySelectorAll('dialog[open]').forEach(d => {
          const hasSave = Array.from(d.querySelectorAll('button'))
            .some(b => /save/i.test(b.textContent));
          if (!hasSave) d.remove();
        });
      });
    } catch {}

    // Force-click the Save button inside the form dialog
    await this.page.locator('button:has-text("Save")').first().click({ force: true, timeout: 10000 });
    await delay(2000);
    await this._dismissDialogs();
    console.log(`    ✓ ${pos.title} @ ${pos.company}`);
  }

  // ─── skills ─────────────────────────────────────────────────

  async _discoverSkills() {
    await this.page.goto(SELECTORS.skills.detailsUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await delay(2000);

    const linkedInSkills = await this.page.evaluate(() => {
      return [...document.querySelectorAll('a[aria-label*=\"Edit \"][aria-label*=\" skill\"]')]
        .map(a => {
          const label = a.getAttribute('aria-label') || '';
          return label.replace(/^Edit /, '').replace(/ skill$/, '').toLowerCase();
        });
    });

    console.log(`  Found ${linkedInSkills.length} existing skills on LinkedIn`);
    return linkedInSkills;
  }

  async updateSkills(skills) {
    if (!skills.length) return;
    console.log(`  ▶ ${skills.length} skills`);

    const existing = this.dryRun ? [] : await this._discoverSkills();
    const existingLower = new Set(existing.map(s => s.toLowerCase()));

    const newSkills = skills.filter(s => !existingLower.has(s.toLowerCase()));
    if (!newSkills.length) {
      console.log('  All skills already on LinkedIn — nothing to add');
      return;
    }

    console.log(`  ${newSkills.length} new skills to add (${skills.length - newSkills.length} already exist)`);

    // Navigate to details page for the add-skill flow
    await this.page.goto(SELECTORS.skills.detailsUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await delay(2000);

    for (const skill of newSkills.slice(0, 50)) {
      console.log(`    + ${skill}`);
      if (this.dryRun) continue;

      try {
        // Click Add a skill
        const addLink = this.page.locator(SELECTORS.skills.addLink).first();
        await addLink.click();
        await delay(2000);

        // Type skill
        const input = await findFirst(this.page, SELECTORS.skills.elements.skillInput);
        if (!input) throw new Error('Skill input not found');
        await input.locator.fill(skill);
        await delay(1500);

        // Click dropdown option
        const option = this.page.locator('[role="option"]').first();
        if (await option.count() > 0) {
          await option.click();
          await delay(500);
        } else {
          console.log('      ⚠ No dropdown match — skipping');
          // Go back to details page
          await this.page.goto(SELECTORS.skills.detailsUrl, { waitUntil: 'domcontentloaded', timeout: 10000 });
          await delay(1500);
          continue;
        }

        // Save
        await this._save();
        await delay(2000);

        // Go back to details page for next skill
        await this.page.goto(SELECTORS.skills.detailsUrl, { waitUntil: 'domcontentloaded', timeout: 10000 });
        await delay(1500);
        console.log(`    ✓ ${skill}`);
      } catch (err) {
        console.error(`    ✗ ${skill}: ${err.message}`);
        // Reset to details page
        try {
          await this.page.goto(SELECTORS.skills.detailsUrl, { waitUntil: 'domcontentloaded', timeout: 10000 });
          await delay(1500);
        } catch { /* can't recover */ }
      }
    }
  }

  // ─── education ──────────────────────────────────────────────

  async _discoverEducation() {
    await this.page.goto(SELECTORS.education.detailsUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await delay(2000);

    const linkedInEdu = await this.page.evaluate((pattern) => {
      return [...document.querySelectorAll('a[href*="' + pattern + '"]')]
        .filter(a => a.getAttribute('aria-label')?.startsWith('Edit education'))
        .map(a => ({
          aria: a.getAttribute('aria-label') || '',
          href: a.getAttribute('href'),
        }));
    }, SELECTORS.education.editUrlPattern);

    console.log(`  Found ${linkedInEdu.length} existing education entries on LinkedIn`);
    return linkedInEdu;
  }

  /**
   * Match a resume education entry against a LinkedIn aria-label + degree.
   * Also checks degree if LinkedIn degree info was scraped during discovery.
   */
  _matchEducation(resumeEdu, linkedInEntry) {
    // Must match school name first
    const aria = linkedInEntry.aria.toLowerCase();
    const school = resumeEdu.school.toLowerCase();
    let schoolMatch = aria.includes(school);
    if (!schoolMatch) {
      const stripped = school.replace(/^(the|a|an)\s+/i, '');
      if (stripped !== school && aria.includes(stripped)) schoolMatch = true;
    }
    if (!schoolMatch) {
      const firstWord = school.split(' ')[0];
      if (firstWord.length > 3 && aria.includes(firstWord)) schoolMatch = true;
    }
    if (!schoolMatch) return false;

    // If we have degree info from LinkedIn, check degree too
    if (linkedInEntry.degree && resumeEdu.degree) {
      const liDegree = linkedInEntry.degree.toLowerCase();
      const resumeDegree = resumeEdu.degree.toLowerCase();
      // Fuzzy degree match — "A.B." matches "Bachelor of Arts", etc.
      if (liDegree.includes(resumeDegree) || resumeDegree.includes(liDegree)) return true;
      // Try matching significant words
      const degreeWords = resumeDegree.split(/\s+/).filter(w => w.length > 2);
      if (degreeWords.some(w => liDegree.includes(w))) return true;
      return false; // school matches but degree doesn't
    }

    return true; // school matches, no degree info to compare
  }

  /** @deprecated — use _matchEducation for school+degree matching */
  _matchSchool(resumeSchool, linkedInAria) {
    const aria = linkedInAria.toLowerCase();
    const school = resumeSchool.toLowerCase();
    if (aria.includes(school)) return true;
    // Try without common prefixes
    const stripped = school.replace(/^(the|a|an)\s+/i, '');
    if (stripped !== school && aria.includes(stripped)) return true;
    const firstWord = school.split(' ')[0];
    if (firstWord.length > 3 && aria.includes(firstWord)) return true;
    return false;
  }

  async updateEducation(entries) {
    if (!entries.length) return;
    console.log(`  ▶ ${entries.length} education entries`);

    const existing = this.dryRun ? [] : await this._discoverEducation();

    for (const edu of entries) {
      const matchIdx = existing.findIndex(li => this._matchEducation(edu, li));
      const match = matchIdx >= 0 ? existing[matchIdx] : null;

      if (match) {
        existing.splice(matchIdx, 1);
        console.log(`    ✎ ${edu.school}`);
        if (this.dryRun) continue;
        try {
          await this._editEducation(match.href, edu);
        } catch (err) {
          console.error(`    ✗ Edit failed: ${err.message}`);
        }
      } else {
        console.log(`    + ${edu.school} (new)`);
        if (this.dryRun) continue;
        try {
          await this._addEducation(edu);
        } catch (err) {
          console.error(`    ✗ Add failed: ${err.message}`);
        }
      }
    }

    // Post-sync duplicate removal: any remaining LinkedIn entries whose
    // school+degree matches a resume entry are duplicates (not in source resume).
    // Delete them to make LinkedIn an exact mirror of the resume.
    for (const leftover of existing) {
      let matchFound = null;
      for (const edu of entries) {
        if (this._matchEducation(edu, leftover)) {
          matchFound = edu;
          break;
        }
      }
      if (matchFound) {
        try {
          await this._deleteEducation(leftover.href, matchFound);
        } catch (err) {
          console.error(`    ✗ Delete failed: ${err.message}`);
        }
      }
    }
  }

  async _editEducation(editUrl, edu) {
    await this.page.goto(editUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await delay(2000);

    const s = SELECTORS.education.elements;

    // School
    const schoolInput = await findFirst(this.page, s.schoolInput);
    if (schoolInput) {
      await schoolInput.locator.clear();
      await schoolInput.locator.fill(edu.school);
    }

    // Degree
    if (edu.degree) {
      const degreeInput = await findFirst(this.page, s.degreeInput);
      if (degreeInput) {
        await degreeInput.locator.clear();
        await degreeInput.locator.fill(edu.degree);
      }
    }

    // Field of study — always clear to prevent LinkedIn's typeahead
    // from accumulating duplicate values on repeated edits.
    const fieldInput = await findFirst(this.page, s.fieldInput);
    if (fieldInput) {
      await fieldInput.locator.clear();
      if (edu.fieldOfStudy) await fieldInput.locator.fill(edu.fieldOfStudy);
    }
    // (edu.degree already cleared+filled above if present)

    // Dismiss any typeahead dropdown before Save (e.g., degree autocomplete)
    await this.page.keyboard.press('Escape');
    await delay(300);

    await delay(500);
    await this._save();
    console.log(`    ✓ ${edu.school}`);
  }

  async _addEducation(edu) {
    await this.page.goto(SELECTORS.education.newUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await delay(2000);

    const s = SELECTORS.education.elements;

    const schoolInput = await findFirst(this.page, s.schoolInput);
    if (schoolInput) await schoolInput.locator.fill(edu.school);

    if (edu.degree) {
      const degreeInput = await findFirst(this.page, s.degreeInput);
      if (degreeInput) await degreeInput.locator.fill(edu.degree);
    }

    // Field of study — always clear to prevent typeahead accumulation
    const fieldInput = await findFirst(this.page, s.fieldInput);
    if (fieldInput) {
      await fieldInput.locator.clear();
      if (edu.fieldOfStudy) await fieldInput.locator.fill(edu.fieldOfStudy);
    }

    // Dismiss any typeahead dropdown before Save
    await this.page.keyboard.press('Escape');
    await delay(300);

    await delay(500);
    await this._save();
    console.log(`    ✓ ${edu.school}`);
  }

  async _deleteEducation(editUrl, edu) {
    console.log(`    🗑 Deleting: ${edu.school}`);
    if (this.dryRun) return;

    await this.page.goto(editUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await delay(2000);

    // LinkedIn places a "Delete" button/link on the education edit form
    const deleteBtn = await findFirst(this.page, [
      'button:has-text("Delete education")',
      'button:has-text("Delete")',
      'a:has-text("Delete")',
      '[aria-label*="Delete"]',
    ]);
    if (!deleteBtn) {
      console.log('      ⚠ Delete button not found — skipping');
      return;
    }

    await deleteBtn.locator.click();
    await delay(2000);

    // LinkedIn's confirmation dialog blocks all automation clicks on its
    // children via a transparent overlay. Bypass by removing the dialog,
    // then clicking the now-exposed Delete button underneath.
    await this.page.evaluate(() => {
      const dialog = document.querySelector('dialog[open]');
      if (dialog) dialog.remove();
    });
    await delay(500);

    // Click Delete again — this time it hits the underlying page element
    const confirmBtn = await findFirst(this.page, [
      'button:has-text("Delete")',
      'button:has-text("Delete education")',
    ]);
    if (confirmBtn) {
      await confirmBtn.locator.click();
      await delay(2000);
    }

    console.log(`    ✓ Deleted: ${edu.school}`);
  }

  async _deletePosition(editUrl, pos) {
    console.log(`    🗑 Deleting: ${pos.title} @ ${pos.company}`);
    if (this.dryRun) return;

    await this.page.goto(editUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await delay(2000);

    const deleteBtn = await findFirst(this.page, [
      'button:has-text("Delete")',
      'a:has-text("Delete")',
      '[aria-label*="Delete"]',
    ]);
    if (!deleteBtn) {
      console.log('      ⚠ Delete button not found — skipping');
      return;
    }

    await deleteBtn.locator.click();
    await delay(2000);

    // LinkedIn's confirmation dialog blocks automation. Remove it, then
    // click the now-exposed Delete button underneath.
    await this.page.evaluate(() => {
      const dialog = document.querySelector('dialog[open]');
      if (dialog) dialog.remove();
    });
    await delay(500);

    const confirmBtn = await findFirst(this.page, [
      'button:has-text("Delete")',
      'button:has-text("Confirm")',
    ]);
    if (confirmBtn) {
      await confirmBtn.locator.click();
      await delay(2000);
    }

    console.log(`    ✓ Deleted: ${pos.title} @ ${pos.company}`);
  }

  // ─── main entry ─────────────────────────────────────────────

  async sync(profile) {
    console.log('\n🔗 LinkedIn Profile Sync');
    console.log(this.dryRun ? '   (DRY RUN — no changes will be made)\n' : '\n');

    await this.launch();
    await this.ensureLoggedIn();

    // ─── validation phase ─────────────────────────────────────
    this.validation = await this.validateSelectors();

    const brokenSections = Object.entries(this.validation)
      .filter(([, r]) => r.status === 'broken')
      .map(([key]) => key);

    if (this.dryRun) {
      console.log('  (Dry run — skipping validation gate)\n');
    } else if (brokenSections.length > 0) {
      console.log(`⛔ ${brokenSections.length} section(s) have broken selectors:`);
      for (const key of brokenSections) console.log(`   - ${SELECTORS[key].name}`);
      console.log('   Skipping these. Screenshots in screenshots/\n');
    }

    const skip = new Set(brokenSections);

    if (!skip.has('headline')) await this.updateHeadline(profile.headline);
    else console.log('  ⊘ Headline: skipped (broken selectors)');

    if (!skip.has('about')) await this.updateAbout(profile.about);
    else console.log('  ⊘ About: skipped (broken selectors)');

    if (!skip.has('position')) await this.updatePositions(profile.positions);
    else console.log('  ⊘ Positions: skipped (broken selectors)');

    await this.updateSkills(profile.skills);

    if (!skip.has('education')) await this.updateEducation(profile.education);
    else console.log('  ⊘ Education: skipped (broken selectors)');

    console.log('\n✓ Sync complete.\n');
    if (this.dryRun) console.log('  This was a dry run. Run without --dry-run to apply changes.');
  }
}
