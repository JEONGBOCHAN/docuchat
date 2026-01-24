# -*- coding: utf-8 -*-
"""Audio Overview (Podcast) API endpoints."""

import asyncio
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.models.audio import (
    AudioStatus,
    VoiceType,
    PodcastScript,
    DialogueLine,
    GenerateAudioRequest,
    AudioOverviewResponse,
    AudioOverviewListResponse,
    ScriptOnlyResponse,
)
from src.application.ports.channel import ChannelPort
from src.infrastructure.di.container import create_channel_port, create_generate_podcast_script_use_case
from src.services.tts_service import TTSService, get_tts_service
from src.infrastructure.persistence.audio_repository import AudioRepository, to_response
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.infrastructure.persistence.channel_repository import ChannelRepository
from src.application.use_cases.podcast import GeneratePodcastScriptRequest

router = APIRouter(prefix="/channels", tags=["audio"])


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


async def generate_audio_task(
    audio_id: str,
    store_name: str,
    duration_minutes: int,
    style: str,
    language: str,
    host_a_voice: VoiceType,
    host_b_voice: VoiceType,
    db_url: str,
):
    """Background task for generating podcast audio.

    This runs the full pipeline: script generation -> TTS -> audio merge.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Create new database session for background task
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        repo = AudioRepository(db)
        tts = get_tts_service()

        # Update status to generating script
        repo.update_status(audio_id, AudioStatus.GENERATING_SCRIPT)

        # Generate podcast script using UseCase
        use_case = create_generate_podcast_script_use_case()
        request = GeneratePodcastScriptRequest(
            store_name=store_name,
            duration_minutes=duration_minutes,
            style=style,
            language=language,
        )

        try:
            script_dto = use_case.execute(request)
        except Exception as e:
            repo.update_status(
                audio_id,
                AudioStatus.FAILED,
                error_message=str(e),
            )
            return

        # Convert DTO to model
        dialogue = []
        for line in script_dto.dialogue:
            speaker = line.speaker
            if "Host A" in speaker or "진행자" in speaker:
                voice = host_a_voice
            else:
                voice = host_b_voice

            dialogue.append(
                DialogueLine(
                    speaker=speaker,
                    text=line.text,
                    voice=voice,
                )
            )

        script = PodcastScript(
            title=script_dto.title,
            introduction=script_dto.introduction,
            dialogue=dialogue,
            conclusion=script_dto.conclusion,
            estimated_duration_seconds=script_dto.estimated_duration_seconds,
        )

        # Update with script
        repo.update_script(audio_id, script)

        # Generate audio
        audio_path, duration = await tts.generate_podcast_audio(
            script=script,
            language=language,
            host_a_voice=host_a_voice,
            host_b_voice=host_b_voice,
        )

        # Mark complete
        repo.update_audio_complete(audio_id, audio_path, duration)

    except Exception as e:
        repo.update_status(
            audio_id,
            AudioStatus.FAILED,
            error_message=str(e),
        )
    finally:
        db.close()


def run_async_task(coro):
    """Run async task in background."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


