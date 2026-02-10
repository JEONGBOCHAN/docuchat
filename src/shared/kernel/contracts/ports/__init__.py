# -*- coding: utf-8 -*-
"""
Shared Kernel Contracts — Ports (Interfaces).

Ports define the boundaries between the application layer and external systems.
They are abstract interfaces that infrastructure adapters implement.

This follows the Ports & Adapters (Hexagonal) architecture pattern.
"""

from src.shared.kernel.contracts.ports.observability import AgentEventSinkPort
from src.shared.kernel.contracts.ports.document_search import DocumentSearchPort, SearchResult
from src.shared.kernel.contracts.ports.web_search import WebSearchPort, WebSearchResult
from src.shared.kernel.contracts.ports.arxiv_search import ArxivSearchPort, ArxivPaperResult
from src.shared.kernel.contracts.ports.semantic_scholar import (
    SemanticScholarSearchPort,
    SemanticScholarPaper,
    SemanticScholarAuthor,
)
from src.shared.kernel.contracts.ports.crossref import (
    CrossrefSearchPort,
    CrossrefWork,
    CrossrefJournal,
    CrossrefFunder,
)
from src.shared.kernel.contracts.ports.google_scholar import (
    GoogleScholarSearchPort,
    GoogleScholarResult,
)
from src.shared.kernel.contracts.ports.llm import LLMPort, LLMMessage, LLMResponse
from src.shared.kernel.contracts.ports.agent_runner import (
    AgentRunnerPort,
    AgentTool,
    AgentResult,
    AgentConfig,
)
from src.shared.kernel.contracts.ports.faq_generation import FAQGenerationPort, FAQItemDTO
from src.shared.kernel.contracts.ports.citation_search import (
    CitationSearchPort,
    CitationDTO,
    CitationResultDTO,
)
from src.shared.kernel.contracts.ports.summarization import SummarizationPort, SummaryDTO
from src.shared.kernel.contracts.ports.document_summary import (
    DocumentSummaryGenerationPort,
    DocumentSummaryCachePort,
    DocumentSummaryDTO,
)
from src.shared.kernel.contracts.ports.timeline import (
    TimelinePort,
    TimelineEventDTO,
    BriefingPort,
    BriefingDTO,
    BriefingSectionDTO,
)
from src.shared.kernel.contracts.ports.learning import (
    StudyGuidePort,
    StudyGuideDTO,
    StudySectionDTO,
    KeyConceptDTO,
    QuizPort,
    QuizDTO,
    QuizQuestionDTO,
    QuizChoiceDTO,
)
from src.shared.kernel.contracts.ports.podcast import (
    PodcastScriptPort,
    PodcastScriptDTO,
    DialogueLineDTO,
)
from src.shared.kernel.contracts.ports.conversation_summary import ConversationSummaryPort
from src.shared.kernel.contracts.ports.channel import ChannelPort, ChannelDTO
from src.shared.kernel.contracts.ports.document import DocumentPort, DocumentDTO, UploadResultDTO

# Persistence Ports
from src.shared.kernel.contracts.ports.persistence import (
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
from src.shared.kernel.contracts.ports.external_services import (
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

# Google Drive Port
from src.shared.kernel.contracts.ports.google_drive import (
    GoogleDrivePort,
    GoogleDriveTokenDTO,
    GoogleDriveFileDTO,
    DownloadedDriveFileDTO,
)

# Cache Port
from src.shared.kernel.contracts.ports.cache import CachePort

# Token Counter Port
from src.shared.kernel.contracts.ports.token_counter import TokenCounterPort

# Infrastructure Ports
from src.shared.kernel.contracts.ports.infrastructure import (
    # DTOs
    EndpointMetricsDTO,
    ApiStatsDTO,
    ScheduledJobDTO,
    JobHistoryDTO,
    # Ports
    ApiMetricsPort,
    SchedulerPort,
    AudioGenerationTaskPort,
)

# Export DTOs
from src.shared.kernel.contracts.ports.export import (
    ExportFormat,
    GroundingSourceDTO,
    NoteExportDTO,
    ChatMessageExportDTO,
    ChatExportDTO,
    ChannelExportMetadataDTO,
    ChannelFullExportDTO,
)

# Preview DTOs
from src.shared.kernel.contracts.ports.preview import (
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
    # Conversation Summary
    "ConversationSummaryPort",
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
    # Google Drive Port
    "GoogleDrivePort",
    "GoogleDriveTokenDTO",
    "GoogleDriveFileDTO",
    "DownloadedDriveFileDTO",
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
    "AudioGenerationTaskPort",
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
