# -*- coding: utf-8 -*-
"""
Channel Domain Entity.

Pure Python representation of a channel (document workspace).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Channel:
    """A channel (document workspace) in the system.

    A channel is a container for documents that can be queried together.
    It represents a logical grouping of related documents.

    Attributes:
        id: Unique channel identifier
        name: Display name of the channel
        description: Optional description
        created_at: When the channel was created
        updated_at: When the channel was last modified
        document_count: Number of documents in the channel
        metadata: Additional channel metadata
    """

    id: str
    name: str
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    document_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        """Update the last modified timestamp."""
        self.updated_at = datetime.now()
