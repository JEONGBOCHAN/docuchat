# -*- coding: utf-8 -*-
"""Tests for CompactionRunner — independent DB session per job."""

import threading
from unittest.mock import MagicMock, patch, call

import pytest

from src.infrastructure.compaction.runner import CompactionRunner


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


@pytest.fixture
def session_factory(mock_db):
    return MagicMock(return_value=mock_db)


@pytest.fixture
def mock_service():
    return MagicMock()


@pytest.fixture
def service_factory(mock_service):
    return MagicMock(return_value=mock_service)


@pytest.fixture
def runner(session_factory, service_factory):
    return CompactionRunner(
        session_factory=session_factory,
        service_factory=service_factory,
    )


class TestCompactionRunner:
    """Tests for CompactionRunner.submit and _run."""

    def test_submit_creates_independent_db_session(
        self, runner, session_factory, service_factory, mock_db, mock_service,
    ):
        """submit() should create a new DB session, build a service, run compaction, then close."""
        # Run synchronously via _run to avoid thread timing issues
        runner._run("sess_1")

        session_factory.assert_called_once()
        service_factory.assert_called_once_with(mock_db)
        mock_service.maybe_compact.assert_called_once_with("sess_1")
        mock_db.close.assert_called_once()

    def test_db_session_closed_on_success(
        self, runner, mock_db, mock_service,
    ):
        """DB session must be closed even after successful compaction."""
        runner._run("sess_1")
        mock_db.close.assert_called_once()

    def test_db_session_closed_on_failure(
        self, runner, session_factory, mock_db, mock_service,
    ):
        """DB session must be closed even when compaction raises an exception."""
        mock_service.maybe_compact.side_effect = RuntimeError("DB error")

        runner._run("sess_1")

        mock_db.close.assert_called_once()

    def test_submit_runs_in_background_thread(
        self, runner, session_factory, service_factory, mock_db, mock_service,
    ):
        """submit() should spawn a daemon thread that eventually calls _run."""
        done_event = threading.Event()
        original_run = runner._run

        def _tracked_run(session_id):
            original_run(session_id)
            done_event.set()

        runner._run = _tracked_run
        runner.submit("sess_bg")

        assert done_event.wait(timeout=5), "Background thread did not complete"
        mock_service.maybe_compact.assert_called_once_with("sess_bg")
        mock_db.close.assert_called_once()

    def test_exception_does_not_propagate(
        self, runner, mock_service, mock_db,
    ):
        """Exceptions from maybe_compact should be caught, not propagated."""
        mock_service.maybe_compact.side_effect = Exception("boom")

        # Should not raise
        runner._run("sess_err")
        mock_db.close.assert_called_once()

    def test_service_factory_receives_fresh_session(
        self, service_factory,
    ):
        """Each _run call should create a fresh DB session via session_factory."""
        db1 = MagicMock()
        db2 = MagicMock()
        factory = MagicMock(side_effect=[db1, db2])
        svc = MagicMock()
        svc_factory = MagicMock(return_value=svc)

        runner = CompactionRunner(session_factory=factory, service_factory=svc_factory)
        runner._run("sess_a")
        runner._run("sess_b")

        assert factory.call_count == 2
        svc_factory.assert_any_call(db1)
        svc_factory.assert_any_call(db2)
        db1.close.assert_called_once()
        db2.close.assert_called_once()
