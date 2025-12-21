# -*- coding: utf-8 -*-
"""Tests for study guide and quiz API endpoints."""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, UTC

from fastapi.testclient import TestClient

from src.main import app
from src.models.study import (
    DifficultyLevel,
    QuizType,
    StudyGuideGenerateRequest,
    QuizGenerateRequest,
)
from src.services.gemini import get_gemini_service


class TestGenerateStudyGuide:
    """Tests for study guide generation endpoint."""

    def test_generate_study_guide_success(self, client_with_db: TestClient, test_db):
        """Test successful study guide generation."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Store",
        }
        mock_gemini.list_store_files.return_value = [
            {"name": "files/file1.pdf", "display_name": "File 1", "size_bytes": 1024},
        ]
        mock_gemini.generate_study_guide.return_value = {
            "title": "Test Study Guide",
            "overview": "This guide covers...",
            "sections": [
                {
                    "title": "Introduction",
                    "content": "Introduction content...",
                    "key_points": ["Point 1", "Point 2"],
                }
            ],
            "key_concepts": [
                {
                    "term": "Concept 1",
                    "definition": "Definition of concept 1",
                    "importance": "Important because...",
                }
            ],
            "study_tips": ["Tip 1", "Tip 2"],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

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

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_study_guide_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test study guide generation with non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/non-existent/generate-study-guide"
        )

        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_study_guide_no_documents(self, client_with_db: TestClient, test_db):
        """Test study guide generation with empty channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Store",
        }
        mock_gemini.list_store_files.return_value = []

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/generate-study-guide"
        )

        assert response.status_code == 400
        assert "no documents" in response.json()["detail"].lower()

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_study_guide_with_options(self, client_with_db: TestClient, test_db):
        """Test study guide generation with custom options."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Store",
        }
        mock_gemini.list_store_files.return_value = [
            {"name": "files/file1.pdf", "display_name": "File 1", "size_bytes": 1024},
        ]
        mock_gemini.generate_study_guide.return_value = {
            "title": "Advanced Study Guide",
            "overview": "Advanced material...",
            "sections": [],
            "key_concepts": [],
            "study_tips": [],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

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
        mock_gemini.generate_study_guide.assert_called_once_with(
            store_name="fileSearchStores/test-store",
            include_concepts=False,
            include_summary=True,
            max_sections=10,
            difficulty="hard",
        )

        app.dependency_overrides.pop(get_gemini_service, None)


class TestGenerateQuiz:
    """Tests for quiz generation endpoint."""

    def test_generate_quiz_success(self, client_with_db: TestClient, test_db):
        """Test successful quiz generation."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Store",
        }
        mock_gemini.list_store_files.return_value = [
            {"name": "files/file1.pdf", "display_name": "File 1", "size_bytes": 1024},
        ]
        mock_gemini.generate_quiz.return_value = {
            "title": "Test Quiz",
            "description": "Test your knowledge",
            "questions": [
                {
                    "question": "What is X?",
                    "question_type": "multiple_choice",
                    "choices": [
                        {"label": "A", "text": "Answer A", "is_correct": True},
                        {"label": "B", "text": "Answer B", "is_correct": False},
                        {"label": "C", "text": "Answer C", "is_correct": False},
                        {"label": "D", "text": "Answer D", "is_correct": False},
                    ],
                    "correct_answer": "A. Answer A",
                    "explanation": "Because X is...",
                    "difficulty": "medium",
                },
                {
                    "question": "Y is true.",
                    "question_type": "true_false",
                    "choices": None,
                    "correct_answer": "True",
                    "explanation": "Y is indeed true because...",
                    "difficulty": "easy",
                },
            ],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/generate-quiz"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["channel_id"] == "fileSearchStores/test-store"
        assert data["title"] == "Test Quiz"
        assert data["total_questions"] == 2
        assert len(data["questions"]) == 2

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_quiz_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test quiz generation with non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/non-existent/generate-quiz"
        )

        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_quiz_no_documents(self, client_with_db: TestClient, test_db):
        """Test quiz generation with empty channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Store",
        }
        mock_gemini.list_store_files.return_value = []

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/generate-quiz"
        )

        assert response.status_code == 400
        assert "no documents" in response.json()["detail"].lower()

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_quiz_with_options(self, client_with_db: TestClient, test_db):
        """Test quiz generation with custom options."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Store",
        }
        mock_gemini.list_store_files.return_value = [
            {"name": "files/file1.pdf", "display_name": "File 1", "size_bytes": 1024},
        ]
        mock_gemini.generate_quiz.return_value = {
            "title": "Multiple Choice Quiz",
            "description": "Easy quiz",
            "questions": [],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

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
        mock_gemini.generate_quiz.assert_called_once_with(
            store_name="fileSearchStores/test-store",
            count=10,
            quiz_type="multiple_choice",
            difficulty="easy",
            include_explanations=False,
        )

        app.dependency_overrides.pop(get_gemini_service, None)


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
