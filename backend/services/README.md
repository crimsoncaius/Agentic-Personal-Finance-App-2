# NLP Service

This directory contains the LangGraph-based NLP service for processing natural language queries in the Expense Tracker MVP.

## Overview

The NLP service uses LangGraph to create a workflow that routes natural language inputs to appropriate processing nodes (READ or WRITE) and executes the intended operation.

## Architecture

```
User Input → Router Node → [Read Node | Write Node] → Database
```

### Components

1. **Router Node**: Analyzes user input and determines if it's a READ or WRITE operation
2. **Read Node**: Converts natural language queries to structured database queries
3. **Write Node**: Extracts structured data from natural language and creates database entries

## Files

- `nlp_service.py`: Main NLP service implementation with LangGraph workflow
- `README.md`: This documentation file

## Usage

```python
from services.nlp_service import NLPService

# Initialize service
nlp_service = NLPService(openai_api_key="your-api-key")

# Process a query
result = await nlp_service.process_query("spent $20 on coffee")
```

## Features

- **Natural Language Processing**: Converts natural language to structured data
- **Router Logic**: Automatically determines read vs write operations
- **Category Fallback**: Uses default categories when LLM suggests unknown ones
- **Error Handling**: Comprehensive error handling for all failure scenarios
- **Date Awareness**: LLM is aware of current date for relative date parsing
- **Database Integration**: Seamlessly integrates with Supabase PostgreSQL

## Error Types

The service handles these error types:

- `missing_fields`: Required fields that can't be extracted
- `ambiguous`: Multiple possible interpretations
- `validation_error`: Database constraint violations
- `parsing_failed`: LLM parsing errors

## Testing

Run the tests using:

```bash
# Run all NLP tests
python run_nlp_tests.py

# Run specific test suites
pytest tests/test_nlp_service.py -v
pytest tests/test_nlp_integration.py -v
pytest tests/test_e2e_chat.py -v
```

## Configuration

The service requires the following environment variables:

- `OPENAI_API_KEY`: OpenAI API key for LLM processing
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_KEY`: Supabase anon key
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key (optional)

## Dependencies

- `langgraph`: For workflow orchestration
- `langchain-openai`: For OpenAI integration
- `supabase`: For database operations
- `pydantic`: For data validation
