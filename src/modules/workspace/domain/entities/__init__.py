# -*- coding: utf-8 -*-
"""
Workspace Domain Entities.

Pure Python data classes representing core business concepts.
No Pydantic, no SQLAlchemy - just dataclasses and typing.
"""

from src.modules.workspace.domain.entities.document import Document, DocumentChunk
from src.modules.workspace.domain.entities.channel import Channel
from src.modules.workspace.domain.entities.note import Note, NoteSource

__all__ = [
    "Document",
    "DocumentChunk",
    "Channel",
    "Note",
    "NoteSource",
]
