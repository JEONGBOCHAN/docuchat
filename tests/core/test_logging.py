# -*- coding: utf-8 -*-
"""Tests for structured logging system."""

import logging
from io import StringIO
from unittest.mock import patch, MagicMock

import pytest
import structlog

from src.core.logging import (
    setup_logging,
    get_logger,
    bind_context,
    clear_context,
    unbind_context,
    get_log_level,
)


class TestLogging:
    """Tests for logging configuration."""

    def setup_method(self):
        """Reset logging state before each test."""
        structlog.reset_defaults()

    def test_get_log_level_default(self):
        """Test default log level is INFO."""
        with patch("src.core.logging.get_settings") as mock_settings:
            mock_settings.return_value.log_level = "INFO"
            assert get_log_level() == logging.INFO

    def test_get_log_level_debug(self):
        """Test DEBUG log level."""
        with patch("src.core.logging.get_settings") as mock_settings:
            mock_settings.return_value.log_level = "DEBUG"
            assert get_log_level() == logging.DEBUG

    def test_get_log_level_warning(self):
        """Test WARNING log level."""
        with patch("src.core.logging.get_settings") as mock_settings:
            mock_settings.return_value.log_level = "WARNING"
            assert get_log_level() == logging.WARNING

    def test_get_log_level_error(self):
        """Test ERROR log level."""
        with patch("src.core.logging.get_settings") as mock_settings:
            mock_settings.return_value.log_level = "ERROR"
            assert get_log_level() == logging.ERROR

    def test_get_log_level_invalid_defaults_to_info(self):
        """Test invalid log level defaults to INFO."""
        with patch("src.core.logging.get_settings") as mock_settings:
            mock_settings.return_value.log_level = "INVALID"
            assert get_log_level() == logging.INFO

    def test_setup_logging_configures_structlog(self):
        """Test that setup_logging configures structlog properly."""
        with patch("src.core.logging.get_settings") as mock_settings:
            mock_settings.return_value.log_level = "INFO"
            mock_settings.return_value.log_format = "console"
            mock_settings.return_value.is_production = False
            mock_settings.return_value.is_development = True

            setup_logging()

            # Verify structlog is configured
            logger = get_logger("test")
            assert logger is not None

    def test_get_logger_returns_bound_logger(self):
        """Test that get_logger returns a bound logger."""
        with patch("src.core.logging.get_settings") as mock_settings:
            mock_settings.return_value.log_level = "INFO"
            mock_settings.return_value.log_format = "console"
            mock_settings.return_value.is_production = False
            mock_settings.return_value.is_development = True

            setup_logging()
            logger = get_logger("test.module")

            assert logger is not None
            # Should be able to call log methods
            assert hasattr(logger, "info")
            assert hasattr(logger, "warning")
            assert hasattr(logger, "error")
            assert hasattr(logger, "debug")


class TestContextBinding:
    """Tests for context binding functions."""

    def setup_method(self):
        """Reset context before each test."""
        clear_context()

    def teardown_method(self):
        """Clear context after each test."""
        clear_context()

    def test_bind_context(self):
        """Test binding context variables."""
        bind_context(request_id="123", user_id=456)

        # Context should be available in structlog's contextvars
        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get("request_id") == "123"
        assert ctx.get("user_id") == 456

    def test_clear_context(self):
        """Test clearing context variables."""
        bind_context(request_id="123")
        clear_context()

        ctx = structlog.contextvars.get_contextvars()
        assert "request_id" not in ctx

    def test_unbind_context(self):
        """Test unbinding specific context variables."""
        bind_context(request_id="123", user_id=456, session_id="abc")
        unbind_context("request_id", "session_id")

        ctx = structlog.contextvars.get_contextvars()
        assert "request_id" not in ctx
        assert "session_id" not in ctx
        assert ctx.get("user_id") == 456
