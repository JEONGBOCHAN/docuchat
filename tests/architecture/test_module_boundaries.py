# -*- coding: utf-8 -*-
"""
Architecture guard tests: enforce modular monolith module boundaries.

These tests statically scan imports to prevent cross-module boundary
violations. If a test fails, it means someone introduced an import that
crosses a forbidden module boundary.

Module rules:
  ┌─────────────────────────────────────────────────────────────┐
  │ src.modules.<A> can import:                                 │
  │   - src.modules.<A>.* (own internals)                       │
  │   - src.modules.<B>.public (other module public API only)   │
  │   - src.shared.* (shared kernel)                            │
  │   - src.core.* (config, database, etc.)                     │
  │   - stdlib, third-party                                     │
  │                                                             │
  │ src.modules.<A> MUST NOT import:                            │
  │   - src.modules.<B>.domain/application/infrastructure/      │
  │     presentation (other module internals)                   │
  │                                                             │
  │ src.modules.<A>.domain can import:                          │
  │   - src.modules.<A>.domain.* (own domain only)              │
  │   - stdlib                                                  │
  │                                                             │
  │ src.modules.<A>.domain MUST NOT import:                     │
  │   - any src.* outside own domain                            │
  └─────────────────────────────────────────────────────────────┘
"""

import ast
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULES_DIR = PROJECT_ROOT / "src" / "modules"

MODULE_INTERNAL_LAYERS = ["domain", "application", "infrastructure", "presentation"]


def _discover_module_names() -> list[str]:
    """Auto-discover module names by scanning src/modules/ directories."""
    if not MODULES_DIR.exists():
        return []
    return sorted(
        d.name
        for d in MODULES_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("__")
    )


MODULE_NAMES = _discover_module_names()


# ──────────────────────────────────────────────────────────
# Helpers (reuses pattern from test_layer_boundaries.py)
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


def _matches_prefix(module: str, prefix: str) -> bool:
    """Check if module matches a prefix (exact or dotted child)."""
    return module == prefix or module.startswith(prefix + ".")


# ──────────────────────────────────────────────────────────
# Cross-module boundary violation scanner
# ──────────────────────────────────────────────────────────

def _find_cross_module_violations(module_name: str) -> list[str]:
    """Scan a module for imports that reach into other modules' internals.

    Allowed cross-module imports:
      - src.modules.<other>.public  (the public API)

    Forbidden:
      - src.modules.<other>.domain.*
      - src.modules.<other>.application.*
      - src.modules.<other>.infrastructure.*
      - src.modules.<other>.presentation.*
      - src.modules.<other>.* (anything beyond public)
    """
    module_dir = MODULES_DIR / module_name
    own_prefix = f"src.modules.{module_name}"
    violations: list[str] = []

    for filepath in _collect_python_files(module_dir):
        rel = filepath.relative_to(PROJECT_ROOT).as_posix()
        for lineno, imported in _extract_imports(filepath):
            # Only check src.modules.* imports
            if not _matches_prefix(imported, "src.modules"):
                continue
            # Own module is always fine
            if _matches_prefix(imported, own_prefix):
                continue
            # Check each other module
            for other in MODULE_NAMES:
                if other == module_name:
                    continue
                other_prefix = f"src.modules.{other}"
                if not _matches_prefix(imported, other_prefix):
                    continue
                # Only src.modules.<other>.public is allowed
                if imported == f"src.modules.{other}.public":
                    continue
                if _matches_prefix(imported, f"src.modules.{other}.public"):
                    continue
                violations.append(
                    f"{rel}:{lineno} imports '{imported}' "
                    f"(must use 'src.modules.{other}.public' instead)"
                )

    return violations


def _find_domain_isolation_violations(module_name: str) -> list[str]:
    """Scan a module's domain layer for imports outside own domain + stdlib.

    Domain must be self-contained:
      - Own domain (src.modules.<module>.domain.*) is fine
      - Everything else from src.* is forbidden
    """
    domain_dir = MODULES_DIR / module_name / "domain"
    own_domain_prefix = f"src.modules.{module_name}.domain"
    forbidden_prefixes = [
        "src.modules",
        "src.shared",
        "src.core",
        "src.application",
        "src.infrastructure",
        "src.api",
        "src.models",
        "fastapi",
        "sqlalchemy",
        "pydantic",
    ]
    violations: list[str] = []

    for filepath in _collect_python_files(domain_dir):
        rel = filepath.relative_to(PROJECT_ROOT).as_posix()
        for lineno, imported in _extract_imports(filepath):
            # Own domain is always fine
            if _matches_prefix(imported, own_domain_prefix):
                continue
            # Check forbidden prefixes
            for prefix in forbidden_prefixes:
                if _matches_prefix(imported, prefix):
                    violations.append(
                        f"{rel}:{lineno} imports '{imported}' "
                        f"(domain must only use stdlib + own domain, "
                        f"forbidden prefix: '{prefix}')"
                    )

    return violations


