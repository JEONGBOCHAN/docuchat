# -*- coding: utf-8 -*-
"""arXiv adapter module.

ArxivAdapter is lazy-imported so the optional `arxiv` package
doesn't break the application when it is not installed.
"""

__all__ = ["ArxivAdapter"]


def __getattr__(name: str):
    if name == "ArxivAdapter":
        from src.infrastructure.external.arxiv.adapter import ArxivAdapter
        return ArxivAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
