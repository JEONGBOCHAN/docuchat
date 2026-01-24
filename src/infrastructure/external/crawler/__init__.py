# -*- coding: utf-8 -*-
"""Crawler infrastructure for web content extraction."""

from src.infrastructure.external.crawler.crawler import (
    CrawlerService,
    CrawlResult,
    get_crawler_service,
)

__all__ = [
    "CrawlerService",
    "CrawlResult",
    "get_crawler_service",
]
