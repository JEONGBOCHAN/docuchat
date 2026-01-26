# -*- coding: utf-8 -*-
"""
Dependency Injection Container.

Provides factory functions for creating properly wired instances
of use cases and their dependencies.

This is where the Clean Architecture comes together:
- Application layer (use cases) is wired to infrastructure implementations
- All dependencies flow inward (DIP)
- Easy to swap implementations for testing or different environments
"""

from functools import lru_cache
from typing import Callable

from src.application.ports import (
    AgentRunnerPort,
    AgentEventSinkPort,
    DocumentSearchPort,
    WebSearchPort,
    ArxivSearchPort,
    FAQGenerationPort,
    SummarizationPort,
    TimelinePort,
    BriefingPort,
    StudyGuidePort,
    QuizPort,
    PodcastScriptPort,
    ChannelPort,
    DocumentPort,
    # Persistence Ports
    ChannelRepositoryPort,
    ChatHistoryRepositoryPort,
    ChatSessionRepositoryPort,
    NoteRepositoryPort,
    FavoriteRepositoryPort,
    SearchHistoryRepositoryPort,
    TrashRepositoryPort,
    AudioRepositoryPort,
    DocumentPreviewCacheRepositoryPort,
    # External Service Ports
    YouTubePort,
    CrawlerPort,
    TTSPort,
    # Cache Port
    CachePort,
    # Infrastructure Ports
    ApiMetricsPort,
    SchedulerPort,
)
from src.application.ports.citation_search import CitationSearchPort
from src.application.use_cases.process_query import ProcessQueryUseCase
from src.application.use_cases.search_with_citations import SearchWithCitationsUseCase
from src.application.use_cases.generate_faq import GenerateFAQUseCase
from src.application.use_cases.summarize import (
    SummarizeChannelUseCase,
    SummarizeDocumentUseCase,
)
from src.application.use_cases.timeline_briefing import (
    GenerateTimelineUseCase,
    GenerateBriefingUseCase,
)
from src.application.use_cases.learning import (
    GenerateStudyGuideUseCase,
    GenerateQuizUseCase,
)
from src.application.use_cases.podcast import GeneratePodcastScriptUseCase

# Infrastructure implementations
from src.infrastructure.agent.langgraph_runner import LangGraphAgentRunner
from src.infrastructure.external.gemini.document_search import GeminiDocumentSearchAdapter
from src.infrastructure.external.gemini.citation import GeminiCitationAdapter
from src.infrastructure.external.gemini.faq import GeminiFAQAdapter
from src.infrastructure.external.gemini.summarization import GeminiSummarizationAdapter
from src.infrastructure.external.gemini.timeline import GeminiTimelineAdapter
from src.infrastructure.external.gemini.briefing import GeminiBriefingAdapter
from src.infrastructure.external.gemini.study_guide import GeminiStudyGuideAdapter
from src.infrastructure.external.gemini.quiz import GeminiQuizAdapter
from src.infrastructure.external.gemini.podcast import GeminiPodcastAdapter
from src.infrastructure.external.gemini.channel import GeminiChannelAdapter
from src.infrastructure.external.gemini.document import GeminiDocumentAdapter
from src.infrastructure.external.mcp.web_search import McpWebSearchAdapter
from src.infrastructure.external.arxiv.adapter import ArxivAdapter
from src.infrastructure.observability.event_store import InMemoryEventStore
from src.infrastructure.observability.state_store_adapter import StateStoreAdapter
from src.agents.middlewares.dashboard import DashboardMiddleware

from src.mcp_server.state import get_global_state_store


# ============================================================
# Singleton Instances (for shared state)
# ============================================================

_event_store: InMemoryEventStore | None = None
_state_store_adapter: StateStoreAdapter | None = None


def get_event_store() -> InMemoryEventStore:
    """Get the global event store (singleton).

    Returns:
        InMemoryEventStore instance.
    """
    global _event_store
    if _event_store is None:
        _event_store = InMemoryEventStore()
    return _event_store


def get_state_store_adapter() -> StateStoreAdapter:
    """Get the state store adapter for dashboard compatibility.

    This bridges the new event system to the legacy AgentStateStore
    used by the MCP dashboard.

    Returns:
        StateStoreAdapter instance.
    """
    global _state_store_adapter
    if _state_store_adapter is None:
        _state_store_adapter = StateStoreAdapter(get_global_state_store())
    return _state_store_adapter


