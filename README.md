# Redline AI

## Project Overview
Redline AI is an Emergency Response Intelligence Platform that leverages artificial intelligence to process and analyze emergency calls in real-time. The system uses a multi-stage AI pipeline to transcribe audio, analyze emotions, apply reasoning, assess severity, perform safety checks, and generate comprehensive dispatch reports to help emergency responders make faster, more informed decisions.

## Features
- **Speech-to-Text (STT)**: Converts emergency call audio to accurate transcripts
- **Emotion Analysis**: Detects and analyzes emotional states from caller transcripts to assess urgency
- **AI-Powered Reasoning**: Applies intelligent reasoning to understand the context and nature of emergencies
- **Severity Assessment**: Automatically evaluates emergency severity levels to prioritize responses
- **Safety Validation**: Performs safety checks and validations on extracted information
- **Automated Dispatch**: Generates detailed dispatch reports with actionable intelligence for first responders
- **Plugin Architecture**: Extensible system supporting custom agents and processing stages
- **Real-time Processing**: Asynchronous pipeline for fast emergency call processing
- **Health Monitoring**: Built-in health checks and status monitoring for all pipeline stages

## Installation
To install Redline AI, follow these steps:
1. Clone the repository:
   ```bash
   git clone https://github.com/Ananya-Ghosh05/Redline-AI.git
   ```
2. Navigate to the project directory:
   ```bash
   cd Redline-AI
   ```
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
After installation, you can start the Redline AI server by running:
```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```
Access the API documentation at `http://localhost:8000/docs`.

### Using Docker
Alternatively, you can run Redline AI using Docker:
```bash
# Build the Docker image
docker build -t redline-ai .

# Run the container
docker run -p 8000:8000 redline-ai
```

Or use Docker Compose:
```bash
docker-compose up
```

### API Endpoints
- `GET /` - Root endpoint with platform information
- `GET /health` - Health check endpoint showing pipeline status
- `POST /process-emergency` - Process emergency call audio file and generate dispatch report

## Architecture
Redline AI uses a modular pipeline architecture with six stages:

1. **STT (Speech-to-Text)**: Transcribes audio to text
   - Input: Raw audio bytes from emergency calls
   - Output: `Transcript` object with text and metadata
   - Converts spoken emergency calls into processable text

2. **Emotion Analysis**: Analyzes emotional content
   - Input: `Transcript` object
   - Output: `EmotionAnalysis` object with emotion scores and detected states
   - Evaluates caller's emotional state to assess urgency and stress levels

3. **Reasoning**: Applies contextual understanding
   - Input: `EmotionAnalysis` object
   - Output: `ReasoningOutput` object with extracted key information
   - Identifies critical details like location, emergency type, and involved parties

4. **Severity Assessment**: Evaluates emergency priority
   - Input: `ReasoningOutput` object
   - Output: `SeverityAssessment` object with priority level and risk factors
   - Determines urgency level for proper resource allocation

5. **Safety Validation**: Performs safety checks
   - Input: `SeverityAssessment` object
   - Output: `SafetyOutput` object with validated information
   - Ensures data quality and flags potential safety concerns

6. **Dispatch**: Generates actionable reports
   - Input: `SafetyOutput` object
   - Output: `DispatchReport` object with comprehensive emergency details
   - Creates formatted dispatch reports for first responders

Each stage is implemented as an independent agent that can be extended or replaced through the plugin system. Agents communicate through typed Pydantic models ensuring data validation at each step.

## Contribution Guidelines
We welcome contributions from the community! Here's how you can contribute:
1. Fork the repository and create your branch:
   ```bash
   git checkout -b feature/YourFeature
   ```
2. Make your changes and commit them:
   ```bash
   git commit -m 'Add a new feature'
   ```
3. Push to your branch:
   ```bash
   git push origin feature/YourFeature
   ```
4. Open a pull request.

## Technology Stack
- **Python 3.11+**: Core language
- **FastAPI**: Web framework for the API
- **Pydantic**: Data validation and serialization
- **Redis**: In-memory data store for caching and session management
- **PostgreSQL**: Database for persistent storage
- **SQLAlchemy**: ORM for database interactions
- **Uvicorn**: ASGI server

## Requirements
### Runtime Requirements
- **Python 3.11 or higher**: Required for core functionality
- **Redis server** (optional for development): Used for caching and session management
  - Recommended version: 5.0.1 or higher
  - Development: The system can run without Redis for testing
- **PostgreSQL database** (optional for development): Used for persistent storage in production
  - Recommended version: 12.0 or higher
  - Development: Not required for basic testing

### Development Requirements
- All dependencies listed in `requirements.txt` or `pyproject.toml`
- For the mock implementations included in the repository, no external AI service credentials are needed
- Production deployments may require API keys for:
  - Speech-to-Text services (if not using mock implementation)
  - AI/ML inference services for emotion and reasoning stages

### Optional
- Docker and Docker Compose for containerized deployment
- Environment variables for configuration (see docker-compose.yml for examples)

## License
This project is part of the emergency response technology initiative.