# -*- coding: utf-8 -*-
"""Admin authentication dependency."""

from fastapi import Header, HTTPException, status

from src.core.config import get_settings


def require_admin_key(
    x_admin_key: str = Header(..., description="Admin API key"),
) -> str:
    """Verify the admin API key from X-Admin-Key header.

    Raises 401 if key is missing/wrong, 503 if not configured.
    """
    settings = get_settings()
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API key is not configured on the server",
        )
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin API key",
        )
    return x_admin_key
