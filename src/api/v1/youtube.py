# -*- coding: utf-8 -*-
"""YouTube source API endpoints."""

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.models.youtube import (
    YouTubeSourceRequest,
    YouTubeSourceResponse,
)
from src.services.gemini import GeminiService, get_gemini_service
from src.services.youtube_service import (
    YouTubeService,
    get_youtube_service,
    YouTubeServiceError,
    TranscriptNotAvailableError,
    InvalidVideoError,
)
from src.services.capacity_service import CapacityService, CapacityExceededError

router = APIRouter(prefix="/channels", tags=["youtube"])


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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    youtube: Annotated[YouTubeService, Depends(get_youtube_service)],
    db: Annotated[Session, Depends(get_db)],
) -> YouTubeSourceResponse:
    """Add a YouTube video as a source to the channel.

    Extracts the transcript from the YouTube video and uploads it as a document.

    The transcript will be automatically extracted from the video. If manual captions
    are available, they will be preferred over auto-generated captions.

    Supported languages (in order of preference): Korean, English, Japanese, Chinese.
    """
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
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
        capacity_service = CapacityService(db)
        file_size = os.path.getsize(tmp_path)
        try:
            capacity_service.validate_upload(channel_id, file_size)
        except CapacityExceededError as e:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(e),
            )

        # Upload to Gemini
        operation = gemini.upload_file(channel_id, tmp_path)

        # Update capacity tracking
        capacity_service.update_after_upload(channel_id, file_size)

        return YouTubeSourceResponse(
            video_id=video_id,
            title=f"YouTube: {video_id}",
            document_id=operation["name"],
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
    except YouTubeServiceError as e:
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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    youtube: Annotated[YouTubeService, Depends(get_youtube_service)],
) -> dict:
    """Preview the transcript of a YouTube video before adding it.

    This endpoint allows you to see what transcript will be extracted
    without actually adding it to the channel.
    """
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
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
    except YouTubeServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"YouTube service error: {str(e)}",
        )
