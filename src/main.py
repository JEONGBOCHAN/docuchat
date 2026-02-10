# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from src.api.v1.router import api_router
from src.core.config import get_settings
from src.core.database import init_db
from src.core.logging import get_logger, setup_logging
from src.core.rate_limiter import limiter
from src.core.sentry import setup_sentry
from src.middleware.metrics import MetricsMiddleware
from src.middleware.request_logging import RequestLoggingMiddleware
from src.modules.ops.public import setup_scheduler, shutdown_scheduler
from src.application.use_cases.exceptions import UpstreamError

# Initialize structured logging first
setup_logging()

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: Initialize Sentry error tracking
    setup_sentry()

    # Startup: Initialize database tables
    init_db()

    # Startup: Start background scheduler (ops module)
    setup_scheduler()

    logger.info(
        "Application started",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env.value,
    )

    yield

    # Shutdown: Stop compaction runner, audio executor, then scheduler
    from src.modules.conversation.public import shutdown_compaction_runner
    shutdown_compaction_runner(wait=False)
    logger.info("Compaction runner shutdown complete")

    from src.api.v1.audio import shutdown_audio_executor
    shutdown_audio_executor(wait=False)
    logger.info("Audio executor shutdown complete")

    shutdown_scheduler(wait=False)
    logger.info("Scheduler shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="NotebookLM Clone - Document-based RAG Chat Application",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate limiting setup
app.state.limiter = limiter


@app.exception_handler(UpstreamError)
async def upstream_error_handler(request: Request, exc: UpstreamError):
    """Handle external service failures with 502 Bad Gateway."""
    logger.error("Upstream error from %s: %s", exc.service, exc)
    return JSONResponse(
        status_code=502,
        content={
            "detail": f"External service error ({exc.service})",
            "message": str(exc),
        },
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom rate limit exceeded handler with proper headers."""
    # Parse rate limit info from exception
    limit_value = getattr(exc, "detail", "Rate limit exceeded")

    response = JSONResponse(
        status_code=429,
        content={
            "detail": "Too Many Requests",
            "message": limit_value,
        },
    )

    # Add rate limit headers
    if hasattr(request.state, "view_rate_limit"):
        rate_info = request.state.view_rate_limit
        # rate_info can be a string ("10 per 1 minute") or tuple
        if isinstance(rate_info, str):
            limit_parts = rate_info.split(" per ")
            if len(limit_parts) == 2:
                response.headers["X-RateLimit-Limit"] = limit_parts[0]
        elif isinstance(rate_info, tuple) and len(rate_info) > 0:
            # Handle tuple format from slowapi
            response.headers["X-RateLimit-Limit"] = str(rate_info[0])

    # Retry-After header (seconds until reset)
    response.headers["Retry-After"] = str(getattr(exc, "retry_after", 60))

    return response


# CORS middleware
# Browser CORS spec disallows credentials with wildcard origin.
# When origins is ["*"], disable credentials to avoid spec violation.
_cors_allow_credentials = "*" not in settings.cors_origins_list
if not _cors_allow_credentials and settings.cors_origins == "*":
    logger.warning(
        "CORS: allow_credentials disabled because cors_origins is wildcard ('*'). "
        "Set explicit origins to enable credentials."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],  # Allow browser to read MCP session header
)

# Request logging middleware (should be outermost for accurate timing)
app.add_middleware(RequestLoggingMiddleware)

# Metrics tracking middleware
app.add_middleware(MetricsMiddleware)

# Include API router
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health",
    }