def create_dashboard_middleware() -> DashboardMiddleware:
    """Create a dashboard middleware with state store.

    Returns:
        DashboardMiddleware instance connected to global state store.
    """
    return DashboardMiddleware(state_store=get_global_state_store())


# ============================================================
# Factory Functions
# ============================================================

def create_event_sink(use_legacy_dashboard: bool = True) -> AgentEventSinkPort:
    """Create an event sink.

    Args:
        use_legacy_dashboard: If True, uses StateStoreAdapter for
                             backward compatibility with dashboard.

    Returns:
        AgentEventSinkPort implementation.
    """
    if use_legacy_dashboard:
        return get_state_store_adapter()
    return get_event_store()


def create_agent_runner(
    event_sink: AgentEventSinkPort | None = None,
    dashboard_middleware: DashboardMiddleware | None = None,
) -> AgentRunnerPort:
    """Create an agent runner.

    Args:
        event_sink: Optional event sink for observability.
        dashboard_middleware: Optional DashboardMiddleware for LLM node display.

    Returns:
        AgentRunnerPort implementation (LangGraphAgentRunner).
    """
    return LangGraphAgentRunner(
        event_sink=event_sink,
        dashboard_middleware=dashboard_middleware,
    )


def create_document_search() -> DocumentSearchPort:
    """Create a document search adapter.

    Returns:
        DocumentSearchPort implementation (GeminiDocumentSearchAdapter).
    """
    return GeminiDocumentSearchAdapter()


def create_web_search() -> WebSearchPort:
    """Create a web search adapter.

    Returns:
        WebSearchPort implementation (McpWebSearchAdapter).
    """
    return McpWebSearchAdapter()


def create_arxiv_search() -> ArxivSearchPort:
    """Create an arXiv search adapter.

    Returns:
        ArxivSearchPort implementation (ArxivAdapter).
    """
    return ArxivAdapter()


def create_citation_search() -> CitationSearchPort:
    """Create a citation search adapter.

    Returns:
        CitationSearchPort implementation (GeminiCitationAdapter).
    """
    return GeminiCitationAdapter()


# ============================================================
# Use Case Factory
# ============================================================

def create_process_query_use_case(
    use_legacy_dashboard: bool = True,
    include_web_search: bool = False,
) -> ProcessQueryUseCase:
    """Create a ProcessQueryUseCase with all dependencies wired.

    This is the main factory function that creates a fully configured
    use case ready for execution.

    Args:
        use_legacy_dashboard: If True, enables dashboard updates via
                             legacy state store adapter.
        include_web_search: If True, includes web search capability.

    Returns:
        Fully configured ProcessQueryUseCase.

    Example:
        use_case = create_process_query_use_case()
        result = use_case.execute(
            query="What is AI?",
            channel_id="channel-123",
        )
    """
    # Create event sink
    event_sink = create_event_sink(use_legacy_dashboard=use_legacy_dashboard)

    # Create dashboard middleware for LLM node display (only when using legacy dashboard)
    dashboard_middleware = create_dashboard_middleware() if use_legacy_dashboard else None

    # Create agent runner with event sink and dashboard middleware
    agent_runner = create_agent_runner(
        event_sink=event_sink,
        dashboard_middleware=dashboard_middleware,
    )

    # Create search adapters
    document_search = create_document_search()
    web_search = create_web_search() if include_web_search else None

    # Wire everything together
    return ProcessQueryUseCase(
        agent_runner=agent_runner,
        event_sink=event_sink,
        document_search=document_search,
        web_search=web_search,
    )


# ============================================================
# Convenience Accessor
# ============================================================

@lru_cache(maxsize=1)
def get_default_use_case() -> ProcessQueryUseCase:
    """Get the default ProcessQueryUseCase (cached).

    This provides a ready-to-use use case for common scenarios.

    Returns:
        ProcessQueryUseCase with default configuration.
    """
    return create_process_query_use_case(
        use_legacy_dashboard=True,
        include_web_search=False,
    )


def reset_use_case_cache() -> None:
    """Reset the cached use case.

    Call this if you need to reconfigure dependencies.
    """
    get_default_use_case.cache_clear()


def create_search_with_citations_use_case() -> SearchWithCitationsUseCase:
    """Create a SearchWithCitationsUseCase with dependencies.

    Returns:
        Fully configured SearchWithCitationsUseCase.

    Example:
        use_case = create_search_with_citations_use_case()
        result = use_case.execute(
            store_name="channel-123",
            query="What is the main topic?",
        )
    """
    citation_port = create_citation_search()
    return SearchWithCitationsUseCase(citation_port=citation_port)


