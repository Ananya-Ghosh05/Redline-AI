/**
 * Real-time translation via Google Cloud Translation API.
 *
 * Falls back to a stub when credentials are not available (dev / test).
 */
const fs = require("fs");

let translateClient = null;
let clientInitFailed = false;

/**
 * Check whether Google Cloud credentials are available.
 */
function hasCredentials() {
  // Check for credentials file
  const credFile = process.env.GOOGLE_APPLICATION_CREDENTIALS;
  if (credFile && fs.existsSync(credFile)) return true;

  // Check for API key
  if (process.env.GOOGLE_API_KEY) return true;

  // Check for default credentials via metadata server (GCE/Cloud Run)
  if (process.env.GCLOUD_PROJECT || process.env.GOOGLE_CLOUD_PROJECT) return true;

  return false;
}

function getClient() {
  if (clientInitFailed) return null;
  if (!translateClient) {
    try {
      if (!hasCredentials()) {
        clientInitFailed = true;
        return null;
      }
      const { Translate } = require("@google-cloud/translate").v2;
      translateClient = new Translate();
    } catch {
      clientInitFailed = true;
      translateClient = null;
    }
  }
  return translateClient;
}

/**
 * Translate text from one language to another.
 *
 * @param {string} text – source text
 * @param {string} from – source language code (e.g. "es")
 * @param {string} to   – target language code (e.g. "en")
 * @returns {string} translated text
 */
async function translate(text, from, to) {
  if (from === to) return text;

  const client = getClient();

  if (!client) {
    // Stub: return original text prefixed with target language
    return `[translated:${to}] ${text}`;
  }

  try {
    const [translation] = await client.translate(text, { from, to });
    return translation;
  } catch {
    // Fallback when API credentials are not configured
    return `[translated:${to}] ${text}`;
  }
}

/**
 * Detect the language of the given text.
 *
 * @param {string} text
 * @returns {{ language: string, confidence: number }}
 */
async function detectLanguage(text) {
  const client = getClient();

  if (!client) {
    return { language: "en", confidence: 1.0 };
  }

  try {
    const [detection] = await client.detect(text);
    return {
      language: detection.language,
      confidence: detection.confidence,
    };
  } catch {
    return { language: "en", confidence: 1.0 };
  }
}

module.exports = { translate, detectLanguage };
