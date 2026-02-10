# -*- coding: utf-8 -*-
"""
Architecture guard tests: enforce Clean Architecture layer boundaries.

These tests statically scan imports to prevent dependency violations.
If a test fails, it means someone introduced an import that crosses
a forbidden layer boundary.

Layer rules (post-migration modular monolith):
  ┌──────────────────┐
  │ Infrastructure     │  → May import: shared kernel, domain
  │ (src/infrastructure) │  → Must NOT import: module presentation, fastapi
  ├──────────────────┤
  │ Domain (src/domain)  │  → May import: stdlib only
  │                      │  → Must NOT import: any src.* layer
  └──────────────────┘

Module-internal boundaries are enforced by separate gate tests.
"""

import ast
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INFRASTRUCTURE_DIR = PROJECT_ROOT / "src" / "infrastructure"
DOMAIN_DIR = PROJECT_ROOT / "src" / "domain"


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


def _matches_prefix(module: str, prefix: str) -> bool:
    """Check if module matches a forbidden prefix."""
    return module == prefix or module.startswith(prefix + ".")


def _find_violations(
    directory: Path,
    forbidden: list[str],
    exceptions: set[str],
    allowed_prefixes: list[str] | None = None,
) -> list[str]:
    """Scan all Python files under *directory* for forbidden imports.

    Args:
        directory: Directory to scan.
        forbidden: List of forbidden import prefixes.
        exceptions: Set of relative file paths to skip.
        allowed_prefixes: Specific sub-prefixes to allow (overrides forbidden).

    Returns a list of human-readable violation descriptions.
    """
    allowed = allowed_prefixes or []
    violations: list[str] = []
    for filepath in _collect_python_files(directory):
        rel = filepath.relative_to(PROJECT_ROOT).as_posix()
        if rel in exceptions:
            continue
        for lineno, module in _extract_imports(filepath):
            for prefix in forbidden:
                if _matches_prefix(module, prefix):
                    # Check if this import is specifically allowed
                    if any(_matches_prefix(module, a) for a in allowed):
                        continue
                    violations.append(
                        f"{rel}:{lineno} imports '{module}' "
                        f"(forbidden prefix: '{prefix}')"
                    )
    return violations


# ──────────────────────────────────────────────────────────
# Infrastructure Layer Tests
# ──────────────────────────────────────────────────────────

# Infrastructure must not import from module presentation layers or web frameworks.
INFRA_FORBIDDEN = ["src.api", "fastapi", "src.models"]
INFRA_EXCEPTIONS: set[str] = set()


class TestInfrastructureLayerBoundaries:
    """Ensure infrastructure does not depend on presentation layers."""

    def test_infrastructure_does_not_import_presentation(self):
        """Infrastructure must not import from presentation layers or web frameworks."""
        violations = _find_violations(
            INFRASTRUCTURE_DIR, INFRA_FORBIDDEN, INFRA_EXCEPTIONS,
        )
        if violations:
            msg = (
                "Infrastructure layer imports presentation/web framework!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: infrastructure should only depend on "
                "shared kernel contracts and domain."
            )
            pytest.fail(msg)


# ──────────────────────────────────────────────────────────
# Domain Layer Tests
# ──────────────────────────────────────────────────────────

# Domain must be completely independent - no src.* imports.
DOMAIN_FORBIDDEN = [
    "src.application",
    "src.infrastructure",
    "src.api",
    "src.models",
    "src.core",
    "fastapi",
    "sqlalchemy",
    "pydantic",
]
DOMAIN_EXCEPTIONS: set[str] = set()


class TestDomainLayerBoundaries:
    """Ensure the domain layer has no external dependencies."""

    def test_domain_is_independent(self):
        """Domain layer must not import from any other src layer or frameworks."""
        violations = _find_violations(
            DOMAIN_DIR, DOMAIN_FORBIDDEN, DOMAIN_EXCEPTIONS,
        )
        if violations:
            msg = (
                "Domain layer has external dependencies!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: domain must only use stdlib. "
                "Move framework-dependent code to application or infrastructure."
            )
            pytest.fail(msg)
