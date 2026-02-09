# -*- coding: utf-8 -*-
"""
Architecture guard tests: enforce Clean Architecture layer boundaries.

These tests statically scan imports to prevent dependency violations.
If a test fails, it means someone introduced an import that crosses
a forbidden layer boundary.

Layer rules:
  ┌──────────────┐
  │   API (src/api)      │  → May import: application, models, core, domain
  │                      │  → Must NOT import: infrastructure (except DI container)
  ├──────────────┤
  │ Application          │  → May import: application, core, domain
  │ (src/application)    │  → Must NOT import: models, infrastructure, fastapi, sqlalchemy
  ├──────────────┤
  │ Infrastructure       │  → May import: application, core, domain, models.db_models
  │ (src/infrastructure) │  → Must NOT import: api, fastapi
  ├──────────────┤
  │ Domain (src/domain)  │  → May import: stdlib only
  │                      │  → Must NOT import: any src.* layer
  └──────────────┘
"""

import ast
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APPLICATION_DIR = PROJECT_ROOT / "src" / "application"
API_DIR = PROJECT_ROOT / "src" / "api"
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
# Application Layer Tests
# ──────────────────────────────────────────────────────────

# Forbidden import prefixes for the application layer.
APP_FORBIDDEN = [
    "src.models",
    "src.infrastructure",
    "fastapi",
    "sqlalchemy",
]
APP_EXCEPTIONS: set[str] = set()


class TestApplicationLayerBoundaries:
    """Ensure the application layer does not depend on outer layers."""

    def test_no_forbidden_imports_in_application_layer(self):
        """Application layer must not import from models, infrastructure,
        fastapi, or sqlalchemy."""
        violations = _find_violations(
            APPLICATION_DIR, APP_FORBIDDEN, APP_EXCEPTIONS,
        )
        if violations:
            msg = (
                "Application layer boundary violations detected!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: move the dependency behind a port/DTO, "
                "or perform the conversion in the API/infrastructure layer."
            )
            pytest.fail(msg)

    @pytest.mark.parametrize("prefix", APP_FORBIDDEN)
    def test_individual_forbidden_prefix(self, prefix: str):
        """Granular check per forbidden prefix for clearer failure messages."""
        violations = _find_violations(
            APPLICATION_DIR, [prefix], APP_EXCEPTIONS,
        )
        if violations:
            msg = (
                f"Application layer imports from '{prefix}':\n\n"
                + "\n".join(f"  - {v}" for v in violations)
            )
            pytest.fail(msg)


# ──────────────────────────────────────────────────────────
# API Layer Tests
# ──────────────────────────────────────────────────────────

# API must not reach directly into infrastructure, except via DI container.
API_FORBIDDEN = ["src.infrastructure"]
API_ALLOWED = ["src.infrastructure.di.container"]
API_EXCEPTIONS: set[str] = set()


class TestApiLayerBoundaries:
    """Ensure the API layer only reaches infrastructure through DI."""

    def test_api_does_not_import_infrastructure_directly(self):
        """API layer must not import from src.infrastructure,
        except src.infrastructure.di.container for wiring."""
        violations = _find_violations(
            API_DIR, API_FORBIDDEN, API_EXCEPTIONS,
            allowed_prefixes=API_ALLOWED,
        )
        if violations:
            msg = (
                "API layer imports infrastructure directly!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: inject dependencies via DI container or ports."
            )
            pytest.fail(msg)


# ──────────────────────────────────────────────────────────
# Infrastructure Layer Tests
# ──────────────────────────────────────────────────────────

# Infrastructure must not import from API layer, web frameworks, or presentation models.
# src.models.db_models is allowed (infrastructure owns persistence).
INFRA_FORBIDDEN = ["src.api", "fastapi", "src.models"]
INFRA_ALLOWED = ["src.models.db_models"]
# Existing violations registered for gradual resolution:
INFRA_EXCEPTIONS: set[str] = {
    "src/infrastructure/persistence/audio_repository.py",
    "src/infrastructure/persistence/trash_repository.py",
    "src/infrastructure/external/tts/tts_service.py",
    "src/infrastructure/external/youtube/youtube_service.py",
    "src/infrastructure/external/adapters.py",
}


class TestInfrastructureLayerBoundaries:
    """Ensure infrastructure does not depend on API/presentation layers."""

    def test_infrastructure_does_not_import_api(self):
        """Infrastructure must not import from src.api, fastapi, or src.models (except db_models)."""
        violations = _find_violations(
            INFRASTRUCTURE_DIR, INFRA_FORBIDDEN, INFRA_EXCEPTIONS,
            allowed_prefixes=INFRA_ALLOWED,
        )
        if violations:
            msg = (
                "Infrastructure layer imports API/web framework!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: infrastructure should only depend on "
                "application ports and domain."
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
