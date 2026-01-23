# -*- coding: utf-8 -*-
"""
LLM Port.

Defines the interface for Large Language Model operations.
This abstracts the actual LLM implementation (Gemini, OpenAI, Claude, etc.)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generator, Any


@dataclass
class LLMMessage:
    """A message in a conversation.

    Attributes:
        role: The role (user, assistant, system)
        content: The message content
    """

    role: str
    content: str


@dataclass
class LLMResponse:
    """Response from an LLM.

    Attributes:
        content: The generated text
        finish_reason: Why generation stopped (stop, length, etc.)
        usage: Token usage information
        metadata: Additional response metadata
    """

    content: str
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMPort(ABC):
    """Abstract interface for LLM operations.

    Implementations of this port handle text generation with LLMs.
    This allows the application to use different LLM providers without
    changing business logic.

    Example:
        # Using Gemini
        llm = GeminiLLMAdapter(api_key)
        response = llm.generate("Explain quantum computing")

        # Can be replaced with OpenAI
        llm = OpenAILLMAdapter(api_key)
        response = llm.generate("Explain quantum computing")
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate text from a prompt.

        Args:
            prompt: The user prompt
            system_prompt: Optional system instructions
            temperature: Creativity (0.0-1.0)
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with generated content
        """
        pass

    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Generator[str, None, None]:
        """Generate text with streaming.

        Args:
            prompt: The user prompt
            system_prompt: Optional system instructions
            temperature: Creativity (0.0-1.0)
            max_tokens: Maximum tokens to generate

        Yields:
            Text chunks as they are generated
        """
        pass

    @abstractmethod
    def chat(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a response in a conversation.

        Args:
            messages: Conversation history
            system_prompt: Optional system instructions
            temperature: Creativity (0.0-1.0)

        Returns:
            LLMResponse with generated content
        """
        pass
