# -*- coding: utf-8 -*-
"""Export service for generating exports in various formats."""

import io
import json
import zipfile
from datetime import datetime, UTC
from sqlalchemy.orm import Session

from src.models.db_models import ChannelMetadata, NoteDB, ChatMessageDB
from src.models.export import (
    ExportFormat,
    NoteExportData,
    ChatExportData,
    ChannelExportMetadata,
    ChannelFullExport,
)
from src.models.chat import GroundingSource, ChatMessage
from src.services.channel_repository import ChannelRepository, ChatHistoryRepository
from src.services.note_repository import NoteRepository


class ExportService:
    """Service for exporting data in various formats."""

    def __init__(self, db: Session):
        """Initialize export service with database session."""
        self.db = db
        self.channel_repo = ChannelRepository(db)
        self.note_repo = NoteRepository(db)
        self.chat_repo = ChatHistoryRepository(db)

    def _parse_sources(self, sources_json: str) -> list[GroundingSource]:
        """Parse sources JSON string to list of GroundingSource."""
        try:
            sources_data = json.loads(sources_json) if sources_json else []
            return [GroundingSource(**s) for s in sources_data]
        except (json.JSONDecodeError, TypeError):
            return []

    def _note_db_to_export(self, note: NoteDB) -> NoteExportData:
        """Convert NoteDB to NoteExportData."""
        return NoteExportData(
            id=note.id,
            title=note.title,
            content=note.content,
            sources=self._parse_sources(note.sources_json),
            created_at=note.created_at,
            updated_at=note.updated_at,
        )

    def _message_db_to_chat(self, msg: ChatMessageDB) -> ChatMessage:
        """Convert ChatMessageDB to ChatMessage."""
        return ChatMessage(
            role=msg.role,
            content=msg.content,
            sources=self._parse_sources(msg.sources_json),
            created_at=msg.created_at,
        )

    def _channel_to_metadata(self, channel: ChannelMetadata) -> ChannelExportMetadata:
        """Convert ChannelMetadata to ChannelExportMetadata."""
        return ChannelExportMetadata(
            id=channel.gemini_store_id,
            name=channel.name,
            description=channel.description,
            created_at=channel.created_at,
            file_count=channel.file_count,
            total_size_bytes=channel.total_size_bytes,
        )

    # ---- Note Export ----

    def export_note_markdown(self, note: NoteDB) -> str:
        """Export a single note as Markdown."""
        lines = [
            f"# {note.title}",
            "",
            note.content,
            "",
        ]

        sources = self._parse_sources(note.sources_json)
        if sources:
            lines.append("---")
            lines.append("")
            lines.append("## Sources")
            lines.append("")
            for i, src in enumerate(sources, 1):
                page_info = f" (p.{src.page})" if src.page else ""
                lines.append(f"{i}. **{src.source}**{page_info}")
                if src.content:
                    lines.append(f"   > {src.content[:200]}...")
            lines.append("")

        lines.append("---")
        lines.append(f"*Created: {note.created_at.isoformat()}*")
        lines.append(f"*Updated: {note.updated_at.isoformat()}*")

        return "\n".join(lines)

    def export_note_json(self, note: NoteDB) -> str:
        """Export a single note as JSON."""
        data = self._note_db_to_export(note)
        return data.model_dump_json(indent=2)

    def export_note_pdf(self, note: NoteDB) -> bytes:
        """Export a single note as PDF."""
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()

        # Add Unicode font for Korean support
        pdf.add_font("NanumGothic", "", "C:/Windows/Fonts/malgun.ttf", uni=True)
        pdf.set_font("NanumGothic", size=16)

        # Title
        pdf.cell(0, 10, note.title, ln=True)
        pdf.ln(5)

        # Content
        pdf.set_font("NanumGothic", size=11)
        pdf.multi_cell(0, 7, note.content)
        pdf.ln(10)

        # Sources
        sources = self._parse_sources(note.sources_json)
        if sources:
            pdf.set_font("NanumGothic", size=12)
            pdf.cell(0, 10, "Sources", ln=True)
            pdf.set_font("NanumGothic", size=10)
            for i, src in enumerate(sources, 1):
                page_info = f" (p.{src.page})" if src.page else ""
                pdf.multi_cell(0, 6, f"{i}. {src.source}{page_info}")

        # Metadata
        pdf.ln(10)
        pdf.set_font("NanumGothic", size=9)
        pdf.cell(0, 5, f"Created: {note.created_at.isoformat()}", ln=True)
        pdf.cell(0, 5, f"Updated: {note.updated_at.isoformat()}", ln=True)

        return bytes(pdf.output())

    # ---- Chat History Export ----

    def export_chat_markdown(self, channel: ChannelMetadata) -> str:
        """Export chat history as Markdown."""
        messages = self.chat_repo.get_history(channel, limit=1000)

        lines = [
            f"# Chat History - {channel.name}",
            "",
            f"*Exported: {datetime.now(UTC).isoformat()}*",
            "",
            "---",
            "",
        ]

        for msg in messages:
            role_display = "**User**" if msg.role == "user" else "**Assistant**"
            lines.append(f"### {role_display}")
            lines.append(f"*{msg.created_at.isoformat()}*")
            lines.append("")
            lines.append(msg.content)
            lines.append("")

            sources = self._parse_sources(msg.sources_json)
            if sources:
                lines.append("**Sources:**")
                for src in sources:
                    page_info = f" (p.{src.page})" if src.page else ""
                    lines.append(f"- {src.source}{page_info}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def export_chat_json(self, channel: ChannelMetadata) -> str:
        """Export chat history as JSON."""
        messages = self.chat_repo.get_history(channel, limit=1000)
        data = ChatExportData(
            channel_id=channel.gemini_store_id,
            messages=[self._message_db_to_chat(m) for m in messages],
            exported_at=datetime.now(UTC),
        )
        return data.model_dump_json(indent=2)

    # ---- Channel Full Export ----

    def export_channel_markdown(self, channel: ChannelMetadata) -> str:
        """Export full channel as Markdown."""
        notes = self.note_repo.get_by_channel(channel, limit=1000)
        messages = self.chat_repo.get_history(channel, limit=1000)

        lines = [
            f"# {channel.name}",
            "",
            f"*{channel.description or 'No description'}*",
            "",
            f"- Created: {channel.created_at.isoformat()}",
            f"- Files: {channel.file_count}",
            f"- Total Size: {channel.total_size_bytes:,} bytes",
            "",
            "---",
            "",
        ]

        # Notes section
        if notes:
            lines.append("# Notes")
            lines.append("")
            for note in notes:
                lines.append(f"## {note.title}")
                lines.append("")
                lines.append(note.content)
                lines.append("")
                lines.append(f"*Created: {note.created_at.isoformat()}*")
                lines.append("")
                lines.append("---")
                lines.append("")

        # Chat history section
        if messages:
            lines.append("# Chat History")
            lines.append("")
            for msg in messages:
                role = "User" if msg.role == "user" else "Assistant"
                lines.append(f"**{role}** ({msg.created_at.isoformat()}):")
                lines.append("")
                lines.append(msg.content)
                lines.append("")

        lines.append("---")
        lines.append(f"*Exported: {datetime.now(UTC).isoformat()}*")

        return "\n".join(lines)

    def export_channel_json(self, channel: ChannelMetadata) -> str:
        """Export full channel as JSON."""
        notes = self.note_repo.get_by_channel(channel, limit=1000)
        messages = self.chat_repo.get_history(channel, limit=1000)

        data = ChannelFullExport(
            metadata=self._channel_to_metadata(channel),
            notes=[self._note_db_to_export(n) for n in notes],
            chat_history=[self._message_db_to_chat(m) for m in messages],
            exported_at=datetime.now(UTC),
        )
        return data.model_dump_json(indent=2)

    def export_channel_zip(self, channel: ChannelMetadata) -> bytes:
        """Export full channel as ZIP archive with multiple files."""
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Channel metadata
            metadata = self._channel_to_metadata(channel)
            zf.writestr("metadata.json", metadata.model_dump_json(indent=2))

            # Notes as individual markdown files
            notes = self.note_repo.get_by_channel(channel, limit=1000)
            for note in notes:
                safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in note.title)
                filename = f"notes/{note.id}_{safe_title[:50]}.md"
                zf.writestr(filename, self.export_note_markdown(note))

            # Notes JSON
            notes_json = [self._note_db_to_export(n).model_dump() for n in notes]
            zf.writestr("notes.json", json.dumps(notes_json, indent=2, default=str))

            # Chat history
            zf.writestr("chat_history.md", self.export_chat_markdown(channel))
            zf.writestr("chat_history.json", self.export_chat_json(channel))

            # Full export JSON
            zf.writestr("full_export.json", self.export_channel_json(channel))

        buffer.seek(0)
        return buffer.getvalue()

    # ---- Public API Methods ----

    def export_note(
        self, channel: ChannelMetadata, note_id: int, format: ExportFormat
    ) -> tuple[bytes | str, str, str]:
        """Export a note in the specified format.

        Args:
            channel: The channel
            note_id: Note ID
            format: Export format

        Returns:
            Tuple of (content, content_type, filename)
        """
        note = self.note_repo.get_by_id(note_id)
        if not note or note.channel_id != channel.id:
            raise ValueError("Note not found")

        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in note.title)[:50]

        if format == ExportFormat.MARKDOWN:
            content = self.export_note_markdown(note)
            return content, "text/markdown; charset=utf-8", f"{safe_title}.md"
        elif format == ExportFormat.PDF:
            content = self.export_note_pdf(note)
            return content, "application/pdf", f"{safe_title}.pdf"
        else:  # JSON
            content = self.export_note_json(note)
            return content, "application/json; charset=utf-8", f"{safe_title}.json"

    def export_chat(
        self, channel: ChannelMetadata, format: ExportFormat
    ) -> tuple[str, str, str]:
        """Export chat history in the specified format.

        Args:
            channel: The channel
            format: Export format

        Returns:
            Tuple of (content, content_type, filename)
        """
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in channel.name)[:50]

        if format == ExportFormat.MARKDOWN:
            content = self.export_chat_markdown(channel)
            return content, "text/markdown; charset=utf-8", f"{safe_name}_chat.md"
        else:  # JSON (PDF not supported for chat)
            content = self.export_chat_json(channel)
            return content, "application/json; charset=utf-8", f"{safe_name}_chat.json"

    def export_channel(
        self, channel: ChannelMetadata, format: ExportFormat
    ) -> tuple[bytes | str, str, str]:
        """Export full channel in the specified format.

        Args:
            channel: The channel
            format: Export format

        Returns:
            Tuple of (content, content_type, filename)
        """
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in channel.name)[:50]

        if format == ExportFormat.MARKDOWN:
            content = self.export_channel_markdown(channel)
            return content, "text/markdown; charset=utf-8", f"{safe_name}_export.md"
        elif format == ExportFormat.JSON:
            content = self.export_channel_json(channel)
            return content, "application/json; charset=utf-8", f"{safe_name}_export.json"
        else:  # ZIP for full backup (treat PDF as ZIP for channel export)
            content = self.export_channel_zip(channel)
            return content, "application/zip", f"{safe_name}_backup.zip"
