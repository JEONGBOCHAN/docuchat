# -*- coding: utf-8 -*-
"""
Strict gate: src/api/v1 shim files must use the re-export pattern.

Every shim file (except __init__.py and router.py) must contain only a
``from src.modules... import *`` or ``from src.shared... import *``
re-export line.  No sys.modules hacks, no local definitions.
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_V1_DIR = PROJECT_ROOT / "src" / "api" / "v1"

# These files are not shims — they have real logic and are exempt.
EXEMPT_FILES = {"__init__.py", "router.py"}


def _is_valid_shim(filepath: Path) -> tuple[bool, str]:
    """Check if a file is a valid re-export shim.

    A valid shim has only:
      - module docstring (optional)
      - coding declaration comment (optional)
      - ``from <target> import *`` statement(s)

    Returns (is_valid, reason).
    """
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return False, "SyntaxError"

    # Collect all top-level statements (skip module docstring)
    stmts = tree.body
    if not stmts:
        return False, "empty file"

    has_star_import = False
    for node in stmts:
        # String constant (docstring) is fine
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        # from X import * is the expected pattern
        if isinstance(node, ast.ImportFrom):
            if node.names and any(alias.name == "*" for alias in node.names):
                target = node.module or ""
                if target.startswith("src.modules.") or target.startswith("src.shared."):
                    has_star_import = True
                    continue
                return False, f"star import from non-module path: {target}"
            return False, f"non-star import: from {node.module}"
        # Anything else (function defs, assignments, regular imports) is forbidden
        return False, f"unexpected statement: {type(node).__name__} at line {node.lineno}"

    if not has_star_import:
        return False, "no star import found"
    return True, ""


class TestApiV1ShimStyle:
    """Ensure all src/api/v1 shim files use the re-export pattern."""

    def test_all_shims_use_star_import(self):
        """Each shim must be a minimal ``from src.modules... import *`` file."""
        violations: list[str] = []
        for filepath in sorted(API_V1_DIR.glob("*.py")):
            if filepath.name in EXEMPT_FILES:
                continue
            valid, reason = _is_valid_shim(filepath)
            if not valid:
                violations.append(f"{filepath.name}: {reason}")
        if violations:
            msg = (
                "src/api/v1 shim files violate re-export pattern!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: shim files must contain only "
                "``from src.modules.<m>.presentation.api.<name> import *``."
            )
            pytest.fail(msg)
