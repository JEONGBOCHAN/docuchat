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
from src.application.ports.persistence import (
    AudioRepositoryPort,
    ChannelRepositoryPort,
)
from src.application.ports.external_services import TTSPort
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.application.use_cases.podcast import GeneratePodcastScriptRequest
from src.infrastructure.di.container import (
    create_channel_port,
    create_generate_podcast_script_use_case,
    create_audio_repository_port,
    create_channel_repository_port,
    create_tts_port,
)

router = APIRouter(prefix="/channels", tags=["audio"])


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


def get_audio_repo_port(db: Session = Depends(get_db)) -> AudioRepositoryPort:
    """Get audio repository port instance."""
    return create_audio_repository_port(db)


def get_channel_repo_port(db: Session = Depends(get_db)) -> ChannelRepositoryPort:
    """Get channel repository port instance."""
    return create_channel_repository_port(db)


def get_tts_port() -> TTSPort:
    """Get TTS port instance."""
    return create_tts_port()


def _audio_dto_to_response(audio_dto, channel_id: str) -> AudioOverviewResponse:
    """Convert AudioDTO to AudioOverviewResponse."""
    # Parse script_json if available
    import json
    script = None
    if audio_dto.script_json:
        try:
            script_data = json.loads(audio_dto.script_json)
            # Convert to PodcastScript model
            dialogue = [
                DialogueLine(
                    speaker=line.get("speaker", ""),
                    text=line.get("text", ""),
                    voice=VoiceType(line.get("voice", "female")),
                )
                for line in script_data.get("dialogue", [])
            ]
            script = PodcastScript(
                title=script_data.get("title", ""),
                introduction=script_data.get("introduction", ""),
                dialogue=dialogue,
                conclusion=script_data.get("conclusion", ""),
                estimated_duration_seconds=script_data.get("estimated_duration_seconds", 0),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    # Generate stream URL if audio is available
    audio_url = None
    if audio_dto.audio_path:
        audio_url = f"/api/v1/channels/{channel_id}/audio/{audio_dto.audio_id}/stream"

    return AudioOverviewResponse(
        id=audio_dto.audio_id,
        channel_id=channel_id,
        title=audio_dto.title,
        status=AudioStatus(audio_dto.status),
        script=script,
        duration_seconds=audio_dto.audio_duration_seconds,
        audio_url=audio_url,
        error=audio_dto.error_message,
        created_at=audio_dto.created_at,
        completed_at=audio_dto.completed_at,
    )


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
    import logging
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.infrastructure.persistence.audio_repository import AudioRepository
    from src.infrastructure.external.tts.tts_service import get_tts_service

    bg_logger = logging.getLogger(__name__)

    # Create new database session for background task
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    repo = None
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
        bg_logger.error("Audio generation failed for %s: %s", audio_id, e)
        if repo is not None:
            repo.update_status(
                audio_id,
                AudioStatus.FAILED,
                error_message=str(e),
            )
    finally:
        db.close()


def run_async_task(coro_fn, **kwargs):
    """Run async task in background thread.

    Creates the coroutine inside the thread to avoid 'coroutine never awaited'
    warnings when Thread.start() is mocked in tests.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(coro_fn(**kwargs))
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
    audio_repo: Annotated[AudioRepositoryPort, Depends(get_audio_repo_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
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
    channel_dto = audio_repo.get_channel_by_store_id(channel_id)
    if not channel_dto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel metadata not found: {channel_id}",
        )

    # Update last accessed time
    channel_repo.touch(channel_id)

    # Create audio overview record
    audio_dto = audio_repo.create_audio_overview(
        channel_id=channel_dto.id,
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
        kwargs={
            "coro_fn": generate_audio_task,
            "audio_id": audio_dto.audio_id,
            "store_name": channel_id,
            "duration_minutes": body.duration_minutes,
            "style": body.style,
            "language": body.language,
            "host_a_voice": body.host_a_voice,
            "host_b_voice": body.host_b_voice,
            "db_url": db_url,
        },
    )
    thread.start()

    return _audio_dto_to_response(audio_dto, channel_id)


@router.get(
    "/{channel_id:path}/audio",
    response_model=AudioOverviewListResponse,
    summary="List audio overviews",
)
@limiter.limit(RateLimits.LIST)
def list_audio_overviews(
    request: Request,
    channel_id: str,
    audio_repo: Annotated[AudioRepositoryPort, Depends(get_audio_repo_port)],
    limit: int = 20,
    offset: int = 0,
) -> AudioOverviewListResponse:
    """List all audio overviews for a channel."""
    # Get channel from database
    channel_dto = audio_repo.get_channel_by_store_id(channel_id)
    if not channel_dto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    audios = audio_repo.get_audios_by_channel(channel_dto.id, limit=limit, offset=offset)
    total = audio_repo.count_audios_by_channel(channel_dto.id)

    return AudioOverviewListResponse(
        items=[_audio_dto_to_response(a, channel_id) for a in audios],
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
    audio_repo: Annotated[AudioRepositoryPort, Depends(get_audio_repo_port)],
) -> AudioOverviewResponse:
    """Get a specific audio overview by ID."""
    audio_dto = audio_repo.get_audio_by_id(audio_id)

    if not audio_dto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio overview not found: {audio_id}",
        )

    # Verify channel matches
    channel_dto = audio_repo.get_channel_by_store_id(channel_id)
    if not channel_dto or audio_dto.channel_id != channel_dto.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio overview not found in channel: {channel_id}",
        )

    return _audio_dto_to_response(audio_dto, channel_id)


@router.get(
    "/{channel_id:path}/audio/{audio_id}/stream",
    summary="Stream audio file",
)
@limiter.limit(RateLimits.DOWNLOAD)
def stream_audio(
    request: Request,
    channel_id: str,
    audio_id: str,
    audio_repo: Annotated[AudioRepositoryPort, Depends(get_audio_repo_port)],
):
    """Stream the generated audio file."""
    audio_dto = audio_repo.get_audio_by_id(audio_id)

    if not audio_dto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio overview not found: {audio_id}",
        )

    # Verify channel ownership
    channel_dto = audio_repo.get_channel_by_store_id(channel_id)
    if not channel_dto or audio_dto.channel_id != channel_dto.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio overview not found in channel: {channel_id}",
        )

    if audio_dto.status != AudioStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio is not ready. Current status: {audio_dto.status}",
        )

    if not audio_dto.audio_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found",
        )

    return FileResponse(
        audio_dto.audio_path,
        media_type="audio/mpeg",
        filename=f"{audio_dto.title or 'audio_overview'}.mp3",
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
    audio_repo: Annotated[AudioRepositoryPort, Depends(get_audio_repo_port)],
    tts_port: Annotated[TTSPort, Depends(get_tts_port)],
):
    """Delete an audio overview and its audio file."""
    audio_dto = audio_repo.get_audio_by_id(audio_id)

    if not audio_dto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio overview not found: {audio_id}",
        )

    # Verify channel matches
    channel_dto = audio_repo.get_channel_by_store_id(channel_id)
    if not channel_dto or audio_dto.channel_id != channel_dto.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio overview not found in channel: {channel_id}",
        )

    # Delete audio file
    if audio_dto.audio_path:
        tts_port.delete_audio(audio_dto.audio_id)

    # Delete database record
    audio_repo.delete_audio(audio_id)


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
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
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
    channel_repo.touch(channel_id)

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
