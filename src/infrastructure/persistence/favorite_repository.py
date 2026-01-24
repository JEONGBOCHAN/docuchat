# -*- coding: utf-8 -*-
"""Favorite repository for database operations."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.db_models import FavoriteDB
from src.models.favorite import TargetType


class FavoriteRepository:
    """Repository for favorite operations."""

    def __init__(self, db: Session):
        self.db = db

    def add(self, target_type: TargetType, target_id: str) -> FavoriteDB:
        """Add a new favorite.

        Args:
            target_type: Type of the target (channel, document, note)
            target_id: ID of the target

        Returns:
            Created favorite
        """
        # Check if already favorited
        existing = self.get(target_type, target_id)
        if existing:
            return existing

        # Get max display_order for this type
        max_order = (
            self.db.query(func.max(FavoriteDB.display_order))
            .filter(FavoriteDB.target_type == target_type.value)
            .scalar()
        )
        new_order = (max_order or 0) + 1

        favorite = FavoriteDB(
            target_type=target_type.value,
            target_id=target_id,
            display_order=new_order,
        )
        self.db.add(favorite)
        self.db.commit()
        self.db.refresh(favorite)
        return favorite

    def remove(self, target_type: TargetType, target_id: str) -> bool:
        """Remove a favorite.

        Args:
            target_type: Type of the target
            target_id: ID of the target

        Returns:
            True if removed, False if not found
        """
        favorite = self.get(target_type, target_id)
        if not favorite:
            return False

        self.db.delete(favorite)
        self.db.commit()
        return True

    def get(self, target_type: TargetType, target_id: str) -> FavoriteDB | None:
        """Get a specific favorite.

        Args:
            target_type: Type of the target
            target_id: ID of the target

        Returns:
            Favorite if found, None otherwise
        """
        return (
            self.db.query(FavoriteDB)
            .filter(
                FavoriteDB.target_type == target_type.value,
                FavoriteDB.target_id == target_id,
            )
            .first()
        )

    def get_by_id(self, favorite_id: int) -> FavoriteDB | None:
        """Get a favorite by ID.

        Args:
            favorite_id: ID of the favorite

        Returns:
            Favorite if found, None otherwise
        """
        return self.db.query(FavoriteDB).filter(FavoriteDB.id == favorite_id).first()

    def list_all(
        self, target_type: TargetType | None = None, limit: int = 100, offset: int = 0
    ) -> list[FavoriteDB]:
        """List favorites.

        Args:
            target_type: Optional filter by target type
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of favorites ordered by display_order
        """
        query = self.db.query(FavoriteDB)

        if target_type:
            query = query.filter(FavoriteDB.target_type == target_type.value)

        return (
            query.order_by(FavoriteDB.display_order)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count(self, target_type: TargetType | None = None) -> int:
        """Count favorites.

        Args:
            target_type: Optional filter by target type

        Returns:
            Number of favorites
        """
        query = self.db.query(func.count(FavoriteDB.id))

        if target_type:
            query = query.filter(FavoriteDB.target_type == target_type.value)

        return query.scalar() or 0

    def is_favorited(self, target_type: TargetType, target_id: str) -> bool:
        """Check if a target is favorited.

        Args:
            target_type: Type of the target
            target_id: ID of the target

        Returns:
            True if favorited, False otherwise
        """
        return self.get(target_type, target_id) is not None

    def get_favorited_ids(self, target_type: TargetType) -> set[str]:
        """Get all favorited target IDs of a given type.

        Args:
            target_type: Type of the target

        Returns:
            Set of favorited target IDs
        """
        favorites = (
            self.db.query(FavoriteDB.target_id)
            .filter(FavoriteDB.target_type == target_type.value)
            .all()
        )
        return {f.target_id for f in favorites}

    def reorder(self, favorite_ids: list[int]) -> bool:
        """Reorder favorites.

        Args:
            favorite_ids: Ordered list of favorite IDs

        Returns:
            True if successful
        """
        for order, fav_id in enumerate(favorite_ids, start=1):
            favorite = self.get_by_id(fav_id)
            if favorite:
                favorite.display_order = order

        self.db.commit()
        return True

    def move_to_top(self, target_type: TargetType, target_id: str) -> FavoriteDB | None:
        """Move a favorite to the top (lowest display_order).

        Args:
            target_type: Type of the target
            target_id: ID of the target

        Returns:
            Updated favorite if found
        """
        favorite = self.get(target_type, target_id)
        if not favorite:
            return None

        # Get min display_order
        min_order = (
            self.db.query(func.min(FavoriteDB.display_order))
            .filter(FavoriteDB.target_type == target_type.value)
            .scalar()
        )

        # Set to one less than minimum
        favorite.display_order = (min_order or 1) - 1
        self.db.commit()
        self.db.refresh(favorite)
        return favorite
