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


def _is_src_outside_domain(module: str) -> bool:
    """Return True if module is a src.* import that is NOT src.domain.*."""
    return module.startswith("src.") and not _matches_prefix(module, "src.domain")


def _is_module_presentation_import(module: str) -> bool:
    """Return True if module path points to src.modules.<m>.presentation..."""
    parts = module.split(".")
    return (
        len(parts) >= 4
        and parts[0] == "src"
        and parts[1] == "modules"
        and parts[3] == "presentation"
    )


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

# Infrastructure must not import from module internals, presentation layers, or web frameworks.
INFRA_FORBIDDEN = ["src.api", "fastapi", "src.models", "src.modules"]
INFRA_EXCEPTIONS: set[str] = set()


class TestInfrastructureLayerBoundaries:
    """Ensure infrastructure does not depend on presentation layers."""

    def test_infrastructure_does_not_import_presentation(self):
        """Infrastructure must not import from presentation layers or web frameworks."""
        violations = _find_violations(
            INFRASTRUCTURE_DIR, INFRA_FORBIDDEN, INFRA_EXCEPTIONS,
        )

        # Also detect module presentation imports (src.modules.<m>.presentation)
        for filepath in _collect_python_files(INFRASTRUCTURE_DIR):
            rel = filepath.relative_to(PROJECT_ROOT).as_posix()
            if rel in INFRA_EXCEPTIONS:
                continue
            for lineno, module in _extract_imports(filepath):
                if _is_module_presentation_import(module):
                    violations.append(
                        f"{rel}:{lineno} imports '{module}' "
                        f"(forbidden: module presentation layer)"
                    )

        if violations:
            msg = (
                "Infrastructure layer boundary violation!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: src/infrastructure must NOT import from "
                "src.modules.* (module internals), presentation layers, "
                "or web frameworks. "
                "It should only depend on shared kernel contracts and domain. "
                "Access module functionality via their public.py API or DI container."
            )
            pytest.fail(msg)


# ──────────────────────────────────────────────────────────
# Domain Layer Tests
# ──────────────────────────────────────────────────────────

# Domain must be completely independent.
# - No src.* imports except src.domain.*
# - No framework imports (fastapi, sqlalchemy, pydantic)
DOMAIN_FRAMEWORK_FORBIDDEN = ["fastapi", "sqlalchemy", "pydantic"]
DOMAIN_EXCEPTIONS: set[str] = set()


class TestDomainLayerBoundaries:
    """Ensure the domain layer has no external dependencies."""

    def test_domain_is_independent(self):
        """Domain layer must not import from any src.* outside src.domain, or frameworks."""
        violations: list[str] = []
        for filepath in _collect_python_files(DOMAIN_DIR):
            rel = filepath.relative_to(PROJECT_ROOT).as_posix()
            if rel in DOMAIN_EXCEPTIONS:
                continue
            for lineno, module in _extract_imports(filepath):
                if _is_src_outside_domain(module):
                    violations.append(
                        f"{rel}:{lineno} imports '{module}' "
                        f"(forbidden: src import outside domain)"
                    )
                for prefix in DOMAIN_FRAMEWORK_FORBIDDEN:
                    if _matches_prefix(module, prefix):
                        violations.append(
                            f"{rel}:{lineno} imports '{module}' "
                            f"(forbidden framework: '{prefix}')"
                        )
        if violations:
            msg = (
                "Domain layer has external dependencies!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: domain must only use stdlib. "
                "Any src.* import outside src.domain.* is forbidden. "
                "Move framework-dependent code to application or infrastructure."
            )
            pytest.fail(msg)


# ──────────────────────────────────────────────────────────
# Helper Self-Tests
# ──────────────────────────────────────────────────────────


class TestHelperPredicates:
    """Verify predicate helpers detect the right patterns."""

    def test_is_module_presentation_import(self):
        assert _is_module_presentation_import("src.modules.workspace.presentation.api.channels")
        assert _is_module_presentation_import("src.modules.knowledge.presentation.schemas.audio")
        assert _is_module_presentation_import("src.modules.workspace.presentation")
        assert not _is_module_presentation_import("src.modules.workspace.infrastructure.di")
        assert not _is_module_presentation_import("src.modules.workspace.application.use_cases")
        assert not _is_module_presentation_import("src.infrastructure.external")

    def test_is_src_outside_domain(self):
        assert _is_src_outside_domain("src.modules.workspace.public")
        assert _is_src_outside_domain("src.shared.kernel.contracts.ports")
        assert _is_src_outside_domain("src.infrastructure.external")
        assert _is_src_outside_domain("src.agents.graph")
        assert not _is_src_outside_domain("src.domain.entities.channel")
        assert not _is_src_outside_domain("src.domain.value_objects")
        assert not _is_src_outside_domain("fastapi")
        assert not _is_src_outside_domain("pydantic")

    def test_matches_prefix_detects_src_modules(self):
        """src.modules prefix must catch all module-internal imports."""
        assert _matches_prefix("src.modules.workspace.infrastructure.di", "src.modules")
        assert _matches_prefix("src.modules.conversation.infrastructure.agent.langgraph_runner", "src.modules")
        assert _matches_prefix("src.modules.ops.infrastructure.scheduler.scheduler_jobs", "src.modules")
        assert not _matches_prefix("src.shared.kernel.contracts", "src.modules")
        assert not _matches_prefix("src.infrastructure.scheduler.scheduler", "src.modules")
