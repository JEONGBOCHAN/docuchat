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
from src.application.ports.arxiv_search import ArxivSearchPort, ArxivPaperResult
from src.application.ports.semantic_scholar import (
    SemanticScholarSearchPort,
    SemanticScholarPaper,
    SemanticScholarAuthor,
)
from src.application.ports.crossref import (
    CrossrefSearchPort,
    CrossrefWork,
    CrossrefJournal,
    CrossrefFunder,
)
from src.application.ports.google_scholar import (
    GoogleScholarSearchPort,
    GoogleScholarResult,
)
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
from src.application.ports.document_summary import (
    DocumentSummaryGenerationPort,
    DocumentSummaryCachePort,
    DocumentSummaryDTO,
)
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
    ChatSessionMemoryDTO,
    NoteDTO,
    FavoriteDTO,
    SearchHistoryDTO,
    TrashItemDTO,
    AudioOverviewDTO,
    DocumentPreviewCacheDTO,
    # Ports
    ChannelRepositoryPort,
    ChatHistoryRepositoryPort,
    ChatSessionRepositoryPort,
    ChatSessionMemoryRepositoryPort,
    NoteRepositoryPort,
    FavoriteRepositoryPort,
    SearchHistoryRepositoryPort,
    TrashRepositoryPort,
    AudioRepositoryPort,
    DocumentPreviewCacheRepositoryPort,
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

# Token Counter Port
from src.application.ports.token_counter import TokenCounterPort

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

# Export DTOs
from src.application.ports.export import (
    ExportFormat,
    GroundingSourceDTO,
    NoteExportDTO,
    ChatMessageExportDTO,
    ChatExportDTO,
    ChannelExportMetadataDTO,
    ChannelFullExportDTO,
)

# Preview DTOs
from src.application.ports.preview import (
    TextHighlightDTO,
    DocumentPreviewDTO,
    SourceLocationDTO,
    SourceLocationResultDTO,
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
    # arXiv Search
    "ArxivSearchPort",
    "ArxivPaperResult",
    # Semantic Scholar Search
    "SemanticScholarSearchPort",
    "SemanticScholarPaper",
    "SemanticScholarAuthor",
    # Crossref Search
    "CrossrefSearchPort",
    "CrossrefWork",
    "CrossrefJournal",
    "CrossrefFunder",
    # Google Scholar Search
    "GoogleScholarSearchPort",
    "GoogleScholarResult",
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
    # Document Summary
    "DocumentSummaryGenerationPort",
    "DocumentSummaryCachePort",
    "DocumentSummaryDTO",
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
    "ChatSessionMemoryDTO",
    "NoteDTO",
    "FavoriteDTO",
    "SearchHistoryDTO",
    "TrashItemDTO",
    "AudioOverviewDTO",
    "ChannelRepositoryPort",
    "ChatHistoryRepositoryPort",
    "ChatSessionRepositoryPort",
    "ChatSessionMemoryRepositoryPort",
    "NoteRepositoryPort",
    "FavoriteRepositoryPort",
    "SearchHistoryRepositoryPort",
    "TrashRepositoryPort",
    "AudioRepositoryPort",
    "DocumentPreviewCacheDTO",
    "DocumentPreviewCacheRepositoryPort",
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
    # Token Counter Port
    "TokenCounterPort",
    # Infrastructure Ports
    "EndpointMetricsDTO",
    "ApiStatsDTO",
    "ScheduledJobDTO",
    "JobHistoryDTO",
    "ApiMetricsPort",
    "SchedulerPort",
    # Export DTOs
    "ExportFormat",
    "GroundingSourceDTO",
    "NoteExportDTO",
    "ChatMessageExportDTO",
    "ChatExportDTO",
    "ChannelExportMetadataDTO",
    "ChannelFullExportDTO",
    # Preview DTOs
    "TextHighlightDTO",
    "DocumentPreviewDTO",
    "SourceLocationDTO",
    "SourceLocationResultDTO",
]
