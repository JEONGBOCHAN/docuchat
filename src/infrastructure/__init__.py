# -*- coding: utf-8 -*-
"""Infrastructure layer - Port implementations and adapters."""

# Explicitly import submodules to make them accessible via attribute access.
# This is required for unittest.mock.patch() to work correctly when patching
# paths like "src.infrastructure.di.create_process_query_use_case"
from src.infrastructure import di
