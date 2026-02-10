# -*- coding: utf-8 -*-
"""Knowledge module DI container."""

from src.application.ports import (
    FAQGenerationPort,
    SummarizationPort,
    TimelinePort,
    BriefingPort,
    StudyGuidePort,
    QuizPort,
    PodcastScriptPort,
    AudioRepositoryPort,
    TTSPort,
)
from src.application.ports.citation_search import CitationSearchPort
from src.modules.knowledge.application.use_cases.search_with_citations import SearchWithCitationsUseCase
from src.modules.knowledge.application.use_cases.generate_faq import GenerateFAQUseCase
from src.modules.knowledge.application.use_cases.summarize import (
    SummarizeChannelUseCase,
    SummarizeDocumentUseCase,
)
from src.modules.knowledge.application.use_cases.timeline_briefing import (
    GenerateTimelineUseCase,
    GenerateBriefingUseCase,
)
from src.modules.knowledge.application.use_cases.learning import (
    GenerateStudyGuideUseCase,
    GenerateQuizUseCase,
)
from src.modules.knowledge.application.use_cases.podcast import GeneratePodcastScriptUseCase


# ============================================================
# Port Factories
# ============================================================

def create_citation_search() -> CitationSearchPort:
    from src.infrastructure.external.gemini.citation import GeminiCitationAdapter
    return GeminiCitationAdapter()


def create_faq_generation() -> FAQGenerationPort:
    from src.infrastructure.external.gemini.faq import GeminiFAQAdapter
    return GeminiFAQAdapter()


def create_summarization() -> SummarizationPort:
    from src.infrastructure.external.gemini.summarization import GeminiSummarizationAdapter
    return GeminiSummarizationAdapter()


def create_timeline() -> TimelinePort:
    from src.infrastructure.external.gemini.timeline import GeminiTimelineAdapter
    return GeminiTimelineAdapter()


def create_briefing() -> BriefingPort:
    from src.infrastructure.external.gemini.briefing import GeminiBriefingAdapter
    return GeminiBriefingAdapter()


def create_study_guide() -> StudyGuidePort:
    from src.infrastructure.external.gemini.study_guide import GeminiStudyGuideAdapter
    return GeminiStudyGuideAdapter()


def create_quiz() -> QuizPort:
    from src.infrastructure.external.gemini.quiz import GeminiQuizAdapter
    return GeminiQuizAdapter()


def create_podcast_script() -> PodcastScriptPort:
    from src.infrastructure.external.gemini.podcast import GeminiPodcastAdapter
    return GeminiPodcastAdapter()


def create_tts_port() -> TTSPort:
    from src.infrastructure.external.adapters import TTSAdapter
    return TTSAdapter()


def create_audio_repository_port(db) -> AudioRepositoryPort:
    from src.infrastructure.persistence.adapters import AudioRepositoryAdapter
    return AudioRepositoryAdapter(db)


# ============================================================
# Use Case Factories
# ============================================================

def create_search_with_citations_use_case() -> SearchWithCitationsUseCase:
    return SearchWithCitationsUseCase(citation_port=create_citation_search())


def create_generate_faq_use_case() -> GenerateFAQUseCase:
    return GenerateFAQUseCase(faq_port=create_faq_generation())


def create_summarize_channel_use_case() -> SummarizeChannelUseCase:
    return SummarizeChannelUseCase(summarization_port=create_summarization())


def create_summarize_document_use_case() -> SummarizeDocumentUseCase:
    return SummarizeDocumentUseCase(summarization_port=create_summarization())


def create_generate_timeline_use_case() -> GenerateTimelineUseCase:
    return GenerateTimelineUseCase(timeline_port=create_timeline())


def create_generate_briefing_use_case() -> GenerateBriefingUseCase:
    return GenerateBriefingUseCase(briefing_port=create_briefing())


def create_generate_study_guide_use_case() -> GenerateStudyGuideUseCase:
    return GenerateStudyGuideUseCase(study_guide_port=create_study_guide())


def create_generate_quiz_use_case() -> GenerateQuizUseCase:
    return GenerateQuizUseCase(quiz_port=create_quiz())


def create_generate_podcast_script_use_case() -> GeneratePodcastScriptUseCase:
    return GeneratePodcastScriptUseCase(podcast_port=create_podcast_script())


def create_generate_audio_use_case(db):
    from src.modules.knowledge.application.use_cases.audio_generation import GenerateAudioUseCase
    return GenerateAudioUseCase(
        audio_repo=create_audio_repository_port(db),
        tts_port=create_tts_port(),
        script_use_case=create_generate_podcast_script_use_case(),
    )
