# Deployment Guide

This guide covers deploying the Personal Finance App with Redis integration to Vercel (frontend) and Railway (backend).

## Architecture Overview

- **Frontend**: React + Vite → Vercel
- **Backend**: FastAPI + Python → Railway
- **Database**: Supabase
- **Cache**: Redis → Railway (Redis Plugin)

## Prerequisites

1. Vercel account and CLI
2. Railway account and CLI
3. Supabase project
4. OpenAI API key
5. Langfuse account (optional, for observability)

## Backend Deployment (Railway)

### 1. Install Railway CLI

```bash
npm install -g @railway/cli
railway login
```

### 2. Create Railway Project

```bash
railway init
```

### 3. Add Redis Plugin

1. Go to your Railway project dashboard
2. Click "Add Service" → "Database" → "Add Redis"
3. Connect the Redis service to your backend service

### 4. Set Environment Variables

In Railway dashboard, add these environment variables to your backend service:

```bash
ENVIRONMENT=production
SUPABASE_URL_PROD=your-production-supabase-url
SUPABASE_KEY_PROD=your-production-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY_PROD=your-production-supabase-service-role-key
OPENAI_API_KEY=your-openai-api-key
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
LANGFUSE_HOST=https://cloud.langfuse.com
CORS_ORIGINS=https://your-frontend-domain.vercel.app
TEST_USER_ID=your-test-user-id
```

**Note**: `REDIS_URL` will be automatically injected by Railway when you add the Redis plugin.

### 5. Deploy Backend

```bash
railway up
```

## Frontend Deployment (Vercel)

### 1. Install Vercel CLI

```bash
npm install -g vercel
vercel login
```

### 2. Set Environment Variables

In Vercel dashboard, add:

```bash
VITE_API_URL=https://your-railway-backend-url.railway.app
```

### 3. Deploy Frontend

```bash
vercel --prod
```

## Local Development with Redis

### 1. Start Redis with Docker

```bash
docker-compose up redis
```

### 2. Set Environment Variables

Copy `.env.example` to `.env` and update with your values:

```bash
cp .env.example .env
```

### 3. Start Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

### 4. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

## Environment Configuration

### Development

- Uses `SUPABASE_URL_DEV` and `SUPABASE_KEY_DEV`
- Redis: `redis://localhost:6379`
- CORS: `http://localhost:3000,http://localhost:5173`

### Production

- Uses `SUPABASE_URL_PROD` and `SUPABASE_KEY_PROD`
- Redis: Auto-injected `REDIS_URL` from Railway
- CORS: Your Vercel domain

## Redis Integration

The app uses Redis for:

- **Conversation Memory**: Stores chat history for contextual NLP processing
- **TTL Management**: Automatic cleanup of old conversations (1 hour default)
- **Scalable Caching**: Handles multiple concurrent users

### Redis Configuration

- **Database**: 0 (default)
- **Max Connections**: 10
- **TTL**: 3600 seconds (1 hour)
- **History Limit**: 10 messages per conversation

## Monitoring and Debugging

### Railway Logs

```bash
railway logs
```

### Vercel Logs

```bash
vercel logs
```

### Redis Health Check

The app includes automatic Redis health checks. If Redis is unavailable, the app will:

- Log warnings
- Continue functioning without conversation memory
- Gracefully degrade features

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**

   - Check if Redis plugin is properly connected in Railway
   - Verify `REDIS_URL` environment variable is set
   - Check Railway logs for connection errors

2. **CORS Errors**

   - Ensure `CORS_ORIGINS` includes your Vercel domain
   - Check that frontend `VITE_API_URL` points to correct backend URL

3. **Environment Variables**
   - Verify all required environment variables are set
   - Check that production/development variables are correctly configured

### Health Checks

- **Backend Health**: `GET /health`
- **Redis Status**: Check application logs for Redis connection status

## Security Notes

- Never commit `.env` files to version control
- Use Railway's environment variable management for secrets
- Ensure CORS is properly configured for production domains
- Regularly rotate API keys and secrets

## Scaling Considerations

- **Redis**: Railway Redis plugin handles scaling automatically
- **Backend**: Railway auto-scales based on traffic
- **Frontend**: Vercel CDN provides global distribution
- **Database**: Supabase handles database scaling

## Cost Optimization

- **Redis**: Railway Redis plugin has usage-based pricing
- **Backend**: Railway charges based on resource usage
- **Frontend**: Vercel has generous free tier
- **Database**: Supabase free tier includes 500MB database

## Next Steps

1. Set up monitoring and alerting
2. Configure custom domains
3. Set up CI/CD pipelines
4. Implement backup strategies
5. Add performance monitoring
