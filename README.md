# Redline-AI

AI-powered IVR (Interactive Voice Response) system for first responders. Streamlines voice data input from emergency calls with real-time translation, severity analysis, responder routing, and full call history via PostgreSQL.

## Features

- **Voice Data Processing** – Transcribes incoming emergency calls using Google Cloud Speech-to-Text
- **Real-time Translation** – Translates non-English calls to English via Google Translate API
- **Severity Analysis** – Keyword-based voice analysis model that marks severity as `critical`, `high`, `medium`, or `low`
- **Responder Routing** – Automatically routes to the correct service (police, fire, ambulance) based on call content
- **Call Summary** – Generates a structured severity report with location coordinates and a Google Maps link
- **PostgreSQL Database** – Stores full call history with transcripts, translations, severity, responder type, GPS coordinates, and status
- **Twilio Integration** – Webhooks for incoming calls and recordings via Twilio IVR

## Architecture

```
Incoming Call (Twilio)
  │
  ▼
┌──────────────────────┐
│  IVR Module          │
│  - Greeting TwiML    │
│  - Audio capture     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Speech-to-Text      │
│  (Google Cloud)      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Translation         │
│  (Google Translate)  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐     ┌──────────────────────┐
│  Severity Analysis   │────▶│  Responder Routing   │
│  (Keyword Model)     │     │  (Police/Fire/Ambu.) │
└──────────┬───────────┘     └──────────┬───────────┘
           │                            │
           ▼                            ▼
┌──────────────────────────────────────────────────┐
│  Summary Generator                               │
│  - Severity report                               │
│  - Location coordinates + map link               │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  PostgreSQL DB  │
              │  (Call History) │
              └─────────────────┘
```

## Tech Stack

| Layer           | Technology                          |
|-----------------|-------------------------------------|
| Runtime         | Node.js                             |
| Web Framework   | Express 5                           |
| Database        | PostgreSQL (via `pg`)               |
| Speech-to-Text  | Google Cloud Speech-to-Text         |
| Translation     | Google Cloud Translation API (v2)   |
| Telephony       | Twilio Programmable Voice           |
| Testing         | Jest                                |

## Getting Started

### Prerequisites

- Node.js 18+
- PostgreSQL 14+
- Google Cloud project with Speech-to-Text and Translation APIs enabled
- Twilio account (for telephony)

### Installation

```bash
npm install
```

### Configuration

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

| Variable                       | Description                         |
|-------------------------------|-------------------------------------|
| `PORT`                        | Server port (default: 3000)         |
| `DATABASE_URL`                | PostgreSQL connection string        |
| `TWILIO_ACCOUNT_SID`          | Twilio Account SID                  |
| `TWILIO_AUTH_TOKEN`           | Twilio Auth Token                   |
| `TWILIO_PHONE_NUMBER`         | Your Twilio phone number            |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account JSON |
| `GOOGLE_PROJECT_ID`           | Google Cloud project ID             |

### Database Setup

Initialize the PostgreSQL `call_history` table:

```bash
npm run db:init
```

### Start the Server

```bash
npm start
```

### Run Tests

```bash
npm test
```

## API Endpoints

| Method  | Endpoint                      | Description                              |
|---------|-------------------------------|------------------------------------------|
| GET     | `/health`                     | Health check                             |
| POST    | `/api/calls/incoming`         | Twilio webhook – initial call greeting   |
| POST    | `/api/calls/handle-recording` | Twilio webhook – process recorded audio  |
| POST    | `/api/calls`                  | Submit a call for processing (REST)      |
| GET     | `/api/calls`                  | List calls (filter by severity/responder)|
| GET     | `/api/calls/:id`              | Get a single call record                 |
| PATCH   | `/api/calls/:id/status`       | Update call status                       |

## Database Schema

```sql
CREATE TABLE call_history (
  id            UUID PRIMARY KEY,
  caller_number VARCHAR(20)  NOT NULL,
  timestamp     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  transcript    TEXT         NOT NULL,
  language      VARCHAR(10),
  translation   TEXT,
  severity      VARCHAR(10)  NOT NULL,  -- low | medium | high | critical
  responder     VARCHAR(20)  NOT NULL,  -- police | fire | ambulance | other
  latitude      DOUBLE PRECISION,
  longitude     DOUBLE PRECISION,
  summary       TEXT         NOT NULL,
  status        VARCHAR(20)  NOT NULL DEFAULT 'pending',
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

## Project Structure

```
src/
├── config/          # Environment & configuration
├── db/              # PostgreSQL schema, queries & connection pool
├── ivr/             # IVR call processing & speech-to-text
├── translation/     # Google Translate API integration
├── analysis/        # Severity marking (voice/text analysis)
├── routing/         # Responder determination (fire/police/ambulance)
├── summary/         # Call summary & severity report builder
├── app.js           # Express routes
└── server.js        # Entry point
tests/               # Jest unit tests
```

## License

ISC