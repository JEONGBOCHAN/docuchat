# -*- coding: utf-8 -*-
"""Tests for scheduler job implementations.

These tests focus on the cleanup_expired_trash function and related
functionality to prevent orphan resources in Gemini cloud.
"""

import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock, patch, Mock

from src.models.db_models import ChannelMetadata, NoteDB
from src.services.trash_repository import TrashRepository


class TestCleanupExpiredTrash:
    """Tests for cleanup_expired_trash scheduler job.

    This test suite verifies the fix for CHA-71:
    - Gemini deletion failures should NOT delete local DB records
    - 404 (not found) should be treated as success
    - Only successfully deleted channels should be removed from DB
    - Notes (no Gemini resources) should be deleted by time-based expiration
    """

    @patch("src.services.scheduler_jobs.GeminiService")
    @patch("src.services.scheduler_jobs.SessionLocal")
    def test_only_deletes_db_on_gemini_success(
        self, mock_session_local, mock_gemini_class
    ):
        """Test that DB deletion only happens when Gemini deletion succeeds.

        This is the main bug fix test for CHA-71.
        """
        from src.services.scheduler_jobs import cleanup_expired_trash

        # Setup mock DB session
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        # Create mock expired channels
        cutoff = datetime.now(UTC) - timedelta(days=30)
        channel1 = MagicMock(spec=ChannelMetadata)
        channel1.id = 1
        channel1.gemini_store_id = "fileSearchStores/success-channel"

        channel2 = MagicMock(spec=ChannelMetadata)
        channel2.id = 2
        channel2.gemini_store_id = "fileSearchStores/failed-channel"

        channel3 = MagicMock(spec=ChannelMetadata)
        channel3.id = 3
        channel3.gemini_store_id = "fileSearchStores/success-channel-2"

        mock_db.query.return_value.filter.return_value.all.return_value = [
            channel1, channel2, channel3
        ]

        # Setup mock Gemini service
        mock_gemini = MagicMock()
        mock_gemini_class.return_value = mock_gemini

        # Simulate: channel1 and channel3 succeed, channel2 fails
        def mock_delete_store(store_id, force=True):
            if store_id == "fileSearchStores/failed-channel":
                return False  # Gemini deletion failed
            return True  # Success

        mock_gemini.delete_store.side_effect = mock_delete_store

        # Setup mock TrashRepository
        with patch("src.services.scheduler_jobs.TrashRepository") as mock_trash_repo_class:
            mock_trash_repo = MagicMock()
            mock_trash_repo_class.return_value = mock_trash_repo
            mock_trash_repo.cleanup_specific_channels.return_value = 2
            mock_trash_repo.cleanup_expired_notes.return_value = 0

            # Run the cleanup
            result = cleanup_expired_trash(retention_days=30)

            # Verify only successful channel IDs were passed to DB deletion
            mock_trash_repo.cleanup_specific_channels.assert_called_once()
            deleted_ids = mock_trash_repo.cleanup_specific_channels.call_args[0][0]

            # Should only contain channel1.id and channel3.id (successful deletions)
            assert 1 in deleted_ids
            assert 2 not in deleted_ids  # Failed channel should NOT be in the list
            assert 3 in deleted_ids

            # Verify result counts
            assert result["gemini_deleted"] == 2
            assert result["gemini_failed"] == 1
            assert result["deleted_channels"] == 2

    @patch("src.services.scheduler_jobs.GeminiService")
    @patch("src.services.scheduler_jobs.SessionLocal")
    def test_gemini_exception_does_not_delete_db(
        self, mock_session_local, mock_gemini_class
    ):
        """Test that exceptions during Gemini deletion prevent DB deletion."""
        from src.services.scheduler_jobs import cleanup_expired_trash

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        # Create mock expired channel
        channel = MagicMock(spec=ChannelMetadata)
        channel.id = 1
        channel.gemini_store_id = "fileSearchStores/exception-channel"

        mock_db.query.return_value.filter.return_value.all.return_value = [channel]

        # Setup Gemini to throw exception
        mock_gemini = MagicMock()
        mock_gemini_class.return_value = mock_gemini
        mock_gemini.delete_store.side_effect = Exception("Network error")

        with patch("src.services.scheduler_jobs.TrashRepository") as mock_trash_repo_class:
            mock_trash_repo = MagicMock()
            mock_trash_repo_class.return_value = mock_trash_repo
            mock_trash_repo.cleanup_specific_channels.return_value = 0
            mock_trash_repo.cleanup_expired_notes.return_value = 0

            result = cleanup_expired_trash(retention_days=30)

            # Should be called with empty list (no successful deletions)
            mock_trash_repo.cleanup_specific_channels.assert_called_once_with([])
            assert result["gemini_deleted"] == 0
            assert result["gemini_failed"] == 1
            assert result["deleted_channels"] == 0

    @patch("src.services.scheduler_jobs.GeminiService")
    @patch("src.services.scheduler_jobs.SessionLocal")
    def test_notes_deleted_independently(
        self, mock_session_local, mock_gemini_class
    ):
        """Test that notes are deleted by time-based expiration (no Gemini resources)."""
        from src.services.scheduler_jobs import cleanup_expired_trash

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        # No expired channels
        mock_db.query.return_value.filter.return_value.all.return_value = []

        mock_gemini = MagicMock()
        mock_gemini_class.return_value = mock_gemini

        with patch("src.services.scheduler_jobs.TrashRepository") as mock_trash_repo_class:
            mock_trash_repo = MagicMock()
            mock_trash_repo_class.return_value = mock_trash_repo
            mock_trash_repo.cleanup_specific_channels.return_value = 0
            mock_trash_repo.cleanup_expired_notes.return_value = 5  # 5 notes deleted

            result = cleanup_expired_trash(retention_days=30)

            # Notes should be deleted regardless of Gemini
            mock_trash_repo.cleanup_expired_notes.assert_called_once_with(30)
            assert result["deleted_notes"] == 5

    @patch("src.services.scheduler_jobs.GeminiService")
    @patch("src.services.scheduler_jobs.SessionLocal")
    def test_empty_expired_channels(
        self, mock_session_local, mock_gemini_class
    ):
        """Test cleanup when there are no expired channels."""
        from src.services.scheduler_jobs import cleanup_expired_trash

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = []

        mock_gemini = MagicMock()
        mock_gemini_class.return_value = mock_gemini

        with patch("src.services.scheduler_jobs.TrashRepository") as mock_trash_repo_class:
            mock_trash_repo = MagicMock()
            mock_trash_repo_class.return_value = mock_trash_repo
            mock_trash_repo.cleanup_specific_channels.return_value = 0
            mock_trash_repo.cleanup_expired_notes.return_value = 0

            result = cleanup_expired_trash(retention_days=30)

            mock_trash_repo.cleanup_specific_channels.assert_called_once_with([])
            assert result["deleted_channels"] == 0
            assert result["gemini_deleted"] == 0
            assert result["gemini_failed"] == 0


