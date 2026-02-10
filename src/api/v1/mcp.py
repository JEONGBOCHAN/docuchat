# -*- coding: utf-8 -*-
"""Compatibility shim — real implementation in conversation module."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module(
    "src.modules.conversation.presentation.api.mcp"
)
