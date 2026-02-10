# -*- coding: utf-8 -*-
"""Checkpoint store port — abstract interface for LangGraph checkpoint management."""

from abc import ABC, abstractmethod


class CheckpointStorePort(ABC):
    """Port for managing LangGraph conversation checkpoints."""

    @abstractmethod
    def delete_thread(self, thread_id: str) -> None:
        """Delete all checkpoints associated with a thread.

        Args:
            thread_id: The thread ID (typically a session_id) whose
                checkpoints should be removed.
        """
        ...
