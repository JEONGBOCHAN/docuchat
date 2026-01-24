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
- ChannelPort: Channel (File Search Store) CRUD operations
- DocumentPort: Document operations within channels

Persistence Ports (Repository abstractions):
- ChannelRepositoryPort: Channel metadata CRUD
- ChatHistoryRepositoryPort: Chat message persistence
- ChatSessionRepositoryPort: Chat session management
- NoteRepositoryPort: Note CRUD
- FavoriteRepositoryPort: Favorites management
- SearchHistoryRepositoryPort: Search history
- TrashRepositoryPort: Soft delete / trash operations
- AudioRepositoryPort: Audio overview persistence

External Service Ports:
- YouTubePort: YouTube transcript extraction
- CrawlerPort: URL content crawling
- TTSPort: Text-to-Speech synthesis

Infrastructure Ports:
- CachePort: Caching operations
- ApiMetricsPort: API metrics tracking
- SchedulerPort: Background task scheduling
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
from src.application.ports.channel import ChannelPort, ChannelDTO
from src.application.ports.document import DocumentPort, DocumentDTO, UploadResultDTO

# Persistence Ports
from src.application.ports.persistence import (
    # DTOs
    ChannelMetadataDTO,
    ChatMessageDTO,
    ChatSessionDTO,
    NoteDTO,
    FavoriteDTO,
    SearchHistoryDTO,
    TrashItemDTO,
    AudioOverviewDTO,
    # Ports
    ChannelRepositoryPort,
    ChatHistoryRepositoryPort,
    ChatSessionRepositoryPort,
    NoteRepositoryPort,
    FavoriteRepositoryPort,
    SearchHistoryRepositoryPort,
    TrashRepositoryPort,
    AudioRepositoryPort,
)

# External Service Ports
from src.application.ports.external_services import (
    # DTOs
    YouTubeTranscriptDTO,
    YouTubeMetadataDTO,
    CrawlResultDTO,
    TTSResultDTO,
    # Ports
    YouTubePort,
    CrawlerPort,
    TTSPort,
)

# Cache Port
from src.application.ports.cache import CachePort

# Infrastructure Ports
from src.application.ports.infrastructure import (
    # DTOs
    EndpointMetricsDTO,
    ApiStatsDTO,
    ScheduledJobDTO,
    JobHistoryDTO,
    # Ports
    ApiMetricsPort,
    SchedulerPort,
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
    # Channel
    "ChannelPort",
    "ChannelDTO",
    # Document
    "DocumentPort",
    "DocumentDTO",
    "UploadResultDTO",
    # Persistence Ports
    "ChannelMetadataDTO",
    "ChatMessageDTO",
    "ChatSessionDTO",
    "NoteDTO",
    "FavoriteDTO",
    "SearchHistoryDTO",
    "TrashItemDTO",
    "AudioOverviewDTO",
    "ChannelRepositoryPort",
    "ChatHistoryRepositoryPort",
    "ChatSessionRepositoryPort",
    "NoteRepositoryPort",
    "FavoriteRepositoryPort",
    "SearchHistoryRepositoryPort",
    "TrashRepositoryPort",
    "AudioRepositoryPort",
    # External Service Ports
    "YouTubeTranscriptDTO",
    "YouTubeMetadataDTO",
    "CrawlResultDTO",
    "TTSResultDTO",
    "YouTubePort",
    "CrawlerPort",
    "TTSPort",
    # Cache Port
    "CachePort",
    # Infrastructure Ports
    "EndpointMetricsDTO",
    "ApiStatsDTO",
    "ScheduledJobDTO",
    "JobHistoryDTO",
    "ApiMetricsPort",
    "SchedulerPort",
]
