/**
 * Routing module – determines which responder type should
 * handle the emergency based on transcript content.
 */

/** Keywords that map to each responder category. */
const RESPONDER_KEYWORDS = {
  fire: [
    "fire",
    "burning",
    "flames",
    "smoke",
    "gas leak",
    "explosion",
    "arson",
    "wildfire",
    "smoke alarm",
    "hazmat",
    "chemical spill",
  ],
  ambulance: [
    "ambulance",
    "medical",
    "heart attack",
    "cardiac",
    "stroke",
    "breathing",
    "choking",
    "bleeding",
    "injury",
    "injured",
    "unconscious",
    "unresponsive",
    "seizure",
    "overdose",
    "poison",
    "allergic",
    "pain",
    "broken",
    "fracture",
    "pregnant",
    "labor",
    "drowning",
    "chest pain",
    "not breathing",
    "dying",
    "hemorrhage",
  ],
  police: [
    "police",
    "robbery",
    "theft",
    "burglary",
    "assault",
    "weapon",
    "gun",
    "knife",
    "shooting",
    "stabbing",
    "fight",
    "domestic violence",
    "suspicious",
    "break-in",
    "hostage",
    "active shooter",
    "armed",
    "hit and run",
    "vandalism",
    "threat",
    "harassment",
    "missing person",
    "kidnapping",
  ],
};

/**
 * Determine the appropriate responder for the call.
 *
 * Priority: ambulance > fire > police > other
 *
 * @param {string} text – English transcript
 * @returns {"police"|"fire"|"ambulance"|"other"}
 */
function determineResponder(text) {
  if (!text) return "other";

  const lower = text.toLowerCase();

  // Tally matches per category
  const scores = { ambulance: 0, fire: 0, police: 0 };

  for (const [responder, keywords] of Object.entries(RESPONDER_KEYWORDS)) {
    for (const kw of keywords) {
      if (lower.includes(kw)) {
        scores[responder]++;
      }
    }
  }

  // Pick responder with the highest score; tie-break: ambulance > fire > police
  const sorted = Object.entries(scores).sort((a, b) => b[1] - a[1]);
  if (sorted[0][1] === 0) return "other";
  return sorted[0][0];
}

module.exports = { determineResponder, RESPONDER_KEYWORDS };
