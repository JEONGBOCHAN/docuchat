# -*- coding: utf-8 -*-
"""Structured logging configuration using structlog.

This module provides centralized logging configuration with:
- JSON formatted logs for production
- Console formatted logs for development
- Request context binding
- Performance metrics
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

from src.core.config import Environment, get_settings


class SafeStreamHandler(logging.StreamHandler):
    """A StreamHandler that handles encoding errors gracefully.

    On Windows with Korean locale (cp949), certain Unicode characters
    like em-dash (—) cannot be encoded. This handler replaces
    unencodable characters instead of raising an error.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            stream = self.stream
            # Handle encoding errors by replacing problematic characters
            if hasattr(stream, "encoding") and stream.encoding:
                try:
                    stream.write(msg + self.terminator)
                except UnicodeEncodeError:
                    # Encode with replacement for problematic characters
                    safe_msg = msg.encode(stream.encoding, errors="replace").decode(
                        stream.encoding
                    )
                    stream.write(safe_msg + self.terminator)
            else:
                stream.write(msg + self.terminator)
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)


def get_log_level() -> int:
    """Get logging level from settings."""
    settings = get_settings()
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(settings.log_level.upper(), logging.INFO)


def get_processors(json_format: bool = True) -> list[Processor]:
    """Get structlog processors based on format.

    Args:
        json_format: If True, use JSON renderer. Otherwise use console renderer.
    """
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        shared_processors.append(structlog.processors.format_exc_info)
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        shared_processors.append(structlog.dev.ConsoleRenderer(colors=True))

    return shared_processors


def setup_logging() -> None:
    """Configure structlog for the application.

    Sets up structured logging with appropriate formatters based on environment.
    Call this function once at application startup.
    """
    settings = get_settings()

    # Determine if we should use JSON format
    use_json = settings.log_format == "json" or settings.is_production
    if settings.is_development:
        use_json = settings.log_format == "json"

    log_level = get_log_level()

    # Configure standard library logging with encoding-safe handler
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add our safe stream handler
    handler = SafeStreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(handler)

    # Set third-party loggers to WARNING to reduce noise
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Configure structlog
    structlog.configure(
        processors=get_processors(json_format=use_json),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (usually __name__).

    Returns:
        A bound structlog logger.

    Example:
        logger = get_logger(__name__)
        logger.info("User logged in", user_id=123, ip="192.168.1.1")
    """
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """Bind context variables to all subsequent log messages.

    Useful for adding request-scoped context like request_id, user_id, etc.

    Args:
        **kwargs: Context key-value pairs to bind.

    Example:
        bind_context(request_id="abc123", user_id=456)
        logger.info("Processing request")  # Will include request_id and user_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables.

    Call this at the end of a request to prevent context leakage.
    """
    structlog.contextvars.clear_contextvars()


def unbind_context(*keys: str) -> None:
    """Remove specific context variables.

    Args:
        *keys: Context keys to remove.
    """
    structlog.contextvars.unbind_contextvars(*keys)
