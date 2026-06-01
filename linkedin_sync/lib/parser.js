/**
 * Spawns the ats_safe_resume Python parser to produce JSON Resume data.
 */
import { execFileSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '../..');

/**
 * Parse a markdown resume and return JSON Resume object.
 * @param {string} resumePath - Absolute path to resume.md
 * @returns {object} JSON Resume data
 */
export function parseResume(resumePath) {
  const script = `
import sys, json
from pathlib import Path
sys.path.insert(0, '${REPO_ROOT}/src')
from ats_safe_resume.parser import parse

md = Path('${resumePath}').read_text()
resume = parse(md)
data = resume.to_json_resume()
print(json.dumps(data, indent=2))
`;

  const raw = execFileSync('python3', ['-c', script], {
    encoding: 'utf-8',
    maxBuffer: 10 * 1024 * 1024,
  });

  return JSON.parse(raw);
}
