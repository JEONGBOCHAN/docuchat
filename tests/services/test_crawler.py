# -*- coding: utf-8 -*-
"""Tests for Crawler service."""

import pytest
from unittest.mock import patch, MagicMock

from src.infrastructure.external.crawler.crawler import (
    CrawlerService,
    CrawlResult,
    get_crawler_service,
    _validate_not_private,
    MAX_RESPONSE_BYTES,
)


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

    @patch.object(CrawlerService, "_validated_request")
    def test_fetch_url_success(self, mock_vr):
        """Test successful URL fetch."""
        html = b"""
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Welcome</h1>
                <p>This is test content.</p>
            </body>
        </html>
        """
        mock_vr.return_value = (html, {"content-type": "text/html; charset=utf-8"})

        crawler = CrawlerService()
        result = crawler.fetch_url("https://example.com")

        assert result.url == "https://example.com"
        assert result.title == "Test Page"
        assert "Welcome" in result.content
        assert "test content" in result.content

    @patch.object(CrawlerService, "_validated_request")
    def test_fetch_url_extracts_main_content(self, mock_vr):
        """Test that crawler extracts main content and ignores nav/footer."""
        html = b"""
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
        mock_vr.return_value = (html, {"content-type": "text/html"})

        crawler = CrawlerService()
        result = crawler.fetch_url("https://example.com/article")

        assert "Article Title" in result.content
        assert "Article content" in result.content
        assert "Navigation menu" not in result.content
        assert "Footer content" not in result.content

    @patch.object(CrawlerService, "_validated_request")
    def test_fetch_url_handles_korean(self, mock_vr):
        """Test that crawler handles Korean content."""
        html = """
        <html>
            <head><title>한국어 페이지</title></head>
            <body>
                <h1>안녕하세요</h1>
                <p>이것은 테스트입니다.</p>
            </body>
        </html>
        """.encode("utf-8")
        mock_vr.return_value = (html, {"content-type": "text/html; charset=utf-8"})

        crawler = CrawlerService()
        result = crawler.fetch_url("https://example.com/korean")

        assert result.title == "한국어 페이지"
        assert "안녕하세요" in result.content
        assert "테스트" in result.content

    @patch.object(CrawlerService, "_validated_request")
    def test_fetch_url_request_error(self, mock_vr):
        """Test that request errors are raised."""
        import requests

        mock_vr.side_effect = requests.RequestException("Connection failed")

        crawler = CrawlerService()

        with pytest.raises(requests.RequestException):
            crawler.fetch_url("https://example.com")

    @patch.object(CrawlerService, "_validated_request")
    def test_save_to_temp_file(self, mock_vr):
        """Test saving crawl result to temp file."""
        import os

        html = b"<html><head><title>Test</title></head><body><p>Content</p></body></html>"
        mock_vr.return_value = (html, {"content-type": "text/html"})

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


class TestSSRFProtection:
    """Tests for SSRF protection in CrawlerService."""

    def test_block_localhost(self):
        """Test that localhost URLs are blocked."""
        crawler = CrawlerService()
        with pytest.raises(ValueError, match="private or reserved"):
            crawler.fetch_url("https://localhost/admin")

    def test_block_127_ip(self):
        """Test that 127.x.x.x IPs are blocked."""
        crawler = CrawlerService()
        with pytest.raises(ValueError, match="private or reserved"):
            crawler.fetch_url("https://127.0.0.1/metadata")

    @patch("src.infrastructure.external.crawler.crawler.socket.getaddrinfo")
    def test_block_private_10_network(self, mock_dns):
        """Test that 10.x.x.x private IPs are blocked."""
        mock_dns.return_value = [
            (2, 1, 6, "", ("10.0.0.1", 0)),
        ]
        crawler = CrawlerService()
        with pytest.raises(ValueError, match="private or reserved"):
            crawler.fetch_url("https://internal.corp.example.com")

    @patch("src.infrastructure.external.crawler.crawler.socket.getaddrinfo")
    def test_block_private_172_network(self, mock_dns):
        """Test that 172.16.x.x private IPs are blocked."""
        mock_dns.return_value = [
            (2, 1, 6, "", ("172.16.0.1", 0)),
        ]
        crawler = CrawlerService()
        with pytest.raises(ValueError, match="private or reserved"):
            crawler.fetch_url("https://internal.example.com")

    @patch("src.infrastructure.external.crawler.crawler.socket.getaddrinfo")
    def test_block_private_192_168_network(self, mock_dns):
        """Test that 192.168.x.x private IPs are blocked."""
        mock_dns.return_value = [
            (2, 1, 6, "", ("192.168.1.1", 0)),
        ]
        crawler = CrawlerService()
        with pytest.raises(ValueError, match="private or reserved"):
            crawler.fetch_url("https://router.local")

    @patch("src.infrastructure.external.crawler.crawler.socket.getaddrinfo")
    def test_block_link_local(self, mock_dns):
        """Test that link-local (169.254.x.x) IPs are blocked (cloud metadata)."""
        mock_dns.return_value = [
            (2, 1, 6, "", ("169.254.169.254", 0)),
        ]
        crawler = CrawlerService()
        with pytest.raises(ValueError, match="private or reserved"):
            crawler.fetch_url("https://metadata.google.internal")

    @patch("src.infrastructure.external.crawler.crawler.socket.getaddrinfo")
    def test_block_unresolvable_hostname(self, mock_dns):
        """Test that unresolvable hostnames are blocked."""
        import socket
        mock_dns.side_effect = socket.gaierror("Name resolution failed")
        crawler = CrawlerService()
        with pytest.raises(ValueError, match="Cannot resolve hostname"):
            crawler.fetch_url("https://nonexistent.invalid")

    @patch("src.infrastructure.external.crawler.crawler.socket.getaddrinfo")
    @patch("src.infrastructure.external.crawler.crawler.requests.get")
    def test_block_redirect_to_private_ip(self, mock_get, mock_dns):
        """Test that redirects to private IPs are blocked."""
        # First resolve is public (allowed)
        # Second resolve (for redirect target) is private (blocked)
        mock_dns.side_effect = [
            [(2, 1, 6, "", ("93.184.216.34", 0))],  # public
            [(2, 1, 6, "", ("10.0.0.1", 0))],        # private (redirect)
        ]

        mock_response = MagicMock()
        mock_response.is_redirect = True
        mock_response.status_code = 302
        mock_response.headers = {"Location": "https://internal.corp/secret"}
        mock_response.close = MagicMock()
        mock_get.return_value = mock_response

        crawler = CrawlerService()
        with pytest.raises(ValueError, match="private or reserved"):
            crawler.fetch_url("https://example.com/redirect")

    @patch("src.infrastructure.external.crawler.crawler.socket.getaddrinfo")
    @patch("src.infrastructure.external.crawler.crawler.requests.get")
    def test_response_size_limit(self, mock_get, mock_dns):
        """Test that oversized responses are rejected."""
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 0))]

        # Create a response that exceeds size limit
        mock_response = MagicMock()
        mock_response.is_redirect = False
        mock_response.raise_for_status = MagicMock()
        # Each chunk is 1MB, return 11 chunks (> 10MB limit)
        big_chunk = b"x" * (1024 * 1024)
        mock_response.iter_content.return_value = iter([big_chunk] * 11)
        mock_response.close = MagicMock()
        mock_get.return_value = mock_response

        crawler = CrawlerService()
        with pytest.raises(ValueError, match="exceeds maximum allowed size"):
            crawler.fetch_url("https://example.com/huge-file")

    @patch("src.infrastructure.external.crawler.crawler.socket.getaddrinfo")
    @patch("src.infrastructure.external.crawler.crawler.requests.get")
    def test_allows_public_ip(self, mock_get, mock_dns):
        """Test that public IPs are allowed through."""
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 0))]

        html = b"<html><head><title>Public</title></head><body><p>OK</p></body></html>"
        mock_response = MagicMock()
        mock_response.is_redirect = False
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content.return_value = iter([html])
        mock_response.headers = {"content-type": "text/html"}
        mock_response.close = MagicMock()
        mock_get.return_value = mock_response

        crawler = CrawlerService()
        result = crawler.fetch_url("https://example.com")
        assert result.title == "Public"


class TestValidateNotPrivate:
    """Unit tests for _validate_not_private helper."""

    @patch("src.infrastructure.external.crawler.crawler.socket.getaddrinfo")
    def test_public_ip_passes(self, mock_dns):
        """Test public IP passes validation."""
        mock_dns.return_value = [(2, 1, 6, "", ("8.8.8.8", 0))]
        _validate_not_private("dns.google.com")  # should not raise

    @patch("src.infrastructure.external.crawler.crawler.socket.getaddrinfo")
    def test_loopback_blocked(self, mock_dns):
        """Test loopback IP is blocked."""
        mock_dns.return_value = [(2, 1, 6, "", ("127.0.0.1", 0))]
        with pytest.raises(ValueError, match="private or reserved"):
            _validate_not_private("localhost")

    @patch("src.infrastructure.external.crawler.crawler.socket.getaddrinfo")
    def test_multicast_blocked(self, mock_dns):
        """Test multicast IPs are blocked."""
        mock_dns.return_value = [(2, 1, 6, "", ("224.0.0.1", 0))]
        with pytest.raises(ValueError, match="private or reserved"):
            _validate_not_private("multicast.example.com")
