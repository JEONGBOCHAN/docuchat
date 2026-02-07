# -*- coding: utf-8 -*-
"""Channel CRUD API endpoints.

Thin controller: delegates all business logic to ChannelCrudUseCase.
Only handles HTTP concerns (status codes, error mapping, DTO→Pydantic conversion).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.models.channel import ChannelCreate, ChannelUpdate, ChannelResponse, ChannelList
from src.application.use_cases.channel_crud import ChannelCrudUseCase, ChannelDetailDTO
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits

router = APIRouter(prefix="/channels", tags=["channels"])


def get_channel_crud_use_case(db: Session = Depends(get_db)) -> ChannelCrudUseCase:
    """Get channel CRUD use case instance with all dependencies wired."""
    from src.infrastructure.di.container import create_channel_crud_use_case
    return create_channel_crud_use_case(db)


def _dto_to_response(dto: ChannelDetailDTO) -> ChannelResponse:
    """Convert application-layer DTO to API response model."""
    return ChannelResponse(
        id=dto.id,
        name=dto.name,
        description=dto.description,
        created_at=dto.created_at,
        file_count=dto.file_count,
        is_favorited=dto.is_favorited,
    )


@router.post(
    "",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new channel",
)
@limiter.limit(RateLimits.DEFAULT)
def create_channel(
    request: Request,
    data: ChannelCreate,
    use_case: Annotated[ChannelCrudUseCase, Depends(get_channel_crud_use_case)],
) -> ChannelResponse:
    """Create a new channel (Gemini File Search Store).

    A channel is a container for documents that can be searched together.
    """
    try:
        dto = use_case.create(data.name, data.description)
        return _dto_to_response(dto)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create channel: {str(e)}",
        )


@router.get(
    "",
    response_model=ChannelList,
    summary="List all channels",
)
@limiter.limit(RateLimits.DEFAULT)
def list_channels(
    request: Request,
    use_case: Annotated[ChannelCrudUseCase, Depends(get_channel_crud_use_case)],
    limit: Annotated[int | None, Query(description="Maximum number of channels", ge=1, le=100)] = None,
    offset: Annotated[int, Query(description="Number of channels to skip", ge=0)] = 0,
    sort_by: Annotated[str, Query(description="Sort by field: created_at or name")] = "created_at",
    sort_order: Annotated[str, Query(description="Sort order: asc or desc")] = "desc",
) -> ChannelList:
    """List all channels (File Search Stores)."""
    try:
        result = use_case.list(
            limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order,
        )
        return ChannelList(
            channels=[_dto_to_response(ch) for ch in result.channels],
            total=result.total,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list channels: {str(e)}",
        )


@router.get(
    "/{channel_id:path}",
    response_model=ChannelResponse,
    summary="Get a channel by ID",
)
@limiter.limit(RateLimits.DEFAULT)
def get_channel(
    request: Request,
    channel_id: str,
    use_case: Annotated[ChannelCrudUseCase, Depends(get_channel_crud_use_case)],
) -> ChannelResponse:
    """Get a specific channel by its ID.

    Note: channel_id should be the full store name (e.g., "fileSearchStores/xxx")
    """
    dto = use_case.get(channel_id)
    if not dto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )
    return _dto_to_response(dto)


@router.put(
    "/{channel_id:path}",
    response_model=ChannelResponse,
    summary="Update a channel",
)
@limiter.limit(RateLimits.DEFAULT)
def update_channel(
    request: Request,
    channel_id: str,
    data: ChannelUpdate,
    use_case: Annotated[ChannelCrudUseCase, Depends(get_channel_crud_use_case)],
) -> ChannelResponse:
    """Update a channel's name and/or description.

    Note: channel_id should be the full store name (e.g., "fileSearchStores/xxx")
    """
    # Validation stays in the router (HTTP concern)
    if data.name is None and data.description is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of 'name' or 'description' must be provided",
        )

    dto = use_case.update(channel_id, name=data.name, description=data.description)
    if not dto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )
    return _dto_to_response(dto)


@router.delete(
    "/{channel_id:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a channel",
)
@limiter.limit(RateLimits.DEFAULT)
def delete_channel(
    request: Request,
    channel_id: str,
    use_case: Annotated[ChannelCrudUseCase, Depends(get_channel_crud_use_case)],
):
    """Delete a channel permanently.

    This deletes the channel from both Gemini and the local database.
    Note: When trash UI is implemented, this will change to soft delete.
    """
    try:
        success = use_case.delete(channel_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Channel not found: {channel_id}",
            )
        return None
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete channel from Gemini: {str(e)}",
        )
