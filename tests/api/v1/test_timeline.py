# -*- coding: utf-8 -*-
"""Tests for Timeline and Briefing API."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.gemini import get_gemini_service
from src.application.use_cases.timeline_briefing import TimelineResult, BriefingResult
from src.application.ports.timeline import TimelineEventDTO, BriefingSectionDTO


class TestGenerateTimeline:
    """Tests for POST /api/v1/channels/{channel_id}/generate-timeline."""

    def test_generate_timeline_success(self, client_with_db: TestClient, test_db):
        """Test successful timeline generation."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = TimelineResult(
            events=[
                TimelineEventDTO(
                    date="2024-01-15",
                    title="Project Launch",
                    description="The project was officially launched",
                    source="launch.pdf",
                ),
                TimelineEventDTO(
                    date="2024-02-01",
                    title="First Milestone",
                    description="Completed phase 1",
                    source=None,
                ),
            ],
            channel_id="fileSearchStores/test-store",
        )

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        with patch("src.api.v1.timeline.create_generate_timeline_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-timeline",
                json={"max_events": 10},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["channel_id"] == "fileSearchStores/test-store"
        assert data["total"] == 2
        assert len(data["events"]) == 2
        assert data["events"][0]["date"] == "2024-01-15"
        assert data["events"][0]["title"] == "Project Launch"
        assert data["events"][1]["source"] is None
        assert "generated_at" in data

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_timeline_empty(self, client_with_db: TestClient, test_db):
        """Test timeline generation with no events found."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = TimelineResult(
            events=[],
            channel_id="fileSearchStores/test-store",
        )

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        with patch("src.api.v1.timeline.create_generate_timeline_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-timeline",
                json={},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["events"] == []

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_timeline_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test timeline generation for non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/generate-timeline",
            json={},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_timeline_api_error(self, client_with_db: TestClient, test_db):
        """Test timeline generation handles API errors."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = TimelineResult(
            events=[],
            channel_id="fileSearchStores/test-store",
            error="API Error",
        )

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        with patch("src.api.v1.timeline.create_generate_timeline_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-timeline",
                json={},
            )

        assert response.status_code == 500
        assert "Failed to generate timeline" in response.json()["detail"]

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_timeline_custom_max_events(self, client_with_db: TestClient, test_db):
        """Test timeline generation with custom max_events."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = TimelineResult(
            events=[],
            channel_id="fileSearchStores/test-store",
        )

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        with patch("src.api.v1.timeline.create_generate_timeline_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-timeline",
                json={"max_events": 50},
            )

        assert response.status_code == 200
        mock_use_case.execute.assert_called_once_with(
            channel_id="fileSearchStores/test-store",
            max_events=50,
        )

        app.dependency_overrides.pop(get_gemini_service, None)


class TestGenerateBriefing:
    """Tests for POST /api/v1/channels/{channel_id}/generate-briefing."""

    def test_generate_briefing_success(self, client_with_db: TestClient, test_db):
        """Test successful briefing generation."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = BriefingResult(
            title="Project Status Briefing",
            executive_summary="This briefing summarizes the current project status.",
            sections=[
                BriefingSectionDTO(title="Current Status", content="The project is on track."),
                BriefingSectionDTO(title="Next Steps", content="Continue with phase 2."),
            ],
            key_points=[
                "Project on schedule",
                "Budget at 75%",
                "No major risks",
            ],
            channel_id="fileSearchStores/test-store",
        )

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        with patch("src.api.v1.timeline.create_generate_briefing_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-briefing",
                json={"style": "executive", "max_sections": 5},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["channel_id"] == "fileSearchStores/test-store"
        assert data["title"] == "Project Status Briefing"
        assert "current project status" in data["executive_summary"]
        assert len(data["sections"]) == 2
        assert data["sections"][0]["title"] == "Current Status"
        assert len(data["key_points"]) == 3
        assert "generated_at" in data

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_briefing_detailed_style(self, client_with_db: TestClient, test_db):
        """Test briefing generation with detailed style."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = BriefingResult(
            title="Detailed Analysis",
            executive_summary="Comprehensive review...",
            sections=[],
            key_points=[],
            channel_id="fileSearchStores/test-store",
        )

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        with patch("src.api.v1.timeline.create_generate_briefing_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-briefing",
                json={"style": "detailed"},
            )

        assert response.status_code == 200
        mock_use_case.execute.assert_called_once_with(
            channel_id="fileSearchStores/test-store",
            style="detailed",
            max_sections=5,
        )

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_briefing_invalid_style(self, client_with_db: TestClient, test_db):
        """Test briefing generation with invalid style."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/generate-briefing",
            json={"style": "invalid_style"},
        )

        assert response.status_code == 400
        assert "executive" in response.json()["detail"]

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_briefing_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test briefing generation for non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/generate-briefing",
            json={},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_briefing_api_error(self, client_with_db: TestClient, test_db):
        """Test briefing generation handles API errors."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = BriefingResult(
            title="",
            executive_summary="",
            sections=[],
            key_points=[],
            channel_id="fileSearchStores/test-store",
            error="API Error",
        )

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        with patch("src.api.v1.timeline.create_generate_briefing_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-briefing",
                json={},
            )

        assert response.status_code == 500
        assert "Failed to generate briefing" in response.json()["detail"]

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_briefing_default_values(self, client_with_db: TestClient, test_db):
        """Test briefing generation with default values."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = BriefingResult(
            title="Default Briefing",
            executive_summary="Summary",
            sections=[],
            key_points=[],
            channel_id="fileSearchStores/test-store",
        )

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        with patch("src.api.v1.timeline.create_generate_briefing_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-briefing",
                json={},
            )

        assert response.status_code == 200
        mock_use_case.execute.assert_called_once_with(
            channel_id="fileSearchStores/test-store",
            style="executive",
            max_sections=5,
        )

        app.dependency_overrides.pop(get_gemini_service, None)
