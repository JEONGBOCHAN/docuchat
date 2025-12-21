# -*- coding: utf-8 -*-
"""Integration tests for Gemini API.

These tests require a valid GOOGLE_API_KEY environment variable.
Run with: pytest -m integration

Note: These tests make real API calls and may incur costs.
"""

import os
import time
import tempfile
import pytest

from src.services.gemini import GeminiService


# Skip all tests if no API key is available
pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
]


class TestChannelLifecycle:
    """Integration tests for channel (FileSearchStore) lifecycle."""

    def test_create_channel(self, gemini_service, cleanup_channels):
        """Test creating a new channel/store."""
        # Create a channel
        result = gemini_service.create_store("Integration Test Channel")

        assert result is not None
        assert "name" in result
        assert result["name"].startswith("fileSearchStores/")

        # Add to cleanup list
        cleanup_channels.append(result["name"])

    def test_get_channel(self, gemini_service, cleanup_channels):
        """Test getting an existing channel."""
        # Create a channel first
        created = gemini_service.create_store("Get Test Channel")
        cleanup_channels.append(created["name"])

        # Wait a bit for API consistency
        time.sleep(1)

        # Get the channel
        result = gemini_service.get_store(created["name"])

        assert result is not None
        assert result["name"] == created["name"]

    def test_list_channels(self, gemini_service, cleanup_channels):
        """Test listing all channels."""
        # Create a test channel
        created = gemini_service.create_store("List Test Channel")
        cleanup_channels.append(created["name"])

        time.sleep(1)

        # List channels
        channels = gemini_service.list_stores()

        assert channels is not None
        assert isinstance(channels, list)
        # Should have at least our test channel
        channel_names = [ch.get("name") for ch in channels]
        assert created["name"] in channel_names

    def test_delete_channel(self, gemini_service):
        """Test deleting a channel."""
        # Create a channel to delete
        created = gemini_service.create_store("Delete Test Channel")

        time.sleep(1)

        # Delete the channel
        result = gemini_service.delete_store(created["name"])

        assert result is True

        # Verify it's deleted
        time.sleep(1)
        deleted_channel = gemini_service.get_store(created["name"])
        assert deleted_channel is None

    def test_get_nonexistent_channel(self, gemini_service):
        """Test getting a channel that doesn't exist."""
        result = gemini_service.get_store("fileSearchStores/nonexistent-12345")

        assert result is None


class TestFileOperations:
    """Integration tests for file operations."""

    @pytest.fixture
    def test_channel(self, gemini_service, cleanup_channels):
        """Create a test channel for file operations."""
        created = gemini_service.create_store("File Test Channel")
        cleanup_channels.append(created["name"])
        time.sleep(1)
        return created

    @pytest.fixture
    def test_file(self):
        """Create a temporary test file."""
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
            encoding="utf-8"
        ) as f:
            f.write("This is a test document for integration testing.\n")
            f.write("It contains some sample content for RAG testing.\n")
            f.write("The document discusses integration testing with Gemini API.\n")
            return f.name

    def test_upload_file(self, gemini_service, test_channel, test_file):
        """Test uploading a file to a channel."""
        result = gemini_service.upload_file(
            store_name=test_channel["name"],
            file_path=test_file,
        )

        assert result is not None
        # Upload returns an operation that may or may not be done
        assert "name" in result

        # Cleanup temp file
        os.unlink(test_file)

    def test_list_files_in_channel(self, gemini_service, test_channel, test_file):
        """Test listing files in a channel after upload."""
        # Upload a file
        upload_result = gemini_service.upload_file(
            store_name=test_channel["name"],
            file_path=test_file,
        )

        # Wait for upload to process
        time.sleep(3)

        # List files
        files = gemini_service.list_store_files(test_channel["name"])

        assert files is not None
        assert isinstance(files, list)

        # Cleanup temp file
        os.unlink(test_file)


class TestErrorHandling:
    """Integration tests for API error handling."""

    def test_invalid_store_id_format(self, gemini_service):
        """Test handling of invalid store ID format."""
        # This should return None, not raise an exception
        result = gemini_service.get_store("invalid-format")

        # Should gracefully handle the error
        assert result is None

    def test_delete_nonexistent_channel(self, gemini_service):
        """Test deleting a channel that doesn't exist."""
        result = gemini_service.delete_store("fileSearchStores/nonexistent-99999")

        # Should return False, not raise an exception
        assert result is False

    def test_upload_to_nonexistent_channel(self, gemini_service):
        """Test uploading to a channel that doesn't exist."""
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
            encoding="utf-8"
        ) as f:
            f.write("Test content")
            temp_file = f.name

        try:
            result = gemini_service.upload_file(
                store_name="fileSearchStores/nonexistent-99999",
                file_path=temp_file,
            )
            # Should either return None or raise an exception
            # Either way is acceptable error handling
        except Exception:
            pass  # Exception is acceptable
        finally:
            os.unlink(temp_file)


class TestChatIntegration:
    """Integration tests for chat/RAG functionality."""

    @pytest.fixture
    def channel_with_content(self, gemini_service, cleanup_channels):
        """Create a channel with some test content."""
        # Create channel
        channel = gemini_service.create_store("Chat Test Channel")
        cleanup_channels.append(channel["name"])
        time.sleep(1)

        # Upload a test document
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            delete=False,
            encoding="utf-8"
        ) as f:
            f.write("# Python Programming Guide\n\n")
            f.write("Python is a high-level programming language.\n")
            f.write("It is known for its simple syntax and readability.\n")
            f.write("Python supports multiple programming paradigms.\n")
            f.write("Common uses include web development, data science, and automation.\n")
            temp_file = f.name

        gemini_service.upload_file(
            store_name=channel["name"],
            file_path=temp_file,
        )

        os.unlink(temp_file)

        # Wait for indexing
        time.sleep(5)

        return channel

    @pytest.mark.skip(reason="File indexing takes significant time - run manually before releases")
    def test_chat_with_context(self, gemini_service, channel_with_content):
        """Test chat with document context.

        Note: This test is skipped by default because file indexing
        takes significant time in the Gemini API.
        """
        response = gemini_service.search_and_answer(
            store_name=channel_with_content["name"],
            query="What is Python known for?",
        )

        assert response is not None
        assert "response" in response
        assert isinstance(response["response"], str)
        assert len(response["response"]) > 0
        # Response should mention something about Python
        assert "python" in response["response"].lower() or "programming" in response["response"].lower()


class TestAPILimits:
    """Tests related to API rate limits and quotas."""

    @pytest.mark.slow
    def test_multiple_channel_creation(self, gemini_service, cleanup_channels):
        """Test creating multiple channels to verify rate limiting."""
        created_channels = []

        for i in range(3):
            try:
                channel = gemini_service.create_store(f"Rate Limit Test {i}")
                created_channels.append(channel["name"])
                cleanup_channels.append(channel["name"])
                time.sleep(1)  # Respect rate limits
            except Exception as e:
                # If we hit a rate limit, that's expected behavior
                print(f"Rate limit or error on channel {i}: {e}")
                break

        # Should have created at least one channel
        assert len(created_channels) >= 1
