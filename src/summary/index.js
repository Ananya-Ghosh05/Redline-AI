/**
 * Summary module – builds a human-readable severity report
 * with location coordinates for dispatchers.
 */

/**
 * Build a call summary string.
 *
 * @param {object} data
 * @param {string} data.callId
 * @param {string} data.callerNumber
 * @param {string} data.transcript
 * @param {string|null} data.translation
 * @param {string} data.severity
 * @param {string} data.responder
 * @param {number} [data.latitude]
 * @param {number} [data.longitude]
 * @returns {string} formatted summary
 */
function buildSummary(data) {
  const lines = [
    `=== EMERGENCY CALL SUMMARY ===`,
    `Call ID      : ${data.callId}`,
    `Caller       : ${data.callerNumber}`,
    `Severity     : ${data.severity.toUpperCase()}`,
    `Responder    : ${data.responder.toUpperCase()}`,
  ];

  if (data.latitude != null && data.longitude != null) {
    lines.push(`Location     : ${data.latitude}, ${data.longitude}`);
    lines.push(
      `Map link     : https://maps.google.com/?q=${data.latitude},${data.longitude}`
    );
  }

  lines.push(``, `--- Transcript ---`);
  lines.push(data.transcript);

  if (data.translation) {
    lines.push(``, `--- Translation (EN) ---`);
    lines.push(data.translation);
  }

  lines.push(``, `==============================`);
  return lines.join("\n");
}

module.exports = { buildSummary };
