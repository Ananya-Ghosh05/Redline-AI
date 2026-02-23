const { Pool } = require("pg");
const config = require("../config");

const pool = new Pool({
  connectionString: config.database.connectionString,
});

/**
 * SQL to create the call_history table for storing all IVR call records.
 * Includes location coordinates, severity, transcript, translation, and routing.
 */
const CREATE_TABLE_SQL = `
CREATE TABLE IF NOT EXISTS call_history (
  id            UUID PRIMARY KEY,
  caller_number VARCHAR(20)  NOT NULL,
  timestamp     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  transcript    TEXT         NOT NULL,
  language      VARCHAR(10),
  translation   TEXT,
  severity      VARCHAR(10)  NOT NULL CHECK (severity IN ('low','medium','high','critical')),
  responder     VARCHAR(20)  NOT NULL CHECK (responder IN ('police','fire','ambulance','other')),
  latitude      DOUBLE PRECISION,
  longitude     DOUBLE PRECISION,
  summary       TEXT         NOT NULL,
  status        VARCHAR(20)  NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','dispatched','resolved')),
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_call_history_severity  ON call_history (severity);
CREATE INDEX IF NOT EXISTS idx_call_history_responder ON call_history (responder);
CREATE INDEX IF NOT EXISTS idx_call_history_timestamp ON call_history (timestamp);
`;

async function initializeDatabase() {
  const client = await pool.connect();
  try {
    await client.query(CREATE_TABLE_SQL);
    return true;
  } finally {
    client.release();
  }
}

/**
 * Insert a new call record.
 * @param {object} call
 * @returns {object} inserted row
 */
async function insertCall(call) {
  const sql = `
    INSERT INTO call_history
      (id, caller_number, timestamp, transcript, language, translation,
       severity, responder, latitude, longitude, summary, status)
    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
    RETURNING *;
  `;
  const values = [
    call.id,
    call.callerNumber,
    call.timestamp || new Date(),
    call.transcript,
    call.language || null,
    call.translation || null,
    call.severity,
    call.responder,
    call.latitude || null,
    call.longitude || null,
    call.summary,
    call.status || "pending",
  ];
  const result = await pool.query(sql, values);
  return result.rows[0];
}

/**
 * Get a call record by ID.
 */
async function getCallById(id) {
  const result = await pool.query(
    "SELECT * FROM call_history WHERE id = $1",
    [id]
  );
  return result.rows[0] || null;
}

/**
 * List calls with optional filters.
 * @param {object} filters – { severity, responder, limit, offset }
 */
async function listCalls(filters = {}) {
  const conditions = [];
  const values = [];
  let idx = 1;

  if (filters.severity) {
    conditions.push(`severity = $${idx++}`);
    values.push(filters.severity);
  }
  if (filters.responder) {
    conditions.push(`responder = $${idx++}`);
    values.push(filters.responder);
  }

  const where = conditions.length
    ? `WHERE ${conditions.join(" AND ")}`
    : "";
  const limit = filters.limit || 50;
  const offset = filters.offset || 0;

  const sql = `SELECT * FROM call_history ${where}
               ORDER BY timestamp DESC LIMIT $${idx++} OFFSET $${idx++}`;
  values.push(limit, offset);

  const result = await pool.query(sql, values);
  return result.rows;
}

/**
 * Update the status of a call.
 */
async function updateCallStatus(id, status) {
  const result = await pool.query(
    "UPDATE call_history SET status = $1 WHERE id = $2 RETURNING *",
    [status, id]
  );
  return result.rows[0] || null;
}

module.exports = {
  pool,
  initializeDatabase,
  insertCall,
  getCallById,
  listCalls,
  updateCallStatus,
  CREATE_TABLE_SQL,
};
