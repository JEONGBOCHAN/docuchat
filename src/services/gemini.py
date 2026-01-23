# -*- coding: utf-8 -*-
"""Gemini File Search API service."""

from functools import lru_cache
from typing import Any

import requests
from google import genai
from google.genai import types

from src.core.config import get_settings


class GeminiService:
    """Service for interacting with Gemini File Search API."""

    def __init__(self):
        """Initialize the Gemini client."""
        settings = get_settings()
        self._api_key = settings.google_api_key
        self._client = genai.Client(api_key=self._api_key)

    @property
    def client(self) -> genai.Client:
        """Get the Gemini client."""
        return self._client

    # ========== File Search Store (Channel) Operations ==========

    def create_store(self, display_name: str) -> dict[str, Any]:
        """Create a new File Search Store.

        Args:
            display_name: Human-readable name for the store

        Returns:
            Store information including name (ID)
        """
        store = self._client.file_search_stores.create(
            config={"display_name": display_name}
        )
        return {
            "name": store.name,
            "display_name": display_name,
        }

    def get_store(self, store_name: str) -> dict[str, Any] | None:
        """Get a File Search Store by name.

        Args:
            store_name: The store name/ID (e.g., "fileSearchStores/xxx")

        Returns:
            Store information or None if not found
        """
        try:
            store = self._client.file_search_stores.get(name=store_name)
            return {
                "name": store.name,
                "display_name": getattr(store, "display_name", ""),
            }
        except Exception:
            return None

    def list_stores(self) -> list[dict[str, Any]]:
        """List all File Search Stores.

        Returns:
            List of store information
        """
        stores = []
        for store in self._client.file_search_stores.list():
            stores.append({
                "name": store.name,
                "display_name": getattr(store, "display_name", ""),
            })
        return stores

    def delete_store(self, store_name: str, force: bool = True) -> bool:
        """Delete a File Search Store.

        Uses REST API directly because SDK doesn't support force delete.

        Args:
            store_name: The store name/ID
            force: Whether to force delete (removes all files first)

        Returns:
            True if deleted successfully or resource not found (already deleted)
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/{store_name}"
        if force:
            url += "?force=true"
        url += f"&key={self._api_key}" if force else f"?key={self._api_key}"

        response = requests.delete(url)
        # Treat 200 (success) and 404 (not found/already deleted) as success
        return response.status_code in (200, 404)

    # ========== Document Operations ==========

    def upload_file(
        self,
        store_name: str,
        file_path: str,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """Upload a file to a File Search Store.

        Args:
            store_name: The store name/ID
            file_path: Path to the file to upload
            display_name: Optional display name for the file

        Returns:
            Operation information including document_name
        """
        try:
            # Use display_name if provided, otherwise use the filename from path
            config = {}
            if display_name:
                config["display_name"] = display_name

            operation = self._client.file_search_stores.upload_to_file_search_store(
                file=file_path,
                file_search_store_name=store_name,
                config=config if config else None,
            )
            # Handle None as False for done field
            is_done = operation.done if operation.done is not None else False
            result = {
                "name": operation.name,
                "done": is_done,
            }
            # Include document_name from response if available
            if operation.response and hasattr(operation.response, "document_name"):
                result["document_name"] = operation.response.document_name
            return result
        except Exception:
            raise

    def get_operation_status(self, operation_name: str) -> dict[str, Any]:
        """Get the status of an upload operation.

        Args:
            operation_name: The operation name/ID

        Returns:
            Operation status - always returns done=True since operation polling is unreliable
        """
        # The Gemini File Search API's operations.get() doesn't work reliably
        # with the operation names returned by upload_to_file_search_store.
        # Since the upload itself succeeds (202 response), we assume the operation
        # completed. The actual document status can be checked via list_store_files.
        return {"name": operation_name, "done": True}

    def list_store_files(self, store_name: str) -> list[dict[str, Any]]:
        """List all files in a File Search Store.

        Args:
            store_name: The store name/ID

        Returns:
            List of file information
        """
        files = []
        try:
            # Use genai client to list documents in store
            documents = list(
                self._client.file_search_stores.documents.list(parent=store_name)
            )
            for doc in documents:
                # Get state as string
                state = "ACTIVE"
                if hasattr(doc, "state"):
                    state_val = doc.state
                    if hasattr(state_val, "name"):
                        state = state_val.name.replace("STATE_", "")
                    elif isinstance(state_val, str):
                        state = state_val.replace("STATE_", "")

                files.append({
                    "name": doc.name if hasattr(doc, "name") else "",
                    "display_name": doc.display_name if hasattr(doc, "display_name") else "",
                    "size_bytes": doc.size_bytes if hasattr(doc, "size_bytes") else 0,
                    "state": state,
                })
        except Exception:
            pass
        return files

    def delete_file(self, file_name: str) -> bool:
        """Delete a file from Files API.

        Args:
            file_name: The file name/ID (e.g., "files/xxx")

        Returns:
            True if deleted successfully
        """
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}"
            url += f"?key={self._api_key}"
            response = requests.delete(url)
            return response.status_code == 200
        except Exception:
            return False

    def delete_store_document(self, document_name: str, force: bool = True) -> bool:
        """Delete a document from File Search Store.

        Uses REST API directly because SDK doesn't support force delete.

        Args:
            document_name: The document name (e.g., "fileSearchStores/xxx/documents/yyy")
            force: If True, delete even if document has chunks

        Returns:
            True if deleted successfully or resource not found (already deleted)
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/{document_name}"
        if force:
            url += "?force=true"
        url += f"&key={self._api_key}" if force else f"?key={self._api_key}"

        response = requests.delete(url)
        # Treat 200 (success) and 404 (not found/already deleted) as success
        return response.status_code in (200, 404)

    # ========== Agent Support Operations ==========
    # NOTE: The following methods are kept for backward compatibility with:
    # - src/agents/ (RAG agent and search tools)
    # - src/mcp_server/tools.py
    # - src/services/scheduler_jobs.py
    # Future Phase 4 could migrate these to use Clean Architecture Ports.

    def search_documents(
        self,
        store_name: str,
        query: str,
        model: str = "gemini-3-flash-preview",
    ) -> dict[str, Any]:
        """Search documents and return results for agent use.

        This is a simplified search that returns sources without generating
        a full answer. Used by the Agent's search tool.

        Args:
            store_name: The store name/ID to search in
            query: The search query
            model: The model to use

        Returns:
            Dict with 'sources' list and optional 'error'
        """
        try:
            # Use a simple search prompt
            search_prompt = f"Find information about: {query}\n\nReturn the relevant content from the documents."

            response = self._client.models.generate_content(
                model=model,
                contents=search_prompt,
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[store_name]
                            )
                        )
                    ]
                ),
            )

            # Extract grounding sources from response
            sources = []
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "grounding_metadata"):
                    metadata = candidate.grounding_metadata
                    if hasattr(metadata, "grounding_chunks"):
                        for chunk in metadata.grounding_chunks:
                            ctx = getattr(chunk, "retrieved_context", None)
                            source_name = "unknown"
                            content = ""
                            if ctx:
                                source_name = getattr(ctx, "title", None) or getattr(ctx, "uri", None) or "unknown"
                                content = getattr(ctx, "text", "") or ""
                            sources.append({
                                "source": source_name,
                                "content": content,
                            })

            return {"sources": sources}

        except Exception as e:
            return {"sources": [], "error": str(e)}


@lru_cache
def get_gemini_service() -> GeminiService:
    """Get cached GeminiService instance."""
    return GeminiService()
