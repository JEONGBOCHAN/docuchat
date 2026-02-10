# -*- coding: utf-8 -*-
"""Tests for study guide and quiz API endpoints."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.models.study import (
    DifficultyLevel,
    QuizType,
    StudyGuideGenerateRequest,
    QuizGenerateRequest,
)
from src.api.v1.deps import get_channel_port, get_document_port_factory
from src.application.ports.channel import ChannelDTO
from src.application.ports.document import DocumentDTO
from src.application.use_cases.learning import StudyGuideResult, QuizResult
from src.application.ports.learning import (
    StudySectionDTO,
    KeyConceptDTO,
    QuizQuestionDTO,
    QuizChoiceDTO,
)


class TestGenerateStudyGuide:
    """Tests for study guide generation endpoint."""

    def test_generate_study_guide_success(self, client_with_db: TestClient, test_db):
        """Test successful study guide generation."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Store",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/file1.pdf", display_name="File 1", size_bytes=1024, state="ACTIVE"),
        ]

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = StudyGuideResult(
            title="Test Study Guide",
            overview="This guide covers...",
            sections=[
                StudySectionDTO(
                    title="Introduction",
                    content="Introduction content...",
                    key_points=["Point 1", "Point 2"],
                )
            ],
            key_concepts=[
                KeyConceptDTO(
                    term="Concept 1",
                    definition="Definition of concept 1",
                    importance="Important because...",
                )
            ],
            study_tips=["Tip 1", "Tip 2"],
            channel_id="fileSearchStores/test-store",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        with patch("src.api.v1.study.create_generate_study_guide_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-study-guide"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["channel_id"] == "fileSearchStores/test-store"
        assert data["title"] == "Test Study Guide"
        assert len(data["sections"]) == 1
        assert len(data["key_concepts"]) == 1
        assert len(data["study_tips"]) == 2

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)

    def test_generate_study_guide_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test study guide generation with non-existent channel."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/non-existent/generate-study-guide"
        )

        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_port, None)

    def test_generate_study_guide_no_documents(self, client_with_db: TestClient, test_db):
        """Test study guide generation with empty channel."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Store",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = []

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/generate-study-guide"
        )

        assert response.status_code == 400
        assert "no documents" in response.json()["detail"].lower()

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)

    def test_generate_study_guide_with_options(self, client_with_db: TestClient, test_db):
        """Test study guide generation with custom options."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Store",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/file1.pdf", display_name="File 1", size_bytes=1024, state="ACTIVE"),
        ]

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = StudyGuideResult(
            title="Advanced Study Guide",
            overview="Advanced material...",
            sections=[],
            key_concepts=[],
            study_tips=[],
            channel_id="fileSearchStores/test-store",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        with patch("src.api.v1.study.create_generate_study_guide_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-study-guide",
                json={
                    "include_concepts": False,
                    "include_summary": True,
                    "max_sections": 10,
                    "difficulty": "hard",
                },
            )

        assert response.status_code == 200
        mock_use_case.execute.assert_called_once_with(
            channel_id="fileSearchStores/test-store",
            include_concepts=False,
            include_summary=True,
            max_sections=10,
            difficulty="hard",
        )

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)

    def test_generate_study_guide_api_error(self, client_with_db: TestClient, test_db):
        """Test study guide generation handles API errors."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Store",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/file1.pdf", display_name="File 1", size_bytes=1024, state="ACTIVE"),
        ]

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = StudyGuideResult(
            title="",
            overview="",
            sections=[],
            key_concepts=[],
            study_tips=[],
            channel_id="fileSearchStores/test-store",
            error="API Error",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        with patch("src.api.v1.study.create_generate_study_guide_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-study-guide"
            )

        assert response.status_code == 500
        assert "Failed to generate study guide" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)


class TestValidationPrecedence:
    """Regression: channel validation must precede document-port factory invocation."""

    def test_study_guide_channel_not_found_skips_factory(
        self, client_with_db: TestClient, test_db
    ):
        """When channel is not found, study guide must NOT invoke document-port factory."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        mock_factory = MagicMock()

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: mock_factory

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/generate-study-guide"
        )

        assert response.status_code == 404
        mock_factory.assert_not_called()

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)

    def test_quiz_channel_not_found_skips_factory(
        self, client_with_db: TestClient, test_db
    ):
        """When channel is not found, quiz must NOT invoke document-port factory."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        mock_factory = MagicMock()

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: mock_factory

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/generate-quiz"
        )

        assert response.status_code == 404
        mock_factory.assert_not_called()

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)


class TestGenerateQuiz:
    """Tests for quiz generation endpoint."""

    def test_generate_quiz_success(self, client_with_db: TestClient, test_db):
        """Test successful quiz generation."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Store",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/file1.pdf", display_name="File 1", size_bytes=1024, state="ACTIVE"),
        ]

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = QuizResult(
            title="Test Quiz",
            description="Test your knowledge",
            questions=[
                QuizQuestionDTO(
                    question="What is X?",
                    question_type="multiple_choice",
                    correct_answer="A. Answer A",
                    choices=[
                        QuizChoiceDTO(label="A", text="Answer A", is_correct=True),
                        QuizChoiceDTO(label="B", text="Answer B", is_correct=False),
                        QuizChoiceDTO(label="C", text="Answer C", is_correct=False),
                        QuizChoiceDTO(label="D", text="Answer D", is_correct=False),
                    ],
                    explanation="Because X is...",
                    difficulty="medium",
                ),
                QuizQuestionDTO(
                    question="Y is true.",
                    question_type="true_false",
                    correct_answer="True",
                    choices=None,
                    explanation="Y is indeed true because...",
                    difficulty="easy",
                ),
            ],
            channel_id="fileSearchStores/test-store",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        with patch("src.api.v1.study.create_generate_quiz_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-quiz"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["channel_id"] == "fileSearchStores/test-store"
        assert data["title"] == "Test Quiz"
        assert data["total_questions"] == 2
        assert len(data["questions"]) == 2

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)

    def test_generate_quiz_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test quiz generation with non-existent channel."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/non-existent/generate-quiz"
        )

        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_port, None)

    def test_generate_quiz_no_documents(self, client_with_db: TestClient, test_db):
        """Test quiz generation with empty channel."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Store",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = []

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/generate-quiz"
        )

        assert response.status_code == 400
        assert "no documents" in response.json()["detail"].lower()

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)

    def test_generate_quiz_with_options(self, client_with_db: TestClient, test_db):
        """Test quiz generation with custom options."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Store",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/file1.pdf", display_name="File 1", size_bytes=1024, state="ACTIVE"),
        ]

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = QuizResult(
            title="Multiple Choice Quiz",
            description="Easy quiz",
            questions=[],
            channel_id="fileSearchStores/test-store",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        with patch("src.api.v1.study.create_generate_quiz_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-quiz",
                json={
                    "count": 10,
                    "quiz_type": "multiple_choice",
                    "difficulty": "easy",
                    "include_explanations": False,
                },
            )

        assert response.status_code == 200
        mock_use_case.execute.assert_called_once_with(
            channel_id="fileSearchStores/test-store",
            count=10,
            quiz_type="multiple_choice",
            difficulty="easy",
            include_explanations=False,
        )

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)

    def test_generate_quiz_api_error(self, client_with_db: TestClient, test_db):
        """Test quiz generation handles API errors."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Store",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/file1.pdf", display_name="File 1", size_bytes=1024, state="ACTIVE"),
        ]

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = QuizResult(
            title="",
            description="",
            questions=[],
            channel_id="fileSearchStores/test-store",
            error="API Error",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        with patch("src.api.v1.study.create_generate_quiz_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-quiz"
            )

        assert response.status_code == 500
        assert "Failed to generate quiz" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)


class TestStudyModels:
    """Tests for study-related Pydantic models."""

    def test_study_guide_request_defaults(self):
        """Test StudyGuideGenerateRequest default values."""
        request = StudyGuideGenerateRequest()
        assert request.include_concepts is True
        assert request.include_summary is True
        assert request.max_sections == 5
        assert request.difficulty == DifficultyLevel.MEDIUM

    def test_study_guide_request_validation(self):
        """Test StudyGuideGenerateRequest validation."""
        # Valid request
        request = StudyGuideGenerateRequest(
            include_concepts=False,
            max_sections=10,
            difficulty=DifficultyLevel.HARD,
        )
        assert request.max_sections == 10

        # Invalid max_sections (too high)
        with pytest.raises(ValueError):
            StudyGuideGenerateRequest(max_sections=15)

        # Invalid max_sections (too low)
        with pytest.raises(ValueError):
            StudyGuideGenerateRequest(max_sections=0)

    def test_quiz_request_defaults(self):
        """Test QuizGenerateRequest default values."""
        request = QuizGenerateRequest()
        assert request.count == 5
        assert request.quiz_type == QuizType.MIXED
        assert request.difficulty == DifficultyLevel.MEDIUM
        assert request.include_explanations is True

    def test_quiz_request_validation(self):
        """Test QuizGenerateRequest validation."""
        # Valid request
        request = QuizGenerateRequest(
            count=20,
            quiz_type=QuizType.MULTIPLE_CHOICE,
            difficulty=DifficultyLevel.EASY,
        )
        assert request.count == 20

        # Invalid count (too high)
        with pytest.raises(ValueError):
            QuizGenerateRequest(count=25)

        # Invalid count (too low)
        with pytest.raises(ValueError):
            QuizGenerateRequest(count=0)
