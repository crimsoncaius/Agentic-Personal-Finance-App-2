# NLP Service V3 - LangGraph ReAct Agent Implementation

## Overview

NLP Service V3 has been rewritten to use LangGraph's prebuilt `create_react_agent` instead of a custom orchestration loop. This provides better reliability, built-in retry logic, and cleaner tool-based architecture.

## Key Changes

### 1. Tools Module (`backend/services/tools/__init__.py`)

Created three LangChain tools using the `@tool` decorator:

- **`fetch_entries`**: Retrieves financial entries using QuerySpec

  - Enforces 10-row limit
  - Automatically filters by user_id for security
  - Supports complex filtering, sorting, and pagination

- **`create_entry`**: Creates new income/expense entries

  - Validates amount, direction, and date format
  - Auto-resolves category names to IDs
  - Includes user_id for security

- **`update_entry`**: Updates existing entries
  - Verifies user_id ownership before updating
  - Only updates provided fields
  - Returns updated entry details

### 2. Agent Architecture

**Before (V3 Manual Loop)**:

```python
for _ in range(MAX_TURNS):
    prompt = _build_main_prompt(text, facts)
    response = llm.call(prompt)
    plan = parse_response(response)

    if action == "get":
        rows = _run_query_spec(plan["query_spec"])
        facts = _summarize_facts(facts, rows)
    elif action == "reply":
        return build_response(plan)
```

**After (V3 ReAct Agent)**:

```python
agent = create_react_agent(
    model=model,
    tools=[fetch_entries, create_entry, update_entry],
    prompt=system_prompt,
    checkpointer=checkpointer
)

result = agent.ainvoke({"messages": messages}, config=config)
response = _parse_agent_output(result)
```

### 3. Tool Context Injection

User ID is automatically injected into all tool calls without requiring the LLM to provide it:

```python
def create_tool_with_user_id(tool_func, user_id_value):
    """Create a new tool with user_id pre-filled"""
    func_with_user_id = partial(tool_func.func, user_id=user_id_value)
    # Remove user_id from schema since it's now pre-filled
    return StructuredTool(
        name=original_name,
        description=original_description,
        func=func_with_user_id,
        args_schema=new_schema_without_user_id
    )
```

### 4. Redis Conversation Memory

Integrated the same Redis memory pattern from V2:

```python
# Before agent invocation
conversation_history = await redis_service.get_conversation_history(chat_id)

# Include history in agent messages
messages = [{"role": msg.role, "content": msg.content} for msg in conversation_history]
messages.append({"role": "user", "content": text})

# After completion
await redis_service.store_message(chat_id, "user", text)
await redis_service.store_message(chat_id, "assistant", response_message)
```

### 5. Langfuse Observability

All agent operations are traced:

```python
async with self.langfuse.trace_operation(
    name="nlp_query_processing_v3",
    user_id=user_id,
    session_id=session_id,
    input_data={"text": text},
    tags=["nlp", "v3", "langgraph", "react_agent"]
) as trace_id:
    # Agent execution
    result_state = await agent.ainvoke({"messages": messages}, config=config)

    # Track metrics
    self.langfuse.track_performance_metrics_v2(
        operation="query_processing_v3",
        trace_id=trace_id,
        metrics={"total_duration": duration, ...}
    )
```

### 6. System Prompt

The agent receives a comprehensive system prompt explaining:

- Role as a financial assistant
- Available tools and when to use them
- Category list (dynamically injected)
- Current date context
- Guidelines for data handling
- Response expectations

Example excerpt:

```
You are a helpful financial assistant helping users track their income and expenses.

**Current Date:** 2024-01-15

**Available Categories:**
Food & Dining, Transportation, Shopping, Salary, ...

**Your Capabilities:**
1. Fetch Entries: Use the fetch_entries tool to retrieve existing financial records
2. Create Entry: Use the create_entry tool to add new transactions
3. Update Entry: Use the update_entry tool to modify existing transactions

**Important Guidelines:**
- Always use tools to fetch or create data - NEVER make up or hallucinate financial data
- When users ask about their finances, use fetch_entries to get real data
- For date queries like "last month", calculate the appropriate date range
```

### 7. Response Format

Output is parsed to maintain backward compatibility with the existing API:

```python
{
    "operation": "read" | "write" | "unsure",
    "result": [...],  # List of entries or created/updated entry
    "message": "Natural language response from agent",
    "chat_id": "unique-chat-identifier"
}
```

## Benefits

1. **Built-in Retry Logic**: LangGraph's create_react_agent automatically handles tool call failures and retries
2. **Cleaner Architecture**: Tool-based approach is more maintainable than custom loops
3. **Better Error Handling**: Framework-level error handling and validation
4. **Easier to Extend**: Adding new tools is straightforward
5. **Consistent Memory**: Redis integration maintains conversation context
6. **Full Observability**: Langfuse tracing for all operations

## Testing

Run the test script to verify functionality:

```bash
cd backend
python test_nlp_v3_agent.py
```

Tests include:

- Read queries (fetching entries)
- Write queries (creating entries)
- Update queries (modifying entries)
- Ambiguous queries (clarification handling)
- Conversation memory (context retention)

## Migration Notes

### From V2 to V3:

- API remains the same - no changes needed in calling code
- Same Redis memory integration
- Same Langfuse tracing
- Enhanced with update capability

### Key Differences:

| Feature        | V2 (LangGraph Custom)         | V3 (ReAct Agent)                 |
| -------------- | ----------------------------- | -------------------------------- |
| Architecture   | Custom workflow with nodes    | Prebuilt ReAct agent             |
| Tools          | Embedded in nodes             | Standalone @tool functions       |
| Retry Logic    | Manual                        | Built-in                         |
| Update Support | ❌                            | ✅                               |
| QuerySpec      | Custom execution              | Integrated in fetch_entries tool |
| Complexity     | Higher (custom orchestration) | Lower (prebuilt framework)       |

## Dependencies

All required packages are already in `requirements.txt`:

```
langgraph>=0.0.20
langchain>=0.1.0
langchain-openai>=0.1.0
langchain-core
redis>=5.0.0
```

## Configuration

Uses the same configuration as V2:

- OpenAI API key from `settings.openai_api_key`
- Redis connection from `settings.redis_url`
- Langfuse configuration from environment variables

## Future Enhancements

Potential improvements:

1. Add more specialized tools (e.g., budget tracking, spending analytics)
2. Implement custom checkpointer using Redis instead of MemorySaver
3. Add tool result validation
4. Implement streaming responses
5. Add multi-turn planning for complex queries
