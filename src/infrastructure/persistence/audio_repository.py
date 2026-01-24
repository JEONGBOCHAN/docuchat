# -*- coding: utf-8 -*-
"""Repository for Audio Overview database operations."""

import json
import uuid
from datetime import datetime, UTC
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.db_models import AudioOverviewDB, ChannelMetadata
from src.models.audio import (
    AudioStatus,
    PodcastScript,
    AudioOverviewResponse,
    AudioOverviewListResponse,
)


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class AudioRepository:
    """Repository for audio overview operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def create_audio_overview(
        self,
        channel_id: int,
        language: str = "ko",
        style: str = "conversational",
    ) -> AudioOverviewDB:
        """Create a new audio overview record.

        Args:
            channel_id: Channel database ID
            language: Language code
            style: Audio style

        Returns:
            Created audio overview database record
        """
        audio = AudioOverviewDB(
            audio_id=str(uuid.uuid4()),
            channel_id=channel_id,
            status=AudioStatus.PENDING.value,
            language=language,
            style=style,
        )
        self.db.add(audio)
        self.db.commit()
        self.db.refresh(audio)
        return audio

    def get_audio_by_id(self, audio_id: str) -> AudioOverviewDB | None:
        """Get audio overview by ID.

        Args:
            audio_id: Audio overview ID

        Returns:
            Audio overview record or None
        """
        stmt = select(AudioOverviewDB).where(AudioOverviewDB.audio_id == audio_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_audios_by_channel(
        self,
        channel_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> list[AudioOverviewDB]:
        """Get all audio overviews for a channel.

        Args:
            channel_id: Channel database ID
            limit: Maximum number of results
            offset: Number of records to skip

        Returns:
            List of audio overview records
        """
        stmt = (
            select(AudioOverviewDB)
            .where(AudioOverviewDB.channel_id == channel_id)
            .order_by(AudioOverviewDB.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_audios_by_channel(self, channel_id: int) -> int:
        """Count audio overviews for a channel.

        Args:
            channel_id: Channel database ID

        Returns:
            Count of audio overviews
        """
        stmt = select(AudioOverviewDB).where(AudioOverviewDB.channel_id == channel_id)
        return len(list(self.db.execute(stmt).scalars().all()))

    def update_status(
        self,
        audio_id: str,
        status: AudioStatus,
        error_message: str | None = None,
    ) -> AudioOverviewDB | None:
        """Update audio overview status.

        Args:
            audio_id: Audio overview ID
            status: New status
            error_message: Error message if failed

        Returns:
            Updated audio overview or None
        """
        audio = self.get_audio_by_id(audio_id)
        if not audio:
            return None

        audio.status = status.value
        if error_message:
            audio.error_message = error_message
        if status == AudioStatus.COMPLETED:
            audio.completed_at = utc_now()

        self.db.commit()
        self.db.refresh(audio)
        return audio

    def update_script(
        self,
        audio_id: str,
        script: PodcastScript,
    ) -> AudioOverviewDB | None:
        """Update audio overview with generated script.

        Args:
            audio_id: Audio overview ID
            script: Generated podcast script

        Returns:
            Updated audio overview or None
        """
        audio = self.get_audio_by_id(audio_id)
        if not audio:
            return None

        audio.title = script.title
        audio.script_json = script.model_dump_json()
        audio.status = AudioStatus.GENERATING_AUDIO.value

        self.db.commit()
        self.db.refresh(audio)
        return audio

    def update_audio_complete(
        self,
        audio_id: str,
        audio_path: str,
        duration_seconds: int,
    ) -> AudioOverviewDB | None:
        """Mark audio generation as complete.

        Args:
            audio_id: Audio overview ID
            audio_path: Path to generated audio file
            duration_seconds: Audio duration in seconds

        Returns:
            Updated audio overview or None
        """
        audio = self.get_audio_by_id(audio_id)
        if not audio:
            return None

        audio.audio_path = audio_path
        audio.duration_seconds = duration_seconds
        audio.status = AudioStatus.COMPLETED.value
        audio.completed_at = utc_now()

        self.db.commit()
        self.db.refresh(audio)
        return audio

    def delete_audio(self, audio_id: str) -> bool:
        """Delete an audio overview record.

        Args:
            audio_id: Audio overview ID

        Returns:
            True if deleted, False if not found
        """
        audio = self.get_audio_by_id(audio_id)
        if not audio:
            return False

        self.db.delete(audio)
        self.db.commit()
        return True

    def get_channel_by_store_id(self, gemini_store_id: str) -> ChannelMetadata | None:
        """Get channel by Gemini store ID.

        Args:
            gemini_store_id: Gemini file search store ID

        Returns:
            Channel metadata or None
        """
        stmt = select(ChannelMetadata).where(
            ChannelMetadata.gemini_store_id == gemini_store_id,
            ChannelMetadata.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()


def to_response(
    audio: AudioOverviewDB,
    gemini_store_id: str,
    base_url: str = "/api/v1",
) -> AudioOverviewResponse:
    """Convert database model to response model.

    Args:
        audio: Database audio overview
        gemini_store_id: Gemini store ID for URL construction
        base_url: API base URL

    Returns:
        Audio overview response
    """
    script = None
    if audio.script_json:
        try:
            script = PodcastScript.model_validate_json(audio.script_json)
        except Exception:
            pass

    audio_url = None
    if audio.audio_path and audio.status == AudioStatus.COMPLETED.value:
        audio_url = f"{base_url}/channels/{gemini_store_id}/audio/{audio.audio_id}/stream"

    return AudioOverviewResponse(
        id=audio.audio_id,
        channel_id=gemini_store_id,
        status=AudioStatus(audio.status),
        title=audio.title,
        duration_seconds=audio.duration_seconds,
        audio_url=audio_url,
        script=script,
        created_at=audio.created_at,
        completed_at=audio.completed_at,
        error=audio.error_message,
    )
