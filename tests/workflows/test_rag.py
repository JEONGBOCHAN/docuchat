# -*- coding: utf-8 -*-
"""Tests for RAG workflow."""

import pytest
from src.workflows.rag import (
    create_rag_workflow,
    RAGState,
    process_query,
    build_context,
    generate_response,
)


class TestProcessQuery:
    """Tests for process_query node."""

    def test_valid_query(self):
        """Test that valid query passes through."""
        state: RAGState = {
            "channel_id": "test-channel",
            "query": "What is attention mechanism?",
            "search_results": None,
            "context_chunks": [],
            "response": "",
            "grounding_sources": [],
            "error": None,
        }

        result = process_query(state)

        assert result["error"] is None
        assert result["query"] == "What is attention mechanism?"

    def test_empty_query(self):
        """Test that empty query returns error."""
        state: RAGState = {
            "channel_id": "test-channel",
            "query": "",
            "search_results": None,
            "context_chunks": [],
            "response": "",
            "grounding_sources": [],
            "error": None,
        }

        result = process_query(state)

        assert result["error"] == "Query cannot be empty"

    def test_whitespace_query(self):
        """Test that whitespace-only query returns error."""
        state: RAGState = {
            "channel_id": "test-channel",
            "query": "   ",
            "search_results": None,
            "context_chunks": [],
            "response": "",
            "grounding_sources": [],
            "error": None,
        }

        result = process_query(state)

        assert result["error"] == "Query cannot be empty"


class TestBuildContext:
    """Tests for build_context node."""

    def test_build_context_with_results(self):
        """Test context building with search results."""
        state: RAGState = {
            "channel_id": "test-channel",
            "query": "test query",
            "search_results": [
                {"content": "Attention is all you need.", "source": "transformer.pdf", "page": 1},
                {"content": "Self-attention mechanism.", "source": "transformer.pdf", "page": 2},
            ],
            "context_chunks": [],
            "response": "",
            "grounding_sources": [],
            "error": None,
        }

        result = build_context(state)

        assert len(result["context_chunks"]) == 2
        assert result["context_chunks"][0]["content"] == "Attention is all you need."
        assert result["context_chunks"][0]["source"] == "transformer.pdf"
        assert "transformer.pdf" in result["grounding_sources"]

    def test_build_context_empty_results(self):
        """Test context building with no search results."""
        state: RAGState = {
            "channel_id": "test-channel",
            "query": "test query",
            "search_results": [],
            "context_chunks": [],
            "response": "",
            "grounding_sources": [],
            "error": None,
        }

        result = build_context(state)

        assert result["context_chunks"] == []
        assert result["grounding_sources"] == []

    def test_build_context_with_error(self):
        """Test that error state is preserved."""
        state: RAGState = {
            "channel_id": "test-channel",
            "query": "",
            "search_results": None,
            "context_chunks": [],
            "response": "",
            "grounding_sources": [],
            "error": "Previous error",
        }

        result = build_context(state)

        assert result["error"] == "Previous error"


class TestGenerateResponse:
    """Tests for generate_response node."""

    def test_generate_response_no_context(self):
        """Test response when no context is available."""
        state: RAGState = {
            "channel_id": "test-channel",
            "query": "test query",
            "search_results": [],
            "context_chunks": [],
            "response": "",
            "grounding_sources": [],
            "error": None,
        }

        result = generate_response(state)

        assert "No relevant documents found" in result["response"]


class TestRAGWorkflow:
    """Integration tests for the full RAG workflow."""

    def test_workflow_creation(self):
        """Test that workflow can be created."""
        workflow = create_rag_workflow()
        assert workflow is not None

    def test_workflow_with_valid_query(self):
        """Test workflow execution with valid query."""
        workflow = create_rag_workflow()

        initial_state: RAGState = {
            "channel_id": "test-channel",
            "query": "What is transformer?",
            "search_results": None,
            "context_chunks": [],
            "response": "",
            "grounding_sources": [],
            "error": None,
        }

        result = workflow.invoke(initial_state)

        assert result["error"] is None
        assert result["response"] != ""

    def test_workflow_with_empty_query(self):
        """Test workflow handles empty query gracefully."""
        workflow = create_rag_workflow()

        initial_state: RAGState = {
            "channel_id": "test-channel",
            "query": "",
            "search_results": None,
            "context_chunks": [],
            "response": "",
            "grounding_sources": [],
            "error": None,
        }

        result = workflow.invoke(initial_state)

        assert result["error"] == "Query cannot be empty"