def create_faq_generation() -> FAQGenerationPort:
    """Create FAQ generation adapter.

    Returns:
        FAQGenerationPort implementation (GeminiFAQAdapter).
    """
    return GeminiFAQAdapter()


def create_generate_faq_use_case() -> GenerateFAQUseCase:
    """Create GenerateFAQUseCase with dependencies.

    Returns:
        Fully configured GenerateFAQUseCase.

    Example:
        use_case = create_generate_faq_use_case()
        result = use_case.execute(
            channel_id="channel-123",
            count=5,
        )
    """
    return GenerateFAQUseCase(faq_port=create_faq_generation())


# ============================================================
# Summarization Factory Functions
# ============================================================

def create_summarization() -> SummarizationPort:
    """Create summarization adapter.

    Returns:
        SummarizationPort implementation (GeminiSummarizationAdapter).
    """
    return GeminiSummarizationAdapter()


def create_summarize_channel_use_case() -> SummarizeChannelUseCase:
    """Create SummarizeChannelUseCase with dependencies.

    Returns:
        Fully configured SummarizeChannelUseCase.

    Example:
        use_case = create_summarize_channel_use_case()
        result = use_case.execute(
            channel_id="channel-123",
            summary_type="detailed",
        )
    """
    return SummarizeChannelUseCase(summarization_port=create_summarization())


def create_summarize_document_use_case() -> SummarizeDocumentUseCase:
    """Create SummarizeDocumentUseCase with dependencies.

    Returns:
        Fully configured SummarizeDocumentUseCase.

    Example:
        use_case = create_summarize_document_use_case()
        result = use_case.execute(
            channel_id="channel-123",
            document_name="report.pdf",
            summary_type="short",
        )
    """
    return SummarizeDocumentUseCase(summarization_port=create_summarization())


# ============================================================
# Timeline and Briefing Factory Functions
# ============================================================

def create_timeline() -> TimelinePort:
    """Create timeline adapter.

    Returns:
        TimelinePort implementation (GeminiTimelineAdapter).
    """
    return GeminiTimelineAdapter()


def create_briefing() -> BriefingPort:
    """Create briefing adapter.

    Returns:
        BriefingPort implementation (GeminiBriefingAdapter).
    """
    return GeminiBriefingAdapter()


def create_generate_timeline_use_case() -> GenerateTimelineUseCase:
    """Create GenerateTimelineUseCase with dependencies.

    Returns:
        Fully configured GenerateTimelineUseCase.

    Example:
        use_case = create_generate_timeline_use_case()
        result = use_case.execute(
            channel_id="channel-123",
            max_events=10,
        )
    """
    return GenerateTimelineUseCase(timeline_port=create_timeline())


def create_generate_briefing_use_case() -> GenerateBriefingUseCase:
    """Create GenerateBriefingUseCase with dependencies.

    Returns:
        Fully configured GenerateBriefingUseCase.

    Example:
        use_case = create_generate_briefing_use_case()
        result = use_case.execute(
            channel_id="channel-123",
            style="executive",
        )
    """
    return GenerateBriefingUseCase(briefing_port=create_briefing())


# ============================================================
# Learning Features Factory Functions
# ============================================================

def create_study_guide() -> StudyGuidePort:
    """Create study guide adapter.

    Returns:
        StudyGuidePort implementation (GeminiStudyGuideAdapter).
    """
    return GeminiStudyGuideAdapter()


def create_quiz() -> QuizPort:
    """Create quiz adapter.

    Returns:
        QuizPort implementation (GeminiQuizAdapter).
    """
    return GeminiQuizAdapter()


def create_generate_study_guide_use_case() -> GenerateStudyGuideUseCase:
    """Create GenerateStudyGuideUseCase with dependencies.

    Returns:
        Fully configured GenerateStudyGuideUseCase.

    Example:
        use_case = create_generate_study_guide_use_case()
        result = use_case.execute(
            channel_id="channel-123",
            difficulty="medium",
        )
    """
    return GenerateStudyGuideUseCase(study_guide_port=create_study_guide())


def create_generate_quiz_use_case() -> GenerateQuizUseCase:
    """Create GenerateQuizUseCase with dependencies.

    Returns:
        Fully configured GenerateQuizUseCase.

    Example:
        use_case = create_generate_quiz_use_case()
        result = use_case.execute(
            channel_id="channel-123",
            count=10,
            quiz_type="mixed",
        )
    """
    return GenerateQuizUseCase(quiz_port=create_quiz())


