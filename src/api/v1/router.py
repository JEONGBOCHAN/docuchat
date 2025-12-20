# -*- coding: utf-8 -*-
from fastapi import APIRouter

from src.api.v1 import health, channels

api_router = APIRouter()

# Health check
api_router.include_router(health.router, tags=["health"])

# Channel CRUD
api_router.include_router(channels.router)

# TODO: Add more routers
# api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
# api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
