# -*- coding: utf-8 -*-
"""Tests for Crawler service."""

import pytest
from unittest.mock import patch, MagicMock

from src.services.crawler import CrawlerService, CrawlResult, get_crawler_service


class TestCrawlerService:
    """Tests for CrawlerService."""

    def test_fetch_url_invalid_url(self):
        """Test fetching invalid URL raises ValueError."""
        crawler = CrawlerService()

        with pytest.raises(ValueError, match="Invalid URL"):
            crawler.fetch_url("not-a-url")

    def test_fetch_url_invalid_scheme(self):
        """Test fetching URL with invalid scheme raises ValueError."""
        crawler = CrawlerService()

        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            crawler.fetch_url("ftp://example.com")

    @patch("src.services.crawler.requests.get")
    def test_fetch_url_success(self, mock_get):
        """Test successful URL fetch."""
        # Mock response
        mock_response = MagicMock()
        mock_response.content = b"""
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Welcome</h1>
                <p>This is test content.</p>
            </body>
        </html>
        """
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        crawler = CrawlerService()
        result = crawler.fetch_url("https://example.com")

        assert result.url == "https://example.com"
        assert result.title == "Test Page"
        assert "Welcome" in result.content
        assert "test content" in result.content

    @patch("src.services.crawler.requests.get")
    def test_fetch_url_extracts_main_content(self, mock_get):
        """Test that crawler extracts main content and ignores nav/footer."""
        mock_response = MagicMock()
        mock_response.content = b"""
        <html>
            <head><title>Article Page</title></head>
            <body>
                <nav>Navigation menu</nav>
                <main>
                    <h1>Article Title</h1>
                    <p>Article content here.</p>
                </main>
                <footer>Footer content</footer>
            </body>
        </html>
        """
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        crawler = CrawlerService()
        result = crawler.fetch_url("https://example.com/article")

        assert "Article Title" in result.content
        assert "Article content" in result.content
        # nav and footer should be removed
        assert "Navigation menu" not in result.content
        assert "Footer content" not in result.content

    @patch("src.services.crawler.requests.get")
    def test_fetch_url_handles_korean(self, mock_get):
        """Test that crawler handles Korean content."""
        mock_response = MagicMock()
        mock_response.content = """
        <html>
            <head><title>한국어 페이지</title></head>
            <body>
                <h1>안녕하세요</h1>
                <p>이것은 테스트입니다.</p>
            </body>
        </html>
        """.encode("utf-8")
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        crawler = CrawlerService()
        result = crawler.fetch_url("https://example.com/korean")

        assert result.title == "한국어 페이지"
        assert "안녕하세요" in result.content
        assert "테스트" in result.content

    @patch("src.services.crawler.requests.get")
    def test_fetch_url_request_error(self, mock_get):
        """Test that request errors are raised."""
        import requests

        mock_get.side_effect = requests.RequestException("Connection failed")

        crawler = CrawlerService()

        with pytest.raises(requests.RequestException):
            crawler.fetch_url("https://example.com")

    @patch("src.services.crawler.requests.get")
    def test_save_to_temp_file(self, mock_get):
        """Test saving crawl result to temp file."""
        import os

        mock_response = MagicMock()
        mock_response.content = b"<html><head><title>Test</title></head><body><p>Content</p></body></html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        crawler = CrawlerService()
        result = crawler.fetch_url("https://example.com")
        tmp_path = crawler.save_to_temp_file(result)

        try:
            assert os.path.exists(tmp_path)
            assert tmp_path.endswith(".md")

            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()

            assert "# Test" in content
            assert "Source: https://example.com" in content
        finally:
            os.unlink(tmp_path)

    def test_get_crawler_service(self):
        """Test get_crawler_service returns CrawlerService instance."""
        service = get_crawler_service()
        assert isinstance(service, CrawlerService)
