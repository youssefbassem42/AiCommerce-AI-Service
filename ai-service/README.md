# AI Commerce Platform — AI Service

Multi-provider AI orchestration service with LangGraph agents, RAG pipeline, and domain-driven design.

## Architecture

```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────┐
│   Client     │────▶│  FastAPI (uvicorn)   │────▶│   Domain     │
│ (JWT/ApiKey) │     │  + Middleware        │     │   (DDD)      │
└──────────────┘     └─────────────────────┘     └──────┬───────┘
                    │        │         │                │
              ┌─────┘  ┌────┴────┐  └─────┐     ┌──────┴───────┐
              │ Agents │Workflows│ Workers│     │Infrastructure│
              │LangGraph│LangGraph│ Celery │     │ MongoDB/Qdrant│
              └────────┘─────────┘────────┘     │ Redis/LLM    │
                                                 └──────────────┘
```

## Prerequisites

- Python 3.12+
- MongoDB 7+
- Redis 7+
- Qdrant (or use local mode)

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Run
make dev
```

## Docker Deployment

```bash
make docker-build
make docker-up
```

Service available at `https://aicommerce-ai-service-production.up.railway.app` (Railway).
Locally at `http://localhost:8000`. Health check: `GET /health/`.

## Project Structure

```
app/
├── agents/         # LangGraph agents (bundle, sales, support, etc.)
├── api/            # FastAPI route handlers
├── application/    # CQRS commands/queries/handlers
├── core/           # Config, settings, model registry
├── db/             # Database connections
├── domain/        # Domain entities, value objects, events
├── infrastructure/ # Providers, repositories, security, cache
├── middleware/     # Auth, logging, rate limit, audit
├── rag/           # RAG pipeline components
├── shared/        # Shared kernel (CQRS primitives, mediator)
├── utils/         # Helpers
├── workers/       # Celery tasks
└── workflows/     # LangGraph workflows
```

## Testing

```bash
make test          # All tests
make test-unit     # Unit tests only
make test-int      # Integration tests only
```

## API Keys

At least one AI provider key is required. Supported providers:
- OpenAI, Azure OpenAI, Gemini, Claude, DeepSeek, Mistral, OpenRouter, Ollama

## Environment Variables

See `.env.example` for all available variables.
