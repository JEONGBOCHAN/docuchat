# -*- coding: utf-8 -*-
"""Google Drive integration port and DTOs."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GoogleDriveTokenDTO:
    access_token: str
    refresh_token: str | None
    expires_in: int | None
    token_type: str = "Bearer"


@dataclass
class GoogleDriveFileDTO:
    id: str
    name: str
    mime_type: str
    size: int | None
    modified_time: str | None
    icon_link: str | None
    thumbnail_link: str | None
    parents: list[str] | None


@dataclass
class DownloadedDriveFileDTO:
    temp_path: str
    file_name: str
    mime_type: str
    size_bytes: int


class GoogleDrivePort(ABC):
    @abstractmethod
    def build_auth_url(self, state: str) -> str: ...

    @abstractmethod
    def exchange_code(self, code: str) -> GoogleDriveTokenDTO: ...

    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> GoogleDriveTokenDTO: ...

    @abstractmethod
    def list_files(
        self, access_token: str, folder_id: str | None, page_token: str | None, page_size: int
    ) -> tuple[list[GoogleDriveFileDTO], str | None]: ...

    @abstractmethod
    def download_to_temp(self, access_token: str, file_id: str) -> DownloadedDriveFileDTO: ...
