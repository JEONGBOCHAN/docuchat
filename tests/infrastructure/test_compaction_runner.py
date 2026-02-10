# -*- coding: utf-8 -*-
"""Tests for CompactionRunner — independent DB sessions + bounded thread pool + coalescing."""

import threading
import time
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
    r = CompactionRunner(
        session_factory=session_factory,
        service_factory=service_factory,
        max_workers=2,
    )
    yield r
    r.shutdown(wait=True)


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

    def test_submit_runs_in_thread_pool(
        self, runner, session_factory, service_factory, mock_db, mock_service,
    ):
        """submit() should execute via the thread pool and eventually complete."""
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

    def test_service_factory_receives_fresh_session(self):
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
        runner.shutdown(wait=True)


class TestCoalescing:
    """Tests for session-level duplicate prevention."""

    def test_duplicate_session_id_is_skipped(self):
        """Second submit for the same session_id while first is running should be skipped."""
        block_event = threading.Event()
        run_count = 0
        run_lock = threading.Lock()

        def slow_compact(session_id):
            nonlocal run_count
            block_event.wait(timeout=5)
            with run_lock:
                run_count += 1

        svc = MagicMock()
        svc.maybe_compact.side_effect = slow_compact
        svc_factory = MagicMock(return_value=svc)
        db = MagicMock()
        session_factory = MagicMock(return_value=db)

        runner = CompactionRunner(
            session_factory=session_factory,
            service_factory=svc_factory,
            max_workers=4,
        )

        # First submit — will block in slow_compact
        runner.submit("sess_dup")
        time.sleep(0.1)  # Let thread start

        # Second submit — same session_id, should be skipped
        runner.submit("sess_dup")

        # Release the blocker
        block_event.set()
        runner.shutdown(wait=True)

        # Only one compaction should have run
        assert run_count == 1

    def test_different_session_ids_run_concurrently(self):
        """Different session_ids should both be executed."""
        completed = set()
        lock = threading.Lock()

        def track_compact(session_id):
            with lock:
                completed.add(session_id)

        svc = MagicMock()
        svc.maybe_compact.side_effect = track_compact
        svc_factory = MagicMock(return_value=svc)
        db = MagicMock()
        session_factory = MagicMock(return_value=db)

        runner = CompactionRunner(
            session_factory=session_factory,
            service_factory=svc_factory,
            max_workers=4,
        )

        runner.submit("sess_a")
        runner.submit("sess_b")
        runner.shutdown(wait=True)

        assert completed == {"sess_a", "sess_b"}

    def test_pending_set_cleared_after_completion(self):
        """After a job completes, its session_id should be removed from pending."""
        svc = MagicMock()
        svc_factory = MagicMock(return_value=svc)
        db = MagicMock()
        session_factory = MagicMock(return_value=db)

        runner = CompactionRunner(
            session_factory=session_factory,
            service_factory=svc_factory,
            max_workers=2,
        )

        runner.submit("sess_x")
        runner.shutdown(wait=True)

        # pending should be empty
        assert "sess_x" not in runner._pending

    def test_pending_cleared_on_failure(self):
        """Even if compaction fails, session_id should be removed from pending."""
        svc = MagicMock()
        svc.maybe_compact.side_effect = RuntimeError("fail")
        svc_factory = MagicMock(return_value=svc)
        db = MagicMock()
        session_factory = MagicMock(return_value=db)

        runner = CompactionRunner(
            session_factory=session_factory,
            service_factory=svc_factory,
            max_workers=2,
        )

        runner.submit("sess_fail")
        runner.shutdown(wait=True)

        assert "sess_fail" not in runner._pending


class TestBoundedWorkers:
    """Tests for ThreadPoolExecutor worker limit."""

    def test_max_workers_respected(self):
        """No more than max_workers threads should run concurrently."""
        concurrent_count = 0
        max_concurrent = 0
        lock = threading.Lock()
        barrier = threading.Event()

        def counting_compact(session_id):
            nonlocal concurrent_count, max_concurrent
            with lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
            barrier.wait(timeout=5)
            with lock:
                concurrent_count -= 1

        svc = MagicMock()
        svc.maybe_compact.side_effect = counting_compact
        svc_factory = MagicMock(return_value=svc)
        db = MagicMock()
        session_factory = MagicMock(return_value=db)

        runner = CompactionRunner(
            session_factory=session_factory,
            service_factory=svc_factory,
            max_workers=2,
        )

        # Submit 4 jobs with different session_ids
        for i in range(4):
            runner.submit(f"sess_{i}")

        time.sleep(0.3)  # Let threads start
        barrier.set()  # Release all
        runner.shutdown(wait=True)

        assert max_concurrent <= 2


