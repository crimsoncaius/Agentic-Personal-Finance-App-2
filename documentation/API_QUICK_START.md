# API Quick Start Guide

## Authentication Required

All API endpoints (except auth endpoints) now require authentication. You must include a valid JWT token in the Authorization header.

## Quick Authentication Flow

### 1. Register a New User

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@example.com",
    "password": "password123",
    "name": "Demo User"
  }'
```

**Response:**

```json
{
  "user": {
    "id": "user-uuid-here",
    "email": "demo@example.com",
    "name": "Demo User",
    "created_at": "2025-10-08T12:00:00Z"
  },
  "session": {
    "access_token": "eyJhbGciOiJI...",
    "refresh_token": "refresh-token-here",
    "expires_at": 1696780800
  },
  "message": "User registered and logged in successfully."
}
```

### 2. Save Your Token

Copy the `access_token` from the response. You'll need it for all subsequent requests.

### 3. Make Authenticated Requests

**Create an Entry:**

```bash
curl -X POST http://localhost:8000/api/v1/entries/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE" \
  -d '{
    "amount": 25.50,
    "direction": "expense",
    "entry_date": "2025-10-08",
    "description": "Coffee and snacks",
    "category_id": null
  }'
```

**Get Your Entries:**

```bash
curl -X GET http://localhost:8000/api/v1/entries/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE"
```

**Use Natural Language (Chat):**

```bash
curl -X POST http://localhost:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE" \
  -d '{
    "text": "I spent $45 on groceries today"
  }'
```

## Token Expiry

- **Access tokens** expire after 1 hour
- **Refresh tokens** last for 7 days

### Refresh Your Token

When your access token expires (you'll get a 401 error), use your refresh token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "YOUR_REFRESH_TOKEN_HERE"
  }'
```

## Environment Variables

Make sure your `.env` file is configured:

```bash
# Supabase Configuration
SUPABASE_URL_DEV=https://your-project.supabase.co
SUPABASE_KEY_DEV=your-anon-key
SUPABASE_SERVICE_ROLE_KEY_DEV=your-service-key

# Environment
ENVIRONMENT=development
```

## Testing the API

### Using FastAPI Docs

1. Start the server: `cd backend && python main.py`
2. Open: http://localhost:8000/docs
3. Click "Authorize" button (green lock icon)
4. Login first via `/auth/login` endpoint
5. Copy the `access_token` from response
6. Click "Authorize" and enter: `Bearer YOUR_ACCESS_TOKEN`
7. Now you can test all protected endpoints!

### Common Errors

**401 Unauthorized:**

- Missing Authorization header
- Expired access token (refresh it)
- Invalid token format (must be `Bearer <token>`)

**404 Not Found on Entry:**

- Entry doesn't exist
- Entry belongs to another user (you can only access your own entries)

**409 Conflict on Registration:**

- Email already registered
- Use login instead

## API Endpoints Summary

### Authentication

- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login existing user
- `POST /api/v1/auth/logout` - Logout (requires token)
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/verify` - Verify token
- `GET /api/v1/auth/me` - Get current user info

### Entries (All Require Authentication)

- `POST /api/v1/entries/` - Create entry
- `GET /api/v1/entries/` - List your entries
- `PATCH /api/v1/entries/{id}` - Update your entry
- `DELETE /api/v1/entries/{id}` - Delete your entry

### Chat (Requires Authentication)

- `POST /api/v1/chat/` - Natural language queries
- `GET /api/v1/chat/service-info` - NLP service info

### Categories (No Authentication Required)

- `GET /api/v1/categories/` - List all categories

## Next Steps

- See `phase3_authentication_implementation.md` for detailed documentation
- Check `frontend_audit.md` for frontend integration guide
- Review `authentication_plan.md` for the complete authentication strategy