# ============================================================
# Podcast Factory Functions
# ============================================================

def create_podcast_script() -> PodcastScriptPort:
    """Create podcast script adapter.

    Returns:
        PodcastScriptPort implementation (GeminiPodcastAdapter).
    """
    return GeminiPodcastAdapter()


def create_generate_podcast_script_use_case() -> GeneratePodcastScriptUseCase:
    """Create GeneratePodcastScriptUseCase with dependencies.

    Returns:
        Fully configured GeneratePodcastScriptUseCase.

    Example:
        use_case = create_generate_podcast_script_use_case()
        result = use_case.execute(
            store_name="channel-123",
            duration_minutes=5,
            style="conversational",
        )
    """
    return GeneratePodcastScriptUseCase(podcast_port=create_podcast_script())


# ============================================================
# Channel Factory Functions
# ============================================================

def create_channel_port() -> ChannelPort:
    """Create channel adapter.

    Returns:
        ChannelPort implementation (GeminiChannelAdapter).
    """
    return GeminiChannelAdapter()


# ============================================================
# Document Factory Functions
# ============================================================

def create_document_port() -> DocumentPort:
    """Create document adapter.

    Returns:
        DocumentPort implementation (GeminiDocumentAdapter).
    """
    return GeminiDocumentAdapter()


# ============================================================
# Repository Port Factory Functions
# ============================================================

def create_channel_repository_port(db=None) -> ChannelRepositoryPort:
    """Create channel repository port.

    Args:
        db: Optional database session. If None, creates one from get_db().

    Returns:
        ChannelRepositoryPort implementation.
    """
    from src.infrastructure.persistence.adapters import ChannelRepositoryAdapter
    return ChannelRepositoryAdapter(db)


def create_chat_history_repository_port(db=None) -> ChatHistoryRepositoryPort:
    """Create chat history repository port.

    Args:
        db: Optional database session. If None, creates one from get_db().

    Returns:
        ChatHistoryRepositoryPort implementation.
    """
    from src.infrastructure.persistence.adapters import ChatHistoryRepositoryAdapter
    return ChatHistoryRepositoryAdapter(db)


def create_chat_session_repository_port(db=None) -> ChatSessionRepositoryPort:
    """Create chat session repository port.

    Args:
        db: Optional database session. If None, creates one from get_db().

    Returns:
        ChatSessionRepositoryPort implementation.
    """
    from src.infrastructure.persistence.adapters import ChatSessionRepositoryAdapter
    return ChatSessionRepositoryAdapter(db)


def create_note_repository_port(db=None) -> NoteRepositoryPort:
    """Create note repository port.

    Args:
        db: Optional database session. If None, creates one from get_db().

    Returns:
        NoteRepositoryPort implementation.
    """
    from src.infrastructure.persistence.adapters import NoteRepositoryAdapter
    return NoteRepositoryAdapter(db)


def create_favorite_repository_port(db=None) -> FavoriteRepositoryPort:
    """Create favorite repository port.

    Args:
        db: Optional database session. If None, creates one from get_db().

    Returns:
        FavoriteRepositoryPort implementation.
    """
    from src.infrastructure.persistence.adapters import FavoriteRepositoryAdapter
    return FavoriteRepositoryAdapter(db)


def create_search_history_repository_port(db=None) -> SearchHistoryRepositoryPort:
    """Create search history repository port.

    Args:
        db: Optional database session. If None, creates one from get_db().

    Returns:
        SearchHistoryRepositoryPort implementation.
    """
    from src.infrastructure.persistence.adapters import SearchHistoryRepositoryAdapter
    return SearchHistoryRepositoryAdapter(db)


def create_trash_repository_port(db=None) -> TrashRepositoryPort:
    """Create trash repository port.

    Args:
        db: Optional database session. If None, creates one from get_db().

    Returns:
        TrashRepositoryPort implementation.
    """
    from src.infrastructure.persistence.adapters import TrashRepositoryAdapter
    return TrashRepositoryAdapter(db)


def create_audio_repository_port(db=None) -> AudioRepositoryPort:
    """Create audio repository port.

    Args:
        db: Optional database session. If None, creates one from get_db().

    Returns:
        AudioRepositoryPort implementation.
    """
    from src.infrastructure.persistence.adapters import AudioRepositoryAdapter
    return AudioRepositoryAdapter(db)


