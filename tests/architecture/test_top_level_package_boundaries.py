# -*- coding: utf-8 -*-
"""
Architecture guard: top-level runtime packages must not import module internals.

Top-level runtime packages (src/mcp_server, src/agents, src/infrastructure/observability)
may only access module functionality through the public API:
  - src.modules.<module>.public

They must NOT import module internal layers:
  - src.modules.<module>.domain.*
  - src.modules.<module>.application.*
  - src.modules.<module>.infrastructure.*
  - src.modules.<module>.presentation.*
"""

import ast
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]

TARGET_PACKAGE_DIRS = [
    PROJECT_ROOT / "src" / "mcp_server",
    PROJECT_ROOT / "src" / "agents",
    PROJECT_ROOT / "src" / "infrastructure" / "observability",
]


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────

def _collect_python_files(directory: Path) -> list[Path]:
    """Collect all .py files under *directory* recursively."""
    if not directory.exists():
        return []
    return sorted(directory.rglob("*.py"))


def _extract_imports(filepath: Path) -> list[tuple[int, str]]:
    """Parse *filepath* and return (line_number, module_name) for every import."""
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


def _is_forbidden_module_internal_import(module: str) -> bool:
    """Return True if *module* is a direct import into module internals.

    Forbidden: src.modules.<name>.<layer> where layer != public
    Allowed:   src.modules.<name>.public (or children under .public)
    """
    parts = module.split(".")
    if len(parts) < 4 or parts[0] != "src" or parts[1] != "modules":
        return False
    return parts[3] != "public"


# ──────────────────────────────────────────────────────────
# Scanner
# ──────────────────────────────────────────────────────────

def _find_violations() -> list[str]:
    """Scan all target packages for forbidden module-internal imports."""
    violations: list[str] = []

    for pkg_dir in TARGET_PACKAGE_DIRS:
        for filepath in _collect_python_files(pkg_dir):
            rel = filepath.relative_to(PROJECT_ROOT).as_posix()
            for lineno, imported in _extract_imports(filepath):
                if _is_forbidden_module_internal_import(imported):
                    violations.append(
                        f"{rel}:{lineno} imports '{imported}'"
                    )

    return violations


# ──────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────

class TestTopLevelPackageBoundaries:
    """Top-level runtime packages must only use module public APIs."""

    def test_top_level_packages_only_use_module_public_api(self):
        """No top-level package may import module internals directly."""
        violations = _find_violations()
        if violations:
            msg = (
                "Top-level runtime packages import module internals directly!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: Replace direct module internal import with "
                "'src.modules.<module>.public' contract.\n"
                "Example: 'from src.modules.workspace.public import ...' "
                "instead of 'from src.modules.workspace.application.* import ...'"
            )
            pytest.fail(msg)

    def test_top_level_packages_do_not_import_module_presentation(self):
        """Specifically verify presentation layer is never imported."""
        violations: list[str] = []

        for pkg_dir in TARGET_PACKAGE_DIRS:
            for filepath in _collect_python_files(pkg_dir):
                rel = filepath.relative_to(PROJECT_ROOT).as_posix()
                for lineno, imported in _extract_imports(filepath):
                    parts = imported.split(".")
                    if (
                        len(parts) >= 4
                        and parts[0] == "src"
                        and parts[1] == "modules"
                        and parts[3] == "presentation"
                    ):
                        violations.append(
                            f"{rel}:{lineno} imports '{imported}'"
                        )

        if violations:
            msg = (
                "Top-level packages must never import module presentation layer!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: Use 'src.modules.<module>.public' instead."
            )
            pytest.fail(msg)


class TestHelperSelfTests:
    """Self-tests to verify guard logic works correctly."""

    def test_forbidden_detects_domain_import(self):
        assert _is_forbidden_module_internal_import("src.modules.workspace.domain.entities") is True

    def test_forbidden_detects_application_import(self):
        assert _is_forbidden_module_internal_import("src.modules.workspace.application.services.foo") is True

    def test_forbidden_detects_infrastructure_import(self):
        assert _is_forbidden_module_internal_import("src.modules.conversation.infrastructure.di") is True

    def test_forbidden_detects_presentation_import(self):
        assert _is_forbidden_module_internal_import("src.modules.ops.presentation.api.health") is True

    def test_allowed_public_import(self):
        assert _is_forbidden_module_internal_import("src.modules.workspace.public") is False

    def test_allowed_public_child_import(self):
        assert _is_forbidden_module_internal_import("src.modules.workspace.public.something") is False

    def test_non_module_import_not_forbidden(self):
        assert _is_forbidden_module_internal_import("src.core.config") is False

    def test_short_module_path_not_forbidden(self):
        assert _is_forbidden_module_internal_import("src.modules.workspace") is False

    def test_stdlib_not_forbidden(self):
        assert _is_forbidden_module_internal_import("os.path") is False
