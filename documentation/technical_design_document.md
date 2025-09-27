# Expense Tracker MVP — Technical Design (React + FastAPI + PostgreSQL)

## 1) Scope

### MVP Core Features (Focus Now)

- **Create**: Convert a natural‑language message into **one** expense/withdrawal **or** income/deposit entry and persist it.
- **Read**: Return **all entries (≤10 total)** filtered from cues in the user's query. Pagination structure included for future scaling but not needed for MVP.

### Explicit Non‑Goals for MVP

- Update, Delete
- Auth/session management
- Bank integrations, receipt OCR, spreadsheet import
- Multi‑currency accounting
- Full dashboards/analytics

(We will design the data model and APIs to be forward‑compatible.)

---

## 2) High‑Level Architecture

```
[React SPA]
  └─(HTTPS/JSON)→ [FastAPI service]
                      ├─(Supabase Client)→ [Supabase PostgreSQL]
                      └─(optional)→ [NLP parsing module]
```

- **Frontend (React):**

  - Styling: **Tailwind CSS** (utility-first)
  - Headless components & transitions: **Headless UI** (`Dialog`, `Combobox`, `Listbox`, `Tab.Group`, `Transition`)
  - Routing: React Router
  - Data fetching/cache: TanStack Query
  - Forms & validation: React Hook Form + Zod

- **Backend (FastAPI):**

  - Pydantic v2 for request/response models
  - Supabase Python client for database operations
  - Uvicorn/Gunicorn for serving
  - Built‑in OpenAPI docs

- **Database (Supabase PostgreSQL):**

  - Managed PostgreSQL with built-in auth, real-time, and API generation
  - Normalized schema with future‑proofing for categories and extensions (notes, merchant, accounts later)
  - Declarative schema management with auto-migration generation
  - Row Level Security ready for multi-tenant future

- **NLP Parsing (MVP):**

  - LLM prompt-based parsing with structured extraction of amount, direction, date, category, and description.
  - LangGraph workflow for multi-step validation and refinement.
  - Pluggable interface so we can swap in different LLM providers later.

---

## 3) Data Model

### 3.1 Entities

**`entry`** — one financial record

- `id` (UUID v4, PK)
- `amount_cents` (BIGINT, non‑negative) — store as integer for precision
- `direction` (ENUM: `expense`, `income`)
- `entry_date` (DATE)
- `category_id` (FK → `category.id`, nullable until classification succeeds)
- `description` (TEXT, optional) — freeform (e.g., “lunch at hawker center”)
- `created_at` (TIMESTAMPTZ, default now())
- `updated_at` (TIMESTAMPTZ, default now())
- `source` (ENUM: `manual`, `nlp`) — traceability
- `parse_confidence` (REAL, nullable) — 0..1 when parsed by NLP

**`category`** — classification

- `id` (UUID v4, PK)
- `name` (TEXT, unique) — e.g., Food, Transport, Rent, Income\:Salary
- `type` (ENUM: `expense`, `income`, `both`) — guardrails
- `parent_id` (FK → `category.id`, nullable) — future subcategories
- `is_system` (BOOL, default true) — protect base categories

**Notes**

- Currency: assume a **single default currency** for MVP; add `currency_code CHAR(3)` later if needed.
- Users: no auth in MVP; add `user_id` FK later for multi‑tenant.

### 3.2 SQL (initial migration)

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
  parse_confidence REAL CHECK (parse_confidence >= 0 AND parse_confidence <= 1),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_entry_date ON entry(entry_date);
