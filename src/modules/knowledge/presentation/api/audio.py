# -*- coding: utf-8 -*-
"""Audio Overview (Podcast) API endpoints (thin controller)."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.modules.knowledge.presentation.schemas.audio import (
    AudioStatus,
    VoiceType,
    PodcastScript,
    DialogueLine,
    GenerateAudioRequest,
    AudioOverviewResponse,
    AudioOverviewListResponse,
    ScriptOnlyResponse,
)
from src.modules.knowledge.application.use_cases.audio_overview import (
    AudioOverviewUseCase,
    ChannelNotFoundError,
    ChannelMetadataNotFoundError,
    AudioNotFoundError,
    AudioNotReadyError,
    AudioFileNotFoundError,
    ScriptGenerationError,
)
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits

router = APIRouter(prefix="/channels", tags=["audio"])


# ── Dependencies ────────────────────────────────────────────

def _get_use_case(db: Session = Depends(get_db)) -> AudioOverviewUseCase:
    from src.modules.knowledge.public import create_audio_overview_use_case
    return create_audio_overview_use_case(db)


# ── Response conversion ────────────────────────────────────

def _audio_dto_to_response(audio_dto, channel_id: str) -> AudioOverviewResponse:
    """Convert AudioDTO to AudioOverviewResponse."""
    script = None
    if audio_dto.script_json:
        try:
            script_data = json.loads(audio_dto.script_json)
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


# ── Endpoints ──────────────────────────────────────────────

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
    use_case: Annotated[AudioOverviewUseCase, Depends(_get_use_case)],
) -> AudioOverviewResponse:
    """Start audio overview generation for a channel."""
    try:
        result = use_case.start_generation(
            channel_id=channel_id,
            duration_minutes=body.duration_minutes,
            style=body.style,
            language=body.language,
            host_a_voice=body.host_a_voice.value,
            host_b_voice=body.host_b_voice.value,
        )
    except ChannelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )
    except ChannelMetadataNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel metadata not found: {channel_id}",
        )

    return _audio_dto_to_response(result.dto, result.channel_store_id)


@router.get(
    "/{channel_id:path}/audio",
    response_model=AudioOverviewListResponse,
    summary="List audio overviews",
)
@limiter.limit(RateLimits.LIST)
def list_audio_overviews(
    request: Request,
    channel_id: str,
    use_case: Annotated[AudioOverviewUseCase, Depends(_get_use_case)],
    limit: int = 20,
    offset: int = 0,
) -> AudioOverviewListResponse:
    """List all audio overviews for a channel."""
    try:
        result = use_case.list(channel_id, limit=limit, offset=offset)
    except ChannelMetadataNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    return AudioOverviewListResponse(
        items=[_audio_dto_to_response(a, result.channel_store_id) for a in result.items],
        total=result.total,
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
    use_case: Annotated[AudioOverviewUseCase, Depends(_get_use_case)],
) -> AudioOverviewResponse:
    """Get a specific audio overview by ID."""
    try:
        result = use_case.get(channel_id, audio_id)
    except AudioNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio overview not found: {audio_id}",
        )

    return _audio_dto_to_response(result.dto, result.channel_store_id)


@router.get(
    "/{channel_id:path}/audio/{audio_id}/stream",
    summary="Stream audio file",
)
@limiter.limit(RateLimits.DOWNLOAD)
def stream_audio(
    request: Request,
    channel_id: str,
    audio_id: str,
    use_case: Annotated[AudioOverviewUseCase, Depends(_get_use_case)],
):
    """Stream the generated audio file."""
    try:
        info = use_case.get_stream_info(channel_id, audio_id)
    except AudioNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio overview not found: {audio_id}",
        )
    except AudioNotReadyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except AudioFileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found",
        )

    return FileResponse(
        info.audio_path,
        media_type="audio/mpeg",
        filename=f"{info.title or 'audio_overview'}.mp3",
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
    use_case: Annotated[AudioOverviewUseCase, Depends(_get_use_case)],
):
    """Delete an audio overview and its audio file."""
    try:
        use_case.delete(channel_id, audio_id)
    except AudioNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio overview not found: {audio_id}",
        )


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
    use_case: Annotated[AudioOverviewUseCase, Depends(_get_use_case)],
) -> ScriptOnlyResponse:
    """Generate and preview podcast script without creating audio."""
    try:
        result = use_case.preview_script(
            channel_id=channel_id,
            duration_minutes=body.duration_minutes,
            style=body.style,
            language=body.language,
            host_a_voice=body.host_a_voice.value,
            host_b_voice=body.host_b_voice.value,
        )
    except ChannelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )
    except ScriptGenerationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # Convert result to response schema
    dialogue = [
        DialogueLine(
            speaker=line["speaker"],
            text=line["text"],
            voice=VoiceType(line["voice"]),
        )
        for line in result.dialogue
    ]

    script = PodcastScript(
        title=result.title,
        introduction=result.introduction,
        dialogue=dialogue,
        conclusion=result.conclusion,
        estimated_duration_seconds=result.estimated_duration_seconds,
    )

    return ScriptOnlyResponse(
        channel_id=result.channel_store_id,
        script=script,
        generated_at=result.generated_at,
    )
