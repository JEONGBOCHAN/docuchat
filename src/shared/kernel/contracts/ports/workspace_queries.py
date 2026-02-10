# -*- coding: utf-8 -*-
"""Workspace query ports for cross-module use."""

from abc import ABC, abstractmethod


class ChannelDocumentSummaryQueryPort(ABC):
    """Port for querying channel document summaries.

    Allows other modules to obtain a formatted context string
    of document summaries without depending on workspace internals.
    """

    @abstractmethod
    def build_context_string(self, channel_id: str, limit: int = 10) -> str:
        """Build a formatted string of document summaries for system prompt.

        Args:
            channel_id: The channel (store) ID
            limit: Maximum number of summaries to include

        Returns:
            Formatted string describing available documents,
            or empty string if no summaries exist.
        """
        ...