CREATE INDEX idx_entry_direction ON entry(direction);
CREATE INDEX idx_entry_category ON entry(category_id);
CREATE INDEX idx_entry_created_at ON entry(created_at);
```

### 3.3 Seed Categories (Default Set)

**Expense Categories:**

- **Food & Dining (Expense)**: Restaurants, groceries, coffee, lunch, dinner, snacks
- **Transportation (Expense)**: Bus, MRT, taxi, Grab, fuel, parking, car maintenance
- **Housing (Expense)**: Rent, mortgage, utilities (electricity, water, gas), internet, maintenance
- **Shopping (Expense)**: Clothing, electronics, household items, personal care
- **Entertainment (Expense)**: Movies, games, subscriptions, hobbies, sports
- **Health & Fitness (Expense)**: Medical bills, pharmacy, gym, doctor visits
- **Education (Expense)**: Courses, books, school fees, training materials
- **Travel (Expense)**: Flights, hotels, vacation expenses, travel insurance
- **Insurance (Expense)**: Health, car, home, life insurance premiums
- **Miscellaneous (Expense)**: Default fallback category for uncategorized expenses

**Income Categories:**

- **Salary (Income)**: Regular employment income, wages, bonuses
- **Freelance (Income)**: Contract work, consulting, gig economy
- **Investment (Income)**: Dividends, interest, capital gains, rental income
- **Gifts (Income)**: Birthday money, wedding gifts, cash gifts
- **Refunds (Income)**: Purchase returns, overpayments, rebates
- **Other Income (Income)**: Default fallback category for uncategorized income

---

## 4) API Design (MVP)

### 4.1 Natural Language Query — `POST /api/v1/chat`

- **Single endpoint** that handles both reads and writes via LLM router
- **Enhanced security** with query validation and parameterized queries

#### Request

```json
{
  "text": "Spent $12.50 on laksa yesterday"
}
```

OR

```json
{
  "text": "Show me food expenses from last week"
}
```

### 4.2 Traditional REST Endpoints

#### Create Entry — `POST /api/v1/entries`

##### Request (Structured)

```json
{
  "amount": 12.5,
  "direction": "expense",
  "date": "2025-09-20",
  "category_id": "<uuid>",
  "description": "laksa lunch"
}
```

##### Request (Natural Language)

```json
{
  "text": "Spent $12.50 on laksa yesterday"
}
```

#### Read Entries — `GET /api/v1/entries`

- **Query params** (all optional):
  - `limit` (default 10, max 10), `offset` (default 0)
  - `date_from`, `date_to`
  - `direction` (`expense|income`)
  - `category_id`
  - `amount_min`, `amount_max`
  - `q` (text search on `description`)
  - `sort` (one of: `entry_date.desc` default, `created_at.desc`)

##### Response (200)

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "amount": 12.5,
      "direction": "expense",
      "date": "2025-01-15",
      "category": {
        "id": "550e8400-e29b-41d4-a716-446655440002",
        "name": "Food & Dining"
      },
      "description": "laksa lunch",
      "source": "nlp",
      "parse_confidence": 0.86,
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "page": { "limit": 10, "offset": 0, "total": 1 }
}
```

### 4.3 Query Endpoint Responses

#### Response (Write Operation - 201)

```json
{
  "operation": "write",
  "result": {
    "id": "<uuid>",
    "amount": 12.5,
    "direction": "expense",
    "date": "2025-09-19",
    "category": { "id": "<uuid>", "name": "Food" },
    "description": "laksa lunch",
    "source": "nlp",
    "parse_confidence": 0.86,
    "created_at": "2025-09-20T04:12:33Z"
  }
}
```

#### Response (Read Operation - 200)

```json
{
  "operation": "read",
  "result": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "amount": 12.5,
      "direction": "expense",
      "date": "2025-01-15",
      "category": {
        "id": "550e8400-e29b-41d4-a716-446655440002",
        "name": "Food & Dining"
      },
      "description": "laksa lunch",
      "source": "nlp",
      "parse_confidence": 0.86,
      "created_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

#### Errors (400)

```json
{
  "error": {
    "code": "parsing_failed",
    "message": "Could not determine the amount. Please specify a number.",
    "details": {
      "missing_fields": ["amount"],
      "suggestions": ["Try: 'spent $20 on coffee'"]
    }
  }
}
```

**Error Codes:**

- `missing_fields`: which fields are required but absent and not inferrable
- `ambiguous`: list of candidate parses; client can choose one
- `validation_error`: database constraint violations
- `parsing_failed`: LLM parsing errors with user-friendly messages

### 4.4 Categories — `GET /api/v1/categories`

- Return list for client pickers; support `type` filter (expense/income).

#### Query Params (optional)

- `type`: Filter by category type (`expense`, `income`)

#### Response (200)

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440002",
    "name": "Food & Dining",
    "type": "expense"
  },
  {
    "id": "550e8400-e29b-41d4-a716-446655440004",
    "name": "Salary",
    "type": "income"
  },
  {
    "id": "550e8400-e29b-41d4-a716-446655440005",
    "name": "Transportation",
    "type": "expense"
  },
  {
    "id": "550e8400-e29b-41d4-a716-446655440006",
    "name": "Investment",
    "type": "income"
  }
]
```

