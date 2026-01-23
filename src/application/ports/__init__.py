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
- SummarizationPort: Document and channel summarization
- TimelinePort: Timeline extraction from documents
- BriefingPort: Briefing document generation
- StudyGuidePort: Study guide generation
- QuizPort: Quiz generation
- PodcastScriptPort: Podcast script generation
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
from src.application.ports.summarization import SummarizationPort, SummaryDTO
from src.application.ports.timeline import (
    TimelinePort,
    TimelineEventDTO,
    BriefingPort,
    BriefingDTO,
    BriefingSectionDTO,
)
from src.application.ports.learning import (
    StudyGuidePort,
    StudyGuideDTO,
    StudySectionDTO,
    KeyConceptDTO,
    QuizPort,
    QuizDTO,
    QuizQuestionDTO,
    QuizChoiceDTO,
)
from src.application.ports.podcast import (
    PodcastScriptPort,
    PodcastScriptDTO,
    DialogueLineDTO,
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
    # Summarization
    "SummarizationPort",
    "SummaryDTO",
    # Timeline
    "TimelinePort",
    "TimelineEventDTO",
    # Briefing
    "BriefingPort",
    "BriefingDTO",
    "BriefingSectionDTO",
    # Study Guide
    "StudyGuidePort",
    "StudyGuideDTO",
    "StudySectionDTO",
    "KeyConceptDTO",
    # Quiz
    "QuizPort",
    "QuizDTO",
    "QuizQuestionDTO",
    "QuizChoiceDTO",
    # Podcast
    "PodcastScriptPort",
    "PodcastScriptDTO",
    "DialogueLineDTO",
]
