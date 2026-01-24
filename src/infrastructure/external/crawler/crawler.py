# -*- coding: utf-8 -*-
"""URL Crawler service for fetching web content."""

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


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

    def fetch_url(self, url: str) -> CrawlResult:
        """Fetch content from a URL.

        Args:
            url: The URL to fetch

        Returns:
            CrawlResult with extracted content

        Raises:
            ValueError: If URL is invalid
            requests.RequestException: If fetch fails
        """
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")

        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

        # Fetch the page
        response = requests.get(
            url,
            headers=self._headers,
            timeout=self._timeout,
            allow_redirects=True,
        )
        response.raise_for_status()

        # Parse HTML
        soup = BeautifulSoup(response.content, "html.parser")

        # Extract title
        title = self._extract_title(soup, url)

        # Extract main content
        content = self._extract_content(soup)

        return CrawlResult(
            url=url,
            title=title,
            content=content,
            content_type=response.headers.get("content-type", "text/html"),
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
