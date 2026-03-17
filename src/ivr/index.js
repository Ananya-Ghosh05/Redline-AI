/**
 * IVR module – handles incoming voice calls via Twilio,
 * streams audio for speech-to-text transcription, and
 * orchestrates the full pipeline (translate → analyse → route → summarise → store).
 */
const { v4: uuidv4 } = require("uuid");
const speechToText = require("./speechToText");
const translationService = require("../translation");
const voiceAnalysis = require("../analysis");
const routingService = require("../routing");
const summaryService = require("../summary");
const db = require("../db");

/**
 * Process an incoming call through the full IVR pipeline.
 *
 * @param {object} callInput
 * @param {string} callInput.callerNumber – caller's phone number
 * @param {Buffer|string} callInput.audio – raw audio data or base64 string
 * @param {number} [callInput.latitude]
 * @param {number} [callInput.longitude]
 * @param {string} [callInput.languageHint] – BCP-47 hint, e.g. "es"
 * @returns {object} full call record
 */
async function processCall(callInput) {
  const callId = uuidv4();

  // 1. Transcribe voice data to text
  const transcription = await speechToText.transcribe(
    callInput.audio,
    callInput.languageHint
  );

  // 2. Translate to English if necessary
  let translation = null;
  let detectedLanguage = transcription.languageCode || "en";
  if (detectedLanguage !== "en") {
    translation = await translationService.translate(
      transcription.text,
      detectedLanguage,
      "en"
    );
  }

  const englishText = translation || transcription.text;

  // 3. Analyse severity from the transcript
  const severity = voiceAnalysis.analyseSeverity(englishText);

  // 4. Route to the correct responder
  const responder = routingService.determineResponder(englishText);

  // 5. Build a summary with severity report and location
  const summary = summaryService.buildSummary({
    callId,
    callerNumber: callInput.callerNumber,
    transcript: transcription.text,
    translation,
    severity,
    responder,
    latitude: callInput.latitude,
    longitude: callInput.longitude,
  });

  // 6. Store in PostgreSQL
  const record = await db.insertCall({
    id: callId,
    callerNumber: callInput.callerNumber,
    transcript: transcription.text,
    language: detectedLanguage,
    translation,
    severity,
    responder,
    latitude: callInput.latitude,
    longitude: callInput.longitude,
    summary,
  });

  return record;
}

/**
 * Generate TwiML for the initial IVR greeting and recording prompt.
 * @returns {string} TwiML XML
 */
function buildGreetingTwiml(baseUrl) {
  return `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice">You have reached the emergency response system. Please describe your emergency after the tone.</Say>
  <Record maxLength="120" action="${baseUrl}/api/calls/handle-recording" transcribe="false" />
  <Say voice="alice">We did not receive a recording. Please call again.</Say>
</Response>`;
}

module.exports = {
  processCall,
  buildGreetingTwiml,
};