class TestSubmitFailure:
    """Tests for submit() failure handling — _pending cleanup."""

    def test_submit_failure_clears_pending(self):
        """If executor.submit raises, session_id must be removed from _pending."""
        svc = MagicMock()
        svc_factory = MagicMock(return_value=svc)
        db = MagicMock()
        session_factory = MagicMock(return_value=db)

        runner = CompactionRunner(
            session_factory=session_factory,
            service_factory=svc_factory,
            max_workers=2,
        )
        # Force executor.submit to fail
        runner._executor.submit = MagicMock(side_effect=RuntimeError("pool shut down"))

        # Should not raise
        runner.submit("sess_broken")

        # _pending must be clean
        assert "sess_broken" not in runner._pending

    def test_submit_failure_does_not_block_retry(self):
        """After a submit failure, the same session_id can be submitted again."""
        svc = MagicMock()
        svc_factory = MagicMock(return_value=svc)
        db = MagicMock()
        session_factory = MagicMock(return_value=db)

        runner = CompactionRunner(
            session_factory=session_factory,
            service_factory=svc_factory,
            max_workers=2,
        )

        # First submit fails
        original_submit = runner._executor.submit
        runner._executor.submit = MagicMock(side_effect=RuntimeError("fail"))
        runner.submit("sess_retry")
        assert "sess_retry" not in runner._pending

        # Restore real submit and retry — should succeed
        runner._executor.submit = original_submit
        runner.submit("sess_retry")
        runner.shutdown(wait=True)

        svc.maybe_compact.assert_called_once_with("sess_retry")


class TestShutdownHelper:
    """Tests for shutdown_compaction_runner container helper."""

    def test_shutdown_noop_when_no_instance(self):
        """shutdown_compaction_runner should be safe to call without a runner instance."""
        from src.infrastructure.di.container import (
            _get_compaction_runner,
            shutdown_compaction_runner,
        )

        saved = getattr(_get_compaction_runner, "_instance", None)
        if hasattr(_get_compaction_runner, "_instance"):
            delattr(_get_compaction_runner, "_instance")

        try:
            # Should not raise
            shutdown_compaction_runner(wait=False)
        finally:
            if saved is not None:
                _get_compaction_runner._instance = saved

    def test_shutdown_calls_runner_shutdown(self):
        """shutdown_compaction_runner should call shutdown on the runner instance."""
        from src.infrastructure.di.container import (
            _get_compaction_runner,
            shutdown_compaction_runner,
        )

        mock_runner = MagicMock()
        saved = getattr(_get_compaction_runner, "_instance", None)
        _get_compaction_runner._instance = mock_runner

        try:
            shutdown_compaction_runner(wait=False)
            mock_runner.shutdown.assert_called_once_with(wait=False)
        finally:
            # shutdown now deletes _instance; restore saved if needed
            if saved is not None:
                _get_compaction_runner._instance = saved

    def test_shutdown_exception_does_not_propagate(self):
        """Even if runner.shutdown raises, shutdown_compaction_runner should not propagate."""
        from src.infrastructure.di.container import (
            _get_compaction_runner,
            shutdown_compaction_runner,
        )

        mock_runner = MagicMock()
        mock_runner.shutdown.side_effect = RuntimeError("pool error")
        saved = getattr(_get_compaction_runner, "_instance", None)
        _get_compaction_runner._instance = mock_runner

        try:
            # Should not raise
            shutdown_compaction_runner(wait=False)
        finally:
            if saved is not None:
                _get_compaction_runner._instance = saved

    def test_shutdown_removes_singleton_instance(self):
        """After shutdown, the singleton _instance must be removed."""
        from src.infrastructure.di.container import (
            _get_compaction_runner,
            shutdown_compaction_runner,
        )

        mock_runner = MagicMock()
        saved = getattr(_get_compaction_runner, "_instance", None)
        _get_compaction_runner._instance = mock_runner

        try:
            shutdown_compaction_runner(wait=False)
            assert not hasattr(_get_compaction_runner, "_instance")
        finally:
            if saved is not None:
                _get_compaction_runner._instance = saved

    def test_shutdown_allows_fresh_recreation(self):
        """After shutdown, _get_compaction_runner must return a new instance."""
        from src.infrastructure.di.container import (
            _get_compaction_runner,
            shutdown_compaction_runner,
        )

        saved = getattr(_get_compaction_runner, "_instance", None)

        try:
            inst1 = _get_compaction_runner()
            shutdown_compaction_runner(wait=False)
            inst2 = _get_compaction_runner()

            assert inst1 is not inst2
        finally:
            # Clean up: shut down whatever is there and restore
            shutdown_compaction_runner(wait=True)
            if saved is not None:
                _get_compaction_runner._instance = saved
