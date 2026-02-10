# -*- coding: utf-8 -*-
"""Google Drive adapter — concentrates all Google SDK imports."""

from __future__ import annotations

import tempfile

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from src.core.config import get_settings
from src.shared.kernel.contracts.ports.google_drive import (
    GoogleDrivePort,
    GoogleDriveTokenDTO,
    GoogleDriveFileDTO,
    DownloadedDriveFileDTO,
)

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]

SUPPORTED_MIMES = [
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.google-apps.folder",
]


class GoogleDriveAdapter(GoogleDrivePort):
    """Adapter wrapping Google Drive SDK operations."""

    def __init__(self):
        self._settings = get_settings()

    def _create_flow(self) -> Flow:
        client_config = {
            "web": {
                "client_id": self._settings.google_oauth_client_id,
                "client_secret": self._settings.google_oauth_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self._settings.google_oauth_redirect_uri],
            }
        }
        return Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=self._settings.google_oauth_redirect_uri,
        )

    def build_auth_url(self, state: str) -> str:
        flow = self._create_flow()
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )
        return auth_url

    def exchange_code(self, code: str) -> GoogleDriveTokenDTO:
        flow = self._create_flow()
        flow.fetch_token(code=code)
        creds = flow.credentials
        return GoogleDriveTokenDTO(
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            expires_in=int(creds.expiry.timestamp()) if creds.expiry else None,
            token_type="Bearer",
        )

    def refresh_access_token(self, refresh_token: str) -> GoogleDriveTokenDTO:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self._settings.google_oauth_client_id,
            client_secret=self._settings.google_oauth_client_secret,
        )
        creds.refresh(Request())
        return GoogleDriveTokenDTO(
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            expires_in=int(creds.expiry.timestamp()) if creds.expiry else None,
            token_type="Bearer",
        )

    def list_files(
        self,
        access_token: str,
        folder_id: str | None,
        page_token: str | None,
        page_size: int,
    ) -> tuple[list[GoogleDriveFileDTO], str | None]:
        creds = Credentials(token=access_token)
        service = build("drive", "v3", credentials=creds)

        mime_query = " or ".join([f"mimeType='{m}'" for m in SUPPORTED_MIMES])
        parent = folder_id or "root"
        query = f"'{parent}' in parents and ({mime_query}) and trashed=false"

        results = (
            service.files()
            .list(
                q=query,
                pageSize=page_size,
                pageToken=page_token,
                fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, iconLink, thumbnailLink, parents)",
                orderBy="folder,name",
            )
            .execute()
        )

        files = [
            GoogleDriveFileDTO(
                id=f["id"],
                name=f["name"],
                mime_type=f["mimeType"],
                size=int(f["size"]) if f.get("size") else None,
                modified_time=f.get("modifiedTime"),
                icon_link=f.get("iconLink"),
                thumbnail_link=f.get("thumbnailLink"),
                parents=f.get("parents"),
            )
            for f in results.get("files", [])
        ]
        return files, results.get("nextPageToken")

    def download_to_temp(self, access_token: str, file_id: str) -> DownloadedDriveFileDTO:
        creds = Credentials(token=access_token)
        service = build("drive", "v3", credentials=creds)

        meta = service.files().get(fileId=file_id, fields="id, name, mimeType, size").execute()
        file_name = meta.get("name", "unknown")
        mime_type = meta.get("mimeType", "")

        # Handle Google Docs export
        if mime_type.startswith("application/vnd.google-apps."):
            if mime_type == "application/vnd.google-apps.document":
                export_mime = "application/pdf"
                file_name = f"{file_name}.pdf"
            else:
                raise ValueError(f"Unsupported Google Docs type: {mime_type}")
            media_request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            media_request = service.files().get_media(fileId=file_id)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_name}")
        try:
            downloader = MediaIoBaseDownload(tmp, media_request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            size = tmp.tell()
        finally:
            tmp.close()

        return DownloadedDriveFileDTO(
            temp_path=tmp.name,
            file_name=file_name,
            mime_type=mime_type,
            size_bytes=size,
        )
