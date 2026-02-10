# -*- coding: utf-8 -*-
"""Database configuration and session management."""

import importlib
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from src.core.config import get_settings

# Create Base class for declarative models
Base = declarative_base()

# Get settings
_settings = get_settings()


def _create_engine():
    """Create database engine based on database type.

    Returns:
        SQLAlchemy engine configured for SQLite or PostgreSQL
    """
    if _settings.is_sqlite:
        # SQLite: Create data directory and use check_same_thread
        db_path = Path(_settings.database_url.replace("sqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)

        return create_engine(
            _settings.database_url,
            connect_args={"check_same_thread": False},  # Needed for SQLite
            echo=_settings.debug,
        )
    elif _settings.is_postgresql:
        # PostgreSQL: Use pool settings for production
        return create_engine(
            _settings.database_url,
            echo=_settings.debug,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Enable connection health checks
        )
    else:
        # Fallback: Generic database URL (no special handling)
        return create_engine(
            _settings.database_url,
            echo=_settings.debug,
        )


# Create engine
engine = _create_engine()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get database session.

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_ORM_MODEL_MODULES: tuple[str, ...] = (
    "src.modules.workspace.infrastructure.persistence.models",
    "src.modules.conversation.infrastructure.persistence.models",
    "src.infrastructure.persistence.db_models",
)


def register_orm_models() -> None:
    """Register all SQLAlchemy model modules before metadata operations.

    Safe to call multiple times (import is idempotent).
    """
    for module_path in _ORM_MODEL_MODULES:
        importlib.import_module(module_path)


def init_db():
    """Initialize database tables."""
    register_orm_models()
    Base.metadata.create_all(bind=engine)
