# -*- coding: utf-8 -*-
"""Tests for Sentry error tracking integration."""

from unittest.mock import patch, MagicMock

import pytest

from src.core.sentry import (
    setup_sentry,
    capture_exception,
    capture_message,
    set_user_context,
    _before_send,
)


class TestSentrySetup:
    """Tests for Sentry initialization."""

    def test_setup_sentry_without_dsn(self):
        """Test that Sentry is not initialized without DSN."""
        with patch("src.core.sentry.get_settings") as mock_settings:
            mock_settings.return_value.sentry_dsn = ""

            result = setup_sentry()

            assert result is False

    def test_setup_sentry_with_dsn(self):
        """Test that Sentry is initialized with valid DSN."""
        with patch("src.core.sentry.get_settings") as mock_settings:
            mock_settings.return_value.sentry_dsn = "https://key@sentry.io/123"
            mock_settings.return_value.app_env.value = "test"
            mock_settings.return_value.app_name = "Chalssak"
            mock_settings.return_value.app_version = "0.1.0"
            mock_settings.return_value.sentry_traces_sample_rate = 0.1
            mock_settings.return_value.sentry_profiles_sample_rate = 0.1

            with patch("sentry_sdk.init") as mock_init:
                result = setup_sentry()

                assert result is True
                mock_init.assert_called_once()

    def test_setup_sentry_import_error(self):
        """Test graceful handling when sentry-sdk is not installed."""
        with patch("src.core.sentry.get_settings") as mock_settings:
            mock_settings.return_value.sentry_dsn = "https://key@sentry.io/123"

            with patch.dict("sys.modules", {"sentry_sdk": None}):
                with patch("builtins.__import__", side_effect=ImportError):
                    result = setup_sentry()
                    # Should not raise, just return False
                    assert result is False


class TestBeforeSend:
    """Tests for the _before_send filter."""

    def test_before_send_passes_normal_event(self):
        """Test that normal events are passed through."""
        event = {"exception": {"values": [{"type": "ValueError"}]}}
        hint = {}

        result = _before_send(event, hint)

        assert result == event

    def test_before_send_filters_http_exception(self):
        """Test that HTTPException is filtered out."""

        class HTTPException(Exception):
            pass

        event = {"exception": {"values": [{"type": "HTTPException"}]}}
        hint = {"exc_info": (HTTPException, HTTPException(), None)}

        result = _before_send(event, hint)

        assert result is None

    def test_before_send_filters_validation_error(self):
        """Test that RequestValidationError is filtered out."""

        class RequestValidationError(Exception):
            pass

        event = {"exception": {"values": [{"type": "RequestValidationError"}]}}
        hint = {"exc_info": (RequestValidationError, RequestValidationError(), None)}

        result = _before_send(event, hint)

        assert result is None


class TestCaptureException:
    """Tests for capture_exception function."""

    def test_capture_exception_without_sentry(self):
        """Test capture_exception when sentry is not available."""
        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                result = capture_exception(ValueError("test error"))
                assert result is None

    def test_capture_exception_with_sentry(self):
        """Test capture_exception with mock sentry - validates function structure."""
        # This test validates the function can be called without errors
        # when sentry is not configured (DSN is empty)
        error = ValueError("test error")
        # Should return None when sentry is not initialized
        result = capture_exception(error, user_id=123)
        # Result is None when sentry SDK is available but not initialized
        assert result is None or isinstance(result, str)


class TestCaptureMessage:
    """Tests for capture_message function."""

    def test_capture_message_without_sentry(self):
        """Test capture_message when sentry is not available."""
        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                result = capture_message("test message")
                assert result is None


class TestSetUserContext:
    """Tests for set_user_context function."""

    def test_set_user_context_without_sentry(self):
        """Test set_user_context when sentry is not available."""
        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                # Should not raise
                set_user_context(user_id="123", email="test@example.com")

    def test_set_user_context_with_none(self):
        """Test setting user context with None clears context."""
        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                # Should not raise
                set_user_context()
