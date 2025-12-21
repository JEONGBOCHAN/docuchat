# -*- coding: utf-8 -*-
"""API metrics tracking middleware.

This middleware records metrics for all API calls.
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.services.api_metrics import get_api_metrics


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for tracking API request metrics.

    Records call count, latency, and success/error status for each endpoint.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request and record metrics.

        Args:
            request: The incoming request
            call_next: The next middleware/handler

        Returns:
            The response from the handler
        """
        start_time = time.time()
        metrics = get_api_metrics()

        # Get endpoint path for grouping
        endpoint = request.url.path

        method = request.method

        try:
            response = await call_next(request)
            latency_ms = (time.time() - start_time) * 1000

            # Record successful call (2xx/3xx status codes)
            success = response.status_code < 400
            metrics.record_call(
                endpoint, success=success, latency_ms=latency_ms, method=method
            )

            return response

        except Exception:
            latency_ms = (time.time() - start_time) * 1000
            metrics.record_call(
                endpoint, success=False, latency_ms=latency_ms, method=method
            )
            raise
