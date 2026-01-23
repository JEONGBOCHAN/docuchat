# -*- coding: utf-8 -*-
"""
Application Use Cases.

Use cases orchestrate the flow of data and coordinate domain entities
and infrastructure services to fulfill business requirements.
"""

from src.application.use_cases.process_query import ProcessQueryUseCase, QueryResult

__all__ = [
    "ProcessQueryUseCase",
    "QueryResult",
]
