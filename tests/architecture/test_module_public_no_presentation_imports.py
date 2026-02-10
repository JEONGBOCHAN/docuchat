# -*- coding: utf-8 -*-
"""Architecture gate: module public.py must not import from presentation layer.

Ensures that src/modules/*/public.py never references its own presentation layer.
public.py should depend on infrastructure/application, not presentation.
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULES_DIR = PROJECT_ROOT / "src" / "modules"


def _collect_public_files() -> list[Path]:
    if not MODULES_DIR.exists():
        return []
    return sorted(MODULES_DIR.glob("*/public.py"))


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


def test_public_py_no_presentation_imports():
    """public.py must not import from its module's presentation layer."""
    violations: list[str] = []
    for filepath in _collect_public_files():
        rel = filepath.relative_to(PROJECT_ROOT).as_posix()
        module_name = filepath.parent.name  # e.g. "knowledge"
        forbidden = f"src.modules.{module_name}.presentation"
        for lineno, module in _extract_imports(filepath):
            if module == forbidden or module.startswith(forbidden + "."):
                violations.append(f"{rel}:{lineno} imports '{module}'")
    if violations:
        pytest.fail(
            "Module public.py imports from presentation layer!\n\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: move the dependency to infrastructure or application layer."
        )
