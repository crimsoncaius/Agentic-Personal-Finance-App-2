# NLP Service V3 - Quick Start Guide

## Overview

NLP Service V3 is powered by LangGraph's ReAct agent with three specialized tools for financial tracking.

## Basic Usage

### Import and Initialize

```python
from backend.services.nlp_service_v3 import NLPServiceV3

# Initialize service
nlp_service = NLPServiceV3()
```

### Process a Query

```python
result = await nlp_service.process_query(
    text="Show me my expenses from last month",
    user_id="user-uuid-here",
    session_id="session-uuid",  # Optional
    chat_id="chat-uuid"  # Optional, auto-generated if not provided
)
```

### Response Format

```python
{
    "operation": "read",  # or "write" or "unsure"
    "result": [
        {
            "id": "entry-uuid",
            "amount": 50.00,
            "description": "Groceries",
            "direction": "expense",
            "entry_date": "2024-01-15",
            "category": {"id": "cat-uuid", "name": "Food & Dining"}
        }
    ],
    "message": "I found 5 expenses from last month totaling $250.00...",
    "chat_id": "chat-uuid"
}
```

## Example Queries

### Reading Data (fetch_entries tool)

```python
# Recent expenses
result = await nlp_service.process_query(
    text="What are my recent expenses?",
    user_id=user_id
)

# Specific category
result = await nlp_service.process_query(
    text="How much did I spend on groceries this month?",
    user_id=user_id
)

# Date range
result = await nlp_service.process_query(
    text="Show me all my income from January 2024",
    user_id=user_id
)

# Amount filtering
result = await nlp_service.process_query(
    text="Find expenses over $100",
    user_id=user_id
)
```

### Creating Data (create_entry tool)

```python
# Create expense
result = await nlp_service.process_query(
    text="I spent $45.50 on groceries today",
    user_id=user_id
)

# Create income
result = await nlp_service.process_query(
    text="Add my $3000 salary from January 1st",
    user_id=user_id
)

# With category
result = await nlp_service.process_query(
    text="Record $25 for lunch at a restaurant on January 15th",
    user_id=user_id
)
```

### Updating Data (update_entry tool)

```python
# Update amount
result = await nlp_service.process_query(
    text="Change my last grocery expense to $50",
    user_id=user_id,
    chat_id=chat_id  # Important for context
)

# Update description
result = await nlp_service.process_query(
    text="Update the description of that entry to 'Weekly groceries'",
    user_id=user_id,
    chat_id=chat_id
)

# Update date
result = await nlp_service.process_query(
    text="Actually that expense was yesterday, not today",
    user_id=user_id,
    chat_id=chat_id
)
```

## Conversation Memory

The service maintains conversation context using Redis:

```python
# First message
result1 = await nlp_service.process_query(
    text="I spent $30 on lunch",
    user_id=user_id,
    chat_id="conversation-1"
)

# Follow-up (agent remembers context)
result2 = await nlp_service.process_query(
    text="Actually, make that $35",  # Agent knows to update the lunch entry
    user_id=user_id,
    chat_id="conversation-1"  # Same chat_id maintains context
)
```

## Integration with Routes

### FastAPI Route Example

```python
from fastapi import APIRouter, Depends
from backend.services.nlp_service_v3 import NLPServiceV3
from backend.middleware.auth import get_current_user

router = APIRouter()
nlp_service = NLPServiceV3()

@router.post("/chat")
async def process_chat(
    message: str,
    chat_id: str = None,
    current_user = Depends(get_current_user)
):
    result = await nlp_service.process_query(
        text=message,
        user_id=str(current_user.id),
        session_id=str(current_user.session_id),
        chat_id=chat_id
    )

    return result
```

## Tool Details

### fetch_entries

**Purpose**: Retrieve existing financial entries

**Parameters** (handled by agent):

- `query_spec_json`: JSON string with QuerySpec fields
- `user_id`: Automatically injected

**Example Tool Call** (by agent):

```json
{
  "select": ["*"],
  "from": "entry",
  "where": {
    "direction": "expense",
    "entry_date": { ">=": "2024-01-01", "<=": "2024-01-31" }
  },
  "order_by": [{ "entry_date": "desc" }],
  "limit": 10
}
```

### create_entry

**Purpose**: Create new income or expense entry

**Parameters** (handled by agent):

- `amount`: Float (dollars)
- `direction`: "income" or "expense"
- `description`: String
- `category`: Category name
- `entry_date`: "YYYY-MM-DD"
- `user_id`: Automatically injected

**Example Tool Call** (by agent):

```json
{
  "amount": 50.0,
  "direction": "expense",
  "description": "Groceries",
  "category": "Food & Dining",
  "entry_date": "2024-01-15"
}
```

### update_entry

**Purpose**: Update existing entry

**Parameters** (handled by agent):

- `entry_id`: UUID string
- `user_id`: Automatically injected
- Optional: `amount`, `direction`, `description`, `category`, `entry_date`

**Example Tool Call** (by agent):

```json
{
  "entry_id": "entry-uuid-here",
  "amount": 75.0,
  "description": "Updated description"
}
```

## Error Handling

The service handles errors gracefully:

```python
result = await nlp_service.process_query(
    text="Some ambiguous query",
    user_id=user_id
)

# If error occurs:
{
    "operation": "unsure",
    "result": [],
    "message": "I encountered an error processing your request: ...",
    "chat_id": "..."
}
```

## Testing

Run the test script:

```bash
cd backend
python test_nlp_v3_agent.py
```

Or test individual queries:

```python
import asyncio
from backend.services.nlp_service_v3 import NLPServiceV3

async def test():
    service = NLPServiceV3()
    result = await service.process_query(
        text="Show me my recent expenses",
        user_id="your-user-id-here"
    )
    print(result)

asyncio.run(test())
```

## Configuration

Required environment variables:

```bash
# OpenAI API
OPENAI_API_KEY=sk-...

# Redis (for conversation memory)
REDIS_URL=redis://localhost:6379
REDIS_DB=0

# Langfuse (for observability)
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

## Debugging

Enable verbose logging:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("nlp_service_v3")
```

View Langfuse traces:

- Go to Langfuse dashboard
- Filter by tag: "v3", "langgraph", "react_agent"
- View trace details, tool calls, and performance metrics

## Best Practices

1. **Always provide user_id**: Required for security and data isolation
2. **Use consistent chat_id**: For maintaining conversation context
3. **Handle all operation types**: read, write, and unsure
4. **Check result structure**: May be list or single item depending on operation
5. **Display message to user**: The `message` field contains user-friendly text

## Limitations

1. **10-row limit**: fetch_entries enforces maximum 10 results
2. **Tool calls required**: Agent must use tools; can't answer from memory alone
3. **Category matching**: Categories must exist in database
4. **Date format**: Must be YYYY-MM-DD format

## Support

For issues or questions:

1. Check the implementation docs: `NLP_V3_AGENT_IMPLEMENTATION.md`
2. Review test examples: `backend/test_nlp_v3_agent.py`
3. Check Langfuse traces for debugging
