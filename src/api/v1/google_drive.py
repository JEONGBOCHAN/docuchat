# -*- coding: utf-8 -*-
"""Compatibility shim — real implementation in workspace module."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module(
    "src.modules.workspace.presentation.api.google_drive"
)