def _has_real_exports(public_py: Path) -> bool:
    """Check if a public.py has at least one real export (def/class/__all__)."""
    source = public_py.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(public_py))
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    return True
    return False


# ──────────────────────────────────────────────────────────
# Tests: Cross-module boundary
# ──────────────────────────────────────────────────────────

class TestModuleBoundaries:
    """Ensure modules only access each other through public.py."""

    @pytest.mark.parametrize("module_name", MODULE_NAMES)
    def test_no_cross_module_internal_imports(self, module_name: str):
        """Module must not import other modules' internals directly."""
        violations = _find_cross_module_violations(module_name)
        if violations:
            msg = (
                f"Module '{module_name}' crosses module boundaries!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: use 'from src.modules.<other>.public import ...' instead."
            )
            pytest.fail(msg)


# ──────────────────────────────────────────────────────────
# Tests: Domain isolation within modules
# ──────────────────────────────────────────────────────────

class TestModuleDomainIsolation:
    """Ensure each module's domain layer has no external dependencies."""

    @pytest.mark.parametrize("module_name", MODULE_NAMES)
    def test_domain_is_self_contained(self, module_name: str):
        """Module domain must only import from own domain + stdlib."""
        violations = _find_domain_isolation_violations(module_name)
        if violations:
            msg = (
                f"Module '{module_name}' domain has external dependencies!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: domain must only use stdlib + own domain. "
                "Move framework-dependent code to application or infrastructure."
            )
            pytest.fail(msg)


# ──────────────────────────────────────────────────────────
# Tests: Module structure validation
# ──────────────────────────────────────────────────────────

class TestModuleStructure:
    """Ensure all modules have the required structure."""

    def test_modules_are_auto_discovered(self):
        """At least one module must exist under src/modules/."""
        assert len(MODULE_NAMES) > 0, (
            "No modules discovered under src/modules/. "
            "Expected at least one module directory."
        )

    @pytest.mark.parametrize("module_name", MODULE_NAMES)
    def test_module_has_public_api(self, module_name: str):
        """Each module must have a public.py file."""
        public_py = MODULES_DIR / module_name / "public.py"
        assert public_py.exists(), (
            f"Module '{module_name}' is missing public.py. "
            f"Expected: {public_py}"
        )

    @pytest.mark.parametrize("module_name", MODULE_NAMES)
    def test_module_has_required_layers(self, module_name: str):
        """Each module must have domain/application/infrastructure/presentation."""
        for layer in MODULE_INTERNAL_LAYERS:
            layer_dir = MODULES_DIR / module_name / layer
            init_file = layer_dir / "__init__.py"
            assert layer_dir.exists(), (
                f"Module '{module_name}' is missing '{layer}/' directory."
            )
            assert init_file.exists(), (
                f"Module '{module_name}/{layer}/' is missing __init__.py."
            )

    @pytest.mark.parametrize("module_name", MODULE_NAMES)
    def test_module_domain_has_real_files(self, module_name: str):
        """Each module domain must contain at least one real rule/entity file."""
        domain_dir = MODULES_DIR / module_name / "domain"
        assert domain_dir.exists(), f"{module_name}/domain/ directory is missing"

        real_files = [
            f for f in domain_dir.rglob("*.py")
            if f.name != "__init__.py"
        ]
        assert len(real_files) >= 1, (
            f"{module_name}/domain/ must have at least one real .py file "
            "besides __init__.py. The domain layer should contain pure business "
            "rules, value objects, or entities. Found none."
        )

    @pytest.mark.parametrize("module_name", MODULE_NAMES)
    def test_public_has_real_exports(self, module_name: str):
        """Each module's public.py must export at least one symbol."""
        public_py = MODULES_DIR / module_name / "public.py"
        if not public_py.exists():
            pytest.skip(f"No public.py for {module_name}")
        assert _has_real_exports(public_py), (
            f"Module '{module_name}' public.py has no real exports "
            f"(needs __all__, def, or class)."
        )
