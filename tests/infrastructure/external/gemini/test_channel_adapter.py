# -*- coding: utf-8 -*-
"""
Tests for GeminiChannelAdapter.

Tests the Gemini adapter implementation for channel (File Search Store) operations.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.infrastructure.external.gemini.channel import GeminiChannelAdapter
from src.application.ports.channel import ChannelDTO


class TestGeminiChannelAdapter:
    """Tests for GeminiChannelAdapter."""

    def _create_mock_store(self, name: str, display_name: str = ""):
        """Create a mock File Search Store object."""
        mock_store = Mock()
        mock_store.name = name
        mock_store.display_name = display_name
        return mock_store

    def _create_mock_client(self):
        """Create a mock Gemini client."""
        mock_client = Mock()
        return mock_client

    def test_create_channel_success(self):
        """Test successful channel creation."""
        mock_client = self._create_mock_client()
        mock_store = self._create_mock_store(
            "fileSearchStores/test-id-123",
            "Test Channel"
        )
        mock_client.file_search_stores.create.return_value = mock_store

        adapter = GeminiChannelAdapter(client=mock_client)
        result = adapter.create_channel("Test Channel")

        assert isinstance(result, ChannelDTO)
        assert result.name == "fileSearchStores/test-id-123"
        assert result.display_name == "Test Channel"
        mock_client.file_search_stores.create.assert_called_once_with(
            config={"display_name": "Test Channel"}
        )

    def test_get_channel_success(self):
        """Test successful channel retrieval."""
        mock_client = self._create_mock_client()
        mock_store = self._create_mock_store(
            "fileSearchStores/test-id-123",
            "My Channel"
        )
        mock_client.file_search_stores.get.return_value = mock_store

        adapter = GeminiChannelAdapter(client=mock_client)
        result = adapter.get_channel("fileSearchStores/test-id-123")

        assert result is not None
        assert isinstance(result, ChannelDTO)
        assert result.name == "fileSearchStores/test-id-123"
        assert result.display_name == "My Channel"
        mock_client.file_search_stores.get.assert_called_once_with(
            name="fileSearchStores/test-id-123"
        )

    def test_get_channel_not_found(self):
        """Test channel retrieval when not found."""
        mock_client = self._create_mock_client()
        mock_client.file_search_stores.get.side_effect = Exception("Not found")

        adapter = GeminiChannelAdapter(client=mock_client)
        result = adapter.get_channel("fileSearchStores/nonexistent")

        assert result is None

    def test_get_channel_missing_display_name(self):
        """Test channel retrieval when display_name is missing."""
        mock_client = self._create_mock_client()
        mock_store = Mock()
        mock_store.name = "fileSearchStores/test-id"
        # Simulate missing display_name attribute
        del mock_store.display_name
        mock_client.file_search_stores.get.return_value = mock_store

        adapter = GeminiChannelAdapter(client=mock_client)
        result = adapter.get_channel("fileSearchStores/test-id")

        assert result is not None
        assert result.display_name == ""

    def test_list_channels_success(self):
        """Test successful channel listing."""
        mock_client = self._create_mock_client()
        mock_stores = [
            self._create_mock_store("fileSearchStores/1", "Channel 1"),
            self._create_mock_store("fileSearchStores/2", "Channel 2"),
            self._create_mock_store("fileSearchStores/3", "Channel 3"),
        ]
        mock_client.file_search_stores.list.return_value = mock_stores

        adapter = GeminiChannelAdapter(client=mock_client)
        result = adapter.list_channels()

        assert len(result) == 3
        assert all(isinstance(ch, ChannelDTO) for ch in result)
        assert result[0].name == "fileSearchStores/1"
        assert result[0].display_name == "Channel 1"
        assert result[1].name == "fileSearchStores/2"
        assert result[2].name == "fileSearchStores/3"

    def test_list_channels_empty(self):
        """Test channel listing when no channels exist."""
        mock_client = self._create_mock_client()
        mock_client.file_search_stores.list.return_value = []

        adapter = GeminiChannelAdapter(client=mock_client)
        result = adapter.list_channels()

        assert result == []

    def test_list_channels_missing_display_name(self):
        """Test channel listing when some channels have missing display_name."""
        mock_client = self._create_mock_client()
        mock_store = Mock()
        mock_store.name = "fileSearchStores/1"
        del mock_store.display_name
        mock_client.file_search_stores.list.return_value = [mock_store]

        adapter = GeminiChannelAdapter(client=mock_client)
        result = adapter.list_channels()

        assert len(result) == 1
        assert result[0].display_name == ""

    @patch('src.infrastructure.external.gemini.channel.requests.delete')
    def test_delete_channel_success(self, mock_delete):
        """Test successful channel deletion."""
        mock_delete.return_value.status_code = 200
        mock_client = self._create_mock_client()

        with patch('src.infrastructure.external.gemini.channel.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            adapter = GeminiChannelAdapter(client=mock_client)
            result = adapter.delete_channel("fileSearchStores/test-id")

        assert result is True
        mock_delete.assert_called_once()
        call_url = mock_delete.call_args[0][0]
        assert "fileSearchStores/test-id" in call_url
        assert "force=true" in call_url

    @patch('src.infrastructure.external.gemini.channel.requests.delete')
    def test_delete_channel_already_deleted(self, mock_delete):
        """Test channel deletion when already deleted (404)."""
        mock_delete.return_value.status_code = 404
        mock_client = self._create_mock_client()

        with patch('src.infrastructure.external.gemini.channel.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            adapter = GeminiChannelAdapter(client=mock_client)
            result = adapter.delete_channel("fileSearchStores/nonexistent")

        assert result is True

    @patch('src.infrastructure.external.gemini.channel.requests.delete')
    def test_delete_channel_failure(self, mock_delete):
        """Test channel deletion failure (500 error)."""
        mock_delete.return_value.status_code = 500
        mock_client = self._create_mock_client()

        with patch('src.infrastructure.external.gemini.channel.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            adapter = GeminiChannelAdapter(client=mock_client)
            result = adapter.delete_channel("fileSearchStores/test-id")

        assert result is False

    @patch('src.infrastructure.external.gemini.channel.requests.delete')
    def test_delete_channel_without_force(self, mock_delete):
        """Test channel deletion without force flag."""
        mock_delete.return_value.status_code = 200
        mock_client = self._create_mock_client()

        with patch('src.infrastructure.external.gemini.channel.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            adapter = GeminiChannelAdapter(client=mock_client)
            result = adapter.delete_channel("fileSearchStores/test-id", force=False)

        assert result is True
        call_url = mock_delete.call_args[0][0]
        assert "force=true" not in call_url

    def test_adapter_creates_client_if_not_provided(self):
        """Test that adapter creates Gemini client if not provided."""
        with patch('src.infrastructure.external.gemini.channel.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            with patch('src.infrastructure.external.gemini.channel.genai.Client') as mock_client_class:
                adapter = GeminiChannelAdapter()
                mock_client_class.assert_called_once_with(api_key="test-api-key")


class TestGeminiChannelAdapterIntegration:
    """Integration tests for GeminiChannelAdapter (mocked)."""

    def test_full_crud_workflow(self):
        """Test full CRUD workflow."""
        mock_client = Mock()

        # Create
        mock_created_store = Mock()
        mock_created_store.name = "fileSearchStores/new-channel-123"
        mock_created_store.display_name = "New Channel"
        mock_client.file_search_stores.create.return_value = mock_created_store

        # Get
        mock_client.file_search_stores.get.return_value = mock_created_store

        # List
        mock_client.file_search_stores.list.return_value = [mock_created_store]

        with patch('src.infrastructure.external.gemini.channel.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            adapter = GeminiChannelAdapter(client=mock_client)

            # Create channel
            created = adapter.create_channel("New Channel")
            assert created.name == "fileSearchStores/new-channel-123"

            # Get channel
            retrieved = adapter.get_channel(created.name)
            assert retrieved is not None
            assert retrieved.name == created.name

            # List channels
            channels = adapter.list_channels()
            assert len(channels) == 1
            assert channels[0].name == created.name

            # Delete channel
            with patch('src.infrastructure.external.gemini.channel.requests.delete') as mock_delete:
                mock_delete.return_value.status_code = 200
                deleted = adapter.delete_channel(created.name)
                assert deleted is True
