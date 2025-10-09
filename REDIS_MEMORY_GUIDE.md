# Redis Conversation Memory - Implementation Guide

## Overview

The NLP chat service now supports conversation memory using Redis, allowing the LLM to understand context across multiple messages within a chat conversation. Users can reference previous messages using phrases like "the same day", "that category", "also add", etc.

## Architecture

### Key Components

1. **RedisService** (`backend/services/redis_service.py`)

   - Manages Redis connections and operations
   - Stores/retrieves conversation history using sorted sets
   - Handles TTL management for auto-expiry

2. **ChatMessage Model** (`backend/models/schemas.py`)

   - Stores individual messages with role, content, and timestamp
   - Used for both user and assistant messages

3. **NLPServiceV2** (`backend/services/nlp_service_v2.py`)

   - Retrieves conversation history before processing
   - Passes history to LLM for context
   - Stores new messages after successful processing

4. **API Routes** (`backend/routes/chat.py`)
   - POST `/api/v1/chat` - Send chat message with optional chat_id
   - GET `/api/v1/chat/{chat_id}/history` - Retrieve conversation history
   - DELETE `/api/v1/chat/{chat_id}` - Clear conversation

## Setup

### Local Development

1. **Start Redis using Docker Compose:**

   ```bash
   docker-compose up -d
   ```

2. **Verify Redis is running:**

   ```bash
   docker ps | grep redis
   ```

3. **Install Python dependencies:**

   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. **Start the backend:**
   ```bash
   python main.py
   ```

### Railway Production Deployment

1. **Add Redis Plugin:**

   - Go to your Railway project dashboard
   - Click "New" → "Database" → "Add Redis"
   - Railway will automatically inject `REDIS_URL` environment variable

2. **Deploy your backend:**
   - Railway will automatically use the `REDIS_URL` for the Redis connection
   - No additional configuration needed

## Usage

### Example: Multi-turn Conversation

**User Message 1:**

```json
POST /api/v1/chat
{
  "text": "I spent $100 on car maintenance yesterday"
}
```

**Response 1:**

