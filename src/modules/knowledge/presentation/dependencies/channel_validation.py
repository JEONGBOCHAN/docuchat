# -*- coding: utf-8 -*-
"""Channel validation dependencies for FastAPI routers."""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.shared.kernel.contracts.ports.channel import ChannelPort, ChannelDTO
from src.shared.kernel.contracts.ports.document import DocumentPort
from src.shared.kernel.contracts.ports.persistence import ChannelRepositoryPort
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


def get_document_port_factory() -> Callable[[], DocumentPort]:
    """Get document port factory for lazy creation."""
    return create_document_port


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
    document_port_factory: Callable[[], DocumentPort] = Depends(get_document_port_factory),
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

    document_port = document_port_factory()
    files = document_port.list_documents(channel_id)
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel has no documents. Upload documents first.",
        )

    channel_repo.touch(channel_id)
    return ValidatedChannel(channel=channel, channel_id=channel_id)
