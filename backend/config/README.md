# Configuration Management

This directory contains the application configuration system using Pydantic for type-safe environment variable management.

## Files

- `settings.py` - Main application settings with environment variable loading
- `database.py` - Database-specific configuration
- `nlp.py` - NLP service configuration
- `logging.yaml` - Logging configuration

## Environment Files

The application uses a simple environment file system:

1. **`.env`** - Main environment file (committed for development)
2. **`.env.example`** - Environment template for new developers

## Usage

```python
from config.settings import settings
from config.database import db_config
from config.nlp import nlp_config

# Access settings
print(settings.supabase_url)
print(settings.cors_origins_list)
print(db_config.connection_params)
print(nlp_config.has_langfuse)
```

## Environment Variables

### Required

- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_KEY` - Supabase anon key
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key
- `OPENAI_API_KEY` - OpenAI API key

### Optional

- `LANGFUSE_PUBLIC_KEY` - Langfuse public key
- `LANGFUSE_SECRET_KEY` - Langfuse secret key
- `LANGFUSE_HOST` - Langfuse host URL
- `CORS_ORIGINS` - Comma-separated CORS origins
- `DEBUG` - Enable debug mode
- `ENVIRONMENT` - Environment name (development/production)
