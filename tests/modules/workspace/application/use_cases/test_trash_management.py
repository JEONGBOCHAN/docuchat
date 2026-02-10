# -*- coding: utf-8 -*-
"""Tests for TrashManagementUseCase."""

from unittest.mock import MagicMock

import pytest

from src.modules.workspace.application.use_cases.trash_management import (
    TrashManagementUseCase,
    TrashItemNotFoundError,
    ExternalDeleteFailedError,
    EmptyTrashResultDTO,
)
from src.shared.kernel.contracts.ports.persistence import (
    TrashItemDTO,
    ChannelMetadataDTO,
    NoteDTO,
)


@pytest.fixture()
def trash_repo():
    return MagicMock()


@pytest.fixture()
def channel_port():
    return MagicMock()


@pytest.fixture()
def use_case(trash_repo, channel_port):
    return TrashManagementUseCase(
        trash_repo=trash_repo,
        channel_port=channel_port,
    )


class TestListItems:
    def test_returns_items(self, use_case, trash_repo):
        items = [MagicMock(spec=TrashItemDTO)]
        trash_repo.get_all_trashed_items.return_value = items
        assert use_case.list_items() == items


class TestRestore:
    def test_restore_channel(self, use_case, trash_repo):
        dto = MagicMock()
        dto.id = 1
        trash_repo.restore_channel.return_value = dto
        result = use_case.restore("channel", 1)
        assert result.id == 1

    def test_restore_note(self, use_case, trash_repo):
        dto = MagicMock()
        dto.id = 2
        trash_repo.restore_note.return_value = dto
        result = use_case.restore("note", 2)
        assert result.id == 2

    def test_restore_channel_not_found(self, use_case, trash_repo):
        trash_repo.restore_channel.return_value = None
        with pytest.raises(TrashItemNotFoundError):
            use_case.restore("channel", 99)

    def test_restore_invalid_type(self, use_case):
        with pytest.raises(ValueError):
            use_case.restore("invalid", 1)


class TestPermanentDelete:
    def test_delete_channel_success(self, use_case, trash_repo, channel_port):
        dto = MagicMock()
        dto.gemini_store_id = "store-1"
        trash_repo.get_trashed_channel_by_db_id.return_value = dto
        channel_port.delete_channel.return_value = True
        trash_repo.permanent_delete_channel.return_value = True

        use_case.permanent_delete("channel", 1)
        channel_port.delete_channel.assert_called_once_with("store-1", force=True)
        trash_repo.permanent_delete_channel.assert_called_once_with(1)

    def test_delete_channel_external_failure(self, use_case, trash_repo, channel_port):
        dto = MagicMock()
        dto.gemini_store_id = "store-1"
        trash_repo.get_trashed_channel_by_db_id.return_value = dto
        channel_port.delete_channel.return_value = False

        with pytest.raises(ExternalDeleteFailedError):
            use_case.permanent_delete("channel", 1)

        # DB delete should NOT have been called
        trash_repo.permanent_delete_channel.assert_not_called()

    def test_delete_channel_not_found(self, use_case, trash_repo):
        trash_repo.get_trashed_channel_by_db_id.return_value = None
        with pytest.raises(TrashItemNotFoundError):
            use_case.permanent_delete("channel", 99)

    def test_delete_note(self, use_case, trash_repo):
        trash_repo.permanent_delete_note.return_value = True
        use_case.permanent_delete("note", 1)
        trash_repo.permanent_delete_note.assert_called_once_with(1)

    def test_delete_note_not_found(self, use_case, trash_repo):
        trash_repo.permanent_delete_note.return_value = False
        with pytest.raises(TrashItemNotFoundError):
            use_case.permanent_delete("note", 99)


class TestEmpty:
    def test_empty_all_succeed(self, use_case, trash_repo, channel_port):
        ch = MagicMock()
        ch.id = 1
        ch.gemini_store_id = "store-1"
        trash_repo.get_all_trashed_channels.return_value = [ch]
        channel_port.delete_channel.return_value = True
        trash_repo.permanent_delete_channel.return_value = True

        note_item = MagicMock()
        note_item.type = "note"
        note_item.id = 2
        trash_repo.get_all_trashed_items.return_value = [note_item]
        trash_repo.permanent_delete_note.return_value = True

        result = use_case.empty()
        assert result.deleted_channels == 1
        assert result.deleted_notes == 1
        assert result.failed_channels == 0

    def test_empty_partial_failure(self, use_case, trash_repo, channel_port):
        ch1 = MagicMock()
        ch1.id = 1
        ch1.gemini_store_id = "store-1"
        ch2 = MagicMock()
        ch2.id = 2
        ch2.gemini_store_id = "store-2"
        trash_repo.get_all_trashed_channels.return_value = [ch1, ch2]
        channel_port.delete_channel.side_effect = [True, False]
        trash_repo.permanent_delete_channel.return_value = True
        trash_repo.get_all_trashed_items.return_value = []

        result = use_case.empty()
        assert result.deleted_channels == 1
        assert result.failed_channels == 1
        assert "failed" in result.message.lower() or "remain" in result.message.lower()


class TestStats:
    def test_returns_stats(self, use_case, trash_repo):
        trash_repo.get_trash_stats.return_value = {"trashed_channels": 1, "trashed_notes": 2, "total": 3}
        result = use_case.stats()
        assert result["total"] == 3
