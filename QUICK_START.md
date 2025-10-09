# Redis Conversation Memory - Quick Start Guide

## ✅ Installation Complete

Redis conversation memory has been successfully implemented! All dependencies are installed and code is ready.

## 🚀 Quick Start (Local Development)

### Step 1: Start Redis

```bash
# Start Redis using Docker Compose
docker-compose up -d

# Verify Redis is running
docker ps | grep redis
```

### Step 2: Activate Conda Environment

```bash
# Activate your conda environment
conda activate agentic-personal-finance
```

### Step 3: Start Backend

```bash
# Start the FastAPI backend
cd backend
python main.py
```

### Step 4: Test Conversation Memory

**Request 1:**

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "text": "I spent $100 on car yesterday"
  }'
```

**Response:**

```json
{
  "operation": "write",
  "result": {...},
  "message": "I've added your $100 expense for car.",
  "chat_id": "abc-123-def-456"
}
```

**Request 2 (with context):**

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "text": "also add motorcycle $150 on the same day",
    "chat_id": "abc-123-def-456"
  }'
```

The LLM will understand "the same day" refers to yesterday! 🎉

## 🔧 Configuration

### Environment Variables

**.env** (already configured)

```env
REDIS_URL=redis://localhost:6379
```

### Settings

**backend/config/settings.py** (already configured)

```python
redis_url: Optional[str] = None  # Auto-loaded from .env
conversation_ttl: int = 3600  # 1 hour
conversation_history_limit: int = 10  # Last 10 messages
```

## 📊 Check Conversation History

```bash
# Get conversation history
curl http://localhost:8000/api/v1/chat/abc-123-def-456/history \
  -H "Authorization: Bearer YOUR_TOKEN"

# Clear conversation
curl -X DELETE http://localhost:8000/api/v1/chat/abc-123-def-456 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🐳 Docker Commands

```bash
# Start Redis
docker-compose up -d

# Stop Redis
docker-compose down

# View Redis logs
docker logs finance-app-redis

# Connect to Redis CLI
docker exec -it finance-app-redis redis-cli

# Inside Redis CLI:
KEYS chat:*  # View all conversations
```

## 🚂 Railway Deployment

### Step 1: Add Redis Plugin

1. Go to Railway dashboard
2. Select your project
3. Click "New" → "Database" → "Add Redis"
4. Railway auto-injects `REDIS_URL`

### Step 2: Deploy

```bash
# Push your changes
git add .
git commit -m "Add Redis conversation memory"
git push

# Railway auto-deploys
```

That's it! Redis will work automatically in production.

## ✅ Verification

### Check imports work:

```bash
conda activate agentic-personal-finance
python -c "import sys; sys.path.insert(0, 'backend'); from services.redis_service import redis_service; print('✅ Success')"
```

### Check Redis connection:

```bash
docker-compose up -d
python -c "import sys; sys.path.insert(0, 'backend'); from services.redis_service import redis_service; print('Redis enabled:', redis_service.enabled)"
```

Should show: `Redis enabled: True`

## 📚 Documentation

- **Full Guide:** `REDIS_MEMORY_GUIDE.md`
- **Implementation Summary:** `REDIS_IMPLEMENTATION_SUMMARY.md`
- **API Docs:** http://localhost:8000/docs (when backend running)

## 🎯 What's Working

✅ Redis service with graceful degradation  
✅ Conversation history storage (sorted sets)  
✅ Auto-expiry (1 hour TTL)  
✅ NLP service integration  
✅ Prompt context injection  
✅ API endpoints (POST, GET, DELETE)  
✅ Schema models (ChatMessage, etc.)  
✅ All linting passed

## 🔥 Example Conversation Flow

```
User: "I spent $100 on car yesterday"
Assistant: "I've added your $100 expense for car."

User: "also add motorcycle $150 on the same day"
Assistant: "I've added your $150 expense for motorcycle on yesterday."
                                                            ↑
                                            Understands context!
```

## 🛠️ Troubleshooting

**Issue: Redis connection failed**

```bash
# Start Redis
docker-compose up -d

# Check if running
docker ps
```

**Issue: Module not found**

```bash
# Activate conda env
conda activate agentic-personal-finance

# Install dependencies
pip install -r backend/requirements.txt
```

**Issue: Can't find chat_id**

- chat_id is returned in the response
- Store it on frontend for follow-up messages
- If omitted, a new chat_id is auto-generated

## 🎉 You're Ready!

Start Redis and test your conversation memory:

```bash
docker-compose up -d
cd backend
python main.py
```

Then make chat requests with `chat_id` to maintain context! 🚀
