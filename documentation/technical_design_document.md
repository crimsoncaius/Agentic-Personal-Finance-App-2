# Expense Tracker MVP - Technical Design (React + FastAPI + PostgreSQL)

## 1. Scope

### MVP Core Features

- **Create**: Convert a single natural language message into exactly one expense (withdrawal) or income (deposit) entry and persist it.
- **Read**: Return a list of entries filtered by cues in the query (limit 10 for the MVP). Pagination metadata is prepared for future work but not required yet.

### Explicit Non-Goals (MVP)

- Update or delete flows
- Authentication/session management
- Bank integrations, receipt OCR, spreadsheet import
- Multi-currency accounting
- Data-rich dashboards or analytics

---

## 2. High-Level Architecture

```
[React SPA]
    |
    v (HTTPS / JSON)
[FastAPI Service]
    |
    v (Supabase client)
[Supabase PostgreSQL]
    |
    v (LLM integration)
[NLP Service powered by OpenAI + LangGraph]
```

- **Frontend (React)**
  - Tailwind CSS for styling
  - Headless UI components for modals, pickers, and transitions
  - React Router for client routing
  - TanStack Query for data fetching/caching
  - React Hook Form + Zod for form handling and validation

- **Backend (FastAPI)**
  - FastAPI application served by Uvicorn (development) or Gunicorn (production)
  - Pydantic v2 for schemas and validation
  - Supabase Python client for database access
  - Pydantic Settings for configuration management
  - OpenAPI/Swagger UI exposed automatically

- **Database (Supabase PostgreSQL)**
  - Normalised schema centred on `entry` and `category`
  - Ready for future Row Level Security and multi-tenant extensions
  - SQL migrations managed inside the repository

- **NLP Service**
  - `NLPService` orchestrates a LangGraph `StateGraph`
  - Uses the direct `openai.OpenAI` client (model `gpt-4.1-nano`)
  - Prompts are generated from Jinja2 templates via `PromptManager`
  - Four nodes: router, read, write, unsure
  - Responses are enriched with conversational summaries via `_call_llm_for_response`

---

## 3. Data Model

### 3.1 Entities

**`entry`** - a financial transaction

- `id` (UUID primary key)
- `amount_cents` (BIGINT, stored as integer for precision)
- `direction` (ENUM: `expense`, `income`)
- `entry_date` (DATE)
- `category_id` (UUID, nullable, FK to `category.id`)
- `description` (TEXT, optional)
- `source` (ENUM: `manual`, `nlp`)
- `parse_confidence` (REAL, optional)
- `created_at` / `updated_at` (TIMESTAMPTZ)

**`category`** - categorisation metadata

- `id` (UUID primary key)
- `name` (TEXT, unique)
- `type` (ENUM: `expense`, `income`)
- `parent_id` (UUID, nullable self-reference)
- `is_system` (BOOLEAN, default `TRUE`)
- `created_at` / `updated_at` (TIMESTAMPTZ)

**Notes**

- Single currency assumption for MVP. Add `currency_code` later if needed.
- No `user_id` yet. Leave room for multi-tenant support.

### 3.2 Schema Snippet

