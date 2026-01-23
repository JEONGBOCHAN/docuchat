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
    FAQGenerationPort,
    SummarizationPort,
    TimelinePort,
    BriefingPort,
    StudyGuidePort,
    QuizPort,
    PodcastScriptPort,
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
from src.infrastructure.external.tavily.web_search import TavilyWebSearchAdapter
from src.infrastructure.observability.event_store import InMemoryEventStore
from src.infrastructure.observability.state_store_adapter import StateStoreAdapter

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
) -> AgentRunnerPort:
    """Create an agent runner.

    Args:
        event_sink: Optional event sink for observability.

    Returns:
        AgentRunnerPort implementation (LangGraphAgentRunner).
    """
    return LangGraphAgentRunner(event_sink=event_sink)


def create_document_search() -> DocumentSearchPort:
    """Create a document search adapter.

    Returns:
        DocumentSearchPort implementation (GeminiDocumentSearchAdapter).
    """
    return GeminiDocumentSearchAdapter()


def create_web_search() -> WebSearchPort:
    """Create a web search adapter.

    Returns:
        WebSearchPort implementation (TavilyWebSearchAdapter).
    """
    return TavilyWebSearchAdapter()


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

    # Create agent runner with event sink
    agent_runner = create_agent_runner(event_sink=event_sink)

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