---

## 5) LLM Router & Processing Module (MVP)

**Goal:** Route natural language inputs to appropriate processing nodes (READ or WRITE) and execute the intended operation.

### 5.1 Router Strategy

- **LLM Router:** Simple system message that routes user input to READ or WRITE commands
- **Two Processing Nodes:** Read Node (SQL generation) and Write Node (structured parsing)
- **No memory/context:** Each query is processed independently without conversation history

### 5.2 Router System Message

```
You are a router for a personal finance app. Analyze the user input and respond with exactly one command:

COMMANDS:
- READ: For queries that want to view, list, show, or get existing entries
- WRITE: For inputs that want to create, add, spend, earn, or record new entries

Respond with only: READ or WRITE
```

### 5.3 Processing Flow

```
User Input → LLM Router → [READ | WRITE] → [Read Node | Write Node]
```

#### Read Node (Query Builder)

1. **LLM generates structured query parameters** based on natural language query
2. **Validate query parameters** against allowed operations and fields
3. **Execute parameterized query** using Supabase client methods
4. **Return results** to user

#### Write Node (Structured Parsing)

1. **LLM extracts structured data** from natural language
2. **Validate required fields** (amount, direction, date)
3. **Map category** to database category ID
4. **Insert entry** into database

### 5.4 Write Node Prompt Template

```
Parse this expense/income entry into structured data:

Text: "{user_input}"

Extract:
- amount: number (required)
- direction: "expense" or "income" (required)
- date: YYYY-MM-DD format (required)
- category: category name from this list: {category_list}
- description: brief description

Return JSON only, no explanation.
```

### 5.5 Read Node Prompt Template

```
Generate structured query parameters for this request:

User Query: "{user_input}"

Available filters: date_from, date_to, direction, category_id, amount_min, amount_max, q (text search), sort, limit, offset

Return JSON with query parameters only, no explanation.
Example: {"direction": "expense", "date_from": "2025-01-01", "limit": 10}
```

### 5.6 Error Handling

#### Parsing Errors

- If parsing fails → return 400 with `missing_fields` error
- If category not found → use default category based on direction
- If amount/date invalid → return 400 with validation error

#### Database Errors

- Connection failures → return 503 with `database_unavailable` error
- Constraint violations → return 400 with specific constraint error details
- Transaction rollback → return 500 with `internal_error`

#### Validation Errors

- Negative amounts → return 400 with `invalid_amount` error
- Future dates beyond reasonable limit → return 400 with `invalid_date` error
- Non-numeric amounts in text → return 400 with `unparseable_amount` error
- Invalid category type for direction → return 400 with `category_mismatch` error

#### Edge Cases

- Empty or whitespace-only input → return 400 with `empty_input` error
- Ambiguous currency symbols → return 400 with `ambiguous_currency` error
- Multiple amounts detected → return 400 with `multiple_amounts` error
- Unclear direction (income vs expense) → return 400 with `ambiguous_direction` error

### 5.7 Observability (Langfuse)

- **Trace each parsing workflow** with Langfuse for debugging and monitoring
- **Track LLM calls** and their performance metrics
- **Monitor parsing accuracy** and identify common failure patterns
- **Log user inputs** and parsed outputs for analysis
- **Set up alerts** for parsing failures or low confidence scores

---

## 6) Frontend UX (MVP)

### 6.1 Unified Chat Interface

- **Single chat input** at bottom: "Ask about your finances or add entries…"
- **Chat history** showing user queries and system responses
- **Direct processing** - backend routes to read/write and executes immediately
- **Natural responses** - show results or confirmations
- **Loading states** - show processing indicators during NLP parsing
- **Confidence scores** - display parsing confidence when available
- **Quick actions** - provide buttons for common operations

#### User Flow (Write):

