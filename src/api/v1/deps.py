# -*- coding: utf-8 -*-
"""Shared FastAPI dependencies for API v1 routers.

Reduces boilerplate for common patterns like channel validation.
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.application.ports.channel import ChannelPort, ChannelDTO
from src.application.ports.document import DocumentPort
from src.application.ports.persistence import ChannelRepositoryPort
from src.core.database import get_db
from src.modules.workspace.public import (
    create_channel_port,
    create_channel_repository_port,
    create_document_port,
)


def get_channel_port() -> ChannelPort:
    """Get channel port singleton."""
    return create_channel_port()


def get_channel_repo(db: Session = Depends(get_db)) -> ChannelRepositoryPort:
    """Get channel repository port."""
    return create_channel_repository_port(db)


def get_document_port() -> DocumentPort:
    """Get document port singleton."""
    return create_document_port()


@dataclass
class ValidatedChannel:
    """Result of channel validation + touch."""

    channel: ChannelDTO
    channel_id: str


def validate_channel_with_touch(
    channel_id: str,
    channel_port: ChannelPort = Depends(get_channel_port),
    channel_repo: ChannelRepositoryPort = Depends(get_channel_repo),
) -> ValidatedChannel:
    """Validate channel exists and update last accessed time.

    Use as a FastAPI dependency to replace the repeated pattern:
        channel = channel_port.get_channel(channel_id)
        if not channel: raise HTTPException(404)
        channel_repo.touch(channel_id)

    Returns:
        ValidatedChannel with the channel DTO and ID.

    Raises:
        HTTPException(404): If channel not found.
    """
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )
    channel_repo.touch(channel_id)
    return ValidatedChannel(channel=channel, channel_id=channel_id)


def require_channel_with_documents(
    channel_id: str,
    channel_port: ChannelPort = Depends(get_channel_port),
    channel_repo: ChannelRepositoryPort = Depends(get_channel_repo),
    document_port: DocumentPort = Depends(get_document_port),
) -> ValidatedChannel:
    """Validate channel exists, has documents, and update last accessed time.

    Returns:
        ValidatedChannel with the channel DTO and ID.

    Raises:
        HTTPException(404): If channel not found.
        HTTPException(400): If channel has no documents.
    """
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    files = document_port.list_documents(channel_id)
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel has no documents. Upload documents first.",
        )

    channel_repo.touch(channel_id)
    return ValidatedChannel(channel=channel, channel_id=channel_id)
