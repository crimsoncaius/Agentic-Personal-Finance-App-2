# Configuration Guide

This guide explains the configuration management system for the Agentic Personal Finance App.

## Environment Setup

### 1. Copy Environment Template

```bash
cp .env.example .env
```

### 2. Configure Your Environment

Edit `.env` with your actual values:

```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key

# LLM Configuration
OPENAI_API_KEY=your-openai-api-key

# Optional: Langfuse for observability
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 3. Environment Management

For different environments, you can create additional `.env` files as needed:

- `.env.local` - Local development overrides (gitignored)
- `.env.production` - Production settings (gitignored)
- `.env.testing` - Testing settings (gitignored)

## Configuration Structure

```
├── .env                    # Main environment file
├── .env.example           # Environment template
└── backend/
    └── config/
        ├── settings.py    # Main settings
        ├── database.py    # Database config
        ├── nlp.py        # NLP config
        └── logging.yaml  # Logging config
```

## Usage in Code

```python
from config.settings import settings
from config.database import db_config
from config.nlp import nlp_config

# Type-safe access to configuration
print(settings.supabase_url)
print(settings.cors_origins_list)
print(db_config.connection_params)
print(nlp_config.has_langfuse)
```

## Environment Variable Priority

1. Environment variables (highest priority)
2. `.env.local` (if it exists)
3. `.env` (lowest priority)

## Security Notes

- Never commit `.env.local`, `.env.production`, or `.env.testing` files
- Use different API keys for different environments
- Rotate keys regularly
- Use least-privilege access for service keys
