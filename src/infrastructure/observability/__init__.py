# -*- coding: utf-8 -*-
"""
Observability Infrastructure.

Implementations of AgentEventSinkPort for different storage backends.

Current implementations:
- InMemoryEventStore: Simple in-memory storage (good for MVP/development)
- StateStoreAdapter: Bridges new events to legacy AgentStateStore (for migration)

Future implementations:
- RedisEventBus: For pub/sub and horizontal scaling
- PostgresEventStore: For persistent event sourcing
"""

from src.infrastructure.observability.event_store import InMemoryEventStore, get_event_store
from src.infrastructure.observability.state_store_adapter import (
    StateStoreAdapter,
    get_event_sink_adapter,
)

__all__ = [
    "InMemoryEventStore",
    "get_event_store",
    "StateStoreAdapter",
    "get_event_sink_adapter",
]
