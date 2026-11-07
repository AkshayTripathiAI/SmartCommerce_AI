import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1 import router as api_v1_router
from app.db import init_db
from app import bootstrap
from app.ai import models

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: Initialize database tables
    await init_db()
    task = None
    if settings.auto_bootstrap:
        # Run in the background so the server binds its port (and passes health checks) immediately.
        task = asyncio.create_task(bootstrap.run_bootstrap())
    yield
    if task and not task.done():
        task.cancel()
    # Shutdown: cleanup if needed


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="AI-powered e-commerce platform with recommendations and conversational shopping",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(api_v1_router)


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - health check."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "status": "healthy",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "bootstrap": bootstrap.state["status"],
        "commit": os.getenv("RENDER_GIT_COMMIT", "")[:7] or None,
        "chat_model": models.resolved_model(),
    }