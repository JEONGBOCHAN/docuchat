# -*- coding: utf-8 -*-
"""Google Drive Integration API endpoints (thin controller)."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Body
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.logging import get_logger
from src.modules.workspace.application.use_cases.google_drive_integration import (
    GoogleDriveIntegrationUseCase,
    InvalidOAuthStateError,
)
from src.shared.kernel.contracts.errors.use_case_errors import ChannelNotFoundError
from src.modules.workspace.domain.exceptions import CapacityExceededError

logger = get_logger(__name__)

router = APIRouter(prefix="/integrations/google-drive", tags=["google-drive"])


# ── Dependency ──────────────────────────────────────────────

def _get_use_case(db: Session = Depends(get_db)) -> GoogleDriveIntegrationUseCase:
    from src.modules.workspace.public import create_google_drive_integration_use_case
    return create_google_drive_integration_use_case(db)


# ── Request / Response schemas ──────────────────────────────

class AuthUrlResponse(BaseModel):
    auth_url: str = Field(..., description="Google OAuth authorization URL")
    state: str = Field(..., description="OAuth state parameter for CSRF protection")


class TokenRequest(BaseModel):
    code: str = Field(..., description="OAuth authorization code from callback")
    state: str = Field(..., description="OAuth state parameter for CSRF verification")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    token_type: str = "Bearer"


class DriveFile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    name: str
    mime_type: str = Field(..., alias="mimeType")
    size: Optional[int] = None
    modified_time: Optional[str] = Field(None, alias="modifiedTime")
    icon_link: Optional[str] = Field(None, alias="iconLink")
    thumbnail_link: Optional[str] = Field(None, alias="thumbnailLink")
    parents: Optional[list[str]] = None


class DriveFilesResponse(BaseModel):
    files: list[DriveFile]
    next_page_token: Optional[str] = None


class ImportFileRequest(BaseModel):
    file_id: str = Field(..., description="Google Drive file ID")
    access_token: str = Field(..., description="OAuth access token")


class ImportFileResponse(BaseModel):
    id: str = Field(..., description="Document ID in the channel")
    filename: str
    status: str
    message: str


# ── Endpoints ───────────────────────────────────────────────

@router.get("/auth-url", response_model=AuthUrlResponse)
def get_auth_url(
    use_case: Annotated[GoogleDriveIntegrationUseCase, Depends(_get_use_case)],
):
    try:
        auth_url, state = use_case.get_auth_url()
        return AuthUrlResponse(auth_url=auth_url, state=state)
    except Exception as e:
        logger.error("Failed to generate OAuth URL", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate OAuth authorization URL")


@router.post("/token", response_model=TokenResponse)
def exchange_token(
    request: TokenRequest,
    use_case: Annotated[GoogleDriveIntegrationUseCase, Depends(_get_use_case)],
):
    try:
        token = use_case.exchange_token(request.code, request.state)
        return TokenResponse(
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_in=token.expires_in,
            token_type=token.token_type,
        )
    except InvalidOAuthStateError:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state parameter. Please retry authorization.",
        )
    except Exception as e:
        logger.error("Failed to exchange OAuth code", error=str(e))
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")


def _extract_bearer_token(authorization: str) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format. Expected: Bearer <token>")
    return authorization[7:]


@router.get("/files", response_model=DriveFilesResponse)
def list_files(
    use_case: Annotated[GoogleDriveIntegrationUseCase, Depends(_get_use_case)],
    authorization: str = Header(..., description="Bearer access token"),
    folder_id: Optional[str] = Query(None, description="Folder ID to list (root if not specified)"),
    page_token: Optional[str] = Query(None, description="Token for next page of results"),
    page_size: int = Query(20, ge=1, le=100, description="Number of files per page"),
):
    try:
        access_token = _extract_bearer_token(authorization)
        files, next_token = use_case.list_files(access_token, folder_id, page_token, page_size)
        return DriveFilesResponse(
            files=[
                DriveFile(
                    id=f.id,
                    name=f.name,
                    mimeType=f.mime_type,
                    size=f.size,
                    modifiedTime=f.modified_time,
                    iconLink=f.icon_link,
                    thumbnailLink=f.thumbnail_link,
                    parents=f.parents,
                )
                for f in files
            ],
            next_page_token=next_token,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list Drive files", error=str(e))
        if "invalid_grant" in str(e).lower() or "invalid credentials" in str(e).lower():
            raise HTTPException(
                status_code=401,
                detail="Access token is invalid or expired. Please re-authenticate.",
            )
        raise HTTPException(status_code=500, detail="Failed to list files from Google Drive")


@router.post("/import/{channel_id}", response_model=ImportFileResponse)
def import_file(
    channel_id: str,
    request: ImportFileRequest,
    use_case: Annotated[GoogleDriveIntegrationUseCase, Depends(_get_use_case)],
):
    try:
        result = use_case.import_file(channel_id, request.access_token, request.file_id)
        return ImportFileResponse(
            id=result.operation_name,
            filename=result.filename,
            status="processing" if not result.done else "completed",
            message=f"Successfully imported {result.filename} from Google Drive",
        )
    except ChannelNotFoundError:
        raise HTTPException(status_code=404, detail=f"Channel not found: {channel_id}")
    except CapacityExceededError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except Exception as e:
        logger.error("Failed to import file from Google Drive", error=str(e), file_id=request.file_id, channel_id=channel_id)
        if "invalid_grant" in str(e).lower() or "invalid credentials" in str(e).lower():
            raise HTTPException(
                status_code=401,
                detail="Access token is invalid or expired. Please re-authenticate.",
            )
        raise HTTPException(status_code=500, detail="Failed to import file from Google Drive")


@router.post("/refresh-token", response_model=TokenResponse)
def refresh_access_token(
    use_case: Annotated[GoogleDriveIntegrationUseCase, Depends(_get_use_case)],
    refresh_token: str = Body(..., embed=True, description="OAuth refresh token"),
):
    try:
        token = use_case.refresh_token(refresh_token)
        return TokenResponse(
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_in=token.expires_in,
            token_type=token.token_type,
        )
    except Exception as e:
        logger.error("Failed to refresh access token", error=str(e))
        raise HTTPException(
            status_code=401,
            detail="Failed to refresh access token. Please re-authenticate.",
        )