def create_document_preview_cache_repository_port(db=None) -> DocumentPreviewCacheRepositoryPort:
    """Create document preview cache repository port.

    Args:
        db: Optional database session. If None, creates one from get_db().

    Returns:
        DocumentPreviewCacheRepositoryPort implementation.
    """
    from src.infrastructure.persistence.adapters import DocumentPreviewCacheRepositoryAdapter
    return DocumentPreviewCacheRepositoryAdapter(db)


# ============================================================
# External Service Port Factory Functions
# ============================================================

def create_youtube_port() -> YouTubePort:
    """Create YouTube service port.

    Returns:
        YouTubePort implementation.
    """
    from src.infrastructure.external.adapters import YouTubeAdapter
    return YouTubeAdapter()


def create_crawler_port() -> CrawlerPort:
    """Create crawler service port.

    Returns:
        CrawlerPort implementation.
    """
    from src.infrastructure.external.adapters import CrawlerAdapter
    return CrawlerAdapter()


def create_tts_port() -> TTSPort:
    """Create TTS service port.

    Returns:
        TTSPort implementation.
    """
    from src.infrastructure.external.adapters import TTSAdapter
    return TTSAdapter()


# ============================================================
# Cache Port Factory Functions
# ============================================================

def create_cache_port() -> CachePort:
    """Create cache port.

    Returns:
        CachePort implementation.
    """
    from src.infrastructure.cache.adapters import CacheAdapter
    return CacheAdapter()


# ============================================================
# Application Service Factory Functions
# ============================================================

def create_capacity_service(db=None):
    """Create capacity service.

    Args:
        db: Optional database session. If None, creates one from get_db().

    Returns:
        CapacityService instance with all dependencies wired.
    """
    if db is None:
        from src.core.database import get_db
        db = next(get_db())
    from src.application.services.capacity_service import CapacityService
    return CapacityService(
        channel_repo=create_channel_repository_port(db),
    )


def create_export_service(db=None):
    """Create export service.

    Args:
        db: Optional database session. If None, creates one from get_db().

    Returns:
        ExportService instance with all dependencies wired.
    """
    if db is None:
        from src.core.database import get_db
        db = next(get_db())
    from src.application.services.export_service import ExportService
    return ExportService(
        channel_repo=create_channel_repository_port(db),
        note_repo=create_note_repository_port(db),
        chat_repo=create_chat_history_repository_port(db),
    )


def create_admin_stats_service(db=None):
    """Create admin stats service.

    Args:
        db: Optional database session. If None, creates one from get_db().

    Returns:
        AdminStatsService instance with all dependencies wired.
    """
    if db is None:
        from src.core.database import get_db
        db = next(get_db())
    from src.application.services.admin_stats import AdminStatsService
    return AdminStatsService(
        channel_repo=create_channel_repository_port(db),
        api_metrics=create_api_metrics_port(),
        scheduler=create_scheduler_port(),
    )


def create_preview_service(db=None):
    """Create preview service.

    Args:
        db: Optional database session. If None, creates one from get_db().

    Returns:
        PreviewService instance with all dependencies wired.
    """
    if db is None:
        from src.core.database import get_db
        db = next(get_db())
    from src.application.services.preview_service import PreviewService
    from src.infrastructure.persistence.adapters import DocumentPreviewCacheRepositoryAdapter
    return PreviewService(
        preview_cache_repo=DocumentPreviewCacheRepositoryAdapter(db),
        document_search=create_document_search(),
    )


# ============================================================
# Infrastructure Port Factory Functions
# ============================================================

# Singleton instances for infrastructure ports
_api_metrics_port: ApiMetricsPort | None = None
_scheduler_port: SchedulerPort | None = None


def create_api_metrics_port() -> ApiMetricsPort:
    """Create or get API metrics port (singleton).

    Returns:
        ApiMetricsPort implementation.
    """
    global _api_metrics_port
    if _api_metrics_port is None:
        from src.infrastructure.monitoring.api_metrics import get_api_metrics
        from src.infrastructure.monitoring.adapters import ApiMetricsAdapter
        _api_metrics_port = ApiMetricsAdapter(get_api_metrics())
    return _api_metrics_port


def create_scheduler_port() -> SchedulerPort:
    """Create or get scheduler port (singleton).

    Returns:
        SchedulerPort implementation.
    """
    global _scheduler_port
    if _scheduler_port is None:
        from src.infrastructure.scheduler.scheduler import get_scheduler
        from src.infrastructure.scheduler.adapters import SchedulerAdapter
        _scheduler_port = SchedulerAdapter(get_scheduler())
    return _scheduler_port
