# -*- coding: utf-8 -*-
"""
Tests for channel validation dependency.
"""

import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException

from src.shared.kernel.presentation.dependencies.channel_validation import (
    validate_channel_with_touch,
    get_channel_port,
    ValidatedChannel,
)
from src.shared.kernel.contracts.ports.channel import ChannelDTO


class TestGetChannelPort:
    """Tests for get_channel_port function."""

    def test_returns_channel_port(self):
        """Test that get_channel_port returns a ChannelPort instance."""
        with patch('src.shared.kernel.presentation.dependencies.channel_validation.create_channel_port') as mock_create:
            mock_port = Mock()
            mock_create.return_value = mock_port

            result = get_channel_port()

            assert result == mock_port
            mock_create.assert_called_once()


class TestValidateChannelWithTouch:
    """Tests for validate_channel_with_touch dependency."""

    def test_returns_validated_channel_when_exists(self):
        """Test successful channel validation."""
        mock_port = Mock()
        mock_repo = Mock()
        mock_channel = ChannelDTO(
            name="fileSearchStores/test-123",
            display_name="Test Channel"
        )
        mock_port.get_channel.return_value = mock_channel

        result = validate_channel_with_touch("fileSearchStores/test-123", mock_port, mock_repo)

        assert isinstance(result, ValidatedChannel)
        assert result.channel_id == "fileSearchStores/test-123"
        assert result.channel == mock_channel
        mock_port.get_channel.assert_called_once_with("fileSearchStores/test-123")
        mock_repo.touch.assert_called_once_with("fileSearchStores/test-123")

    def test_raises_404_when_channel_not_found(self):
        """Test that 404 is raised when channel doesn't exist."""
        mock_port = Mock()
        mock_repo = Mock()
        mock_port.get_channel.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            validate_channel_with_touch("fileSearchStores/nonexistent", mock_port, mock_repo)

        assert exc_info.value.status_code == 404
        assert "Channel not found" in exc_info.value.detail
        assert "fileSearchStores/nonexistent" in exc_info.value.detail

    def test_passes_channel_id_to_port(self):
        """Test that channel_id is correctly passed to the port."""
        mock_port = Mock()
        mock_repo = Mock()
        mock_channel = ChannelDTO(name="ch-1", display_name="CH1")
        mock_port.get_channel.return_value = mock_channel

        validate_channel_with_touch("special/channel/id", mock_port, mock_repo)

        mock_port.get_channel.assert_called_once_with("special/channel/id")


class TestValidatedChannel:
    """Tests for ValidatedChannel dataclass."""

    def test_validated_channel_creation(self):
        """Test ValidatedChannel can be created with expected fields."""
        channel = ChannelDTO(name="ch-1", display_name="Test")
        validated = ValidatedChannel(channel_id="ch-1", channel=channel)

        assert validated.channel_id == "ch-1"
        assert validated.channel == channel
        assert validated.channel.display_name == "Test"
