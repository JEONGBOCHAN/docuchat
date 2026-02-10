# -*- coding: utf-8 -*-
"""Architecture gate: modules may only import src.infrastructure from DI files.

Policy:
  - src/modules/<m>/infrastructure/di.py files MAY import from src.infrastructure.*
  - All other src/modules/**/*.py files MUST NOT import from src.infrastructure.*

This prevents infrastructure dependency spread beyond the designated DI boundary.
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULES_DIR = PROJECT_ROOT / "src" / "modules"

FORBIDDEN_PREFIX = "src.infrastructure"

# Only these files are allowed to import from src.infrastructure.*
ALLOWED_FILES = {
    "src/modules/workspace/infrastructure/di.py",
    "src/modules/knowledge/infrastructure/di.py",
    "src/modules/conversation/infrastructure/di.py",
    "src/modules/ops/infrastructure/di.py",
}


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
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


def test_modules_infrastructure_import_policy():
    """Only DI files may import from src.infrastructure.*."""
    violations: list[str] = []
    for filepath in _collect_python_files(MODULES_DIR):
        rel = filepath.relative_to(PROJECT_ROOT).as_posix()
        if rel in ALLOWED_FILES:
            continue
        for lineno, module in _extract_imports(filepath):
            if module == FORBIDDEN_PREFIX or module.startswith(FORBIDDEN_PREFIX + "."):
                violations.append(f"{rel}:{lineno} imports '{module}'")
    if violations:
        pytest.fail(
            "src/modules files outside DI import from src.infrastructure!\n\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: move src.infrastructure imports to the module's infrastructure/di.py file."
        )
