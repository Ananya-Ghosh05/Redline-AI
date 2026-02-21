/**
 * Speech-to-Text transcription using Google Cloud Speech-to-Text.
 *
 * Falls back to a stub when credentials are not available (dev / test).
 */
const fs = require("fs");

let speechClient = null;
let clientInitFailed = false;

function hasCredentials() {
  const credFile = process.env.GOOGLE_APPLICATION_CREDENTIALS;
  if (credFile && fs.existsSync(credFile)) return true;
  if (process.env.GOOGLE_API_KEY) return true;
  if (process.env.GCLOUD_PROJECT || process.env.GOOGLE_CLOUD_PROJECT) return true;
  return false;
}

function getClient() {
  if (clientInitFailed) return null;
  if (!speechClient) {
    try {
      if (!hasCredentials()) {
        clientInitFailed = true;
        return null;
      }
      const speech = require("@google-cloud/speech");
      speechClient = new speech.SpeechClient();
    } catch {
      clientInitFailed = true;
      speechClient = null;
    }
  }
  return speechClient;
}

/**
 * Transcribe raw audio to text.
 *
 * @param {Buffer|string} audio – raw audio bytes or base64 string
 * @param {string} [languageHint="en-US"] – BCP-47 language code hint
 * @returns {{ text: string, languageCode: string }}
 */
async function transcribe(audio, languageHint = "en-US") {
  const client = getClient();

  if (!client) {
    // Stub for dev/test when Google credentials are absent
    return { text: String(audio), languageCode: languageHint.split("-")[0] };
  }

  const audioContent =
    audio instanceof Buffer ? audio.toString("base64") : audio;

  const [response] = await client.recognize({
    config: {
      encoding: "LINEAR16",
      sampleRateHertz: 8000,
      languageCode: languageHint,
      alternativeLanguageCodes: ["es", "fr", "zh", "ar", "hi"],
      enableAutomaticPunctuation: true,
    },
    audio: { content: audioContent },
  });

  const transcript = response.results
    .map((r) => r.alternatives[0].transcript)
    .join(" ");

  const detectedLanguage =
    response.results[0]?.languageCode || languageHint.split("-")[0];

  return { text: transcript, languageCode: detectedLanguage };
}

module.exports = { transcribe };
