# -*- coding: utf-8 -*-
"""
Gemini Channel Adapter.

Implements ChannelPort using Google Gemini File Search Store API.
"""

import logging
import requests
from google import genai
from google.genai.errors import ClientError, ServerError, APIError

from src.shared.kernel.contracts.ports.channel import ChannelPort, ChannelDTO
from src.shared.kernel.contracts.errors.use_case_errors import UpstreamError
from src.core.config import get_settings

logger = logging.getLogger(__name__)


class GeminiChannelAdapter(ChannelPort):
    """ChannelPort implementation using Google Gemini File Search Store.

    This adapter directly interacts with Gemini File Search Store API
    for channel CRUD operations.

    Example:
        adapter = GeminiChannelAdapter()
        channel = adapter.create_channel("My Channel")
        channels = adapter.list_channels()
        adapter.delete_channel(channel.name)
    """

    def __init__(self, client: genai.Client | None = None):
        """Initialize adapter with Gemini client.

        Args:
            client: Optional Gemini client instance.
                   Creates one if not provided.
        """
        settings = get_settings()
        self._api_key = settings.google_api_key
        self._client = client

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def create_channel(self, display_name: str) -> ChannelDTO:
        """Create a new channel (File Search Store).

        Args:
            display_name: Human-readable name for the channel.

        Returns:
            ChannelDTO with channel information.

        Raises:
            Exception: If channel creation fails.
        """
        store = self._get_client().file_search_stores.create(
            config={"display_name": display_name}
        )
        return ChannelDTO(
            name=store.name,
            display_name=display_name,
        )

    def get_channel(self, channel_id: str) -> ChannelDTO | None:
        """Get a channel by ID.

        Args:
            channel_id: The channel name/ID (e.g., "fileSearchStores/xxx").

        Returns:
            ChannelDTO with channel information, or None if not found.

        Raises:
            UpstreamError: If the external API fails for reasons other than 404.
        """
        try:
            store = self._get_client().file_search_stores.get(name=channel_id)
            return ChannelDTO(
                name=store.name,
                display_name=getattr(store, "display_name", ""),
            )
        except ClientError as e:
            if e.code == 404:
                return None
            # Gemini returns 403 PERMISSION_DENIED for non-existent stores
            # with messages like "or it may not exist"
            if e.code == 403 and "not exist" in str(e.message).lower():
                return None
            logger.error("Gemini client error for channel %s: %s (code=%s)", channel_id, e.message, e.code)
            raise UpstreamError("Gemini", str(e.message), status_code=e.code) from e
        except ServerError as e:
            logger.error("Gemini server error for channel %s: %s (code=%s)", channel_id, e.message, e.code)
            raise UpstreamError("Gemini", str(e.message), status_code=e.code) from e
        except APIError as e:
            logger.error("Gemini API error for channel %s: %s", channel_id, e)
            raise UpstreamError("Gemini", str(e), status_code=getattr(e, 'code', None)) from e
        except Exception as e:
            logger.error("Unexpected error accessing channel %s: %s", channel_id, e)
            raise UpstreamError("Gemini", str(e)) from e

    def list_channels(self) -> list[ChannelDTO]:
        """List all channels.

        Returns:
            List of ChannelDTO objects.
        """
        channels = []
        for store in self._get_client().file_search_stores.list():
            channels.append(
                ChannelDTO(
                    name=store.name,
                    display_name=getattr(store, "display_name", ""),
                )
            )
        return channels

    def delete_channel(self, channel_id: str, force: bool = True) -> bool:
        """Delete a channel.

        Uses REST API directly because SDK doesn't support force delete.

        Args:
            channel_id: The channel name/ID.
            force: If True, delete even if channel has documents.

        Returns:
            True if deleted successfully or already deleted.
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/{channel_id}"
        if force:
            url += "?force=true"
        url += f"&key={self._api_key}" if force else f"?key={self._api_key}"

        response = requests.delete(url, timeout=10)
        # Treat 200 (success) and 404 (not found/already deleted) as success
        return response.status_code in (200, 404)