1. User types: "spent $20 on coffee yesterday"
2. **Loading state**: Show "Processing your request..." with spinner
3. Router detects WRITE operation
4. Backend parses and saves entry
5. **Success response**: "✅ Added $20 expense to Food & Dining (Expense) category for coffee yesterday (confidence: 92%)"
6. **Quick actions**: Show "Add another expense" button
7. Entry appears in chat history with confidence indicator

#### User Flow (Read):

1. User types: "show me food expenses from last week"
2. **Loading state**: Show "Searching your entries..." with spinner
3. Router detects READ operation
4. Backend generates query parameters and executes
5. **Results display**: Formatted list with totals and category breakdown
6. **Quick actions**: Show "Export to CSV" or "Add filter" buttons
7. Results appear in chat history with summary statistics

#### User Flow (Error):

1. User types: "spent money on food" (missing amount)
2. **Loading state**: Show "Processing your request..."
3. Backend detects missing required field
4. **Error response**: "❌ Could not determine the amount. Please specify a number."
5. **Suggestions**: Show "Try: 'spent $20 on food'" with clickable suggestion
6. **Retry option**: Allow user to edit and resend

### 6.2 Frontend Component Specifications

#### ChatMessage Interface

```typescript
interface ChatMessage {
  id: string;
  type: "user" | "system" | "error" | "loading";
  content: string;
  timestamp: Date;
  confidence?: number;
  actions?: QuickAction[];
  metadata?: {
    operation?: "read" | "write";
    entryId?: string;
    totalAmount?: number;
    categoryBreakdown?: Record<string, number>;
  };
}

interface QuickAction {
  label: string;
  action: () => void;
  variant: "primary" | "secondary" | "danger";
}
```

#### Loading States

- **Processing**: Spinner with "Processing your request..."
- **Parsing**: "Understanding your message..." with progress bar
- **Saving**: "Saving entry..." with checkmark animation
- **Searching**: "Searching your entries..." with search icon

#### Error States

- **Parsing Error**: Red alert with suggestion buttons
- **Network Error**: Retry button with offline indicator
- **Validation Error**: Inline field highlighting with helpful messages
- **Server Error**: Generic error with "Try again" option

### 6.3 Natural Language Queries

- **Unified interface** handles both reads and writes
- **Examples**:
  - "spent $50 on groceries"
  - "show me all expenses this month"
  - "what did I spend on transport last week"
  - "add $100 income from freelance work"

## 7) Security Considerations

### 7.1 Input Validation

- **Natural Language Sanitization**: Strip potentially harmful characters from user input
- **Amount Validation**: Enforce reasonable limits (0 < amount < 1,000,000) to prevent overflow attacks
- **Date Validation**: Reject dates beyond reasonable bounds (e.g., > 10 years ago, > 1 year future)
- **Text Length Limits**: Limit description field to 500 characters to prevent DoS attacks

### 7.2 API Security

- **Rate Limiting**: Implement per-IP rate limiting (e.g., 100 requests/minute)
- **CORS Configuration**: Restrict origins to frontend domain only
- **Request Size Limits**: Limit request body size to prevent large payload attacks
- **Input Sanitization**: Validate and sanitize all JSON input fields

### 7.3 Database Security

- **SQL Injection Prevention**: Use parameterized queries exclusively
- **Row Level Security**: Implement RLS policies even for single-user MVP
- **Connection Security**: Use SSL/TLS for all database connections
- **Credential Management**: Store database credentials in environment variables

### 7.4 LLM Security

- **Prompt Injection Prevention**: Sanitize user input before sending to LLM
- **API Key Security**: Rotate LLM API keys regularly
- **Input Logging**: Log sanitized versions of user inputs for debugging
- **Output Validation**: Validate LLM responses before processing

### 7.5 Infrastructure Security

- **Environment Variables**: Never hardcode secrets in source code
- **HTTPS Only**: Enforce HTTPS for all API endpoints
- **Error Information**: Avoid exposing sensitive information in error messages
- **Logging**: Implement structured logging without sensitive data

---

## 8) Validation & Business Rules

- `amount` > 0 (allow 0 for refunds? MVP: require > 0)
- `date` must be ≤ today (future dates optional; MVP allow for planned income? default: allow)
- `direction` must match category type (expense categories for expenses, income categories for income).
- Limit read responses to ≤ 10 items regardless of `limit` param.

