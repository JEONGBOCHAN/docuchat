# -*- coding: utf-8 -*-
"""Domain value objects.

Simple value types that belong to the domain layer.
No external framework dependencies.
"""

from enum import Enum


class TargetType(str, Enum):
    """Favorite target types."""

    CHANNEL = "channel"
    DOCUMENT = "document"
    NOTE = "note"
