# -*- coding: utf-8 -*-
"""Trash (soft delete) API endpoints (thin controller)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.modules.workspace.presentation.schemas.trash import (
    TrashList,
    TrashItem,
    TrashItemType,
    RestoreResponse,
    EmptyTrashResponse,
)
from src.modules.workspace.application.use_cases.trash_management import (
    TrashManagementUseCase,
    TrashItemNotFoundError,
    ExternalDeleteFailedError,
)
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.shared.kernel.presentation.dependencies.admin_auth import require_admin_key

router = APIRouter(prefix="/trash", tags=["trash"])


# ── Dependency ──────────────────────────────────────────────

def _get_use_case(db: Session = Depends(get_db)) -> TrashManagementUseCase:
    from src.modules.workspace.public import create_trash_management_use_case
    return create_trash_management_use_case(db)


# ── Endpoints ───────────────────────────────────────────────

@router.get("", response_model=TrashList, summary="List all trashed items")
@limiter.limit(RateLimits.DEFAULT)
def list_trash(
    request: Request,
    use_case: Annotated[TrashManagementUseCase, Depends(_get_use_case)],
) -> TrashList:
    items_dto = use_case.list_items()
    items = [
        TrashItem(
            id=dto.id,
            type=TrashItemType(dto.type),
            name=dto.name,
            deleted_at=dto.deleted_at,
        )
        for dto in items_dto
    ]
    return TrashList(items=items, total=len(items))


@router.post(
    "/{item_type}/{item_id}/restore",
    response_model=RestoreResponse,
    summary="Restore a trashed item",
)
@limiter.limit(RateLimits.DEFAULT)
def restore_item(
    request: Request,
    item_type: TrashItemType,
    item_id: int,
    use_case: Annotated[TrashManagementUseCase, Depends(_get_use_case)],
) -> RestoreResponse:
    try:
        result = use_case.restore(item_type.value, item_id)
        name = getattr(result, "name", None) or getattr(result, "title", "item")
        return RestoreResponse(
            id=result.id,
            type=item_type,
            message=f"'{name}' has been restored",
        )
    except TrashItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trashed {item_type.value} not found: {item_id}",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid item type: {item_type}",
        )


@router.delete(
    "/{item_type}/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a trashed item",
)
@limiter.limit(RateLimits.DEFAULT)
def delete_item_permanently(
    request: Request,
    item_type: TrashItemType,
    item_id: int,
    use_case: Annotated[TrashManagementUseCase, Depends(_get_use_case)],
    _admin: Annotated[str, Depends(require_admin_key)],
):
    try:
        use_case.permanent_delete(item_type.value, item_id)
        return None
    except TrashItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trashed {item_type.value} not found: {item_id}",
        )
    except ExternalDeleteFailedError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid item type: {item_type}",
        )


@router.delete("", response_model=EmptyTrashResponse, summary="Empty the trash")
@limiter.limit(RateLimits.DEFAULT)
def empty_trash(
    request: Request,
    use_case: Annotated[TrashManagementUseCase, Depends(_get_use_case)],
    _admin: Annotated[str, Depends(require_admin_key)],
    confirm: Annotated[bool, Query(description="Confirm permanent deletion")] = False,
) -> EmptyTrashResponse:
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please confirm by setting confirm=true",
        )
    result = use_case.empty()
    return EmptyTrashResponse(
        deleted_channels=result.deleted_channels,
        deleted_notes=result.deleted_notes,
        failed_channels=result.failed_channels,
        message=result.message,
    )


@router.get("/stats", summary="Get trash statistics")
@limiter.limit(RateLimits.DEFAULT)
def get_trash_stats(
    request: Request,
    use_case: Annotated[TrashManagementUseCase, Depends(_get_use_case)],
) -> dict:
    return use_case.stats()
