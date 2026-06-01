#!/usr/bin/env node
/**
 * LinkedIn Sync — Sync ats_safe_resume markdown resume to LinkedIn.
 *
 * Usage:
 *   node index.js [--resume path/to/resume.md] [--dry-run]
 *
 * Default resume path: ../../my_resume/resume.md (relative to this script)
 */
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { parseResume } from './lib/parser.js';
import { mapResumeToLinkedIn } from './lib/mapper.js';
import { LinkedInUpdater } from './lib/linkedin.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DEFAULT_RESUME = resolve(__dirname, '../../my_resume/resume.md');

// ─── CLI ──────────────────────────────────────────────────────

const { values } = parseArgs({
  options: {
    resume: { type: 'string', default: DEFAULT_RESUME },
    'dry-run': { type: 'boolean', default: false },
  },
});

const resumePath = resolve(values.resume);
const dryRun = values['dry-run'];

// ─── main ─────────────────────────────────────────────────────

async function main() {
  console.log(`📄 Resume: ${resumePath}`);

  // Parse
  console.log('⏳ Parsing resume...');
  const jsonResume = parseResume(resumePath);

  // Map
  const profile = mapResumeToLinkedIn(jsonResume);

  // Print what would sync
  console.log('\n📋 Profile Map:');
  console.log(`  Headline:  "${profile.headline}"`);
  console.log(`  About:     "${profile.about.slice(0, 80)}..."`);
  console.log(`  Positions: ${profile.positions.length}`);
  profile.positions.forEach(p =>
    console.log(`    - ${p.title} @ ${p.company} (${p.startDate?.year || '?'} – ${p.endDate?.year || 'Present'})`)
  );
  console.log(`  Skills:    ${profile.skills.length}`);
  console.log(`  Education: ${profile.education.length}`);

  // Sync
  const updater = new LinkedInUpdater({ dryRun });
  try {
    await updater.sync(profile);
  } finally {
    await updater.close();
  }
}

main().catch(err => {
  console.error(`\n💥 Fatal: ${err.message}`);
  process.exit(1);
});
