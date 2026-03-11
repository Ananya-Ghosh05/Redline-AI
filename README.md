# Redline AI

Redline AI is an open-source IVR (Interactive Voice Response) system for emergency dispatch. It processes incoming calls, transcribes audio using local speech recognition, classifies caller intent and emotional urgency using trained ML models, and routes calls to the appropriate emergency service. All call records are persisted for review and audit.

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Local speech-to-text** using OpenAI Whisper; no third-party STT API required
- **Intent classification** using a fine-tuned DistilBERT model exported to ONNX for CPU inference
- **Severity analysis** combining a keyword engine with emotion signals to assign a priority level (low, medium, high, critical)
- **Responder routing** that maps classified intent to the appropriate service (police, fire, ambulance)
- **Translation** of non-English transcripts to English before further processing
- **Real-time call events** delivered to connected clients over WebSocket
- **Operator dashboard** for monitoring active calls and dispatch status
- **Multi-tenant data isolation** so multiple dispatch centers can share one deployment
- **JWT-based authentication** with rate limiting and CORS enforcement
- **Prometheus metrics** exposed at `/metrics` for integration with standard monitoring stacks
- **Twilio webhook integration** for inbound calls and recordings
- **PostgreSQL persistence** for complete call history with transcripts, severity, GPS coordinates, and status

## Architecture

```
Incoming Call (Twilio)
        |
        v
  IVR Module (TwiML)
        |
        v
  Whisper STT (local)
        |
        v
  Translation (if non-English)
        |
        v
  Intent Classification (DistilBERT ONNX)
        |
        +---> Severity Engine (keyword + emotion CNN)
        |
        v
  Responder Routing (police / fire / ambulance)
        |
        v
  Call Record (PostgreSQL)
        |
        v
  WebSocket Broadcast --> Operator Dashboard
```

## Tech Stack

### Backend (production)

| Layer               | Technology                              |
|---------------------|-----------------------------------------|
| Language            | Python 3.11                             |
| Web framework       | FastAPI (async)                         |
| Database            | PostgreSQL via async SQLAlchemy         |
| Migrations          | Alembic                                 |
| Cache / pub-sub     | Redis                                   |
| Speech-to-text      | OpenAI Whisper (local, CPU)             |
| Intent model        | DistilBERT fine-tuned, ONNX runtime     |
| Severity model      | Keyword engine + emotion CNN            |
| Auth                | JWT (python-jose)                       |
| Rate limiting       | SlowAPI                                 |
| Observability       | structlog (JSON), Prometheus            |
| Telephony           | Twilio Programmable Voice               |
| Testing             | pytest, pytest-asyncio, httpx           |

### Node.js MVP (original prototype, `src/`)

| Layer               | Technology                              |
|---------------------|-----------------------------------------|
| Runtime             | Node.js 18                              |
| Web framework       | Express 5                               |
| Database            | PostgreSQL via `pg`                     |
| Speech-to-text      | Google Cloud Speech-to-Text             |
| Translation         | Google Cloud Translation API v2         |
| Telephony           | Twilio Programmable Voice               |
| Testing             | Jest                                    |

## Getting Started

### Option 1: Docker Compose (recommended)

Requires Docker and Docker Compose.

```bash
cp .env.example .env
# Edit .env with your credentials (see Configuration below)
docker compose up
```

This starts the FastAPI backend on port 8000, an ML inference service on port 8001, PostgreSQL on port 5432, and Redis on port 6379.

### Option 2: Manual setup (Python backend)

**Prerequisites**

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- ffmpeg (required by Whisper)

**Install dependencies**

```bash
cd backend
pip install -r requirements.txt
```

**Configure environment**

```bash
cp ../.env.example .env
# Edit .env with your credentials
```

**Run database migrations**

```bash
alembic upgrade head
```

**Start the server**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Option 3: Node.js MVP

**Prerequisites**

- Node.js 18+
- PostgreSQL 14+
- Google Cloud project with Speech-to-Text and Translation APIs enabled
- Twilio account

**Install and run**

```bash
npm install
npm run db:init
npm start
```

## Configuration

Copy `.env.example` to `.env` and set the following variables.

### Python backend