@router.post(
    "/{channel_id:path}/audio",
    response_model=AudioOverviewResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate audio overview",
)
@limiter.limit(RateLimits.UPLOAD)
def generate_audio_overview(
    request: Request,
    channel_id: str,
    body: GenerateAudioRequest,
    background_tasks: BackgroundTasks,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    db: Annotated[Session, Depends(get_db)],
) -> AudioOverviewResponse:
    """Start audio overview generation for a channel.

    Generates a podcast-style audio summary of all documents in the channel.
    The audio features two AI hosts discussing the content in a natural,
    conversational manner.

    Returns immediately with a task ID. Poll the GET endpoint to check status.
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Get channel from database
    repo = AudioRepository(db)
    channel = repo.get_channel_by_store_id(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel metadata not found: {channel_id}",
        )

    # Update last accessed time
    channel_repo = ChannelRepository(db)
    channel_repo.touch(channel_id)

    # Create audio overview record
    audio = repo.create_audio_overview(
        channel_id=channel.id,
        language=body.language,
        style=body.style,
    )

    # Get database URL for background task
    from src.core.config import get_settings
    db_url = get_settings().database_url

    # Start background generation
    import threading
    thread = threading.Thread(
        target=run_async_task,
        args=(
            generate_audio_task(
                audio_id=audio.audio_id,
                store_name=channel_id,
                duration_minutes=body.duration_minutes,
                style=body.style,
                language=body.language,
                host_a_voice=body.host_a_voice,
                host_b_voice=body.host_b_voice,
                db_url=db_url,
            ),
        ),
    )
    thread.start()

    return to_response(audio, channel_id)


@router.get(
    "/{channel_id:path}/audio",
    response_model=AudioOverviewListResponse,
    summary="List audio overviews",
)
@limiter.limit(RateLimits.LIST)
def list_audio_overviews(
    request: Request,
    channel_id: str,
    limit: int = 20,
    offset: int = 0,
    db: Annotated[Session, Depends(get_db)] = None,
) -> AudioOverviewListResponse:
    """List all audio overviews for a channel."""
    # Get channel from database
    repo = AudioRepository(db)
    channel = repo.get_channel_by_store_id(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    audios = repo.get_audios_by_channel(channel.id, limit=limit, offset=offset)
    total = repo.count_audios_by_channel(channel.id)

    return AudioOverviewListResponse(
        items=[to_response(a, channel_id) for a in audios],
        total=total,
    )


@router.get(
    "/{channel_id:path}/audio/{audio_id}",
    response_model=AudioOverviewResponse,
    summary="Get audio overview",
)
@limiter.limit(RateLimits.LIST)
def get_audio_overview(
    request: Request,
    channel_id: str,
    audio_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> AudioOverviewResponse:
    """Get a specific audio overview by ID."""
    repo = AudioRepository(db)
    audio = repo.get_audio_by_id(audio_id)

    if not audio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio overview not found: {audio_id}",
        )

    # Verify channel matches
    channel = repo.get_channel_by_store_id(channel_id)
    if not channel or audio.channel_id != channel.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio overview not found in channel: {channel_id}",
        )

    return to_response(audio, channel_id)


@router.get(
    "/{channel_id:path}/audio/{audio_id}/stream",
    summary="Stream audio file",
)
@limiter.limit(RateLimits.DOWNLOAD)
def stream_audio(
    request: Request,
    channel_id: str,
    audio_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    """Stream the generated audio file."""
    repo = AudioRepository(db)
    audio = repo.get_audio_by_id(audio_id)

    if not audio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio overview not found: {audio_id}",
        )

    if audio.status != AudioStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio is not ready. Current status: {audio.status}",
        )

    if not audio.audio_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found",
        )

    return FileResponse(
        audio.audio_path,
        media_type="audio/mpeg",
        filename=f"{audio.title or 'audio_overview'}.mp3",
    )


@router.delete(
    "/{channel_id:path}/audio/{audio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete audio overview",
)
@limiter.limit(RateLimits.UPLOAD)
def delete_audio_overview(
    request: Request,
    channel_id: str,
    audio_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    """Delete an audio overview and its audio file."""
    repo = AudioRepository(db)
    audio = repo.get_audio_by_id(audio_id)

    if not audio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio overview not found: {audio_id}",
        )

    # Verify channel matches
    channel = repo.get_channel_by_store_id(channel_id)
    if not channel or audio.channel_id != channel.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio overview not found in channel: {channel_id}",
        )

    # Delete audio file
    if audio.audio_path:
        tts = get_tts_service()
        tts.delete_audio(audio.audio_id)

    # Delete database record
    repo.delete_audio(audio_id)


@router.post(
    "/{channel_id:path}/audio/preview-script",
    response_model=ScriptOnlyResponse,
    summary="Preview podcast script",
)
@limiter.limit(RateLimits.CHAT)
def preview_script(
    request: Request,
    channel_id: str,
    body: GenerateAudioRequest,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    db: Annotated[Session, Depends(get_db)],
) -> ScriptOnlyResponse:
    """Generate and preview podcast script without creating audio.

    Useful for previewing the script content before committing to
    full audio generation.
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Update last accessed time
    repo = ChannelRepository(db)
    repo.touch(channel_id)

    # Generate script using UseCase
    use_case = create_generate_podcast_script_use_case()
    script_request = GeneratePodcastScriptRequest(
        store_name=channel_id,
        duration_minutes=body.duration_minutes,
        style=body.style,
        language=body.language,
    )

    try:
        script_dto = use_case.execute(script_request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate script: {str(e)}",
        )

    # Convert DTO to model
    dialogue = []
    for line in script_dto.dialogue:
        speaker = line.speaker
        if "Host A" in speaker or "진행자" in speaker:
            voice = body.host_a_voice
        else:
            voice = body.host_b_voice

        dialogue.append(
            DialogueLine(
                speaker=speaker,
                text=line.text,
                voice=voice,
            )
        )

    script = PodcastScript(
        title=script_dto.title,
        introduction=script_dto.introduction,
        dialogue=dialogue,
        conclusion=script_dto.conclusion,
        estimated_duration_seconds=script_dto.estimated_duration_seconds,
    )

    return ScriptOnlyResponse(
        channel_id=channel_id,
        script=script,
        generated_at=datetime.now(UTC),
    )
