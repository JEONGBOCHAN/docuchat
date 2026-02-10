# -*- coding: utf-8 -*-
"""
Generate FAQ Use Case.

This use case handles FAQ generation from documents in a channel.
It orchestrates the FAQ generation process through the port interface.
"""

from dataclasses import dataclass, field

from src.shared.kernel.contracts.ports.faq_generation import FAQGenerationPort, FAQItemDTO


@dataclass
class FAQResult:
    """Result of FAQ generation.

    Attributes:
        items: List of generated FAQ items
        channel_id: The channel/store that was analyzed
        error: Error message if generation failed
    """

    items: list[FAQItemDTO] = field(default_factory=list)
    channel_id: str | None = None
    error: str | None = None


class GenerateFAQUseCase:
    """Use case for generating FAQ from channel documents.

    This use case coordinates FAQ generation through the port interface,
    allowing the underlying implementation to be swapped without changing
    the application logic.

    Example:
        use_case = GenerateFAQUseCase(faq_port=gemini_adapter)
        result = use_case.execute(
            channel_id="channel-123",
            count=5,
        )
        for item in result.items:
            print(f"Q: {item.question}")
            print(f"A: {item.answer}")
    """

    def __init__(self, faq_port: FAQGenerationPort):
        """Initialize the use case with dependencies.

        Args:
            faq_port: The FAQ generation port implementation
        """
        self.faq_port = faq_port

    def execute(
        self,
        channel_id: str,
        count: int = 5,
    ) -> FAQResult:
        """Execute FAQ generation.

        Args:
            channel_id: The channel (document store) to analyze
            count: Number of FAQ items to generate (1-20)

        Returns:
            FAQResult with generated items or error
        """
        try:
            # Generate FAQ items through the port
            items = self.faq_port.generate_faq(
                store_name=channel_id,
                count=count,
            )

            return FAQResult(
                items=items,
                channel_id=channel_id,
                error=None,
            )

        except Exception as e:
            return FAQResult(
                items=[],
                channel_id=channel_id,
                error=str(e),
            )