class TestGeminiDeleteStore:
    """Tests for GeminiService.delete_store method.

    Verifies that 404 (not found) is treated as success.
    """

    @patch("src.services.gemini.requests.delete")
    def test_delete_store_success_200(self, mock_delete):
        """Test that HTTP 200 returns True (success)."""
        from src.services.gemini import GeminiService

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_delete.return_value = mock_response

        with patch("src.services.gemini.get_settings") as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            service = GeminiService()

            result = service.delete_store("fileSearchStores/test-store")

            assert result is True

    @patch("src.services.gemini.requests.delete")
    def test_delete_store_success_404_not_found(self, mock_delete):
        """Test that HTTP 404 (not found) is treated as success.

        This is critical for the orphan resource bug fix.
        If a resource is already deleted, we should treat it as success
        and proceed with local DB deletion.
        """
        from src.services.gemini import GeminiService

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_delete.return_value = mock_response

        with patch("src.services.gemini.get_settings") as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            service = GeminiService()

            result = service.delete_store("fileSearchStores/already-deleted-store")

            # 404 should be treated as success
            assert result is True

    @patch("src.services.gemini.requests.delete")
    def test_delete_store_failure_500(self, mock_delete):
        """Test that HTTP 500 returns False (failure)."""
        from src.services.gemini import GeminiService

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_delete.return_value = mock_response

        with patch("src.services.gemini.get_settings") as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            service = GeminiService()

            result = service.delete_store("fileSearchStores/error-store")

            assert result is False

    @patch("src.services.gemini.requests.delete")
    def test_delete_store_failure_403(self, mock_delete):
        """Test that HTTP 403 (forbidden) returns False (failure)."""
        from src.services.gemini import GeminiService

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_delete.return_value = mock_response

        with patch("src.services.gemini.get_settings") as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            service = GeminiService()

            result = service.delete_store("fileSearchStores/forbidden-store")

            assert result is False


