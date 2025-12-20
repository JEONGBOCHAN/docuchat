# -*- coding: utf-8 -*-
"""Rate limiting configuration and utilities."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def get_rate_limit_key(request: Request) -> str:
    """Get rate limit key based on IP and optional user.

    Returns IP-based key by default. Can be extended to include user ID
    when authentication is implemented.
    """
    # For now, use IP-based limiting
    # TODO: Add user-based limiting when auth is implemented
    return get_remote_address(request)


# Create the limiter instance
limiter = Limiter(key_func=get_rate_limit_key)


# Rate limit constants
class RateLimits:
    """Rate limit configurations for different endpoint types."""

    # Chat endpoints - 10 requests per minute (Gemini API cost protection)
    CHAT = "10/minute"

    # File upload endpoints - 20 requests per hour
    FILE_UPLOAD = "20/hour"

    # Default for other endpoints - 100 requests per minute
    DEFAULT = "100/minute"
