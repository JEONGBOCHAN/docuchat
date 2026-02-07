# -*- coding: utf-8 -*-
"""
Architecture guard tests: enforce Clean Architecture layer boundaries.

These tests statically scan imports in the application layer to prevent
dependency violations. If a test fails, it means someone introduced an
import that crosses a forbidden layer boundary.

Rules enforced:
  - application MUST NOT import from src.models (presentation Pydantic models)
  - application MUST NOT import from fastapi (web framework)
  - application MUST NOT import from sqlalchemy (ORM / persistence impl)
  - application MUST NOT import from src.infrastructure (adapter implementations)

Allowed:
  - application CAN import from src.application (same layer)
  - application CAN import from src.core (shared config / utilities)
  - application CAN import from stdlib and third-party libs (abc, dataclasses, etc.)
"""

import ast
import os
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APPLICATION_DIR = PROJECT_ROOT / "src" / "application"

# Forbidden import prefixes for the application layer.
FORBIDDEN_PREFIXES = [
    "src.models",
    "src.infrastructure",
    "fastapi",
    "sqlalchemy",
]

# Files that are explicitly allowed to break the rules (escape hatch).
# Add paths here only with a comment explaining WHY.
ALLOWED_EXCEPTIONS: set[str] = set()


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────

def _collect_python_files(directory: Path) -> list[Path]:
    """Collect all .py files under *directory* recursively."""
    return sorted(directory.rglob("*.py"))


def _extract_imports(filepath: Path) -> list[tuple[int, str]]:
    """Parse *filepath* and return (line_number, module_name) for every import.

    Handles both ``import X`` and ``from X import Y`` forms.
    """
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.lineno, node.module))
    return imports


def _find_violations(
    directory: Path,
    forbidden: list[str],
    exceptions: set[str],
) -> list[str]:
    """Scan all Python files under *directory* for forbidden imports.

    Returns a list of human-readable violation descriptions.
    """
    violations: list[str] = []
    for filepath in _collect_python_files(directory):
        rel = filepath.relative_to(PROJECT_ROOT).as_posix()
        if rel in exceptions:
            continue
        for lineno, module in _extract_imports(filepath):
            for prefix in forbidden:
                if module == prefix or module.startswith(prefix + "."):
                    violations.append(
                        f"{rel}:{lineno} imports '{module}' "
                        f"(forbidden prefix: '{prefix}')"
                    )
    return violations


# ──────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────

class TestApplicationLayerBoundaries:
    """Ensure the application layer does not depend on outer layers."""

    def test_no_forbidden_imports_in_application_layer(self):
        """Application layer must not import from models, infrastructure,
        fastapi, or sqlalchemy."""
        violations = _find_violations(
            APPLICATION_DIR,
            FORBIDDEN_PREFIXES,
            ALLOWED_EXCEPTIONS,
        )
        if violations:
            msg = (
                "Application layer boundary violations detected!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: move the dependency behind a port/DTO, "
                "or perform the conversion in the API/infrastructure layer."
            )
            pytest.fail(msg)

    @pytest.mark.parametrize("prefix", FORBIDDEN_PREFIXES)
    def test_individual_forbidden_prefix(self, prefix: str):
        """Granular check per forbidden prefix for clearer failure messages."""
        violations = _find_violations(
            APPLICATION_DIR,
            [prefix],
            ALLOWED_EXCEPTIONS,
        )
        if violations:
            msg = (
                f"Application layer imports from '{prefix}':\n\n"
                + "\n".join(f"  - {v}" for v in violations)
            )
            pytest.fail(msg)
