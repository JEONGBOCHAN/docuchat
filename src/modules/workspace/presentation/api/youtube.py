# -*- coding: utf-8 -*-
"""YouTube source API endpoints."""

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status

from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.models.youtube import (
    YouTubeSourceRequest,
    YouTubeSourceResponse,
)
from src.application.ports.channel import ChannelPort
from src.application.ports.document import DocumentPort
from src.application.ports.external_services import YouTubePort
from src.application.services.capacity_service import CapacityService
from src.domain.exceptions import CapacityExceededError
from src.application.use_cases.exceptions import (
    YouTubeError,
    TranscriptNotAvailableError,
    InvalidVideoError,
)
from src.modules.workspace.public import (
    create_channel_port,
    create_document_port,
    create_youtube_port,
    create_capacity_service,
)

router = APIRouter(prefix="/channels", tags=["youtube"])


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


def get_document_port() -> DocumentPort:
    """Get document port instance."""
    return create_document_port()


def get_youtube_port() -> YouTubePort:
    """Get YouTube port instance."""
    return create_youtube_port()


def get_capacity_service(db=Depends(get_db)) -> CapacityService:
    """Get capacity service instance."""
    return create_capacity_service(db)


@router.post(
    "/{channel_id:path}/sources/youtube",
    response_model=YouTubeSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add YouTube video as source",
)
@limiter.limit(RateLimits.FILE_UPLOAD)
def add_youtube_source(
    request: Request,
    channel_id: str,
    body: YouTubeSourceRequest,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    document_port: Annotated[DocumentPort, Depends(get_document_port)],
    youtube: Annotated[YouTubePort, Depends(get_youtube_port)],
    capacity_service: Annotated[CapacityService, Depends(get_capacity_service)],
) -> YouTubeSourceResponse:
    """Add a YouTube video as a source to the channel.

    Extracts the transcript from the YouTube video and uploads it as a document.

    The transcript will be automatically extracted from the video. If manual captions
    are available, they will be preferred over auto-generated captions.

    Supported languages (in order of preference): Korean, English, Japanese, Chinese.
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    tmp_path = None
    try:
        # Extract video ID
        video_id = youtube.extract_video_id(body.url)

        # Get transcript
        transcript = youtube.get_transcript(video_id)

        # Create temp file with transcript
        tmp_path = youtube.save_transcript_to_temp_file(
            video_id=video_id,
            transcript=transcript,
            include_timestamps=True,
        )

        # Check capacity
        file_size = os.path.getsize(tmp_path)
        try:
            capacity_service.validate_upload(channel_id, file_size)
        except CapacityExceededError as e:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(e),
            )

        # Upload to Gemini
        result = document_port.upload_document(channel_id, tmp_path)

        # Update capacity tracking
        capacity_service.update_after_upload(channel_id, file_size)

        return YouTubeSourceResponse(
            video_id=video_id,
            title=f"YouTube: {video_id}",
            document_id=result.operation_name,
            transcript_length=len(transcript.full_text),
            language=transcript.language,
            message="YouTube transcript added successfully",
        )

    except InvalidVideoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except TranscriptNotAvailableError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except CapacityExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        )
    except YouTubeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"YouTube service error: {str(e)}",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add YouTube source: {str(e)}",
        )
    finally:
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@router.get(
    "/{channel_id:path}/sources/youtube/preview",
    summary="Preview YouTube transcript without adding",
)
@limiter.limit(RateLimits.DEFAULT)
def preview_youtube_transcript(
    request: Request,
    channel_id: str,
    url: Annotated[str, Query(description="YouTube video URL")],
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    youtube: Annotated[YouTubePort, Depends(get_youtube_port)],
) -> dict:
    """Preview the transcript of a YouTube video before adding it.

    This endpoint allows you to see what transcript will be extracted
    without actually adding it to the channel.
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    try:
        # Extract video ID
        video_id = youtube.extract_video_id(url)

        # Get transcript
        transcript = youtube.get_transcript(video_id)

        # Return preview
        return {
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "language": transcript.language,
            "segment_count": len(transcript.segments),
            "character_count": len(transcript.full_text),
            "preview": transcript.full_text[:500] + "..." if len(transcript.full_text) > 500 else transcript.full_text,
            "available": True,
        }

    except InvalidVideoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except TranscriptNotAvailableError:
        return {
            "video_id": youtube.extract_video_id(url) if url else "",
            "url": url,
            "available": False,
            "message": "No transcript available for this video",
        }
    except YouTubeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"YouTube service error: {str(e)}",
        )
