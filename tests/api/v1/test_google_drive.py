# -*- coding: utf-8 -*-
"""Tests for Google Drive API endpoints.

Tests router-level behavior: HTTP mapping, error codes, dependency injection.
Business logic tests are in tests/modules/workspace/application/use_cases/.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.modules.workspace.application.use_cases.google_drive_integration import (
    GoogleDriveIntegrationUseCase,
    InvalidOAuthStateError,
)
from src.shared.kernel.contracts.ports.google_drive import (
    GoogleDriveTokenDTO,
    GoogleDriveFileDTO,
)
from src.modules.workspace.application.use_cases.document_crud import DocumentUploadResultDTO
from src.shared.kernel.contracts.errors.use_case_errors import (
    ChannelNotFoundError,
    ServiceNotConfiguredError,
    FileValidationError,
)
from src.modules.workspace.domain.exceptions import CapacityExceededError


@pytest.fixture()
def mock_use_case():
    return MagicMock(spec=GoogleDriveIntegrationUseCase)


@pytest.fixture()
def client(mock_use_case):
    from src.main import app
    from src.modules.workspace.presentation.api.google_drive import _get_use_case

    app.dependency_overrides[_get_use_case] = lambda: mock_use_case
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


class TestGetAuthUrl:
    def test_success(self, client, mock_use_case):
        mock_use_case.get_auth_url.return_value = ("https://auth.example.com", "state123")
        resp = client.get("/api/v1/integrations/google-drive/auth-url")
        assert resp.status_code == 200
        data = resp.json()
        assert data["auth_url"] == "https://auth.example.com"
        assert data["state"] == "state123"

    def test_failure_returns_500(self, client, mock_use_case):
        mock_use_case.get_auth_url.side_effect = RuntimeError("boom")
        resp = client.get("/api/v1/integrations/google-drive/auth-url")
        assert resp.status_code == 500

    def test_not_configured_returns_503(self, client, mock_use_case):
        mock_use_case.get_auth_url.side_effect = ServiceNotConfiguredError(
            "google_drive", missing_fields=["GOOGLE_OAUTH_CLIENT_ID"]
        )
        resp = client.get("/api/v1/integrations/google-drive/auth-url")
        assert resp.status_code == 503
        assert "google_drive" in resp.json()["detail"]


class TestExchangeToken:
    def test_success(self, client, mock_use_case):
        mock_use_case.exchange_token.return_value = GoogleDriveTokenDTO(
            access_token="at", refresh_token="rt", expires_in=3600
        )
        resp = client.post(
            "/api/v1/integrations/google-drive/token",
            json={"code": "authcode", "state": "valid-state"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "at"

    def test_invalid_state_returns_400(self, client, mock_use_case):
        mock_use_case.exchange_token.side_effect = InvalidOAuthStateError("bad state")
        resp = client.post(
            "/api/v1/integrations/google-drive/token",
            json={"code": "authcode", "state": "bad"},
        )
        assert resp.status_code == 400

    def test_not_configured_returns_503(self, client, mock_use_case):
        mock_use_case.exchange_token.side_effect = ServiceNotConfiguredError(
            "google_drive", missing_fields=["GOOGLE_OAUTH_CLIENT_SECRET"]
        )
        resp = client.post(
            "/api/v1/integrations/google-drive/token",
            json={"code": "authcode", "state": "some-state"},
        )
        assert resp.status_code == 503


class TestListFiles:
    def test_success(self, client, mock_use_case):
        files = [
            GoogleDriveFileDTO(
                id="f1", name="test.pdf", mime_type="application/pdf",
                size=100, modified_time=None, icon_link=None,
                thumbnail_link=None, parents=None,
            )
        ]
        mock_use_case.list_files.return_value = (files, None)
        resp = client.get(
            "/api/v1/integrations/google-drive/files",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["files"]) == 1
        assert data["files"][0]["name"] == "test.pdf"

    def test_missing_bearer_returns_401(self, client):
        resp = client.get(
            "/api/v1/integrations/google-drive/files",
            headers={"Authorization": "InvalidFormat"},
        )
        assert resp.status_code == 401


class TestImportFile:
    def test_success(self, client, mock_use_case):
        mock_use_case.import_file.return_value = DocumentUploadResultDTO(
            operation_name="op1", filename="test.pdf", done=True
        )
        resp = client.post(
            "/api/v1/integrations/google-drive/import/ch1",
            json={"file_id": "f1", "access_token": "at"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "op1"
        assert data["status"] == "completed"

    def test_channel_not_found_returns_404(self, client, mock_use_case):
        mock_use_case.import_file.side_effect = ChannelNotFoundError("ch1")
        resp = client.post(
            "/api/v1/integrations/google-drive/import/ch1",
            json={"file_id": "f1", "access_token": "at"},
        )
        assert resp.status_code == 404

    def test_capacity_exceeded_returns_413(self, client, mock_use_case):
        mock_use_case.import_file.side_effect = CapacityExceededError(
            "limit reached", limit_type="size", current=100.0, limit=50.0
        )
        resp = client.post(
            "/api/v1/integrations/google-drive/import/ch1",
            json={"file_id": "f1", "access_token": "at"},
        )
        assert resp.status_code == 413

    def test_unsupported_type_returns_400(self, client, mock_use_case):
        mock_use_case.import_file.side_effect = FileValidationError(
            "Unsupported Google Docs type: application/vnd.google-apps.spreadsheet"
        )
        resp = client.post(
            "/api/v1/integrations/google-drive/import/ch1",
            json={"file_id": "f1", "access_token": "at"},
        )
        assert resp.status_code == 400
        assert "Unsupported" in resp.json()["detail"]


class TestRefreshToken:
    def test_success(self, client, mock_use_case):
        mock_use_case.refresh_token.return_value = GoogleDriveTokenDTO(
            access_token="new-at", refresh_token=None, expires_in=3600
        )
        resp = client.post(
            "/api/v1/integrations/google-drive/refresh-token",
            json={"refresh_token": "old-rt"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "new-at"

    def test_failure_returns_401(self, client, mock_use_case):
        mock_use_case.refresh_token.side_effect = RuntimeError("failed")
        resp = client.post(
            "/api/v1/integrations/google-drive/refresh-token",
            json={"refresh_token": "bad"},
        )
        assert resp.status_code == 401

    def test_not_configured_returns_503(self, client, mock_use_case):
        mock_use_case.refresh_token.side_effect = ServiceNotConfiguredError(
            "google_drive", missing_fields=["GOOGLE_OAUTH_CLIENT_ID"]
        )
        resp = client.post(
            "/api/v1/integrations/google-drive/refresh-token",
            json={"refresh_token": "some-rt"},
        )
        assert resp.status_code == 503
