# -*- coding: utf-8 -*-
"""Compatibility shim — real implementation in ops module."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module(
    "src.modules.ops.presentation.api.health"
)