```sql
CREATE TYPE entry_direction AS ENUM ('expense', 'income');
CREATE TYPE source_type AS ENUM ('manual', 'nlp');
CREATE TYPE category_kind AS ENUM ('expense', 'income');

CREATE TABLE category (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  type category_kind NOT NULL,
  parent_id UUID REFERENCES category(id),
  is_system BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE entry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  amount_cents BIGINT NOT NULL CHECK (amount_cents >= 0),
  direction entry_direction NOT NULL,
  entry_date DATE NOT NULL,
  category_id UUID REFERENCES category(id),
  description TEXT,
  source source_type NOT NULL DEFAULT 'manual',
  parse_confidence REAL CHECK (parse_confidence BETWEEN 0 AND 1),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 3.3 Default Categories

Seed expense categories: Food & Dining, Transportation, Housing, Shopping, Entertainment, Health & Fitness, Education, Travel, Insurance, Miscellaneous.

Seed income categories: Salary, Freelance, Investment, Gifts, Refunds, Other Income.

---

## 4. API Surface

### 4.1 Natural Language Endpoint - `POST /api/v1/chat`

Single entry point for both read and write intents.

**Request**

```json
{
  "text": "Show me food expenses from last week"
}
```

**Successful response (read)**

```json
{
  "operation": "read",
  "result": [
    {
      "id": "...",
      "amount": 12.5,
      "direction": "expense",
      "entry_date": "2025-01-15",
      "description": "laksa",
      "source": "nlp",
      "parse_confidence": 0.9,
      "created_at": "2025-01-15T10:30:00Z",
      "category": {
        "id": "...",
        "name": "Food & Dining (Expense)",
        "type": "expense"
      }
    }
  ],
  "message": "Here are the expenses that match your request."
}
```

**Successful response (write)**

```json
{
  "operation": "write",
  "result": {
    "id": "...",
    "amount": 20.0,
    "direction": "expense",
    "entry_date": "2025-01-15",
    "description": "coffee",
    "source": "nlp",
    "parse_confidence": 0.8,
    "created_at": "2025-01-15T10:00:00Z",
    "category": {
      "id": "...",
      "name": "Food & Dining (Expense)"
    }
  },
  "message": "Entry created successfully."
}
```

**Ambiguous response**

```json
{
  "operation": "unsure",
  "result": [],
  "message": "I'm not sure what you want to do. Could you clarify?"
}
```

The API returns `ParseError` objects (Pydantic models) when validation fails. Ambiguous results are surfaced as successful responses with an `unsure` operation so the UI can prompt for clarification without treating it as a hard error.

### 4.2 Structured REST Endpoints

- `POST /api/v1/entries` - create an entry with explicit fields
- `GET /api/v1/entries` - filter entries by date range, direction, category, amount range, free-text search (limit 10, offset based pagination)
- `GET /api/v1/categories` - list categories, optional `type` filter

---

## 5. NLP Service Implementation

### 5.1 Core Components

- `NLPService` lives in `backend/services/nlp_service.py`
- Depends on:
  - `openai.OpenAI` client (configured via `OPENAI_API_KEY`)
  - `PromptManager` for Jinja2 prompt templates (router, read, write, response, unsure)
  - `LangGraph StateGraph` to orchestrate node execution
  - Supabase database connection (`db_connection`)
  - Pydantic models in `backend/models/schemas.py`

### 5.2 Workflow Nodes

1. **Router Node**
   - Generates a router prompt and calls OpenAI.
   - Normalises output to `read`, `write`, or `unsure`.
   - On failure, attaches a `ParseError(code="parsing_failed")` to the state.

2. **Read Node**
   - Fetches categories (cached on first call).
   - Builds a read prompt with category context and current date.
   - Parses LLM JSON into `QueryParams`.
   - Executes `_execute_read_query` with validated filters.
   - Calls `_call_llm_for_response` to generate a friendly summary string.
   - Returns `result` list and `message` in state.
   - On JSON/validation errors, returns `ParseError(code="parsing_failed")`.

3. **Write Node**
   - Fetches categories and builds a write prompt.
   - Parses JSON into `ParsedData` (including ISO date conversion).
   - Calls `_create_entry`, which maps categories and assigns a default parse confidence of 0.8.
   - Generates a user-facing confirmation message via `_call_llm_for_response`.
   - On missing fields, returns `ParseError(code="missing_fields")` with suggestions.

4. **Unsure Node**
   - Crafts safe fallback guidance with template-generated suggestions.
   - Returns `ParseError(code="ambiguous")` plus a message from `_call_llm_for_response`.

### 5.3 Category Handling

- `_get_categories` caches Supabase results in `_categories_cache`.
- On Supabase failure, falls back to default expense/income categories generated locally.

### 5.4 Error Handling

- Ambiguous or validation failures are encapsulated in `ParseError` objects.
- `process_query` catches unhandled exceptions and returns `ParseError(code="parsing_failed")` with rephrase suggestions.
- Ambiguous router outcomes propagate as `unsure` operations instead of raising errors.

### 5.5 Prompt Strategy

Prompts live under `backend/templates/` and are rendered by `PromptManager`. The templates include:

- `router_prompt.j2`
- `read_prompt.j2`
- `write_prompt.j2`
- `read_response.j2`
- `write_response.j2`
- `unsure_response.j2`

This keeps system instructions centralised and testable.

---

## 6. Configuration

- `backend/config/settings.py` defines `Settings(BaseSettings)` with `model_config = SettingsConfigDict(...)`.
- Required environment variables:
  - `SUPABASE_URL`
  - `SUPABASE_KEY`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `OPENAI_API_KEY`
  - Optional Langfuse keys for observability
- `.env` is loaded automatically by Pydantic Settings.

---

## 7. Testing Strategy

### 7.1 Unit Tests (`backend/tests/unit/test_nlp.py`)

- Mock the OpenAI client, Supabase connection, and PromptManager.
- Assert router/read/write/unsure nodes produce correct operations, results, and messages.
- Ensure `_call_llm_for_response` outputs propagate into final responses.
- Cover ambiguous workflow branch (`test_process_query_handles_ambiguous_error`).

### 7.2 Integration Tests with Mocks (`backend/tests/integration/test_nlp_e2e_mock.py`)

- Patch external dependencies identically to the unit suite.
- Exercise end-to-end flows via `process_query` for read/write/ambiguous scenarios.
- Verify message strings alongside result payloads.

### 7.3 API Tests (`backend/tests/api/test_chat.py`)

- Use FastAPI TestClient / httpx to hit `/api/v1/chat`.
- Inject a mocked `NLPService` and assert HTTP responses propagate `operation`, `result`, and `message`.
- Check error responses preserve `ParseError` fields.

### 7.4 Additional Coverage

- Database tests validate category fallbacks and entry creation paths.
- Concurrent query behaviour is exercised with `asyncio.gather` in both service and API tests.

---

## 8. Observability & Operations

- Logging via `structlog` (structured JSON-ready logs).
- Langfuse integration hooks available for tracing LLM interactions (optional).
- Suggested metrics: request latency, parse success rate, error counts by code.
- Alerts should trigger on sustained parsing failures and database errors.

### Environment Setup

```bash
# Clone and install
git clone <repo>
cd Agentic-Personal-Finance-App-2
pip install -r backend/requirements.txt
npm install  # if frontend lives in repo

# Configure environment
cp .env.example .env
# edit values for Supabase + OpenAI

# Start backend
cd backend
uvicorn main:app --reload
```

---

## 9. Example Flows

### 9.1 Create via NLP

1. User: "spent $8 on kopi yesterday"
2. Router -> write node -> entry created with default confidence 0.8
3. Response message: "Entry created successfully." with entry payload.

### 9.2 Ambiguous Query

1. User: "refund 100"
2. Router returns `unsure`.
3. Unsure node responds with clarification suggestions and a friendly message.

### 9.3 Filtered Read

1. User: "show transport expenses from last week"
2. Read node produces Supabase filters and returns matching entries plus summary message.

---

## 10. Future Enhancements

- Authentication via Supabase Auth with Row Level Security
- Multi-tenant data partitioning (`user_id` on `entry`/`category`)
- Budgeting and alerting modules
- Receipt OCR and attachment storage (Supabase Storage)
- Additional LLM providers via PromptManager (Anthropic, Vertex)
- Rule-based categorisation to complement LLM parsing
- Soft deletes and audit logging for compliance