class TestTrashRepositoryCleanupMethods:
    """Tests for TrashRepository cleanup methods."""

    def test_cleanup_specific_channels_success(self, test_db):
        """Test cleanup_specific_channels deletes only specified channels."""
        # Create multiple trashed channels
        channel1 = ChannelMetadata(
            gemini_store_id="fileSearchStores/channel-1",
            name="Channel 1",
            deleted_at=datetime.now(UTC) - timedelta(days=35),
        )
        channel2 = ChannelMetadata(
            gemini_store_id="fileSearchStores/channel-2",
            name="Channel 2",
            deleted_at=datetime.now(UTC) - timedelta(days=35),
        )
        channel3 = ChannelMetadata(
            gemini_store_id="fileSearchStores/channel-3",
            name="Channel 3",
            deleted_at=datetime.now(UTC) - timedelta(days=35),
        )
        test_db.add_all([channel1, channel2, channel3])
        test_db.commit()
        test_db.refresh(channel1)
        test_db.refresh(channel2)
        test_db.refresh(channel3)

        # Store IDs before deletion
        channel1_id = channel1.id
        channel2_id = channel2.id
        channel3_id = channel3.id

        # Only delete channel1 and channel3
        repo = TrashRepository(test_db)
        deleted_count = repo.cleanup_specific_channels([channel1_id, channel3_id])

        assert deleted_count == 2

        # Verify channel2 still exists (using stored ID)
        remaining = test_db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel2_id
        ).first()
        assert remaining is not None
        assert remaining.name == "Channel 2"

        # Verify channel1 and channel3 are deleted (using stored IDs)
        deleted1 = test_db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel1_id
        ).first()
        deleted3 = test_db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel3_id
        ).first()
        assert deleted1 is None
        assert deleted3 is None

    def test_cleanup_specific_channels_empty_list(self, test_db):
        """Test cleanup_specific_channels with empty list."""
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/channel",
            name="Channel",
            deleted_at=datetime.now(UTC) - timedelta(days=35),
        )
        test_db.add(channel)
        test_db.commit()
        test_db.refresh(channel)

        repo = TrashRepository(test_db)
        deleted_count = repo.cleanup_specific_channels([])

        assert deleted_count == 0

        # Channel should still exist
        remaining = test_db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel.id
        ).first()
        assert remaining is not None

    def test_cleanup_specific_channels_only_trashed(self, test_db):
        """Test cleanup_specific_channels only deletes trashed channels."""
        # Create an active channel (not in trash)
        active_channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/active-channel",
            name="Active Channel",
            deleted_at=None,  # Not in trash
        )
        test_db.add(active_channel)
        test_db.commit()
        test_db.refresh(active_channel)

        repo = TrashRepository(test_db)
        deleted_count = repo.cleanup_specific_channels([active_channel.id])

        # Should not delete because it's not in trash
        assert deleted_count == 0

        # Channel should still exist
        remaining = test_db.query(ChannelMetadata).filter(
            ChannelMetadata.id == active_channel.id
        ).first()
        assert remaining is not None

    def test_cleanup_expired_notes(self, test_db):
        """Test cleanup_expired_notes deletes notes by time-based expiration."""
        # Create a channel for notes
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/channel",
            name="Channel",
        )
        test_db.add(channel)
        test_db.commit()

        # Create expired notes (older than 30 days)
        expired_note1 = NoteDB(
            channel_id=channel.id,
            title="Expired Note 1",
            content="Content",
            deleted_at=datetime.now(UTC) - timedelta(days=35),
        )
        expired_note2 = NoteDB(
            channel_id=channel.id,
            title="Expired Note 2",
            content="Content",
            deleted_at=datetime.now(UTC) - timedelta(days=40),
        )

        # Create non-expired note (less than 30 days)
        recent_note = NoteDB(
            channel_id=channel.id,
            title="Recent Note",
            content="Content",
            deleted_at=datetime.now(UTC) - timedelta(days=15),
        )

        test_db.add_all([expired_note1, expired_note2, recent_note])
        test_db.commit()

        repo = TrashRepository(test_db)
        deleted_count = repo.cleanup_expired_notes(retention_days=30)

        assert deleted_count == 2

        # Recent note should still exist
        remaining = test_db.query(NoteDB).filter(NoteDB.deleted_at.isnot(None)).all()
        assert len(remaining) == 1
        assert remaining[0].title == "Recent Note"


