# -*- coding: utf-8 -*-
"""Adapter that wraps LangGraph's BaseCheckpointSaver as a CheckpointStorePort."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.shared.kernel.contracts.ports.checkpoint import CheckpointStorePort

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver

logger = logging.getLogger(__name__)


class LangGraphCheckpointAdapter(CheckpointStorePort):
    """Adapts LangGraph's BaseCheckpointSaver to the CheckpointStorePort interface."""

    def __init__(self, checkpointer: BaseCheckpointSaver):
        self._checkpointer = checkpointer

    def delete_thread(self, thread_id: str) -> None:
        """Delete all checkpoints for the given thread_id."""
        self._checkpointer.delete_thread(thread_id)
