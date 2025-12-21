# -*- coding: utf-8 -*-
"""Request/Response logging middleware.

This middleware provides structured logging for all HTTP requests and responses,
including request context binding for correlation.
"""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.logging import bind_context, clear_context, get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request/response logging.

    Features:
    - Unique request ID generation for correlation
    - Request details logging (method, path, client IP)
    - Response logging (status code, latency)
    - Context binding for all logs within request scope
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request and log details.

        Args:
            request: The incoming request
            call_next: The next middleware/handler

        Returns:
            The response from the handler
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]

        # Extract client IP
        client_ip = self._get_client_ip(request)

        # Bind request context for all subsequent logs
        bind_context(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
        )

        # Store request ID in request state for access in handlers
        request.state.request_id = request_id

        start_time = time.time()

        # Log incoming request
        logger.info(
            "Request started",
            query_params=dict(request.query_params) if request.query_params else None,
            user_agent=request.headers.get("user-agent"),
        )

        try:
            response = await call_next(request)
            latency_ms = (time.time() - start_time) * 1000

            # Log successful response
            logger.info(
                "Request completed",
                status_code=response.status_code,
                latency_ms=round(latency_ms, 2),
            )

            # Add request ID to response headers for client-side correlation
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000

            # Log error
            logger.error(
                "Request failed",
                error=str(e),
                error_type=type(e).__name__,
                latency_ms=round(latency_ms, 2),
                exc_info=True,
            )
            raise

        finally:
            # Clear context to prevent leakage between requests
            clear_context()

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxies.

        Args:
            request: The incoming request

        Returns:
            Client IP address
        """
        # Check for forwarded headers (when behind proxy/load balancer)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # First IP in the list is the original client
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fallback to direct connection
        if request.client:
            return request.client.host

        return "unknown"