class TestIntegrationOrphanResourcePrevention:
    """Integration tests for orphan resource prevention.

    These tests verify the complete flow of the bug fix.
    """

    @patch("src.services.scheduler_jobs.GeminiService")
    @patch("src.services.scheduler_jobs.SessionLocal")
    def test_mixed_success_failure_scenario(
        self, mock_session_local, mock_gemini_class
    ):
        """Test realistic scenario with mixed Gemini deletion results.

        Scenario:
        - 5 expired channels in trash
        - 3 succeed in Gemini deletion (2 with 200, 1 with 404)
        - 2 fail in Gemini deletion (1 with 500, 1 with exception)
        - Only 3 should be deleted from local DB
        """
        from src.services.scheduler_jobs import cleanup_expired_trash

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        # Create 5 expired channels
        channels = []
        for i in range(5):
            channel = MagicMock(spec=ChannelMetadata)
            channel.id = i + 1
            channel.gemini_store_id = f"fileSearchStores/channel-{i + 1}"
            channels.append(channel)

        mock_db.query.return_value.filter.return_value.all.return_value = channels

        mock_gemini = MagicMock()
        mock_gemini_class.return_value = mock_gemini

        # Define behavior:
        # channel-1: success (200)
        # channel-2: success (404 - already deleted)
        # channel-3: failure (500)
        # channel-4: success (200)
        # channel-5: exception
        call_count = [0]
        def mock_delete_store(store_id, force=True):
            call_count[0] += 1
            if store_id == "fileSearchStores/channel-3":
                return False  # 500 error
            if store_id == "fileSearchStores/channel-5":
                raise Exception("Connection timeout")
            return True  # 200 or 404

        mock_gemini.delete_store.side_effect = mock_delete_store

        with patch("src.services.scheduler_jobs.TrashRepository") as mock_trash_repo_class:
            mock_trash_repo = MagicMock()
            mock_trash_repo_class.return_value = mock_trash_repo
            mock_trash_repo.cleanup_specific_channels.return_value = 3
            mock_trash_repo.cleanup_expired_notes.return_value = 2

            result = cleanup_expired_trash(retention_days=30)

            # Verify only successful channel IDs were passed
            deleted_ids = mock_trash_repo.cleanup_specific_channels.call_args[0][0]
            assert sorted(deleted_ids) == [1, 2, 4]  # channel-1, 2, 4
            assert 3 not in deleted_ids  # Failed
            assert 5 not in deleted_ids  # Exception

            # Verify counts
            assert result["gemini_deleted"] == 3
            assert result["gemini_failed"] == 2
            assert result["deleted_channels"] == 3
            assert result["deleted_notes"] == 2
