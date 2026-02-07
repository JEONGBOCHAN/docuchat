# -*- coding: utf-8 -*-
"""URL Crawler service for fetching web content."""

import ipaddress
import re
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

# Safety limits
MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_REDIRECTS = 5


def _validate_not_private(hostname: str) -> None:
    """Validate that hostname does not resolve to a private/reserved IP.

    Raises:
        ValueError: If hostname resolves to a blocked IP range.
    """
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname: {hostname}")

    for _, _, _, _, sockaddr in addr_info:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("URL resolves to a private or reserved IP address")


@dataclass
class CrawlResult:
    """Result of crawling a URL."""

    url: str
    title: str
    content: str
    content_type: str


class CrawlerService:
    """Service for crawling URLs and extracting content."""

    def __init__(self, timeout: int = 30):
        """Initialize the crawler.

        Args:
            timeout: Request timeout in seconds
        """
        self._timeout = timeout
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def _validated_request(self, url: str) -> tuple[bytes, dict[str, str]]:
        """Fetch a URL with SSRF protection and response size limit.

        Validates that resolved IPs are not private/reserved before each
        request (including redirects) and caps response body size.

        Returns:
            Tuple of (content_bytes, response_headers).
        """
        parsed = urlparse(url)
        _validate_not_private(parsed.hostname)

        response = requests.get(
            url,
            headers=self._headers,
            timeout=self._timeout,
            allow_redirects=False,
            stream=True,
        )

        # Follow redirects manually so each hop is SSRF-checked
        redirects = 0
        while response.is_redirect and redirects < MAX_REDIRECTS:
            location = response.headers.get("Location")
            if not location:
                break
            redirect_url = urljoin(url, location)  # handles relative URLs
            redirect_parsed = urlparse(redirect_url)
            if redirect_parsed.scheme not in ("http", "https"):
                raise ValueError(f"Redirect to unsupported scheme: {redirect_parsed.scheme}")
            _validate_not_private(redirect_parsed.hostname)
            url = redirect_url
            response.close()
            response = requests.get(
                url,
                headers=self._headers,
                timeout=self._timeout,
                allow_redirects=False,
                stream=True,
            )
            redirects += 1

        response.raise_for_status()

        # Read body with size limit
        chunks: list[bytes] = []
        bytes_read = 0
        for chunk in response.iter_content(chunk_size=8192):
            bytes_read += len(chunk)
            if bytes_read > MAX_RESPONSE_BYTES:
                response.close()
                raise ValueError(
                    f"Response exceeds maximum allowed size ({MAX_RESPONSE_BYTES // 1024 // 1024} MB)"
                )
            chunks.append(chunk)
        response.close()

        return b"".join(chunks), dict(response.headers)

    def fetch_url(self, url: str) -> CrawlResult:
        """Fetch content from a URL.

        Args:
            url: The URL to fetch

        Returns:
            CrawlResult with extracted content

        Raises:
            ValueError: If URL is invalid or targets private network
            requests.RequestException: If fetch fails
        """
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")

        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

        # Fetch with SSRF protection + size limit
        content_bytes, headers = self._validated_request(url)

        # Parse HTML
        soup = BeautifulSoup(content_bytes, "html.parser")

        # Extract title
        title = self._extract_title(soup, url)

        # Extract main content
        content = self._extract_content(soup)

        return CrawlResult(
            url=url,
            title=title,
            content=content,
            content_type=headers.get("content-type", "text/html"),
        )

    def _extract_title(self, soup: BeautifulSoup, fallback_url: str) -> str:
        """Extract page title."""
        # Try <title> tag
        if soup.title and soup.title.string:
            return soup.title.string.strip()

        # Try <h1> tag
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        # Fallback to domain
        parsed = urlparse(fallback_url)
        return parsed.netloc

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from HTML as markdown-like text."""
        # Remove unwanted elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
            tag.decompose()

        # Try to find main content area
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", {"class": re.compile(r"content|article|post|entry", re.I)})
            or soup.find("div", {"id": re.compile(r"content|article|post|entry", re.I)})
            or soup.body
            or soup
        )

        # Convert to markdown-like text
        lines = []
        for element in main_content.descendants:
            if element.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = int(element.name[1])
                text = element.get_text(strip=True)
                if text:
                    lines.append(f"\n{'#' * level} {text}\n")

            elif element.name == "p":
                text = element.get_text(strip=True)
                if text:
                    lines.append(f"\n{text}\n")

            elif element.name == "li":
                text = element.get_text(strip=True)
                if text:
                    lines.append(f"- {text}")

            elif element.name == "a":
                href = element.get("href", "")
                text = element.get_text(strip=True)
                if text and href and not href.startswith("#"):
                    # Skip if parent already processed
                    pass

            elif element.name == "blockquote":
                text = element.get_text(strip=True)
                if text:
                    lines.append(f"\n> {text}\n")

            elif element.name == "pre" or element.name == "code":
                text = element.get_text(strip=False)
                if text and element.name == "pre":
                    lines.append(f"\n```\n{text}\n```\n")

        # Clean up and join
        content = "\n".join(lines)

        # Remove excessive newlines
        content = re.sub(r"\n{3,}", "\n\n", content)

        return content.strip()

    def save_to_temp_file(self, result: CrawlResult) -> str:
        """Save crawl result to a temporary file.

        Args:
            result: The crawl result to save

        Returns:
            Path to the temporary file
        """
        # Create markdown content
        content = f"# {result.title}\n\n"
        content += f"Source: {result.url}\n\n"
        content += "---\n\n"
        content += result.content

        # Save to temp file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(content)
            return tmp.name


def get_crawler_service() -> CrawlerService:
    """Get CrawlerService instance."""
    return CrawlerService()
