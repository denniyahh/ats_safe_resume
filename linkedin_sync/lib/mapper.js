/**
 * Map JSON Resume data to LinkedIn profile fields.
 *
 * LinkedIn profile sections:
 *   - headline: single-line job title / tagline
 *   - about: multi-paragraph summary (rich text)
 *   - positions: array of { title, company, description, startDate, endDate, location }
 *   - skills: array of skill strings (top 50 max on LinkedIn)
 *   - education: array of { school, degree, fieldOfStudy }
 */

/**
 * Build the LinkedIn headline from the resume label.
 * @param {object} jsonResume
 * @returns {string}
 */
export function mapHeadline(jsonResume) {
  return jsonResume.basics?.label || '';
}

/**
 * Build the About section from the resume summary.
 * @param {object} jsonResume
 * @returns {string}
 */
export function mapAbout(jsonResume) {
  return jsonResume.basics?.summary || '';
}

/**
 * Build positions array from JSON Resume work entries.
 * Each entry: { title, company, location, description, startDate, endDate }
 * @param {object} jsonResume
 * @returns {object[]}
 */
/**
 * Strip markdown links and formatting from text.
 * [text](url) → text, **bold** → bold, *italic* → italic
 */
function stripMarkdown(text) {
  return text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')  // [text](url) → text
    .replace(/\*\*([^*]+)\*\*/g, '$1')          // **bold** → bold
    .replace(/\*([^*]+)\*/g, '$1')              // *italic* → italic
    .replace(/__([^_]+)__/g, '$1')              // __bold__ → bold
    .replace(/_([^_]+)_/g, '$1');              // _italic_ → italic
}

export function mapPositions(jsonResume) {
  return (jsonResume.work || [])
    // Skip positions with no company name (e.g., "Earlier Experience" placeholder)
    .filter(entry => entry.name && entry.name !== 'Earlier Experience')
    .map(entry => ({
      title: stripMarkdown(entry.position || ''),
      company: stripMarkdown(entry.name || ''),
      location: stripMarkdown(entry.location || ''),
      description: stripMarkdown(buildDescription(entry)),
      startDate: parseLinkedInDate(entry.startDate),
      endDate: parseLinkedInDate(entry.endDate),
    }));
}

/**
 * Build the position description from summary + highlights.
 */
function buildDescription(entry) {
  const parts = [];
  if (entry.summary) parts.push(entry.summary);
  if (entry.highlights?.length) {
    parts.push(entry.highlights.map(h => `• ${h}`).join('\n'));
  }
  return parts.join('\n\n');
}

/**
 * Parse date strings into LinkedIn's expected format.
 * "2021-06-01" → { month: 6, year: 2021 }
 * null/undefined → null (present)
 * @param {string|null} dateStr
 * @returns {{ month: number, year: number }|null}
 */
function parseLinkedInDate(dateStr) {
  if (!dateStr) return null;
  // Try ISO: "2021-06-01"
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr);
  if (iso) {
    return { month: parseInt(iso[2], 10), year: parseInt(iso[1], 10) };
  }
  // Try "Jun 2021" format
  const months = {
    jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6,
    jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12,
  };
  const named = /^([A-Za-z]{3})\s+(\d{4})$/.exec(dateStr);
  if (named) {
    return { month: months[named[1].toLowerCase()], year: parseInt(named[2], 10) };
  }
  // Try just year
  const yearOnly = /^(\d{4})$/.exec(dateStr);
  if (yearOnly) return { year: parseInt(yearOnly[1], 10) };
  return null;
}

/**
 * Build skills list from JSON Resume skills.
 * Flattens all skill categories into a single array of keyword strings.
 * @param {object} jsonResume
 * @returns {string[]}
 */
export function mapSkills(jsonResume) {
  const skills = [];
  for (const cat of jsonResume.skills || []) {
    if (cat.keywords?.length) {
      skills.push(...cat.keywords.map(k => k.trim()).filter(Boolean));
    }
  }
  return [...new Set(skills)]; // deduplicate
}

/**
 * Build education entries.
 * @param {object} jsonResume
 * @returns {object[]}
 */
export function mapEducation(jsonResume) {
  return (jsonResume.education || []).map(entry => {
    const school = entry.institution || '';
    let degree = entry.studyType || '';
    let fieldOfStudy = entry.area || '';

    // If degree contains field-of-study (e.g. "A.B. Economics"), split it
    // so LinkedIn's typeahead doesn't auto-parse and cause accumulation.
    if (!fieldOfStudy && degree.includes(' ')) {
      const commonDegreePrefixes = /^(A\.B\.|B\.S\.|B\.A\.|M\.S\.|M\.A\.|M\.B\.A\.|Ph\.D\.|J\.D\.|M\.D\.|B\.Eng\.|M\.Eng\.|B\.Sc\.|M\.Sc\.|B\.Tech\.|M\.Tech\.)\s+/i;
      const match = degree.match(commonDegreePrefixes);
      if (match) {
        fieldOfStudy = degree.slice(match[0].length).trim();
        degree = match[1].trim();
      }
    }

    return { school, degree, fieldOfStudy };
  });
}

/**
 * Produce the full LinkedIn profile map.
 * @param {object} jsonResume
 * @returns {object}
 */
export function mapResumeToLinkedIn(jsonResume) {
  return {
    headline: mapHeadline(jsonResume),
    about: mapAbout(jsonResume),
    positions: mapPositions(jsonResume),
    skills: mapSkills(jsonResume),
    education: mapEducation(jsonResume),
  };
}
