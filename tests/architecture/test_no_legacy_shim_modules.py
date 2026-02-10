# -*- coding: utf-8 -*-
"""Verify legacy re-export shim imports do not re-appear.

These infrastructure shims were removed during the modular monolith
migration. Any import referencing them indicates a regression.
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
TESTS_DIR = PROJECT_ROOT / "tests"

BANNED_SHIM_MODULES = (
    "src.infrastructure.agent.langgraph_runner",
    "src.infrastructure.agent.checkpoint_adapter",
    "src.infrastructure.compaction.runner",
    "src.infrastructure.scheduler.scheduler_jobs",
)


def _collect_python_files(*directories: Path) -> list[Path]:
    files: list[Path] = []
    for d in directories:
        if d.exists():
            files.extend(d.rglob("*.py"))
    return sorted(files)


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
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


def _matches_any_shim(module: str) -> str | None:
    for shim in BANNED_SHIM_MODULES:
        if module == shim or module.startswith(shim + "."):
            return shim
    return None


def test_no_legacy_shim_imports():
    """No source or test code should import from removed shim modules."""
    violations: list[str] = []

    for filepath in _collect_python_files(SRC_DIR, TESTS_DIR):
        rel = filepath.relative_to(PROJECT_ROOT).as_posix()
        for lineno, module in _extract_imports(filepath):
            matched = _matches_any_shim(module)
            if matched:
                violations.append(
                    f"{rel}:{lineno} imports '{module}' "
                    f"(removed shim: '{matched}')"
                )

    if violations:
        pytest.fail(
            "Legacy shim module imports found!\n\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nThese re-export shims were removed. "
            "Use the canonical module paths instead."
        )
