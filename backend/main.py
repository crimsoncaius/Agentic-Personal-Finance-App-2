"""
Main FastAPI application for Expense Tracker MVP
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load environment variables
load_dotenv()

# Import routes
from routes import categories, chat, entries

# Create FastAPI app
app = FastAPI(
    title="Expense Tracker MVP",
    description="Personal finance app with natural language processing",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(entries.router)
app.include_router(categories.router)
app.include_router(chat.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Expense Tracker MVP API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "expense-tracker-mvp"}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    return JSONResponse(
        status_code=500,
        content={
            "error": {"code": "internal_error", "message": "Internal server error"}
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
