# Backend Libraries and Dependencies

## Core Framework

- **FastAPI** (^0.104.1) - Modern, fast web framework for building APIs with Python 3.7+ based on standard Python type hints
- **Uvicorn** (^0.24.0) - ASGI server implementation for FastAPI
- **Pydantic** (^2.5.0) - Data validation and settings management using Python type annotations

## Database

- **supabase** (^2.3.0) - Official Supabase Python client for database operations
- **psycopg2-binary** (^2.9.9) - PostgreSQL adapter for Python (fallback for direct connections)

## LLM and NLP

- **openai** (^1.3.0) - OpenAI API client for GPT models
- **anthropic** (^0.7.0) - Anthropic API client for Claude models
- **langgraph** (^0.0.20) - LangGraph for multi-step LLM workflows and validation
- **langchain** (^0.1.0) - LangChain for LLM application development

## HTTP and Async

- **httpx** (^0.25.0) - Async HTTP client for API requests and testing
- **aiofiles** (^23.2.0) - Async file operations

## Validation and Security

- **python-multipart** (^0.0.6) - For handling multipart form data
- **python-jose[cryptography]** (^3.3.0) - JWT token handling
- **passlib[bcrypt]** (^1.7.4) - Password hashing utilities
- **cryptography** (^41.0.0) - Cryptographic recipes and primitives

## Environment and Configuration

- **python-dotenv** (^1.0.0) - Load environment variables from .env file
- **pydantic-settings** (^2.1.0) - Settings management using Pydantic models

## Monitoring and Observability

- **langfuse** (^2.0.0) - Langfuse client for LLM observability and tracing
- **structlog** (^23.2.0) - Structured logging for better observability

## Testing

- **pytest** (^7.4.0) - Testing framework
- **pytest-asyncio** (^0.21.0) - Async testing support for pytest
- **pytest-mock** (^3.12.0) - Mocking utilities for pytest
- **httpx** (^0.25.0) - For async HTTP testing
- **factory-boy** (^3.3.0) - Test data factory library

## Development Tools

- **black** (^23.0.0) - Code formatter
- **isort** (^5.12.0) - Import sorter
- **flake8** (^6.0.0) - Linting tool
- **mypy** (^1.7.0) - Static type checking

## Production

- **gunicorn** (^21.2.0) - WSGI HTTP Server for UNIX (for production deployment)
- **uvloop** (^0.19.0) - Fast event loop implementation (optional performance boost)

## Installation Command

```bash
pip install fastapi uvicorn pydantic supabase psycopg2-binary openai anthropic langgraph langchain httpx aiofiles python-multipart python-jose[cryptography] passlib[bcrypt] cryptography python-dotenv pydantic-settings langfuse structlog pytest pytest-asyncio pytest-mock factory-boy black isort flake8 mypy gunicorn uvloop
```

## Requirements File

Create a `requirements.txt` file in the backend directory with these dependencies for easier installation:

```bash
pip freeze > requirements.txt
```
