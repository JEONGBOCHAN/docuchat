# -*- coding: utf-8 -*-
"""Compatibility shim — real implementation in knowledge module."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module(
    "src.modules.knowledge.presentation.api.faq"
)
