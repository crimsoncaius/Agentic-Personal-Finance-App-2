# Expense Tracker MVP - Backend

FastAPI backend for the personal finance application with natural language processing capabilities.

## Features

- **REST API Endpoints**: Create, read, and manage financial entries
- **Natural Language Processing**: Convert text to structured financial data (planned)
- **Database Integration**: Supabase PostgreSQL with connection management
- **Comprehensive Testing**: Unit, integration, and API tests
- **Data Validation**: Pydantic models with business rule validation
- **Error Handling**: Structured error responses with helpful messages

## API Endpoints

### Entries

- `POST /api/v1/entries/` - Create entry with structured data
- `POST /api/v1/entries/nlp` - Create entry from natural language (planned)
- `GET /api/v1/entries/` - Get entries with filtering and pagination

### Categories

- `GET /api/v1/categories/` - Get categories with optional type filtering

### Chat/NLP

- `POST /api/v1/chat/` - Natural language query processing (planned)

### Health & Documentation

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /docs` - Interactive API documentation (Swagger)
- `GET /redoc` - Alternative API documentation

## Quick Start

### Prerequisites

- Python 3.9+
- Supabase project with database set up
- Environment variables configured

### Installation

1. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment**:

   ```bash
   cp ../.env.example .env
   # Edit .env with your Supabase credentials
   ```

3. **Set up database**:

   ```bash
   # Run the database initialization in Supabase SQL Editor:
   # 1. backend/database/initialization/schema.sql
   # 2. backend/database/initialization/seed_categories.sql
   # 3. Validate: python database/initialization/test_tables.py
   ```

4. **Run the application**:

   ```bash
   python main.py
   # Or with uvicorn:
   uvicorn main:app --reload --port 8000
   ```

5. **Access the API**:
   - API: http://localhost:8000
   - Docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health

## Testing

### Run All Tests

```bash
python run_tests.py
```

### Run Specific Test Categories

```bash
# Unit tests only
python -m pytest tests/test_models.py tests/test_services.py tests/test_routes.py -v

# Integration tests (requires database)
python -m pytest tests/test_integration.py -v -m integration

# Skip integration tests
python -m pytest -m "not integration" -v
```

### Test Structure

- **`test_models.py`**: Pydantic model validation tests
- **`test_services.py`**: Service layer logic tests (mocked)
- **`test_routes.py`**: API endpoint tests (mocked)
- **`test_integration.py`**: Database integration tests

## Development

### Code Quality

```bash
# Format code
python -m black .
python -m isort .

# Lint code
python -m flake8 .
python -m mypy .

# Run all quality checks
python run_tests.py
```

### Project Structure

```
backend/
├── main.py                 # FastAPI application
├── models/                 # Pydantic models
│   └── schemas.py         # Request/response models
├── routes/                # API route handlers
│   ├── entries.py         # Entry endpoints
│   ├── categories.py      # Category endpoints
│   └── chat.py           # NLP/chat endpoints
├── services/              # Business logic
│   ├── entry_service.py   # Entry operations
│   └── category_service.py # Category operations
├── database/              # Database layer
│   ├── connection.py      # Database connection
│   └── initialization/    # Schema and seeding
├── tests/                 # Test suite
│   ├── test_models.py     # Model tests
│   ├── test_services.py   # Service tests
│   ├── test_routes.py     # Route tests
│   └── test_integration.py # Integration tests
└── requirements.txt       # Dependencies
```

## API Usage Examples

### Create Entry

```bash
curl -X POST "http://localhost:8000/api/v1/entries/" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 12.50,
    "direction": "expense",
    "entry_date": "2025-01-15",
    "description": "Coffee at Starbucks",
    "source": "manual"
  }'
```

### Get Entries

```bash
curl "http://localhost:8000/api/v1/entries/?direction=expense&limit=5"
```

### Get Categories

```bash
curl "http://localhost:8000/api/v1/categories/?type=expense"
```

## Configuration

### Environment Variables

```bash
# Supabase Configuration
SUPABASE_URL=your-supabase-project-url
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key

# Application Configuration
CORS_ORIGINS=http://localhost:3000,https://your-domain.com
RATE_LIMIT_PER_MINUTE=100
MAX_REQUEST_SIZE_MB=10

# LLM Configuration (for future NLP features)
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# Optional: Observability
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
LANGFUSE_HOST=https://cloud.langfuse.com
```

## Database Schema

The application uses two main tables:

### Categories

- Expense and income categories
- Hierarchical structure support
- System vs user-created categories

### Entries

- Financial transactions
- Amount stored in cents for precision
- NLP parsing confidence tracking
- Source tracking (manual vs NLP)

See `database/initialization/schema.sql` for complete schema definition.

## Error Handling

The API returns structured error responses:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Amount must be positive",
    "details": {
      "missing_fields": ["amount"],
      "suggestions": ["Try: 'spent $20 on coffee'"]
    }
  }
}
```

## Future Enhancements

- Natural language processing integration
- Real-time updates with WebSockets
- User authentication and multi-tenancy
- Receipt OCR and bank integrations
- Budget tracking and analytics
- Data export and reporting

## Contributing

1. Write tests first (TDD approach)
2. Ensure all tests pass
3. Run linting and formatting
4. Update documentation
5. Create pull request

## License

This project is part of the Expense Tracker MVP.
