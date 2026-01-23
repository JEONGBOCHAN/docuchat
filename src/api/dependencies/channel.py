# -*- coding: utf-8 -*-
"""
Channel Validation Dependency.

Provides a reusable FastAPI dependency for validating channel existence.
This replaces the repeated gemini.get_store() calls across API endpoints.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status

from src.application.ports.channel import ChannelPort, ChannelDTO
from src.infrastructure.di.container import create_channel_port


@dataclass
class ValidatedChannel:
    """Validated channel data returned by the dependency.

    Attributes:
        channel_id: The channel ID (e.g., "fileSearchStores/xxx")
        channel: The channel DTO with full information
    """

    channel_id: str
    channel: ChannelDTO


def get_channel_port() -> ChannelPort:
    """Get the channel port instance.

    This is a separate function to enable easy mocking in tests.

    Returns:
        ChannelPort implementation.
    """
    return create_channel_port()


def get_validated_channel(
    channel_id: str,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
) -> ValidatedChannel:
    """Validate that a channel exists and return its information.

    This is a FastAPI dependency that validates channel existence.
    Use it as a dependency in API endpoints to ensure the channel
    exists before processing the request.

    Args:
        channel_id: The channel ID to validate.
        channel_port: The channel port (injected).

    Returns:
        ValidatedChannel with channel information.

    Raises:
        HTTPException: 404 if channel not found.

    Example:
        @router.get("/channels/{channel_id}/documents")
        def list_documents(
            channel: Annotated[ValidatedChannel, Depends(get_validated_channel)],
        ):
            # channel.channel_id is the validated channel ID
            # channel.channel contains the ChannelDTO
            ...
    """
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )
    return ValidatedChannel(channel_id=channel_id, channel=channel)
