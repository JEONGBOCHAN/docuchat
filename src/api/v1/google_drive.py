# -*- coding: utf-8 -*-
"""Google Drive Integration API endpoints."""

import io
import os
import tempfile
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.database import get_db
from src.core.logging import get_logger
from src.services.gemini import GeminiService, get_gemini_service
from src.services.capacity_service import CapacityService, CapacityExceededError
from src.services.cache_service import CacheService, get_cache_service

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/integrations/google-drive", tags=["google-drive"])

# OAuth 2.0 scopes for Google Drive
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]


class AuthUrlResponse(BaseModel):
    """Response containing OAuth authorization URL."""
    auth_url: str = Field(..., description="Google OAuth authorization URL")


class TokenRequest(BaseModel):
    """Request containing OAuth authorization code."""
    code: str = Field(..., description="OAuth authorization code from callback")


class TokenResponse(BaseModel):
    """Response containing OAuth tokens."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    token_type: str = "Bearer"


class DriveFile(BaseModel):
    """Google Drive file metadata."""
    id: str
    name: str
    mime_type: str = Field(..., alias="mimeType")
    size: Optional[int] = None
    modified_time: Optional[str] = Field(None, alias="modifiedTime")
    icon_link: Optional[str] = Field(None, alias="iconLink")
    thumbnail_link: Optional[str] = Field(None, alias="thumbnailLink")
    parents: Optional[list[str]] = None

    class Config:
        populate_by_name = True


class DriveFilesResponse(BaseModel):
    """Response containing list of Drive files."""
    files: list[DriveFile]
    next_page_token: Optional[str] = None


class ImportFileRequest(BaseModel):
    """Request to import a file from Google Drive."""
    file_id: str = Field(..., description="Google Drive file ID")
    access_token: str = Field(..., description="OAuth access token")


class ImportFileResponse(BaseModel):
    """Response after importing a file."""
    id: str = Field(..., description="Document ID in the channel")
    filename: str
    status: str
    message: str


def _get_oauth_flow() -> Flow:
    """Create OAuth flow with client credentials."""
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise HTTPException(
            status_code=503,
            detail="Google Drive integration is not configured. "
                   "Please set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET."
        )

    client_config = {
        "web": {
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_oauth_redirect_uri],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=settings.google_oauth_redirect_uri,
    )

    return flow


@router.get("/auth-url", response_model=AuthUrlResponse)
async def get_auth_url():
    """
    Get Google OAuth authorization URL.

    The frontend should redirect the user to this URL to authorize
    access to their Google Drive.
    """
    try:
        flow = _get_oauth_flow()
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )

        logger.info("Generated Google OAuth authorization URL")
        return AuthUrlResponse(auth_url=auth_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate OAuth URL", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/token", response_model=TokenResponse)
async def exchange_token(request: TokenRequest):
    """
    Exchange authorization code for access token.

    After the user authorizes access, Google redirects back with a code.
    This endpoint exchanges that code for access and refresh tokens.
    """
    try:
        flow = _get_oauth_flow()
        flow.fetch_token(code=request.code)

        credentials = flow.credentials

        logger.info("Successfully exchanged OAuth code for tokens")

        return TokenResponse(
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            expires_in=credentials.expiry.timestamp() if credentials.expiry else None,
            token_type="Bearer",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to exchange OAuth code", error=str(e))
        raise HTTPException(
            status_code=400,
            detail=f"Failed to exchange authorization code: {str(e)}"
        )


@router.get("/files", response_model=DriveFilesResponse)
async def list_files(
    access_token: str = Query(..., description="OAuth access token"),
    folder_id: Optional[str] = Query(None, description="Folder ID to list (root if not specified)"),
    page_token: Optional[str] = Query(None, description="Token for next page of results"),
    page_size: int = Query(20, ge=1, le=100, description="Number of files per page"),
):
    """
    List files from Google Drive.

    Returns files that can be imported (PDF, TXT, DOCX).
    Use folder_id to browse into folders.
    """
    try:
        credentials = Credentials(token=access_token)
        service = build("drive", "v3", credentials=credentials)

        # Build query for supported file types
        supported_mimes = [
            "application/pdf",
            "text/plain",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.google-apps.folder",  # Include folders for navigation
        ]
        mime_query = " or ".join([f"mimeType='{m}'" for m in supported_mimes])

        # Add folder filter if specified
        if folder_id:
            query = f"'{folder_id}' in parents and ({mime_query}) and trashed=false"
        else:
            query = f"'root' in parents and ({mime_query}) and trashed=false"

        # Execute query
        results = service.files().list(
            q=query,
            pageSize=page_size,
            pageToken=page_token,
            fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, iconLink, thumbnailLink, parents)",
            orderBy="folder,name",
        ).execute()

        files = results.get("files", [])
        next_page_token = results.get("nextPageToken")

        logger.info(
            "Listed Google Drive files",
            count=len(files),
            folder_id=folder_id,
        )

        return DriveFilesResponse(
            files=[DriveFile(**f) for f in files],
            next_page_token=next_page_token,
        )

    except Exception as e:
        logger.error("Failed to list Drive files", error=str(e))
        if "invalid_grant" in str(e).lower() or "invalid credentials" in str(e).lower():
            raise HTTPException(
                status_code=401,
                detail="Access token is invalid or expired. Please re-authenticate."
            )
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.post("/import/{channel_id}", response_model=ImportFileResponse)
async def import_file(
    channel_id: str,
    request: ImportFileRequest,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
):
    """
    Import a file from Google Drive to a channel.

    Downloads the file from Drive and uploads it to the specified channel.
    """
    try:
        credentials = Credentials(token=request.access_token)
        service = build("drive", "v3", credentials=credentials)

        # Get file metadata
        file_metadata = service.files().get(
            fileId=request.file_id,
            fields="id, name, mimeType, size",
        ).execute()

        file_name = file_metadata.get("name", "unknown")
        mime_type = file_metadata.get("mimeType", "")
        file_size = int(file_metadata.get("size", 0))

        # Check file size
        max_size = settings.max_file_size_mb * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File size ({file_size / 1024 / 1024:.1f}MB) exceeds maximum allowed ({settings.max_file_size_mb}MB)"
            )

        logger.info(
            "Importing file from Google Drive",
            file_id=request.file_id,
            file_name=file_name,
            mime_type=mime_type,
            channel_id=channel_id,
        )

        # Handle Google Docs export
        if mime_type.startswith("application/vnd.google-apps."):
            # Google Docs need to be exported
            if mime_type == "application/vnd.google-apps.document":
                export_mime = "application/pdf"
                file_name = f"{file_name}.pdf"
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported Google Docs type: {mime_type}"
                )

            request_media = service.files().export_media(
                fileId=request.file_id,
                mimeType=export_mime,
            )
        else:
            # Regular file download
            request_media = service.files().get_media(fileId=request.file_id)

        # Download file to memory
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request_media)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        file_buffer.seek(0)
        file_content = file_buffer.read()
        actual_size = len(file_content)

        # Validate channel exists
        store = gemini.get_store(channel_id)
        if not store:
            raise HTTPException(
                status_code=404,
                detail=f"Channel not found: {channel_id}",
            )

        # Check capacity limits
        capacity_service = CapacityService(db)
        try:
            capacity_service.validate_upload(channel_id, actual_size)
        except CapacityExceededError as e:
            raise HTTPException(
                status_code=413,
                detail=str(e),
            )

        # Save to temp file for upload
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_name}") as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        try:
            # Upload to Gemini store
            operation = gemini.upload_file(channel_id, tmp_path)

            # Update capacity tracking
            capacity_service.update_after_upload(channel_id, actual_size)

            # Invalidate caches
            cache.invalidate_document_cache(channel_id)
            cache.invalidate_chat_cache(channel_id)

            logger.info(
                "Successfully imported file from Google Drive",
                file_name=file_name,
                channel_id=channel_id,
                document_id=operation.get("name"),
            )

            return ImportFileResponse(
                id=operation.get("name", ""),
                filename=file_name,
                status="processing" if not operation.get("done") else "completed",
                message=f"Successfully imported {file_name} from Google Drive",
            )

        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to import file from Google Drive",
            error=str(e),
            file_id=request.file_id,
            channel_id=channel_id,
        )
        if "invalid_grant" in str(e).lower() or "invalid credentials" in str(e).lower():
            raise HTTPException(
                status_code=401,
                detail="Access token is invalid or expired. Please re-authenticate."
            )
        raise HTTPException(status_code=500, detail=f"Failed to import file: {str(e)}")


@router.post("/refresh-token", response_model=TokenResponse)
async def refresh_access_token(
    refresh_token: str = Body(..., embed=True, description="OAuth refresh token"),
):
    """
    Refresh an expired access token using a refresh token.
    """
    try:
        from google.auth.transport.requests import Request

        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_oauth_client_id,
            client_secret=settings.google_oauth_client_secret,
        )

        credentials.refresh(Request())

        logger.info("Successfully refreshed OAuth access token")

        return TokenResponse(
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            expires_in=credentials.expiry.timestamp() if credentials.expiry else None,
            token_type="Bearer",
        )

    except Exception as e:
        logger.error("Failed to refresh access token", error=str(e))
        raise HTTPException(
            status_code=401,
            detail="Failed to refresh access token. Please re-authenticate."
        )