| Variable                | Description                                          |
|-------------------------|------------------------------------------------------|
| `SECRET_KEY`            | Secret used to sign JWT tokens                       |
| `APP_ENV`               | `development` or `production`                        |
| `POSTGRES_USER`         | PostgreSQL username                                  |
| `POSTGRES_PASSWORD`     | PostgreSQL password                                  |
| `POSTGRES_SERVER`       | PostgreSQL host                                      |
| `POSTGRES_PORT`         | PostgreSQL port (default: 5432)                      |
| `POSTGRES_DB`           | Database name                                        |
| `USE_SQLITE`            | Set `true` to use SQLite for local development       |
| `REDIS_URL`             | Redis connection string (default: redis://localhost:6379) |
| `WHISPER_MODEL_SIZE`    | Whisper model to load: tiny, base, small, medium, large |
| `ML_SERVICE_URL`        | URL of the ML inference sidecar (default: http://localhost:8001) |
| `ALLOWED_ORIGINS`       | Comma-separated list of allowed CORS origins         |
| `ENABLE_DOCS`           | Set `false` to disable Swagger/ReDoc in production   |
| `TWILIO_AUTH_TOKEN`     | Twilio auth token for webhook signature validation   |
| `GROQ_API_KEY`          | Optional: Groq API key for LLM-assisted summarization|

### Node.js MVP

| Variable                          | Description                              |
|-----------------------------------|------------------------------------------|
| `PORT`                            | Server port (default: 3000)              |
| `DATABASE_URL`                    | PostgreSQL connection string             |
| `TWILIO_ACCOUNT_SID`              | Twilio Account SID                       |
| `TWILIO_AUTH_TOKEN`               | Twilio Auth Token                        |
| `TWILIO_PHONE_NUMBER`             | Your Twilio phone number                 |
| `GOOGLE_APPLICATION_CREDENTIALS`  | Path to GCP service account JSON         |
| `GOOGLE_PROJECT_ID`               | Google Cloud project ID                  |

## API Reference

### Python backend (`/api/v1`)

All routes under `/api/v1` require a valid JWT in the `Authorization: Bearer` header.

| Method | Endpoint                              | Description                              |
|--------|---------------------------------------|------------------------------------------|
| GET    | `/health`                             | Service health check                     |
| POST   | `/api/v1/auth/login`                  | Obtain a JWT token                       |
| POST   | `/api/v1/calls/start`                 | Start a new call session                 |
| GET    | `/api/v1/calls/`                      | List calls for the current tenant        |
| GET    | `/api/v1/calls/{id}`                  | Get a single call record                 |
| POST   | `/api/v1/calls/{id}/transcript`       | Submit a transcript chunk for processing |
| GET    | `/api/v1/severity/`                   | List severity assessments                |
| POST   | `/emergency/incoming`                 | Twilio webhook for inbound calls         |
| GET    | `/ws/calls`                           | WebSocket stream of call events          |
| GET    | `/dashboard`                          | Operator dashboard (HTML)                |
| GET    | `/metrics`                            | Prometheus metrics                       |

### Node.js MVP (`src/`)

| Method | Endpoint                      | Description                              |
|--------|-------------------------------|------------------------------------------|
| GET    | `/health`                     | Service health check                     |
| POST   | `/api/calls/incoming`         | Twilio webhook for inbound calls         |
| POST   | `/api/calls/handle-recording` | Twilio webhook for completed recordings  |
| POST   | `/api/calls`                  | Submit a call for processing             |
| GET    | `/api/calls`                  | List calls (filter by severity/responder)|
| GET    | `/api/calls/:id`              | Get a single call record                 |
| PATCH  | `/api/calls/:id/status`       | Update call status                       |

## Project Structure

```
backend/                     # Python/FastAPI backend (production)
  app/
    api/v1/endpoints/        # Route handlers (auth, calls, severity, emergency)
    core/                    # Config, database, Redis, security, orchestrator
    dashboard/               # Jinja2 operator dashboard
    ml/                      # Model loaders (intent, emotion)
    models/                  # SQLAlchemy ORM models
    schemas/                 # Pydantic request/response schemas
    services/                # Business logic (call processing, dispatch, STT)
    websockets/              # WebSocket connection manager
    main.py                  # FastAPI app and lifespan setup
  ml_service/                # ML inference sidecar (ONNX)
  alembic/                   # Database migration scripts
  tests/                     # pytest test suite
  requirements.txt
  Dockerfile

ml/                          # Training assets and dataset builders
  intent_model/              # Fine-tuned DistilBERT ONNX model
  train_intent_model.py
  train_emotion_cnn_multidataset.py
  build_*.py                 # Dataset construction scripts

src/                         # Node.js MVP (original prototype)
  config/                    # Environment and configuration
  db/                        # PostgreSQL schema and query helpers
  ivr/                       # IVR flow and Google Cloud STT
  translation/               # Google Cloud Translation integration
  analysis/                  # Keyword-based severity classification
  routing/                   # Responder type determination
  summary/                   # Call summary builder
  app.js                     # Express routes
  server.js                  # Entry point
tests/                       # Jest unit tests for the Node.js MVP

docker-compose.yml
.env.example
```

## Contributing

Contributions are welcome. Please open an issue before submitting a pull request for significant changes. Ensure all existing tests pass before requesting a review.

- Python: `cd backend && pytest`
- Node.js: `npm test`

## License

ISC
