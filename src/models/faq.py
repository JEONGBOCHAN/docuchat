# -*- coding: utf-8 -*-
"""Pydantic models for FAQ generation."""

from datetime import datetime, UTC
from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class FAQItem(BaseModel):
    """A single FAQ item with question and answer."""

    question: str = Field(..., description="Generated question")
    answer: str = Field(..., description="Generated answer based on documents")


class FAQGenerateRequest(BaseModel):
    """Request model for FAQ generation."""

    count: int = Field(default=5, ge=1, le=20, description="Number of FAQ items to generate")


class FAQGenerateResponse(BaseModel):
    """Response model for FAQ generation."""

    channel_id: str = Field(..., description="Channel ID")
    items: list[FAQItem] = Field(..., description="Generated FAQ items")
    generated_at: datetime = Field(default_factory=_utc_now)
