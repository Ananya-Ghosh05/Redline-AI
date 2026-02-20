# Redline AI

A production-grade, modular, agentic AI system for emergency response intelligence.

## Architecture

Redline AI follows a clean architecture with dependency injection and SOLID principles. The system processes emergency calls through a pipeline of specialized agents:

1. **STT (Speech-to-Text)**: Converts audio to text
2. **Emotion Analysis**: Analyzes emotional content
3. **Reasoning**: Applies contextual reasoning
4. **Severity Assessment**: Deterministically scores emergency severity
5. **Safety Checks**: Validates response safety
6. **Dispatch**: Generates dispatch recommendations

## Features

- **Modular Design**: Pluggable AI components
- **Pydantic Validation**: Structured data with schema validation
- **Deterministic Logic**: Separate decision logic from LLM reasoning
- **Memory Management**: Redis for short-term, PostgreSQL for long-term storage
- **Docker Ready**: Containerized deployment
- **Async Processing**: High-performance async processing
- **Comprehensive Testing**: Unit tests with pytest

## Quick Start

### Using Docker Compose

```bash
# Clone the repository
git clone <repository-url>
cd redline-ai

# Start all services
docker-compose up --build

# The API will be available at http://localhost:8000
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis and PostgreSQL (or use docker-compose for just the databases)
docker-compose up redis postgres

# Run the application
uvicorn api.main:app --reload

# Run tests
pytest
```

## API Usage

### Process Emergency Call

```bash
curl -X POST "http://localhost:8000/process-emergency" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@emergency_call.wav"
```

### Health Check

```bash
curl http://localhost:8000/health
```

## Project Structure

```
redline-ai/
├── agents/                 # Agent implementations
│   ├── base.py            # Base agent classes
│   ├── stt/
│   ├── emotion/
│   ├── reasoning/
│   ├── severity/
│   ├── safety/
│   └── dispatch/
├── plugins/               # Plugin system
│   ├── base.py           # Base plugin classes
│   ├── registry.py       # Plugin registry
│   └── [component]/      # Component plugins
├── core/                  # Core system components
│   ├── orchestrator.py   # Main orchestrator
│   ├── memory/           # Memory management
│   └── schemas/          # Pydantic schemas
├── api/                   # FastAPI application
├── tests/                 # Unit tests
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── pyproject.toml
```

## Development

### Adding New Agents

1. Create agent class inheriting from `BaseAgent`
2. Implement `process()`, `get_input_schema()`, `get_output_schema()`
3. Create corresponding plugin
4. Register in orchestrator

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_agents.py

# Run with coverage
pytest --cov=agents --cov=core
```

## Configuration

Environment variables:

- `REDIS_URL`: Redis connection URL (default: redis://localhost:6379)
- `POSTGRES_URL`: PostgreSQL connection URL

## License

[License information]