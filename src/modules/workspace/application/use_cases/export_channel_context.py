# -*- coding: utf-8 -*-
"""Export channel context resolver use case.

Resolves a channel ID to its metadata, ensuring local metadata exists.
No FastAPI/HTTP dependencies.
"""

from __future__ import annotations

import logging

from src.shared.kernel.contracts.ports.channel import ChannelPort
from src.shared.kernel.contracts.ports.persistence import (
    ChannelRepositoryPort,
    ChannelMetadataDTO,
)
from src.shared.kernel.contracts.errors.use_case_errors import ChannelNotFoundError

logger = logging.getLogger(__name__)


class ExportChannelContextUseCase:
    """Resolves a channel ID to validated metadata for export."""

    def __init__(
        self,
        channel_port: ChannelPort,
        channel_repo: ChannelRepositoryPort,
    ):
        self._channel_port = channel_port
        self._channel_repo = channel_repo

    def resolve(self, channel_id: str) -> ChannelMetadataDTO:
        """Resolve channel ID to local metadata.

        - Verifies channel exists in external store
        - Gets or creates local metadata record

        Raises:
            ChannelNotFoundError: Channel not found in external store.
        """
        channel = self._channel_port.get_channel(channel_id)
        if not channel:
            raise ChannelNotFoundError(channel_id)

        channel_meta = self._channel_repo.get_by_gemini_id(channel_id)
        if not channel_meta:
            channel_meta = self._channel_repo.create(
                gemini_store_id=channel_id,
                name=channel.display_name or "unknown",
            )

        return channel_meta
