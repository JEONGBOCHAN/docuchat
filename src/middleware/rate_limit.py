# -*- coding: utf-8 -*-
"""Rate limiting middleware with custom headers."""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RateLimitHeaderMiddleware(BaseHTTPMiddleware):
    """Middleware to add rate limit headers to responses.

    Adds the following headers:
    - X-RateLimit-Limit: Maximum number of requests allowed
    - X-RateLimit-Remaining: Number of requests remaining
    - X-RateLimit-Reset: Unix timestamp when the limit resets
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Check if rate limit info is available in request state
        # slowapi stores this info after processing
        if hasattr(request.state, "_rate_limiting"):
            rate_info = request.state._rate_limiting

            # Extract rate limit info from slowapi's internal state
            if rate_info:
                # Get the first limit (primary rate limit)
                for limit_info in rate_info.values():
                    if limit_info:
                        limit_data = limit_info[0] if limit_info else None
                        if limit_data:
                            response.headers["X-RateLimit-Limit"] = str(limit_data.get("limit", 0))
                            response.headers["X-RateLimit-Remaining"] = str(limit_data.get("remaining", 0))
                            response.headers["X-RateLimit-Reset"] = str(limit_data.get("reset", 0))
                        break

        return response
