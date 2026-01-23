# -*- coding: utf-8 -*-
"""
Channel Port (Interface).

Defines the interface for channel (File Search Store) operations.
This abstracts the Gemini File Search Store CRUD operations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ChannelDTO:
    """Data Transfer Object for channel information."""

    name: str  # The store name/ID (e.g., "fileSearchStores/xxx")
    display_name: str  # Human-readable name


class ChannelPort(ABC):
    """Port for channel (File Search Store) operations.

    This interface abstracts the channel CRUD operations,
    allowing different implementations (Gemini, mock, etc.).
    """

    @abstractmethod
    def create_channel(self, display_name: str) -> ChannelDTO:
        """Create a new channel (File Search Store).

        Args:
            display_name: Human-readable name for the channel.

        Returns:
            ChannelDTO with channel information.

        Raises:
            Exception: If channel creation fails.
        """
        pass

    @abstractmethod
    def get_channel(self, channel_id: str) -> ChannelDTO | None:
        """Get a channel by ID.

        Args:
            channel_id: The channel name/ID (e.g., "fileSearchStores/xxx").

        Returns:
            ChannelDTO with channel information, or None if not found.
        """
        pass

    @abstractmethod
    def list_channels(self) -> list[ChannelDTO]:
        """List all channels.

        Returns:
            List of ChannelDTO objects.
        """
        pass

    @abstractmethod
    def delete_channel(self, channel_id: str, force: bool = True) -> bool:
        """Delete a channel.

        Args:
            channel_id: The channel name/ID.
            force: If True, delete even if channel has documents.

        Returns:
            True if deleted successfully or already deleted.
        """
        pass
