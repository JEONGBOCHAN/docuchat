# -*- coding: utf-8 -*-
"""Shared use case exceptions.

Domain-level exceptions raised by use cases.
Routers catch these and translate to HTTP status codes.
"""


class ChannelNotFoundError(Exception):
    """Channel not found. Maps to HTTP 404."""

    def __init__(self, channel_id: str):
        self.channel_id = channel_id
        super().__init__(f"Channel not found: {channel_id}")


class TargetNotFoundError(Exception):
    """Favorite target (note, document) not found. Maps to HTTP 404."""
    pass


class InvalidTargetError(Exception):
    """Invalid target format. Maps to HTTP 400."""
    pass
