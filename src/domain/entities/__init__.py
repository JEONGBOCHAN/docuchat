# -*- coding: utf-8 -*-
"""
Domain Entities.

Pure Python data classes representing core business concepts.
No Pydantic, no SQLAlchemy - just dataclasses and typing.
"""

from src.domain.entities.document import Document, DocumentChunk
from src.domain.entities.channel import Channel
from src.domain.entities.note import Note, NoteSource

__all__ = [
    "Document",
    "DocumentChunk",
    "Channel",
    "Note",
    "NoteSource",
]
