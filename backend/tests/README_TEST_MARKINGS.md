# Test Marking System

This document explains the improved test marking system used in this project to clearly indicate what dependencies are mocked vs real, and what type of testing is being performed.

## Overview

The previous marking system used broad categories like `mock` and `real` which didn't clearly indicate what specific components were being mocked. The new system uses granular markers that make it immediately clear what dependencies are real vs mocked.

## Markers

### Dependency Markers

These markers indicate which external dependencies are mocked vs real:

- **`db_mock`** - Database operations are mocked (no real database calls)
- **`db_real`** - Uses real database connections and operations
- **`llm_mock`** - LLM/OpenAI API calls are mocked
- **`llm_real`** - Uses real LLM/OpenAI API calls

### Test Type Markers

These markers indicate the scope and purpose of the tests:

- **`unit`** - Isolated unit tests (typically with mocked dependencies)
- **`integration`** - Tests that verify component interactions
- **`e2e`** - End-to-end tests with real dependencies

### Performance Markers

These markers help manage test execution time:

- **`fast`** - Quick tests for rapid feedback (typically < 1 second)
- **`slow`** - Slower tests (network calls, complex operations, > 5 seconds)

### Legacy Markers (for backward compatibility)

- **`mock`** - Legacy marker (use `db_mock + llm_mock` instead)
- **`real`** - Legacy marker (use `db_real + llm_real` instead)
- **`asyncio`** - Marks tests as async

## Common Marker Combinations

### Fast Unit Tests (Everything Mocked)

```python
pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
    pytest.mark.db_mock,
    pytest.mark.llm_mock,
]
```

**Use case**: Testing business logic without external dependencies

### Integration Tests (Real DB, Mocked LLM)

```python
pytestmark = [
    pytest.mark.integration,
    pytest.mark.db_real,
    pytest.mark.llm_mock,
]
```

**Use case**: Testing database operations and data flow without LLM costs

### LLM Integration Tests (Mocked DB, Real LLM)

```python
pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.db_mock,
    pytest.mark.llm_real,
]
```

**Use case**: Testing LLM parsing accuracy without database setup

### End-to-End Tests (Everything Real)

```python
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.slow,
    pytest.mark.db_real,
    pytest.mark.llm_real,
]
```

**Use case**: Full system testing with real dependencies

## Running Tests by Markers

### Run only fast tests

```bash
pytest -m "fast"
```

### Run only unit tests (everything mocked)

```bash
pytest -m "unit"
```

### Run integration tests with real database

```bash
pytest -m "integration and db_real"
```

### Run tests with real LLM (requires API key)

```bash
pytest -m "llm_real"
```

### Run tests without slow tests

```bash
pytest -m "not slow"
```

### Run everything except E2E tests

```bash
pytest -m "not e2e"
```

## Current Test File Structure

The test suite is organized with clean, consistent naming:

| File                      | Type        | DB   | LLM  | Purpose                       |
| ------------------------- | ----------- | ---- | ---- | ----------------------------- |
| `test_models.py`          | unit        | mock | mock | Model validation (fast)       |
| `test_services.py`        | integration | real | mock | Service layer with real DB    |
| `test_routes.py`          | integration | real | real | API routes with real DB + LLM |
| `test_nlp.py`             | unit        | mock | mock | NLP service unit tests (fast) |
| `test_nlp_integration.py` | integration | mock | real | NLP service with real LLM     |
| `test_nlp_e2e_mock.py`    | integration | mock | mock | NLP e2e tests (mocked)        |
| `test_nlp_e2e.py`         | e2e         | real | real | NLP e2e tests (real)          |
| `test_chat.py`            | unit        | mock | mock | Chat route unit tests (fast)  |

## File Examples

### Model Tests (`test_models.py`)

```python
pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
    pytest.mark.db_mock,  # No database operations in model tests
    pytest.mark.llm_mock,  # No LLM operations in model tests
]
```

### Service Tests (`test_services.py`)

```python
pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.db_real,  # Uses real database operations
    pytest.mark.llm_mock,  # No LLM operations in service tests
]
```

### Route Tests (`test_routes.py`)

```python
pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.db_real,  # Uses real database operations
    pytest.mark.llm_real,  # Uses real LLM/OpenAI API calls (for chat routes)
]
```

## Benefits

1. **Clear Dependencies**: Immediately know what's mocked vs real
2. **Better Test Selection**: Run specific types of tests based on what you want to test
3. **Cost Management**: Easily avoid expensive LLM tests during development
4. **Performance Control**: Run fast tests for quick feedback, slow tests when needed
5. **Debugging**: Quickly identify which tests use which dependencies

## Migration from Old Markers

### Before

```python
pytestmark = pytest.mark.mock  # Unclear what's mocked
pytestmark = pytest.mark.real  # Unclear what's real
```

### After

```python
pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
    pytest.mark.db_mock,  # Database is mocked
    pytest.mark.llm_mock,  # LLM is mocked
]
```

## Best Practices

1. **Always specify both dependency markers**: Use both `db_*` and `llm_*` markers
2. **Include test type**: Add `unit`, `integration`, or `e2e` marker
3. **Add performance marker**: Include `fast` or `slow` for execution time management
4. **Use comments**: Add inline comments explaining why specific markers are used
5. **Be specific**: Don't use legacy `mock`/`real` markers for new tests

## Environment Requirements

- **`db_real` tests**: Require database connection
- **`llm_real` tests**: Require `OPENAI_API_KEY` environment variable
- **`slow` tests**: May take several seconds and cost API credits

## Troubleshooting

### Tests skipping unexpectedly

- Check if required environment variables are set
- Verify database connection for `db_real` tests
- Ensure API keys are configured for `llm_real` tests

### Tests running slowly

- Use `pytest -m "fast"` to run only quick tests
- Use `pytest -m "not slow"` to exclude slow tests

### Too many dependencies

- Use `pytest -m "unit"` to run isolated tests only
- Use `pytest -m "integration and db_mock and llm_mock"` for fast integration tests
