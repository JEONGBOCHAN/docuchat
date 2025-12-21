# -*- coding: utf-8 -*-
from fastapi import APIRouter

from src.api.v1 import health, channels, documents, chat, capacity, scheduler, admin, notes, faq, summarize, search, citations, favorites, preview, trash, export, timeline, youtube, study, audio, google_drive

api_router = APIRouter()

# Health check
api_router.include_router(health.router, tags=["health"])

# Document upload (must come before channels due to path parameter conflict)
# Documents uses /channels/{channel_id}/documents which would be matched by
# channels' /{channel_id:path} if channels came first
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

# Channel CRUD
api_router.include_router(channels.router)
