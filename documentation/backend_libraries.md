# Backend Libraries and Dependencies

## Core Framework

- **FastAPI** (>=0.104.0) - Web framework for building the API layer
- **Uvicorn** (>=0.24.0) - ASGI server used during development
- **Gunicorn** (>=21.2.0) - Production process manager
- **Pydantic** (>=2.5.0) - Data validation and schema modelling
- **Pydantic Settings** (>=2.1.0) - Environment-driven configuration with `SettingsConfigDict`

## Database

- **supabase-py** (>=2.20.0) - Official Supabase client for Postgres access
- **psycopg2-binary** (>=2.9.9) - PostgreSQL adapter (fallback / migrations)

## LLM and NLP

- **openai** (>=1.3.0) - Direct OpenAI API client (`openai.OpenAI`)
- **langgraph** (>=0.0.20) - State machine for orchestrating LLM workflows
- **langchain** (>=0.1.0) - Prompt utilities (legacy helpers retained for future use)
- **langchain-openai** (>=0.1.0) - Adapter used in legacy paths (kept for compatibility)
- **Jinja2** (>=3.1.0) - Template engine powering `PromptManager`
- **Langfuse** (>=2.57.0) - Observability hooks for LLM calls (optional)

## HTTP and Async

- **httpx** (>=0.25.0) - Async client used in API tests
- **aiofiles** (>=23.2.0) - Async file I/O helpers

## Validation and Security

- **python-multipart** (>=0.0.6) - Multipart/form-data parsing
- **python-jose[cryptography]** (>=3.3.0) - JWT handling
- **passlib[bcrypt]** (>=1.7.4) - Password hashing utilities
- **cryptography** (>=41.0.0) - Cryptographic primitives

## Monitoring and Logging

- **structlog** (>=23.2.0) - Structured logging
- **langfuse** (>=2.57.0) - LLM tracing (optional)

## Testing

- **pytest** (>=7.4.0) - Core test framework
- **pytest-asyncio** (>=0.21.0) - Async test support
- **pytest-mock** (>=3.12.0) - Mock helpers
- **factory-boy** (>=3.3.0) - Test data factories
- **httpx** (>=0.25.0) - Used for async API tests

## Development Tooling

- **black** (>=23.0.0) - Formatter
- **isort** (>=5.12.0) - Import sorter
- **flake8** (>=6.0.0) - Linting
- **mypy** (>=1.7.0) - Static typing

## Installation

From the backend directory:

```bash
pip install -r requirements.txt
```

The `requirements.txt` file already pins the versions listed above. Run `pip freeze > requirements.txt` if you upgrade packages and need to capture the full lock snapshot for deployment.
