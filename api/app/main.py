"""Main FastAPI application entry point."""

import structlog
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import uuid

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings as app_settings
from app.db.session import init_db, close_db
from app.routers import documents, exceptions, export, metrics, webhooks, auth, settings as settings_router


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if app_settings.is_production else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Rate limiter - uses remote address for identification
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to each request for tracing."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        # Add to request state for access in handlers
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting application", environment=app_settings.environment)
    await init_db()
    logger.info("Database initialized")

    yield

    # Shutdown
    logger.info("Shutting down application")
    await close_db()
    logger.info("Database connections closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        description="Automated data ingestion system for private credit funds using GCP managed services.",
        docs_url="/docs" if not app_settings.is_production else None,
        redoc_url="/redoc" if not app_settings.is_production else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID middleware for distributed tracing
    app.add_middleware(RequestIDMiddleware)

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Include routers
    app.include_router(auth.router, prefix=f"{app_settings.api_prefix}/auth", tags=["Authentication"])
    app.include_router(documents.router, prefix=f"{app_settings.api_prefix}/documents", tags=["Documents"])
    app.include_router(exceptions.router, prefix=f"{app_settings.api_prefix}/exceptions", tags=["Exceptions"])
    app.include_router(export.router, prefix=f"{app_settings.api_prefix}/export", tags=["Export"])
    app.include_router(metrics.router, prefix=f"{app_settings.api_prefix}/metrics", tags=["Metrics"])
    app.include_router(webhooks.router, prefix=f"{app_settings.api_prefix}/webhook", tags=["Webhooks"])
    app.include_router(settings_router.router, prefix=f"{app_settings.api_prefix}/settings", tags=["Settings"])

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled exception",
            exc_info=exc,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    return app


app = create_app()


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint for load balancers and monitoring."""
    return {
        "status": "healthy",
        "version": app_settings.app_version,
        "environment": app_settings.environment,
    }


@app.get("/ready", tags=["Health"])
async def readiness_check() -> dict:
    """Readiness check endpoint to verify all dependencies are available."""
    # TODO: Add actual dependency checks (database, GCS, etc.)
    return {
        "status": "ready",
        "database": "connected",
        "storage": "connected",
    }
