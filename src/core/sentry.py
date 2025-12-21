# -*- coding: utf-8 -*-
"""Sentry error tracking configuration.

This module provides Sentry SDK initialization for error tracking and performance monitoring.
"""

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


def setup_sentry() -> bool:
    """Initialize Sentry SDK for error tracking.

    Configures Sentry with:
    - Error tracking with full stack traces
    - Performance monitoring (transactions)
    - FastAPI integration
    - Environment and release tagging

    Returns:
        True if Sentry was initialized, False if DSN is not configured.
    """
    settings = get_settings()

    if not settings.sentry_dsn:
        logger.info("Sentry DSN not configured, skipping initialization")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env.value,
            release=f"{settings.app_name}@{settings.app_version}",
            # Performance monitoring
            traces_sample_rate=settings.sentry_traces_sample_rate,
            profiles_sample_rate=settings.sentry_profiles_sample_rate,
            # Integrations
            integrations=[
                StarletteIntegration(transaction_style="endpoint"),
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                LoggingIntegration(
                    level=None,  # Capture all levels
                    event_level=None,  # Don't send logs as events (use structured logging)
                ),
            ],
            # Data filtering
            send_default_pii=False,  # Don't send PII by default
            # Hooks
            before_send=_before_send,
        )

        logger.info(
            "Sentry initialized",
            environment=settings.app_env.value,
            release=f"{settings.app_name}@{settings.app_version}",
        )
        return True

    except ImportError:
        logger.warning("sentry-sdk not installed, skipping Sentry initialization")
        return False
    except Exception as e:
        logger.error("Failed to initialize Sentry", error=str(e))
        return False


def _before_send(event: dict, hint: dict) -> dict | None:
    """Filter events before sending to Sentry.

    This hook allows us to:
    - Filter out certain errors
    - Sanitize sensitive data
    - Add custom context

    Args:
        event: The Sentry event dict
        hint: Additional context about the event

    Returns:
        The modified event, or None to drop it
    """
    # Don't send certain expected errors
    if "exc_info" in hint:
        exc_type, exc_value, _ = hint["exc_info"]

        # Filter out common expected errors
        if exc_type.__name__ in ("HTTPException", "RequestValidationError"):
            return None

    return event


def capture_exception(error: Exception, **extra_context) -> str | None:
    """Capture an exception to Sentry with additional context.

    Args:
        error: The exception to capture
        **extra_context: Additional context to attach

    Returns:
        The Sentry event ID if captured, None otherwise
    """
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in extra_context.items():
                scope.set_extra(key, value)
            return sentry_sdk.capture_exception(error)
    except ImportError:
        return None


def capture_message(message: str, level: str = "info", **extra_context) -> str | None:
    """Capture a message to Sentry.

    Args:
        message: The message to capture
        level: Log level (debug, info, warning, error, fatal)
        **extra_context: Additional context to attach

    Returns:
        The Sentry event ID if captured, None otherwise
    """
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in extra_context.items():
                scope.set_extra(key, value)
            return sentry_sdk.capture_message(message, level=level)
    except ImportError:
        return None


def set_user_context(user_id: str | None = None, **extra) -> None:
    """Set user context for Sentry events.

    Args:
        user_id: The user identifier
        **extra: Additional user properties
    """
    try:
        import sentry_sdk

        user_data = {"id": user_id} if user_id else {}
        user_data.update(extra)
        sentry_sdk.set_user(user_data if user_data else None)
    except ImportError:
        pass