---

## 8) Implementation Details

### 8.1 FastAPI Models (Pydantic)

- `EntryCreateStructured`, `EntryCreateNL`, `EntryResponse`, `EntryListResponse`
- `ParseError` model with `code` = `missing_fields | ambiguous`

### 8.2 Supabase Integration

- Use Supabase Python client for database operations
- Pydantic models for request/response validation
- Direct SQL queries or Supabase client methods for data access

### 8.3 Schema Management

- Declarative schema files in SQL format (`backend/database/schema.sql`)
- Database initialization script (`backend/database/init_db_simple.py`) for setup validation
- Connection management via Supabase client (`backend/database/connection.py`)
- Seed data for initial categories (`backend/database/seed_categories.sql`)
- Manual setup via Supabase Studio SQL Editor for MVP
- Future: `supabase db diff` to generate migrations from schema changes
- Future: `supabase db push` to apply migrations across environments

### 8.4 Testing

#### Unit Tests

- **Parser Components**: Test individual LangGraph nodes and validation logic
- **Validators**: Test amount, date, and category validation functions
- **Business Logic**: Test entry creation and filtering logic
- **Error Handling**: Test all error scenarios and edge cases
- **Test Tools**: pytest for Python backend, Jest for React frontend
- **Mock Data**: Use factory_boy for Python, faker.js for JavaScript test data

#### API Tests

- **Happy Paths**: Test successful entry creation (both structured and NLP)
- **Error Scenarios**: Test all 400/500 error responses
- **Edge Cases**: Test ambiguous inputs, invalid data, and boundary conditions
- **Security**: Test CORS, rate limiting, and input validation
- **Test Tools**: pytest with httpx for async testing, Postman/Newman for collection testing
- **Mock LLM**: Use mock responses for consistent testing without API costs

#### Integration Tests

- **Database Operations**: Test create→read flow with Supabase
- **LLM Integration**: Test end-to-end NLP parsing with mock LLM responses
- **Category Mapping**: Test category resolution and default fallbacks
- **Data Consistency**: Verify data integrity across operations

#### End-to-End Tests

- **User Workflows**: Test complete user journeys (add expense, view entries)
- **Natural Language**: Test various NL input formats and edge cases
- **Filtering**: Test all query parameter combinations
- **Error Recovery**: Test user experience with parsing failures
- **Test Tools**: Playwright for cross-browser testing, Cypress for component testing
- **Test Data**: Use test database with seeded data for consistent results

#### Performance Tests

- **Response Times**: Verify <200ms for reads, <2s for NLP parsing
- **Load Testing**: Test with 10 concurrent users using k6 or Artillery
- **Memory Usage**: Monitor for memory leaks during parsing
- **Database Performance**: Test query performance with realistic data volumes
- **Test Tools**: k6 for load testing, pytest-benchmark for performance regression testing

#### NLP Edge Case Tests

- **Ambiguous Inputs**: "spent money on food" (no amount)
- **Multiple Amounts**: "spent $10 and $20 on lunch"
- **Currency Variations**: Test $, USD, dollars, cents
- **Date Variations**: "yesterday", "last week", "January 15th"
- **Category Variations**: "food", "lunch", "restaurant", "dining"

### 8.5 Observability

- **Request logging** (path, status, latency)
- **Parse outcomes histogram**; error counters by code
- **Langfuse integration** for LLM workflow tracing and monitoring
- **Performance metrics** for parsing accuracy and response times
- **Alerting** for parsing failures and system errors

### 8.6 Environment Configuration

#### Required Environment Variables

```bash
# Supabase Configuration
SUPABASE_URL=your-supabase-project-url
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key

# LLM Configuration
OPENAI_API_KEY=your-openai-api-key

# Application Configuration
CORS_ORIGINS=http://localhost:3000,https://your-domain.com
RATE_LIMIT_PER_MINUTE=100
MAX_REQUEST_SIZE_MB=10

# Optional: Langfuse for observability
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
LANGFUSE_HOST=https://cloud.langfuse.com
```

#### Development Setup

