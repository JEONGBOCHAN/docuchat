# -*- coding: utf-8 -*-
"""Tests for GoogleDriveIntegrationUseCase and OAuthStateSigner."""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.modules.workspace.application.services.oauth_state_signer import OAuthStateSigner
from src.modules.workspace.application.use_cases.google_drive_integration import (
    GoogleDriveIntegrationUseCase,
    InvalidOAuthStateError,
)
from src.shared.kernel.contracts.ports.google_drive import (
    GoogleDriveTokenDTO,
    GoogleDriveFileDTO,
    DownloadedDriveFileDTO,
)
from src.modules.workspace.application.use_cases.document_crud import DocumentUploadResultDTO


# ── OAuthStateSigner tests ─────────────────────────────────


class TestOAuthStateSigner:
    def _make_signer(self, secret="test-secret-key", ttl=600):
        return OAuthStateSigner(secret=secret, ttl_seconds=ttl)

    def test_create_and_verify_roundtrip(self):
        signer = self._make_signer()
        state = signer.create()
        assert signer.verify(state) is True

    def test_state_has_three_parts(self):
        signer = self._make_signer()
        state = signer.create()
        assert len(state.split(".")) == 3

    def test_tampered_signature_rejected(self):
        signer = self._make_signer()
        state = signer.create()
        parts = state.split(".")
        tampered = f"{parts[0]}.{parts[1]}.{'a' * 64}"
        assert signer.verify(tampered) is False

    def test_tampered_nonce_rejected(self):
        signer = self._make_signer()
        state = signer.create()
        parts = state.split(".")
        tampered = f"{'b' * 32}.{parts[1]}.{parts[2]}"
        assert signer.verify(tampered) is False

    def test_expired_state_rejected(self):
        signer = self._make_signer()
        state = signer.create()
        with patch(
            "src.modules.workspace.application.services.oauth_state_signer.time"
        ) as mock_time:
            mock_time.time.return_value = time.time() + 700
            assert signer.verify(state) is False

    def test_malformed_state_rejected(self):
        signer = self._make_signer()
        assert signer.verify("not-a-valid-state") is False
        assert signer.verify("only.two") is False
        assert signer.verify("") is False

    def test_invalid_timestamp_rejected(self):
        signer = self._make_signer()
        assert signer.verify("abc.not_a_number.def") is False

    def test_different_secret_rejected(self):
        signer1 = self._make_signer(secret="secret-one")
        state = signer1.create()
        signer2 = self._make_signer(secret="secret-two")
        assert signer2.verify(state) is False

    def test_unique_states(self):
        signer = self._make_signer()
        states = {signer.create() for _ in range(10)}
        assert len(states) == 10


# ── GoogleDriveIntegrationUseCase tests ────────────────────


class TestGoogleDriveIntegrationUseCase:
    @pytest.fixture()
    def drive_port(self):
        return MagicMock()

    @pytest.fixture()
    def signer(self):
        signer = OAuthStateSigner(secret="test-secret", ttl_seconds=600)
        return signer

    @pytest.fixture()
    def document_crud(self):
        return MagicMock()

    @pytest.fixture()
    def use_case(self, drive_port, signer, document_crud):
        return GoogleDriveIntegrationUseCase(
            drive_port=drive_port,
            state_signer=signer,
            document_crud=document_crud,
        )

    def test_get_auth_url(self, use_case, drive_port):
        drive_port.build_auth_url.return_value = "https://example.com/auth"
        auth_url, state = use_case.get_auth_url()
        assert auth_url == "https://example.com/auth"
        assert len(state.split(".")) == 3
        drive_port.build_auth_url.assert_called_once_with(state)

    def test_exchange_token_success(self, use_case, drive_port, signer):
        state = signer.create()
        expected = GoogleDriveTokenDTO(
            access_token="at", refresh_token="rt", expires_in=3600
        )
        drive_port.exchange_code.return_value = expected

        result = use_case.exchange_token("code123", state)
        assert result.access_token == "at"
        drive_port.exchange_code.assert_called_once_with("code123")

    def test_exchange_token_invalid_state(self, use_case):
        with pytest.raises(InvalidOAuthStateError):
            use_case.exchange_token("code", "bad.state.value")

    def test_refresh_token(self, use_case, drive_port):
        expected = GoogleDriveTokenDTO(
            access_token="new-at", refresh_token=None, expires_in=3600
        )
        drive_port.refresh_access_token.return_value = expected
        result = use_case.refresh_token("old-rt")
        assert result.access_token == "new-at"

    def test_list_files(self, use_case, drive_port):
        files = [
            GoogleDriveFileDTO(
                id="f1", name="test.pdf", mime_type="application/pdf",
                size=100, modified_time=None, icon_link=None,
                thumbnail_link=None, parents=None,
            )
        ]
        drive_port.list_files.return_value = (files, "next-token")
        result_files, next_token = use_case.list_files("at", None, None, 20)
        assert len(result_files) == 1
        assert next_token == "next-token"

    def test_import_file_success(self, use_case, drive_port, document_crud):
        downloaded = DownloadedDriveFileDTO(
            temp_path="/tmp/test.pdf",
            file_name="test.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
        )
        drive_port.download_to_temp.return_value = downloaded
        upload_result = DocumentUploadResultDTO(
            operation_name="op1", filename="test.pdf", done=True
        )
        document_crud.upload.return_value = upload_result

        with patch("os.unlink"):
            result = use_case.import_file("ch1", "at", "file1")

        assert result.operation_name == "op1"
        document_crud.upload.assert_called_once_with("ch1", "/tmp/test.pdf", "test.pdf", 1024)

    def test_import_file_cleans_up_temp_on_failure(self, use_case, drive_port, document_crud):
        downloaded = DownloadedDriveFileDTO(
            temp_path="/tmp/test.pdf",
            file_name="test.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
        )
        drive_port.download_to_temp.return_value = downloaded
        document_crud.upload.side_effect = RuntimeError("upload failed")

        with patch("os.unlink") as mock_unlink:
            with pytest.raises(RuntimeError, match="upload failed"):
                use_case.import_file("ch1", "at", "file1")
            mock_unlink.assert_called_once_with("/tmp/test.pdf")
