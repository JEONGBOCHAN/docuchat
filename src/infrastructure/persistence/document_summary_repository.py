# -*- coding: utf-8 -*-
"""Document summary cache repository — compatibility shim.

The implementation has been moved to:
  src.modules.workspace.infrastructure.persistence.document_summary_repository

This file re-exports for backward compatibility only.
No new implementations should be added here.
"""

from src.modules.workspace.infrastructure.persistence.document_summary_repository import (  # noqa: F401
    DocumentSummaryCacheRepository,
)