1. **Clone repository and install dependencies**

   ```bash
   git clone <repository-url>
   cd expense-tracker-mvp
   npm install  # Frontend
   pip install -r requirements.txt  # Backend
   ```

2. **Set up Supabase project**

   ```bash
   # Option A: Using Supabase CLI (future enhancement)
   npm install -g supabase
   supabase init
   supabase start
   supabase db push
   supabase db seed

   # Option B: Manual setup via Supabase Dashboard (current MVP approach)
   # 1. Create project at https://supabase.com
   # 2. Go to SQL Editor in Supabase Dashboard
   # 3. Run backend/database/schema.sql
   # 4. Run backend/database/seed_categories.sql
   # 5. Verify setup with: python backend/database/init_db_simple.py
   ```

3. **Configure environment**

   ```bash
   # Copy environment template
   cp .env.example .env

   # Edit .env with your values
   nano .env
   ```

4. **Start development servers**

   ```bash
   # Terminal 1: Backend
   cd backend
   uvicorn main:app --reload --port 8000

   # Terminal 2: Frontend
   cd frontend
   npm run dev
   ```

### 8.7 Database Seeding

#### Initial Categories Seeding Script

```sql
-- Insert expense categories
INSERT INTO category (id, name, type, is_system) VALUES
  (gen_random_uuid(), 'Food & Dining (Expense)', 'expense', true),
  (gen_random_uuid(), 'Transportation (Expense)', 'expense', true),
  (gen_random_uuid(), 'Housing (Expense)', 'expense', true),
  (gen_random_uuid(), 'Shopping (Expense)', 'expense', true),
  (gen_random_uuid(), 'Entertainment (Expense)', 'expense', true),
  (gen_random_uuid(), 'Health & Fitness (Expense)', 'expense', true),
  (gen_random_uuid(), 'Education (Expense)', 'expense', true),
  (gen_random_uuid(), 'Travel (Expense)', 'expense', true),
  (gen_random_uuid(), 'Insurance (Expense)', 'expense', true),
  (gen_random_uuid(), 'Miscellaneous (Expense)', 'expense', true);

-- Insert income categories
INSERT INTO category (id, name, type, is_system) VALUES
  (gen_random_uuid(), 'Salary (Income)', 'income', true),
  (gen_random_uuid(), 'Freelance (Income)', 'income', true),
  (gen_random_uuid(), 'Investment (Income)', 'income', true),
  (gen_random_uuid(), 'Gifts (Income)', 'income', true),
  (gen_random_uuid(), 'Refunds (Income)', 'income', true),
  (gen_random_uuid(), 'Other Income (Income)', 'income', true);
```

### 8.8 Deployment

- Docker images for frontend and API
- Supabase managed PostgreSQL with automatic backups
- Environment variables configured in deployment platform
- Optional: Supabase Edge Functions for serverless API endpoints

---

## 9) Example Flows

### 9.1 NL Create → Success

- Input: "spent \$8 on kopi yesterday"
- Parse → amount=8.00, direction=expense, date=(today-1), category=Food, description="kopi"
- Response 201 with `source=nlp`, `parse_confidence=0.82`

### 9.2 NL Create → Ambiguous Direction

- Input: "\$100 from refund on Monday"
- Parse → amount ok, date ok, direction unclear (`income` vs `expense(refund)`)
- API 400 `ambiguous` with options; client shows toggle; resend.

### 9.3 Read with Filters

- `GET /entries?date_from=2025-09-01&date_to=2025-09-21&direction=expense&limit=10`
- Returns first page and `total` for client paging.

---

## 10) Extensibility Hooks (Future Enhancements)

- **Authentication**: Leverage Supabase Auth for user management (built-in)
- **Multi-tenancy**: Add `user_id` and `account_id` tables with Row Level Security
- **Real-time**: Use Supabase real-time subscriptions for live updates
- **File Storage**: Supabase Storage for receipt images and OCR pipeline
- **Currency**: Add `currency_code` column; FX handling
- **Smart Features**: Add `rule` table for smart categorization
- **Budgeting**: Add `budget` and `alert` tables
- **Data Recovery**: Add soft‑delete (`deleted_at`) for recoverability
- **API Generation**: Leverage auto-generated REST/GraphQL APIs from schema
