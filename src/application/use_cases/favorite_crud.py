# -*- coding: utf-8 -*-
"""
Favorite CRUD use case.

Extracts favorites orchestration logic from the API router into the application layer.
Handles target validation + favorites CRUD operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC

from src.application.ports.channel import ChannelPort
from src.application.ports.persistence import (
    FavoriteRepositoryPort,
    NoteRepositoryPort,
)
from src.application.use_cases.exceptions import (
    ChannelNotFoundError,
    TargetNotFoundError,
    InvalidTargetError,
)


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass
class FavoriteDetailDTO:
    """Application-layer DTO for favorite details."""

    id: int
    target_type: str
    target_id: str
    display_order: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class FavoriteListResultDTO:
    """Result of listing favorites."""

    favorites: list[FavoriteDetailDTO] = field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Use Case
# ---------------------------------------------------------------------------

class FavoriteCrudUseCase:
    """Orchestrates favorite CRUD operations with target validation."""

    def __init__(
        self,
        channel_port: ChannelPort,
        fav_repo: FavoriteRepositoryPort,
        note_repo: NoteRepositoryPort,
    ):
        self._channel_port = channel_port
        self._fav_repo = fav_repo
        self._note_repo = note_repo

    @staticmethod
    def _to_dto(fav_dto) -> FavoriteDetailDTO:
        """Convert persistence FavoriteDTO to application FavoriteDetailDTO."""
        return FavoriteDetailDTO(
            id=fav_dto.id,
            target_type=fav_dto.target_type,
            target_id=fav_dto.target_id,
            display_order=fav_dto.display_order,
            created_at=fav_dto.created_at,
        )

    # -- Validation -----------------------------------------------------------

    def validate_target(self, target_type: str, target_id: str) -> None:
        """Validate that the favorite target exists.

        Raises:
            ChannelNotFoundError: If channel target not found.
            TargetNotFoundError: If note target not found.
            InvalidTargetError: If target ID format is invalid.
        """
        if target_type == "channel":
            channel = self._channel_port.get_channel(target_id)
            if not channel:
                raise ChannelNotFoundError(target_id)
        elif target_type == "document":
            if not target_id:
                raise InvalidTargetError(
                    "Document ID must not be empty."
                )
        elif target_type == "note":
            try:
                note_id = int(target_id)
                note = self._note_repo.get_by_id(note_id)
                if not note:
                    raise TargetNotFoundError(f"Note not found: {target_id}")
            except ValueError:
                raise InvalidTargetError(
                    "Invalid note ID format. Expected integer."
                )

    # -- Add ------------------------------------------------------------------

    def add(self, target_type: str, target_id: str) -> FavoriteDetailDTO:
        """Validate target and add to favorites.

        Raises:
            ChannelNotFoundError, TargetNotFoundError, InvalidTargetError
        """
        self.validate_target(target_type, target_id)
        favorite = self._fav_repo.add(target_type, target_id)
        return self._to_dto(favorite)

    # -- Remove ---------------------------------------------------------------

    def remove(self, target_type: str, target_id: str) -> bool:
        """Remove from favorites. Returns False if not found."""
        return self._fav_repo.remove(target_type, target_id)

    # -- List -----------------------------------------------------------------

    def list(
        self,
        target_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> FavoriteListResultDTO:
        """List all favorites, optionally filtered by type."""
        favorites = self._fav_repo.list_all(
            target_type=target_type, limit=limit, offset=offset,
        )
        total = self._fav_repo.count(target_type=target_type)

        return FavoriteListResultDTO(
            favorites=[self._to_dto(f) for f in favorites],
            total=total,
        )

    # -- Check ----------------------------------------------------------------

    def check(self, target_type: str, target_id: str) -> bool:
        """Check if a target is favorited."""
        return self._fav_repo.is_favorited(target_type, target_id)

    # -- Reorder --------------------------------------------------------------

    def reorder(self, favorite_ids: list[int]) -> None:
        """Reorder favorites by providing a new order of IDs."""
        self._fav_repo.reorder(favorite_ids)
