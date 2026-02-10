# -*- coding: utf-8 -*-
"""Module-native API router.

Assembles all module presentation routers into a single APIRouter.
This replaces the legacy src.api.v1.router as the primary entry point.
"""

from fastapi import APIRouter

from src.modules.ops.presentation.api import health, scheduler, admin
from src.modules.workspace.presentation.api import (
    documents, export, capacity, notes, search, favorites, preview, trash,
    youtube, channels, google_drive,
)
from src.modules.conversation.presentation.api import chat, dashboard, mcp
from src.modules.knowledge.presentation.api import (
    faq, summarize, citations, timeline, study, audio,
)

api_router = APIRouter()

# Health check
api_router.include_router(health.router, tags=["health"])

# Document upload (must come before channels due to path parameter conflict)
api_router.include_router(documents.router)

# Export API
api_router.include_router(export.router)

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

# Citations API (inline citations with source navigation)
api_router.include_router(citations.router)

# Favorites API
api_router.include_router(favorites.router)

# Document preview API
api_router.include_router(preview.router)

# Trash API
api_router.include_router(trash.router)

# Timeline/Briefing generation API
api_router.include_router(timeline.router)

# YouTube source API
api_router.include_router(youtube.router)

# Study guide and quiz API
api_router.include_router(study.router)

# Audio Overview (Podcast) API
api_router.include_router(audio.router)

# Google Drive Integration API
api_router.include_router(google_drive.router)

# Agent Dashboard (MCP Apps browser testing)
api_router.include_router(dashboard.router)

# MCP Streamable HTTP Transport (for frontend MCP client)
api_router.include_router(mcp.router)

# Channel CRUD (last due to path parameter conflict)
api_router.include_router(channels.router)
