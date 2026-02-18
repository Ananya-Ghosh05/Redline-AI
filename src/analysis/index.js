/**
 * Voice / text analysis module for severity marking.
 *
 * Uses keyword-based heuristics to classify the severity of an
 * emergency call. In production this can be swapped for an ML model.
 */

/** Keywords mapped to severity weight (higher = more severe). */
const SEVERITY_KEYWORDS = {
  critical: [
    "dying",
    "not breathing",
    "heart attack",
    "cardiac arrest",
    "stroke",
    "unconscious",
    "unresponsive",
    "gunshot",
    "stabbing",
    "explosion",
    "bomb",
    "collapsed building",
    "mass casualty",
    "active shooter",
    "hostage",
    "drowning",
    "choking",
    "severe bleeding",
    "hemorrhage",
    "trapped",
  ],
  high: [
    "fire",
    "burning",
    "flames",
    "smoke",
    "assault",
    "weapon",
    "knife",
    "gun",
    "robbery",
    "crash",
    "collision",
    "hit and run",
    "broken bone",
    "fracture",
    "seizure",
    "overdose",
    "poison",
    "chest pain",
    "difficulty breathing",
    "armed",
    "domestic violence",
  ],
  medium: [
    "accident",
    "injury",
    "bleeding",
    "pain",
    "fall",
    "fell",
    "dizzy",
    "faint",
    "theft",
    "burglary",
    "suspicious",
    "fight",
    "altercation",
    "minor fire",
    "smoke alarm",
    "gas leak",
    "flood",
    "stuck",
  ],
  low: [
    "noise complaint",
    "parking",
    "lost",
    "found",
    "non-emergency",
    "information",
    "follow up",
    "report",
    "minor",
    "cat",
    "pet",
    "lockout",
  ],
};

/**
 * Analyse the transcript text and return a severity level.
 *
 * @param {string} text – English transcript
 * @returns {"critical"|"high"|"medium"|"low"} severity level
 */
function analyseSeverity(text) {
  if (!text) return "low";

  const lower = text.toLowerCase();

  // Check from most severe to least; return first match
  for (const level of ["critical", "high", "medium", "low"]) {
    for (const keyword of SEVERITY_KEYWORDS[level]) {
      if (lower.includes(keyword)) {
        return level;
      }
    }
  }

  // Default to medium when we cannot determine severity
  return "medium";
}

module.exports = { analyseSeverity, SEVERITY_KEYWORDS };
