# -*- coding: utf-8 -*-
"""
Strict gate: src/modules must NOT import from src.api.

Modules own their own presentation layer (src/modules/<m>/presentation/).
The legacy src/api path is a compatibility shim and must not be referenced
from modules.
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULES_DIR = PROJECT_ROOT / "src" / "modules"

FORBIDDEN_PREFIXES = [
    "src.api",
]


def _collect_python_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.rglob("*.py"))


def _extract_imports(filepath: Path) -> list[tuple[int, str]]:
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


class TestModulesNoSrcApiImports:
    """Modules must not import from the legacy src.api path."""

    def test_no_src_api_imports_in_modules(self):
        violations: list[str] = []
        for filepath in _collect_python_files(MODULES_DIR):
            rel = filepath.relative_to(PROJECT_ROOT).as_posix()
            for lineno, module in _extract_imports(filepath):
                for prefix in FORBIDDEN_PREFIXES:
                    if module == prefix or module.startswith(prefix + "."):
                        violations.append(
                            f"{rel}:{lineno} imports '{module}'"
                        )
        if violations:
            msg = (
                "src/modules imports from legacy src.api!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: modules must not depend on the legacy API layer."
            )
            pytest.fail(msg)
