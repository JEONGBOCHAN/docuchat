# -*- coding: utf-8 -*-
"""Architecture gate: module presentation API must not import src.models directly.

Ensures that src/modules/**/presentation/api/*.py never imports from src.models.
Schema types should be accessed via module-local presentation/schemas/ facades.
Files under presentation/schemas/ are exempt (they are the re-export layer).
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULES_DIR = PROJECT_ROOT / "src" / "modules"
FORBIDDEN_PREFIX = "src.models"


def _collect_api_files() -> list[Path]:
    if not MODULES_DIR.exists():
        return []
    return sorted(MODULES_DIR.glob("*/presentation/api/*.py"))


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


def test_presentation_api_no_direct_src_models_imports():
    """Presentation API files must not import from src.models directly."""
    violations: list[str] = []
    for filepath in _collect_api_files():
        rel = filepath.relative_to(PROJECT_ROOT).as_posix()
        for lineno, module in _extract_imports(filepath):
            if module == FORBIDDEN_PREFIX or module.startswith(FORBIDDEN_PREFIX + "."):
                violations.append(f"{rel}:{lineno} imports '{module}'")
    if violations:
        pytest.fail(
            "Module presentation API files import from src.models directly!\n\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: use module-local presentation/schemas/ facades instead."
        )