```json
{
  "operation": "write",
  "result": { ... },
  "message": "I've added your $100 expense for car maintenance.",
  "chat_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**User Message 2 (using the same chat_id):**

```json
POST /api/v1/chat
{
  "text": "also add motorcycle maintenance for $150 on the same day",
  "chat_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response 2:**

```json
{
  "operation": "write",
  "result": { ... },
  "message": "I've added your $150 expense for motorcycle maintenance on the same day (yesterday).",
  "chat_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

The LLM understands "the same day" refers to "yesterday" from the first message!

### Retrieve Conversation History

```bash
GET /api/v1/chat/550e8400-e29b-41d4-a716-446655440000/history
```

**Response:**

```json
{
  "chat_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    {
      "role": "user",
      "content": "I spent $100 on car maintenance yesterday",
      "timestamp": 1696789012.345
    },
    {
      "role": "assistant",
      "content": "I've added your $100 expense for car maintenance.",
      "timestamp": 1696789013.456
    },
    {
      "role": "user",
      "content": "also add motorcycle maintenance for $150 on the same day",
      "timestamp": 1696789020.123
    },
    {
      "role": "assistant",
      "content": "I've added your $150 expense for motorcycle maintenance on the same day (yesterday).",
      "timestamp": 1696789021.234
    }
  ],
  "count": 4
}
```

### Clear Conversation

```bash
DELETE /api/v1/chat/550e8400-e29b-41d4-a716-446655440000
```

**Response:**

```json
{
  "message": "Conversation cleared successfully",
  "chat_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Configuration

### Environment Variables

**.env**

```env
# Local development
REDIS_URL=redis://localhost:6379

# Railway production (auto-injected)
# REDIS_URL=redis://default:password@redis.railway.internal:6379
```

### Settings (`backend/config/settings.py`)

```python
# Redis Configuration
redis_url: Optional[str] = None  # Railway auto-injects REDIS_URL
redis_password: Optional[str] = None
redis_db: int = 0
redis_max_connections: int = 10
conversation_ttl: int = 3600  # 1 hour (in seconds)
conversation_history_limit: int = 10  # Last 10 messages
```

## Redis Key Structure

**Pattern:** `chat:{chat_id}:messages`

**Data Structure:** Redis Sorted Set

- **Score:** Message timestamp (milliseconds)
- **Member:** JSON-serialized message

**Example:**

```
Key: chat:550e8400-e29b-41d4-a716-446655440000:messages
Score: 1696789012345
Member: {"role":"user","content":"I spent $100...","timestamp":1696789012.345}
```

## TTL (Time-to-Live) Strategy

- **Default TTL:** 3600 seconds (1 hour)
- **Auto-extension:** TTL is reset on each new message
- **Auto-expiry:** After 1 hour of inactivity, conversation is automatically deleted
- **Manual clear:** Use DELETE endpoint to clear immediately

## Error Handling

### Redis Connection Failures

If Redis is unavailable:

- The service will log a warning
- Conversation memory will be disabled
- Chat will still work but without context from previous messages
- Each message will be treated as a new conversation

### Graceful Degradation

```python
if not self.redis.enabled:
    # Continue without conversation memory
    return []
```

## Best Practices

1. **Chat ID Management:**

   - Store chat_id on the frontend for the duration of a conversation
   - Generate new chat_id when starting a fresh conversation
   - If chat_id is not provided, a new one is auto-generated

2. **Conversation Limits:**

   - Default: Last 10 messages (5 exchanges)
   - Configurable via `conversation_history_limit` setting
   - Prevents token limit issues with very long conversations

3. **Privacy:**

   - Conversations auto-expire after 1 hour
   - Users can manually clear with DELETE endpoint
   - No persistent storage beyond TTL

4. **Performance:**
   - Redis sorted sets are O(log N) for inserts
   - ZRANGE is efficient for retrieving last N messages
   - Uses connection pooling for better performance

## Monitoring

### Check Redis Connection (Local)

```bash
# Connect to Redis CLI
docker exec -it finance-app-redis redis-cli

# Check stored conversations
KEYS chat:*

# View a conversation
ZRANGE chat:550e8400-e29b-41d4-a716-446655440000:messages 0 -1

# Check TTL
TTL chat:550e8400-e29b-41d4-a716-446655440000:messages
```

### Railway Redis Monitoring

- View Redis metrics in Railway dashboard
- Monitor connection count, memory usage, operations/sec
- Check logs for connection errors

## Troubleshooting

### Issue: "Redis connection failed"

**Solution:**

1. Check if Redis is running: `docker ps`
2. Verify REDIS_URL in .env: `echo $REDIS_URL`
3. Restart Redis: `docker-compose restart redis`

### Issue: "Conversation history not persisting"

**Solution:**

1. Check TTL setting: Should be > 0
2. Verify messages are being stored (check Redis logs)
3. Ensure same chat_id is being used across requests

### Issue: "Context not working in LLM responses"

**Solution:**

1. Verify conversation_history is being passed to prompt
2. Check prompt template includes history section
3. Review LLM response to ensure it's reading the context

## Future Enhancements

Potential improvements:

- [ ] User-scoped conversations (filter by user_id)
- [ ] Conversation search/indexing
- [ ] Export conversation history
- [ ] Configurable TTL per conversation
- [ ] Conversation analytics/insights
- [ ] Multi-language support
- [ ] Conversation summarization for very long chats

## Cost Estimation

### Railway Redis

- **Price:** $5/month
- **Included:** 256MB RAM, 1GB storage
- **Sufficient for:** ~10,000 active conversations (with 10 msg limit & 1hr TTL)

### Local Development

- **Cost:** Free (Docker)
- **Resources:** Minimal (~50MB RAM)

## Support

For issues or questions:

- Check logs: `docker logs finance-app-redis`
- Review Redis service implementation: `backend/services/redis_service.py`
- Check NLP service integration: `backend/services/nlp_service_v2.py`
