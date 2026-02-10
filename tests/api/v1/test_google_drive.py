# -*- coding: utf-8 -*-
"""Tests for Google Drive OAuth HMAC state functions."""

import time
from unittest.mock import patch

import pytest


class TestOAuthStateHMAC:
    """Test HMAC-signed stateless OAuth state."""

    def _get_functions(self):
        """Import functions under test with mocked settings."""
        from src.modules.workspace.presentation.api.google_drive import (
            _create_oauth_state,
            _verify_oauth_state,
        )
        return _create_oauth_state, _verify_oauth_state

    @patch("src.modules.workspace.presentation.api.google_drive.settings")
    def test_create_and_verify_roundtrip(self, mock_settings):
        mock_settings.google_oauth_client_secret = "test-secret-key"
        create, verify = self._get_functions()

        state = create()
        assert verify(state) is True

    @patch("src.modules.workspace.presentation.api.google_drive.settings")
    def test_state_has_three_parts(self, mock_settings):
        mock_settings.google_oauth_client_secret = "test-secret-key"
        create, _ = self._get_functions()

        state = create()
        parts = state.split(".")
        assert len(parts) == 3

    @patch("src.modules.workspace.presentation.api.google_drive.settings")
    def test_tampered_signature_rejected(self, mock_settings):
        mock_settings.google_oauth_client_secret = "test-secret-key"
        create, verify = self._get_functions()

        state = create()
        parts = state.split(".")
        # Tamper with signature
        tampered = f"{parts[0]}.{parts[1]}.{'a' * 64}"
        assert verify(tampered) is False

    @patch("src.modules.workspace.presentation.api.google_drive.settings")
    def test_tampered_nonce_rejected(self, mock_settings):
        mock_settings.google_oauth_client_secret = "test-secret-key"
        create, verify = self._get_functions()

        state = create()
        parts = state.split(".")
        tampered = f"{'b' * 32}.{parts[1]}.{parts[2]}"
        assert verify(tampered) is False

    @patch("src.modules.workspace.presentation.api.google_drive.settings")
    def test_expired_state_rejected(self, mock_settings):
        mock_settings.google_oauth_client_secret = "test-secret-key"
        create, verify = self._get_functions()

        # Create state, then fast-forward time past TTL
        state = create()
        with patch("src.modules.workspace.presentation.api.google_drive.time") as mock_time:
            mock_time.time.return_value = time.time() + 700  # 700s > 600s TTL
            assert verify(state) is False

    @patch("src.modules.workspace.presentation.api.google_drive.settings")
    def test_malformed_state_rejected(self, mock_settings):
        mock_settings.google_oauth_client_secret = "test-secret-key"
        _, verify = self._get_functions()

        assert verify("not-a-valid-state") is False
        assert verify("only.two") is False
        assert verify("") is False

    @patch("src.modules.workspace.presentation.api.google_drive.settings")
    def test_invalid_timestamp_rejected(self, mock_settings):
        mock_settings.google_oauth_client_secret = "test-secret-key"
        _, verify = self._get_functions()

        assert verify("abc.not_a_number.def") is False

    @patch("src.modules.workspace.presentation.api.google_drive.settings")
    def test_different_secret_rejected(self, mock_settings):
        mock_settings.google_oauth_client_secret = "secret-one"
        create, _ = self._get_functions()
        state = create()

        # Change secret
        mock_settings.google_oauth_client_secret = "secret-two"
        _, verify = self._get_functions()
        assert verify(state) is False

    @patch("src.modules.workspace.presentation.api.google_drive.settings")
    def test_unique_states(self, mock_settings):
        mock_settings.google_oauth_client_secret = "test-secret-key"
        create, _ = self._get_functions()

        states = {create() for _ in range(10)}
        assert len(states) == 10
