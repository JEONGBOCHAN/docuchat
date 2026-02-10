# -*- coding: utf-8 -*-
"""Architecture gate: module public.py must not expose ORM models.

Ensures that src/modules/*/public.py never re-exports ORM model classes
from infrastructure.persistence.models.  Module boundaries must use
Port/DTO/UseCase contracts only.
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULES_DIR = PROJECT_ROOT / "src" / "modules"

# Patterns that indicate ORM model imports
FORBIDDEN_IMPORT_SUFFIXES = [
    ".infrastructure.persistence.models",
]

# ORM model name patterns (suffixes)
ORM_NAME_PATTERNS = ("DB", "Model", "Metadata")


def _collect_public_files() -> list[Path]:
    """Collect all public.py files under src/modules/*/."""
    if not MODULES_DIR.exists():
        return []
    return sorted(MODULES_DIR.glob("*/public.py"))


def _extract_imports(filepath: Path) -> list[tuple[int, str, list[str]]]:
    """Extract imports: (lineno, module_path, imported_names)."""
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []
    results: list[tuple[int, str, list[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [alias.name for alias in node.names]
            results.append((node.lineno, node.module, names))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                results.append((node.lineno, alias.name, []))
    return results


def _extract_all_list(filepath: Path) -> list[str]:
    """Extract names from __all__ list if present."""
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        return [
                            elt.value
                            for elt in node.value.elts
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                        ]
    return []


def test_public_py_no_orm_model_imports():
    """public.py must not import from infrastructure.persistence.models."""
    violations: list[str] = []
    for filepath in _collect_public_files():
        rel = filepath.relative_to(PROJECT_ROOT).as_posix()
        for lineno, module, names in _extract_imports(filepath):
            for suffix in FORBIDDEN_IMPORT_SUFFIXES:
                if module.endswith(suffix):
                    violations.append(
                        f"{rel}:{lineno} imports from '{module}' (names: {names})"
                    )
    if violations:
        pytest.fail(
            "Module public.py files import ORM models from persistence layer!\n\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: public.py should only expose Port/DTO/UseCase/factory contracts."
        )


def test_public_py_all_no_orm_names():
    """public.py __all__ must not contain ORM model names."""
    violations: list[str] = []
    for filepath in _collect_public_files():
        rel = filepath.relative_to(PROJECT_ROOT).as_posix()
        all_names = _extract_all_list(filepath)
        for name in all_names:
            if name.endswith(ORM_NAME_PATTERNS):
                violations.append(f"{rel}: __all__ contains '{name}'")
    if violations:
        pytest.fail(
            "Module public.py __all__ exposes ORM model names!\n\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: remove ORM models from __all__ and expose DTO/Port types instead."
        )
