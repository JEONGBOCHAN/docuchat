# -*- coding: utf-8 -*-
from fastapi import APIRouter

from src.core.config import get_settings
from src.modules.conversation.public import get_checkpointer_type

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    settings = get_settings()
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "checkpointer": get_checkpointer_type(),
    }
