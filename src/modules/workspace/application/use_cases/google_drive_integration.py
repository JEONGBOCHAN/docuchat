# -*- coding: utf-8 -*-
"""Google Drive integration use case.

Orchestrates OAuth flow, file listing, and file import from Google Drive.
No HTTP/FastAPI dependencies — pure application logic.
"""

from __future__ import annotations

import logging
import os

from src.shared.kernel.contracts.ports.google_drive import (
    GoogleDrivePort,
    GoogleDriveTokenDTO,
    GoogleDriveFileDTO,
    DownloadedDriveFileDTO,
)
from src.modules.workspace.application.services.oauth_state_signer import OAuthStateSigner
from src.modules.workspace.application.use_cases.document_crud import (
    DocumentCrudUseCase,
    DocumentUploadResultDTO,
)

logger = logging.getLogger(__name__)


class InvalidOAuthStateError(Exception):
    """OAuth state verification failed."""
    pass


class GoogleDriveIntegrationUseCase:
    """Orchestrates Google Drive integration operations."""

    def __init__(
        self,
        drive_port: GoogleDrivePort,
        state_signer: OAuthStateSigner,
        document_crud: DocumentCrudUseCase,
    ):
        self._drive = drive_port
        self._signer = state_signer
        self._document_crud = document_crud

    def get_auth_url(self) -> tuple[str, str]:
        """Generate OAuth authorization URL with signed state.

        Returns:
            (auth_url, state) tuple.
        """
        state = self._signer.create()
        auth_url = self._drive.build_auth_url(state)
        logger.info("Generated Google OAuth authorization URL")
        return auth_url, state

    def exchange_token(self, code: str, state: str) -> GoogleDriveTokenDTO:
        """Exchange authorization code for tokens after verifying state.

        Raises:
            InvalidOAuthStateError: If state verification fails.
        """
        if not self._signer.verify(state):
            raise InvalidOAuthStateError(
                "Invalid or expired OAuth state parameter. Please retry authorization."
            )
        token = self._drive.exchange_code(code)
        logger.info("Successfully exchanged OAuth code for tokens")
        return token

    def refresh_token(self, refresh_token: str) -> GoogleDriveTokenDTO:
        """Refresh an expired access token."""
        token = self._drive.refresh_access_token(refresh_token)
        logger.info("Successfully refreshed OAuth access token")
        return token

    def list_files(
        self,
        access_token: str,
        folder_id: str | None,
        page_token: str | None,
        page_size: int,
    ) -> tuple[list[GoogleDriveFileDTO], str | None]:
        """List files from Google Drive."""
        files, next_token = self._drive.list_files(
            access_token, folder_id, page_token, page_size
        )
        logger.info("Listed Google Drive files", extra={"count": len(files), "folder_id": folder_id})
        return files, next_token

    def import_file(
        self,
        channel_id: str,
        access_token: str,
        file_id: str,
    ) -> DocumentUploadResultDTO:
        """Import a file from Google Drive into a channel.

        Downloads the file from Drive and delegates upload to DocumentCrudUseCase.

        Raises:
            ChannelNotFoundError: Channel not found.
            CapacityExceededError: Capacity limits exceeded.
        """
        downloaded: DownloadedDriveFileDTO | None = None
        try:
            downloaded = self._drive.download_to_temp(access_token, file_id)
            logger.info(
                "Importing file from Google Drive",
                extra={
                    "file_id": file_id,
                    "file_name": downloaded.file_name,
                    "mime_type": downloaded.mime_type,
                    "channel_id": channel_id,
                },
            )
            result = self._document_crud.upload(
                channel_id,
                downloaded.temp_path,
                downloaded.file_name,
                downloaded.size_bytes,
            )
            logger.info(
                "Successfully imported file from Google Drive",
                extra={
                    "file_name": downloaded.file_name,
                    "channel_id": channel_id,
                    "document_id": result.operation_name,
                },
            )
            return result
        finally:
            if downloaded:
                try:
                    os.unlink(downloaded.temp_path)
                except Exception:
                    pass
