# -*- coding: utf-8 -*-
"""Architecture gate: non-legacy code must not import from src.application.

Non-legacy directories (src/infrastructure, src/agents, src/models, src/api)
should import from src.shared.kernel.contracts.* instead of src.application.*.

The src/application directory itself is exempt (it contains compatibility shims).
The src/modules directory is exempt (has its own guard tests).
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_PREFIX = "src.application"

# Directories that must NOT import from src.application
TARGET_DIRS = [
    PROJECT_ROOT / "src" / "infrastructure",
    PROJECT_ROOT / "src" / "agents",
    PROJECT_ROOT / "src" / "models",
    PROJECT_ROOT / "src" / "api",
]


def _collect_python_files() -> list[Path]:
    files: list[Path] = []
    for d in TARGET_DIRS:
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


def test_nonlegacy_no_src_application_imports():
    """Non-legacy code must not import from src.application.*."""
    violations: list[str] = []
    for filepath in _collect_python_files():
        rel = filepath.relative_to(PROJECT_ROOT).as_posix()
        for lineno, module in _extract_imports(filepath):
            if module == FORBIDDEN_PREFIX or module.startswith(FORBIDDEN_PREFIX + "."):
                violations.append(f"{rel}:{lineno} imports '{module}'")
    if violations:
        pytest.fail(
            "Non-legacy code imports from src.application!\n\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: use src.shared.kernel.contracts.* instead."
        )
