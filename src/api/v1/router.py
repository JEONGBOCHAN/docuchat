# -*- coding: utf-8 -*-
from fastapi import APIRouter

from src.api.v1 import health, channels, documents, chat, capacity, scheduler, admin, notes, faq, summarize, search

api_router = APIRouter()

# Health check
api_router.include_router(health.router, tags=["health"])

# Document upload (must come before channels due to path parameter conflict)
# Documents uses /channels/{channel_id}/documents which would be matched by
# channels' /{channel_id:path} if channels came first
api_router.include_router(documents.router)

# Chat API
api_router.include_router(chat.router)

# Capacity API
api_router.include_router(capacity.router)

# Scheduler API
api_router.include_router(scheduler.router)

# Admin monitoring API
api_router.include_router(admin.router)

# Notes API
api_router.include_router(notes.router)

# FAQ generation API
api_router.include_router(faq.router)

# Summarization API
api_router.include_router(summarize.router)

# Multi-channel search API
api_router.include_router(search.router)

# Channel CRUD
api_router.include_router(channels.router)
