# -*- coding: utf-8 -*-
"""
Application Ports (Interfaces).

Ports define the boundaries between the application layer and external systems.
They are abstract interfaces that infrastructure adapters implement.

This follows the Ports & Adapters (Hexagonal) architecture pattern.

Available Ports:
- AgentEventSinkPort: Observability/event emission
- DocumentSearchPort: Document retrieval (RAG)
- WebSearchPort: Web search (Tavily, Brave, etc.)
- LLMPort: LLM text generation
- AgentRunnerPort: Agent execution framework abstraction
- FAQGenerationPort: FAQ generation from documents
- CitationSearchPort: Document search with inline citations
"""

from src.application.ports.observability import AgentEventSinkPort
from src.application.ports.document_search import DocumentSearchPort, SearchResult
from src.application.ports.web_search import WebSearchPort, WebSearchResult
from src.application.ports.llm import LLMPort, LLMMessage, LLMResponse
from src.application.ports.agent_runner import (
    AgentRunnerPort,
    AgentTool,
    AgentResult,
    AgentConfig,
)
from src.application.ports.faq_generation import FAQGenerationPort, FAQItemDTO
from src.application.ports.citation_search import (
    CitationSearchPort,
    CitationDTO,
    CitationResultDTO,
)

__all__ = [
    # Observability
    "AgentEventSinkPort",
    # Document Search
    "DocumentSearchPort",
    "SearchResult",
    # Web Search
    "WebSearchPort",
    "WebSearchResult",
    # LLM
    "LLMPort",
    "LLMMessage",
    "LLMResponse",
    # Agent Runner
    "AgentRunnerPort",
    "AgentTool",
    "AgentResult",
    "AgentConfig",
    # FAQ Generation
    "FAQGenerationPort",
    "FAQItemDTO",
    # Citation Search
    "CitationSearchPort",
    "CitationDTO",
    "CitationResultDTO",
]
